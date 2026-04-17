"""Drift detection: three-level monitoring for agent performance.

Level 1 (weekly): Performance drift vs baseline (2-sigma threshold)
Level 2 (monthly): Judge calibration drift (Cohen's kappa)
Level 3: Governance artifact drift (AgentFacts integrity)
"""

from __future__ import annotations

import logging
import math
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("meta.drift")


class DriftAlert(BaseModel):
    """Structured alert emitted when drift is detected."""

    level: int
    alert_type: str
    metric_name: str
    baseline_value: float
    current_value: float
    threshold: float
    message: str
    triggered: bool = True


class DriftReport(BaseModel):
    """Combined report from all drift detection levels."""

    alerts: list[DriftAlert] = Field(default_factory=list)
    level1_checked: bool = False
    level2_checked: bool = False
    level3_checked: bool = False

    @property
    def has_drift(self) -> bool:
        return any(a.triggered for a in self.alerts)


# ── Level 1: Performance drift ──────────────────────────────────────


def detect_performance_drift(
    baseline_scores: list[float],
    production_scores: list[float],
    sigma_threshold: float = 2.0,
) -> list[DriftAlert]:
    """Compare production scores against baseline using 2-sigma threshold."""
    alerts: list[DriftAlert] = []

    if not baseline_scores or not production_scores:
        return alerts

    baseline_mean = sum(baseline_scores) / len(baseline_scores)
    baseline_var = sum((x - baseline_mean) ** 2 for x in baseline_scores) / len(baseline_scores)
    baseline_std = math.sqrt(baseline_var) if baseline_var > 0 else 0.0

    production_mean = sum(production_scores) / len(production_scores)

    if baseline_std == 0:
        if production_mean != baseline_mean:
            alerts.append(DriftAlert(
                level=1,
                alert_type="performance_drift",
                metric_name="mean_score",
                baseline_value=baseline_mean,
                current_value=production_mean,
                threshold=sigma_threshold,
                message=f"Score changed from {baseline_mean:.3f} to {production_mean:.3f} (zero-variance baseline)",
            ))
        return alerts

    z_score = abs(production_mean - baseline_mean) / baseline_std

    if z_score >= sigma_threshold:
        alerts.append(DriftAlert(
            level=1,
            alert_type="performance_drift",
            metric_name="mean_score",
            baseline_value=baseline_mean,
            current_value=production_mean,
            threshold=sigma_threshold,
            message=(
                f"Performance drift detected: baseline={baseline_mean:.3f}, "
                f"production={production_mean:.3f}, z={z_score:.2f} >= {sigma_threshold}"
            ),
        ))

    return alerts


# ── Level 2: Judge calibration drift ────────────────────────────────


def compute_cohens_kappa(
    ratings_a: list[int],
    ratings_b: list[int],
    num_categories: int = 5,
) -> float:
    """Compute Cohen's kappa for two sets of ordinal ratings."""
    if len(ratings_a) != len(ratings_b) or not ratings_a:
        return 0.0

    n = len(ratings_a)
    confusion = [[0] * num_categories for _ in range(num_categories)]

    for a, b in zip(ratings_a, ratings_b):
        ai = max(0, min(a - 1, num_categories - 1))
        bi = max(0, min(b - 1, num_categories - 1))
        confusion[ai][bi] += 1

    po = sum(confusion[i][i] for i in range(num_categories)) / n

    row_sums = [sum(confusion[i]) for i in range(num_categories)]
    col_sums = [sum(confusion[j][i] for j in range(num_categories)) for i in range(num_categories)]
    pe = sum(row_sums[i] * col_sums[i] for i in range(num_categories)) / (n * n)

    if pe == 1.0:
        return 1.0

    return (po - pe) / (1 - pe)


def detect_calibration_drift(
    human_labels: list[int],
    judge_labels: list[int],
    kappa_threshold: float = 0.75,
) -> list[DriftAlert]:
    """Level 2: check judge calibration via Cohen's kappa."""
    alerts: list[DriftAlert] = []

    kappa = compute_cohens_kappa(human_labels, judge_labels)

    if kappa < kappa_threshold:
        alerts.append(DriftAlert(
            level=2,
            alert_type="calibration_drift",
            metric_name="cohens_kappa",
            baseline_value=kappa_threshold,
            current_value=kappa,
            threshold=kappa_threshold,
            message=(
                f"Judge calibration drift: kappa={kappa:.3f} < {kappa_threshold} threshold"
            ),
        ))

    return alerts


# ── Level 3: Governance artifact drift ──────────────────────────────


