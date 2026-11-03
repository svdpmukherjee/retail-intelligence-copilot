"""Hermetic Stage 3 contracts; no serving DB, model loading or network."""

import json
import re

import pytest

from app.config import Settings
from retrieval import hybrid
from retrieval.chunking import chunk_parent, source_parent
from retrieval.embeddings import FreeEmbedder
from retrieval.evidence_bundle import (
    EvidenceBundleStore,
    build_fixture_bundle,
    configured_bundle,
    open_bundle,
    pin_bundle,
    write_fixture_pointer,
)
from retrieval.index_docs import prepare_candidate_docs
from retrieval.index_reviews import prepare_candidate_reviews
from retrieval.normalization import normalize_source
from retrieval.provenance import (
    EmbeddingIdentity,
    EvidenceCompatibilityError,
    review_parent_id,
)
from retrieval.schema import Chunk, SearchHit
from retrieval.selection import select_reviews
from retrieval.sufficiency import lexical_query, select_evidence


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    import socket

    import psycopg

    def denied(*args, **kwargs):
        raise AssertionError("No external IO allowed in Stage 3 unit tests")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(psycopg, "connect", denied)


class WordTokenizer:
    """Scripted tokenizer for offset arithmetic only; real tokenizer tested in smoke."""

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]}

    def encode(self, text):
        return [0] * (len(text.split()) + 2)


class ScriptedEmbedder(FreeEmbedder):
    """Bounded build orchestration only; not a model-quality assertion."""

    def __init__(self):
        self._offline = True
        self.calls = 0

    identity = EmbeddingIdentity(
        provider="local",
        model="fixture",
        revision="abc",
        dimensions=3,
        tokenizer="word",
        preprocessing="fixture",
    )
    tokenizer = WordTokenizer()
    max_tokens = 30
    dim = 3

    def embed(self, texts):
        self.calls += len(texts)
        return [[1.0, 0.0, 0.0] if "battery" in t else [0.0, 1.0, 0.0] for t in texts]


def row(key="one", **kwargs):
    return {
        "review_id": key,
        "category": "Electronics",
        "asin": "P1",
        "title": "Review",
        "text": "battery stopped working",
        "rating": 1.0,
        "year": 2023,
        "timestamp": "2023-01-01T00:00:00Z",
        "product_title": "Battery device",
        **kwargs,
    }


def sql_rows():
    return [
        {
            "asin": "P1",
            "category": "Electronics",
            "rating": 1.0,
            "product_title": "Device",
        },
        {
            "asin": "P1",
            "category": "Electronics",
            "rating": 2.0,
            "product_title": "Device",
        },
        {"asin": "P2", "category": "Books", "rating": 5.0, "product_title": "Book"},
    ]


def parent(key="one", **kwargs):
    return source_parent(row(key, **kwargs), "fixture:1")


def test_normalization_decodes_once_and_never_executes_or_copies_hidden_content():
    raw = (
        "<div>Broken<br />battery &amp; charger</div>"
        "<script>alert(1)</script><style>secret</style>"
    )
    result = normalize_source(raw)
    assert result.text == "Broken\nbattery & charger"
    assert normalize_source(result) == result
    assert normalize_source("Use &amp;lt;br&amp;gt; literally").text == "Use &lt;br&gt; literally"
    assert (
        normalize_source("<p>mail a@example.com or +1 202 555 0198</p>").text
        == "mail [EMAIL] or [PHONE]"
    )
    assert normalize_source('<img src="https://invalid/secret" onerror="bad()">safe').text == "safe"
    with pytest.raises(ValueError, match="no usable text"):
        normalize_source("<script>hidden</script>")
    with pytest.raises(ValueError, match="version"):
        normalize_source(result.model_copy(update={"version": "other"}))


