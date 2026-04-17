"""L1 tests for ``meta.CodeReviewerAgentTest.report_renderer.render_markdown``."""

from __future__ import annotations

import re

from meta.CodeReviewerAgentTest.report_renderer import render_markdown
from trust.review_schema import (
    Certificate,
    DimensionResult,
    DimensionStatus,
    ReviewFinding,
    ReviewReport,
    Severity,
    Verdict,
)


def _fixture_report() -> ReviewReport:
    crit = ReviewFinding(
        rule_id="R7",
        dimension="D5",
        severity=Severity.CRITICAL,
        file="orchestration/react_loop.py",
        line=42,
        description="Critical wiring gap.",
        fix_suggestion="Wire the counter at the SqliteSaver.put site.",
        confidence=0.95,
        certificate=Certificate(
            premises=["[P1] grep returns zero call sites"],
            conclusion="R7 FAIL -- counters never incremented",
        ),
    )
    warn = ReviewFinding(
        rule_id="H1",
        dimension="D2",
        severity=Severity.WARNING,
        file="meta/fallback_prototype.py",
        line=365,
        description="Hardcoded prompt string.",
        fix_suggestion="Move to prompts/.j2 and load via PromptService.",
        confidence=0.9,
        certificate=Certificate(
            premises=["[P1] _DEFAULT_SYSTEM_PROMPT defined as Python literal"],
            conclusion="H1 FAIL -- prompt is configured in code",
        ),
    )
    return ReviewReport(
        verdict=Verdict.REQUEST_CHANGES,
        statement="REQUEST_CHANGES because of one critical wiring gap and one warning.",
        confidence=0.78,
        dimensions=[
            DimensionResult(
                dimension="D2",
                name="Style Guide Adherence",
                status=DimensionStatus.PARTIAL,
                hypotheses_tested=24,
                hypotheses_confirmed=1,
                hypotheses_killed=23,
                findings=[warn],
            ),
            DimensionResult(
                dimension="D5",
                name="Code Quality and Anti-Patterns",
                status=DimensionStatus.FAIL,
                hypotheses_tested=18,
                hypotheses_confirmed=1,
                hypotheses_killed=17,
                findings=[crit],
            ),
        ],
        gaps=["LLM behaviour not exercised."],
        validation_log=[
            "Phase 5 -- Synthesized report",
            "Judge: D5-C1 KEPT",
        ],
        files_reviewed=["orchestration/react_loop.py", "meta/fallback_prototype.py"],
    )


def test_renders_all_ten_sections_in_order():
    md = render_markdown(_fixture_report(), {"phase_label": "Test"})
    section_order = [
        "## 1. Governing Thought",
        "## 2. Pyramid Self-Validation Log",
        "## 3. Files Reviewed",
        "## 4. Dimension Results",
        "## 5. Cross-Dimension Interactions",
        "## 6. Gaps",
        "## 7. Judge Filter Log",
        "## 8. Verdict Decision Trace",
        "## 9. Recommended Action List",
        "## 10. Metadata",
    ]
    last_pos = -1
    for header in section_order:
        pos = md.find(header)
        assert pos > last_pos, f"Section out of order or missing: {header}"
        last_pos = pos


def test_action_list_orders_critical_before_warning():
    md = render_markdown(_fixture_report(), {})
    action_section = md.split("## 9. Recommended Action List")[1].split("## 10.")[0]
    crit_idx = action_section.find("[CRITICAL]")
    warn_idx = action_section.find("[WARNING]")
    assert crit_idx >= 0 and warn_idx >= 0
    assert crit_idx < warn_idx, (
        "Critical findings must appear before warnings in the action list"
    )


def test_metadata_reports_correct_file_count():
    md = render_markdown(_fixture_report(), {"model_used": "claude-3-haiku"})
    assert "| Files reviewed | 2 |" in md
    assert "| Model used | claude-3-haiku |" in md


def test_governing_thought_includes_verdict_and_confidence():
    md = render_markdown(_fixture_report(), {})
    assert "**REQUEST_CHANGES -- confidence 0.78.**" in md


def test_renderer_handles_empty_report():
    """Rendering a verdict-only report must not crash."""
    report = ReviewReport(
        verdict=Verdict.APPROVE,
        statement="Nothing to flag.",
        confidence=1.0,
    )
    md = render_markdown(report, {})
    assert "## 1. Governing Thought" in md
    assert "## 10. Metadata" in md
    assert re.search(r"Files reviewed \| 0", md)
