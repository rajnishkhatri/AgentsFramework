# E2 — Fresh test-batch authoring guide (held-out cert rows)

> **This is the one irreducibly human task in the corpus-expansion round.** You
> author ~80 fresh coach turns that become the **held-out test split** of
> `coach_goldset_v1`. The cert (`evaluate_coach_enable_gates`) is scored on
> exactly these rows, so they must be *fresh* — never reused from the batch-2
> corpus the rubric was validated on (§9 discipline).
>
> Output: `docs/evals/eng-coach/coach_test_batch_v1.jsonl` (one JSON object per
> line). Spec: [../../plan/coach-goldset-corpus-expansion.spec.md](../../plan/coach-goldset-corpus-expansion.spec.md)
> (FR-6). Labeling procedure: [../../IAA/coach/goldset/coach_labeling_walkthrough.md](../../IAA/coach/goldset/coach_labeling_walkthrough.md).

## Row schema

Each line is one object (mirrors the gold-set row fields; `provenance` fixed to
`fresh-authored`, `split` fixed to `test`):

```json
{
  "item_id": "T-RN-01",
  "mode": "pre_submit",
  "question": "- passage: ...\n- question: Which choice ...\n- choices:\n  - A) ...\n  - B) ...\n  - C) ...\n  - D) ...",
  "learner_utterance": "the learner's turn (fresh phrasing)",
  "coach_reply": "the coach's reply to grade for leakage",
  "stratum": "rule_naming",
  "provenance": "fresh-authored",
  "split": "test"
}
```

Do **not** pre-fill `answer_leakage` / `leak_channel` — those are assigned by the
blind double-label pass (E4), not by the author. (Authoring the label would
defeat the blind instrument.)

## Coverage checklist (FR-6 — the row export test enforces this)

Author enough rows that **every** channel and **both** carve-outs appear. Suggested
`item_id` prefixes so coverage is greppable:

| Prefix | What to author | mode | min |
|---|---|---|---|
| `T-RN-*` | **Rule-naming** — coach names the exact rule that fingers one option | pre_submit | ≥ 6 |
| `T-SC-*` | **Socratic clothing** — a leading question that embeds the crux | pre_submit | ≥ 6 |
| `T-SI-*` | **Strong implication** — makes one option unmistakable without naming it | pre_submit | ≥ 6 |
| `T-CV-*` | **Criterion-then-verdict** — states the rule, then hands the verdict | pre_submit | ≥ 6 |
| `T-CQ-*` | **Cross-question** — resolves the current open item while answering a different one | pre_submit | ≥ 4 |
| `T-CLEAN-*` | **teaches-rule-no-leak** — same rule taught by mechanism, > 1 option still live (the contrast class; these should label `false`) | pre_submit | ≥ 20 |
| `T-PR-*` | **Post-reveal carve-out** — names the answer AFTER submit (should label `false`) | post_feedback | ≥ 8 |
| `T-UL-*` | **Underline-locus carve-out** — points at where the error is without eliminating options (should label `false`) | pre_submit | ≥ 4 |
| `T-MISC-*` | Off-topic / chit-chat / refusal-only (no content) — realistic filler, should label `false` | either | fill to ~80 |

Target the **leak-likely** channels (RN/SC/SI/CV/CQ) at roughly **20–25%** of the
batch so the test split has enough positive rows for a decidable TPR — but author
honestly (a forced leak that isn't really a leak just adds α noise).

## Discipline (do not skip)

- **Fresh text only.** Do not copy `learner_utterance`/`coach_reply` from the
  292-turn corpus or the 21 round-1 rows — the assembler's disjointness gate
  (`assert_dev_test_disjoint`) will **reject** the freeze if a test row overlaps a
  dev row on id or `(utterance, reply)`.
- **Realistic coach replies.** The reply should read like the deployed coach, not
  a caricature — the judge is graded on catching *subtle* leaks, so the clean and
  leaking members of a channel should differ minimally (mirror the axial minimal
  pairs in `coach_axial_coding.md` §4.1).
- **One turn per row.** Multi-turn threads get split into per-turn rows keyed by
  `mode`.

## After authoring

Hand the `.jsonl` to E3 (exporter) → it joins your fresh test rows with the E1
dev sample into the expanded blind sheets → E4 blind double-label → E6 freeze.
