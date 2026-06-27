"""L4 Failure-Mode Matrix: ERROR_OCCURRED carries a discriminating ``error_class``.

The tool-execution seam (``_execute_tools_impl``) records an ``ERROR_OCCURRED``
BlackBox event whenever a tool call fails. Before this matrix, a malformed-args
failure (Pydantic ``ValidationError``) and a genuine runtime crash both landed in
the SAME generic ``except Exception`` and emitted an identical carrier — they were
indistinguishable from telemetry alone (the KEY TELEMETRY GAP behind the
tool-calling-failure investigation).

This module pins the contract that each distinct failure branch stamps a distinct
``details["error_class"]`` on the recorded carrier, so future traces self-categorize:

    unknown_tool | validation | timeout | runtime | tool_reported

Discipline (research/tdd_agentic_systems_prompt.md, Protocol D / Pattern 11):
  * Failure paths first — the error branches are the matrix; the success/no-error
    row is the single non-failure case, asserted last.
  * Behavior over implementation — we assert the *recorded* ``error_class`` on the
    BlackBox carrier (observable telemetry), never the runtime's ``isinstance``
    branch logic (Anti-Pattern 1, tautological tests).
  * No mock-addiction — a real ``ToolRegistry`` + a real ``BlackBoxRecorder`` (on
    ``tmp_path``); only the leaf executor is a stub that raises the target error
    (Anti-Pattern 2). No live LLM — the ``AIMessage.tool_calls`` are constructed
    directly, so the test is deterministic and CI-safe (Anti-Pattern 5).
"""

from __future__ import annotations

import subprocess

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from services.base_config import AgentConfig
from services.governance.black_box import BlackBoxRecorder, EventType
from services.tools.registry import (
    ToolDefinition,
    ToolExecutionResult,
    ToolRegistry,
)


class _ToolInput(BaseModel):
    value: str = "x"


def _registry_with(executor) -> ToolRegistry:
    """Real registry whose single ``the_tool`` runs ``executor`` (Pattern 6 shape)."""
    return ToolRegistry(
        {"the_tool": ToolDefinition(executor=executor, schema=_ToolInput, cacheable=False)}
    )


def _state_calling(tool_name: str) -> dict:
    """Minimal state whose last message is one tool_call to ``tool_name``."""
    ai = AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": {"value": "x"}, "id": "call-1", "type": "tool_call"}],
    )
    return {"workflow_id": "wf-errclass", "messages": [ai], "step_count": 1}


def _run(state: dict, registry: ToolRegistry, tmp_path) -> list:
    """Execute the seam and return the recorded ERROR_OCCURRED events."""
    from orchestration.react_loop import _execute_tools_impl

    black_box = BlackBoxRecorder(storage_dir=tmp_path)
    _execute_tools_impl(
        state,
        tool_registry=registry,
        black_box=black_box,
        agent_config=AgentConfig(),
    )
    events = black_box.replay("wf-errclass")
    return [e for e in events if e.event_type == EventType.ERROR_OCCURRED]


# ── Stub executors, one per failure branch ──────────────────────────────────


def _validation_error():
    try:
        _ToolInput.model_validate({"value": object()})
    except Exception as exc:  # pydantic.ValidationError
        return exc
    raise AssertionError("expected ValidationError")


def _raise_timeout(_args):
    raise subprocess.TimeoutExpired(cmd="sleep", timeout=1)


def _raise_runtime(_args):
    raise RuntimeError("boom")


def _return_failure(_args):
    return ToolExecutionResult(output="Error: tool said no", ok=False, error="tool said no")


def _return_typed_validation(_args):
    """A self-handling tool (e.g. ``file_io``) that caught its own malformed-args
    error and *declares* the class on the envelope instead of masking it as a
    generic ``"Error:"`` string. This is the F1 un-masking path: the executor does
    NOT raise, but the recorded carrier must still surface ``validation``."""
    return ToolExecutionResult(
        output="Error: Path /workspace/x is outside workspace boundary",
        ok=False,
        error="Path /workspace/x is outside workspace boundary",
        error_class="validation",
    )


def _return_ok(_args):
    return ToolExecutionResult(output="fine", ok=True)


# ── Failure-Mode Matrix (failure branches first) ─────────────────────────────


@pytest.mark.parametrize(
    "tool_name,executor,expected_class",
    [
        # unknown tool: name not in the registry -> KeyError branch
        ("missing_tool", _return_ok, "unknown_tool"),
        # malformed args: executor raises a Pydantic ValidationError
        ("the_tool", lambda a: (_ for _ in ()).throw(_validation_error()), "validation"),
        # timeout: executor raises subprocess.TimeoutExpired
        ("the_tool", _raise_timeout, "timeout"),
        # runtime: any other raised exception
        ("the_tool", _raise_runtime, "runtime"),
        # tool_reported: executor returns ok=False (no raise), no class declared
        ("the_tool", _return_failure, "tool_reported"),
        # validation (F1 un-mask): executor returns ok=False AND declares
        # error_class="validation" on the envelope -> carrier surfaces validation,
        # NOT the generic tool_reported. This is the masked-validation fix.
        ("the_tool", _return_typed_validation, "validation"),
    ],
)
def test_error_occurred_carries_error_class(tool_name, executor, expected_class, tmp_path):
    registry = _registry_with(executor)
    errors = _run(_state_calling(tool_name), registry, tmp_path)
    assert errors, f"expected an ERROR_OCCURRED for {expected_class}"
    classes = {e.details.get("error_class") for e in errors}
    assert expected_class in classes, (
        f"expected error_class={expected_class!r}, got {classes!r}"
    )


