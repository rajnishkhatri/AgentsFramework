"""Pydantic-AI style ReAct prototype (STORY-414).

A minimal, framework-agnostic ReAct loop that mirrors
``orchestration/react_loop.py`` without depending on LangGraph or
LangChain. Built so the project has a known-good fallback when the
primary LangGraph topology needs replacing (PLAN_v2.md Phase 4 contingency).

Key properties
--------------
* State is a Pydantic ``BaseModel`` (not a ``TypedDict``) so it can be
  serialized to disk for the checkpoint/restore contract.
* LLM calls go through raw ``litellm.completion()``; we never import
  ``ChatLiteLLM`` or ``langchain``.
* Routing reuses ``components/router.py`` and outcome classification
  reuses ``components/evaluator.py`` so the fallback obeys the same
  rules as the production loop.
* Architecture: lives in ``meta/`` and imports only from
  ``components/``, ``services/``, and ``trust/`` -- AP8 (no
  orchestration imports). Architecture tests in
  ``tests/architecture/test_dependency_rules.py`` enforce this.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from components.evaluator import (
    build_step_result,
    classify_outcome,
)
from components.router import select_model
from components.routing_config import RoutingConfig
from components.schemas import StepResult, TaskResult
from services.base_config import AgentConfig, ModelProfile

logger = logging.getLogger("meta.fallback_prototype")


class FallbackMessage(BaseModel):
    """One conversation turn carried in the loop's state."""

    role: str
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None


class FallbackState(BaseModel):
    """Pydantic state for :class:`FallbackReactLoop`.

    The full state must be JSON-serializable end-to-end so the
    checkpoint contract works without custom hooks.
    """

    task_id: str
    task_input: str
    messages: list[FallbackMessage] = Field(default_factory=list)
    step_count: int = 0
    selected_model: str = ""
    routing_reason: str = ""
    last_outcome: str = ""
    last_error_type: str = ""
    consecutive_errors: int = 0
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    model_history: list[dict[str, Any]] = Field(default_factory=list)
    step_results: list[StepResult] = Field(default_factory=list)
    final_answer: str | None = None
    status: str = "running"


