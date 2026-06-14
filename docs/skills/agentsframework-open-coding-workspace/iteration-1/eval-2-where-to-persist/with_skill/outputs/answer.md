# Where to persist a coded trace-set in Langfuse — recommendation + walkthrough

## Short answer

Use a **Langfuse dataset** — one item per case. Not scores, not an annotation queue.

A dataset is the only Langfuse surface that shows, **for every case on one paginated
screen**: the task (item `input`), the agent's answer (`expected_output`), and your
codes (item `metadata`), with a `source_trace_id` link back to the full trace. That is
exactly the "see each task, the agent's answer, and the codes, all in one place" view
you described, and it is shareable with your teammate.

You should **not** edit codes directly in Langfuse, though. The right division of labor
in this repo is:

- **HTML coder (local) = the write/edit surface.** You and your teammate tag, re-tag,
  and memo here.
- **Langfuse dataset = the read/review surface.** Page through, drill into traces,
  discuss.

To change codes later: edit in the coder → Save → re-run the exporter. The export is
**idempotent** (item id is `uuid5` of the trace id), so re-running updates the same
items in place — no duplicates, no manual cleanup.

## Why not scores or an annotation queue

This was settled the hard way coding 11 planning-depth traces (see
`docs/skills/agentsframework-open-coding/references/langfuse-surface.md`):

| Surface | What review actually looks like | Verdict |
|---|---|---|
| **Dataset** | One item per case: task + answer + all codes together, paginated, with a trace back-link. | Use this. |
| **Trace Scores tab** | A score binds to one *observation*, so `open_code` scatters across `run.started` / `step.0` / `step.executed` on a single trace. No one place shows task + answer + all codes. Fine for "filter all traces where code contains X"; useless for case-by-case review. | Scattered. |
| **Annotation queue** | The drawer opens on the trace's *top* observation (`run.started` — carries run/thread ids, **not** the prompt or final answer, the two things you need to code against). API-pushed scores are collapsed behind a toggle. The Hobby plan caps you at **one** queue, so you can't even keep a queue per session. | Wrong content + capped. |

There's also a scores read-back trap: a TEXT score's value lives in `string_value`, not
`.value` (which is `None` for TEXT). Datasets sidestep this entirely — codes are plain
item metadata.

So scores aren't *wrong*, they're just the wrong tool for **human review**. Keep them in
mind only if you later want UI-side filtering across many traces. For ~15 hand-coded
cases that you and a teammate read together, a dataset wins outright.

## The walkthrough in this repo

The mechanics are already built and parameterized for any coding session — the scripts
live under `docs/skills/agentsframework-open-coding/`. Pick a working dir (anywhere; the
planning-depth session used `cache/goaljudge_eval/open_coding/`). Below, `$WORK` is that
dir.

### 1. Build the cases JSON (one row per trace)

Each row carries enough to code without leaving the page. Minimum is `trace_id` +
`prompt`; in practice include the answer and outcome signals. Pull these from your trace
store by `trace_id`:

```json
{
  "trace_id": "7c71871fb0...",
  "stratum": "batch-1",
  "prompt": "the task given to the agent",
  "final_answer": "the agent's last message",
  "goal_met": false,
  "partial_fraction": 0.5,
  "trajectory": [{"ev": "step.planned"}, {"ev": "error.occurred", "tool": "shell"}],
  "rationale": "judge's reasoning (optional context)"
}
```

Schema + a worked example:
`docs/skills/agentsframework-open-coding/assets/cases.schema.json` and
`assets/sample_cases.json`. Two notes:

- **Any extra keys survive the round-trip** into dataset item metadata. Put whatever
  you'll want to filter/group on later (family, severity, model) right on the row.
- `want_depth`/`fired_depth` are GoalJudge-specific (they drive a depth badge). For a
  generic coding session, just drop them — the badge only renders when both are present.

Write the array to `$WORK/cases.json` and copy the coder next to it:

```bash
cp docs/skills/agentsframework-open-coding/assets/coder.html "$WORK"/coder.html
# ...write your cases array to "$WORK"/cases.json...
```

### 2. Serve the coder (always over http, never file://)

```bash
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py \
    --dir "$WORK"            # serves on :3117
```

