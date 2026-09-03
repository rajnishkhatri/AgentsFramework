---
type: plan
title: Handover — Exam official-forms implementation → code-review
description: >-
  SDD Stage 6 implement is done on feat/exam-official-forms. Next session runs
  the unified code-review skill, then sdd-converge for V-M-B1/B2. Do not review
  the dirty main checkout.
tags: [plan, exam, handover]
---

# Handover — Exam module phase 2 (official forms) → new session runs `/code-review`

**Written:** 2026-09-03 · **From:** the SDD Stage 6 implement + Phase 3 VALIDATE session
**For:** a fresh code-review session (zero prior context) over the **implementation** on
`feat/exam-official-forms`
**State:** Phase 0 + WT-A/B/C + SERIAL **shipped and merged to the feature branch**; VALIDATE
**landed** (V-E/R/S PASS, V-M FAIL on image serve, V-T FAIL browser / PASS substitute). Next
gate is **code-review**, then **sdd-converge** for V-M-B1/B2. **No PR** unless the user asks.

Pairs with the planning handover ([exam-module-official-forms.handover.md](exam-module-official-forms.handover.md))
that sent implementers into Stage 6. This file is the **implement → review** sibling.

---

## 1. Situation in three sentences

PT2 (`act-practice-test-2`, Enhanced ACT) now loads as an **asset-served, server-graded**
form across all four sections when gitignored `_generated/` artifacts exist: keys stay off
the client, Test-01 stays client-bundled, and ADR-0042 is **Accepted**. Section data-path
validation is green for English / Reading / Science; Math keys/counts/scale are clean but
**image serve is broken** (V-M-B1 doubled `form_id`, V-M-B2 slashy key vs `[key]` route) —
V-T confirmed the same class on Math **and** Science at sit time. A real browser sit was
blocked by WorkOS env in the worktree (not a product bug); the substitute server-grade run
PASSed. Review the feature-branch worktree, then route image findings to **sdd-converge**.

---

## 2. Read these, in this order (≈20 min)

1. This file — git state, what shipped, VALIDATE verdicts, how to invoke review.
2. [exam-module-official-forms.spec.md](exam-module-official-forms.spec.md) — FR-P2-1…19 (EARS).
3. [exam-module-official-forms.plan.md](exam-module-official-forms.plan.md) — lanes + validation §6.4.
4. [ADR-0042](../adr/0042-exam-official-forms-asset-served-server-graded.md) — **Accepted**; do
   **not** re-litigate. Fires [ADR-0041](../adr/0041-exam-answer-key-posture.md) Option B for
   asset-served forms.
5. VALIDATE reports (already committed at `128ec69`):
   - [english.md](exam-official-forms-validation/english.md) — V-E **PASS** 50/50, 0 mismatches
   - [reading.md](exam-official-forms-validation/reading.md) — V-R **PASS** 36/36, 0 mismatches
   - [science.md](exam-official-forms-validation/science.md) — V-S **PASS** 40/40, 0 mismatches (data-path)
   - [math.md](exam-official-forms-validation/math.md) — V-M **FAIL** — V-M-B1 / V-M-B2
   - [tester.md](exam-official-forms-validation/tester.md) — V-T **FAIL** browser sit · **PASS** substitute
6. Code-review skill: `.claude/skills/code-review/SKILL.md` (invoke **and** interpret
   `review.json`; vacuous `approve` + empty `files_reviewed` is not a pass).

---

## 3. Git state — do this FIRST

Work **only** in this worktree (or a fresh worktree of the same branch):

```text
/Users/rajnishkhatri/Documents/AgentsFramework/agent/.worktrees/exam-official-forms
```

| Item | Verified 2026-09-03 |
|---|---|
| **Branch** | `feat/exam-official-forms` tracking `origin/feat/exam-official-forms` |
| **HEAD (before this handover commit)** | `128ec696c7abc105ab57462f08d5c522fd7a26b6` — `docs(exam): PT2 Phase 3 validation reports (V-E/M/R/S/T)` |
| **Working tree** | clean of product/docs changes; worktree-local `?? .venv` and `?? frontend/node_modules` only — **do not commit** |
| **PR** | **none** — do not open one unless the user asks |
| **Main checkout** | `fix/exam-ui-polish` is **dirty with unrelated uncommitted work**. Never review or edit that tree. Never `git reset --hard` / `git stash`. |

