---
type: brainstorm
title: 'Epic A — Trust-bug hardening (Q-6 Reveal · S-2b Summary time)'
status: 'Stage-1 CLOSED (2026-07-09) — gate: A1=D6+D1 (clarify UI FR-D6 then wire Reveal as gated submit alias); A0=remainder docs; A2=D3 triage parallel; D2/D5/D7 deferred'
authored: 2026-07-09
---

# Brainstorm — Epic A Trust-bug hardening

> **SDD Stage-1 artifact** (`brainstorm`). Premise audit + directions for Epic A
> ([sprint board](preact-parity-sprint-board-A.md)). Contains **no code**.
>
> **Status:** Stage-1 CLOSED — 2026-07-09 · **Owner:** Rajnish Khatri
> **Related:**
> - Board: [`preact-parity-sprint-board-A.md`](preact-parity-sprint-board-A.md)
> - Epics: [`preact-parity-epics.md`](preact-parity-epics.md)
> - A0 (prior): [`preact-parity-A0-correct-record.spec.md`](preact-parity-A0-correct-record.spec.md)
> - Advance → A1: [`preact-parity-A1-reveal.spec.md`](preact-parity-A1-reveal.spec.md)

---

## 1. Intent (restated)

Eliminate controls that are *present but lie*. Findings in scope: `Q-6` (dead
"Reveal answer" button) and `S-2b` (Summary "time" showed "0 min").

---

## 2. Premise audit

Every load-bearing premise checked against the working tree (2026-07-09).

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | `quiz-reveal` has no `onClick` (trust bug) | **verified** | [QuizView.tsx:105-111](../../frontend/components/quiz/QuizView.tsx) |
| P2 | `QuizItemVM` omits `answerLetter` (FR-D5) | **verified** | [quiz_item_vm.ts:8-11,24-45](../../frontend/lib/translators/quiz_item_vm.ts) |
| P3 | UI FR-D5 / FR-D6 are real and **compatible** | **verified** (contradiction **refuted**) | [ui.spec.md:173-177](preact-english-coach-ui.spec.md) |
| P4 | Engine reuses FR-D5/D6 IDs for unrelated reqs | **verified** | [engine.spec.md:173-187](preact-english-coach-engine.spec.md) |
| P5 | `decisions.md` has FR-D5/D6 resolution | **verified absent** | grep of [decisions.md](../adr/decisions.md) |
| P6 | Epics doc still claims FR contradiction | **verified stale** | [preact-parity-epics.md:97,101,112](preact-parity-epics.md) |
| P7 | QuizView comment still says "sanctioned control" | **refuted** (already softened) | [QuizView.tsx:104](../../frontend/components/quiz/QuizView.tsx) |
| P8 | Prototype Reveal = in-place letter show | **refuted** | Prototype shares `submit` → Feedback ([Prototype.dc.html:114,242](../../PreAct/UI-Design/English%20Coach%20-%20Prototype.dc.html)) |
| P9 | Board Options 1/3 (gated `revealed` + VM letter) match prototype | **refuted** | Invents non-prototype behavior; Feedback already teaches the answer |
| P10 | Summary time plumbing exists + unit-tested | **verified** | [session_summary_vm.ts:49-54](../../frontend/lib/translators/session_summary_vm.ts) |
| P11 | `use_summary` stale cache causes "0 min" | **refuted** | Fresh `sessionRepo.get` ([use_summary.ts:70-71](../../frontend/components/summary/use_summary.ts)) |
| P12 | Capture "0 min" = sub-minute session | **needs-probe** | `Math.round(ms/60000)` → `"0 min"` for sub-minute closed sessions |
| P13 | E2E asserts `summary-time` | **refuted** (skipped) | [full-session.spec.ts:137-142](../../frontend/e2e/learn/full-session.spec.ts) |
| P14 | No tests touch `quiz-reveal` | **verified** | repo-wide grep |

**Corrected framing after audit (P8/P9 re-pose):** A1 is **not** "expose
`answerLetter` on `QuizItemVM` after submit." It is: close a dead labelled
control so it matches prototype intent (**Reveal = low-emphasis submit→Feedback**)
or deliberately drop the affordance and amend FR-D6.

**D0 (blocking hygiene):** A0 is not fully landed — remaining: `decisions.md`,
epics contradiction language, VISUAL-report sync. Comment rewrite largely done.

---

## 3. Directions (six)

### High-probability

- **D1 — Reveal as gated submit alias** *(implementation lead)* — wire
  `quiz-reveal` → same `onSubmit` as Submit; disable when `!canSubmit`. Zero new
  reducer/VM field. Pattern: [QuizView.tsx:124-133](../../frontend/components/quiz/QuizView.tsx).
- **D2 — Remove Reveal + amend UI FR-D6** — delete button; update UI spec.
- **D3 — A2 triage + e2e guard** — live multi-minute repro; close as artifact or
  fix; assert `summary-time`. `needs-probe`.

### Exploratory

- **D4 — Demand-side / no second reveal surface** — same outcome as D1; Feedback
  is the answer surface (G1: resist new abstraction).
- **D5 — Class-level dead-control ratchet** — arch/lint for inert testid buttons.
  Deferred behind Epic A exit.
- **D6 — Spec-first clarify FR-D6 then implement** — amend UI FR-D6(+a) to match
  prototype interaction table, then D1.
- **D7 — `"<1 min"` copy** — product polish on `timeTile()`; independent of A2 bug.

---

## 4. Hypotheses for D1 (validated)

| H | Claim | Result |
|---|---|---|
| H1 | Prototype Reveal aliases `submit` | **validated** — Prototype.dc.html:114,242 |
| H2 | FR-D5 only constrains the hint | **validated** — ui.spec.md:173-175 |
| H3 | Feedback already shows correct letter | **validated** — FeedbackView FR-E1/E4 |
| H4 | Disabled-when-unselected stops lying | **validated by analogy** — Submit gate |
| H5 | Zero new reducer action | **validated** — reuse `onSubmit` |
| H6 | A0 comment rewrite still required | **rejected** — comment already accurate |

---

## 5. Gate decision (binding on sdd-spec)

| Axis | Choice | Id |
|---|---|---|
| A1 direction | Clarify UI FR-D6 then wire Reveal as gated submit alias | **D6+D1** |
| A0 | Finish docs remainder (epics / VISUAL / `decisions.md`); A0 spec already authored | **A0-first** (or same PR as A1 docs half) |
| A2 | Triage + e2e guard; parallel to A1 | **D3** / `A2-parallel` |
| Deferred | Remove (D2), class ratchet (D5), `<1 min` copy (D7) | behind Epic A exit / product call |

Advance → **sdd-spec** for A1 (`preact-parity-A1-reveal.spec.md`). A0 continues
under its existing spec/plan pair.
