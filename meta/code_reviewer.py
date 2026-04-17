"""CodeReviewer Agent: architecture validation via LLM + deterministic checks (STORY-408/409/410).

Produces structured ReviewReport output. Uses PromptService for all prompts.
Zero imports from orchestration/.
"""

from __future__ import annotations

import ast
import json
import logging
import sys
import uuid
from pathlib import Path
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
    detect_anti_patterns,
)

logger = logging.getLogger("meta.code_reviewer")

AGENT_ROOT = Path(__file__).resolve().parent.parent


# ── STORY-409: Deterministic dimension validators ───────────────────


def check_import_rules(file_path: str) -> list[ReviewFinding]:
    """Run all deterministic import validators and return findings."""
    findings: list[ReviewFinding] = []

    dep_result = check_dependency_rules(file_path)
    for v in dep_result.get("violations", []):
        findings.append(ReviewFinding(
            rule_id=v["rule"],
            dimension="D1",
            severity=Severity.CRITICAL,
            file=v["file"],
            line=v.get("line"),
            description=v["description"],
            fix_suggestion="Remove the forbidden import and restructure to follow the dependency table.",
            confidence=1.0,
            certificate=Certificate(
                premises=[f"[P1] check_dependency_rules: {v['file']}:{v.get('line', '?')} — {v['description']}"],
                traces=[f"[T1] {v['file']} imports from forbidden layer"],
                conclusion=f"{v['rule']} FAIL — {v['description']}",
            ),
        ))

    purity_result = check_trust_purity(file_path)
    for v in purity_result.get("violations", []):
        findings.append(ReviewFinding(
            rule_id=v["rule"],
            dimension="D4",
            severity=Severity.CRITICAL,
            file=v["file"],
            line=v.get("line"),
            description=v["description"],
            fix_suggestion="Remove the I/O import. Trust foundation must be pure data and pure functions.",
            confidence=1.0,
            certificate=Certificate(
                premises=[f"[P1] check_trust_purity: {v['file']}:{v.get('line', '?')} — {v['description']}"],
                conclusion=f"{v['rule']} FAIL — {v['description']}",
            ),
        ))

    ap_result = detect_anti_patterns(file_path)
    for v in ap_result.get("violations", []):
        findings.append(ReviewFinding(
            rule_id=v["rule"],
            dimension="D5",
            severity=Severity.WARNING,
            file=v["file"],
            line=v.get("line"),
            description=v["description"],
            fix_suggestion="Address the anti-pattern per the architecture style guide.",
            confidence=0.9,
            certificate=Certificate(
                premises=[f"[P1] detect_anti_patterns: {v['file']}:{v.get('line', '?')} — {v['description']}"],
                conclusion=f"{v['rule']} FAIL — {v['description']}",
            ),
        ))

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
        status = DimensionStatus.FAIL if has_critical else (
            DimensionStatus.PARTIAL if findings else DimensionStatus.PASS
        )
        dimensions.append(DimensionResult(
            dimension=dim_id,
            name=dim_name,
            status=status,
            hypotheses_tested=len(files_reviewed),
            hypotheses_confirmed=len(findings),
            hypotheses_killed=len(files_reviewed) - len(findings),
            findings=findings,
        ))

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
        statement = f"REQUEST CHANGES: {warning_count} warning(s) detected requiring attention."

    return ReviewReport(
        verdict=verdict,
        statement=statement,
        confidence=1.0 if not all_findings else 0.9,
        dimensions=dimensions,
        gaps=["D2 (Style Guide) not evaluated — deterministic mode",
              "D3 (Test Quality) not evaluated — deterministic mode"],
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
    ) -> None:
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile
        self._task_id = task_id or str(uuid.uuid4())
        self._user_id = user_id or "code_reviewer"

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
    ) -> ReviewReport:
        """Produce a structured review combining deterministic checks + LLM analysis."""
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

    async def _run_llm_review(
        self, files: list[str], diff: str | None
    ) -> ReviewReport:
        """Run LLM-based review with retry on schema validation failure."""
        system_prompt = self._prompt_service.render_prompt(
            "codeReviewer/CodeReviewer_system_prompt"
        )

        files_data = []
        for fp in files:
            p = Path(fp)
            if p.exists() and p.suffix == ".py":
                layer_info = classify_layer(fp)
                files_data.append({
                    "path": fp,
                    "layer": layer_info["layer"],
                    "content": p.read_text()[:10000],
                    "language": "python",
                })

        submission = self._prompt_service.render_prompt(
            "codeReviewer/CodeReviewer_review_submission",
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
                response = await self._llm_service.invoke(
                    self._judge_profile, messages
                )
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
        return ReviewReport(verdict=Verdict.REJECT, statement="Unexpected error", confidence=0.0)

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
        return ReviewReport.model_validate(data)

    def _merge_reports(
        self, deterministic: ReviewReport, llm: ReviewReport
    ) -> ReviewReport:
        """Merge deterministic and LLM reports, deterministic findings take priority."""
        all_findings = list(deterministic.dimensions)
        llm_dims = {d.dimension: d for d in llm.dimensions}

        merged_dims: list[DimensionResult] = []
        seen_dims: set[str] = set()

        for d in deterministic.dimensions:
            seen_dims.add(d.dimension)
            llm_dim = llm_dims.get(d.dimension)
            if llm_dim:
                extra_findings = [
                    f for f in llm_dim.findings
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
                        hypotheses_tested=d.hypotheses_tested + llm_dim.hypotheses_tested,
                        hypotheses_confirmed=d.hypotheses_confirmed + len(extra_findings),
                        hypotheses_killed=d.hypotheses_killed,
                        findings=list(d.findings) + extra_findings,
                    )
                    merged_dims.append(merged)
                    continue
            merged_dims.append(d)

        for d in llm.dimensions:
            if d.dimension not in seen_dims:
                merged_dims.append(d)

        all_f = [f for d in merged_dims for f in d.findings]
        critical = sum(1 for f in all_f if f.severity == Severity.CRITICAL)
        warnings = sum(1 for f in all_f if f.severity == Severity.WARNING)

        llm_infra_failed = llm.verdict == Verdict.REJECT and any(
            "LLM review failed" in g for g in llm.gaps
        )

        if llm_infra_failed:
            verdict = Verdict.REJECT
            statement = llm.statement
        elif critical > 0:
            verdict = Verdict.REJECT
            statement = deterministic.statement
        elif warnings > 2:
            verdict = Verdict.REQUEST_CHANGES
            statement = llm.statement
        else:
            verdict = Verdict.APPROVE
            statement = llm.statement

        return ReviewReport(
            verdict=verdict,
            statement=statement,
            confidence=min(deterministic.confidence, llm.confidence),
            dimensions=merged_dims,
            gaps=list(set(deterministic.gaps) | set(llm.gaps)),
            validation_log=deterministic.validation_log + llm.validation_log,
            files_reviewed=list(set(deterministic.files_reviewed) | set(llm.files_reviewed)),
        )


# ── CLI entrypoint (STORY-410) ──────────────────────────────────────


async def _async_llm_review(
    files: list[str],
    diff: str | None,
    task_id: str | None,
    user_id: str | None,
) -> ReviewReport:
    """Build services and run full CodeReviewerAgent.review (LLM + deterministic).

    Uses an explicit ``template_dir`` for :class:`PromptService` (mirroring
    the idiom in ``meta/judge.py``) so the CLI does NOT mutate the global
    working directory -- D5-W2 fix from the Phase 4 review.
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
    )
    return await reviewer.review(files, diff)


def run_code_reviewer_cli(args: list[str] | None = None) -> int:
    """CLI for running code reviews.

    Exit codes: 0=approve, 1=request_changes, 2=reject, 3=error.
    """
    import argparse
    import asyncio
    import os

    parser = argparse.ArgumentParser(description="CodeReviewer CLI")
    parser.add_argument("--files", nargs="+", required=True, help="Python files to review")
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
    parsed = parser.parse_args(args)

    if parsed.llm and parsed.deterministic_only:
        logger.error("Cannot combine --llm with --deterministic-only")
        return 3

    try:
        diff_text: str | None = None
        if parsed.diff:
            diff_path = Path(parsed.diff)
            if not diff_path.is_file():
                logger.error("Diff file not found: %s", parsed.diff)
                return 3
            diff_text = diff_path.read_text()

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
                    parsed.files,
                    diff_text,
                    task_id=parsed.task_id,
                    user_id=parsed.user_id,
                )
            )
        else:
            report = run_deterministic_review(parsed.files)

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
