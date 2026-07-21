---
title: 'Eng-coach Gen2 / v2 adoption — exploratory session notes + adoption todo'
type: design
status: 'Draft — direction recommended (Path A); awaiting human lock before sdd-spec'
date: 2026-07-17
owner: Rajnish Khatri
related:
  - docs/questionbank/coach-bank-gen2-qa-report.md
  - docs/questionbank/coach-item-bank-gen2.promoted.json
  - docs/questionbank/coach-bank-hints-gen2.json
  - docs/plan/coach-item-bank-live.promoted.json
  - docs/plan/coach-bank-hints.seed.json
  - research/eng_coach_v2_pedagogy_spec.md
  - docs/adr/0012-subject-coach-context-contract-hint-ladder.md
  - docs/plan/preact-tier1-misconception-taxonomy.brainstorm.md
  - docs/width-design-ui-session-artifacts/locked-spec-artifacts/PreACT-English-Coach-LOCKED-Spec.md
tags: [eng-coach, gen2, v2-pedagogy, question-bank, session-notes]
---

# Eng-coach Gen2 / v2 adoption — exploratory session (2026-07-17)

> **What this is.** Capture of a devil's-advocate + A/B + hybrid-critique session on
> whether/how to adopt the Gen2 question bank and v2 coaching pedagogy into the live
> English coach. Not an Accepted SDD spec — use as input to Phase 0 locks → `sdd-spec`.
>
> **Recommended direction:** Path A — moment-based pedagogy + Gen2-style ladders on
> **reviewed** fuel first; treat the 1000-item Gen2 dump as a curated pool, not a drop-in.

---

## 1. Intent of the session

1. Critically judge Gen2 items + hints before integration.
2. Map Gen2 against v2 research (Axis A runtime vs Axis B fuel).
3. A/B Gen1 ladder (`probe → concept → direction`) vs Gen2 ladder
   (`pump → hint → prompt → assertion`) for PreACT ages 12–18 — same questions / same
   wrong options (both Gen2-fixed and inverse Gen1-fixed constructs).
4. Stress-test hybrid ideas (layout-gated coach, skill-gated coach).
5. Draft an adoption approach grounded in repo reality.

---

## 2. Current state (verified against tree)

### 2.1 Production (Gen1) — what `/learn` serves

| Asset | Path | Count |
|-------|------|------:|
| Promoted items | `docs/plan/coach-item-bank-live.promoted.json` | 171 |
| Hint seed | `docs/plan/coach-bank-hints.seed.json` | 513 |
| Frontend emit | `frontend/lib/adapters/engine/_test_item_bank.ts` + `_hint_bank.ts` | 171 / 513 |
| Backend emit | `components/subject_coach_bank_hints.py` | 513 |

- All items + hints: `reviewed: true`.
- Ladder: exactly rungs **1–3** per item (probe / conceptual / directive).
- No `choice_letter`. Unique key today: `(question_id, rung)`.
- `misconception`: free-text on **47/171** items; **0** kebab tags / MiscLibrary.
- Wire: Zod/Pydantic `Hint.rung` = `1|2|3` only; `HintRepo` / `rungs_for_question` serve reviewed only.

### 2.2 Gen2 corpus — on disk, not wired

| Asset | Path | Count |
|-------|------|------:|
| Items | `docs/questionbank/coach-item-bank-gen2.promoted.json` | 1000 |
| Hints | `docs/questionbank/coach-bank-hints-gen2.json` (`{rows:[…]}`) | 12000 |
| QA | `docs/questionbank/coach-bank-gen2-qa-report.md` | — |

- Overlap with Gen1: **0** shared IDs.
- All rows: `reviewed: false` (machine-generated, validator-gated only).
- Hints: 12 per item = 3 wrong letters × 4 rungs; `choice_letter` on every hint.
- Item-level `misconception` field: **missing**.
- No `MiscLibrary` / per-choice `tag`; conditionality is inline per-(item, letter) text.
- Standards **33–43** present (live syllabus seed still max **32**).
- Emit scripts / coach runtime: **zero** Gen2 wiring.

