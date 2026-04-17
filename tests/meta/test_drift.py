"""L2 Contract: Drift detection tests (Story 4.2).

Tests three-level drift detection with known baseline/production data.
"""

from __future__ import annotations

import pytest

from meta.drift import (
    DriftAlert,
    DriftReport,
    compute_cohens_kappa,
    detect_calibration_drift,
    detect_governance_drift,
    detect_performance_drift,
    run_drift_cli,
    run_full_drift_check,
)
from services.governance.agent_facts_registry import AgentFactsRegistry
from trust.models import AgentFacts


class TestPerformanceDrift:
    def test_drift_detected_above_2sigma(self):
        baseline = [4.0, 4.2, 3.8, 4.1, 3.9, 4.0, 4.1, 3.8, 4.2, 4.0]
        production = [2.0, 2.1, 1.9, 2.2, 2.0, 1.8, 2.1, 2.0, 1.9, 2.1]

        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "performance_drift"
        assert alerts[0].triggered is True

    def test_no_drift_when_stable(self):
        baseline = [4.0, 4.1, 3.9, 4.0, 4.2]
        production = [4.0, 3.9, 4.1, 4.0, 4.0]

        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) == 0

    def test_empty_inputs_no_alerts(self):
        assert detect_performance_drift([], []) == []
        assert detect_performance_drift([1.0], []) == []
        assert detect_performance_drift([], [1.0]) == []


class TestCalibrationDrift:
    def test_low_kappa_triggers_alert(self):
        human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        judge = [5, 4, 3, 2, 1, 5, 4, 3, 2, 1]

        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "calibration_drift"

    def test_high_kappa_no_alert(self):
        human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        judge = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]

        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) == 0

    def test_cohens_kappa_perfect_agreement(self):
        a = [1, 2, 3, 4, 5]
        b = [1, 2, 3, 4, 5]
        kappa = compute_cohens_kappa(a, b)
        assert kappa == pytest.approx(1.0)

    def test_cohens_kappa_no_agreement(self):
        a = [1, 1, 1, 1, 1]
        b = [5, 5, 5, 5, 5]
        kappa = compute_cohens_kappa(a, b)
        assert kappa <= 0.0  # No agreement


class TestGovernanceDrift:
    def test_tampered_agent_facts_triggers_alert(self, tmp_path):
        registry = AgentFactsRegistry(
            storage_dir=tmp_path / "facts", secret="test-secret"
        )
        registry.register(
            AgentFacts(
                agent_id="agent-ok",
                agent_name="OK Bot",
                owner="test",
                version="1.0.0",
            ),
            registered_by="test",
        )

        import json
        facts_file = tmp_path / "facts" / "agent-ok.json"
        data = json.loads(facts_file.read_text())
        data["agent_name"] = "Tampered Name"
        facts_file.write_text(json.dumps(data))

        alerts = detect_governance_drift(registry)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "governance_drift"

    def test_valid_agent_facts_no_alert(self, tmp_path):
        registry = AgentFactsRegistry(
            storage_dir=tmp_path / "facts", secret="test-secret"
        )
        registry.register(
            AgentFacts(
                agent_id="agent-valid",
                agent_name="Valid Bot",
                owner="test",
                version="1.0.0",
            ),
            registered_by="test",
        )

        alerts = detect_governance_drift(registry)
        assert len(alerts) == 0


class TestFullDriftCheck:
    def test_combined_report_has_all_levels(self, tmp_path):
        registry = AgentFactsRegistry(
            storage_dir=tmp_path / "facts", secret="test-secret"
        )
        registry.register(
            AgentFacts(
                agent_id="agent-1",
                agent_name="Bot",
                owner="test",
                version="1.0.0",
            ),
            registered_by="test",
        )

        report = run_full_drift_check(
            baseline_scores=[4.0, 4.0, 4.0],
            production_scores=[4.0, 4.0, 4.0],
            human_labels=[1, 2, 3],
            judge_labels=[1, 2, 3],
            agent_facts_registry=registry,
        )

        assert isinstance(report, DriftReport)
        assert report.level1_checked is True
        assert report.level2_checked is True
        assert report.level3_checked is True
        assert report.has_drift is False


# ── STORY-407: Complete L1/L2 test coverage ─────────────────────────


class MockAgentFactsRegistry:
    """Lightweight mock for governance drift tests (no real I/O)."""

    def __init__(self, storage_dir, verify_results=None):
        self._storage_dir = str(storage_dir)
        self._verify_results = verify_results or {}

    def verify(self, agent_id):
        return self._verify_results.get(agent_id, True)


