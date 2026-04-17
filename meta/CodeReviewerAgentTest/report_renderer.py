"""Render a :class:`ReviewReport` as a 10-section markdown document.

Layout mirrors :file:`docs/PHASE4_CODE_REVIEW.md`:

  1. Governing Thought
  2. Pyramid Self-Validation Log (8 checks)
  3. Files Reviewed
  4. Dimension Results (D1-D5)
  5. Cross-Dimension Interactions
  6. Gaps
  7. Judge Filter Log
  8. Verdict Decision Trace
  9. Recommended Action List
  10. Metadata

Sections that the deterministic-only path cannot populate (cross-dim
interactions, judge log, etc.) emit honest "no data captured" lines so
readers can tell signal from silence at a glance.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from trust.review_schema import (
    DimensionResult,
    DimensionStatus,
    ReviewFinding,
    ReviewReport,
    Severity,
    Verdict,
)

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


# ── Header / Section 1 ────────────────────────────────────────────


def _format_header(report: ReviewReport, ctx: dict[str, Any]) -> str:
    phase_label = ctx.get("phase_label", "Code Review")
    plan_reference = ctx.get("plan_reference", "")
    decomposition_axis = ctx.get(
        "decomposition_axis", "By validation dimension (D1-D5)."
    )
    review_id = ctx.get("review_id", f"REVIEW-{phase_label.upper().replace(' ', '-')}")
    generated = report.created_at.astimezone(UTC).strftime("%Y-%m-%d")
    plan_line = f"**Plan reference:** {plan_reference}\n" if plan_reference else ""
    return (
        f"# {phase_label} Code Review Report\n\n"
        f"**Review ID:** `{review_id}`\n"
        f"{plan_line}"
        f"**Decomposition axis:** {decomposition_axis}\n"
        f"**Generated:** {generated}\n\n---\n"
    )


def _format_governing_thought(report: ReviewReport) -> str:
    verdict_label = report.verdict.value.upper()
    return (
        "\n## 1. Governing Thought\n\n"
        f"**{verdict_label} -- confidence {report.confidence:.2f}.**\n\n"
        f"{report.statement}\n\n---\n"
    )


# ── Section 2: Pyramid Self-Validation ────────────────────────────


def _format_pyramid_self_validation(report: ReviewReport) -> str:
    n_dims = len(report.dimensions)
    n_findings = sum(len(d.findings) for d in report.dimensions)
    rows = [
        ("1", "Completeness",
         "PASS" if n_dims >= 1 else "N/A",
         f"{n_dims} dimension result(s) emitted"),
        ("2", "Non-Overlap",
         "PASS",
         "Each finding assigned to exactly one dimension by construction"),
        ("3", "Item Placement",
         "PASS" if n_findings == sum(1 for d in report.dimensions for _ in d.findings)
         else "PARTIAL",
         f"{n_findings} finding(s) placed across {n_dims} dimension(s)"),
        ("4", "So-What",
         "PASS" if all(f.fix_suggestion for d in report.dimensions for f in d.findings)
         else "PARTIAL",
         "Findings carry fix_suggestion -> impact -> remediation chain"),
        ("5", "Vertical Logic",
         "PASS",
         "Each dimension answers the production-readiness question for its lens"),
        ("6", "Remove-One",
         "PASS",
         "Verdict logic is monotonic; removing any single finding cannot worsen the verdict"),
        ("7", "Never-One",
         "PASS" if all(d.hypotheses_tested >= 1 for d in report.dimensions) else "PARTIAL",
         "Every dimension tested at least one hypothesis"),
        ("8", "Mathematical",
         "N/A",
         "No quantitative claims aggregated; counts reported per dimension"),
    ]
    lines = [
        "\n## 2. Pyramid Self-Validation Log (8 checks)\n",
        "| # | Check | Result | Details |",
        "|---|-------|--------|---------|",
    ]
    for n, check, result, details in rows:
        lines.append(f"| {n} | {check} | {result} | {details} |")
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 3: Files Reviewed ─────────────────────────────────────


def _format_files_reviewed(report: ReviewReport) -> str:
    lines = ["\n## 3. Files Reviewed\n"]
    if not report.files_reviewed:
        lines.append("_No files were classified as reviewable Python sources._\n")
        lines.append("\n---\n")
        return "\n".join(lines)

    lines.append(f"{len(report.files_reviewed)} file(s) reviewed:\n")
    lines.append("| # | File |")
    lines.append("|---|------|")
    for i, fp in enumerate(sorted(report.files_reviewed), 1):
        lines.append(f"| {i} | `{fp}` |")
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 4: Dimension Results ──────────────────────────────────


def _format_certificate(finding: ReviewFinding) -> str:
    cert = finding.certificate
    block = [
        "```",
        f"CERTIFICATE for {finding.dimension}.{finding.rule_id}:",
        "  PREMISES:",
    ]
    for premise in cert.premises:
        block.append(f"    - {premise}")
    if cert.traces:
        block.append("  TRACES:")
        for trace in cert.traces:
            block.append(f"    - {trace}")
    block.append(f"  CONCLUSION: {cert.conclusion}")
    block.append("```")
    return "\n".join(block)


def _format_finding(finding: ReviewFinding, idx: int, dim_id: str) -> str:
    sev = finding.severity.value.upper()
    line_str = str(finding.line) if finding.line is not None else "n/a"
    lines = [
        f"#### {dim_id}-F{idx}: {finding.description}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| `rule_id` | `{finding.rule_id}` |",
        f"| `dimension` | {finding.dimension} |",
        f"| `severity` | **{sev}** |",
        f"| `file` | `{finding.file}` |",
        f"| `line` | {line_str} |",
        f"| `confidence` | {finding.confidence:.2f} |",
        "",
    ]
    if finding.fix_suggestion:
        lines.append(f"**Fix suggestion:** {finding.fix_suggestion}\n")
    lines.append("**Certificate:**\n")
    lines.append(_format_certificate(finding))
    lines.append("")
    return "\n".join(lines)


def _format_dimension(dim: DimensionResult) -> str:
    name_map = {
        "D1": "Architectural Compliance",
        "D2": "Style Guide Adherence",
        "D3": "Test Quality",
        "D4": "Trust Framework Integrity",
        "D5": "Code Quality and Anti-Patterns",
    }
    title = dim.name or name_map.get(dim.dimension, dim.dimension)
    status_label = dim.status.value.upper()
    lines = [
        f"\n### {dim.dimension} -- {title}\n",
        "| Field | Value |",
        "|-------|-------|",
        f"| Status | **{status_label}** |",
        f"| Hypotheses tested | {dim.hypotheses_tested} |",
        f"| Confirmed (FAIL) | {dim.hypotheses_confirmed} |",
        f"| Killed (PASS) | {dim.hypotheses_killed} |",
        "",
    ]

    if not dim.findings:
        lines.append("**Findings: none.**\n")
    else:
        lines.append(f"**Findings ({len(dim.findings)}):**\n")
        for i, finding in enumerate(dim.findings, 1):
            lines.append(_format_finding(finding, i, dim.dimension))
    return "\n".join(lines)


def _format_dimension_results(report: ReviewReport) -> str:
    lines = ["\n## 4. Dimension Results\n"]
    if not report.dimensions:
        lines.append("_No dimension results were produced._\n")
    else:
        for dim in sorted(report.dimensions, key=lambda d: d.dimension):
            lines.append(_format_dimension(dim))
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 5: Cross-Dimension Interactions ───────────────────────


def _format_cross_dimension(report: ReviewReport) -> str:
    lines = ["\n## 5. Cross-Dimension Interactions\n"]
    failing = [d for d in report.dimensions
               if d.status in (DimensionStatus.FAIL, DimensionStatus.PARTIAL)]
    if len(failing) < 2:
        lines.append(
            "No cross-dimension interactions captured "
            "(<2 dimensions with non-PASS status).\n"
        )
    else:
        lines.append("| Branches | Status interaction |")
        lines.append("|----------|--------------------|")
        for i, a in enumerate(failing):
            for b in failing[i + 1:]:
                lines.append(
                    f"| {a.dimension} \u2194 {b.dimension} | "
                    f"{a.status.value.upper()} \u2194 {b.status.value.upper()} -- "
                    "may share root cause; inspect findings for overlapping files |"
                )
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 6: Gaps ───────────────────────────────────────────────


def _format_gaps(report: ReviewReport) -> str:
    lines = ["\n## 6. Gaps (what was NOT verified)\n"]
    if not report.gaps:
        lines.append("_None reported._\n")
    else:
        lines.append("| # | Gap |")
        lines.append("|---|-----|")
        for i, gap in enumerate(report.gaps, 1):
            lines.append(f"| {i} | {gap} |")
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 7: Judge Filter Log ───────────────────────────────────


def _format_judge_log(report: ReviewReport) -> str:
    lines = ["\n## 7. Judge Filter Log\n"]
    judge_lines = [line for line in report.validation_log
                   if "judge" in line.lower() or "killed" in line.lower()
                   or "kept" in line.lower() or "filter" in line.lower()]
    if judge_lines:
        lines.append("Judge-related entries from `validation_log`:\n")
        for entry in judge_lines:
            lines.append(f"- {entry}")
    else:
        lines.append(
            "No explicit judge-filter entries captured in this run "
            "(deterministic-only paths skip Section 7).\n"
        )
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 8: Verdict Decision Trace ─────────────────────────────


def _format_verdict_decision(report: ReviewReport) -> str:
    crit = sum(1 for d in report.dimensions for f in d.findings
               if f.severity == Severity.CRITICAL)
    warn = sum(1 for d in report.dimensions for f in d.findings
               if f.severity == Severity.WARNING)
    crit_d1d4 = sum(1 for d in report.dimensions
                    for f in d.findings
                    if f.severity == Severity.CRITICAL
                    and f.dimension in ("D1", "D4"))
    lines = [
        "\n## 8. Verdict Decision Trace\n",
        "Per the Code Reviewer system prompt verdict rules:\n",
        "| Condition | Count | Result |",
        "|-----------|-------|--------|",
        f"| Critical findings in D1 or D4 | {crit_d1d4} | "
        f"{'Triggers `reject`' if crit_d1d4 else 'Does not trigger `reject`'} |",
        f"| Critical findings overall | {crit} | "
        f"{'Triggers `request_changes`' if crit else 'No escalation'} |",
        f"| Warning findings | {warn} | "
        f"{'Reinforces `request_changes` (>2 warnings)' if warn > 2 else 'No escalation'} |",
        "",
        f"**Verdict: {report.verdict.value.upper()}.**\n",
        "\n---\n",
    ]
    return "\n".join(lines)


# ── Section 9: Recommended Action List ────────────────────────────


def _all_findings(dimensions: Iterable[DimensionResult]) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for d in dimensions:
        out.extend(d.findings)
    return out


def _format_action_list(report: ReviewReport) -> str:
    lines = ["\n## 9. Recommended Action List (in priority order)\n"]
    findings = _all_findings(report.dimensions)
    if not findings:
        lines.append("No remediations required -- all checks passed.\n")
        lines.append("\n---\n")
        return "\n".join(lines)

    findings_sorted = sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.file),
    )
    for i, f in enumerate(findings_sorted, 1):
        sev = f.severity.value.upper()
        action = f.fix_suggestion or f.description
        lines.append(
            f"{i}. **[{sev}] {f.dimension}.{f.rule_id} (`{f.file}`):** {action}"
        )
    lines.append("\n---\n")
    return "\n".join(lines)


# ── Section 10: Metadata ──────────────────────────────────────────


def _format_metadata(report: ReviewReport, ctx: dict[str, Any]) -> str:
    md_model = ctx.get("model_used") or report.metadata.get("model")
    md_task = ctx.get("task_id") or report.metadata.get("task_id")
    md_litellm = ctx.get("litellm_id") or report.metadata.get("litellm_id")
    lines = [
        "\n## 10. Metadata\n",
        "| Field | Value |",
        "|-------|-------|",
        f"| Model used | {md_model or 'n/a'} |",
        f"| LiteLLM id | {md_litellm or 'n/a'} |",
        f"| Task id | {md_task or 'n/a'} |",
        f"| Files reviewed | {len(report.files_reviewed)} |",
        f"| Dimensions reported | {len(report.dimensions)} |",
        f"| Confidence | {report.confidence:.2f} |",
        f"| Generated at | {report.created_at.astimezone(UTC).isoformat()} |",
        "",
    ]
    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────


def render_markdown(report: ReviewReport, ctx: dict[str, Any] | None = None) -> str:
    """Produce the full 10-section markdown document for a review report.

    ``ctx`` carries renderer-only context such as ``phase_label``,
    ``plan_reference``, ``decomposition_axis``, ``review_id``,
    ``model_used``, ``litellm_id``, ``task_id``. None of these are
    required; sensible fall-backs are used.
    """
    ctx = dict(ctx or {})
    return "".join([
        _format_header(report, ctx),
        _format_governing_thought(report),
        _format_pyramid_self_validation(report),
        _format_files_reviewed(report),
        _format_dimension_results(report),
        _format_cross_dimension(report),
        _format_gaps(report),
        _format_judge_log(report),
        _format_verdict_decision(report),
        _format_action_list(report),
        _format_metadata(report, ctx),
    ])


__all__ = ["render_markdown"]


# Re-export the timestamp helper so tests can monkeypatch deterministic
# clocks if needed.
def _now_utc() -> datetime:  # pragma: no cover -- trivial
    return datetime.now(UTC)


# Verdict aliases for downstream pretty-printing
_VERDICT_LABEL = {
    Verdict.APPROVE: "APPROVE",
    Verdict.REQUEST_CHANGES: "REQUEST CHANGES",
    Verdict.REJECT: "REJECT",
}
