---
title: 'Sprint D0 — Correct the record (Epic D refuted premises) · Spec'
type: spec
status: Implemented (docs-only; 2026-07-10)
date: 2026-07-10
owner: Rajnish Khatri
epic: D
derives_from: docs/plan/preact-parity-sprint-board-D.md
related:
  - docs/plan/preact-parity-sprint-board-D.md              # §Sprint D0 + ladder
  - docs/plan/preact-parity-epic-D.brainstorm.md           # Stage-1 audit (P3/P8/P10/P14/P15 evidence)
  - docs/plan/preact-parity-epics.md                       # §Epic D rows (Q-7, Q-9, Q-1b, D-8, X-4) to correct
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # §Q-7/Q-9/Q-1b/D-8/X-4 rows
  - docs/plan/preact-parity-A0-correct-record.spec.md      # precedent
  - docs/adr/decisions.md                                  # the FR-3 target file
governs:
  - docs/plan/preact-parity-epics.md                       # §Epic D corrections
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
  - docs/plan/preact-parity-sprint-board-D.md              # verified clean by grep
  - docs/adr/decisions.md                                  # newest-first entry appended
---

# Sprint D0 — Correct the record (Epic D refuted premises)

> **What / why split.** This spec is the *what* (grep-verifiable acceptance criteria).
> There is no *why*-ADR: D0 makes no structural change; its intent debt lives in a
> `docs/adr/decisions.md` entry (FR-3 below), which is the right weight per root
> `AGENTS.md`.

---

## 1. Goal

Erase **five refuted framings** from the PreAct parity knowledge plane before D1, D2, and
D3 enter their own `sdd-spec`. The `sdd-brainstorm` premise audit (2026-07-10) for Epic D
found five premises in the epics doc / parity report that the code does not support; if
left in place they would each seed a wrong-shape spec for the sprints that follow. D0 is
**docs-only** — it does not touch any production `.tsx` / VM / reducer / seed (that is
D1/D2). Explicit non-goal: D0 does not implement any Q-7/Q-8/Q-9/Q-1b/D-3b/D-8 fix.

Verification model: **grep + file inspection only** — no runtime tests, no arch test, no
`make check` gate additions. D0 is the smallest possible correction sprint. Each FR
collapses to a single `grep` or file-read that a reviewer runs by hand.

## 2. Context

