"""Tests for GoalJudge corpus export helpers (Stage 5 failure_mode surface)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing the export script from tests/.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
import tempfile
import uuid

from scripts.export_goaljudge_corpus import _case_map_from_jsonl, _resolve_failure_mode


class TestResolveFailureMode:
    def test_prefers_verdict_axis_when_present(self) -> None:
        verdict = {"failure_mode": "partial-counted-as-full"}
        assert _resolve_failure_mode(verdict, "fabricated-progress") == (
            "partial-counted-as-full"
        )

    def test_blank_verdict_falls_back_to_registry_target_code(self) -> None:
        assert _resolve_failure_mode({}, "fabricated-progress") == "fabricated-progress"

    def test_none_string_verdict_falls_back_to_registry(self) -> None:
        assert _resolve_failure_mode({"failure_mode": "none"}, "subtask-dropped") == (
            "subtask-dropped"
        )

    def test_unknown_target_code_returns_none(self) -> None:
        assert _resolve_failure_mode({}, "unknown") is None

    def test_invalid_verdict_code_falls_back_when_target_valid(self) -> None:
        assert _resolve_failure_mode(
            {"failure_mode": "not-a-code"}, "fluent-evasion"
        ) == ("fluent-evasion")


class TestCaseMapFromJsonl:
    def test_maps_fresh_authored_case_id(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-F-001").hex
        row = {"case_id": "GJ-F-001", "trace_id": trace_id}
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(json.dumps(row) + "\n")
            path = fh.name

        case_map = _case_map_from_jsonl(path)

        assert trace_id in case_map
        assert case_map[trace_id].stratum == "representative"
        assert case_map[trace_id].provenance == "live"
        assert case_map[trace_id].target_code == "unknown"

    def test_maps_stress_case_id(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-STRESS-001").hex
        row = {"case_id": "GJ-STRESS-001", "trace_id": trace_id}
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(json.dumps(row) + "\n")
            path = fh.name

        case_map = _case_map_from_jsonl(path)

        assert trace_id in case_map
        assert case_map[trace_id].provenance == "synthetic"
        assert case_map[trace_id].target_code == "fabricated-progress"
