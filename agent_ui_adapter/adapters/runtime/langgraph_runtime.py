"""LangGraphRuntime — production ``AgentRuntime`` wrapping ``orchestration.react_loop``.

Per AGENT_UI_ADAPTER_SPRINTS.md US-3.3.

Translation contract:

- A LangGraph compiled app exposes ``astream_events(input, config, version='v2')``
  yielding dicts with shape ``{"event": <name>, "data": {...}, "name": str, "run_id": str}``.
- This adapter consumes that stream and emits ``agent_ui_adapter.wire.domain_events``
  values WITHOUT exposing any LangGraph types past its own boundary.
- Every emitted event carries the same ``trace_id`` for the run (plan §4.3 Option B).
- Exceptions raised by the graph are caught and translated to a
  ``RunFinishedDomain(error=<message>)`` so the wire boundary never sees a raw stack.

LangChain event-name mapping (subset; v1 wire surface):

| LangGraph event              | Domain event                  |
|------------------------------|-------------------------------|
| on_chat_model_stream         | LLMTokenEmitted (delta=chunk) |
| on_chat_model_start          | LLMMessageStarted             |
| on_chat_model_end            | LLMMessageEnded               |
| on_tool_start                | ToolCallStarted               |
| on_tool_end                  | ToolResultReceived            |

Future enhancements (deferred): JSON Patch translation for state mutations,
HITL ``request_approval`` wiring (S7).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable, Protocol

from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import (
    DomainEvent,
    LLMMessageEnded,
    LLMMessageStarted,
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
    ToolCallStarted,
    ToolResultReceived,
)
from trust.models import AgentFacts, TrustTraceRecord

# LangGraph’s config merge differs from LangChain’s; normalize here so Pregel sees
# the requested ``recursion_limit`` after ``Runnable.astream_events`` runs.
from langgraph.utils.config import ensure_config as _lg_ensure_config

_logger = logging.getLogger("agent_ui_adapter.adapters.langgraph_runtime")

# LangGraph defaults recursion_limit to 25 (graph node transitions). Each ReAct lap
# (guard/route/call_llm/execute_tool/evaluate) consumes several transitions, so
# web_search-heavy runs otherwise raise GraphRecursionError before synthesis.
_DEFAULT_RECURSION_LIMIT = 150


class _CompiledGraphLike(Protocol):
    """Structural shape of a LangGraph compiled app (subset)."""

    def astream_events(
        self,
        input: Any,
        config: dict | None = ...,
        version: str = ...,
    ) -> AsyncIterator[dict]: ...

    async def aget_state(self, config: dict) -> Any: ...


class LangGraphRuntime:
    """Production ``AgentRuntime`` wrapping a LangGraph compiled app."""

    def __init__(
        self,
        graph: _CompiledGraphLike,
        *,
        trace_emit: Callable[[TrustTraceRecord], None] | None = None,
    ) -> None:
        self._graph = graph
        self._trace_emit = trace_emit
        self._run_tasks: dict[str, asyncio.Task] = {}
        self._streamed_run_ids: set[str] = set()

    def _emit_trace(
        self,
        *,
        trace_id: str,
        agent_id: str,
        event_type: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self._trace_emit is None:
            return
        record = TrustTraceRecord(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            trace_id=trace_id,
            agent_id=agent_id,
            layer="L4",
            event_type=event_type,
            details=details or {},
            outcome=outcome,
        )
        try:
            self._trace_emit(record)
        except Exception as exc:
            _logger.error("trace_emit failed: %s: %s", type(exc).__name__, exc)

    async def run(
        self,
        thread_id: str,
        input: dict[str, Any],
        identity: AgentFacts,
    ) -> AsyncIterator[DomainEvent]:
        trace_id = uuid.uuid4().hex
        run_id = uuid.uuid4().hex

        self._emit_trace(
            trace_id=trace_id,
            agent_id=identity.agent_id,
            event_type="run_started",
            outcome="pass",
            details={"run_id": run_id, "thread_id": thread_id},
        )

        yield RunStartedDomain(
            trace_id=trace_id, run_id=run_id, thread_id=thread_id
        )

        config = _lg_ensure_config(
            None,
            {
                "recursion_limit": _DEFAULT_RECURSION_LIMIT,
                "configurable": {
                    "thread_id": thread_id,
                    "trace_id": trace_id,
                    "user_id": identity.owner,
                    "registered_agent_id": identity.agent_id,
                },
            },
        )
        _logger.info(
            "astream_events using recursion_limit=%s (thread_tail=%s)",
            config.get("recursion_limit"),
            thread_id[-12:] if len(thread_id) >= 12 else thread_id,
        )
        # Seed correlation keys into state so graph nodes can key black-box
        # recordings and phase logs under the same trace_id that SSE emits.
        input = {
            **input,
            "workflow_id": trace_id,
            "task_id": run_id,
            "registered_agent_id": identity.agent_id,
        }
        error: str | None = None
        self._streamed_run_ids = set()
        try:
            async for raw in self._graph.astream_events(
                input, config=config, version="v2"
            ):
                for event in self._translate_event(raw, trace_id):
                    yield event
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        self._emit_trace(
            trace_id=trace_id,
            agent_id=identity.agent_id,
            event_type="run_finished",
            outcome="fail" if error else "pass",
            details={"run_id": run_id, "thread_id": thread_id, "error": error},
        )

        yield RunFinishedDomain(
            trace_id=trace_id,
            run_id=run_id,
            thread_id=thread_id,
            error=error,
        )

    async def cancel(self, run_id: str) -> None:
        task = self._run_tasks.pop(run_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def get_state(self, thread_id: str) -> ThreadState:
        from datetime import UTC, datetime

        config = {"configurable": {"thread_id": thread_id}}
        try:
            snapshot = await self._graph.aget_state(config)
        except Exception:
            snapshot = None

        now = datetime.now(UTC)
        messages: list[dict] = []
        if snapshot is not None:
            values = getattr(snapshot, "values", None) or snapshot
            if isinstance(values, dict):
                raw_msgs = values.get("messages", [])
                for m in raw_msgs:
                    if isinstance(m, dict):
                        messages.append(m)
                    else:
                        messages.append(
                            {
                                "role": getattr(m, "role", "assistant"),
                                "content": getattr(m, "content", ""),
                            }
                        )

        return ThreadState(
            thread_id=thread_id,
            user_id="langgraph",
            messages=messages,
            created_at=now,
            updated_at=now,
        )

    # ── translation ───────────────────────────────────────────────────

    @staticmethod
    def _extract_content(obj: object) -> str:
        """Extract text content from a LangChain message or chunk.

        Handles both string content and list-of-blocks content (Anthropic
        style: ``[{"type": "text", "text": "..."}]``).
        """
        content = getattr(obj, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "".join(parts)
        return ""

    @staticmethod
    def _extract_llm_chunk_text(chunk: object) -> str:
        """Text from a chat chunk, or legacy ``GenerationChunk.text``."""
        text = LangGraphRuntime._extract_content(chunk)
        if text:
            return text
        raw_text = getattr(chunk, "text", None)
        return raw_text if isinstance(raw_text, str) else ""

    @staticmethod
    def _tool_calls_preview(obj: object) -> str:
        """When the model returns only tool calls, surface a short line for the UI."""
        tool_calls = getattr(obj, "tool_calls", None)
        if not tool_calls:
            return ""
        names: list[str] = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                name = tc.get("name", "")
            else:
                name = getattr(tc, "name", "") or ""
            if isinstance(name, str) and name:
                names.append(name)
        if not names:
            return ""
        return "Using tools: " + ", ".join(names) + "…"

    @staticmethod
    def _suppress_llm_event_for_node(raw: dict) -> bool:
        """Hide LLM traffic from internal graph nodes (e.g. input guardrail).

        LangGraph tags the emitting node in ``metadata.langgraph_node``. A key
        may be present with a null/empty value on some runs; those must **not**
        be treated as ``!= "call_llm"`` or we drop the main model stream.
        """
        meta = raw.get("metadata") or {}
        node = meta.get("langgraph_node")
        if not isinstance(node, str) or not node.strip():
            return False
        return node != "call_llm"

    def _translate_event(self, raw: dict, trace_id: str) -> list[DomainEvent]:
        ev_name = raw.get("event", "")
        data = raw.get("data") or {}
        event_run_id = raw.get("run_id") or uuid.uuid4().hex

        # Only surface LLM events from the main call_llm node. Internal nodes
        # (guardrails, routers) also invoke LLMs but their outputs must not be
        # rendered as user-visible messages. LangGraph v2 events carry the
        # originating node name in metadata.langgraph_node.
        #
        # When metadata lacks a usable langgraph_node (unit-test fakes, older
        # streams, or null placeholders), pass events through unchanged.
        if ev_name in (
            "on_chat_model_start",
            "on_chat_model_stream",
            "on_chat_model_end",
            "on_llm_stream",
            "on_llm_end",
        ):
            if self._suppress_llm_event_for_node(raw):
                return []

        if ev_name == "on_chat_model_stream":
            chunk = data.get("chunk")
            content = self._extract_llm_chunk_text(chunk) if chunk else ""
            if content:
                self._streamed_run_ids.add(event_run_id)
                return [LLMTokenEmitted(
                    trace_id=trace_id, message_id=event_run_id, delta=content
                )]
            return []

        if ev_name == "on_llm_stream":
            chunk = data.get("chunk")
            content = self._extract_llm_chunk_text(chunk) if chunk else ""
            if content:
                self._streamed_run_ids.add(event_run_id)
                return [LLMTokenEmitted(
                    trace_id=trace_id, message_id=event_run_id, delta=content
                )]
            return []

        if ev_name == "on_chat_model_start":
            return [LLMMessageStarted(trace_id=trace_id, message_id=event_run_id)]

        if ev_name == "on_chat_model_end":
            events: list[DomainEvent] = []
            already_streamed = event_run_id in self._streamed_run_ids
            if not already_streamed:
                output = data.get("output")
                content = self._extract_content(output) if output else ""
                if not content and output:
                    content = self._tool_calls_preview(output)
                if content:
                    events.append(LLMTokenEmitted(
                        trace_id=trace_id, message_id=event_run_id, delta=content
                    ))
            events.append(LLMMessageEnded(trace_id=trace_id, message_id=event_run_id))
            self._streamed_run_ids.discard(event_run_id)
            return events

        if ev_name == "on_llm_end":
            events: list[DomainEvent] = []
            already_streamed = event_run_id in self._streamed_run_ids
            if not already_streamed:
                output = data.get("output")
                text = ""
                if isinstance(output, dict):
                    gens = output.get("generations") or []
                    if gens and gens[0]:
                        g0 = gens[0][0]
                        if isinstance(g0, dict):
                            text = str(g0.get("text", "") or "")
                        else:
                            text = str(getattr(g0, "text", None) or "")
                elif output is not None:
                    text = str(output)
                if text:
                    events.append(LLMTokenEmitted(
                        trace_id=trace_id, message_id=event_run_id, delta=text
                    ))
            events.append(LLMMessageEnded(trace_id=trace_id, message_id=event_run_id))
            self._streamed_run_ids.discard(event_run_id)
            return events

        if ev_name == "on_tool_start":
            tool_call_id = (
                data.get("tool_call_id")
                or raw.get("id")
                or event_run_id
            )
            args_raw = data.get("input", {})
            try:
                args_json = json.dumps(args_raw, default=str, sort_keys=True)
            except (TypeError, ValueError):
                args_json = str(args_raw)
            return [ToolCallStarted(
                trace_id=trace_id,
                tool_call_id=tool_call_id,
                tool_name=raw.get("name", ""),
                args_json=args_json,
            )]

        if ev_name == "on_tool_end":
            tool_call_id = (
                data.get("tool_call_id")
                or raw.get("id")
                or event_run_id
            )
            output = data.get("output", "")
            return [ToolResultReceived(
                trace_id=trace_id,
                tool_call_id=tool_call_id,
                result=str(output),
            )]

        return []


__all__ = ["LangGraphRuntime"]
