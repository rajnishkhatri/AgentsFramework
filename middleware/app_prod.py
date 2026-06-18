"""middleware/app_prod.py -- Production combined backend for Cloud Run.

Composes the middleware auth/ACL app (middleware/server.py) with the
agent_ui_adapter SSE surface (agent_ui_adapter/server.py) into a single
FastAPI application suitable for a combined Cloud Run deployment (Tier A).

Usage:
    uvicorn middleware.app_prod:build_combined_app --factory --host 0.0.0.0 --port 8080

Environment variables (all injected via Secret Manager on Cloud Run):
    GCP_EXECUTION_ENV       - "cloudrun" (triggers GCP adapter wiring)
    (profile)               - read by composition.py, not here (rule C5)
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

import asyncio
import importlib
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

AGENT_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "150")

sys.path.insert(0, str(AGENT_ROOT))

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.server import _ThreadStore, derive_thread_title
from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.transport.sse import (
    PROXY_HEADERS,
    SENTINEL_LINE,
    encode_error,
    encode_event,
)
from agent_ui_adapter.wire.agent_protocol import (
    MemoryCreateRequest,
    MemoryItem,
    MemoryListResponse,
    ThreadCreateRequest,
    ThreadListResponse,
    ThreadRenameRequest,
    ThreadState,
)
from agent_ui_adapter.wire.domain_events import RunFinishedDomain
from middleware import telemetry_bridge
from middleware.run_stream_context import build_run_stream_context
from middleware.composition import (
    AgentComponents,
    AgentRuntimeSettings,
    build_adapters,
    build_components,
    build_runtime_graph,
)
from middleware.server import build_middleware_app
from middleware.understanding_edit import register_understanding_edit_route
from services.trace_service import TraceService
from services.trace_sinks.gcs_sink import GcsTraceSink
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


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


logger = logging.getLogger("middleware.app_prod")


def _build_components() -> tuple[Any, Any, Any, Path, Any]:
    """Build non-async components for the production backend (compat shim)."""
    os.environ.setdefault("AGENT_ENV", "prod")
    settings = AgentRuntimeSettings(agent_env="prod")
    components = build_components(settings, agent_root=AGENT_ROOT)
    return (
        components.agent_config,
        components.tool_registry,
        components.agent_facts_registry,
        components.cache_dir,
        components.goal_judge_config_reader,
    )


def _build_agent_components() -> AgentComponents:
    """Full typed bag for internal wiring."""
    os.environ.setdefault("AGENT_ENV", "prod")
    settings = AgentRuntimeSettings(agent_env="prod")
    return build_components(settings, agent_root=AGENT_ROOT)


def build_combined_app() -> FastAPI:
    """Factory function for the combined production backend.

    Called by uvicorn with --factory flag:
        uvicorn middleware.app_prod:build_combined_app --factory
    """
    # _build_components() is the 5-tuple compat shim (existing tests patch it
    # to inject the registry/cache/reader fixtures); the graph-shaping members
    # (agent_config, tool_registry, settings) are intentionally discarded here
    # because the graph is built from the full bag below, not a partial rebuild.
    (
        _agent_config,
        _tool_registry,
        agent_facts_registry,
        cache_dir,
        goal_judge_reader,
    ) = _build_components()
    # The full typed bag is the SINGLE source the graph is built from. A
    # previous version hand-rebuilt a narrow AgentComponents here (copying
    # agent_config/tool_registry/.../settings) and passed THAT to
    # build_runtime_graph, silently dropping memory_service + memory_autocapture
    # (they fell back to the dataclass None default) -> the graph compiled
    # memory-blind, so recall/store/autocapture never fired in prod even with
    # MEMORY_ENABLED=true. Always hand build_runtime_graph the full bag; the
    # regression guard in tests/middleware/test_app_prod_memory_wiring.py pins
    # that the graph's components carry a non-None memory_service.
    components = _build_agent_components()
    memory_service = getattr(components, "memory_service", None)
    threads = _ThreadStore()
    build_graph = _load_graph_factory()

    gcs_traces_bucket = os.environ.get("GCS_TRACES_BUCKET", "")
    if not gcs_traces_bucket:
        raise RuntimeError("GCS_TRACES_BUCKET is required in production")
    trace_service = TraceService(sinks=[GcsTraceSink(gcs_traces_bucket)])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Enter async Postgres checkpointer before graph compilation.

        Also runs the BlackBox→Langfuse relay as an in-process asyncio task
        when ``BLACKBOX_RELAY_MODE=in_process`` (the Tier A default). This
        mirrors the dev entry point (``middleware/__main__.py``); without it
        BlackBox recordings written to tmpfs are never exported to Langfuse.
        """
        from agent_ui_adapter.adapters.runtime.postgres_saver import PostgresCheckpointer

        relay = adapters.black_box_relay
        relay_task: asyncio.Task | None = None
        if relay is not None:
            # E7: join the relay (adapters factory) with the AgentFacts registry
            # (components factory) so compliance bundles carry identity_cards.
            relay.set_agent_facts_registry(agent_facts_registry)
            relay_task = asyncio.create_task(relay.run_forever(interval_s=1.0))
            logger.info("BlackBox→Langfuse relay started (in-process)")

        try:
            try:
                goal_judge_reader.get()
            except Exception:
                logger.warning(
                    "goal_judge config cache-warm failed at startup",
                    exc_info=True,
                )
            async with PostgresCheckpointer.from_env() as pg_cp:
                graph = build_runtime_graph(
                    components,
                    build_graph,
                    checkpointer=pg_cp.saver,
                    interrupt_before_execute_tool=False,
                )
                app.state.runtime = LangGraphRuntime(
                    graph,
                    trace_emit=trace_service.emit,
                    autocapture=components.memory_autocapture,
                )
                logger.info("Production graph compiled, runtime ready")
                yield
        finally:
            if relay_task is not None and relay is not None:
                relay.stop()
                relay_task.cancel()
                try:
                    await relay_task
                except asyncio.CancelledError:
                    pass
                logger.info("BlackBox→Langfuse relay stopped (in-process)")
            try:
                adapters.telemetry_exporter.shutdown()
            except Exception:
                logger.debug("telemetry exporter shutdown swallowed", exc_info=True)

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
            "goal_judge": goal_judge_reader.health_posture(),
        }

    app.mount("/middleware", middleware_app)

    def _verify_edit_bearer(authorization: str | None) -> str:
        """JWT → WorkOS subject for the understanding edit route (401 on failure)."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization[len("Bearer "):].strip()
        try:
            return adapters.jwt_verifier.verify(token).subject
        except Exception as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid token: {exc}"
            ) from None

    def _resolve_identity(subject: str) -> AgentFacts:
        """Registry lookup with first-request auto-provision (shared path).

        Mirrors the /run/stream behavior so the thread/memory CRUD routes use
        one identity contract: an unknown subject is provisioned, not rejected.
        """
        try:
            return agent_facts_registry.get(subject)
        except KeyError:
            identity = agent_facts_registry.register(
                AgentFacts(
                    agent_id=subject,
                    agent_name=subject,
                    owner=subject,
                    version="1.0.0",
                    description="Auto-provisioned on first authenticated request",
                    capabilities=[Capability(name="delegate.subagent.*")],
                    status=IdentityStatus.ACTIVE,
                ),
                registered_by="app_prod:auto_provision",
            )
            logger.info("auto_provisioned_identity subject=%s", subject)
            return identity

    def _bearer_identity(
        authorization: str | None = Header(default=None),
    ) -> AgentFacts:
        """FastAPI dependency: verify bearer → resolve identity (401 on failure).

        Used by the /agent/threads + /agent/memory CRUD routes. Every CRUD
        handler scopes to ``identity.owner`` (the verified subject's owner),
        NEVER a client-supplied user_id — this IS the cross-user-leak guard.
        """
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization[len("Bearer "):].strip()
        try:
            claims = adapters.jwt_verifier.verify(token)
        except Exception as exc:
            raise HTTPException(
                status_code=401, detail=f"invalid token: {exc}"
            ) from None
        return _resolve_identity(claims.subject)

    def _require_memory():
        """Return the wired LongTermMemoryService or 503 if memory is off.

        503 (not 500) keeps the memory panel degrading to "unavailable" cleanly
        when MEMORY is unwired in a given deployment.
        """
        if memory_service is None:
            raise HTTPException(
                status_code=503, detail="memory service not available"
            )
        return memory_service

    # ── Thread CRUD (Phase 3 sidebar surface) ─────────────────────────
    # The BFF proxies these for the chat-history sidebar. Owner-scoped;
    # archived threads are soft-deleted (hidden from list/get). In-memory
    # store for now — the persistent ThreadStore is the BFF's concern (F-R9).

    @app.get("/agent/threads", response_model=ThreadListResponse)
    async def list_threads(
        cursor: str | None = None,
        limit: int = 20,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> ThreadListResponse:
        bounded = max(1, min(100, limit))
        page, next_cursor = threads.list(
            identity.owner, cursor=cursor, limit=bounded
        )
        return ThreadListResponse(threads=page, next_cursor=next_cursor)

    @app.post("/agent/threads", response_model=ThreadState)
    async def create_thread(
        body: ThreadCreateRequest,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> ThreadState:
        # Scope to the verified owner — ignore body.user_id for storage key.
        return threads.create(user_id=identity.owner, metadata=body.metadata)

    @app.get("/agent/threads/{thread_id}", response_model=ThreadState)
    async def get_thread(
        thread_id: str,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> ThreadState:
        state = threads.get(thread_id, owner=identity.owner)
        if state is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return state

    @app.patch("/agent/threads/{thread_id}", response_model=ThreadState)
    async def rename_thread(
        thread_id: str,
        body: ThreadRenameRequest,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> ThreadState:
        renamed = threads.rename(thread_id, identity.owner, body.title)
        if renamed is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return renamed

    @app.delete("/agent/threads/{thread_id}")
    async def archive_thread(
        thread_id: str,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> dict:
        if not threads.archive(thread_id, identity.owner):
            raise HTTPException(status_code=404, detail="thread not found")
        return {"archived": thread_id}

    # ── Memory CRUD (Phase 3 memory panel) ────────────────────────────
    # Every route scopes to identity.owner — never a client-supplied user_id
    # (cross-user-leak guard). Content is returned to its OWNER by design (the
    # panel shows the owner their own memories); it is never logged.

    @app.get("/agent/memory", response_model=MemoryListResponse)
    async def list_memory(
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> MemoryListResponse:
        memory = _require_memory()
        records = memory.search(identity.owner, "", limit=500)
        items = [
            MemoryItem(
                key=r.key,
                type=r.metadata.get("type"),
                content=str(r.payload.get("text", "")),
                salience=r.metadata.get("salience"),
            )
            for r in records
        ]
        return MemoryListResponse(items=items)

    @app.post("/agent/memory", response_model=MemoryItem)
    async def create_memory(
        body: MemoryCreateRequest,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> MemoryItem:
        memory = _require_memory()
        key = body.key or uuid.uuid4().hex
        memory.store(
            identity.owner,
            key,
            {"text": body.content},
            metadata={"type": body.type, "source": "user_added"},
        )
        return MemoryItem(
            key=key, type=body.type, content=body.content, salience=None
        )

    @app.delete("/agent/memory/{key}")
    async def delete_memory(
        key: str,
        identity: AgentFacts = Depends(_bearer_identity),
    ) -> dict:
        memory = _require_memory()
        if not memory.forget(identity.owner, key):
            raise HTTPException(status_code=404, detail="memory not found")
        return {"deleted": key}

    # task_understanding plan Phase 4: soft-gate card edit seam. The client
    # pauses the stream, POSTs the corrected artifact here, then resumes by
    # re-invoking /run/stream with the same thread_id.
    register_understanding_edit_route(
        app,
        verify_bearer=_verify_edit_bearer,
        get_runtime=lambda: app.state.runtime,
        black_box_dir=cache_dir / "black_box_recordings",
    )

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

        identity = _resolve_identity(claims.subject)

        run_ctx = build_run_stream_context(
            body,
            identity=identity,
            subject=claims.subject,
        )
        if run_ctx.saturation is not None:
            logger.info(
                "goaljudge_saturation case=%s trace=%s thread=%s",
                run_ctx.saturation.case_id,
                run_ctx.saturation.trace_id,
                run_ctx.thread_id,
            )

        run_started_at = time.monotonic()

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
                        adapters.telemetry_exporter,
                        domain_event,
                        subject=run_ctx.telemetry_subject,
                        release_on_finish=False,
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
                    run_id, run_ctx.thread_id, trace_id_seen, duration_ms, errored,
                )
                # I6: teardown order is drain -> release_trace -> flush. The
                # relay tail MUST be drained before any step.N span is closed,
                # otherwise late BlackBox events recreate fresh spans and the
                # trace tree shape is nondeterministic across runs.
                relay = adapters.black_box_relay
                if relay is not None and trace_id_seen is not None:
                    relay.drain_workflow(trace_id_seen)

                if trace_id_seen is not None and not run_finished_emitted:
                    telemetry_bridge.emit_run_finished(
                        adapters.telemetry_exporter,
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
                    adapters.telemetry_exporter.release_trace(trace_id_seen)
                adapters.telemetry_exporter.flush()

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
