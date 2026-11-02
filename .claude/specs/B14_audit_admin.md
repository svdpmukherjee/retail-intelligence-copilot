# B-14 — Audit admin view (read-only over `audit_log`)

**Source:** backlog item B-14 (`context/BACKLOG.md`), picked up as a `/change`.
**ADR:** see `context/DECISIONS.md` → "B-14 (2026-11-02) … Option A".
**Decision in one line:** a role-gated, read-only admin surface over the existing
`audit_log` — a new `GET /audit` endpoint + a small in-app React view in its own
`admin/` subtree — so operators can reconstruct why an answer was given, showing exactly
the internals the chat UI must hide.

## Scope & guardrails

- **Read-only.** No schema change (`audit_ddl` untouched), no writes, no DDL, no corpus
  access. The endpoint only `SELECT`s from `audit_log`.
- **Role-gated server-side.** Only the `admin` role (already `{}` = unrestricted in
  `ACCESS_POLICY`) may read; any other role → typed `HTTPException(403)`. The check is in
  the endpoint, enforced before any data is returned — never prompt-asked. Same posture as
  retrieval access control.
- **Operator plane, not the chat.** The view is the sanctioned home for ids, cost, routing,
  tokens, latency (`ux-surface` rule). It lives in `frontend/src/admin/`, **separate from the
  chat shapes**; the chat UI is not modified beyond the routing seam in `App.tsx`.
- Reference-build grain: list → row detail, pagination, nothing more. No charts, no filters
  beyond pagination in this change (filters can be a later backlog item).

## Sub-modules

### B14.1 — Backend: audit read path + endpoint

**Acceptance criteria**
1. `AuditStore` gains read methods (its first read path; it was write-only):
   - `list_recent(limit: int, offset: int) -> list[dict]` — rows newest-first
     (`ORDER BY created_at DESC, id DESC`), including `id` and `created_at`, with `limit`
     clamped to a sane max (e.g. 1–200, default 50) and `offset >= 0`.
   - `get(audit_id: int) -> dict | None` — one full row, or `None` if absent.
   - `count() -> int` — total rows, so the view can show "X of Y".
   Rows are returned as the stored (already-redacted) values; no secrets, no un-redaction.
2. `GET /audit?limit=&offset=&role=` in `main.py`:
   - requires `role` (query param, like `/threads`); if `role != "admin"` → `HTTPException(403,
     detail="Audit log is admin-only")`. Unknown role also rejected.
   - returns `{ "items": [...], "total": <int>, "limit": <int>, "offset": <int> }`, newest-first.
   - DB failure → `HTTPException(503, detail="Audit log unavailable")` (never an unhandled 500).
   - runs the blocking DB call via `asyncio.to_thread`, matching `/threads`.
3. `GET /audit/{audit_id}?role=admin` → the full row, or `HTTPException(404)` if absent; same
   403 gate.
4. Response models are Pydantic `BaseModel`s mirrored later in `types.ts`.

**Build steps**
- `backend/governance/audit.py`: add `list_recent`, `get`, `count` to `AuditStore`
  (each opens a connection via `_connect`, like `record`). Use the existing `dict_row` factory.
- `backend/app/main.py`: add `AuditRow`/`AuditListResponse` models and the two endpoints.
  Keep the admin check inline and explicit.

**Files:** `backend/governance/audit.py`, `backend/app/main.py`.

**Integration point:** new GET routes on the existing FastAPI app; no change to `/query`,
`/threads`, or the audit write path (`record_audit`).

**Tests (unit + one real smoke; scoped — do not run the full backend suite):**
- Unit over `AuditStore` read methods against the `<db>_test` scratch DB (via `conftest.py`),
  inserting a few rows then asserting order, pagination (limit/offset), `get` hit/miss, `count`.
  Must **not** touch the real `rag` corpus DB or re-embed anything.
- One real end-to-end smoke: insert a row, call `GET /audit?role=admin` through the app
  (TestClient), assert the row is returned with its operator fields; call with `role=support`
  and assert `403`.

### B14.2 — Frontend: admin view (own subtree)

**Acceptance criteria**
1. New `admin` demo identity exists (`identities.ts`) so the view is reachable; selecting it
   switches the app to the audit view, non-admin identities show the chat as today.
2. `frontend/src/admin/` holds the view (e.g. `AuditView.tsx` list + `AuditDetail.tsx` or an
   inline detail panel). **No chat shape component is imported or modified.**
3. The list shows, per row: created_at (relative + absolute), role, intent, tokens, cost_usd,
   latency_ms, and a tool_path summary. Clicking a row shows the full record (sources,
   grounding, memory, sql_error if present). These are the operator internals the chat hides.
4. Pagination control (prev/next over `limit`/`offset`) using `total`.
5. API calls go through `api/client.ts` (`getAudit`, `getAuditRow`) with types in `api/types.ts`;
   errors surfaced in the UI via the existing error pattern, never a silent blank state.
6. `App.tsx` change is confined to a routing seam: when the active identity's role is `admin`,
   render the admin view instead of the chat; otherwise unchanged.

**Build steps**
- `identities.ts`: add `{ userId: "admin_1", role: "admin" }`.
- `api/types.ts`: add `AuditRow`, `AuditListResponse` mirroring the backend models.
- `api/client.ts`: add `getAudit(role, limit, offset)` and `getAuditRow(role, id)`.
- `frontend/src/admin/`: new view components (list + detail), with their own minimal styling
  (reuse `App.css` tokens where trivial; do not fold into chat shape CSS).
- `App.tsx`: branch on `identity.role === "admin"` to render the admin view.

**Files:** `frontend/src/identities.ts`, `frontend/src/api/types.ts`,
`frontend/src/api/client.ts`, `frontend/src/admin/*` (new), `frontend/src/App.tsx`.

**Integration point:** the identity switcher already drives app state; the admin branch hangs
off the selected identity's role. The chat path is untouched for non-admin identities.

**Tests (scoped):** type-check / build (`npm run build` or `tsc`) passes; a component/render
check if the frontend test setup supports it, else the build + a manual-smoke note. Backend
contract already covered by B14.1's smoke.

## Module-level acceptance (after both sub-modules)

- An operator selecting the `admin` identity sees a paginated audit list and can open any row
  to see the full governance record; a non-admin never reaches it and the API denies them `403`.
- No change to the chat answer path, the audit write path, or the audit schema.
- `ruff`/`black` clean on backend; frontend builds.

## Out of scope (deferred)

- Real authentication (demo identities remain the mechanism; no login).
- Filtering/search by role/intent/date, CSV export, live tail — later backlog items if wanted.
- Any link from the chat UI to the admin view (the planes stay separate).
