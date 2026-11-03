import asyncio
import sys
from contextlib import contextmanager

import pytest

from app.config import get_settings
from observability.tracing import NoOpTracer, _safe, get_tracer


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    for key in ("OBSERVABILITY_ENABLED", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    get_tracer.cache_clear()
    yield
    get_settings.cache_clear()
    get_tracer.cache_clear()


def _flip(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    get_tracer.cache_clear()


def test_default_is_noop():
    assert isinstance(get_tracer(), NoOpTracer)


def test_enabled_without_keys_is_noop(monkeypatch):
    _flip(monkeypatch, OBSERVABILITY_ENABLED="true")
    assert isinstance(get_tracer(), NoOpTracer)


def test_keys_without_flag_is_noop(monkeypatch):
    _flip(monkeypatch, LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk")
    assert isinstance(get_tracer(), NoOpTracer)


def test_enabled_and_keyed_falls_back_when_langfuse_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "langfuse", None)  # forces ImportError
    _flip(
        monkeypatch,
        OBSERVABILITY_ENABLED="true",
        LANGFUSE_PUBLIC_KEY="pk",
        LANGFUSE_SECRET_KEY="sk",
    )
    assert isinstance(get_tracer(), NoOpTracer)


def test_noop_trace_span_flush_cycle_runs_cleanly():
    tracer = get_tracer()
    trace = tracer.start_trace("query", metadata={"role": "analyst"})
    with trace.span("route", metadata={"intent": "sql"}) as span:
        span.update({"latency_ms": 1.5, "tokens": 10, "cost_usd": 0.0})
    trace.end({"tool_path": "sql_agent"})
    tracer.flush()


def test_metadata_drops_text_and_non_scalars():
    cleaned = _safe({"role": "analyst", "query": "my secret", "tokens": 3, "obj": [1]})
    assert cleaned == {"role": "analyst", "tokens": 3}


class _FakeSpan:
    def __init__(self, name):
        self.name, self.meta, self.input, self.output = name, {}, None, None

    def update(self, metadata=None, *, input=None, output=None):
        self.meta.update(metadata or {})
        if input is not None:
            self.input = input
        if output is not None:
            self.output = output


class _FakeTrace:
    def __init__(self, metadata, input=None):
        self.metadata, self.spans, self.ended = dict(metadata), [], None
        self.input, self.output = input, None

    @contextmanager
    def span(self, name, *, metadata=None):
        span = _FakeSpan(name)
        self.spans.append(span)
        yield span

    def end(self, metadata=None, *, output=None):
        self.ended = dict(metadata or {})
        self.output = output


class _FakeTracer:
    def __init__(self):
        self.traces = []

    def start_trace(self, name, *, metadata=None, input=None):
        self.traces.append(_FakeTrace(metadata or {}, input=input))
        return self.traces[-1]

    def flush(self):
        return None


class _NoLLM:
    available = False


def test_answer_traces_each_stage_without_leaking_query(monkeypatch):
    from agents import pipeline
    from agents.router import RouteDecision
    from retrieval.schema import Chunk, SearchHit

    secret = "zq-unique-customer-question-9137"
    hit = SearchHit(
        chunk=Chunk(id="c1", source_type="review", text="battery dies", asin="B1", category="E"),
        score=1.0,
    )

    async def fake_route(query, role, ledger=None, **kwargs):
        ledger.add(7, 0.25)
        return RouteDecision(intent="review_rag", scope={}, rationale="test")

    tracer = _FakeTracer()
    monkeypatch.setattr(pipeline, "get_tracer", lambda: tracer)
    monkeypatch.setattr(pipeline, "route", fake_route)
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [hit])
    monkeypatch.setattr("agents.composer.get_llm", lambda **_: _NoLLM())
    monkeypatch.setenv("AUDIT_ENABLED", "false")
    get_settings.cache_clear()

    result = asyncio.run(pipeline.answer(secret, "support"))

    assert len(tracer.traces) == 1
    trace = tracer.traces[0]
    assert [s.name for s in trace.spans] == ["route", "review_rag", "compose"]
    assert trace.spans[0].meta["tokens"] == 7 and trace.spans[0].meta["cost_usd"] == 0.25
    assert all("latency_ms" in s.meta for s in trace.spans)
    # Enriched trace summary: route + grounding outcome + real totals, still text-free.
    assert trace.ended["intent"] == "review_rag" and trace.ended["tool_path"] == "review_rag"
    assert trace.ended["grounding"] == "extractive" and trace.ended["n_sources"] == 1
    assert "tokens" in trace.ended and "cost_usd" in trace.ended
    # Retrieval observability is recorded on the span, not just counted globally.
    review_span = next(s for s in trace.spans if s.name == "review_rag")
    assert review_span.meta["hits"] == 1 and review_span.meta["top_score"] == 1.0
    seen = [trace.metadata, trace.ended, *(s.meta for s in trace.spans)]
    assert secret not in repr(seen)
    assert result.audit["query"] == secret and result.audit["tool_path"] == ["review_rag"]


def test_answer_survives_tracer_failure(monkeypatch):
    from agents import pipeline
    from agents.router import RouteDecision

    class Boom:
        def start_trace(self, name, *, metadata=None):
            raise RuntimeError("down")

    async def fake_route(query, role, ledger=None, **kwargs):
        return RouteDecision(intent="review_rag", scope={}, rationale="test")

    monkeypatch.setattr(pipeline, "get_tracer", lambda: Boom())
    monkeypatch.setattr(pipeline, "route", fake_route)
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [])
    monkeypatch.setattr("agents.composer.get_llm", lambda **_: _NoLLM())
    monkeypatch.setenv("AUDIT_ENABLED", "false")
    get_settings.cache_clear()

    # A specific question takes the execute path; the point is that a failing tracer is
    # swallowed and the turn still produces its answer and audit.
    result = asyncio.run(pipeline.answer("what do customers say about the battery", "support"))
    assert result.audit["intent"] == "review_rag"
