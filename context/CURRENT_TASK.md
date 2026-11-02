# Current task

**B-14 — Audit admin view** (spec: `.claude/specs/B14_audit_admin.md`)

- B14.1 (backend read path + `GET /audit`, `GET /audit/{id}`): **built**, awaiting Tester
  (files: `backend/governance/audit.py`, `backend/app/main.py`).
- B14.2 (frontend admin view): **built** (`npm run build` clean), awaiting Tester. Files: `frontend/src/admin/*`, `identities.ts`, `api/types.ts`, `api/client.ts`, `App.tsx` (routing seam).
