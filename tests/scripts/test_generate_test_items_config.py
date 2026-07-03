"""L2 config contract for scripts/generate_test_items.py (Phase 6, FR-23.4).

The governed generator job must ride the SAME identity/capability contract as
the live coach, with exactly two deliberate overrides (the generate_hints.py
precedent): its own eval stream (never masquerading as coach shadow traffic or
the hint-generator stream) and the learner-domain guardrail dropped for
first-party template input. This pins the built config, not a live run — no LLM
is called (invariant: no live LLM in CI).
"""

from __future__ import annotations

from scripts.generate_test_items import build_generator_config, TEST_ITEM_TARGET


class TestGeneratorConfig:
    def test_eval_target_is_its_own_stream(self):
        # Generation turns must NOT feed the coach shadow corpus or the hint
        # stream — a distinct target keeps the eval streams isolated.
        cfg = build_generator_config()
        assert cfg.eval_capture_target == TEST_ITEM_TARGET
        assert TEST_ITEM_TARGET == "test_item_generator_llm"
        assert cfg.eval_capture_target != "subject_coach"
        assert cfg.eval_capture_target != "hint_generator_llm"

    def test_domain_guardrail_dropped_for_first_party_input(self):
        # The learner-domain condition guards UNTRUSTED utterances; the
        # generator's input is our own rendered template (first-party). The
        # prompt-injection rail still runs; identity + capability gate stay.
        cfg = build_generator_config()
        assert cfg.input_guardrail_accept_condition == ""

    def test_identity_and_capability_gate_preserved(self):
        cfg = build_generator_config()
        assert cfg.agent_name == "subject-coach-english"
        assert cfg.capability_gating_enabled is True
