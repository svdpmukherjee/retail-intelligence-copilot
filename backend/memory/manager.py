from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from agents.llm import get_llm
from app.config import get_settings
from app.cost import CostLedger
from governance.pii import redact
from governance.policy import scope_for_role
from memory.store import MemoryStore, get_memory_store

if TYPE_CHECKING:  # composer imports MemoryContext from here; runtime import would be circular
    from agents.composer import AnswerResult

MAX_TURN_CHARS = 400
MAX_ITEMS_SHOWN = 5
MAX_SUMMARY_CHARS = 300
SUMMARY_SENTENCES = 2

PREFERENCE_RE = re.compile(
    r"\b(?:i prefer|i like|please always|always (?:show|give|use|answer)|"
    r"from now on)\b[^.!?\n]*",
    re.IGNORECASE,
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
CITATION_RE = re.compile(r"\s*\[\d+\]")
SUMMARY_SYSTEM = (
    "Summarise this question and answer as one short factual finding for later reference. "
    "Use only the given answer; do not add facts."
)


class Turn(BaseModel):
    role_kind: Literal["user", "assistant"]
    content: str


class MemoryContext(BaseModel):
    """Per-query memory. Prompt context only: never a citable source."""

    thread_id: str
    history: list[Turn] = []
    preferences: list[str] = []
    prior_findings: list[str] = []

    def render(self) -> str:
        """Short bounded text block; empty string when there is nothing to show."""
        cap = get_settings().memory_history_turns
        sections: list[str] = []
        if self.preferences:
            items = "\n".join(f"- {p}" for p in self.preferences[:MAX_ITEMS_SHOWN])
            sections.append(f"User preferences:\n{items}")
        if self.prior_findings:
            items = "\n".join(f"- {f}" for f in self.prior_findings[:MAX_ITEMS_SHOWN])
            sections.append(f"Earlier findings (context only, not citable):\n{items}")
        if self.history and cap > 0:
            lines = "\n".join(
                f"{t.role_kind}: {' '.join(t.content.split())[:MAX_TURN_CHARS]}"
                for t in self.history[-cap:]
            )
            sections.append(f"Conversation so far:\n{lines}")
        if not sections:
            return ""
        return "Conversation memory (background only; cite only the numbered sources):\n" + (
            "\n\n".join(sections)
        )


class MemoryManager:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or get_memory_store()

    def load(self, thread_id: str, user_id: str, role: str, *, limit: int) -> MemoryContext:
        """History is read with user_id so a non-owner gets nothing; unknown thread is empty.
        Findings are filtered in SQL by the role's scope; an unknown role raises AccessDenied."""
        role_scope = scope_for_role(role)
        n = min(limit, get_settings().memory_history_turns)
        messages = self._store.recent_messages(thread_id, n, user_id=user_id) if n > 0 else []
        return MemoryContext(
            thread_id=thread_id,
            history=[Turn(role_kind=m.role_kind, content=m.content) for m in messages],
            preferences=[
                r.content for r in self._store.list_memory(user_id, kind="preference", limit=n)
            ],
            prior_findings=[
                r.content
                for r in self._store.list_memory(user_id, kind="finding", limit=n, scope=role_scope)
            ],
        )

    async def persist(
        self,
        thread_id: str,
        user_id: str,
        role: str,
        query: str,
        result: AnswerResult,
        ledger: CostLedger,
        *,
        scope: dict,
    ) -> int:
        """Append the turn, then store <=1 finding and any stated preference. Returns the count
        of durable memory items written (messages are not counted)."""
        settings = get_settings()
        if not settings.memory_enabled:
            return 0
        scope_for_role(role)  # deny-by-default: an unknown role writes nothing
        self._store.append_message(thread_id, "user", self._redact(query), user_id=user_id)
        self._store.append_message(
            thread_id, "assistant", self._redact(result.answer), user_id=user_id
        )
        persisted = 0
        if result.answer.strip() and result.citations:
            summary = await self._summarise(query, result, ledger)
            sources = ", ".join(result.audit.get("sources", []))
            intent = result.audit.get("intent", "unknown")
            finding = f"{summary} [intent: {intent}; sources: {sources}]"
            self._store.add_memory(user_id, "finding", self._redact(finding), scope)
            persisted += 1
        for preference in self._preferences(query):
            self._store.add_memory(user_id, "preference", self._redact(preference), scope)
            persisted += 1
        if persisted:
            self._store.trim_memory(user_id, settings.memory_max_items)
        return persisted

    async def _summarise(self, query: str, result: AnswerResult, ledger: CostLedger) -> str:
        llm = get_llm()
        if llm.available:
            try:
                text = await llm.complete(
                    SUMMARY_SYSTEM,
                    f"Question: {query}\n\nAnswer: {result.answer}",
                    ledger=ledger,
                    max_tokens=get_settings().memory_summary_max_tokens,
                )
                if text.strip():
                    return " ".join(text.split())[:MAX_SUMMARY_CHARS]
            except Exception:  # cap breach / gate / endpoint down: memory must not fail the turn
                pass
        return self._deterministic_summary(result.answer)

    @staticmethod
    def _deterministic_summary(answer: str) -> str:
        """First grounded sentences of the answer, citation markers stripped, truncated. $0."""
        plain = CITATION_RE.sub("", " ".join(answer.split()))
        sentences = SENTENCE_RE.split(plain)[:SUMMARY_SENTENCES]
        return " ".join(sentences)[:MAX_SUMMARY_CHARS]

    @staticmethod
    def _preferences(query: str) -> list[str]:
        return [m.group(0).strip() for m in PREFERENCE_RE.finditer(query)][:1]

    @staticmethod
    def _redact(text: str) -> str:
        return redact(text)
