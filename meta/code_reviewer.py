"""CodeReviewer Agent: architecture validation via LLM + deterministic checks (STORY-408/409/410).

Produces structured ReviewReport output. Uses PromptService for all prompts.
Zero imports from orchestration/.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from services import eval_capture

from trust.review_schema import (
    Certificate,
    DimensionResult,
    DimensionStatus,
    ReviewFinding,
    ReviewReport,
    Severity,
    Verdict,
)
from utils.code_analysis import (
    check_dependency_rules,
    check_trust_purity,
    classify_layer,
    detect_adr1_missing,
    detect_anti_patterns,
    detect_failure_path_ratio,
    detect_mock_abuse,
)

# WI-6: router + frontend deterministic fold. `code_reviewer/` sits outside the
# four-layer hierarchy (a review tool package), so these downward imports do
# not violate any architecture invariant (meta/ may not import orchestration/
# only — `code_reviewer/` is not orchestration).
from code_reviewer.frontend.findings import findings_from_tool
from code_reviewer.frontend.tools import applicable_tools, run_ts_script
from code_reviewer.routing import group_by_rules_file, route

logger = logging.getLogger("meta.code_reviewer")

AGENT_ROOT = Path(__file__).resolve().parent.parent


# ── STORY-409: Deterministic dimension validators ───────────────────


def check_import_rules(file_path: str) -> list[ReviewFinding]:
    """Run all deterministic import validators and return findings."""
    findings: list[ReviewFinding] = []

    dep_result = check_dependency_rules(file_path)
    for v in dep_result.get("violations", []):
        findings.append(
            ReviewFinding(
                rule_id=v["rule"],
                dimension="D1",
                severity=Severity.CRITICAL,
                file=v["file"],
                line=v.get("line"),
                description=v["description"],
                fix_suggestion="Remove the forbidden import and restructure to follow the dependency table.",
                confidence=1.0,
                certificate=Certificate(
                    premises=[
                        f"[P1] check_dependency_rules: {v['file']}:{v.get('line', '?')} — {v['description']}"
                    ],
                    traces=[f"[T1] {v['file']} imports from forbidden layer"],
                    conclusion=f"{v['rule']} FAIL — {v['description']}",
                ),
            )
        )

    purity_result = check_trust_purity(file_path)
    for v in purity_result.get("violations", []):
        findings.append(
            ReviewFinding(
                rule_id=v["rule"],
                dimension="D4",
                severity=Severity.CRITICAL,
                file=v["file"],
                line=v.get("line"),
                description=v["description"],
                fix_suggestion="Remove the I/O import. Trust foundation must be pure data and pure functions.",
                confidence=1.0,
                certificate=Certificate(
                    premises=[
                        f"[P1] check_trust_purity: {v['file']}:{v.get('line', '?')} — {v['description']}"
                    ],
                    conclusion=f"{v['rule']} FAIL — {v['description']}",
                ),
            )
        )

    ap_result = detect_anti_patterns(file_path)
    for v in ap_result.get("violations", []):
        findings.append(
            ReviewFinding(
                rule_id=v["rule"],
                dimension="D5",
                severity=Severity.WARNING,
                file=v["file"],
                line=v.get("line"),
                description=v["description"],
                fix_suggestion="Address the anti-pattern per the architecture style guide.",
                confidence=0.9,
                certificate=Certificate(
                    premises=[
                        f"[P1] detect_anti_patterns: {v['file']}:{v.get('line', '?')} — {v['description']}"
                    ],
                    conclusion=f"{v['rule']} FAIL — {v['description']}",
                ),
            )
        )

    return findings


def run_deterministic_review(files: list[str]) -> ReviewReport:
    """Run deterministic-only review (no LLM). Suitable for CI without API keys."""
    all_findings: list[ReviewFinding] = []
    files_reviewed: list[str] = []
    validation_log: list[str] = []

    for file_path in files:
        p = Path(file_path)
        if not p.exists():
            validation_log.append(f"Skipped {file_path}: file not found")
            continue
        if not p.suffix == ".py":
            validation_log.append(f"Skipped {file_path}: not a Python file")
            continue

        files_reviewed.append(file_path)
        layer_info = classify_layer(file_path)
        validation_log.append(
            f"Classified {file_path} as {layer_info['layer']} ({layer_info['layer_dir']}/)"
        )

        findings = check_import_rules(file_path)
        all_findings.extend(findings)

    # Aggregate by dimension
    dim_findings: dict[str, list[ReviewFinding]] = {}
    for f in all_findings:
        dim_findings.setdefault(f.dimension, []).append(f)

    dimensions: list[DimensionResult] = []
    for dim_id, dim_name in [
        ("D1", "Architectural Compliance"),
        ("D4", "Trust Framework Integrity"),
        ("D5", "Code Quality and Anti-Patterns"),
    ]:
        findings = dim_findings.get(dim_id, [])
        has_critical = any(f.severity == Severity.CRITICAL for f in findings)
        status = (
            DimensionStatus.FAIL
            if has_critical
            else (DimensionStatus.PARTIAL if findings else DimensionStatus.PASS)
        )
        dimensions.append(
            DimensionResult(
                dimension=dim_id,
                name=dim_name,
                status=status,
                hypotheses_tested=len(files_reviewed),
                hypotheses_confirmed=len(findings),
                hypotheses_killed=len(files_reviewed) - len(findings),
                findings=findings,
            )
        )

    # Determine verdict
    critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    warning_count = sum(1 for f in all_findings if f.severity == Severity.WARNING)

    if critical_count > 0:
        verdict = Verdict.REJECT
    elif warning_count > 2:
        verdict = Verdict.REQUEST_CHANGES
    else:
        verdict = Verdict.APPROVE

    # Governing statement
    if verdict == Verdict.APPROVE:
        statement = "APPROVE: All deterministic checks pass. No architectural violations detected."
    elif verdict == Verdict.REJECT:
        statement = (
            f"REJECT: {critical_count} critical violation(s) detected in "
            f"architectural compliance or trust integrity."
        )
    else:
        statement = (
            f"REQUEST CHANGES: {warning_count} warning(s) detected requiring attention."
        )

    return ReviewReport(
        verdict=verdict,
        statement=statement,
        confidence=1.0 if not all_findings else 0.9,
        dimensions=dimensions,
        gaps=[
            "D2 (Style Guide) not evaluated — deterministic mode",
            "D3 (Test Quality) not evaluated — deterministic mode",
        ],
        validation_log=validation_log,
        files_reviewed=files_reviewed,
    )


# ── WI-6: v3 unified, context-routed deterministic review ──────────


# Frontend dimension labels reused from the legacy runner; kept local to avoid
# importing the superseded runner module.
_FD_DIM_LABELS: dict[str, str] = {
    "FD1": "Layering & Dependency Direction",
    "FD2": "Pattern Adherence",
    "FD3": "Security & Sandboxing",
    "FD4": "Accessibility (WCAG 2.2 AA)",
    "FD5": "Performance & Streaming",
    "FD6": "Tests & Architecture Tests",
    "FD7": "Anti-Patterns",
}

_BACKEND_DIM_LABELS: dict[str, str] = {
    "D1": "Architectural Compliance",
    "D2": "Style Guide Adherence",
    "D3": "Test Quality",
    "D4": "Trust Framework Integrity",
    "D5": "Code Quality and Anti-Patterns",
}


def _is_test_path(path: str) -> bool:
    """Heuristic: does this path look like a Python test module?"""
    norm = path.replace("\\", "/")
    name = norm.rsplit("/", 1)[-1]
    return name.startswith("test_") or "/tests/" in norm or norm.startswith("tests/")


def _finding_from_violation(
    v: dict[str, Any],
    *,
    dimension: str,
    severity: Severity,
    fix_suggestion: str,
    tool: str,
) -> ReviewFinding:
    file_ref = str(v.get("file", "<unknown>"))
    line = v.get("line")
    rule_id = str(v.get("rule", f"{dimension}.UNKNOWN"))
    description = str(v.get("description", ""))
    return ReviewFinding(
        rule_id=rule_id,
        dimension=dimension,
        severity=severity,
        file=file_ref,
        line=line,
        description=description,
        fix_suggestion=fix_suggestion,
        confidence=1.0,
        certificate=Certificate(
            premises=[
                f"[P1] {tool}: {file_ref}{':' + str(line) if line else ''} — {description}"
            ],
            traces=[],
            conclusion=f"{rule_id} FAIL -- {description}",
        ),
    )


# ── WI-9: calibrated verdict policy (severity + confidence + dimension-aware) ──

# A warning only trips the gate once its confidence is at least this high.
# Below it, a cosmetic warning is demoted to INFO ("note") and does not gate.
_V3_WARNING_CONFIDENCE_THRESHOLD = 0.7
# ≥N high-confidence warnings → REQUEST_CHANGES. Preserves the count semantics of
# the old ">2 warnings" rule while gating on confidence so a 598-file format
# baseline (many low-confidence cosmetics) cannot trip the verdict.
_V3_HIGH_CONF_WARNING_QUORUM = 3
# FD7 anti-patterns the v3 system prompt declares auto-reject
# (security/trust-critical; emitted at `critical` severity by the frontend fold).
_V3_FD7_AUTO_REJECT_RULE_IDS = frozenset(
    {"FE-AP-4", "FE-AP-6", "FE-AP-7", "FE-AP-12", "FE-AP-18", "FE-AP-19"}
)
# Dimensions whose criticals auto-reject (backend architectural / trust kernel).
_V3_REJECT_DIMENSIONS = frozenset({"D1", "D4"})


def _demote_cosmetic_warnings(
    findings: list[ReviewFinding],
) -> list[ReviewFinding]:
    """Return a new list where low-confidence warnings become INFO ("notes").

    A warning with confidence < ``_V3_WARNING_CONFIDENCE_THRESHOLD`` is a
    cosmetic: it stays in the report as an INFO note so the signal is preserved,
    but it no longer counts toward the warning quorum. Criticals and INFO
    findings are passed through unchanged. Deterministic findings carry
    confidence 1.0 so this is a no-op on the deterministic half — the demotion
    targets the LLM half, where un-validated cosmetics must not gate.
    """
    demoted: list[ReviewFinding] = []
    for f in findings:
        if (
            f.severity == Severity.WARNING
            and f.confidence < _V3_WARNING_CONFIDENCE_THRESHOLD
        ):
            demoted.append(
                f.model_copy(
                    update={
                        "severity": Severity.INFO,
                        "description": (
                            f"{f.description} (demoted to note: "
                            f"confidence {f.confidence:.2f} < "
                            f"{_V3_WARNING_CONFIDENCE_THRESHOLD})"
                        ),
                    }
                )
            )
        else:
            demoted.append(f)
    return demoted


def apply_v3_verdict_policy(
    findings: list[ReviewFinding],
) -> tuple[Verdict, str, list[ReviewFinding]]:
    """WI-9 calibrated v3 verdict policy — single source of truth.

    Replaces the schema-compatible ``>2 warnings → REQUEST_CHANGES`` heuristic
    that was duplicated across the deterministic v3 path and the LLM merge.
    Collapsing the two inline blocks into one function stops the policy from
    drifting between the deterministic-only and LLM-merged reports and makes the
    calibration (dimension-aware reject + confidence gate + cosmetic demotion)
    unit-testable in isolation.

    Policy:
    - Demote low-confidence warnings (confidence < 0.7) to INFO notes; they do
      not gate.
    - ``reject``: any critical in D1 or D4 (backend architectural / trust
      kernel) OR any FD7 auto-reject anti-pattern (frontend security-critical).
    - ``request_changes``: any *other* critical, OR ≥ ``_V3_HIGH_CONF_WARNING_QUORUM``
      warnings with confidence ≥ 0.7.
    - ``approve``: otherwise (0 gate-relevant criticals, sub-quorum warnings).

    Returns ``(verdict, statement, findings_with_cosmetics_demoted)`` so callers
    can use the demoted findings in the emitted report (cosmetics surface as
    notes rather than vanishing).
    """
    demoted = _demote_cosmetic_warnings(findings)

    reject_criticals = [
        f
        for f in demoted
        if f.severity == Severity.CRITICAL
        and (
            f.dimension in _V3_REJECT_DIMENSIONS
            or f.rule_id in _V3_FD7_AUTO_REJECT_RULE_IDS
        )
    ]
    other_criticals = [
        f
        for f in demoted
        if f.severity == Severity.CRITICAL and f not in reject_criticals
    ]
    high_conf_warnings = [
        f
        for f in demoted
        if f.severity == Severity.WARNING
        and f.confidence >= _V3_WARNING_CONFIDENCE_THRESHOLD
    ]

    if reject_criticals:
        return (
            Verdict.REJECT,
            f"REJECT: {len(reject_criticals)} critical violation(s) in "
            f"architectural/trust-integrity dimension "
            f"({'/'.join(sorted({f.dimension for f in reject_criticals}))}).",
            demoted,
        )
    if other_criticals:
        return (
            Verdict.REQUEST_CHANGES,
            f"REQUEST CHANGES: {len(other_criticals)} critical violation(s) "
            f"requiring resolution before merge.",
            demoted,
        )
    if len(high_conf_warnings) >= _V3_HIGH_CONF_WARNING_QUORUM:
        return (
            Verdict.REQUEST_CHANGES,
            f"REQUEST CHANGES: {len(high_conf_warnings)} high-confidence "
            f"warning(s) (confidence ≥ {_V3_WARNING_CONFIDENCE_THRESHOLD}) "
            f"exceed the quorum of {_V3_HIGH_CONF_WARNING_QUORUM}.",
            demoted,
        )
    note_count = sum(1 for f in demoted if f.severity == Severity.INFO)
    if high_conf_warnings:
        return (
            Verdict.APPROVE,
            f"APPROVE: No criticals and {len(high_conf_warnings)} high-confidence "
            f"warning(s) below the quorum; {note_count} cosmetic note(s) demoted.",
            demoted,
        )
    return (
        Verdict.APPROVE,
        "APPROVE: No criticals and sub-quorum warnings; no gate-tripping findings.",
        demoted,
    )


def run_deterministic_review_v3(
    files: list[str],
    *,
    repo_root: Path | None = None,
    added_files: list[str] | None = None,
) -> ReviewReport:
    """WI-6 v3 deterministic review: routed, with the frontend + ADR.1 + TAP folds.

    Runs the existing backend AST validators (D1/D4/D5) on Python files, the
    new TAP-2/TAP-4 detectors on Python test files (D3), the TS deterministic
    predicates (FD2/FD3) on frontend files, and the ADR.1 file-list check
    across the whole diff. Pure deterministic — no LLM, no API key.

    ``repo_root`` routes the file list and resolves each group's REVIEW.md.
    When ``None``, ``AGENT_ROOT`` is used.
    """
    root = Path(repo_root) if repo_root is not None else AGENT_ROOT
    all_findings: list[ReviewFinding] = []
    files_reviewed: list[str] = []
    validation_log: list[str] = []

    entries = route(files, repo_root=root)
    grouped = group_by_rules_file(entries)

    for rules_file, group_entries in grouped.items():
        validation_log.append(
            f"Routed group {rules_file}: {len(group_entries)} file(s)"
        )
        for entry in group_entries:
            p = Path(entry.path)
            full = p if p.is_absolute() else (root / entry.path)
            if not full.exists():
                validation_log.append(f"Skipped {entry.path}: file not found")
                continue
            files_reviewed.append(entry.path)

            if entry.language == "backend":
                # Backend AST: D1/D4/D5 via the existing validators. These
                # operate on absolute paths; feed the resolved path but keep
                # the repo-relative path in the emitted findings.
                abs_str = str(full)
                for v in check_dependency_rules(abs_str).get("violations", []):
                    v["file"] = entry.path
                    all_findings.append(
                        _finding_from_violation(
                            v,
                            dimension="D1",
                            severity=Severity.CRITICAL,
                            fix_suggestion=(
                                "Remove the forbidden import and restructure to "
                                "follow the dependency table."
                            ),
                            tool="check_dependency_rules",
                        )
                    )
                for v in check_trust_purity(abs_str).get("violations", []):
                    v["file"] = entry.path
                    all_findings.append(
                        _finding_from_violation(
                            v,
                            dimension="D4",
                            severity=Severity.CRITICAL,
                            fix_suggestion=(
                                "Remove the I/O import. Trust foundation must be "
                                "pure data and pure functions."
                            ),
                            tool="check_trust_purity",
                        )
                    )
                for v in detect_anti_patterns(abs_str).get("violations", []):
                    v["file"] = entry.path
                    all_findings.append(
                        _finding_from_violation(
                            v,
                            dimension="D5",
                            severity=Severity.WARNING,
                            fix_suggestion=(
                                "Address the anti-pattern per the architecture "
                                "style guide."
                            ),
                            tool="detect_anti_patterns",
                        )
                    )
                # TAP-2 / TAP-4 on test modules (D3)
                if _is_test_path(entry.path):
                    try:
                        source = full.read_text(encoding="utf-8")
                    except OSError as exc:
                        validation_log.append(
                            f"Skipped TAP scan for {entry.path}: {exc}"
                        )
                    else:
                        for v in detect_mock_abuse(source).get("violations", []):
                            v["file"] = entry.path
                            all_findings.append(
                                _finding_from_violation(
                                    v,
                                    dimension="D3",
                                    severity=Severity.WARNING,
                                    fix_suggestion=(
                                        "Reduce the mock count to ≤3 per test, or "
                                        "consolidate mocks behind a fixture."
                                    ),
                                    tool="detect_mock_abuse",
                                )
                            )
                        for v in detect_failure_path_ratio(source).get(
                            "violations", []
                        ):
                            v["file"] = entry.path
                            all_findings.append(
                                _finding_from_violation(
                                    v,
                                    dimension="D3",
                                    severity=Severity.WARNING,
                                    fix_suggestion=(
                                        "Add rejection-path tests for the decision "
                                        "points (guards/gates) before the happy path."
                                    ),
                                    tool="detect_failure_path_ratio",
                                )
                            )

            elif entry.language == "frontend":
                # Folded frontend TS predicates (FD2/FD3). run_ts_script shells
                # out to frontend/scripts/*.ts; missing tsx surfaces as a gap.
                for tool_name, args in applicable_tools(entry.path):
                    raw = run_ts_script(tool_name, *args)
                    if raw.get("error"):
                        validation_log.append(
                            f"{tool_name}({entry.path}) -> error: {raw.get('error')}"
                        )
                        continue
                    if raw.get("skipped"):
                        validation_log.append(
                            f"{tool_name}({entry.path}) -> skipped: {raw.get('reason')}"
                        )
                        continue
                    new = findings_from_tool(tool_name, entry.path, raw)
                    # findings_from_tool returns ReviewFinding already.
                    all_findings.extend(new)
                    validation_log.append(
                        f"{tool_name}({entry.path}) -> "
                        f"exit_code={raw.get('exit_code')}, {len(new)} finding(s)"
                    )
            else:
                validation_log.append(
                    f"No deterministic check for {entry.path} (language={entry.language})"
                )

    # ADR.1 ratchet across the whole changed-file list (D2).
    adr_result = detect_adr1_missing(files, added_files=added_files)
    for v in adr_result.get("violations", []):
        v["file"] = "<diff>"
        all_findings.append(
            _finding_from_violation(
                v,
                dimension="D2",
                severity=Severity.WARNING,
                fix_suggestion=(
                    "Append a numbered ADR under docs/adr/ documenting the "
                    "Ask-first decision (Context / Decision / Options / "
                    "Rationale / Consequences)."
                ),
                tool="detect_adr1_missing",
            )
        )

    # Aggregate by dimension (backend D1-D5 + frontend FD*).
    dim_findings: dict[str, list[ReviewFinding]] = {}
    for f in all_findings:
        dim_findings.setdefault(f.dimension, []).append(f)

    labels = {**_BACKEND_DIM_LABELS, **_FD_DIM_LABELS}
    dimensions: list[DimensionResult] = []
    for dim_id in sorted(dim_findings):
        findings = dim_findings[dim_id]
        has_critical = any(f.severity == Severity.CRITICAL for f in findings)
        status = (
            DimensionStatus.FAIL
            if has_critical
            else (DimensionStatus.PARTIAL if findings else DimensionStatus.PASS)
        )
        dimensions.append(
            DimensionResult(
                dimension=dim_id,
                name=labels.get(dim_id, dim_id),
                status=status,
                hypotheses_tested=len(files_reviewed),
                hypotheses_confirmed=len(findings),
                hypotheses_killed=max(0, len(files_reviewed) - len(findings)),
                findings=findings,
            )
        )

    # WI-9 calibrated verdict. The deterministic half carries confidence 1.0,
    # so the calibrated policy here is dimension-aware reject + the
    # high-confidence warning quorum; cosmetic-demotion is a no-op on det
    # findings (it targets the LLM half in _merge_reports).
    verdict, statement, _demoted = apply_v3_verdict_policy(all_findings)

    gaps: list[str] = []
    if not any(d.dimension == "D2" for d in dimensions):
        gaps.append("D2 (Style Guide / ADR.1) — no Ask-first trigger in this diff.")
    # LLM-only rows are not evaluated deterministically.
    evaluated = {d.dimension for d in dimensions}
    for dim_id in ("D2", "D3", "D5"):
        if dim_id not in evaluated:
            gaps.append(f"{dim_id} not evaluated — deterministic mode.")

    return ReviewReport(
        verdict=verdict,
        statement=statement,
        confidence=1.0 if not all_findings else 0.9,
        dimensions=dimensions,
        gaps=gaps,
        validation_log=validation_log,
        files_reviewed=files_reviewed,
    )


class CodeReviewerAgent:
    """LLM-powered code reviewer producing structured ReviewReport (STORY-408)."""

    def __init__(
        self,
        llm_service: Any = None,
        prompt_service: Any = None,
        judge_profile: Any = None,
        task_id: str | None = None,
        user_id: str | None = None,
        prompt_version: str = "v1",
        repo_root: Path | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile
        self._task_id = task_id or str(uuid.uuid4())
        self._user_id = user_id or "code_reviewer"
        self._prompt_version = prompt_version
        # WI-8: repo_root lets the validation harness run the v3 reviewer over
        # materialized fixture trees without mutating the real repo. Defaults to
        # AGENT_ROOT so production callers are unchanged.
        self._repo_root = Path(repo_root) if repo_root is not None else AGENT_ROOT
        if self._prompt_version not in {"v1", "v2", "v3"}:
            raise ValueError(f"Unsupported prompt_version={self._prompt_version!r}")

    def _system_prompt_template(self) -> str:
        if self._prompt_version == "v3":
            return "codeReviewer/v3/CodeReviewer_system_prompt"
        if self._prompt_version == "v2":
            return "codeReviewer/v2/CodeReviewer_system_prompt"
        return "codeReviewer/CodeReviewer_system_prompt"

    def _submission_prompt_template(self) -> str:
        if self._prompt_version == "v3":
            return "codeReviewer/v3/CodeReviewer_review_submission"
        if self._prompt_version == "v2":
            return "codeReviewer/v2/CodeReviewer_review_submission"
        return "codeReviewer/CodeReviewer_review_submission"

    def _eval_config(self) -> dict[str, Any]:
        """RunnableConfig-shaped dict for eval_capture (H5)."""
        return {
            "configurable": {
                "task_id": self._task_id,
                "user_id": self._user_id,
            },
        }

    async def review(
        self,
        files: list[str],
        diff: str | None = None,
        added_files: list[str] | None = None,
    ) -> ReviewReport:
        """Produce a structured review combining deterministic checks + LLM analysis.

        ``added_files`` is the newly-added subset of ``files`` (from
        ``git diff --diff-filter=A``); it enables the ADR.1 new-service trigger
        in the v3 deterministic path. Ignored by v1/v2.
        """
        # WI-6: v3 is the unified, context-routed path. v1/v2 stay on the
        # legacy flat-files path (v2 is the A/B baseline — do not mutate).
        if self._prompt_version == "v3":
            return await self._review_v3(files, diff, added_files=added_files)

        # Phase 1: Deterministic checks
        deterministic_report = run_deterministic_review(files)

        if self._llm_service is None or self._prompt_service is None:
            return deterministic_report

        # Phase 2: LLM-based review
        try:
            llm_report = await self._run_llm_review(files, diff)
        except Exception as exc:
            logger.error("LLM review failed: %s", exc)
            return deterministic_report

        # Merge: deterministic findings take precedence, LLM adds new ones
        return self._merge_reports(deterministic_report, llm_report)

    async def _review_v3(
        self,
        files: list[str],
        diff: str | None,
        *,
        added_files: list[str] | None = None,
    ) -> ReviewReport:
        """WI-6 v3 path: route → deterministic (folded) → LLM with REVIEW.md injected."""
        deterministic_report = run_deterministic_review_v3(
            files, repo_root=self._repo_root, added_files=added_files
        )

        if self._llm_service is None or self._prompt_service is None:
            return deterministic_report

        try:
            llm_report = await self._run_llm_review_v3(
                files, diff, deterministic_report
            )
        except Exception as exc:
            logger.error("v3 LLM review failed: %s", exc)
            return deterministic_report

        return self._merge_reports(deterministic_report, llm_report)

    async def review_v3_llm_only(
        self,
        files: list[str],
        diff: str | None = None,
        *,
        added_files: list[str] | None = None,
    ) -> ReviewReport:
        """WI-8 seam: return the v3 LLM report *before* the deterministic merge.

        WI-8 validates the LLM judge's detection accuracy in isolation from the
        (already-trusted) deterministic half. ``review()`` returns the merged
        report; this returns only the LLM-produced ``ReviewReport`` so the
        validation gate measures the judge, not the deterministic fold.

        Raises ``ValueError`` if called without LLM + prompt services (the
        validation harness requires a live LLM). On LLM failure, returns the
        error report ``_run_llm_review_v3`` produces (verdict ``REJECT``,
        confidence 0.0) — that counts as a detected failure for the gate.
        """
        if self._llm_service is None or self._prompt_service is None:
            raise ValueError("review_v3_llm_only requires llm_service + prompt_service")
        if self._prompt_version != "v3":
            raise ValueError(
                f"review_v3_llm_only requires prompt_version='v3', got "
                f"{self._prompt_version!r}"
            )
        deterministic_report = run_deterministic_review_v3(
            files, repo_root=self._repo_root, added_files=added_files
        )
        return await self._run_llm_review_v3(files, diff, deterministic_report)

    def _build_routed_groups(
        self, files: list[str], *, repo_root: Path
    ) -> list[dict[str, Any]]:
        """Build the ``routed_groups`` payload for the v3 submission template.

        Each group carries its governing ``REVIEW.md`` content plus the file
        payloads (path, folder, language, language_hint, content). Missing
        REVIEW.md files fall back to the root REVIEW.md content (or a marker
        string) so the template always has a well-formed enforcement map.
        """
        entries = route(files, repo_root=repo_root)
        grouped = group_by_rules_file(entries)

        def _language_hint(path: str, language: str) -> str:
            if language == "backend":
                return "python"
            if language == "frontend":
                suffix = PurePosixPath(path).suffix.lower().lstrip(".")
                return suffix or "tsx"
            return "text"

        groups: list[dict[str, Any]] = []
        for rules_file, group_entries in grouped.items():
            rf_path = repo_root / rules_file
            if rf_path.is_file():
                try:
                    rules_content = rf_path.read_text(encoding="utf-8")
                except OSError:
                    rules_content = f"(REVIEW.md unreadable: {rules_file})"
            else:
                # Fall back to root REVIEW.md if the routed one is absent.
                root_rf = repo_root / "REVIEW.md"
                rules_content = (
                    root_rf.read_text(encoding="utf-8")
                    if root_rf.is_file()
                    else f"(REVIEW.md not found: {rules_file})"
                )

            file_payloads: list[dict[str, Any]] = []
            group_languages = {e.language for e in group_entries}
            group_language = (
                next(iter(group_languages)) if len(group_languages) == 1 else "mixed"
            )
            for entry in group_entries:
                p = Path(entry.path)
                full = p if p.is_absolute() else (repo_root / entry.path)
                try:
                    content = full.read_text(encoding="utf-8")[:20_000]
                except (OSError, UnicodeDecodeError):
                    content = "<missing or binary>"
                file_payloads.append(
                    {
                        "path": entry.path,
                        "folder": entry.folder or "root",
                        "language": entry.language,
                        "language_hint": _language_hint(entry.path, entry.language),
                        "content": content,
                        "lines_changed": "Full file",
                    }
                )
            groups.append(
                {
                    "rules_file": rules_file,
                    "language": group_language,
                    "rules_file_content": rules_content,
                    "files": file_payloads,
                }
            )
        return groups

    async def _run_llm_review_v3(
        self,
        files: list[str],
        diff: str | None,
        deterministic_report: ReviewReport,
    ) -> ReviewReport:
        """Render the v3 submission with routed REVIEW.md + deterministic findings."""
        system_prompt = self._prompt_service.render_prompt(
            self._system_prompt_template()
        )

        routed_groups = self._build_routed_groups(files, repo_root=self._repo_root)

        # Serialize the deterministic findings so the LLM sees pre-computed
        # results (precedence preserved by _merge_reports). Keep it compact:
        # rule_id / dimension / severity / file / line / description.
        det_payload = [
            {
                "rule_id": f.rule_id,
                "dimension": f.dimension,
                "severity": f.severity.value,
                "file": f.file,
                "line": f.line,
                "description": f.description,
            }
            for dim in deterministic_report.dimensions
            for f in dim.findings
        ]
        deterministic_findings_json = (
            json.dumps(det_payload, indent=2) if det_payload else ""
        )

        submission = self._prompt_service.render_prompt(
            self._submission_prompt_template(),
            submission_context=diff or "No diff provided.",
            review_scope=(
                "Routed review — enforce each folder-group's injected "
                "REVIEW.md; activate FD1-FD7 for TS/TSX groups."
            ),
            deterministic_findings=deterministic_findings_json,
            routed_groups=routed_groups,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": submission},
        ]

        cfg = self._eval_config()
        profile = self._judge_profile
        model_name = getattr(profile, "name", None)

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await self._llm_service.invoke(self._judge_profile, messages)
                raw = getattr(response, "content", str(response))
                parsed = self._parse_review_response(raw)
                await eval_capture.record(
                    target="code_review",
                    ai_input={"messages": messages},
                    ai_response=parsed.model_dump(mode="json"),
                    config=cfg,
                    step=attempt,
                    model=model_name,
                )
                return parsed
            except Exception as exc:
                logger.warning("v3 LLM review attempt %d failed: %s", attempt + 1, exc)
                if attempt == max_retries:
                    err_report = ReviewReport(
                        verdict=Verdict.REJECT,
                        statement=(
                            f"v3 LLM review failed after {max_retries + 1} "
                            f"attempts: {exc}"
                        ),
                        confidence=0.0,
                        gaps=[f"v3 LLM review failed: {exc}"],
                    )
                    await eval_capture.record(
                        target="code_review",
                        ai_input={"messages": messages},
                        ai_response={"error": str(exc)},
                        config=cfg,
                        step=attempt,
                        model=model_name,
                    )
                    return err_report

        return ReviewReport(
            verdict=Verdict.REJECT, statement="Unexpected error", confidence=0.0
        )

    async def _run_llm_review(self, files: list[str], diff: str | None) -> ReviewReport:
        """Run LLM-based review with retry on schema validation failure."""
        system_prompt = self._prompt_service.render_prompt(
            self._system_prompt_template()
        )

        files_data = []
        for fp in files:
            p = Path(fp)
            if p.exists() and p.suffix == ".py":
                layer_info = classify_layer(fp)
                files_data.append(
                    {
                        "path": fp,
                        "layer": layer_info["layer"],
                        "content": p.read_text()[:10000],
                        "language": "python",
                    }
                )

        submission = self._prompt_service.render_prompt(
            self._submission_prompt_template(),
            files_to_review=files_data,
            submission_context=diff or "No diff provided.",
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": submission},
        ]

        cfg = self._eval_config()
        profile = self._judge_profile
        model_name = getattr(profile, "name", None)

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await self._llm_service.invoke(self._judge_profile, messages)
                raw = getattr(response, "content", str(response))
                parsed = self._parse_review_response(raw)
                await eval_capture.record(
                    target="code_review",
                    ai_input={"messages": messages},
                    ai_response=parsed.model_dump(mode="json"),
                    config=cfg,
                    step=attempt,
                    model=model_name,
                )
                return parsed
            except Exception as exc:
                logger.warning("LLM review attempt %d failed: %s", attempt + 1, exc)
                if attempt == max_retries:
                    err_report = ReviewReport(
                        verdict=Verdict.REJECT,
                        statement=f"LLM review failed after {max_retries + 1} attempts: {exc}",
                        confidence=0.0,
                        gaps=[f"LLM review failed: {exc}"],
                    )
                    await eval_capture.record(
                        target="code_review",
                        ai_input={"messages": messages},
                        ai_response={"error": str(exc)},
                        config=cfg,
                        step=attempt,
                        model=model_name,
                    )
                    return err_report

        # Unreachable but satisfies type checker
        return ReviewReport(
            verdict=Verdict.REJECT, statement="Unexpected error", confidence=0.0
        )

    def _parse_review_response(self, raw: str) -> ReviewReport:
        """Parse LLM response into ReviewReport."""
        cleaned = raw.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1]
            cleaned = cleaned.split("```", 1)[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1]
            cleaned = cleaned.split("```", 1)[0]

        data = json.loads(cleaned.strip())
        data = self._normalize_review_payload(data)
        return ReviewReport.model_validate(data)

    def _normalize_review_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize loose LLM JSON into ReviewReport-compatible shape.

        Handles common schema drift from LLMs:
        - enum casing (PASS/WARNING/APPROVE -> lowercase values)
        - missing finding fields (dimension, confidence, certificate)
        - alias fields (`rule` -> `rule_id`, etc.)
        - dimension labels merged with ids (e.g. "D1 Architectural Compliance")
        """

        def _to_status(value: str | None) -> str:
            if not value:
                return "partial"
            lowered = value.lower().strip()
            if lowered in {"pass", "fail", "partial", "skipped"}:
                return lowered
            if lowered in {"passed"}:
                return "pass"
            if lowered in {"failed"}:
                return "fail"
            return "partial"

        def _to_severity(value: str | None) -> str:
            if not value:
                return "warning"
            lowered = value.lower().strip()
            if lowered in {"critical", "warning", "info"}:
                return lowered
            if lowered in {"error", "high"}:
                return "critical"
            if lowered in {"medium"}:
                return "warning"
            if lowered in {"low"}:
                return "info"
            return "warning"

        def _to_verdict(value: str | None) -> str:
            if not value:
                return "request_changes"
            lowered = value.lower().strip()
            if lowered in {"approve", "request_changes", "reject"}:
                return lowered
            if lowered in {"approved"}:
                return "approve"
            if lowered in {"request changes", "changes_requested"}:
                return "request_changes"
            if lowered in {"rejected"}:
                return "reject"
            return "request_changes"

        def _infer_dimension_id_and_name(
            dim_raw: Any, name_raw: Any
        ) -> tuple[str, str]:
            canonical = {
                "D1": "Architectural Compliance",
                "D2": "Style Guide Adherence",
                "D3": "Test Quality",
                "D4": "Trust Framework Integrity",
                "D5": "Code Quality and Anti-Patterns",
            }

            dim_text = str(dim_raw or "").strip()
            name_text = str(name_raw or "").strip()
            combined = f"{dim_text} {name_text}".strip()

            for dim_id, dim_name in canonical.items():
                if dim_text == dim_id:
                    return dim_id, (name_text or dim_name)
                if dim_text.lower().startswith(f"{dim_id.lower()} "):
                    suffix = dim_text[len(dim_id) :].strip()
                    return dim_id, (suffix or name_text or dim_name)
                if dim_name.lower() in combined.lower():
                    return dim_id, dim_name

            return "D5", (name_text or dim_text or canonical["D5"])

        if isinstance(payload.get("verdict"), str):
            payload["verdict"] = _to_verdict(payload["verdict"])
        else:
            payload["verdict"] = "request_changes"
        payload.setdefault("statement", "LLM-produced review report")
        payload.setdefault("confidence", 0.6)
        payload.setdefault("validation_log", [])
        payload.setdefault("files_reviewed", [])

        # ``gaps`` must be a list of strings; LLMs sometimes emit a list of
        # dicts (e.g. {"rule_id": ..., "note": ...}). Coerce each entry to a
        # single descriptive string so the field always validates.
        raw_gaps = payload.get("gaps")
        if not isinstance(raw_gaps, list):
            payload["gaps"] = []
        else:
            coerced: list[str] = []
            for g in raw_gaps:
                if isinstance(g, str) and g.strip():
                    coerced.append(g)
                elif isinstance(g, dict):
                    parts = [
                        str(g.get("rule_id", "")),
                        str(g.get("note", g.get("description", g.get("message", "")))),
                    ]
                    text = " ".join(p for p in parts if p and p != "None").strip()
                    coerced.append(text or "Unclassified gap.")
                elif g is not None:
                    coerced.append(str(g))
            payload["gaps"] = coerced

        # ``files_reviewed`` must be a list of strings; coerce dict entries the
        # LLM sometimes emits (e.g. {"file": "...", "findings_count": N}).
        raw_files = payload.get("files_reviewed")
        if not isinstance(raw_files, list):
            payload["files_reviewed"] = []
        else:
            payload["files_reviewed"] = [
                f
                if isinstance(f, str)
                else (
                    str(f.get("file") or f.get("path") or "<unknown>")
                    if isinstance(f, dict)
                    else str(f)
                )
                for f in raw_files
            ]

        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, list):
            payload["dimensions"] = []
            return payload

        def _normalize_finding(finding: dict[str, Any], dim_id: str) -> dict[str, Any]:
            """Apply field aliases + defaults so a loose finding dict validates.

            Coerces ``None`` and wrong-typed values (e.g. ``fix_suggestion: null``,
            ``line: "9-13"``) into schema-valid defaults — LLMs frequently emit
            these shapes and without coercion every finding in the report fails
            validation and falls back to an empty error report.
            """
            if not finding.get("rule_id"):
                finding["rule_id"] = finding.get("rule") or "LLM.UNKNOWN_RULE"
            if not finding.get("description"):
                finding["description"] = finding.get("message", "LLM-reported finding")
            if not finding.get("fix_suggestion"):
                finding["fix_suggestion"] = (
                    finding.get("suggestion") or finding.get("fix") or ""
                )
            if not isinstance(finding.get("fix_suggestion"), str):
                finding["fix_suggestion"] = ""

            finding["severity"] = _to_severity(
                finding["severity"]
                if isinstance(finding.get("severity"), str)
                else None
            )
            if not isinstance(finding.get("file"), str) or not finding["file"]:
                finding["file"] = "<unknown>"
            if (
                not isinstance(finding.get("description"), str)
                or not finding["description"]
            ):
                finding["description"] = "LLM-reported finding"
            finding.setdefault("dimension", dim_id)
            if not isinstance(finding.get("confidence"), (int, float)):
                finding["confidence"] = 0.6

            # ``line`` may be missing, null, or a range string like "9-13" / "9–13".
            line_val = finding.get("line")
            if isinstance(line_val, bool):  # bool is an int subclass; reject it
                line_val = None
            if isinstance(line_val, int):
                finding["line"] = line_val
            elif isinstance(line_val, str) and line_val.strip():
                digits = ""
                for ch in line_val.strip():
                    if ch.isdigit():
                        digits += ch
                    elif digits:
                        break
                finding["line"] = int(digits) if digits else 0
            else:
                finding["line"] = 0

            if not isinstance(finding.get("certificate"), dict):
                rule_id = str(finding.get("rule_id", "LLM.FINDING"))
                description = str(finding.get("description", "LLM-reported finding"))
                finding["certificate"] = {
                    "premises": ["[P1] LLM-reported finding (normalization fallback)."],
                    "traces": [],
                    "conclusion": f"{rule_id} FAIL -- {description}",
                }
            return finding

        def _is_finding_shaped(d: dict[str, Any]) -> bool:
            """True when a ``dimensions`` element is a flattened finding, not a
            dimension. Some LLMs emit ``dimensions`` as a flat list of finding
            objects (``rule_id``/``severity``/``description`` at the top level)
            rather than dimension objects with a nested ``findings`` array.
            """
            if isinstance(d.get("findings"), list):
                return False
            finding_markers = (
                "rule_id",
                "rule",
                "severity",
                "description",
                "message",
                "fix_suggestion",
            )
            return any(k in d for k in finding_markers)

        # Split true dimensions from flattened findings the LLM emitted in lieu
        # of a nested shape, then group the flattened findings by their declared
        # dimension so they survive normalization instead of being dropped.
        true_dimensions: list[dict[str, Any]] = []
        flat_by_dim: dict[str, list[dict[str, Any]]] = {}
        for dim in dimensions:
            if not isinstance(dim, dict):
                continue
            if _is_finding_shaped(dim):
                fid, _ = _infer_dimension_id_and_name(dim.get("dimension"), None)
                flat_by_dim.setdefault(fid, []).append(dim)
            else:
                true_dimensions.append(dim)

        def _build_dimension(
            dim: dict[str, Any] | None,
            dim_id: str,
            dim_name: str,
            findings: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {
                "dimension": dim_id,
                "name": dim_name,
                "status": _to_status(
                    dim.get("status")
                    if dim and isinstance(dim.get("status"), str)
                    else None
                ),
                "hypotheses_tested": int(
                    dim.get("hypotheses_tested", len(findings) or 1)
                    if dim
                    else (len(findings) or 1)
                ),
                "hypotheses_confirmed": int(
                    dim.get("hypotheses_confirmed", len(findings))
                    if dim
                    else len(findings)
                ),
                "hypotheses_killed": int(dim.get("hypotheses_killed", 0) if dim else 0),
                "findings": findings,
            }

        normalized_dimensions: list[dict[str, Any]] = []
        for dim in true_dimensions:
            dim_id, dim_name = _infer_dimension_id_and_name(
                dim.get("dimension"),
                dim.get("name"),
            )
            raw_findings = dim.get("findings")
            if not isinstance(raw_findings, list):
                raw_findings = []
            normalized_findings: list[dict[str, Any]] = [
                _normalize_finding(dict(f), dim_id)
                for f in raw_findings
                if isinstance(f, dict)
            ]
            # Fold in any flattened findings the LLM routed to this dimension.
            for ff in flat_by_dim.pop(dim_id, []):
                normalized_findings.append(_normalize_finding(dict(ff), dim_id))
            normalized_dimensions.append(
                _build_dimension(dim, dim_id, dim_name, normalized_findings)
            )

        # Orphan flattened findings whose dimension had no true-dimension host.
        for dim_id, ffs in flat_by_dim.items():
            _, dim_name = _infer_dimension_id_and_name(dim_id, None)
            normalized_findings = [_normalize_finding(dict(ff), dim_id) for ff in ffs]
            normalized_dimensions.append(
                _build_dimension(None, dim_id, dim_name, normalized_findings)
            )

        payload["dimensions"] = normalized_dimensions
        return payload

    def _merge_reports(
        self, deterministic: ReviewReport, llm: ReviewReport
    ) -> ReviewReport:
        """Merge deterministic and LLM reports, deterministic findings take priority."""
        deterministic_findings_by_dim: dict[str, list[ReviewFinding]] = {
            d.dimension: list(d.findings) for d in deterministic.dimensions
        }
        llm_dims = {d.dimension: d for d in llm.dimensions}

        merged_dims: list[DimensionResult] = []
        seen_dims: set[str] = set()
        reconciliation_gaps: list[str] = []

        for d in deterministic.dimensions:
            seen_dims.add(d.dimension)
            llm_dim = llm_dims.get(d.dimension)
            if llm_dim:
                reconciled_llm_findings = self._reconcile_llm_findings(
                    llm_findings=list(llm_dim.findings),
                    deterministic_findings=deterministic_findings_by_dim.get(
                        d.dimension, []
                    ),
                    dimension=d.dimension,
                    reconciliation_gaps=reconciliation_gaps,
                )
                extra_findings = [
                    f
                    for f in reconciled_llm_findings
                    if not any(
                        ef.rule_id == f.rule_id and ef.file == f.file
                        for ef in d.findings
                    )
                ]
                if extra_findings:
                    merged = DimensionResult(
                        dimension=d.dimension,
                        name=d.name,
                        status=d.status,
                        hypotheses_tested=d.hypotheses_tested
                        + llm_dim.hypotheses_tested,
                        hypotheses_confirmed=d.hypotheses_confirmed
                        + len(extra_findings),
                        hypotheses_killed=d.hypotheses_killed,
                        findings=list(d.findings) + extra_findings,
                    )
                    merged_dims.append(merged)
                    continue
            merged_dims.append(d)

        for d in llm.dimensions:
            if d.dimension not in seen_dims:
                reconciled = self._reconcile_llm_findings(
                    llm_findings=list(d.findings),
                    deterministic_findings=deterministic_findings_by_dim.get(
                        d.dimension, []
                    ),
                    dimension=d.dimension,
                    reconciliation_gaps=reconciliation_gaps,
                )
                merged_dims.append(
                    DimensionResult(
                        dimension=d.dimension,
                        name=d.name,
                        status=d.status,
                        hypotheses_tested=d.hypotheses_tested,
                        hypotheses_confirmed=d.hypotheses_confirmed,
                        hypotheses_killed=d.hypotheses_killed,
                        findings=reconciled,
                    )
                )

        # WI-9: demote low-confidence LLM cosmetics to INFO notes inside the
        # merged dimensions so the emitted report surfaces them as notes, then
        # apply the calibrated verdict policy on the flattened demoted findings.
        demoted_dims: list[DimensionResult] = []
        for d in merged_dims:
            demoted_fs = _demote_cosmetic_warnings(list(d.findings))
            if len(demoted_fs) != len(d.findings) or any(
                a.severity != b.severity for a, b in zip(demoted_fs, d.findings)
            ):
                # Recompute status: a dimension whose only finding was a demoted
                # warning drops from PARTIAL to PASS (a note is not a violation).
                has_critical = any(f.severity == Severity.CRITICAL for f in demoted_fs)
                has_remaining = any(
                    f.severity in {Severity.CRITICAL, Severity.WARNING}
                    for f in demoted_fs
                )
                status = (
                    DimensionStatus.FAIL
                    if has_critical
                    else (
                        DimensionStatus.PARTIAL
                        if has_remaining
                        else DimensionStatus.PASS
                    )
                )
                demoted_dims.append(
                    d.model_copy(update={"findings": demoted_fs, "status": status})
                )
            else:
                demoted_dims.append(d)
        merged_dims = demoted_dims

        all_f = [f for d in merged_dims for f in d.findings]

        # Fail-closed: an LLM infra failure (not a policy outcome) stays REJECT.
        llm_infra_failed = llm.verdict == Verdict.REJECT and any(
            "LLM review failed" in g for g in llm.gaps
        )

        if llm_infra_failed:
            verdict = Verdict.REJECT
            statement = llm.statement
        else:
            verdict, policy_statement, _ = apply_v3_verdict_policy(all_f)
            # Prefer the deterministic statement on a critical-driven reject so
            # the governing voice is the trusted half; otherwise use the
            # calibrated policy statement.
            if verdict == Verdict.REJECT and any(
                f.severity == Severity.CRITICAL
                and (f.dimension in _V3_REJECT_DIMENSIONS)
                for f in all_f
            ):
                statement = deterministic.statement
            else:
                statement = policy_statement

        return ReviewReport(
            verdict=verdict,
            statement=statement,
            confidence=min(deterministic.confidence, llm.confidence),
            dimensions=merged_dims,
            gaps=list(
                set(deterministic.gaps) | set(llm.gaps) | set(reconciliation_gaps)
            ),
            validation_log=deterministic.validation_log + llm.validation_log,
            files_reviewed=list(
                set(deterministic.files_reviewed) | set(llm.files_reviewed)
            ),
        )

    def _reconcile_llm_findings(
        self,
        llm_findings: list[ReviewFinding],
        deterministic_findings: list[ReviewFinding],
        dimension: str,
        reconciliation_gaps: list[str],
    ) -> list[ReviewFinding]:
        """Downgrade uncorroborated LLM criticals in D1/D4 to warnings."""
        if dimension not in {"D1", "D4"}:
            return llm_findings

        deterministic_critical_keys = {
            (f.rule_id, f.file)
            for f in deterministic_findings
            if f.severity == Severity.CRITICAL
        }
        reconciled: list[ReviewFinding] = []
        for finding in llm_findings:
            if (
                finding.severity == Severity.CRITICAL
                and (finding.rule_id, finding.file) not in deterministic_critical_keys
            ):
                reconciliation_gaps.append(
                    "LLM critical downgraded to warning due to missing deterministic corroboration: "
                    f"{finding.rule_id} in {finding.file}"
                )
                reconciled.append(
                    finding.model_copy(
                        update={
                            "severity": Severity.WARNING,
                            "description": (
                                f"{finding.description} "
                                "[Downgraded: not corroborated by deterministic checks.]"
                            ),
                        }
                    )
                )
                continue
            reconciled.append(finding)
        return reconciled


# ── CLI entrypoint (STORY-410) ──────────────────────────────────────


async def _async_llm_review(
    files: list[str],
    diff: str | None,
    task_id: str | None,
    user_id: str | None,
    prompt_version: str = "v1",
    added_files: list[str] | None = None,
    repo_root: Path | None = None,
) -> ReviewReport:
    """Build services and run full CodeReviewerAgent.review (LLM + deterministic).

    Uses an explicit ``template_dir`` for :class:`PromptService` (mirroring
    the idiom in ``meta/judge.py``) so the CLI does NOT mutate the global
    working directory -- D5-W2 fix from the Phase 4 review.

    ``repo_root`` (WI-8) lets the validation harness run the v3 reviewer over
    a materialized fixture tree; defaults to ``AGENT_ROOT`` for production.
    """
    from meta.CodeReviewerAgentTest.env_settings import reviewer_profile_from_env
    from services.base_config import AgentConfig
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

    profile = reviewer_profile_from_env()
    agent_config = AgentConfig(
        default_model=profile.name,
        models=[profile],
    )
    llm = LLMService(agent_config)
    prompt_service = PromptService(template_dir=str(AGENT_ROOT / "prompts"))
    reviewer = CodeReviewerAgent(
        llm_service=llm,
        prompt_service=prompt_service,
        judge_profile=profile,
        task_id=task_id,
        user_id=user_id,
        prompt_version=prompt_version,
        repo_root=repo_root,
    )
    return await reviewer.review(files, diff, added_files=added_files)


def _git_diff_files(base: str) -> tuple[list[str], list[str]]:
    """Return ``(changed_files, added_files)`` from ``git diff --name-only <base>``.

    ``added_files`` is the subset newly added (``--diff-filter=A``) — used by
    the v3 ADR.1 new-service trigger. Runs git in ``AGENT_ROOT``. On any git
    error returns ``([], [])`` so the CLI surfaces a clean "nothing to review".
    """
    import subprocess

    def _run(extra: list[str]) -> list[str]:
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only", *extra, "--", base],
                cwd=AGENT_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("git diff failed: %s", exc)
            return []
        if proc.returncode != 0:
            logger.warning("git diff non-zero exit: %s", proc.stderr.strip())
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    changed = _run([])
    added = _run(["--diff-filter=A"])
    return changed, added


def run_code_reviewer_cli(args: list[str] | None = None) -> int:
    """CLI for running code reviews.

    Exit codes: 0=approve, 1=request_changes, 2=reject, 3=error.
    """
    import argparse
    import asyncio
    import os

    parser = argparse.ArgumentParser(description="CodeReviewer CLI")
    parser.add_argument(
        "--files",
        nargs="+",
        required=False,
        default=None,
        help=(
            "Files to review. Required unless --from-git-diff is set (in which "
            "case the file list comes from `git diff --name-only <base>`)."
        ),
    )
    parser.add_argument(
        "--from-git-diff",
        action="store_true",
        help=(
            "Populate the file list from `git diff --name-only <base>` (and "
            "added files from `--diff-filter=A`). Enables the ADR.1 new-service "
            "trigger in v3. Mutually exclusive with supplying --files directly."
        ),
    )
    parser.add_argument(
        "--git-base",
        default="HEAD",
        help=(
            "Git ref to diff against for --from-git-diff (default HEAD). Use "
            "'origin/main...HEAD' for a PR-style review of branch commits."
        ),
    )
    parser.add_argument("--diff", type=str, help="Path to diff file")
    parser.add_argument("--output", type=str, help="Output file path (default: stdout)")
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Skip LLM review (useful for CI without API keys)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Run LLM + deterministic review (requires API keys; not for CI)",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="task_id for eval_capture (H5)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="user_id for eval_capture (H5)",
    )
    parser.add_argument(
        "--prompt-version",
        choices=["v1", "v2", "v3"],
        default="v1",
        help=(
            "Prompt bundle version for LLM review path. v3 is the unified "
            "context-routed reviewer (uses the path router + REVIEW.md)."
        ),
    )
    parsed = parser.parse_args(args)

    if parsed.llm and parsed.deterministic_only:
        logger.error("Cannot combine --llm with --deterministic-only")
        return 3

    if not parsed.from_git_diff and not parsed.files:
        logger.error("Either --files or --from-git-diff must be provided")
        return 3

    try:
        diff_text: str | None = None
        if parsed.diff:
            diff_path = Path(parsed.diff)
            if not diff_path.is_file():
                logger.error("Diff file not found: %s", parsed.diff)
                return 3
            diff_text = diff_path.read_text()

        # Resolve the file list (and added files for ADR.1) from git when
        # --from-git-diff is set; otherwise use --files directly.
        added_files: list[str] | None = None
        if parsed.from_git_diff:
            files, added_files = _git_diff_files(parsed.git_base)
            if not files:
                logger.info(
                    "No changed files in `git diff %s`; nothing to review",
                    parsed.git_base,
                )
        else:
            files = list(parsed.files or [])

        if parsed.llm:
            key = (
                os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("LITELLM_API_KEY")
            )
            if not key:
                logger.error(
                    "LLM review requires ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                    "or LITELLM_API_KEY in the environment",
                )
                return 3
            report = asyncio.run(
                _async_llm_review(
                    files,
                    diff_text,
                    task_id=parsed.task_id,
                    user_id=parsed.user_id,
                    prompt_version=parsed.prompt_version,
                    added_files=added_files,
                )
            )
        elif parsed.prompt_version == "v3":
            report = run_deterministic_review_v3(
                files, repo_root=AGENT_ROOT, added_files=added_files
            )
        else:
            report = run_deterministic_review(files)

        output_json = report.model_dump_json(indent=2)
        if parsed.output:
            out_path = Path(parsed.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_json)
            logger.info("Report written to %s", parsed.output)
        else:
            print(output_json)

        exit_map = {
            Verdict.APPROVE: 0,
            Verdict.REQUEST_CHANGES: 1,
            Verdict.REJECT: 2,
        }
        return exit_map.get(report.verdict, 3)

    except Exception as exc:
        logger.error("Code review failed: %s", exc)
        return 3


if __name__ == "__main__":
    sys.exit(run_code_reviewer_cli())
