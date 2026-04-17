"""L2 Contract: Meta-optimizer tests (STORY-402/403).

Tests config mutation, candidate proposal, and benchmark comparison logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from components.routing_config import RoutingConfig
from components.schemas import EvalRecord
from meta.analysis import AgentMetrics, OptimizerInput
from meta.optimizer import (
    BenchmarkResult,
    BenchmarkRunner,
    ConfigMutator,
    OptimizationSettings,
    select_best,
)
from meta.run_eval import EvalReport
from services.base_config import ModelProfile

try:
    from hypothesis import given, settings as hyp_settings
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False


@pytest.fixture
def default_config():
    return RoutingConfig()


@pytest.fixture
def default_metrics():
    return OptimizerInput(
        metrics=AgentMetrics(total_tasks=100, success_rate=0.8),
        config_snapshot={"escalate_after_failures": 2},
    )


@pytest.fixture
def zero_metrics():
    return OptimizerInput(metrics=AgentMetrics(total_tasks=0))


class TestConfigMutator:
    def test_propose_returns_candidates(self, default_config, default_metrics):
        mutator = ConfigMutator(OptimizationSettings(seed=42))
        candidates = mutator.propose(default_config, default_metrics)
        assert len(candidates) >= 1
        assert all(isinstance(c, RoutingConfig) for c in candidates)

    def test_zero_tasks_returns_current(self, default_config, zero_metrics):
        mutator = ConfigMutator()
        candidates = mutator.propose(default_config, zero_metrics)
        assert len(candidates) == 1
        assert candidates[0] == default_config

    def test_deterministic_with_seed(self, default_config, default_metrics):
        m1 = ConfigMutator(OptimizationSettings(seed=42))
        m2 = ConfigMutator(OptimizationSettings(seed=42))
        c1 = m1.propose(default_config, default_metrics)
        c2 = m2.propose(default_config, default_metrics)
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a.model_dump() == b.model_dump()


if HAS_HYPOTHESIS:

    @pytest.mark.property
    class TestConfigMutatorProperty:
        """Property-based version of ``test_all_candidates_valid`` (STORY-402).

        Replaces the prior 5-case parametrize with a Hypothesis-driven sweep,
        closing the D3-W2 gap from the Phase 4 review (parametrize is not
        property-based testing).
        """

        @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
        @hyp_settings(max_examples=25, deadline=500)
        def test_all_candidates_valid(self, seed):
            config = RoutingConfig()
            metrics = OptimizerInput(
                metrics=AgentMetrics(total_tasks=50, success_rate=0.7)
            )
            candidates = ConfigMutator(
                OptimizationSettings(seed=seed)
            ).propose(config, metrics)
            for c in candidates:
                assert isinstance(c, RoutingConfig)
                assert c.escalate_after_failures >= 1
                assert c.max_escalations >= 1
                assert 0.0 <= c.budget_downgrade_threshold <= 1.0


class TestSelectBest:
    def test_better_candidate_selected(self):
        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.7,
            cost_usd=1.0,
        )
        candidates = [
            BenchmarkResult(
                config=RoutingConfig(escalate_after_failures=3).model_dump(),
                mean_score=0.85,
                cost_usd=1.05,
            ),
        ]
        best = select_best(candidates, baseline)
        assert best.escalate_after_failures == 3

    def test_no_improvement_returns_baseline(self):
        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.9,
            cost_usd=1.0,
        )
        candidates = [
            BenchmarkResult(
                config=RoutingConfig(escalate_after_failures=3).model_dump(),
                mean_score=0.7,
                cost_usd=0.8,
            ),
        ]
        best = select_best(candidates, baseline)
        assert best == RoutingConfig()

    def test_cost_exceeds_tolerance_rejected(self):
        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.7,
            cost_usd=1.0,
        )
        candidates = [
            BenchmarkResult(
                config=RoutingConfig(escalate_after_failures=3).model_dump(),
                mean_score=0.85,
                cost_usd=1.20,  # 20% > 10% tolerance
            ),
        ]
        best = select_best(candidates, baseline)
        assert best == RoutingConfig()

    def test_all_worse_returns_baseline(self):
        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.9,
            cost_usd=1.0,
        )
        candidates = [
            BenchmarkResult(config=RoutingConfig().model_dump(), mean_score=0.5, cost_usd=0.5),
            BenchmarkResult(config=RoutingConfig().model_dump(), mean_score=0.6, cost_usd=0.6),
        ]
        best = select_best(candidates, baseline)
        assert best == RoutingConfig()

    def test_empty_results_returns_baseline_unchanged(self):
        """``select_best`` with no candidates returns the baseline config.

        The "empty golden set raises" contract is enforced upstream by
        :class:`BenchmarkRunner.run` (see ``TestBenchmarkRunner``); this
        unit-level test only proves that ``select_best`` itself degrades
        gracefully when no candidate results were produced.
        """
        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(), mean_score=0.0, cost_usd=0.0,
        )
        best = select_best([], baseline)
        assert best == RoutingConfig()


# ── STORY-403: BenchmarkRunner ─────────────────────────────────────


def _judge_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _sample_record(task_id: str = "t-1") -> EvalRecord:
    return EvalRecord(
        task_id=task_id,
        user_id="u-1",
        step=0,
        target="call_llm",
        ai_input={"task_input": "hello"},
        ai_response="ok",
        timestamp=datetime.now(UTC),
    )


def _fake_eval_runner(score_for_index: list[float]):
    """Return an async ``run_eval_pipeline`` stand-in with deterministic scores.

    Each call returns a report whose ``mean_score`` comes from the provided
    list, indexed by call order. Used to exercise BenchmarkRunner without
    invoking the judge.
    """
    counter = {"i": 0}

    async def runner(*, golden_set, llm_service, judge_profile, report_id):
        i = counter["i"]
        counter["i"] += 1
        score = score_for_index[i] if i < len(score_for_index) else 0.0
        return EvalReport(
            report_id=report_id,
            total_records=len(golden_set),
            scored_records=len(golden_set),
            failed_records=0,
            mean_score=score,
        )

    return runner


class TestBenchmarkRunner:
    """L2 contract tests for STORY-403 (failure paths first)."""

    @pytest.mark.asyncio
    async def test_empty_golden_set_raises_value_error(self):
        runner = BenchmarkRunner(
            llm_service=AsyncMock(),
            judge_profile=_judge_profile(),
            eval_runner=_fake_eval_runner([]),
        )
        with pytest.raises(ValueError, match="non-empty golden_set"):
            await runner.run([RoutingConfig()], golden_set=[])

    @pytest.mark.asyncio
    async def test_runs_each_candidate_against_golden_set(self):
        candidates = [
            RoutingConfig(escalate_after_failures=2),
            RoutingConfig(escalate_after_failures=3),
            RoutingConfig(escalate_after_failures=4),
        ]
        runner = BenchmarkRunner(
            llm_service=AsyncMock(),
            judge_profile=_judge_profile(),
            eval_runner=_fake_eval_runner([0.7, 0.85, 0.6]),
        )
        results = await runner.run(candidates, golden_set=[_sample_record()])

        assert len(results) == 3
        assert [r.mean_score for r in results] == [0.7, 0.85, 0.6]
        # Each result references its source candidate config.
        for cand, res in zip(candidates, results):
            assert res.config == cand.model_dump()
        # Each result carries the underlying EvalReport.
        for res in results:
            assert res.eval_report is not None
            assert res.eval_report.scored_records == 1

    @pytest.mark.asyncio
    async def test_select_best_consumes_runner_output(self):
        """End-to-end: feed BenchmarkRunner output into ``select_best``."""
        candidates = [
            RoutingConfig(escalate_after_failures=2),  # baseline-shape
            RoutingConfig(escalate_after_failures=4),  # winner
        ]
        runner = BenchmarkRunner(
            llm_service=AsyncMock(),
            judge_profile=_judge_profile(),
            eval_runner=_fake_eval_runner([0.6, 0.9]),
        )
        results = await runner.run(candidates, golden_set=[_sample_record()])

        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.7,
            cost_usd=0.0,
        )
        best = select_best(results, baseline)
        assert best.escalate_after_failures == 4

    @pytest.mark.asyncio
    async def test_all_candidates_worse_returns_baseline(self):
        candidates = [
            RoutingConfig(escalate_after_failures=2),
            RoutingConfig(escalate_after_failures=4),
        ]
        runner = BenchmarkRunner(
            llm_service=AsyncMock(),
            judge_profile=_judge_profile(),
            eval_runner=_fake_eval_runner([0.4, 0.5]),
        )
        results = await runner.run(candidates, golden_set=[_sample_record()])

        baseline = BenchmarkResult(
            config=RoutingConfig().model_dump(),
            mean_score=0.9,
            cost_usd=0.0,
        )
        best = select_best(results, baseline)
        assert best == RoutingConfig()

    @pytest.mark.asyncio
    async def test_eval_capture_failure_does_not_abort(self, monkeypatch):
        """If eval_capture raises, the runner logs and continues (H5 graceful)."""
        from services import eval_capture

        async def _boom(**_kwargs):
            raise RuntimeError("disk full")

        monkeypatch.setattr(eval_capture, "record", _boom)

        runner = BenchmarkRunner(
            llm_service=AsyncMock(),
            judge_profile=_judge_profile(),
            eval_runner=_fake_eval_runner([0.5]),
        )
        results = await runner.run(
            [RoutingConfig()], golden_set=[_sample_record()]
        )
        assert len(results) == 1
        assert results[0].mean_score == 0.5


# ── STORY-404: Optimizer CLI + AST-safe config writes ─────────────


SAMPLE_ROUTING_CONFIG = '''"""Routing config for tests."""

from __future__ import annotations

from pydantic import BaseModel


class RoutingConfig(BaseModel):
    default_model: str = "gpt-4o-mini"
    escalate_after_failures: int = 2
    max_escalations: int = 3
    budget_downgrade_threshold: float = 0.8
'''


@pytest.fixture
def routing_config_file(tmp_path):
    """Write a fresh copy of routing_config.py into tmp_path."""
    path = tmp_path / "routing_config.py"
    path.write_text(SAMPLE_ROUTING_CONFIG)
    return path


class TestDiffConfigs:
    def test_no_diff_for_identical_configs(self):
        from meta.optimizer import diff_configs

        diffs = diff_configs(RoutingConfig(), RoutingConfig())
        assert diffs == []

    def test_diff_lists_changed_fields(self):
        from meta.optimizer import diff_configs

        cur = RoutingConfig()
        new = RoutingConfig(escalate_after_failures=4, max_escalations=5)
        diffs = {d.field: (d.before, d.after) for d in diff_configs(cur, new)}
        assert diffs == {
            "escalate_after_failures": (2, 4),
            "max_escalations": (3, 5),
        }


class TestAstRewriteRoutingConfig:
    def test_rewrites_int_field(self):
        from meta.optimizer import _ast_rewrite_routing_config

        new_source = _ast_rewrite_routing_config(
            SAMPLE_ROUTING_CONFIG,
            RoutingConfig(escalate_after_failures=4),
        )
        assert "escalate_after_failures: int = 4" in new_source
        # Untouched fields keep their original defaults.
        assert "max_escalations: int = 3" in new_source

    def test_rewrites_float_field(self):
        from meta.optimizer import _ast_rewrite_routing_config

        new_source = _ast_rewrite_routing_config(
            SAMPLE_ROUTING_CONFIG,
            RoutingConfig(budget_downgrade_threshold=0.5),
        )
        assert "budget_downgrade_threshold: float = 0.5" in new_source

    def test_missing_class_raises(self):
        from meta.optimizer import _ast_rewrite_routing_config

        with pytest.raises(ValueError, match="RoutingConfig"):
            _ast_rewrite_routing_config(
                "x = 1\n", RoutingConfig()
            )


class TestWriteOptimizedConfig:
    """Failure paths first."""

    def test_dry_run_does_not_mutate_file(self, routing_config_file):
        from meta.optimizer import write_optimized_config

        original = routing_config_file.read_text()
        proposed = RoutingConfig(escalate_after_failures=4)
        status, diffs = write_optimized_config(
            routing_config_file, proposed, dry_run=True
        )
        assert status == "dry_run"
        assert routing_config_file.read_text() == original
        assert not routing_config_file.with_suffix(".py.bak").exists()
        assert {d.field for d in diffs} == {"escalate_after_failures"}

    def test_write_creates_backup_and_updates_file(self, routing_config_file):
        from meta.optimizer import write_optimized_config

        original = routing_config_file.read_text()
        proposed = RoutingConfig(escalate_after_failures=4)
        status, diffs = write_optimized_config(
            routing_config_file, proposed
        )

        assert status == "written"
        backup = routing_config_file.with_suffix(".py.bak")
        assert backup.exists()
        assert backup.read_text() == original
        assert "escalate_after_failures: int = 4" in routing_config_file.read_text()
        assert len(diffs) == 1

    def test_unchanged_config_short_circuits(self, routing_config_file):
        from meta.optimizer import write_optimized_config

        # Use the file's own values as the proposal.
        proposed = RoutingConfig()
        status, diffs = write_optimized_config(
            routing_config_file, proposed
        )
        assert status == "unchanged"
        assert diffs == []
        assert not routing_config_file.with_suffix(".py.bak").exists()

    def test_decision_logged_to_phase_logger(self, routing_config_file, tmp_path):
        from meta.optimizer import write_optimized_config

        spy = _SpyPhaseLogger()
        proposed = RoutingConfig(max_escalations=4)
        write_optimized_config(
            routing_config_file,
            proposed,
            phase_logger=spy,
            workflow_id="opt-001",
            dry_run=True,
        )
        assert len(spy.calls) == 1
        wf, decision = spy.calls[0]
        assert wf == "opt-001"
        assert decision.phase.value == "evaluation"
        assert "max_escalations" in decision.rationale


class _SpyPhaseLogger:
    def __init__(self):
        self.calls = []

    def log_decision(self, workflow_id, decision):
        self.calls.append((workflow_id, decision))


class TestRunOptimizerCli:
    def test_dry_run_prints_diff_without_writing(
        self, routing_config_file, capsys
    ):
        from meta.optimizer import run_optimizer_cli

        original = routing_config_file.read_text()
        exit_code = run_optimizer_cli(
            [
                "--config-file", str(routing_config_file),
                "--dry-run",
            ],
            proposed_config=RoutingConfig(escalate_after_failures=4),
        )
        assert exit_code == 0
        assert routing_config_file.read_text() == original
        captured = capsys.readouterr()
        assert "escalate_after_failures" in captured.out

    def test_unchanged_returns_exit_one(self, routing_config_file, capsys):
        from meta.optimizer import run_optimizer_cli

        exit_code = run_optimizer_cli(
            [
                "--config-file", str(routing_config_file),
                "--dry-run",
            ],
            proposed_config=RoutingConfig(),  # equal to current
        )
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "kept baseline" in captured.out

    def test_write_produces_backup(self, routing_config_file):
        from meta.optimizer import run_optimizer_cli

        exit_code = run_optimizer_cli(
            [
                "--config-file", str(routing_config_file),
            ],
            proposed_config=RoutingConfig(escalate_after_failures=4),
        )
        assert exit_code == 0
        assert routing_config_file.with_suffix(".py.bak").exists()
        assert "escalate_after_failures: int = 4" in (
            routing_config_file.read_text()
        )

    def test_missing_config_file_returns_two(self, tmp_path, capsys):
        from meta.optimizer import run_optimizer_cli

        exit_code = run_optimizer_cli(
            [
                "--config-file", str(tmp_path / "nope.py"),
                "--dry-run",
            ],
            proposed_config=RoutingConfig(),
        )
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_no_runner_no_proposal_returns_two(
        self, routing_config_file, capsys
    ):
        from meta.optimizer import run_optimizer_cli

        exit_code = run_optimizer_cli(
            ["--config-file", str(routing_config_file)],
        )
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "no benchmark_runner" in captured.err

    def test_write_failure_returns_two(self, routing_config_file, capsys):
        """Read-only target produces a graceful exit code 2."""
        from meta.optimizer import run_optimizer_cli

        # Make the parent directory read-only so the .bak copy fails.
        original_mode = routing_config_file.parent.stat().st_mode
        try:
            routing_config_file.parent.chmod(0o500)
            exit_code = run_optimizer_cli(
                ["--config-file", str(routing_config_file)],
                proposed_config=RoutingConfig(escalate_after_failures=4),
            )
            assert exit_code == 2
            captured = capsys.readouterr()
            assert "ERROR" in captured.err
        finally:
            routing_config_file.parent.chmod(original_mode)

    def test_phase_log_dir_persists_decision(
        self, routing_config_file, tmp_path
    ):
        from meta.optimizer import run_optimizer_cli

        log_dir = tmp_path / "phase_logs"
        exit_code = run_optimizer_cli(
            [
                "--config-file", str(routing_config_file),
                "--phase-log-dir", str(log_dir),
                "--workflow-id", "opt-cli-001",
                "--dry-run",
            ],
            proposed_config=RoutingConfig(escalate_after_failures=4),
        )
        assert exit_code == 0
        decisions_file = log_dir / "opt-cli-001" / "decisions.jsonl"
        assert decisions_file.exists()
        import json
        lines = [
            json.loads(line)
            for line in decisions_file.read_text().strip().splitlines()
            if line.strip()
        ]
        assert len(lines) == 1
        assert lines[0]["phase"] == "evaluation"


@pytest.mark.slow
class TestBenchmarkRunnerL3:
    """L3 fixture-driven benchmark (uses recorded judge output, no live LLM)."""

    @pytest.mark.asyncio
    async def test_end_to_end_with_recorded_judge_response(self):
        from unittest.mock import MagicMock
        import json

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 4,
            "failure_categories": [],
            "reasoning": "Good output",
            "confidence": 0.9,
        })
        mock_service = MagicMock()
        mock_service.invoke = AsyncMock(return_value=mock_response)

        candidates = [
            RoutingConfig(escalate_after_failures=2),
            RoutingConfig(escalate_after_failures=3),
        ]
        golden_set = [_sample_record(task_id=f"t-{i}") for i in range(2)]

        runner = BenchmarkRunner(
            llm_service=mock_service,
            judge_profile=_judge_profile(),
        )
        results = await runner.run(candidates, golden_set=golden_set)

        assert len(results) == 2
        for res in results:
            assert res.mean_score == pytest.approx(4.0)
            assert res.eval_report is not None
            assert res.eval_report.scored_records == 2
