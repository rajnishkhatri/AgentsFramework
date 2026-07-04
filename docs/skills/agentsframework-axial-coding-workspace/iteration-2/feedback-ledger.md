# Iteration 2 feedback → action ledger

The reviewer verified every output against the fixture again. The signal is
tightly convergent: **the errors have moved to the prose-emit step, where no gate
exists**, and one mechanical check (proposed in 4 of 6 reviews) would catch them.

## Confirmed against the fixture

| # | Defect | Verified? | Where |
|---|---|---|---|
| D1 | eval-0 §7 assertion 5 cites `0d3f493f` for `no-teach-back` — it doesn't carry it (correct exemplar is `00eda7de`); and `08…` is a dangling ID | ✅ verified: 0d3f493f has no no-teach-back; no trace starts 08 | prose emit (§7) |
| D2 | eval-2 "strong leaks = 6/30" contradicts its own rung placement: `41efeb07` has overshoots+rule-naming (a rung-2 trace by its taxonomy) → should be 7/30 | ✅ verified: 41efeb07 lacks strong/hands-over codes | prose count |
| D3 | eval-1 gradient: ordering says rule-naming worse than strong-implication, but severe-split skips rule-naming — internally inconsistent; dimension omits 2 of 7 members | ✅ (per review; ordering + membership mismatch) | categories.csv |

## The convergent fix (build it — TWO new checker rules)

Both D2 and D3 are caught by **gradient-consistency validation** in
`axial_checker.py`:
1. **Membership completeness** — every code whose inventory `category` is a
   gradient category must appear in that category's `dimension` ordering (or be
   explicitly marked off-gradient).
2. **Contiguous threshold** — (documented rule + the ordering is the source of
   truth) any "rungs ≥ k" count reported must be a contiguous prefix/suffix of
   the declared ordering. The checker can't see the prose count, but it CAN
   enforce that the dimension lists every member in order, which removes the
   ambiguity that lets the prose diverge.

D1 is caught by a **second new check — exemplar-ID fidelity** (its own small
script, run at emit time): walk the emitted assertions/judge-cases, confirm every
cited trace_id (a) resolves in the coded JSONL and (b) carries the code the
assertion claims. This is the missing gate at the prose-emit step.

## Applied this iteration (iteration-3 skill) — DONE 2026-07-04

- [x] A4: `axial_checker.py` — gradient membership completeness (every gradient
      category's member codes appear in its `dimension`).
- [x] A5: new `axial_cite_check.py` — exemplar-ID fidelity (cited IDs resolve +
      carry the claimed code). The missing prose-emit gate.
- [x] A3 (finally): populate `short_definition` — the iteration-2 eval-0
      *baseline* proved the pipeline can generate them. Either the builder fills
      from memos, or SKILL.md step 0 says to. (Reviewer: longest-open finding.)
- [x] B5: SKILL.md — "check the fixture for design metadata (strata, modes) and
      condition counts on it." The eval-0 baseline's **stratum analysis**
      (100% leak on rule_naming/leak_bait vs 32% breadth) was the single best
      finding in either arm and the with-skill run MISSED it. High-value add.
- [x] B6: SKILL.md — a code known to be contested (e.g. `overshoots-the-ask`,
      placed in 3 different categories across runs) needs a memo-grounded
      justification for its placement; pin the decision.
- [x] Doc: one line in checker docstring that empty `category` is allowed for
      non-agent-behavior (confound/judge) codes — currently an undocumented
      allowance.

## Deferred to iteration-3 eval RUN (infra)

- **Baseline isolation, for real:** fixture relocation demonstrably failed TWICE.
  The skill dir `docs/skills/agentsframework-axial-coding/` is grep-discoverable
  from the prompt word "axial." Fix: run baselines in a workspace where the skill
  dir is absent/unreadable — a git worktree with it removed, or /tmp with the
  output path NOT under docs/skills/. Also scrub "without_skill" + the skill name
  from baseline paths (arm-revealing path leaks framing even without pipeline).
- Category-boundary drift: add an inventory.csv category-column diff between two
  runs so the human ratifier sees contested placements.

## The reviewer's net read (worth quoting)

> The skill's value on this evidence is **structure** (testable checks, partition,
> gradients, pairs), **not arithmetic care** — which supports adding the mechanical
> gradient-consistency check to axial_checker.py rather than assuming the skill
> loop alone prevents count errors.

Two runs also showed the pipeline is **robust when picked up cold** (contaminated
baselines reproduced 12/29 exactly), and in places the cold run produced a
*cleaner* design than the guided one — evidence the discipline transfers, and that
the mechanical checks (not prose) are what close the residual gaps.
