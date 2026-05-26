"""middleware/app_prod.py -- Production combined backend for Cloud Run.

Composes the middleware auth/ACL app (middleware/server.py) with the
agent_ui_adapter SSE surface (agent_ui_adapter/server.py) into a single
FastAPI application suitable for a combined Cloud Run deployment (Tier A).

Usage:
    uvicorn middleware.app_prod:build_combined_app --factory --host 0.0.0.0 --port 8080

Environment variables (all injected via Secret Manager on Cloud Run):
    GCP_EXECUTION_ENV       - "cloudrun" (triggers GCP adapter wiring)
    ARCHITECTURE_PROFILE    - "v3" (default)
    DATABASE_URL            - postgres connection string
    GCS_FACTS_BUCKET        - agent-facts bucket name
    GCS_TRACES_BUCKET       - trust-traces bucket name
    AGENT_FACTS_SECRET      - HMAC key for fact signing
    OPENAI_API_KEY          - LLM provider key
    WORKOS_CLIENT_ID        - WorkOS auth
    WORKOS_API_KEY          - WorkOS auth
    MEM0_API_KEY            - long-term memory
    LANGFUSE_PUBLIC_KEY     - observability
    LANGFUSE_SECRET_KEY     - observability
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

AGENT_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "150")

sys.path.insert(0, str(AGENT_ROOT))

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.transport.sse import (
    PROXY_HEADERS,
    SENTINEL_LINE,
    encode_error,
    encode_event,
)
from middleware.composition import build_adapters
from middleware.server import build_middleware_app
from services.base_config import AgentConfig, ModelProfile
from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry
from services.observability import setup_logging
from services.trace_service import TraceService
from services.trace_sinks.gcs_sink import GcsTraceSink
from services.tools.delegation_dispatcher import LocalLLMDelegationDispatcher
from services.tools.file_io import FileIOInput, execute_file_io
from services.tools.file_tools import StateFileToolInput, execute_state_file_tool
from services.tools.registry import ToolDefinition, ToolRegistry
from services.tools.shell import ShellToolInput, execute_shell
from services.tools.task_tool import TaskToolInput, build_task_tool_executor
from services.tools.think_tool import ThinkToolInput, execute_think_tool
from services.tools.todo_tools import StateTodoToolInput, execute_state_todo_tool
from services.tools.web_search import WebSearchInput, execute_web_search
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability

logger = logging.getLogger("middleware.app_prod")


def _load_graph_factory():
    """Load the graph factory from langgraph.json without static imports."""
    config_path = AGENT_ROOT / "langgraph.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    target = payload.get("graphs", {}).get("react_loop")
    if not target or ":" not in target:
        raise RuntimeError("langgraph.json missing graphs.react_loop entry")
    module_name, attr_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, attr_name, None)
    if factory is None:
        raise RuntimeError(f"Graph factory '{target}' not found")
    return factory


def _build_components() -> tuple[AgentConfig, ToolRegistry, AgentFactsGcsRegistry, Path]:
    """Build non-async components for the production backend."""
    setup_logging()

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

    delegation_dispatcher = LocalLLMDelegationDispatcher(agent_config)
    tool_registry = ToolRegistry({
        "shell": ToolDefinition(
            executor=execute_shell, schema=ShellToolInput, cacheable=True
        ),
        "file_io": ToolDefinition(
            executor=execute_file_io, schema=FileIOInput, cacheable=True
        ),
        "state_file": ToolDefinition(
            executor=execute_state_file_tool, schema=StateFileToolInput, cacheable=False
        ),
        "state_todo": ToolDefinition(
            executor=execute_state_todo_tool, schema=StateTodoToolInput, cacheable=False
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
    })

    cache_dir = Path(os.environ.get("AGENT_OFFLOAD_DIR", "/tmp/agent_offload"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    agent_facts_secret = os.environ.get(
        "AGENT_FACTS_SECRET", "dev-secret-do-not-use-in-production"
    )
    gcs_facts_bucket = os.environ.get("GCS_FACTS_BUCKET", "")
    if not gcs_facts_bucket:
        raise RuntimeError("GCS_FACTS_BUCKET is required in production")

    agent_facts_registry = AgentFactsGcsRegistry(
        bucket_name=gcs_facts_bucket,
        secret=agent_facts_secret,
    )

    return agent_config, tool_registry, agent_facts_registry, cache_dir


def build_combined_app() -> FastAPI:
    """Factory function for the combined production backend.

    Called by uvicorn with --factory flag:
        uvicorn middleware.app_prod:build_combined_app --factory
    """
    agent_config, tool_registry, agent_facts_registry, cache_dir = _build_components()
    build_graph = _load_graph_factory()

    gcs_traces_bucket = os.environ.get("GCS_TRACES_BUCKET", "")
    if not gcs_traces_bucket:
        raise RuntimeError("GCS_TRACES_BUCKET is required in production")
    trace_service = TraceService(sinks=[GcsTraceSink(gcs_traces_bucket)])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Enter async Postgres checkpointer before graph compilation."""
        from agent_ui_adapter.adapters.runtime.postgres_saver import PostgresCheckpointer

        async with PostgresCheckpointer.from_env() as pg_cp:
            graph = build_graph(
                agent_config=agent_config,
                tool_registry=tool_registry,
                cache_dir=cache_dir,
                checkpointer=pg_cp.saver,
                agent_facts_registry=agent_facts_registry,
                interrupt_before_execute_tool=False,
            )
            app.state.runtime = LangGraphRuntime(
                graph, trace_emit=trace_service.emit
            )
            logger.info("Production graph compiled, runtime ready")
            yield

    adapters = build_adapters()
    middleware_app = build_middleware_app(adapters=adapters)

    app = FastAPI(
        title="Agent Combined Backend",
        description="Production combined backend: middleware auth/ACL + agent runtime",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    @app.get("/health")
    async def healthz():
        """Cloud Run liveness/readiness probe — pre-auth."""
        return {
            "status": "ok",
            "profile": adapters.profile,
            "runtime": "langgraph",
            "mode": "combined",
        }

    app.mount("/middleware", middleware_app)

    @app.post("/run/stream")
    async def run_stream(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """SSE streaming endpoint matching BFF expectations."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")

        runtime: LangGraphRuntime = request.app.state.runtime
        body = await request.json()
        thread_id = body.get("thread_id", uuid.uuid4().hex)
        user_input = body.get("input", {})
        task_input = ""
        if isinstance(user_input, dict):
            messages = user_input.get("messages", [])
            if messages:
                last = messages[-1]
                if isinstance(last, dict):
                    task_input = last.get("content", "")
                elif isinstance(last, str):
                    task_input = last

        token = authorization[len("Bearer "):].strip()
        try:
            claims = adapters.jwt_verifier.verify(token)
        except Exception as exc:
            logger.warning(
                "jwt_verify_failed type=%s detail=%s",
                type(exc).__name__,
                str(exc)[:200],
            )
            raise HTTPException(
                status_code=401, detail=f"invalid token: {exc}"
            ) from None

        try:
            identity = agent_facts_registry.get(claims.subject)
        except KeyError:
            identity = agent_facts_registry.register(
                AgentFacts(
                    agent_id=claims.subject,
                    agent_name=claims.subject,
                    owner=claims.subject,
                    version="1.0.0",
                    description="Auto-provisioned on first authenticated request",
                    capabilities=[Capability(name="delegate.subagent.*")],
                    status=IdentityStatus.ACTIVE,
                ),
                registered_by="app_prod:auto_provision",
            )
            logger.info("auto_provisioned_identity subject=%s", claims.subject)

        run_started_at = time.monotonic()

        async def _generate() -> AsyncIterator[bytes]:
            run_id: str | None = None
            trace_id_seen: str | None = None
            errored = False
            try:
                async for domain_event in runtime.run(
                    thread_id=thread_id,
                    input={**(user_input or {}), "task_input": task_input},
                    identity=identity,
                ):
                    if trace_id_seen is None:
                        trace_id_seen = domain_event.trace_id
                    if run_id is None and hasattr(domain_event, "run_id"):
                        run_id = domain_event.run_id
                    for ag_ui_event in to_ag_ui(domain_event):
                        yield encode_event(
                            ag_ui_event, event_id=uuid.uuid4().hex
                        )
                yield SENTINEL_LINE
            except Exception as exc:
                errored = True
                logger.exception("stream error: %s", exc)
                yield encode_error(
                    f"{type(exc).__name__}: {exc}", code="runtime_error"
                )
                yield SENTINEL_LINE
            finally:
                duration_ms = int((time.monotonic() - run_started_at) * 1000)
                logger.info(
                    "stream_ended run_id=%s thread=%s trace=%s "
                    "duration_ms=%d errored=%s",
                    run_id, thread_id, trace_id_seen, duration_ms, errored,
                )

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers=dict(PROXY_HEADERS),
        )

    @app.post("/run/cancel")
    async def run_cancel(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        body = await request.json()
        run_id = body.get("run_id", "")
        runtime: LangGraphRuntime = request.app.state.runtime
        await runtime.cancel(run_id)
        return {"cancelled": run_id}

    logger.info(
        "Combined production app built profile=%s",
        adapters.profile,
    )
    return app
