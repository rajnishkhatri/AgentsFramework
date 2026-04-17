"""Developer-facing schema: a single JSON file describes a code-review agent.

The fields below are the only knobs an author needs to expose a new
code-review agent. The runner, env settings, and renderer are reused
across all configs.

Example file (see ``configs/phase1.json``)::

    {
      "name": "phase1-verification",
      "model_env_var": "MODEL_NAME",
      "files": ["trust/__init__.py", ...],
      "output_json": "docs/PHASE1_CODE_REVIEW.json",
      "output_md":   "docs/PHASE1_CODE_REVIEW.md"
    }
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewAgentConfig(BaseModel):
    """Schema for a single code-review agent invocation."""

    name: str = Field(
        description="Short slug for the agent, used in logs and report metadata.",
        min_length=1,
    )
    description: str = ""
    model_env_var: str = Field(
        default="MODEL_NAME",
        description="Which .env variable selects the LLM (MODEL_NAME, "
        "MODEL_NAME_JUDGE, MODEL_NAME_REVIEWER).",
    )
    files: list[str] = Field(
        description="Repo-relative Python files to review.",
        min_length=1,
    )
    diff_path: str | None = Field(
        default=None,
        description="Optional repo-relative path to a unified diff file.",
    )
    prompt_template_dir: str = Field(
        default="prompts",
        description="Template root, relative to AGENT_ROOT.",
    )
    system_prompt_template: str = Field(
        default="codeReviewer/CodeReviewer_system_prompt",
        description="Template path (without .j2) for the system prompt.",
    )
    submission_template: str = Field(
        default="codeReviewer/CodeReviewer_review_submission",
        description="Template path (without .j2) for the user submission.",
    )
    task_id: str | None = None
    user_id: str = "code-reviewer"
    deterministic_only: bool = Field(
        default=False,
        description="When True, skip the LLM phase and run only the "
        "deterministic validators (no API key required).",
    )
    output_json: str = Field(
        description="Repo-relative path for the ReviewReport JSON dump.",
    )
    output_md: str | None = Field(
        default=None,
        description="If set, also render markdown to this repo-relative path.",
    )
    md_template_section_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Free-form context dict passed to the markdown renderer "
        "(phase_label, plan_reference, decomposition_axis, ...).",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("files")
    @classmethod
    def _files_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("files must contain at least one entry")
        return value

    @classmethod
    def from_path(cls, path: str | Path) -> "ReviewAgentConfig":
        """Convenience loader: read JSON from disk and validate."""
        return cls.model_validate_json(Path(path).read_text())
