"""Automated evaluation scoring pipeline.

Loads a golden set of EvalRecords, runs each through the agent, scores
with the LLM judge, and produces a structured report.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from components.schemas import EvalRecord
from meta.judge import JudgeResult, JudgeScore, load_taxonomy, score_eval_record
from services.base_config import ModelProfile

logger = logging.getLogger("meta.run_eval")


class EvalReportEntry(BaseModel):
    """One row in the evaluation report."""

    task_id: str
    step: int
    judge_score: JudgeScore
    error: str | None = None


class EvalReport(BaseModel):
    """Full evaluation report produced by the pipeline."""

    report_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_records: int = 0
    scored_records: int = 0
    failed_records: int = 0
    mean_score: float = 0.0
    score_distribution: dict[int, int] = Field(default_factory=dict)
    failure_category_counts: dict[str, int] = Field(default_factory=dict)
    entries: list[EvalReportEntry] = Field(default_factory=list)


def load_golden_set(path: Path) -> list[EvalRecord]:
    """Load EvalRecords from a JSONL file."""
    records: list[EvalRecord] = []
    if not path.exists():
        return records
    for line in path.read_text().strip().split("\n"):
        if line.strip():
            try:
                records.append(EvalRecord.model_validate_json(line))
            except Exception as exc:
                logger.warning("Skipping invalid record: %s", exc)
    return records


async def run_eval_pipeline(
    golden_set: list[EvalRecord],
    llm_service: Any,
    judge_profile: ModelProfile,
    report_id: str = "eval-report",
    taxonomy: dict[str, Any] | None = None,
) -> EvalReport:
    """Run the full evaluation pipeline: score each record, produce report."""
    if taxonomy is None:
        taxonomy = load_taxonomy()

    entries: list[EvalReportEntry] = []
    scores: list[int] = []
    category_counts: dict[str, int] = {}
    failed = 0

    for record in golden_set:
        try:
            result: JudgeResult = await score_eval_record(
                record, llm_service, judge_profile, taxonomy
            )
            entry = EvalReportEntry(
                task_id=result.task_id,
                step=result.step,
                judge_score=result.judge_score,
            )
            scores.append(result.judge_score.score)
            for cat in result.judge_score.failure_categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1
        except Exception as exc:
            logger.error("Pipeline error for %s: %s", record.task_id, exc)
            entry = EvalReportEntry(
                task_id=record.task_id,
                step=record.step,
                judge_score=JudgeScore(score=1, reasoning=f"Pipeline error: {exc}"),
                error=str(exc),
            )
            failed += 1
        entries.append(entry)

    score_dist: dict[int, int] = {}
    for s in scores:
        score_dist[s] = score_dist.get(s, 0) + 1

    mean = sum(scores) / len(scores) if scores else 0.0

    return EvalReport(
        report_id=report_id,
        total_records=len(golden_set),
        scored_records=len(scores),
        failed_records=failed,
        mean_score=mean,
        score_distribution=score_dist,
        failure_category_counts=category_counts,
        entries=entries,
    )


def save_report(report: EvalReport, output_path: Path) -> None:
    """Write the report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2))
    logger.info("Report saved to %s", output_path)
