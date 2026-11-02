from agents.composer import SQL_DISPLAY_LABEL, build_sources
from retrieval.schema import Chunk, SearchHit


def _hit(**kw) -> SearchHit:
    base = {"id": "abc123deadbeef", "text": "Great pan, heats evenly."}
    return SearchHit(chunk=Chunk(**{**base, **kw}), score=0.9)


def _cites(*hits, sql=None):
    return [c for c, _ in build_sources(sql, list(hits))]


def test_review_display_label_uses_prettified_category():
    (c,) = _cites(_hit(source_type="review", category="Home_and_Kitchen", asin="B00XYZ1234"))
    assert c.display_label == "customer review · Home and Kitchen"


def test_review_without_category_is_plain():
    (c,) = _cites(_hit(source_type="review", asin="B00XYZ1234"))
    assert c.display_label == "customer review"


def test_review_display_label_has_no_raw_ids():
    (c,) = _cites(_hit(source_type="review", category="Home_and_Kitchen", asin="B00XYZ1234"))
    assert "B00XYZ1234" not in c.display_label
    assert "abc123deadbeef" not in c.display_label
    assert "_" not in c.display_label
    assert "B00XYZ1234" in c.label  # label unchanged


def test_doc_display_label_title_and_section_not_slug():
    (c,) = _cites(
        _hit(
            source_type="doc",
            doc_id="return_policy_v2",
            doc_title="Return Policy",
            section="Refund window",
        )
    )
    assert c.display_label == "Return Policy · Refund window"
    assert "return_policy_v2" not in c.display_label
    assert c.label == "Return Policy / Refund window"


def test_doc_slug_title_is_prettified_and_no_section():
    (c,) = _cites(_hit(source_type="doc", doc_id="return_policy.md", doc_title="return_policy"))
    assert c.display_label == "Return Policy"
    assert "_" not in c.display_label


def test_sql_display_label_and_label_unchanged():
    cites = _cites(sql={"columns": ["a"], "rows": [[1]]})
    assert cites[0].display_label == SQL_DISPLAY_LABEL == "Calculated from your data"
    assert cites[0].label == "SQL result"
    assert cites[0].snippet
