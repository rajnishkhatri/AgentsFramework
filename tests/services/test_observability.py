"""L2 Contract: FrameworkTelemetry tests (STORY-412).

Tests counter increments, serialization, and JSONL persistence.
"""

from __future__ import annotations

import pytest

from services.observability import FrameworkTelemetry, load_telemetry, save_telemetry


class TestFrameworkTelemetry:
    def test_serialization_roundtrip(self):
        t = FrameworkTelemetry(
            checkpoint_invocations=5,
            rollback_invocations=2,
            rollback_time_saved_ms=1500.0,
            auto_trace_insights=3,
        )
        serialized = t.model_dump_json()
        deserialized = FrameworkTelemetry.model_validate_json(serialized)
        assert deserialized.checkpoint_invocations == 5
        assert deserialized.rollback_invocations == 2
        assert deserialized.rollback_time_saved_ms == 1500.0
        assert deserialized.auto_trace_insights == 3

    def test_increment_checkpoint(self):
        t = FrameworkTelemetry()
        assert t.checkpoint_invocations == 0
        t.increment_checkpoint()
        assert t.checkpoint_invocations == 1
        t.increment_checkpoint()
        assert t.checkpoint_invocations == 2

    def test_increment_rollback(self):
        t = FrameworkTelemetry()
        assert t.rollback_invocations == 0
        assert t.rollback_time_saved_ms == 0.0
        t.increment_rollback(time_saved_ms=500.0)
        assert t.rollback_invocations == 1
        assert t.rollback_time_saved_ms == 500.0
        t.increment_rollback(time_saved_ms=300.0)
        assert t.rollback_invocations == 2
        assert t.rollback_time_saved_ms == 800.0

    def test_defaults(self):
        t = FrameworkTelemetry()
        assert t.checkpoint_invocations == 0
        assert t.rollback_invocations == 0
        assert t.rollback_time_saved_ms == 0.0
        assert t.auto_trace_insights == 0


class TestSaveTelemetry:
    def test_save_creates_jsonl(self, tmp_path):
        t = FrameworkTelemetry(checkpoint_invocations=3)
        save_telemetry(t, output_dir=tmp_path)
        filepath = tmp_path / "framework_telemetry.jsonl"
        assert filepath.exists()
        content = filepath.read_text().strip()
        assert '"checkpoint_invocations":3' in content

    def test_save_appends(self, tmp_path):
        save_telemetry(FrameworkTelemetry(checkpoint_invocations=1), output_dir=tmp_path)
        save_telemetry(FrameworkTelemetry(checkpoint_invocations=2), output_dir=tmp_path)
        filepath = tmp_path / "framework_telemetry.jsonl"
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_save_failure_does_not_crash(self, tmp_path):
        """Write to a non-writable path → logged warning, no exception."""
        bad_path = tmp_path / "nonexistent_subdir" / "deeper"
        # save_telemetry creates dirs, so use a file as dir to force error
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir")
        save_telemetry(
            FrameworkTelemetry(),
            output_dir=blocker / "subdir",
        )


class TestLoadTelemetry:
    def test_load_returns_latest(self, tmp_path):
        save_telemetry(FrameworkTelemetry(checkpoint_invocations=1), output_dir=tmp_path)
        save_telemetry(FrameworkTelemetry(checkpoint_invocations=5), output_dir=tmp_path)
        loaded = load_telemetry(input_dir=tmp_path)
        assert loaded.checkpoint_invocations == 5

    def test_load_nonexistent_returns_defaults(self, tmp_path):
        loaded = load_telemetry(input_dir=tmp_path / "nope")
        assert loaded.checkpoint_invocations == 0

    def test_load_corrupted_returns_defaults(self, tmp_path):
        filepath = tmp_path / "framework_telemetry.jsonl"
        filepath.write_text("NOT VALID JSON\n")
        loaded = load_telemetry(input_dir=tmp_path)
        assert loaded.checkpoint_invocations == 0