# ── Level 1: Performance drift (additional) ─────────────────────────


class TestPerformanceDriftExtended:
    def test_performance_drift_zero_variance_baseline(self):
        baseline = [5.0, 5.0, 5.0, 5.0, 5.0]
        production = [3.0, 3.0, 3.0]
        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "performance_drift"
        assert alerts[0].triggered is True
        assert "zero-variance" in alerts[0].message

    def test_performance_drift_zero_variance_baseline_same(self):
        baseline = [5.0, 5.0, 5.0, 5.0]
        production = [5.0, 5.0]
        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) == 0

    def test_performance_drift_negative(self):
        baseline = [4.0, 4.1, 3.9, 4.0, 4.1]
        production = [1.0, 1.1, 0.9, 1.0, 1.1]
        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) >= 1
        assert alerts[0].triggered is True
        assert alerts[0].current_value < alerts[0].baseline_value

    def test_performance_drift_positive(self):
        baseline = [2.0, 2.1, 1.9, 2.0, 2.1]
        production = [9.0, 9.1, 8.9, 9.0, 9.1]
        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) >= 1
        assert alerts[0].triggered is True
        assert alerts[0].current_value > alerts[0].baseline_value

    def test_performance_drift_within_threshold(self):
        baseline = [4.0, 4.5, 3.5, 4.2, 3.8, 4.1, 3.9, 4.0, 4.3, 3.7]
        mean = sum(baseline) / len(baseline)
        var = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        std = var ** 0.5
        safe_value = mean + std  # 1-sigma away, well within 2-sigma
        production = [safe_value] * 5
        alerts = detect_performance_drift(baseline, production)
        assert len(alerts) == 0

    def test_performance_drift_single_element_lists(self):
        alerts = detect_performance_drift([5.0], [3.0])
        assert len(alerts) == 1
        assert alerts[0].alert_type == "performance_drift"
        assert alerts[0].triggered is True

    def test_performance_drift_empty_baseline(self):
        alerts = detect_performance_drift([], [1.0, 2.0, 3.0])
        assert alerts == []

    def test_performance_drift_empty_production(self):
        alerts = detect_performance_drift([1.0, 2.0, 3.0], [])
        assert alerts == []


# ── Level 2: Calibration drift (additional) ─────────────────────────


class TestCalibrationDriftExtended:
    def test_calibration_drift_perfect_agreement(self):
        labels = [1, 2, 3, 4, 5, 1, 2, 3]
        alerts = detect_calibration_drift(labels, labels)
        assert len(alerts) == 0

    def test_calibration_drift_chance_agreement(self):
        human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        judge = [3, 1, 4, 2, 5, 2, 4, 1, 3, 5]
        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "calibration_drift"
        assert alerts[0].triggered is True

    def test_calibration_drift_below_threshold(self):
        human = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        judge = [2, 1, 3, 2, 4, 3, 5, 4, 1, 5]
        kappa = compute_cohens_kappa(human, judge)
        assert kappa < 0.75
        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) >= 1
        assert alerts[0].triggered is True

    def test_calibration_drift_above_threshold(self):
        human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        judge = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        kappa = compute_cohens_kappa(human, judge)
        assert kappa > 0.75
        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) == 0

    def test_calibration_drift_mismatched_lengths(self):
        human = [1, 2, 3]
        judge = [1, 2]
        kappa = compute_cohens_kappa(human, judge)
        assert kappa == 0.0
        alerts = detect_calibration_drift(human, judge)
        assert len(alerts) >= 1

    def test_calibration_drift_empty_lists(self):
        kappa = compute_cohens_kappa([], [])
        assert kappa == 0.0
        alerts = detect_calibration_drift([], [])
        assert len(alerts) >= 1


# ── Level 3: Governance drift (additional) ──────────────────────────


class TestGovernanceDriftExtended:
    def test_governance_drift_empty_registry(self):
        alerts = detect_governance_drift(None)
        assert alerts == []

    def test_governance_drift_no_storage_dir(self):
        class NoStorageRegistry:
            pass

        alerts = detect_governance_drift(NoStorageRegistry())
        assert alerts == []

    def test_governance_drift_all_valid(self, tmp_path):
        import json

        for name in ["agent-a", "agent-b"]:
            (tmp_path / f"{name}.json").write_text(json.dumps({"agent_id": name}))

        registry = MockAgentFactsRegistry(
            storage_dir=tmp_path,
            verify_results={"agent-a": True, "agent-b": True},
        )
        alerts = detect_governance_drift(registry)
        assert alerts == []

    def test_governance_drift_tampered_agent(self, tmp_path):
        import json

        for name in ["agent-ok", "agent-bad"]:
            (tmp_path / f"{name}.json").write_text(json.dumps({"agent_id": name}))

        registry = MockAgentFactsRegistry(
            storage_dir=tmp_path,
            verify_results={"agent-ok": True, "agent-bad": False},
        )
        alerts = detect_governance_drift(registry)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "governance_drift"
        assert alerts[0].triggered is True
        assert "agent-bad" in alerts[0].message


