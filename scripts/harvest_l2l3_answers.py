"""Harvest each arm's final L2/L3 answers into one raw-answers file.

For the blind-adjudication gold-set seed (docs/plans/
model_ab_l2l3_blind_adjudication.plan.md) we need, for every (arm x L2/L3 case), the
model's final answer text. This script pulls them from each arm's per-arm
``evals.log`` snapshot and writes a single ``{arm: {case: answer_text}}`` map.

Why a separate extractor (not score_answers): ``_final_answers_by_case`` in
model_ab_answer_score.py iterates ONLY ``EXPECTED_BY_CASE`` (the 10 L1 cases). The
last-call_llm / uuid5(case) keying is identical, so we reuse that join logic here but
parametrize it on an arbitrary case list (the 9 L2/L3 cases).

HARVEST-TRUNCATION HAZARD (2026-06-26): the ``call_llm`` ``ai_response`` we read
here is PRE-CLIPPED to 500 chars by the react-loop eval-capture
(``orchestration/react_loop.py``: ``response_text(response)[:500]``). These answers
are faithful for human adjudication of short answers, but they are NOT a faithful
re-judge input — the LIVE GoalJudge saw ``eval_telemetry.clip_eval_text`` (8192-char)
final answers. To inspect what the judge actually graded (e.g. when a rationale says
a subtask is "missing"), read the per-arm ``evals.log`` ``goal_judge`` record's
``ai_input.final_answer``, not this file. See memory
``goaljudge-residual-fp-root-cause`` (the 2 residual fp split into one judge bug and
one lenient-label case only once the 8192-char view was used).

Arm sources (config below, edit as runs land):
  - cheap arms already on disk in cache/model_ab/a3b_full_* (candidate arm = the
    pinned model under test; baseline arm in those runs is gpt-4o-mini).
  - reasoning arms from the fresh l2l3_<arm>_<ts> runs (Phase 0b).

The candidate vs baseline arm within a run: model_ab_eval drives BOTH a baseline and
a candidate per run. For a run pinned candidate=<model> baseline=gpt-4o-mini, the
candidate/evals.log holds <model>'s answers and baseline/evals.log holds
gpt-4o-mini's. We therefore name each (run_dir, arm) source explicitly.

Acceptance: 6 arms x 9 cases = 54 cells; any missing/empty cell is printed (and
recorded as the empty string) so the operator knows to re-harvest, never silently
dropped.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
MODEL_AB = AGENT_ROOT / "cache" / "model_ab"
DEFAULT_OUT = AGENT_ROOT / "cache" / "model_ab_answer" / "l2l3_raw_answers.json"
L2L3_BATCH = AGENT_ROOT / "cache" / "model_ab_answer" / "l2l3_batch.jsonl"

# arm label -> (run_dir relative to cache/model_ab, "baseline"|"candidate")
# All six arms ran against the SEEDED L2/L3 fixtures (seed_model_ab_l2l3_workspace.py);
# the pre-seed a3b_full_* answers graded file-absence and are NOT used. gpt-4o-mini
# rides along as the baseline arm of the opus run (every run drives baseline=gpt-4o-mini).
DEFAULT_SOURCES: dict[str, tuple[str, str]] = {
    "claude-opus-4-8": ("l2l3_opus48_seeded_171054", "candidate"),
    "gpt-5": ("l2l3_gpt5_seeded_171859", "candidate"),
    "deepseek-v4-pro": ("l2l3_deepseekpro_seeded_172802", "candidate"),
    "claude-haiku-4-5": ("l2l3_haiku_seeded_173810", "candidate"),
    "deepseek-v4-flash": ("l2l3_flash_seeded_174657", "candidate"),
    "gpt-4o-mini": ("l2l3_opus48_seeded_171054", "baseline"),
}


def l2l3_cases(batch: Path = L2L3_BATCH) -> list[str]:
    """The 9 L2/L3 case ids, in corpus order."""
    cases: list[str] = []
    for line in batch.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line)["case"])
    return cases


def final_answers_for_cases(eval_log: Path, cases: list[str]) -> dict[str, str]:
    """case -> final call_llm answer text, for an arbitrary case list.

    Mirrors model_ab_answer_score._final_answers_by_case (last call_llm per
    task_id, task_id == uuid5(NAMESPACE_DNS, case).hex), but parametrized on the
    given cases instead of the L1-only EXPECTED_BY_CASE table.
    """
    last_call: dict[str, dict] = {}
    for line in eval_log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("target") != "call_llm":
            continue
        tid = rec.get("task_id", "")
        if tid:
            last_call[tid] = rec  # later overwrites earlier => final step wins

    out: dict[str, str] = {}
    for case in cases:
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        rec = last_call.get(tid)
        if rec is None:
            continue
        resp = rec.get("ai_response", "")
        out[case] = resp if isinstance(resp, str) else json.dumps(resp)
    return out


def harvest(
    sources: dict[str, tuple[str, str]] = DEFAULT_SOURCES,
    cases: list[str] | None = None,
    model_ab: Path = MODEL_AB,
) -> tuple[dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Return ({arm: {case: answer}}, missing) where missing is (arm, case) pairs
    with no answer or an empty/whitespace answer."""
    cases = cases or l2l3_cases()
    raw: dict[str, dict[str, str]] = {}
    missing: list[tuple[str, str]] = []
    for arm, (run_dir, sub) in sources.items():
        eval_log = model_ab / run_dir / sub / "evals.log"
        answers = final_answers_for_cases(eval_log, cases) if eval_log.exists() else {}
        raw[arm] = {}
        for case in cases:
            text = answers.get(case, "")
            raw[arm][case] = text
            if not text or not text.strip():
                missing.append((arm, case))
    return raw, missing


def write_json(raw: dict[str, dict[str, str]], out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, indent=2) + "\n")
    return out


if __name__ == "__main__":
    raw, missing = harvest()
    write_json(raw)
    n_cells = sum(len(v) for v in raw.values())
    print(f"harvested {len(raw)} arms x cases = {n_cells} cells -> {DEFAULT_OUT}")
    if missing:
        print(f"MISSING/EMPTY ({len(missing)}):")
        for arm, case in missing:
            print(f"  {arm}  {case}")
    else:
        print("all cells non-empty")
