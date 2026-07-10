---
title: 'Sprint A0 — Correct the record · Plan + Tasks'
type: plan
status: Draft
date: 2026-07-09
owner: Rajnish Khatri
epic: A
implements: docs/plan/preact-parity-A0-correct-record.spec.md
related:
  - docs/plan/preact-parity-sprint-board-A.md
  - docs/adr/decisions.md
---

# Sprint A0 — Plan + Tasks

Implements [preact-parity-A0-correct-record.spec.md](preact-parity-A0-correct-record.spec.md).
Docs-only; no `⚠️ Ask first` trigger → **no ADR** (a `decisions.md` entry is the capture, per FR-3).

---

## 1. Architecture / approach

A0 has two halves that must land in one PR, red-first:

1. **The guard (the durable artifact).** A new Python arch test,
   `tests/architecture/test_parity_docs_no_refuted_framing.py`, scans a **fixed allow-list of
   governed docs** for the phantom-contradiction framing as a *live claim*, and passes only when
   every governed doc is either clean or quotes the framing inside a **refutation context**. It
   follows the [test_skills_mirror_parity.py](../../tests/architecture/test_skills_mirror_parity.py)
   precedent (`_AGENT_ROOT = Path(__file__).resolve().parents[2]`, pure file reads, zero deps). It
   is part of `make check` via the `test` target.

2. **The corrections (make the guard go green).** Edit the four documents + one code comment that
   currently assert the contradiction, then re-run the guard until green.

**Guard design (the one non-trivial piece — hardened after the Analyze pass).** A per-line scan
over each governed file:

- **DENY** (a live assertion): case-insensitive match of `FR-D5/FR-D6 contradiction`,
  `Reveal\s+sanctioned`, or `self-contradict`. A match makes the line a *candidate violation*.
- **ALLOW** (refutation context): the **same line** ends with the explicit inline sentinel
  `<!-- refuted-framing-ok -->`. Nothing else allows it.

A file **fails** iff it has ≥1 candidate line without the sentinel. The failure message lists
`file:line` + the offending text. This encodes **FR-1** (deny live claims) and **FR-7** (permit
quoted-refuted mentions) in one pass.

> **Why a single explicit sentinel, not a "REFUTED nearby" heuristic.** The Stage-4 Analyze grep
> found the phantom strings scattered across A0's *own* correction prose — the premise table, the
> "Notes carried back" section, and the task descriptions ("still say '…contradiction'; correct to
> …"). A line-proximity rule (`REFUTED` on the same line) both **false-negatives** (a `REFUTED`
> section header with the quote two lines down) and **false-positives** (unrelated prose). A single,
> self-documenting, must-be-on-the-line sentinel is unambiguous and greppable. Cost: every quoting
> line A0 authors/keeps must end with the sentinel — a deliberate, visible act.

**Governed-file allow-list (explicit — excludes historical/superseded docs, spec §6):**

```
docs/plan/preact-parity-sprint-board-A.md
docs/plan/preact-parity-epics.md
docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
```

*Excluded on purpose:* `preact-ui-prototype-parity-gap-matrix.md` (superseded record), this A0
spec/plan pair (they *define* the refutation), and `docs/adr/decisions.md` (the new entry quotes the
framing to reject it; the long decision log is not policed). The QuizView comment is checked by a
**separate** FR-2 assertion, not this doc scan.

> **Note (Analyze finding):** the sprint board **is governed** and is **not yet clean** — it has a
> surviving live claim at the A1 DoD (board `:186`) plus A0's own quoting lines (premise table,
> "Notes carried back", task prose). A0 corrects `:186` and appends the sentinel to every remaining
> quoting line in the board (task A0-0 below), so the guard passes for it. FR-5 is therefore a real
> edit, not a no-op checkpoint.

**Why a Python arch test, not OKF lint or vitest.** `make check` runs `cite-lint` + `test`, **not**
`okf_lint` (verified in the `Makefile`) — so only a `tests/`-tree test actually gates. A frontend
vitest doc-lint would gate only the frontend suite and couldn't see `docs/plan/*`. The arch test
sees the whole repo and rides the existing precedent. `okf_lint` still runs as a DoD structural
check (exit 0), separately.

## 2. File-level touchpoints

