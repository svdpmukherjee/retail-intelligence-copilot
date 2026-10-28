# CURRENT_TASK.md

No module in progress.

**M8 — Serving & UI is DONE** (closed 2026-10-28). Built in 4 sub-modules: M8.1
backend serving hardening (CORS from `Settings.cors_allow_origins`, `GET /roles`
from `ACCESS_POLICY`, unknown-role → typed 400 via an API-boundary edge check);
M8.2 frontend API client/types/config (`vite.config.ts`, `src/api/{types,client}`
mirroring the backend contract, base URL from `VITE_API_BASE_URL`, typed
`ApiError`); M8.3 chat UI (role picker, numbered citations, error banner,
`thread_id`/`user_id` continuity); M8.4 inert deploy artifacts (backend+frontend
Dockerfiles, inert `infra/webapp.bicep`, build-only CI `frontend` job). One
build-back on M8.1 (monkeypatched-400 → real edge-check 400).

Module gate PASS (live free mode): real `POST /query` → grounded cited answer at
$0, follow-up reused the same `thread_id` (`history_turns_used` 0→2), CORS
origin-scoped, unknown role → 400, `test_serving_api.py` 4 passed, frontend
`npm run build` green, both Docker builds succeeded, CI YAML parses. New Settings:
`cors_allow_origins`. Cloud spend $0. See `docs/modules/M8_serving_ui.md` and
`WORKLOG.md`.

**Open items (human):**
- No UI screenshot captured — add one of the running chat (role selected, answer
  with numbered citations) under `docs/img/` and link it in the M8 note.
- CI `frontend` job (and the M7 `eval` job) not yet observed on a real GitHub
  runner — verify on first push; optionally capture a passing-job screenshot.
- The e2e smoke wrote memory rows for `user_id=qa-m8` and its thread
  `27bf01c8...`; deletable if tidying the dev DB.

**Pending housekeeping (human, carried):** clear accumulated dev-DB test rows —
`docker exec infra-pgvector-1 psql -U rag -d rag -c "TRUNCATE audit_log;" -c "DROP TABLE IF EXISTS chunks;"`
(harmless; tidies dev state).

Next step: open a **new session** and run `/module M9` (Documentation —
consolidated architecture diagrams + design record), the last remaining TODO in
`PROJECT.md`.
