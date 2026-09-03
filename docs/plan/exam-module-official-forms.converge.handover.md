---
type: plan
title: Handover — Exam official-forms Phase-4 close → sdd-converge
description: >-
  Stage 6 closed the two Phase-4 image-serve gaps (CV4-1/2/3). Next session runs
  /sdd-converge (Stages 9–10) in the feat/exam-official-forms worktree. Do not
  re-open deferred items. Do not commit unless the human asks.
tags: [plan, exam, handover, converge]
---

# Handover — Exam module phase 2, **Phase-4 close** → new session runs `/sdd-converge`

**Written:** 2026-09-03 · **From:** the Stage 6 implement session that closed CV4-1/2/3
**For:** a fresh `/sdd-converge` thread (zero prior context) — SDD Stages 9–10
**Change:** exam-module-official-forms (PT2 asset-served, server-graded)
**State:** Phase 0 + WT-A/B/C + SERIAL + VALIDATE **already shipped**. Prior converge
classified two **partial** image-serve gaps and spawned CV4-*. Stage 6 **implemented**
those tasks (uncommitted). Intended next skill: **`sdd-converge`**. Do **not** start
another implement pass unless Stage 9 finds a new `missing`/`partial`/`contradicts` gap.

Sibling handovers (stale on image-serve — this file supersedes them for converge):
`exam-module-official-forms.handover.md` (plan→implement),
`exam-module-official-forms.implement.handover.md` (implement→review; still says V-M FAIL).

---

## 0. How to invoke

```text
Worktree cwd:
  /Users/rajnishkhatri/Documents/AgentsFramework/agent/.worktrees/exam-official-forms

Handover (this file):
  docs/plan/exam-module-official-forms.converge.handover.md

Skill:
  .claude/skills/sdd-converge/SKILL.md
  (fallback: repo .claude/skills/sdd-converge/SKILL.md)

Binding:
  docs/skills/_sdd/binding.reference.toml
  check_gate = make check
  test_gate  = pytest tests/architecture/ -q
  adr_home   = docs/adr/
  gate_catalog = docs/adr/GATES.md
```

Paste this file into a new chat and run `/sdd-converge`. Work **only** in this worktree.
Do **not** commit unless the human asks. Do **not** open a PR unless asked.

---

## 1. Situation in three sentences

PT2 (`act-practice-test-2`) already ships asset-served + server-graded across all four
sections; keys stay off the client; ADR-0042 is **Accepted**. Phase-3 VALIDATE was green
on English / Reading / Science **data-path** and on Math keys/counts/scale; the only
open product class was **image serve** (V-M-B1 doubled `form_id`, V-M-B2 slashy `[key]`).
Stage 6 closed both: converter emits store-relative keys, VM encodes the key segment,
`math.md` / `tester.md` image-serve flipped **FAIL → PASS**. Converge classifies vs the
spec and runs Stage 10 — do **not** spawn Form 805 / picker / GCS / WorkOS / V-R tasks.

---

## 2. Read these, in order (≈10 min)

1. This file.
2. [sdd-converge skill](../../.claude/skills/sdd-converge/SKILL.md) — Stage 9 classify-then-spawn; Stage 10 six sign-off items. Never fix in place.
3. [exam-module-official-forms.tasks.md](exam-module-official-forms.tasks.md) **§ Phase 4 — Convergence** (CV4-1/2/3). Status block there is **stale** (still says not converged).
4. [exam-module-official-forms.spec.md](exam-module-official-forms.spec.md) FR-P2-1…19 — especially **FR-P2-11, FR-P2-13, FR-P2-14, FR-P2-15**.
5. [exam-module-official-forms.plan.md](exam-module-official-forms.plan.md) §6.4 validation table.
6. VALIDATE reports:
   - [english.md](exam-official-forms-validation/english.md) — V-E **PASS** (unchanged)
   - [reading.md](exam-official-forms-validation/reading.md) — V-R **PASS** (unchanged; observations **deferred**)
   - [science.md](exam-official-forms-validation/science.md) — V-S **PASS** data-path (unchanged this increment)
   - [math.md](exam-official-forms-validation/math.md) — V-M **PASS** (just flipped; B1/B2 **closed**)
   - [tester.md](exam-official-forms-validation/tester.md) — image-serve **PASS**; browser sit still WorkOS-blocked
7. ADR-0042 **Accepted** / ADR-0041 amended — do **not** rewrite.

---

## 3. Git state — do this FIRST

```text
/Users/rajnishkhatri/Documents/AgentsFramework/agent/.worktrees/exam-official-forms
```

| Item | Verified 2026-09-03 |
|---|---|
| **Branch** | `feat/exam-official-forms` @ `10819af` (`docs(exam): implement→review handover…`), tracking `origin/feat/exam-official-forms` |
| **Working tree** | Stage-6 CV4 product + validation edits **uncommitted (M)**; this handover **untracked**. Worktree-local `?? .venv`, `?? frontend/node_modules` — **do not commit those** |
| **PR** | **none** — do not open one unless the user asks |
| **©ACT — never commit** | `docs/preact9secure/**`, `frontend/lib/adapters/engine/exam_forms/_generated/**` (both gitignored) |

