# Spec — `agentsframework-axial-coding` skill

> Acceptance criteria use **EARS**. "THE SYSTEM" here = the skill + its bundled
> scripts as used by a coder following the runbook. Failure paths (IF-THEN)
> first.

**Status:** Draft (clarified) — 2026-07-04
**Owner:** Rajnish Khatri
**Related:** [brainstorm](agentsframework-axial-coding-skill.brainstorm.md) (Stage 1
complete) · handbook Stage 2 `.claude/skills/llm-eval-grounded-theory/SKILL.md`
L122–144 · sibling `.claude/skills/agentsframework-open-coding/SKILL.md` ·
exemplars `docs/research/goaljudge_phase3_axial_coding.md`,
`docs/evals/eng-coach/coach_axial_coding.md`

---

## 1. Goal

Give a coder an **operational companion** for grounded-theory Stage 2 (axial
coding): turn an open-coded `coded.jsonl` into a partitioned, testable failure
taxonomy plus rubric/judge-case candidates — capturing the discipline both hand
passes re-derived, so the third pass reuses instead of reinventing. For the
eval-authoring engineer running the open→axial→rubric pipeline in this repo.

## 2. Context

Axial coding was done by hand twice (GoalJudge Phase 3 3-axis; eng-coach 9-cat +
dimensions) with no shared template — the recurring asset is a **discipline**,
not a fill-in form (brainstorm P5, refuted→re-posed). The handbook only *names*
Stage 2 in ~22 lines of *why*; the operational *how* (confound partition, minimal-
pair detection, emit-to-judge-cases) has nowhere to live. This skill is the *how*,
exactly as `agentsframework-open-coding` is the *how* for Stage 1.

**Code lives in repo `scripts/`; the skill *references* it.** The new scripts sit
in the repo's top-level `scripts/` (beside `build_coach_open_code_inventory.py`,
which FR-13 extends), and the `docs/skills/` bundle references them by path — the
same split the open-coding skill uses. No runtime, no layer crossing. The skill
bundle itself is docs + references only.

## 3. Functional requirements (EARS)

**The mandatory-partition gate (the core rule) — failure paths first**

- **FR-1.** IF any frequency count, top-mode pick, or emitted assertion derives
  from an aggregate that has **not** been partitioned into the three axes
  (Agent-behavior / Environment-confound / Judge-reliability) THEN THE SYSTEM
  SHALL refuse to emit it and name the unpartitioned aggregate. *(Class-level
  rule: "no assertion from an unpartitioned aggregate.")*
- **FR-2.** IF a proposed category has no binary pass/fail check writable against
  observable trace evidence THEN THE SYSTEM SHALL reject it as un-testable (the
  "capability limitations" reject; the testable-category rule,
  `goaljudge_phase3_axial_coding.md` §2 "Each category must be *testable*").
- **FR-3.** WHEN partitioning, THE SYSTEM SHALL treat the Environment-confound
  axis as a **validity precondition** — confound-only cases are excluded from
  Agent-behavior frequency denominators, not folded into behavioral clusters.

**The discipline (Ubiquitous / WHEN)**

- **FR-4.** THE SYSTEM SHALL cluster Agent-behavior open codes into a small set
  of **named, testable** categories (**target 5–6, not a gate** — the eng-coach
  pass honestly ran to 9; forced lumping is worse than an extra honest
  category), each defined in the **category contract** (§4) with member codes, a
  polarity, and its binary check.
