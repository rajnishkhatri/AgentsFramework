# Transcript — eval-2 "where to persist coded traces"

Task: advise where in Langfuse to put ~15 hand-coded traces for joint review +
later editing. Advice only; no push to Langfuse.

## Skill invoked

- `docs/skills/agentsframework-open-coding/SKILL.md` — the operational open-coding
  skill. Directly answers the question: dataset is the review surface, scores
  scatter, annotation queues show the wrong observation + are capped on Hobby.

## Files consulted

1. `docs/skills/agentsframework-open-coding/SKILL.md`
   — the loop (work dir → cases.json → serve coder → code → verify → export →
   review), cardinal rule #3 "dataset is the review surface, not scores",
   the file:// / memo-vs-chip / Python 3.13 gotchas, and the
   old-vs-new-script warning.
2. `docs/skills/agentsframework-open-coding/references/langfuse-surface.md`
   — the three-surface comparison table and the rationale for each rejection
   (score-per-observation scatter, annotation-queue top-observation + Hobby cap,
   TEXT score `string_value` trap). This is the spine of the recommendation.
3. `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
   — confirmed exact flags: `--write`, `--dataset` (required), `--coded`
   (required), `--answers`, `--meta-keys`, `--id-keys`; idempotent
   `uuid5(trace_id)` item ids; item shape input/expected_output/metadata/
   source_trace_id.
4. `docs/skills/agentsframework-open-coding/assets/cases.schema.json`
   — required keys (trace_id, prompt), optional fields, "extra keys survive into
   metadata" rule.
5. `docs/skills/agentsframework-open-coding/references/example-planning-depth.md`
   — confirmed the worked reference session and that the top-level scripts are the
   hardcoded ancestors.
6. Directory listing of the skill folder to confirm script/asset paths exist.

## Scripts I pointed the user at (exact paths)

- Serve the coder:
  `docs/skills/agentsframework-open-coding/scripts/serve_open_coder.py --dir $WORK`
- Coder asset to copy:
  `docs/skills/agentsframework-open-coding/assets/coder.html`
- Cases schema / starter:
  `assets/cases.schema.json`, `assets/sample_cases.json`
- Export to dataset:
  `docs/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py`
  (dry run by default; `--write --dataset team-review --coded $WORK/coded.jsonl`).

Explicitly steered AWAY from the top-level `scripts/serve_open_coder.py` and
`scripts/export_depth_cases_to_dataset.py` (planning-depth-hardcoded ancestors,
no `--dir/--dataset` flags).

## Verification one-liner included

`.venv/bin/python -c "..."` to catch the empty-`open_codes` / memo-vs-chip trap
before export. Stressed `.venv/bin/python` (repo is Python 3.13).

## Not done (per task constraints)

- Did NOT push anything to Langfuse.
- Did NOT run any script (advice task).

## Output

- `outputs/answer.md` — recommendation + 7-step walkthrough.
