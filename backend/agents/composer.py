from decimal import Decimal

import httpx
from pydantic import BaseModel

from agents.llm import LLM, get_llm
from agents.sql_agent import MAX_ROWS
from app.cost import CostLedger
from governance.grounding import CITE, enforce_grounding
from governance.pii import redact
from memory.manager import MemoryContext
from retrieval.embeddings import GoAheadRequired
from retrieval.schema import SearchHit

SQL_SOURCE = "sql"
MAX_QUOTE_CHARS = 240
# Match the SQL query's own row bound (sql_agent.MAX_ROWS): the result set is already capped
# there, so the display must never drop a row the query kept. SqlBlock.total_rows lets the UI
# say "showing X of Y" on the rare case a query actually hits that bound.
MAX_SQL_ROWS_SHOWN = MAX_ROWS
SQL_FLOAT_DECIMALS = 2

SYSTEM_PROMPT = (
    "Answer the question using ONLY the numbered sources. Write one claim per line; every line "
    "must end with an inline citation like [1] naming the source(s) it relies on. Do not cite "
    "numbers that are not listed. If the sources do not answer the question, say so."
)


class Citation(BaseModel):
    n: int
    source_id: str  # chunk id, or "sql" for the SQL result
    label: str
    snippet: str | None = None  # redacted excerpt of the source text, for the UI


class SqlBlock(BaseModel):
    """The exact SQL result behind citation [1]; the UI renders it, never re-parses prose."""

    sql: str
    columns: list[str]
    rows: list[list]
    total_rows: int  # rows the query returned before display truncation; UI shows "X of Y" when > len(rows)


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    audit: dict
    sql: SqlBlock | None = None  # set only when the SQL citation survives into `citations`


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
    if len(rows) > MAX_SQL_ROWS_SHOWN:
        shown += f" (showing first {MAX_SQL_ROWS_SHOWN} of {len(rows)})"
    return shown or "no rows"


def _cell(value):
    if isinstance(value, Decimal):
        value = float(value)  # JSON-safe number; DuckDB aggregates can return DECIMAL
    if isinstance(value, float):
        return round(value, SQL_FLOAT_DECIMALS)
    return redact(value) if isinstance(value, str) else value


def _sql_block(sql_result: dict) -> SqlBlock:
    all_rows = sql_result["rows"]
    rows = [[_cell(v) for v in row] for row in all_rows[:MAX_SQL_ROWS_SHOWN]]
    return SqlBlock(
        sql=sql_result.get("sql", ""),
        columns=sql_result["columns"],
        rows=rows,
        total_rows=len(all_rows),
    )


def _snippet(text: str) -> str | None:
    return redact(" ".join(text.split())[:MAX_QUOTE_CHARS]) if text else None


def build_sources(sql_result: dict | None, hits: list[SearchHit]) -> list[tuple[Citation, str]]:
    """Numbered evidence from the tools; the only things an answer is allowed to cite."""
    sources: list[tuple[Citation, str]] = []
    if sql_result is not None:
        text = _sql_text(sql_result)
        cite = Citation(n=1, source_id=SQL_SOURCE, label="SQL result", snippet=_snippet(text))
        sources.append((cite, text))
    for hit in hits:
        cite = Citation(
            n=len(sources) + 1,
            source_id=hit.chunk.id,
            label=_label(hit),
            snippet=_snippet(hit.chunk.text),
        )
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
    llm: LLM | None = None,
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
    llm = llm or get_llm()
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
    kept = [c for c in citations if c.n in used]
    sql_cited = sql_result is not None and any(c.source_id == SQL_SOURCE for c in kept)
    return AnswerResult(
        answer=answer,
        citations=kept,
        audit={"grounding": grounding},
        sql=_sql_block(sql_result) if sql_cited else None,
    )
