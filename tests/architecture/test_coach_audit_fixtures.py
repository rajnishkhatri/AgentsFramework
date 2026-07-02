"""Mechanical gate for the §13.4 coach audit fixtures (Subject-Coach Phase 2).

The governance-trace-audit skill gains two coach fixtures (design §13.4,
red-first: the context-violation trace must FAIL the audit before the clean
pre-submit trace passes). The audit itself is an LLM skill run — this test is
the DETERMINISTIC lock on the fixture contract, so the fixtures cannot drift
into shapes that no longer exercise the §13.2 headline check:

  - the violation fixture's recorded LLM input carries ALL FOUR answer-bearing
    fields on a pre-submit turn (the coach's corrupt-success analog);
  - the clean fixture carries NONE of them;
  - both are honest coach-shape traces: coach identity on ``task.started``,
    tool vocabulary ⊆ {think, file_io}, token-bearing ``step.executed``, and
    NO ``eval.goal_judge`` (absent-is-expected, ADR-0009 / spec v2);
  - ``evals.json`` binds the violation fixture to a NON-COMPLIANT verdict and
    the clean fixture to a COMPLIANT one, violation listed first (red-first).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_EVALS_DIR = _REPO / "docs" / "skills" / "governance-trace-audit" / "evals"
_FIXTURES = _EVALS_DIR / "fixtures"

VIOLATION_FIXTURE = "trace_coach_context_violation_pre_submit.json"
CLEAN_FIXTURE = "trace_coach_clean_pre_submit.json"

# ADR-0012's four answer-bearing fields — the pre-submit exclusion set.
ANSWER_BEARING_FIELDS = (
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
)

COACH_AGENT_ID = "subject-coach-english"
LEGAL_COACH_TOOLS = {"tool.think", "tool.file_io"}


def _load(name: str) -> list[dict]:
    path = _FIXTURES / name
    assert path.exists(), f"missing coach audit fixture: {path}"
    observations = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(observations, list) and observations
    return observations


def _named(observations: list[dict], prefix: str) -> list[dict]:
    return [o for o in observations if str(o.get("name", "")).startswith(prefix)]


def _llm_input_text(observations: list[dict]) -> str:
    calls = _named(observations, "llm.call")
    assert calls, "fixture has no llm.call observation"
    return " ".join(str(o.get("input", "")) for o in calls)


class TestViolationFixture:
    """The §13.2 corrupt-success analog — asserted BEFORE the clean shape."""

    def test_pre_submit_input_carries_all_four_answer_fields(self):
        observations = _load(VIOLATION_FIXTURE)
        text = _llm_input_text(observations)
        # §13.2 step 1: the derived mode is read from task.started's recorded
        # task_input (the coach_context convention), not a new observation.
        started = _named(observations, "task.started")
        assert started, "fixture has no task.started observation"
        task_input = json.loads(started[0]["input"])["details"]["task_input"]
        assert '"mode": "pre_submit"' in task_input
        for field in ANSWER_BEARING_FIELDS:
            assert field in text, (
                f"violation fixture must show {field!r} reaching the persona "
                "render — otherwise it no longer exercises the headline check"
            )


class TestCleanFixture:
    def test_pre_submit_input_carries_no_answer_field(self):
        observations = _load(CLEAN_FIXTURE)
        text = _llm_input_text(observations)
        for field in ANSWER_BEARING_FIELDS:
            assert field not in text, (
                f"clean fixture leaks {field!r} into the recorded LLM input"
            )


@pytest.mark.parametrize("name", [VIOLATION_FIXTURE, CLEAN_FIXTURE])
class TestCoachShapeInvariants:
    """Both fixtures must be honest coach-shape traces (§13.1)."""

    def test_task_started_carries_coach_identity(self, name: str):
        observations = _load(name)
        started = _named(observations, "task.started")
        assert started, "fixture has no task.started observation"
        payload = str(started[0].get("input", ""))
        assert COACH_AGENT_ID in payload

    def test_tool_vocabulary_is_think_and_file_io_only(self, name: str):
        observations = _load(name)
        tools = {
            str(o["name"]).split(" ")[0]
            for o in observations
            if str(o.get("name", "")).startswith("tool.")
        }
        assert tools <= LEGAL_COACH_TOOLS, (
            f"illegal coach tool carriers {tools - LEGAL_COACH_TOOLS} — the "
            "ADR-0007 gate would have failed at bind time"
        )

    def test_no_inline_goal_judge_observation(self, name: str):
        """Absent-is-expected (ADR-0009 / carrier-spec v2): the fixtures model
        the CORRECT coach shape, which has no inline eval.goal_judge."""
        observations = _load(name)
        assert not _named(observations, "eval.goal_judge")

    def test_token_bearing_step_executed_present(self, name: str):
        observations = _load(name)
        executed = _named(observations, "step.executed")
        assert executed, "token seam: step.executed must be present"
        payload = str(executed[0].get("input", "")) + str(executed[0].get("output", ""))
        assert "tokens_in" in payload and "tokens_out" in payload

    def test_guardrail_check_recorded(self, name: str):
        """Validation pillar: the §6 English-condition verdict must leave a
        guardrail.checked carrier."""
        observations = _load(name)
        assert _named(observations, "guardrail.checked")


def _contract_carriers(observations: list[dict]) -> list[dict]:
    carriers = []
    for obs in _named(observations, "guardrail.checked"):
        payload = json.loads(obs["input"])
        if payload.get("details", {}).get("guardrail") == "coach_context_contract":
            carriers.append(payload["details"])
    return carriers


class TestContractCarrier:
    """§13 audit finding F1: every coach turn records ONE
    ``coach_context_contract`` carrier — the applied (fail-closed) mode plus
    the answer-field render/strip testimony. The fixtures must model it so
    the skill's carrier-first mode derivation is exercised."""

    @pytest.mark.parametrize("name", [VIOLATION_FIXTURE, CLEAN_FIXTURE])
    def test_exactly_one_contract_carrier(self, name: str):
        carriers = _contract_carriers(_load(name))
        assert len(carriers) == 1, "one contract carrier per coach turn"
        assert carriers[0]["mode"] == "pre_submit"
        assert carriers[0]["answer_fields_rendered"] == []

    def test_violation_models_a_formatter_bypass(self):
        """The carrier truthfully reports the formatter stripped all four
        fields — yet the llm.call input carries them: the contradiction the
        §13.2 check must flag (fields bypassed the formatter path)."""
        carriers = _contract_carriers(_load(VIOLATION_FIXTURE))
        assert set(carriers[0]["answer_fields_stripped"]) == set(ANSWER_BEARING_FIELDS)

    def test_clean_fixture_had_nothing_to_strip(self):
        """Clean shape: the BFF strip held upstream, so the formatter saw no
        answer-bearing fields at all."""
        carriers = _contract_carriers(_load(CLEAN_FIXTURE))
        assert carriers[0]["answer_fields_stripped"] == []


class TestEvalsBinding:
    def test_violation_binds_non_compliant_before_clean_compliant(self):
        evals = json.loads((_EVALS_DIR / "evals.json").read_text(encoding="utf-8"))
        entries = evals["evals"]
        by_fixture: dict[str, tuple[int, dict]] = {}
        for idx, entry in enumerate(entries):
            for file in entry.get("files", []):
                by_fixture[Path(file).name] = (idx, entry)

        assert VIOLATION_FIXTURE in by_fixture, "violation fixture not in evals.json"
        assert CLEAN_FIXTURE in by_fixture, "clean fixture not in evals.json"

        violation_idx, violation = by_fixture[VIOLATION_FIXTURE]
        clean_idx, clean = by_fixture[CLEAN_FIXTURE]
        assert violation_idx < clean_idx, (
            "red-first: the violation eval must precede the clean eval"
        )

        violation_text = json.dumps(violation)
        assert "NON-COMPLIANT" in violation_text
        clean_expected = str(clean.get("expected_output", ""))
        assert "NON-COMPLIANT" not in clean_expected
        assert "COMPLIANT" in clean_expected
