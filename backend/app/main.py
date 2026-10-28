import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.composer import AnswerResult
from agents.pipeline import PipelineError, answer, new_thread
from app.config import get_settings
from governance.policy import ACCESS_POLICY, AccessDenied

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
