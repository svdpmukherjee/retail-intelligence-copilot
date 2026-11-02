from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel

from agents.llm import LLM, get_llm
from agents.model_policy import model_for
from app.cost import CostLedger
from governance.grounding import CITE, enforce_grounding
from governance.pii import redact
from memory.manager import MemoryContext
from retrieval.embeddings import GoAheadRequired
from retrieval.schema import SearchHit

SQL_SOURCE = "sql"
SQL_DISPLAY_LABEL = "Calculated from your data"
MAX_QUOTE_CHARS = 240
# A chat answer is a summary, not a data export: show a readable head of the result and let
# SqlBlock.total_rows drive a "showing X of Y" note when the query returned more. (A query can
# still return up to sql_agent.MAX_ROWS; the UI never renders a hundred-row wall in the thread.)
MAX_SQL_ROWS_SHOWN = 25
SQL_FLOAT_DECIMALS = 2

SYSTEM_PROMPT = (
    "You are answering a retail manager who is not technical. Use ONLY the numbered sources below. "
    "Lead with a one- or two-sentence plain-language answer to the question — the key takeaway in "
    "the reader's words, with no jargon, no raw IDs and no verbatim quotes. Then give a few short "
    "supporting points, grouping what customers say into themes rather than listing individual "
    "reviews. End every point that states a specific fact, number or customer claim with an inline "
    "citation like [1] (use [1][2] for several) naming the source(s) it comes from. Never cite a "
    "number that is not listed and never invent a figure. If the sources do not answer the "
    "question, say so plainly in one sentence."
)


class Citation(BaseModel):
    n: int
    source_id: str  # chunk id, or "sql" for the SQL result
    label: str
    display_label: str  # plain-language chip text for the UI; built from titles/category only
    snippet: str | None = None  # redacted excerpt of the source text, for the UI


class SqlBlock(BaseModel):
    """The exact SQL result behind citation [1]; the UI renders it, never re-parses prose."""

    sql: str
    columns: list[str]
    rows: list[list]
    total_rows: (
        int  # rows the query returned before display truncation; UI shows "X of Y" when > len(rows)
    )


class AnswerResult(BaseModel):
    # "clarification" is a turn where the copilot asks the user a question instead of answering
    # (too vague, or data we do not have); the UI renders it as a question, with no sources.
    kind: Literal["answer", "clarification"] = "answer"
    answer: str
    citations: list[Citation]
    audit: dict
    sql: SqlBlock | None = None  # set only when the SQL citation survives into `citations`


def clarification(question: str, audit: dict) -> "AnswerResult":
    """A turn that asks the user a question rather than answering — no evidence, no citations."""
    return AnswerResult(kind="clarification", answer=question, citations=[], audit=audit)


def _label(hit: SearchHit) -> str:
    c = hit.chunk
    if c.source_type == "doc":
        return f"{c.doc_title or c.doc_id} / {c.section}" if c.section else str(c.doc_title)
    return f"review {c.asin} ({c.category})"


def _humanize(text: str) -> str:
    """Underscores/hyphens to spaces, title-cased only when the text is a raw slug."""
    spaced = text.replace("_", " ").replace("-", " ").strip()
    return spaced.title() if spaced.islower() or spaced != text else spaced


def _display_label(hit: SearchHit) -> str:
    """Reader-facing source name: never an ASIN, chunk id, slug or filename, nor review text."""
    c = hit.chunk
    if c.source_type == "doc":
        title = _humanize(c.doc_title or c.doc_id or "Policy document")
        return f"{title} · {_humanize(c.section)}" if c.section else title
    category = _humanize(c.category).replace(" And ", " and ") if c.category else ""
    return f"customer review · {category}" if category else "customer review"


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


def _truncate(text: str) -> str:
    """Cap display text at MAX_QUOTE_CHARS on a word boundary, marking the cut with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= MAX_QUOTE_CHARS:
        return text
    window = text[:MAX_QUOTE_CHARS]
    # A single token longer than the cap (e.g. a URL) has no boundary to back off to: hard cut.
    cut = window.rsplit(" ", 1)[0] if " " in window else window
    return cut + "…"


def _snippet(text: str) -> str | None:
    return redact(_truncate(text)) if text else None


def build_sources(sql_result: dict | None, hits: list[SearchHit]) -> list[tuple[Citation, str]]:
    """Numbered evidence from the tools; the only things an answer is allowed to cite."""
    sources: list[tuple[Citation, str]] = []
    if sql_result is not None:
        text = _sql_text(sql_result)
        cite = Citation(
            n=1,
            source_id=SQL_SOURCE,
            label="SQL result",
            display_label=SQL_DISPLAY_LABEL,
            snippet=_snippet(text),
        )
        sources.append((cite, text))
    for hit in hits:
        cite = Citation(
            n=len(sources) + 1,
            source_id=hit.chunk.id,
            label=_label(hit),
            display_label=_display_label(hit),
            snippet=_snippet(hit.chunk.text),
        )
        sources.append((cite, hit.chunk.text))
    return sources


def _extractive(sources: list[tuple[Citation, str]]) -> str:
    """Last-resort answer when no LLM can synthesise: the sources' own words, cited. Uses the
    reader-facing display label (never a raw ASIN/chunk id), so even the fallback stays readable."""
    lines = []
    for cite, text in sources:
        quote = _truncate(text)
        lines.append(f"{cite.display_label}: {quote} [{cite.n}]")
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
    # Synthesis is the answer the user reads: the strong default model (model_for -> None).
    llm = llm or get_llm(model=model_for("compose"))
    if llm.available:
        listing = "\n".join(f"[{c.n}] ({c.label}) {' '.join(t.split())}" for c, t in sources)
        user = f"Question: {query}\n\nSources:\n{listing}"
        if context is not None and (block := context.render()):
            user = f"{block}\n\n{user}"
        try:
            draft = await llm.complete(SYSTEM_PROMPT, user, ledger=ledger, task="compose")
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
