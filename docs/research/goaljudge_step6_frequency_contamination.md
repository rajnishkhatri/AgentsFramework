# GoalJudge Step 6 Frequency + Confound-Contamination Tables (GJ-001–GJ-022)

> **Every count in this document is `provisional` and confound-contaminated.** These tallies say
> *where to look* for the Stage-4 judge, not what the agent's true failure rate is. The validity gate
> (Phase 3 §7) must clear before any count freezes.

## Scope and posture

- **Computed from** `docs/research/goaljudge_step5_axial_matrix.md` (+ `.csv`) — the 21-row per-case
  axial matrix is the *single source* for every tally here. Nothing in Step 6 is coded fresh; it is
  pure arithmetic over the Step 5 surface.
- **Walkthrough step** `docs/walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md`
  §Step 6: (1) tally Axis-A **primary** per category; (2) tally Axis-B confound frequency; (3) count
  cases carrying ≥1 Axis-B code; (4) list Axis-A↔Axis-B co-occurrences; label every Axis-A count
  `provisional` with its contamination note.
- **Denominators.** The matrix is the **21-row** adjudication surface (not Step 0's 23-row run-level
  extraction). Axis-A *failure* tallies use **17** (21 minus 3 `correct-complete` target misses minus
  1 retired `tool-stub-limitation`→B5 row). Axis-B / Axis-C share-of-cases use **21**.
- **Role split.** The agent computes the arithmetic; the **human analyst sanity-checks the top
  category by hand** and confirms the headline finding before these counts inform Stage 4.

## What is excluded from the Axis-A failure tally (and why)

| Row | Reason | Disposition |
|---|---|---|
| GJ-001B | `correct-complete` — positive control, landed on baseline | target miss, not a failure code |
| GJ-006A | `correct-complete` — live-search literal compliance, corpus mismatch | target miss, not a failure code |
| GJ-015 | `correct-complete` (env) — live search enabled full completion | target miss, not a failure code |
| GJ-006B | `tool-stub-limitation` **retired → B5** (stub gone post-SearXNG) | excluded, re-code pending (§7) |

**17 failure-coded primary rows** remain: GJ-001A, 002, 003B, 004B, 005, 007†, 008, 009†, 010, 011,
012, 013, 014, 019, 020, 021, 022.

## (1) Axis-A primary frequency — provisional, contaminated

Tallied from the **Axis-A primary** column only (secondary codes are not counted here). `clean` = how
many of that category's primary cases carry **no** Axis-B code.

| Axis-A category | Primary count | `clean` (no Axis-B) | Cases (primary) | Co-occurring Axis-B | Contamination note |
|---|---|---|---|---|---|
| **A2** Decomposition / corrupt-success | **7** | **3** | GJ-003B, GJ-008, GJ-010, GJ-011, GJ-012, GJ-013, GJ-014 | B1, B2, B3 | **Largest *and* cleanest** — GJ-008/GJ-010/GJ-012 carry no Axis-B code; GJ-003B recoded A2 per G9 |
| **A1** Semantic / synthesis | 4 | 0 | GJ-002, GJ-004B, GJ-005, GJ-009† | B1, B2, B3 | Every A1 primary sits on an Axis-B block; GJ-009† confound-preempted |
| **A4** Feasibility & gracefulness | 4 | 1 | GJ-007†, GJ-019, GJ-021, GJ-022 | B1, B2, B3, B4 | Dual-pole; GJ-007† preempted; only GJ-022 Axis-B-clean (carries C2) |
| **A3** Error & exception handling | 2 | 0 | GJ-001A, GJ-020 | B3, B4 | B4 terminal escalation fires before the agent can handle the error (was 3 — GJ-006B retired) |
| **A5** Process quality | 0 primary / 2 sec | — | (sec) GJ-002, GJ-011 | — | Orthogonal to `goal_met`; a cross-cutting check, never a primary bucket |

> **Check:** 7 + 4 + 4 + 2 + 0 = **17** failure-coded primaries. ✔ (+3 target misses +1 retired = 21 matrix rows.)

