# Stage 3 isolated evidence verification

2026-11-03. Synthetic sources; real cached local model, SQLite FTS/vectors, Delta SQL and pipeline.
This is an evidence-contract smoke, not a live-corpus answer-quality or factual-support pass.

| Check | Result |
|---|---|
| battery stopped charging | PASS |
| quantum isotope reactor coolant | PASS |
| Why do customers complain about battery charging? | PASS |
| What do customers praise about headphone comfort? | PASS |
| What color is the submarine periscope? | PASS |
| Why do customers complain about a battery leaking? | PASS |
| empty/crossed scope | PASS |
| empty/crossed scope | PASS |
| pipeline selection and constrained retrieval tools | PASS |
| no hosted generation | PASS |
| SQL selection independent of chunk counts | PASS |
| honest selection-only when generic query is below relevance floor | PASS |
| real pipeline retrieves relevant review evidence | PASS |
| scope enforced in candidate pipeline | PASS |
| denied category has no evidence | PASS |
| atomic switch binds SQL and index | PASS |
| deleted docs removed | PASS |
| rollback restores prior doc evidence | PASS |

| Probe | Indexed-parent recall | Source-parent recall | Lexical-only relevant parents |
|---|---:|---:|---:|
| calibration: battery stopped charging | 1.0 | 1.0 | 0 |
| calibration: quantum isotope reactor coolant | None | None | 0 |
| heldout: Why do customers complain about battery charging? | 1.0 | 1.0 | 0 |
| heldout: What do customers praise about headphone comfort? | 1.0 | 0.5 | 0 |
| heldout: What color is the submarine periscope? | None | None | 0 |
| heldout: Why do customers complain about a battery leaking? | 1.0 | 1.0 | 0 |

Recall denominators are explicit in the companion JSON. Null means no relevant-source
denominator for an unanswerable probe. Headphone source recall is 0.5 because the
bounded core selected one of two source reviews; indexed-parent recall is 1.0.
Lexical matches did not add a relevant parent beyond vector top-k in this tiny fixture.
The candidate 0.35 raw-cosine floor separates these two calibration/four held-out probes;
this is insufficient for general calibration. The generic product-explanation query
honestly abstains from reasons below that floor. RRF scores are never confidence.

Backend verification: 135 scoped tests pass; one old real-model unit test was explicitly
deselected because the offline end-to-end smoke owns real-model verification.
The separate cached-Java/Delta two-review Spark integration test passes.
No hosted generation, serving corpus mutation, model downloads or real backfill.
Actual live overlap evidence stays local at `/private/tmp/ric-stage3-coverage.json`.
