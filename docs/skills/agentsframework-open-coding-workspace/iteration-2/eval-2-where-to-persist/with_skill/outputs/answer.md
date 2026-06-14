# Where to put your coded traces in Langfuse

**Short answer: use a Langfuse _dataset_ — not scores, not an annotation queue.**

A dataset gives you exactly what you asked for: one item per case showing the
task, the agent's final answer, and your codes, all on one paginated screen, with
a link back to the full trace for drill-down. It's the read/review surface. You
keep editing codes in the local HTML coder (the write surface) and re-run the
exporter; items update in place. This repo already has the scripts to do it.

## Why a dataset and not the other two

This was decided the hard way in this repo while coding 11 planning-depth traces
(see `docs/skills/agentsframework-open-coding/references/langfuse-surface.md`).

| Surface | What review actually looks like | Verdict |
|---|---|---|
| **Dataset** | One item per case: task = `input`, answer = `expected_output`, codes + memo = `metadata`, `source_trace_id` links to the trace. All together, paginated, shareable link. | **Use this.** |
| **Scores** | A score binds to a single observation, so `open_code` scatters across `run.started` / `step.0` / `step.executed` on one trace. No single screen shows task + answer + all codes. (Bonus trap: TEXT scores read back from `string_value`, not `.value`, which is `None`.) | Scattered — fine for filtering, useless for joint review. |
| **Annotation queue** | The drawer opens on the trace's _top_ observation (`run.started`) — which carries run/thread ids, **not** the prompt or the answer, i.e. the two things you both need to read. API-pushed scores hide behind a toggle. The Hobby plan caps you at **one** queue, so you can't even keep a queue per session. | Wrong content + capped. |

Scores are the right tool when you want to *filter* ("show all traces where
`open_code` contains X") in the Langfuse UI. They're the wrong tool for "let's sit
down and read these 15 cases together," which is what you described.

## The division of labor that works

- **HTML coder = write/edit surface.** Tag, re-tag, memo. Local, fast, no network
  round-trip per keystroke. This is where you and your teammate change codes.
- **Langfuse dataset = read/review surface.** Paginated, task + answer + codes
  together, shareable, trace back-link. **Don't edit codes in Langfuse** — edit in
  the coder, Save, re-export (idempotent, items update in place).

## Walkthrough for your ~15 traces (exact paths/commands)

Run everything from the repo root, and use `.venv/bin/python` — this repo is
Python 3.13 and the system `python` will throw `int | None` syntax errors. Use
**this skill's** bundled scripts by full path; the top-level
`scripts/serve_open_coder.py` and `scripts/export_depth_cases_to_dataset.py` are
the older planning-depth-hardcoded ancestors and won't take the `--dir/--dataset`
flags below.

### 0. Make a session work dir and drop in the coder

```bash
WORK=cache/open_coding/team-review            # any path you like
mkdir -p "$WORK"
cp docs/skills/agentsframework-open-coding/assets/coder.html "$WORK/coder.html"
```

The coder is generic — it fetches its cases from the server, so you never
hand-edit the HTML. You only edit `cases.json`.

### 1. Build the cases JSON (one row per trace)

Write your 15 traces to `$WORK/cases.json` as an array, one object per trace.
Minimum per row is `trace_id` + `prompt`; include `final_answer` so the card and
the dataset's `expected_output` are populated. Schema + worked example:
`docs/skills/agentsframework-open-coding/assets/cases.schema.json`; a 3-row
starter: `docs/skills/agentsframework-open-coding/assets/sample_cases.json`.

```json
{
  "trace_id": "7c71871fb0...",
  "stratum": "batch-1",
  "prompt": "the task given to the agent",
  "final_answer": "the agent's last message",
  "goal_met": false,
  "partial_fraction": 0.5,
  "trajectory": [{"ev": "step.planned"}, {"ev": "error.occurred", "tool": "shell"}],
  "rationale": "judge's reasoning (optional)"
}
```

Any extra keys you add (family, severity, model…) survive the round-trip into
dataset item metadata, so attach now whatever you'll want to filter on later.
`want_depth`/`fired_depth` are GoalJudge-specific — drop them unless this is a
planning-depth set.

### 2. Serve the coder

```bash
python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py --dir "$WORK"
# add --port 3118 if 3117 is busy
```

Open **http://localhost:3117/coder.html**. Always serve over http — never open
the `.html` as a `file://`, or the Save button's POST to `/save` fails silently
and your codes end up only as a browser download. The server also serves prior
codes back at `/load`, validates each saved line, refuses a save that shrinks the
file below 50% of existing rows (unless `?force=1`), and writes a timestamped
backup on every save.

### 3. Code in the browser (you, by hand — not the LLM)

Per card: read the task, expand the answer + judge rationale, glance at the
trajectory counts, then type a short code and **press Enter** to commit it as a
chip. Add a memo for nuance. Good codes are short and behavioral —
`fabricated-progress`, `tool-error-unhandled`, `clarification-instead-of-action`.
Click **Save to disk** to write `$WORK/coded.jsonl`.

Open coding is a human noticing what the trace _did_ vs what the agent _claimed_.
Don't auto-generate first-pass codes with an LLM; that comes later in axial coding.

### 4. Verify the JSONL (the one trap that bites everyone)

The #1 failure mode: prose in the memo, `open_codes` empty — because codes only
persist if you press **Enter** to chip them; a comma-list typed into the memo box
does not populate `open_codes`. Check before exporting:

```bash
.venv/bin/python -c "import json; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

(The exporter's dry run prints the same count, so you'll catch it either way.)

### 5. Export to a dataset — dry run first

```bash
EXPORT=docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py

# dry run (default) — prints what it would write + the NO-codes count
.venv/bin/python "$EXPORT" --dataset team-review --coded "$WORK/coded.jsonl"

# actually push, once the dry run looks right
.venv/bin/python "$EXPORT" --write \
    --dataset team-review \
    --coded "$WORK/coded.jsonl" \
    --meta-keys stratum,goal_met,severity
```

Each item lands as `input={task,...}`, `expected_output=final_answer`,
`metadata={open_codes, memo, ...--meta-keys}`, plus a `source_trace_id` back-link.
The item id is `uuid5(trace_id)`, so **re-running updates the same items** rather
than duplicating. If your `final_answer` lives in a separate corpus instead of on
the coded rows, join it with `--answers path/to/rich.jsonl`. Needs creds in `.env`
(`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST`; default EU host
— a stray `us.` host 502s).

### 6. Review together and iterate

Open the dataset in Langfuse (`/project/<id>/datasets/<dataset-id>`). You and your
teammate get all ~15 cases in one paginated table, task + answer per row, codes in
metadata, trace link for drill-down. To change a code: edit in the **coder**,
Save, re-run step 5 — items update in place. The dataset is read-only review; the
coder is where edits happen.

## TL;DR

Dataset, not scores or an annotation queue. Code in the local HTML coder
(`serve_open_coder.py --dir $WORK`), then push to a Langfuse dataset with
`export_coded_to_dataset.py --write --dataset team-review`. Dry-run first, verify
`open_codes` is non-empty, and re-export any time you refine codes — it's
idempotent. The full mechanics live in
`docs/skills/agentsframework-open-coding/SKILL.md`.
