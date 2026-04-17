"""Jinja2 template rendering + render logging (H1 pattern).

Renders .j2 templates from the prompts/ directory. Logs every render
to the services.prompt_service logger for auditability.

Notable templates: ``system_prompt``, ``routing_policy``, ``input_guardrail``,
``output_guardrail``, ``codeReviewer/CodeReviewer_system_prompt``,
``sprint_story_agent_system`` (includes ``includes/sprint_architecture_digest.j2`` when
``include_architecture_digest`` is true).
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger("services.prompt_service")

_DEFAULT_TEMPLATE_DIR = str(Path(__file__).resolve().parent.parent / "prompts")


class PromptService:
    def __init__(self, template_dir: str = _DEFAULT_TEMPLATE_DIR) -> None:
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape([]),
            undefined=__import__("jinja2").StrictUndefined,
        )

    def render_prompt(self, template_name: str, **context) -> str:
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"
        template = self._env.get_template(template_name)
        rendered = template.render(**context)
        logger.info(
            "Rendered template %s",
            template_name,
            extra={"template": template_name, "context_keys": list(context.keys())},
        )
        return rendered
