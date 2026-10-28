import json
from pathlib import Path

import pytest

from eval.metrics import mean, mrr, percentile, recall_at_k
from governance.policy import ACCESS_POLICY
from retrieval.index_docs import DOCS_ROOT

GOLD_DIR = Path(__file__).resolve().parent.parent / "eval" / "ground_truth"


def test_recall_at_k_counts_relevant_found_in_top_k():
    assert recall_at_k(["a", "b", "c"], ["a", "c"], k=2) == 0.5
    assert recall_at_k(["a", "b", "c"], ["a", "c"], k=3) == 1.0


def test_recall_at_k_zero_when_no_relevant():
    assert recall_at_k(["a"], [], k=1) == 0.0
    assert recall_at_k(["x"], ["a"], k=1) == 0.0


def test_mrr_is_reciprocal_of_first_relevant_rank():
    assert mrr(["x", "y", "a"], ["a", "b"]) == pytest.approx(1 / 3)
    assert mrr(["a", "x"], ["a"]) == 1.0
    assert mrr(["x", "y"], ["a"]) == 0.0


def test_percentile_nearest_rank():
    values = [50, 10, 40, 20, 30]
    assert percentile(values, 50) == 30
    assert percentile(values, 95) == 50
    assert percentile([], 50) == 0.0


def test_mean():
    assert mean([1, 2, 3, 4]) == 2.5
    assert mean([]) == 0.0


def _load(name: str) -> list[dict]:
    return json.loads((GOLD_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["retrieval.json", "answers.json"])
def test_gold_doc_ids_are_real_files(name):
    items = _load(name)
    assert 8 <= len(items) <= 12
    for item in items:
        for doc_id in item["relevant_doc_ids"]:
            matches = [p for p in DOCS_ROOT.glob(f"{doc_id}.*") if p.suffix in {".md", ".pdf"}]
            assert matches, f"{doc_id} has no file under {DOCS_ROOT}"


def test_answer_fixtures_match_retrieval_questions_and_use_valid_roles():
    retrieval, answers = _load("retrieval.json"), _load("answers.json")
    assert [i["question"] for i in retrieval] == [i["question"] for i in answers]
    for item in answers:
        assert item["role"] in ACCESS_POLICY
        assert item["must_include"]