class FallbackReactLoop:
    """Single-task ReAct loop without LangGraph.

    The loop's public surface is :meth:`run`. The remaining methods
    (``_invoke_completion``, ``_execute_tool``, ``_checkpoint``,
    ``_restore_checkpoint``) are protected so subclasses and L2 tests
    can override them without touching the loop body.
    """

    DEFAULT_FINAL_ANSWER_TAG = "FINAL ANSWER:"

    def __init__(
        self,
        agent_config: AgentConfig,
        routing_config: RoutingConfig,
        *,
        tool_executor: Callable[[str, dict[str, Any]], str] | None = None,
        system_prompt: str | None = None,
        checkpoint_dir: Path | str | None = None,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._agent_config = agent_config
        self._routing_config = routing_config
        self._tool_executor = tool_executor or _default_tool_executor
        self._system_prompt = (
            system_prompt
            if system_prompt is not None
            else _load_default_system_prompt()
        )
        self._checkpoint_dir = (
            Path(checkpoint_dir) if checkpoint_dir is not None else None
        )
        self._completion_fn = completion_fn  # injectable for L2 tests

    # ── checkpoint protocol ────────────────────────────────────────

    def checkpoint(self, state: FallbackState) -> str:
        """Serialize ``state`` to JSON and (optionally) persist to disk.

        Always returns the JSON string so the caller can hold an
        in-memory fallback even when no ``checkpoint_dir`` was set.
        """
        payload = state.model_dump_json()
        if self._checkpoint_dir is not None:
            self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
            path = (
                self._checkpoint_dir
                / f"{state.task_id}-step{state.step_count}.json"
            )
            path.write_text(payload)
        return payload

    @staticmethod
    def restore(payload: str) -> FallbackState:
        """Deserialize a checkpoint payload produced by :meth:`checkpoint`."""
        return FallbackState.model_validate_json(payload)

    # ── loop body ──────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        *,
        user_id: str = "fallback-user",
        task_id: str | None = None,
    ) -> TaskResult:
        """Execute the ReAct loop until terminal and return a TaskResult."""
        state = FallbackState(
            task_id=task_id or str(uuid.uuid4()),
            task_input=task,
            messages=[
                FallbackMessage(role="system", content=self._system_prompt),
                FallbackMessage(role="user", content=task),
            ],
        )

        start = time.time()
        while not self._is_terminal(state):
            checkpoint_payload = self.checkpoint(state)

            profile, reason = select_model(
                step_count=state.step_count,
                consecutive_errors=state.consecutive_errors,
                last_error_type=state.last_error_type,
                total_cost_usd=state.total_cost_usd,
                model_history=state.model_history,
                agent_config=self._agent_config,
                routing_config=self._routing_config,
            )
            state.selected_model = profile.name
            state.routing_reason = reason

            try:
                response = await self._invoke_completion(profile, state)
            except Exception as exc:
                logger.warning(
                    "LLM completion failed for task=%s step=%d: %s",
                    state.task_id, state.step_count, exc,
                )
                state = self.restore(checkpoint_payload)
                state.consecutive_errors += 1
                state.last_outcome = "failure"
                state.last_error_type = "model_error"
                state.step_count += 1
                continue

            await self._record_eval(profile, response, state, user_id=user_id)

            assistant_msg, tool_call = _extract_assistant_message(response)
            state.messages.append(assistant_msg)

            if tool_call is not None:
                # Re-checkpoint immediately before tool execution so a
                # crashing tool can't poison ``messages`` mid-step.
                tool_checkpoint = self.checkpoint(state)
                tool_name = tool_call["name"]
                tool_args = tool_call.get("arguments", {})
                try:
                    tool_output = self._tool_executor(tool_name, tool_args)
                except Exception as exc:
                    logger.warning(
                        "Tool %s failed for task=%s: %s",
                        tool_name, state.task_id, exc,
                    )
                    state = self.restore(tool_checkpoint)
                    failure_step = build_step_result(
                        step_id=state.step_count,
                        action="tool_call",
                        model_used=profile.name,
                        routing_reason=reason,
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd=0.0,
                        latency_ms=0.0,
                        outcome="failure",
                        error_record=None,
                        reasoning=f"tool {tool_name} raised: {exc}"[:200],
                        tool_name=tool_name,
                        tool_input=tool_args,
                    )
                    # Stamp the error_type explicitly because we don't have
                    # a structured ErrorRecord at this layer.
                    failure_step.error_type = "tool_error"
                    state.step_results.append(failure_step)
                    state.consecutive_errors += 1
                    state.last_outcome = "failure"
                    state.last_error_type = "tool_error"
                    state.step_count += 1
                    continue

                state.messages.append(FallbackMessage(
                    role="tool",
                    content=str(tool_output),
                    tool_call_id=tool_call.get("id"),
                ))
                outcome, error_record = "success", None
            else:
                final = _extract_final_answer(
                    assistant_msg.content, self.DEFAULT_FINAL_ANSWER_TAG
                )
                if final is not None:
                    state.final_answer = final
                    state.status = "completed"
                outcome, error_record = classify_outcome(
                    assistant_msg.content, None,
                    model=profile.name,
                    step=state.step_count,
                )

            step_result = build_step_result(
                step_id=state.step_count,
                action="tool_call" if tool_call is not None else "answer",
                model_used=profile.name,
                routing_reason=reason,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
                outcome=outcome,
                error_record=error_record,
                reasoning=assistant_msg.content[:200],
                tool_name=tool_call["name"] if tool_call else None,
                tool_input=tool_call.get("arguments") if tool_call else None,
            )
            state.step_results.append(step_result)
            state.step_count += 1
            state.last_outcome = outcome
            state.consecutive_errors = (
                0 if outcome == "success" else state.consecutive_errors + 1
            )
            state.model_history.append({
                "step": state.step_count,
                "model": profile.name,
                "tier": profile.tier,
                "reason": reason,
            })

        elapsed_ms = (time.time() - start) * 1000
        return TaskResult(
            task_id=state.task_id,
            task_input=state.task_input,
            steps=state.step_results,
            final_answer=state.final_answer,
            total_cost_usd=state.total_cost_usd,
            total_latency_ms=elapsed_ms,
            total_steps=state.step_count,
            status=state.status if state.final_answer else "exhausted",
        )

    # ── overridable LLM call ───────────────────────────────────────

    async def _invoke_completion(
        self,
        profile: ModelProfile,
        state: FallbackState,
    ) -> dict[str, Any]:
        """Call ``litellm.completion`` with the conversation history.

        Returns a normalized dict so downstream parsing is provider-agnostic:
            {"content": str, "tool_calls": [{name, arguments, id}]}

        Tests inject ``completion_fn`` to keep the loop offline.
        """
        if self._completion_fn is None:
            try:
                import litellm  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - env-specific
                raise RuntimeError(
                    "litellm is required for FallbackReactLoop._invoke_completion"
                ) from exc
            completion_fn = litellm.completion
        else:
            completion_fn = self._completion_fn

        messages = [
            {"role": m.role, "content": m.content}
            for m in state.messages
        ]
        raw = completion_fn(
            model=profile.litellm_id,
            messages=messages,
        )
        return _normalize_litellm_response(raw)

    # ── eval capture ───────────────────────────────────────────────

    async def _record_eval(
        self,
        profile: ModelProfile,
        response: dict[str, Any],
        state: FallbackState,
        *,
        user_id: str,
    ) -> None:
        """Record this invocation through ``eval_capture`` (H5)."""
        try:
            from services import eval_capture

            await eval_capture.record(
                target="fallback_prototype",
                ai_input={"task_input": state.task_input[:200]},
                ai_response=str(response.get("content", ""))[:500],
                config={"configurable": {
                    "user_id": user_id,
                    "task_id": state.task_id,
                }},
                step=state.step_count,
                model=profile.name,
            )
        except Exception as exc:
            logger.warning("eval_capture.record failed: %s", exc)

    # ── termination ────────────────────────────────────────────────

    def _is_terminal(self, state: FallbackState) -> bool:
        if state.final_answer is not None:
            return True
        if state.step_count >= self._agent_config.max_steps:
            return True
        if state.total_cost_usd >= self._agent_config.max_cost_usd:
            return True
        if state.last_error_type == "terminal":
            return True
        return False


