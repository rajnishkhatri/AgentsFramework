"""L2 config contract for scripts/generate_test_items.py (Phase 6, FR-23.4).

The governed generator job must ride the SAME identity/capability contract as
the live coach, with exactly two deliberate overrides (the generate_hints.py
precedent): its own eval stream (never masquerading as coach shadow traffic or
the hint-generator stream) and the learner-domain guardrail dropped for
first-party template input. This pins the built config, not a live run — no LLM
is called (invariant: no live LLM in CI).
"""

from __future__ import annotations

from scripts.generate_test_items import (
    TEST_ITEM_TARGET,
    _make_tiered_solver,
    build_generator_config,
)
from services.base_config import default_capable_profile


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


def _stub_solvers() -> tuple:
    """Two recording stub solvers — no graphs, no LLM (L2)."""
    calls: list[tuple[str, object]] = []

    async def fast(item) -> str:
        calls.append(("fast", item.get("difficulty")))
        return "A"

    async def capable(item) -> str:
        calls.append(("capable", item.get("difficulty")))
        return "A"

    return fast, capable, calls


class TestCapableTierRouting:
    """Phase B FR-10 — d >= threshold verifies on the capable tier, the rest
    stay fast, and the knob is OFF by default (None routes nothing up)."""

    def test_default_capable_profile_is_capable_tier(self):
        profile = default_capable_profile()
        assert profile.tier == "capable"

    def test_capable_profile_is_distinct_from_fast(self):
        from services.base_config import default_fast_profile

        assert default_capable_profile().name != default_fast_profile().name

    async def test_items_route_by_difficulty_threshold(self):
        fast, capable, calls = _stub_solvers()
        solve = _make_tiered_solver(fast, capable, 4)
        for difficulty in (1, 3, 4, 5):
            assert await solve({"difficulty": difficulty}) == "A"
        assert calls == [("fast", 1), ("fast", 3), ("capable", 4), ("capable", 5)]

    async def test_missing_or_bad_difficulty_stays_fast(self):
        fast, capable, calls = _stub_solvers()
        solve = _make_tiered_solver(fast, capable, 4)
        await solve({})
        await solve({"difficulty": "5"})  # junk difficulty never escalates
        assert calls == [("fast", None), ("fast", "5")]

    async def test_off_by_default_routes_everything_fast(self):
        fast, capable, calls = _stub_solvers()
        solve = _make_tiered_solver(fast, capable, None)
        await solve({"difficulty": 5})
        assert calls == [("fast", 5)]

    async def test_boundary_below_threshold_rejects_escalation(self):
        """Off-by-one guard: threshold is d >= N, so d == N-1 must stay fast.
        A `>` -> `>=` slip here would silently route d3 to the costly capable
        tier on every run."""
        fast, capable, calls = _stub_solvers()
        solve = _make_tiered_solver(fast, capable, 4)
        await solve({"difficulty": 3})
        assert ("capable", 3) not in calls
        assert calls == [("fast", 3)]

    async def test_invalid_negative_difficulty_never_escalates(self):
        """A malformed negative difficulty is not >= threshold and must fail
        safe onto the fast tier rather than escalating on a sign error."""
        fast, capable, calls = _stub_solvers()
        solve = _make_tiered_solver(fast, capable, 4)
        await solve({"difficulty": -4})
        assert ("capable", -4) not in calls
        assert calls == [("fast", -4)]

    def test_build_generator_config_binds_the_given_profile(self):
        profile = default_capable_profile()
        cfg = build_generator_config(profile)
        assert cfg.default_model == profile.name
        assert [m.name for m in cfg.models] == [profile.name]
