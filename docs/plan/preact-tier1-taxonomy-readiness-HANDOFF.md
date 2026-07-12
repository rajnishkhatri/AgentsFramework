# HANDOFF — Tier-1 taxonomy-readiness probe (implementation)

> **Read this file first, then the spec + plan.** This is the single manifest to hand a fresh
> coding-agent session. It is self-contained: it inlines the measured ground truth, the exact
> create/edit list, the ground-truth code anchors, the rules, and the landmines — so you can
> implement without the originating conversation. **You are implementing SDD Stage-6 (sdd-implement)
> for an already-Approved spec.** Do NOT re-open the design; the direction, thresholds, and scope are
> settled.

**Branch:** `feat/preact-parity-epic-E` (the 3 planning docs below are UNCOMMITTED on it).
**No ADR** — confirmed no ⚠️ Ask-first trigger (read-only `scripts/` tool, stdlib only).
**Deliverable:** one Python probe + one architecture test + one committed verdict JSON. **3 new files,
0 edits to shipped code.**

---

## 0. The three artifacts to read (in order)

| Doc | What it gives you |
|-----|-------------------|
| `docs/plan/preact-tier1-taxonomy-readiness.spec.md` | **Approved** spec — 9 EARS FRs (failure-first), data contracts, invariants, edge cases, test plan, DoD. The *what*. |
| `docs/plan/preact-tier1-taxonomy-readiness.plan.md` | Architecture (function list), touchpoints, **8 atomic tasks T1–T8** with red→green tests, FR→task→test matrix, Stage-4 analyze. The *how*. |
| `docs/plan/preact-tier1-misconception-taxonomy.brainstorm.md` | (context only) SDD Stage-1 — why this exists, the 6 directions, why D3 "measure-first" was chosen. Read if you need the *why*. |

**Execution order:** implement T1→T2→T3→T4→T6→T7→T8 (T5 parallels T3). Each task = write the test,
**watch it fail first**, then implement. Paste actual command output (repo rule: evidence, not "tests pass").

---

## 1. What you are building (one paragraph)

A read-only measurement probe `scripts/tier1_taxonomy_readiness.py` that answers: *is there enough
tagged, themeable misconception data for the deferred `/learn/skill` tier-1 "Your pattern · X"
aggregate callout to ever fire meaningfully?* It reports per-skill tag coverage, **candidate themes on
the already-controlled `standard_id` axis** (never manufactured from free text), and a **simulated
per-learner fire-rate**, then emits a machine-readable **verdict** (`build` / `defer`) against two
locked thresholds. It ships the *decision*, not the tier-1 feature. Mirror
`scripts/syllabus_coverage_report.py` (same read-only, stdlib-only, deterministic, verdict-JSON shape).

---

## 2. Ground truth — INLINED (measured 2026-07-12; do not re-derive, but a `make check` run re-verifies)

**The serving bank** `docs/plan/coach-item-bank-live.promoted.json` — a JSON array of 171 objects.
(Misnamed "coach"; it is the `ti-gen-*` **governed practice bank ADR-0021** that `/learn` serves, emitted
by `scripts/emit_test_item_bank.py` → `frontend/lib/adapters/engine/_test_item_bank.ts`.)

- **171 total items · 47 tagged** (non-null, non-empty `misconception`) **· all 47 tag strings DISTINCT · 0 exact clusters.** Tags are free-text prose.
- Every row has the same 17 keys. The ones you use: `id`, `skill_id`, `standard_id` (int), `misconception` (string|null), `difficulty`.
- Sample tagged row: `{"id":"ti-gen-9a237b9f8b5ba000","skill_id":"s-sent","standard_id":15,"difficulty":2,"misconception":"'However' feels like a conjunction, but it's an adverb …"}`

**The controlled axis** `docs/plan/act-english-syllabus.seed.json` — 32 rows `{standard_id, name, category, app_skill}`. This is the 32-standard ACT-English syllabus. `app_skill` maps each standard to a skill (`s-*`).