def detect_governance_drift(
    agent_facts_registry: Any,
) -> list[DriftAlert]:
    """Level 3: verify all registered agent identities are intact."""
    alerts: list[DriftAlert] = []

    if agent_facts_registry is None:
        return alerts

    storage_dir = getattr(agent_facts_registry, "_storage_dir", None)
    if storage_dir is None:
        return alerts

    from pathlib import Path
    storage = Path(storage_dir)
    if not storage.exists():
        return alerts

    total = 0
    failed = 0
    for facts_file in storage.glob("*.json"):
        if facts_file.name.endswith("_audit.jsonl"):
            continue
        agent_id = facts_file.stem
        total += 1
        try:
            if not agent_facts_registry.verify(agent_id):
                failed += 1
                alerts.append(DriftAlert(
                    level=3,
                    alert_type="governance_drift",
                    metric_name="agent_facts_integrity",
                    baseline_value=1.0,
                    current_value=0.0,
                    threshold=1.0,
                    message=f"AgentFacts integrity check failed for agent_id={agent_id!r}",
                ))
        except Exception as exc:
            failed += 1
            alerts.append(DriftAlert(
                level=3,
                alert_type="governance_drift",
                metric_name="agent_facts_integrity",
                baseline_value=1.0,
                current_value=0.0,
                threshold=1.0,
                message=f"AgentFacts verification error for {agent_id!r}: {exc}",
            ))

    return alerts


# ── STORY-406: PhaseLogger drift alerting integration ─────────────


def emit_drift_alerts(
    report: "DriftReport",
    phase_logger: Any,
    workflow_id: str,
) -> int:
    """Emit one ``Decision`` per triggered alert in ``report``.

    Each alert is forwarded to ``phase_logger.log_decision`` so the
    governance trail correlates with the originating workflow. The call
    is wrapped in try/except to keep the drift loop non-blocking: a
    crashing PhaseLogger MUST NOT stop us from reporting drift to
    operators -- failures are mirrored to stderr and the next alert is
    still attempted.

    Returns the number of alerts that were successfully logged.

    Args:
        report: The report produced by ``run_full_drift_check``.
        phase_logger: A ``services.governance.phase_logger.PhaseLogger``
            instance (or any object exposing ``log_decision``).
        workflow_id: Correlation id used by the governance trail.
    """
    if phase_logger is None or not report.has_drift:
        return 0

    # Imported lazily so ``meta/`` does not pay the import cost when no
    # alerting target is configured (and so the module remains usable
    # in environments where services/ is partially bootstrapped).
    try:
        from services.governance.phase_logger import (
            Decision,
            WorkflowPhase,
        )
    except Exception as exc:  # pragma: no cover - defensive import
        import sys

        print(
            f"[meta.drift] PhaseLogger import failed: {exc}; "
            f"alerts NOT logged for workflow_id={workflow_id!r}",
            file=sys.stderr,
        )
        return 0

    logged = 0
    for alert in report.alerts:
        if not alert.triggered:
            continue
        description = (
            f"Drift L{alert.level} ({alert.alert_type}): "
            f"{alert.metric_name} "
            f"baseline={alert.baseline_value:.4f} "
            f"current={alert.current_value:.4f}"
        )
        decision = Decision(
            phase=WorkflowPhase.EVALUATION,
            description=description,
            alternatives=["ignore", "retrain", "rollback"],
            rationale=alert.message,
            confidence=1.0,
        )
        try:
            phase_logger.log_decision(workflow_id, decision)
            logged += 1
        except Exception as exc:
            import sys

            print(
                f"[meta.drift] PhaseLogger.log_decision failed for "
                f"alert={alert.alert_type!r} workflow_id={workflow_id!r}: "
                f"{exc}",
                file=sys.stderr,
            )

    return logged


def run_full_drift_check(
    baseline_scores: list[float] | None = None,
    production_scores: list[float] | None = None,
    human_labels: list[int] | None = None,
    judge_labels: list[int] | None = None,
    agent_facts_registry: Any = None,
    sigma_threshold: float = 2.0,
    kappa_threshold: float = 0.75,
) -> DriftReport:
    """Run all three drift detection levels and return a combined report."""
    report = DriftReport()

    if baseline_scores is not None and production_scores is not None:
        report.level1_checked = True
        report.alerts.extend(
            detect_performance_drift(baseline_scores, production_scores, sigma_threshold)
        )

    if human_labels is not None and judge_labels is not None:
        report.level2_checked = True
        report.alerts.extend(
            detect_calibration_drift(human_labels, judge_labels, kappa_threshold)
        )

    if agent_facts_registry is not None:
        report.level3_checked = True
        report.alerts.extend(detect_governance_drift(agent_facts_registry))

    return report


# ── CLI helpers ─────────────────────────────────────────────────────