# ── DriftReport tests ───────────────────────────────────────────────


class TestDriftReportExtended:
    def test_drift_report_has_drift_true(self):
        report = DriftReport(
            alerts=[
                DriftAlert(
                    level=1,
                    alert_type="performance_drift",
                    metric_name="mean_score",
                    baseline_value=4.0,
                    current_value=2.0,
                    threshold=2.0,
                    message="drift",
                    triggered=True,
                )
            ],
            level1_checked=True,
        )
        assert report.has_drift is True

    def test_drift_report_has_drift_false(self):
        report = DriftReport(alerts=[], level1_checked=True)
        assert report.has_drift is False

    def test_drift_report_levels_checked(self):
        report = DriftReport(
            level1_checked=True, level2_checked=False, level3_checked=True
        )
        assert report.level1_checked is True
        assert report.level2_checked is False
        assert report.level3_checked is True


# ── run_full_drift_check (additional) ───────────────────────────────


class TestFullDriftCheckExtended:
    def test_full_check_all_levels(self, tmp_path):
        import json

        (tmp_path / "agent-x.json").write_text(json.dumps({"agent_id": "agent-x"}))
        registry = MockAgentFactsRegistry(
            storage_dir=tmp_path,
            verify_results={"agent-x": False},
        )

        report = run_full_drift_check(
            baseline_scores=[5.0, 5.0, 5.0],
            production_scores=[1.0, 1.0, 1.0],
            human_labels=[1, 2, 3, 4, 5],
            judge_labels=[5, 4, 3, 2, 1],
            agent_facts_registry=registry,
        )
        assert report.level1_checked is True
        assert report.level2_checked is True
        assert report.level3_checked is True
        assert report.has_drift is True
        assert len(report.alerts) >= 3

    def test_full_check_partial_levels(self):
        report = run_full_drift_check(
            baseline_scores=[4.0, 4.0],
            production_scores=[4.0, 4.0],
        )
        assert report.level1_checked is True
        assert report.level2_checked is False
        assert report.level3_checked is False
        assert report.has_drift is False


# ── CLI tests (STORY-405) ──────────────────────────────────────────


class TestDriftCLI:
    def test_cli_no_drift(self, tmp_path):
        baseline = tmp_path / "baseline.jsonl"
        production = tmp_path / "production.jsonl"
        baseline.write_text("4.0\n4.0\n4.0\n")
        production.write_text("4.0\n4.0\n4.0\n")

        exit_code = run_drift_cli([
            "--baseline", str(baseline),
            "--production", str(production),
            "--level", "1",
        ])
        assert exit_code == 0

    def test_cli_drift_detected(self, tmp_path):
        baseline = tmp_path / "baseline.jsonl"
        production = tmp_path / "production.jsonl"
        baseline.write_text("4.0\n4.0\n4.0\n4.0\n4.0\n")
        production.write_text("1.0\n1.0\n1.0\n1.0\n1.0\n")

        exit_code = run_drift_cli([
            "--baseline", str(baseline),
            "--production", str(production),
            "--level", "1",
        ])
        assert exit_code == 1

    def test_cli_missing_baseline(self, tmp_path):
        exit_code = run_drift_cli([
            "--baseline", str(tmp_path / "nonexistent.jsonl"),
            "--production", str(tmp_path / "nonexistent.jsonl"),
            "--level", "1",
        ])
        assert exit_code == 2

    def test_cli_output_file(self, tmp_path):
        baseline = tmp_path / "baseline.jsonl"
        production = tmp_path / "production.jsonl"
        output = tmp_path / "report.json"
        baseline.write_text("4.0\n4.0\n4.0\n")
        production.write_text("4.0\n4.0\n4.0\n")

        exit_code = run_drift_cli([
            "--baseline", str(baseline),
            "--production", str(production),
            "--level", "1",
            "--output", str(output),
        ])
        assert exit_code == 0
        assert output.exists()
        import json
        report = json.loads(output.read_text())
        assert "alerts" in report

    def test_cli_level_selection(self, tmp_path):
        baseline = tmp_path / "baseline.jsonl"
        production = tmp_path / "production.jsonl"
        baseline.write_text("4.0\n4.0\n4.0\n")
        production.write_text("4.0\n4.0\n4.0\n")

        exit_code = run_drift_cli([
            "--baseline", str(baseline),
            "--production", str(production),
            "--level", "1",
        ])
        assert exit_code == 0


