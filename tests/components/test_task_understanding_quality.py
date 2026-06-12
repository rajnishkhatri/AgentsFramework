"""L3 Probabilistic: generated-condition quality over the gold registry.

Live-LLM, NEVER in CI (run nightly / on demand):

    .venv/bin/python -m pytest tests/components/test_task_understanding_quality.py \
        -m live_llm -q

Formalizes the task_understanding plan's Phase 2a spot-check: for a sample of
gold-set tasks, the generator's checklist must (a) clear the deterministic
gates and (b) structurally cover the task's enumerated subtasks — one
condition sharing vocabulary with each extracted branch, no invented
requirements beyond the grounding gate. Aggregate pass-rate thresholds, never
exact strings (TAP-3).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from components.plan_builder import _extract_branches
from components.task_understanding import (
    TaskUnderstandingGenerator,
    _content_tokens,
)
from services.base_config import AgentConfig, default_fast_profile
from services.llm_config import LLMService
from services.prompt_service import PromptService

pytestmark = [pytest.mark.live_llm, pytest.mark.slow]

_GOLDSET = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "IAA"
    / "goalJudge"
    / "goldset"
    / "goaljudge_stage5_goldset_combined_sheet.csv"
)

_SAMPLE_SIZE = 30
# Stage 2a gate (plan §5 Phase 2 rollout): ≥95% of generations pass the
# deterministic gates; ≥80% of multi-branch tasks get full branch coverage.
_GATE_PASS_THRESHOLD = 0.95
_COVERAGE_THRESHOLD = 0.80


def _sample_tasks() -> list[str]:
    with _GOLDSET.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tasks = [r["task"].strip() for r in rows if r.get("task", "").strip()]
    # Deterministic sample: every k-th row across the corpus strata.
    step = max(1, len(tasks) // _SAMPLE_SIZE)
    return tasks[::step][:_SAMPLE_SIZE]


def _covers_branches(conditions: list[str], task: str) -> bool:
    """Each extracted branch shares ≥1 content token with ≥1 condition."""
    branches = _extract_branches(task)
    condition_tokens = [_content_tokens(c) for c in conditions]
    for branch in branches:
        branch_tokens = _content_tokens(branch)
        if not branch_tokens:
            continue
        if not any(branch_tokens & ct for ct in condition_tokens):
            return False
    return True


@pytest.mark.asyncio
async def test_generated_conditions_quality_over_goldset_sample():
    config = AgentConfig(default_model="gpt-4o-mini", models=[default_fast_profile()])
    generator = TaskUnderstandingGenerator(
        llm_service=LLMService(config=config),
        prompt_service=PromptService(),
        profile=default_fast_profile(),
    )

    tasks = _sample_tasks()
    assert len(tasks) >= 20, "goldset sample unexpectedly small"

    gate_passes = 0
    coverage_passes = 0
    multi_branch_total = 0
    failures: list[str] = []

    for task in tasks:
        try:
            artifact = await generator.generate(task_input=task)
            gate_passes += 1
        except Exception as exc:
            failures.append(f"{task[:60]!r}: {type(exc).__name__}: {exc}")
            continue
        if len(_extract_branches(task)) >= 2:
            multi_branch_total += 1
            if _covers_branches(artifact.success_conditions, task):
                coverage_passes += 1

    gate_rate = gate_passes / len(tasks)
    assert gate_rate >= _GATE_PASS_THRESHOLD, (
        f"gate pass-rate {gate_rate:.2f} < {_GATE_PASS_THRESHOLD}; "
        f"failures: {failures}"
    )
    if multi_branch_total:
        coverage_rate = coverage_passes / multi_branch_total
        assert coverage_rate >= _COVERAGE_THRESHOLD, (
            f"branch-coverage rate {coverage_rate:.2f} < {_COVERAGE_THRESHOLD} "
            f"over {multi_branch_total} multi-branch tasks"
        )
