# Where to put ~15 coded traces in Langfuse for shared review

## Short answer

Use a **Langfuse dataset** — one item per trace — as the shared review surface.
Do **not** use Langfuse scores or an annotation queue for the "see task + answer +
my codes on one screen, review together, edit later" workflow you describe.

Scores and annotation queues each fail on one of your three requirements
(everything-in-one-place, review-together, edit-later). A dataset satisfies all
three, and this repo already has the tooling to push one.

## Why a dataset, mapped to what you asked for

You want three things. Here's how each surface scores:

| You want… | Dataset | Scores | Annotation queue |
|---|---|---|---|
| Task + agent answer + your codes **in one place** | Yes — one item per case: `input` = task, `expected_output` = the agent's final answer, `metadata` = your codes + memo | No — a score attaches to a single *observation*, not the trace as a whole, so codes scatter across `run.started` / `step.N` / `step.executed` and nothing shows the task, the answer, and all codes together | No — the queue drawer opens on the trace's **top** observation (`run.started`), which carries run/thread ids, **not** the prompt or the final answer — the two things you actually code against |
| You and a teammate **review together** | Yes — paginated list, one shareable project link, each item links back to its full trace via `source_trace_id` for drill-down | Poor — you'd be clicking trace-by-trace, hunting the Scores tab on each | Capped — Langfuse's Hobby/free plan allows only **one** annotation queue, so you can't even keep a session's worth separate; and the codes you push via API land collapsed behind a detail toggle |
| **Edit codes later** | Yes (with the right loop — see below) | Awkward — a TEXT score's text lives in `string_value`, not `.value` (which is `None` for TEXT), so reading/editing them back is a footgun | Same scatter/visibility problem |

Net: **scores are built for filtering** ("show me all traces where the judge
score < 0.5"), not for *reading a case set*. **Annotation queues are built for a
human grading queue against the live trace view**, not for reviewing pre-coded
free-text codes. A **dataset is a curated, paginated, shareable collection of
cases** — which is exactly what a coded trace-set is.

## The one catch — and how this repo already solves it

The honest caveat: **a Langfuse dataset is not an in-place editor.** You don't
re-tag codes by typing into the Langfuse UI. So the workflow that actually works
is a two-surface split, and the repo is already built around it:

- **Write/edit surface (local):** the HTML open-coder. You tag, re-tag, and write
  memos there. It saves a coded JSONL to disk. No network round-trip per
  keystroke.
- **Read/review surface (Langfuse):** the dataset. Paginated, everything-together,
  shareable, with trace back-links for drill-down.

To **edit codes later**: change them in the coder → Save → re-run the exporter.
The exporter is **idempotent** (each item id is `uuid5(trace_id)`), so re-running
updates items in place rather than duplicating. You never edit codes inside
Langfuse; you re-sync from the coder. Your teammate reviews in the dataset; you
both agree on changes; you apply them in the coder and re-push.

## Concrete walkthrough in this repo

The repo already has the exporter for this exact job:
`docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
(it wraps `scripts/langfuse_dataset_client.py`, the repo's standard
`RealLangfuseDatasetClient`, EU host by default — `cloud.langfuse.com`, **not**
`us.cloud.langfuse.com`, which has bitten past sessions with 502s).

**1. Get your codes into the coded-JSONL shape.** The HTML coder
(`docs/skills/agentsframework-open-coding/assets/coder.html`, served by
`scripts/serve_open_coder.py` on `:3117`) emits one JSON object per line with at
least:

```json
{"trace_id": "<full-32+-char id>", "prompt": "<task>", "open_codes": ["code-a", "code-b"], "memo": "rationale", "final_answer": "<agent answer>"}
```

Two things to verify before pushing:
- **Full trace ids.** Codes only match a Langfuse trace if `trace_id` is the full
  id (≥32 chars). Short/truncated ids silently won't match.
- **Codes are committed as chips, not just typed.** In the coder, a code only
  lands in `open_codes` if you Enter-commit it as a chip. Text left in the memo
  box is *not* a code. The exporter warns about rows with empty `open_codes` — heed it.

If your final answers live in a separate corpus file, the exporter can join them
in by `trace_id` via `--answers`.

**2. Dry-run the export (writes nothing):**

```bash
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py \
    --dataset my-coding-session \
    --coded path/to/coded.jsonl
```

Confirm the printed item count is ~15 and the codes look right. (If you need the
agent answers joined: add `--answers path/to/rich.jsonl`.)

**3. Push for real:**

```bash
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py --write \
    --dataset my-coding-session \
    --coded path/to/coded.jsonl \
    --answers path/to/rich.jsonl \
    --meta-keys stratum,goal_met        # any row keys you want as filterable item metadata
```

Each item becomes: `input.task` = the prompt, `expected_output` = the agent's
final answer, `metadata.open_codes` + `metadata.memo` = your codes, plus
`source_trace_id` linking back to the full trace.

**4. Review together.** Both of you open
`https://cloud.langfuse.com` → **Datasets** → `my-coding-session`. You get the
paginated list — task, answer, codes per item — and click `source_trace_id` on
any item to drill into the full trace.

**5. Edit codes later.** Re-open the coder, change the chips/memos, Save, re-run
step 3. Items update in place (same `uuid5(trace_id)` id). Done.

## When the other surfaces *are* right (so you're not surprised later)

- **Scores** — once your emergent codes stabilize into a fixed taxonomy and you
  want to *filter/aggregate* traces by code in the Langfuse UI (or gate a batch
  on them). The repo even has `scripts/push_open_codes_to_langfuse.py` that pushes
  codes as TEXT scores for exactly that filtering use case. It's complementary,
  not a substitute for the review dataset. Promote to a CATEGORICAL score config
  when the taxonomy is locked.
- **Annotation queue** — when you want a *fresh* human-grading workflow where a
  reviewer grades against the live trace view (not pre-assigned free-text codes),
  and you're not on the one-queue Hobby cap.

For your stated goal — co-review ~15 already-coded traces, everything on one
screen, editable later — the **dataset** is the right surface, and the repo's
`export_coded_to_dataset.py` is the tool. (Per the task constraint, nothing was
pushed to Langfuse here.)

## Files referenced

- `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py` — the dataset exporter (idempotent, joins answers)
- `scripts/langfuse_dataset_client.py` — `RealLangfuseDatasetClient` / `build_real_langfuse_dataset_client` (EU host default)
- `scripts/serve_open_coder.py` + `docs/skills/agentsframework-open-coding/assets/coder.html` — the local write/edit surface
- `scripts/push_open_codes_to_langfuse.py` — codes-as-TEXT-scores pusher (the *filtering* path, not review)
- `docs/skills/agentsframework-open-coding/references/langfuse-surface.md` — repo's prior decision record on this exact question
