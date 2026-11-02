# 01 · Wireframes — M8 Chat / Serving UI · **iteration 4**

**Design Track · iteration 4 · Stage 2 (wireframes).** Lo-fi, annotated layouts
only — structure, flow, and copy intent. No color, type, pixels, HTML, or app
code. Realizes the approved `00_brief.md` (same framing, same gaps G1–G8, same 8
success criteria). The hi-fi mockup comes next, gated on D2.

> **Surface audit, applied to every sketch below.** None of these appear anywhere
> on the user surface: `thread_id`/`session_id`, token counts, `cost_usd`,
> latency, intent/routing labels, `tool_path`, model slugs, provider names, raw
> `audit` JSON. (Count = 0 across all states — brief §4 criterion 1.) Where a
> value helps the user understand the *answer*, it is re-rendered as plain,
> grounded, cited content.

---

## 0. Layout skeleton & legend

Three regions on desktop; the center is the only thing that scrolls.

```
┌──────────────┬───────────────────────────────────────────┬──────────────┐
│  RAIL (L)    │  CONVERSATION (center)                     │ EVIDENCE (R) │
│              │                                            │              │
│  brand line  │  header: "answering as: support"          │  inspect one │
│  demo switch │  ┌──────────────────────────────────────┐ │  source at a │
│  + new chat  │  │ TRANSCRIPT (fixed height, scrolls,   │ │  time; empty │
│  ───────     │  │ newest at bottom, auto-scrolled)     │ │  by default  │
│  History     │  │                                      │ │              │
│  (owner-     │  │                                      │ │              │
│   scoped)    │  └──────────────────────────────────────┘ │              │
│              │  composer (pinned, always visible)         │              │
└──────────────┴───────────────────────────────────────────┴──────────────┘
```

Legend: `▣` demo-only control · `»` suggested question (clickable) ·
`◆ Source: …` human-readable source chip · `�﹅` plain honest note (not a warning)
· `⟳` loading · `[scroll]` internal scroll boundary of the fixed-height transcript.

**Phone:** single column — center fills the screen; the rail collapses behind a
`☰` History drawer; Evidence becomes a bottom sheet. (State 8b, 4b.)

---

## 1. First load / empty state

```
┌──────────────┬───────────────────────────────────────────┬──────────────┐
│ Retail Intel │  answering as: support                     │  Evidence    │
│ grounded ·   │                                            │              │
│   cited      │  ┌──────────────── TRANSCRIPT ───────────┐ │  Click a     │
│              │  │                                        │ │  source on   │
│ ▣ Demo —     │  │   Ask about reviews, products and      │ │  any answer  │
│   not a login│  │   policy. Every answer is grounded     │ │  to see the  │
│ [support_1 ▾]│  │   and cited.                           │ │  exact words │
│              │  │                                        │ │  behind it.  │
│ + New chat   │  │   Try asking:                          │ │              │
│ ──────────   │  │   » What is the return policy?         │ │  (empty)     │
│ History      │  │   » What do customers complain         │ │              │
│ (no past     │  │     about most?                        │ │              │
│  conversa-   │  │                                        │ │              │
│  tions yet)  │  └────────────────────────────────────────┘ │              │
│              │  [ Ask about reviews, complaints… ] (Send)  │              │
└──────────────┴───────────────────────────────────────────┴──────────────┘
```

- **Shown:** product line **"grounded · cited"** (G3 — no `$0/query`); reassurance
  scope header **"answering as: support"** (G4 — role half only, no intent); the
  demo switcher **set apart and labelled "Demo — not a login"** (G7/G8); plain
  tagline + 2–3 **suggested starters** (`»`, role-specific, JTBD-3); empty History
  with a plain "no past conversations yet"; empty Evidence with a plain prompt.
- **NOT shown:** no SESSION panel (G1), no cost line (G3), no routing/intent (G4),
  no instrumentation anywhere.
- **Binds (conceptual):** starters = role-based suggestion set; scope header =
  active role; switcher options = demo identities; History = owner-scoped thread
  list (empty).

---