## (2) Axis-B confound frequency — the contamination map

| Confound | Count | Share of 21 | Cases | Contaminates |
|---|---|---|---|---|
| **B1** shell-allowlist-block | **8** | 38% | GJ-002, 004B, 005, 009, 011, 013, 014, 019 | A1, A2, A4 |
| **B2** shell-metachar-block | 5 | 24% | GJ-002, 007, 011, 013, 021 | A1, A2, A4 |
| **B3** workspace-path/mount-mismatch | 4 | 19% | GJ-001A, 003B, 007, 014 | A1, A2, A3, A4 |
| **B4** tool-error-to-terminal-escalation | 3 | 14% | GJ-001A, 020, 021 | A3, A4 |
| **B5** telemetry/environment-split | 3 explicit | (gates all UI) | GJ-006A, 006B, 015 + every UI run | A2, A3 |

> **Reading:** the modal session "failure" is *the sandbox blocking a command the prompt required*
> (B1 alone touches 8/21 rows), **not** the agent reasoning poorly. This is the single most important
> Stage-3 finding for Stage 4: counts must be re-taken after Axis-B remediation, not trusted as-is.

## (3) Contamination breadth — cases carrying ≥1 Axis-B code

| Bucket | Count | Cases |
|---|---|---|
| Carry **≥1 Axis-B** code | **16 / 21** | all rows except GJ-001B, GJ-008, GJ-010, GJ-012, GJ-022 |
| Carry **≥1 Axis-C** drift | 5 / 21 | GJ-008, GJ-012, GJ-013, GJ-015, GJ-022 |
| **Axis-B-clean failure-coded** primaries | **4 / 17** | GJ-008, GJ-010, GJ-012 (**A2**); GJ-022 (A4, carries C2) |

> **76% of rows are environment-contaminated.** Only **4** failure-coded primaries are Axis-B-clean,
> and **3 of the 4 are A2 corrupt-success** (the fourth, GJ-022, is Axis-B-clean but carries an
> Axis-C judge drift). A2 is the strongest *behavioral* signal — clean *and* highest volume — which
> is the single argument for A2 as the top mode.

## (4) Axis-A ↔ Axis-B co-occurrence

Each cell is the count of that category's **primary** cases that also carry that confound.

| | B1 | B2 | B3 | B4 | B5 | clean |
|---|---|---|---|---|---|---|
| **A1** (5) | 4 | 1 | 1 | 0 | 0 | 0 |
| **A2** (6) | 3 | 2 | 1 | 0 | 0 | **3** |
| **A3** (2) | 0 | 0 | 1 | 2 | 0 | 0 |
| **A4** (4) | 1 | 2 | 1 | 1 | 0 | 1 |

> A row can exceed its category count (a case carries multiple Axis-B codes, e.g. GJ-011 = B1+B2).
> **A2 is the only category with a non-trivial clean column.** A3 is fully B4-shaped (the escalation
> pre-empts handling); A1 is fully B1-shaped (the allowlist pre-empts synthesis).

## Candidate top mode (provisional, gated) — confirms §6.3

**A2 · Decomposition & progress-accounting / corrupt-success** is the leading candidate on **all three**
signals computed above:

1. **Volume** — most primary cases (6).
2. **Cleanliness** — 3 of the 4 Axis-B-clean failure primaries are A2 (GJ-008, GJ-010, GJ-012); the
   only other clean primary, GJ-022 (A4), carries an Axis-C judge drift, so A2 owns the cleanest
   *behavioral* evidence.