def test_success_emits_no_error_occurred(tmp_path):
    """The single non-failure row: an ok=True tool records no ERROR_OCCURRED."""
    registry = _registry_with(_return_ok)
    errors = _run(_state_calling("the_tool"), registry, tmp_path)
    assert errors == [], "a successful tool call must not emit ERROR_OCCURRED"


# ── F2: validation-class repair hint on the ToolMessage ──────────────────────


def _run_full(state: dict, registry: ToolRegistry, tmp_path, agent_config=None):
    """Execute the seam and return the full response delta (messages included)."""
    from orchestration.react_loop import _execute_tools_impl

    black_box = BlackBoxRecorder(storage_dir=tmp_path)
    return _execute_tools_impl(
        state,
        tool_registry=registry,
        black_box=black_box,
        agent_config=agent_config or AgentConfig(),
    )


def _tool_message_contents(response: dict) -> list[str]:
    from langchain_core.messages import ToolMessage

    return [m.content for m in response["messages"] if isinstance(m, ToolMessage)]


def test_validation_failure_appends_repair_hint(tmp_path):
    """F2: a validation-class tool failure must append a model-facing corrective
    hint to the ToolMessage so the next turn can self-repair (vs loop+give-up)."""
    registry = _registry_with(_return_typed_validation)
    response = _run_full(_state_calling("the_tool"), registry, tmp_path)
    contents = _tool_message_contents(response)
    assert contents, "expected a ToolMessage for the failed call"
    joined = "\n".join(contents).lower()
    # The hint must name the failure as a malformed-args/validation problem and
    # cue a corrected retry — exact wording is implementation detail, so assert
    # on the actionable cues, not a fixed string (avoids determinism theater).
    assert "validation" in joined or "rejected" in joined or "invalid" in joined
    assert "retry" in joined or "correct" in joined or "fix" in joined


def test_tool_reported_failure_has_no_repair_hint(tmp_path):
    """A genuine tool-reported failure (not malformed args) must NOT get the
    validation repair hint — only validation-class errors are repairable this way."""
    registry = _registry_with(_return_failure)
    response = _run_full(_state_calling("the_tool"), registry, tmp_path)
    joined = "\n".join(_tool_message_contents(response)).lower()
    assert "retry with corrected" not in joined


def test_unknown_tool_nudge_lists_available_tools(tmp_path):
    """F3/F4: a hallucinated tool name must surface the AVAILABLE tools to the
    model so it can self-correct on the next turn instead of looping on the same
    invented name. The registry's KeyError already carries the list; the node
    must forward it into the ToolMessage, not flatten it to a bare error."""
    registry = _registry_with(_return_ok)  # only "the_tool" is registered
    response = _run_full(_state_calling("imaginary_tool"), registry, tmp_path)
    joined = "\n".join(_tool_message_contents(response)).lower()
    assert "the_tool" in joined, "available tool name must be shown to the model"
    assert "available" in joined or "valid tool" in joined


def test_unknown_tool_records_unknown_tool_class(tmp_path):
    """The unknown-tool nudge must not disturb the single unknown_tool carrier."""
    registry = _registry_with(_return_ok)
    errors = _run(_state_calling("imaginary_tool"), registry, tmp_path)
    assert len(errors) == 1
    assert errors[0].details.get("error_class") == "unknown_tool"


def test_repair_hint_disabled_by_flag(tmp_path):
    """The hint is gated: with tool_repair_hint_enabled=False the ToolMessage is
    the raw tool output, byte-for-byte (no enrichment)."""
    from services.base_config import AgentConfig

    cfg = AgentConfig(tool_repair_hint_enabled=False)
    registry = _registry_with(_return_typed_validation)
    response = _run_full(_state_calling("the_tool"), registry, tmp_path, agent_config=cfg)
    joined = "\n".join(_tool_message_contents(response)).lower()
    assert "retry" not in joined and "correct" not in joined


@pytest.mark.parametrize(
    "tool_name,executor,expected_class",
    [
        ("missing_tool", _return_ok, "unknown_tool"),
        ("the_tool", lambda a: (_ for _ in ()).throw(_validation_error()), "validation"),
        ("the_tool", _raise_timeout, "timeout"),
        ("the_tool", _raise_runtime, "runtime"),
        ("the_tool", _return_failure, "tool_reported"),
        ("the_tool", _return_typed_validation, "validation"),
    ],
)
def test_one_error_occurred_per_failure(tool_name, executor, expected_class, tmp_path):
    """Governance: a single tool failure emits EXACTLY ONE error.occurred carrier
    with ONE error_class — never a duplicate. The raised-exception branches set
    ``ok=False`` and record their own carrier; the trailing ``not ok`` block must
    not record a second, conflicting (``tool_reported``) carrier for the same call.
    Exactly-one-reliable-carrier is the audit's cardinal rule."""
    registry = _registry_with(executor)
    errors = _run(_state_calling(tool_name), registry, tmp_path)
    assert len(errors) == 1, (
        f"{expected_class}: expected exactly one ERROR_OCCURRED, got "
        f"{[e.details.get('error_class') for e in errors]}"
    )
    assert errors[0].details.get("error_class") == expected_class
