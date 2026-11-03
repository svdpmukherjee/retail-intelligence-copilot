import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)

Scalar = str | int | float | bool | None

# Span/trace *metadata* stays non-PII by design: callers pass role / intent / tool_path / model /
# numeric deltas only, and anything string-bearing under these names is dropped. The user's text
# travels on a separate channel — the explicit `input`/`output` fields — which the caller redacts
# before it is handed over, so the operator Preview can show what went in and came out (the same
# query/answer the audit plane already stores) without leaking raw PII into metadata.
_FORBIDDEN_KEYS = frozenset({"query", "retrieval_query", "question", "text", "prompt", "answer"})


def _safe(metadata: dict[str, Scalar] | None) -> dict[str, Scalar]:
    """Keep scalar, non-text-bearing metadata only."""
    if not metadata:
        return {}
    return {
        key: value
        for key, value in metadata.items()
        if key not in _FORBIDDEN_KEYS and isinstance(value, str | int | float | bool | None)
    }


class SpanHandle(Protocol):
    def update(
        self,
        metadata: dict[str, Scalar] | None = None,
        *,
        input: str | None = None,
        output: str | None = None,
    ) -> None: ...


class TraceHandle(Protocol):
    def span(self, name: str, *, metadata: dict[str, Scalar] | None = None): ...

    def end(
        self, metadata: dict[str, Scalar] | None = None, *, output: str | None = None
    ) -> None: ...


class Tracer(Protocol):
    def start_trace(
        self, name: str, *, metadata: dict[str, Scalar] | None = None, input: str | None = None
    ) -> TraceHandle: ...

    def flush(self) -> None: ...


class _NoOpSpan:
    def update(
        self,
        metadata: dict[str, Scalar] | None = None,
        *,
        input: str | None = None,
        output: str | None = None,
    ) -> None:
        return None


_NOOP_SPAN = _NoOpSpan()


class _NoOpTrace:
    @contextmanager
    def span(self, name: str, *, metadata: dict[str, Scalar] | None = None) -> Iterator[SpanHandle]:
        yield _NOOP_SPAN

    def end(self, metadata: dict[str, Scalar] | None = None, *, output: str | None = None) -> None:
        return None


_NOOP_TRACE = _NoOpTrace()


class NoOpTracer:
    """Default: does nothing and allocates nothing per call."""

    def start_trace(
        self, name: str, *, metadata: dict[str, Scalar] | None = None, input: str | None = None
    ) -> TraceHandle:
        return _NOOP_TRACE

    def flush(self) -> None:
        return None


class _LangfuseSpan:
    def __init__(self, span) -> None:
        self._span = span

    def update(
        self,
        metadata: dict[str, Scalar] | None = None,
        *,
        input: str | None = None,
        output: str | None = None,
    ) -> None:
        fields: dict = {"metadata": _safe(metadata)}
        if input is not None:
            fields["input"] = input
        if output is not None:
            fields["output"] = output
        self._span.update(**fields)


class _LangfuseTrace:
    def __init__(self, root) -> None:
        self._root = root

    @contextmanager
    def span(self, name: str, *, metadata: dict[str, Scalar] | None = None) -> Iterator[SpanHandle]:
        child = self._root.start_observation(name=name, as_type="span", metadata=_safe(metadata))
        try:
            yield _LangfuseSpan(child)
        finally:
            child.end()

    def end(self, metadata: dict[str, Scalar] | None = None, *, output: str | None = None) -> None:
        fields: dict = {"metadata": _safe(metadata)}
        if output is not None:
            fields["output"] = output
        self._root.update(**fields)
        self._root.end()


class LangfuseTracer:
    """Langfuse export. The package is imported here, never at module import time."""

    def __init__(self, host: str | None, public_key: str, secret_key: str) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)

    def start_trace(
        self, name: str, *, metadata: dict[str, Scalar] | None = None, input: str | None = None
    ) -> TraceHandle:
        fields: dict = {"name": name, "as_type": "span", "metadata": _safe(metadata)}
        if input is not None:
            fields["input"] = input
        return _LangfuseTrace(self._client.start_observation(**fields))

    def flush(self) -> None:
        self._client.flush()


@lru_cache
def get_tracer() -> Tracer:
    """NoOpTracer unless explicitly enabled and keyed; never raises."""
    settings = get_settings()
    if not (
        settings.observability_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    ):
        return NoOpTracer()
    try:
        return LangfuseTracer(
            settings.langfuse_host,
            settings.langfuse_public_key.get_secret_value(),
            settings.langfuse_secret_key.get_secret_value(),
        )
    except Exception as exc:  # missing package or bad config must not break the app
        logger.warning("Langfuse tracer unavailable, tracing disabled: %s", type(exc).__name__)
        return NoOpTracer()
