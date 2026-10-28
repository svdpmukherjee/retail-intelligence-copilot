import httpx
from pydantic import BaseModel

from agents.llm import get_llm
from app.cost import CostLedger
from governance.grounding import CITE, enforce_grounding
from governance.pii import redact
from memory.manager import MemoryContext
from retrieval.embeddings import GoAheadRequired
from retrieval.schema import SearchHit

SQL_SOURCE = "sql"
MAX_QUOTE_CHARS = 240
MAX_SQL_ROWS_SHOWN = 10

SYSTEM_PROMPT = (
    "Answer the question using ONLY the numbered sources. Write one claim per line; every line "
    "must end with an inline citation like [1] naming the source(s) it relies on. Do not cite "
    "numbers that are not listed. If the sources do not answer the question, say so."
)


class Citation(BaseModel):
    n: int
    source_id: str  # chunk id, or "sql" for the SQL result
    label: str


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    audit: dict


def _label(hit: SearchHit) -> str:
    c = hit.chunk
    if c.source_type == "doc":
        return f"{c.doc_title or c.doc_id} / {c.section}" if c.section else str(c.doc_title)
    return f"review {c.asin} ({c.category})"


def _sql_text(sql_result: dict) -> str:
    cols, rows = sql_result["columns"], sql_result["rows"]
    shown = "; ".join(
        ", ".join(f"{c}={v}" for c, v in zip(cols, row, strict=False))
        for row in rows[:MAX_SQL_ROWS_SHOWN]
    )
    return shown or "no rows"


def build_sources(sql_result: dict | None, hits: list[SearchHit]) -> list[tuple[Citation, str]]:
    """Numbered evidence from the tools; the only things an answer is allowed to cite."""
    sources: list[tuple[Citation, str]] = []
    if sql_result is not None:
        sources.append(
            (Citation(n=1, source_id=SQL_SOURCE, label="SQL result"), _sql_text(sql_result))
        )
    for hit in hits:
        cite = Citation(n=len(sources) + 1, source_id=hit.chunk.id, label=_label(hit))
        sources.append((cite, hit.chunk.text))
    return sources


def _extractive(sources: list[tuple[Citation, str]]) -> str:
    lines = []
    for cite, text in sources:
        quote = " ".join(text.split())[:MAX_QUOTE_CHARS]
        lines.append(f"{cite.label}: {quote} [{cite.n}]")
    return "\n".join(lines)


async def compose(
    query: str,
    sql_result: dict | None,
    hits: list[SearchHit],
    ledger: CostLedger,
    *,
    context: MemoryContext | None = None,
) -> AnswerResult:
    """Cited answer: LLM when available, else extractive; uncited output never leaves here."""
    sources = build_sources(sql_result, hits)
    citations = [c for c, _ in sources]
    grounding: dict = {"path": "extractive", "issues": []}
    if not sources:
        answer = "No supporting evidence was found for this question."
        grounding["path"] = "none"
        return AnswerResult(answer=answer, citations=[], audit={"grounding": grounding})

    answer = _extractive(sources)
    llm = get_llm()
    if llm.available:
        listing = "\n".join(f"[{c.n}] ({c.label}) {' '.join(t.split())}" for c, t in sources)
        user = f"Question: {query}\n\nSources:\n{listing}"
        if context is not None and (block := context.render()):
            user = f"{block}\n\n{user}"
        try:
            draft = await llm.complete(SYSTEM_PROMPT, user, ledger=ledger)
        except (httpx.HTTPError, RuntimeError, GoAheadRequired) as exc:
            grounding["issues"].append(f"llm unavailable: {type(exc).__name__}")
        else:
            issues = enforce_grounding(draft, {c.n for c in citations})
            if issues:
                # Blocked: keep the grounded extractive answer, record why the draft was rejected.
                grounding["issues"] = ["llm draft blocked", *issues]
            else:
                answer, grounding["path"] = draft.strip(), "llm"
    # Generation-time scrub: whatever the LLM echoed, PII never reaches the user.
    answer = redact(answer)
    used = {int(m) for m in CITE.findall(answer)}
    return AnswerResult(
        answer=answer,
        citations=[c for c in citations if c.n in used],
        audit={"grounding": grounding},
    )
