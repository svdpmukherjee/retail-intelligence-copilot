# Authorized conversational planning correction — M4/M5/M8 integration

2026-11-03. User explicitly requested analysis, a plan and proceeding to fix
reported greeting/access/typo/clarification/follow-up/answer failures. This is a
localized continuation of answer-quality remediation, not acceptance of prior
stages. Preserve all uncommitted work, baselines, serving data and provider setup.

1. Add a bounded structured conversation planner before tool routing. Use the
existing configured large model tier for interpretation and final synthesis;
retain code-level permission enforcement and safe deterministic handling for
obvious greetings, own-role questions, prohibited categories and unrelated code
requests. Never send these to vector search. Unknown/malformed model output must
not silently widen scope. Correct unambiguous category typos against vocabulary,
preserve explicit constraints and support reference-dependent category changes.
2. Ask for materially ambiguous lowest-product definitions. Persist typed
clarification state in existing JSON message payload; accept lowest-average rank
or an absolute average threshold, minimum review count and count limit. Invalid
replies remain clarification; topic switches remain new requests. Compute selected
products from ALL review ratings using validated numeric conditions; do not
confuse dataset counts with external total review histories. Existing bounded
Silver checks and honest missing/partial evidence apply; no population theme
frequency counting is claimed.
3. Carry planned query parts/conditions into existing scoped tool routing. Keep
one budget, one persisted turn, per-part failures and citations. Final synthesis
uses existing large tier, bounded sources, deterministic SQL summaries and known
support guards. Access answers derive from actual server policy, not model memory.
4. Add optional suggestion choices and clarification state to response/history
payloads, no DB DDL. LLM may select structured supported follow-up actions; code
renders/filters them against current role and available tools. Deterministic
fallback remains available. UI buttons fill/focus composer and never auto-submit;
replay preserves new fields and old history remains compatible. Render deliberate
conversational/access replies instead of replacing them with no-evidence copy.
5. Scope verification to reported examples plus relevant planning/SQL/memory/
composition/UI contracts. DB-free pytest (--noconftest), existing frontend harness
and build, one read-only generation-disabled integrated smoke. No hosted calls,
ETL/reindex/corpus/schema mutation, model download, deployment, commits or pushes.
Report LLM-path scripted tests separately from real hosted behavior not exercised.

Files: agents/conversation.py and suggestions/selection helpers as needed,
query_plan/router/pipeline/sql_agent/composer/answer_evidence/model_policy;
memory/manager; eval fixture adapter isolation; frontend response types,
App/StackedTurns/AssistantTurn/suggestion component/CSS/panel state; focused tests
and module/context notes. Code remains valid for free/Azure/OpenRouter adapters.
Do not add a second model-provider dependency or hard-code a new model slug.

Acceptance: reported marketing Automotive/Home and support Beauty requests
explicitly explain lack of access before retrieval; role-access questions use
policy; hello introduces capabilities; Python request + answer never retrieve
reviews; automative resolves Automotive without permitting outside-role hits;
how-about Pet Supplies preserves requested sentiment; lowest criteria can be
clarified and executed across turns without looping or discarding companions;
suggestions respect role and fill only; malformed planners fail safely; exact
SQL values and citation/source retention survive synthesis.

## User-authorized natural-conversation repair (2026-11-03)

User reports real clarification loops and explicitly authorizes implementation,
live hosted conversations, diagnosis and rechecks. Replace lexical preemption with
schema-informed typed interpretation, validated conditions and durable active-plan
context; retain deterministic access enforcement, cancellation and safe model-error
fallback. Validate numeric/category constraints without requiring literal rewrites.
Supported product discovery/price operations use product-grain deduplication and
known non-null prices; price observations are dataset metadata, not current quotes.
Unsupported selection qualifiers must be surfaced, never silently discarded.
Follow-up questions must reflect the executed plan/results, offer executable next
steps (including empty-result relaxation), remain role-scoped, and preserve context.
Backend zero-match/execution explanations must remain visible in live/replay UI.
Verify the supplied conversation and additional multi-turn boundaries through real
React/FastAPI/configured hosted models, independent SQL checks and source review;
repair observed failures and repeat affected cases. Keep aggregate reservations and
spend below the remaining original $2 approval. No corpus/ETL/reindex/schema writes,
downloads, deployment, commit/push. Live history/audits use ephemeral storage only.

### Final implementation and pre-publication reconciliation (2026-11-03)

Additional owned files: `agents/catalogue.py` and `tests/test_natural_conversation.py`.
Typed product metadata operations deduplicate ASIN/category, use recorded non-null
prices, preserve literal title/strict price constraints, and expose missing-price
counts. Final synthesis retains all evidence internally until a public draft passes;
return-policy questions prefer matching return/refund documents, and shipping-fee
refunds cannot establish full purchase-price refunds. One bounded same-source repair
is permitted; excerpts remain the honest fallback. Explicit role/data-denial tasks
must not be mistaken for generic own-role introduction requests.

The publication audit restores fallback clarification resolution for a concrete
replacement metric without weakening the unavailable-measure guard. Numeric display
modifiers such as “and show1” remain part of the original task, not an independent
unscoped query. Stage3's partial-state test supplies explicit selection conditions
and retains its original partial-state assertions. This is a small integration
repair, not authorization for a new hosted run or a broader implementation stage.