def test_identity_survives_text_edit_and_distinguishes_equal_text_reviews():
    first = parent("one")
    edited = parent("one", text="Update: replacement fixed it")
    identical_other = parent("two")
    assert first.parent_id == edited.parent_id != identical_other.parent_id
    assert first.content_hash != edited.content_hash
    with pytest.raises(ValueError, match="identity"):
        review_parent_id({"asin": "P", "text": "same"})
    private = row()
    private.pop("review_id")
    private["user_id_hash"] = "private-key"
    assert review_parent_id(private)[0] != "private-key"
    assert "private-key" not in source_parent(private, "fixture:1").model_dump_json()


def test_chunk_tail_bounds_offsets_and_parent_context():
    p = parent(text=" ".join(["works"] * 80) + " battery cracked. Update: replacement fixed it.")
    chunks = chunk_parent(p, WordTokenizer(), max_tokens=20, overlap=3)
    assert len(chunks) > 1
    assert any("replacement fixed it" in c.text for c in chunks)
    assert all(len(WordTokenizer().encode(c.text)) <= 20 for c in chunks)
    assert all(c.text == p.text[c.start_char : c.end_char] for c in chunks)
    assert {c.parent_id for c in chunks} == {p.parent_id}
    assert len({c.id for c in chunks}) == len(chunks)
    with pytest.raises(ValueError):
        chunk_parent(p, WordTokenizer(), max_tokens=20, overlap=20)


def test_candidate_rejections_are_explicit_and_bounded():
    parents, rejected = prepare_candidate_reviews(
        [row(), {"asin": "P"}, row("empty", title="", text="")], "fixture:1"
    )
    assert len(parents) == 1 and len(rejected) == 2
    docs, rejected = prepare_candidate_docs(
        [("return", "# Returns\n## Damage\nReturn damaged goods."), ("blank", "")],
        "fixture:1",
    )
    assert len(docs) == 1 and len(rejected) == 1
    with pytest.raises(ValueError, match="100"):
        prepare_candidate_reviews([row()] * 101, "fixture:1")


def test_product_stratified_selection_records_bias_and_is_deterministic():
    rows = [row(str(i), rating=float(i % 5 + 1), year=2022 + i % 2) for i in range(20)]
    picked = select_reviews(rows, seed="frozen")
    assert picked == select_reviews(list(reversed(rows)), seed="frozen")
    assert len(picked) < len(rows)
    supplement = select_reviews(rows, seed="frozen", diagnostic_products={("Electronics", "P1")})
    assert len(supplement) == len(rows)
    assert all(
        "low_rating_diagnostic_nonrepresentative" in r["sample_membership"] for r in supplement
    )
    assert all("user_id_hash" not in r for r in supplement)


