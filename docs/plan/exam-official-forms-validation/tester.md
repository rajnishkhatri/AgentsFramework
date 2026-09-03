# V-T — PT2 full-run tester sit

**Task:** Phase 3 VALIDATE V-T (`docs/plan/exam-module-official-forms.tasks.md`)
**Plan / spec:** sit all four sections · DoD = screens + run read-back · FR-P2-5/6/11/13/17/18/19
**Form:** `act-practice-test-2` (Enhanced ACT) · `delivery: asset-served`
**Base:** `.worktrees/exam-official-forms` on `feat/exam-official-forms` @ `8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74`
**Date:** 2026-09-03
**Verdict vs V-T criteria: FAIL** (browser sit blocked) · **substitute run PASS**

This file is report-only. No exam code or `_generated/` content was edited. Findings route to sdd-converge, never to hand-edits of generated artifacts.

©ACT stem, choice, and passage text is **not** reproduced here.

---

## V-T pass/fail criteria

| Criterion | Result |
|---|---|
| Tester sits a full PT2 run locally (all four sections) | **substitute only** — see §1 |
| DoD screens of a completed sit | **no** — `/learn/exam` on the worktree Next server is a WorkOS runtime error overlay |
| DoD run read-back (scores after finish) | **yes** — §3 |
| Test-01 still works | **yes** — listed beside PT2; client-bundled finish submitted with `raw_scored_total > 0`; posture `"client"` |
| Image serve (Math / Science) | **FAIL as expected** — V-M-B1 + V-M-B2 confirmed at sit time, including Science |

---

## 1. What was sat

| Path | Outcome |
|---|---|
| Preferred: real browser → worktree Next (`:3010`) + `HttpEngineDb` (`NEXT_PUBLIC_FF_DURABLE_ENGINE=1`) + `EXAM_ASSET_DIR` → main checkout `docs/preact9secure/json` + `E2E_BYPASS_AUTH=1` | Server process started and compiled. Every page and `/api/engine/*` request returned **500**. Middleware `authkit()` throws: WorkOS needs an API key / clientId. The worktree does not load the main checkout’s env files; those were not copied or read. Screenshot: Next.js runtime overlay on `/learn/exam` (grey page, “WorkOS requires either an API key or a clientId”). |
| Playwright `e2e/learn/exam.spec.ts` against `:3010` | Not run. Same WorkOS wall. Starting Playwright’s own `webServer` with `E2E_BYPASS_AUTH=1` would bind **:3000** and clobber the dirty main-checkout Next already listening there. |
| Substitute: `InMemoryEngineDb` + `finishExamSectionServer` + generated PT2 artifacts (same seam as `pt2_sit.integration.test.ts`, extended to all four sections) | **Sat.** Official keys on every item. Server grade ignored a planted client score of 99. Test-01 finish still uses the client-bundled repo path. |

`InMemoryEngineDb` does **not** import `generated_official_form.ts` (only `drizzle_engine_db.ts` does). A default browser bag without the durable flag would not list PT2 even if WorkOS were present. A real UI sit requires HttpEngineDb + a working BFF.

### Could not verify (browser)

- Clicking Start / Begin / Next / Submit on the live runner
- Visible “content unavailable” placeholder vs a broken `<img>`
- Review chrome (`exam-review-score-summary` text, unscored badges, post-grade reveal)
- Home status after each section (Submitted / composite display)
- Auth’d asset GET (401 vs 404 vs PNG). Unauth curls to `:3010` were 500 HTML (WorkOS), not a clean 401/404

---

## 2. Image-serve evidence (V-M-B1 / V-M-B2)

`LocalFileAssetStore(EXAM_ASSET_DIR)` with `EXAM_ASSET_DIR` = main checkout `docs/preact9secure/json`. `toExamItemVM` URLs and store `has()` on every image `AssetRef`.

| Check | Math | Science | English / Reading |
|---|---|---|---|
| Image-necessary items | **34** | **34** | **0** |
| Store `has(ref)` hits | **0 / 34** | **0 / 34** | n/a |
| Key starts with `act-practice-test-2/` (doubled `form_id`) | **34 / 34** | **34 / 34** | n/a |
| Key contains `/` (slashy; `[key]` is one segment) | **34 / 34** | **34 / 34** | n/a |

