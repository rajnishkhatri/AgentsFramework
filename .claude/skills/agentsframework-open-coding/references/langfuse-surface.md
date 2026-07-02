# Why a dataset, not scores or an annotation queue

Decided 2026-06-14 the hard way, coding 11 planning-depth traces. We tried all
three Langfuse surfaces for reviewing a coded case-set. Use a **dataset**.

## The contenders

| Surface | What it shows for review | Verdict |
|---|---|---|
| **Dataset** | One item per case: task (input) + answer (expected_output) + codes (metadata), all together, paginated. `source_trace_id` links back to the trace. | ✅ **Use this.** |
| **Trace Scores tab** | Scores attach **per observation**, so `open_code` scatters across `run.started` / `step.0` / `step.executed` on a single trace. No one place shows task + answer + all codes. | ✗ scattered |
| **Annotation queue** | The drawer shows the **top observation** (`run.started` — only run_id/thread_id, not the task or answer) and hides API-pushed scores behind a detail toggle. Hobby plan caps queues at **1**. | ✗ wrong content + capped |

## Why scores lose for *review* (they're fine for filtering)

A Langfuse score is bound to one observation. Push `open_code` and it lands on
whatever observation you target; the trace's Scores tab then lists scores
interleaved across the trace's observations. Good for "filter all traces where
`open_code` contains X" in the UI. Useless for "show me case 7's task, the
agent's answer, and everything I coded about it on one screen."

Reading a TEXT score back has its own trap: the value is in `string_value`, not
`.value` (which is `None` for TEXT). Datasets sidestep this — codes live in plain
item metadata.

## Why the annotation queue loses

The queue item points at a trace and opens a drawer on the trace's top
observation. For an agent run that's `run.started`, which carries run/thread ids
but not the prompt or the final answer — exactly the two things you need to code
against. The codes you pushed via the API are present but collapsed behind a
toggle. And the Hobby plan allows only one queue, so you can't even keep separate
queues per coding session.

## The division of labor that works

- **HTML coder = the write/edit surface.** Tagging, re-tagging, memos. Local,
  fast, no network round-trip per keystroke.
- **Langfuse dataset = the read/review surface.** Paginated, task + answer +
  codes together, shareable link, trace back-link for drill-down.

To change codes: edit in the coder → Save → re-run the exporter (idempotent, so
items update in place). Don't try to edit codes in Langfuse.
