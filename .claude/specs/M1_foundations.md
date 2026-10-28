# Spec M1: Foundations

## User story
As the engineering team building the copilot, I want a clean repo skeleton,
environment-driven config, IaC stubs, and cost guardrails in place, so that
every later module has a known structure to build into and we can never
accidentally spend cloud money or leak a secret.

## Module acceptance criteria
- [ ] Repo contains `backend/`, `frontend/`, `infra/`, `data/`, `.github/workflows/`
      matching PRD §11, each importable/runnable as a skeleton (no feature code).
- [ ] A `pydantic-settings` config loads from `.env`; `.env.example` documents
      **every** key; a `PROVIDER_MODE` switch (`azure` | `free`) is read and
      exposed, so later provider adapters have a home. No secret is committed.
- [ ] A minimal async FastAPI app starts and serves `GET /health` returning the
      active provider mode; `pytest` passes against it.
- [ ] An in-code cost/token ceiling helper exists and **raises** when a running
      total would exceed its configured cap; `COST.md` exists and tracks spend.
- [ ] `infra/` holds Bicep **stubs** plus a budget-alert definition and a
      teardown script — all inert (no `az deploy` run, no resource provisioned).
- [ ] `ruff` + `black` pass on `backend/`; CI workflow stub runs lint + tests.

## Sub-modules (ordered, each build → verify → integrate)

### M1.1 Repo scaffold & dev tooling
- Goal: lay down the directory tree and Python/JS tooling so everything else has a home.
- Acceptance criteria:
  - [ ] `backend/`, `frontend/`, `infra/`, `data/`, `.github/workflows/` exist per PRD §11
        (backend has `agents/ retrieval/ governance/ eval/` as empty packages with `__init__.py`).
  - [ ] `cd backend && pip install -e .` succeeds; `ruff check` and `black --check` run clean.
  - [ ] `frontend/` has a Vite+React skeleton (`package.json`, `src/App.tsx`) that type-checks.
- Build steps:
  1. Create `backend/pyproject.toml` (Python 3.12, deps: `fastapi`, `uvicorn`,
     `pydantic-settings`, `pytest`, `ruff`, `black`; configure ruff+black+pytest).
  2. Create backend package tree: `backend/app/__init__.py`, and
     `backend/agents/__init__.py`, `backend/retrieval/__init__.py`,
     `backend/governance/__init__.py`, `backend/eval/__init__.py`.
  3. Scaffold `frontend/` with Vite React-TS (`package.json`, `tsconfig.json`,
     `index.html`, `src/App.tsx`, `src/main.tsx`), plus `data/.gitkeep`.
  4. Add `.github/workflows/ci.yml` stub: install, `ruff check`, `black --check`, `pytest`.
- Files to touch: `backend/pyproject.toml`, `backend/app/__init__.py`,
  `backend/{agents,retrieval,governance,eval}/__init__.py`,
  `frontend/package.json`, `frontend/tsconfig.json`, `frontend/index.html`,
  `frontend/src/App.tsx`, `frontend/src/main.tsx`, `data/.gitkeep`,
  `.github/workflows/ci.yml`.
- Integration point: extends the existing repo (which already has `.gitignore`
  covering `.env`, `node_modules/`, `.terraform/`, `data/raw..gold/`).

### M1.2 Config system & app skeleton
- Goal: one env-driven settings object + a running FastAPI app that proves it loads.
- Acceptance criteria:
  - [ ] `Settings` (pydantic-settings) loads from `.env`; `PROVIDER_MODE` defaults to `free`.
  - [ ] `.env.example` lists every key (provider mode, Azure OpenAI/Search/Blob,
        Databricks, pgvector/DB, cost caps) with placeholder values, no real secrets.
  - [ ] `GET /health` returns `{"status":"ok","provider_mode":<mode>}`; a pytest hits it.
- Build steps:
  1. Write `backend/app/config.py`: `Settings(BaseSettings)` with `provider_mode:
     Literal["azure","free"]`, optional Azure/Databricks/DB fields, and cost-cap
     fields; `env_file=".env"`. Provide a cached `get_settings()`.
  2. Write `backend/app/main.py`: async FastAPI app, `GET /health` reading settings;
     upstream errors return typed `HTTPException` per code_style rules.
  3. Write `backend/.env.example` documenting every key (grouped, commented).
  4. Write `backend/tests/test_health.py` using FastAPI `TestClient`.
- Files to touch: `backend/app/config.py`, `backend/app/main.py`,
  `backend/.env.example`, `backend/tests/__init__.py`, `backend/tests/test_health.py`.
