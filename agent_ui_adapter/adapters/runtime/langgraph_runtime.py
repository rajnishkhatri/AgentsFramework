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

_logger = logging.getLogger("agent_ui_adapter.adapters.langgraph_runtime")


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

        config = {"configurable": {"thread_id": thread_id}}
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

    def _translate_event(self, raw: dict, trace_id: str) -> list[DomainEvent]:
        ev_name = raw.get("event", "")
        data = raw.get("data") or {}
        event_run_id = raw.get("run_id") or uuid.uuid4().hex

        if ev_name == "on_chat_model_stream":
            chunk = data.get("chunk")
            content = self._extract_content(chunk) if chunk else ""
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
                if content:
                    events.append(LLMTokenEmitted(
                        trace_id=trace_id, message_id=event_run_id, delta=content
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
