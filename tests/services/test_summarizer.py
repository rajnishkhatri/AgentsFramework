"""Phase 1 — golden + property tests for the C1 summarizer pure functions.

Specification:
  docs/plans/c1_message_compaction.impl.md  (Phase 1)
  docs/plans/c1_message_compaction.design.md (§4 functions, §8.2 L1-d golden table)

TDD layer: Protocol A — Trust-Foundation-style pure TDD (Red-Green-Refactor).
  - L1: zero uncertainty; deterministic; no I/O; no langchain.
  - Failure-paths-first (Anti-Pattern 6) — orphan/empty/no-tool cases come BEFORE
    the happy-path assertions inside each section.
  - Anti-Pattern 1 avoided: assertions are behavioral (verbatim, order-preserving,
    deterministic, no-orphan invariant); they never re-implement the algorithm.
  - Anti-Pattern 7 avoided: this test imports only from ``services.summarizer``;
    no ``langchain_core`` import (I-4) and no ``components`` import (I-5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from services.summarizer import (
    CompactionPlan,
    MessageView,
    PinnedConstraint,
    build_constraint_floor,
    build_message_compaction,
    derive_pinned_floor,
    plan_fold_cutoff,
    plan_observation_mask,
)


# ════════════════════════════════════════════════════════════════════════════
# Test fixtures — minimal MessageView builders.
#
# We hand-author each view shape instead of using the live ``orchestration``
# adapter, because Phase 1 is inert and must be langchain-free (I-4 + the
# AGENTS.md `services/` rule). The fixture builders deliberately mirror the
# MessageView contract from design §3.1.
# ════════════════════════════════════════════════════════════════════════════


def _human(content: str) -> MessageView:
    return MessageView(role="human", content=content)


def _ai(content: str, *, tool_calls: tuple[str, ...] = ()) -> MessageView:
    # Design §3.1: tool_calls is a tuple of ids (strings), not dicts.
    return MessageView(role="ai", content=content, tool_calls=tuple(tool_calls))


def _tool(content: str, *, tool_call_id: str) -> MessageView:
    return MessageView(role="tool", content=content, tool_call_id=tool_call_id)


def _system(content: str) -> MessageView:
    return MessageView(role="system", content=content)


def _block(ai_text: str, tool_ids: tuple[str, ...]) -> list[MessageView]:
    """Render a single Interaction Block (AI + all its answering tool views)."""
    views: list[MessageView] = [_ai(ai_text, tool_calls=tool_ids)]
    for tc_id in tool_ids:
        views.append(_tool(f"observation for {tc_id}", tool_call_id=tc_id))
    return views


# ════════════════════════════════════════════════════════════════════════════
# A. CompactionPlan / PinnedConstraint dataclass shape (Protocol A1).
#
# These dataclasses are the pure→orchestration handoff. Tests pin the field set
# AND mutability posture (frozen) so a future field rename can't silently land.
# ════════════════════════════════════════════════════════════════════════════


class TestCompactionPlanShape:
    def test_compaction_plan_has_pinned_field_set(self):
        plan = CompactionPlan(
            mask_indices=frozenset({0, 1}),
            cutoff=3,
            summary="stub",
            pinned=(),
            floor_exceeded=False,
        )
        assert plan.mask_indices == frozenset({0, 1})
        assert plan.cutoff == 3
        assert plan.summary == "stub"
        assert plan.pinned == ()
        assert plan.floor_exceeded is False

    def test_compaction_plan_is_frozen(self):
        plan = CompactionPlan(
            mask_indices=frozenset(),
            cutoff=0,
            summary="",
            pinned=(),
            floor_exceeded=False,
        )
        with pytest.raises((AttributeError, Exception)):
            plan.cutoff = 99  # type: ignore[misc]

    def test_pinned_constraint_polarity_must_be_validated_string(self):
        pc = PinnedConstraint(text="never delete X", polarity="must-not", source="success")
        assert pc.text == "never delete X"
        assert pc.polarity == "must-not"
        assert pc.source == "success"


# ════════════════════════════════════════════════════════════════════════════
# B. plan_observation_mask (§4 fn 1).
#
# Failure-paths-first: empty/no-tool/below-M before the masking happens.
# Then the masking selection itself, plus the role exclusion rule.
# ════════════════════════════════════════════════════════════════════════════


class TestPlanObservationMask:
    def test_empty_history_returns_empty_mask(self):
        assert plan_observation_mask([], mask_after_steps=10) == frozenset()

    def test_only_human_and_ai_never_selected(self):
        views = [_human("hi"), _ai("hello"), _human("ok"), _ai("done")]
        assert plan_observation_mask(views, mask_after_steps=0) == frozenset()

    def test_system_view_never_selected(self):
        views = [_system("pinned"), _human("hi"), _ai("ok")]
        assert plan_observation_mask(views, mask_after_steps=0) == frozenset()

    def test_recent_tool_within_window_kept(self):
        # one block — the tool obs is the LAST step; mask_after_steps=10 keeps it.
        views = _block("call", ("t1",))
        assert plan_observation_mask(views, mask_after_steps=10) == frozenset()

    def test_old_tool_beyond_window_selected(self):
        # 12 step-blocks; with mask_after_steps=10 the earliest two are masked.
        views: list[MessageView] = []
        for i in range(12):
            views.extend(_block(f"call-{i}", (f"t{i}",)))
        mask = plan_observation_mask(views, mask_after_steps=10)
        # tool views live at indices 1, 3, 5, ... ; first two blocks → indices 1, 3
        assert 1 in mask
        assert 3 in mask
        # last block's tool view (index 23) is within the window — never masked
        assert 23 not in mask

    def test_default_mask_after_steps_is_ten(self):
        # the design's §B1-R R1 ablated optimum — pin the default explicitly.
        views: list[MessageView] = []
        for i in range(11):
            views.extend(_block(f"c{i}", (f"t{i}",)))
        default = plan_observation_mask(views)
        explicit = plan_observation_mask(views, mask_after_steps=10)
        assert default == explicit

    def test_mask_is_deterministic_under_repeated_calls(self):
        views: list[MessageView] = []
        for i in range(20):
            views.extend(_block(f"c{i}", (f"t{i}", f"t{i}b")))
        first = plan_observation_mask(views, mask_after_steps=5)
        for _ in range(9):
            assert plan_observation_mask(views, mask_after_steps=5) == first


# ════════════════════════════════════════════════════════════════════════════
# C. plan_fold_cutoff (§4 fn 2) — the §8.2 L1-d golden-case table.
#
# Every row of the design's L1-d table gets a first-class test that asserts the
# bidirectional Interaction-Block invariant: no orphan ToolMessage AND no
# AI-with-tool_calls whose answering ToolMessages were dropped. Each test
# documents the case label in its docstring so failures surface the design row.
# ════════════════════════════════════════════════════════════════════════════


def _suffix_after_cutoff(views: list[MessageView], cutoff: int) -> list[MessageView]:
    return views[cutoff:]


def _has_orphan(views: list[MessageView]) -> bool:
    """A suffix is orphaned iff a tool view's tool_call_id has no AI ancestor
    in the suffix, OR an AI view has a tool_call_id with no answering tool.
    """
    tool_call_ids_in_suffix = {v.tool_call_id for v in views if v.role == "tool"}
    ai_call_ids = set()
    for v in views:
        if v.role == "ai" and v.tool_calls:
            # Design §3.1: tool_calls is an id-tuple of strings.
            ai_call_ids.update(v.tool_calls)
    # Orphan side (a): tool with no AI ancestor in the suffix.
    if tool_call_ids_in_suffix - ai_call_ids:
        return True
    # Orphan side (b): AI with at least one unanswered tool_call in the suffix.
    if ai_call_ids - tool_call_ids_in_suffix:
        return True
    return False


class TestPlanFoldCutoffGoldenCases:
    """The §8.2 L1-d golden-case checklist — one test per row."""

    def test_row_empty_history(self):
        """empty history → no fold, plan is a no-op (cutoff == 0)."""
        assert plan_fold_cutoff([], keep_last_k=4) == 0

    def test_row_single_turn(self):
        """single turn → cutoff keeps the whole turn; nothing to fold."""
        views = [_human("hi"), _ai("hello there")]
        cutoff = plan_fold_cutoff(views, keep_last_k=4)
        assert cutoff == 0
        assert not _has_orphan(_suffix_after_cutoff(views, cutoff))

    def test_row_no_tool_results(self):
        """Human/AI prose only — plain message-boundary cutoff, no block logic."""
        views = [_human(f"h{i}") if i % 2 == 0 else _ai(f"a{i}") for i in range(8)]
        cutoff = plan_fold_cutoff(views, keep_last_k=4)
        assert 0 <= cutoff <= len(views)
        assert len(_suffix_after_cutoff(views, cutoff)) >= 4
        assert not _has_orphan(_suffix_after_cutoff(views, cutoff))

    def test_row_cutoff_on_tool_pair(self):
        """cutoff lands between AI and its single ToolMessage → walk back to AI."""
        views: list[MessageView] = []
        for i in range(5):
            views.extend(_block(f"call-{i}", (f"t{i}",)))
        cutoff = plan_fold_cutoff(views, keep_last_k=3)
        suffix = _suffix_after_cutoff(views, cutoff)
        # The first view in the suffix must be an AI view, never a stray tool obs.
        if suffix:
            assert suffix[0].role in ("ai", "human", "system")
        assert not _has_orphan(suffix)

    def test_row_parallel_tool_calls_straddling_cutoff(self):
        """one AI with ≥2 tool_calls answered across the cutoff → keep the whole block."""
        prefix = _block("prelude", ("p1",))
        straddle = _block("call-parallel", ("a", "b", "c"))
        tail = _block("after", ("d",))
        views = [*prefix, *straddle, *tail]
        cutoff = plan_fold_cutoff(views, keep_last_k=2)
        suffix = _suffix_after_cutoff(views, cutoff)
        # No orphan on either side — parallel block must be whole.
        assert not _has_orphan(suffix)
        # If the parallel block survives at all, its AI view must be in the suffix
        # AND every one of its three answering tools must be in the suffix.
        ai_calls = [
            v for v in suffix if v.role == "ai" and v.content == "call-parallel"
        ]
        if ai_calls:
            answered = {v.tool_call_id for v in suffix if v.role == "tool"}
            assert {"a", "b", "c"}.issubset(answered)

    def test_row_multiple_parallel_blocks_at_boundary(self):
        """two back-to-back AI views, each parallel, at the cutoff → each whole."""
        views: list[MessageView] = []
        views.extend(_block("call-A", ("a1", "a2")))
        views.extend(_block("call-B", ("b1", "b2", "b3")))
        views.extend(_block("call-C", ("c1",)))
        cutoff = plan_fold_cutoff(views, keep_last_k=4)
        suffix = _suffix_after_cutoff(views, cutoff)
        assert not _has_orphan(suffix)

    def test_row_system_messages_interleaved(self):
        """system views preserved; never count as block members."""
        views = [
            _system("pinned-floor"),
            *_block("call-1", ("t1",)),
            _system("pinned-mid"),
            *_block("call-2", ("t2",)),
            *_block("call-3", ("t3",)),
        ]
        cutoff = plan_fold_cutoff(views, keep_last_k=2)
        suffix = _suffix_after_cutoff(views, cutoff)
        assert not _has_orphan(suffix)

    def test_row_all_pinned_declines_or_keeps_all(self):
        """every message pinned → fold declines (cutoff==0) or keeps all (§5.3)."""
        # In Phase 1 we cannot know which messages are pinned (that's §5.3 wiring).
        # The invariant Phase 1 must preserve is: the cutoff function alone never
        # discards more than (len - keep_last_k) message-pair boundaries' worth.
        views = [_human("h"), _ai("a"), _human("h2"), _ai("a2")]
        cutoff = plan_fold_cutoff(views, keep_last_k=len(views))
        assert cutoff == 0


# ════════════════════════════════════════════════════════════════════════════
# D. plan_fold_cutoff — Hypothesis property layer.
#
# The combinatorial surface of parallel + interleaved blocks is too large for
# the explicit table alone. These properties harden the no-orphan invariant
# across generated message-list shapes.
# ════════════════════════════════════════════════════════════════════════════


# Generators

_role_text = st.text(min_size=0, max_size=20)

_tool_call_id_st = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=6,
)


@st.composite
def _interaction_block_strategy(draw):
    n_calls = draw(st.integers(min_value=1, max_value=3))
    call_ids = tuple(f"{draw(_tool_call_id_st)}{i}" for i in range(n_calls))
    return _block(draw(_role_text), call_ids)


@st.composite
def _history_strategy(draw):
    n_segments = draw(st.integers(min_value=0, max_value=6))
    views: list[MessageView] = []
    for _ in range(n_segments):
        choice = draw(st.integers(min_value=0, max_value=3))
        if choice == 0:
            views.append(_human(draw(_role_text)))
        elif choice == 1:
            views.append(_ai(draw(_role_text)))
        elif choice == 2:
            views.append(_system(draw(_role_text)))
        else:
            views.extend(draw(_interaction_block_strategy()))
    return views


class TestPlanFoldCutoffProperties:
    @given(views=_history_strategy(), keep_last_k=st.integers(min_value=0, max_value=8))
    @settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
    def test_no_orphan_invariant_always(self, views, keep_last_k):
        """The cutoff suffix never contains a half-block — ever."""
        cutoff = plan_fold_cutoff(views, keep_last_k=keep_last_k)
        assert 0 <= cutoff <= len(views)
        suffix = _suffix_after_cutoff(views, cutoff)
        assert not _has_orphan(suffix), (
            f"orphan in suffix for cutoff={cutoff}, views={[v.role for v in views]}"
        )

    @given(views=_history_strategy())
    @settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
    def test_cutoff_is_deterministic(self, views):
        first = plan_fold_cutoff(views, keep_last_k=4)
        for _ in range(3):
            assert plan_fold_cutoff(views, keep_last_k=4) == first


class TestPlanObservationMaskProperties:
    @given(
        n_blocks=st.integers(min_value=0, max_value=15),
        m_a=st.integers(min_value=0, max_value=20),
        m_b=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
    def test_mask_monotone_in_mask_after_steps(self, n_blocks, m_a, m_b):
        """Larger mask_after_steps ⇒ a SUPERSET of preserved (smaller mask)."""
        views: list[MessageView] = []
        for i in range(n_blocks):
            views.extend(_block(f"c{i}", (f"t{i}",)))
        m_small, m_large = sorted((m_a, m_b))
        small_mask = plan_observation_mask(views, mask_after_steps=m_small)
        large_mask = plan_observation_mask(views, mask_after_steps=m_large)
        # Bigger window → fewer (or equal) tool obs masked.
        assert large_mask.issubset(small_mask)


# ════════════════════════════════════════════════════════════════════════════
# E. build_message_compaction (§4 fn 3) — bucket schema + verbatim PINNED.
# ════════════════════════════════════════════════════════════════════════════


_BUCKETS = ("SESSION INTENT", "SUMMARY", "ARTIFACTS", "NEXT STEPS", "PINNED")


class TestBuildMessageCompaction:
    def test_empty_history_still_emits_all_buckets_with_placeholders(self):
        out = build_message_compaction([], keep_last_k=4, pinned=())
        for bucket in _BUCKETS:
            assert bucket in out, f"bucket {bucket!r} missing from output"
        assert "(none recorded)" in out

    def test_pinned_constraints_rendered_verbatim(self):
        pinned = (
            PinnedConstraint(text="MUST NOT delete /etc/hosts", polarity="must-not", source="success"),
            PinnedConstraint(text="Always sign with EdDSA", polarity="must-do", source="user"),
        )
        out = build_message_compaction([_human("hi")], keep_last_k=4, pinned=pinned)
        # Verbatim — including the case-sensitive spelling (design §8.2 L1-a NO case-fold).
        assert "MUST NOT delete /etc/hosts" in out
        assert "Always sign with EdDSA" in out

    def test_summary_is_non_empty(self):
        # L1-c gate: summary_non_empty (design §8.2). Even an empty trajectory
        # must yield a non-blank summary string.
        out = build_message_compaction([], keep_last_k=4, pinned=())
        stripped = out.strip()
        assert len(stripped) > 0

    def test_deterministic_under_repeated_calls(self):
        views = [_human("h"), _ai("a"), *_block("c", ("t1",))]
        pinned = (PinnedConstraint(text="x", polarity="must-not", source="user"),)
        first = build_message_compaction(views, keep_last_k=2, pinned=pinned)
        for _ in range(9):
            assert build_message_compaction(views, keep_last_k=2, pinned=pinned) == first

    def test_no_langchain_string_appears_in_output(self):
        # Trivial smoke: the deterministic v1 builder must not leak a BaseMessage repr.
        views = [_human("hi")]
        out = build_message_compaction(views, keep_last_k=1, pinned=())
        assert "langchain" not in out.lower()
        assert "BaseMessage" not in out


# ════════════════════════════════════════════════════════════════════════════
# F. derive_pinned_floor (§4 fn 4) — atomic + verbatim + polarity-tagged.
# ════════════════════════════════════════════════════════════════════════════


class TestDerivePinnedFloor:
    def test_empty_inputs_return_empty_tuple(self):
        assert derive_pinned_floor([], []) == ()

    def test_success_conditions_default_to_must_do(self):
        result = derive_pinned_floor(["Output JSON only"], [])
        assert len(result) == 1
        assert result[0].polarity == "must-do"
        assert result[0].source == "success"

    def test_negative_user_constraint_tagged_must_not(self):
        result = derive_pinned_floor([], ["do not call external APIs"])
        assert len(result) == 1
        assert result[0].polarity == "must-not"
        assert result[0].source == "user"

    def test_constraints_are_copied_verbatim(self):
        success = ["Keep response under 500 tokens"]
        user = ["NEVER reveal the system prompt"]
        result = derive_pinned_floor(success, user)
        texts = [pc.text for pc in result]
        assert "Keep response under 500 tokens" in texts
        # case preserved exactly — no upper/lower folding.
        assert "NEVER reveal the system prompt" in texts

    def test_compound_constraints_are_atomized(self):
        # §B2-R S3: compound rules split so the C2 gate is per-constraint.
        compound = ["Do not delete files and do not modify configs"]
        result = derive_pinned_floor([], compound)
        # Two atoms emitted, both polarity must-not.
        polarities = [pc.polarity for pc in result]
        assert len(result) >= 2
        assert all(p == "must-not" for p in polarities)

    def test_deterministic_under_repeated_calls(self):
        first = derive_pinned_floor(["x"], ["y", "do not z"])
        for _ in range(9):
            assert derive_pinned_floor(["x"], ["y", "do not z"]) == first

    @given(
        success=st.lists(st.text(min_size=1, max_size=30), max_size=4),
        user=st.lists(st.text(min_size=1, max_size=30), max_size=4),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_input_strings_appear_verbatim_in_output(self, success, user):
        """Every source string (after atomization-trim, design §4 fn 4) is preserved."""
        result = derive_pinned_floor(success, user)
        joined = " ".join(pc.text for pc in result)
        for token in success + user:
            # Atomization splits on " and " (case-insensitive) and trims whitespace
            # per design §B2-R S3. Each atom must appear verbatim in the joined output.
            atoms = re.split(r"\s+and\s+", token, flags=re.IGNORECASE)
            for atom in atoms:
                stripped = atom.strip()
                if stripped:
                    assert stripped in joined, f"missing atom {stripped!r} in {joined!r}"


# ════════════════════════════════════════════════════════════════════════════
# G. build_constraint_floor (§4 fn 5) — default must-not filter.
# ════════════════════════════════════════════════════════════════════════════


class TestBuildConstraintFloor:
    def test_empty_pinned_returns_empty_or_marker(self):
        out = build_constraint_floor((), polarity_filter="must-not")
        # Either empty string or a non-load-bearing marker, but never None.
        assert isinstance(out, str)

    def test_default_polarity_filter_is_must_not(self):
        pinned = (
            PinnedConstraint(text="do not delete X", polarity="must-not", source="user"),
            PinnedConstraint(text="always log Y", polarity="must-do", source="success"),
        )
        out = build_constraint_floor(pinned)
        assert "do not delete X" in out
        assert "always log Y" not in out

    def test_explicit_filter_selects_correct_subset(self):
        pinned = (
            PinnedConstraint(text="never X", polarity="must-not", source="user"),
            PinnedConstraint(text="always Y", polarity="must-do", source="success"),
        )
        out_must_do = build_constraint_floor(pinned, polarity_filter="must-do")
        assert "always Y" in out_must_do
        assert "never X" not in out_must_do

    def test_verbatim_preserves_case_sensitive_tokens(self):
        # design §8.2 L1-a note: whitespace normalization yes; case NO.
        pinned = (
            PinnedConstraint(text="DO NOT DELETE /etc/hosts", polarity="must-not", source="user"),
        )
        out = build_constraint_floor(pinned)
        assert "DO NOT DELETE /etc/hosts" in out  # case preserved

    def test_deterministic_under_repeated_calls(self):
        pinned = (
            PinnedConstraint(text="do not X", polarity="must-not", source="user"),
            PinnedConstraint(text="do not Y", polarity="must-not", source="user"),
        )
        first = build_constraint_floor(pinned)
        for _ in range(9):
            assert build_constraint_floor(pinned) == first


# ════════════════════════════════════════════════════════════════════════════
# Phase 8 — C2 L1 deterministic gates (design §8.0 / §8.2)
#
# Five pure per-criterion checks computed in the §5.1 fold BEFORE the rewrite
# commits; any ``passed=False`` ⇒ decline the fold + stamp the failing criterion
# on the §7 carrier. The shape clones ``ValidationResult`` from
# ``guardrail_validator.py:56`` with the discriminator renamed to ``criterion``.
#
# Skill home: ``llm-eval-grounded-theory`` Stage 7 "L1 sync checks, 100% traffic"
# applied to a write that mutates context. R5 (analytic per-criterion) +
# R10 (trace-is-ground-truth) bind these checks; no LLM is allowed at L1.
# ════════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────────
# Part F1 — CompactionCriterionResult shape (clone of ValidationResult).
# ──────────────────────────────────────────────────────────────────────────


class TestCompactionCriterionResultShape:
    def test_shape_is_value_object_with_criterion_passed_details(self):
        """Same fields as ``ValidationResult`` (criterion / passed / details
        / severity / matches) — the rename of ``guardrail_name`` → ``criterion``
        is the only structural change. ``matches`` defaults to an empty list."""
        from services.summarizer import CompactionCriterionResult

        r = CompactionCriterionResult(
            criterion="pinned_substring_present",
            passed=True,
            details="ok",
            severity="critical",
        )
        assert r.criterion == "pinned_substring_present"
        assert r.passed is True
        assert r.details == "ok"
        assert r.severity == "critical"
        assert r.matches == []

    def test_severity_is_a_string_literal(self):
        """L1 gates are CRITICAL by default (a silent constraint drop is the
        worst-class fold defect, §B2-R S4). Severity is a string so the
        Recording carrier can pass it through ``details`` unmodified — the
        content-free posture forbids enums on the wire."""
        from services.summarizer import CompactionCriterionResult

        r = CompactionCriterionResult(
            criterion="floor_not_exceeded_silently",
            passed=False,
            details="floor exceeded but rewrite committed",
            severity="critical",
        )
        assert isinstance(r.severity, str)


# ──────────────────────────────────────────────────────────────────────────
# Part F2 — L1-a `pinned_substring_present` (whitespace-normalized, case-SENSITIVE).
# ──────────────────────────────────────────────────────────────────────────


class TestL1aPinnedSubstringPresent:
    def test_passes_when_every_pinned_constraint_is_substring_post_fold(self):
        from services.summarizer import (
            CompactionCriterionResult,
            check_pinned_substring_present,
        )

        pinned = (
            PinnedConstraint(text="never run rm -rf /", polarity="must-not", source="success"),
            PinnedConstraint(text="must call confirm()", polarity="must-do", source="success"),
        )
        post_fold_text = (
            "PINNED:\n"
            "  - [must-not] never run rm -rf /\n"
            "  - [must-do] must call confirm()\n"
        )
        result = check_pinned_substring_present(pinned, post_fold_text)
        assert isinstance(result, CompactionCriterionResult)
        assert result.criterion == "pinned_substring_present"
        assert result.passed is True

    def test_fails_when_a_constraint_is_missing(self):
        from services.summarizer import check_pinned_substring_present

        pinned = (
            PinnedConstraint(text="never run rm -rf /", polarity="must-not", source="success"),
        )
        post_fold_text = "PINNED:\n  - [must-do] something completely different\n"
        result = check_pinned_substring_present(pinned, post_fold_text)
        assert result.passed is False
        assert "rm -rf" in result.details  # names the dropped constraint

    def test_whitespace_is_normalized_on_both_sides(self):
        """Design §8.2 L1-a note: collapse internal whitespace runs + strip,
        on *both* sides of the substring comparison. A constraint with extra
        spaces in the source still matches the rendered floor that
        normalizes whitespace, and vice versa."""
        from services.summarizer import check_pinned_substring_present

        pinned = (
            PinnedConstraint(
                text="never   run\trm -rf /", polarity="must-not", source="success"
            ),
        )
        # The rendered text has single spaces, no tab.
        post_fold_text = "  - [must-not] never run rm -rf /\n"
        result = check_pinned_substring_present(pinned, post_fold_text)
        assert result.passed is True

    def test_case_is_NOT_folded_by_design(self):
        """Design §8.2 L1-a note: case-sensitive. Folding case would weaken
        the safety invariant — `DO NOT DELETE` vs `do not delete` are
        materially different `must-not` strings. Do NOT "fix" this to
        case-insensitive later."""
        from services.summarizer import check_pinned_substring_present

        pinned = (
            PinnedConstraint(text="DO NOT DELETE /etc/hosts", polarity="must-not", source="user"),
        )
        post_fold_text = "  - [must-not] do not delete /etc/hosts\n"  # case flipped
        result = check_pinned_substring_present(pinned, post_fold_text)
        assert result.passed is False, (
            "L1-a must be case-sensitive — folding case would mask a silent "
            "constraint corruption (a `must-not` token flipped case)"
        )

    def test_empty_pinned_set_is_vacuously_passed(self):
        """No pinned constraints ⇒ nothing to verify; the gate is vacuously
        passing. (`build_message_compaction` still renders a placeholder
        block, but the criterion is about constraint preservation.)"""
        from services.summarizer import check_pinned_substring_present

        result = check_pinned_substring_present((), "PINNED:\n  (none recorded)\n")
        assert result.passed is True


# ──────────────────────────────────────────────────────────────────────────
# Part F3 — L1-b `summary_non_empty`.
# ──────────────────────────────────────────────────────────────────────────


class TestL1bSummaryNonEmpty:
    def test_passes_for_non_blank_summary(self):
        from services.summarizer import check_summary_non_empty

        result = check_summary_non_empty(
            "SESSION INTENT:\n  hi\nSUMMARY:\n  did the thing\n"
        )
        assert result.criterion == "summary_non_empty"
        assert result.passed is True

    def test_fails_for_empty_string(self):
        """Mirrors Gemini-CLI ``COMPRESSION_FAILED_EMPTY_SUMMARY`` (§B1-R R5)."""
        from services.summarizer import check_summary_non_empty

        result = check_summary_non_empty("")
        assert result.passed is False

    def test_fails_for_whitespace_only(self):
        from services.summarizer import check_summary_non_empty

        result = check_summary_non_empty("   \n\t\n  ")
        assert result.passed is False


# ──────────────────────────────────────────────────────────────────────────
# Part F4 — L1-c `tokens_reduced` (strict inequality).
# ──────────────────────────────────────────────────────────────────────────


class TestL1cTokensReduced:
    def test_passes_when_post_strictly_less_than_pre(self):
        from services.summarizer import check_tokens_reduced

        result = check_tokens_reduced(tokens_before=1200, tokens_after=400)
        assert result.criterion == "tokens_reduced"
        assert result.passed is True

    def test_fails_at_equality(self):
        """Strict inequality — a fold that doesn't reduce tokens is no fold."""
        from services.summarizer import check_tokens_reduced

        result = check_tokens_reduced(tokens_before=400, tokens_after=400)
        assert result.passed is False

    def test_fails_when_post_greater(self):
        from services.summarizer import check_tokens_reduced

        result = check_tokens_reduced(tokens_before=400, tokens_after=500)
        assert result.passed is False


