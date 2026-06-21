"""C1 Phases 5 + 6 — WRITE wire at ``evaluate_node`` + READ wire at
``call_llm_node`` (design §5.1 / §5.2 / §5.4).

Test stations:

* ``TestStateRewriteRoundTrip`` is the **load-bearing** proof the impl plan
  flags as ``Fix A``: the ``RemoveMessage(REMOVE_ALL_MESSAGES)`` rewrite is
  exercised **nowhere else in-repo**, so without this test a future langgraph
  bump can silently break the §B1-R R4 reload-and-stay-compacted contract.
  The tests run on a minimal one-node graph + ``MemorySaver`` — no
  ``evaluate_node`` involved — so they pin the langgraph mechanism Phase 5
  leans on, independent of the caller. A ``langgraph`` version guard fires
  the test on every bump.

* ``TestEvaluateNodeWriteWire`` drives ``evaluate_node`` directly via
  ``build_graph(...).nodes['evaluate'].bound``. Default-OFF must stay
  byte-identical (no ``messages``/``last_compaction_step`` keys in the
  returned dict); flag-ON + over-trigger emits the rewrite; cooldown
  suppresses a second fold; the §5.4 terminal gate raises a typed
  ``ContextWindowExhaustedError`` classified ``terminal``.

* ``TestCallLlmReadWireFlagOff`` + ``TestCallLlmReadWireMaskOn`` +
  ``TestCallLlmReadWireTailFloor`` cover the Phase 6 READ wire. Flag-OFF
  must stay byte-identical (the unchanged ``test_react_loop.py`` regression
  also enforces this on the full node). Flag-ON: tool observations older
  than ``M`` steps get their ``content`` masked **transiently** (only on the
  stack handed to ``llm_service.invoke_with_tools``), and when
  ``context_constraint_reinject_turns > 0`` the tail constraint floor is
  **persisted append-only** in ``result["messages"]`` on cadence turns,
  dropping the prior tail-floor so it never accumulates (§5.2).

L1, pure (apart from the langgraph round-trip — still in-process), <10s,
zero flake.
"""

from __future__ import annotations

import asyncio
import importlib.metadata as _ilm

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from orchestration.state import AgentState
from services.base_config import AgentConfig, ModelProfile


# ════════════════════════════════════════════════════════════════════════════
# Part A — langgraph add_messages REMOVE_ALL_MESSAGES contract (Fix A).
#
# This test station establishes the mechanism Phase 5's WRITE seam relies on:
# the ``RemoveMessage(REMOVE_ALL_MESSAGES)`` sentinel reduces the entire
# ``messages`` channel to the tail-after-sentinel — even across a checkpoint
# reload. It is exercised nowhere else in-repo (design §2, impl §7).
# ════════════════════════════════════════════════════════════════════════════


def _fake_pre_fold_msgs() -> list:
    """A representative pre-fold transcript (3 turns × {Human, AI, Tool}).

    The AI message carries the issuing ``tool_calls`` entry that the Tool
    message answers — without it, Phase 8's L1-d ``no_orphaned_tool`` gate
    correctly flags every block as a split orphan. This shape matches what
    the live ReAct loop emits: ``AIMessage.tool_calls`` and
    ``ToolMessage.tool_call_id`` are paired.
    """
    out: list = []
    for i in range(3):
        out.append(HumanMessage(content=f"q-{i}"))
        out.append(
            AIMessage(
                content=f"a-{i}",
                tool_calls=[
                    {"id": f"call-{i}", "name": "echo", "args": {"x": i}},
                ],
            )
        )
        out.append(ToolMessage(content=f"obs-{i}", tool_call_id=f"call-{i}"))
    return out


def _rewrite_emit_node(summary: str, preserved: list):
    """Build a node fn that returns the §5.1 rewrite as the node's delta."""

    def _node(state) -> dict:
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=summary),
                *preserved,
            ]
        }

    return _node


class TestStateRewriteRoundTrip:
    """The §B1-R R4 fix: ``add_messages`` short-circuits on the sentinel and
    the *compacted* list is what the checkpointer reloads."""

    def test_langgraph_version_guard(self) -> None:
        """Pin langgraph at the version the design verified
        (``0.6.11``, design §2). A future bump must re-run this whole suite
        — the ``REMOVE_ALL_MESSAGES`` short-circuit is what makes the §5.1
        rewrite work; if the reducer behavior shifts, every C1 invariant
        below is suspect."""
        installed = _ilm.version("langgraph")
        # Only the minor-line is contract-relevant; the design verified the
        # ``0.6.x`` series. A jump to ``0.7.x`` MUST re-run this gate by hand.
        assert installed.startswith("0.6."), (
            f"langgraph version {installed} crosses the design-verified line "
            "(0.6.x). Re-verify REMOVE_ALL_MESSAGES short-circuit, then bump."
        )

    def test_sentinel_replaces_entire_channel(self) -> None:
        """A single ``[RemoveMessage(REMOVE_ALL_MESSAGES), SystemMessage,
        *preserved]`` delta REPLACES the prior messages list (prefix gone)."""
        preserved = _fake_pre_fold_msgs()[-3:]  # the "last K" tail

        builder = StateGraph(AgentState)
        builder.add_node("rewrite", _rewrite_emit_node("SUMMARY", preserved))
        builder.set_entry_point("rewrite")
        builder.set_finish_point("rewrite")
        graph = builder.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "c1-rw-1"}}
        # Seed the channel with the full pre-fold history.
        seed_msgs = _fake_pre_fold_msgs()
        out = graph.invoke({"messages": seed_msgs}, cfg)

        # Exactly: SystemMessage(summary) + the 3-message preserved tail.
        assert len(out["messages"]) == 1 + len(preserved), (
            "the prefix was not dropped — sentinel did not short-circuit"
        )
        assert isinstance(out["messages"][0], SystemMessage)
        assert out["messages"][0].content == "SUMMARY"
        # Tail content preserved verbatim.
        for i, msg in enumerate(out["messages"][1:]):
            assert type(msg) is type(preserved[i])
            assert msg.content == preserved[i].content

    def test_compacted_state_survives_checkpoint_reload(self) -> None:
        """The R4 guard: the *compacted* list is what the next invoke loads
        — re-bloat would mean the rewrite landed in delta-space only."""
        preserved = _fake_pre_fold_msgs()[-3:]
        seen: dict[str, list] = {}

        def rewrite(state) -> dict:
            return {
                "messages": [
                    RemoveMessage(id=REMOVE_ALL_MESSAGES),
                    SystemMessage(content="SUMMARY"),
                    *preserved,
                ]
            }

        def read_only(state) -> dict:
            # Capture what the SECOND invoke reads from the checkpointer.
            seen["after_reload"] = list(state["messages"])
            return {}

        builder = StateGraph(AgentState)
        builder.add_node("rewrite", rewrite)
        builder.add_node("read_only", read_only)
        builder.set_entry_point("rewrite")
        builder.add_edge("rewrite", "read_only")
        builder.set_finish_point("read_only")
        graph = builder.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "c1-rw-2"}}
        graph.invoke({"messages": _fake_pre_fold_msgs()}, cfg)
        # Second invoke on the SAME thread — no fresh input. The compacted
        # transcript must already be the loaded state when `read_only` runs.
        graph.invoke({}, cfg)

        # The read after reload must see the compacted list, not the full
        # pre-fold history.
        assert len(seen["after_reload"]) == 1 + len(preserved), (
            f"R4 re-bloat: reload restored the full prefix "
            f"(got {len(seen['after_reload'])} messages, expected "
            f"{1 + len(preserved)}) — rewrite did not persist"
        )
        assert isinstance(seen["after_reload"][0], SystemMessage)
        assert seen["after_reload"][0].content == "SUMMARY"

    def test_rewrite_assigns_fresh_ids(self) -> None:
        """``add_messages`` assigns ids on rematerialization — Phase 5 never
        copies the prior ids, so the post-fold tail carries fresh ids."""
        preserved = [HumanMessage(content="kept")]
        builder = StateGraph(AgentState)
        builder.add_node("rewrite", _rewrite_emit_node("S", preserved))
        builder.set_entry_point("rewrite")
        builder.set_finish_point("rewrite")
        graph = builder.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "c1-rw-3"}}
        out = graph.invoke({"messages": _fake_pre_fold_msgs()}, cfg)

        # Every message has an id (auto-assigned), and they're all unique.
        ids = [m.id for m in out["messages"]]
        assert all(i is not None for i in ids)
        assert len(set(ids)) == len(ids), "duplicate ids in the rewritten list"


