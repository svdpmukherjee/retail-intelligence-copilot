# Answer-quality Stage 3 — evidence foundations proposal

2026-11-03. **Approved for implementation and isolated fixture verification** by the user’s
“go ahead” after proposal review. Stage 2 bounded implementation accepted; overall
answer quality remains incomplete. This scoped M2/M3/M4 change follows
option B; it does not reopen original module completion or authorize corpus writes.

As a retail user, I want product explanations drawn from identifiable, relevant
reviews, with honest coverage limits, so that SQL selections and cited evidence
describe the same products and population.

## Stage 2 acceptance status

Saved verification: 118 scoped tests passed; build/scoped lint/format passed;
six generation-disabled read-only smokes passed. Separate synthetic comparison:
108 assertions PASS, 0 FAIL, 66 unmeasured; no complete quality pass. These results
were inspected, not rerun for this proposal. Stage 1 `quality-baseline.*` stays intact.

The saved Chrome report exists: 13 actual UI queries, real corpus/hosted models,
marketing/executive, ephemeral history and emulated phone. Tested Stage 2 behavior
includes standalone versus dependent follow-ups, category/permission intersections,
review-weighted averages, selection-to-retrieval constraints and honest missing
evidence. Both selected lowest products have zero indexed chunks by independent
ASIN counts. This proves those gaps, not overall SQL/vector overlap or their cause.

The user accepted the bounded Stage 2 contracts with “go ahead”. End-to-end
product explanations remain incomplete pending coverage. Generated-SQL repair
quality, calibrated semantic support, durable ownership/persistence and remaining
adversarial boundaries are unvalidated. Browser findings remain failures: wrong
highest/lowest prose over correct SQL, seven literal-Markdown answers, grouped
citation/source-retention losses, long fallbacks/raw HTML text, unsorted ranked
charts, malformed prose and resolved complaints presented as current. Stage 4 owns
synthesis/formatting/chart repairs; Stage 3 supplies cleaner, traceable evidence.
Citation syntax does not demonstrate factual support.

## Established code facts and unresolved causes

`data/etl/gold.py` independently caps SQL and RAG rows by category, newest first.
Gold review projection omits rating, exact timestamp and product title already
available to structured Gold. `retrieval/chunking.py` makes one unbounded chunk
per review, keyed by ASIN and text hash, without stable parent review identity.
Text edits change IDs; equal text can collapse distinct reviews. Indexers upsert
without reconciling removed chunks. `schema.py` has no corpus/model/version
manifest; `hybrid.py` embeds before checking compatibility and uses the entire
question for lexical search. AzureSearchStore is currently an inert gated stub.

Different caps/newest-first sampling are plausible contributors to missing product
coverage, not a measured explanation for the two observed gaps. Availability of
their text in existing Silver/Bronze, stable upstream IDs, exact recoverable legacy
metadata and the original embedding revision must be measured before backfill.

## Ordered implementation proposal (after approval)

1. **S3.1 Read-only overlap and lineage report.** Pin Delta versions and index
   snapshot identity. Stream distinct `(category, asin)` sets and review counts
   from structured Gold, review Gold and index. Report SQL∩RAG∩index, both anti-join
   directions, SQL-product coverage and review-weighted coverage, per category,
   year/rating strata where known, duplicate/missing keys and metadata completeness.
   Distinguish SQL rows, source reviews, unique parents and chunks. Trace the two
   failed products through existing local layers; mark unavailable fields unknown.
   No raw reviewer IDs/text in shareable reports. Acceptance: counts reconcile on
   a known fixture; actual local report labels every denominator and snapshot.
   Files: new `backend/eval/evidence_coverage.py`, isolated tests and local report.

2. **S3.2 Versioned source and chunk contracts.** Carry rating, exact review time,
   product title, category/ASIN, stable parent ID, source snapshot/version, redacted
   content hash, normalization/chunker versions and parent offsets. Prefer an
   upstream immutable review ID; otherwise define a private deterministic source
   key before projection and explicitly document identity/update limitations.
   Never infer a review identity solely from ASIN plus text or expose reviewer
   identifiers. Ambiguous legacy matches remain unknown. Preserve full parent
   update/correction context; do not infer a current issue from rating alone.
   Manifest includes model identity, resolved revision/deployment version where
   available, dimensions, tokenizer/preprocessing, selection seed and source
   versions. Unknown legacy provenance remains unverified; never certify it from
   vector dimension. Acceptance: round-trip metadata, distinct equal-text reviews,
   edited-parent identity, and same-dimension model mismatch rejection.
   Files: `data/etl/gold.py`, `backend/retrieval/{schema,embeddings,vector_store}.py`.

3. **S3.3 Safe normalization, chunks and reconciled indexing.** Parse review HTML
   into plain text: decode entities once, preserve block/line boundaries, remove
   script/style content, never fetch links or execute markup. Reapply PII redaction
   and retain restricted source lineage/hash plus normalized-parent offsets;
   offsets are into normalized text, not falsely presented as original HTML offsets.
   Token-bound chunks using the embedding tokenizer, with overlap and parent IDs;
   retain nearby updates and access to full redacted parent context. Empty or
   unparseable sources get explicit rejected records. Manifest diff replaces all
   chunks of an edited parent and removes deleted/superseded parents only inside
   a new candidate version. Acceptance: idempotent normalization, HTML/entities,
   PII/malicious input, long-review tail complaint, shortened/deleted docs and
   rollback fixtures; multiple chunks never inflate review counts.
   Files: new `backend/retrieval/normalization.py`, chunking and both indexers.

