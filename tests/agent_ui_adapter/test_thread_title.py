"""Unit tests for the deterministic thread-title helper (Phase 3 sidebar).

Pure function, failure/edge paths first (TAP-4). The title is derived from the
first user message — no LLM call (the 'seam + tests, no new infra' choice). An
LLM auto-title is a later upgrade behind the same ``title`` field.
"""

from __future__ import annotations

from agent_ui_adapter.server import derive_thread_title


class TestDeriveThreadTitle:
    # ── edge / fallback paths first ──

    def test_empty_input_falls_back(self):
        assert derive_thread_title("") == "New chat"

    def test_whitespace_only_falls_back(self):
        assert derive_thread_title("   \n\t ") == "New chat"

    def test_non_string_falls_back(self):
        assert derive_thread_title(None) == "New chat"  # type: ignore[arg-type]

    # ── shaping ──

    def test_short_message_used_verbatim(self):
        assert derive_thread_title("Plan my trip to Rome") == "Plan my trip to Rome"

    def test_collapses_internal_whitespace_and_newlines(self):
        assert (
            derive_thread_title("Plan my\n  trip   to\tRome")
            == "Plan my trip to Rome"
        )

    def test_long_message_truncated_with_ellipsis(self):
        long = "a " * 100  # 200 chars
        title = derive_thread_title(long)
        assert len(title) <= 60
        assert title.endswith("…")

    def test_truncation_prefers_word_boundary(self):
        msg = "Summarize the quarterly earnings report for the board meeting tomorrow"
        title = derive_thread_title(msg)
        assert len(title) <= 60
        # No partial trailing word before the ellipsis.
        assert "  " not in title
        assert title.startswith("Summarize the quarterly")

    def test_strips_leading_trailing_whitespace(self):
        assert derive_thread_title("  hello  ") == "hello"