# ════════════════════════════════════════════════════════════════════════════
# Part B — evaluate_node WRITE wire (the Phase 5 production target).
#
# Drive evaluate_node directly via the compiled graph's PregelNode.bound.
# evaluate_node is a closure inside build_graph — reaching it via .bound
# is the only way to unit-test the WRITE wire without scaffolding the entire
# LLM/tool/eval stack just to fall through to evaluation.
# ════════════════════════════════════════════════════════════════════════════


def _evaluate_callable():
    """Build a graph and return the runnable wrapping ``evaluate_node``.

    Calling site passes through a fresh ``AgentConfig`` so tests that want a
    flag-ON config (or a custom model) can rebuild instead of mutating.
    """
    from orchestration.react_loop import build_graph

    cfg = AgentConfig()
    graph = build_graph(cfg)
    return graph.nodes["evaluate"].bound


def _flag_on_evaluate_callable(
    *,
    profile: ModelProfile | None = None,
    cache_dir: object | None = None,
):
    """Build a graph with the C1 master flag ON.

    A test profile with a tiny context_window lets the §5.4 terminal gate
    fire on a controllable token count. ``cache_dir`` (Phase 7) lets the
    caller redirect the per-graph ``black_box`` / ``phase_logger`` storage
    to a tmp_path so JSONL emissions are inspectable.
    """
    from orchestration.react_loop import build_graph

    cfg = AgentConfig(
        context_compact_messages_enabled=True,
        context_compact_trigger_fraction=0.6,
        context_keep_last_k=2,
        context_compact_cooldown_steps=5,
        # If a profile is supplied, register it on the config so select_model
        # can resolve it via name.
        models=[profile] if profile is not None else [],
        default_model=profile.name if profile is not None else "gpt-4o-mini",
    )
    kwargs = {} if cache_dir is None else {"cache_dir": cache_dir}
    graph = build_graph(cfg, **kwargs)
    return graph.nodes["evaluate"].bound


def _minimal_state(**overrides) -> dict:
    """A pre-evaluate AgentState the node will accept without erroring."""
    base = {
        "messages": [],
        "workflow_id": "wf-c1",
        "task_id": "task-c1",
        "step_count": 0,
        "current_token_count": 0,
        "last_compaction_step": 0,
        "selected_model": "gpt-4o-mini",
        "task_input": "hello",
    }
    base.update(overrides)
    return base


def _config_for_thread(thread_id: str = "th-c1") -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _invoke(node, state, config) -> dict:
    return asyncio.run(node.ainvoke(state, config))


class TestEvaluateNodeWriteWireFlagOff:
    """Default-OFF byte-identical (the prod-safety invariant) — the result
    dict never carries Phase 5's added keys when the master flag is off."""

    def test_default_off_omits_messages_rewrite(self) -> None:
        """The result dict for a normal evaluation must NOT include a
        ``messages`` rewrite when ``context_compact_messages_enabled=False``.
        """
        node = _evaluate_callable()  # default config: flag OFF
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            # Set token count above ANY reasonable trigger to prove the gate
            # holds purely on the master flag.
            current_token_count=10_000_000,
        )
        out = _invoke(node, state, _config_for_thread("th-off-1"))
        assert "messages" not in out, (
            "flag OFF emitted a messages rewrite — byte-identical-when-off "
            "invariant violated"
        )

    def test_default_off_omits_last_compaction_step(self) -> None:
        """Cooldown stamp is only written when a fold actually runs."""
        node = _evaluate_callable()
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(), current_token_count=10_000_000
        )
        out = _invoke(node, state, _config_for_thread("th-off-2"))
        assert "last_compaction_step" not in out, (
            "flag OFF stamped last_compaction_step — gate leak"
        )


class TestEvaluateNodeWriteWireFlagOn:
    """Flag ON + trigger met → ``evaluate_node`` returns the §5.1 rewrite
    + ``last_compaction_step`` stamp + ``truncation_applied=True``."""

    def _tiny_profile(self, window: int = 1000) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=window,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def test_flag_on_with_trigger_emits_rewrite(self) -> None:
        """Token count above the trigger fraction + cooldown elapsed →
        the result dict carries the canonical rewrite (RemoveMessage sentinel
        + summary SystemMessage + preserved tail)."""
        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile)

        # 0.6 × 1000 = 600 → 700 > 600 trips the trigger.
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,
            step_count=10,
            last_compaction_step=0,  # never folded → cooldown elapsed
            selected_model=profile.name,
        )
        out = _invoke(node, state, _config_for_thread("th-on-1"))

        assert "messages" in out, "flag ON + over-trigger: no rewrite emitted"
        rewrite = out["messages"]
        assert isinstance(rewrite, list) and len(rewrite) >= 2
        # First element MUST be the sentinel.
        assert isinstance(rewrite[0], RemoveMessage)
        assert rewrite[0].id == REMOVE_ALL_MESSAGES
        # Second element MUST be the summary SystemMessage.
        assert isinstance(rewrite[1], SystemMessage)
        assert rewrite[1].content, "summary SystemMessage is empty"

    def test_flag_on_stamps_last_compaction_step(self) -> None:
        """A successful fold stamps ``last_compaction_step = step_count``."""
        profile = self._tiny_profile()
        node = _flag_on_evaluate_callable(profile=profile)
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,
            step_count=10,
            last_compaction_step=0,
            selected_model=profile.name,
        )
        out = _invoke(node, state, _config_for_thread("th-on-2"))
        assert out.get("last_compaction_step") == 10, (
            "last_compaction_step not stamped to current step_count"
        )
        assert out.get("truncation_applied") is True

    def test_flag_on_below_trigger_no_rewrite(self) -> None:
        """Under-trigger: no fold, no stamp."""
        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile)
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=100,  # << 600 trigger
            step_count=10,
            last_compaction_step=0,
            selected_model=profile.name,
        )
        out = _invoke(node, state, _config_for_thread("th-on-3"))
        assert "messages" not in out
        assert "last_compaction_step" not in out

    def test_cooldown_holds_second_fold(self) -> None:
        """Cooldown predicate: ``step_count - last_compaction_step <
        cooldown_steps`` — no second fold within the window even if the
        trigger is met (the §6 within-turn stale-count guard)."""
        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile)
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,  # trigger met
            step_count=12,
            last_compaction_step=10,  # delta = 2 < cooldown_steps=5 → HOLD
            selected_model=profile.name,
        )
        out = _invoke(node, state, _config_for_thread("th-on-4"))
        assert "messages" not in out, "cooldown failed — fold ran within window"

    def test_cooldown_elapsed_permits_second_fold(self) -> None:
        """Symmetric: once cooldown elapsed, another fold IS permitted."""
        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile)
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,
            step_count=20,
            last_compaction_step=10,  # delta = 10 ≥ 5 → permit
            selected_model=profile.name,
        )
        out = _invoke(node, state, _config_for_thread("th-on-5"))
        assert "messages" in out, "cooldown over-held — fold did not run"