**`origin/main..HEAD` (newest first), verified:**

| SHA | Subject |
|---|---|
| `128ec69` (`128ec696c7abc105ab57462f08d5c522fd7a26b6`) | `docs(exam): PT2 Phase 3 validation reports (V-E/M/R/S/T)` — five reports only; **pushed, no PR** |
| `8269a1b` (`8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74`) | `feat(exam): load PT2 server-side when generated artifacts exist` — SERIAL |
| `8a484c5` (`8a484c5e058c09bda519491e6635e3714299637a`) | `merge(exam): WT-B server B-1…B-8` |
| `7c2d0d7` (`7c2d0d78bf0bc69b93de431a69a454cd6a66cc8b`) | `feat(exam): server-grade asset-served forms; keys stay off the client` — lane `feat/exam-wt-server` |
| `f284744` (`f284744e8c54ec939b53494d4f9f8e87fbe6e2e3`) | `merge(exam): WT-C render C-1…C-5` |
| `2e673af` (`2e673af6d900edbbcf7eade80378e7d4d3da83c9`) | `merge(exam): WT-A converter A-1…A-3` |
| `77e35a1` (`77e35a198ea61579e9849a9e3ad2ba2af3c68544`) | `feat(exam): render official forms text-first with exam-local item VM` — lane `feat/exam-wt-render` |
| `f7507d4` (`f7507d40f183cfcc3d6dd08f266bdfeca7046c0d`) | `feat(exam): convert official-form JSON to key-safe client artifacts` — lane `feat/exam-wt-converter` |
| `9af7869` (`9af78691e8453319b3bbfe1257bbb12e565ca851`) | `feat(exam): land Phase 0 official-forms BASE (wire, port, guard, fixture)` |

