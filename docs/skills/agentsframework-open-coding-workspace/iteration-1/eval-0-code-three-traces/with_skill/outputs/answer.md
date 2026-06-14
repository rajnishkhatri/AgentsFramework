# Open-coding three traces, then into a Langfuse dataset

You're all set up. The HTML coder is running and loaded with your three cases
(`Design a rate limiter`, `Refactor the auth module`, `Compare Redis and
Memcached`). Below is exactly how to tag/save them and how the coded result
becomes a Langfuse dataset you can page through. I've taken you right up to the
`--write` step and stopped — nothing has been pushed to Langfuse.

---

## 1. The coder is already running

The local coder server is up on port **3117**, serving from
`cache/goaljudge_eval/open_coding/`. Open this in a browser:

```
http://localhost:3117/coder.html
```

If it's ever *not* running, start it with (always over http, never `file://` —
the Save button POSTs to `/save`, which dies on a `file://` origin and silently
downloads to ~/Downloads instead):

```bash
.venv/bin/python scripts/serve_open_coder.py            # serves on :3117
# or pick another port:
.venv/bin/python scripts/serve_open_coder.py --port 3118
```

The page shows one card per trace with the task, the agent's final answer, the
judge rationale, the `goal_met` / `partial_fraction` badges, and the compressed
trajectory event counts — everything you need to code against observable
behavior **without leaving the page**. (Cardinal rule: the trace is ground
truth, the agent's prose is a suspect claim.)

> Note on what's loaded: this repo's coder bakes its cases into the HTML as a
> `const CASES=[…]` array rather than fetching a `cases.json` (the SKILL.md
> describes the fetch design; the actual file inlines them). I replaced that
> array with your three rows from
> `docs/skills/agentsframework-open-coding/assets/sample_cases.json` and seeded
> `cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl` with the same
> three rows, codes empty, so `GET /load` restores a clean slate. The original
> 11-case planning-depth coder and its coded file are backed up next to them
> (`coder.depth11.bak.html`, `depth_strata_coded.depth11.bak.jsonl`).

---

## 2. How to tag codes and save

For each of the three cards:

1. Read the task. Expand the final answer and the judge rationale. Glance at the
   trajectory counts (e.g. case 3 has `error.occurred` on `state_todo` /
   `state_file` — that's why it produced no recommendation).
2. Type a short **code** into the code box and press **Enter**. Each Enter
   commits one code as a chip. **This is the step sessions get wrong:** typing a
   comma-list into the *memo* box does NOT populate `open_codes`. Only
   Enter-committed chips count.
3. Add a **memo** for nuance (free prose — context, your reasoning).
4. Codes autosave to `localStorage` on every change. When you're done, click
   **Save to disk** — that POSTs the JSONL to the server, which writes
   `cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl` (plus a
   timestamped backup every save).

Good open codes are short, descriptive, behavioral — they name *what happened*,
not the fix. For these three traces, candidates you might reach for:

- Case 1 (`Design a rate limiter`, goal_met=true): looks clean — maybe
  `single-step-plan` if you want to flag that a design task fired at L0.
- Case 2 (`Refactor the auth module`, goal_met=false): `clarification-instead-of-action`
  — it asked for more info rather than doing anything.
- Case 3 (`Compare Redis and Memcached`, goal_met=false): `tool-error-unhandled`
  + `gave-up-on-subtasks` — `state_todo`/`state_file` errored and it completed
  none of the three enumerated subtasks.

Don't over-think consistency now; you merge/rename in axial coding later.

### Verify the save actually has codes (the trap)

Before exporting, confirm `open_codes` is non-empty for the rows you coded:

```bash
.venv/bin/python -c "import json; \
rows=[json.loads(l) for l in open('cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

If a row you thought you coded shows up as uncoded, go back to the browser and
Enter-commit its chips, then Save again.

---

## 3. How the coded result becomes a reviewable Langfuse dataset

Why a **dataset** and not per-trace scores or an annotation queue: a dataset
shows one item per case — task (`input`) + agent answer (`expected_output`) +
your codes (`metadata`) — all together, paginated, with a `source_trace_id`
back-link. Scores scatter across observations; the annotation-queue drawer shows
the wrong observation and is capped at 1 on the Hobby plan. The coder is the
*write/edit* surface; the dataset is the *read/review* surface.

The exporter is **idempotent** — the dataset item id is derived from the
trace_id, so re-running updates the same items. Refine codes in the coder → Save
→ re-run the exporter, and the same items update in place.

### Dry run first (writes nothing — already verified working for your 3 cases):

```bash
.venv/bin/python scripts/export_depth_cases_to_dataset.py
```

This printed, for your three cases:

```
3 cases -> dataset 'planning-depth-open-coding'
[would write] L1/L0 'Design a rate limiter for the API.'  codes=[…]
[would write] L1/L0 'Refactor the auth module.'           codes=[…]
[would write] L2/L0 'Compare Redis and Memcached …'        codes=[…]
DRY RUN — nothing written. Re-run with --write.
```

### The actual push — STOP HERE, run this only when you're ready:

```bash
.venv/bin/python scripts/export_depth_cases_to_dataset.py --write --dataset three-sample-traces-open-coding
```

I have **not** run this. `--write` annotates your real Langfuse project, so
eyeball the dry-run output first. Each item lands as:
`input={task, want_depth}`, `expected_output=<agent final answer>`,
`metadata={open_codes, code_detail, want_depth, fired_depth, depth_miss,
stratum, goal_met, partial_fraction}`, with `source_trace_id` linking back to
the full trace.

Then review at `…/project/<id>/datasets/three-sample-traces-open-coding` — all
three cases in one paginated table. To change codes, edit in the coder, Save,
re-run the export; items update in place.

---

## Two honest caveats about the exporter (read before `--write`)

The SKILL.md describes a generic `scripts/export_coded_to_dataset.py` with
`--coded` / `--answers` / `--meta-keys` flags. **That script does not exist in
this repo.** The actual exporter is
`scripts/export_depth_cases_to_dataset.py`, which is hardcoded to the
planning-depth session. Two consequences for your three-case run:

1. **Default dataset name is `planning-depth-open-coding`.** Pass
   `--dataset three-sample-traces-open-coding` (as above) so you don't pollute
   the depth dataset.

2. **`expected_output` comes from a join, not your sample file.** The exporter
   ignores the inline `final_answer` in your coded rows and instead joins the
   answer from `cache/goaljudge_eval/depth_strata_rich.jsonl` by `trace_id`. All
   three of your trace_ids happen to exist in that rich corpus, so the export
   resolves — but the answer that lands in the dataset is the *full* rich-corpus
   version, which differs from the shortened `final_answer` strings in
   `sample_cases.json`. This is harmless (a fuller answer for review), just know
   that's where it's sourced. If you specifically want the inline summaries in
   the dataset instead, that needs a one-line tweak to the exporter to prefer
   the row's own `final_answer` — say the word and I'll make the exporter
   generic (the `--coded`/`--answers` version the skill actually describes).

Everything is staged and verified up to — but not including — `--write`.
