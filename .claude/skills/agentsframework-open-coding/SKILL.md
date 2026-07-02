---
name: agentsframework-open-coding
type: skill
description: >-
  Run a hands-on open-coding session over a set of agent traces: spin up the local
  HTML coder, tag short qualitative codes + memos per case, save to JSONL, then
  persist the coded case-set to a Langfuse DATASET (one item per case: task +
  final answer + codes + trace back-link) for paginated human review. Use this
  whenever you have a handful of traces/runs to error-analyze by hand — when the
  user says "open code these traces", "let me tag/label these cases", "review
  these failures in one place", "code this strata set", wants to turn a coded
  JSONL into a reviewable Langfuse dataset, asks where to STORE hand-assigned codes
  (Langfuse scores vs. annotation queue vs. dataset), or is troubleshooting why
  codes they typed in the coder aren't showing up in Langfuse. This is the OPERATIONAL companion to
  the strategic `llm-eval-grounded-theory` handbook (which covers Stage 1 open
  coding conceptually); reach for this skill when you actually need to DO a coding
  pass and persist it, not just plan one.
disable-model-invocation: false
paths:
  - cache/goaljudge_eval/open_coding/**
  - scripts/serve_open_coder.py
  - scripts/export_*_to_dataset.py
  - scripts/push_open_codes_to_langfuse.py
---

# AgentsFramework Open Coding

Run a manual open-coding pass over a small set of agent traces and land the result
in a Langfuse **dataset** that a human can page through and edit. Open coding is
the first-pass qualitative error analysis from grounded theory: read each trace,
write down short descriptive codes for what you observe, accumulate a memo. The
codes later roll up into an axial taxonomy and a judge rubric — but that's the
handbook's job. This skill is about the **mechanics of one coding session**, done
right, with the gotchas already solved.

> **Docs mirror.** Canonical Cursor install:
> [`.cursor/skills/agentsframework-open-coding/`](../../../.cursor/skills/agentsframework-open-coding/).
> This folder versions the skill with the repo for PR review and discovery. The
> conceptual pipeline lives in
> [`llm-eval-grounded-theory`](../llm-eval-grounded-theory/SKILL.md) — Stage 1
> (open coding) and Stage 2 (axial) there are the *why*; this is the *how*.

---

## When to use

- You have ~5–30 traces (a strata set, a batch of failures, a sampled window) and
  you want to error-analyze them **by hand**, not delegate to an LLM.
- You want the coded result somewhere a human can review **all cases in one place**,
  paginated, with task + answer + codes side by side, and edit codes later.
- You're following the grounded-theory loop and need to produce the Stage-1
  artifact (coded JSONL) that feeds axial coding.

**Do not** auto-generate the first-pass codes with an LLM. The whole value of open
coding is a human noticing what the trace actually did versus what the agent
*claimed* it did (R3, R10 in the handbook). The LLM proposes structure later, in
axial coding — not here.

---

## Cardinal rules (carried from the handbook, made concrete)

1. **Trace is ground truth; narration is a suspect claim.** Code what the tool
   outputs and termination show, not the agent's prose. The coder surfaces
   `goal_met`, `partial_fraction`, the trajectory event counts, and the judge
   rationale precisely so you code against observable behavior.
2. **Human codes first.** You type the codes. The skill never fills them in.
3. **Dataset is the review surface, not scores.** Per-trace Langfuse *scores*
   scatter across observations and the annotation-queue drawer hides them; a
   **dataset** shows task + answer + codes together, paginated. This was decided
   the hard way — see [references/langfuse-surface.md](references/langfuse-surface.md).
4. **Idempotent persistence.** Re-running the export updates the same items
   (item id = `uuid5` of the trace id), so you can refine codes and re-push freely.

---

## The loop

```
0. Make a session work dir →  copy this skill's coder.html into it
1. Build the cases JSON    →  <workdir>/cases.json  (one row per trace; see assets/cases.schema.json)
2. Serve the coder         →  python <skill>/scripts/serve_open_coder.py --dir <workdir>
3. Code in the browser     →  http://localhost:3117/coder.html  (tag codes, memo, Save)
4. Verify the JSONL        →  check open_codes is non-empty, not just memos
5. Export to a dataset     →  python <skill>/scripts/export_coded_to_dataset.py --write ...
6. Review + iterate        →  page the dataset; refine in coder; re-run 4–5
```

> **Use THIS skill's bundled scripts/assets, by their full path** — e.g.
> `docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py`. The repo's
> top-level `scripts/serve_open_coder.py` and `scripts/export_depth_cases_to_dataset.py`
> are the OLDER, planning-depth-hardcoded ancestors (inline cases, fixed dataset
> name, only `--port`). They still work for the planning-depth session but won't
> take the `--dir/--cases/--dataset/--coded` flags this skill's steps use. When in
> doubt, run the copy under this skill folder. Below, `<skill>` =
> `docs/skills/agentsframework-open-coding` and `<workdir>` = a scratch dir you make
> for this session.

Steps 4 and the codes-vs-memo distinction are where sessions go wrong. Read on.

---

## Step 0 — Make a session work dir

The coder, its cases, and the coded output all live together in one scratch dir so
sessions don't collide and `cache/` cleanup can't wipe your codes:

```bash
WORK=cache/open_coding/<your-session-name>          # any path you like
mkdir -p "$WORK"
cp docs/skills/agentsframework-open-coding/assets/coder.html "$WORK/coder.html"
# (cases.json comes next, in Step 1)
```

This is the "copy the coder, don't edit it in place" rule: `coder.html` is generic
and fetches its cases from the server at `/cases`, so you never hand-edit the HTML
to change what's being coded — you only change `cases.json`.

---

## Step 1 — Build the cases JSON

The coder renders one card per trace. Each row carries enough context to code
**without leaving the page**: the task, the agent's final answer, the judge's
rationale, and a compressed trajectory (event counts). Pull these from your trace
store (Langfuse, PhaseLogger, a corpus JSONL) by `trace_id`.

The schema and a worked example are in
[assets/cases.schema.json](assets/cases.schema.json). Minimum per row:

```json
{
  "trace_id": "7c71871fb0...",
  "stratum": "depth:L2:adversarial",
  "prompt": "the task given to the agent",
  "final_answer": "the agent's last message",
  "goal_met": false,
  "partial_fraction": 0.5,
  "trajectory": [{"ev": "step.planned"}, {"ev": "error.occurred", "tool": "shell"}],
  "rationale": "judge's reasoning (optional context)",
  "want_depth": "L2", "fired_depth": "L0"
}
```

`want_depth`/`fired_depth` are GoalJudge-specific (they drive the want→fired
badge). For a non-depth coding session, drop them — the coder shows the badge
only when both are present. **Any extra keys you add survive the round-trip** and
land in the dataset item metadata, so put whatever you'll want to filter on later
(family, severity, model) right on the row.

Write the cases array to `<workdir>/cases.json`. The server serves it at `/cases`
and the coder fetches it on load, so you never hand-edit the HTML. (A 3-case
example to copy from: [assets/sample_cases.json](assets/sample_cases.json).)

---

## Step 2 — Serve the coder

```bash
python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py --dir "$WORK"
python docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py --dir "$WORK" --port 3118
```

`--dir` is the work dir from Step 0 (holds `coder.html` + `cases.json`); coded
output and backups land there too. Then open `http://localhost:3117/coder.html`.

**Always serve over http — never open the .html as a `file://`.** The Save button
POSTs the coded JSONL to `/save`; on `file://` that fetch fails
(`Failed to parse URL from /save`) and silently falls back to a browser download,
which is how a session ends up with codes only in `~/Downloads`. The server also:

- serves `<workdir>/cases.json` at `GET /cases` (what the coder renders) and the
  coded JSONL at `GET /load` so reopening the page restores your prior codes;
- **validates** every saved line is JSON with a `trace_id` (rejects garbage);
- **refuses a save that shrinks the file below 50%** of existing rows unless
  `?force=1` — this guard exists because a stray `curl /save` once overwrote a
  fully-coded file with the literal string `probe`;
- writes a **timestamped backup** on every save, so a clobber is recoverable.

---

## Step 3 — Code in the browser

For each card: read the task, expand the answer + judge rationale, glance at the
trajectory counts, then type short codes and press **Enter** to commit each one as
a chip. Add a memo for nuance. Codes autosave to `localStorage` on every change;
click **Save to disk** to write the JSONL the exporter reads.

Good open codes are short, descriptive, and behavioral:
`depth-under-plan`, `fabricated-progress`, `clarification-instead-of-action`,
`tool-error-unhandled`, `claim-without-tool-evidence`. They name *what happened*,
not a fix. You'll merge and rename them in axial coding — don't over-think
consistency now.

---

## Step 4 — Verify the JSONL (the trap)

**The single most common failure: memos full of prose, `open_codes` empty.** Codes
only persist if you press **Enter** to turn each into a chip. Typing a comma-list
into the memo box does *not* populate `open_codes`. Before exporting, confirm:

```bash
.venv/bin/python -c "import json,sys; \
rows=[json.loads(l) for l in open('$WORK/coded.jsonl') if l.strip()]; \
empty=[r['trace_id'] for r in rows if not r.get('open_codes')]; \
print(f'{len(rows)} rows, {len(empty)} with NO codes'); print('uncoded:', empty)"
```

The exporter's dry run (Step 5) prints the same `(N with NO codes)` count plus a
warning banner, so you'll catch this even if you skip the one-liner. If
`open_codes` is empty for rows you thought you coded, go back to the browser and
Enter-commit them. (This repo requires Python 3.13 — always use `.venv/bin/python`,
not the system `python`, or you'll hit `int | None` syntax errors.)

---

## Step 5 — Export to a Langfuse dataset

Run from the repo root with `.venv/bin/python` (it imports
`scripts.langfuse_dataset_client`). `EXPORT=docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`:

```bash
# dry run (default) — prints what it would write, including the NO-codes count
.venv/bin/python "$EXPORT" --dataset my-coding-session --coded "$WORK/coded.jsonl"

# actually push
.venv/bin/python "$EXPORT" --write \
    --dataset my-coding-session \
    --coded "$WORK/coded.jsonl" \
    --meta-keys stratum,want_depth,fired_depth,goal_met,severity

# if final_answer lives in a separate corpus rather than on the coded rows:
.venv/bin/python "$EXPORT" --write --dataset my-coding-session \
    --coded "$WORK/coded.jsonl" --answers cache/.../rich.jsonl
```

The exporter is **parameterized** so it works for any coding session, not just
planning-depth (unlike the repo's hardcoded `scripts/export_depth_cases_to_dataset.py`,
which only does the planning-depth dataset). `--dataset` and `--coded` are
required. Flags:

- `--dataset` — Langfuse dataset name (created if absent).
- `--coded` — the coded JSONL from the coder (`<workdir>/coded.jsonl`).
- `--answers` — optional second JSONL to join `final_answer` by `trace_id`
  (the coded file may not carry the answer; the rich corpus does). If your coded
  rows already have `final_answer`, omit this.
- `--meta-keys` — which row keys to copy into item metadata. `open_codes` and
  `memo` are always included.

Each dataset item: `input={task, ...id-keys}`, `expected_output=final_answer`,
`metadata={open_codes, memo, ...meta-keys}`, `source_trace_id` back-link. Item id
is `uuid5(trace_id)` so **re-running updates in place** — refine codes in the
coder, Save, re-run with `--write`, and the same items update.

Default is a **dry run** that prints what it would write. Pushing to Langfuse
annotates a real project — only `--write` after you've eyeballed the dry run.

---

## Step 6 — Review and iterate

Open the dataset in Langfuse (`/project/<id>/datasets/<dataset-id>`). You get all
cases in one paginated table, each showing task + answer, with codes in metadata.
To change codes: edit in the **HTML coder** (the edit surface), Save, re-run the
exporter. The dataset is the *read* surface; the coder is the *write* surface.

For why a dataset beats the trace Scores tab and annotation queues here, see
[references/langfuse-surface.md](references/langfuse-surface.md).

---

## Worked example: planning-depth strata

The bundled scripts were built coding 11 GoalJudge planning-depth traces. That
session is the reference implementation end-to-end:
[references/example-planning-depth.md](references/example-planning-depth.md) walks
the actual files (`depth_strata_coded.jsonl`, dataset `planning-depth-open-coding`)
and the axial taxonomy that came out of it.

## Environment

- Langfuse creds in `.env` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_HOST` — default EU `https://cloud.langfuse.com`; a stray `us.` host
  502s).
- Reading a TEXT score back later: the value is in `string_value`, NOT `.value`
  (which is `None` for TEXT). Datasets avoid this entirely — prefer them.
