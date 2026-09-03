# Handover — Exam module phase 2 (real official forms) → new session runs `sdd-implement`

**Written:** 2026-09-03 · **From:** the planning session that produced the SDD artifacts below
**For:** a fresh Claude Code session (zero prior context) that will execute the approved tasks
**State:** SDD Stages 2–4 **done and human-approved**; **implementation NOT started** (explicit
instruction). Everything below is on disk but **UNCOMMITTED** — see §3 before doing anything.

---

## 1. Situation in three sentences

The shipped `exam` module serves **only English**, and that English is an **authored** practice
test (`PreAct/practice-tests/Test-01.md`), not a real ACT — the other three sections were
phase-1's *deliberate* non-goals, not an oversight. The **real official forms** exist as
**verified** ©ACT JSON under the git-ignored `docs/preact9secure/json/` but the app cannot load
them: there is no server grading path, no image field, no passage rendering. This work loads
**PT2** (`act-practice-test-2`, Enhanced ACT) across **all four sections**, key-safe and
server-graded, as the fastest build a tester can sit — with three parallel worktrees.

## 2. Read these, in this order (≈15 min)

1. [exam-module-official-forms.spec.md](exam-module-official-forms.spec.md) — the *what*: FR-P2-1…19 (EARS), data model §4, non-goals §2.1.
2. [exam-module-official-forms.plan.md](exam-module-official-forms.plan.md) — the *how*: architecture §1, lanes §2, **parallel-worktree topology §6** (why by file-ownership, not by section), Phase-3 validation §6.4.
3. [exam-module-official-forms.tasks.md](exam-module-official-forms.tasks.md) — **the executable list**: Phase 0 BASE → WT-A ∥ WT-B ∥ WT-C → SERIAL → VALIDATE ∥×4, each with a RED-FIRST test → FR.
4. [ADR-0042](../adr/0042-exam-official-forms-asset-served-server-graded.md) — the *why* + rejected options; it **fires** [ADR-0041](../adr/0041-exam-answer-key-posture.md)'s tripwire (0041 amended → Option B for asset-served forms).
5. `docs/adr/decisions.md` — the two 2026-09-03 entries (image-necessary rule; parallel cut).
6. Phase-1 context if needed: [exam-module-official-rules.spec.md](exam-module-official-rules.spec.md) / `.plan.md` / `.tasks.md` (the runtime you are extending, incl. its own worktree strategy §6 that this plan mirrors).

## 3. Git state — do this FIRST

- **Branch:** `fix/exam-ui-polish` (1 commit ahead of `main`: `abf14d4` scrollable runner/Prev-Next).
- **UNCOMMITTED SDD artifacts** (this work): `docs/plan/exam-module-official-forms.{spec,plan,tasks,handover}.md`,
  `docs/adr/0042-exam-official-forms-asset-served-server-graded.md`, and edits to
  `docs/adr/{0041-exam-answer-key-posture.md,index.md,log.md,decisions.md}`.
- **Nothing to commit from the baseline fix** (§4): `make skills-pack` (run 2026-09-03) regenerated the **git-ignored, machine-local** `docs/skills/sdd-skills-bundle.zip` — the stale artifact; the six tracked `docs/skills/*.skill` archives came out byte-identical to HEAD. (`make skills-sync` was tried first and does **not** clear it — it only syncs mirrors.) Unrelated to exam code.
- The tree also carries **other pre-existing uncommitted work** (`.arch/`, `arch-lifecycle-bundle/`, untracked `.claude/skills/arch-*`, presentations, etc.) that is **not** part of this handover. Leave it alone.
- ⚠️ **Never `git reset --hard` / `git stash` in this tree** (repo rule — uncommitted work has been lost that way before).