Open `http://localhost:3117/coder.html`. **Do not** open the `.html` as a `file://` —
the Save button POSTs to `/save`, and on `file://` that fetch fails
(`Failed to parse URL from /save`) and silently falls back to a browser download, so
your codes end up only in `~/Downloads`. The server also:

- serves your cases on `GET /cases` and restores prior codes on `GET /load` (so
  reopening the page resumes where you left off);
- **validates** every saved line is JSON with a `trace_id`;
- **refuses a save that shrinks the file below 50%** of existing rows unless `?force=1`
  (this guard exists because a stray `curl /save` once clobbered a fully-coded file with
  the literal string `probe`);
- writes a **timestamped backup** on every save.

### 3. Code in the browser (human codes, not the LLM)

For each card: read the task, expand the answer + judge rationale, glance at the
trajectory counts, then type a short code and **press Enter** to commit it as a chip.
Add a memo for nuance. Good codes are short, descriptive, behavioral —
`fabricated-progress`, `clarification-instead-of-action`, `tool-error-unhandled`,
`claim-without-tool-evidence`. They name *what happened*, not the fix.

Do not auto-generate first-pass codes with an LLM. The whole point of open coding is a
human noticing what the trace *did* versus what the agent *claimed*. The LLM proposes
structure later, in axial coding — not here. (Two people coding the same ~15 cases
independently, then reconciling, is exactly the right use of "review them together.")

### 4. Verify the JSONL (the one trap that bites everyone)

**The most common failure: memos full of prose, `open_codes` empty.** Codes only persist
if you pressed Enter to chip them; a comma-list typed into the memo box does *not*
populate `open_codes`. Check before exporting:

```bash
.venv/bin/python -c "import json; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

(Use `.venv/bin/python`, not system `python` — this repo is Python 3.13 and the scripts
use `int | None` syntax.)

### 5. Export to a dataset — dry run first, then `--write`

```bash
# dry run (default): prints exactly what it would push, writes nothing
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py \
    --dataset batch-1-open-coding \
    --coded "$WORK"/coded.jsonl

# real push, once the dry run looks right
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py --write \
    --dataset batch-1-open-coding \
    --coded "$WORK"/coded.jsonl \
    --meta-keys stratum,goal_met,severity
```

Flags that matter:

- `--dataset` — dataset name, created if absent.
- `--coded` — the coded JSONL from the coder.
- `--answers` — optional second JSONL to join `final_answer` by `trace_id`, for when
  the coded file doesn't carry the answer but a rich corpus does. If your coded rows
  already have `final_answer` (they will if you put it in `cases.json`), omit this.
- `--meta-keys` — which row keys to copy into item metadata. `open_codes` and `memo` are
  always included.
- `--id-keys` — extra row keys to fold into the item `input` alongside `task`.

Each item lands as: `input={task, ...id-keys}`, `expected_output=final_answer`,
`metadata={open_codes, memo, ...meta-keys}`, plus a `source_trace_id` back-link. The
dry run is the default precisely because `--write` annotates a real Langfuse project —
eyeball it first. The exporter also re-warns you if any row has empty `open_codes`.

Credentials come from the repo `.env` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_HOST`). Default host is EU `https://cloud.langfuse.com`; a stray `us.` host
502s. The exporter loads `.env` itself and uses the repo's
`scripts/langfuse_dataset_client.py` (same client as the compliance-audit / incident-replay
flows), so run it from the repo root.

### 6. Review together, then iterate

Open `/project/<id>/datasets/<dataset-id>` in Langfuse and share the link. You both get
the full case-set in one paginated table — task + answer per row, codes in metadata,
trace back-link for drill-down. When you want to change codes after discussion: edit in
the **HTML coder**, Save, re-run the exporter. The same items update in place. The
dataset is the *read* surface; the coder is the *write* surface — don't try to edit codes
in Langfuse.

## TL;DR for your 15 traces

1. Build `cases.json` (15 rows: trace_id, prompt, final_answer, outcome signals).
2. `serve_open_coder.py --dir $WORK`, open over http, code each card (Enter-commit chips).
3. Verify `open_codes` is non-empty.
4. `export_coded_to_dataset.py` dry run, then `--write --dataset <name>`.
5. Share the dataset URL with your teammate; re-edit in the coder and re-export to refine.

Reuse the bundled, parameterized scripts under
`docs/skills/agentsframework-open-coding/` — don't hand-roll scores or a queue.
