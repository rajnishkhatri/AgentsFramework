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
| on_chain_end (node)          | StateMutated (todos/plan_ref) |
| on_chain_end (evaluate node) | StepProgressed (ReAct lap)    |

Future enhancements (deferred): HITL ``request_approval`` wiring (S7).
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
    MemoryRecalled,
    ReasoningSummarized,
    RunFinishedDomain,
    RunStartedDomain,
    StateMutated,
    StepProgressed,
    TaskUnderstood,
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
        autocapture: Any = None,
    ) -> None:
        self._graph = graph
        self._trace_emit = trace_emit
        # Phase 2 typed background auto-capture (optional). When injected, the
        # post-run seam debounce-schedules a typed extraction after the stream
        # finishes — OUTSIDE the user-visible latency path. None (the default)
        # is byte-identical to the pre-Phase-2 runtime, so every existing
        # construction site and test is unaffected.
        self._autocapture = autocapture
        self._run_tasks: dict[str, asyncio.Task] = {}
        self._streamed_run_ids: set[str] = set()
        self._step_meter_count = 0
        self._live_tool_call_ids: set[str] = set()
        # task_understanding plan Phase 3: route re-runs every loop iteration
        # with the memoized artifact; dedupe card emission on the payload so
        # the card renders once and re-renders only on a real change
        # (e.g. a Phase 4 user edit).
        self._last_task_understanding: dict | None = None
        # memory_layer_wiring Phase 3: route re-runs every lap carrying the
        # memoized recall count; dedupe so the transparent-recall indicator
        # emits once per run (None = not yet emitted this run).
        self._last_recall_count: int | None = None

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
        graph_input = dict(input)
        saturation = graph_input.pop("_goaljudge_saturation", None)
        resume = bool(graph_input.pop("_resume", False))
        if resume:
            # task_understanding plan Phase 4: continue a paused thread from
            # its checkpoint. The trace_id is recovered, never re-minted
            # (F-R7: one trace per run), and the graph input is None — the
            # canonical LangGraph checkpoint-resume invocation.
            snapshot = await self._graph.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
            values = (
                getattr(snapshot, "values", None) if snapshot is not None else None
            )
            if not values:
                raise KeyError(f"no checkpoint for thread {thread_id!r}")
            if not getattr(snapshot, "next", ()):
                raise RuntimeError(
                    f"run already completed for thread {thread_id!r}; "
                    "nothing to resume"
                )
            workflow_id = str(values.get("workflow_id") or "")
            if not workflow_id:
                raise ValueError(
                    f"checkpoint for thread {thread_id!r} has no workflow_id; "
                    "it was not seeded by this runtime"
                )
            trace_id = workflow_id
            task_id = str(values.get("task_id") or workflow_id)
            eval_user_id = identity.owner
            run_id = uuid.uuid4().hex
        elif saturation is not None:
            trace_id = str(saturation["trace_id"])
            # ``task_id`` MUST be fresh per invocation even in saturation mode:
            # it scopes the planner's per-task tool-result count
            # (``select_planning_depth`` short-circuit). Reusing ``trace_id`` as
            # ``task_id`` makes every replay of the same case look like a
            # continuation, capping multi-subtask prompts at ``L0``/1 plan step.
            # See ``middleware/goaljudge_saturation_bridge.saturation_input_overlay``.
            task_id = str(saturation.get("task_id") or uuid.uuid4().hex)
            eval_user_id = str(saturation.get("user_id", identity.owner))
            run_id = trace_id
        else:
            trace_id = uuid.uuid4().hex
            run_id = uuid.uuid4().hex
            task_id = run_id
            eval_user_id = identity.owner

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
                    "task_id": task_id,
                    "user_id": eval_user_id,
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
        # In resume mode the checkpoint already holds them and the graph
        # input MUST be None (any dict would overwrite checkpoint channels).
        stream_input: dict[str, Any] | None
        if resume:
            stream_input = None
        else:
            stream_input = {
                **graph_input,
                "workflow_id": trace_id,
                "task_id": task_id,
                "registered_agent_id": identity.agent_id,
                # Phase 1 memory wiring: thread the run's subject into AgentState
                # so the recall (route_node) / store (run-end) seams and the T3
                # Send payload read it from state. This is identity.owner — the
                # same subject already on config["configurable"]["user_id"] and
                # the cross-user-leak guard (no memory op uses any other user_id).
                # Resume mode passes None (checkpoint holds prior channels); those
                # seams fall back to configurable["user_id"] there.
                "user_id": eval_user_id,
            }
        error: str | None = None
        self._streamed_run_ids = set()
        self._step_meter_count = 0
        self._live_tool_call_ids = set()
        self._last_task_understanding = None
        self._last_recall_count = None
        try:
            async for raw in self._graph.astream_events(
                stream_input, config=config, version="v2"
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

        # Phase 2 typed background auto-capture: after the stream finishes,
        # debounce-schedule a typed extraction over the run's window. This runs
        # OUTSIDE the user-visible latency path (the answer already streamed) and
        # never blocks or fails the run — the service swallows its own errors. On
        # an errored run there is no salient answer to remember, so skip. The
        # workflow_id == trace_id, so the proposal carriers land in the same
        # BlackBox trace the graph wrote (recorder injected at the root).
        if self._autocapture is not None and not error:
            await self._schedule_autocapture(
                thread_id=thread_id,
                user_id=eval_user_id,
                trace_id=trace_id,
                task_id=task_id,
            )

    async def _schedule_autocapture(
        self,
        *,
        thread_id: str,
        user_id: str,
        trace_id: str,
        task_id: str,
    ) -> None:
        """Read the run's window from the checkpoint and enqueue extraction.

        Best-effort: any failure here must never affect the (already-finished)
        run, so it is logged and swallowed.
        """
        try:
            snapshot = await self._graph.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
            values = getattr(snapshot, "values", None) or {}
            task_input = str(values.get("task_input", "")).strip()
            answer = str(values.get("last_final_answer", "")).strip()
            messages: list[dict[str, str]] = []
            if task_input:
                messages.append({"role": "user", "content": task_input})
            if answer:
                messages.append({"role": "assistant", "content": answer})
            if not messages:
                return
            self._autocapture.schedule(
                thread_id=thread_id,
                user_id=user_id,
                messages=messages,
                workflow_id=trace_id,
                task_id=task_id,
            )
        except Exception as exc:  # pragma: no cover - defensive, never raises up
            _logger.warning(
                "autocapture scheduling failed: %s: %s",
                type(exc).__name__,
                exc,
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

    async def update_task_understanding(
        self,
        *,
        thread_id: str,
        trace_id: str,
        restated_intent: str,
        success_conditions: list[str],
    ) -> tuple[dict, dict]:
        """Write a user-edited TaskUnderstanding to the thread checkpoint.

        task_understanding plan Phase 4 (§4.6): the soft-gate card's edit
        round-trip — validate the thread + trace echo, write the
        ``user_edited`` artifact via ``aupdate_state``, return ``(old, new)``
        so the caller can record PARAMETER_CHANGED with content hashes.

        Raises:
            KeyError: no checkpoint exists for ``thread_id``.
            ValueError: ``trace_id`` does not echo the run's workflow_id
                (F-R7 — the browser never mints a trace_id).
            RuntimeError: the run already completed (nothing to resume; a
                late edit is an explicit no-op error, plan §9.3).
        """
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        values = getattr(snapshot, "values", None) if snapshot is not None else None
        if not values:
            raise KeyError(f"no checkpoint for thread {thread_id!r}")
        workflow_id = str(values.get("workflow_id", ""))
        if trace_id != workflow_id:
            raise ValueError(
                f"trace_id mismatch: edit carries {trace_id!r}, "
                f"run is {workflow_id!r}"
            )
        if not getattr(snapshot, "next", ()):
            raise RuntimeError(
                f"run already completed for thread {thread_id!r}; "
                "late edits are not applied"
            )
        old = dict(values.get("task_understanding") or {})
        new = {
            **old,
            "restated_intent": restated_intent,
            "success_conditions": list(success_conditions),
            "source": "user_edited",
        }
        await self._graph.aupdate_state(config, {"task_understanding": new})
        return old, new

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
    def _extract_usage(output: object) -> tuple[int | None, int | None, str | None]:
        """Pull ``(tokens_in, tokens_out, model)`` from a LangChain message.

        Reads ``usage_metadata`` (``{input_tokens, output_tokens}``) and
        ``response_metadata`` (``model_name``). For ``on_llm_end`` the output is
        a dict carrying ``generations`` / ``llm_output`` instead of a message;
        handled best-effort. Missing data → ``None`` (the wire field stays None,
        the merged generation simply renders no usage). MUST NOT raise.
        """
        try:
            usage = getattr(output, "usage_metadata", None)
            resp = getattr(output, "response_metadata", None) or {}
            if usage is None and isinstance(output, dict):
                llm_output = output.get("llm_output") or {}
                usage = llm_output.get("usage") or llm_output.get("token_usage")
                resp = llm_output.get("model_name") and {"model_name": llm_output["model_name"]} or resp
            tokens_in = tokens_out = None
            if isinstance(usage, dict):
                tokens_in = usage.get("input_tokens") or usage.get("prompt_tokens")
                tokens_out = usage.get("output_tokens") or usage.get("completion_tokens")
            model = resp.get("model_name") if isinstance(resp, dict) else None
            return tokens_in, tokens_out, model
        except Exception:
            return None, None, None

    @staticmethod
    def _extract_llm_chunk_text(chunk: object) -> str:
        """Text from a chat chunk, or legacy ``GenerationChunk.text``."""
        text = LangGraphRuntime._extract_content(chunk)
        if text:
            return text
        raw_text = getattr(chunk, "text", None)
        return raw_text if isinstance(raw_text, str) else ""

    @staticmethod
    def _extract_input_messages(data: dict[str, Any]) -> str:
        """Serialize LangChain chat-model inputs for telemetry.

        LangChain's ``on_chat_model_start`` emits ``data["input"]`` as a flat
        list of message objects (``[SystemMessage, HumanMessage, ...]``). Some
        code paths / test fixtures instead pass ``{"messages": [...]}`` or a
        batched list-of-lists. All three shapes are handled so the prompt text
        reaches Langfuse.
        """
        inp = data.get("input")
        if isinstance(inp, dict):
            messages = inp.get("messages")
        else:
            messages = inp
        if not isinstance(messages, list) or not messages:
            return ""
        # Unwrap a single batched inner list: [[msg, msg]] -> [msg, msg].
        if len(messages) == 1 and isinstance(messages[0], list):
            messages = messages[0]
        parts: list[str] = []
        for msg in messages:
            if isinstance(msg, dict):
                role = str(msg.get("role") or msg.get("type") or "unknown")
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = LangGraphRuntime._extract_content(
                        type("_Msg", (), {"content": content})()
                    )
                else:
                    content = str(content)
            else:
                role = str(getattr(msg, "type", None) or getattr(msg, "role", "unknown"))
                content = LangGraphRuntime._extract_content(msg)
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)

    @staticmethod
    def _suppress_llm_event_for_node(raw: dict) -> bool:
        """Hide LLM traffic from internal graph nodes (e.g. input guardrail).

        LangGraph tags the emitting node in ``metadata.langgraph_node``. A key
        may be present with a null/empty value on some runs; those must **not**
        be treated as ``!= "call_llm"`` or we drop the main model stream.

        The F10 Tier-2 recap completion is additionally tagged
        ``reasoning_recap`` on its invoke config — suppress on the tag too so
        recap tokens never leak into the answer even if node metadata is
        absent.
        """
        if "reasoning_recap" in (raw.get("tags") or []):
            return True
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
            input_text = self._extract_input_messages(data)
            return [
                LLMMessageStarted(
                    trace_id=trace_id,
                    message_id=event_run_id,
                    input_text=input_text or None,
                )
            ]

        if ev_name == "on_chat_model_end":
            events: list[DomainEvent] = []
            already_streamed = event_run_id in self._streamed_run_ids
            output = data.get("output")
            content = self._extract_content(output) if output else ""
            # Tool-call-only turns emit NO text token (eval-UI F2): the
            # "Using tools: ..." preview used to land in the answer body
            # and froze into inadmissible captures (GJ-012/GJ-F-008).
            # Tool activity reaches the UI via ToolCallStarted events.
            if not already_streamed:
                if content:
                    events.append(LLMTokenEmitted(
                        trace_id=trace_id, message_id=event_run_id, delta=content
                    ))
            tokens_in, tokens_out, model = self._extract_usage(output)
            events.append(
                LLMMessageEnded(
                    trace_id=trace_id,
                    message_id=event_run_id,
                    output_text=content or None,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    model=model,
                )
            )
            self._streamed_run_ids.discard(event_run_id)
            return events

        if ev_name == "on_llm_end":
            events: list[DomainEvent] = []
            already_streamed = event_run_id in self._streamed_run_ids
            text = ""
            if not already_streamed:
                output = data.get("output")
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
            tokens_in, tokens_out, model = self._extract_usage(data.get("output"))
            events.append(
                LLMMessageEnded(
                    trace_id=trace_id,
                    message_id=event_run_id,
                    output_text=text or None,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    model=model,
                )
            )
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
            self._live_tool_call_ids.add(str(tool_call_id))
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

        if ev_name == "on_chain_end":
            return self._translate_chain_end(raw, data, trace_id)

        return []

    def _translate_chain_end(
        self, raw: dict, data: dict, trace_id: str
    ) -> list[DomainEvent]:
        """Graph-node completion → step meter + state-delta surface.

        - ``evaluate`` node end marks one completed ReAct lap →
          ``StepProgressed`` (wire: ``Custom name='step_meter'``).
        - Any node whose output carries ``todos``/``plan_ref`` →
          ``StateMutated`` with JSON-Patch ``replace`` ops (the loop
          replaces these channels wholesale, never patches items).
        - The compiled graph's own ``on_chain_end`` (name ``LangGraph``)
          restates the final state; suppressed to avoid a duplicate
          trailing delta.
        """
        node_name = raw.get("name", "")
        if node_name == "LangGraph":
            return []

        events: list[DomainEvent] = []
        output = data.get("output")

        if isinstance(output, dict):
            ops: list[dict] = []
            todos = output.get("todos")
            if isinstance(todos, list):
                ops.append({"op": "replace", "path": "/todos", "value": todos})
            plan_ref = output.get("plan_ref")
            if isinstance(plan_ref, str) and plan_ref:
                ops.append({"op": "replace", "path": "/plan_ref", "value": plan_ref})
            selected_model = output.get("selected_model")
            if isinstance(selected_model, str) and selected_model:
                ops.append({
                    "op": "replace",
                    "path": "/selected_model",
                    "value": selected_model,
                })
            if ops:
                events.append(StateMutated(trace_id=trace_id, delta=ops))

        if node_name == "execute_tool" and isinstance(output, dict):
            events.extend(
                self._synthesize_tool_events(output.get("tool_results"), trace_id)
            )

        if node_name == "route" and isinstance(output, dict):
            understanding = output.get("task_understanding")
            if (
                isinstance(understanding, dict)
                and isinstance(understanding.get("restated_intent"), str)
                and understanding.get("restated_intent")
                and isinstance(understanding.get("success_conditions"), list)
                and understanding.get("success_conditions")
                and understanding != self._last_task_understanding
            ):
                self._last_task_understanding = understanding
                try:
                    confidence = float(understanding.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                events.append(
                    TaskUnderstood(
                        trace_id=trace_id,
                        restated_intent=understanding["restated_intent"],
                        success_conditions=[
                            str(c) for c in understanding["success_conditions"]
                        ],
                        confidence=confidence,
                        source=str(understanding.get("source", "deterministic")),
                    )
                )

            # memory_layer_wiring Phase 3: surface the recall count for the
            # transparent-recall indicator. route_node writes recalled_memories_
            # count (metadata only, never content); emit once per run, deduped on
            # the value so a reflexion lap carrying the same memoized count does
            # not re-emit. Count 0 still emits the first time (the indicator is a
            # no-op at 0, but the event keeps the channel truthful for the run).
            raw_count = output.get("recalled_memories_count")
            if isinstance(raw_count, int) and raw_count != self._last_recall_count:
                self._last_recall_count = raw_count
                events.append(MemoryRecalled(trace_id=trace_id, count=raw_count))

        if node_name == "join" and isinstance(output, dict):
            # T3 fan-out: the join node synthesizes the merged worker_results
            # into ONE answer OUTSIDE the call_llm node -- either via an LLM
            # invoke (whose on_chat_model_* events are suppressed here because
            # langgraph_node != "call_llm") or via a deterministic floor (no LLM
            # call at all). Neither path emits a model-stream token, so the
            # join's last_final_answer is the only carrier of the user-visible
            # answer. Without this, the SSE stream delivers 0 text segments and
            # the UI renders the "completed without producing any output"
            # fallback (Stage B live defect). Emit the same Started/Token/Ended
            # trio call_llm produces so the answer renders as one text segment.
            joined = output.get("last_final_answer")
            if isinstance(joined, str) and joined.strip():
                join_msg_id = uuid.uuid4().hex
                events.append(
                    LLMMessageStarted(trace_id=trace_id, message_id=join_msg_id)
                )
                events.append(
                    LLMTokenEmitted(
                        trace_id=trace_id, message_id=join_msg_id, delta=joined
                    )
                )
                events.append(
                    LLMMessageEnded(
                        trace_id=trace_id,
                        message_id=join_msg_id,
                        output_text=joined,
                    )
                )

        if node_name == "reasoning_recap" and isinstance(output, dict):
            summary = output.get("reasoning_summary")
            if isinstance(summary, str) and summary.strip():
                events.append(
                    ReasoningSummarized(trace_id=trace_id, text=summary.strip())
                )

        if node_name == "evaluate":
            self._step_meter_count += 1
            step_name = ""
            if isinstance(output, dict):
                step_name = str(output.get("current_workflow_phase", "") or "")
            events.append(
                StepProgressed(
                    trace_id=trace_id,
                    step_count=self._step_meter_count,
                    step_name=step_name or "evaluate",
                )
            )

        return events

    def _synthesize_tool_events(
        self, tool_results: Any, trace_id: str
    ) -> list[DomainEvent]:
        """``execute_tool`` invokes tools via ``_execute_tools_impl`` directly,
        so LangGraph never fires ``on_tool_start``/``on_tool_end`` for them.
        The node's ``tool_results`` records are the only tool-activity signal
        (eval-UI F3: without this, tool cards never render against the real
        graph). Records whose call id already streamed live are skipped.
        """
        if not isinstance(tool_results, list):
            return []
        events: list[DomainEvent] = []
        for rec in tool_results:
            if not isinstance(rec, dict):
                continue
            record_id = str(rec.get("record_id") or "") or uuid.uuid4().hex
            bare_id = record_id.split(":", 1)[-1]
            if record_id in self._live_tool_call_ids or bare_id in self._live_tool_call_ids:
                continue
            try:
                args_json = json.dumps(
                    rec.get("tool_input", {}), default=str, sort_keys=True
                )
            except (TypeError, ValueError):
                args_json = str(rec.get("tool_input", {}))
            events.append(
                ToolCallStarted(
                    trace_id=trace_id,
                    tool_call_id=record_id,
                    tool_name=str(rec.get("tool_name", "")),
                    args_json=args_json,
                )
            )
            result_text = str(rec.get("tool_output", "") or "")
            if not rec.get("ok", True) and not result_text.startswith("Error:"):
                # "Error:" prefix is the registry convention the UI keys
                # errored tool cards on (ToolExecutionResult).
                error = str(rec.get("error", "") or "tool returned failure")
                result_text = (
                    f"Error: {error}" if not result_text
                    else f"{result_text}\nError: {error}"
                )
            events.append(
                ToolResultReceived(
                    trace_id=trace_id,
                    tool_call_id=record_id,
                    result=result_text,
                )
            )
        return events


__all__ = ["LangGraphRuntime"]
