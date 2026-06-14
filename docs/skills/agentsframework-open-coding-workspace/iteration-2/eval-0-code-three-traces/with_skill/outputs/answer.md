# Open-coding three traces — your walkthrough

You wanted to hand-code three agent traces and end up with all three reviewable
together in a Langfuse dataset, taken right up to (but not including) the
`--write` push. Here's the setup I built and exactly how to drive it.

Skill followed: `docs/skills/agentsframework-open-coding/SKILL.md` (the 6-step
loop). I used the skill's **bundled** scripts by full path, not the repo's older
top-level `scripts/serve_open_coder.py` / `scripts/export_depth_cases_to_dataset.py`
(those are planning-depth-hardcoded and don't take the `--dir/--dataset/--coded`
flags this session needs).

## What's already done

- **Session work dir:** `cache/open_coding/code-three-traces/`
  - `coder.html` — copied from the skill's `assets/coder.html` (generic; never hand-edited)
  - `cases.json` — your 3 cases, copied from
    `docs/skills/agentsframework-open-coding/assets/sample_cases.json`
- I verified the server, the `/cases` + `/save` + `/load` round-trip, the
  truncation guard, the timestamped backup, the Step-4 verify one-liner, and the
  Step-5 **dry run** all work. Then I stopped the server and reset the work dir to
  a clean start state (just `coder.html` + `cases.json`), so when you first press
  Save you get a genuine blank slate — I did **not** fabricate any codes
  (Cardinal rule 2: the human codes first).

The three cases you'll be coding (all `want L1/L2 → fired L0` depth-misses):

| trace_id (short) | task | goal_met |
|---|---|---|
| `e68552dd…` | Design a rate limiter for the API | true |
| `2c0f3fceb1…` | Refactor the auth module | false |
| `9d2c84fb4a…` | Compare Redis vs Memcached, (1)(2)(3) then recommend | false |

## Step A — Start the coder

The repo already has a stale server squatting on the default port **3117** (not
mine — I left it alone), so this session runs on **3118**:

```bash
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py \
    --dir cache/open_coding/code-three-traces --port 3118
```

Then open **http://localhost:3118/coder.html** in a browser.

> Always over `http://` — never open the `.html` as a `file://`. On `file://` the
> Save button's POST to `/save` fails and silently falls back to a `~/Downloads`
> file. The server also validates each saved row, refuses a save that shrinks the
> file below 50% (pass `?force=1` to override), and writes a timestamped backup on
> every save.

## Step B — How to tag codes and save (the part that trips people up)

For each of the 3 cards: read the task, expand **answer + judge rationale**,
glance at the trajectory event counts and the `goal_met` / `want→fired` badge,
then code what the trace actually *did*.

- Type a short code in the **"add open code, press Enter"** box and press
  **Enter**. Each Enter turns the text into a chip. That — and only that —
  populates `open_codes`.
- **The trap:** typing a comma-list into the **memo** box does NOT create codes.
  The memo is free-text nuance only. If your codes live in the memo, `open_codes`
  stays empty and the export writes blank-coded items.
- Click the **×** on a chip to remove it. Add a memo for anything a code can't
  capture.
- Click **Save to disk**. You should see `saved to disk: 3 rows -> coded.jsonl`.
  That writes `cache/open_coding/code-three-traces/coded.jsonl`. (Codes also
  autosave to `localStorage` on every keystroke, and reopening the page restores
  them via `/load`.)

Good open codes are short, behavioral, and name *what happened* — not a fix.
For these three the obvious candidates are things like:
`clarification-instead-of-action` (case 2 asked for more info instead of
refactoring), `subagent-result-lost` / `claim-without-tool-evidence` (case 3's
tool errors swallowed the results), `depth-under-plan` (all three wanted L1/L2 but
fired L0). Type your own — don't overthink consistency; you merge/rename later in
axial coding.

## Step C — Verify before exporting (Step 4)

The single most common failure is memos full of prose with `open_codes` empty.
After Save, confirm every row you meant to code actually has codes:

```bash
WORK=cache/open_coding/code-three-traces
.venv/bin/python -c "import json,sys; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

You want `3 rows, 0 with NO codes`. If any trace_id shows up in `uncoded`, go
back to the browser and Enter-commit codes for it.

## Step D — Dry run the dataset export (right up to `--write`)

This is the line you stop at. Dry run is the default (no `--write`), so it only
prints what it *would* push:

```bash
EXPORT=docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py
.venv/bin/python "$EXPORT" \
    --dataset code-three-traces \
    --coded cache/open_coding/code-three-traces/coded.jsonl \
    --meta-keys stratum,trigger_family,want_depth,fired_depth,goal_met
```

It prints `N cases -> dataset 'code-three-traces' (X with NO codes)`, a warning
banner if any rows are uncoded, and a `[would write] '<task>' codes=[...]` line
per case, ending with `DRY RUN — nothing written.` Eyeball that the codes column
shows what you tagged.

I ran this dry run already (against the uncoded baseline, since you haven't tagged
yet) and it behaved exactly as documented — see `transcript.md`.

## Step E — The actual push (NOT done — your call)

When the dry run looks right, the same command with `--write` creates the dataset
(if absent) and one item per case, idempotently (item id = `uuid5(trace_id)`, so
re-running updates in place):

```bash
.venv/bin/python "$EXPORT" --write \
    --dataset code-three-traces \
    --coded cache/open_coding/code-three-traces/coded.jsonl \
    --meta-keys stratum,trigger_family,want_depth,fired_depth,goal_met
```

I deliberately stopped before this. Each dataset item lands as
`input={task}`, `expected_output=final_answer`,
`metadata={open_codes, memo, ...meta-keys}`, with a `source_trace_id` back-link.

## Step F — Review and iterate

After `--write`, open the dataset in Langfuse
(`/project/<id>/datasets/<dataset-id>`): all three cases in one paginated table,
task + answer visible, codes in metadata, trace back-link for drill-down. To
change codes, edit in the **HTML coder** (the write surface), Save, re-run the
exporter — the dataset is read-only review, the coder is where you edit.

A dataset is the right surface (not per-trace Scores, not an annotation queue) —
the reasoning is in `docs/skills/agentsframework-open-coding/references/langfuse-surface.md`.

## Environment notes

- Langfuse creds come from the repo `.env` (`LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`; default EU `https://cloud.langfuse.com`
  — a `us.` host 502s). The exporter loads `.env` itself.
- Always `.venv/bin/python` (Python 3.13), never system `python`, or you'll hit
  `int | None` syntax errors in the imported client.