**Recommended first action:** commit the SDD docs (+ the skills-sync regeneration) as one docs
commit on `fix/exam-ui-polish`, e.g. `docs(exam): phase-2 official-forms spec/plan/tasks + ADR-0042`.
Then decide the base-branch parentage with the user (plan says `feat/exam-official-forms` **off
`main`**, but `main` won't contain these docs): either merge `fix/exam-ui-polish → main` first if
that PR is ready, **or** branch `feat/exam-official-forms` off `main` and cherry-pick the docs
commit onto it. Ask; don't guess.

## 4. Baseline status (Stage-4 precondition) — re-verify, don't trust

| Gate | Result on 2026-09-03 | Re-verify with |
|---|---|---|
| OKF lint (ADR frontmatter/index/log) | **0 failures** (770 pre-existing broken-link warnings, none in new files) | `.venv/bin/python scripts/okf_lint.py` |
| Hygiene (trailing ws / EOF newline) on the 8 docs | clean | `make check` runs the same hooks |
| `pytest tests/architecture/ -q` | first run: 252 passed, 4 skipped, **1 failed** (`test_skills_pack::test_pack_check_detects_drift` — the **git-ignored, machine-local** `docs/skills/sdd-skills-bundle.zip` was stale; the tracked `.skill` archives and the SKILL.md sources are clean at HEAD; unrelated to exam). **Fixed with `make skills-pack`** (`make skills-sync` does **not** clear it) → **253 passed, 4 skipped — observed 2026-09-03.** | `.venv/bin/python -m pytest tests/architecture/ -q` → expect **253 passed**. On a **fresh clone or any new worktree** the ignored zip is absent ⇒ run `make skills-pack` once first, or this test is red |
| Frontend | not run this session | `cd frontend && pnpm vitest run && pnpm typecheck` |

Run all four **before Phase 0**. Use `.venv/bin/python` — it is the only working interpreter here.

## 5. Decisions already made — do NOT re-litigate

| Decision | Value | Where recorded |
|---|---|---|
| Source of truth | verified private official-form JSON (`docs/preact9secure/json/`), **not** the authored Test-01 | ADR-0042 |
| First form | **PT2** `act-practice-test-2` (Enhanced ACT; all 4-choice → fits renderer gate; has scale tables). 805 + 5-choice + form picker = follow-up | ADR-0042, spec §2.1 |
| Sections | **all four**, one form, end-to-end | spec §1 |
| Rendering | **text-first**; official PNG **only** where `text_fidelity ∈ {math-notation, low}` or the passage is a figure (Math 34/45, Science ~10, English/Reading **0**) | decisions.md, `exam_image_rule` |
| Delivery | **`FormAssetStore` port** — `LocalFileAssetStore` now (local/dev, `node:fs`, $0), `GcsAssetStore` later (~$0 cost; needs **middleware** signed-URL — F-R9 forbids GCS creds in the BFF) | ADR-0042, spec §4.3/4.4 |
| Grading | **server-side, keys never client-served** for asset-served forms (ADR-0041 tripwire fired). Test-01 stays client-bundled (recorded exemption) | ADR-0041 amendment, spec FR-P2-5..9 |
| Guard | **harden** `test_exam_no_client_served_keys`: retire the textual `db-served` heuristic → resolved-graph + payload-schema + red fixtures | spec FR-P2-8, task B0-5 |
| Parallelism | implementation by **file ownership** (converter ∥ server ∥ render), **not** by section; validation **by section** (E ∥ M ∥ R ∥ S) | plan §6.1/§6.4, decisions.md |
| Tester env | local/dev first | spec §2 |

## 6. Session-verified facts you can rely on (don't redo)

- `PreACT_Secure_Practice_805.pdf` sha256 `526ccc736d7cec59bbef186d5170f8be169c3d1ee98ff33c645bae13a0125247` **== `preact-secure-805.json` `source.sha256`**; 27 extractor tests pass; **all four sections' keys match the PDF scoring page with 0 mismatches** (Eng 48 · Math 38 · Read 33 · Sci 36).
- `ACT-Test-Prep-ACT-Practice-Test-2-Form1.pdf` sha256 `2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d` **== `act-practice-test-2.json` `source.sha256`** (Form1 = byte-identical dup of Form). PT2: Eng 50/40 scored · Math 45/41 · Read 36/27 · Sci 40/34; all `choice_count: 4`; `has_scale = true` all sections. **PT2's full key diff is still PENDING** — task **A-2** closes it using the PDF's scoring-key page, same method as 805 (extract page text with PyMuPDF; don't eyeball two-column keys).
- PT2 image inventory: 171 question PNGs (4.2 MB) + 46 page PNGs (6.5 MB); necessary under text-first ≈ **44** (Math 34 lossy + Science 4 lossy + ~6 figure passages).
- Code reality (explore map): `db-served` is a dormant literal; no image field in the wire; `ExamQuestion.passage` is an analytics label only; grading is client-side in `DrizzleExamRunRepo.finishSection` (same class in both composition roots); the `"server-only"` disposition slot exists and is unused by exam; conformance pins **exactly 41 methods / 5 server-only** (`http_engine_db.conformance.test.ts:46-47`) → becomes **43 / 6**; exam learner-arg map is **`EXAM_LEARNER_ARG`** (`route.ts:20,40`).

## 7. Exact next steps (the new session's runbook)

0. §3 commit + parentage decision with the user; §4 baseline green.
1. Invoke **`/sdd-implement`** with `docs/plan/exam-module-official-forms.tasks.md`.
2. **Phase 0 (BASE)** on `feat/exam-official-forms`: tasks **B0-1…B0-8** in order; **B0-5 guard is RED-FIRST** (both planted fixtures must fail before you make it green); **B0-8 `.gitignore` before any converter run**. Then **freeze** wire/port/rule/fixture/posture/guard.
3. Create the three worktrees off base (plan §6.2), e.g.
   `git worktree add .worktrees/exam-converter -b feat/exam-wt-converter feat/exam-official-forms` (and `exam-server`, `exam-render`). In each: symlink `frontend/node_modules` → main checkout's, and the root `.venv` → main checkout's (repo worktree rule). The private folder is **not** in worktrees — WT-A points the converter at the main checkout's `docs/preact9secure/` via `--src`. **Also run `make skills-pack` once in each new worktree**: the bundle zip it produces is git-ignored, so it is absent in a fresh worktree and `pytest tests/architecture/` is red there until it exists (found 2026-09-03).
4. Execute **WT-A (A-1…A-3) ∥ WT-B (B-1…B-8) ∥ WT-C (C-1…C-5)** — three parallel sessions/subagents, each confined to its directory. Merge each → base **independently when green** (`make check` + `pnpm vitest run` + `pnpm typecheck` + `pytest tests/architecture/ -q`). WT-B's merge is the first **non-vacuous** run of the hardened guard.
5. **Phase 2 SERIAL** S-I1…S-I4, S-F1 (ADR-0042 → Accepted). Real converter run needs the private folder present locally.
6. **Phase 3 VALIDATE ∥×4** (V-E/M/R/S — per-section discrepancy reports under `docs/plan/exam-official-forms-validation/`), then **V-T** tester sits a full PT2 run. Findings → `sdd-converge`.

## 8. Hard rules / gotchas for the implementer

- **Red/green TDD** every task; paste actual test output, not summaries.
- **Never** commit anything from `docs/preact9secure/` or `exam_forms/_generated/` (©ACT). Client artifacts must strict-parse under `ClientExamForm` (zero answer-bearing fields).
- **Do not** widen `lib/translators/quiz_item_vm.ts` (shared with the quiz; isolation guard) — use the exam-local `exam_item_vm.ts`.
- `finishExamSection` stays `"fine"` (client triggers); only `getExamFormKeys` is `"server-only"`. Client path for asset-served forms must **skip** local scoring.
- Env reads only in `lib/composition_engine.ts` (`EXAM_ASSET_DIR`); the browser composition root gets **no** asset store.
- Test-01 must keep working unchanged (client-bundled, its e2e green).
- Totality tests will go red **on purpose** (41→43, 5→6, `EXAM_LEARNER_ARG` completeness) — each is a listed task, not a surprise.
- Lanes must **not** edit frozen Phase-0 files; route wire changes back to base.
- FR-P2-16 (`GcsAssetStore`) is **design-only** here — do not build it.

## 9. Open follow-ups (not this work)

- Form **805** + **5-choice Math** renderer/wire; a real **form picker**; **`GcsAssetStore`** + middleware signed-URL + bucket/IAM/seed for Cloud Run.
- ADR-0042 Proposed → **Accepted** at task S-F1; `docs/preact9secure/README.md` "Step 2 (not started)" → point at the converter.
- Housekeeping: the memory index is over its 15 KB budget — run the `memory-compaction` skill at some point. Memory pointer for this work: `exam-phase2-official-forms-sdd-status`.