# ── helpers ────────────────────────────────────────────────────────


def _load_default_system_prompt() -> str:
    """Load the FallbackReactLoop system prompt via the H1 template service.

    Lazy-imported so importing this module does not require the prompts
    directory (e.g. in environments that strip ``prompts/``). On any
    failure we fall back to a tiny inline string so the prototype stays
    standalone (PLAN_v2.md Phase 4 contingency).
    """
    try:
        from services.prompt_service import PromptService

        ps = PromptService()
        return ps.render_prompt(
            "fallback_prototype/FallbackReactLoop_system_prompt"
        ).strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Falling back to inline system prompt; PromptService failed: %s",
            exc,
        )
        return (
            "You are a ReAct agent. Reason step by step. When you have an "
            "answer, prefix the line with 'FINAL ANSWER:' and stop."
        )


def _default_tool_executor(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Stub executor used when no real registry is wired in."""
    raise RuntimeError(
        f"No tool executor configured -- received call to {tool_name!r} "
        f"with args={tool_args!r}"
    )


def _extract_assistant_message(
    response: dict[str, Any],
) -> tuple[FallbackMessage, dict[str, Any] | None]:
    """Coerce a normalized response into a ``FallbackMessage`` + optional tool call."""
    content = response.get("content", "") or ""
    tool_calls = response.get("tool_calls", []) or []
    msg = FallbackMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
    )
    first_call = tool_calls[0] if tool_calls else None
    return msg, first_call


def _extract_final_answer(content: str, tag: str) -> str | None:
    """Return the final answer text if ``content`` contains the marker."""
    if tag in content:
        return content.split(tag, 1)[1].strip()
    return None


def _normalize_litellm_response(raw: Any) -> dict[str, Any]:
    """Map a litellm ``ModelResponse`` (or dict-like) into our schema.

    Handles both the dict-style (``raw["choices"][0]["message"]``) and the
    object-style (``raw.choices[0].message.content``) envelopes that
    different providers expose through litellm.
    """
    if isinstance(raw, dict):
        choices = raw.get("choices", [])
    else:
        choices = getattr(raw, "choices", []) or []

    if not choices:
        return {"content": "", "tool_calls": []}

    first = choices[0]
    message = (
        first.get("message", {}) if isinstance(first, dict)
        else getattr(first, "message", {}) or {}
    )
    if isinstance(message, dict):
        content = message.get("content") or ""
        raw_calls = message.get("tool_calls") or []
    else:
        content = getattr(message, "content", "") or ""
        raw_calls = getattr(message, "tool_calls", []) or []

    tool_calls: list[dict[str, Any]] = []
    for tc in raw_calls:
        if isinstance(tc, dict):
            fn = tc.get("function", {}) or {}
            name = fn.get("name") or tc.get("name", "")
            arguments_raw = fn.get("arguments") or tc.get("arguments", "{}")
            tc_id = tc.get("id")
        else:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn is not None else getattr(tc, "name", "")
            arguments_raw = (
                getattr(fn, "arguments", "{}") if fn is not None else "{}"
            )
            tc_id = getattr(tc, "id", None)

        if isinstance(arguments_raw, str):
            try:
                arguments = json.loads(arguments_raw) if arguments_raw else {}
            except json.JSONDecodeError:
                arguments = {"raw": arguments_raw}
        else:
            arguments = arguments_raw or {}

        tool_calls.append({"name": name, "arguments": arguments, "id": tc_id})

    return {"content": content, "tool_calls": tool_calls}
