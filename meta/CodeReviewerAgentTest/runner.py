"""Async runner that wraps :class:`meta.code_reviewer.CodeReviewerAgent`.

Responsibilities are intentionally narrow: build the LLM service, the
prompt service, the reviewer agent, and call ``.review()``. All review
logic stays in :mod:`meta.code_reviewer` -- this module is a glue layer
so that authoring a new code-review agent is a config edit, not a code
edit.
"""

from __future__ import annotations

import logging
from pathlib import Path

from meta.CodeReviewerAgentTest.env_settings import (
    AGENT_ROOT,
    reviewer_profile_from_env,
)
from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig
from meta.code_reviewer import CodeReviewerAgent
from services.base_config import AgentConfig
from services.llm_config import LLMService
from services.prompt_service import PromptService
from trust.review_schema import ReviewReport

logger = logging.getLogger("meta.CodeReviewerAgentTest.runner")


def _resolve(path: str) -> str:
    """Resolve a repo-relative path to an absolute path under AGENT_ROOT."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str(AGENT_ROOT / p)


async def run_review(config: ReviewAgentConfig) -> ReviewReport:
    """Build the reviewer from ``config`` and produce a :class:`ReviewReport`.

    Honours ``config.deterministic_only``: when set, the LLM service and
    the prompt service are not constructed at all, so missing API keys
    or template paths cannot block the deterministic phase.
    """
    profile = reviewer_profile_from_env(config.model_env_var)
    logger.info(
        "Running review %r with profile=%s (litellm_id=%s)",
        config.name,
        profile.name,
        profile.litellm_id,
    )

    llm_service: LLMService | None = None
    prompt_service: PromptService | None = None
    if not config.deterministic_only:
        agent_config = AgentConfig(
            default_model=profile.name,
            models=[profile],
        )
        llm_service = LLMService(agent_config)
        prompt_service = PromptService(
            template_dir=str(AGENT_ROOT / config.prompt_template_dir)
        )

    reviewer = CodeReviewerAgent(
        llm_service=llm_service,
        prompt_service=prompt_service,
        judge_profile=profile,
        task_id=config.task_id,
        user_id=config.user_id,
    )

    files = [_resolve(f) for f in config.files]
    diff_text: str | None = None
    if config.diff_path:
        diff_path = Path(_resolve(config.diff_path))
        if diff_path.is_file():
            diff_text = diff_path.read_text()
        else:
            logger.warning("Diff file not found: %s", diff_path)

    report = await reviewer.review(files, diff_text)
    return _normalize_report_paths(report)


def _normalize_report_paths(report: ReviewReport) -> ReviewReport:
    """Rewrite absolute paths in the report back to repo-relative form.

    The deterministic validators record whatever path they were given,
    so when the runner passes absolute paths the report becomes hard to
    read. Frozen models force us to reconstruct, but the rewrite is
    cheap and keeps the public output stable.
    """
    root = str(AGENT_ROOT) + "/"

    def _rel(s: str) -> str:
        if s.startswith(root):
            return s[len(root):]
        return s

    new_files = [_rel(f) for f in report.files_reviewed]
    new_log = [_rel(line) if root in line else line for line in report.validation_log]

    new_dimensions = []
    for dim in report.dimensions:
        new_findings = []
        for f in dim.findings:
            if f.file.startswith(root):
                new_findings.append(f.model_copy(update={"file": _rel(f.file)}))
            else:
                new_findings.append(f)
        new_dimensions.append(dim.model_copy(update={"findings": new_findings}))

    return report.model_copy(update={
        "files_reviewed": new_files,
        "validation_log": new_log,
        "dimensions": new_dimensions,
    })