# ════════════════════════════════════════════════════════════════════════════
# Part C — §5.4 terminal gate: ContextWindowExhaustedError.
#
# When the floor is exceeded AND current_token_count > 0.95 × profile.context_window,
# the node raises a typed terminal error. The error must be importable from
# orchestration/react_loop.py and classified terminal (not retryable).
# ════════════════════════════════════════════════════════════════════════════


class TestContextWindowExhaustedError:
    def test_error_is_importable(self) -> None:
        """The typed error lives in ``orchestration.react_loop`` (where
        ``profile`` is in scope, design §5.4)."""
        from orchestration.react_loop import ContextWindowExhaustedError  # noqa: F401

    def test_error_carries_terminal_classification(self) -> None:
        """The error instance must signal it is non-retryable.

        Design §5.4 demands ``last_error_type='context_window_exhausted'``;
        the node sets this *and* the error type's name itself is a stable
        anchor for the route node's classifier.
        """
        from orchestration.react_loop import ContextWindowExhaustedError

        e = ContextWindowExhaustedError("hard window reached")
        assert isinstance(e, Exception)
        # Type name is the load-bearing classification anchor — never rename
        # without re-checking the route_node branch in react_loop.py:1997.
        assert type(e).__name__ == "ContextWindowExhaustedError"


class TestEvaluateNodeTerminalGate:
    """The §5.4 ceiling: floor_exceeded AND tokens > 0.95×window → raise
    typed terminal error, set ``last_error_type='context_window_exhausted'``,
    surface the error type in state."""

    def _tiny_profile(self, window: int) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=window,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def test_terminal_gate_raises_when_floor_exceeded_at_ceiling(self) -> None:
        """floor_exceeded AND tokens > 0.95×window → typed terminal raise.

        We synthesize ``floor_exceeded=True`` by feeding a profile whose
        ``context_window`` is so small that even the cheapest plan-fold can't
        fit (the planner sets ``floor_exceeded`` when ``keep_last_k`` worth of
        tail + pinned floor > budget). With window=100 and tokens=99 we are
        at 99% — over the 0.95 ceiling — and the same tiny window guarantees
        the pure planner's ``floor_exceeded`` flag.
        """
        from orchestration.react_loop import ContextWindowExhaustedError

        profile = self._tiny_profile(window=100)
        node = _flag_on_evaluate_callable(profile=profile)

        # 0.95 × 100 = 95 → 99 trips the ceiling.
        # Pinned constraints via task_understanding success_conditions: the
        # planner consults this dict (design §5.4); set tons of them so
        # floor_exceeded is true even when keep_last_k is tiny.
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=99,
            step_count=10,
            last_compaction_step=0,
            selected_model=profile.name,
            task_understanding={
                "success_conditions": [
                    "MUST preserve constraint " + ("X" * 1000),
                ]
                * 50,
                "source": "deterministic",
                "restated_intent": "test",
            },
        )

        with pytest.raises(ContextWindowExhaustedError):
            _invoke(node, state, _config_for_thread("th-term-1"))

    def test_terminal_gate_holds_below_ceiling(self) -> None:
        """floor_exceeded but tokens UNDER 0.95×window → DECLINE the fold
        (return without rewrite) but do NOT raise — §5.3 fail-loud."""
        from orchestration.react_loop import ContextWindowExhaustedError

        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile)

        # 0.95 × 1000 = 950 → 700 is under the ceiling.
        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,
            step_count=10,
            last_compaction_step=0,
            selected_model=profile.name,
            task_understanding={
                "success_conditions": [
                    "MUST preserve constraint " + ("X" * 1000),
                ]
                * 50,
                "source": "deterministic",
                "restated_intent": "test",
            },
        )

        # Must NOT raise — declines silently (§5.3), no rewrite emitted.
        try:
            out = _invoke(node, state, _config_for_thread("th-term-2"))
        except ContextWindowExhaustedError:
            pytest.fail(
                "terminal gate fired below 0.95×window ceiling — §5.4 mis-wired"
            )

        # Declined fold = no rewrite, no stamp.
        assert "messages" not in out
        assert "last_compaction_step" not in out


# ════════════════════════════════════════════════════════════════════════════
# Part D — Phase 6 READ wire at ``call_llm_node`` (design §5.2).
#
# Two transient/persisted behaviors layered behind the master flag:
#
# 1) **Observation masking** — for tool messages older than M steps, replace
#    ``content`` with a placeholder BEFORE handing the stack to the LLM.
#    Transient: nothing in ``result["messages"]`` records the mask; the
#    next turn re-derives it from the current step_count clock.
#
# 2) **Tail constraint floor** — when ``context_constraint_reinject_turns > 0``
#    AND ``step_count % N == 0`` AND there are pinned ``must-not`` constraints,
#    append a ``SystemMessage(build_constraint_floor(pinned))`` to
#    ``result["messages"]`` (persisted append-only, §0). The PRIOR tail floor
#    must be dropped on every fresh re-injection so the channel doesn't bloat
#    one ``SystemMessage`` per cadence turn (§5.2 wiring detail).
#
# The READ wire never raises and never gates a fold — it only reshapes the
# prompt stack. We capture what the LLM sees by monkey-patching
# ``LLMService.invoke_with_tools`` to record the messages list.
# ════════════════════════════════════════════════════════════════════════════


class _FakeLLMResponse:
    """A minimal duck for the response shape ``call_llm_node`` reads."""

    def __init__(self, content: str = "ok") -> None:
        self.content = content
        self.tool_calls = []
        self.usage_metadata = {"input_tokens": 0, "output_tokens": 0}
        self.response_metadata = {}


class _RecordingLLM:
    """Captures every ``invoke_with_tools`` call so a test can inspect the
    transient stack the node assembled."""

    def __init__(self) -> None:
        self.calls: list[list] = []

    async def invoke_with_tools(
        self, profile, messages, tool_schemas=None, **kw
    ):
        self.calls.append(list(messages))
        return _FakeLLMResponse()


