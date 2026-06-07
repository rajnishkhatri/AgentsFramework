# GoalJudge Step 7 Inter-Annotator Agreement — Multi-Model Panel (Fleiss' κ) — PROVISIONAL

> **Five independent model coders, fully blind.** This is a stronger version of the single-model
> Step 7 pass ([`goaljudge_step7_iaa_kappa.md`](goaljudge_step7_iaa_kappa.md)). Five different models
> each re-coded the same 12-case sample from a **code-free evidence packet** (the open-code labels and
> every prior "Coding" line were stripped out; coders were instructed not to read the Step 5 matrix,
> Phase 3, or any existing coding). It is still a **model** panel, not a human one — so it remains
> **PROVISIONAL** and the real **human IAA** stays an open §7 gate — but the blindness is genuine
> (none of the five saw the answer key) and five independent raters give a real Fleiss' κ instead of a
> single pairwise number.

## Panel and posture

- **Coder 1 (reference):** the Step 5 matrix Axis-A primary
  ([`goaljudge_step5_axial_matrix.md`](goaljudge_step5_axial_matrix.md)) — the existing coding.
- **Coders 2–6 (blind re-code):** five models, each given an identical self-contained packet —
  the A1–A5 definitions + member codes, the five Step 4 binary checks, the three coding rules
  (first-failure discipline, the `†` confound-preemption rule, the `correct-complete` target-miss
  rule), and a **code-free** evidence block for all 12 cases:
  - `gpt-5.5-medium`, `composer-2.5-fast`, `gemini-3.1-pro`, `grok-4.3`, `gemini-3.5-flash`.
- **Unit of agreement:** the **Axis-A category** (A1–A5), not the finer member code (same convention
  as the single-model pass).
- **Sample:** the same 12 cases — GJ-001A, GJ-002, GJ-003B, GJ-005, GJ-007, GJ-008, GJ-009, GJ-010,
  GJ-011, GJ-013, GJ-019, GJ-020 — spanning A1–A4 (A5 has no matrix primary; it appears only as a
  *disagreement* destination here, which is itself a finding).

## The κ result (recomputable from the CSV)

