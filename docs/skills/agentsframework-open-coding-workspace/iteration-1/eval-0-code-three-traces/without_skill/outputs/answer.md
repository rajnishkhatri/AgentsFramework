# Open-coding your three traces, then into a reviewable Langfuse dataset

You're set up. The coder is running, all three cases load, the save round-trip is
verified, and I've taken the pipeline right up to (but not through) the Langfuse
`--write`. Here's exactly what's live and what you do next.

---

## What I did for you

1. Made a work directory and put the two files the coder server expects into it
   (it reads `coder.html` + `cases.json` by those exact names):
   - `outputs/coder.html` (copied from the skill asset)
   - `outputs/cases.json` (your `sample_cases.json`, renamed — 3 cases)
2. Started the coder server (see "Gotcha" below for which script).
3. Verified the three routes: `GET /coder.html` (200), `GET /cases` (3 cases),
   `GET /load` (empty before any save).
4. Did a first hand-coding pass on all three traces and saved it, to prove the
   Save button's round-trip works. **These are my codes — overwrite them with
   yours in the browser.** They're a starting draft, not the final analysis.
5. Ran the Step-4 verification (`0 rows with NO codes`) and the export **dry run**.
   Stopped there. Nothing was written to Langfuse.

---

## 1. The coder is already running

```
http://localhost:3119/coder.html
```

Open that in your browser. You'll see three cards, one per trace. If the page is
ever not running, restart it with **the skill's parameterized script** (not the
repo-root one — see Gotcha):

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py \
  --dir docs/skills/agentsframework-open-coding-workspace/iteration-1/eval-0-code-three-traces/without_skill/outputs \
  --port 3119
```

Always over `http://` — never open the `.html` as a `file://`. On `file://` the
Save button's POST fails and silently falls back to a browser download, and your
codes end up stranded in `~/Downloads`.

---

## 2. How to tag codes and save (the mechanics that matter)

Each card shows the task, an expandable final answer + judge rationale, and the
trajectory event counts. Code against **what the trajectory and `goal_met` show**,
not what the answer's prose claims.

For each card:

- **Add a code:** type a short code in the "add open code, press Enter" box and
  **press Enter**. It becomes a chip. Repeat for as many codes as you want.
- **Remove a code:** click the `×` on its chip.
- **Memo:** type freeform nuance in the memo box (optional).
- **Save:** click **Save to disk**. Status flips to `saved to disk: 3 rows -> coded.jsonl`.

Codes also autosave to `localStorage` on every keystroke, so a reload won't lose
work — but **only "Save to disk" writes the JSONL the exporter reads.**

### The one trap that ruins sessions

**Codes only count if they're Enter-committed chips.** Text you type into the
*memo* box does **not** populate `open_codes`. A comma-list sitting in a memo
exports as zero codes. After saving, the codes-vs-memo split is the thing to
verify (next step).

Good open codes are short, behavioral, and name *what happened* (not a fix):
`depth-under-plan`, `clarification-instead-of-action`, `tool-error-unhandled`,
`goal-not-met`. Don't agonize over consistency — you merge/rename later in axial
coding.

### My draft codes (already saved — replace as you see fit)

| Trace | Task | Draft codes |
|---|---|---|
| `e68552dd` | Design a rate limiter | `depth-under-plan`, `goal-met-despite-underplan`, `single-shot-design` |
| `2c0f3fce` | Refactor the auth module | `clarification-instead-of-action`, `no-tool-use`, `depth-under-plan`, `goal-not-met` |
| `9d2c84fb` | Compare Redis vs Memcached (3 subtasks) | `tool-error-unhandled`, `fabricated-progress-absent`, `subtasks-zero-of-three`, `depth-under-plan`, `goal-not-met` |

All three `want` a deeper plan (L1/L2) but `fired_depth` is L0 — the depth scorer
under-planned each. Note `9d2c84fb` honestly *reports* the tool failure rather
than faking a recommendation, so it's a tool-error case, not a corrupt-success.

---

## 3. Verify before you export (Step 4)

After Save, confirm every row you meant to code actually has chips:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
.venv/bin/python -c "import json; \
rows=[json.loads(l) for l in open('docs/skills/agentsframework-open-coding-workspace/iteration-1/eval-0-code-three-traces/without_skill/outputs/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

Right now this prints `3 rows, 0 with NO codes` / `uncoded: []`. If any trace_id
shows up in `uncoded:` after your pass, go back to the browser and Enter-commit
its codes. (Use `.venv/bin/python` — this repo needs Python 3.13.)

---

## 4. How the coded result becomes a paginated Langfuse dataset

A **dataset** is the review surface — not per-trace Scores (they scatter across a
trace's observations) and not an annotation queue (its drawer shows `run.started`,
which has no task or answer, and the Hobby plan caps queues at 1). The dataset
puts task + answer + codes together, one item per case, paginated, with a
`source_trace_id` link back to the full trace.

The exporter builds each item as:
- `input` = the task (`prompt`)
- `expected_output` = the agent's `final_answer`
- `metadata` = `open_codes` + `memo` (always) + whatever `--meta-keys` you list
- `source_trace_id` = the trace back-link

Item id is `uuid5(trace_id)`, so re-running **updates the same items** — refine
codes in the coder, Save, re-export, no duplicates.

### The dry run (default — what I already ran for you)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py \
  --dataset open-coding-three-traces \
  --coded docs/skills/agentsframework-open-coding-workspace/iteration-1/eval-0-code-three-traces/without_skill/outputs/coded.jsonl \
  --meta-keys stratum,trigger_family,want_depth,fired_depth,goal_met,partial_fraction \
  --id-keys want_depth,fired_depth
```

It prints `[would write] ...` per case and ends with `DRY RUN — nothing written`.
Your `final_answer` is already on each row, so no `--answers` join file is needed.

### When you're ready — the `--write` step (I did NOT run this)

Add `--write` to the exact same command and it creates the dataset
`open-coding-three-traces` and pushes the three items:

```bash
.venv/bin/python docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py --write \
  --dataset open-coding-three-traces \
  --coded docs/skills/agentsframework-open-coding-workspace/iteration-1/eval-0-code-three-traces/without_skill/outputs/coded.jsonl \
  --meta-keys stratum,trigger_family,want_depth,fired_depth,goal_met,partial_fraction \
  --id-keys want_depth,fired_depth
```

This hits your real Langfuse project (creds are in `.env`, EU host). Only run it
after you've eyeballed the dry run and replaced my draft codes with yours.

### Then review

Open the dataset in Langfuse (`/project/<id>/datasets/<dataset-id>`). All three
cases in one paginated table — task + answer visible, codes in metadata, trace
back-link for drill-down. To change anything: edit in the **HTML coder** (the
write surface), Save, re-run the exporter. The dataset is read-only review; the
coder is where you edit.

---

## Summary of the loop

```
coder running  ->  tag codes (Enter = chip)  ->  Save to disk  ->  verify 0 uncoded
   ->  export dry run (done)  ->  [you] add --write  ->  page the dataset
```

You're at the arrow right before `--write`.
