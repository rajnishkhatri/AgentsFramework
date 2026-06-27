"""L1/L2 contract tests for the memory multi-session corpus builder.

Failure-paths-first: the abstention + leak-control CONTROLS are the precision
guards this corpus exists for, so they are asserted before the happy-recall
shape. The builder is a pure function (no live LLM, no network) — these run in
CI. See ``docs/plans/memory_multisession_e2e_stress.plan.md`` §3.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_BUILDER = _AGENT_ROOT / "scripts" / "build_memory_multisession_corpus.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_mem_corpus", _BUILDER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    return _load_builder().build_corpus()


# ── the mem: thread bridge regex (must stay in lockstep with the backend) ──
# middleware/goaljudge_saturation_bridge.py _MEM_THREAD_RE user_id segment is
# [0-9A-Za-z]+ ; the corpus user_id must satisfy it or the live run can't carry it.
_USER_ID_RE = re.compile(r"^[0-9A-Za-z]+$")
_VALID_ABILITIES = {
    "recall",
    "multi-session",
    "temporal",
    "leak-control",
    "knowledge-update",
    "abstention",
    "persona-drift",
    # Hermes / memory-os adoptions (docs/research/memory/hermes_adoptions_design.md).
    "relevance-floor",
    "recall-dedup",
    "salience-tier",
    "budget-consolidation",
}
# Session kinds: the original conversational kinds plus crud-seed (A1/A3 plant
# memories directly via the /agent/memory route with explicit salience/type).
_VALID_KINDS = {"seed", "filler", "probe", "crud-seed"}
_VALID_PROVENANCE = {"longmemeval-derived", "synthetic-locomo-shape", "synthetic"}


class TestControlsFirst:
    """The precision guards (failure-paths-first) — authored and asserted first."""

    def test_has_leak_control_cases(self, corpus: list[dict]) -> None:
        leak = [c for c in corpus if c["ability"] == "leak-control"]
        assert leak, "leak-control cases are the headline cross-user precision guard"

    def test_has_abstention_cases(self, corpus: list[dict]) -> None:
        abstain = [c for c in corpus if c["ability"] == "abstention"]
        assert abstain, "abstention cases guard against fabricated memories"

    def test_abstention_probe_expects_no_recall(self, corpus: list[dict]) -> None:
        for c in corpus:
            if c["ability"] != "abstention":
                continue
            probes = [s for s in c["sessions"] if s["kind"] == "probe"]
            assert probes, f"{c['case']} abstention case needs a probe session"
            for p in probes:
                assert p.get("want_recall") is False, (
                    f"{c['case']} abstention probe must expect want_recall=False "
                    "(nothing was seeded — recall must return 0 / abstain)"
                )

    def test_leak_control_user_id_never_seeds_the_probed_fact(
        self, corpus: list[dict]
    ) -> None:
        """A leak-control case probes a fact only ever seeded under ANOTHER
        case's user_id, so its own sessions must contain no seed of that fact.
        Structurally: a leak-control case has a probe but the fact's evidence
        lives in a different user's case (no in-case seed session)."""
        for c in corpus:
            if c["ability"] != "leak-control":
                continue
            kinds = {s["kind"] for s in c["sessions"]}
            assert "seed" not in kinds, (
                f"{c['case']} leak-control must NOT seed its own probed fact — "
                "the fact belongs to another user; recall must return 0"
            )
            assert "probe" in kinds


class TestCaseSchema:
    def test_nonempty(self, corpus: list[dict]) -> None:
        assert len(corpus) >= 5

    def test_required_keys(self, corpus: list[dict]) -> None:
        for c in corpus:
            for key in (
                "case",
                "mem_id",
                "ability",
                "provenance",
                "user_id",
                "sessions",
            ):
                assert key in c, f"{c.get('case', '?')} missing {key}"

    def test_ability_and_provenance_in_vocab(self, corpus: list[dict]) -> None:
        for c in corpus:
            assert c["ability"] in _VALID_ABILITIES, c["ability"]
            assert c["provenance"] in _VALID_PROVENANCE, c["provenance"]

    def test_mem_id_is_bridge_conforming(self, corpus: list[dict]) -> None:
        # mem:{mem_id}:s{idx}:{user8}:{trace}; mem_id must match MEM-[0-9A-Za-z-]+
        for c in corpus:
            assert re.match(r"^MEM-[0-9A-Za-z-]+$", c["mem_id"]), c["mem_id"]

    def test_user_id_bridge_conforming(self, corpus: list[dict]) -> None:
        for c in corpus:
            assert _USER_ID_RE.match(c["user_id"]), (
                f"{c['case']} user_id {c['user_id']!r} not [0-9A-Za-z]+ — the "
                "mem: thread bridge would reject it"
            )


