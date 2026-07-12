---
title: 'Epic E1b — /learn/skill remaining carve-outs (accuracy read + coach seed; tier-1 deferred): SDD Stage-1 brainstorm'
type: brainstorm
epic: E
sub_epic: E1b
stage: 1
scope: 'The two honest carve-outs E1a §1.1 left open (accuracy aggregation, tier-1 aggregate callout) + the coachEntry lesson→coach seed contract (OQ-3/D4c). Three INDEPENDENT-PARALLEL deliverables.'
date: 2026-07-12
status: 'Accepted — human direction gate closed 2026-07-12; advancing to sdd-spec'
artifact: Eng-coach-ui-design/e1-learn-skill-delivery/ + Eng-coach-ui-design/lesson-delivery/
parent: docs/plan/preact-parity-epic-E1a.spec.md
supersedes_scope_of: 'the design spec §12 original 8-item E1b bucket (returning/refresher/tier-2-3 callout/dueChecklist already shipped in E1a per the 2026-07-11 gate)'
method: 'sdd-brainstorm — 43-agent audit workflow (5 parallel readers × design-contract + current-impl per seam → adversarial verify every load-bearing premise → synthesis) + independent data-gate probes; all hypotheses validated against file:line'
decisions:
  - 'HG-1: close the LIVE dashboard mastery≠accuracy bug (D0) now, separate PR, ahead of E1b'
  - 'HG-2: priority order (a) accuracy → (c) coach seed → (b) tier-1'
  - 'HG-3: OQ-1 accuracy window decided at spec time (last-N vs rolling)'
  - 'HG-4: tier-1 needs-probe RAN → hard-confirms DEFER (0 clusters; blocked on OQ-2 pipeline)'
outcome: 'E1b lesson-surface = D0 (hygiene) + D1 (accuracy) + D2 (coach seed). Tier-1 parked behind the reviewed OQ-2 tag-clustering pipeline (separate initiative).'
---

# Epic E1b — the remaining `/learn/skill` carve-outs

> **The framing.** E1a shipped the full 3-context `/learn/skill` surface with **two honest
> carve-outs** (spec §1.1) — `accuracyStat` self-omits, and the tier-1 "Your pattern · X"
> aggregate callout is deferred — plus a button-only `coachEntry` **seam**. E1b closes exactly
> those three gaps. A 2026-07-11 gate had already pulled `returning`/`refresher`/tier-2-3
> callout/`dueChecklist` **into E1a**, so the true E1b remainder is **narrower** than the design
> spec's original §12 bucket: the two carve-outs + the coach-seed contract, nothing more.

## Design source-of-truth

- **`Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md`**
  — §3.4/3.5 (callout tiers, accuracy/due data), §5.4 (accuracy data-gating), FR-BLK-19/20
  (accuracyStat + coachEntry render contracts), §12 phasing (E1a vs E1b), §14 open questions
  (OQ-1..OQ-5), the traceability map.
- **`Eng-coach-ui-design/e1-learn-skill-delivery/specs/Adaptive-Lesson-Decisions.md`** —
  D4c (coach seed), D6-1 (aggregate callout), D7-2 (accuracy ≠ mastery), I1 (callout fallback tiers).
- **`docs/plan/preact-parity-epic-E1a.spec.md`** §1.1 — the two honest carve-outs, verbatim.

## The three deliverables — independent, not sequenced

| # | Deliverable | Data reality (**measured**) | Verdict |
|---|-------------|------------------------------|---------|
| **(a)** | **Accuracy aggregation** (`accuracyStat`) | `attempt.correct` + `attempt.question_id→skill_id` join is **live in prod** (`drizzle_engine_db.ts:500-534`, `listSessionSkillIds`). Render authored-dormant: `skill_detail_vm.ts:366-371` = self-omit guard **then** unconditional `return null` ("today always null"). | 🟢 **Clean read-join.** Biggest *code* lift (needs a new 6-bar chart primitive + ≥6-session fixtures), zero data risk. |
| **(b)** | **Tier-1 "Your pattern · X" callout** | Live serving bank: **47/171 tagged, all 47 tag strings distinct → 0 clusters**; seed bank + `Eng-coach-ui-design/` copy = **0 tags**. `missTag` captured nowhere. | 🔴 **`gated-on-data: 0`.** The "reviewed tag-clustering pipeline" has no input corpus. **Probe (below) hard-confirms defer.** |
| **(c)** | **`coachEntry` skill-seed** | Entry EXISTS (bare `<Link>`, `SkillDetailView.tsx:370-390`) but carries **no seed** → cold-opens the coach against a stale/null pin. Skill-only *seed* un-expressible: `CoachSurfacePin.questionId` required (`coach_surface_vm.ts:25`). | 🟡 **Contract-authoring, frontend-ring only.** No middleware change. |

