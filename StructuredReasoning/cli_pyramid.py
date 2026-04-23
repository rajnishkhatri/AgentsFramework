"""CLI entry point for the Pyramid ReACT agent.

Run from the ``agent/`` directory::

    python -m StructuredReasoning.cli_pyramid "<problem statement>"

or, with the parent of ``agent/`` on ``sys.path``::

    python -m agent.StructuredReasoning.cli_pyramid "<problem>"

On a successful run the CLI:
1. Pretty-prints a YAML render of ``analysis_output`` inside a Rich Panel
   (governing thought first, then the key arguments, then the validation
   log).
2. Writes the full JSON payload to
   ``cache/pyramid/<workflow_id>/analysis.json``.
3. Prints a one-line summary: iterations, steps, total cost in USD.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel

AGENT_ROOT = Path(__file__).resolve().parent.parent


def _build_default_tool_registry() -> Any:
    """Same default tool set as the outer ``cli.py``.

    Pyramid PR 1 does not invoke tools, but the registry is still built
    so the system prompt's ``Available tools`` block is populated and
    PR 2's ``act`` node can dispatch real tool calls without changing
    this entry point.
    """
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.shell import ShellToolInput, execute_shell
    from services.tools.web_search import WebSearchInput, execute_web_search

    return ToolRegistry({
        "shell": ToolDefinition(executor=execute_shell, schema=ShellToolInput, cacheable=True),
        "file_io": ToolDefinition(executor=execute_file_io, schema=FileIOInput, cacheable=True),
        "web_search": ToolDefinition(executor=execute_web_search, schema=WebSearchInput, cacheable=False),
    })


def _build_agent_config() -> Any:
    from services.base_config import AgentConfig, ModelProfile

    fast = ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )
    capable = ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )
    return AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=5.0,
    )


def _render_panel(console: Console, analysis: dict[str, Any]) -> None:
    """Render the analysis_output as YAML inside a Rich Panel."""
    yaml_text = yaml.safe_dump(
        analysis,
        sort_keys=False,
        default_flow_style=False,
        width=100,
        allow_unicode=True,
    )
    console.print(Panel(
        yaml_text,
        title="[bold green]analysis_output[/bold green]",
        border_style="green",
    ))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m StructuredReasoning.cli_pyramid '<problem statement>'")
        sys.exit(1)

    task_input = " ".join(sys.argv[1:])
    console = Console()

    logs_dir = AGENT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    os.chdir(str(AGENT_ROOT))

    from services.observability import setup_logging
    setup_logging()

    from StructuredReasoning.orchestration.pyramid_loop import build_pyramid_graph

    agent_config = _build_agent_config()
    tool_registry = _build_default_tool_registry()
    cache_dir = AGENT_ROOT / "cache"

    graph = build_pyramid_graph(
        agent_config=agent_config,
        tool_registry=tool_registry,
        cache_dir=cache_dir,
        max_iterations=3,
    )

    workflow_id = f"pyramid-wf-{uuid.uuid4().hex[:8]}"
    task_id = f"pyramid-task-{uuid.uuid4().hex[:8]}"
    user_id = os.environ.get("USER", "local-user")

    console.print(f"\n[bold blue]Pyramid Task:[/bold blue] {task_input}")
    console.print(f"[dim]workflow_id={workflow_id} task_id={task_id}[/dim]\n")

    result = asyncio.run(graph.ainvoke(
        {
            "task_id": task_id,
            "task_input": task_input,
            "messages": [],
            "workflow_id": workflow_id,
        },
        config={
            "configurable": {
                "task_id": task_id,
                "user_id": user_id,
                "workflow_id": workflow_id,
            },
        },
    ))

    outcome = result.get("last_outcome", "")
    analysis = result.get("analysis_output_json", {})

    if outcome == "rejected":
        console.print(Panel(
            "Input rejected by the pyramid input guardrail.",
            title="[bold red]Rejected[/bold red]",
            border_style="red",
        ))
    elif outcome == "parse_failed" or not analysis:
        console.print(Panel(
            f"Pyramid agent did not produce a valid analysis_output.\n"
            f"parse_error: {result.get('parse_error', 'unknown')}",
            title="[bold red]Parse Failure[/bold red]",
            border_style="red",
        ))
    else:
        _render_panel(console, analysis)
        out_path = cache_dir / "pyramid" / workflow_id / "analysis.json"
        console.print(f"[dim]analysis.json: {out_path}[/dim]")

    iterations = result.get("iteration_count", 1)
    cost = result.get("total_cost_usd", 0.0)
    console.print(
        f"\n[dim]Iterations: {iterations} | Cost: ${cost:.4f}[/dim]"
    )


if __name__ == "__main__":
    main()