The five refuted premises, with the audit evidence that refuted each ([brainstorm §1
premise audit](preact-parity-epic-D.brainstorm.md#1--premise-audit-grounded-against-the-working-tree)):

| # | Refuted premise (as epics-doc / report states it) | Refutation evidence (verified `file:line`) |
|---|---|---|
| **P3** | `Q-7` is a view-only chip render | Wire `Question` has no `skill_name` / `accent_var` ([`engine_entities.ts:61-64`](../../frontend/lib/wire/engine_entities.ts:61)); those live on `Skill` ([`:34-44`](../../frontend/lib/wire/engine_entities.ts:34)). Fix is hook + translator + view, not view-only. |
| **P8** | `Q-9` "dismissible timer" — learner turns off a rendered clock | No clock renders today — grep on `components/quiz/` for `timer`/`Clock`/`elapsed` = 0 UI hits. Reframe: *collapsible / off-by-default*. |
| **P10** | `Q-1b` is a code sprint ("change 30 to 10") | Parity report §Q-1b line 140 leaves the decision **explicitly open** ("is 30 intended for adaptive?"). This is a product decision, not a bug. Epics doc §Epic D itself says the decision may be "keep 30 — recorded in `decisions.md`, not necessarily a code change." |
| **P14** | `D-8` is a safe one-liner (add `"skill"` to `NAV_MEMBERSHIP`) | `screen("skill", ..., comingSoon: true)` already exists at [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) but its route `/learn/skill` **404s today** (Epic E territory). Adding to membership = **dead nav item** = same class as `Q-6` (closed by Epic A). |
| **P15** | `X-4` is a finding independent of `D-3b` | Parity report §X-4 explicitly says "see D-3b" — same 6-name list, cross-cut framing, not a separate finding. Merge into D2. |

If D0 does not land, each of D1/D2/D3 would spec against the stale framing:
- D1 would try to render a chip from `skillId` alone and be blocked at implementation.
- D2 would spec X-4 as a separate sprint and duplicate scope.
- D3 would spec a "change 30 to 10" code sprint before the product answer exists.
- D-8 would either be forgotten or land as a dead nav item.

**Precedent.** Sprints A0 and B0 ran the same shape: a Stage-1 audit refuted a load-bearing
premise, the correction landed as a docs-only sprint that unblocked the next spec.
D0 explicitly follows [A0's spec](preact-parity-A0-correct-record.spec.md) at a lighter
weight: A0 needed a runtime grep guard because A1's `sdd-spec` was already open and could
re-inherit the stale framing mid-flight; D0's follow-on sprints have not entered `sdd-spec`
yet, so a **one-pass reviewer grep + human read** is sufficient. No new arch test.

**Self-correction trap (inherited from A0).** D0's corrections must **quote** the phantom
framings in order to say they were wrong (the premise table above; the `decisions.md`
entry). This spec addresses that by scoping every FR-1..FR-5 check to a specific line the
correction TARGETS — the reviewer greps for the *live claim in the row/paragraph being
corrected*, not for the string anywhere in the file. Quoting-in-context (this spec, the
sprint board's premise table, the `decisions.md` entry) is not policed.

## 3. Functional requirements (EARS)

Failure/guard paths first, then the record corrections. Each FR collapses to one
grep-or-read check a human reviewer performs and pastes into the D0 DoD.

- **FR-1** (guard, failure-path). IF, after D0 lands, [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)
  still describes `Q-7` as a "skill chip" render WITHOUT naming the wire→VM→view seam,
  THEN the epics doc SHALL be treated as failing D0's DoD (FR-2 has not landed).
  *(Verified by opening the epics doc §Epic D `Q-7` row and reading it — the row must
  mention "VM"/"translator"/"hook" (P3 corrected framing), not just "chip".)*

- **FR-2** (Q-7 framing corrected in the epics doc). THE row for `Q-7` in
  [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)
  SHALL be amended to state that the fix touches wire→VM→view (`skillName` / `accentVar`
  join at the hook boundary), not just a chip render. The corrected row SHALL NOT imply
  the fix is view-only.

- **FR-3** (Q-9 framing corrected in the epics doc AND the VISUAL report). THE row for
  `Q-9` in [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)
  AND the §Q-9 entry in [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md)
  SHALL be amended to describe Q-9 as a **collapsible / off-by-default** timer, with a
  short note that `elapsed_ms` capture is already correct (cite
  [`session_summary_vm.ts:60-65`](../../frontend/lib/translators/session_summary_vm.ts:60)
  or the A2 triage record). The corrected rows SHALL NOT say "dismissible".

- **FR-4** (Q-1b framing corrected in the epics doc). THE row for `Q-1b` in
  [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)
  SHALL be amended to state that Q-1b is a **decision-first sprint (D3)** recorded via
  `decisions.md`; upgrades to code + ADR-0023 amend iff the decision changes
  `DEFAULT_TARGET_COUNT`. The corrected row SHALL NOT imply Q-1b is a code sprint by
  default.

- **FR-5** (D-8 gate + X-4 merge corrected in the epics doc AND the VISUAL report). THE
  row for `D-8` in the epics doc §Epic D SHALL be amended to state that
  `screen("skill")` already exists at `nav_model.ts:75` as `comingSoon` but is excluded
  from `NAV_MEMBERSHIP`, and that adding it before Epic E's `/learn/skill` route lands
  ships a dead nav item (Q-6 class); default posture = defer to Epic E; alternate = D4
  `comingSoon`-gated add. THE row for `X-4` SHALL be marked as **absorbed into D2**
  (cross-cut duplicate of `D-3b`), not shipped as a separate sprint. THE VISUAL report
  §D-8 SHALL carry a matching caveat that D-8 is gated on Epic E.

- **FR-6** (`decisions.md` intent-debt entry). THE SYSTEM SHALL record a newest-first
  entry in [`docs/adr/decisions.md`](../adr/decisions.md) noting: (a) the five refuted
  premises (P3, P8, P10, P14, P15) with a one-line rationale + `file:line` evidence
  citation for each; (b) that Epic D's sprint ladder is `D0 → { D1, D2, D3 }` (parallel-
  independent), with D4 optional; (c) that D-8 defaults to **deferred to Epic E**; (d) a
  Rejected-alternatives tail naming the discarded framings ("Q-7 view-only", "Q-9
  dismissible", "Q-1b code sprint by default", "D-8 free nav add", "X-4 as separate
  sprint"). *(This is the intent-debt payload — the *why* of D0. Follows the
  A0/B0 `decisions.md` shape.)*

- **FR-7** (sprint board finalization — no new claim, verify existing). THE
  [sprint board](preact-parity-sprint-board-D.md) SHALL be verified to already describe
  the corrected framings for Q-7 / Q-9 / Q-1b / D-8 / X-4 (the board was authored
  post-audit, so this should be a no-op check). IF any board row still contains the
  stale framing as a live claim, D0 SHALL correct it in the same PR. *(This is the
  self-check FR; A0's equivalent found a live claim in the A1 DoD — D0 verifies the
  board is already clean.)*

## 4. Data model / contracts

No wire shapes, schemas, types, or file formats change. No trust-kernel type is
touched → **no re-signing**, **no ADR trigger**. No new file is created (unlike A0,
which added a Python arch test). D0 edits three existing docs (epics, VISUAL report,
`decisions.md`) and re-reads one (the sprint board).

## 5. Invariants & security boundaries

- **Frontend Ring (root `AGENTS.md` #3/#6):** D0 does **not** touch `frontend/`. No
  `.tsx`, no VM, no reducer, no seed. `make check`'s frontend suites do not move.
- **No ⚠️ Ask-first trigger:** no new node/service/dep/trust-type/abstraction. A
  `decisions.md` entry (FR-6), not an ADR, is the correct capture weight — same as
  A0/B0.
- **OKF knowledge plane:** D0 is a Routine-3/4 correction (fix stale prose; keep
  extractable). It MUST leave `scripts/okf_lint.py` at **exit 0** (governed by
  `docs/CONVENTIONS_OKF.md`).
- **G8 no-test-weakening:** D0 adds no tests and rewrites no assertions, so the
  `test_no_test_weakening.py` sensor has no surface.

## 6. Edge cases

- **Self-reference (the load-bearing edge — same as A0 §6).** D0's corrections
  necessarily contain the phantom framings: this spec's §2 premise table, the
  `decisions.md` entry's rejected-alternatives tail, and the sprint board's own §D0
  premise table already do. **D0 does not police the corrections themselves** — the FRs
  target the *specific rows* being corrected in the epics doc and VISUAL report, not
  every occurrence of the strings anywhere in the repo. This is why D0 does not need
  A0's `<!-- refuted-framing-ok -->` sentinel machinery: no runtime grep guard is
  authored, so there is nothing that could over-fire on quoted-refuted mentions.
- **Line drift.** The `:NN` anchors in §2 are point-in-time (2026-07-10). All FR-2..FR-5
  checks are content-based (does the corrected row mention "VM"/"translator"/etc.), not
  line-number-based, so intervening edits do not break the checks.
- **Historical/superseded docs.** [`preact-ui-prototype-parity-gap-matrix.md`](preact-ui-prototype-parity-gap-matrix.md)
  is a superseded record and is **not** governed by D0 — its historical text stays
  as-is.
- **X-4 traceability.** After D0 marks X-4 as "absorbed into D2," the [epics doc
  §Traceability table](preact-parity-epics.md) row for backlog #8 must still resolve
  to Epic D — which it already does (backlog #8 = "Bucket taxonomy + color dots +
  Skills nav" → D). No traceability edit is needed; the change is display-language
  only.

## 7. Non-functional requirements

- **Determinism:** every FR is a grep-or-read check, no runtime, no LLM, no network.
- **Reversibility:** every change is a doc/paragraph edit — trivially revertible via git.
- **Cost/latency:** negligible (three doc edits + a `decisions.md` append + one grep
  pass over the board).

## 8. Test plan

Every FR maps to a **grep or read check**, run by a human reviewer at PR time and
pasted into the DoD (§9). No new automated test files are created.

| FR | Verification |
|----|--------------|
| FR-1 / FR-2 (Q-7 in epics doc) | `grep -n "Q-7" docs/plan/preact-parity-epics.md` — the surrounding row must contain "VM" or "translator" or "hook" (P3 corrected framing). |
| FR-3 (Q-9 in epics doc + VISUAL report) | `grep -n "Q-9" docs/plan/preact-parity-epics.md docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md` — the rows must contain "collapsible" (P8 corrected framing); must NOT contain "dismissible" as a live description. |
| FR-4 (Q-1b in epics doc) | `grep -n "Q-1b" docs/plan/preact-parity-epics.md` — the row must reference `decisions.md` or D3, not a code change. |
| FR-5 (D-8 + X-4 in epics doc + VISUAL report) | `grep -n "D-8\|X-4" docs/plan/preact-parity-epics.md docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md` — D-8 row must contain "Epic E" or "gated" (P14 corrected framing); X-4 row must contain "D-3b" or "absorbed" (P15 corrected framing). |
| FR-6 (`decisions.md` entry) | `head -60 docs/adr/decisions.md` — the newest entry must mention Epic D + all five premise IDs (P3, P8, P10, P14, P15) + the Rejected-alternatives tail. Human read pasted into DoD. |
| FR-7 (board verified clean) | `grep -niE "skill chip|dismissible|change 30 to 10|X-4 (as )?independent" docs/plan/preact-parity-sprint-board-D.md` — a live claim would surface here; the board already corrected these in-session, so this is a **verify-only** check expected to return no live claims (matches within the premise table / quoted context are fine — the board is not policed like the epics doc). |

**Red-first order:** D0 is docs-only; there is no runtime red-first cycle. Instead, the
"watched red" evidence is the **pre-D0 grep output** showing the stale framings live
in the epics doc and VISUAL report today — that output is pasted at the top of the
DoD (§9) so a reader can see what D0 corrected.

## 9. Definition of Done

- [x] **Pre-D0 grep output pasted** — showing the stale framings live in the epics doc
      + VISUAL report before any edit (the "watched red" for a docs-only sprint).
- [x] FR-2 epics doc `Q-7` row corrected (P3 framing); post-D0 grep pasted.
- [x] FR-3 epics doc + VISUAL report `Q-9` rows corrected (P8 framing); post-D0 grep
      pasted.
- [x] FR-4 epics doc `Q-1b` row corrected (P10 framing); post-D0 grep pasted.
- [x] FR-5 epics doc + VISUAL report `D-8` + `X-4` rows corrected (P14/P15 framings);
      post-D0 grep pasted.
- [x] FR-6 `decisions.md` newest-first entry appended (five premise refutations +
      ladder + D-8 default posture + Rejected tail); `head -60` output pasted.
- [x] FR-7 sprint board verified clean of live stale claims (findings-in-scope line
      corrected: dismissible → collapsible; remaining grep hits are premise-table /
      quoted-refutation context); grep output pasted.
- [x] `python scripts/okf_lint.py` → **exit 0** (knowledge plane still extractable).
- [x] `make check` green — should be a no-op since D0 touches no `frontend/` or
      `tests/` files; output pasted to confirm.
- [x] D0 explicitly logged as **corrected the record — did NOT implement any Q-7 / Q-8
      / Q-9 / Q-1b / D-3b / D-8 fix** (those are D1/D2/D3/D4). "Green" is not to be
      misread as "features shipped."