def _build_llm_node_with_recording(
    *,
    flag: bool,
    profile: ModelProfile | None = None,
    mask_after_steps: int = 10,
    reinject_turns: int = 0,
    keep_last_k: int = 10,
) -> tuple[object, _RecordingLLM, object]:
    """Compile a graph and rebind ``llm_service`` inside ``call_llm_node``'s
    closure to a recording fake.

    Returns ``(bound_node, recorder, cleanup_fn)``. Tests MUST call the
    cleanup_fn (or use the context manager helper below) to leave the
    ``LLMService`` class clean for the next test.
    """
    from orchestration import react_loop as _rl

    cfg = AgentConfig(
        context_compact_messages_enabled=flag,
        context_compact_trigger_fraction=0.6,
        context_keep_last_k=keep_last_k,
        context_mask_after_steps=mask_after_steps,
        context_compact_cooldown_steps=5,
        context_constraint_reinject_turns=reinject_turns,
        models=[profile] if profile is not None else [],
        default_model=profile.name if profile is not None else "gpt-4o-mini",
    )

    rec = _RecordingLLM()

    # Monkey-patch ``LLMService.invoke_with_tools`` on the CLASS, and KEEP
    # the patch live until the test calls cleanup — Python resolves the
    # method on every call via instance.__class__.invoke_with_tools, so the
    # closure's ``llm_service`` instance picks up the patched method at call
    # time even though it was constructed before the patch.
    import services.llm_config as _llm_mod

    _orig = _llm_mod.LLMService.invoke_with_tools

    async def _patched(self, profile, messages, tool_schemas=None, **kw):
        return await rec.invoke_with_tools(
            profile, messages, tool_schemas=tool_schemas, **kw
        )

    # Also patch ``get_profile`` so the closure resolves the test profile
    # even when it isn't registered in the underlying LLMService's profile
    # map (the recording test never needs the real one).
    _orig_get_profile = _llm_mod.LLMService.get_profile

    def _patched_get_profile(self, name: str):
        if profile is not None and name == profile.name:
            return profile
        return _orig_get_profile(self, name)

    _llm_mod.LLMService.invoke_with_tools = _patched
    _llm_mod.LLMService.get_profile = _patched_get_profile

    graph = _rl.build_graph(cfg)
    bound = graph.nodes["call_llm"].bound

    def _cleanup() -> None:
        _llm_mod.LLMService.invoke_with_tools = _orig
        _llm_mod.LLMService.get_profile = _orig_get_profile

    return bound, rec, _cleanup


def _msgs_with_old_tool_obs() -> list:
    """A transcript with old tool observations the mask should target.

    Builds 12 ``HumanMessage/AIMessage/ToolMessage`` blocks so even with
    ``mask_after_steps=10`` at least the oldest 2 blocks' tool obs are
    masked.
    """
    out: list = []
    for i in range(12):
        out.append(HumanMessage(content=f"q-{i}"))
        out.append(AIMessage(content=f"a-{i}", tool_calls=[]))
        out.append(ToolMessage(content=f"obs-{i}", tool_call_id=f"call-{i}"))
    return out


class TestCallLlmReadWireFlagOff:
    """Master flag OFF → the LLM sees the same stack it would have today
    (``[SystemMessage(system_prompt)] + list(existing_messages)``)."""

    def test_flag_off_no_mask_no_tail(self) -> None:
        node, rec, _cleanup = _build_llm_node_with_recording(flag=False)
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(), step_count=15
            )
            out = _invoke(node, state, _config_for_thread("th-r-off-1"))

            assert rec.calls, "LLM was not invoked"
            # No ToolMessage was masked — every original obs-* content survived.
            sent = rec.calls[0]
            obs_contents = [
                m.content for m in sent if isinstance(m, ToolMessage)
            ]
            assert all(c.startswith("obs-") for c in obs_contents), (
                "flag OFF masked an observation — byte-identical-when-off "
                "violated"
            )
            # And nothing tail-floor-ish landed in result["messages"]: only the
            # AIMessage the node always appends.
            assert isinstance(out["messages"], list)
            from langchain_core.messages import AIMessage as _AI
            assert all(isinstance(m, _AI) for m in out["messages"]), (
                "flag OFF appended something other than the AI response — "
                "byte-identical-when-off violated"
            )
        finally:
            _cleanup()


class TestCallLlmReadWireMaskOn:
    """Flag ON: tool observations older than ``mask_after_steps`` blocks are
    masked in the stack handed to the LLM. The mask is **transient** — it
    never lands in ``result["messages"]`` (which still only carries the AI
    response, as today)."""

    def _tiny_profile(self) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=128_000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def test_mask_applied_to_old_tool_obs(self) -> None:
        """The mask reaches the LLM stack: tool observations older than the
        ``mask_after_steps`` window have their ``content`` replaced (and the
        ``tool_call_id`` preserved); recent ones are byte-identical.

        We pin the boundary against the pure planner's own output rather than
        re-deriving it here — the *contract* under test is "what the planner
        marks for masking IS what reaches the LLM with masked content," not
        the planner's block-counting math (covered by tests/services/test_summarizer.py).
        """
        from orchestration.message_view import to_views
        from services.summarizer import plan_observation_mask

        profile = self._tiny_profile()
        node, rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, mask_after_steps=10
        )
        try:
            msgs = _msgs_with_old_tool_obs()
            # Compute the planner's expected mask once; assert the wire applies
            # exactly that set.
            expected_mask = plan_observation_mask(
                to_views(msgs), mask_after_steps=10
            )
            # The planner SHOULD mask at least one obs in this 12-triple
            # transcript (else the test is trivially passing).
            assert expected_mask, (
                "test transcript no longer exercises the planner — fix the "
                "fixture so plan_observation_mask returns a non-empty set"
            )

            state = _minimal_state(
                messages=msgs,
                step_count=12,
                selected_model=profile.name,
            )
            _invoke(node, state, _config_for_thread("th-r-mask-1"))

            assert rec.calls, "LLM was not invoked"
            sent = rec.calls[0]
            # Drop the leading SystemMessage(system_prompt) so positional
            # indices align with the pre-call ``existing_messages`` slice
            # (which is what ``plan_observation_mask`` indexes into).
            tail = sent[1:]
            assert len(tail) == len(msgs), (
                f"system prompt strip changed message count: "
                f"got {len(tail)}, expected {len(msgs)}"
            )
            for i, m in enumerate(tail):
                if i in expected_mask:
                    assert isinstance(m, ToolMessage), (
                        f"planner targeted index {i} but stack carries "
                        f"{type(m).__name__}"
                    )
                    assert not m.content.startswith("obs-"), (
                        f"index {i}: planner marked for masking but "
                        f"content survived ({m.content!r})"
                    )
                    # Orphan-safety: same tool_call_id preserved on masked msg.
                    assert m.tool_call_id == msgs[i].tool_call_id
                else:
                    # Not selected → byte-identical content.
                    assert getattr(m, "content", None) == getattr(
                        msgs[i], "content", None
                    ), (
                        f"index {i}: planner did NOT target this view but "
                        f"its content changed ({m.content!r} vs "
                        f"{msgs[i].content!r})"
                    )
        finally:
            _cleanup()

    def test_mask_is_transient_not_in_result_messages(self) -> None:
        """The mask must not bleed into ``result["messages"]`` — the persisted
        channel still carries only the AI response (today's behavior). The
        next turn re-derives the mask from step_count."""
        profile = self._tiny_profile()
        node, rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, mask_after_steps=10
        )
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(),
                step_count=12,
                selected_model=profile.name,
            )
            out = _invoke(node, state, _config_for_thread("th-r-mask-2"))

            # The result delta must NOT contain any masked ToolMessage or any
            # SystemMessage (no tail-floor, reinject_turns defaulted to 0).
            deltas = out.get("messages") or []
            from langchain_core.messages import AIMessage as _AI
            assert all(isinstance(m, _AI) for m in deltas), (
                f"READ-side mask leaked into result['messages']: {deltas!r}"
            )
        finally:
            _cleanup()

    def test_mask_off_when_master_flag_off(self) -> None:
        """Flag-OFF must NOT apply the mask even when mask_after_steps is
        configured — the gate is the master flag, not the knob."""
        node, rec, _cleanup = _build_llm_node_with_recording(
            flag=False, mask_after_steps=2  # would mask aggressively if applied
        )
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(), step_count=12
            )
            _invoke(node, state, _config_for_thread("th-r-mask-3"))

            sent = rec.calls[0]
            tool_msgs = [m for m in sent if isinstance(m, ToolMessage)]
            assert all(m.content.startswith("obs-") for m in tool_msgs), (
                "mask applied when master flag was OFF — gate leak"
            )
        finally:
            _cleanup()


