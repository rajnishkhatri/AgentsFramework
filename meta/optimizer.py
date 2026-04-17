"""Meta-optimizer: propose and evaluate RoutingConfig candidates (STORY-402/403/404).

Reads logged metrics, mutates RoutingConfig fields within bounds,
and selects the best candidate via benchmark comparison.

Imports only from components/ (vertical, allowed) and meta/ (same package).
Zero imports from orchestration/, services/, or trust/.
"""

from __future__ import annotations

import ast
import logging
import random
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from components.routing_config import RoutingConfig
from components.schemas import EvalRecord
from meta.analysis import AgentMetrics, OptimizerInput
from meta.run_eval import EvalReport, run_eval_pipeline
from services.base_config import ModelProfile

logger = logging.getLogger("meta.optimizer")

DEFAULT_ROUTING_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "components" / "routing_config.py"
)


class OptimizationSettings(BaseModel):
    """Bounds for config field perturbation."""

    escalate_after_failures_range: tuple[int, int] = (1, 5)
    max_escalations_range: tuple[int, int] = (1, 5)
    budget_downgrade_threshold_range: tuple[float, float] = (0.5, 1.0)
    num_candidates: int = 4
    seed: int | None = None


class BenchmarkResult(BaseModel):
    """Result from running a candidate config against a golden set.

    ``eval_report`` carries the full ``EvalReport`` produced by
    :func:`meta.run_eval.run_eval_pipeline` so downstream consumers
    (CLI, audit logs) can inspect per-record scores without re-running
    the pipeline. It defaults to ``None`` for the legacy mock-only call
    sites (e.g. tests that exercise ``select_best`` in isolation).
    """

    config: dict[str, Any] = Field(default_factory=dict)
    metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    mean_score: float = 0.0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    scored_records: int = 0
    failed_records: int = 0
    eval_report: EvalReport | None = None


class ConfigMutator:
    """Propose RoutingConfig candidates by perturbing one field at a time."""

    def __init__(self, settings: OptimizationSettings | None = None) -> None:
        self._settings = settings or OptimizationSettings()

    def propose(
        self,
        current_config: RoutingConfig,
        metrics: OptimizerInput,
    ) -> list[RoutingConfig]:
        """Generate candidate configs by perturbing one field at a time.

        If metrics show zero tasks, returns the current config unchanged.
        """
        if metrics.metrics.total_tasks == 0:
            return [current_config]

        rng = random.Random(self._settings.seed)
        candidates: list[RoutingConfig] = []
        s = self._settings

        fields_to_perturb = [
            (
                "escalate_after_failures",
                lambda: rng.randint(*s.escalate_after_failures_range),
            ),
            (
                "max_escalations",
                lambda: rng.randint(*s.max_escalations_range),
            ),
            (
                "budget_downgrade_threshold",
                lambda: round(rng.uniform(*s.budget_downgrade_threshold_range), 2),
            ),
        ]

        for field_name, gen_value in fields_to_perturb:
            new_value = gen_value()
            candidate_dict = current_config.model_dump()
            candidate_dict[field_name] = new_value
            try:
                candidate = RoutingConfig.model_validate(candidate_dict)
                candidates.append(candidate)
            except Exception as exc:
                logger.warning(
                    "Invalid candidate for %s=%s: %s", field_name, new_value, exc
                )

        # Add one combined mutation
        combined = current_config.model_dump()
        for field_name, gen_value in fields_to_perturb:
            combined[field_name] = gen_value()
        try:
            candidates.append(RoutingConfig.model_validate(combined))
        except Exception as exc:
            logger.warning("Invalid combined candidate: %s", exc)

        return candidates[: self._settings.num_candidates]


def select_best(
    results: list[BenchmarkResult],
    baseline: BenchmarkResult,
    cost_tolerance: float = 0.10,
) -> RoutingConfig:
    """Pick the candidate that improves success_rate without exceeding baseline cost by >tolerance.

    If no candidate beats baseline, returns baseline config.
    """
    best_config = RoutingConfig.model_validate(baseline.config)
    best_score = baseline.mean_score

    for result in results:
        cost_ok = result.cost_usd <= baseline.cost_usd * (1 + cost_tolerance)
        if result.mean_score > best_score and cost_ok:
            best_score = result.mean_score
            best_config = RoutingConfig.model_validate(result.config)

    return best_config


# ── STORY-403: Benchmark execution loop ────────────────────────────


