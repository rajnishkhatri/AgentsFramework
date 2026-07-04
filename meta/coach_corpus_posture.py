"""Phase-3 environment posture checker — the garbage-in guard before coding.

A ``meta/`` job (invariant #8: reads captured logs, never the live graph).
Classifies each coach turn's environment posture from the EvalRecord stream
ONLY (C9 — not a blackbox guardrail join) plus an optional batch manifest:

  - ``coding_eligible``     — clean; counts toward the >= 100/mode gate
  - ``confound``            — manifest mode mismatch (FR-G1.1) OR missing mode
                              carrier (FR-G1.2); excluded from the coach-behavior
                              coding sample entirely
  - ``partial_context``     — pre_submit AND eval-capture truncated ``task_input``
                              at the 200-char cap (FR-G1.3); eligible for open
                              coding, EXCLUDED from gold-set test-split holdout
                              candidacy (full-text manifest join required at
                              assembly — FR-G5.6)

Counts only — never a fabricated quality score (AP-6). Mode derivation reuses
the sampler's fail-closed ``mode_of``; carrier *presence* is checked here
because ``mode_of`` silently defaults to ``pre_submit`` and the posture layer
must NOT trust a default as a real mode signal (FR-G1.2).
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from components.schemas import EvalRecord
from meta.subject_coach_corpus_harvest import GATE_TURNS_PER_MODE
from meta.subject_coach_judge_sampler import (
    COACH_TARGET,
    latest_turn_per_task,
    mode_of,
)
from meta.analysis import records_for_target

logger = logging.getLogger("meta.coach_corpus_posture")

__all__ = [
    "EVAL_CAPTURE_TASK_INPUT_CAP",
    "ManifestModeMap",
    "PostureClassification",
    "PostureReport",
    "check_posture",
    "load_manifest_mode_map",
]

# Eval-capture hard cap on coach ``task_input`` (react_loop.py:2374 —
# ``state.get("task_input", "")[:200]``). No truncation marker is recorded, so a
# row whose recorded length == cap is treated as truncated (the spec accepts
# this heuristic — a naturally-exactly-cap input is rare and only flags for a
# manifest join, never excludes from coding). Coach reply cap is 500 (C12) but
# only task_input truncation gates holdout candidacy.
EVAL_CAPTURE_TASK_INPUT_CAP = 200

_MODES = ("pre_submit", "post_feedback")

Classification = Literal["coding_eligible", "confound", "partial_context"]

# The legacy pre-F1 marker reused by ``mode_of`` — a coach turn with neither the
# ``coach_mode`` carrier NOR this marker has no verifiable mode signal.
_POST_FEEDBACK_MARKER = '"mode": "post_feedback"'

_CONFOUND_REASONS = {"manifest_mode_mismatch", "missing_mode_carrier"}


class PostureClassification(BaseModel):
    """One coach turn's posture verdict."""

    task_id: str
    mode: str  # derived mode (mode_of) — present even for confounds for telemetry
    classification: Classification
    reason: str | None = None  # set for confound / partial_context

    @property
    def is_confound(self) -> bool:
        return self.classification == "confound"


class PostureReport(BaseModel):
    """Counts only — never a fabricated quality/coverage metric (AP-6)."""

    coding_eligible: int = 0
    confound_rows: int = 0
    partial_context_rows: int = 0
    per_mode: dict[str, int] = {}  # coding_eligible counts per mode
    shortfall: dict[str, int] = {}


class ManifestModeMap:
    """Utterance → authored manifest row for the synthetic-batch manifest.

    Production harvest has no manifest (``expected_mode`` returns ``None`` and
    FR-G1.1 is skipped). Built from the ``manifest.json`` shape
    ``[{mode, utterance, question_id, cls, index}, ...]``. The mode map drives
    posture (FR-G1.1); ``row_for`` exposes ``question_id``/``cls`` (stratum) for
    the coding-sample export's C11 field map.
    """

    def __init__(self, mapping: dict[str, str], rows: dict[str, dict]) -> None:
        self._mapping = mapping
        self._rows = rows

    def expected_mode(self, utterance: str) -> str | None:
        return self._mapping.get(utterance)

    def row_for(self, utterance: str) -> dict | None:
        return self._rows.get(utterance)