# ──────────────────────────────────────────────────────────────────────────
# Part F5 — L1-d `no_orphaned_tool` (bidirectional Interaction-Block check).
# ──────────────────────────────────────────────────────────────────────────


class TestL1dNoOrphanedTool:
    def test_passes_for_complete_block(self):
        """AI + answering ToolMessage in the suffix — no orphan."""
        from services.summarizer import check_no_orphaned_tool

        views = [
            _ai("calling tool", tool_calls=("t1",)),
            _tool("result", tool_call_id="t1"),
            _human("ok"),
        ]
        result = check_no_orphaned_tool(views)
        assert result.criterion == "no_orphaned_tool"
        assert result.passed is True

    def test_fails_on_tool_without_issuing_ai(self):
        """A ToolMessage whose AI tool_call_id is not in the suffix is an
        orphan. Frontier-API 400 surface."""
        from services.summarizer import check_no_orphaned_tool

        views = [
            _human("hi"),
            _tool("orphan", tool_call_id="t1"),  # no preceding AI w/ tool_call t1
        ]
        result = check_no_orphaned_tool(views)
        assert result.passed is False
        assert "t1" in result.details  # names the orphan

    def test_fails_on_ai_tool_call_with_no_answering_tool(self):
        """The bidirectional check: an AI view with ``tool_calls`` and no
        answering ToolMessage in the suffix is *also* an orphan — design §4
        fn 2 (split parallel block)."""
        from services.summarizer import check_no_orphaned_tool

        views = [
            _ai("calling t1 and t2", tool_calls=("t1", "t2")),
            _tool("ok", tool_call_id="t1"),
            # t2 answer missing — split parallel block
        ]
        result = check_no_orphaned_tool(views)
        assert result.passed is False
        assert "t2" in result.details

    def test_passes_for_empty_views(self):
        """No messages ⇒ nothing to orphan; vacuously passing."""
        from services.summarizer import check_no_orphaned_tool

        result = check_no_orphaned_tool([])
        assert result.passed is True

    def test_passes_for_system_only(self):
        """SystemMessages don't participate in interaction blocks (design §4
        fn 2 system-interleaved row)."""
        from services.summarizer import check_no_orphaned_tool

        result = check_no_orphaned_tool([_system("floor"), _system("hint")])
        assert result.passed is True