def test_immutable_reconcile_sql_binding_and_rollback(tmp_path):
    embedder = ScriptedEmbedder()
    first = tmp_path / "v1"
    p1, p2 = parent("one"), parent("two")
    docs, _ = prepare_candidate_docs([("policy", "# Return\n" + "Policy. " * 60)], "fixture:1")
    build_fixture_bundle(
        first,
        version="v1",
        parents=[p1, p2, *docs],
        structured_rows=sql_rows(),
        embedder=embedder,
        seed="frozen",
    )
    original = EvidenceBundleStore(first)
    calls = embedder.calls
    # Edit one review, delete another, shorten the document.
    updated_docs, _ = prepare_candidate_docs([("policy", "# Return\nNew policy.")], "fixture:2")
    second = tmp_path / "v2"
    result = build_fixture_bundle(
        second,
        version="v2",
        parents=[parent("one", text="battery replacement"), *updated_docs],
        structured_rows=sql_rows(),
        embedder=embedder,
        seed="frozen",
        previous=original,
    )
    assert p2.parent_id in result["deleted_parents"]
    assert p1.parent_id in result["edited_parents"]
    current = EvidenceBundleStore(second)
    assert current.parents[p1.parent_id].text.endswith("battery replacement")
    assert p2.parent_id not in current.parents
    stored = current.parents[p1.parent_id]
    assert stored.rating == 1.0 and stored.timestamp.year == 2023
    assert stored.product_title == "Battery device" and stored.source_snapshot == "fixture:1"
    assert len(current._chunks(None)) < len(original._chunks(None))
    assert embedder.calls > calls
    assert p2.parent_id in EvidenceBundleStore(first).parents
    pointer = tmp_path / "current.json"
    write_fixture_pointer(pointer, second)
    assert open_bundle(pointer).manifest.corpus_version == "v2"
    write_fixture_pointer(pointer, first)
    with pin_bundle(str(pointer)):
        write_fixture_pointer(pointer, second)
        assert configured_bundle(str(pointer)).manifest.corpus_version == "v1"
    assert configured_bundle(str(pointer)).manifest.corpus_version == "v2"
    write_fixture_pointer(pointer, first)
    assert open_bundle(pointer).manifest.corpus_version == "v1"
    with pytest.raises(ValueError, match="overwrite"):
        build_fixture_bundle(
            first,
            version="v1",
            parents=[p1],
            structured_rows=sql_rows(),
            embedder=embedder,
            seed="frozen",
        )
    assert len(current.query([1, 0, 0], 10, filters={"category": []})) == 0
    assert current.parent(p1.parent_id, filters={"category": ["Books"]}) is None
    assert current.parent(p1.parent_id, filters={"category": ["Electronics"], "asin": ["P1"]})
    assert not current.keyword_query("battery", 3, filters={"asin": []})
    assert current.keyword_query("battery", 3, filters={"asin": ["P1"]})
    assert all(h.chunk.parent_text for h in current.query([1, 0, 0], 10))
    with pytest.raises(ValueError, match="unsupported filter"):
        current.query([1, 0, 0], 2, filters={"injection": "x"})
    with pytest.raises(ValueError, match="Immutable"):
        current.upsert([])
    # SQL and index cannot drift independently under one pointer.
    next(current.structured_path.rglob("*.parquet")).write_bytes(b"corrupt")
    with pytest.raises(EvidenceCompatibilityError, match="SQL Gold"):
        EvidenceBundleStore(second)


