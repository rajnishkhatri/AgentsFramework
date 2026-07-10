---
title: 'Sprint A0 — Correct the record (audit-refuted FR-D5/FR-D6 premise) · Spec'
type: spec
status: Draft
date: 2026-07-09
owner: Rajnish Khatri
epic: A
derives_from: docs/plan/preact-parity-sprint-board-A.md
related:
  - docs/plan/preact-parity-sprint-board-A.md          # Sprint A0 section + ladder
  - docs/plan/preact-parity-epics.md                   # Epic A goal (Q-6 row + Gates line to correct)
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # §Q-6 rows to correct
  - docs/plan/preact-english-coach-ui.spec.md          # canonical FR-D5/FR-D6 (UI spec)
  - docs/plan/preact-english-coach-engine.spec.md      # colliding FR-D5/FR-D6 (engine spec)
  - docs/adr/decisions.md                              # 2026-07-02 premise-audit entry (why "correct-and-continue")
governs:
  - frontend/components/quiz/QuizView.tsx              # the over-strong FR-D6 comment (task 1)
  - tests/architecture/test_parity_docs_no_refuted_framing.py  # the grep guard (task 4)
---

# Sprint A0 — Correct the record (audit-refuted FR-D5/FR-D6 premise)

> **What / why split.** This spec is the *what* (testable acceptance criteria). There is no
> *why*-ADR: A0 makes no structural change, so its intent debt lives in a `docs/adr/decisions.md`
> entry (FR-3 below), which is the right weight per root `AGENTS.md`.

---

## 1. Goal

Erase a **false claim** from the PreAct parity knowledge plane and stop it recurring. The
`sdd-brainstorm` premise audit (2026-07-09) for Sprint A1 **refuted** the load-bearing premise that
quiz requirements **FR-D5** and **FR-D6** *contradict* each other. Four documents and one code
comment still assert that phantom contradiction; A0 corrects each and adds a mechanical guard so the
refuted framing cannot re-enter as a live claim. A0 is **docs-only** — it does not touch the
`quiz-reveal` control's behavior (that is Sprint A1).

## 2. Context

The board framed A1 as "adjudicate a self-contradictory spec." The audit ([sprint board §A0
premise table](preact-parity-sprint-board-A.md)) established, with verified `file:line` evidence,
that the canonical UI spec is coherent:

- **FR-D5** ([preact-english-coach-ui.spec.md:173-175](preact-english-coach-ui.spec.md:173)):
  *WHEN "Get a hint" is activated … SHALL NOT reveal the correct answer* — constrains the **hint**.
- **FR-D6** ([preact-english-coach-ui.spec.md:176-177](preact-english-coach-ui.spec.md:176)):
  *SHALL render "Reveal answer" as a … ghost control separate from "Get a hint"* — requires the
  control to **exist**; **silent on gating/behavior**.