### 2.3 v2 research vs built

Source of truth: [`research/eng_coach_v2_pedagogy_spec.md`](../../research/eng_coach_v2_pedagogy_spec.md).

| Axis | Spec | Built? |
|------|------|--------|
| **B — fuel** | Per-distractor tags + `MiscLibrary` (~16 × 4 rungs) | Design-only ([tier-1 taxonomy brainstorm](preact-tier1-misconception-taxonomy.brainstorm.md)) |
| **A — runtime** | `classify → verify → escalate` pump→hint→prompt→assertion | Gen1 3-rung select/paraphrase; no classifier; no assertion |

**ADR-0012** deliberately ships **no assertion rung** pre-submit; v2 Axis A allows assertion when ladder exhausted / “show answer.” That conflict needs an explicit ADR amendment — not a silent emit.

**Naming trap:** Gen2 bank ≠ full v2. Gen2 ≈ large choice-conditional corpus. Full v2 ≈ MiscLibrary + inner-loop engine + (optional) assertion policy.

---

## 3. Session findings (constraints)

| # | Finding | Constraint |
|---|---------|------------|
| F1 | Gen2 QA validators passed, but human review absent | Do **not** integrate Gen2 as-is |
| F2 | Schema gaps: rung 4, `choice_letter`, unique `(qid,rung)`, missing item `misconception` | Schema + emit work before any serve path |
| F3 | Same-item A/B: Gen2 ladder stronger for **wrong-letter unstick**; Gen1 stronger on **readiness/polish** | Prefer Gen2 **pedagogy shape** on reviewed stems |
| F4 | Layout hybrid (inline=Gen2, standalone=Gen1+freer LLM) | **Reject** — breaks Direction 2b parity; confounds learning; puts freer LLM on riskiest surface |
| F5 | Skill-swap hybrid (global level → different coach species) | **Reject as system swap**; skill = **dose** only (start rung / nudge cap / verbosity) |
| F6 | Moment-based pedagogy | **Adopt** as the product rule for ladder selection |
| F7 | Free-text `misconception` ≠ MiscLibrary | Don’t fake tier-1 clustering from Gen2 trailing `(tag)` prose |

### 3.1 Moment-based pedagogy (adopted framing)

| Moment | What’s true | Pedagogy |
|--------|-------------|----------|
| No pick yet | Stuck; no trusted choice letter | Item-level Gen1-style `probe → concept → direction` (`choice_letter` null) |
| Wrong pick known | Wrong letter selected/submitted | Choice-conditional Gen2-style ladder for **that** letter |
| Free-ask | User typed a question | Same LLM coach on **all** surfaces under ADR-0012 |
| Skill (later) | Mastery / proficiency signal | Dose knobs only — not a second coach species |

One coach chrome (Direction 2b) everywhere; layout never chooses the ladder ontology.

### 3.2 Inverse A/B pilot items (Gen1-fixed)

Useful freeze set for Phase 1 content + student A/B:

| Item id | Focus |
|---------|--------|
| `ti-gen-2b9ae16d270c28ea` | Subject–verb |
| `ti-gen-0871498e14f92745` | Comma splice |
| `ti-gen-74185039391e8c26` | Redundancy |
| `ti-gen-b149168609a7069d` | Relevance / delete |
| `ti-gen-18702ebe60cf2373` | Fragment |

---

## 4. Target architecture (summary)

```text
Moment router (Axis A — thin)
  no pick     → item-level 3-rung (Gen1-style)
  wrong letter→ choice-conditional ladder (v2-style)
  free-ask    → LLM + ADR-0012 (all surfaces)
  skill       → dose only

Fuel (Axis B — phased)
  Phase 1: reviewed Gen1 stems + authored choice-conditional ladders
  Phase 2: curated Gen2 items (human review → reviewed:true) in batches
  Phase 3: MiscLibrary tags + classify() + shared rung text
```