## 2. Loading / thinking state

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ What is the return policy?           │          │
│  │ └──────────────────────────────────────┘          │
│  │                                                    │
│  │   ⟳  Looking through the sources…                  │   ← single plain line
│  │                                                    │
│  └────────────────────────── [auto-scrolled] ────────┘
│  [ … ] (Send — disabled while working)
```

- **Shown:** the user's question echoed as a turn; one calm **"Looking through the
  sources…"** line with a quiet progress affordance; composer disabled.
- **NOT shown:** NO stage pipeline (`routing / retrieving (scoped) / grounding /
  answer`) — that exposes internal stages; replaced by one plain phrase (G2).
- **Binds:** in-flight flag for the active turn; echoed question text.

---

## 3. Clean grounded answer

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ What is the return policy?           │          │
│  │ └──────────────────────────────────────┘          │
│  │                                                    │
│  │ Most items can be returned within 30 days of       │
│  │ delivery for a full refund, provided they are in   │
│  │ original condition. Opened electronics follow a    │
│  │ 14-day window.                                     │
│  │                                                    │
│  │ ◆ Source: return-refund policy                     │   ← human-readable chips
│  │ ◆ Source: electronics warranty guide               │
│  │                                                    │
│  │ You might also ask:                                │
│  │ » Do opened electronics qualify for a refund?      │   ← suggested follow-ups
│  │ » How long do refunds take to process?             │
│  └────────────────────────── [auto-scrolled] ────────┘
│  [ Ask a follow-up… ] (Send)
```

- **Shown:** answer in **plain language**; evidence as **human-readable source
  chips** `◆ Source: return-refund policy` (G6); **suggested follow-ups** beneath
  (JTBD-3); the reassurance scope header persists above.
- **NOT shown:** NO footer chips — no route pill, no `grounded (extractive/llm)`,
  no `⏱ ms`, no `$`, no `why ▾`, no tokens/memory line (G2). A clean grounded
  answer carries **no badge at all** (brief §4 criterion 4).
- **Binds:** answer text = composed answer body; chips = citations rendered as
  readable source labels (not raw `source_id`); follow-ups = suggestion set.

---

## 4. Click-to-inspect a source chip

### 4a — desktop (right dock)

```
│  │ ◆ Source: return-refund policy  ◄─ clicked          │ │  Source:          │
│  │ ◆ Source: electronics warranty guide                │ │  return-refund    │
│  │                                                     │ │  policy           │
│  │ (answer text, chip now marked active)               │ │                   │
│  │                                                     │ │  "Items may be    │
│  │                                                     │ │   returned within │
│  │                                                     │ │   30 days for a   │
│  │                                                     │ │   full refund.    │
│  │                                                     │ │   Contact [EMAIL] │
│  │                                                     │ │   to start a      │
│  │                                                     │ │   return."        │
│  │                                                     │ │                   │
│  │                                                     │ │  (exactly ONE     │
│  │                                                     │ │   source shown)   │
```

### 4b — phone (bottom sheet)

```
┌─────────────────────────┐
│ ◆ Source: return-refund…│  ← tap a chip
├─────────────────────────┤
│ Source: return-refund   │
│ policy            [×]   │
│ "Items may be returned  │
│  within 30 days… [EMAIL]│
│  to start a return."    │
└─────────────────────────┘  (sheet over transcript; tap × / backdrop to close)
```

- **Shown:** exactly **one** source at a time (inherited one-at-a-time rule); the
  **PII-redacted snippet verbatim**, including redaction tokens like `[EMAIL]` /
  `[PHONE]` shown as-is; the clicked chip marked active; clicking a different chip
  **replaces** (never stacks).
- **NOT shown:** NO raw `source_id`, NO JSON, NO internal ids (G6); the UI never
  un-redacts or fabricates — a missing snippet shows a plain "snippet unavailable"
  note, never invented text.
- **Binds:** snippet = the already-redacted citation snippet; title = the readable
  source label; `null` snippet → honest unavailable note.

---

## 5. Honest / fallback states (re-worded as reassurance)

### 5a — verbatim evidence (answer could not be fully verified)

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ Does the X200 headset have a mic mute?│         │
│  │ └──────────────────────────────────────┘          │
│  │                                                    │
│  │ �﹅ Here are the exact words from the sources:      │   ← reassurance, not a warning
│  │                                                    │
│  │  "The X200 includes an inline mic with a           │
│  │   dedicated mute switch on the cable."             │
│  │                                                    │
│  │ ◆ Source: X200 product manual                      │
│  └────────────────────────── [auto-scrolled] ────────┘
```

- **Shown:** a short, plain lead **"Here are the exact words from the sources:"**
  then the verbatim quoted evidence + its source chip. Framed as *more*
  trustworthy, not an error (JTBD-2).
- **NOT shown:** NO `grounding (extractive)`, NO `llm draft blocked`, NO `⚠`, NO
  "could not be fully verified" / "verbatim extract" system wording (G5). No raw
  grounding tokens anywhere.
- **Binds:** triggered when the composed answer is a verbatim/extractive fallback;
  quote = the evidence body; the forbidden-token list must not appear in copy.

### 5b — numbers couldn't be computed (SQL/compute failure)

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ What's our average rating this quarter?│        │
│  │ └──────────────────────────────────────┘          │
│  │                                                    │
│  │ �﹅ We couldn't calculate the numbers for this one  │   ← plain, no "query failed"
│  │    — here's what customers actually said:          │
│  │                                                    │
│  │ Customers frequently mention improved battery      │
│  │ life and faster shipping this season, though some  │
│  │ note packaging damage on arrival.                  │
│  │                                                    │
│  │ ◆ Source: recent customer reviews                  │
│  └────────────────────────── [auto-scrolled] ────────┘
```