- **Per-skill standard count:** `s-gram:14, s-punc:5, s-sent:6, s-style:4, s-rhet:2` (MULTI-standard → clusterable) · **`s-org:1` (SINGLE-standard → EXCLUDED, see FR-3).**
- **Meaningful clusters (≥2 tagged items sharing a `standard_id`, multi-standard skills only): 14.** Of these, **4 have ≥3 items:** `(s-rhet, 2)`, `(s-rhet, 4)`, `(s-sent, 15)`, `(s-style, 5)`. Largest cluster = 3.

**The two locked thresholds (resolved at human gate — do NOT change):**
- `min_meaningful_clusters` = **≥1 skill with a `standard_id` cluster of ≥3 tagged items** → **PASSES today** (4 exist).
- `min_fire_rate` = **≥5%** of simulated learners fire tier-1 (under the all-missed-skills-due upper-bound model).
- **`build` iff BOTH clear; else `defer` + the failing reason(s).** Since cluster-gate passes today, the verdict is decided by the fire-rate simulation.

---

## 3. Files to CREATE (exhaustive — nothing else changes)

| # | Path | What |
|---|------|------|
| 1 | `scripts/tier1_taxonomy_readiness.py` | The probe. Pure helpers + thin `main()`. Function list is in the plan §A. |
| 2 | `tests/architecture/test_tier1_readiness_probe.py` | FR-1…FR-9 gates + verdict-drift lock. |
| 3 | `docs/plan/tier1-taxonomy-readiness.verdict.json` | The committed machine verdict (written by running the probe in T6). |

**Files to EDIT: NONE.** No DB, no wire, no `frontend/`, no `pyproject.toml`, no ADR.

---

## 4. Ground-truth code anchors (verified `file:line` — read these, they are your templates)

- **The read-only report template + honesty discipline** — `scripts/syllabus_coverage_report.py`:
  - `coverage_matrix()` (:36-44) — how to count only rows carrying the controlled key; `continue` past the rest.
  - `untagged_rows()` (:47-53) — collect rows lacking the key; NEVER count them.
  - `render_report()` (:66-97) — fixed-width matrix; foot line `UNTAGGED rows (never counted, FR-5)`.
  - `main()` (:100-124) — argparse `--corpus/--syllabus`, absent-file → `[]`.
- **The verdict-JSON-to-disk pattern** — `scripts/measure_l2l3_goaljudge.py:279` (`result["formal_gate"] = {"verdict":…, "gates":…}`) + `:355-358` (`OUT_JSON.write_text(json.dumps(result, indent=2) + "\n")`).
- **The architecture-test import + structure** — `tests/architecture/test_syllabus_coverage_ratchet.py:27` (`from scripts.syllabus_coverage_report import coverage_matrix, floor_violations`) + its two-guard shape (regression + monotonicity/drift). Mirror this: import your pure helpers, assert FRs, add a verdict-drift lock (committed verdict == fresh run).
- **The tier-1 firing condition to replicate** — `frontend/lib/translators/newest_due_miss.ts:35-58`. The shipped render join is `misses × skillStates.due_at × questions.misconception`, returns the *newest single* due miss's verbatim tag. **Tier-1 extends this: group a learner's due-tagged misses by cluster-key (`standard_id`) and fire when one cluster has ≥2.** Your `simulate_fire_rate` models this over synthetic learners.
- **Bank/syllabus shapes** — `frontend/lib/wire/engine_entities.ts`: `Attempt` (:224-234) has `question_id` + `correct` but **NO `skill_id`** (join via question); `SkillState.due_at` (:305) is per-skill; `misconception` on Question/TestItem (:76-77, :151-152) is `z.string().nullable()`.

---

## 5. Rules (repo invariants that gate merge)