Fleiss' κ over the 5 blind model coders, and over all 6 raters (matrix + 5 models). Pairwise Cohen's
κ of each model against the matrix. Target bar (MAST, [arXiv 2503.13657](https://arxiv.org/abs/2503.13657)):
**κ ≥ 0.8**.

| Panel | n raters | n cases | Fleiss' κ | vs 0.8 bar | Landis–Koch band |
|---|---|---|---|---|---|
| 5 blind models | 5 | 12 | **0.50** | **below** | moderate |
| matrix + 5 models | 6 | 12 | **0.51** | **below** | moderate |
| 5 models, excl. the 2 terminal-abort cases (GJ-001A, GJ-020) | 5 | 10 | 0.53 | below | moderate |

| Model vs matrix | observed agreement | Cohen's κ |
|---|---|---|
| **grok-4.3** | **10/12 (0.83)** | **0.77** |
| gpt-5.5-medium | 7/12 (0.58) | 0.46 |
| composer-2.5-fast | 7/12 (0.58) | 0.47 |
| gemini-3.1-pro | 7/12 (0.58) | 0.46 |
| gemini-3.5-flash | 7/12 (0.58) | 0.46 |

Mean pairwise Cohen's κ **among the five models** = **0.50** (range 0.36–0.79).

> **Headline:** independent blind coding lands at **Fleiss' κ ≈ 0.50 — moderate, well under the 0.8
> bar.** The single-model pass's 0.77 was optimistic: only **grok-4.3** reproduces the matrix that
> closely (κ = 0.77); the other four cluster at κ ≈ 0.46. The taxonomy has a **hard core of four
> unanimous cases** but **eight cases with real category-level disagreement**, and the disagreement is
> *systematic*, not noise — it isolates exactly three definitional seams.

## Per-case agreement (matrix + 5 models = 6 votes each)

| Case | matrix | gpt-5.5 | composer | gemini-pro | grok | gemini-flash | majority | matrix = majority? |
|---|---|---|---|---|---|---|---|---|
| GJ-005 | A1 | A1 | A1 | A1 | A1 | A1 | **A1 (6/6)** | ✓ unanimous |
| GJ-007 | A4 | A4 | A4 | A4 | A4 | A4 | **A4 (6/6)** | ✓ unanimous |
| GJ-008 | A2 | A2 | A2 | A2 | A2 | A2 | **A2 (6/6)** | ✓ unanimous |
| GJ-009 | A1 | A1 | A1 | A1 | A1 | A1 | **A1 (6/6)** | ✓ unanimous |
| GJ-020 | A3 | A4 | A3 | A3 | A3 | A3 | A3 (5/6) | ✓ |
| GJ-010 | A2 | A2 | A2 | A2 | A2 | A4 | A2 (5/6) | ✓ |
| GJ-013 | A2 | A2 | A5 | A2 | A5 | A2 | A2 (4/6) | ✓ |
| GJ-002 | A1 | A5 | A5 | A5 | A1 | A5 | **A5 (4/6)** | ✗ (matrix A1, panel A5) |
| GJ-001A | A3 | A2 | A5 | A1 | A1 | A1 | **A1 (3/6)** | ✗ (matrix A3, panel A1) |
| GJ-003B | A1 | A3 | A3 | A2 | A1 | A1 | A1 (3/6) | ✓ (but only 3/6) |
| GJ-011 | A2 | A5 | A2 | A5 | A2 | A5 | A2 (3/6) | ✓ (3–3 tie A2/A5) |
| GJ-019 | A4 | A4 | A1 | A3 | A4 | A3 | A4 (3/6) | ✓ (3-way split) |

**Notable shift from the single-model pass.** GJ-007 and GJ-009 — the two cases the single-model run
flagged as the `†`-convention disagreement drivers — are now **unanimous (6/6)**. The sharper,
self-contained packet plus the explicit `†` rule resolved them. The instability **moved** to the
*terminally-aborted* `†` cases (no final answer to read) and to a brand-new seam the single pass never
surfaced.

## Disagreement analysis — three systematic seams

Only **4 of 12** cases are unanimous; the other 8 split. But the splits are not random — they
concentrate on three under-specified boundaries:

### Seam 1 — A2 vs A5: "blocked tool → prose computation → claimed done" (GJ-002, GJ-011, GJ-013)
When the tool that *should* have produced a result was blocked by the environment and the agent then
**computed the answer in prose** and framed the task as complete, is that:
- **A2** corrupt-success (a subtask with no supporting tool evidence, counted as full — the matrix
  view), or
- **A5** right-answer-wrong-process (correct value reached via an unverified/hardcoded path)?

Three models read GJ-002 and GJ-011 as **A5**; the matrix and grok read them as A1/A2. This is the
**dominant driver of the low κ** and was **invisible to the single-model pass** (one coder simply
never picked A5). A1 vs A2 vs A5 are competing for the same "answer present but unverified" region.

### Seam 2 — the `†` rule under-specifies *which category* a terminally-aborted case maps to (GJ-001A, GJ-019, GJ-020)
The `†` rule says "code to the intended design target," but for cases where an environment block or
orchestrator abort fired so early that **no final answer exists** (GJ-001A, GJ-020) — or where the
agent only produced a graceful decline (GJ-019) — coders cannot agree what the intended target's
*category* is:
- GJ-001A spread across **A1 / A2 / A3 / A5** (matrix A3 is a 1/6 minority; panel majority A1).
- GJ-019 split **A4 / A1 / A3** (matrix A4; gemini-pro/flash read the missing raw-error deliverable as
  A3, composer as A1).
- GJ-020 split **A3 / A4** (matrix A3, 5/6 agree; gpt-5.5 reads the unhandled abort as A4).

The `†` rule needs an explicit **category mapping for no-final-answer cases**, not just "intended
target."

### Seam 3 — A1 vs A2 vs A3 on the never-attempted else-branch (GJ-003B)
Same boundary the single-model pass found, now **three-way**: matrix and grok say **A1**
(missing-requested-information), gpt-5.5/composer say **A3** (the missing-file result was mishandled),
gemini-pro says **A2** (the else-branch subtask was dropped). The first-failure on a conditional
prompt — read-error vs dropped-branch vs missing-final-datum — is genuinely ambiguous.

(GJ-010's lone **A4** vote from gemini-flash — treating "Mars has no numeric population" as an
impossible subtask rather than a partial-counted-as-full — is an isolated outlier, not a seam.)

## Definition revisions the panel demands

These extend (and partly supersede) the single-model pass's two revisions:

1. **A2/A5 tie-breaker for blocked-tool prose computation (NEW — Seam 1).** Add to the Step 2 A2/A5
   definitions: *"If a required computation/subtask's tool was blocked and the agent supplied the
   answer **in prose without any tool evidence** while framing the task complete, code **A2
   corrupt-success** (the claim exceeds the evidence). Reserve **A5** for cases where the trajectory
   **did** reach the outcome but via an unsafe/wasteful/hardcoded *successful* path. 'No tool evidence
   + claimed done' is A2, not A5."* This is the single highest-leverage fix — it owns three of the
   eight disagreements.

2. **`†` no-final-answer mapping (sharpened — Seam 2).** Make the Step 5 `†` rule explicit: *"For a
   `†` case where the environment/orchestrator aborted before any final answer (GJ-001A, GJ-020) or
   left only a forced decline (GJ-019), code to the intended design target's category **and mark the
   case `†` — excluded from the κ denominator and the Axis-A saturation count**. If the intended
   target is itself contested, the case does not count toward reliability at all."* The κ sensitivity
   supports this: these are the cases that cannot be coded consistently.

3. **A1/A2/A3 first-failure tie-breaker for conditional prompts (carried from single-model pass —
   Seam 3).** *"On a conditional (if/else) prompt where the guard's tool result is handled correctly
   but the else-branch is **never attempted**, code **A2 `subtask-dropped`** (the drop is the first
   deviation), not A1 and not A3."* Resolves GJ-003B toward the dropped-branch reading.

With (1)–(3) applied and the `†` cases removed by rule, the eligible-sample disagreements collapse to
the GJ-010 outlier; the structural seams are closed.

## Why this is recorded as PROVISIONAL (open gates)

| Gate | Status |
|---|---|
| **Human coders** (the playbook's actual IAA requirement) | **OPEN** — this is a 5-model panel, not human. |
| **Blind coding** (coders must not have seen the matrix) | **MET for this pass** — code-free packet, no matrix access (stronger than the single-model pass, which was only partially blind). |
| **κ ≥ 0.8 on the full sample** | **OPEN** — Fleiss' κ = 0.50 (5 models) / 0.51 (with matrix); best single model 0.77. |
| **Definition revisions merged upstream** (Step 2 A2/A5 + A1/A2, Step 5 `†`) | **CLEARED** — G7/G8/G9 applied to Step 2/Step 5 (2026-06-07); human G5 re-code still **OPEN**. |

Until a **human** panel clears κ ≥ 0.8 on the revised definitions, the taxonomy is usable for Stage-4
*design* but counts and the top-mode pick stay provisional. The multi-model panel **lowers** the
reliability estimate from the single-model 0.77 to ≈0.50 and **adds a third revision** (the A2/A5
seam) — i.e. the taxonomy is less reliable than the single-model pass suggested, and the work to
harden it is now precisely scoped to three seams.

## Acceptance check (Step 7 walkthrough, multi-model variant)

- ≥10-case sample independently re-coded from definitions + checks only, by **five** blind coders
  (n = 12 each). ✔
- Fleiss' κ computed on the Axis-A primary category and **recorded** (0.50 / 0.51), recomputable from
  [`goaljudge_step7_iaa_multimodel.csv`](goaljudge_step7_iaa_multimodel.csv). ✔
- Every disagreement traced to a specific definitional seam (A2/A5 prose-after-block; `†`
  no-final-answer mapping; A1/A2/A3 conditional-prompt boundary), with a concrete revision each. ✔
- κ < 0.8 ⇒ definitions revised, **not** frozen (anti-pattern avoided). ✔
- Model panel recorded as **provisional**; **human IAA listed as an open §7 gate**. ✔
