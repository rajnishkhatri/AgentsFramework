---
type: decision-record
title: 'ADR-0002: Repo-wide ruff baseline (commit 3b89b4e) — G8 test-mass-rewrite audit'
status: accepted
created: 2026-06-27
updated: 2026-06-27
owner: rajnish.khatri
related: 0000-template.md
tags: [decision-record, tooling, g8]
---

# ADR-0002: Repo-wide ruff baseline (commit 3b89b4e) — G8 test-mass-rewrite audit

**Status:** Accepted — 2026-06-27.
**Related:** [AGENTS.md](../../AGENTS.md) §"Decision records (intent debt) + comprehension gates" (the G8 gate); commit `3b89b4e` (the baseline).
**Audience:** Anyone reconsidering whether the Track-A ruff baseline silently weakened the test suite, or auditing a future large `--fix` pass.

---

## Context

Track A introduced a `[tool.ruff]` config and applied a one-time repo-wide
`ruff format` + safe `ruff check --fix` baseline (commit `3b89b4e`): **598 files
changed, +16340 / −8956**, of which **202 are under `tests/`**. The G8 gate
(AGENTS.md) says a large rewrite of existing tests can silently weaken the suite
(TAP-1/3/4), and requires justifying that *each weakened assertion is still
sound* before relying on the green result. The baseline commit recorded the suite
green (architecture 119, L1+L2 1406) and one intentional restoration
(`carrier_gate.py` `EVT_*` import) but did **not** carry the G8 audit record.
This ADR is that record, produced after the fact.

---

## Decision

Accept the `3b89b4e` ruff baseline as **format-and-safe-fix only**: it changed no
assertion's truth condition. The audit below is the evidence; future large
`--fix` passes must attach an equivalent audit.

---

## Options considered & rejected

| Option | Why rejected |
|--------|--------------|
| Trust the green suite alone | A green suite is exactly what G8 says is insufficient — a weakened assertion can still pass. Need to show *which* test lines changed and why each is still sound. |
| Revert the baseline | The baseline is load-bearing (it's what the swap-radius format-only discriminator reproduces, ADR-adjacent in `tests/architecture/test_mphase2_swap_radius.py`). Reverting would re-introduce the lint debt and break that discriminator's premise. |
| Hand-review all 202 test files | Disproportionate. The audit can be made rigorous by mechanical diff analysis (below) plus ruff's safe-fix contract, without reading 16k lines. |

---

## Rationale

Three independent lines of evidence, together, establish that no assertion
semantics changed:

1. **Mechanical diff audit.** Normalizing every `assert`-bearing line in the
   `tests/**` diff (strip `+`/`-`, collapse whitespace) and taking
   `comm -23 removed added` yields 118 "removed-but-not-re-added" candidates.
   Spot-checking the assertion-comparison candidates (`==`, `is True/False`)
   against the current tree shows each one still present — either verbatim (e.g.
   `verify_answer(EVENTS_TASK, "The peak error hour is 10.", EVENTS_EV) is False`
   in `tests/components/test_answer_verifiers_value_shapes.py`) or as a
   `ruff format` line-reflow of the same call (e.g.
   `should_compact_trajectory(current_token_count=4000, token_threshold=3000) is
   True` wrapped across lines in `tests/services/test_reasoning_tools.py`;
   `exit_code_for("request_changes", findings, "critical") == EXIT_REQUEST_CHANGES`
   wrapped in `tests/code_reviewer/test_frontend_runner.py`). The "candidates" are
   reflows and import removals, not weakenings.

2. **Ruff safe-fix contract.** `ruff check --fix` (without `--unsafe-fixes`)
   applies only fixes ruff classifies as safe — by ruff's own contract these
   preserve runtime behavior (F401 unused-import removal, I import-sort, UP
   syntax modernization, E/W whitespace). A safe fix that altered an assertion's
   truth value would be a ruff defect, not a silent test weakening. No
   `--unsafe-fixes` was used in the baseline.

3. **Suite parity.** The suite was green before and after at the same counts; the
   one behavioral edit ruff would have made (removing the `carrier_gate.py`
   `EVT_*` "unused" import that is actually re-exported) was caught and manually
   restored in the same commit. That this single non-format consequence was
   noticed and reversed is positive evidence the diff was reviewed for semantic
   impact, not blindly accepted.

The audit commands are recorded so they can be re-run:

```bash
# normalized assert-line set diff
git show 3b89b4e -- 'tests/**' \
  | grep -E '^-' | grep -vE '^---' | grep 'assert' \
  | sed -E 's/^-//; s/[[:space:]]+/ /g; s/^ //; s/ $//' | sort > /tmp/removed.txt
git show 3b89b4e -- 'tests/**' \
  | grep -E '^\+' | grep -vE '^\+\+\+' | grep 'assert' \
  | sed -E 's/^\+//; s/[[:space:]]+/ /g; s/^ //; s/ $//' | sort > /tmp/added.txt
comm -23 /tmp/removed.txt /tmp/added.txt   # candidates -> verified as reflows/import-removals
```

---

## Consequences

- **Commits us to** attaching a G8 audit (the command block above, plus a
  spot-check of comparison asserts) to any future repo-wide or large `--fix`
  pass, rather than relying on the green suite.
- **Accepted risk:** the spot-check is a sample, not an exhaustive line-by-line
  proof. Mitigation: it is backed by ruff's safe-fix contract (evidence #2) and
  suite parity (evidence #3), so the sample only needs to catch a *class* of
  error, not every instance. `--unsafe-fixes` is never run in a baseline; if it
  ever is, this audit's contract does not cover it and a full review is required.
- **Follow-on:** the swap-radius format-only discriminator
  (`tests/architecture/test_mphase2_swap_radius.py`) depends on this baseline
  being reproducible by `ruff format` + plain `--fix`; keep the repo ruff config
  and that discriminator's fix-set in sync (no `--select` narrowing — review #4).

---

## Supersedes / related

- Records the G8 audit for commit `3b89b4e`. Supersedes nothing.
- Related: AGENTS.md G8 gate; `tests/architecture/test_mphase2_swap_radius.py`
  (`_reformatted_matches` — the format-only discriminator that reproduces this
  baseline's reformat).
