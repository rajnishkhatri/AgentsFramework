# NOTES — axial coding pass (coded_slice.jsonl)

**Skill:** `agentsframework-axial-coding` (grounded-theory Stage 2).
**Input:** `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
— 30 traces, 21 distinct open codes, all `pre_submit`.
**Date:** 2026-07-04 · interpreter: `.venv/bin/python`.

## What I did (the skill loop, steps 0–6)

0. **Inventory** — ran the bundled `scripts/build_coach_open_code_inventory.py`
   over the coded slice → `inventory.csv` (21 rows, one per code, blank
   axis/category).
1. **Partition** — read all 30 memos, then filled `axis` for every code:
   19 agent-behavior, 1 environment-confound (`truncated-reply`, by *cause* =
   harness truncation; consequence noted in the write-up), 0 judge-reliability.
2. **Cluster** — grouped the 19 agent-behavior codes into 6 named categories and
   hand-authored `categories.csv` (category, axis, polarity, binary_check,
   dimension). C1 (leakage) is the one ordered gradient → boundary checks at each
   pole, `|`-separated, with `dimension` set.
3. **Gate** — `axial_checker.py` → **exit 0, OK, emit allowed.**
4. **Count + pairs** — `axial_matrix.py` (`matrix.json`) and
   `axial_minimal_pairs.py` (`minimal_pairs.json`).
5. **Write-up** — `coach_axial_coding.md` (category map, axis partition, the C1
   gradient, definitions, minimal pairs, template note).
6. **Emit** — rubric assertions + judge test-case candidates in write-up §5.

## Final taxonomy (6 categories, all agent-behavior)

| Cat | Name | Polarity | Trace count (denom 30) |
|---|---|---|---|
| C1 | Answer-leakage channel (gradient) | ± | 20 |
| C2 | Answer-boundary hold | + | 8 |
| C3 | Uptake of learner thinking | ± | 11 |
| C4 | Scaffold calibration | ± | 29 |
| C5 | Verification of understanding | ± | 15 |
| C6 | Register & conversation policy | ± | 4 |

Off-axis: `truncated-reply` (environment-confound, 3); id-churn + template-reuse
memos = corpus-quality findings, no axis.

## Final script outputs

### axial_checker.py (the emit gate)
```
OK — partition complete, every category testable; emit allowed.
exit=0
```

### axial_matrix.py
```json
{
  "agent_denominator": 30,
  "category_counts": {
    "C1-leakage-channel": 20,
    "C2-answer-boundary": 8,
    "C3-uptake": 11,
    "C4-scaffold-calibration": 29,
    "C5-verification": 15,
    "C6-register-policy": 4
  },
  "confound_only_excluded": 0
}
```
Note: `confound_only_excluded = 0` because all 3 truncated traces also carry
agent-behavior codes — the FR-3 exclusion had nothing to drop here; denominator
is the full 30.

### axial_minimal_pairs.py — 4 groups surfaced (tool is axis-blind)
- **GOLD** "i think it's between b and c" — `1e28adc2` (ignores-learner-hypothesis)
  vs `2b4cf8ce` (builds-on-learner-hypothesis). C3 contingency.
- **GOLD** "if i had to explain this sentence to a friend…" — `0d3f493f`
  (strong-implication + hand-over) vs `104ba6ae` (rule-naming). C1 gradient.
- **GOLD** "give me a hint but a small one" — 3-way positive family diverging on
  C5 elicits-evidence / C2. Graded "good small hint" family.
- **NOISE (reject)** "if i swap the underlined part…" — `1b4ce6ca` vs `3108cc62`
  differ ONLY on `truncated-reply` (environment-confound). Not a minimal pair.

## Cross-cut findings (hand off to rubric design / item-bank owner)
- **Refusal theater** (traces 15, 28): resists-answer-begging + leak-strong-
  implication on the same turn — the load-bearing adversarial case for a leakage
  judge; a by-name refusal masks a functional leak.
- **C1 ↔ C4 coupling:** every `overshoots-the-ask` (24, 26) is *what produces*
  the leak — scope overshoot and leakage co-fire.
- **Template economy:** DUP-FLAG clusters (cover-the-phrase, return-crux-leader,
  arithmetic-detour, essay-intro) reuse byte-near answers across different
  prompts. Take one exemplar per cluster into any gold set.
- **Corpus quality:** question_id ↔ item mapping is unreliable (same item under
  ≥4 different qids) — item-bank check needed before option-dependent leak calls
  are trusted.

## Output files (this directory)
- `inventory.csv` — 21 codes, axis + category filled.
- `categories.csv` — 6 categories with binary_check + C1 dimension.
- `matrix.json` — per-category counts (confound-excluded).
- `minimal_pairs.json` — raw minimal-pair tool output.
- `coach_axial_coding.md` — the axial write-up (steps 5–6).
- `NOTES.md` — this file.
