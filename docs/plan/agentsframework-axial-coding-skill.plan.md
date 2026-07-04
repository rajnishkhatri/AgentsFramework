# Plan — `agentsframework-axial-coding` skill

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Derives from:** [spec](agentsframework-axial-coding-skill.spec.md) (accepted) +
[brainstorm](agentsframework-axial-coding-skill.brainstorm.md). Constitution:
`AGENTS.md` 8 invariants + `tests/architecture/`.

---

## 1. Architecture at a glance

A **docs-only skill bundle** + **three read-only Python scripts** + a
**one-column extension** to an existing repo script. No runtime, no layer
crossing, no new dependency (κ deferred to v2, pure-stdlib when built).

```
coded.jsonl (Stage-1 output)
   │
   ├─▶ build_*_open_code_inventory.py  ──▶  inventory CSV  ──(human fills axis+category)──┐
   │        (repo scripts/, EXTENDED: +axis +category cols)                               │
   │                                                                                       │
   │                                          categories.csv  ──(human: polarity/check/dim)┤
   │                                                                                       ▼
   ├─▶ axial_minimal_pairs.py   (bundle scripts/, NEW)                              axial_checker.py
   ├─▶ axial_matrix.py          (bundle scripts/, NEW) ◀── join code→category ── (bundle, NEW)
   │                                                                                       │
   └─────────────────────────────────────────────────────────────────────── emit gate ◀──┘
                                                            (checker green → coder writes
                                                             <component>_axial_coding.md)
```

## 2. Location decision (refines spec §2 — a real fork the spec glossed)

Investigation found the established pattern is **not** "everything in repo
`scripts/`". The open-coding bundle's `scripts/` holds skill-specific tooling
(`serve_open_coder.py`, `export_coded_to_dataset.py`) that is *canonical there*
and mirror-synced; repo `scripts/` holds the coach-pipeline scripts (with tests
in `tests/scripts/`). So we **split by ownership**:

