# Spec M8: Serving & UI

## User story
As a retail business user (executive, analyst, support, marketing, admin), I want a web
chat where I pick my role and ask questions, so that I get grounded, cited answers scoped
to what my role is allowed to see — served by the existing FastAPI backend and a React UI
that are packaged for Azure deployment.

## Module acceptance criteria
- [ ] The backend serves `/health`, `/query`, and a new `GET /roles` with CORS allowed only
      for the configured origin (from `Settings`, not hard-coded); an out-of-scope origin is
      not granted CORS.
- [ ] A React SPA lets the user pick a role (populated from `GET /roles`), type a question,
      and see the answer text with its numbered citations/sources rendered.
- [ ] Backend/upstream errors surface as a visible message in the UI (never a silent blank);
      backend returns typed `HTTPException` JSON, never an unhandled 500.
- [ ] Follow-up questions in the same session reuse the returned `thread_id` (and `user_id`),
      so conversation continuity works end to end.
- [ ] Deploy artifacts exist and are inert: backend `Dockerfile`, frontend `Dockerfile`, a
      build/typecheck CI job (no live Azure deploy), and documented env keys — $0 spend.

## Sub-modules (ordered, each build → verify → integrate)

### M8.1 Backend serving hardening (CORS + roles + typed errors)
- Goal: make the existing API browser-ready and expose the role list the UI needs.
- Acceptance criteria:
  - [ ] `GET /roles` returns the policy roles, e.g. `{"roles": ["executive","admin","analyst","support","marketing"]}`, sourced from `governance/policy.ACCESS_POLICY`.
  - [ ] `CORSMiddleware` is added with `allow_origins` read from a new `Settings.cors_allow_origins` (comma-separated, default `http://localhost:5173`); a request from an unlisted origin receives no `access-control-allow-origin` header.
  - [ ] A query with an unknown role returns a typed `HTTPException` (400) with JSON `detail`, not a 500.
- Build steps:
  1. Add `cors_allow_origins: list[str]` to `Settings` (NoDecode + CSV split validator, mirroring `sql_categories`); default `["http://localhost:5173"]`.
  2. In `app/main.py` add `CORSMiddleware` using `get_settings().cors_allow_origins`; allow methods GET/POST, headers `*`.
  3. Add `GET /roles` returning `{"roles": list(ACCESS_POLICY)}` (import from `governance.policy`).
  4. In `POST /query`, catch `governance.policy.AccessDenied` → `HTTPException(400, detail=str(exc))` (ordered before the generic `except`).
- Files to touch: `backend/app/main.py`, `backend/app/config.py`, `backend/.env.example`, new `backend/tests/test_serving_api.py`.
- Integration point: extends the existing `app` and `/query` route; reuses `ACCESS_POLICY` and `AccessDenied` from M6 governance.

### M8.2 Frontend API client + types + config
- Goal: a typed client mirroring the `/query` and `/roles` contracts, with a configurable base URL.
- Acceptance criteria:
  - [ ] `vite.config.ts` exists; backend base URL comes from `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`), never hard-coded in components.
  - [ ] TS types `QueryRequest`, `Citation`, `AnswerResult`, `QueryResponse` match `composer.AnswerResult` + `main.QueryResponse` (`answer: string`, `citations: {n,source_id,label}[]`, `audit`, `thread_id?`, `user_id?`).
  - [ ] `postQuery()` and `getRoles()` throw a typed error carrying the backend `detail` on non-2xx.
  - [ ] `npm run typecheck` passes.
- Build steps:
  1. Add `frontend/vite.config.ts` (`@vitejs/plugin-react`, port 5173).
  2. Add `frontend/src/api/types.ts` mirroring the backend models.
  3. Add `frontend/src/api/client.ts` with `getRoles()` / `postQuery()` using `fetch`, reading `VITE_API_BASE_URL`, parsing `detail` on error.
  4. Add `frontend/.env.example` documenting `VITE_API_BASE_URL`.