- **Shown:** plain lead **"We couldn't calculate the numbers for this one — here's
  what customers actually said:"** then the review-based answer + source chip. No
  empty chart placeholder, no broken-metric slot.
- **NOT shown:** NO "The data query failed, so metrics and trends are hidden" (G5),
  NO `sql_error`, NO `sql_rag`, NO latency/cost. The *departure* gets one plain
  note and nothing else (brief §4 criterion 4).
- **Binds:** triggered by the SQL/compute-failure condition; text = the
  review-grounded remainder; copy re-authored from the raw degradation sentence.

---

## 6. Vague follow-up resolving to a cited answer (carry-forward acceptance criterion)

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ What do customers complain about with │          │
│  │ │ our wireless earbuds?                 │          │
│  │ └──────────────────────────────────────┘          │
│  │ The most common complaints are intermittent        │
│  │ Bluetooth dropouts and a short battery life after   │
│  │ a few months of use.                                │
│  │ ◆ Source: earbuds customer reviews                  │
│  │                                                     │
│  │ ┌ you ─────────────────────────────────┐          │   ← vague follow-up
│  │ │ and the fix?                          │          │
│  │ └──────────────────────────────────────┘          │
│  │ For the dropouts, customers report that re-pairing  │
│  │ the earbuds and updating firmware resolves it in    │
│  │ most cases.                                         │
│  │ ◆ Source: earbuds customer reviews                  │
│  │ ◆ Source: earbuds setup guide                       │
│  └────────────────────────── [auto-scrolled] ────────┘
│  [ Ask a follow-up… ] (Send)
```

- **Shown:** the vague **"and the fix?"** follows the prior turn and resolves to a
  **cited** answer (the conversation carries context); previous turn stays visible
  above. This is the carry-forward acceptance criterion **in action** — question +
  vague follow-up, both cited, surface clean.
- **NOT shown:** NO memory/history-turns-used line, NO routing change label, NO
  metrics — the user never sees that a follow-up was "resolved" by memory (G1/G2/G4).
- **Binds:** follow-up posts within the active thread (continuity handled behind
  the surface); both turns bind to their own answer + chips.

---

## 7. Bounded, fixed-height, auto-scrolled transcript (multiple stacked turns)

```
│  │ ▲ (earlier turns above — scroll up to reach)       │ │   ← [scroll] top boundary
│  │ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │ │
│  │ ┌ you ─┐  … turn 3 …                                │ │
│  │ answer 3  ◆ Source: …                               │ │
│  │ ┌ you ─┐  … turn 4 (newest) …                       │ │
│  │ answer 4  ◆ Source: …                               │ │   ← newest pinned at bottom
│  └──────────────────────── [auto-scrolls on new] ──────┘ │      after each answer
│  [ Ask a follow-up… ] (Send)                              │   ← composer always pinned
```

- **Shown:** turns **stack** oldest→newest inside a **fixed-height region that
  scrolls internally**; newest answer auto-scrolled into view; composer stays
  pinned; older turns reached by scrolling up or via the History rail (state 8).
- **NOT shown:** the page itself does **not** grow unbounded (G8); after N turns
  the page height is stable (brief §4 criterion 5).
- **Binds:** ordered turns of the active thread; scroll-to-bottom on each new turn.

---

## 8. History rail (owner-scoped)

### 8a — desktop

```
┌──────────────┐
│ Retail Intel │
│ grounded ·   │
│   cited      │
│              │
│ ▣ Demo —     │   ← set apart, labelled; switching reloads the rail to that owner
│   not a login│
│ [support_1 ▾]│
│              │
│ + New chat   │
│ ──────────   │
│ History      │
│ ┌──────────┐ │
│ │ Return    │ │  ← row = plain label (first question), relative time beneath
│ │ policy…   │ │
│ │ 2h ago    │ │
│ ├──────────┤ │
│ │ Earbud    │ │  ◄ active (reopened) — marked current
│ │ complaints│ │
│ │ yesterday │ │
│ ├──────────┤ │
│ │ Return    │ │
│ │ window…   │ │
│ │ 3 days ago│ │
│ └──────────┘ │
└──────────────┘
```

- **Shown:** **owner-scoped** list of the active identity's past conversations;
  each row a **plain label** (derived from the first question) + relative time;
  click to **reopen** (restores that thread's turns into the transcript); **+ New
  chat** starts fresh; exactly one row marked active. Switching the demo identity
  reloads the rail to that owner's conversations only (owner-scoping made visible).
- **NOT shown:** NO `thread_id`/`user_id` on rows, NO turn counts styled as
  metrics, NO cross-owner or cross-role threads (G1; governance intact).
- **Binds:** rows = owner-scoped thread list (label + relative time); click =
  reopen that thread; active = current thread.

### 8b — phone (drawer)

```
┌─────────────────────────┐        ┌─────────────────────────┐
│ ☰  answering as: support│  tap→  │ History            [×]  │
│                         │  ☰     │ ▣ Demo — not a login    │
│  (transcript fills      │        │ [support_1 ▾]           │
│   the screen)           │        │ + New chat              │
│                         │        │ ─────────────           │
│  [ Ask… ] (Send)        │        │ • Return policy…  2h    │
│                         │        │ • Earbud complaints yd  │
└─────────────────────────┘        └─────────────────────────┘
                                    (off-canvas; × / backdrop closes; focus trapped)