The two do not clash. The "contradiction" originates in an **over-strong code-comment paraphrase**
at [QuizView.tsx:104](../../frontend/components/quiz/QuizView.tsx:104) ("Reveal answer is a low-emphasis
ghost control") that later docs escalated to "Reveal **sanctioned**," which the board and report
inherited. Two further hazards the audit surfaced:

1. **ID collision.** The *engine* spec ([preact-english-coach-engine.spec.md:173-184](preact-english-coach-engine.spec.md:173))
   reuses FR-D5/FR-D6 for **unrelated** requirements (`used_hint` persistence; recommended-next
   drill). Any bare "FR-D6" is ambiguous → citations must name the **UI** spec by path.
2. **Self-correction trap.** A0's own corrections must *quote* the phantom "contradiction" to say
   it was wrong (the premise table's `REFUTED` row; the `decisions.md` entry). The guard (FR-6/FR-7)
   must therefore distinguish a **live assertion** from a **quoted-and-refuted mention**, or it
   would reject A0's own honest record-keeping.

Per the brainstorm-hardening rule ([decisions.md 2026-07-02 premise-audit entry](../adr/decisions.md)),
a refuted load-bearing premise is handled **correct-and-continue**: re-pose the corrected framing as
tracked work. A0 is that tracked work.

**Already applied in-session (verification-only in A0):** the *sprint board itself* was corrected
live during the brainstorm (the A0 section, ladder row, premise table, A1 re-framing, and "Notes
carried back"). A0 does not re-edit the board; it **verifies** the board no longer asserts the
contradiction (FR-5).

## 3. Functional requirements (EARS)

Failure/guard paths first (FR-1, FR-6, FR-7), then the record corrections.

- **FR-1** (guard, failure-path). IF any governed parity doc asserts the FR-D5/FR-D6 "contradiction"
  as a **live claim** (a bare `FR-D5/FR-D6 contradiction`, `Reveal sanctioned`, or `self-contradict*`
  on a line **not** carrying the refutation sentinel per FR-7) THEN the guard test SHALL fail.
  *(Write this test and watch it fail on the current tree first — the assertion is non-vacuous
  because the strings exist today at the anchors in §6, including a surviving live claim at
  [sprint board §A1 DoD](preact-parity-sprint-board-A.md) that the in-session brainstorm edit
  missed — see FR-5.)*
- **FR-2.** THE code comment at [QuizView.tsx:104](../../frontend/components/quiz/QuizView.tsx:104)
  (currently `FR-D6: Reveal answer is a low-emphasis ghost control, separate from the hint.`) SHALL
  be amended to state that **FR-D6 is silent on gating and behavior** and that the control's
  behavior is **decided in Sprint A1** — so the comment can no longer be read as licensing a reveal
  (the seed the docs escalated to "sanctioned"). The corrected comment SHALL NOT imply Reveal may
  show the answer.
- **FR-3.** THE SYSTEM SHALL record, as a newest-first `docs/adr/decisions.md` entry: (a) FR-D5 and
  FR-D6 are **compatible** (hint-non-reveal vs. a separate control's existence), citing the **UI**
  spec by path; (b) the **engine-spec ID collision** caveat; (c) that the build-vs-remove decision
  is **deferred to A1**. *(The Rejected-alternatives tail names the discarded "adjudicate a
  contradiction" framing — this is the intent-debt payload.)*
- **FR-4.** WHERE [preact-parity-epics.md](preact-parity-epics.md) states the FR-D5/FR-D6
  contradiction (the `Q-6` row `:97` and the Gates line `:101`), THE SYSTEM SHALL correct it to
  "close the dead control (no contradiction; FR-D6 gating unspecified)".
- **FR-5** (board finalization). THE [sprint board](preact-parity-sprint-board-A.md) SHALL contain
  **no** live "contradiction" assertion. The A0 *section* was corrected in-session, BUT the Analyze
  pass found a **surviving live claim in the A1 DoD** ("the FR-D5/FR-D6 contradiction is resolved in
  `decisions.md`") — A0 SHALL correct that line too. Any A0 task/notes prose that must *quote* the
  refuted phrase SHALL carry the FR-7 sentinel. A0 then confirms the board is clean via the FR-1
  guard.
- **FR-6.** WHERE [preact-ui-prototype-parity-VISUAL-gap-report.md](preact-ui-prototype-parity-VISUAL-gap-report.md)
  states the contradiction (the `Q-6` rows `:145` and `:321`), THE SYSTEM SHALL correct each to
  "trust bug: dead control; FR-D5/FR-D6 compatible" while preserving the visual-clip evidence and
  the `🟥 latent`/dead-button classification.
- **FR-7** (guard, refutation-aware). WHERE a line in a governed doc *quotes* the refuted framing
  **and** carries the explicit inline sentinel `<!-- refuted-framing-ok -->` on that same line, THE
  guard SHALL treat it as allowed and NOT fail. *(A single, explicit, self-documenting marker —
  chosen over "any `REFUTED` word nearby" because the Analyze pass showed line-proximity heuristics
  false-negative across multi-line contexts and false-positive on unrelated prose. The premise-table
  `REFUTED` rows, the "Notes carried back" quotes, and A0's own task text each get the sentinel on
  the quoting line; the guard stays a simple per-line deny-unless-sentinel scan.)*

## 4. Data model / contracts

No wire shapes, schemas, types, or file formats change. No trust-kernel type is touched → **no
re-signing**, **no ADR trigger**. The only *new* file is the guard test
`tests/architecture/test_parity_docs_no_refuted_framing.py` (a repo-doc assertion, precedent:
[test_skills_mirror_parity.py](../../tests/architecture/test_skills_mirror_parity.py)).

## 5. Invariants & security boundaries

- **Frontend Ring (root `AGENTS.md` #3/#6, F-R1):** FR-2 edits a **comment** in
  `QuizView.tsx` — no behavior, no VM, no import, no SDK. The presentational component and its
  `QuizItemVM` are untouched; `make check`'s frontend suites do not move.
- **No ⚠️ Ask-first trigger:** no new node/service/dep/trust-type/abstraction. A `decisions.md`
  entry (FR-3), not an ADR, is the correct capture weight.
- **OKF knowledge plane:** A0 is a Routine-3/4 correction (fix stale prose; keep extractable). It
  must leave `scripts/okf_lint.py` at **exit 0** (governed by `docs/CONVENTIONS_OKF.md`). Note
  `okf_lint` is *not* in `make check` (which runs `cite-lint`, not `okf_lint`) — so A0 runs it
  explicitly as a DoD step (§9).
- **G8 no-test-weakening:** A0 *adds* a test and rewrites no existing assertion, so the
  `test_no_test_weakening.py` sensor has no surface.

## 6. Edge cases

- **Self-reference (the load-bearing edge — confirmed by the Analyze pass).** A0's corrections
  necessarily contain the phantom strings: the premise-table `REFUTED` rows, the "Notes carried
  back" quotes, and A0's own task descriptions ("still say '…contradiction'; correct to …"). The
  Analyze grep found these on the current tree. The FR-7 **inline sentinel** is what lets each such
  line coexist with the guard. A guard without it would fail on the very commit that fixes the docs.
  Every quoting line A0 authors/leaves in a governed doc MUST end with `<!-- refuted-framing-ok -->`.
- **Correct usage of "sanctioned" elsewhere.** [QuizView.tsx:17](../../frontend/components/quiz/QuizView.tsx:17)
  uses "sanctioned" correctly (the `dangerouslySetInnerHTML` delivery of reviewed content). The
  guard scopes to the FR-D6 *paraphrase* pattern (`Reveal .*sanctioned` / the contradiction phrase),
  NOT the bare word "sanctioned", so line 17 does not trip it.
- **Line drift.** The `:NN` anchors in §3 are point-in-time (2026-07-09). Implementation greps the
  **string**, not the line number, so an intervening edit that shifts lines does not break the task.
- **Historical/superseded docs.** The Stage-1 matrix
  ([preact-ui-prototype-parity-gap-matrix.md](preact-ui-prototype-parity-gap-matrix.md)) is
  explicitly superseded; A0 does **not** rewrite it (it is a record of what was believed then). The
  guard's governed-file list excludes superseded docs so their historical text is not policed.

## 7. Non-functional requirements

- **Determinism:** the guard is a pure string/regex scan over a fixed file list — L1 deterministic,
  no LLM, no network, runs in `make check`.
- **Reversibility:** every change is a doc/comment edit or one new test file — trivially revertible.
- **Cost/latency:** negligible (a handful of file reads).

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/architecture/test_parity_docs_no_refuted_framing.py::test_no_live_contradiction_claim` — **seen red first** on the pre-A0 tree (strings present at §6 anchors) | L1 | yes |
| FR-7 | `…::test_allows_quoted_refuted_mention` — a fixture line carrying `REFUTED`/sentinel is accepted | L1 | yes |
| FR-2 | `…::test_quizview_comment_flags_fr_d6_gating_unspecified` (asserts the QuizView FR-D6 comment carries the "gating unspecified / decided in A1" wording) | L1 | yes |
| FR-3 | Manual: `decisions.md` newest-first entry present with (a)/(b)/(c) + Rejected tail; pasted `head` output in DoD | doc | no (human diff + grep) |
| FR-4 | Covered by FR-1 guard over `preact-parity-epics.md` (no live claim) + manual read of the corrected `Q-6`/Gates wording | L1 + doc | yes (guard) |
| FR-5 | FR-1 guard over the sprint board, **after** correcting the surviving A1-DoD live claim + sentineling A0's quoting lines | L1 | yes |
| FR-6 | Covered by FR-1 guard over the VISUAL report + manual read that clip evidence + `🟥 latent` survive | L1 + doc | yes (guard) |

**Red-first order:** author the FR-1 guard, run it, and **paste the failure** (it must fail on the
current docs — otherwise it is vacuous, TAP-4). Only then make the doc corrections until the guard
goes green. FR-7's allow-rule is added *with* the guard (they co-design), tested by a fixture.

## 9. Definition of Done

- [ ] FR-1 guard authored and **seen to fail first** on the pre-A0 tree (failure output pasted).
- [ ] FR-2 `QuizView.tsx:104` comment corrected; FR-2 test green; no other `frontend/` change.
- [ ] FR-3 `decisions.md` newest-first entry appended (compatibility finding + ID-collision caveat +
      A1-deferral + Rejected tail); `head` output pasted.
- [ ] FR-4 epics doc `Q-6` row + Gates line corrected; FR-6 VISUAL report `Q-6` rows corrected
      (clip evidence + `🟥 latent` preserved).
- [ ] FR-5 sprint board confirmed clean by the guard (no re-edit needed).
- [ ] `make check` green (the new arch test passes; `cite-lint` + hygiene unaffected) — **actual
      output pasted, not summarized**.
- [ ] `python scripts/okf_lint.py` → **exit 0** (knowledge plane still extractable).
- [ ] A0 explicitly logged as **corrected the record — did NOT fix the control** (that is A1), so
      "green" is not misread as "Reveal fixed."
