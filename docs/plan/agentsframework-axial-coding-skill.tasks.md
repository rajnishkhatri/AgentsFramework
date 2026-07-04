# Tasks — `agentsframework-axial-coding` skill

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Derives from:** [spec](agentsframework-axial-coding-skill.spec.md) (accepted) +
[plan](agentsframework-axial-coding-skill.plan.md) (accepted).

---

## A. Measurability checklist ("unit tests for English")

Every FR checked: is the acceptance criterion measurable, and by what?

| FR | Measurable? | By what |
|----|----|----|
| FR-1 refuse emit if unpartitioned | ✅ | checker exit code (= FR-13) |
| FR-2 reject un-testable category | ⚠️ prose | L4 walkthrough — a human judges "capability limitations"; not machine-decidable, correctly L4 |
| FR-3 confound = validity precondition | ✅ | matrix denominator excludes `environment-confound` rows |
| FR-4 5–6 testable categories (not a gate) | ✅ | checker: each category has member codes + non-empty `binary_check` |
| FR-4a gradient → dimension + boundary checks | ✅ | checker: gradient category has `dimension` + ≥2 boundary checks |
| FR-5 first-failure primary code | ⚠️ prose | L4 walkthrough — "first deviation" is a human read of the trajectory |
| FR-6 emit rubric + judge-case candidates | ⚠️ prose | L4 walkthrough — emit is judgment, no script |
| FR-7 input contract | ✅ | contract validator rejects missing `trace_id`/`open_codes` |
| FR-8 minimal-pair detector | ✅ | same normalized prompt + divergent codes → surfaced |
| FR-9 code×category matrix | ✅ | join counts assert-equal on a fixture |
| FR-9a normalized-exact grouping | ✅ | normalization unit test (case/space/punct) |
| FR-12 red-team assist only | ⚠️ prose | L4 walkthrough — assist proposes name → rejected |
| FR-13 axis/category checker + straddle | ✅ | checker exit code; straddle by-cause rule |
| FR-14 axial-only scope | ✅ | absence check — no selective script shipped |
| FR-15 packaging | ✅ | mirror-parity test + okf_lint exit 0 |

**Flagged back to spec:** none require a spec change. The four ⚠️ (FR-2, 5, 6,
12) are *correctly* prose/L4 — they encode human judgment that a Python assert
would only fake. This is the honest L1/L4 split, not a coverage gap.

---

## B. Atomic tasks (file-level, dependency-marked, 1:1 to FRs)

Legend: **[dep: …]** blocker · **[P]** parallelizable with siblings · each task
names its pass/fail = the mapped test.

### T0 — Spike: bundle-script test import  [P]
- **Do:** confirm how `tests/skills/axial_coding/` imports bundle scripts
  (`docs/skills/.../scripts/*.py`) not on the `scripts.` path — importlib by
  file path vs a thin repo re-export.
- **Files:** throwaway probe; decision recorded in the plan §2 caveat.
- **Pass/fail:** a bundle script is importable + callable from a pytest under
  `tests/skills/` and collected by `make check`. Resolves before T3–T5 tests.

### T1 — Extend inventory script: +axis +category columns  [dep: none]
- **Do:** add `axis` + `category` to `GOALJUDGE_COLUMNS` (blank, human-filled),
  keep parity note; no behavior change to first-seen logic.
- **Files:** `scripts/build_coach_open_code_inventory.py`;
  `tests/scripts/test_build_coach_open_code_inventory.py` (extend).
- **Pass/fail (FR-13 partial):** `test_inventory_has_axis_and_category_columns`
  — CSV header contains both, cells blank. Red first (columns absent).

### T2 — Define the categories-CSV contract  [dep: T1]
- **Do:** specify `<component>_categories.csv` columns
  (`category,axis,polarity,binary_check,dimension`) in
  `references/input-contract.md`; a sample categories.csv + inventory.csv fixture
  pair under the test dir.
- **Files:** `docs/skills/agentsframework-axial-coding/references/input-contract.md`;
  test fixtures.
- **Pass/fail:** fixtures parse; contract doc names every column + the straddle
  tie-break rule (by cause, consequence→memo).

### T3 — `axial_checker.py` (the emit gate) — TDD, failure paths first  [dep: T0, T2]
- **Do:** implement the checker: valid `axis` per code; `category` per clustered
  code; non-empty `binary_check` per category; axis-uniform members; gradient →
  `dimension` + ≥2 boundary checks. Non-zero exit + names offender.
