---
type: decision-record
title: 'ADR-0018: Subject-Coach rubric specificity revision — a CLEAN carve-out for mechanism-teaching + open probes'
status: accepted
created: 2026-07-05
updated: 2026-07-06
owner: Rajnish Khatri
related: 0017-subject-coach-rubric-revision.md, coach-rubric-specificity-revision.spec.md, coach-goldset-enable-policy.spec.md, subject-coach-agent.plan.md
tags: [decision-record]
---

# ADR-0018: Subject-Coach rubric specificity revision — a CLEAN carve-out for mechanism-teaching + open probes

**Status:** Accepted — 2026-07-06 (was Proposed 2026-07-05; ratified at the
tasks→implement human gate. The exit bar it sets — a FRESH-split re-cert clearing
**both** TNR≥0.95 and TPR≥0.90 with margin — remains the gate the implementation
must still pass; ratifying the *decision* does not pre-satisfy it, and
`COACH_LEAKAGE_GATE_ENABLED` stays OFF until it does).
**Related:** [ADR-0017](0017-subject-coach-rubric-revision.md) (the recall revision
this corrects) · [specificity spec](../plan/coach-rubric-specificity-revision.spec.md) ·
[enable-policy](../plan/coach-goldset-enable-policy.spec.md) (ADR-0008 cond#1 floor) ·
[parent ledger](../plan/subject-coach-agent.plan.md) (Task 3.9/3.10).
**Audience:** anyone editing `prompts/subject_coach_pedagogy_judge.j2` or reasoning
about the coach enable cert (TNR floor).

---

## Context

ADR-0017 revised the pedagogy rubric to *catch* the five indirect leak channels —
a **recall** fix, driven by a 0/5-caught baseline. It explicitly named the
symmetric risk in its Consequences ("over-fitting the wording to these 22 fixtures
… the controls guard over-fitting on the false-positive side") and made the
out-of-sample ≥20-trace round **non-optional** — "the out-of-sample check this pass
structurally cannot be."

That out-of-sample check has now run. Task 3.9 assembled a **non-provisional**
`coach_goldset_v1` (human α-labeled, `provisional=false`, 116-row frozen test split:
29 leak / 87 clean) and ran the real enable cert against the ADR-0008 cond#1 floor
(TPR≥0.90 / TNR≥0.95 / κ≥0.75). Result (`cache/coach_eval/coach_enable_cert.json`,
`gpt-4o`):

- **verdict = REFUSE.** TPR **0.966** pass, κ pass, **TNR 0.9186 FAIL** (floor ≥0.95).
- Confusion: TP 28 / FN 1 / **FP 7** / TN 79 (+1 abstain, `T-CLEAN-20`, dropped from
  the TNR denominator — 79/(79+7)=0.9186). The judge is **not missing leaks**
  (FN 1). It **over-flags clean teaching as leakage**: 7 false positives among the 87
  clean rows. TNR needs ≤4 FP here; we have 7.

So the recall revision over-corrected on specificity — exactly the false-positive
over-fit ADR-0017 flagged. This is the honest, expected shape of a first real
out-of-sample cert, and it points at **one** fixable failure mode.

**Open coding of the false positives** (`cache/open_coding/coach-phase39-tnr-fps/`,
all 7 FPs captured live — an 8th flagged clean row, `T-CLEAN-20`, abstained on a
provider timeout and was dropped from the confusion, not scored as an FP; see the
replay-hang note) axial-collapses into a **single category**:

> **OVERFLAG-1 — mechanism-teaching read as item-collapse.** The judge fires
> `answer_leakage=true` whenever the coach *teaches a general rule* or *asks an open
> diagnostic/agreement probe*, even though the learner must still **map the rule
> onto the four options themselves** (≥2 options remain genuinely live). The judge
> skips the second half of ADR-0017's decisive test — "…for a learner **who hasn't
> solved it yet**" — and treats "taught the mechanism" as "resolved the item."

Per-case codes (7 FPs, each grammar item; codes stored in the coded JSONL):

| Sub-code | n | The judge's over-read |
|---|---|---|
| `overflag-open-probe-as-socratic` | 5 | An **open** classification/agreement probe read as a *leading* socratic question only one option survives. |
| `overflag-rule-named-not-applied` | 4 | Naming a rule *in general* (contraction test, adj-vs-adverb frame) read as *applying* it to this item. |
| `overflag-strong-implication` | 2 | A partial sort that removes *one* distractor read as full collapse to one. |
| `overflag-locus-pointing` | 2 | Pointing **at** the in-sentence cue (the verb, "has") read as eliminating options — already listed in the rubric as NOT leakage. |
| `overflag-hint-removed-one-not-all` | 1 | A hint that eliminates one option read as eliminating all-but-one. |

**Zero** `gold-dispute` and **zero** `judge-rationale-incoherent`: this is not a
labeling artifact and not a bad read — it is a coherent **rubric-boundary miss**.
The rubric already *lists* "pointing at the locus is not leakage" and "teaching the
mechanism while ≥2 options stay live is the good case," but as a short "What is NOT
leakage" tail after a long, vivid list of five leak channels — so the judge
pattern-matches the channels and under-weights the carve-out.

A change is necessary now because Task 3.9 is REFUSE and Phase 5 (any
`COACH_LEAKAGE_GATE_ENABLED` flip) stays gated until the cert reaches ENABLE.

---

## Decision

Revise `prompts/subject_coach_pedagogy_judge.j2` to **strengthen the CLEAN
carve-out** so the judge stops reading mechanism-teaching + open probes as
item-collapse, and re-certify on a **fresh** split. Specifically:

1. **Promote the "What is NOT leakage" section from a tail to a first-class,
   symmetric CLEAN test** placed *beside* the decisive test — not after the five
   channels. State the positive rule directly: *teaching a rule/mechanism, pointing
   at an in-sentence cue, or asking an open classification/agreement probe is CLEAN
   when ≥2 options remain live until the learner maps the rule to a choice
   themselves.* Expressed as **prose reasoning, not a numeric threshold** (config
   split — ADR-0017 rejected-option B stands).
2. **Add a "count the surviving options" instruction to the decisive test:** before
   flagging, the judge must state *which* options it believes are eliminated and
   *which* remain live, and flag only if that count is ≤1. This makes the
   "who hasn't solved it yet" clause operational the same way ADR-0017 made the leak
   channels operational — a checkable step, not a slogan. (The FP rationales show
   the judge never actually enumerates the surviving options; it infers collapse
   from the *presence* of teaching.)
3. **Name the two most common over-reads as explicit non-leaks** (mirroring the
   channel tells, but for the CLEAN side): an **open probe** ("what does the verb
   agree with?") is not socratic-clothing unless only one option survives *the
   question itself*; **naming a rule** is not rule-naming leakage unless one option
   *uniquely* satisfies it on this item.

No schema change (`PedagogyVerdict`/`leak_channel` unchanged — ADR-0017's field
stands; this is prose-only). `rubric_version` bumps
(`coach_rubric_v1_revised` → `coach_rubric_v2_specificity`).

**Prove the revision on a FRESH split, never on these 7 FP rows (§9).** The
strict exit bar is the ADR-0008 cond#1 floor met **with margin** on the held-out
re-cert: **TNR ≥ 0.95**, **TPR ≥ 0.90** (no recall regression — the ADR-0017 leaks
must stay caught), κ ≥ 0.75. Margin, not a knife-edge pass, because the judge is not
run-to-run deterministic even at temperature 0 (a clean row flipped tn→fn across two
3.9 replays).

---

## Options considered & rejected

| Option | Why it lost |
|---|---|
| **(A) Lower the TNR floor** (e.g. 0.95 → 0.90 so the current judge passes) | **Moves the goalpost, not the judge.** The ADR-0008 cond#1 floor is the contract that makes the leakage flag trustworthy enough to gate the live coach; relaxing it to fit a 0.9186 result ships a judge that false-flags ~1 in 12 clean turns as leaks. The FPs are a real defect (a coach that refuses to teach a mechanism is a bad coach), not gate over-strictness. |
| **(B) Fix the 7 FPs by editing/removing them from the test split** | **§9 violation.** The test split is the out-of-sample surface; re-scoring it to green is fitting noise (and ADR-0017 built the whole telemetry-only regime to *earn* an honest out-of-sample check). Two of the FPs were adjudicated `gold-dispute`? — **no**: open coding found 0 gold disputes; all 7 are clean rows the judge wrong-flagged. The gold is right. |
| **(C) Add a deterministic pre-filter that whitelists "teaching" language** | Symmetric to ADR-0017's rejected-D. Whether a probe leaves ≥2 options live is **semantic** ("does *this* question survive only one choice on *this* item?"), not lexical — a keyword whitelist for "teaching" would pass a genuine socratic-clothing leak dressed as a probe. The judgment must stay with the LLM. |
| **(D) Revert ADR-0017** (drop the five-channel recall revision to kill the over-flags) | **Throws away the recall win.** TPR is 0.966 and FN is 1 — the revision *works* on recall. Reverting trades a 7-FP specificity miss for a 0/5-recall miss. The fix is a specificity carve-out *on top of* ADR-0017, not instead of it. |
| **(E) Ship at telemetry-only forever, don't fix** (accept REFUSE) | Defensible and is the current state (Phase 5 stays gated), but leaves a known, single-category, cheaply-fixable defect in place. The open coding produced the exact carve-out; declining to apply it wastes the out-of-sample signal ADR-0017 paid for. |

---

## Rationale

The fix ties directly to the coded failure. OVERFLAG-1 is one category with zero
gold disputes and zero incoherent reads, so the miss is a **boundary the rubric
states too weakly**, not a model-capacity or data problem — which is why the answer
is a prose carve-out, not a bigger model (A-class reasoning, already rejected in
ADR-0017) or a pre-filter (C). ADR-0017 made the *leak* side operational (name the
channel, apply the decisive test); this ADR makes the *clean* side operational the
same way (count the surviving options, name the two over-reads) — completing the
symmetry the first revision left lopsided. Keeping the test as prose respects the
config split (rejecting A's cousin, the numeric threshold). Preserving ADR-0017's
schema and channels keeps the recall win (rejecting D). And validating on a fresh
split with margin respects both §9 and the measured judge non-determinism.

---

## Consequences

- **New commitments:** the pedagogy `.j2` gains a first-class CLEAN test +
  count-the-options step; header flips REVISED → REVISED (v2) and `rubric_version`
  bumps to `coach_rubric_v2_specificity`. No `PedagogyVerdict`/schema change (no
  re-sign; `trust/` untouched). One ⚠️ Ask-first trigger fires — AP-3 (rubric prose)
  — covered by this ADR.
- **Accepted risk — recall regression.** A carve-out that tells the judge to flag
  less can re-open the ADR-0017 leaks (push TPR down while lifting TNR). The exit
  bar therefore gates **both** TNR≥0.95 **and** TPR≥0.90 on the fresh re-cert; a
  revision that clears TNR by dropping a real leak is rejected, not shipped. This is
  the exact inverse of ADR-0017's "TNR=1.000 is non-negotiable" invariant.
- **Accepted risk — n and non-determinism.** The carve-out is reverse-engineered
  from 7 confirmed FPs; over-fitting the wording to *these* clean rows is the mirror of
  ADR-0017's n=5 circularity. Mitigation is identical and non-optional: validate on
  a **fresh** split (never these test rows), and require **margin** above 0.95, not a
  knife-edge pass — a clean row flipped tn→fn between two temperature-0 replays, so a
  0.951 pass is inside the noise band.
- **Leakage stays telemetry-only until the fresh re-cert reaches ENABLE.**
  `COACH_LEAKAGE_GATE_ENABLED` stays OFF through this task (unchanged from
  ADR-0008/0012/0017). This ADR does not flip a flag; it aims a REFUSE at ENABLE.
- **Follow-on:** the fresh re-cert needs a held-out clean+leak split the current
  goldset does not yet contain (the 116-row test split is now "seen" by this fix).
  Producing that split — corpus expansion or a fresh-authored control set, human
  α-labeled — is the gating prerequisite and is called out in the spec/tasks. The
  live re-cert is manual/local (creds-gated); CI stays live-free (the
  `run_coach_calibration` pure core replays committed labels offline).
- **Honest downside:** the rubric grows again (already long after ADR-0017), raising
  cost/latency slightly, and a strong CLEAN carve-out is precisely the lever that can
  re-admit leaks — hence the paired TPR gate. If the fresh re-cert can't clear both
  gates with margin, the honest outcome is telemetry-only (option E), not a relaxed
  floor (option A).

---

## Supersedes / related

Extends ADR-0017 (does not supersede it — the five channels, the schema field, the
payload-over-refusal rule all stand). Corrects the specificity side of that revision
using the out-of-sample cert ADR-0017 named as its own required follow-up. Pairs
with the specificity spec/plan/tasks and the parent-ledger Task 3.10.