def load_manifest_mode_map(rows: list[dict]) -> ManifestModeMap:
    """Build an utterance→manifest map from manifest rows.

    Raises ``ValueError`` if the same utterance is authored under conflicting
    modes (a manifest bug — silently picking one would hide a posture defect).
    """
    mapping: dict[str, str] = {}
    by_utterance: dict[str, dict] = {}
    for row in rows:
        utterance = row.get("utterance")
        mode = row.get("mode")
        if not utterance or not mode:
            continue
        prior = mapping.get(utterance)
        if prior is not None and prior != mode:
            raise ValueError(
                f"manifest utterance authored under conflicting modes: "
                f"{utterance!r} -> {prior!r} vs {mode!r}"
            )
        mapping[utterance] = mode
        by_utterance[utterance] = row
    return ManifestModeMap(mapping, by_utterance)


def _has_mode_signal(rec: EvalRecord) -> tuple[str, bool]:
    """Return ``(derived_mode, carrier_present)``.

    ``carrier_present`` is True when either the ``coach_mode`` carrier is set OR
    the legacy post_feedback marker is in ``task_input`` (mode_of's two
    resolution paths). A turn with neither has no verifiable mode signal and is
    a confound per FR-G1.2 — ``mode_of`` would silently default it to
    ``pre_submit``, which the posture layer must not trust.
    """
    derived = mode_of(rec)
    task_input = str(rec.ai_input.get("task_input", ""))
    carrier_present = (
        "coach_mode" in rec.ai_input or _POST_FEEDBACK_MARKER in task_input
    )
    return derived, carrier_present


def _classify(
    rec: EvalRecord, *, manifest: ManifestModeMap | None
) -> PostureClassification:
    derived_mode, carrier_present = _has_mode_signal(rec)
    task_input = str(rec.ai_input.get("task_input", ""))

    if not carrier_present:
        return PostureClassification(
            task_id=rec.task_id,
            mode=derived_mode,
            classification="confound",
            reason="missing_mode_carrier",
        )

    if manifest is not None:
        expected = manifest.expected_mode(task_input)
        if expected is not None and expected != derived_mode:
            return PostureClassification(
                task_id=rec.task_id,
                mode=derived_mode,
                classification="confound",
                reason="manifest_mode_mismatch",
            )

    # FR-G1.3: pre_submit truncation → partial_context (still coding-eligible,
    # excluded from holdout candidacy). The cap check uses the recorded length;
    # eval capture always truncates when source > cap and records no marker.
    if derived_mode == "pre_submit" and len(task_input) >= EVAL_CAPTURE_TASK_INPUT_CAP:
        return PostureClassification(
            task_id=rec.task_id,
            mode=derived_mode,
            classification="partial_context",
            reason="eval_capture_truncated_task_input",
        )

    return PostureClassification(
        task_id=rec.task_id,
        mode=derived_mode,
        classification="coding_eligible",
    )


def _shortfall(per_mode: dict[str, int]) -> dict[str, int]:
    return {
        mode: max(0, GATE_TURNS_PER_MODE - per_mode.get(mode, 0)) for mode in _MODES
    }


def check_posture(
    records: list[EvalRecord],
    *,
    manifest: ManifestModeMap | None = None,
) -> tuple[list[PostureClassification], PostureReport]:
    """EvalRecords → per-turn posture verdicts + a counts-only report.

    Reuses the sampler's ``records_for_target`` + ``latest_turn_per_task`` so a
    multi-step task is collapsed to its final turn (the reply the learner saw).
    Confounds are excluded from ``coding_eligible`` and from ``per_mode``; a
    ``partial_context`` row is its own bucket — never counted as eligible.
    """
    coach = records_for_target(records, COACH_TARGET)
    turns = latest_turn_per_task(coach)

    classified: list[PostureClassification] = []
    report = PostureReport()
    per_mode: dict[str, int] = {mode: 0 for mode in _MODES}

    for rec in turns:
        verdict = _classify(rec, manifest=manifest)
        classified.append(verdict)
        if verdict.classification == "coding_eligible":
            report.coding_eligible += 1
            if verdict.mode in per_mode:
                per_mode[verdict.mode] += 1
        elif verdict.classification == "confound":
            report.confound_rows += 1
        elif verdict.classification == "partial_context":
            report.partial_context_rows += 1

    report.per_mode = per_mode
    report.shortfall = _shortfall(per_mode)
    logger.info(
        "posture: %d turns -> %d eligible, %d confound, %d partial_context | "
        "per_mode %s | shortfall %s",
        len(turns),
        report.coding_eligible,
        report.confound_rows,
        report.partial_context_rows,
        per_mode,
        report.shortfall,
    )
    return classified, report
