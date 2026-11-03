from eval.evidence_coverage import compare, summarize


def test_coverage_denominators_and_missing_identity():
    sql = summarize([{"category": "A", "asin": a} for a in ["x", "x", "y", "z"]])
    rag = summarize([{"category": "A", "asin": a} for a in ["x", "y", "w"]])
    index = summarize([{"category": "A", "asin": a} for a in ["x", "x", "w", "q"]])
    out = compare(sql, rag, index)
    overall = out["overall"]
    assert overall["triple_overlap"] == 1
    assert overall["sql_without_rag"] == 1
    assert overall["sql_without_index"] == 2
    assert overall["index_without_rag"] == 1
    assert overall["sql_product_coverage"] == {"numerator": 1, "denominator": 3}
    assert overall["sql_row_weighted_product_coverage"] == {
        "numerator": 2,
        "denominator": 4,
    }
    assert out["layers"]["index"]["unique_parents"] is None
    assert out["layers"]["index"]["rows"] == 4
    assert out["by_category"]["A"] == overall


def test_missing_keys_strata_and_parent_duplicates():
    out = summarize(
        [
            {"category": "A", "asin": "x", "parent_id": "p", "rating": 1, "year": 2023},
            {"category": "A", "asin": "x", "parent_id": "p", "rating": 1, "year": 2023},
            {"category": "A", "parent_id": "q"},
        ]
    )
    assert out["missing_product_keys"] == 1
    assert out["unique_parents"] == 2
    assert out["duplicate_parent_rows"] == 1
    assert out["strata"][("A", 2023, 1)] == 2
    assert compare(summarize([]), summarize([]), summarize([]))["overall"]["sql_products"] == 0