# ── STORY-406: PhaseLogger drift alerting ──────────────────────────


class _SpyPhaseLogger:
    """Capture (workflow_id, decision) pairs for assertion."""

    def __init__(self, raise_on_log: Exception | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self._raise = raise_on_log

    def log_decision(self, workflow_id, decision):
        self.calls.append((workflow_id, decision))
        if self._raise is not None:
            raise self._raise


class TestEmitDriftAlerts:
    """Failure paths first: a drifty world MUST surface to PhaseLogger."""

    def test_alerts_logged_when_drift_present(self):
        from meta.drift import emit_drift_alerts

        report = run_full_drift_check(
            baseline_scores=[5.0, 5.0, 5.0, 5.0, 5.0],
            production_scores=[1.0, 1.0, 1.0, 1.0, 1.0],
        )
        assert report.has_drift is True

        spy = _SpyPhaseLogger()
        logged = emit_drift_alerts(report, spy, workflow_id="wf-001")

        assert logged == len(spy.calls)
        assert logged >= 1
        wf_ids = {wf for wf, _ in spy.calls}
        assert wf_ids == {"wf-001"}
        # Decision payload is structured; alternatives are fixed by contract.
        decision = spy.calls[0][1]
        assert decision.alternatives == ["ignore", "retrain", "rollback"]
        assert decision.phase.value == "evaluation"
        assert "Drift L1" in decision.description

    def test_no_alerts_no_calls(self):
        from meta.drift import emit_drift_alerts

        report = run_full_drift_check(
            baseline_scores=[4.0, 4.0, 4.0],
            production_scores=[4.0, 4.0, 4.0],
        )
        assert report.has_drift is False

        spy = _SpyPhaseLogger()
        logged = emit_drift_alerts(report, spy, workflow_id="wf-quiet")
        assert logged == 0
        assert spy.calls == []

    def test_phase_logger_none_is_noop(self):
        from meta.drift import emit_drift_alerts

        report = run_full_drift_check(
            baseline_scores=[5.0, 5.0, 5.0, 5.0, 5.0],
            production_scores=[1.0, 1.0, 1.0, 1.0, 1.0],
        )
        # Must NOT crash when no logger is available.
        assert emit_drift_alerts(report, None, "wf-none") == 0

    def test_phase_logger_failure_does_not_crash(self, capsys):
        from meta.drift import emit_drift_alerts

        report = run_full_drift_check(
            baseline_scores=[5.0, 5.0, 5.0, 5.0, 5.0],
            production_scores=[1.0, 1.0, 1.0, 1.0, 1.0],
        )
        spy = _SpyPhaseLogger(raise_on_log=RuntimeError("disk full"))

        # The contract: function returns the count of successful logs (zero
        # here) and prints diagnostics to stderr -- it never re-raises.
        logged = emit_drift_alerts(report, spy, workflow_id="wf-bad")
        assert logged == 0
        captured = capsys.readouterr()
        assert "PhaseLogger.log_decision failed" in captured.err

    def test_cli_with_alert_log_dir_writes_decisions(self, tmp_path):
        baseline = tmp_path / "baseline.jsonl"
        production = tmp_path / "production.jsonl"
        baseline.write_text("5.0\n5.0\n5.0\n5.0\n5.0\n")
        production.write_text("1.0\n1.0\n1.0\n1.0\n1.0\n")

        alert_dir = tmp_path / "phase_logs"
        exit_code = run_drift_cli([
            "--baseline", str(baseline),
            "--production", str(production),
            "--level", "1",
            "--alert-log-dir", str(alert_dir),
            "--workflow-id", "drift-cli-001",
        ])
        assert exit_code == 1

        decisions_file = alert_dir / "drift-cli-001" / "decisions.jsonl"
        assert decisions_file.exists()
        import json
        lines = [
            json.loads(line)
            for line in decisions_file.read_text().strip().split("\n")
            if line.strip()
        ]
        assert len(lines) >= 1
        first = lines[0]
        assert first["workflow_id"] == "drift-cli-001"
        assert first["phase"] == "evaluation"
        assert first["alternatives"] == ["ignore", "retrain", "rollback"]