- **Files:** `docs/skills/agentsframework-axial-coding/scripts/axial_checker.py`;
  `tests/skills/axial_coding/test_checker.py`.
- **Pass/fail (FR-1, FR-4, FR-4a, FR-13):** RED FIRST — `test_missing_axis_fails`,
  `test_missing_category_fails`, `test_category_without_binary_check_fails`,
  `test_gradient_records_dimension_and_boundary_checks`,
  `test_straddle_assigned_by_cause`. Then green.

### T4 — `axial_matrix.py` — TDD  [dep: T0, T2] [P with T5]
- **Do:** join inventory(code→category) ⋈ categories(category→axis); code×category
  counts, per-mode where present; **exclude `environment-confound` from
  agent-behavior denominators**.
- **Files:** `docs/skills/agentsframework-axial-coding/scripts/axial_matrix.py`;
  `tests/skills/axial_coding/test_matrix.py`.
- **Pass/fail (FR-3, FR-9):** `test_confound_excluded_from_denominator` (red
  first), `test_code_x_category_counts_via_join`.

### T5 — `axial_minimal_pairs.py` — TDD  [dep: T0] [P with T4]
- **Do:** group by normalized-exact `prompt`; surface `open_codes` divergence;
  axis-blind v1 with the noise-mode note in output; graceful degrade when no
  `final_answer`.
- **Files:** `docs/skills/agentsframework-axial-coding/scripts/axial_minimal_pairs.py`;
  `tests/skills/axial_coding/test_minimal_pairs.py`.
- **Pass/fail (FR-7, FR-8, FR-9a):** `test_rejects_row_missing_trace_id_or_codes`,
  `test_same_prompt_divergent_codes_surfaced`, `test_prompt_normalization`.

### T6 — `SKILL.md` + references (the runbook)  [dep: T3, T4, T5]
- **Do:** write SKILL.md (frontmatter: `name`, `type: skill`, Use-whenever/
  Do-NOT-use description, `paths:`) + the 6-move discipline, the partition gate,
  the CSV edit surface, **emit-as-prose** step, pointers to handbook Stage 2 +
  open-coding. `references/exemplars.md`. Mirror open-coding structure, ≤~300 ln.
- **Files:** `docs/skills/agentsframework-axial-coding/SKILL.md`, `references/*`.
- **Pass/fail (FR-2, FR-5, FR-6, FR-12, FR-14):** the **L4 walkthrough** over a
  20-row `coded.jsonl` slice runs and each prose gate catches its seeded
  violation; SKILL.md scopes to axial only (no selective automation).

### T7 — Package: sync + OKF + index/log  [dep: T6]
- **Do:** `docs/skills/index.md` + `log.md` entry (newest-first); run
  `make skills-sync`; `scripts/okf_lint.py`.
- **Files:** `docs/skills/index.md`, `docs/skills/log.md`, generated mirrors.
- **Pass/fail (FR-15):** `pytest tests/architecture/test_skills_mirror_parity.py`
  green; `python scripts/okf_lint.py` exit 0.

### T8 — Green gate  [dep: T1–T7]
- **Do:** full `make check` + architecture suite; L4 walkthrough evidence
  captured (checker blocks, matrix excludes confound, pair surfaces known pair).
- **Pass/fail:** `make check` green; actual command output pasted (not
  summarized) per AGENTS.md.

---

## C. Parallelization & critical path

- **Critical path:** T0 → T2 → T3 → T6 → T7 → T8.
- **Parallel:** T1 ∥ T0; T4 ∥ T5 (both need T0+T2/T0).
- **Contracts-first discipline:** T1+T2 define the two join artifacts before any
  consumer (T3/T4) is written — no consumer runs without its input contract
  (the spec §4 gap the review caught, now enforced by ordering).

## D. Definition of Done (from spec §9)

- [ ] T1–T8 complete; every L1 test seen RED before green.
- [ ] `make check` green; `tests/architecture/` green incl. mirror parity.
- [ ] `okf_lint.py` exit 0; index/log entry present.
- [ ] No ADR (no ⚠️ trigger); no `decisions.md` unless T1 column choice proves
      non-obvious.
- [ ] L4 walkthrough evidence + `make check` output pasted verbatim.
