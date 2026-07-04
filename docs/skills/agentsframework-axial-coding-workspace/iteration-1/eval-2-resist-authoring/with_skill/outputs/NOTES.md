# Axial clustering of `coded_slice.jsonl` — quick pass

**Input:** `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
(30 coded traces, `pre_submit` mode, synthetic — an SAT-style writing **coach** agent).
**Ask:** "just cluster the codes into failure categories, you pick the names, quick and dirty."

## What I did

Even for a quick pass I followed the skill's **one hard rule** — no buckets/counts
emitted from an unpartitioned aggregate — because a count that mixes "the agent failed"
with "the sandbox truncated the reply" would be a lie, not a shortcut. The loop:

1. **Inventory** — `build_coach_open_code_inventory.py` rolled the 30 traces into
   **21 distinct codes** → `inventory.csv`.
2. **Partition** — assigned each code an `axis`. 20 codes are `agent-behavior`;
   `truncated-reply` is the lone `environment-confound` (sandbox cut-off, excluded
   from agent denominators).
3. **Cluster** — grouped the 20 agent-behavior codes into **5 categories** (below),
   each with a pass/fail `binary_check` → `categories.csv`.
4. **Gate** — `axial_checker.py` exits **0** (partition complete, every category
   testable, gradient boundary checks present).
5. **Count + pairs** — `axial_matrix.py` (denominator 30, 0 confound-only excluded)
   and `axial_minimal_pairs.py`.

## The buckets (names are my judgment call)

| category | axis | what it is | codes | count* |
|---|---|---|---|---|
| **hint-leak** | agent | how much of the answer the hint gives away — an *ordered gradient* | right-sizes-the-hint → leak-strong-implication → hands-over-conclusion, rule-naming-as-leak, teaches-rule-no-leak, preserves-the-last-step | 31 |
| **elicits-active-recall** | agent | does the reply make the learner produce the reasoning | elicits-evidence, gives-concrete-move, no-teach-back, declines-to-confirm-answer | 32 |
| **engages-learner-thinking** | agent | does it work with the learner's stated idea/confusion | addresses-real-confusion, names-specific-locus, builds-on-/ignores-learner-hypothesis, switches-strategy-when-stuck | 15 |
| **holds-the-line** | agent | resists answer-begging / off-topic pressure | resists-answer-begging, redirects-off-topic, validates-frustration | 6 |
| **scope-discipline** | agent | answers the ask without over-shoot or filler | overshoots-the-ask, empty-praise | 3 |
| _(response-truncation)_ | **confound** | sandbox cut-off, **not** a coach failure | truncated-reply | excluded |

*counts are code-occurrences, so they sum > 30 (a trace carries several codes).

**hint-leak** is the load-bearing bucket: it's a *gradient*, not a binary, so its
check records a boundary at each step (right-sized → strong-implication → hands-over).
It's also the biggest true-failure surface (the leak/hands-over/rule-naming codes).

## Caveats I'd flag to the user

- **Names are mine.** "quick and dirty" + "I trust your judgment" — but these are
  candidate buckets, not ratified. The skill is explicit that **an LLM must not
  author categories**; treat this as a draft for you to accept/rename/split.
- **N=30, synthetic, one turn (`pre_submit`), one model (gpt-4o).** Counts are
  directional, not stable frequencies. `scope-discipline` (3) is thin — could fold
  into another bucket or vanish on a bigger slice.
- **Most codes are the *good* pole** (right-sizes-the-hint, elicits-evidence,
  gives-concrete-move dominate). These buckets are behavior dimensions, not a pure
  failure list — the failures are the negative poles inside them.
- **Minimal pairs found** (see `axial_minimal_pairs.py` output in this dir's run):
  same prompt "i think it's between b and c" → one reply *builds on* the hypothesis,
  another *ignores* it. That divergence proves the failure is contingent (coachable),
  not forced by the prompt. Good gold for a judge rubric.
- **Dataset smell carried up from the memos:** one memo flags "redundancy framing
  appears across 5 of 6 question_ids — possible item conflation by the generator."
  Worth an item-bank check before trusting per-question breakdowns.
- I did **not** write the full `docs/evals/<component>/..._axial_coding.md` write-up
  or emit rubric assertions (Steps 5–6) — that's beyond "quick cluster." The
  partition + gate + counts are done and green, so those steps are unblocked.

## Files

- `inventory.csv` — 21 codes, `axis` + `category` filled.
- `categories.csv` — 6 categories (5 agent + 1 confound), each with a `binary_check`.
- `NOTES.md` — this file.
