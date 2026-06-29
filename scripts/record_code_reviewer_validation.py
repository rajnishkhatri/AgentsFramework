#!/usr/bin/env python3
"""WI-8 recording helper: run the v3 LLM reviewer over the labeled fixture.

Materializes each case from
``tests/fixtures/code_reviewer/wi8_validation/cases.json`` into a temp tree
(with the folder's ``REVIEW.md`` copied in so routing resolves), runs
``CodeReviewerAgent.review_v3_llm_only`` over it, and writes the recorded
verdicts to ``tests/fixtures/code_reviewer/wi8_validation/verdicts.json``.

Requires ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY`` / ``LITELLM_API_KEY``.
NOT invoked by CI — intended for human use when (re)recording the WI-8
validation set. See ``tests/fixtures/code_reviewer/wi8_validation/README.md``.

Usage::

    python scripts/record_code_reviewer_validation.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "code_reviewer" / "wi8_validation"
CASES_JSON = FIXTURE_DIR / "cases.json"
VERDICTS_JSON = FIXTURE_DIR / "verdicts.json"


def _build_synthetic_diff(repo_rel_path: str, content: str) -> str:
    """Build a 'new file' unified diff for a case file."""
    lines = content.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{repo_rel_path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def _materialize_case(case: dict) -> tuple[Path, list[str], str]:
    """Copy a case's files + governing REVIEW.md into a temp tree.

    Returns ``(temp_root, repo_relative_files, diff)``.
    """
    temp_root = Path(tempfile.mkdtemp(prefix=f"wi8-{case['id']}-"))
    case_dir = FIXTURE_DIR / "cases" / case["id"]

    # Copy each case file at its repo-relative path.
    for rel in case["files"]:
        src = case_dir / rel
        dst = temp_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # Copy the folder's REVIEW.md (and root REVIEW.md) so routing resolves
    # exactly as it would in the real repo. The router walks ancestors and
    # returns the first existing REVIEW.md.
    folder = case["folder"]
    review_sources: list[Path] = []
    if folder:
        review_sources.append(REPO_ROOT / folder / "REVIEW.md")
    review_sources.append(REPO_ROOT / "REVIEW.md")
    for src in review_sources:
        if not src.is_file():
            continue
        rel = src.relative_to(REPO_ROOT)
        dst = temp_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # Build a single combined diff across the case's files.
    diff_parts: list[str] = []
    for rel in case["files"]:
        content = (case_dir / rel).read_text(encoding="utf-8")
        diff_parts.append(_build_synthetic_diff(rel, content))
    diff = "\n".join(diff_parts)

    return temp_root, list(case["files"]), diff


async def _record_one(case: dict) -> dict:
    """Run the v3 LLM-only reviewer over one case; return the record."""
    from meta.code_reviewer import CodeReviewerAgent
    from meta.CodeReviewerAgentTest.env_settings import reviewer_profile_from_env
    from services.base_config import AgentConfig
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

    temp_root, files, diff = _materialize_case(case)

    try:
        profile = reviewer_profile_from_env()
        agent_config = AgentConfig(default_model=profile.name, models=[profile])
        llm = LLMService(agent_config)
        prompt_service = PromptService(template_dir=str(REPO_ROOT / "prompts"))
        agent = CodeReviewerAgent(
            llm_service=llm,
            prompt_service=prompt_service,
            judge_profile=profile,
            task_id=f"wi8-{case['id']}",
            user_id="wi8-recorder",
            prompt_version="v3",
            repo_root=temp_root,
        )
        report = await agent.review_v3_llm_only(files, diff)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    findings = [f for d in report.dimensions for f in d.findings]
    actionable = [f for f in findings if f.severity.value in {"critical", "warning"}]
    return {
        "case_id": case["id"],
        "folder": case["folder"],
        "gold_goal_met": case["gold_goal_met"],
        "rule_id": case.get("rule_id"),
        "llm_verdict": report.verdict.value,
        "llm_statement": report.statement,
        "llm_confidence": report.confidence,
        "finding_count": len(findings),
        "actionable_finding_count": len(actionable),
        "detected": len(actionable) > 0,  # judge says "not-met" iff actionable finding
        "findings": [
            {
                "rule_id": f.rule_id,
                "dimension": f.dimension,
                "severity": f.severity.value,
                "file": f.file,
                "description": f.description,
            }
            for f in findings
        ],
    }


async def _record_all() -> int:
    if not (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("LITELLM_API_KEY")
    ):
        print(
            "ERROR: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or LITELLM_API_KEY "
            "before recording.",
            file=sys.stderr,
        )
        return 1

    manifest = json.loads(CASES_JSON.read_text())
    cases = manifest["cases"]
    from meta.CodeReviewerAgentTest.env_settings import reviewer_profile_from_env

    judge_model_id = reviewer_profile_from_env().litellm_id
    print(f"Recording WI-8 verdicts for {len(cases)} cases (judge={judge_model_id})...")

    records: list[dict] = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {case['id']} ({case['folder']})...", flush=True)
        try:
            rec = await _record_one(case)
        except Exception as exc:  # noqa: BLE001 — surface every failure
            rec = {
                "case_id": case["id"],
                "folder": case["folder"],
                "gold_goal_met": case["gold_goal_met"],
                "rule_id": case.get("rule_id"),
                "error": str(exc),
                "detected": None,
            }
            print(f"      FAILED: {exc}", file=sys.stderr)
        records.append(rec)

    out = {
        "version": 1,
        "generated_by": "scripts/record_code_reviewer_validation.py",
        "judge_model": judge_model_id,
        "detection_convention": manifest.get("detection_convention"),
        "gate": manifest.get("gate"),
        "records": records,
    }
    VERDICTS_JSON.write_text(json.dumps(out, indent=2))
    print(f"Wrote {VERDICTS_JSON.relative_to(REPO_ROOT)}")

    # Quick summary so the human sees the gate result immediately.
    valid = [r for r in records if r.get("detected") is not None]
    if valid:
        judge = {r["case_id"]: not r["detected"] for r in valid}
        gold = {r["case_id"]: r["gold_goal_met"] for r in valid}
        from meta.judge_validation import validate_judge

        result = validate_judge(
            judge,
            gold,
            tpr_min=manifest["gate"]["tpr_min"],
            tnr_min=manifest["gate"]["tnr_min"],
        )
        verdict = "PASS" if result.passed else "FAIL"
        print(
            f"  VALIDATION: {verdict}  "
            f"TPR={result.rates.tpr}  TNR={result.rates.tnr}  "
            f"(n={result.counts.tp + result.counts.fp + result.counts.fn + result.counts.tn})"
        )
        for reason in result.reasons:
            print(f"    - {reason}")
    return 0


def main() -> int:
    return asyncio.run(_record_all())


if __name__ == "__main__":
    sys.exit(main())