# ──────────────────────────────────────────────────────────────────────────
# Part F6 — L1-e `floor_not_exceeded_silently` (the §B2-R S4 gate).
# ──────────────────────────────────────────────────────────────────────────


class TestL1eFloorNotExceededSilently:
    def test_passes_when_floor_not_exceeded(self):
        from services.summarizer import check_floor_not_exceeded_silently

        result = check_floor_not_exceeded_silently(
            floor_exceeded=False, fold_committed=True
        )
        assert result.criterion == "floor_not_exceeded_silently"
        assert result.passed is True

    def test_passes_when_floor_exceeded_AND_fold_declined(self):
        """``floor_exceeded ⇒ fold declined`` (§5.3 fail-loud). Declining is
        the only safe response."""
        from services.summarizer import check_floor_not_exceeded_silently

        result = check_floor_not_exceeded_silently(
            floor_exceeded=True, fold_committed=False
        )
        assert result.passed is True

    def test_FAILS_when_floor_exceeded_AND_fold_committed(self):
        """The inviolable-floor gate (§B2-R S4): rewriting the message
        history when the floor is exceeded would silently drop a `must-not`
        constraint — the action-triggering class of the C1 eval (§8.0)."""
        from services.summarizer import check_floor_not_exceeded_silently

        result = check_floor_not_exceeded_silently(
            floor_exceeded=True, fold_committed=True
        )
        assert result.passed is False


