"""L2 contract tests for GoalJudgeRuntimeConfigReader.

Failure paths first (TAP-4): malformed/extra keys, never-read fail-dark,
unset URI zero I/O. Acceptance paths: valid parse, TTL cache, stale-on-error.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time
from pydantic import ValidationError

from services.goal_judge_runtime_config import (
    GoalJudgeRuntimeConfig,
    GoalJudgeRuntimeConfigReader,
    InMemoryGoalJudgeConfigReader,
    ResolvedGoalJudgeConfig,
)


_VALID_JSON = {
    "schema_version": 1,
    "goal_judge_enabled": True,
    "goal_judge_downgrade_enabled": False,
    "updated_at": "2026-06-02T20:00:00Z",
    "updated_by": "tester",
}


# ─────────────────────────────────────────────────────────────────────
# Schema validation (failure first)
# ─────────────────────────────────────────────────────────────────────


class TestGoalJudgeRuntimeConfigSchema:
    def test_rejects_unknown_key_extra_forbid(self):
        payload = {**_VALID_JSON, "goal_judge_enable": True}
        with pytest.raises(ValidationError):
            GoalJudgeRuntimeConfig.model_validate(payload)

    def test_accepts_minimal_two_key_payload(self):
        cfg = GoalJudgeRuntimeConfig.model_validate(
            {
                "goal_judge_enabled": False,
                "goal_judge_downgrade_enabled": False,
            }
        )
        assert cfg.schema_version == 1
        assert cfg.updated_by == "unknown"


# ─────────────────────────────────────────────────────────────────────
# Reader failure paths
# ─────────────────────────────────────────────────────────────────────


class TestReaderFailurePaths:
    def test_unset_uri_performs_zero_io_uses_env_fallback(self, monkeypatch):
        monkeypatch.delenv("GOAL_JUDGE_CONFIG_URI", raising=False)
        monkeypatch.setenv("GOAL_JUDGE_ENABLED", "true")
        monkeypatch.setenv("GOAL_JUDGE_DOWNGRADE_ENABLED", "false")

        reader = GoalJudgeRuntimeConfigReader(
            uri=None,
            env_enabled=True,
            env_downgrade=False,
            defaults_enabled=False,
            defaults_downgrade=False,
        )
        resolved = reader.get()
        assert resolved.goal_judge_enabled is True
        assert resolved.goal_judge_downgrade_enabled is False
        assert resolved.source == "env"

    def test_malformed_json_fail_dark_when_never_read(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not json", encoding="utf-8")
        uri = f"file://{bad_file}"

        reader = GoalJudgeRuntimeConfigReader(
            uri=uri,
            ttl_s=30,
            timeout_s=2,
            defaults_enabled=False,
            defaults_downgrade=False,
        )
        resolved = reader.get()
        assert resolved.goal_judge_enabled is False
        assert resolved.goal_judge_downgrade_enabled is False
        assert resolved.source == "default"

    def test_extra_key_in_file_fail_dark_when_never_read(self, tmp_path):
        bad_file = tmp_path / "typo.json"
        bad_file.write_text(
            json.dumps(
                {
                    "goal_judge_enabled": True,
                    "goal_judge_downgrade_enabled": True,
                    "goal_judge_enable": True,
                }
            ),
            encoding="utf-8",
        )
        reader = GoalJudgeRuntimeConfigReader(
            uri=f"file://{bad_file}",
            defaults_enabled=False,
            defaults_downgrade=False,
        )
        resolved = reader.get()
        assert resolved.goal_judge_enabled is False
        assert resolved.source == "default"


# ─────────────────────────────────────────────────────────────────────
# Reader acceptance paths
# ─────────────────────────────────────────────────────────────────────


class TestReaderAcceptance:
    def test_reads_valid_file_uri(self, tmp_path):
        cfg_file = tmp_path / "goal_judge_config.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")

        reader = GoalJudgeRuntimeConfigReader(uri=f"file://{cfg_file}")
        resolved = reader.get()

        assert resolved.goal_judge_enabled is True
        assert resolved.goal_judge_downgrade_enabled is False
        assert resolved.source == f"file:{cfg_file}"
        assert resolved.schema_version == 1
        assert resolved.updated_by == "tester"

    def test_ttl_cache_avoids_re_read(self, tmp_path):
        cfg_file = tmp_path / "goal_judge_config.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")

        read_count = 0
        original_read = GoalJudgeRuntimeConfigReader._read_file_text

        def counting_read(self, path: Path) -> str:
            nonlocal read_count
            read_count += 1
            return original_read(self, path)

        reader = GoalJudgeRuntimeConfigReader(
            uri=f"file://{cfg_file}", ttl_s=30
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                GoalJudgeRuntimeConfigReader,
                "_read_file_text",
                counting_read,
            )
            reader.get()
            reader.get()
        assert read_count == 1

    @freeze_time("2026-06-02T12:00:00")
    def test_ttl_expiry_triggers_refresh(self, tmp_path):
        cfg_file = tmp_path / "goal_judge_config.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")

        read_count = 0
        original_read = GoalJudgeRuntimeConfigReader._read_file_text

        def counting_read(self, path: Path) -> str:
            nonlocal read_count
            read_count += 1
            return original_read(self, path)

        reader = GoalJudgeRuntimeConfigReader(
            uri=f"file://{cfg_file}", ttl_s=30
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                GoalJudgeRuntimeConfigReader,
                "_read_file_text",
                counting_read,
            )
            reader.get()
            with freeze_time("2026-06-02T12:00:31"):
                reader.get()
        assert read_count == 2

    def test_stale_on_error_after_successful_read(self, tmp_path):
        cfg_file = tmp_path / "goal_judge_config.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")

        reader = GoalJudgeRuntimeConfigReader(
            uri=f"file://{cfg_file}", ttl_s=0
        )
        first = reader.get()
        assert first.source.startswith("file:")

        cfg_file.write_text("{broken", encoding="utf-8")
        stale = reader.get()
        assert stale.goal_judge_enabled is True
        assert stale.source == "stale"

    def test_mocked_gcs_read(self):
        blob = MagicMock()
        blob.download_as_text.return_value = json.dumps(_VALID_JSON)
        bucket = MagicMock()
        bucket.blob.return_value = blob
        client = MagicMock()
        client.bucket.return_value = bucket

        reader = GoalJudgeRuntimeConfigReader(
            uri="gs://my-bucket/ops/goal_judge_config.json",
            gcs_client=client,
        )
        resolved = reader.get()
        assert resolved.goal_judge_enabled is True
        assert resolved.source == "gcs:ops/goal_judge_config.json"
        client.bucket.assert_called_once_with("my-bucket")
        bucket.blob.assert_called_once_with("ops/goal_judge_config.json")

    def test_in_memory_reader_for_tests(self):
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=True,
            goal_judge_downgrade_enabled=True,
            source="test",
        )
        resolved = reader.get()
        assert resolved.goal_judge_enabled is True
        assert resolved.goal_judge_downgrade_enabled is True
        assert resolved.source == "test"


class TestHealthEcho:
    def test_health_posture_from_cache_without_io(self, tmp_path):
        cfg_file = tmp_path / "goal_judge_config.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        reader = GoalJudgeRuntimeConfigReader(uri=f"file://{cfg_file}")
        reader.get()
        echo = reader.health_posture()
        assert echo["enabled"] is True
        assert echo["downgrade_enabled"] is False
        assert echo["source"].startswith("file:")
