# coach-bank gen2 — QA report (coach-item-bank-gen2.promoted.json)

Generated 2026-07-16 · profile `enhanced-act` (PoW 40 / KoL 20 / CSE 40) · provenance `claude-fable-5+claude-opus-4-8>=v1@4931561dee2300e4a1b57ee1413067b6`

## Totals
- Questions: **1000** (all new; zero overlap with the 171-item live bank)
- Hints: **12000** = 1,000 questions x 3 wrong letters x 4 rungs (pump -> hint -> prompt -> assertion)
- Item types: 750 underlined-span-mc, 250 rhetorical-mc (goal-format)

## Distribution
- Skills: {'s-gram': 133, 's-org': 200, 's-punc': 133, 's-rhet': 200, 's-sent': 134, 's-style': 200}
- Difficulty: {1: 36, 2: 242, 3: 378, 4: 263, 5: 81}
- Answer letters: {'A': 273, 'B': 243, 'C': 242, 'D': 242} (chi2 = 2.82, uniform at p >= 0.01)
- NO CHANGE-bearing items: 750; NO CHANGE correct: 210 (28.0%, target 25-33%)

## Gates passed
- Per-shard validator (40/40 shards): schema, spec conformance (skill/standard/difficulty/answer letter),
  exactly one underlined span per span item, per-choice rationales, 4-rung ladders on exactly the 3 wrong
  letters, leak lint (key content words, letter references, 'no change' on key-A items), within-shard
  duplicate contexts.
- Dedup: exact + fuzzy (Jaccard >= 0.75 / difflib >= 0.85) within the 1,000 and against the live bank -> 0 hits
  (max observed within-standard similarity 0.50).
- Global: unique content-hashed IDs, letter balance 25% +/- 3 with chi-square, NO CHANGE rate, 12 hints per
  question, rung-1 opener diversity (top opener <= 20%).

## Notes
- `reviewed` is `false` on every row: items are machine-generated and validator-gated but not yet
  human-reviewed. Flip per item after review, as with the seed pipeline.
- Hint schema = seed schema + `choice_letter` (which wrong option the ladder targets) and `rung` 1-4
  instead of 1-3. Ladders follow pump -> hint -> prompt -> assertion; rung 4 states the rule but never the key.
- Standard IDs 1-32 follow the live bank; 33-43 are new standards covering the gaps flagged in the
  bucket-weights research (add/delete, essay purpose, intro/conclusion, ordering, division, modifiers,
  colons, unnecessary punctuation, precision, register).
