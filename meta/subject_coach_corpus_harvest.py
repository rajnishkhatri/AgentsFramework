"""Phase-3 corpus harvest — coach shadow traffic → coding-ready corpus rows.

A ``meta/`` job (invariant #8: reads captured logs, never the live graph). The
plan's decided Phase-3 corpus path is production shadow traffic: eval_capture's
console handler ships every ``target="subject_coach"`` record to Cloud Logging;
this job turns an export of that stream into deduped corpus rows split by mode,
plus an honest count-based report against the Phase-3 entry gate
(>= ``GATE_TURNS_PER_MODE`` turns per mode).

Export command (``agent-backend-combined`` is the live backend service):

    gcloud logging read '
      resource.type="cloud_run_revision"
      resource.labels.service_name="agent-backend-combined"
      jsonPayload.target="subject_coach"
    ' --freshness=7d --format=json > export.json

The local dev stream works unchanged: ``logs/evals.log`` lines are the same
JSON objects without the Cloud Logging envelope.

Usage (idempotent — re-runs append only unseen task_ids):

    .venv/bin/python -m meta.subject_coach_corpus_harvest \
        --input export.json --output coach_corpus.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from components.schemas import EvalRecord
from meta.analysis import records_for_target
from meta.subject_coach_judge_sampler import latest_turn_per_task, mode_of

logger = logging.getLogger("meta.subject_coach_corpus_harvest")

__all__ = [
    "GATE_TURNS_PER_MODE",
    "CoachCorpusRow",
    "HarvestReport",
    "harvest_corpus",
    "main",
    "parse_harvest_object",
    "parse_harvest_stream",
]

COACH_TARGET = "subject_coach"

# Phase-3 entry gate (plan): >= 100 coded turns per mode from production traffic.
GATE_TURNS_PER_MODE = 100

_MODES = ("pre_submit", "post_feedback")

CoachMode = Literal["pre_submit", "post_feedback"]


class CoachCorpusRow(BaseModel):
    """One coach turn, ready for Stage-1/2 open coding."""

    task_id: str
    user_id: str
    timestamp: datetime
    mode: CoachMode
    learner_utterance: str
    coach_reply: str
    model: str | None = None
    step: int
    provenance: Literal["production", "synthetic"] = "production"


class HarvestReport(BaseModel):
    """Counts only — never a fabricated quality/coverage metric (AP-6)."""

    total_records: int = 0
    coach_records: int = 0
    deduped: int = 0
    per_mode: dict[str, int] = {}
    gate_met: bool = False
    shortfall: dict[str, int] = {}


def parse_harvest_object(obj: object) -> EvalRecord | None:
    """One exported entry → EvalRecord, fail-closed.

    Accepts either the raw eval-log JSON object (fields at top level) or a
    Cloud Logging entry (the record nested under ``jsonPayload``). Anything
    malformed returns ``None`` — a poisoned line must never sink the batch.
    """
    if not isinstance(obj, dict):
        return None
    payload = obj.get("jsonPayload", obj)
    if not isinstance(payload, dict):
        return None
    try:
        return EvalRecord.model_validate(payload)
    except ValidationError:
        return None


def parse_harvest_stream(text: str) -> tuple[list[EvalRecord], int]:
    """Parse an export file: JSONL (local log) or one JSON array (gcloud).

    Returns ``(records, skipped)`` — malformed lines/entries are counted,
    never raised past (the §13 garbage-in guard applied to the harvest).
    """
    stripped = text.strip()
    if not stripped:
        return [], 0

    candidates: list[object] = []
    skipped = 0
    if stripped.startswith("["):
        try:
            candidates = json.loads(stripped)
        except json.JSONDecodeError:
            candidates = []
    if not candidates:
        for line in stripped.splitlines():
            if not line.strip():
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                skipped += 1

    records: list[EvalRecord] = []
    for obj in candidates:
        rec = parse_harvest_object(obj)
        if rec is None:
            skipped += 1
        else:
            records.append(rec)
    return records, skipped


def _gate(per_mode: dict[str, int]) -> tuple[bool, dict[str, int]]:
    shortfall = {
        mode: max(0, GATE_TURNS_PER_MODE - per_mode.get(mode, 0)) for mode in _MODES
    }
    return all(count == 0 for count in shortfall.values()), shortfall


def harvest_corpus(
    records: list[EvalRecord],
    *,
    existing_task_ids: set[str] | frozenset[str] = frozenset(),
    provenance: Literal["production", "synthetic"] = "production",
) -> tuple[list[CoachCorpusRow], HarvestReport]:
    """Coach records → one corpus row per task (latest turn), deduped.

    Mode derivation reuses the sampler's fail-closed ``mode_of`` (the F1
    ``coach_mode`` carrier preferred; unknown ⇒ ``pre_submit``, the stricter
    rubric). The report's gate section covers ONLY the rows returned here —
    callers holding a pre-existing corpus should re-summarize the union
    (``main`` does).
    """
    report = HarvestReport(total_records=len(records))
    coach_records = records_for_target(records, COACH_TARGET)
    report.coach_records = len(coach_records)

    rows: list[CoachCorpusRow] = []
    for rec in latest_turn_per_task(coach_records):
        if rec.task_id in existing_task_ids:
            report.deduped += 1
            continue
        reply = (
            rec.ai_response
            if isinstance(rec.ai_response, str)
            else str(rec.ai_response)
        )
        rows.append(
            CoachCorpusRow(
                task_id=rec.task_id,
                user_id=rec.user_id,
                timestamp=rec.timestamp,
                mode=mode_of(rec),  # type: ignore[arg-type]  # closed vocab by construction
                learner_utterance=str(rec.ai_input.get("task_input", "")),
                coach_reply=reply,
                model=rec.model,
                step=rec.step,
                provenance=provenance,
            )
        )

    report.per_mode = {
        mode: sum(1 for row in rows if row.mode == mode) for mode in _MODES
    }
    report.gate_met, report.shortfall = _gate(report.per_mode)
    return rows, report


def _load_existing_rows(path: Path) -> list[CoachCorpusRow]:
    if not path.exists():
        return []
    rows: list[CoachCorpusRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(CoachCorpusRow.model_validate_json(line))
        except ValidationError:
            logger.warning("corpus file %s: skipping malformed row", path)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="export file (JSONL or array)")
    parser.add_argument("--output", required=True, help="corpus JSONL (append/dedupe)")
    parser.add_argument(
        "--provenance",
        choices=["production", "synthetic"],
        default="production",
        help="label stamped on every harvested row (default: production)",
    )
    args = parser.parse_args(argv)

    source = Path(args.input)
    if not source.exists():
        print(f"input not found: {source}")
        return 1

    records, skipped = parse_harvest_stream(source.read_text(encoding="utf-8"))
    out_path = Path(args.output)
    existing = _load_existing_rows(out_path)
    rows, report = harvest_corpus(
        records,
        existing_task_ids={row.task_id for row in existing},
        provenance=args.provenance,
    )

    if rows:
        with out_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(row.model_dump_json() + "\n")

    # The gate verdict the operator acts on covers the WHOLE corpus file.
    corpus = existing + rows
    per_mode = {mode: sum(1 for row in corpus if row.mode == mode) for mode in _MODES}
    gate_met, shortfall = _gate(per_mode)
    print(
        f"harvest: {report.total_records} records ({skipped} skipped) -> "
        f"{report.coach_records} coach -> {len(rows)} new rows "
        f"({report.deduped} already in corpus)"
    )
    print(
        f"corpus: {len(corpus)} turns | per-mode {per_mode} | "
        f"phase-3 gate ({GATE_TURNS_PER_MODE}/mode): "
        + ("MET" if gate_met else f"NOT MET, shortfall {shortfall}")
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
