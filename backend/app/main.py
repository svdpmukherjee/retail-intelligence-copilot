import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.composer import AnswerResult
from agents.pipeline import PipelineError, answer, new_thread
from app.config import get_settings
from governance.policy import ACCESS_POLICY, AccessDenied
from memory.schema import RoleKind, ThreadListRow
from memory.store import get_memory_store

app = FastAPI(title="Retail Customer Intelligence Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_methods=["GET", "POST"],
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
            turns=[TurnOut(turn=r.turn, role_kind=r.role_kind, content=r.content) for r in rows],
        )

    try:
        detail = await asyncio.to_thread(load)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Conversation history unavailable") from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return detail