Sample (Math Q2; Science keys are the same shape):

| Field | Value |
|---|---|
| `AssetRef.key` | `act-practice-test-2/questions/math-q02.png` |
| VM `imageUrl` | `/api/engine/asset/act-practice-test-2/act-practice-test-2/questions/math-q02.png` |
| Store looks for | `…/json/act-practice-test-2/act-practice-test-2/questions/math-q02.png` |
| File on disk | `…/json/act-practice-test-2/questions/math-q02.png` (exists; V-M / V-S data-path) |

**V-M-B1** confirmed: `resolveKey` is `baseDir/form_id/key` while the converter copied a key that already includes `form_id/`.

**V-M-B2** confirmed: VM does not encode the key; the live URL has extra path segments and cannot bind `app/api/engine/asset/[formId]/[key]`.

Science data-path (V-S) was PASS (PNG on disk at `json/<AssetRef.key>`). Sit-time **serve** fails for the same two reasons. Not a new root cause — same class on Science.

Live HTTP GETs of those URLs on `:3010` returned **500** HTML (WorkOS), so they do not add a third failure mode.

---

## 3. Run read-back (scripted official keys)

`finishExamSectionServer` + `ExactLetterGrader`. Client-supplied `{ raw_correct: 99, raw_scored_total: 99, scale_score: 1 }` was ignored on every section (FR-P2-6).

| Section | items | imaged | store hits | raw_correct | raw_scored_total | scale | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| English | 50 | 0 | 0 | 40 | 40 | 36 | field-test excluded; matches V-E |
| Math | 45 | 34 | 0 | 41 | 41 | 36 | field-test excluded; matches V-M |
| Reading | 36 | 0 | 0 | 27 | 27 | 36 | field-test excluded; matches V-R |
| Science | 40 | 34 | 0 | 34 | 34 | 36 | not in composite; matches V-S |

`examComposite` on the finished attempts = **36** (mean of E/M/R scales 36/36/36). Science 36 is reported separately and is not in the mean (FR-P2-17).

`run.composite` stayed `null` on this substitute because the script called `finishExamSectionServer` directly. The repo `finishSection` path is what writes `setExamRunComposite`. On HttpEngineDb the repo still runs that write after the BFF returns — **not** a new product gap.

`HttpEngineDb.getExamFormKeys` still throws server-only without fetching (FR-P2-7).

Listed forms: `test01-english`, `act-practice-test-2`. Posture: PT2 `"server"`, Test-01 `"client"`. Client PT2 payload has no `answer_letter`.

Existing `pt2_sit.integration.test.ts` (S-I3) also green: English server-grade, Math image URL mapping, Science passage present, keys not client-fetchable.

Test-01: `exam_home`, `exam_key_posture`, and a client-bundled `finishSection` all green.

---

## 4. Sibling section reports

| Lane | File | Verdict |
|---|---|---|
| V-E | [english.md](english.md) | PASS |
| V-M | [math.md](math.md) | FAIL (V-M-B1, V-M-B2) |
| V-R | [reading.md](reading.md) | PASS |
| V-S | [science.md](science.md) | PASS (data-path; serve fails at sit — §2) |

---

## 5. Converge findings (do not fix here)

| ID | Gap | Class | New? |
|---|---|---|---|
| **V-M-B1** | `AssetRef.key` already contains `form_id/`; `LocalFileAssetStore` joins `baseDir/form_id/key` → 0/34 Math and 0/34 Science store hits | `partial` (FR-P2-11/14) | no — sit confirmation; Science serve now in scope |
| **V-M-B2** | Slashy key + `/api/engine/asset/${form_id}/${key}` vs `[formId]/[key]` | `partial` (FR-P2-11/15) | no — sit confirmation |
| WorkOS / env in worktree | Durable Next + HttpEngineDb UI sit could not start | environment | **not** a product finding |

No new product findings beyond V-M-B1/B2. Do not hand-edit `_generated/`.