- Files to touch: `frontend/vite.config.ts`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/.env.example`.
- Integration point: consumes the M8.1 endpoints; no UI yet — pure client layer imported by M8.3.

### M8.3 Chat UI (role picker, answer + citations, errors, continuity)
- Goal: the usable chat screen.
- Acceptance criteria:
  - [ ] On load, the role dropdown is populated from `getRoles()`; a question cannot be sent without a role.
  - [ ] Submitting a question renders the answer text and a numbered citations list (`[n] label`); a loading state shows while awaiting.
  - [ ] A backend error renders a visible error banner (from the thrown `detail`), not a blank screen.
  - [ ] The `thread_id`/`user_id` returned by the first answer are held in state and sent on the next question (continuity); a stable `user_id` is generated client-side on first use.
- Build steps:
  1. Replace `frontend/src/App.tsx` with the chat container (role select, input, send, message list, error banner) wired to the M8.2 client.
  2. Add small presentational components: `frontend/src/components/MessageList.tsx`, `frontend/src/components/Citations.tsx`.
  3. Add minimal `frontend/src/App.css` (or inline) for a readable layout; wrap every API call in `try/catch`.
- Files to touch: `frontend/src/App.tsx`, `frontend/src/components/MessageList.tsx`, `frontend/src/components/Citations.tsx`, `frontend/src/App.css`.
- Integration point: imports `client.ts`/`types.ts` from M8.2; calls the live M8.1 API.

### M8.4 Deploy artifacts (inert) + CI build gate
- Goal: package both apps and add a build/typecheck CI gate — no live cloud deploy, $0.
- Acceptance criteria:
  - [ ] `backend/Dockerfile` builds a Python 3.12 image running `uvicorn app.main:app`; `frontend/Dockerfile` builds the static bundle (`npm ci && npm run build`).
  - [ ] A commented/inert Azure deploy artifact exists (e.g. `infra/webapp.bicep` stub or notes block) in the same inert style as `infra/main.bicep`; nothing provisions resources.
  - [ ] CI gains a `frontend` job that runs `npm ci` + `npm run build` (typecheck + vite build); it does not deploy anywhere.
  - [ ] `frontend/.env.example` and `backend/.env.example` document `VITE_API_BASE_URL` and `CORS_ALLOW_ORIGINS`.
- Build steps:
  1. Add `backend/Dockerfile` and `frontend/Dockerfile` (+ `frontend/.dockerignore`).
  2. Add inert `infra/webapp.bicep` (params only, deploy blocks commented) mirroring `infra/main.bicep`.
  3. Add a `frontend` job to `.github/workflows/ci.yml` (node setup, `npm ci`, `npm run build`).
  4. Add `CORS_ALLOW_ORIGINS` to `backend/.env.example` if not already added in M8.1.
- Files to touch: `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/.dockerignore`, `infra/webapp.bicep`, `.github/workflows/ci.yml`, `backend/.env.example`.
- Integration point: packages the M8.1 backend and M8.3 frontend; extends the existing `ci.yml` (keeps `backend`/`eval` jobs intact) and the inert `infra/` pattern from M1.

## Test plan
- M8.1 (tester): `backend/tests/test_serving_api.py` via `TestClient` — asserts `GET /roles` body, CORS header present for the allowed origin and absent for a disallowed one, and unknown-role `/query` returns 400 with `detail`. (One file + the existing `/health` smoke; not the full suite.)
- M8.2: `npm run typecheck` passes (client/types compile against the contract).
- M8.3: `npm run build` passes; manual/scripted check that the dropdown loads and an answer+citations render.
- M8.4: `docker build` of each Dockerfile succeeds locally; the new CI `frontend` job runs `npm run build` green.
- Module end-to-end smoke: with `PROVIDER_MODE=free` backend running (`uvicorn app.main:app`) and `npm run dev`, load the SPA, pick a role, ask one real question, and confirm a grounded answer with at least one citation renders in the browser; ask a follow-up and confirm the same `thread_id` is sent. If the live LLM/DB path is unavailable, the tester reports it plainly (not a silent PASS), per `.claude/rules/testing.md`.

## Security & cost notes
- Cost: **$0**. No cloud provisioning; deploy artifacts are inert (Dockerfiles, inert Bicep stub, build-only CI). Any real Azure deploy is out of scope and would need explicit human go-ahead (cost gate) — CHECKPOINT 1 is also the cost go-ahead, but expected spend is $0.
- Secrets: none added to code. CORS origin and API base URL are config (`.env`/Vite env), documented in `.env.example` files; no keys committed.
- Access control unchanged: governance is still enforced server-side at retrieval; the UI only *selects* a role and the backend denies unknown roles. The UI does not and must not enforce scope itself.

## Out of scope
- Live Azure provisioning/deployment, custom domains, TLS, auth/login (role is self-selected for this reference build).
- Streaming responses, multi-conversation history UI, and any JS unit-test runner (typecheck + build is the frontend gate).
- Changes to retrieval, agents, memory, or governance logic.