---

## 5. Path options

| Path | Summary | When |
|------|---------|------|
| **A (recommended)** | Phase 0 locks → Phase 1 on Gen1 stems → student A/B → selective Gen2 promote | Default |
| **B** | Parallel Gen2 human-review pipeline while Phase 1 ships (still no unreviewed emit) | If content breadth is urgent |
| **C** | MiscLibrary (Phase 3) before any Gen2 promote | Cleanest long-term; slowest ladder lift |

---

## 6. Explicitly rejected

- Shipping all 1000 Gen2 items because validators passed.
- Inline = Gen2 coach; standalone/drawer/iPhone = Gen1 + freer LLM.
- Global skill band → different coach species.
- Treating Gen2 rationale trailing `(tag)` as MiscLibrary.
- Using viewport / device as A/B assignment.

---

## 7. Adoption todo list

Checkbox list for adopting Gen2 / v2 into the eng coach. Order is dependency-aware.
**Do not start Phase 1 code until Phase 0 is human-locked.**

### Phase 0 — Lock decisions (docs / ADR)

- [x] **P0.1** Accept Path A (or explicitly lock B/C) as the adoption path. → **Path A locked (2026-07-17).**
- [x] **P0.2** Ratify moment-based pedagogy as normative (no-pick / wrong-pick / free-ask). → **Ratified.**
- [x] **P0.3** Record rejection of layout-hybrid and skill-swap-hybrid (`docs/adr/decisions.md` or short ADR). → **Recorded in `docs/adr/decisions.md` (2026-07-17).**
- [x] **P0.4** Assertion policy: keep ADR-0012 no-assertion **or** amend — assertion / rung-4 **post-feedback only** (never pre-submit reveal). → **Amend: post-feedback-only + item-type-aware; exercises ADR-0012's built-in reveal-rung trigger. Precise amendment text deferred to `sdd-spec`.**
- [x] **P0.5** Schema direction lock: unique `(question_id, choice_letter | null, rung)`; null = item-level ladder. → **Two partial unique indexes (PG + SQLite parity).**
- [x] **P0.6** Define student A/B metrics: first-rechoose accuracy, time-to-correct, nudge count, felt-helpful, leak incidents. → **Adopted as listed.**
- [ ] **P0.7** Human Accept → open `sdd-spec` for Phase 1 (EARS + plan + tasks). *(P0.1–P0.6 + P0.8 locked 2026-07-17; this gate opens `sdd-spec` next.)*

> **P0.8 (from architecture doc §7)** — pilot-emit scope: **(a) quiz-engine serve path only** locked (skip `BANK_RUNGS`; UC-3 unchanged; LLD T5 deferred). 2026-07-17.

### Phase 1 — Pedagogy on reviewed fuel (highest ROI; no Gen2 emit)

- [ ] **P1.1** Freeze pilot item set (start with §3.2 five Gen1 IDs; optionally expand to 20–50).
- [ ] **P1.2** Author choice-conditional ladders per wrong letter (pump→hint→prompt; assertion only if P0.4 allows post-feedback); source from `per_choice_rationale` / `why_tempted_md` / `misconception`.
- [ ] **P1.3** Run in-repo leak lint (`hint_leakage` / cascade) on every new rung; flip `reviewed: true` only after human pass.
- [ ] **P1.4** Schema/wire: optional `choice_letter`; extend rung literal if P0.4 requires; migrate uniqueness; update Zod + Python + both DB dialects.
- [ ] **P1.5** Emit path for pilot pack (do **not** point emit defaults at Gen2 JSON).
- [ ] **P1.6** Moment router in quiz/coach: no letter → null-letter ladder; wrong letter → that letter’s ladder; composer unchanged.
- [ ] **P1.7** Keep Direction 2b chrome identical across inline / drawer / fullscreen (parity lock).
- [ ] **P1.8** Feature-flag moment router + choice-conditional pack.
- [ ] **P1.9** Arch tests: serve path never loads `reviewed: false`; uniqueness/choice_letter invariants.
- [ ] **P1.10** Dogfood internally, then student A/B (same items; randomize **ladder pack only**).
- [ ] **P1.11** Gate: clear lift or documented no-lift before Phase 2 scale.