1. **Read-only + deterministic + offline** (FR-9): zero writes except the verdict JSON; zero network/LLM; stdlib only (`json`, `argparse`, `pathlib`, seeded `random` or pure enumeration). Byte-identical output on repeat. Safe in `make check`.
2. **Cluster ONLY on `standard_id`** (FR-2): free-text word overlap must NEVER form a cluster. The audit proved naive normalization manufactures false themes (`s-gram` "where"×3 = 3 *different* misconceptions). `standard_id` is the pre-controlled axis; that is the only legitimate key.
3. **Exclude single-standard skills** (FR-3): `s-org` (1 standard) → its cluster is the whole-skill bucket, not a sub-theme; a "pattern in X · X" callout is tautological. Mark `not-meaningful`, exclude from the build gate.
4. **Candidate ≠ theme** (FR-4): label every cluster the probe surfaces as a human-review *candidate* ("is standard N a genuine misconception theme?"), never a confirmed theme. The probe surfaces; a human ratifies (this is the OQ-2 anti-manufacture discipline the whole initiative exists to honor).
5. **Untagged never counted** (FR-1): `misconception` null/empty → excluded from every count, reported separately at the foot.
6. **AP-6 — no fabricated 0.0**: a structural zero (no meaningful clusters exist) must be *labeled* as such, distinct from a measured-low fire-rate. Return/print `—` for absent, not a fake `0.0` that reads as "measured".
7. **Due-ness is an EXPLICIT param** (FR-7): the report states which due-model produced the number; default `all_due` = upper bound.
8. **Red→green + paste output**: every FR test seen to fail first; paste actual command output. `make check` green before done.

---

## 6. Landmines (each cost real investigation — avoid them)

- **FSRS is TypeScript-ONLY.** There is no Python scheduler and no `fsrs` in `pyproject.toml`. Do **NOT** re-implement FSRS due-logic in Python (divergence risk). The sim uses **synthetic learners + an explicit `due_model` param**, and reports the number as an approximation (FR-7). It does not run the real scheduler.
- **`scripts/build_memory_multisession_corpus.py` is the WRONG corpus.** It is the memory-recall stress subsystem (chat turns, fact recall) — zero skill/attempt/due/misconception concepts. Do not use it for the fire-rate sim. Generate synthetic learners in-probe.
- **`Attempt` has NO `skill_id`.** Join `miss → question_id → Question.skill_id/standard_id/misconception`. In the sim you model learners drawing over *tagged bank items* (which already carry skill+standard+tag), so the join is implicit — but don't assume an attempt row self-describes its skill.
- **DON'T name it "D3".** `scripts/syllabus_coverage_report.py` already self-names "D3" (ADR-0022), and there's a released Epic-D "D3" (session-length). The file is `scripts/tier1_taxonomy_readiness.py`; the concept is "tier-1 taxonomy-readiness probe."
- **Duplicate-named bank copies exist** (`Eng-coach-ui-design/coach-item-bank-live.promoted.json` has 0 tags; worktree copies). Pin the default `--corpus` to `docs/plan/coach-item-bank-live.promoted.json`.
- **`s-org` will tempt a false "5-item cluster."** All 5 of s-org's tagged items share standard 1 — but that's because s-org *has only one standard*. FR-3 exists precisely to exclude this; don't let it trip the build gate.

---

## 7. Definition of Done (from spec §9 / plan §E)

- [ ] `scripts/tier1_taxonomy_readiness.py` implements FR-1…FR-9 (read-only, stdlib, deterministic).
- [ ] `docs/plan/tier1-taxonomy-readiness.verdict.json` committed with today's verdict + the two thresholds.
- [ ] Every FR has a passing test **seen to fail first** (red→green); actual output pasted.
- [ ] `make check` green (lint + format-check + pyright + test) incl. `test_tier1_readiness_probe.py`.
- [ ] `tests/architecture/` green; no ADR (confirmed); decision + thresholds auditable in the verdict JSON.

## 8. Expected result (so you know when it's right)

On today's bank the cluster-gate passes (4 clusters of ≥3), so the verdict turns on the simulated
fire-rate. Because the largest cluster is only 3 items and firing needs a learner to miss ≥2 of *those
specific* items, the honest expected verdict is **`defer`** unless the sim clears 5% — that is the
*useful* answer ("keep authoring tagged items until a standard-cluster densifies, then build the D1
taxonomy"). Whatever the number, the test `test_verdict_*_on_todays_bank` **regression-locks the
measured reality** so future bank growth visibly flips it. Do not tune the sim to force a `build`;
report what the data says.
