"""L1/L2 contract tests for the memory multi-session trace analyzer.

Failure-paths-first (Anti-Pattern 6 / Check 4): the THREE hard-0 violations
this analyzer exists to catch — a cross-user leak, a stale value after an
update, and a fabricated memory on an abstention probe — are asserted FIRST,
each from a hand-built event/row fixture. The rate metrics come after.

Pure / mocked — no live LLM, no network. The analyzer's source readers are
reused from analyze_planning_traces; here we inject events_by_row directly so
the scorer is tested in isolation (Pattern 6 mock provider). See
``docs/plans/memory_multisession_e2e_stress.plan.md`` §5.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_ANALYZER = _AGENT_ROOT / "scripts" / "analyze_memory_traces.py"


def _load():
    spec = importlib.util.spec_from_file_location("analyze_mem", _ANALYZER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _recall_event(user_id: str, count: int) -> dict:
    return {
        "event_type": "memory_recalled",
        "details": {"user_id": user_id, "count": count, "query_len": 10},
    }


def _store_event(user_id: str, key: str) -> dict:
    return {
        "event_type": "memory_stored",
        "details": {"user_id": user_id, "key": key},
    }


# ─────────────────────────────────────────────────────────────────────────────
# THE THREE HARD-0 VIOLATIONS (failure-paths-first)
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossUserLeakGuard:
    def test_leak_detected_when_probe_recalls_another_users_fact(self) -> None:
        """A leak-control probe (user_B) whose recall returns count>=1 names a
        foreign fact — a cross-user leak. HARD-0."""
        mod = _load()
        rows = [
            {
                "case": "MEM-LEAK-x",
                "ability": "leak-control",
                "user_id": "userB",
                "response_text": "You prefer metric units.",
                "probe_recall_expected": False,
            }
        ]
        # The recall carrier fired with count=1 under userB — leak.
        events = {"MEM-LEAK-x": [_recall_event("userB", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["cross_user_leaks"] >= 1
        assert mod.gate_failures(summary), "a leak must fail the gate unconditionally"

    def test_no_leak_when_leak_control_recalls_nothing(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-LEAK-x",
                "ability": "leak-control",
                "user_id": "userB",
                "response_text": "I don't have any record of that.",
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-LEAK-x": [_recall_event("userB", 0)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["cross_user_leaks"] == 0

    def test_no_leak_when_recall_fires_but_answer_abstains(self) -> None:
        """The gate is ANSWER-grounded, not count-grounded (P0 #2a follow-up):
        the `mem:` bridge collapses per-case users to the real owner, so a
        control probe legitimately recalls the OWNER's own memories (count>=1)
        and then correctly abstains. Bare recall_count must NOT trip the leak
        gate; only a foreign user_id OR an answer that asserts a remembered fact
        does. This is the exact false-positive the live smoke surfaced
        (count=1, foreign=[], clean abstention)."""
        mod = _load()
        rows = [
            {
                "case": "MEM-LEAK-collapse",
                "ability": "leak-control",
                "user_id": "userleak01",
                "response_text": (
                    "I'm sorry, but I don't have any previous interactions or "
                    "memory of your preferences."
                ),
                "probe_recall_expected": False,
            }
        ]
        # Recall fired count=1 under the SAME (collapsed) user — no foreign id.
        events = {"MEM-LEAK-collapse": [_recall_event("userleak01", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["cross_user_leaks"] == 0
        assert not mod.gate_failures(summary)

    def test_leak_when_foreign_user_id_in_carrier(self) -> None:
        """A recall carrier naming a DIFFERENT user_id is a genuine cross-user
        leak regardless of the answer text — the strongest leak evidence."""
        mod = _load()
        rows = [
            {
                "case": "MEM-LEAK-foreign",
                "ability": "leak-control",
                "user_id": "userB",
                "response_text": "I don't think I have anything for you.",
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-LEAK-foreign": [_recall_event("userA", 1)]}  # foreign!
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["cross_user_leaks"] >= 1
        assert mod.gate_failures(summary)


class TestKnowledgeUpdateStaleValue:
    def test_stale_value_detected(self) -> None:
        """An update probe whose answer still contains the OLD value X (not the
        corrected Y) is a stale-value failure. HARD-0."""
        mod = _load()
        rows = [
            {
                "case": "MEM-UPDATE-units",
                "ability": "knowledge-update",
                "user_id": "userU",
                "response_text": "I'll use imperial units as you prefer.",
                "expect_substring": ["metric"],
                "stale_substring": ["imperial"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-UPDATE-units": [_recall_event("userU", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["stale_after_update"] >= 1
        assert mod.gate_failures(summary)

    def test_corrected_value_passes(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-UPDATE-units",
                "ability": "knowledge-update",
                "user_id": "userU",
                "response_text": "I'll use metric units.",
                "expect_substring": ["metric"],
                "stale_substring": ["imperial"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-UPDATE-units": [_recall_event("userU", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["stale_after_update"] == 0


class TestAbstentionFabrication:
    def test_fabricated_memory_detected(self) -> None:
        """An abstention probe (nothing seeded) whose recall fired count>=1 OR
        whose answer claims to remember is a fabricated memory. HARD-0."""
        mod = _load()
        rows = [
            {
                "case": "MEM-ABSTAIN-pet",
                "ability": "abstention",
                "user_id": "userA",
                "response_text": "I remember your pet is named Rex.",
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-ABSTAIN-pet": [_recall_event("userA", 2)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["fabricated_memories"] >= 1
        assert mod.gate_failures(summary)

    def test_proper_abstention_passes(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-ABSTAIN-pet",
                "ability": "abstention",
                "user_id": "userA",
                "response_text": "I don't have any information about your pet.",
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-ABSTAIN-pet": [_recall_event("userA", 0)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["fabricated_memories"] == 0

    def test_abstention_passes_when_recall_fires_but_answer_disclaims(self) -> None:
        """Answer-grounded (P0 #2a follow-up): under user-collapse the recall
        carrier fires count>=1 even on an abstention probe, but a clean
        disclaimer is NOT a fabrication. Only an answer that CLAIMS a remembered
        fact is. Mirrors the live smoke false-positive (count=1, claims=False)."""
        mod = _load()
        rows = [
            {
                "case": "MEM-ABSTAIN-collapse",
                "ability": "abstention",
                "user_id": "userabs01",
                "response_text": "I don't have any information about your pet's name.",
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-ABSTAIN-collapse": [_recall_event("userabs01", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["fabricated_memories"] == 0
        assert not mod.gate_failures(summary)


# ─────────────────────────────────────────────────────────────────────────────
# RATE METRICS (after the hard-0 gates)
# ─────────────────────────────────────────────────────────────────────────────


class TestRecallRates:
    def test_recall_hit_counted(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RECALL-units",
                "ability": "recall",
                "user_id": "userP",
                "response_text": "I'll use metric units when summarizing.",
                "expect_substring": ["metric"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-RECALL-units": [_recall_event("userP", 1)]}
        summary = mod.score_run(rows, events)
        rec = summary["abilities"]["recall"]
        assert rec["hits"] == 1
        assert rec["rate"] == 1.0

    def test_recall_miss_counted(self) -> None:
        """A recall probe whose carrier fired count=0 (or whose answer lacks the
        expected substring) is a miss — counted, not a hard-0 (recall misses are
        cheap; precision violations are not)."""
        mod = _load()
        rows = [
            {
                "case": "MEM-RECALL-units",
                "ability": "recall",
                "user_id": "userP",
                "response_text": "Sure, here's a summary.",
                "expect_substring": ["metric"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-RECALL-units": [_recall_event("userP", 0)]}
        summary = mod.score_run(rows, events)
        rec = summary["abilities"]["recall"]
        assert rec["hits"] == 0
        assert any("MISS" in m for m in rec["mismatches"])

    def test_multi_session_needs_two_evidence(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-MULTI-trip",
                "ability": "multi-session",
                "user_id": "userM",
                "response_text": "Your trip to Japan with a 3000 dollar budget.",
                "expect_substring": ["Japan", "3000"],
                "probe_recall_expected": True,
            }
        ]
        # count>=2 == both evidence facts recalled.
        events = {"MEM-MULTI-trip": [_recall_event("userM", 2)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["multi-session"]["hits"] == 1


class TestMissingTrace:
    def test_missing_trace_recorded_not_crash(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RECALL-x",
                "ability": "recall",
                "user_id": "userP",
                "response_text": "",
                "expect_substring": ["metric"],
                "probe_recall_expected": True,
            }
        ]
        summary = mod.score_run(rows, {})  # no events for the case
        rec = summary["abilities"]["recall"]
        assert rec["missing_trace"] == 1


class TestGatePassesClean:
    def test_clean_batch_passes_gate(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RECALL-units",
                "ability": "recall",
                "user_id": "userP",
                "response_text": "metric units it is",
                "expect_substring": ["metric"],
                "probe_recall_expected": True,
            },
            {
                "case": "MEM-ABSTAIN-pet",
                "ability": "abstention",
                "user_id": "userA",
                "response_text": "I have no record of a pet.",
                "probe_recall_expected": False,
            },
        ]
        events = {
            "MEM-RECALL-units": [_recall_event("userP", 1)],
            "MEM-ABSTAIN-pet": [_recall_event("userA", 0)],
        }
        summary = mod.score_run(rows, events)
        assert mod.gate_failures(summary) == []


class TestDeterminism:
    def test_score_run_is_deterministic(self) -> None:
        """Check 7 determinism: scoring the same input twice is identical."""
        mod = _load()
        rows = [
            {
                "case": "MEM-RECALL-units",
                "ability": "recall",
                "user_id": "userP",
                "response_text": "metric",
                "expect_substring": ["metric"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-RECALL-units": [_recall_event("userP", 1)]}
        assert mod.score_run(rows, events) == mod.score_run(rows, events)


class TestMemSessionIdJoin:
    """The probe→trace join key: the spec installs a *client* thread
    `mem:{mem_id}:s{idx}:{user}:{trace}`, but the BACKEND
    (`goaljudge_saturation_bridge.parse_goaljudge_thread_id`) rewrites the
    Langfuse sessionId to `session-{mem_id.lower()}-s{idx}`. The analyzer must
    join on the backend's form — querying the raw `mem:` string 404s on every
    probe (the defect this regression-guards: P0 #2a, hermes_adoptions_design
    §10.5)."""

    def test_uses_backend_rewritten_session_id(self) -> None:
        mod = _load()
        row = {
            "mem_id": "MEM-0401",
            "session_idx": 3,
            "user_id": "userpers01",
            "probe_trace_id": "70a1bbd8a21bec8a9e97a33611ef0b7c",
        }
        # NOT the client `mem:` form, and NOT trace_id/user_id dependent.
        assert mod._mem_session_id(row) == "session-mem-0401-s3"

    def test_lowercases_mem_id_to_match_backend(self) -> None:
        mod = _load()
        # The backend lowercases case_id (`case_id.lower()`); the corpus emits
        # upper-case `MEM-` ids, so a case-sensitive join would silently 404.
        assert (
            mod._mem_session_id({"mem_id": "MEM-1001", "session_idx": 2})
            == "session-mem-1001-s2"
        )

    def test_independent_of_trace_and_user(self) -> None:
        mod = _load()
        # trace_id / user_id are NOT in the backend sessionId, so changing them
        # must not change the join key.
        base = {"mem_id": "MEM-0001", "session_idx": 0}
        assert mod._mem_session_id(
            {**base, "user_id": "u1", "probe_trace_id": "a" * 32}
        ) == (mod._mem_session_id({**base, "user_id": "u2", "trace_id": "b" * 32}))
        assert mod._mem_session_id(base) == "session-mem-0001-s0"

    def test_empty_when_required_segment_missing(self) -> None:
        mod = _load()
        # session_idx 0 is valid (falsy-but-present); mem_id is required.
        assert mod._mem_session_id({"session_idx": 0}) == ""
        assert mod._mem_session_id({"mem_id": "MEM-1"}) == ""


# ─────────────────────────────────────────────────────────────────────────────
# HERMES / memory-os ADOPTIONS (A1/A2/A3) — new ability branches + hard-0 gate
# Failure-paths-first: the evicted-high-salience hard-0 is asserted before the
# happy rates.
# ─────────────────────────────────────────────────────────────────────────────


def _consolidation_event(
    user_id: str, mem_type: str, *, kept: int, evicted: int, deduped: int = 0
) -> dict:
    return {
        "event_type": "memory_consolidated",
        "details": {
            "user_id": user_id,
            "type": mem_type,
            "kept": kept,
            "evicted": evicted,
            "deduped": deduped,
        },
    }


class TestBudgetConsolidationHardZero:
    def test_evicting_high_salience_while_keeping_low_is_hard_zero(self) -> None:
        # The high-salience fact (peanut allergy) is ABSENT from the answer while
        # a trivial low-salience one survived → wrong eviction order → hard-0.
        mod = _load()
        rows = [
            {
                "case": "MEM-BUDGET-safety",
                "ability": "budget-consolidation",
                "user_id": "userB",
                "response_text": "Here's what I know: you like board games and houseplants.",
                "expect_substring": ["peanut", "allerg"],
                "expect_absent_substring": ["houseplant"],
                "expect_consolidation": True,
            }
        ]
        events = {
            "MEM-BUDGET-safety": [
                _recall_event("userB", 5),
                _consolidation_event("userB", "semantic", kept=5, evicted=1),
            ]
        }
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["evicted_high_salience"] == 1
        assert mod.gate_failures(summary), "wrong-order eviction must fail the gate"

    def test_correct_eviction_passes(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-BUDGET-ok",
                "ability": "budget-consolidation",
                "user_id": "userB",
                "response_text": "Most important: you have a severe peanut allergy.",
                "expect_substring": ["peanut", "allerg"],
                "expect_absent_substring": ["houseplant"],
                "expect_consolidation": True,
            }
        ]
        events = {
            "MEM-BUDGET-ok": [
                _recall_event("userB", 5),
                _consolidation_event("userB", "semantic", kept=5, evicted=1),
            ]
        }
        summary = mod.score_run(rows, events)
        assert summary["hard_zero"]["evicted_high_salience"] == 0
        assert summary["abilities"]["budget-consolidation"]["hits"] == 1
        assert mod.gate_failures(summary) == []

    def test_expected_consolidation_missing_is_a_miss_not_hard_zero(self) -> None:
        # The budget should have been exceeded but NO consolidation carrier fired
        # → a miss (the high fact still present, so not the wrong-order hard-0).
        mod = _load()
        rows = [
            {
                "case": "MEM-BUDGET-noconsol",
                "ability": "budget-consolidation",
                "user_id": "userB",
                "response_text": "Most important: severe peanut allergy.",
                "expect_substring": ["peanut", "allerg"],
                "expect_consolidation": True,
            }
        ]
        events = {
            "MEM-BUDGET-noconsol": [_recall_event("userB", 6)]
        }  # no consolidation event
        summary = mod.score_run(rows, events)
        b = summary["abilities"]["budget-consolidation"]
        assert b["hits"] == 0
        assert summary["hard_zero"]["evicted_high_salience"] == 0  # high fact present
        assert any("BUDGET miss" in m for m in b["mismatches"])

    def test_at_budget_control_must_not_consolidate(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-BUDGET-control",
                "ability": "budget-consolidation",
                "user_id": "userB",
                "response_text": "You use Vim and live in Denver.",
                "expect_substring": ["Vim"],
                "expect_consolidation": False,
            }
        ]
        # No consolidation event → control passes.
        events = {"MEM-BUDGET-control": [_recall_event("userB", 5)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["budget-consolidation"]["hits"] == 1

    def test_at_budget_control_fails_if_it_unexpectedly_consolidates(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-BUDGET-control",
                "ability": "budget-consolidation",
                "user_id": "userB",
                "response_text": "You use Vim.",
                "expect_substring": ["Vim"],
                "expect_consolidation": False,
            }
        ]
        events = {
            "MEM-BUDGET-control": [
                _recall_event("userB", 5),
                _consolidation_event("userB", "semantic", kept=4, evicted=1),
            ]
        }
        summary = mod.score_run(rows, events)
        b = summary["abilities"]["budget-consolidation"]
        assert b["hits"] == 0
        assert any("CONTROL miss" in m for m in b["mismatches"])


class TestRelevanceFloorScoring:
    def test_floor_keeps_on_topic_drops_off_topic(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RELFLOOR-1",
                "ability": "relevance-floor",
                "user_id": "userR",
                "response_text": "You prefer dark-mode UIs.",
                "expect_substring": ["dark"],
                "expect_absent_substring": ["oatmeal"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-RELFLOOR-1": [_recall_event("userR", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["relevance-floor"]["hits"] == 1

    def test_floor_leak_of_off_topic_fact_is_a_miss(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RELFLOOR-1",
                "ability": "relevance-floor",
                "user_id": "userR",
                "response_text": "You prefer dark-mode UIs and eat oatmeal.",
                "expect_substring": ["dark"],
                "expect_absent_substring": ["oatmeal"],
                "probe_recall_expected": True,
            }
        ]
        events = {"MEM-RELFLOOR-1": [_recall_event("userR", 1)]}
        summary = mod.score_run(rows, events)
        f = summary["abilities"]["relevance-floor"]
        assert f["hits"] == 0
        assert any("FLOOR miss" in m for m in f["mismatches"])

    def test_floor_abstains_when_nothing_on_topic(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-RELFLOOR-abstain",
                "ability": "relevance-floor",
                "user_id": "userR",
                "response_text": "I don't have a record of your database preference.",
                "expect_absent_substring": ["hiking"],
                "probe_recall_expected": False,
            }
        ]
        events = {"MEM-RELFLOOR-abstain": [_recall_event("userR", 0)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["relevance-floor"]["hits"] == 1


class TestDedupAndSalienceScoring:
    def test_dedup_recall_hit(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-DEDUP-1",
                "ability": "recall-dedup",
                "user_id": "userD",
                "response_text": "You prefer metric units.",
                "expect_substring": ["metric"],
            }
        ]
        events = {"MEM-DEDUP-1": [_recall_event("userD", 2)]}  # backend returned 2 rows
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["recall-dedup"]["hits"] == 1

    def test_salience_tier_recall_hit(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "MEM-SAL-1",
                "ability": "salience-tier",
                "user_id": "userS",
                "response_text": "You prefer email over phone.",
                "expect_substring": ["email"],
            }
        ]
        events = {"MEM-SAL-1": [_recall_event("userS", 2)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["salience-tier"]["hits"] == 1

    def test_salience_unmarked_legacy_no_tier_leak(self) -> None:
        # The legacy case asserts NO tier prefix leaked into the answer.
        mod = _load()
        rows = [
            {
                "case": "MEM-SAL-legacy",
                "ability": "salience-tier",
                "user_id": "userS",
                "response_text": "You're based in Toronto.",
                "expect_substring": ["Toronto"],
                "expect_absent_substring": ["[confirmed]", "[inferred]"],
            }
        ]
        events = {"MEM-SAL-legacy": [_recall_event("userS", 1)]}
        summary = mod.score_run(rows, events)
        assert summary["abilities"]["salience-tier"]["hits"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase B reject harness (C1/C3/C4/C5) — failure-paths-first
# ─────────────────────────────────────────────────────────────────────────────


def _recall_event_with_keys(user_id: str, keys: list[str]) -> dict:
    return {
        "event_type": "memory_recalled",
        "details": {
            "user_id": user_id,
            "count": len(keys),
            "query_len": 10,
            "keys": keys,
        },
    }


class TestRejectPhaseScoring:
    def test_c4_fail_when_rejected_key_still_recalled(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "PHASEB-X",
                "run": 1,
                "trace_id": "t1",
                "user_id": "u1",
                "seed_snippets": ["metric"],
            },
            {
                "case": "PHASEB-X",
                "run": 2,
                "trace_id": "t2",
                "user_id": "u1",
                "reject_key": "k1",
            },
        ]
        events = {
            "t1": [_recall_event_with_keys("u1", ["k1", "k2"])],
            "t2": [_recall_event_with_keys("u1", ["k1", "k2"])],
        }
        summary = mod.score_reject_batch(
            rows, events, suppress_found={"PHASEB-X": True}
        )
        assert summary["hard_zero"]["reject_not_excluded"] == 1
        assert mod.gate_failures_reject(summary)

    def test_c4_pass_when_rejected_key_excluded(self) -> None:
        mod = _load()
        rows = [
            {
                "case": "PHASEB-OK",
                "run": 1,
                "trace_id": "t1",
                "user_id": "u1",
                "seed_snippets": ["Berlin"],
            },
            {
                "case": "PHASEB-OK",
                "run": 2,
                "trace_id": "t2",
                "user_id": "u1",
                "reject_key": "k1",
            },
        ]
        events = {
            "t1": [_recall_event_with_keys("u1", ["k1", "k2"])],
            "t2": [_recall_event_with_keys("u1", ["k2"])],
        }
        summary = mod.score_reject_batch(
            rows, events, suppress_found={"PHASEB-OK": True}
        )
        assert summary["hard_zero"]["reject_not_excluded"] == 0
        assert mod.gate_failures_reject(summary) == []

    def test_empty_join_fail_closed(self) -> None:
        mod = _load()
        rows = [
            {"case": "PHASEB-MISS", "run": 1, "trace_id": "t1", "user_id": "u1"},
            {
                "case": "PHASEB-MISS",
                "run": 2,
                "trace_id": "t2",
                "user_id": "u1",
                "reject_key": "k1",
            },
        ]
        summary = mod.score_reject_batch(rows, {})
        assert summary["hard_zero"]["missing_trace_join"] >= 1
        assert mod.gate_failures_reject(summary)

    def test_c3_suppress_carrier_missing_fails_gate(self) -> None:
        mod = _load()
        rows = [
            {"case": "PHASEB-NOSUP", "run": 1, "trace_id": "t1", "user_id": "u1"},
            {
                "case": "PHASEB-NOSUP",
                "run": 2,
                "trace_id": "t2",
                "user_id": "u1",
                "reject_key": "k1",
            },
        ]
        events = {
            "t1": [_recall_event_with_keys("u1", ["k1"])],
            "t2": [_recall_event_with_keys("u1", [])],
        }
        summary = mod.score_reject_batch(
            rows, events, suppress_found={"PHASEB-NOSUP": False}
        )
        assert summary["hard_zero"]["suppress_carrier_missing"] == 1
        assert mod.gate_failures_reject(summary)


class TestC5ContentLeak:
    """C5: the recall carrier must carry metadata only (user_id/count/query_len/
    keys), never payload content. The check must distinguish a REAL leak from
    the trace-envelope plumbing the Langfuse flattener attaches to every event
    (resourceAttributes / scope / integrity_hash / a re-nested details dict) —
    those are long structured strings but NOT content (the false positive that
    flagged a clean PhaseB run; see the live 2026-06-19 validation)."""

    def test_clean_carrier_does_not_leak(self) -> None:
        mod = _load()
        events = [_recall_event_with_keys("u1", ["k1", "k2"])]
        assert (
            mod._content_leaked_in_recall_carriers(events, seed_snippets=["Berlin"])
            is False
        )

    def test_trace_envelope_plumbing_is_not_a_leak(self) -> None:
        """The Langfuse flattener merges envelope fields onto the carrier dict.
        A 143-char resourceAttributes / 120-char scope / re-nested details must
        NOT trip the len>80 heuristic — they are SDK/OTel metadata, not payload."""
        mod = _load()
        carrier_details = {
            "user_id": "user_01KQ0",
            "count": "2",
            "query_len": "38",
            "keys": ["54934e3f", "7ae5c670"],
        }
        # As the real reader returns it: details merged up + envelope plumbing.
        leaky_envelope = {
            "event_type": "memory_recalled",
            "details": dict(carrier_details),
            **carrier_details,
            "resourceAttributes": {
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version": "1.42.1",
                "service.name": "agent-runtime",
            },
            "scope": {"name": "langfuse-sdk", "version": "4.7.1"},
            "integrity_hash": "1df9aa4ba83bf2feccf4d11fe5edf8207b76ab66f6b9f6c359ae8141a3ec51a4",
        }
        assert (
            mod._content_leaked_in_recall_carriers(
                [leaky_envelope], seed_snippets=["Berlin", "home timezone"]
            )
            is False
        )

    def test_seed_snippet_in_detail_value_is_a_real_leak(self) -> None:
        """A genuine leak — the recalled fact's text echoed into a detail field
        (e.g. a 'query' field carrying the raw query) — MUST be caught."""
        mod = _load()
        leaky = {
            "event_type": "memory_recalled",
            "details": {
                "user_id": "u1",
                "count": 1,
                "query": "where does the user live? Berlin",  # raw content leaked
                "keys": ["k1"],
            },
            "user_id": "u1",
            "count": 1,
            "query": "where does the user live? Berlin",
            "keys": ["k1"],
        }
        assert (
            mod._content_leaked_in_recall_carriers([leaky], seed_snippets=["Berlin"])
            is True
        )