### Phase 2 — Curate Gen2 as a pool (content pipeline)

- [ ] **P2.1** Keep Gen2 under `docs/questionbank/` as **candidate** corpus (not live emit input).
- [ ] **P2.2** Prioritize under-covered standards/skills (33–43, rhetorical-mc, thin Gen1 skills).
- [ ] **P2.3** Extend syllabus seed for standards 33–43 before those items can sequence.
- [ ] **P2.4** Human-review pipeline: per item + its 12 hints; re-run leak checks; flip `reviewed` per row.
- [ ] **P2.5** Promote in small batches (e.g. 25–50) through existing emit → live bank.
- [ ] **P2.6** New promoted items ship with choice-conditional ladders; keep null-letter 3-rung for Moment 1 if still supported.
- [ ] **P2.7** Batch exit: zero unreviewed rows in emit inputs; QA + human sign-off recorded.

### Phase 3 — True v2 Axis B (MiscLibrary)

- [ ] **P3.1** Lock ~16 kebab `MisconceptionTag`s (human; align with tier-1 taxonomy initiative).
- [ ] **P3.2** Author `MiscLibrary` entries (pump/hint/prompt/assertion + `{underline}`/`{choice}` slots); lint with `leaks()`.
- [ ] **P3.3** Tag distractors (`Choice.tag`); deterministic `classify(wrongLetter) → tag`.
- [ ] **P3.4** Runtime: compose wrong-pick turns from library + item fill; Gen2 per-item bodies as migration source/fallback.
- [ ] **P3.5** Unlock tier-1 “Your pattern · X” only after real clusters exist (see OQ-2 brainstorm).

### Phase 4 — Axis A engine (after fuel is trustworthy)

- [ ] **P4.1** Explicit escalate state machine (attempt-gated), matching v2 pedagogy spec.
- [ ] **P4.2** Deterministic `composeTurn` fallback when LLM unavailable.
- [ ] **P4.3** Reasoning-trace fields for eval / Langfuse.
- [ ] **P4.4** Assertion UX (“Show the answer”) **only if** P0.4 ADR amended.

### Hard blockers (must clear before any Gen2 serve)

- [ ] **B1** `reviewed: false` hard gate — never bypass.
- [ ] **B2** Wire/schema accept `choice_letter` + uniqueness change.
- [ ] **B3** Rung-4 / assertion policy reconciled with ADR-0012.
- [ ] **B4** Emit scripts pointed only at reviewed inputs.
- [ ] **B5** Syllabus coverage for any promoted standard > 32.

---

## 8. Suggested calendar (sketch)

| Window | Focus |
|--------|--------|
| Week 0 | Phase 0 locks + ADR sketch |
| Weeks 1–2 | Phase 1 schema + 5–20 item pack + flagged moment router |
| Weeks 2–3 | Dogfood → small student A/B |
| Weeks 3–5 | Phase 2 first curated Gen2 batch (only if P1.11 justifies) |
| Parallel / later | Phase 3 taxonomy (Epic E OQ-2) |
| Later | Phase 4 full inner-loop engine |

---

## 9. Next step

Human lock on **Path A/B/C** and Phase 0 checklist → then `sdd-spec` for Phase 1
(`eng-coach-gen2-v2-adoption.spec.md` + plan + tasks). Do not emit Gen2 into
`_hint_bank.ts` / `BANK_RUNGS` until Phase 2 batch gates pass.