def test_same_dimension_model_mismatch_rejected_before_query_embedding(tmp_path, monkeypatch):
    embedder = ScriptedEmbedder()
    root = tmp_path / "v1"
    build_fixture_bundle(
        root,
        version="v1",
        parents=[parent()],
        structured_rows=sql_rows(),
        embedder=embedder,
        seed="frozen",
    )
    store = EvidenceBundleStore(root)

    class Wrong(ScriptedEmbedder):
        identity = ScriptedEmbedder.identity.model_copy(update={"model": "different-same-dim"})

        def embed(self, texts):
            pytest.fail("Mismatch must be rejected before query embedding")

    monkeypatch.setattr(hybrid, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(EvidenceCompatibilityError, match="identities differ"):
        hybrid.hybrid_search("battery", store=store, embedder=Wrong())
    unknown = embedder.identity.model_copy(update={"revision": "unknown"})
    with pytest.raises(EvidenceCompatibilityError, match="unverified"):
        unknown.require_match(unknown)


def test_reuse_only_compatible_unchanged_text(tmp_path):
    e = ScriptedEmbedder()
    build_fixture_bundle(
        tmp_path / "v1",
        version="v1",
        parents=[parent()],
        structured_rows=sql_rows(),
        embedder=e,
        seed="frozen",
    )
    original = EvidenceBundleStore(tmp_path / "v1")
    result = build_fixture_bundle(
        tmp_path / "v2",
        version="v2",
        parents=[parent()],
        structured_rows=sql_rows(),
        embedder=e,
        seed="frozen",
        previous=original,
    )
    assert result["embedded_chunks"] == 0 and result["reused_chunks"] == 1
    assert (
        json.loads((tmp_path / "v1" / "parents.json").read_text())[0]["source_snapshot"]
        == "fixture:1"
    )


def hit(key, parent_id, rating=1, asin="P1"):
    return SearchHit(
        chunk=Chunk(
            id=key,
            parent_id=parent_id,
            source_type="review",
            text="battery broke",
            rating=rating,
            asin=asin,
            category="Electronics",
        ),
        score=0.5,
    )


def test_sufficiency_uses_raw_similarity_not_rrf_and_counts_unique_parents():
    good, duplicate, praise, unrelated = (
        hit("a", "p"),
        hit("b", "p"),
        hit("c", "q", 5),
        hit("d", "r"),
    )
    vectors = [good, duplicate, praise, unrelated.model_copy(update={"score": 0.05})]
    fused = [h.model_copy(update={"score": 0.01}) for h in [good, duplicate, praise, unrelated]]
    selected = select_evidence(
        "Why do customers complain about battery?",
        fused,
        vectors,
        filters={"asin": ["P1", "P2"]},
        minimum_similarity=0.35,
        k=6,
    )
    assert [h.chunk.id for h in selected] == ["a"]
    assert selected.assessment["status"] == "partial"
    assert selected.assessment["unique_review_parents"] == 1
    assert selected.assessment["missing_product_ids"] == ["P2"]
    assert lexical_query("Why are customers unhappy with our battery products?") == "battery"
    none = select_evidence(
        "complaints", [unrelated], vectors, filters={}, minimum_similarity=0.35, k=6
    )
    assert none.assessment["status"] == "none"


def test_path_escape_and_tampering_are_rejected(tmp_path):
    from retrieval.evidence_bundle import member

    with pytest.raises(ValueError, match="escapes"):
        member(tmp_path, "../elsewhere")
    e = ScriptedEmbedder()
    root = tmp_path / "v1"
    build_fixture_bundle(
        root,
        version="v1",
        parents=[parent()],
        structured_rows=sql_rows(),
        embedder=e,
        seed="frozen",
    )
    (root / "parents.json").write_text("[]")
    with pytest.raises(EvidenceCompatibilityError, match="checksum"):
        EvidenceBundleStore(root)


def test_fixture_build_guards_precede_embedding_and_leave_no_version(tmp_path):
    e = ScriptedEmbedder()
    with pytest.raises(ValueError, match="source limit"):
        build_fixture_bundle(
            tmp_path / "large",
            version="large",
            parents=[parent()] * 101,
            structured_rows=sql_rows(),
            embedder=e,
            seed="frozen",
        )
    with pytest.raises(ValueError, match="backfill is gated"):
        build_fixture_bundle(
            tmp_path / "live",
            version="live",
            parents=[parent().model_copy(update={"source_snapshot": "silver:1"})],
            structured_rows=sql_rows(),
            embedder=e,
            seed="frozen",
        )
    with pytest.raises(ValueError, match="differs from normalized"):
        build_fixture_bundle(
            tmp_path / "bad",
            version="bad",
            parents=[parent().model_copy(update={"text": "unhashed edit"})],
            structured_rows=sql_rows(),
            embedder=e,
            seed="frozen",
        )
    assert e.calls == 0
    assert list(tmp_path.iterdir()) == []


def test_partial_state_reaches_plain_language_answer(monkeypatch):
    import asyncio

    from agents import pipeline
    from eval.quality_baseline import environment
    from eval.quality_fixture import load_fixture
    from retrieval.sufficiency import EvidenceHits

    with environment("fixture", load_fixture()):
        original = pipeline.review_rag

        def partial(query, scope):
            hits = original(query, scope)
            return EvidenceHits(
                hits[:1], {"status": "partial", "missing_product_ids": ["uncovered"]}
            )

        monkeypatch.setattr(pipeline, "review_rag", partial)
        answer = asyncio.run(
            pipeline.answer(
                "Why are the lowest average Electronics products disappointing customers? "
                "Use at least 2 reviews and show 1.",
                "executive",
            )
        )
    assert answer.audit["evidence"]["status"] == "partial"
    assert "only some of the selected products" in answer.answer
    assert "uncovered" not in answer.answer


def test_local_identity_refuses_unverified_online_resolution():
    embedder = FreeEmbedder(Settings(_env_file=None, embedding_local_files_only=False))
    with pytest.raises(EvidenceCompatibilityError, match="offline snapshot"):
        _ = embedder.identity
