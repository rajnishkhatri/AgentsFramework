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
from typing import Any, AsyncIterator

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
from middleware.run_stream_context import build_run_stream_context
from middleware.understanding_edit import register_understanding_edit_route
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.ports.telemetry_exporter import TelemetryExporter
from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay
from middleware.composition import (
    AgentComponents,
    AgentRuntimeSettings,
    build_coach_components,
    build_components,
    build_runtime_graph,
)
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_AGENT_ID,
    SUBJECT_COACH_CAPABILITIES,
    register_subject_coach,
)
from services.trace_service import JsonlFileTraceSink, TraceService
from trust.models import AgentFacts

_GCP_EXECUTION_ENV = os.environ.get("GCP_EXECUTION_ENV")

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

    def flush(self) -> None:
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
        exporter = LangfuseCloudExporter(public_key=pk, secret_key=sk, host=host)
        logger.info("Langfuse telemetry enabled for dev")
        return exporter
    except Exception as exc:
        logger.warning("Langfuse exporter init failed: %s; dev telemetry disabled", exc)
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
    storage_dir = (
        Path(storage_dir_str)
        if storage_dir_str
        else (cache_dir / "black_box_recordings")
    )

    from middleware.ports.compliance_publisher import CompliancePublisher

    compliance_publisher = (
        exporter if isinstance(exporter, CompliancePublisher) else None
    )

    # Phase 4: curated view on by default; LANGFUSE_RELAY_CURATED=false restores
    # the audit-complete dual view (Option B).
    curated_view = (
        os.environ.get("LANGFUSE_RELAY_CURATED", "true").strip().lower() != "false"
    )

    return BlackBoxToTelemetryRelay(
        storage_dir=storage_dir,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
        curated_view=curated_view,
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


def _build_base_components() -> tuple[Any, Any, Any, Path, Any]:
    """Build all non-async components (compat shim → composition root)."""
    os.chdir(str(AGENT_ROOT))
    if _GCP_EXECUTION_ENV:
        os.environ.setdefault("AGENT_ENV", "prod")
        settings = AgentRuntimeSettings(agent_env="prod")
    else:
        os.environ.setdefault("AGENT_ENV", "local")
        settings = AgentRuntimeSettings(agent_env="local")
    components = build_components(settings, agent_root=AGENT_ROOT)
    return (
        components.agent_config,
        components.tool_registry,
        components.agent_facts_registry,
        components.cache_dir,
        components.goal_judge_config_reader,
    )


def _build_agent_components() -> AgentComponents:
    os.chdir(str(AGENT_ROOT))
    if _GCP_EXECUTION_ENV:
        os.environ.setdefault("AGENT_ENV", "prod")
        settings = AgentRuntimeSettings(agent_env="prod")
    else:
        os.environ.setdefault("AGENT_ENV", "local")
        settings = AgentRuntimeSettings(agent_env="local")
    return build_components(settings, agent_root=AGENT_ROOT)


def build_dev_app() -> FastAPI:
    """Build the local dev FastAPI app with permissive auth."""
    # Use the FULL composition-root components (not the slimmed 5-tuple): the
    # memory recall service AND the Phase-2 autocapture service are built by
    # build_components() and must be carried through to LangGraphRuntime, or the
    # dev runner silently drops autocapture (autocapture=None) regardless of the
    # MEMORY_AUTOCAPTURE_ENABLED flag.
    components = _build_agent_components()
    agent_config = components.agent_config
    tool_registry = components.tool_registry
    agent_facts_registry = components.agent_facts_registry
    cache_dir = components.cache_dir
    goal_judge_reader = components.goal_judge_config_reader
    build_graph = _load_graph_factory()
    dev_identity = agent_facts_registry.get(DEV_AGENT_ID)
    dev_telemetry = _build_dev_telemetry_exporter()
    from middleware.composition import _wire_eval_telemetry

    _wire_eval_telemetry(dev_telemetry)

    if _GCP_EXECUTION_ENV:
        from services.trace_sinks.gcs_sink import GcsTraceSink

        gcs_traces_bucket = os.environ.get("GCS_TRACES_BUCKET", "")
        if not gcs_traces_bucket:
            raise RuntimeError(
                "GCS_TRACES_BUCKET is required when GCP_EXECUTION_ENV is set"
            )
        trace_service = TraceService(sinks=[GcsTraceSink(gcs_traces_bucket)])
    else:
        trust_traces_dir = cache_dir / "trust_traces"
        trust_traces_dir.mkdir(parents=True, exist_ok=True)
        trace_service = TraceService(
            sinks=[JsonlFileTraceSink(trust_traces_dir / "records.jsonl")]
        )

    dev_relay = _build_dev_relay(dev_telemetry, cache_dir)
    if dev_relay is not None:
        # E7: forward the AgentFacts registry so compliance bundles carry
        # identity_cards (the registry is built in components, the relay in the
        # telemetry path — joined here at the composition root).
        dev_relay.set_agent_facts_registry(agent_facts_registry)

    def _install_runtimes(app: FastAPI, checkpointer: Any) -> None:
        """Compile the default + coach graphs on one checkpointer.

        1B-10 (ADR-0007/0012): the coach graph is selected per-request on
        body agent_id. Fail-SAFE for chat (a coach composition defect must
        not take the dev backend down) but fail-CLOSED for the coach:
        ``coach_runtime`` stays None and /run/stream 503s coach requests
        rather than ever serving them on the ungated default graph.
        """
        graph = build_runtime_graph(
            components,
            build_graph,
            checkpointer=checkpointer,
            interrupt_before_execute_tool=False,
        )
        app.state.runtime = LangGraphRuntime(
            graph,
            trace_emit=trace_service.emit,
            autocapture=components.memory_autocapture,
        )
        try:
            coach_graph = build_runtime_graph(
                build_coach_components(components),
                build_graph,
                checkpointer=checkpointer,
                interrupt_before_execute_tool=False,
                bound_capabilities=SUBJECT_COACH_CAPABILITIES,
            )
            app.state.coach_runtime = LangGraphRuntime(
                coach_graph,
                trace_emit=trace_service.emit,
                autocapture=components.memory_autocapture,
            )
            logger.info("Coach graph compiled (%s, shadow)", SUBJECT_COACH_AGENT_ID)
        except Exception:
            app.state.coach_runtime = None
            logger.exception(
                "coach graph build failed — coach requests will 503 "
                "(fail-closed, never the default graph)"
            )
        app.state.dev_identity = dev_identity
        app.state.telemetry_exporter = dev_telemetry

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Enter checkpointer context before the graph is compiled."""
        relay_task: asyncio.Task | None = None
        if dev_relay is not None:
            relay_task = asyncio.create_task(dev_relay.run_forever(interval_s=1.0))
            logger.info("BlackBox→Langfuse relay started (in-process)")

        try:
            if _GCP_EXECUTION_ENV:
                from agent_ui_adapter.adapters.runtime.postgres_saver import (
                    PostgresCheckpointer,
                )

                async with PostgresCheckpointer.from_env() as pg_cp:
                    _install_runtimes(app, pg_cp.saver)
                    yield
            else:
                try:
                    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                    async with AsyncSqliteSaver.from_conn_string(
                        str(cache_dir / "checkpoints.db")
                    ) as cp:
                        _install_runtimes(app, cp)
                        yield
                except ImportError:
                    logger.warning(
                        "AsyncSqliteSaver not available; running without checkpointer"
                    )
                    _install_runtimes(app, None)
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
        return {
            "status": "ok",
            "profile": "dev",
            "runtime": "langgraph",
            "goal_judge": goal_judge_reader.health_posture(),
        }

    # ── GET /models (model picker catalog) ─────────────────────────
    # Mirrors agent_ui_adapter.server.build_app's /models so the dev BFF
    # (default MIDDLEWARE_URL=:8000) can populate the picker. Reads the same
    # H2-canonical registry for the active MODEL_PROFILE_SET; exposes name+tier
    # ONLY (no pricing / litellm ids reach the client). Without this the picker
    # falls back to Auto-only against the dev backend.

    @app.get("/models")
    async def list_models(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        from services.llm_config import build_model_registry

        models, default_model = build_model_registry(
            os.environ.get("MODEL_PROFILE_SET", "openai")
        )
        return {
            "default": default_model,
            "models": [{"name": m.name, "tier": m.tier} for m in models],
        }

    # ── /agent/memory (Memory tab) ─────────────────────────────────
    # The BFF's HttpMemoryStore calls GET/POST/DELETE /agent/memory and expects
    # {"items": [...]}. The dev runner has no durable memory backend, so this is
    # an ephemeral in-process store (cleared on restart) — enough for the Memory
    # tab + run path not to 500. Items match the wire MemoryItem shape
    # (key/type/content/salience). Without this, /api/memory returns 500.
    memory_store: dict[str, dict] = {}

    @app.get("/agent/memory")
    async def list_memory(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        return {"items": list(memory_store.values())}

    @app.post("/agent/memory")
    async def add_memory(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        body = await request.json()
        key = str(body.get("key") or f"mem-{uuid.uuid4().hex[:12]}")
        item = {
            "key": key,
            "type": body.get("type"),
            "content": str(body.get("content", "")),
            "salience": body.get("salience"),
        }
        memory_store[key] = item
        return item

    @app.delete("/agent/memory/{key}")
    async def delete_memory(
        request: Request,
        key: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        memory_store.pop(key, None)
        return {"deleted": key}

    # ── POST /run/understanding/{thread_id} (Phase 4 edit seam) ─────

    def _verify_edit_bearer(authorization: str | None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        return "dev-user"

    register_understanding_edit_route(
        app,
        verify_bearer=_verify_edit_bearer,
        get_runtime=lambda: app.state.runtime,
        black_box_dir=cache_dir / "black_box_recordings",
    )

    # ── POST /run/stream ───────────────────────────────────────────

    # Registered lazily on the first coach request (mirrors app_prod.py);
    # the stored, signed card is what guard_input verifies per run (FR-2).
    _coach_card: list[AgentFacts] = []

    def _coach_run_identity(subject: str) -> AgentFacts:
        if not _coach_card:
            _coach_card.append(
                register_subject_coach(
                    agent_facts_registry, registered_by="dev-runner:coach_seed"
                )
            )
        return _coach_card[0].model_copy(update={"owner": subject})

    @app.post("/run/stream")
    async def run_stream(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        identity = _require_bearer(request, authorization)
        body = await request.json()
        # 1B-10: body agent_id selects the identity-bound coach graph.
        # Fail CLOSED when the coach runtime is unwired — never serve a
        # coach request on the ungated default graph (mirrors app_prod.py).
        if body.get("agent_id") == SUBJECT_COACH_AGENT_ID:
            runtime: LangGraphRuntime = getattr(
                request.app.state, "coach_runtime", None
            )
            if runtime is None:
                raise HTTPException(
                    status_code=503, detail="coach runtime not available"
                )
            # Seed then verify (R3) — mirrors app_prod.py (drift guard).
            # Stage-4 note: seeds with DEV_USER_ID (not claims.subject); that
            # is intentional for the permissive-auth local runner.
            identity = _coach_run_identity(DEV_USER_ID)
            if not agent_facts_registry.verify(SUBJECT_COACH_AGENT_ID):
                raise HTTPException(status_code=503, detail="coach identity unverified")
        else:
            runtime = request.app.state.runtime
        run_ctx = build_run_stream_context(
            body,
            identity=identity,
            subject=DEV_USER_ID,
        )
        if body.get("agent_id") == SUBJECT_COACH_AGENT_ID:
            logger.info(
                "coach_identity_verified subject=%s agent_id=%s verified=%s trace=%s",
                DEV_USER_ID,
                SUBJECT_COACH_AGENT_ID,
                True,
                run_ctx.thread_id,
            )
        if run_ctx.saturation is not None:
            logger.info(
                "goaljudge_saturation case=%s trace=%s thread=%s",
                run_ctx.saturation.case_id,
                run_ctx.saturation.trace_id,
                run_ctx.thread_id,
            )

        run_started_at = time.monotonic()

        exporter = dev_telemetry

        async def _generate() -> AsyncIterator[bytes]:
            run_id: str | None = None
            trace_id_seen: str | None = None
            errored = False
            run_finished_emitted = False
            try:
                async for domain_event in runtime.run(
                    thread_id=run_ctx.thread_id,
                    input={**run_ctx.user_input, "task_input": run_ctx.task_input},
                    identity=run_ctx.identity,
                ):
                    if trace_id_seen is None:
                        trace_id_seen = domain_event.trace_id
                    if run_id is None and hasattr(domain_event, "run_id"):
                        run_id = domain_event.run_id

                    telemetry_bridge.emit_domain_event(
                        exporter,
                        domain_event,
                        subject=run_ctx.telemetry_subject,
                        release_on_finish=False,
                    )
                    if isinstance(domain_event, RunFinishedDomain):
                        run_finished_emitted = True

                    for ag_ui_event in to_ag_ui(domain_event):
                        yield encode_event(ag_ui_event, event_id=uuid.uuid4().hex)
                yield SENTINEL_LINE
            except Exception as exc:
                errored = True
                logger.exception("stream error: %s", exc)
                yield encode_error(f"{type(exc).__name__}: {exc}", code="runtime_error")
                yield SENTINEL_LINE
            finally:
                duration_ms = int((time.monotonic() - run_started_at) * 1000)
                logger.info(
                    "stream_ended run_id=%s thread=%s trace=%s "
                    "duration_ms=%d errored=%s",
                    run_id,
                    run_ctx.thread_id,
                    trace_id_seen,
                    duration_ms,
                    errored,
                )
                # I6: teardown order is drain -> release_trace -> flush. The
                # relay tail MUST be drained before any step.N span is closed,
                # otherwise late BlackBox events recreate fresh spans and the
                # trace tree shape is nondeterministic across runs. Mirrors
                # middleware/app_prod.py.
                if dev_relay is not None and trace_id_seen is not None:
                    dev_relay.drain_workflow(trace_id_seen)

                if trace_id_seen is not None and not run_finished_emitted:
                    telemetry_bridge.emit_run_finished(
                        exporter,
                        trace_id=trace_id_seen,
                        run_id=run_id,
                        thread_id=run_ctx.thread_id,
                        duration_ms=duration_ms,
                        errored=errored,
                        subject=run_ctx.telemetry_subject,
                        release=False,
                    )

                if trace_id_seen is not None:
                    # Idempotent: closes step spans (if any remain) and flushes.
                    exporter.release_trace(trace_id_seen)
                exporter.flush()

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
    # Dev-only in-process thread store mirroring the prod Cloud SQL store's
    # CONTRACT so click-to-resume actually works locally:
    #   * honor the client-supplied thread_id (it MUST equal the checkpoint /
    #     resume id, or loadThreadTurns can never match the row it created),
    #   * derive `title` from metadata.first_message (sidebar label),
    #   * persist turns via POST /threads/{id}/messages as {role, content}
    #     pairs (the shape replayThread parses), and
    #   * support PATCH (rename) + DELETE (archive) the sidebar calls.
    # Ephemeral (cleared on restart) — enough for the chat history rail + resume.

    def _thread_title(metadata: dict, fallback: str = "New chat") -> str:
        first = str((metadata or {}).get("first_message", "")).strip()
        if not first:
            return fallback
        return first[:60]

    @app.post("/threads")
    async def create_thread(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        body = await request.json()
        # Use the client-supplied id when present (it is the resume/checkpoint
        # id); only mint one when absent. A repeat create for the same id is
        # idempotent (return the existing row) so a retry never wipes history.
        thread_id = str(body.get("thread_id") or f"t-{uuid.uuid4().hex[:12]}")
        existing = threads_store.get(thread_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC).isoformat()
        thread = {
            "thread_id": thread_id,
            "user_id": body.get("user_id", DEV_USER_ID),
            "title": _thread_title(body.get("metadata", {})),
            "messages": [],
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        }
        threads_store[thread_id] = thread
        return thread

    @app.get("/threads")
    async def list_threads(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        # Hide soft-deleted (archived) threads from the sidebar, newest first.
        live = [t for t in threads_store.values() if t.get("archived_at") is None]
        live.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
        return {"threads": live, "nextCursor": None}

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

    @app.post("/threads/{thread_id}/messages")
    async def append_turn(
        request: Request,
        thread_id: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        body = await request.json()
        # Create-on-append: the durable row may not exist yet if create raced or
        # was skipped — mirror the prod store's create-or-append so a turn is
        # never lost (the BFF treats 404 as a silent miss otherwise).
        thread = threads_store.get(thread_id)
        if thread is None:
            now = datetime.now(UTC).isoformat()
            thread = {
                "thread_id": thread_id,
                "user_id": DEV_USER_ID,
                "title": _thread_title(
                    {}, fallback=str(body.get("user", ""))[:60] or "New chat"
                ),
                "messages": [],
                "created_at": now,
                "updated_at": now,
                "archived_at": None,
            }
            threads_store[thread_id] = thread
        # Idempotent on turn_id: a retried POST must not double-append.
        turn_id = str(body.get("turn_id", ""))
        if turn_id and any(m.get("turn_id") == turn_id for m in thread["messages"]):
            return thread
        user_text = str(body.get("user", ""))
        assistant_text = str(body.get("assistant", ""))
        if user_text:
            thread["messages"].append(
                {"role": "user", "content": user_text, "turn_id": turn_id}
            )
        if assistant_text:
            thread["messages"].append(
                {"role": "assistant", "content": assistant_text, "turn_id": turn_id}
            )
        thread["updated_at"] = datetime.now(UTC).isoformat()
        return thread

    @app.patch("/threads/{thread_id}")
    async def rename_thread(
        request: Request,
        thread_id: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        thread = threads_store.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")
        body = await request.json()
        title = str(body.get("title", "")).strip()
        if title:
            thread["title"] = title[:60]
            thread["updated_at"] = datetime.now(UTC).isoformat()
        return thread

    @app.delete("/threads/{thread_id}")
    async def delete_thread(
        request: Request,
        thread_id: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(request, authorization)
        thread = threads_store.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")
        # Soft-delete (tombstone) to match the prod archived_at semantics.
        thread["archived_at"] = datetime.now(UTC).isoformat()
        return {"thread_id": thread_id, "archived": True}

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
