# NOTES — axial pass, iteration-2 eval-0

Process log + judgment calls for the axial pass over
`tests/fixtures/axial_coding_eval/coded_slice.jsonl` (30 traces, 21 codes, 90 occ).

## Loop followed (per SKILL.md)
0. Inventory  — `scripts/build_coach_open_code_inventory.py` → `inventory.csv` (21 rows).
1. Partition  — filled `axis` by cause: 20 agent-behavior, 1 environment-confound, 0 judge.
2. Cluster    — 7 agent categories → `categories.csv`.
3. Gate       — `axial_checker.py` → **exit 0** (green) after one fix (see below).
4. Count+pairs— `axial_matrix.py` → `matrix.json`; `axial_minimal_pairs.py` → `minimal_pairs.json`.
5. Write-up   — `coach_axial_coding.md`.
6. Emit       — rubric-assertion + judge-test-case candidates in write-up §7.

## Checker gate: one red → green
First run BLOCKED on `elicitation-quality declares a dimension but binary_check has <2
boundary checks`. Root cause was **not** a real dimension — an unquoted comma inside that
row's `binary_check` ("a genuine probe, not narration…") spilled into the `dimension`
column under CSV parsing. Fix: quoted the field. Re-ran → exit 0. (Only `answer-leak`
legitimately carries a dimension, with 4 `|`-separated boundary checks.)

## Axis calls
- Only `truncated-reply` is `environment-confound` — a generator cutoff, not a coach
  choice. All 3 truncated traces also carry an agent-behavior code, so
  `confound_only_excluded = 0` and the overall `agent_denominator = 30`.
- **No judge-reliability codes.** The slice coded coach behavior only; no verdict/label
  defects were minted. Recorded as 0, not forced.

## The denominator / straddle call (the load-bearing one)
For the **leak-rate specifically**, applied the skill's straddle rule per trace:
- `1b4ce6ca`, `2dfe11e7` — leaked *before* the truncation cut → observed → KEEP.
- `05fa7a88` — cut *before* any leak; coder withheld the leak code → leak status UNKNOWN
  → DROP from the leak denominator (unscorable for this question).
→ leak-rate denominator = **29**, not 30 (over-folds unscorable) and not 27 (over-drops
the two that leaked before their cut). any-leak = 12/29 (41%); strong-or-worse = 6/29 (21%).

## Units discipline
Quoted **trace counts** for prevalence throughout. Two categories diverge occ vs trace:
`answer-leak` 24 occ / 20 traces; `scaffolding-move` 27 occ / 21 traces. Never reported
occurrences as "N/30".

## Minimal-pairs filtering (v1 is axis-blind)
4 pairs returned. Confirmed agent-behavior divergence on A (leak severity), B
(learner-state ±), C (elicitation add-on, softer). **Pair D excluded** — its only
divergence is `truncated-reply` (environment-confound); the agent behavior is identical,
so it is noise, not gold.

## Carried-forward dataset flags (NOT agent failures, no axis)
Coder memos repeatedly flag `question_id`↔item churn (same item under different ids;
redundancy framing across 5/6 ids). Fix in the item bank before this corpus is promoted to
a gold set. Template reuse (cover-the-phrase probe, return-crux-leader, arithmetic-detour)
is real but memo-only; its rubric consequence is that `scaffolding-move` and
`learner-state-uptake` must be scored independently.

## Files
inventory.csv · categories.csv · coach_axial_coding.md · matrix.json ·
minimal_pairs.json · NOTES.md