Modified (this increment, vs `10819af`):

| Path | Why |
|---|---|
| `frontend/scripts/convert_official_form.ts` | CV4-1: `storeRelativeKey`; fallback `questions/…`; passage keys `pages/…` |
| `frontend/scripts/convert_official_form.test.ts` | CV4-1 + CV4-3 |
| `frontend/lib/adapters/engine/assets/local_file_asset_store.test.ts` | PT2-shaped `questions/math-q02.png` |
| `frontend/components/exam/exam_item_vm.ts` | CV4-2: `encodeURIComponent(ref.key)` |
| `frontend/components/exam/exam_item_vm.test.ts` | encoded-segment assertion |
| `frontend/app/api/engine/asset/[formId]/[key]/route.test.ts` | VM URL → store key → 200 |
| `frontend/components/exam/ExamPassageBlock.test.tsx` | encoded fixture URL |
| `frontend/lib/adapters/engine/exam_forms/pt2_sit.integration.test.ts` | assert via `assetRefToUrl` |
| `docs/plan/exam-official-forms-validation/math.md` | verdict PASS |
| `docs/plan/exam-official-forms-validation/tester.md` | image-serve PASS |
| `docs/plan/exam-module-official-forms.tasks.md` | Phase-4 tasks (from prior Stage 9; still marked not converged) |

⚠️ Never `git reset --hard` / `git stash` in this tree.

---

## 4. What shipped this increment (Stage 6)

| ID | Gap | Result | EARS |
|---|---|---|---|
| **CV4-1** | Converter put `form_id/` in `AssetRef.key`; store joins `baseDir/form_id/key` → doubled path | `storeRelativeKey` strips leading `form_id/`. Fallback `questions/…`. Passage keys `pages/…`. Regenerated keys (implementer): 74 images → `questions/` 68, `pages/` 6, `act-practice-test-2/` **0** | V-M-B1 · **FR-P2-14** |
| **CV4-2** | Slashy key could not bind `[key]`; VM did not encode | Preferred one-liner: `encodeURIComponent(ref.key)` in `assetRefToUrl`. Route already `decodeURIComponent`s. **Not** catch-all `[...key]` | V-M-B2 · **FR-P2-11 / FR-P2-15** |
| **CV4-3** | Re-verify Math 34/34 + Science images; flip reports | Live count (implementer / `tester.md`): math-q **34/34**, sci-q **34/34**, sci-p **6/6**, encoded **34/34/6**, doubled **0**. `math.md` FAIL→**PASS**. `tester.md` image-serve **PASS** | **FR-P2-11 / FR-P2-13 / FR-P2-15 / FR-P2-19** |

G9 (implementer): no new `try/except` / `return None`. `storeRelativeKey` only strips a leading `form_id/`.

---

## 5. Prior converge status (do not re-open closed gaps)

**Already PASS before this increment** (Phase 0–3 + prior Stage 9):

| Area | Status |
|---|---|
| V-E English | **PASS** 50/50, 0 mismatches |
| V-R Reading | **PASS** 36/36, 0 mismatches |
| V-S Science data-path | **PASS** 40/40, 0 mismatches |
| Math keys / counts / scale / text-first | **PASS** (never the FAIL) |
| Key-safety / `ClientExamForm.strict()` / Test-01 client-bundled | **PASS** |
| ADR-0042 Accepted · ADR-0041 Option B for asset-served | **PASS** (do not rewrite) |
| Eval-capture (Stage 10 item 5) | **N/A** — no LLM seam |

**Was PARTIAL — now claimed PASS** (verify, do not spawn another CV4):

| Finding | Was | Now (on disk) |
|---|---|---|
| V-M-B1 doubled `form_id` | `partial` | **closed** — `math.md` §5, converter + store test |
| V-M-B2 slashy `[key]` | `partial` | **closed** — `encodeURIComponent` + route test |
| V-M rollup / V-T image-serve | FAIL / 0/34 store hits | **PASS** — `math.md` verdict PASS; `tester.md` image-serve PASS |

`tasks.md` Phase-4 header still says “Not converged” — that line is **pre-CV4**. Update it append-only if Stage 9 agrees the gaps are closed. Do not rewrite existing CV4 task rows.

---

## 6. Stage 10 sign-off checklist (current known status)

From the skill (six items; prior handover said “criterion 1 should now pass; still do 4/6”).

