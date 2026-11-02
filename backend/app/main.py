import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.composer import AnswerResult
from agents.pipeline import PipelineError, answer, new_thread
from app.config import get_settings
from governance.audit import DEFAULT_LIMIT, MAX_LIMIT, get_audit_store
from governance.policy import ACCESS_POLICY, AccessDenied
from memory.schema import RoleKind, ThreadListRow
from memory.store import get_memory_store
from observability.tracing import get_tracer

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    try:  # flush buffered spans so a clean shutdown does not drop them
        await asyncio.to_thread(get_tracer().flush)
    except Exception as exc:
        log.warning("tracer flush failed: %s", type(exc).__name__)


app = FastAPI(title="Retail Customer Intelligence Copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        settings = get_settings()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Configuration is invalid") from exc
    return {"status": "ok", "provider_mode": settings.provider_mode}


@app.get("/roles")
async def roles() -> dict[str, list[str]]:
    return {"roles": list(ACCESS_POLICY)}


class QueryRequest(BaseModel):
    query: str
    role: str
    thread_id: str | None = None
    user_id: str | None = None


class QueryResponse(AnswerResult):
    thread_id: str | None = None
    user_id: str | None = None


@app.post("/query")
async def query(req: QueryRequest) -> QueryResponse:
    if req.role not in ACCESS_POLICY:
        raise HTTPException(status_code=400, detail=f"Unknown role: {req.role!r}")
    thread_id = req.thread_id
    try:
        if req.user_id and not thread_id:
            try:
                thread_id = await asyncio.to_thread(new_thread, req.user_id, req.role)
            except Exception:  # memory is optional: no thread means a plain single-shot answer
                thread_id = None
        result = await answer(req.query, req.role, thread_id=thread_id, user_id=req.user_id)
        return QueryResponse(**result.model_dump(), thread_id=thread_id, user_id=req.user_id)
    except AccessDenied as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PipelineError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream failure: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Query failed") from exc


class ThreadListResponse(BaseModel):
    threads: list[ThreadListRow]


class TurnOut(BaseModel):
    turn: int
    role_kind: RoleKind
    content: str
    payload: dict[str, Any] | None = None  # assistant render snapshot for full replay


class ThreadDetailResponse(BaseModel):
    thread_id: str
    role: str
    turns: list[TurnOut]


_MAX_RESUME_TURNS = 200


@app.get("/threads")
async def list_threads(
    user_id: str = Query(min_length=1), role: str = Query(min_length=1)
) -> ThreadListResponse:
    if role not in ACCESS_POLICY:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role!r}")
    try:
        threads = await asyncio.to_thread(get_memory_store().list_threads, user_id, role)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conversation history unavailable") from exc
    return ThreadListResponse(threads=threads)


@app.get("/threads/{thread_id}")
async def thread_detail(thread_id: str, user_id: str = Query(min_length=1)) -> ThreadDetailResponse:
    def load() -> ThreadDetailResponse | None:
        store = get_memory_store()
        thread = store.get_thread(thread_id, user_id)
        if thread is None:
            return None
        rows = store.recent_messages(thread_id, _MAX_RESUME_TURNS, user_id=user_id)
        return ThreadDetailResponse(
            thread_id=thread.id,
            role=thread.role,
            turns=[
                TurnOut(turn=r.turn, role_kind=r.role_kind, content=r.content, payload=r.payload)
                for r in rows
            ],
        )

    try:
        detail = await asyncio.to_thread(load)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conversation history unavailable") from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return detail


class DeleteResult(BaseModel):
    deleted: int  # threads removed (0 or 1 for a single thread; N for clear-all)


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, user_id: str = Query(min_length=1)) -> DeleteResult:
    """Permanently delete one conversation (owner-scoped). The caller confirms in the UI first."""
    try:
        removed = await asyncio.to_thread(
            get_memory_store().delete_thread, thread_id, user_id
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conversation history unavailable") from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Thread not found")
    return DeleteResult(deleted=1)


@app.delete("/threads")
async def delete_all_threads(
    user_id: str = Query(min_length=1), role: str = Query(min_length=1)
) -> DeleteResult:
    """Permanently delete every conversation this user holds under `role`. UI warns first."""
    if role not in ACCESS_POLICY:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role!r}")
    try:
        removed = await asyncio.to_thread(
            get_memory_store().delete_all_threads, user_id, role
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conversation history unavailable") from exc
    return DeleteResult(deleted=removed)


class AuditRow(BaseModel):
    id: int
    created_at: datetime
    query: str
    role: str
    user_id: str | None = None
    intent: str | None
    model: str | None = None
    answer: str | None = None
    tool_path: list[Any]
    sources: list[Any]
    llm_calls: list[Any] = []
    routing: list[Any] = []
    tokens: int
    cost_usd: float
    latency_ms: float
    grounding: dict[str, Any] | None
    memory: dict[str, Any] | None


class AuditListResponse(BaseModel):
    items: list[AuditRow]
    total: int
    limit: int
    offset: int


def _require_admin(role: str) -> None:
    """Server-side gate for the operator plane; runs before any audit data is read."""
    if role not in ACCESS_POLICY:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role!r}")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Audit log is admin-only")


@app.get("/audit")
async def list_audit(
    role: str = Query(min_length=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> AuditListResponse:
    _require_admin(role)

    def load() -> AuditListResponse:
        store = get_audit_store()
        return AuditListResponse(
            items=[AuditRow(**r) for r in store.list_recent(limit, offset)],
            total=store.count(),
            limit=limit,
            offset=offset,
        )

    try:
        return await asyncio.to_thread(load)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Audit log unavailable") from exc


@app.get("/audit/{audit_id}")
async def audit_detail(audit_id: int, role: str = Query(min_length=1)) -> AuditRow:
    _require_admin(role)
    try:
        row = await asyncio.to_thread(get_audit_store().get, audit_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Audit log unavailable") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Audit record not found")
    return AuditRow(**row)
