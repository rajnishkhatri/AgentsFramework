"""EventBuffer resumption tests.

Per AGENT_UI_ADAPTER_SPRINTS.md S5 / US-5.3.
TDD Protocol B; failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import pytest

from agent_ui_adapter.transport.resumption import EventBuffer, UnknownCursorError


# ─── failure paths first ──────────────────────────────────────────────


def test_unknown_cursor_raises_unknown_cursor_error() -> None:
    buf = EventBuffer()
    buf.append("t1", "1", b"a")
    buf.append("t1", "2", b"b")

    with pytest.raises(UnknownCursorError):
        buf.replay_after("t1", "999")


def test_unknown_thread_raises_unknown_cursor_error() -> None:
    buf = EventBuffer()
    with pytest.raises(UnknownCursorError):
        buf.replay_after("never-seen", "1")


def test_evicted_cursor_raises_unknown_cursor_error() -> None:
    buf = EventBuffer(max_per_thread=3)
    for i in range(1, 6):
        buf.append("t1", str(i), f"e{i}".encode())

    # ids 1 and 2 evicted; current buffer is [3, 4, 5]
    with pytest.raises(UnknownCursorError):
        buf.replay_after("t1", "1")


def test_max_per_thread_must_be_positive() -> None:
    with pytest.raises(ValueError):
        EventBuffer(max_per_thread=0)


# ─── acceptance ───────────────────────────────────────────────────────


def test_replay_after_returns_only_events_after_cursor() -> None:
    buf = EventBuffer()
    buf.append("t1", "1", b"a")
    buf.append("t1", "2", b"b")
    buf.append("t1", "3", b"c")

    assert buf.replay_after("t1", "1") == [b"b", b"c"]
    assert buf.replay_after("t1", "2") == [b"c"]
    assert buf.replay_after("t1", "3") == []


def test_buffer_evicts_oldest_when_max_per_thread_exceeded() -> None:
    buf = EventBuffer(max_per_thread=3)
    for i in range(1, 6):
        buf.append("t1", str(i), f"e{i}".encode())

    # Evicted: 1, 2. Remaining: 3, 4, 5
    assert buf.replay_after("t1", "3") == [b"e4", b"e5"]
    assert buf.has("t1", "3") is True
    assert buf.has("t1", "1") is False

    # Evicted-id resume must error, not silently return wrong slice
    with pytest.raises(UnknownCursorError):
        buf.replay_after("t1", "2")


def test_buffer_isolates_threads() -> None:
    buf = EventBuffer()
    buf.append("a", "1", b"alpha")
    buf.append("b", "1", b"beta")
    buf.append("a", "2", b"alpha2")

    assert buf.replay_after("a", "1") == [b"alpha2"]
    assert buf.replay_after("b", "1") == []
    assert buf.has("a", "1") and not buf.has("b", "alpha")


def test_has_returns_false_for_unknown_thread() -> None:
    buf = EventBuffer()
    assert buf.has("ghost", "1") is False


def test_has_returns_true_only_for_present_id() -> None:
    buf = EventBuffer()
    buf.append("t1", "1", b"a")
    buf.append("t1", "2", b"b")
    assert buf.has("t1", "1") is True
    assert buf.has("t1", "3") is False