class TestCallLlmReadWireTailFloor:
    """Tail-floor opt-in: ``context_constraint_reinject_turns > 0`` AND
    ``step_count % N == 0`` AND pinned must-not constraints exist →
    a ``SystemMessage(build_constraint_floor(pinned))`` is appended to
    ``result["messages"]`` (persisted, append-only, §0); the prior tail
    floor must be dropped before re-appending (§5.2)."""

    def _tiny_profile(self) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=128_000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def _task_understanding_with_mustnots(self) -> dict:
        # ``derive_pinned_floor`` parses ``MUST NOT`` strings as polarity
        # ``must-not``; this is what makes the floor body non-empty.
        return {
            "success_conditions": [
                "MUST NOT call external network",
                "MUST NOT mutate user records",
            ],
            "source": "deterministic",
            "restated_intent": "test",
        }

    def test_tail_floor_off_when_n_is_zero(self) -> None:
        """Default ``context_constraint_reinject_turns=0`` → no tail floor
        ever, even with pinned constraints + step % N would-be-0."""
        profile = self._tiny_profile()
        node, _rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, reinject_turns=0
        )
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(),
                step_count=0,
                selected_model=profile.name,
                task_understanding=self._task_understanding_with_mustnots(),
            )
            out = _invoke(node, state, _config_for_thread("th-r-tail-0"))

            deltas = out.get("messages") or []
            # SystemMessages in deltas would be the tail floor — there must
            # be none.
            from langchain_core.messages import SystemMessage as _Sys
            assert not any(isinstance(m, _Sys) for m in deltas), (
                "tail floor was appended even when N=0 — opt-in gate leak"
            )
        finally:
            _cleanup()

    def test_tail_floor_persisted_on_cadence_turn(self) -> None:
        """N=3, step_count=6 (6 % 3 == 0) AND must-not constraints exist →
        a SystemMessage(constraint floor) is appended to result['messages'].
        """
        profile = self._tiny_profile()
        node, _rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, reinject_turns=3
        )
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(),
                step_count=6,  # 6 % 3 == 0
                selected_model=profile.name,
                task_understanding=self._task_understanding_with_mustnots(),
            )
            out = _invoke(node, state, _config_for_thread("th-r-tail-1"))

            deltas = out.get("messages") or []
            from langchain_core.messages import SystemMessage as _Sys
            sys_msgs = [m for m in deltas if isinstance(m, _Sys)]
            assert len(sys_msgs) == 1, (
                f"expected exactly one tail-floor SystemMessage in deltas, "
                f"got {len(sys_msgs)}: {deltas!r}"
            )
            assert "MUST NOT call external network" in sys_msgs[0].content
            assert "MUST NOT mutate user records" in sys_msgs[0].content
        finally:
            _cleanup()

    def test_tail_floor_off_turn_no_append(self) -> None:
        """N=3, step_count=5 (5 % 3 != 0) → no tail-floor append; just the
        AI response in the delta."""
        profile = self._tiny_profile()
        node, _rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, reinject_turns=3
        )
        try:
            state = _minimal_state(
                messages=_msgs_with_old_tool_obs(),
                step_count=5,
                selected_model=profile.name,
                task_understanding=self._task_understanding_with_mustnots(),
            )
            out = _invoke(node, state, _config_for_thread("th-r-tail-2"))

            from langchain_core.messages import SystemMessage as _Sys
            deltas = out.get("messages") or []
            assert not any(isinstance(m, _Sys) for m in deltas), (
                "tail floor was appended on a non-cadence turn"
            )
        finally:
            _cleanup()

    def test_tail_floor_drops_prior_when_reappending(self) -> None:
        """The §5.2 accumulation guard: when re-appending on a cadence turn,
        any prior tail-floor SystemMessage in the persisted ``messages`` must
        be dropped (via ``RemoveMessage`` on its id) so the floor does NOT
        accumulate one copy per cadence turn."""
        from langchain_core.messages import SystemMessage as _Sys
        from langchain_core.messages import RemoveMessage as _Rm

        profile = self._tiny_profile()
        node, _rec, _cleanup = _build_llm_node_with_recording(
            flag=True, profile=profile, reinject_turns=3
        )
        try:
            # Simulate a prior tail-floor SystemMessage in the persisted
            # channel.
            prior_floor = _Sys(
                content="Constraint floor (must-not):\n- STALE\n",
                id="cf-prior-1",
            )
            msgs = _msgs_with_old_tool_obs() + [prior_floor]
            state = _minimal_state(
                messages=msgs,
                step_count=6,  # cadence turn
                selected_model=profile.name,
                task_understanding=self._task_understanding_with_mustnots(),
            )
            out = _invoke(node, state, _config_for_thread("th-r-tail-3"))

            deltas = out.get("messages") or []
            # The delta must contain BOTH a RemoveMessage targeting the prior
            # floor's id AND the fresh tail-floor SystemMessage. The order
            # matters: the RemoveMessage must precede the SystemMessage so
            # add_messages drops the prior before appending the new one.
            rms = [m for m in deltas if isinstance(m, _Rm)]
            sys_msgs = [m for m in deltas if isinstance(m, _Sys)]
            assert any(m.id == "cf-prior-1" for m in rms), (
                f"prior tail-floor RemoveMessage not in deltas: {deltas!r}"
            )
            assert len(sys_msgs) == 1
            # And the fresh tail-floor carries the current must-not list.
            assert "MUST NOT mutate user records" in sys_msgs[0].content
        finally:
            _cleanup()


# ════════════════════════════════════════════════════════════════════════════
# Part E — Phase 7 dual-carrier wiring at the fold site (design §7.2).
#
# A fold must announce, justify, and prove-floor-intact. At evaluate_node's
# WRITE seam, this means TWO sinks emit, joined by ``decision_id``:
#
#  - Reasoning  → ``phase_logger.log_decision(... alternatives=["keep_full"])``
#                 → ``decisions.jsonl``
#  - Recording  → ``black_box.record(TraceEvent(CONTEXT_COMPACTED, details={
#                   "decision_id": …, counts, hash, flags}))``
#                 → ``black_box_recordings/<wf>/events.jsonl``
#
# Inspecting the on-disk JSONL emissions is the honest way to verify both
# sinks fired — they're closures inside ``build_graph``, and pointing
# ``cache_dir`` at a tmp_path captures them deterministically.
# ════════════════════════════════════════════════════════════════════════════