| # | Criterion | Known status |
|---|---|---|
| **1** | Every EARS criterion has a passing test; no `missing`/`partial`/`contradicts` remain | **Claimed pass** for the two product gaps (CV4-1/2/3 + flipped reports). Converge must still walk FR-P2-1…19 vs tests. Browser sit is **environment**, not a remaining product `partial`. |
| **2** | `make check` green **and** `pytest tests/architecture/ -q` green — paste real output | **Claimed green by implementer** (see §7). Re-run and paste. Do not treat the nested-worktree full-`pnpm vitest` ts-morph timeout as a product fail. |
| **3** | Every ADR trigger has a filed `docs/adr/` record + `index.md`/`log.md` | **Pass** — ADR-0042 Accepted, ADR-0041 amended. Do **not** rewrite. |
| **4** | Comprehension gates that fired (G1/G3/G4/G7/G8/G9 in `docs/adr/GATES.md`) answered **by the human in their own words** | **Still needed.** G1 for `FormAssetStore` is already in ADR-0042. **G9** applies to CV4 (`storeRelativeKey` prefix strip — implementer named it; human must still answer). |
| **5** | Record every LLM call via `eval_capture.record()` with `user_id`+`task_id` | **N/A** — no LLM seam in this change. |
| **6** | Blast-radius cleanup scoped to **this** diff — delete what this change added that is now dead | **Still needed.** Check whether any transitional key-normalisation / doubled-`form_id` branch is now unused. Scope = CV4 diff, not a repo-wide delete. |

Honest unknowns: no real-browser sit (WorkOS env absent — same as V-T, **not** a product bug). Authenticated asset GET / runner chrome / “content unavailable” vs broken `<img>` in UI = **unverified**.

---

## 7. Suggested verification (cwd = this worktree)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/.worktrees/exam-official-forms

# scoped (the suites this increment touched)
cd frontend && pnpm vitest run \
  scripts/convert_official_form \
  lib/adapters/engine/assets/local_file_asset_store \
  components/exam/exam_item_vm \
  components/exam/ExamPassageBlock.test.tsx \
  lib/adapters/engine/exam_forms/pt2_sit.integration.test.ts \
  'app/api/engine/asset'
# implementer: 7 files, 38 passed

cd .. && .venv/bin/python -m pytest tests/architecture/ -q
# implementer: 254 passed

# Stage 10 item 2 — paste output
make check
cd frontend && pnpm typecheck
```

Implementer evidence (do not treat as your paste — re-run):

- Scoped frontend: 7 files, 38 tests passed
- Architecture: 254 passed
- `pnpm typecheck` exit 0
- `make check` green after hygiene newline: **5372 passed, 55 skipped**
- Full `pnpm vitest run` hit the known **nested-worktree ts-morph timeout artifact** — not a product failure; scoped suites + `make check` are authoritative

Setup gotchas (same as prior handovers): symlink `frontend/node_modules` + root `.venv` if this is a fresh clone of the worktree; `make skills-pack` if architecture is red on the git-ignored zip; `docs/preact9secure/` lives in the **main checkout** (`EXAM_ASSET_DIR` / converter `--src`).

---

## 8. Out of scope (do **not** spawn Stage 9 fix tasks)

These are deferred / already decided. Spec does not require them in this change:

- Form **805** + 5-choice Math
- A real **form picker**
- **`GcsAssetStore`** + middleware signed-URL (FR-P2-16 **design-only**)
- **V-R observations** (Reading line-numbers; dual-passage PDF headings; silk table as text) — product call, not a §6.4 mismatch
- Rewriting **ADR-0042** / **ADR-0041**
- **WorkOS 500s** on local `:3010` — environment, not a product defect
- Hand-edits of `_generated/` or `docs/preact9secure/` (©ACT)

---

## 9. Review status (Stage 7)

A deterministic review of the **pre-CV4** tree was recorded in `tasks.md` Phase-4 (approve, 0 findings — reviewer cannot see runtime path bugs). **This CV4 increment has not been code-reviewed in a fresh thread.** Converge is not the reviewer; note the gap. If the human wants Stage 7 first, point them at `.claude/skills/code-review/SKILL.md` over this worktree vs `origin/main` (or vs `HEAD` for the uncommitted CV4 diff). Do **not** pretend review of CV4 happened.

---

## 10. Hard rules

- Classify, then spawn append-only `## Phase N — Convergence` tasks. **Never fix in place.**
- Do not invent remaining work. If Stage 9 finds no `missing`/`partial`/`contradicts`, do not manufacture CV5 tasks for deferred items in §8.
- Never commit ©ACT (`docs/preact9secure/**`, `exam_forms/_generated/**`).
- Do not widen `lib/translators/quiz_item_vm.ts`.
- `finishExamSection` stays `"fine"`; only `getExamFormKeys` is `"server-only"`.
- Test-01 stays client-bundled (ADR-0041 exemption).
- **Do not commit** unless the human asks. No PR unless asked.

**Bounded loop:** this is the re-entry after iteration-1 implement. If new gaps appear, append Phase 5 tasks and stop — do not thrash.
