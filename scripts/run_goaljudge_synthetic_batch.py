#!/usr/bin/env python
"""Batch runner for GoalJudge synthetic saturation corpus.

Drives the live prompts through the real agent and GoalJudge locally
under a dedicated scoping user_id ("synthetic-saturation-user") with deterministic
32-hex trace/task/workflow IDs.

Before running, ensure you have the outbox relay running in another terminal:
    python -m middleware.sidecars
And ensure your LANGFUSE_* keys and OPENAI_API_KEY are configured.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Configure import paths
SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv
load_dotenv(AGENT_ROOT / ".env")

# Run from AGENT_ROOT so that logging.json's relative handlers (e.g.
# logs/evals.log) and the file_io /workspace sandbox resolve to the same
# locations the export reads from. cli.py does the same chdir.
os.chdir(str(AGENT_ROOT))

# Setup logging
from services.observability import setup_logging
setup_logging()

# Import core dependencies
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

# Import case registry
from tests.fixtures.goaljudge.case_registry import LIVE_CASES, GoalJudgeCase

console = Console()

# §10.2 shadow anchors gradable before post-G3 batch (plan §8.3 pass 1).
_PRE_G3_SHADOW_ANCHORS = frozenset({"GJ-008", "GJ-010", "GJ-012", "GJ-001B", "GJ-019"})


def _normalize_prompt_for_batch(prompt: str, workspace: Path) -> str:
    """Map registry `/workspace/…` paths to the local batch workspace dir.

    Only rewrites docker-style ``/workspace/`` prefixes. Prompts that already
    embed the repo ``workspace/`` mac path are left unchanged.
    """
    ws = str(workspace.resolve())
    if "/workspace/" not in prompt or ws in prompt:
        return prompt
    prefix = ws if ws.endswith("/") else ws + "/"
    return prompt.replace("/workspace/", prefix)


def _ensure_batch_env() -> Path:
    """Posture for Stage 4 confirmation batch (G3 remediation + G1)."""
    workspace = AGENT_ROOT / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    # Force local workspace to match registry mac paths; .env often sets /workspace.
    os.environ["WORKSPACE_DIR"] = str(workspace)

    cfg_path = AGENT_ROOT / "config" / "goal_judge_config.json"
    if cfg_path.is_file():
        os.environ.setdefault("GOAL_JUDGE_CONFIG_URI", f"file:{cfg_path}")
    os.environ.setdefault("GOAL_JUDGE_ENABLED", "true")
    os.environ.setdefault("GOAL_JUDGE_DOWNGRADE_ENABLED", "false")
    return workspace


def truncate_eval_log() -> None:
    """Truncate logs/evals.log to isolate this batch run's capture half."""
    evals_path = AGENT_ROOT / "logs" / "evals.log"
    evals_path.parent.mkdir(exist_ok=True)
    console.print(f"[bold yellow]Truncating {evals_path} to isolate batch run...[/bold yellow]")
    with open(evals_path, "w") as fh:
        fh.write("")  # clear file


def build_agent_and_tools() -> tuple[AgentConfig, RoutingConfig, ToolRegistry, AgentFactsRegistry]:
    """Assemble agent config, routing config, tools, and identity registry."""
    # One source of truth for the catalog (H2 registry). Honors MODEL_PROFILE_SET
    # from the env so the model-A/B harness's set-arm (Part II) can swap the whole
    # Auto stack by setting os.environ["MODEL_PROFILE_SET"] before this call.
    from services.llm_config import build_model_registry

    models, default_model = build_model_registry(
        os.environ.get("MODEL_PROFILE_SET", "openai")
    )

    agent_config = AgentConfig(
        default_model=default_model,
        models=models,
        max_steps=20,
        max_cost_usd=1.0,
        goal_judge_enabled=True,
        goal_judge_downgrade_enabled=False,
    )
    # Pass default_model explicitly so routing_config.default_model can never
    # disagree with agent_config.models (F1/F10 — both come from the SAME
    # build_model_registry call, not two independent reads).
    routing_config = RoutingConfig(default_model=default_model)

    delegation_dispatcher = LocalLLMDelegationDispatcher(agent_config)
    tool_registry = ToolRegistry({
        # shell/file_io not cacheable: thread tool_cache never invalidates, so
        # repeating an identical command/read after the file changes is stale.
        "shell": ToolDefinition(executor=execute_shell, schema=ShellToolInput, cacheable=False),
        "file_io": ToolDefinition(executor=execute_file_io, schema=FileIOInput, cacheable=False),
        "state_file": ToolDefinition(executor=execute_state_file_tool, schema=StateFileToolInput, cacheable=False),
        "state_todo": ToolDefinition(executor=execute_state_todo_tool, schema=StateTodoToolInput, cacheable=False),
        "task": ToolDefinition(
            executor=build_task_tool_executor(delegation_dispatcher.dispatch),
            schema=TaskToolInput,
            cacheable=False,
        ),
        "think": ToolDefinition(executor=execute_think_tool, schema=ThinkToolInput, cacheable=False),
        "web_search": ToolDefinition(executor=execute_web_search, schema=WebSearchInput, cacheable=False),
    })

    cache_dir = AGENT_ROOT / "cache"
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
                capabilities=[Capability(name="delegate.subagent.*")],
                status=IdentityStatus.ACTIVE,
            ),
            registered_by="cli-bootstrap",
        )

    return agent_config, routing_config, tool_registry, agent_facts_registry


