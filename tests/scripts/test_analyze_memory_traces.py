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
    """The probe→trace join key: the spec installs `mem:{mem_id}:s{idx}:{user}:
    {trace}` as the Langfuse sessionId, and the analyzer must reconstruct it
    byte-identically (the backend never echoes the client probe_trace_id as a
    trace id — FE-AP-7 — so this reconstruction is the only reliable join)."""

    def test_reconstructs_full_mem_session_id(self) -> None:
        mod = _load()
        row = {
            "mem_id": "MEM-0401",
            "session_idx": 3,
            "user_id": "userpers01",
            "probe_trace_id": "70a1bbd8a21bec8a9e97a33611ef0b7c",
        }
        assert (
            mod._mem_session_id(row)
            == "mem:MEM-0401:s3:userpers01:70a1bbd8a21bec8a9e97a33611ef0b7c"
        )

    def test_falls_back_to_corpus_trace_id_when_no_probe_trace(self) -> None:
        mod = _load()
        row = {
            "mem_id": "MEM-0001",
            "session_idx": 0,
            "user_id": "userpref01",
            "trace_id": "a" * 32,
        }
        assert mod._mem_session_id(row).endswith(":userpref01:" + "a" * 32)

    def test_empty_when_any_segment_missing(self) -> None:
        mod = _load()
        # session_idx 0 is valid (falsy-but-present); a missing user_id is not.
        assert mod._mem_session_id({"mem_id": "MEM-1", "session_idx": 0}) == ""
        assert mod._mem_session_id({"session_idx": 0, "user_id": "u", "probe_trace_id": "t"}) == ""