The three share a **root cause** (honest data/contract absent), **not code**. So this is a
**priority** decision, not a dependency chain.

### Refuted premise, re-posed (the coach "entry vs seed" distinction)

The audit refuted "the coach has no skill-only path." Corrected framing: the `/learn/skill`
`CoachEntryBlock` is **already a skill-scoped ENTRY** — but it carries **no seed at all** (a bare
`<Link>`, no pin write), landing the learner on whatever stale/null pin sits in the
`coach_thread_store` singleton. What is genuinely absent is a skill-only **SEED** that yields a
valid `coach_context` (`CoachSurfacePin.questionId` required; `assembleCoachContext`/`WireCoachContext`
demand a full `Question`). D2 widens exactly those two seams via a **discriminated-union pin** —
it does not invent a new entry mechanism. The cold-open-against-stale-pin is the real latent bug D2 closes.

## D0 — a LIVE, shipped defect (surfaced by the audit; not a carve-out)

`bucket_card_vm.ts:34,42` renders `SkillState.mastery` (FSRS **retrievability**) as `masteryPct`
with **no `accuracyPct` and no guard/comment** separating the two — an all-wrong-but-retrievable
card shows a high "mastery %". This is the **exact** mastery≠accuracy conflation (`DATA-ACC-1`/
`GUARD-ACC-1`) that E1b's accuracy read exists to keep *out* of the lesson — already live in the
dashboard. **Same defect class, two VMs** (`bucket_card_vm` + `skill_detail_vm.accuracyStat`) =
class-over-instance. It is **F1** in `docs/plan/preact-learn-followups.notes.md:21` /
`preact-dashboard-mastery-retrievability-bug` memory. Minimal fix = mastery-distinct label/footnote
+ red-green test, **no read needed**, separate PR.

## Directions (7)

| id | kind | direction | follows pattern | ADR trigger |
|----|------|-----------|-----------------|-------------|
| **D0** | blocking-defect | Close the live dashboard mastery≠accuracy bug | `bucket_card_vm.ts:17-42` + a failing test | none (label-only) |
| **D1** | high-probability | Per-skill accuracy read = new `AttemptRepo.accuracyBySkill()` + EngineDb projection | TutorialRepo/ProgressRepo 4-file ADR-0028 pattern; join reuses `drizzle_engine_db.ts:500-534` | new read-seam → ADR-or-`decisions.md` |
| **D2** | high-probability | Skill-only coach **seed**: discriminated-union pin (item-pin \| lesson-pin) + lesson-context `coach_context` | quiz store-write-then-navigate (`quiz page.tsx:411-418`) | OQ-3/D4c → own decision record; no middleware |
| **D3** | high-probability | Deterministic tag-cluster from **existing** tags (demand-side, no pipeline first), pure translator | `newest_due_miss.ts:35-57` | G1 if the hand-map becomes durable |
| **D4** | exploratory | Miss-**count** substitute for tier-1 ("You've missed N in {skill}") | `use_coach_surface.ts:29-48` `countMissesOnSkill` | **DEVIATES I1 tier-3** → ADR + spec re-open |
| **D5** | exploratory | Unify accuracy+mastery under one shared translator, consumed by dashboard **and** lesson (class-over-instance) | T1 pure-translator; consumers `bucket_card_vm` + `skill_detail_vm` | G1 shared abstraction → ADR; depends on D1 |
| **D6** | exploratory | Capture the misconception tag at miss-time on the attempt row (schema shift) | (new abstraction) `engine_entities.ts:224-239` + both DB schemas | Drizzle migration → ADR; **wrong lever** (still 47/47 distinct) |