| # | File | Change | FR |
|---|------|--------|----|
| T1 | `tests/architecture/test_parity_docs_no_refuted_framing.py` | **new** — the guard (deny + allow regex over the governed list; +an FR-2 assertion on the QuizView comment; +an FR-7 fixture) | FR-1, FR-2, FR-7 |
| T2 | [frontend/components/quiz/QuizView.tsx:104](../../frontend/components/quiz/QuizView.tsx:104) | amend the FR-D6 **comment** → "silent on gating; behavior decided in A1" (no behavior change) | FR-2 |
| T3 | [docs/adr/decisions.md](../adr/decisions.md) | **prepend** newest-first entry (compatibility + ID-collision + A1-deferral + Rejected tail) | FR-3 |
| T4 | [docs/plan/preact-parity-epics.md:97,101](preact-parity-epics.md:97) | correct the `Q-6` row + the "Release criteria" line to drop "contradiction" | FR-4 |
| T5 | [docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md:145,321](preact-ui-prototype-parity-VISUAL-gap-report.md:145) | correct both `Q-6` rows (keep clip evidence + `🟥 latent`) | FR-6 |
| T6 | [docs/plan/preact-parity-sprint-board-A.md:186](preact-parity-sprint-board-A.md:186) + quoting lines | correct the surviving A1-DoD live claim; append `<!-- refuted-framing-ok -->` to every remaining quoting line (premise table, "Notes carried back", A0 task prose) | FR-5, FR-7 |

## 3. Migration / sequencing

Red-first is mandatory (TAP-4). Order:

1. **T1a** — write the guard + run it → **must fail** on the current tree. The Analyze grep confirms
   live/quoting hits in board `:95/:98/:186/:279/:282`, epics `:97/:101`, and VISUAL `:145/:321`, so
   the guard is non-vacuous. **Paste the red.**
2. **T6/A0-0, then T2–T5** — finalize the board (correct `:186`, sentinel the quoting lines), then
   apply the QuizView + epics + VISUAL + `decisions.md` corrections.
3. **T1b** — re-run the guard → green. Then `make check` + `okf_lint`.

No dependency on A1/A2. Ships as its own PR.

## 4. Constitution check (root `AGENTS.md`)

- Invariants #1–#8: untouched (docs + a comment + a repo-doc test; no layer imports, no trust type,
  no framework leak). Frontend F-R1 holds — T2 is a comment.
- ⚠️ Ask-first list: none triggered → no ADR (FR-3 `decisions.md` entry is correct weight).
- G8 no-test-weakening: A0 *adds* a test, rewrites no assertion → no sensor surface.
- `test_adr_ratchet.py`: A0 touches no ADR seam (no `trust/models.py`, no new node/service/dep), so
  no `docs/adr/*` file is required. (The changed paths are docs + a test + a `.tsx` comment.)

---

## 5. Task list (atomic, 1:1 to EARS)

Each task names its file(s), its verification, and the FR it closes. Failure/guard tasks first.

### Task A0-1 — Author the guard, seen red first  `[FR-1, FR-7]`
- **Do:** create `tests/architecture/test_parity_docs_no_refuted_framing.py` with:
  - `test_no_live_contradiction_claim` — scans the governed allow-list; DENY regex minus ALLOW
    marker; fails listing `file:line`.
  - `test_allows_quoted_refuted_mention` — an inline fixture string carrying the phrase + `REFUTED`
    (and one with the `<!-- refuted-framing-ok -->` sentinel) is accepted.
- **Verify (red):** `pytest tests/architecture/test_parity_docs_no_refuted_framing.py -q` **FAILS**
  on the current tree (epics + VISUAL still assert the framing). **Paste the failure output.**
- **Pass/fail:** the test exists, is non-vacuous (fails now), and the failure names the real
  offending lines.

### Task A0-0 — Finalize the sprint board (surviving claim + sentinels)  `[FR-5, FR-7]`
- **Do:** in [preact-parity-sprint-board-A.md](preact-parity-sprint-board-A.md): (a) correct the
  surviving live claim at the A1 DoD (`:186` — done in this session's edit; confirm it reads
  "build-vs-remove decision recorded", not "contradiction resolved"); (b) append
  `<!-- refuted-framing-ok -->` to **every** remaining line that quotes the phantom phrase (the
  premise-table `REFUTED` rows, the "Notes carried back" quotes, and the A0 task-description lines
  at `:95/:98`).
