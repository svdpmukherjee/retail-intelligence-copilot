# Approved workaround — product evidence and truthful presentation

2026-11-03. User: “what is the workaround? you have permission to fix them”.
This authorizes implementing the previously explained coverage/metadata/narration
fixes and their necessary presentation integration, in the existing staged change.
It does not declare Stage 3 accepted or authorize paid work, bulk indexing, source
mutation, deployment, commit or push. Existing uncommitted work/baselines stay intact.

1. **Read-only source fallback and metadata.** For a supported SQL lowest-product
   selection, retrieve reviews by selected category/ASIN directly from existing
   Silver directly for supported selections, avoiding dependence on index coverage. Intersect permissions before reading;
   empty filters never widen. Pin Silver version, bound reads/products/source size,
   compare selection count/average against source review rows before explaining.
   Carry private stable parent identity, readable title, review rating/date and
   source version. Exact legacy-chunk matches may be enriched; ASIN-only matches
   must never be represented as the same review. No ETL/embedding/index write.
   Failure, mismatch or missing text yields an honest partial/unavailable state.
   Files: retrieval/source_reviews.py, pipeline, config/.env.example and tests.
2. **Truthful synthesis.** Render SQL-only numeric results with deterministic
   summaries calculated from actual complete rows; never ask an LLM to invent
   extrema/ranks. Product explanation uses selected source excerpts with bounded
   context and preserved updates. Normalize legacy source HTML safely after
   retrieval; keep identity/provenance honest. Short source-backed fallbacks and
   qualitative/sample wording, not population prevalence. Delimit untrusted source
   and memory data, reject malformed/unsupported drafts conservatively; do not
   claim citation syntax proves semantic support. Files: composer, grounding and
   focused evidence helpers/tests. Full calibrated semantic judging remains open.
3. **Safe formatting, evidence and charts.** Shared grouped/adjacent citation
   grammar across validation/retention/rendering; safe Markdown subset (headings,
   emphasis, lists, tables, code and citations), no raw HTML execution. Full
   redacted context expandable where available; old snapshots remain compatible.
   All roles use data-driven comparisons or chronological time series; never
   category-as-time, themes-as-counts or unsorted rank labels. Ambiguous/incomplete
   SQL stays a table. No frontend dependency downloads. Files: answer.ts,
   AnswerDocument/AssistantTurn/shape/EvidencePanel components, API types and CSS.
4. **Verification/documentation.** Hermetic scoped tests with --noconftest;
   generation-disabled read-only live smoke using existing Gold/index/Silver,
   ephemeral chats, corpus counts/checksum preservation; actual browser interaction
   where existing tooling is available. Hosted generation/faithfulness remains
   unmeasured unless separately authorized. Update context and module note; final
   human review checkpoint. No new thresholds or baseline replacement.

Acceptance: missing live selected products can use only their permitted Silver
reviews with checked selection metrics; mismatches/limits cannot substitute other
products. SQL extrema match independent values even with shuffled rows/ties or
partial results. Grouped sources retained/clickable live/replay. Raw HTML is inert;
formatting renders semantically. Charts have verified dimensions/order or fall
back to table. Resolved updates are visible and not silently extracted as ongoing
complaints. Tests must expose remaining semantic-support limitations.

Implementation localization: the source path is preferred for supported lowest-product
explanations, not a query-time ETL or embedding job. It verifies all source-rating
counts/averages before using any selected review, bounds reads and review sizes,
and fails closed on absent/mismatched source data. Ordinary review search keeps
its existing vector index, with exact-ID metadata enrichment and conservative
rating-intent filters; it remains a sample. The exact unqualified category review-
count question now has a deterministic COUNT(*) operation; qualifiers still use
the guarded SQL path. Full hosted semantic support/finish-reason calibration remains
open; no complete Stage 4 or overall quality pass is asserted by this workaround.

## Follow-up: explicit combined questions (2026-11-03)

Within the user's existing permission to fix reported failures, split two to four
explicit independently phrased questions at question-boundary conjunctions,
semicolons or newlines. Do not split category lists or dependent clauses. Execute
each through existing scoped routing/tools/composition, with one shared query
budget and one memory/audit persistence. Preserve partial success, independently
scoped categories and globally renumbered grouped citations. Keep one SQL table
only when exactly one part produces one; multiple calculations retain their cited
summaries rather than attaching an unrelated table. No schema/corpus writes or
new providers. Clearly disclose that selected complaint examples cannot answer
“most common”. Verify focused split/routing/permissions/citations/partial failure/
memory/budget regressions, one generation-disabled read-only combined smoke, and
frontend type build for additive audit values; no broad browser campaign.