**Leading directions:** D0 (hygiene), D1 (accuracy), D2 (coach seed). D3/D4/D6 are the tier-1
options (mutually exclusive, each needs a human/ADR ruling before build). D5 is a post-D1 consolidation.

### Validated hypotheses (leading directions)

- **D1 works** — raw correctness + the exact join exist and are proven in prod: `accuracy =
  count(correct)/count(*)` grouped by skill needs no new capture (`drizzle_engine_db.ts:500-534`,
  `engine_entities.ts:230`). **Safe** — follows the ratified read-only 4-file pattern (ADR-0028),
  adds no write/provenance surface (raw attempts are not reviewed-gated). **Safe** — flipping the
  self-omit stub cannot fabricate a trend: `FR-CMP-11` rejects empty-state; the block self-omits
  on no data.
- **D2 works** — the `coachEntry` VM already carries `skillId`+`skillName` and the coach display
  chrome already runs on `skillId` alone (`coach page.tsx:51-67`); only the pin schema + wire
  `coach_context` block a skill-only seed. **Safe** — entirely frontend-ring: the BFF sanitizer
  fails closed to `pre_submit` on absent `question_id` (the correct lesson default); middleware
  branches on `agent_id` (orthogonal).
- **D3 works** as a pure translator over already-fetched data (mirrors `newest_due_miss.ts`), and
  **is safe** because GUARD-CALL-1 forces self-hide below ≥2 clusters — but the sub-claim "a small
  hand-normalization map is not an uncontrolled taxonomy" is **REJECTED**: it *is* the smallest
  instance of the OQ-2 pipeline and inherits G1 once durable.

## The tier-1 needs-probe (HG-4) — RAN 2026-07-12, hard-confirms DEFER

Measured over the live serving bank (`_test_item_bank.ts` = the emitted
`docs/plan/coach-item-bank-live.promoted.json`), whose `misconception` tags are **full free-text
prose sentences** ("using casual 'seen' for the past participle", "hearing 'could've' as 'could of'"):

- **73% untagged** (124/171) — matches the spec.
- **Exact-match clusters: 0** whole-bank (all 47 tag strings distinct) **and 0 within-skill** —
  no skill has ≥2 items sharing an identical tag.
- **Normalization ceiling is noise, not signal:** the only same-skill tag-pair word overlaps are
  stop-word-adjacent junk (`{because}`, `{feels, like}`, `{like}`). No genuine shared misconception
  theme exists to cluster on. A normalization map here would **manufacture** categories, not
  discover them — the exact uncontrolled-mini-taxonomy risk OQ-2 exists to prevent.

**⟹ Tier-1 is genuinely blocked on the reviewed OQ-2 pipeline** (author a controlled taxonomy →
tag the bank → cluster), which is its own initiative — **not E1b lesson-surface code**. Even the
deterministic D3 path renders nothing on today's data, and no honest normalization changes that.

## Human direction gate — CLOSED 2026-07-12

| Q | Decision |
|---|----------|
| **HG-1** — close the live D0 dashboard bug now? | **YES — separate PR, ahead of E1b** |
| **HG-2** — E1b priority order? | **(a) accuracy → (c) coach seed → (b) tier-1** |
| **HG-3** — OQ-1 accuracy window? | **Decide at spec time** (last-N vs rolling; enumerate in Stage 2) |
| **HG-4** — tier-1 strategy? | **Run the probe first → hard-confirms DEFER** (tier-1 parked behind OQ-2) |

## Outcome + next stage

**E1b lesson-surface = D0 (hygiene, separate PR) + D1 (accuracy) + D2 (coach seed).** Tier-1
formally parked behind the OQ-2 tag-clustering pipeline with evidence (the probe above).

**Advance → `sdd-spec`**, three specs in priority order, ADR posture pre-scoped:

1. **D0** — dashboard mastery≠accuracy guard (light spec / `decisions.md` line; no ADR, label-only). Independent; can start immediately.
2. **D1** — per-skill accuracy read + `accuracyStat` render (new `AttemptRepo.accuracyBySkill()` following ADR-0028; ADR-or-`decisions.md` for the read seam; **OQ-1 window resolved in the spec**).
3. **D2** — skill-only coach seed (discriminated-union pin + lesson-context `coach_context`; own OQ-3/D4c decision record; frontend-ring only).