class TestEvaluateNodeCompactionCarrierWiring:
    """Phase 7: the fold site emits BOTH a PhaseLogger Decision and a
    BlackBox ``CONTEXT_COMPACTED`` event, joined by ``decision_id``."""

    def _tiny_profile(self, window: int = 1000) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=window,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def _fold_state(self, profile: ModelProfile) -> dict:
        return _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=700,  # 700 > 0.6 × 1000 = 600 → trigger trips
            step_count=10,
            last_compaction_step=0,  # cooldown elapsed
            workflow_id="wf-c1-wire",
            selected_model=profile.name,
        )

    def test_fold_emits_phase_logger_decision_with_keep_full_alternative(
        self, tmp_path
    ) -> None:
        """The Reasoning sink: a ``Decision`` lands in ``decisions.jsonl``
        with ``alternatives=["keep_full"]`` and a non-empty ``decision_id``
        (the join key §7.0)."""
        profile = self._tiny_profile()
        node = _flag_on_evaluate_callable(
            profile=profile, cache_dir=tmp_path
        )
        out = _invoke(
            node, self._fold_state(profile), _config_for_thread("th-wire-1")
        )

        # Sanity: the fold actually ran.
        assert "messages" in out, (
            "fold did NOT run — wiring test cannot assert on its carriers"
        )

        decisions_path = (
            tmp_path / "phase_logs" / "wf-c1-wire" / "decisions.jsonl"
        )
        assert decisions_path.exists(), (
            f"phase_logger decisions.jsonl missing at {decisions_path}"
        )
        lines = [
            __import__("json").loads(line)
            for line in decisions_path.read_text().splitlines()
            if line.strip()
        ]
        # Find the compaction decision among any others the run produced.
        compaction_decisions = [
            d
            for d in lines
            if d.get("phase") == "evaluation"
            and "keep_full" in (d.get("alternatives") or [])
        ]
        assert compaction_decisions, (
            f"no compaction Decision found in {lines!r} — Reasoning sink "
            "did not fire"
        )
        dec = compaction_decisions[0]
        assert dec.get("decision_id"), (
            "compaction Decision is missing decision_id (the §7.0 join key)"
        )
        # Rationale is counts/knobs only — no dropped text, no constraint strings.
        rationale = (dec.get("rationale") or "").lower()
        assert "q-" not in rationale and "a-" not in rationale, (
            f"Decision.rationale leaks dropped message content: {rationale!r}"
        )

    def test_fold_emits_black_box_context_compacted_event(
        self, tmp_path
    ) -> None:
        """The Recording sink: a ``CONTEXT_COMPACTED`` event lands in the
        black_box JSONL with counts/hash/flags."""
        import json as _json

        profile = self._tiny_profile()
        node = _flag_on_evaluate_callable(
            profile=profile, cache_dir=tmp_path
        )
        out = _invoke(
            node, self._fold_state(profile), _config_for_thread("th-wire-2")
        )
        assert "messages" in out, "fold did not run"

        events_path = (
            tmp_path / "black_box_recordings" / "wf-c1-wire" / "trace.jsonl"
        )
        assert events_path.exists(), (
            f"black_box JSONL missing at {events_path}"
        )
        events = [
            _json.loads(line)
            for line in events_path.read_text().splitlines()
            if line.strip()
        ]
        compacted = [
            e for e in events if e["event_type"] == "context_compacted"
        ]
        assert len(compacted) == 1, (
            f"expected exactly one CONTEXT_COMPACTED event; got "
            f"{len(compacted)}: {[e['event_type'] for e in events]!r}"
        )
        details = compacted[0]["details"]
        # Required scalars.
        for key in (
            "tokens_before",
            "tokens_after",
            "turns_folded",
            "observations_cleared",
            "keep_last_k",
            "pinned_kept",
            "must_not_count",
            "constraint_floor_hash",
            "floor_reinjected",
            "floor_exceeded",
            "context_exhausted",
        ):
            assert key in details, (
                f"carrier details missing required key {key!r}: {details!r}"
            )
        # Counts make sense relative to the test fixture.
        assert details["tokens_before"] >= 0
        assert details["floor_exceeded"] is False
        assert details["context_exhausted"] is False

    def test_fold_decision_id_joins_both_carriers(self, tmp_path) -> None:
        """The §7.0 join contract: the Decision's ``decision_id`` MUST also
        appear in the CONTEXT_COMPACTED event's details — without it the
        audit can't tie *what happened* to *why*."""
        import json as _json

        profile = self._tiny_profile()
        node = _flag_on_evaluate_callable(
            profile=profile, cache_dir=tmp_path
        )
        _invoke(
            node, self._fold_state(profile), _config_for_thread("th-wire-3")
        )

        decisions_path = (
            tmp_path / "phase_logs" / "wf-c1-wire" / "decisions.jsonl"
        )
        decisions = [
            _json.loads(line)
            for line in decisions_path.read_text().splitlines()
            if line.strip()
        ]
        fold_decisions = [
            d for d in decisions if "keep_full" in (d.get("alternatives") or [])
        ]
        dec_id = fold_decisions[0]["decision_id"]
        assert dec_id

        events_path = (
            tmp_path / "black_box_recordings" / "wf-c1-wire" / "trace.jsonl"
        )
        events = [
            _json.loads(line)
            for line in events_path.read_text().splitlines()
            if line.strip()
        ]
        evt = next(e for e in events if e["event_type"] == "context_compacted")
        assert evt["details"].get("decision_id") == dec_id, (
            "Recording↔Reasoning join broken: CONTEXT_COMPACTED.details."
            "decision_id does not match the PhaseLogger Decision.decision_id"
        )

    def test_no_carrier_emitted_when_flag_off(self, tmp_path) -> None:
        """Default-OFF must NOT emit either carrier (the prod-safety
        invariant projected to the governance triangle)."""
        import json as _json

        from orchestration.react_loop import build_graph

        cfg = AgentConfig()  # flag default OFF
        graph = build_graph(cfg, cache_dir=tmp_path)
        node = graph.nodes["evaluate"].bound

        state = _minimal_state(
            messages=_fake_pre_fold_msgs(),
            current_token_count=10_000_000,  # would trip any token gate
            workflow_id="wf-c1-off",
        )
        _invoke(node, state, _config_for_thread("th-wire-off"))

        # No CONTEXT_COMPACTED event in the JSONL.
        ev_path = (
            tmp_path / "black_box_recordings" / "wf-c1-off" / "trace.jsonl"
        )
        if ev_path.exists():
            events = [
                _json.loads(line)
                for line in ev_path.read_text().splitlines()
                if line.strip()
            ]
            assert not any(
                e["event_type"] == "context_compacted" for e in events
            ), "CONTEXT_COMPACTED emitted while master flag was OFF"

        # No keep_full-alternative Decision in decisions.jsonl.
        dec_path = tmp_path / "phase_logs" / "wf-c1-off" / "decisions.jsonl"
        if dec_path.exists():
            decisions = [
                _json.loads(line)
                for line in dec_path.read_text().splitlines()
                if line.strip()
            ]
            assert not any(
                "keep_full" in (d.get("alternatives") or []) for d in decisions
            ), "compaction Decision emitted while master flag was OFF"


