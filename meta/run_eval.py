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


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Not a GCS URI: {uri}")
    bucket, _, blob = uri[5:].partition("/")
    if not bucket or not blob:
        raise ValueError(f"GCS URI must include bucket and object path: {uri}")
    return bucket, blob


def _download_gcs(uri: str, dest: Path) -> Path:
    from google.cloud import storage

    bucket_name, blob_name = _parse_gs_uri(uri)
    dest.parent.mkdir(parents=True, exist_ok=True)
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(str(dest))
    return dest


def _upload_gcs(local_path: Path, uri: str) -> None:
    from google.cloud import storage

    bucket_name, blob_name = _parse_gs_uri(uri)
    storage.Client().bucket(bucket_name).blob(blob_name).upload_from_filename(
        str(local_path),
        content_type="application/json",
    )


def resolve_input_path(path: str, *, cache_dir: Path = Path("/tmp/meta_eval")) -> Path:
    """Resolve a local path or download ``gs://`` object to a cache file."""
    if path.startswith("gs://"):
        suffix = Path(_parse_gs_uri(path)[1]).suffix or ".jsonl"
        dest = cache_dir / f"golden{suffix}"
        return _download_gcs(path, dest)
    return Path(path)


def persist_output_path(report: EvalReport, path: str, *, cache_dir: Path = Path("/tmp/meta_eval")) -> Path:
    """Write report locally and optionally upload to ``gs://``."""
    if path.startswith("gs://"):
        local_path = cache_dir / "report.json"
        save_report(report, local_path)
        _upload_gcs(local_path, path)
        logger.info("Report uploaded to %s", path)
        return local_path
    local_path = Path(path)
    save_report(report, local_path)
    return local_path


def _judge_profile_from_env() -> ModelProfile:
    name = __import__("os").environ.get("META_JUDGE_MODEL", "gpt-4o-mini")
    return ModelProfile(
        name=name,
        litellm_id=f"openai/{name}",
        tier="fast",
        context_window=128_000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def run_eval_cli(args: list[str] | None = None) -> int:
    """CLI entry point for Cloud Run Jobs and local ``python -m meta.run_eval``."""
    import argparse
    import asyncio
    import sys

    from services.base_config import AgentConfig
    from services.llm_config import LLMService

    parser = argparse.ArgumentParser(description="Run the meta evaluation scoring pipeline.")
    parser.add_argument(
        "--golden-set",
        required=True,
        help="Local path or gs:// URI to the golden-set JSONL file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Local path or gs:// URI for the eval report JSON output.",
    )
    parser.add_argument(
        "--report-id",
        default="meta-eval-report",
        help="Report identifier embedded in the output JSON.",
    )
    parsed = parser.parse_args(args)

    try:
        golden_path = resolve_input_path(parsed.golden_set)
        golden = load_golden_set(golden_path)
        if not golden:
            print(
                f"ERROR: golden set is empty or missing at {parsed.golden_set}",
                file=sys.stderr,
            )
            return 2

        judge_profile = _judge_profile_from_env()
        llm_service = LLMService(
            AgentConfig(default_model=judge_profile.name, models=[judge_profile])
        )
        report = asyncio.run(
            run_eval_pipeline(
                golden_set=golden,
                llm_service=llm_service,
                judge_profile=judge_profile,
                report_id=parsed.report_id,
            )
        )
        persist_output_path(report, parsed.output)
        print(
            f"Eval complete: scored={report.scored_records} "
            f"failed={report.failed_records} mean={report.mean_score:.2f}"
        )
        return 0
    except Exception as exc:
        logger.error("Meta eval CLI failed: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import sys

    sys.exit(run_eval_cli())
