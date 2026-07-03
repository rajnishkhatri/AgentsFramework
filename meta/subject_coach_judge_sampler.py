"""Post-hoc Subject-Coach judge sampler — a ``meta/`` job (design §7.3).

EvalRecords ``target="subject_coach"`` → deterministic task_id-hash sampling
at ``coach_judge_sample_rate`` → the two coach judges on the SAME sampled turn
(paired verdicts) → verdict records via ``eval_capture.record`` with
``target="coach_judges"`` and the source turn's ``task_id``/``user_id``.

Never inline (ADR-0009): nothing here runs in ``evaluate_node`` — this job
reads captured logs offline, exactly the meta-layer contract (invariant #8:
no orchestration imports). There is no probe registry (§7.3's stated
absence): the job is invoked operator-cadence and its verdict stream feeds
the existing ``meta/drift.py`` entry points downstream.

AP-6: an undecidable turn (judge returned ``None``) is COUNTED, never
recorded — a fabricated verdict row would poison the §7.4 calibration slices.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from components.schemas import EvalRecord
from meta.analysis import records_for_target
from services import eval_capture

if TYPE_CHECKING:
    from components.subject_coach_judges import GraderJudge, PedagogyJudge
    from services.subject_coach_judge_runtime_config import (
        InMemorySubjectCoachJudgeConfigReader,
        SubjectCoachJudgeConfigReader,
    )

logger = logging.getLogger("meta.subject_coach_judge_sampler")

__all__ = [
    "CoachJudgeSamplingReport",
    "run_coach_judge_sampling",
    "should_sample",
]

COACH_TARGET = "subject_coach"
VERDICT_TARGET = "coach_judges"

# The BFF-derived mode marker as it appears inside a recorded coach
# ``task_input`` (the ``coach_context`` JSON rides the run input — spec §4).
# The full JSON key/value pair, NOT the bare word: a learner utterance that
# merely mentions "post_feedback" must not flip the turn onto the lenient
# leakage rubric (that would be the fail-open direction).
_POST_FEEDBACK_MARKER = '"mode": "post_feedback"'


class _Recorder(Protocol):
    async def __call__(
        self,
        target: str,
        ai_input: dict[str, Any],
        ai_response: Any,
        config: dict[str, Any],
        *,
        model: str | None = None,
    ) -> None: ...


async def _record_eval(
    target: str,
    ai_input: dict[str, Any],
    ai_response: Any,
    config: dict[str, Any],
    *,
    model: str | None = None,
) -> None:
    """Default recorder: the H5 eval_capture seam, pinned to _Recorder's shape."""
    await eval_capture.record(target, ai_input, ai_response, config, model=model)


class CoachJudgeSamplingReport(BaseModel):
    """What one sampling pass did — telemetry for the operator, never a gate."""

    total_records: int = 0
    coach_records: int = 0
    sampled_tasks: int = 0
    judged: int = 0
    undecidable: int = 0


def should_sample(task_id: str, rate: float) -> bool:
    """Deterministic task_id-hash sampling (design §7.3).

    SHA-256, never ``hash()`` (randomized per process — a re-run would sample
    a different population). The first 8 bytes map the task into [0, 1);
    thresholding makes the selection MONOTONIC in ``rate``: raising the dial
    only ever adds tasks, so longitudinal comparisons stay apples-to-apples.
    """
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    digest = hashlib.sha256(task_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / 2**64
    return bucket < rate


def _latest_turn_per_task(records: list[EvalRecord]) -> list[EvalRecord]:
    """Collapse a task's LLM calls to its final turn, order-preserving.

    Paired judges must see the SAME turn; the last step is the reply the
    learner actually received.
    """
    latest: dict[str, EvalRecord] = {}
    order: list[str] = []
    for rec in records:
        if rec.task_id not in latest:
            order.append(rec.task_id)
            latest[rec.task_id] = rec
        elif rec.step >= latest[rec.task_id].step:
            latest[rec.task_id] = rec
    return [latest[task_id] for task_id in order]


def _mode_of(record: EvalRecord) -> str:
    """Derive the turn's mode from the recorded input — fail-closed.

    Preference order (§13 audit finding F1): the run's own carrier
    ``ai_input["coach_mode"]`` — the formatter-derived mode recorded at the
    eval seam — then the legacy marker parse for pre-F1 records. On real
    traffic ``task_input`` is last-message-only, so the marker alone froze
    every turn at pre_submit.

    Unknown/absent ⇒ ``pre_submit``: the STRICTER leakage rubric. Only the
    exact string ``"post_feedback"`` flips — mis-grading a post-feedback turn
    as pre-submit costs a false leak flag (human review absorbs it); the
    reverse would hide a real leak.
    """
    if record.ai_input.get("coach_mode") == "post_feedback":
        return "post_feedback"
    text = str(record.ai_input.get("task_input", ""))
    return "post_feedback" if _POST_FEEDBACK_MARKER in text else "pre_submit"


async def run_coach_judge_sampling(
    records: list[EvalRecord],
    *,
    grader_judge: GraderJudge,
    pedagogy_judge: PedagogyJudge,
    config_reader: SubjectCoachJudgeConfigReader
    | InMemorySubjectCoachJudgeConfigReader,
    recorder: _Recorder = _record_eval,
) -> CoachJudgeSamplingReport:
    """One offline sampling pass over a captured EvalRecord stream."""
    posture = config_reader.get()
    report = CoachJudgeSamplingReport(total_records=len(records))
    if not (posture.coach_grader_judge_enabled or posture.coach_pedagogy_judge_enabled):
        return report

    coach_records = records_for_target(records, COACH_TARGET)
    report.coach_records = len(coach_records)
    turns = [
        rec
        for rec in _latest_turn_per_task(coach_records)
        if should_sample(rec.task_id, posture.coach_judge_sample_rate)
    ]
    report.sampled_tasks = len(turns)

    for rec in turns:
        learner_utterance = str(rec.ai_input.get("task_input", ""))
        coach_reply = (
            rec.ai_response
            if isinstance(rec.ai_response, str)
            else str(rec.ai_response)
        )
        mode = _mode_of(rec)
        run_config = {"configurable": {"task_id": rec.task_id, "user_id": rec.user_id}}

        if posture.coach_grader_judge_enabled:
            verdict = await grader_judge.evaluate(
                question=learner_utterance, coach_content=coach_reply
            )
            if verdict is None:
                report.undecidable += 1
            else:
                report.judged += 1
                await recorder(
                    target=VERDICT_TARGET,
                    ai_input={"judge": "grader", "mode": mode, "source_step": rec.step},
                    ai_response=verdict.model_dump(),
                    config=run_config,
                    model=grader_judge.model_name,
                )

        if posture.coach_pedagogy_judge_enabled:
            verdict = await pedagogy_judge.evaluate(
                learner_utterance=learner_utterance,
                coach_reply=coach_reply,
                mode=mode,
            )
            if verdict is None:
                report.undecidable += 1
            else:
                report.judged += 1
                await recorder(
                    target=VERDICT_TARGET,
                    ai_input={
                        "judge": "pedagogy",
                        "mode": mode,
                        "source_step": rec.step,
                    },
                    ai_response=verdict.model_dump(),
                    config=run_config,
                    model=pedagogy_judge.model_name,
                )

    logger.info(
        "coach judge sampling: %d records -> %d coach -> %d sampled -> %d verdicts (%d undecidable)",
        report.total_records,
        report.coach_records,
        report.sampled_tasks,
        report.judged,
        report.undecidable,
    )
    return report