class TestCarrierDriftGuardUntouched:
    """The §7.0 enrichment decision: ``default_spec()`` is NOT touched, so
    the drift-guard test suite must still see the same four pillars and
    the same required-carrier strings as before C1 landed."""

    def test_default_spec_does_not_require_context_compacted(self) -> None:
        """``CONTEXT_COMPACTED`` is enrichment, not per-phase required.
        Adding it to ``default_spec()`` would false-alarm on every
        non-compaction turn (most of them)."""
        from trust.governance_carrier_spec import default_spec

        spec = default_spec()
        # ``requirements`` is dict[phase_value, tuple[CarrierRule, …]];
        # walk every rule's ``event_value`` and assert ``context_compacted``
        # is not listed for any phase.
        for phase, rules in spec.requirements.items():
            for rule in rules:
                event_value = getattr(rule, "event_value", None)
                assert event_value != "context_compacted", (
                    f"drift-guard breach: context_compacted listed as "
                    f"required for phase={phase}"
                )

    def test_spec_version_unchanged_at_one(self) -> None:
        """Adding C1 must NOT bump the spec version (enrichment, §7.0).
        A version bump would force every downstream consumer of the
        carrier-spec to re-pin; the drift-guard's whole point is that
        enrichment carriers don't cost a version."""
        from trust.governance_carrier_spec import default_spec

        spec = default_spec()
        assert spec.spec_version == 1, (
            f"spec_version unexpectedly bumped to {spec.spec_version} — "
            "C1's CONTEXT_COMPACTED is enrichment and must not move it"
        )


# ════════════════════════════════════════════════════════════════════════════
# Part H — Phase 8: L1 fold-decline live wire (the fail-safe path).
#
# Design §8.0 / §8.2: the L1 result is computed inside the §5.1 fold block
# *before* the ``RemoveMessage`` rewrite is committed. Any ``passed=False``
# ⇒ DECLINE the fold (return today's no-compaction path) and stamp the
# failing criterion on the §7 carrier as ``floor_exceeded=True`` (the gate
# the carrier carries that the audit can read).
#
# The simplest declined-fold case: feed a transcript whose deterministic
# fold *drops* a pinned constraint that has no substring match in the
# rendered summary. We force this by setting up the planner to walk back
# to a cutoff and inject a pinned constraint that is NOT in any preserved
# message — so L1-a (pinned_substring_present) fails on the prepared
# summary, and the fold MUST decline.
# ════════════════════════════════════════════════════════════════════════════


class TestEvaluateNodeL1FoldDeclineWire:
    """When any L1 criterion fails, the fold declines: no ``messages``
    rewrite, no ``last_compaction_step`` stamp, ``truncation_applied`` not
    set, and the carrier ``details`` reflects the gate failure."""

    def _tiny_profile(self, window: int = 1000) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=window,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def test_declines_fold_when_pinned_constraint_missing_from_summary(
        self, tmp_path
    ) -> None:
        """The trip case: a pinned ``must-not`` whose verbatim text does NOT
        survive into the deterministic summary's PINNED block. The L1-a
        gate fails ⇒ the fold declines (NO rewrite, NO stamp).

        We engineer this by registering a pinned constraint string that the
        ``build_message_compaction`` PINNED block CANNOT render verbatim:
        an empty ``success_conditions`` list with NO user constraints would
        render ``(none recorded)`` — so we instead supply a constraint that
        ``derive_pinned_floor`` will mangle by atomization (the `_atomize`
        split-on-" and "). Result: the pinned object's atomized text doesn't
        match what we will assert is "expected" in the summary, *and* (here's
        the actual trick) we poison the summary by monkey-patching
        ``build_message_compaction`` to omit the constraint entirely — the
        most honest expression of "L1 caught a dropped pinned".
        """
        from orchestration import react_loop as _rl
        from services import summarizer as _sm

        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile, cache_dir=tmp_path)

        # Force a summary that LACKS the pinned constraint string. The
        # monkey-patch is local to the test — restored in finally.
        original_build = _sm.build_message_compaction

        def _summary_without_pinned(views, *, keep_last_k, pinned):
            return (
                "SESSION INTENT:\n  test\nSUMMARY:\n  did stuff\n"
                "ARTIFACTS:\n  (none recorded)\nNEXT STEPS:\n  (none recorded)\n"
                "PINNED:\n  (none recorded)\n"  # constraint dropped here
            )

        _sm.build_message_compaction = _summary_without_pinned
        # The react_loop module imported the symbol at module-load time, so
        # we patch THERE too (per Phase-7 lesson on closure-bound services).
        _rl.build_message_compaction = _summary_without_pinned
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=700,
                step_count=10,
                last_compaction_step=0,
                selected_model=profile.name,
                workflow_id="wf-l1-decline",
                # Pinned constraint that will NOT appear in the summary.
                task_understanding={
                    "success_conditions": ["never delete production files"],
                },
            )
            out = _invoke(node, state, _config_for_thread("th-l1-decline-1"))
            # L1 caught it ⇒ no rewrite, no stamp.
            assert "messages" not in out, (
                "L1 fold-decline failed: rewrite committed despite dropped "
                "pinned constraint (the action-triggering class)"
            )
            assert "last_compaction_step" not in out, (
                "L1 fold-decline failed: cooldown stamp landed on a declined "
                "fold (the cooldown only stamps on commit, design §8.0)"
            )
        finally:
            _sm.build_message_compaction = original_build
            _rl.build_message_compaction = original_build

    def test_decline_stamps_l1_failure_on_the_carrier(self, tmp_path) -> None:
        """When the fold declines on an L1 failure, the §7 carrier MUST
        carry ``floor_exceeded=True`` (the audit-readable flag for "the
        rewrite did NOT commit"). This is how the four-pillar audit reads
        a declined fold — there is no separate "L1-declined" wire."""
        import json as _json
        from orchestration import react_loop as _rl
        from services import summarizer as _sm

        profile = self._tiny_profile(window=1000)
        node = _flag_on_evaluate_callable(profile=profile, cache_dir=tmp_path)

        original_build = _sm.build_message_compaction

        def _summary_without_pinned(views, *, keep_last_k, pinned):
            return (
                "SESSION INTENT:\n  test\nSUMMARY:\n  did stuff\n"
                "PINNED:\n  (none recorded)\n"
            )

        _sm.build_message_compaction = _summary_without_pinned
        _rl.build_message_compaction = _summary_without_pinned
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=700,
                step_count=10,
                last_compaction_step=0,
                selected_model=profile.name,
                workflow_id="wf-l1-decline-carrier",
                task_understanding={
                    "success_conditions": ["never delete production files"],
                },
            )
            _invoke(node, state, _config_for_thread("th-l1-decline-2"))

            # Read the recorder JSONL — the §7 carrier MUST exist with
            # ``floor_exceeded=True`` (declined fold).
            trace_path = (
                tmp_path
                / "black_box_recordings"
                / "wf-l1-decline-carrier"
                / "trace.jsonl"
            )
            assert trace_path.exists(), f"recorder JSONL missing: {trace_path}"
            events = [
                _json.loads(line) for line in trace_path.read_text().splitlines()
            ]
            compacted = [
                e for e in events if e["event_type"] == "context_compacted"
            ]
            assert len(compacted) == 1, (
                f"expected exactly one context_compacted carrier on declined "
                f"fold; got {len(compacted)}"
            )
            assert compacted[0]["details"]["floor_exceeded"] is True, (
                "L1 decline did not surface as floor_exceeded=True on the "
                "carrier — the audit can't read the decline"
            )
        finally:
            _sm.build_message_compaction = original_build
            _rl.build_message_compaction = original_build