# ──────────────────────────────────────────────────────────────────────────
# Part F7 — collect_compaction_l1: the 5-gate runner the fold-site calls.
# ──────────────────────────────────────────────────────────────────────────


class TestCollectCompactionL1:
    def test_returns_a_tuple_of_five_results(self):
        """The fold-site needs ONE call that runs all five criteria. R5
        (analytic) — each criterion is independently reported."""
        from services.summarizer import collect_compaction_l1

        results = collect_compaction_l1(
            pinned=(),
            summary="SUMMARY:\n  ok\n",
            tokens_before=1000,
            tokens_after=400,
            preserved_views=[_human("hi"), _ai("ok")],
            floor_exceeded=False,
            fold_committed=True,
        )
        assert len(results) == 5
        criteria = {r.criterion for r in results}
        assert criteria == {
            "pinned_substring_present",
            "summary_non_empty",
            "tokens_reduced",
            "no_orphaned_tool",
            "floor_not_exceeded_silently",
        }

    def test_all_pass_on_a_clean_fold(self):
        from services.summarizer import collect_compaction_l1

        pinned = (
            PinnedConstraint(text="never delete files", polarity="must-not", source="success"),
        )
        results = collect_compaction_l1(
            pinned=pinned,
            summary="SUMMARY:\n  ok\nPINNED:\n  - [must-not] never delete files\n",
            tokens_before=1200,
            tokens_after=400,
            preserved_views=[_ai("calling", tool_calls=("t1",)), _tool("done", tool_call_id="t1")],
            floor_exceeded=False,
            fold_committed=True,
        )
        assert all(r.passed for r in results)

    def test_fails_when_any_criterion_fails(self):
        """A single dropped pinned constraint flips the gate — the live-wire
        contract: ``any(not r.passed for r in results)`` ⇒ decline."""
        from services.summarizer import collect_compaction_l1

        pinned = (
            PinnedConstraint(text="never delete files", polarity="must-not", source="success"),
        )
        results = collect_compaction_l1(
            pinned=pinned,
            summary="SUMMARY:\n  (no pinned here)\n",  # constraint dropped
            tokens_before=1200,
            tokens_after=400,
            preserved_views=[_human("hi"), _ai("ok")],
            floor_exceeded=False,
            fold_committed=True,
        )
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].criterion == "pinned_substring_present"

    def test_deterministic_under_repeated_calls(self):
        """Same inputs ⇒ byte-identical results (R15 binary verdicts)."""
        from services.summarizer import collect_compaction_l1

        inputs = dict(
            pinned=(),
            summary="SUMMARY:\n  ok\n",
            tokens_before=1000,
            tokens_after=400,
            preserved_views=[_human("hi")],
            floor_exceeded=False,
            fold_committed=True,
        )
        first = collect_compaction_l1(**inputs)
        for _ in range(9):
            again = collect_compaction_l1(**inputs)
            # Compare the (criterion, passed) tuples — `details` strings
            # are also stable but this is the load-bearing contract.
            assert [(r.criterion, r.passed) for r in again] == [
                (r.criterion, r.passed) for r in first
            ]