class BenchmarkRunner:
    """Execute candidate :class:`RoutingConfig` instances against a golden set.

    Each candidate is scored by ``meta.run_eval.run_eval_pipeline`` and
    wrapped in a :class:`BenchmarkResult`. The runner also records every
    invocation through :func:`services.eval_capture.record` with a
    ``optimizer_benchmark`` target so the meta-optimization loop is
    auditable end-to-end (H5 pattern).

    Architectural notes
    -------------------
    * Lives in ``meta/`` and reads only from ``components/``, ``services/``,
      and ``meta/`` siblings -- AP8 (no orchestration imports).
    * The injected ``llm_service`` is whatever object ``run_eval_pipeline``
      expects (a ``services.llm_config.LLMService`` in production; a mock
      in L2 tests). The runner never instantiates an LLM directly.
    """

    def __init__(
        self,
        llm_service: Any,
        judge_profile: ModelProfile,
        *,
        eval_runner: Any | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._judge_profile = judge_profile
        # Allow tests to inject a fake pipeline without monkey-patching.
        self._eval_runner = eval_runner or run_eval_pipeline

    async def run(
        self,
        candidates: list[RoutingConfig],
        golden_set: list[EvalRecord],
        *,
        user_id: str = "optimizer",
        task_id: str = "benchmark",
    ) -> list[BenchmarkResult]:
        """Score every candidate against ``golden_set`` and return results.

        Raises ``ValueError`` when ``golden_set`` is empty -- the comparison
        contract requires at least one record so the per-candidate
        ``mean_score`` is meaningful (failure-paths-first; we refuse to
        return zero-noise scores that would later fool ``select_best``).
        """
        if not golden_set:
            raise ValueError(
                "BenchmarkRunner.run requires a non-empty golden_set; "
                "received 0 records."
            )

        results: list[BenchmarkResult] = []
        for index, candidate in enumerate(candidates):
            report = await self._eval_runner(
                golden_set=golden_set,
                llm_service=self._llm_service,
                judge_profile=self._judge_profile,
                report_id=f"benchmark-candidate-{index}",
            )

            cost_usd, latency_ms = self._aggregate_costs(report)
            result = BenchmarkResult(
                config=candidate.model_dump(),
                mean_score=report.mean_score,
                scored_records=report.scored_records,
                failed_records=report.failed_records,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                eval_report=report,
            )
            results.append(result)

            # H5: audit the benchmark itself. Failures here must not
            # silently abort the optimization loop -- log and continue.
            try:
                from services import eval_capture

                await eval_capture.record(
                    target="optimizer_benchmark",
                    ai_input={
                        "candidate_config": candidate.model_dump(),
                        "golden_set_size": len(golden_set),
                    },
                    ai_response={
                        "mean_score": report.mean_score,
                        "scored_records": report.scored_records,
                        "failed_records": report.failed_records,
                    },
                    config={
                        "configurable": {
                            "user_id": user_id,
                            "task_id": f"{task_id}-{index}",
                        }
                    },
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                logger.warning(
                    "eval_capture.record failed for candidate %d: %s",
                    index,
                    exc,
                )

        return results

    @staticmethod
    def _aggregate_costs(report: EvalReport) -> tuple[float, float]:
        """Pull cost / latency totals from the report when available.

        ``EvalReport`` does not currently carry per-entry cost or latency,
        so the prototype returns 0.0 for both. Once judge scoring tracks
        usage per record we will sum it here without changing the
        :class:`BenchmarkResult` contract.
        """
        return 0.0, 0.0


# ── STORY-404: Optimizer CLI and config persistence ───────────────


class ConfigDiff(BaseModel):
    """Field-by-field diff between current and proposed RoutingConfig."""

    field: str
    before: Any
    after: Any


def diff_configs(
    current: RoutingConfig,
    proposed: RoutingConfig,
) -> list[ConfigDiff]:
    """Return only fields whose value changed (current != proposed)."""
    cur = current.model_dump()
    new = proposed.model_dump()
    diffs: list[ConfigDiff] = []
    for field in cur:
        if cur[field] != new.get(field):
            diffs.append(
                ConfigDiff(field=field, before=cur[field], after=new[field])
            )
    return diffs


def _ast_rewrite_routing_config(source: str, proposed: RoutingConfig) -> str:
    """Return new source where ``RoutingConfig`` defaults match ``proposed``.

    The function locates ``class RoutingConfig`` in ``source``, walks its
    ``AnnAssign`` field declarations, and substitutes ``node.value`` with
    a new ``ast.Constant`` for every field present in ``proposed``. Any
    field defined on ``RoutingConfig`` that is NOT present in ``source``
    raises ``ValueError`` so silent drift is impossible.
    """
    tree = ast.parse(source)
    target_values = proposed.model_dump()
    seen: set[str] = set()

    found_class = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "RoutingConfig":
            continue
        found_class = True
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            field_name = stmt.target.id
            if field_name not in target_values:
                continue
            stmt.value = ast.Constant(value=target_values[field_name])
            seen.add(field_name)

    if not found_class:
        raise ValueError("class RoutingConfig not found in source")

    missing = set(target_values) - seen
    if missing:
        raise ValueError(
            f"Could not locate field defaults for: {sorted(missing)}"
        )

    return ast.unparse(tree) + "\n"


def write_optimized_config(
    config_path: Path,
    proposed: RoutingConfig,
    *,
    current: RoutingConfig | None = None,
    phase_logger: Any | None = None,
    workflow_id: str = "optimizer",
    dry_run: bool = False,
) -> tuple[str, list[ConfigDiff]]:
    """Persist ``proposed`` to ``config_path`` (with a ``.bak`` backup).

    Returns ``(status, diffs)`` where ``status`` is one of:
      * ``"unchanged"`` -- no field differs from ``current``;
      * ``"dry_run"`` -- diffs computed and logged but no file mutation;
      * ``"written"`` -- backup created, source rewritten, decision logged;

    Raises any underlying ``OSError`` so the CLI can map it to exit code 2.
    """
    config_path = Path(config_path)
    if current is None:
        # Re-import the live config to compute the diff. We do NOT want
        # to instantiate RoutingConfig() blindly because the file on disk
        # may already carry overrides relative to the class defaults.
        current_source = config_path.read_text()
        current = _eval_routing_config(current_source)

    diffs = diff_configs(current, proposed)
    if not diffs:
        return "unchanged", diffs

    if dry_run:
        _maybe_log_decision(
            phase_logger,
            workflow_id,
            description="Optimizer dry-run -- no config changes applied",
            rationale=_render_diff(diffs),
        )
        return "dry_run", diffs

    backup_path = config_path.with_suffix(config_path.suffix + ".bak")
    shutil.copy2(config_path, backup_path)

    new_source = _ast_rewrite_routing_config(config_path.read_text(), proposed)
    config_path.write_text(new_source)

    _maybe_log_decision(
        phase_logger,
        workflow_id,
        description="RoutingConfig updated by optimizer",
        rationale=_render_diff(diffs),
    )
    return "written", diffs


def _eval_routing_config(source: str) -> RoutingConfig:
    """Parse a ``RoutingConfig`` source file into a live model instance.

    Reads only the ``RoutingConfig`` class's ``AnnAssign`` defaults so we
    do not execute the file. Falls back to ``RoutingConfig()`` defaults
    for any field whose value is not a literal constant.
    """
    tree = ast.parse(source)
    overrides: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "RoutingConfig":
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            if isinstance(stmt.value, ast.Constant):
                overrides[stmt.target.id] = stmt.value.value
    return RoutingConfig.model_validate(overrides) if overrides else RoutingConfig()


def _render_diff(diffs: list[ConfigDiff]) -> str:
    return "; ".join(f"{d.field}: {d.before!r} -> {d.after!r}" for d in diffs)


def _maybe_log_decision(
    phase_logger: Any | None,
    workflow_id: str,
    *,
    description: str,
    rationale: str,
) -> None:
    """Forward to PhaseLogger when available; never raise on failure."""
    if phase_logger is None:
        return
    try:
        from services.governance.phase_logger import Decision, WorkflowPhase

        decision = Decision(
            phase=WorkflowPhase.EVALUATION,
            description=description,
            alternatives=["accept", "reject", "rollback"],
            rationale=rationale,
            confidence=1.0,
        )
        phase_logger.log_decision(workflow_id, decision)
    except Exception as exc:
        logger.warning("PhaseLogger.log_decision failed: %s", exc)


def run_optimizer_cli(
    args: list[str] | None = None,
    *,
    benchmark_runner: BenchmarkRunner | None = None,
    proposed_config: RoutingConfig | None = None,
) -> int:
    """CLI entrypoint. Returns 0=improved+written, 1=baseline kept, 2=error.

    Parameters
    ----------
    args:
        argv-style list (``["--dry-run", ...]``). ``None`` means parse
        from ``sys.argv``.
    benchmark_runner:
        Optional injected runner. When ``None`` the CLI cannot score
        candidates and will refuse to write. Tests use this to stay
        offline; production wiring builds one from an ``LLMService``.
    proposed_config:
        Test hook -- skips the benchmark loop entirely and treats this
        config as the optimizer's recommendation. When set,
        ``benchmark_runner`` and ``--eval-data`` are ignored.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Meta-optimizer CLI (STORY-404)")
    parser.add_argument(
        "--eval-data", type=str,
        help="Path to JSONL log of EvalRecord entries for OptimizerInput",
    )
    parser.add_argument(
        "--golden-set", type=str,
        help="Path to JSONL golden set for benchmarking",
    )
    parser.add_argument(
        "--config-file", type=str,
        default=str(DEFAULT_ROUTING_CONFIG_PATH),
        help="Path to routing_config.py to be (potentially) updated",
    )
    parser.add_argument(
        "--phase-log-dir", type=str,
        help="Directory for governance Decision audit log",
    )
    parser.add_argument(
        "--workflow-id", type=str, default="optimizer-run",
        help="Workflow id for PhaseLogger correlation",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the proposed diff without writing the file",
    )
    parsed = parser.parse_args(args)

    config_path = Path(parsed.config_file)

    try:
        if not config_path.exists():
            print(
                f"ERROR: routing config not found at {config_path}",
                file=__import__("sys").stderr,
            )
            return 2

        current = _eval_routing_config(config_path.read_text())

        # Determine the proposed config.
        if proposed_config is not None:
            proposed = proposed_config
        elif benchmark_runner is None:
            print(
                "ERROR: no benchmark_runner injected and no proposed_config "
                "supplied; cannot evaluate candidates",
                file=__import__("sys").stderr,
            )
            return 2
        else:
            # Production path: load eval data + golden set, run mutator,
            # benchmark, select best. Surfaced as a clean error when the
            # required input files are missing.
            if not parsed.eval_data or not parsed.golden_set:
                print(
                    "ERROR: --eval-data and --golden-set are required when "
                    "no proposed_config is injected",
                    file=__import__("sys").stderr,
                )
                return 2
            proposed = _benchmark_and_select(
                Path(parsed.eval_data),
                Path(parsed.golden_set),
                current,
                benchmark_runner,
            )

        phase_logger = None
        if parsed.phase_log_dir:
            from services.governance.phase_logger import PhaseLogger

            phase_logger = PhaseLogger(storage_dir=parsed.phase_log_dir)

        status, diffs = write_optimized_config(
            config_path,
            proposed,
            current=current,
            phase_logger=phase_logger,
            workflow_id=parsed.workflow_id,
            dry_run=parsed.dry_run,
        )

        if not diffs:
            print("Optimizer kept baseline -- no field changes proposed.")
            return 1
        for d in diffs:
            print(f"{status}: {d.field}: {d.before!r} -> {d.after!r}")

        if status in ("written", "dry_run"):
            return 0
        return 1

    except OSError as exc:
        print(f"ERROR: filesystem failure ({exc})", file=__import__("sys").stderr)
        return 2
    except Exception as exc:
        logger.error("Optimizer CLI failed: %s", exc)
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


def _benchmark_and_select(
    eval_data_path: Path,
    golden_set_path: Path,
    current: RoutingConfig,
    runner: BenchmarkRunner,
) -> RoutingConfig:
    """Run the production benchmark loop and return the chosen RoutingConfig."""
    import asyncio
    import json

    from meta.analysis import build_optimizer_input, load_eval_records
    from meta.run_eval import load_golden_set

    if not eval_data_path.exists():
        raise FileNotFoundError(f"eval data not found: {eval_data_path}")
    if not golden_set_path.exists():
        raise FileNotFoundError(f"golden set not found: {golden_set_path}")

    records = load_eval_records(eval_data_path)
    golden = load_golden_set(golden_set_path)

    optimizer_input = build_optimizer_input(
        records, config_snapshot=current.model_dump()
    )
    candidates = ConfigMutator().propose(current, optimizer_input)

    results = asyncio.run(runner.run(candidates, golden_set=golden))
    baseline = BenchmarkResult(
        config=current.model_dump(),
        mean_score=sum(optimizer_input.golden_set_scores) / len(optimizer_input.golden_set_scores)
        if optimizer_input.golden_set_scores
        else 0.0,
        cost_usd=0.0,
    )
    return select_best(results, baseline)


if __name__ == "__main__":
    import sys

    sys.exit(run_optimizer_cli())
