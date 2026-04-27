"""CLI entry point: python -m agent.cli "task"

Parses task_input, builds AgentConfig/RoutingConfig, constructs
RunnableConfig, invokes compiled graph, pretty-prints final answer.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

AGENT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m agent.cli '<task>'")
        sys.exit(1)

    task_input = " ".join(sys.argv[1:])
    console = Console()

    logs_dir = AGENT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    from services.observability import setup_logging

    os.chdir(str(AGENT_ROOT))
    setup_logging()

    from components.routing_config import RoutingConfig
    from orchestration.react_loop import build_graph
    from services.base_config import AgentConfig, ModelProfile
    from services.governance.agent_facts_registry import AgentFactsRegistry
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.shell import ShellToolInput, execute_shell
    from services.tools.web_search import WebSearchInput, execute_web_search
    from trust.enums import IdentityStatus
    from trust.models import AgentFacts

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

    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
    )
    routing_config = RoutingConfig()

    tool_registry = ToolRegistry({
        "shell": ToolDefinition(executor=execute_shell, schema=ShellToolInput, cacheable=True),
        "file_io": ToolDefinition(executor=execute_file_io, schema=FileIOInput, cacheable=True),
        "web_search": ToolDefinition(executor=execute_web_search, schema=WebSearchInput, cacheable=False),
    })

    cache_dir = AGENT_ROOT / "cache"

    # Story 1.4: AgentFacts registry setup
    agent_facts_secret = os.environ.get("AGENT_FACTS_SECRET", "dev-secret-do-not-use-in-production")
    agent_facts_dir = cache_dir / "agent_facts"
    agent_facts_registry = AgentFactsRegistry(
        storage_dir=agent_facts_dir,
        secret=agent_facts_secret,
    )

    agent_id = "cli-agent"
    try:
        agent_facts_registry.get(agent_id)
    except KeyError:
        agent_facts_registry.register(
            AgentFacts(
                agent_id=agent_id,
                agent_name="CLI Agent",
                owner="cli-user",
                version="1.0.0",
                description="Default CLI agent",
                status=IdentityStatus.ACTIVE,
            ),
            registered_by="cli-bootstrap",
        )

    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    user_id = os.environ.get("USER", "local-user")

    console.print(f"\n[bold blue]Task:[/bold blue] {task_input}")
    console.print(f"[dim]workflow_id={workflow_id} task_id={task_id}[/dim]\n")

    async def _run_with_checkpointer() -> dict:
        # AsyncSqliteSaver.from_conn_string is an @asynccontextmanager — must
        # be entered with `async with` before the graph can use it.
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            async with AsyncSqliteSaver.from_conn_string(
                str(cache_dir / "checkpoints.db")
            ) as checkpointer:
                graph = build_graph(
                    agent_config=agent_config,
                    routing_config=routing_config,
                    tool_registry=tool_registry,
                    cache_dir=cache_dir,
                    checkpointer=checkpointer,
                    agent_facts_registry=agent_facts_registry,
                )
                return await graph.ainvoke(
                    {
                        "task_id": task_id,
                        "task_input": task_input,
                        "messages": [],
                        "workflow_id": workflow_id,
                        "registered_agent_id": agent_id,
                    },
                    config={
                        "configurable": {
                            "task_id": task_id,
                            "user_id": user_id,
                            "workflow_id": workflow_id,
                            "registered_agent_id": agent_id,
                            "thread_id": session_id,
                        },
                    },
                )
        except ImportError:
            graph = build_graph(
                agent_config=agent_config,
                routing_config=routing_config,
                tool_registry=tool_registry,
                cache_dir=cache_dir,
                checkpointer=None,
                agent_facts_registry=agent_facts_registry,
            )
            return await graph.ainvoke(
                {
                    "task_id": task_id,
                    "task_input": task_input,
                    "messages": [],
                    "workflow_id": workflow_id,
                    "registered_agent_id": agent_id,
                },
                config={
                    "configurable": {
                        "task_id": task_id,
                        "user_id": user_id,
                        "workflow_id": workflow_id,
                        "registered_agent_id": agent_id,
                        "thread_id": session_id,
                    },
                },
            )

    result = asyncio.run(_run_with_checkpointer())

    messages = result.get("messages", [])
    final_answer = None
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if content:
            final_answer = content
            break

    if final_answer:
        console.print(Panel(
            final_answer,
            title="[bold green]Final Answer[/bold green]",
            border_style="green",
        ))
    else:
        console.print("[yellow]No final answer produced.[/yellow]")

    steps = result.get("step_count", 0)
    cost = result.get("total_cost_usd", 0.0)
    console.print(f"\n[dim]Steps: {steps} | Cost: ${cost:.4f}[/dim]")


if __name__ == "__main__":
    main()
