"""Gate meta-benchmark: ``validate_conditions`` vs labeled REAL artifacts.

Process rule (tu-gate longterm plan §6.2): **gates get gated** — a
deterministic validator that can discard production artifacts ships with its
own labeled must-accept/must-reject benchmark. Round 2 shipped a retry loop
and a prompt rule to compensate a gate whose false-positive rate had never
been measured against a single real model output; the actual defect was
``_content_tokens`` gluing sentence-final punctuation onto the last token
(``data.`` ≠ ``data`` — every failed task ends in its key noun).

Fixture: ``tests/fixtures/task_understanding/gate_benchmark_v1.json`` — 70
real gpt-4o-mini regenerations of the round-2 goldset subset (exact deployed
prompt, deploy ``tierA-prod-2026.06.0-e72920c``), labeled offline with the
punct-strip transform verified in
``docs/research/goaljudge_tu_gate_longterm_plan/r2_dot_verify.py`` (20/20
failed-sample recovery, strictly monotone vs the live gate). Record/replay
(Pattern 5): the test replays frozen labels and asserts the production gate
agrees — no gate logic is reimplemented here (TAP-1).

Rejection paths first (TAP-4): a gate that accepts everything is more
dangerous than one that rejects everything.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from components.task_understanding import _content_tokens, validate_conditions

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "task_understanding"
    / "gate_benchmark_v1.json"
)
_BENCH = json.loads(_FIXTURE.read_text())

_GROUNDING_INDEX = re.compile(r"grounding gate: condition (\d+)")


def _grounding_indexes(issues: list[str]) -> set[int]:
    """Indexes the grounding gate rejected, parsed from the public issue
    strings (the same strings the retry feedback forwards to the model)."""
    return {
        int(m.group(1))
        for issue in issues
        for m in [_GROUNDING_INDEX.search(issue)]
        if m
    }


# ─────────────────────────────────────────────────────────────────────
# Must-reject — genuinely invented requirements stay rejected (TAP-4 first).
# Guards the fix's direction: punct-strip may only RECOVER true positives,
# never admit the case-16-style inventions that retry exists to catch.
# ─────────────────────────────────────────────────────────────────────


class TestMustReject:
    @pytest.mark.parametrize(
        "entry", _BENCH["must_reject"], ids=lambda e: e["id"]
    )
    def test_invented_requirement_rejected_at_labeled_index(self, entry):
        issues = validate_conditions(
            entry["conditions"], task_input=entry["task"]
        )
        assert _grounding_indexes(issues) == set(entry["ungrounded_indexes"])

    def test_off_vocabulary_fabrication_rejected(self):
        """A fully off-topic condition still trips grounding — guards against
        over-relaxation (stemming-to-mush, wholesale punctuation removal)."""
        task = _BENCH["must_reject"][0]["task"]
        issues = validate_conditions(
            ["Zorblat frequencies harmonized completely.", task],
            task_input=task,
        )
        assert _grounding_indexes(issues) == {0}


# ─────────────────────────────────────────────────────────────────────
# Adversarial topicality bound — documented KNOWN-PASS, not desired behavior.
# A lexical gate is a topicality filter (longterm-plan finding #3.4): an
# on-vocabulary fabricated requirement grounds under EVERY lexical variant.
# Pinning the full 6×5 matrix keeps the bound honest in both directions:
# if this test ever fails, either the gate got semantic powers (update the
# fixture deliberately) or it regressed off-topic rejection.
# ─────────────────────────────────────────────────────────────────────


class TestAdversarialTopicalityBound:
    @pytest.mark.parametrize(
        "entry",
        _BENCH["adversarial"],
        ids=lambda e: f"case{e['case']:02d}-{e['probe'][:30]}",
    )
    def test_probe_grounding_matches_documented_bound(self, entry):
        # Anchor condition = the task text itself (trivially grounded), so
        # the probe at index 1 is the only condition that can trip grounding.
        issues = validate_conditions(
            [entry["task"], entry["probe"]], task_input=entry["task"]
        )
        expected = set() if entry["grounds"] else {1}
        assert _grounding_indexes(issues) == expected


# ─────────────────────────────────────────────────────────────────────
# Must-accept — 68 real artifacts the fixed gate accepts. The 22 entries
# with v0_rejected=true are the trailing-punctuation false positives that
# capped round 2 at 83%: the model QUOTED the task verbatim and the gate's
# "shares no word with the task" feedback was factually false.
# ─────────────────────────────────────────────────────────────────────


class TestMustAccept:
    @pytest.mark.parametrize(
        "entry", _BENCH["must_accept"], ids=lambda e: e["id"]
    )
    def test_real_artifact_passes_all_gates(self, entry):
        issues = validate_conditions(
            entry["conditions"], task_input=entry["task"]
        )
        assert issues == [], (
            f"{entry['id']} (v0_rejected={entry['v0_rejected']}): {issues}"
        )


# ─────────────────────────────────────────────────────────────────────
# Tokenizer unit pins — the exact transform verified in r2_dot_verify.py.
# ─────────────────────────────────────────────────────────────────────


class TestContentTokens:
    def test_sentence_final_punctuation_stripped(self):
        """The headline defect: every round-2 failed task ends in its single
        most important noun, and ``data.`` ≠ ``data`` rejected verbatim quotes."""
        tokens = _content_tokens("Refuse this request because it would delete production data.")
        assert "data" in tokens
        assert "data." not in tokens

    def test_interior_path_punctuation_preserved(self):
        """Edge-strip only: ``workspace/status.txt`` must survive intact —
        the '.' in the token class exists precisely to keep paths whole."""
        tokens = _content_tokens("Overwrite /workspace/status.txt with the single character OK.")
        assert "workspace/status.txt" in tokens
        assert "ok" in tokens

    def test_stopword_filter_runs_before_edge_strip(self):
        """Pins the verified order: stopwords filter on RAW tokens, THEN
        edge-strip. A dotted stopword therefore survives as its bare form
        ({'the'} here). Not an endorsement of stopword leakage — this order
        is what makes the fix strictly monotone vs the live gate (every V0
        match maps to a stripped match), which is the safety argument for
        shipping R3 without a dedicated shadow round. Flipping the order
        would silently break that proof."""
        assert _content_tokens("done the.") == {"the"}
