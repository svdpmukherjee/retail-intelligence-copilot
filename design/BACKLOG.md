# Design Backlog

Deferred design/visual work, newest at the bottom. Each item says **what** and
**why deferred** so a later iteration can pick it up without re-deriving context.
This is the holding pen for polish; behavioural/structural design decisions live
in `02_decisions.md` and `DECISIONS.md`.

## Deferred to a later iteration (post-M8 v3)

- **Cosmetic polish of the clean dashboard.** Once the conversation + evidence
  structure is settled in M8 v3, a dedicated pass on spacing rhythm, motion/
  transitions, empty-state illustration, and typography refinement.
  *Why deferred:* structure before surface — get the conversation model and the
  auditability content right first; looks are cheap to change afterward and
  expensive to redo if the structure shifts under them.
- **Per-persona screenshots for the portfolio.** Capture support / marketing /
  executive / default × key states in light + dark for the recruiter deck.
  *Why deferred:* open from v1; only worth capturing once the v3 conversation UI
  is in place, or they'll be reshot.
- **4 edge states not driven live in v2 QA** (400, 502, no-evidence,
  degraded-SQL). *Why deferred:* accepted coverage gap at v2 close; fold into the
  v3 browser visual-QA matrix rather than a separate pass.
- **History search / rename / delete threads.** ChatGPT-style thread management
  beyond list + resume + new. *Why deferred:* v3 ships list/resume/new (the
  minimum that makes conversation feel real); management affordances are polish.
- **Real auth.** The role + user-ID picker is a demo convenience, not a login.
  A real deployment needs authenticated identity feeding `user_id`/role.
  *Why deferred:* out of scope for a $0 local recruiter demo; noted so it is a
  conscious omission, not an oversight.
