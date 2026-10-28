# System Integration Testing — SIT (tester-owned, lightweight)

**Purpose:** confirm the components that make up a module actually work
**together**, end to end, before the module is called complete. Because the
architecture has many interacting parts (config, retrieval, agents, store, UI),
SIT is how we claim integration was done — not just that each part works alone.

This is a short **glimpse** of enterprise SIT, not a multi-environment campaign.

**When:** at the module boundary, after all sub-modules are integrated, run by
the `tester`.

**Checklist (per module):**
- [ ] Each component is reached via a **real** call (not a mock) on at least one happy path.
- [ ] One real end-to-end smoke exercises the integrated chain and returns a valid result.
- [ ] No component silently swallows an upstream error (loud-but-clean holds across the seam).

**Example (M1):** a live `uvicorn` + `curl /health` exercises `.env → Settings →
FastAPI` together → HTTP 200 `{provider_mode}`. Later modules extend the chain:
`ingest → index → retrieve → compose → cited answer`.

A module is **integration-complete** only when its SIT checklist passes.
