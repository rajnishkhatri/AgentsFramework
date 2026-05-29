"""Local dev entry point: ``python -m middleware``

Starts a combined FastAPI app on port 8000 by default (matching the
frontend BFF's default ``MIDDLEWARE_URL``). If that port is busy, the next
free port up to +63 is used unless ``PORT_STRICT=1`` is set.

  1. Builds the real LangGraph ReAct graph from ``orchestration.react_loop``.
  2. Wraps it with ``LangGraphRuntime`` from ``agent_ui_adapter``.
  3. Serves the paths the BFF expects: ``/run/stream``, ``/run/cancel``,
     ``/threads``, ``/threads/{id}``, ``/healthz``.
  4. Uses a permissive dev-mode auth: any ``Bearer <token>`` is accepted
     and mapped to a local dev identity. Production deploys use
     ``middleware/server.py`` with real WorkOS JWT verification.

Usage::

    # from the repo root (loads .env automatically)
    python -m middleware

    # custom port
    PORT=9000 python -m middleware

    # fail if PORT is busy (no auto-increment)
    PORT_STRICT=1 python -m middleware
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import socket
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

AGENT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(AGENT_ROOT / ".env")

# LangGraph’s default cap (25 transitions) is low for ReAct+tools; align process
# default so any code path that merges against env-based DEFAULT gets headroom.
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
from agent_ui_adapter.wire.domain_events import RunFinishedDomain
from middleware import telemetry_bridge
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay
from services.base_config import AgentConfig, ModelProfile
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.observability import setup_logging
from services.trace_service import JsonlFileTraceSink, TraceService

_GCP_EXECUTION_ENV = os.environ.get("GCP_EXECUTION_ENV")
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
from utils.debug_fc2601 import debug_fc2601

logger = logging.getLogger("middleware.__main__")

_DEV_PORT_SEARCH_SPAN = 64


# ─────────────────────────────────────────────────────────────────────
# Telemetry exporter for dev parity (Phase 4)
# ─────────────────────────────────────────────────────────────────────


class _NoopTelemetryExporter:
    """Port-shaped stub: all methods are silent no-ops.

    Used when Langfuse is disabled or keys are not configured.
    Satisfies the TelemetryExporter protocol.
    """

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: dict | None = None,
    ) -> None:
        pass

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _build_dev_telemetry_exporter() -> TelemetryExporter:
    """Build a telemetry exporter for dev: Langfuse when available, noop otherwise.

    Kill switch: ``LANGFUSE_ENABLED=false`` → noop.
    Missing keys: no ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` → noop.
    Construction failure: ``LangfuseCloudExporter.__init__`` raises → noop.
    """
    if os.environ.get("LANGFUSE_ENABLED", "true").lower() == "false":
        logger.info("LANGFUSE_ENABLED=false; dev telemetry disabled")
        return _NoopTelemetryExporter()

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not pk or not sk:
        logger.info("Langfuse keys not configured; dev telemetry disabled")
        return _NoopTelemetryExporter()

    try:
        host = (
            os.environ.get("LANGFUSE_HOST")
            or os.environ.get("LANGFUSE_BASE_URL")
            or "https://cloud.langfuse.com"
        )
        exporter = LangfuseCloudExporter(
            public_key=pk, secret_key=sk, host=host
        )
        logger.info("Langfuse telemetry enabled for dev")
        return exporter
    except Exception as exc:
        logger.warning(
            "Langfuse exporter init failed: %s; dev telemetry disabled", exc
        )
        return _NoopTelemetryExporter()


def _build_dev_relay(
    exporter: TelemetryExporter, cache_dir: Path
) -> BlackBoxToTelemetryRelay | None:
    """Build the BlackBox→Langfuse relay for dev if enabled.

    Respects BLACKBOX_RELAY_MODE env (default: in_process).
    Passes compliance_publisher when the exporter satisfies the protocol.
    """
    mode = os.environ.get("BLACKBOX_RELAY_MODE", "in_process")
    if mode != "in_process":
        logger.info("BlackBox relay mode=%s; relay not started in-process", mode)
        return None

    storage_dir_str = os.environ.get("BLACKBOX_STORAGE_DIR", "")
    storage_dir = Path(storage_dir_str) if storage_dir_str else (cache_dir / "black_box_recordings")

    from middleware.ports.compliance_publisher import CompliancePublisher

    compliance_publisher = exporter if isinstance(exporter, CompliancePublisher) else None

    return BlackBoxToTelemetryRelay(
        storage_dir=storage_dir,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
    )


def _tcp_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Return True if *host*:*port* can be bound for a new listener.

    Intentionally omits ``SO_REUSEADDR`` so we detect ports held by typical
    dev servers (matching uvicorn's default bind semantics for "in use").
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _resolve_listen_port(preferred: int) -> int:
    """Return a listen port, starting at *preferred*.

    When ``PORT_STRICT`` is truthy, only *preferred* may be used.
    Otherwise the next free port in a bounded range is chosen.
    """
    strict = os.environ.get("PORT_STRICT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if strict:
        if not _tcp_port_available(preferred):
            msg = (
                f"Port {preferred} is not available (PORT_STRICT is set). "
                "Free the port or unset PORT_STRICT to auto-pick a nearby port."
            )
            raise OSError(msg)
        return preferred
    if _tcp_port_available(preferred):
        return preferred
    upper = preferred + _DEV_PORT_SEARCH_SPAN
    for port in range(preferred + 1, upper):
        if _tcp_port_available(port):
            logger.warning(
                "Port %d is in use; listening on %d instead. "
                "Set MIDDLEWARE_URL=http://localhost:%d for the Next.js BFF.",
                preferred,
                port,
                port,
            )
            return port
    raise RuntimeError(
        f"No free TCP port found between {preferred} and {upper - 1} inclusive"
    )


DEV_AGENT_ID = "dev-agent"
DEV_USER_ID = "dev-user"


def _load_graph_factory():
    """Load the graph factory from ``langgraph.json`` without static imports."""
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


def _build_base_components() -> tuple[AgentConfig, ToolRegistry, AgentFactsRegistry, Path]:
    """Build all non-async components (config, tools, identity registry).

    Separated from the graph/runtime so the async lifespan can enter the
    AsyncSqliteSaver context manager before compiling the graph.
    """
    os.chdir(str(AGENT_ROOT))
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

    if _GCP_EXECUTION_ENV:
        cache_dir = Path(os.environ.get("AGENT_OFFLOAD_DIR", "/tmp/agent_offload"))
    else:
        cache_dir = AGENT_ROOT / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    agent_facts_secret = os.environ.get(
        "AGENT_FACTS_SECRET", "dev-secret-do-not-use-in-production"
    )

    if _GCP_EXECUTION_ENV:
        from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry

        gcs_facts_bucket = os.environ.get("GCS_FACTS_BUCKET", "")
        if not gcs_facts_bucket:
            raise RuntimeError("GCS_FACTS_BUCKET is required when GCP_EXECUTION_ENV is set")
        agent_facts_registry = AgentFactsGcsRegistry(
            bucket_name=gcs_facts_bucket,
            secret=agent_facts_secret,
        )
    else:
        agent_facts_dir = cache_dir / "agent_facts"
        agent_facts_registry = AgentFactsRegistry(
            storage_dir=agent_facts_dir,
            secret=agent_facts_secret,
        )

        try:
            agent_facts_registry.get(DEV_AGENT_ID)
        except KeyError:
            agent_facts_registry.register(
                AgentFacts(
                    agent_id=DEV_AGENT_ID,
                    agent_name="Dev Agent",
                    owner=DEV_USER_ID,
                    version="1.0.0",
                    description="Local development agent",
                    capabilities=[Capability(name="delegate.subagent.*")],
                    status=IdentityStatus.ACTIVE,
                ),
                registered_by="dev-bootstrap",
            )

    return agent_config, tool_registry, agent_facts_registry, cache_dir


def build_dev_app() -> FastAPI:
    """Build the local dev FastAPI app with permissive auth."""
    agent_config, tool_registry, agent_facts_registry, cache_dir = _build_base_components()
    build_graph = _load_graph_factory()
    dev_identity = agent_facts_registry.get(DEV_AGENT_ID)
    dev_telemetry = _build_dev_telemetry_exporter()

    if _GCP_EXECUTION_ENV:
        from services.trace_sinks.gcs_sink import GcsTraceSink

        gcs_traces_bucket = os.environ.get("GCS_TRACES_BUCKET", "")
        if not gcs_traces_bucket:
            raise RuntimeError("GCS_TRACES_BUCKET is required when GCP_EXECUTION_ENV is set")
        trace_service = TraceService(sinks=[GcsTraceSink(gcs_traces_bucket)])
    else:
        trust_traces_dir = cache_dir / "trust_traces"
        trust_traces_dir.mkdir(parents=True, exist_ok=True)
        trace_service = TraceService(
            sinks=[JsonlFileTraceSink(trust_traces_dir / "records.jsonl")]
        )

    dev_relay = _build_dev_relay(dev_telemetry, cache_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Enter checkpointer context before the graph is compiled."""
        relay_task: asyncio.Task | None = None
        if dev_relay is not None:
            relay_task = asyncio.create_task(dev_relay.run_forever(interval_s=1.0))
            logger.info("BlackBox→Langfuse relay started (in-process)")

        try:
            if _GCP_EXECUTION_ENV:
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
                    app.state.dev_identity = dev_identity
                    app.state.telemetry_exporter = dev_telemetry
                    yield
            else:
                checkpointer = None
                try:
                    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                    async with AsyncSqliteSaver.from_conn_string(
                        str(cache_dir / "checkpoints.db")
                    ) as cp:
                        graph = build_graph(
                            agent_config=agent_config,
                            tool_registry=tool_registry,
                            cache_dir=cache_dir,
                            checkpointer=cp,
                            agent_facts_registry=agent_facts_registry,
                            interrupt_before_execute_tool=False,
                        )
                        app.state.runtime = LangGraphRuntime(
                            graph, trace_emit=trace_service.emit
                        )
                        app.state.dev_identity = dev_identity
                        app.state.telemetry_exporter = dev_telemetry
                        yield
                except ImportError:
                    logger.warning("AsyncSqliteSaver not available; running without checkpointer")
                    graph = build_graph(
                        agent_config=agent_config,
                        tool_registry=tool_registry,
                        cache_dir=cache_dir,
                        checkpointer=checkpointer,
                        agent_facts_registry=agent_facts_registry,
                        interrupt_before_execute_tool=False,
                    )
                    app.state.runtime = LangGraphRuntime(
                        graph, trace_emit=trace_service.emit
                    )
                    app.state.dev_identity = dev_identity
                    app.state.telemetry_exporter = dev_telemetry
                    yield
        finally:
            if relay_task is not None:
                dev_relay.stop()
                relay_task.cancel()
                try:
                    await relay_task
                except asyncio.CancelledError:
                    pass
                logger.info("BlackBox→Langfuse relay stopped")
            try:
                dev_telemetry.shutdown()
            except Exception:
                logger.debug("telemetry exporter shutdown swallowed", exc_info=True)

    app = FastAPI(title="Agent Dev Middleware", version="0.1.0-dev", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    threads_store: dict[str, dict] = {}

    def _require_bearer(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> AgentFacts:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        return request.app.state.dev_identity

    # ── healthz ────────────────────────────────────────────────────

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "profile": "dev", "runtime": "langgraph"}

    # ── POST /run/stream ───────────────────────────────────────────

    @app.post("/run/stream")
    async def run_stream(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        identity = _require_bearer(request, authorization)
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

        run_started_at = time.monotonic()

        exporter = dev_telemetry

        async def _generate() -> AsyncIterator[bytes]:
            # region agent log
            _ilist = []
            if isinstance(user_input, dict):
                _ilist = user_input.get("messages") or []
            debug_fc2601(
                hypothesis_id="H-thread",
                location="middleware.__main__:run_stream",
                message="generate_start",
                data={
                    "thread_tail": thread_id[-12:] if len(thread_id) >= 12 else thread_id,
                    "incoming_messages_len": len(_ilist),
                    "task_input_len": len(task_input),
                },
            )
            # endregion agent log
            run_id: str | None = None
            trace_id_seen: str | None = None
            errored = False
            run_finished_emitted = False
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

                    telemetry_bridge.emit_domain_event(
                        exporter,
                        domain_event,
                        subject=DEV_USER_ID,
                    )
                    if isinstance(domain_event, RunFinishedDomain):
                        run_finished_emitted = True

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
                if trace_id_seen is not None and not run_finished_emitted:
                    telemetry_bridge.emit_run_finished(
                        exporter,
                        trace_id=trace_id_seen,
                        run_id=run_id,
                        thread_id=thread_id,
                        duration_ms=duration_ms,
                        errored=errored,
                        subject=DEV_USER_ID,
                    )

        return StreamingResponse(
            _generate(),
            media_type="text/event-stream",
            headers=dict(PROXY_HEADERS),
        )

    # ── POST /run/cancel ───────────────────────────────────────────

    @app.post("/run/cancel")
    async def run_cancel(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        body = await request.json()
        run_id = body.get("run_id", "")
        await request.app.state.runtime.cancel(run_id)
        return {"cancelled": run_id}

    # ── threads ────────────────────────────────────────────────────

    @app.post("/threads")
    async def create_thread(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        body = await request.json()
        thread_id = f"t-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        thread = {
            "thread_id": thread_id,
            "user_id": body.get("user_id", DEV_USER_ID),
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        threads_store[thread_id] = thread
        return thread

    @app.get("/threads")
    async def list_threads(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        return {
            "threads": list(threads_store.values()),
            "nextCursor": None,
        }

    @app.get("/threads/{thread_id}")
    async def get_thread(
        request: Request,
        thread_id: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        thread = threads_store.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return thread

    return app


def main() -> None:
    preferred = int(os.environ.get("PORT", "8000"))
    port = _resolve_listen_port(preferred)
    logger.info("Starting dev middleware on port %d", port)
    uvicorn.run(
        "middleware.__main__:build_dev_app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        factory=True,
    )


if __name__ == "__main__":
    main()
