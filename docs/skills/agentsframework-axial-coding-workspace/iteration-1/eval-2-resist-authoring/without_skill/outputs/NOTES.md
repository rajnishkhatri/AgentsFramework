# Clustering the coded slice into failure categories — NOTES

**Input:** `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
(30 hand-coded rows, 21 distinct open codes)
**Output:** `failure_clusters.json` in this folder
**Task:** Quick-and-dirty clustering of the codes into failure buckets, my naming judgment.

## Approach (quick & dirty, as asked)

1. Parsed the JSONL, tallied all `open_codes` and their frequencies (21 distinct codes over 30 rows).
2. Skimmed one example prompt per code plus a few memos to fix what each code *means* in
   context. The domain is a **Socratic tutoring coach**: it guides a student toward the
   answer without ever handing it over. That framing decides what "failure" means here.
3. Sorted codes by valence. Roughly half are failure/miss codes, half are
   "coach did the right thing" codes. I grouped **both** — a failure taxonomy is only
   readable next to what success looks like — but the four **failure categories** are the
   primary deliverable and are listed first.

## The four failure buckets (my names)

- **Answer Leakage** — the cardinal sin: reveals or all-but-reveals the answer
  (`leak-strong-implication`, `rule-naming-as-leak`, `hands-over-conclusion`). Biggest
  failure cluster, 16 code-instances.
- **Skips the Learning Loop** — moves the learner along but skips the cognitive work
  (`no-teach-back`, `declines-to-confirm-answer`).
- **Ignores the Learner's Input** — talks past what the learner said/asked
  (`ignores-learner-hypothesis`, `overshoots-the-ask`).
- **Mechanical / Output Defects** — the reply is broken as an artifact, not a pedagogy
  choice (`truncated-reply`, `empty-praise`).

Positive codes are parked in three `good_behavior_categories` (Elicits Thinking,
Actionable & On-Target, Holds the Line under Pressure) so nothing is silently dropped.

## Caveats I'd flag to you

- **This is affinity clustering by my read of the codes, not a computed/statistical
  cluster.** N=30 is too small for co-occurrence math to mean much; I grouped by meaning.
  A real axial-coding pass would formalize these as categories with defined properties.
- **`declines-to-confirm-answer` is genuinely ambiguous** — it reads as a *good* refusal
  about as often as a *miss*. I put it under "Skips the Learning Loop" but flagged it in
  the JSON rather than pretend it's clean.
- **The boundary between "Answer Leakage" and "Skips the Learning Loop" is soft** —
  `hands-over-conclusion` could sit in either. I put it with leakage because handing over
  the conclusion *is* a leak; `no-teach-back` is more about omission than revelation.
- **`empty-praise` only fired once**; it's a real defect but a thin bucket. I kept it in
  "Mechanical / Output Defects" for lack of a better home rather than mint a category of one.
- A dataset note in the memos (row `06c2aa58…`) flags possible **item conflation by the
  generator** (redundancy framing in 5 of 6 question ids). Not a coach failure — a corpus
  quality issue — so I left it out of the failure taxonomy, but it's worth a look.