**On `origin/main` (parentage, not this branch's tip):** `b157008` (`b157008a6b0232704733348824317fd927bb3df1`) — Merge PR **#187** (`fix/exam-ui-polish`) — docs + ADR-0042 onto main.

Lane branch tips (same SHAs as the feat commits above): `feat/exam-wt-converter` @ `f7507d4` · `feat/exam-wt-server` @ `7c2d0d78` · `feat/exam-wt-render` @ `77e35a19`.

**Do not commit** `docs/preact9secure/` or `frontend/lib/adapters/engine/exam_forms/_generated/` (©ACT).

---

## 4. Decisions already made — do NOT re-litigate

| Decision | Value | Where |
|---|---|---|
| Source of truth | verified private official-form JSON (`docs/preact9secure/json/`), **not** authored Test-01 | ADR-0042 **Accepted** |
| First form | **PT2** `act-practice-test-2` (Enhanced ACT; all 4-choice) | ADR-0042, spec §2.1 |
| Delivery | `FormAssetStore` + `LocalFileAssetStore` now; `GcsAssetStore` is **design-only** (FR-P2-16 — not built) | ADR-0042 |
| Grading | server-side for asset-served; keys never client-served. Test-01 stays client-bundled | ADR-0041 Option B, FR-P2-5..9 |
| `finishExamSection` | stays `"fine"` (client triggers). Only `getExamFormKeys` is `"server-only"` | plan / WT-B |
| Render VM | exam-local `exam_item_vm.ts` — **do not** widen `quiz_item_vm.ts` | WT-C / isolation guard |
| Image rule | official PNG only where `text_fidelity ∈ {math-notation, low}` or passage is a figure | `decisions.md`, `needsImage` |
| Review vs converge | review **does not silently fix** V-M-B1/B2. After review → **sdd-converge** | this file |

---

## 5. Session-verified facts you can rely on (don't redo)

### What shipped (implement, not just docs)

- **Phase 0 B0-1…B0-8** (`9af7869`): wire (`AssetRef`, `image`, `ExamPassage`, `delivery`, `ClientExamForm.strict()`), `FormAssetStore` port, `needsImage`, `examKeyPosture`, hardened `test_exam_no_client_served_keys` (retired `db-served` heuristic; planted fixtures), fake fixture + FakeAssetStore, asset-served registry, `.gitignore` `_generated/` + `docs/preact9secure/`.
- **WT-A A-1…A-3** (`f7507d4` / merge `2e673af`): `frontend/scripts/convert_official_form.ts` — integrity fail-closed, PT2 parse, PyMuPDF key match vs PDF scoring page, client emit keyless + `convert:official`.
- **WT-B B-1…B-8** (`7c2d0d78` / merge `8a484c5`): `LocalFileAssetStore`, `getExamFormForClient` + `getExamFormKeys` (server-only, client 404), 41→43 methods / 5→6 server-only, `EXAM_LEARNER_ARG`, `exam_server_grade`, finishSection skip local scoring for asset-served, asset route, composition_engine `EXAM_ASSET_DIR` only, review reveal after finish.
- **WT-C C-1…C-5** (`77e35a19` / merge `f284744`): exam-local `exam_item_vm.ts` (NOT `quiz_item_vm.ts`), `ExamPassageBlock`, runner images, review unscored/post-grade.
- **SERIAL S-I1…S-I4, S-F1** (`8269a1b`): real PT2 convert (artifacts gitignored, **not** committed), `listClientForms` / home loads PT2 when `_generated` exists, sit tests, ADR-0042 Proposed → **Accepted**.

### VALIDATE (reports at `128ec69`)

| Lane | File | Verdict |
|---|---|---|
| V-E | [english.md](exam-official-forms-validation/english.md) | **PASS** 50/50, 0 mismatches |
| V-R | [reading.md](exam-official-forms-validation/reading.md) | **PASS** 36/36, 0 mismatches. Observations (not mismatches): line numbers dropped; dual-passage headings live in the PDF, not JSON `text` |
| V-S | [science.md](exam-official-forms-validation/science.md) | **PASS** 40/40, 0 mismatches (data-path; PNGs on disk). Sit-time **serve** fails for the same V-M-B1/B2 class |
| V-M | [math.md](exam-official-forms-validation/math.md) | **FAIL**. Keys/counts/scale clean. **V-M-B1:** store doubles `form_id` (`resolveKey` = `baseDir/form_id/key` while converter key already includes `form_id/`). **V-M-B2:** slashy key vs `[formId]/[key]` (one segment). Image items not sit-ready |
| V-T | [tester.md](exam-official-forms-validation/tester.md) | **FAIL** for a browser sit · **PASS** for the substitute run. **Done — read tester.md.** Do **not** treat V-T as missing |

### V-T (landed — do not re-sit)

- Next on `:3010` started; every `/learn/exam` and `/api/engine/*` returned **500**. Middleware `authkit()` wants WorkOS creds the worktree does not load. **Not a product bug.** Do not file it as a review defect.
- Playwright vs `:3010` was not run (same WorkOS wall). Starting Playwright's `webServer` would bind **:3000** and clobber the dirty main-checkout Next already there.
- Substitute: `InMemoryEngineDb` + `finishExamSectionServer` over generated PT2, all four sections, official keys. Client-supplied score **99 ignored** (FR-P2-6).
- Scores: Eng 40/40→36 · Math 41/41→36 · Read 27/27→36 · Sci 34/34→36 (Science **not** in composite). `examComposite` = **36**. Test-01 still client-bundled.
- Image-serve: Math **0/34** and Science **0/34** store hits. Confirms V-M-B1 and V-M-B2 at sit time (Science serve now in scope; same root cause, not a new finding).
- Could **not** verify in UI: Start/Begin/Next/Submit, content-unavailable placeholder, review chrome, home status, auth'd asset GET.
- **No new product findings** beyond V-M-B1/B2.

### Known test-env gotcha (not a product fail)

Full `pnpm vitest run` can **10s-timeout** architecture ts-morph tests when many `Project()`s run in parallel in a **nested worktree**. Scoped exam/engine suites and `make check` were green. If architecture tests are red on a missing skills-pack zip, run `make skills-pack` once (git-ignored artifact).

---

## 6. Exact next steps (the review session's runbook)

0. **Work in** `.worktrees/exam-official-forms` (or `git worktree add … feat/exam-official-forms`). Symlink `frontend/node_modules` and root `.venv` to the main checkout if this is a fresh worktree. `make skills-pack` if `pytest tests/architecture/` is red on the ignored zip.
1. Invoke the repo **`/code-review`** skill (`.claude/skills/code-review/SKILL.md`) over **branch changes vs `main`**. This branch is exam-only vs `origin/main`, so the default PR-style command is the right one:

   ```bash
   .venv/bin/python -m meta.code_reviewer --from-git-diff \
       --git-base 'origin/main...HEAD' --prompt-version v3 --output review.json
   ```

   `make review` is the same (`BASE=origin/main...HEAD` default). Always `--from-git-diff` (ADR.1 needs `git diff --diff-filter=A`). Deterministic is the default; add `--llm` only if the user asks (write `review_llm.json`, do not overwrite `review.json`).
2. **Scope:** exam official-forms implementation only — frontend exam/engine/converter, ADR-0042, these plan files. **Not** `.arch/`, presentations, `arch-lifecycle-bundle/`, or the dirty main-checkout tree.
3. **Sanity-check `review.json` before trusting it** (skill Step 1.5): if `files_reviewed == []`, that is a **vacuous** approve, not a pass. Confirm the file list matches `git diff --name-only origin/main...HEAD`.
4. **Interpret** per the skill template: verdict + three-way CI gate (approve / request_changes non-blocking / reject blocks) + criticals with routed `AGENTS.md`/`REVIEW.md` + gaps + fix-vs-justify. Do not dump raw JSON.
5. **Known converge items — still review the design, do not "fix while reviewing"** unless the user asks:
   - V-M-B1 / V-M-B2 (store `form_id` join + slashy `[key]` route; converter key shape). Review `LocalFileAssetStore`, `convert_official_form.ts`, `exam_item_vm` URL builder, and `app/api/engine/asset/[formId]/[key]`.
   - WorkOS 500s on `:3010` are **environment**. Not a product defect.
6. **After review → `sdd-converge`** for V-M-B1/B2 (and any *new* review findings). Append-only fix tasks; do not hand-edit `_generated/`.

---

## 7. Hard rules / gotchas for the reviewer (and anyone continuing)

- **Never** commit ©ACT: `docs/preact9secure/`, `exam_forms/_generated/`.
- **Do not** widen `lib/translators/quiz_item_vm.ts` — exam-local `exam_item_vm.ts` only.
- `finishExamSection` is `"fine"`; only `getExamFormKeys` is `"server-only"`.
- Browser composition root has **no** asset store. Env reads only in `lib/composition_engine.ts` (`EXAM_ASSET_DIR`).
- Test-01 must stay **client-bundled** (recorded exemption).
- FR-P2-16 `GcsAssetStore` is **design-only** — not built; do not demand it in review.
- Review **this feature-branch worktree**, not the dirty main checkout.
- Do **not** re-litigate ADR-0042 decisions.
- Do **not** treat WorkOS / missing worktree env as a product defect.
- Image bugs are **known** converge items — review the store/route/converter design; do not silently patch them in the review session.
- Do **not** open a PR unless the user already asked.

---

## 8. Open follow-ups (not this review)

- **sdd-converge** for V-M-B1 / V-M-B2 (Math + Science image serve). Suggested directions are already in [math.md](exam-official-forms-validation/math.md) §5 — converter store-relative keys **or** store `baseDir/key` when key starts with `form_id/`; catch-all `[...key]` **or** encode/decode in the VM + route.
- V-R observations (line numbers; dual-passage PDF headings) — converge only if product wants them; not §6.4 mismatches.
- A real **authenticated** browser sit (WorkOS creds or `E2E_BYPASS_AUTH` without clobbering :3000) after image serve is fixed.
- Form **805** + **5-choice Math** renderer/wire; a real **form picker**; **`GcsAssetStore`** + middleware signed-URL (FR-P2-16).
- Housekeeping: memory index over budget — `memory-compaction` when convenient.
