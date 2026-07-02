"""L2 contract tests for SubjectCoachJudgeConfigReader (Phase 2, design §7.2).

Pattern: ``test_goal_judge_runtime_config.py`` (Protocol B3 time-mocked TTL).
Failure paths first (TAP-4): defaults-OFF is THE headline contract — every
flag defaults OFF and the CI path never sees a live LLM; malformed config
fails DARK (off), never open. Stale-cache / flag-flip paths before the
valid-read acceptance path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.conftest import freeze_time

from services.subject_coach_judge_runtime_config import (
    InMemorySubjectCoachJudgeConfigReader,
    SubjectCoachJudgeConfigReader,
    SubjectCoachJudgeRuntimeConfig,
)

_VALID_JSON = {
    "schema_version": 1,
    "coach_grader_judge_enabled": True,
    "coach_pedagogy_judge_enabled": True,
    "coach_judge_sample_rate": 0.25,
    "coach_leakage_gate_enabled": False,
    "updated_at": "2026-07-02T20:00:00Z",
    "updated_by": "tester",
}

_ALL_ENV = (
    "COACH_JUDGE_CONFIG_URI",
    "COACH_GRADER_JUDGE_ENABLED",
    "COACH_PEDAGOGY_JUDGE_ENABLED",
    "COACH_JUDGE_SAMPLE_RATE",
    "COACH_LEAKAGE_GATE_ENABLED",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ALL_ENV:
        monkeypatch.delenv(name, raising=False)


# ─────────────────────────────────────────────────────────────────────
# THE headline contract: everything defaults OFF (no live LLM in CI).
# ─────────────────────────────────────────────────────────────────────


class TestDefaultsOff:
    def test_no_uri_no_env_all_flags_off(self):
        resolved = SubjectCoachJudgeConfigReader(uri=None).get()
        assert resolved.coach_grader_judge_enabled is False
        assert resolved.coach_pedagogy_judge_enabled is False
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.coach_judge_sample_rate == pytest.approx(0.10)
        assert resolved.source == "default"

    def test_in_memory_reader_defaults_off(self):
        resolved = InMemorySubjectCoachJudgeConfigReader().get()
        assert resolved.coach_grader_judge_enabled is False
        assert resolved.coach_pedagogy_judge_enabled is False
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.coach_judge_sample_rate == pytest.approx(0.10)

    def test_leakage_gate_defaults_off_even_when_judges_enabled_in_file(self, tmp_path):
        """ADR-0008: the gate flips only post-floor — enabling the judges must
        not implicitly enable the gate."""
        cfg = {
            "coach_grader_judge_enabled": True,
            "coach_pedagogy_judge_enabled": True,
        }
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(cfg), encoding="utf-8")
        resolved = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}").get()
        assert resolved.coach_pedagogy_judge_enabled is True
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.coach_judge_sample_rate == pytest.approx(0.10)


# ─────────────────────────────────────────────────────────────────────
# Schema failure paths
# ─────────────────────────────────────────────────────────────────────


class TestSchemaRejections:
    def test_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            SubjectCoachJudgeRuntimeConfig.model_validate(
                {**_VALID_JSON, "coach_grader_judge_enable": True}
            )

    def test_rejects_out_of_range_sample_rate(self):
        with pytest.raises(ValidationError):
            SubjectCoachJudgeRuntimeConfig.model_validate(
                {**_VALID_JSON, "coach_judge_sample_rate": 1.5}
            )
        with pytest.raises(ValidationError):
            SubjectCoachJudgeRuntimeConfig.model_validate(
                {**_VALID_JSON, "coach_judge_sample_rate": -0.1}
            )


# ─────────────────────────────────────────────────────────────────────
# Reader failure paths (fail DARK, stale-on-error)
# ─────────────────────────────────────────────────────────────────────


class TestReaderFailurePaths:
    def test_malformed_file_never_read_fails_dark(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        resolved = SubjectCoachJudgeConfigReader(uri=f"file://{bad}").get()
        assert resolved.coach_grader_judge_enabled is False
        assert resolved.coach_pedagogy_judge_enabled is False
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.source == "default"

    def test_stale_on_error_preserves_last_good_posture(self, tmp_path):
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        reader = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}", ttl_s=0)
        first = reader.get()
        assert first.coach_pedagogy_judge_enabled is True
        # Corrupt the file → the last-good posture is served, tagged stale —
        # a transient config outage must not silently flip the judges off/on.
        cfg_file.write_text("{not json", encoding="utf-8")
        resolved = reader.get()
        assert resolved.source == "stale"
        assert resolved.coach_pedagogy_judge_enabled is True
        assert resolved.coach_judge_sample_rate == pytest.approx(0.25)

    def test_invalid_env_sample_rate_degrades_to_default(self, monkeypatch):
        monkeypatch.setenv("COACH_GRADER_JUDGE_ENABLED", "true")
        monkeypatch.setenv("COACH_JUDGE_SAMPLE_RATE", "lots")
        resolved = SubjectCoachJudgeConfigReader(uri=None).get()
        assert resolved.coach_grader_judge_enabled is True
        assert resolved.coach_judge_sample_rate == pytest.approx(0.10)

    def test_out_of_range_env_sample_rate_clamped(self, monkeypatch):
        monkeypatch.setenv("COACH_PEDAGOGY_JUDGE_ENABLED", "1")
        monkeypatch.setenv("COACH_JUDGE_SAMPLE_RATE", "7")
        resolved = SubjectCoachJudgeConfigReader(uri=None).get()
        assert resolved.coach_judge_sample_rate == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────
# Acceptance paths
# ─────────────────────────────────────────────────────────────────────


class TestReaderAcceptance:
    def test_reads_valid_file_uri(self, tmp_path):
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        resolved = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}").get()
        assert resolved.coach_grader_judge_enabled is True
        assert resolved.coach_pedagogy_judge_enabled is True
        assert resolved.coach_judge_sample_rate == pytest.approx(0.25)
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.source == f"file:{cfg_file}"
        assert resolved.updated_by == "tester"

    def test_env_fallback_when_uri_unset(self, monkeypatch):
        monkeypatch.setenv("COACH_GRADER_JUDGE_ENABLED", "true")
        monkeypatch.setenv("COACH_LEAKAGE_GATE_ENABLED", "false")
        resolved = SubjectCoachJudgeConfigReader(uri=None).get()
        assert resolved.coach_grader_judge_enabled is True
        assert resolved.coach_leakage_gate_enabled is False
        assert resolved.source == "env"

    def test_ttl_cache_avoids_re_read(self, tmp_path):
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        read_count = 0
        original = SubjectCoachJudgeConfigReader._read_file_text

        def counting(self, path: Path) -> str:
            nonlocal read_count
            read_count += 1
            return original(self, path)

        reader = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}", ttl_s=30)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SubjectCoachJudgeConfigReader, "_read_file_text", counting)
            reader.get()
            reader.get()
        assert read_count == 1

    def test_ttl_expiry_triggers_refresh(self, tmp_path):
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        read_count = 0
        original = SubjectCoachJudgeConfigReader._read_file_text

        def counting(self, path: Path) -> str:
            nonlocal read_count
            read_count += 1
            return original(self, path)

        reader = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}", ttl_s=30)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(SubjectCoachJudgeConfigReader, "_read_file_text", counting)
            with freeze_time("2026-07-02T12:00:00"):
                reader.get()
            with freeze_time("2026-07-02T12:00:31"):
                reader.get()
        assert read_count == 2

    def test_health_posture_serves_cache_only(self, tmp_path):
        cfg_file = tmp_path / "coach.json"
        cfg_file.write_text(json.dumps(_VALID_JSON), encoding="utf-8")
        reader = SubjectCoachJudgeConfigReader(uri=f"file://{cfg_file}", ttl_s=30)
        reader.get()
        posture = reader.health_posture()
        assert posture["grader_judge_enabled"] is True
        assert posture["pedagogy_judge_enabled"] is True
        assert posture["sample_rate"] == pytest.approx(0.25)
        assert posture["leakage_gate_enabled"] is False