class TestUserIdUniqueness:
    """The cross-user-leak guard precondition: distinct user_id per case."""

    def test_user_id_unique_per_case(self, corpus: list[dict]) -> None:
        users = [c["user_id"] for c in corpus]
        assert len(users) == len(set(users)), (
            "user_id must be unique per case or a cross-user leak is impossible "
            "to detect (all cases would share one memory namespace)"
        )

    def test_case_ids_unique(self, corpus: list[dict]) -> None:
        cases = [c["case"] for c in corpus]
        assert len(cases) == len(set(cases))
        mem_ids = [c["mem_id"] for c in corpus]
        assert len(mem_ids) == len(set(mem_ids))


class TestSessionShape:
    def test_sessions_ordered_and_typed(self, corpus: list[dict]) -> None:
        for c in corpus:
            sessions = c["sessions"]
            assert sessions, f"{c['case']} has no sessions"
            # session_idx is 0-based and strictly increasing (seed before probe).
            idxs = [s["session_idx"] for s in sessions]
            assert idxs == sorted(idxs)
            assert idxs == list(range(len(sessions)))
            for s in sessions:
                assert s["kind"] in _VALID_KINDS
                assert isinstance(s["turns"], list)
                # A crud-seed session carries no conversational turns (it plants
                # memories via seed_memory); every other kind needs real turns.
                if s["kind"] == "crud-seed":
                    assert s.get("seed_memory"), (
                        f"{c['case']} crud-seed needs seed_memory"
                    )
                else:
                    assert s["turns"]
                    assert all(isinstance(t, str) and t for t in s["turns"])

    def test_probe_sessions_carry_expectations(self, corpus: list[dict]) -> None:
        for c in corpus:
            for s in c["sessions"]:
                if s["kind"] != "probe":
                    continue
                assert "want_recall" in s, f"{c['case']} probe missing want_recall"
                if s["want_recall"]:
                    assert s.get("expect_substring"), (
                        f"{c['case']} recall-expecting probe needs expect_substring"
                    )
                    assert "evidence_session_idx" in s, (
                        f"{c['case']} recall probe needs evidence_session_idx"
                    )

    def test_recall_probe_evidence_precedes_probe(self, corpus: list[dict]) -> None:
        """The experiment is seed-THEN-probe: evidence must be an EARLIER
        session, never the probe itself or a later one."""
        for c in corpus:
            for s in c["sessions"]:
                if s["kind"] == "probe" and s.get("want_recall"):
                    ev = s["evidence_session_idx"]
                    assert ev < s["session_idx"], (
                        f"{c['case']} evidence_session_idx {ev} must precede probe "
                        f"session {s['session_idx']}"
                    )


class TestKnowledgeUpdate:
    def test_update_case_has_seed_correction_probe(self, corpus: list[dict]) -> None:
        """A knowledge-update case seeds X, corrects to Y, then probes — and the
        probe's expect_substring is the CORRECTED value (the ADD-vs-UPDATE seam)."""
        upd = [c for c in corpus if c["ability"] == "knowledge-update"]
        assert upd, "knowledge-update is phase B"
        for c in upd:
            seeds = [s for s in c["sessions"] if s["kind"] == "seed"]
            assert len(seeds) >= 2, (
                f"{c['case']} update case needs >=2 seeds (original X + correction Y)"
            )
            probe = [s for s in c["sessions"] if s["kind"] == "probe"]
            assert probe and probe[-1].get("want_recall") is True


class TestDeterminismAndLicensing:
    def test_idempotent_regen(self) -> None:
        """Check 7 determinism: two builds produce identical output."""
        mod = _load_builder()
        assert mod.build_corpus() == mod.build_corpus()

    def test_no_locomo_verbatim_text(self, corpus: list[dict]) -> None:
        """LoCoMo is CC BY-NC — synthetic-locomo-shape rows are PARAPHRASED, not
        copied. The known LoCoMo speaker names (Caroline / Melanie) must never
        appear verbatim in our committed fixture."""
        blob = repr(corpus)
        for banned in ("Caroline", "Melanie"):
            assert banned not in blob, (
                f"LoCoMo verbatim token {banned!r} leaked into the fixture — "
                "persona-drift cases must be independently authored"
            )

    def test_locomo_shape_cases_marked(self, corpus: list[dict]) -> None:
        drift = [c for c in corpus if c["ability"] == "persona-drift"]
        for c in drift:
            assert c["provenance"] == "synthetic-locomo-shape"