4. **S3.4 Coverage policy and retrieval sufficiency.** Recommend a deterministic
   product-aware core within the SQL snapshot, stratified across date/rating and
   categories, plus an explicitly nonrepresentative diagnostic supplement for
   eligible low-rated products. Measure candidate size before choosing numeric
   caps; do not silently restrict SQL rankings to indexed products. No new raw
   downloads; missing source text remains missing. Keep diagnostic and general
   sample membership recorded. Qualitative top-k examples never establish theme
   prevalence; counted claims require unique parents and a stated population.
   Improve focused lexical terms alongside vector retrieval, preserving identical
   role/request/ASIN constraints in both paths. Evaluate lexical contribution
   separately; reject absent/irrelevant evidence with explicit partial states.
   Calibrate sufficiency on held-out answerable/unanswerable fixtures; RRF score is
   not confidence. Metadata/coverage supports correction-aware synthesis but does
   not solve it without Stage 4. Files: Gold selection, `hybrid.py`, `_rag.py`,
   pipeline contracts and existing quality fixtures.

## Migration/backfill and operational boundaries

| Change | Required operation before use |
|---|---|
| Rating/date/title/parent IDs absent from review Gold | Rebuild a **separate versioned Gold candidate** from existing local source; join only on validated unique keys. Ambiguous matches cannot be patched by ASIN. |
| Metadata only, identical text and proven embedding identity | Vector reuse is possible with verified one-to-one lineage; dimensions alone are insufficient. |
| Normalization or token chunks change text; new reviews added | Re-embed affected/new text in a candidate index. Full rebuild only if scope measurements justify it and separately authorized. |
| Unknown/mismatched original embedding model | Block mixing; separately approve a consistently embedded candidate rather than guessing the model revision. |
| Source edit/deletion | Reconcile candidate manifest; ordinary upsert is insufficient. Retain prior version for rollback. |

Do not run current `run_gold()` against serving paths: it overwrites both Gold
tables. Do not run current index CLIs against serving `chunks`. Prefer a separate
local database and candidate Gold root, initially at most 100 fixture reviews and
3 documents, at most 500 chunks. An approved implementation may create only that
isolated fixture target; no live backfill is implied. Snapshot selection, Gold,
index and embedding manifest must switch together through a versioned configured
pointer; retain the old set and rehearse rollback. Existing 225,000 review and 79
document chunks remain untouched. No in-place DDL is proposed on serving data.
Azure stays gated and must reject unsupported new contracts explicitly.

Before **any real candidate backfill**, present a separate run plan: measured
source/product/review/chunk counts, storage/CPU/time estimate, cached model identity,
embedding token estimate, provider transfer details if any, explicit spend cap,
target paths/database, reconciliation diff, backup and rollback commands. Serving
cutover and eventual old-version cleanup each require explicit authorization.
The old $2 live-test approval does not authorize these operations.

## Verification and approval boundary

Use DB/network-free tests where possible, inspecting fixtures first; shared
`backend/tests/conftest.py` creates a `_test` database and truncates mutable tables.
Do not run it against serving data. Require a real cached-local-embedding smoke
only in the explicitly isolated fixture target, no downloads/hosted generation,
plus A10/A11/A16–A19/A22 relevant evidence boundaries. Record exact retrieval
expectations/recall and missing evidence, not a citation-density support score.
Full-corpus recall, provider behavior and answer-quality acceptance remain separate.

Implementation acceptance requires reconciled coverage reporting, source-to-chunk
traceability, model mismatch rejection, safe normalized text, deduplicated parent
counts, no cross-scope retrieval, and demonstrated edit/delete/rollback behavior
in isolation. No serving-data quality improvement may be claimed from fixtures.

Approved by the user: Stage 2 bounded acceptance and S3.1–S3.4 code plus isolated
fixture verification. Stage 3 final acceptance remains a human checkpoint. Planning costs $0; proposed local implementation has $0 hosted spend.
No full ETL/reindex, serving schema/data mutation, model download, deployment,
commit or push; stages 4–5 remain deferred.

Approval localization: real backfill, serving cutover, corpus mutation and paid work
remain unauthorized. Existing serving contracts stay compatible until a separately
approved versioned candidate is activated.

## Implementation localization and measured limits

The isolated fixture target uses SQLite vectors + FTS5, with immutable parent/index/
Delta Gold manifests and a per-turn pinned pointer. This avoids creating another
Postgres database and leaves the existing pgvector schema/columns untouched. It
implements the versioned contract at fixture scale (100 reviews/3 docs/500 chunks),
not a production-scale replacement adapter. Real pgvector/Azure migration remains
part of the separately approved operational plan; Azure remains explicitly gated.
The candidate builder refuses real source snapshots. Default serving settings and
legacy behavior remain unchanged; do not activate the bundle setting on serving.

Measured read-only snapshots: SQL 645448 products / 911308 review rows; review Gold
and index share 191007 products; index has 225000 review chunks and 79 doc chunks.
454441 SQL products have no indexed reviews. Covered products account for 324526
SQL review rows. Both selected failed products have Silver rows (2 and 3) but zero
Gold-review/index rows. This localizes their gap before indexing; it does not prove
source text quality or that all other coverage gaps share one cause. Legacy parent
identity and embedding revision remain unverified. Local complete audit:
`/private/tmp/ric-stage3-coverage.json` (read-only, no source bodies).

A 225000-review budget cannot cover all 645448 products even at one review each.
Choose a declared bounded population or a larger index after measuring a candidate;
never silently narrow SQL rankings to indexed products. No numeric production
sampling caps, paid budget or backfill execution is approved here.