```

- **Shown:** `☰` opens History off-canvas; the demo switcher + New chat live inside
  the drawer; transcript fills the screen when closed.
- **NOT shown:** no operator values; the switcher stays labelled demo-only even in
  the drawer (G7/G8).

---

## 9. Error states (plain language)

### 9a — nothing found in scope

```
│  │ ┌ you ─────────────────────────────────┐          │
│  │ │ What's the refund policy for boats?   │          │
│  │ └──────────────────────────────────────┘          │
│  │                                                    │
│  │ I couldn't find anything about that in the         │
│  │ sources you have access to. Try rephrasing, or     │
│  │ ask about a different product or topic.            │
│  │                                                    │
│  │ » What is the return policy?                       │   ← offer a way forward
│  └────────────────────────── [auto-scrolled] ────────┘
```

- **Shown:** a plain "couldn't find anything in the sources you have access to"
  message + a recovery suggestion. Scope phrased in **user terms** ("the sources
  you have access to"), not "not filtered" / "no session trust" (G4/G5).
- **NOT shown:** NO stack trace, NO "no evidence within access scope" jargon
  verbatim, NO status codes.

### 9b — something went wrong (request/system error)

```
│  │ Something went wrong getting that answer. Please    │
│  │ try again in a moment.                             │
│  │                                   [ Try again ]     │
```

- **Shown:** one calm sentence + a **Try again** action (never a silent blank
  state — per code_style frontend rule).
- **NOT shown:** NO HTTP status, NO `detail` payload, NO provider/model, NO
  latency/trace id. Operator detail for a real error lives in the audit/
  observability planes, not the chat (G1).
- **Binds:** triggered on a failed request; retry re-posts the last question.

---

## 10. State coverage checklist (ties to brief §4)

| State | Covered | Key gaps enforced |
|---|---|---|
| Empty / first load | §1 | G3, G4, G7, G8 |
| Loading | §2 | G2 (no stage pipeline) |
| Clean grounded answer | §3 | G2, G6 |
| Inspect source chip | §4a/4b | G6 |
| Verbatim fallback | §5a | G5 |
| SQL/compute failure | §5b | G5 |
| Vague follow-up (acceptance criterion) | §6 | G1, G2, G4 |
| Bounded scrollable transcript | §7 | G8 |
| History rail (desktop + drawer) | §8a/8b | G1, G7, G8 |
| Error — nothing found | §9a | G4, G5 |
| Error — system | §9b | G1 |

**Operator-value audit across all sketches:** `thread_id`/`session_id` = 0,
tokens = 0, `cost_usd` = 0, latency = 0, intent/routing label = 0, `tool_path` = 0,
model slug = 0, provider = 0, raw `audit` JSON = 0. ✓ (brief §4 criterion 1).

---

*Next (gated on D2 approval of the hi-fi mockup):
`design/iteration-4/mockups/<surface>.html` — the theme-aware hi-fi design that
makes these states real. This is wireframes only — no pixels, no HTML.*
