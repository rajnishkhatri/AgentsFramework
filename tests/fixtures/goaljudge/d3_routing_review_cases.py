"""Stage 5 Tier 3 — D3 (routing_reason) MECE review fixtures.

D3 is **not** prompt-derived: ``select_model()`` reads thread state
(step_count, consecutive_errors, last_error_type, cost_fraction,
model_history). These five cases document one scenario per MECE branch
for human review and L3 router regression tests.

Each case optionally links a ``sample_prompt`` — the kind of task that
would be running when that branch fires (same prompt, different thread
state). Fresh-task authoring (``fresh_test_tasks.py``) covers D1/D5/D7/D8;
D3 review lives here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class D3RoutingReviewCase:
    """One ``select_model`` state tuple with expected branch outcome."""

    id: str
    branch_label: str
    description: str
    step_count: int
    consecutive_errors: int
    last_error_type: str
    cost_fraction: float
    history_tiers: tuple[str, ...]
    expected_tier: str
    expected_reason_prefix: str
    sample_prompt: str = ""


# One case per MECE branch (``components/router.py::select_model`` order).
D3_ROUTING_REVIEW_CASES: tuple[D3RoutingReviewCase, ...] = (
    D3RoutingReviewCase(
        id="D3-R-001",
        branch_label="capable-for-planning",
        description="First step of a new task — capable tier for planning.",
        step_count=0,
        consecutive_errors=0,
        last_error_type="",
        cost_fraction=0.0,
        history_tiers=(),
        expected_tier="capable",
        expected_reason_prefix="capable-for-planning",
        sample_prompt=(
            "Compare three inputs: (1) read /workspace/pinned_version.txt; "
            "(2) search the web for the latest release; (3) report whether "
            "they match."
        ),
    ),
    D3RoutingReviewCase(
        id="D3-R-002",
        branch_label="steady-state-fast",
        description="Mid-run steady state — fast tier after planning turn.",
        step_count=5,
        consecutive_errors=0,
        last_error_type="",
        cost_fraction=0.1,
        history_tiers=("fast", "fast", "fast", "fast", "fast"),
        expected_tier="fast",
        expected_reason_prefix="steady-state-fast",
        sample_prompt="Run grep -c ERROR /workspace/service.log and report the total.",
    ),
    D3RoutingReviewCase(
        id="D3-R-003",
        branch_label="budget-downgrade",
        description="Cost fraction at threshold — budget branch wins over all others.",
        step_count=5,
        consecutive_errors=2,
        last_error_type="retryable",
        cost_fraction=0.85,
        history_tiers=("fast", "fast", "fast", "fast", "fast"),
        expected_tier="fast",
        expected_reason_prefix="budget-downgrade",
        sample_prompt=(
            "Compare three step for deploy check first read workspace config "
            "yaml second run grep error in workspace service log third search "
            "web for known bug fix and tell if safe to push"
        ),
    ),
    D3RoutingReviewCase(
        id="D3-R-004",
        branch_label="retry-after-backoff",
        description="Retryable error — reuse the same model tier as last step.",
        step_count=5,
        consecutive_errors=1,
        last_error_type="retryable",
        cost_fraction=0.1,
        history_tiers=("capable", "capable", "capable", "capable", "capable"),
        expected_tier="capable",
        expected_reason_prefix="retry-after-backoff",
        sample_prompt="Search the web for CVE-2024-3400 severity and cite the source hostname.",
    ),
    D3RoutingReviewCase(
        id="D3-R-005",
        branch_label="escalate-after-N-failures",
        description="Two consecutive failures — escalate to capable tier.",
        step_count=5,
        consecutive_errors=2,
        last_error_type="model_error",
        cost_fraction=0.1,
        history_tiers=("fast", "fast", "fast", "fast", "fast"),
        expected_tier="capable",
        expected_reason_prefix="escalate-after-2-failures",
        sample_prompt=(
            "Compare three compliance artifacts: (1) read "
            "/workspace/policy/data_retention.md; (2) run ls -1 "
            "/workspace/archives | wc -l; (3) search the web for GDPR "
            "minimum retention and judge compliance."
        ),
    ),
)