| New/changed file | Home | Why |
|---|---|---|
| `axial_matrix.py`, `axial_minimal_pairs.py`, `axial_checker.py` | **bundle** `docs/skills/agentsframework-axial-coding/scripts/` | generic, skill-owned, mirror-synced (like open-coding's exporter) |
| `axis`/`category` columns | **repo** `scripts/build_coach_open_code_inventory.py` | it's a coach-pipeline script with an existing test; FR-13 extends it |

The generic contract (FR-7) is honored by the **bundle scripts** consuming any
`coded.jsonl` + inventory/categories CSVs; the coach inventory script stays
coach-flavored but grows the two generic columns every axial pass needs.

> **Testing the bundle scripts.** Repo `tests/scripts/` imports `from scripts.…`.
> Bundle scripts aren't on that path. Resolve by adding
> `tests/skills/axial_coding/` that imports the bundle scripts by file path
> (importlib) — same approach as any out-of-tree script test. Confirm at
> implementation; fallback is a thin repo-`scripts/` re-export if importlib
> proves ugly. (Task 0 spike.)

## 3. File-level touchpoints

**New — skill bundle** `docs/skills/agentsframework-axial-coding/`:
- `SKILL.md` — frontmatter (`name`, `type: skill`, `description` with
  Use-whenever/Do-NOT-use, `paths:`) + the runbook: the 6-move discipline, the
  mandatory-partition gate, the CSV edit surface, the emit-as-prose step,
  pointers to handbook Stage 2 (why) and `agentsframework-open-coding` (Stage 1).
  Mirror the open-coding SKILL.md structure. ≤~300 lines.
- `scripts/axial_matrix.py` — FR-9/FR-3: join inventory(code→category) ⋈
  categories(category→axis/check); emit code×category counts, per-mode where
  present; **exclude `environment-confound` rows from agent-behavior
  denominators**.
- `scripts/axial_minimal_pairs.py` — FR-8/FR-9a: group by normalized-exact
  `prompt`, surface `open_codes` divergence; axis-blind in v1 with the
  noise-mode note in output.
- `scripts/axial_checker.py` — FR-1/FR-2/FR-4/FR-4a/FR-13: the **emit gate**.
  Verifies every code has a valid `axis`; every clustered code a `category`;
  every category a non-empty `binary_check` and axis-uniform members; gradient
  categories record a dimension + boundary checks. Non-zero exit + names the
  offender on any failure. *FR-1 "refuse to emit" = this checker failing; no
  separate emit pipeline.*
- `references/input-contract.md` — the JSONL + inventory-CSV + categories-CSV
  contracts (§4 of the spec, expanded); the straddle tie-break rule.
- `references/exemplars.md` — points at the two hand passes as worked examples;
  the gradient/minimal-pair/template-economy vocabulary.
- `evals/evals.json` — skill-creator test prompts (NOT mirrored; sync excludes
  `evals/`).

**Changed — repo:**
- `scripts/build_coach_open_code_inventory.py` — add `axis` + `category` to
  `GOALJUDGE_COLUMNS` (blank cells, human-filled), preserving column order/parity
  note. Small, additive.
- `docs/skills/index.md` + `docs/skills/log.md` — OKF bundle registration
  (FR-15); newest-first log line. Use `agentsframework-okf-curator` or hand-edit.

**New — tests:**
- `tests/skills/axial_coding/test_matrix.py` — FR-3, FR-4, FR-9.
- `tests/skills/axial_coding/test_minimal_pairs.py` — FR-8, FR-9a.
- `tests/skills/axial_coding/test_checker.py` — FR-1, FR-4a, FR-13 (failure
  paths first: missing axis, missing category, missing check, straddle).
- `tests/scripts/test_build_coach_open_code_inventory.py` — extend for the two
  new columns.

## 4. Constitution check (derived-from `AGENTS.md`)

| Invariant / gate | Status |
|---|---|
| #1–#8 layering | **untouched** — scripts read JSONL/CSV, import only stdlib; no orchestration/component/service/trust code; no `langgraph`/`langchain`. |
| ⚠️ Ask-first (dep/trust-type/node/service/abstraction) | **none** — no `pyproject.toml` change; the skill is the only "abstraction" and G1 is answered by spec P3. |
| ADR.1 ratchet | **no ADR** — no ⚠️ trigger path touched. If `stop_adr_reminder.py` fires on the `docs/skills/` add, it's a false positive (no seam governed); note "ADR-OK: docs-only skill, no invariant" if a range commit trips `test_adr_ratchet.py`. |
| Mirror parity | `make skills-sync` + `test_skills_mirror_parity.py` (FR-15). |
| OKF lint | `scripts/okf_lint.py` — bundle needs `type: skill` frontmatter + index/log entry. |
| PromptService / eval_capture / no-hardcoded-model | **N/A** — no LLM call on any shipped path (FR-12 red-team is coder-run, off-CI). |

**No ADR required.** The one borderline is FR-13 editing a shared pipeline
script; it's a two-column additive change, not a trust-kernel/interface break —
`decisions.md` line at most, and only if the column-parity choice is non-obvious.

## 5. Migration / sequencing (feeds Stage 3 tasks)

1. **Task 0 (spike):** confirm bundle-script test-import approach (importlib vs
   thin re-export). Resolves the §2 caveat before writing tests.
2. **Contracts first:** extend the inventory script (+2 columns) + define the
   categories CSV shape → the two artifacts everything else joins on.
3. **Checker (the gate) TDD:** failure-path tests first (missing axis/category/
   check, straddle) — red before green. This is FR-1's real mechanism.
4. **Matrix + minimal-pairs TDD:** confound-exclusion and normalization tests.
5. **SKILL.md + references:** the runbook prose; emit-as-prose step; exemplar
   pointers. L4 walkthrough over a slice of the two real `coded.jsonl`.
6. **Package:** `make skills-sync`, `okf_lint`, index/log entry; `make check`
   green.

## 6. Verification (end-to-end)

- **Baseline before implement:** `make check` + `pytest tests/architecture/ -q`
  green on a clean tree (Stage-4 requirement; run at sdd-implement start).
- **Per-FR:** the spec §8 table — L1 tests via `.venv/bin/python -m pytest
  tests/skills/axial_coding/ tests/scripts/test_build_coach_open_code_inventory.py -q`.
- **L4 walkthrough:** run the three scripts over a 20-row slice of
  `docs/evals/eng-coach/coded.jsonl` + a hand-filled inventory/categories CSV;
  confirm (a) checker blocks emit when a code lacks an axis, (b) matrix excludes
  the `F1`/truncated confound rows from agent denominators, (c) minimal-pairs
  surfaces a known divergent pair (e.g. the `cool-next` redirect pair).
- **Mirror + lint:** `make skills-sync && python scripts/okf_lint.py` → exit 0;
  `pytest tests/architecture/test_skills_mirror_parity.py -q` green.
- Evidence: paste actual command output, not summaries (AGENTS.md).