def _load_scores(path: str) -> list[float]:
    """Load float scores from JSONL (one per line, or JSON objects with 'score' field)."""
    import json
    from pathlib import Path

    scores: list[float] = []
    for line in Path(path).read_text().strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                scores.append(float(obj["score"]))
            else:
                scores.append(float(obj))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.warning("Skipping unparseable line in %s: %s", path, line)
    return scores


def _load_label_pairs(
    baseline_path: str, production_path: str
) -> tuple[list[int], list[int]]:
    """Load integer label pairs from two JSONL files."""
    import json
    from pathlib import Path

    def _read_labels(p: str) -> list[int]:
        labels: list[int] = []
        for line in Path(p).read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    labels.append(int(obj["label"]))
                else:
                    labels.append(int(obj))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                logger.warning("Skipping unparseable line in %s: %s", p, line)
        return labels

    return _read_labels(baseline_path), _read_labels(production_path)


class _RegistryStub:
    """Minimal registry-like object for Level 3 governance drift checks."""

    def __init__(self, registry_path: Any) -> None:
        from pathlib import Path

        self._storage_dir = Path(registry_path)

    def verify(self, agent_id: str) -> bool:
        import json
        from trust.signature import verify_signature
        from trust.models import AgentFacts

        facts_file = self._storage_dir / f"{agent_id}.json"
        data = json.loads(facts_file.read_text())
        facts = AgentFacts(**data)
        return verify_signature(facts)


def _create_registry_stub(registry_path: Any) -> _RegistryStub:
    """Create a minimal object with _storage_dir and verify() for Level 3 checks."""
    return _RegistryStub(registry_path)


# ── CLI entrypoint ──────────────────────────────────────────────────


def run_drift_cli(args: list[str] | None = None) -> int:
    """CLI entrypoint for drift detection.

    Returns exit code: 0=no drift, 1=drift detected, 2=error.
    """
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Drift detection CLI")
    parser.add_argument("--baseline", type=str, help="Path to baseline scores JSONL")
    parser.add_argument("--production", type=str, help="Path to production scores JSONL")
    parser.add_argument(
        "--registry-dir", type=str, help="Path to AgentFacts registry directory"
    )
    parser.add_argument(
        "--level",
        type=str,
        default="all",
        choices=["1", "2", "3", "all"],
        help="Which drift level to check (default: all)",
    )
    parser.add_argument(
        "--output", type=str, help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--alert-log-dir",
        type=str,
        help=(
            "When set, drift alerts are emitted as governance Decisions "
            "into a PhaseLogger rooted at this directory (STORY-406)."
        ),
    )
    parser.add_argument(
        "--workflow-id",
        type=str,
        default="drift-check",
        help="Correlation id used when emitting alerts to PhaseLogger.",
    )
    parsed = parser.parse_args(args)

    try:
        baseline_scores = None
        production_scores = None
        human_labels = None
        judge_labels = None
        registry = None

        levels = [parsed.level] if parsed.level != "all" else ["1", "2", "3"]

        if "1" in levels and parsed.baseline and parsed.production:
            baseline_scores = _load_scores(parsed.baseline)
            production_scores = _load_scores(parsed.production)

        if "2" in levels and parsed.baseline and parsed.production:
            human_labels, judge_labels = _load_label_pairs(
                parsed.baseline, parsed.production
            )

        if "3" in levels and parsed.registry_dir:
            registry_path = Path(parsed.registry_dir)
            if not registry_path.exists():
                logger.error(
                    "Registry directory does not exist: %s", parsed.registry_dir
                )
                return 2
            registry = _create_registry_stub(registry_path)

        report = run_full_drift_check(
            baseline_scores=baseline_scores,
            production_scores=production_scores,
            human_labels=human_labels,
            judge_labels=judge_labels,
            agent_facts_registry=registry,
        )

        output_json = report.model_dump_json(indent=2)
        if parsed.output:
            Path(parsed.output).parent.mkdir(parents=True, exist_ok=True)
            Path(parsed.output).write_text(output_json)
            logger.info("Report written to %s", parsed.output)
        else:
            print(output_json)

        # STORY-406: optional governance decision log for triggered alerts.
        if parsed.alert_log_dir and report.has_drift:
            try:
                from services.governance.phase_logger import PhaseLogger

                phase_logger = PhaseLogger(storage_dir=parsed.alert_log_dir)
                logged = emit_drift_alerts(
                    report, phase_logger, parsed.workflow_id
                )
                logger.info(
                    "Emitted %d drift alert(s) to PhaseLogger at %s",
                    logged,
                    parsed.alert_log_dir,
                )
            except Exception as exc:
                logger.error("Drift alert emission failed: %s", exc)

        return 1 if report.has_drift else 0

    except Exception as exc:
        logger.error("Drift check failed: %s", exc)
        return 2


if __name__ == "__main__":
    import sys

    sys.exit(run_drift_cli())