async def run_case(
    case: GoalJudgeCase,
    agent_config: AgentConfig,
    routing_config: RoutingConfig,
    tool_registry: ToolRegistry,
    agent_facts_registry: AgentFactsRegistry,
    *,
    workspace: Path,
    cache_dir: Path | None = None,
    graph_input_extra: dict | None = None,
) -> dict:
    """Execute a single synthetic case through the compiled LangGraph agent graph.

    ``cache_dir`` overrides where the graph writes black-box recordings /
    checkpoints (the model-A/B harness passes a per-arm dir so the two arms never
    cross-contaminate). ``graph_input_extra`` merges extra keys into the initial
    graph-state dict — the A/B harness seeds ``selected_model`` here, the same way
    the UI pins a model, so the router's ``pinned_model`` branch honors it.
    """
    # Compute deterministic 32-hex trace ID based on case ID
    trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, case.id).hex
    workflow_id = trace_id
    task_id = trace_id
    session_id = f"session-{case.id.lower()}"
    user_id = "synthetic-saturation-user"
    agent_id = "cli-agent"
    cache_dir = cache_dir or (AGENT_ROOT / "cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    extra = graph_input_extra or {}
    task_input = _normalize_prompt_for_batch(case.prompt, workspace)

    console.print(Panel(
        f"[bold cyan]Case ID:[/bold cyan] {case.id}\n"
        f"[bold cyan]Target Code:[/bold cyan] {case.target_code}\n"
        f"[bold cyan]Stratum / Domain:[/bold cyan] {case.stratum} / {case.domain}\n"
        f"[bold cyan]Trace ID (32-hex):[/bold cyan] {trace_id}\n"
        f"[bold cyan]Prompt:[/bold cyan] {task_input}",
        title="Executing Synthetic Case"
    ))

    # AsyncSqliteSaver.from_conn_string is used to enable checkpointer
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(str(cache_dir / "checkpoints.db")) as checkpointer:
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
                    **extra,
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
                **extra,
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


async def main() -> None:
    # Ensure keys are present
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[bold red]Error: OPENAI_API_KEY environment variable is not configured.[/bold red]")
        sys.exit(1)
    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get("LANGFUSE_SECRET_KEY"):
        console.print("[bold red]Error: LANGFUSE keys are not configured. Telemetry is required.[/bold red]")
        sys.exit(1)

    console.print(f"[bold green]Found {len(LIVE_CASES)} live cases to execute.[/bold green]")
    
    # Prompt before full live run
    import argparse
    parser = argparse.ArgumentParser(description="Run GoalJudge synthetic saturation corpus batch")
    parser.add_argument("--case", help="Specific Case ID to run (e.g., GJ-001)")
    parser.add_argument(
        "--anchors",
        action="store_true",
        help="Run §10.2 pre-G3 shadow anchors only (GJ-008/010/012/001B/019)",
    )
    parser.add_argument(
        "--export-replay",
        action="store_true",
        help="After batch, write cache/goaljudge_eval/shadow_replay.json",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    workspace = _ensure_batch_env()

    cases_to_run = LIVE_CASES
    if args.case:
        cases_to_run = [c for c in LIVE_CASES if c.id == args.case]
        if not cases_to_run:
            console.print(f"[bold red]Case {args.case} not found in registry.[/bold red]")
            sys.exit(1)
    elif args.anchors:
        cases_to_run = [c for c in LIVE_CASES if c.id in _PRE_G3_SHADOW_ANCHORS]
        if len(cases_to_run) != len(_PRE_G3_SHADOW_ANCHORS):
            found = {c.id for c in cases_to_run}
            missing = _PRE_G3_SHADOW_ANCHORS - found
            console.print(
                f"[bold red]Anchor filter missing registry cases: {sorted(missing)}[/bold red]"
            )
            sys.exit(1)

    if not args.yes:
        confirm = input(f"Do you want to run {len(cases_to_run)} cases locally? This will cost real LLM tokens. (y/N): ")
        if confirm.lower() != "y":
            console.print("[yellow]Batch execution canceled.[/yellow]")
            sys.exit(0)

    # Clean previous evals log
    truncate_eval_log()

    # Build agent wiring
    agent_config, routing_config, tool_registry, agent_facts_registry = build_agent_and_tools()

    success_count = 0
    for i, case in enumerate(cases_to_run, 1):
        console.print(f"\n[bold green]=== [Running Case {i}/{len(cases_to_run)}] ===[/bold green]")
        try:
            result = await run_case(
                case,
                agent_config,
                routing_config,
                tool_registry,
                agent_facts_registry,
                workspace=workspace,
            )
            success_count += 1
            console.print(f"[bold green]Case {case.id} completed successfully.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Case {case.id} failed to run: {e}[/bold red]")

    console.print(Panel(
        f"Executed: {len(cases_to_run)} cases\n"
        f"Completed: {success_count} successfully\n"
        f"Failed: {len(cases_to_run) - success_count} failures",
        title="Batch Run Complete"
    ))

    if args.export_replay:
        from scripts.export_goaljudge_shadow_replay import export_shadow_replay

        out = AGENT_ROOT / "cache" / "goaljudge_eval" / "shadow_replay.json"
        count, missing = export_shadow_replay(out_path=str(out))
        if missing:
            console.print(
                f"[bold yellow]Shadow replay: {count} anchors written; "
                f"missing: {sorted(missing)}[/bold yellow]"
            )
        else:
            console.print(
                f"[bold green]Shadow replay export: {count} anchors → {out}[/bold green]"
            )
            console.print(
                "[dim]Behavioral gate: "
                f"GOALJUDGE_LANGFUSE_EXPORT={out} "
                "pytest tests/components/test_goal_judge_shadow_offline.py -q[/dim]"
            )


if __name__ == "__main__":
    asyncio.run(main())