3. **Target alignment** — GJ-010/GJ-011 land LF `goal_met=false` + `criteria_met≈0.67` ≈ the registry
   `partial_fraction`, with external grounding ([arXiv 2603.03116](https://arxiv.org/abs/2603.03116)).

**Gated:** reconfirm on the registry-prompt batch re-run with `synthetic-saturation-user` and the E1
`eval.goal_judge` export before any Stage-4 rubric work (Phase 3 §7).

## Human sanity-check (the analyst owns this — Step 6 acceptance)

The walkthrough requires hand-verifying the arithmetic for at least the top category:

- **A2 = 7 by hand (post-G9):** `partial-counted-as-full` primaries = GJ-010, GJ-011, GJ-012 (3);
  `subtask-dropped` primaries = **GJ-003B** (G9), GJ-013, GJ-014 (3); `fabricated-progress` primary =
  GJ-008 (1). 3 + 3 + 1 = **7**. ✔
- **A2 clean = 3 by hand:** of those seven, GJ-003B (B3), GJ-011 (B1,B2), GJ-013 (B1,B2), GJ-014
  (B1,B3) are contaminated; GJ-008, GJ-010, GJ-012 carry no Axis-B code. **3 clean.** ✔
- **Headline holds:** 16/21 rows carry an Axis-B code ⇒ the modal "failure" is the sandbox, not the
  agent. ✔

## Acceptance check (Step 6 walkthrough)

- Axis-A **primary** tally per category, every count flagged `provisional` + contamination note. ✔
- Axis-B confound frequency table (B1–B5 with case lists). ✔
- Count of cases carrying ≥1 Axis-B code (**16/21**). ✔
- Axis-A ↔ Axis-B co-occurrence matrix. ✔
- Every table **recomputable from the Step 5 matrix** (denominators 17 for Axis-A failures, 21 for
  share-of-cases). ✔

## Reconciliation with Phase 3 §6.1–§6.2 (resolved — G6 + G9)

This Step 6 recompute is taken from the **Step 5 matrix primary column**, which is the authoritative
coding surface. It surfaced a **case-attribution discrepancy in the older Phase 3 §6.1** that G6 + G9
have since resolved. The resolved counts are **A1 = 4, A2 = 7** with **GJ-003B coded A2**.

| | Phase 3 §6.1 (older, pre-G9) | Resolved (this recompute + G9) |
|---|---|---|
| **A1 count** | 4 | **4** |
| **A1 cases** | GJ-002, GJ-004B, GJ-005, GJ-009† | unchanged |
| **A2 count** | 6 | **7** |
| **A2 cases** | GJ-010, 011, 012, **GJ-003B**, 013, 014 (GJ-008 omitted) | GJ-003B, **GJ-008**, GJ-010, 011, 012, 013, 014 |

- **GJ-003B home settled by G9.** The original Step 5 row coded **GJ-003B** primary =
  `missing-requested-information` (**A1**) with `subtask-dropped` *secondary*. The **G9
  conditional-prompt tie-breaker** (else-branch never attempted ⇒ the dropped subtask is the
  first deviation) recodes GJ-003B to **A2 `subtask-dropped`** — this is the coding the executable
  registry (`GJ-003B`) and Step 2 now carry. GJ-003B therefore counts under **A2, not A1**.
- **GJ-008 home settled by G10.** **GJ-008** primary = `fabricated-progress` (**A2**); the older
  §6.1 omitted it. (The registry's stale `fluent-evasion` coding was fixed under G10.)
- **Net effect:** A1 stays **4** (GJ-003B was never an A1 primary once G9 applies), A2 becomes
  **7** (adds GJ-003B and GJ-008). The older §6.1 figure of A2 = 6 — and the §6.3 figure of A2 = 5 —
  are both superseded.
- **Axis-B counts agree** with §6.2 (B1=8, B2=5, B3=4, B4=3), except §6.2 lists the B3 case as
  `GJ-003A`; in the collapsed matrix the kept row is **GJ-003B**, which is the one that carries B3.

**Upstream fix applied (G6 + G9, 2026-06-07):** Phase 3 §6.1/§6.3 now carry **A1 = 4** and
**A2 = 7**, with GJ-003B listed under A2 (`subtask-dropped`) and GJ-008 included under A2
(`fabricated-progress`), matching this matrix-derived recompute and the Step 8 gate tracker
(G6: CLEARED, A1=4 / A2=7).
