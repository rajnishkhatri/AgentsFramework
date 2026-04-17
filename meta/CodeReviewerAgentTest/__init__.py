"""Reusable wrapper around :class:`meta.code_reviewer.CodeReviewerAgent`.

Provides an env-driven model selector, a small JSON config schema, an
async runner, and a markdown renderer so a developer can author a new
code-review agent (Phase verification, security audit, governance audit,
etc.) by writing a single JSON file under ``configs/``.

Public API:
    - :class:`EnvSettings` -- pydantic-settings reader for ``.env``
    - :func:`reviewer_profile_from_env` -- env var -> :class:`ModelProfile`
    - :class:`ReviewAgentConfig` -- developer-facing schema
    - :func:`run_review` -- async runner, returns a :class:`ReviewReport`
    - :func:`render_markdown` -- :class:`ReviewReport` -> markdown string

The new package lives in ``meta/`` and follows the AGENTS.md dependency
rule that ``meta/`` may import from ``trust/``, ``services/``,
``components/``, ``utils/`` -- never from ``orchestration/``.
"""

from __future__ import annotations

from meta.CodeReviewerAgentTest.env_settings import (
    EnvSettings,
    reviewer_profile_from_env,
)
from meta.CodeReviewerAgentTest.report_renderer import render_markdown
from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig
from meta.CodeReviewerAgentTest.runner import run_review

__all__ = [
    "EnvSettings",
    "ReviewAgentConfig",
    "render_markdown",
    "reviewer_profile_from_env",
    "run_review",
]
