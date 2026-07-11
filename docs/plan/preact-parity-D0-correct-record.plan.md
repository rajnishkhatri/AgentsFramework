---
title: 'Sprint D0 — Correct the record · Plan + Tasks'
type: plan
status: Implemented (docs-only; 2026-07-10)
date: 2026-07-10
owner: Rajnish Khatri
epic: D
implements: docs/plan/preact-parity-D0-correct-record.spec.md
related:
  - docs/plan/preact-parity-sprint-board-D.md
  - docs/plan/preact-parity-epic-D.brainstorm.md
  - docs/plan/preact-parity-A0-correct-record.plan.md   # precedent
  - docs/adr/decisions.md                                # FR-6 target
---

# Sprint D0 — Plan + Tasks

Implements [preact-parity-D0-correct-record.spec.md](preact-parity-D0-correct-record.spec.md).
Docs-only; no `⚠️ Ask first` trigger → **no ADR** (a `decisions.md` entry is the capture,
per FR-6).

---

## 1. Architecture / approach

D0 is the smallest possible correction sprint. Unlike A0 (which needed a runtime grep
guard because A1's `sdd-spec` was already open and could re-inherit stale framing),
Epic D's follow-on sprints (D1/D2/D3/D4) have not entered `sdd-spec` yet. A **one-pass
reviewer grep + human read** is sufficient. No new arch test, no `<!-- refuted-framing-ok
-->` sentinel machinery, no `make check` gate addition.

D0 has three halves that must land in one PR:

1. **The "watched red" grep** (evidence-first, per SDD discipline). Before any edit,
   run the FR verification greps from [spec §8](preact-parity-D0-correct-record.spec.md#8-test-plan)
   over the current tree and paste the output. This shows the stale framings live in
   the epics doc + VISUAL report **today** — the docs-only equivalent of a red test.

2. **The corrections (five row edits, one appended `decisions.md` entry).** Edit the
   `Q-7`, `Q-9`, `Q-1b`, `D-8`, and `X-4` rows in
   [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)
   and the corresponding entries in
   [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md).
   Append a newest-first entry to [`docs/adr/decisions.md`](../adr/decisions.md).

3. **The verification pass (re-run greps, expect green).** Re-run the FR verification
   greps; paste post-D0 output; confirm the sprint board is already clean (FR-7).

**Why no runtime guard.** A0 needed one because A1 was already in-flight and there was
a real risk of the stale framing re-entering as a live claim mid-flight. Epic D's
follow-on sprints have not started specifying yet — D0 lands first, and D1/D2/D3
inherit the corrected framing on read. Adding a Python arch test to police the same
strings has near-zero marginal value in this window and would ship an artifact for
future sprints to maintain. Deliberate omission.

**Why no code comment edit.** A0 fixed a code comment because the phantom "sanctioned"
paraphrase in [`QuizView.tsx:104`](../../frontend/components/quiz/QuizView.tsx:104) was
the *seed* the docs escalated from. Epic D's refuted premises did not originate in a
code comment — they originated in the epics doc and parity report themselves. No
`frontend/` file needs editing.

## 2. Files touched

| File | Edit | Owning FR |
|------|------|-----------|
| [`docs/plan/preact-parity-epics.md`](preact-parity-epics.md) | Rewrite `Q-7`, `Q-9`, `Q-1b`, `D-8`, `X-4` rows in §Epic D | FR-2, FR-3, FR-4, FR-5 |
| [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) | Rewrite `Q-9` and `D-8` entries; mark `X-4` as absorbed into `D-3b` | FR-3, FR-5 |
| [`docs/adr/decisions.md`](../adr/decisions.md) | Append newest-first Epic D premise-audit entry | FR-6 |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | **Verify only** (grep clean) — no edit expected | FR-7 |

**Explicitly NOT touched:**

- Any `frontend/` file (no `.tsx`, no VM, no reducer, no seed).
- Any `tests/` file (no new arch test — see §1).
- Any `docs/adr/00XX-*.md` file (no ADR — `decisions.md` is the right weight).
- [`preact-ui-prototype-parity-gap-matrix.md`](preact-ui-prototype-parity-gap-matrix.md)
  (superseded record; historical text stays as-is).

## 3. Task list

Task markers:
- `[red]` — pre-edit "watched red" grep evidence.
- `[green]` — the correction edit.
- `[verify]` — post-edit grep confirming the FR passes.
- `[P]` — can run in parallel with siblings inside the same block.

### Block 0 — Watched-red evidence

- **T0.1 [red]** Run the FR verification greps over the current tree and paste output
  into the D0 DoD "Pre-D0" section:
  ```bash
  grep -n "Q-7\|Q-9\|Q-1b\|D-8\|X-4" \
    docs/plan/preact-parity-epics.md \
    docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
  ```
  Expected: rows currently describe Q-7 as "skill chip" (view-only), Q-9 as
  "dismissible timer", Q-1b as a code decision without noting docs-first D3 posture,
  D-8 without the Epic-E gate caveat, and X-4 as a separate row. If any row is already
  corrected, note it — that FR reduces to a verify-only check.

### Block 1 — Epics-doc corrections (FR-2 · FR-3 · FR-4 · FR-5)

Edits to [`docs/plan/preact-parity-epics.md`](preact-parity-epics.md) §Epic D table.
Each is one row edit; four sub-tasks can run in parallel since they touch different
table rows.

- **T1.1 [green] [P]** Rewrite the `Q-7` row (P3 corrected framing). The corrected
  row MUST mention the wire→VM→view seam (contain "VM" AND ("translator" OR "hook")).
  MUST NOT imply view-only.
- **T1.2 [green] [P]** Rewrite the `Q-9` row (P8 corrected framing). MUST contain
  "collapsible" AND a note that `elapsed_ms` capture is already correct (cite
  `session_summary_vm.ts:60-65` or the A2 triage record). MUST NOT contain
  "dismissible" as a live description.
- **T1.3 [green] [P]** Rewrite the `Q-1b` row (P10 corrected framing). MUST reference
  D3 as a decision-first sprint recorded via `decisions.md`. MUST NOT frame it as a
  code sprint by default.
- **T1.4 [green] [P]** Rewrite the `D-8` row (P14 corrected framing). MUST reference
  Epic E's `/learn/skill` route as the gate and state that adding to `NAV_MEMBERSHIP`
  before E ships would land a dead nav item (Q-6 class). MUST state default posture =
  defer to Epic E; alternate = D4 `comingSoon`-gated add.
- **T1.5 [green] [P]** Mark the `X-4` row as **absorbed into D2** (cross-cut duplicate
  of `D-3b`), not shipped as a separate sprint (P15 corrected framing). The
  Traceability table (backlog #8 → D) already resolves correctly — no edit there.
- **T1.6 [verify]** Re-run the T0.1 grep and paste output — each row now contains its
  P-corrected keywords.

### Block 2 — VISUAL-report corrections (FR-3 · FR-5)

Edits to [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md).

- **T2.1 [green] [P]** Rewrite the §Q-9 entry — change "dismissible" language to
  "collapsible / off-by-default" and add the `elapsed_ms`-already-captured note (cite
  A2 triage or `session_summary_vm.ts:60-65`). Preserve any visual-clip evidence and
  severity classification.
- **T2.2 [green] [P]** Add a gate caveat to the §D-8 entry: "gated on Epic E's
  `/learn/skill` route; do not enable until E lands, or ship as `comingSoon`." Preserve
  severity + visual evidence.
- **T2.3 [green] [P]** In §X-4, note that the finding is absorbed into `D-3b`'s sprint
  (D2). Preserve the cross-ref back to D-3b that already exists.
- **T2.4 [verify]** Re-run the T0.1 grep over the VISUAL report and paste — Q-9 rows
  no longer say "dismissible" as a live claim; D-8 rows carry the Epic-E gate caveat;
  X-4 rows note the D-3b absorption.

### Block 3 — `decisions.md` intent-debt entry (FR-6)

- **T3.1 [green]** Append a newest-first entry to
  [`docs/adr/decisions.md`](../adr/decisions.md) with:
  - **Date** 2026-07-10.
  - **Header** "Epic D — Stage-1 premise audit corrections (Sprint D0)".
  - **Body** — one paragraph per refuted premise (P3, P8, P10, P14, P15), each naming
    the refuted claim + one-line rationale + `file:line` evidence citation from the
    audit (see spec §2).
  - **Ladder note** — Epic D's sprint ladder is `D0 → { D1, D2, D3 }` (parallel-
    independent) with **D4 optional**; D-8 defaults to **deferred to Epic E**.
  - **Rejected alternatives (tail)** — the discarded framings, one line each:
    (i) "Q-7 as view-only chip render"; (ii) "Q-9 as dismissible-clock UI";
    (iii) "Q-1b as a code sprint by default"; (iv) "D-8 as a free `NAV_MEMBERSHIP`
    add"; (v) "X-4 as an independent sprint".
- **T3.2 [verify]** `head -60 docs/adr/decisions.md` — paste; the newest entry
  mentions Epic D + all five premise IDs + the Rejected tail.

### Block 4 — Sprint board verification (FR-7)

- **T4.1 [verify]** Confirm the sprint board is already clean:
  ```bash
  grep -niE "skill chip|dismissible|change 30 to 10|X-4 (as )?independent" \
    docs/plan/preact-parity-sprint-board-D.md
  ```
  Expected: **no live claims** (matches within the board's own premise table or
  quoted context are fine — the board authored the corrected framings at Stage-1
  close). If a live claim surfaces, correct it in this PR (same block).

### Block 5 — Structural + green + log

- **T5.1** `python scripts/okf_lint.py` → **exit 0**. Paste output.
- **T5.2** `make check` — should be a no-op since D0 touches no `frontend/` or `tests/`
  files; paste output to confirm.
- **T5.3** Log in the PR body: **D0 corrected the record for Epic D — did NOT
  implement any Q-7 / Q-8 / Q-9 / Q-1b / D-3b / D-8 fix** (those are D1/D2/D3/D4).
  "Green" is not to be misread as "features shipped."

---

## FR → task crosswalk

Every FR from [`spec §3`](preact-parity-D0-correct-record.spec.md#3-functional-requirements-ears)
maps to at least one green + verify task.

| FR | Watched-red | Green task | Verify task |
|----|-------------|------------|-------------|
| FR-1 / FR-2 (Q-7 epics-doc row) | T0.1 | T1.1 | T1.6 |
| FR-3 (Q-9 epics + VISUAL) | T0.1 | T1.2, T2.1 | T1.6, T2.4 |
| FR-4 (Q-1b epics-doc row) | T0.1 | T1.3 | T1.6 |
| FR-5 (D-8 + X-4 epics + VISUAL) | T0.1 | T1.4, T1.5, T2.2, T2.3 | T1.6, T2.4 |
| FR-6 (`decisions.md` entry) | — (append-only) | T3.1 | T3.2 |
| FR-7 (board verified clean) | — | — | T4.1 |

Every FR has an owning task. No FR is "tested by inspection alone" — each has an
explicit grep or file-read whose output is pasted into the DoD.

---

## Parallelization envelope

Blocks fire sequentially (each has an artifact the next reads/verifies). Inside a
block:

- **Block 1:** T1.1–T1.5 all edit different rows of the same table — can be authored in
  parallel and committed as one edit. T1.6 must run after all five.
- **Block 2:** T2.1–T2.3 touch different sections of the VISUAL report — parallel-safe.
  T2.4 runs after.
- **Block 3:** single task (T3.1) + verify (T3.2), sequential.
- **Block 4:** single verify (T4.1).
- **Block 5:** T5.1, T5.2 independent; T5.3 last (PR body).

No `[P]` marker exists across blocks — each block's evidence gates the next.

---

## Definition of Done (D0)

Mirrors [spec §9](preact-parity-D0-correct-record.spec.md#9-definition-of-done). All
paste-into-PR items are in the block-level tasks above; the DoD is where they land as a
checklist for the reviewer.
