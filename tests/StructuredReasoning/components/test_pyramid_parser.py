"""L3 tests for the pyramid parser.

Failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

import json

import pytest

from StructuredReasoning.components.pyramid_parser import (
    ParseError,
    build_retry_prompt,
    extract_json_object,
    parse_analysis_output,
)
from StructuredReasoning.trust import AnalysisOutput
from tests.StructuredReasoning.trust.test_pyramid_schema import _minimal_valid_payload


# ── Failure paths ──────────────────────────────────────────────────────


class TestParseFailures:
    def test_empty_response_raises_extract(self):
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output("")
        assert exc_info.value.stage == "extract"

    def test_whitespace_only_raises_extract(self):
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output("   \n  \t ")
        assert exc_info.value.stage == "extract"

    def test_no_json_object_raises_extract(self):
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output("Sorry, I cannot answer that.")
        assert exc_info.value.stage == "extract"

    def test_malformed_json_raises_json(self):
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output("{not: valid json}")
        assert exc_info.value.stage == "json"

    def test_top_level_array_rejected_as_json(self):
        # Extractor regex grabs the inner object, but the schema then fails.
        # The wrapper itself ([ {...} ]) cannot be parsed as a top-level
        # object; the regex extracts the inner block which IS a dict, so
        # the failure surfaces at the schema layer, not at json.
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output("[{}]")
        assert exc_info.value.stage == "schema"

    def test_valid_json_invalid_schema_raises_schema(self):
        bad_payload = {"problem_definition": {}}  # missing many required fields
        with pytest.raises(ParseError) as exc_info:
            parse_analysis_output(json.dumps(bad_payload))
        assert exc_info.value.stage == "schema"


# ── Extraction edge cases ──────────────────────────────────────────────


class TestExtractJsonObject:
    def test_strips_fenced_code_block(self):
        wrapped = "Sure! Here you go:\n```json\n{\"a\": 1}\n```\nAnything else?"
        assert extract_json_object(wrapped).strip() == '{"a": 1}'

    def test_handles_unfenced_object_with_prose(self):
        text = 'Some preamble {"a": 1, "b": [1,2]} trailing prose'
        assert json.loads(extract_json_object(text)) == {"a": 1, "b": [1, 2]}

    def test_picks_outermost_object(self):
        text = '{"outer": {"inner": 1}}'
        extracted = extract_json_object(text)
        assert json.loads(extracted) == {"outer": {"inner": 1}}


# ── Happy path ─────────────────────────────────────────────────────────


class TestParseSuccess:
    def test_round_trip_against_schema(self):
        payload = _minimal_valid_payload()
        result = parse_analysis_output(json.dumps(payload))
        assert isinstance(result, AnalysisOutput)
        assert result.governing_thought.statement == payload["governing_thought"]["statement"]

    def test_tolerates_fenced_response(self):
        payload = _minimal_valid_payload()
        wrapped = "```json\n" + json.dumps(payload) + "\n```"
        assert isinstance(parse_analysis_output(wrapped), AnalysisOutput)


# ── Retry prompt ───────────────────────────────────────────────────────


class TestBuildRetryPrompt:
    def test_includes_stage_and_detail(self):
        err = ParseError(stage="json", detail="Expecting ',' delimiter at line 5")
        msg = build_retry_prompt(err)
        assert "json" in msg
        assert "Expecting" in msg
        assert "JSON object" in msg