- Integration point: imports the package tree from M1.1; app is the entrypoint
  (`uvicorn app.main:app`) later modules mount routers onto.

### M1.3 Cost tracking & ceiling helper
- Goal: enforce a token/cost ceiling in code and record real spend in `COST.md`.
- Acceptance criteria:
  - [ ] `CostLedger.add(tokens, usd)` accumulates; exceeding the configured cap
        raises a typed `CostCeilingExceeded`.
  - [ ] Caps are read from `Settings` (e.g. `max_cost_usd`, `max_tokens_per_query`), not hard-coded.
  - [ ] `COST.md` exists with a dated table (module, service, est/actual spend) seeded at $0.
- Build steps:
  1. Write `backend/app/cost.py`: `CostCeilingExceeded(Exception)` and a
     `CostLedger` reading caps from `get_settings()`; `add()` raises on breach.
  2. Add `backend/tests/test_cost.py`: under-cap passes, over-cap raises.
  3. Create `COST.md` at repo root: header + table (date, module, service, est, actual), M1 row = $0.
- Files to touch: `backend/app/cost.py`, `backend/tests/test_cost.py`, `COST.md`.
- Integration point: consumes `Settings` from M1.2; later agent/LLM calls wrap
  usage through `CostLedger` (hooked in M4+).

### M1.4 IaC skeleton & budget alerts
- Goal: inert Bicep stubs + budget alert + teardown script, provisioning nothing.
- Acceptance criteria:
  - [ ] `infra/main.bicep` plus module stubs compile/parse but declare no deployed
        resources beyond parameterized placeholders (commented, no secrets).
  - [ ] `infra/budget.bicep` defines a consumption budget with an alert threshold,
        reading amount/contact from parameters (`infra/main.bicepparam` placeholders).
  - [ ] `infra/teardown.sh` exists, is documented as destructive, and is not executed.
- Build steps:
  1. Write `infra/main.bicep` with `targetScope` + parameters (location, env,
     naming prefix) and commented module references for later Azure resources.
  2. Write `infra/budget.bicep` (Microsoft.Consumption budget + alert threshold)
     and `infra/main.bicepparam` with placeholder values.
  3. Write `infra/teardown.sh` (resource-group delete, guarded by a confirm prompt)
     and `infra/README.md` stating M1 provisions nothing (cost = $0).
- Files to touch: `infra/main.bicep`, `infra/budget.bicep`,
  `infra/main.bicepparam`, `infra/teardown.sh`, `infra/README.md`.
- Integration point: parameter names mirror config env keys (naming prefix,
  region) so a future deploy module stays consistent with `Settings`.

## Test plan
- M1.1: `cd backend && ruff check . && black --check . && pip install -e .` all pass;
  `cd frontend && npm install && npx tsc --noEmit` type-checks.
- M1.2: `pytest backend/tests/test_health.py` — `/health` returns 200 with provider mode;
  manual check that `.env.example` has no real secret values.
- M1.3: `pytest backend/tests/test_cost.py` — under-cap passes, over-cap raises `CostCeilingExceeded`.
- M1.4: `az bicep build -f infra/main.bicep` / `infra/budget.bicep` parse clean
  (or lint-only if the CLI is unavailable — report plainly, not a silent PASS). No deploy.
- Module-level end-to-end smoke: from a fresh clone, copy `.env.example`→`.env`,
  `pip install -e backend`, run `uvicorn app.main:app`, `curl /health` → 200 with
  `provider_mode:"free"`; `pytest backend` green. This is the one real smoke.

## Security & cost notes
- **Expected cloud spend for M1 = $0.** IaC is skeleton/stub only — no `az deploy`,
  no resource created, no embedding run. CHECKPOINT 1 is also the cost go-ahead,
  but the go-ahead here authorizes only committing inert stubs.
- Secrets live **only** in `.env` (already gitignored); `.env.example` carries
  placeholders and is the single source documenting every key. No key is logged or printed.
- Budget cap: `infra/budget.bicep` defines the alert threshold for when real
  provisioning begins in later modules; the in-code `CostLedger` cap is its runtime twin.
- No access-control surface is introduced yet (role→source policy arrives in M5).

## Out of scope
- Any real Azure provisioning, deployment, or embedding run (M2/M3/M7).
- Actual provider adapters (Azure OpenAI / AI Search / pgvector clients) — M1 only
  provides the `PROVIDER_MODE` config seam, not the implementations.
- Data ingestion/ETL, retrieval, agents, governance, evaluation (M2–M6).
- Frontend beyond a type-checking skeleton; no UI wiring to the backend yet (M7).