- **FR-4a.** WHERE the member codes of a category form an **ordered gradient**
  (e.g. eng-coach `right-sizes-the-hint` → `leak-strong-implication` →
  `hands-over-conclusion`), THE SYSTEM SHALL record the dimension and place a
  binary check at **each category boundary** — a gradient reduces to ordered
  boundary-checks, not one coarse pass/fail. (Without this, FR-2 would reject
  the most valuable structures in the exemplar's own data.)
- **FR-5.** WHERE a case carries multiple Agent-behavior codes, THE SYSTEM SHALL
  pick the **primary** one by first-failure order (first trajectory deviation;
  downstream symptoms secondary, ≤3 codes/axis). *This is an axial-stage
  re-coding rule — choosing the primary axis-A code when building the per-case
  matrix — not a Stage-1 assignment rule; per-trace code assignment stays in
  `agentsframework-open-coding`.*
- **FR-6.** WHEN a category is finalized, THE SYSTEM SHALL yield candidate
  **rubric assertions AND judge test-case candidates** (proven consumer:
  eng-coach §7 → `judge_test_cases.jsonl`), each traceable to a partitioned
  category. *Emit is **prose discipline**, not a script (locked v1 scope =
  contract + matrix + minimal-pairs); the eng-coach emit was judgment-heavy
  (exemplar selection, `must_catch`/`failure_if` wording) and gains nothing from
  automation. Verified by the L4 walkthrough, not an emit pipeline.*

**Bundled scripts — input contract (D2)**

- **FR-7.** THE SYSTEM SHALL provide repo `scripts/` (referenced by the skill,
  §2) that consume any open-coded JSONL matching a **documented input contract**
  (rows with `trace_id` + `open_codes[]`; other columns optional), not coach- or
  GoalJudge-specific columns.
- **FR-8.** THE SYSTEM SHALL provide a **minimal-pair detector**: group rows by
  normalized `prompt` and surface groups whose `open_codes` diverge (proves
  failure is contingent, not forced). IF the axis column (§4) is present THEN the
  detector MAY filter to **agent-behavior divergence**; v1 ships axis-blind but
  SHALL note in its output that pairs diverging only on environment/judge codes
  are noise, not minimal pairs.
- **FR-9.** THE SYSTEM SHALL provide a **code×category matrix + frequency**
  roller over the input contract **joined to the category contract (§4)**
  (per-category, per-mode where `mode` present).
- **FR-9a.** WHEN grouping by prompt (FR-8) THE SYSTEM SHALL use
  **normalized-exact** matching (lowercase, collapse whitespace, strip
  surrounding punctuation) — no tunable similarity threshold in v1.

**Deferred to v2 (documented, not built)**

- **FR-10 (v2).** Template-similarity detector (fuzzy near-duplicate
  `final_answer` clustering, the coach doc's 0.61–0.89 scores) — deferred; v1
  ships exact-normalized grouping only. The skill *names* the template-economy
  phenomenon and points here.
- **FR-11 (v2).** IF ≥2 coders produced the input THEN a Cohen's κ script MAY be
  run as a **conditional check, not a gate**; single-coder input skips it
  returning "n/a" (never a fabricated `0.0`). v1 documents the rule and the skip;
  the κ script itself is v2. **κ is ~10 lines of pure stdlib — commit to no numpy
  now**, so no new `pyproject.toml` dependency and no `decisions.md` entry.

**Adversarial review (D6, narrowed)**

- **FR-12.** WHERE an LLM assist is used, THE SYSTEM SHALL use it **only** to
  red-team proposed categories (hunt un-testable / over-broad buckets per FR-2),
  NEVER to draft categories or own their names (R3/R12: human owns names).

**Axis assignment (clarified)**

- **FR-13.** THE SYSTEM SHALL assign each distinct code its axis via an **`axis`
  column on the inventory CSV** produced by `build_*_open_code_inventory.py`
  (extend the existing script, one row per distinct code; the human fills it).
  A checker script SHALL verify every code carries a valid axis before emit
  (FR-1).

**Stage boundary (clarified)**

- **FR-14.** THE SYSTEM SHALL scope to **Stage 2 (axial) only**; selective
  coding (core category + storyline, e.g. `coach_selective_coding.md`) is the
  human-judgment synthesis on top — the skill points to the handbook for it and
  does NOT automate it (matches open-coding's single-stage scope).

**Skill packaging**

- **FR-15.** THE SYSTEM SHALL be authored canonically at
  `docs/skills/agentsframework-axial-coding/`, mirrored by `make skills-sync`,
  with an `index.md` + `log.md` entry — passing
  `tests/architecture/test_skills_mirror_parity.py` and `scripts/okf_lint.py`.

## 4. Data model / contracts

**Input contract (FR-7)** — open-coded JSONL, one row/trace:

```json
{ "trace_id": "…", "open_codes": ["code-a", "code-b"],
  "prompt": "…", "final_answer": "…", "mode": "…", "stratum": "…", "memo": "…" }
```
Required: `trace_id`, `open_codes[]`. `prompt`/`final_answer` required only for
FR-8/FR-9 (pair + template detectors). Extra keys ignored. Matches the existing
`scripts/build_coach_open_code_inventory.py` `--coded` interface — new scripts
sit beside it, same flag.

**Inventory CSV — axis + category columns** (FR-1/FR-3/FR-9/FR-13) — the
inventory CSV (`<component>_open_code_inventory.csv`, produced by the extended
`build_*_open_code_inventory.py`, one row per distinct code) is the coder's
**single edit surface** and gains two human-filled columns:

| Column | Filled by | Values |
|---|---|---|
| `axis` | human | exactly one of `agent-behavior` \| `environment-confound` \| `judge-reliability` |
| `category` | human | the category label this code belongs to (blank until clustered) |

The `axis` column is the partition source of truth (FR-1). The `category` column
is what makes the FR-9 matrix runnable — **without it the matrix script has no
code→category mapping and cannot run**. Both live on one CSV so the coder edits
one file (consistent with FR-13).

**Tie-break for a straddling code** (FR-13) — a code may legitimately touch two
axes (e.g. `truncated-reply`: environment-confound *by cause* = `max_tokens`,
judge-reliability *by consequence* = unscorable → `scorable:false` in the coach
judge cases; verified: 9/34 truncated traces also carry an agent-behavior leak
code). Rule: **assign `axis` by cause; record the consequence in the memo/notes
column.** The single-column invariant holds; the coder never silently decides.

**Category contract** (FR-4/FR-4a/FR-9) — category-level metadata lives in a
small **`<component>_categories.csv`** (or an equivalent table the checker
parses), one row per category:

| Column | Meaning |
|---|---|
| `category` | label (joins to the inventory CSV `category` column) |
| `axis` | which axis the category sits on (must be uniform across its member codes) |
| `polarity` | `+` / `−` / `±` |
| `binary_check` | the pass/fail check text (FR-2 admissibility) |
| `dimension` | optional; the ordered gradient + boundary-check notes (FR-4a) |

The FR-9 matrix = inventory CSV (code→category) ⋈ categories CSV
(category→axis/check). The checker (FR-13) verifies: every code has an `axis`;
every clustered code has a `category`; every category has a non-empty
`binary_check`; a category's `axis` matches its members' — before any emit.

**Output docs** — `docs/evals/<component>/<component>_axial_coding.md` (no OKF
frontmatter, excluded dir per `docs/CONVENTIONS_OKF.md`); no trust-kernel type
change.

## 5. Invariants & security boundaries

- **No Architecture Invariant touched** — docs + `scripts/` only; scripts are
  read-only over JSONL, framework-agnostic, import stdlib + repo helpers. No
  orchestration/component/service/trust code.
- **No ⚠️ Ask-first trigger** — **no new `pyproject.toml` dep** (κ is pure
  stdlib, v2; no numpy), no trust type, no graph node, no service. **G1
  new-abstraction gate** applies to the skill: "what it buys over the handbook" =
  P3 (handbook Stage 2 is 22 lines).
- Security: no secrets, no live-LLM in CI (the FR-12 red-team assist is a coder-
  run tool, never on the `make check` hot path).

## 6. Edge cases

- **Empty `open_codes`** on a row → excluded from clustering with a count
  (mirrors the open-coding Step-4 trap); never silently treated as a category.
- **Single-coder input** → κ path skipped (FR-11, v2 rule), not faked to a
  fabricated agreement number (AP-6: return "n/a", not `0.0`).
- **Unassigned `axis` cell** in the inventory CSV → checker FAILS the emit gate
  and names the code (FR-13 → FR-1), never defaults a code to a bucket.
- **Truncated traces** (eng-coach had 34) → flaggable + excludable from
  denominators; the detector marks, the coder decides.
- **`question_id` / prompt churn** (same content, different id) → normalized-
  prompt grouping (FR-8) must not over-split; document the normalization.
- **No `final_answer` column** → the FR-8 pair detector degrades gracefully:
  it still groups by `prompt` and compares `open_codes`, but skips any
  reply-equality check (template-sim is v2 anyway), emitting a note rather than
  crashing.
- **Straddling code** (touches two axes) → assign `axis` by cause, record
  consequence in memo (§4 tie-break); never silently dropped or double-counted.
- **A category with only confound members** → not admissible on Axis A (FR-3).

## 7. Non-functional requirements

- **Determinism:** scripts are L1-deterministic (same JSONL → same matrix/pairs);
  no LLM on the scripted path. Re-runnable, idempotent, read-only over input.
- **Cost/latency:** local, no network. The only LLM touch (FR-11 red-team) is
  opt-in and off-CI.
- **Reversibility:** additive skill; produces docs/artifacts, mutates nothing.

## 8. Test plan

Failure-path tests first. Script FRs get L1 unit tests; skill-discipline FRs
(2, 5, 6, 12) are prose rules verified by a **fixture walkthrough** over a slice
of the two real coded.jsonl files (behavioral/L4) — the check is "the runbook's
gate catches the seeded violation," not a Python assert.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `test_checker::test_emit_blocked_when_code_has_no_axis` (= FR-13 checker failing; no separate emit script) | L1 | yes |
| FR-2 | walkthrough: "capability limitations" bucket → rejected | L4 | no (doc gate) |
| FR-3 | `test_matrix::test_confound_excluded_from_denominator` | L1 | yes |
| FR-4 | `test_checker::test_category_requires_member_codes_and_binary_check` | L1 | yes |
| FR-4a | `test_checker::test_gradient_category_records_dimension_and_boundary_checks` | L1 | yes |
| FR-5 | walkthrough: multi-code case → primary = first-deviation (axial re-code) | L4 | no |
| FR-6 | walkthrough: category → rubric assertion + judge-case candidate (prose, no script) | L4 | no |
| FR-7 | `test_contract::test_rejects_row_missing_trace_id_or_codes` | L1 | yes |
| FR-8 | `test_minimal_pairs::test_same_prompt_divergent_codes_surfaced` | L1 | yes |
| FR-9 | `test_matrix::test_code_x_category_counts_via_join` | L1 | yes |
| FR-9a | `test_minimal_pairs::test_prompt_normalization` | L1 | yes |
| FR-12 | walkthrough: assist proposes a category name → rejected (human owns) | L4 | no |
| FR-13 | `test_checker::test_missing_axis_or_category_or_check_fails`; straddle → by-cause | L1 | yes |
| FR-14 | (scope assertion — no selective automation shipped) | — | n/a |
| FR-15 | `tests/architecture/test_skills_mirror_parity.py`; `scripts/okf_lint.py` | L1 | yes |

FR-10/FR-11 are v2 — no v1 tests. **FR-1's "refuse to emit" is the FR-13 checker
failing — no separate emit pipeline is built** (keeps v1 to the 3 locked
scripts + the checker).

## 9. Definition of Done

- [ ] All FRs implemented; each L1 test seen to fail first.
- [ ] `make check` green (lint + format-check + pyright + test).
- [ ] Invariants §5 unbroken (`tests/architecture/` green, incl. mirror parity).
- [ ] `scripts/okf_lint.py` exit 0 (skill bundle + index/log entry).
- [ ] No ADR needed (no ⚠️ trigger); no `decisions.md` line (κ = stdlib, no new
      dependency).
- [ ] Actual command output pasted for verification claims.
