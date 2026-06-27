"""Phase 2 — MessageView adapter unit tests (design §3.1 / §3.2).

Protocol A (pure TDD): failure-paths-first, deterministic, no LLM, no I/O.
The adapter is the **only** place ``BaseMessage`` and the stdlib view meet,
so these tests pin the round-trip invariants that the C1 fold relies on:

  * ``to_views`` extracts ``tool_call_id`` from ToolMessage and AI-issued
    ``tool_calls`` ids — the data plan_fold_cutoff uses to keep Interaction
    Blocks atomic.
  * ``rebuild`` rematerializes the compacted transcript verbatim — no field
    re-ordering, no id rewriting, no silent text mutation.
  * ``mask_observation`` returns a ToolMessage copy with ``content`` swapped
    and ``tool_call_id`` preserved (the masking-key invariant).

These tests must run at L1 budget (<10s) per the agentic testing pyramid.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from orchestration.message_view import (
    MessageView,
    mask_observation,
    rebuild,
    to_views,
)


# ════════════════════════════════════════════════════════════════════════════
# Fixtures — the two ToolMessage shapes from react_loop.py:349,477 are
# byte-identical (both call ``ToolMessage(content=..., tool_call_id=...)``),
# so a single fixture covers the spec. AI tool_calls use the dict shape
# langchain_core canonicalizes ({"id","name","args"}).
# ════════════════════════════════════════════════════════════════════════════


def _ai_with_calls(content: str, ids: list[str]) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[
            {"id": tid, "name": f"tool_{tid}", "args": {"x": 1}} for tid in ids
        ],
    )


def _tool(content: str, *, tool_call_id: str) -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tool_call_id)


# ════════════════════════════════════════════════════════════════════════════
# Shape — MessageView contract (design §3.1).
# ════════════════════════════════════════════════════════════════════════════


class TestMessageViewShape:
    """The dataclass must be a frozen stdlib view with the §3.1 fields."""

    def test_is_frozen_dataclass(self):
        assert is_dataclass(MessageView)
        view = MessageView(role="human", content="x")
        with pytest.raises(FrozenInstanceError):
            view.content = "y"  # type: ignore[misc]

    def test_field_set_matches_design(self):
        names = {f.name for f in fields(MessageView)}
        assert names == {"role", "content", "tool_call_id", "tool_calls"}

    def test_tool_calls_is_id_tuple_per_design(self):
        view = MessageView(role="ai", content="hi", tool_calls=("a", "b"))
        assert isinstance(view.tool_calls, tuple)
        assert view.tool_calls == ("a", "b")
        assert all(isinstance(tc, str) for tc in view.tool_calls)


# ════════════════════════════════════════════════════════════════════════════
# to_views — BaseMessage → MessageView (failure-paths-first).
# ════════════════════════════════════════════════════════════════════════════


class TestToViews:
    """Adapter from langchain_core BaseMessage → stdlib MessageView."""

    def test_empty_list_returns_empty(self):
        assert to_views([]) == []

    def test_system_view_role(self):
        out = to_views([SystemMessage(content="sys")])
        assert out == [MessageView(role="system", content="sys")]

    def test_human_view_role(self):
        out = to_views([HumanMessage(content="hi")])
        assert len(out) == 1
        assert out[0].role == "human"
        assert out[0].content == "hi"
        assert out[0].tool_call_id is None
        assert out[0].tool_calls == ()

    def test_ai_view_without_tool_calls(self):
        out = to_views([AIMessage(content="thinking")])
        assert out == [MessageView(role="ai", content="thinking")]

    def test_ai_view_extracts_only_call_ids(self):
        out = to_views([_ai_with_calls("call_t", ids=["call_a", "call_b"])])
        assert len(out) == 1
        assert out[0].role == "ai"
        assert out[0].content == "call_t"
        # Design §3.1: tool_calls is a tuple of ids, not the full dict.
        assert out[0].tool_calls == ("call_a", "call_b")

    def test_tool_message_react_loop_349_shape(self):
        """Round-trip the ToolMessage shape from react_loop.py:349 (cached branch)."""
        out = to_views([_tool("cached output", tool_call_id="call_X")])
        assert out == [
            MessageView(role="tool", content="cached output", tool_call_id="call_X")
        ]

    def test_tool_message_react_loop_477_shape(self):
        """Round-trip the ToolMessage shape from react_loop.py:477 (uncached branch)."""
        out = to_views([_tool("uncached output", tool_call_id="call_Y")])
        assert out == [
            MessageView(role="tool", content="uncached output", tool_call_id="call_Y")
        ]

    def test_multi_message_order_preserved(self):
        msgs: list[BaseMessage] = [
            SystemMessage(content="sys"),
            HumanMessage(content="hi"),
            _ai_with_calls("a", ids=["1"]),
            _tool("res", tool_call_id="1"),
            AIMessage(content="done"),
        ]
        roles = [v.role for v in to_views(msgs)]
        assert roles == ["system", "human", "ai", "tool", "ai"]

    def test_content_passthrough_unmodified(self):
        # The adapter must NEVER trim, strip, or normalize content (the
        # round-trip rebuild contract depends on byte preservation).
        weird = "  Line 1\n\n  Line 2  "
        out = to_views([HumanMessage(content=weird)])
        assert out[0].content == weird


# ════════════════════════════════════════════════════════════════════════════
# mask_observation — ToolMessage masking (transient).
# ════════════════════════════════════════════════════════════════════════════


class TestMaskObservation:
    """The masking key is tool_call_id; only ToolMessage content is swapped."""

    def test_tool_message_content_replaced(self):
        original = _tool("very long output", tool_call_id="call_X")
        masked = mask_observation(original, "[MASKED]")
        assert isinstance(masked, ToolMessage)
        assert masked.content == "[MASKED]"

    def test_tool_message_tool_call_id_preserved(self):
        original = _tool("very long output", tool_call_id="call_X")
        masked = mask_observation(original, "[MASKED]")
        assert masked.tool_call_id == "call_X"

    def test_tool_message_returns_copy_not_mutation(self):
        original = _tool("very long output", tool_call_id="call_X")
        _ = mask_observation(original, "[MASKED]")
        # Original must be untouched (frozen-in-spirit).
        assert original.content == "very long output"

    def test_non_tool_message_returned_unchanged(self):
        """Safety: ai/human/system pass through; mask is a no-op."""
        ai = AIMessage(content="thinking")
        out = mask_observation(ai, "[MASKED]")
        # Identity OR equality — but content must NOT have been replaced.
        assert isinstance(out, AIMessage)
        assert out.content == "thinking"

    def test_placeholder_empty_string_is_legal(self):
        original = _tool("x", tool_call_id="c")
        masked = mask_observation(original, "")
        assert masked.content == ""
        assert masked.tool_call_id == "c"


# ════════════════════════════════════════════════════════════════════════════
# rebuild — compacted transcript materialization.
# ════════════════════════════════════════════════════════════════════════════


class TestRebuild:
    """rebuild emits: [SystemMessage(summary)?, *preserved, SystemMessage(tail)?]."""

    def test_summary_only_produces_one_system_message(self):
        out = rebuild(summary="S", preserved=[], tail=None)
        assert len(out) == 1
        assert isinstance(out[0], SystemMessage)
        assert out[0].content == "S"

    def test_no_summary_no_tail_returns_preserved_verbatim(self):
        preserved: list[BaseMessage] = [
            HumanMessage(content="h"),
            AIMessage(content="a"),
        ]
        out = rebuild(summary=None, preserved=preserved, tail=None)
        assert out == preserved  # same objects, not copies

    def test_summary_plus_preserved_order(self):
        preserved: list[BaseMessage] = [
            HumanMessage(content="h"),
            AIMessage(content="a"),
        ]
        out = rebuild(summary="S", preserved=preserved, tail=None)
        assert len(out) == 3
        assert isinstance(out[0], SystemMessage) and out[0].content == "S"
        assert out[1:] == preserved

    def test_tail_appended_last(self):
        preserved: list[BaseMessage] = [HumanMessage(content="h")]
        out = rebuild(summary="S", preserved=preserved, tail="floor")
        assert len(out) == 3
        assert out[0].content == "S"
        assert out[1] is preserved[0]
        assert isinstance(out[2], SystemMessage)
        assert out[2].content == "floor"

    def test_empty_summary_string_treated_as_no_summary(self):
        """An empty summary string is a degenerate input; it must NOT inject an
        empty SystemMessage that would later trip the summary_non_empty gate.
        """
        preserved: list[BaseMessage] = [HumanMessage(content="h")]
        out = rebuild(summary="", preserved=preserved, tail=None)
        assert out == preserved

    def test_empty_tail_string_treated_as_no_tail(self):
        preserved: list[BaseMessage] = [HumanMessage(content="h")]
        out = rebuild(summary="S", preserved=preserved, tail="")
        assert len(out) == 2
        assert out[0].content == "S"

    def test_preserved_messages_are_not_copied(self):
        """The compacted suffix must preserve message identity so checkpoint ids
        rematerialize predictably (rebuild is a layout step, not a mutation).
        """
        h = HumanMessage(content="h")
        a = AIMessage(content="a")
        out = rebuild(summary=None, preserved=[h, a], tail=None)
        assert out[0] is h
        assert out[1] is a


# ════════════════════════════════════════════════════════════════════════════
# Property layer — round-trip and structural invariants (Hypothesis).
# ════════════════════════════════════════════════════════════════════════════


_role_strategy = st.sampled_from(["system", "human", "ai"])


@st.composite
def _basemessages(draw):
    role = draw(_role_strategy)
    content = draw(st.text(min_size=0, max_size=32))
    if role == "system":
        return SystemMessage(content=content)
    if role == "human":
        return HumanMessage(content=content)
    ids = draw(
        st.lists(
            st.text(alphabet="abcdef0123456789", min_size=1, max_size=4), max_size=3
        )
    )
    if ids:
        return _ai_with_calls(content, ids=ids)
    return AIMessage(content=content)


class TestRoundTripProperties:
    @given(msgs=st.lists(_basemessages(), max_size=8))
    @settings(deadline=400, max_examples=80)
    def test_to_views_preserves_length_and_role_order(self, msgs):
        views = to_views(msgs)
        assert len(views) == len(msgs)
        for view, msg in zip(views, msgs):
            assert view.role in {"system", "human", "ai", "tool"}

    @given(msgs=st.lists(_basemessages(), max_size=6))
    @settings(deadline=400, max_examples=60)
    def test_rebuild_no_summary_no_tail_is_identity(self, msgs):
        # rebuild(preserved=X) with no decoration must return X verbatim.
        out = rebuild(summary=None, preserved=msgs, tail=None)
        assert out == msgs

    @given(
        content=st.text(min_size=0, max_size=64),
        call_id=st.text(alphabet="abcdef0123456789", min_size=1, max_size=8),
        placeholder=st.text(min_size=0, max_size=16),
    )
    @settings(deadline=400, max_examples=60)
    def test_mask_observation_tool_call_id_invariant(
        self, content, call_id, placeholder
    ):
        original = _tool(content, tool_call_id=call_id)
        masked = mask_observation(original, placeholder)
        assert masked.tool_call_id == call_id
        assert masked.content == placeholder
