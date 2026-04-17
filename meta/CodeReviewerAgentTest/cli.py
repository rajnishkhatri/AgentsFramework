"""CLI for the reusable code-review agent wrapper.

Usage::

    python -m meta.CodeReviewerAgentTest agent/meta/CodeReviewerAgentTest/configs/phase1.json

Exit codes (matches :mod:`meta.code_reviewer`)::

    0  approve
    1  request_changes
    2  reject
    3  configuration / runtime error
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import langsmith
from dotenv import load_dotenv

from meta.CodeReviewerAgentTest.env_settings import (
    AGENT_ROOT,
    EnvSettings,
    reviewer_profile_from_env,
)
from meta.CodeReviewerAgentTest.report_renderer import render_markdown
from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig
from meta.CodeReviewerAgentTest.runner import run_review
from trust.review_schema import Verdict

logger = logging.getLogger("meta.CodeReviewerAgentTest.cli")

_EXIT_FOR_VERDICT = {
    Verdict.APPROVE: 0,
    Verdict.REQUEST_CHANGES: 1,
    Verdict.REJECT: 2,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m meta.CodeReviewerAgentTest",
        description="Reusable, env-driven CodeReviewer wrapper",
    )
    p.add_argument(
        "config_path",
        type=str,
        help="Path to a ReviewAgentConfig JSON file "
        "(see configs/phase1.json for an example).",
    )
    p.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Override config: skip the LLM phase. Useful for CI without API keys.",
    )
    p.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Override config.task_id (eval_capture H5).",
    )
    p.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Override config.user_id (eval_capture H5).",
    )
    return p


def _required_api_key(env_var: str) -> str | None:
    """Return the env-var name a given model_env_var implies (or None)."""
    settings = EnvSettings()
    field_name = env_var.lower()
    litellm_id = (getattr(settings, field_name, None) or "").lower()
    if litellm_id.startswith("anthropic/"):
        return "ANTHROPIC_API_KEY"
    if litellm_id.startswith("openai/") or litellm_id.startswith("gpt"):
        return "OPENAI_API_KEY"
    if litellm_id.startswith("together_ai/"):
        return "TOGETHER_API_KEY"
    return None


def _resolve_repo(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return AGENT_ROOT / p


def run_cli(argv: list[str] | None = None) -> int:
    """Entry point used by ``__main__`` and tests."""
    load_dotenv(AGENT_ROOT / ".env", override=False)
    args = _build_parser().parse_args(argv)

    config_path = Path(args.config_path)
    if not config_path.is_absolute():
        config_path = AGENT_ROOT / config_path
    if not config_path.is_file():
        logger.error("Config file not found: %s", config_path)
        return 3

    try:
        config = ReviewAgentConfig.from_path(config_path)
    except Exception as exc:
        logger.error("Failed to load config %s: %s", config_path, exc)
        return 3

    if args.deterministic_only:
        config = config.model_copy(update={"deterministic_only": True})
    if args.task_id is not None:
        config = config.model_copy(update={"task_id": args.task_id})
    if args.user_id is not None:
        config = config.model_copy(update={"user_id": args.user_id})

    if not config.deterministic_only:
        required_key = _required_api_key(config.model_env_var)
        if required_key and not os.environ.get(required_key):
            settings = EnvSettings()
            from_env_file = getattr(settings, required_key.lower(), None)
            if not from_env_file:
                logger.error(
                    "%s is required for the selected model but is not set "
                    "(neither in os.environ nor in .env). "
                    "Either set it or run with --deterministic-only.",
                    required_key,
                )
                return 3
            os.environ[required_key] = from_env_file

    try:
        traced_run = langsmith.traceable(
            run_type="chain",
            name=f"code-review:{config.name}",
            metadata={
                "phase": config.md_template_section_overrides.get("phase_label", ""),
                "task_id": config.task_id or "",
                "user_id": config.user_id,
                "files_count": len(config.files),
            },
        )(run_review)
        report = asyncio.run(traced_run(config))
    except Exception as exc:
        logger.exception("Review failed: %s", exc)
        return 3

    output_json_path = _resolve_repo(config.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(report.model_dump_json(indent=2))
    logger.info("Wrote JSON report to %s", output_json_path)

    if config.output_md:
        profile = reviewer_profile_from_env(config.model_env_var)
        ctx: dict[str, str] = {
            "model_used": profile.name,
            "litellm_id": profile.litellm_id,
            "task_id": config.task_id or "",
        }
        ctx.update(config.md_template_section_overrides)
        md_path = _resolve_repo(config.output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report, ctx))
        logger.info("Wrote markdown report to %s", md_path)

    return _EXIT_FOR_VERDICT.get(report.verdict, 3)


def main() -> int:  # pragma: no cover -- thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return run_cli()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
