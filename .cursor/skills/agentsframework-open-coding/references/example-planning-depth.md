# Worked example: planning-depth strata

The reference session that produced this skill. Goal: find out why the agent
"under-plans" complex tasks. 12 synthetic prompts were run live through the agent
(GoalJudge T3 batch), 11 traces collected, then open-coded by hand.

## The files (in-repo, planning-depth-specific)

| File | Role |
|---|---|
| `cache/goaljudge_eval/depth_strata_rich.jsonl` | rich corpus: trace_id, prompt, final_answer, goal_met, partial_fraction, trajectory, rationale, want/fired depth |
| `cache/goaljudge_eval/open_coding/coder.html` | the coder, with the 11 cases inlined (this skill's `assets/coder.html` is the generalized version that fetches `/cases` instead) |
| `cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl` | the coded output: each row + `open_codes` + `memo` |
| `scripts/serve_open_coder.py` | the server (paths hardcoded to the open_coding dir) |
| `scripts/export_depth_cases_to_dataset.py` | the original, hardcoded exporter → dataset `planning-depth-open-coding` |

The skill's `scripts/` are the generalized descendants: `serve_open_coder.py`
takes `--dir/--cases/--coded`, and `export_coded_to_dataset.py` takes
`--dataset/--coded/--answers/--meta-keys`. Same behavior, no hardcoded names.

## How the example maps onto the loop

1. **Cases JSON** — built by joining live trace fields by `trace_id`. Each row
   carried `want_depth`/`fired_depth` (drives the want→fired badge), `goal_met`,
   `partial_fraction`, and a `trajectory` event list.
2. **Serve + code** — 11 cards, coded by hand against the trajectory and answer,
   not the agent's prose.
3. **Verify** — caught the classic trap once: codes typed into the memo box
   instead of Enter-committed, so `open_codes` came back empty. Re-coded as chips.
4. **Export** — `--dataset planning-depth-open-coding`, joining `final_answer`
   from the rich corpus, metadata = want/fired depth + goal_met + stratum + codes.

## The taxonomy that came out

The dominant code was **`depth-under-plan`** (want > fired). Axial split by
outcome:

- **`goal-met-despite-underplan`** — benign. Synthesis-only tasks (design,
  migration plan, login walkthrough) succeed at 1 step even when the heuristic
  under-scored depth.
- **harmful execution codes** — `fabricated-progress`,
  `clarification-instead-of-action`, `fluent-evasion`, `claim-without-tool-evidence`,
  `tool-error-unhandled`, `fabricated-delegation`, `incomplete-enumeration`.

Key axial finding: **lone-marker depth misses are benign on synthesis tasks but
harmful on action/tool tasks.** The one catastrophic L2 miss was a distinct
mechanism (`post-tool-synthesis-short-circuit`), not lexical under-scoring.

This is exactly the kind of structure open coding is supposed to surface: the
"under-plans" hunch resolved into a benign-vs-harmful split with a named distinct
mechanism — the input a downstream fix or judge rubric actually needs.
