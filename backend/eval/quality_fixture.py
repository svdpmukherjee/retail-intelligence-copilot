"""Bounded adapters for baseline contracts, NOT a model/retrieval-quality simulation."""

import json
import math
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import duckdb

from app.cost import CostLedger
from retrieval.chunking import chunk_doc, chunk_review
from retrieval.schema import SearchHit

FIXTURE = Path(__file__).parent / "ground_truth" / "quality_fixture.json"
POLICY = Path(__file__).resolve().parents[2] / "data/docs/authored/return-refund-policy.md"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def words(text: str) -> Counter:
    return Counter(re.findall(r"[a-z]+", text.lower()))


class FixtureEmbedder:
    """Authored bag-of-words vectors; no pretrained embeddings or network."""

    def __init__(self, chunks: list) -> None:
        self.vocab = sorted({w for c in chunks for w in words(c.text)})

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            counts = words(text)
            vector = [float(counts[w]) for w in self.vocab]
            norm = math.sqrt(sum(v * v for v in vector)) or 1
            vectors.append([v / norm for v in vector])
        return vectors


class FixtureStore:
    """In-memory source/permission filters; real hybrid fusion runs above these adapters."""

    def __init__(self, fixture: dict) -> None:
        self.chunks = [chunk_review(row) for row in fixture["rows"]]
        self.chunks += chunk_doc("authored/return-refund-policy", POLICY.read_text())
        self.embedder = FixtureEmbedder(self.chunks)
        self.vectors = self.embedder.embed([c.text for c in self.chunks])

    def _filtered(self, filters: dict) -> list:
        return [
            (c, v)
            for c, v in zip(self.chunks, self.vectors, strict=True)
            if all(
                getattr(c, k) in (value if isinstance(value, list) else [value])
                for k, value in (filters or {}).items()
            )
        ]

    def query(self, vector: list, k: int, *, filters: dict) -> list:
        hits = [
            SearchHit(chunk=c, score=sum(a * b for a, b in zip(vector, v, strict=True)))
            for c, v in self._filtered(filters)
        ]
        return sorted(hits, key=lambda h: (-h.score, h.chunk.id))[:k]

    def keyword_query(self, query: str, k: int, *, filters: dict) -> list:
        terms = set(words(query))
        hits = [
            SearchHit(chunk=c, score=float(len(terms & set(words(c.text)))))
            for c, _ in self._filtered(filters)
            if terms & set(words(c.text))
        ]
        return sorted(hits, key=lambda h: (-h.score, h.chunk.id))[:k]


class FixtureLLM:
    """Scripted SQL/route/source echo. Success here never establishes live synthesis quality."""

    available = True
    model = "scripted-fixture"

    async def complete(
        self,
        system: str,
        user: str,
        *,
        ledger: CostLedger,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> str:
        if task == "route":
            return json.dumps({"intent": "review_rag", "rationale": "scripted fixture route"})
        if task == "sql":
            question = user.lower()
            if "unknowncategory" in question:
                return "SELECT asin FROM structured WHERE category = 'UnknownCategory'"
            if "average" in question:
                return (
                    "SELECT category, AVG(rating) AS avg_rating "
                    "FROM structured GROUP BY category ORDER BY category"
                )
            if "lowest" in question:
                category = "Toys_and_Games" if "toys" in question else "Electronics"
                return (
                    "SELECT asin, AVG(rating) AS avg_rating FROM structured "
                    f"WHERE category = '{category}' GROUP BY asin "
                    "HAVING COUNT(*) >= 2 ORDER BY avg_rating, asin LIMIT 1"
                )
            return (
                "SELECT asin, COUNT(*) AS review_count FROM structured "
                "GROUP BY asin ORDER BY review_count DESC, asin"
            )
        if task == "summary":
            return "Synthetic finding; not live model evidence."
        # Echo only numbered source bodies. This deliberately does not manufacture a good answer.
        if "<source_data>" in user:
            payload = user.split("<source_data>", 1)[1].split("</source_data>", 1)[0]
            return "\n".join(f"{s['text']} [{s['citation']}]" for s in json.loads(payload))
        listing = user.split("Sources:\n", 1)[-1]
        lines = []
        for line in listing.splitlines():
            if match := re.match(r"\[(\d+)\] \([^)]*\) (.*)", line):
                lines.append(f"{match[2]} [{match[1]}]")
        return "\n".join(lines)


def fixture_connection(fixture: dict, scope: dict | None) -> duckdb.DuckDBPyConnection:
    """A real DuckDB SELECT executes over authored rows, never a serving Delta table."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE structured (asin VARCHAR, category VARCHAR, rating DOUBLE, "
        "year INTEGER, timestamp VARCHAR, product_title VARCHAR)"
    )
    categories = (scope or {}).get("category")
    rows = [
        r
        for r in fixture["rows"]
        if categories is None
        or r["category"] in ([categories] if isinstance(categories, str) else categories)
    ]
    if rows:
        conn.executemany(
            "INSERT INTO structured VALUES (?, ?, ?, ?, ?, ?)",
            [
                [r[k] for k in ("asin", "category", "rating", "year", "timestamp", "product_title")]
                for r in rows
            ],
        )
    conn.execute("SET enable_external_access = false")
    return conn


class EphemeralMemoryStore:
    """Storage adapter only; production MemoryManager still loads, resolves and persists turns."""

    def __init__(self) -> None:
        self.messages = {}
        self.items = {}

    def recent_messages(
        self,
        thread_id: str,
        limit: int,
        *,
        user_id: str | None = None,
    ) -> list[SimpleNamespace]:
        return self.messages.get((user_id, thread_id), [])[-limit:]

    def append_message(
        self,
        thread_id: str,
        role_kind: str,
        content: str,
        *,
        user_id: str,
        payload: dict | None = None,
    ) -> None:
        self.messages.setdefault((user_id, thread_id), []).append(
            SimpleNamespace(role_kind=role_kind, content=content, payload=payload)
        )

    def list_memory(
        self,
        user_id: str,
        *,
        kind: str,
        limit: int,
        scope: dict | None = None,
    ) -> list:
        # Findings are intentionally empty: baseline focuses on within-thread resolution.
        return []

    def add_memory(self, user_id: str, kind: str, content: str, scope: dict) -> None:
        self.items.setdefault(user_id, []).append((kind, content, scope))

    def trim_memory(self, user_id: str, limit: int) -> None:
        self.items[user_id] = self.items.get(user_id, [])[-limit:]