- **Verify:** the FR-1 guard passes for the board (`grep` shows every DENY-hit line ends with the
  sentinel, or is corrected away).
- **Pass/fail:** board has zero un-sentineled live claims.

### Task A0-2 — Correct the QuizView FR-D6 comment  `[FR-2]`
- **Do:** amend [QuizView.tsx:104](../../frontend/components/quiz/QuizView.tsx:104) — the comment
  states FR-D6 is *silent on gating/behavior*, behavior *decided in Sprint A1*; no code/behavior
  change. Add `test_quizview_comment_flags_fr_d6_gating_unspecified` to the guard file asserting the
  corrected wording is present and no reveal-licensing phrasing remains.
- **Verify:** the FR-2 test goes green; `frontend` build/tests unaffected (comment-only).
- **Pass/fail:** comment matches corrected wording; FR-2 test passes.

### Task A0-3 — Record the resolution in `decisions.md`  `[FR-3]`
- **Do:** prepend a newest-first entry to [decisions.md](../adr/decisions.md): (a) FR-D5/FR-D6
  **compatible** (hint-non-reveal vs. separate control existence), citing the **UI** spec by path;
  (b) the **engine-spec ID collision** caveat; (c) build-vs-remove **deferred to A1**; Rejected tail
  names the discarded "adjudicate a contradiction" framing. The entry line itself may quote the
  phantom phrase (it is in the decision log, outside the guard's parity-doc list).
- **Verify:** `head -20 docs/adr/decisions.md` shows the entry newest-first. Paste it.
- **Pass/fail:** entry present with (a)/(b)/(c) + Rejected; dated 2026-07-09.

### Task A0-4 — Correct the epics doc  `[FR-4]`
- **Do:** rewrite [preact-parity-epics.md:97](preact-parity-epics.md:97) `Q-6` row and the
  `:101` release-criteria line: strike "FR-D5 … vs FR-D6 … contradiction" → "close the dead control
  (no contradiction; FR-D6 gating unspecified, decided in A1)". Keep the "Confirmed dead" trust-bug
  framing.
- **Verify:** the guard no longer flags this file; manual read confirms corrected wording.
- **Pass/fail:** no live "contradiction" claim remains; guard green for this file.

### Task A0-5 — Correct the VISUAL gap report  `[FR-6]`
- **Do:** rewrite the two `Q-6` rows at
  [VISUAL-gap-report.md:145,321](preact-ui-prototype-parity-VISUAL-gap-report.md:145) → "trust bug:
  dead control; FR-D5/FR-D6 compatible (see A0)". **Preserve** the visual-clip evidence, the
  `🟥 latent`/`🐞 dead` classification, and the row structure.
- **Verify:** guard green for this file; clip links + severity tags intact on manual read.
- **Pass/fail:** no live claim; evidence + classification preserved.

### Task A0-6 — Green the gate + verify board  `[FR-1, FR-5, DoD]`
- **Do:** re-run the guard → **green**; run `make check`; run `python scripts/okf_lint.py`.
- **Verify (all pasted, not summarized):**
  - `pytest tests/architecture/test_parity_docs_no_refuted_framing.py -q` → pass (incl. board, FR-5).
  - `make check` → green.
  - `python scripts/okf_lint.py` → exit 0.
- **Pass/fail:** all three green; board confirmed clean by the guard (FR-5, no re-edit).
- **Log line:** "A0 corrected the record; the `quiz-reveal` control is unchanged — that is A1."

---

## 6. Parallelization

- **A0-1 is the gate** and must be red before any correction (defines "done" for A0-2…A0-5).
- **A0-2, A0-3, A0-4, A0-5 are independent** (different files) and may be applied in any order /
  together once A0-1 is red.
- **A0-6 is the barrier** — runs after all corrections.

## 7. What is explicitly NOT in A0

- The `quiz-reveal` control's behavior (build/disable/remove) — **Sprint A1**.
- Any VM/reducer/`.tsx` change beyond the T2 comment.
- Rewriting the superseded Stage-1 matrix.