# ════════════════════════════════════════════════════════════════════════════
# Part I — Phase 8: caller-side sampling gate + L2 eval_capture call (design §8.3).
#
# A NEW gate (no sampler exists in-repo today, Fix D). When the fold
# COMMITS and the sample-rate hits, the §5.1 wire awaits
# ``eval_capture.record(target="compaction_fidelity", ..., config=...)``
# with ``user_id`` and ``task_id`` routed via ``config.configurable``
# (AGENTS.md mandate). When the sample-rate misses (or the fold declined)
# eval_capture is NOT called.
# ════════════════════════════════════════════════════════════════════════════


class TestSamplingGateAndEvalCapture:
    """The caller-side sampling gate: random() < context_compaction_fidelity_sample_rate
    ⇒ ``await eval_capture.record(target="compaction_fidelity", ...)``."""

    def _tiny_profile(self, window: int = 1000) -> ModelProfile:
        return ModelProfile(
            name="tiny",
            litellm_id="openai/tiny",
            tier="fast",
            context_window=window,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    def _build_node_with_sample_rate(self, *, sample_rate: float, cache_dir):
        """A clone of ``_flag_on_evaluate_callable`` carrying the new
        ``context_compaction_fidelity_sample_rate`` field. Returns the
        evaluate node."""
        from orchestration.react_loop import build_graph

        profile = self._tiny_profile(window=1000)
        cfg = AgentConfig(
            context_compact_messages_enabled=True,
            context_compact_trigger_fraction=0.6,
            context_keep_last_k=2,
            context_compact_cooldown_steps=5,
            context_compaction_fidelity_sample_rate=sample_rate,
            models=[profile],
            default_model=profile.name,
        )
        graph = build_graph(cfg, cache_dir=cache_dir)
        return graph.nodes["evaluate"].bound, profile

    def test_sample_rate_zero_skips_eval_capture(self, tmp_path) -> None:
        """``sample_rate=0`` ⇒ no eval_capture.record call (the gate fully
        suppresses; this is the prod-default posture so the L2 path stays
        off until calibration earns its cost)."""
        from services import eval_capture as _ec

        node, profile = self._build_node_with_sample_rate(
            sample_rate=0.0, cache_dir=tmp_path
        )

        # Spy on eval_capture.record (it is the imported symbol the wire calls).
        calls: list[dict] = []
        original = _ec.record

        async def _spy(target, ai_input, ai_response, config, **kw):
            calls.append({"target": target, "config": config, **kw})

        _ec.record = _spy
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=700,
                step_count=10,
                last_compaction_step=0,
                selected_model=profile.name,
                workflow_id="wf-samp-0",
            )
            _invoke(node, state, _config_for_thread("th-samp-0"))
            # No compaction_fidelity capture at sample_rate=0.
            cf_calls = [c for c in calls if c["target"] == "compaction_fidelity"]
            assert len(cf_calls) == 0, (
                f"sample_rate=0 still emitted {len(cf_calls)} fidelity "
                "capture(s) — the gate is leaking"
            )
        finally:
            _ec.record = original

    def test_sample_rate_one_emits_eval_capture_with_identity(
        self, tmp_path
    ) -> None:
        """``sample_rate=1.0`` ⇒ every committed fold emits exactly one
        ``eval_capture.record(target="compaction_fidelity", ...)`` carrying
        ``user_id``/``task_id`` via ``config.configurable`` (design §8.3).
        """
        from services import eval_capture as _ec

        node, profile = self._build_node_with_sample_rate(
            sample_rate=1.0, cache_dir=tmp_path
        )

        calls: list[dict] = []
        original = _ec.record

        async def _spy(target, ai_input, ai_response, config, **kw):
            calls.append(
                {
                    "target": target,
                    "ai_input": ai_input,
                    "ai_response": ai_response,
                    "config": config,
                    **kw,
                }
            )

        _ec.record = _spy
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=700,
                step_count=10,
                last_compaction_step=0,
                selected_model=profile.name,
                workflow_id="wf-samp-1",
                task_id="task-samp-1",
            )
            # The config MUST route user_id/task_id via configurable
            # (services/eval_capture.py:37-38 reads them from there).
            config = {
                "configurable": {
                    "thread_id": "th-samp-1",
                    "user_id": "user-samp-1",
                    "task_id": "task-samp-1",
                }
            }
            _invoke(node, state, config)
            cf_calls = [c for c in calls if c["target"] == "compaction_fidelity"]
            assert len(cf_calls) == 1, (
                f"sample_rate=1 expected exactly one fidelity capture; "
                f"got {len(cf_calls)}"
            )
            # Identity routed via configurable (AGENTS.md §Always).
            captured_cfg = cf_calls[0]["config"]
            assert captured_cfg["configurable"]["user_id"] == "user-samp-1"
            assert captured_cfg["configurable"]["task_id"] == "task-samp-1"
        finally:
            _ec.record = original

    def test_declined_fold_skips_eval_capture_even_at_sample_rate_one(
        self, tmp_path
    ) -> None:
        """The skill's *reported, never gated* posture is for COMMITTED
        folds. A declined fold has no rewrite to grade — emitting a
        fidelity capture on a no-op would be noise (and would skew
        graduation metrics by contaminating the corpus, §8.5)."""
        from orchestration import react_loop as _rl
        from services import eval_capture as _ec
        from services import summarizer as _sm

        node, profile = self._build_node_with_sample_rate(
            sample_rate=1.0, cache_dir=tmp_path
        )

        calls: list[dict] = []
        original_record = _ec.record

        async def _spy(target, ai_input, ai_response, config, **kw):
            calls.append({"target": target})

        _ec.record = _spy

        original_build = _sm.build_message_compaction

        def _summary_without_pinned(views, *, keep_last_k, pinned):
            return "PINNED:\n  (none recorded)\n"

        _sm.build_message_compaction = _summary_without_pinned
        _rl.build_message_compaction = _summary_without_pinned
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=700,
                step_count=10,
                last_compaction_step=0,
                selected_model=profile.name,
                workflow_id="wf-samp-decline",
                task_understanding={
                    "success_conditions": ["never delete production files"],
                },
            )
            _invoke(node, state, _config_for_thread("th-samp-decline"))
            cf_calls = [c for c in calls if c["target"] == "compaction_fidelity"]
            assert len(cf_calls) == 0, (
                "fidelity capture emitted on a DECLINED fold — corpus "
                "contamination risk (§8.5)"
            )
        finally:
            _ec.record = original_record
            _sm.build_message_compaction = original_build
            _rl.build_message_compaction = original_build

    def test_flag_off_skips_eval_capture(self, tmp_path) -> None:
        """Master flag OFF ⇒ no fold ⇒ no fidelity capture. The §10
        byte-identical-when-off invariant extends to the L2 path."""
        from services import eval_capture as _ec

        node = _evaluate_callable()  # flag OFF
        calls: list[dict] = []
        original = _ec.record

        async def _spy(target, ai_input, ai_response, config, **kw):
            calls.append({"target": target})

        _ec.record = _spy
        try:
            state = _minimal_state(
                messages=_fake_pre_fold_msgs(),
                current_token_count=10_000_000,  # would over-trigger if flag ON
                workflow_id="wf-flag-off",
            )
            _invoke(node, state, _config_for_thread("th-flag-off"))
            cf_calls = [c for c in calls if c["target"] == "compaction_fidelity"]
            assert len(cf_calls) == 0
        finally:
            _ec.record = original
