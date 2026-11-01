# RESUME — next session (written 2026-11-01, end of day)

Branch: `main` at `f12af36`, synced with `origin/main`. Working tree clean. Single working
tree (the parallel `ric-b8` / `ric-b10` worktrees were removed after merge).

## Where we are
Wave-1 + Wave-2 backlog is **done and on `main`**: B-5, B-6, B-7, B-8, B-10, B-11, B-12, plus
data-op P4 (corpus re-embedded locally, 225,079 chunks). The B-8 live model-comparison study
ran ($0.0054). No task in progress. Full detail in `WORKLOG.md` (2026-11-01 entries) and
`CURRENT_TASK.md`.

## Environment notes (so a new session can run things)
- **Local pgvector** (`infra-pgvector-1`) holds the real corpus in DB `rag` (225,079 chunks).
  Start it if down: `cd infra && docker compose up -d pgvector`. Tests target `rag_test`
  (B-12 guard), not `rag`.
- **Free-mode LLM** = local Ollama on `:11434` (`qwen2.5:3b`). Embeddings are always local MiniLM.
- **OpenRouter**: `backend/.env` now has the `OPENROUTER_*` block + the key, but **gated OFF**
  (`PROVIDER_MODE=free`, `OPENROUTER_GO_AHEAD=false`). To re-run the B-8 study live, set
  `PROVIDER_MODE=openrouter` + `OPENROUTER_GO_AHEAD=true`, then
  `cd backend && PYTHONPATH=$PWD .venv/bin/python -m eval.study --live` (≈$0.023; confirm slugs/prices first).
- `.env` is gitignored; its OpenRouter key lives only on this machine now.

## What to do next (open a NEW session; one task per session)
1. **Backlog work** — remaining items: **B-2** (HIGH), **B-3**, **B-4**, **B-9** (optional).
   `BACKLOG_PLAN.md` is stale (predates B-8/B-10/B-11/B-12 done), so **first command: `/prioritize`**
   to refresh the plan, then **`/change <ID>`** (likely `/change B-2`). B-4→B-2 serialize on
   `composer.py`; B-9 re-embeds, run alone.
2. **or Module M9 — Documentation** (last module in `PROJECT.md`): **`/module M9`**.

## Loose ends to glance at
- **Azure Postgres `ric-pg-13396`** may still be burning ~€4–5/day (cloud plane parked). If the
  live Azure run (P5–P8) isn't resuming, tear down: `az group delete -n rg-ric-demo`.
- Carried M8v3 human items (phone reflow, error banners, per-turn audit persistence) — see `CURRENT_TASK.md`.
