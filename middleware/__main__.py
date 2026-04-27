"""Local dev entry point: ``python -m middleware``

Starts a combined FastAPI app on port 8000 (the default MIDDLEWARE_URL
the frontend BFF forwards to) that:

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
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

AGENT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(AGENT_ROOT / ".env")

sys.path.insert(0, str(AGENT_ROOT))

from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
from agent_ui_adapter.transport.sse import (
    PROXY_HEADERS,
    SENTINEL_LINE,
    encode_error,
    encode_event,
)
from agent_ui_adapter.wire.agent_protocol import RunCreateRequest
from components.routing_config import RoutingConfig
from orchestration.react_loop import build_graph
from services.base_config import AgentConfig, ModelProfile
from services.governance.agent_facts_registry import AgentFactsRegistry
from services.observability import setup_logging
from services.tools.file_io import FileIOInput, execute_file_io
from services.tools.registry import ToolDefinition, ToolRegistry
from services.tools.shell import ShellToolInput, execute_shell
from services.tools.web_search import WebSearchInput, execute_web_search
from trust.enums import IdentityStatus
from trust.models import AgentFacts

logger = logging.getLogger("middleware.__main__")

DEV_AGENT_ID = "dev-agent"
DEV_USER_ID = "dev-user"


def _build_graph_and_runtime() -> tuple[LangGraphRuntime, AgentFacts]:
    """Wire the LangGraph ReAct graph + runtime (mirrors cli.py)."""
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

    tool_registry = ToolRegistry({
        "shell": ToolDefinition(
            executor=execute_shell, schema=ShellToolInput, cacheable=True
        ),
        "file_io": ToolDefinition(
            executor=execute_file_io, schema=FileIOInput, cacheable=True
        ),
        "web_search": ToolDefinition(
            executor=execute_web_search, schema=WebSearchInput, cacheable=False
        ),
    })

    cache_dir = AGENT_ROOT / "cache"
    cache_dir.mkdir(exist_ok=True)

    checkpointer = None
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        checkpointer = AsyncSqliteSaver.from_conn_string(
            str(cache_dir / "checkpoints.db")
        )
    except ImportError:
        logger.warning("AsyncSqliteSaver not available; running without checkpointer")

    agent_facts_secret = os.environ.get(
        "AGENT_FACTS_SECRET", "dev-secret-do-not-use-in-production"
    )
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
                status=IdentityStatus.ACTIVE,
            ),
            registered_by="dev-bootstrap",
        )

    graph = build_graph(
        agent_config=agent_config,
        routing_config=RoutingConfig(),
        tool_registry=tool_registry,
        cache_dir=cache_dir,
        checkpointer=checkpointer,
        agent_facts_registry=agent_facts_registry,
    )

    dev_identity = agent_facts_registry.get(DEV_AGENT_ID)
    runtime = LangGraphRuntime(graph)
    return runtime, dev_identity


def build_dev_app() -> FastAPI:
    """Build the local dev FastAPI app with permissive auth."""
    runtime, dev_identity = _build_graph_and_runtime()

    app = FastAPI(title="Agent Dev Middleware", version="0.1.0-dev")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    threads_store: dict[str, dict] = {}

    def _require_bearer(
        authorization: str | None = Header(default=None),
    ) -> AgentFacts:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        return dev_identity

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
        identity = _require_bearer(authorization)
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

        async def _generate() -> AsyncIterator[bytes]:
            run_id: str | None = None
            trace_id_seen: str | None = None
            errored = False
            try:
                async for domain_event in runtime.run(
                    thread_id=thread_id,
                    input=user_input if user_input else {"task_input": task_input},
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

    # ── POST /run/cancel ───────────────────────────────────────────

    @app.post("/run/cancel")
    async def run_cancel(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(authorization)
        body = await request.json()
        run_id = body.get("run_id", "")
        await runtime.cancel(run_id)
        return {"cancelled": run_id}

    # ── threads ────────────────────────────────────────────────────

    @app.post("/threads")
    async def create_thread(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(authorization)
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
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(authorization)
        return {
            "threads": list(threads_store.values()),
            "nextCursor": None,
        }

    @app.get("/threads/{thread_id}")
    async def get_thread(
        thread_id: str,
        authorization: str | None = Header(default=None),
    ):
        _require_bearer(authorization)
        thread = threads_store.get(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return thread

    return app


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    logger.info("Starting dev middleware on port %d", port)
    app = build_dev_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
