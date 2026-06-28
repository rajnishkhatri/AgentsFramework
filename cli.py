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
    from services.base_config import AgentConfig
    from services.governance.agent_facts_registry import AgentFactsRegistry
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.delegation_dispatcher import LocalLLMDelegationDispatcher
    from services.tools.file_tools import StateFileToolInput, execute_state_file_tool
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.shell import ShellToolInput, execute_shell
    from services.tools.task_tool import TaskToolInput, build_task_tool_executor
    from services.tools.think_tool import ThinkToolInput, execute_think_tool
    from services.tools.todo_tools import StateTodoToolInput, execute_state_todo_tool
    from services.tools.web_search import WebSearchInput, execute_web_search
    from trust.enums import IdentityStatus
    from trust.models import AgentFacts, Capability

    # One source of truth for the catalog (H2 registry); honors MODEL_PROFILE_SET
    # from the env so an A/B set-arm run can swap the whole Auto stack.
    # (`os` is already imported at module scope — a second function-local import
    # here made `os` a local, breaking the earlier os.chdir with UnboundLocalError.)
    from services.llm_config import build_model_registry

    models, default_model = build_model_registry(
        os.environ.get("MODEL_PROFILE_SET", "openai")
    )

    agent_config = AgentConfig(
        default_model=default_model,
        models=models,
        max_steps=20,
        max_cost_usd=1.0,
    )
    # Pass default_model explicitly so routing_config.default_model tracks the
    # SAME registry read as agent_config.models (F1/F10).
    routing_config = RoutingConfig(default_model=default_model)

    delegation_dispatcher = LocalLLMDelegationDispatcher(agent_config)
    tool_registry = ToolRegistry(
        {
            # shell/file_io not cacheable: thread tool_cache never invalidates, so
            # repeating an identical command/read after the file changes is stale.
            "shell": ToolDefinition(
                executor=execute_shell, schema=ShellToolInput, cacheable=False
            ),
            "file_io": ToolDefinition(
                executor=execute_file_io, schema=FileIOInput, cacheable=False
            ),
            "state_file": ToolDefinition(
                executor=execute_state_file_tool,
                schema=StateFileToolInput,
                cacheable=False,
            ),
            "state_todo": ToolDefinition(
                executor=execute_state_todo_tool,
                schema=StateTodoToolInput,
                cacheable=False,
            ),
            "task": ToolDefinition(
                executor=build_task_tool_executor(delegation_dispatcher.dispatch),
                schema=TaskToolInput,
                cacheable=False,
            ),
            "think": ToolDefinition(
                executor=execute_think_tool, schema=ThinkToolInput, cacheable=False
            ),
            "web_search": ToolDefinition(
                executor=execute_web_search, schema=WebSearchInput, cacheable=False
            ),
        }
    )

    cache_dir = AGENT_ROOT / "cache"

    # Story 1.4: AgentFacts registry setup
    agent_facts_secret = os.environ.get(
        "AGENT_FACTS_SECRET", "dev-secret-do-not-use-in-production"
    )
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
                capabilities=[Capability(name="delegate.subagent.*")],
                status=IdentityStatus.ACTIVE,
            ),
            registered_by="cli-bootstrap",
        )

    workflow_id = uuid.uuid4().hex
    task_id = workflow_id
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
                    interrupt_before_execute_tool=False,
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
                        "recursion_limit": 100,
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
                    "recursion_limit": 100,
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
        console.print(
            Panel(
                final_answer,
                title="[bold green]Final Answer[/bold green]",
                border_style="green",
            )
        )
    else:
        console.print("[yellow]No final answer produced.[/yellow]")

    steps = result.get("step_count", 0)
    cost = result.get("total_cost_usd", 0.0)
    console.print(f"\n[dim]Steps: {steps} | Cost: ${cost:.4f}[/dim]")


if __name__ == "__main__":
    main()
