"""L1 unit + property tests for ``services.governance.iaa``.

Pyramid layer:  L1 Deterministic (TDD Protocol A — Red-Green-Refactor)
Architecture:  Horizontal (services/governance/). The Phase 5 α-gate plumbing
                — Krippendorff α on nominal labels, disagreement diffs, and
                adjudication application — lives here as pure functions so
                CLI scripts (Stage 5 α gate) and downstream tooling
                (manifest builder, Phase 6 assembly) can both import it
                without a subprocess hack.

Why pure-stdlib L1, not a SciPy/krippendorff library import: the function is
~25 lines of nominal-distance combinatorics that we want to *prove* in tests,
not delegate. Importing a third-party α library would convert this test file
into an integration test against an external implementation (anti-pattern
AP-1 Tautological: re-running the algorithm to derive the expected value).

Anti-patterns guarded against (per ``research/tdd_agentic_systems_prompt.md``):

* AP-1 Tautological: every α expected value is hand-computed by the test
  author, written into the test as a literal, and cited in a comment with
  the formula and the substituted numbers.
* AP-2 Mock addiction: zero mocks. Pure-function input → pure-function output.
* AP-3 Determinism theater: the underlying function is deterministic by
  construction — no LLM in sight; the property tests prove that
  reordering raters within an item doesn't change α.
* AP-5 Live LLM in CI: zero LLM.
* AP-6 Gap blindness: every behavioral contract has a *rejection* test
  (corrupt input → expected failure value) authored BEFORE the acceptance
  test, per Failure-Paths-First.
* AP-7 Cross-layer dependency leak: imports only from
  ``services.governance.iaa`` (its own layer). No ``components`` /
  ``orchestration`` / ``governance`` (meta-layer) imports.

These tests follow Pattern 1 (Property-Based Schema Test — externally
derived expected values) and Pattern 4 (Consumer-Driven Contract Test —
the script + the assembler are the two consumers).
"""

from __future__ import annotations

import math

import pytest

from services.governance.iaa import (
    apply_adjudication,
    compute_disagreement_diff,
    krippendorff_alpha_nominal,
    landis_koch_band,
    normalize_bool_label,
)


# ───────────────────────────────────────────────────────────────────────────
# krippendorff_alpha_nominal — externally-verified property + edge cases
# ───────────────────────────────────────────────────────────────────────────


class TestKrippendorffAlphaNominalEdges:
    """Failure paths first: degenerate inputs MUST produce well-defined
    NaN-or-edge results, never crash. Per AP-6: every gap that exists in the
    domain (no data, one rater, single label class) gets its own test."""

    def test_empty_input_returns_nan(self) -> None:
        """No items → no observations → α undefined. Function MUST return
        NaN, not 0.0 (0.0 would mean 'chance agreement', which is a real
        claim about a real dataset, not 'no dataset')."""
        result = krippendorff_alpha_nominal([])
        assert math.isnan(result)

    def test_all_items_have_fewer_than_two_raters_returns_nan(self) -> None:
        """Each item has < 2 ratings → no pairs available → α undefined.
        Real-world cause: every row had at most one annotator fill it."""
        items = [["true"], ["false"], [""]]
        result = krippendorff_alpha_nominal(items)
        assert math.isnan(result)

    def test_single_label_class_after_filtering_returns_nan(self) -> None:
        """If after dropping empties only one nominal class remains across
        ALL ratings, expected agreement de=0 and α is undefined (0/0).
        This catches the silent-NaN-from-de=0 bug."""
        # Three items, every (non-empty) rater says "true".
        items = [["true", "true"], ["true", "true"], ["true", "true"]]
        result = krippendorff_alpha_nominal(items)
        assert math.isnan(result)


class TestKrippendorffAlphaNominalKnownValues:
    """Acceptance tests with externally-derived expected α. Every expected
    value below is hand-computed by substituting into:

        α = 1 − Do/De
        Do = (1/Σm) Σ_pairs δ
        De = 1 − Σ c·(c−1) / (n·(n−1))

    with δ=0 for matching nominal labels and δ=1 otherwise. Each test
    comments its substitutions in full so a reviewer can verify without
    re-running the algorithm.
    """

    def test_perfect_agreement_on_balanced_binary_returns_one(self) -> None:
        """Six items, 50/50 true/false, both raters perfectly agree.
        Do = 0/6 = 0 ⇒ α = 1 − 0/De = 1.0 regardless of De>0."""
        items = [
            ["true", "true"],
            ["true", "true"],
            ["true", "true"],
            ["false", "false"],
            ["false", "false"],
            ["false", "false"],
        ]
        assert krippendorff_alpha_nominal(items) == pytest.approx(1.0)

    def test_total_disagreement_on_balanced_binary_is_minus_one(self) -> None:
        """Six items: every pair disagrees in opposite direction.
        Tallies: 6 'true', 6 'false', n=12 total ratings.
        Pairs (one per item): 6 pairs, all δ=1 ⇒ Do = 6/6 = 1.
        De = 1 − [6·5 + 6·5]/(12·11) = 1 − 60/132 = 72/132 = 6/11.
        α = 1 − 1/(6/11) = 1 − 11/6 = −5/6 ≈ −0.83333.

        Why the test exists: confirms the formula handles 'worse than
        chance' (negative α) symmetrically. A bug that floors at 0 would
        slip past every positive-α test."""
        items = [
            ["true", "false"],
            ["true", "false"],
            ["true", "false"],
            ["false", "true"],
            ["false", "true"],
            ["false", "true"],
        ]
        expected = -5.0 / 6.0
        assert krippendorff_alpha_nominal(items) == pytest.approx(expected, abs=1e-6)

    def test_three_quarters_agreement_balanced_binary(self) -> None:
        """Four items: 3 agree, 1 disagrees. Balanced class distribution.

        Items: [t,t], [f,f], [t,t], [f,t]
        Tallies: 'true' appears 5 times, 'false' appears 3 times, n=8.
        Pairs: 4 pairs, δ values [0, 0, 0, 1] ⇒ Do = 1/4 = 0.25.
        De = 1 − [5·4 + 3·2]/(8·7) = 1 − 26/56 = 30/56 = 15/28 ≈ 0.53571.
        α = 1 − 0.25/(15/28) = 1 − 7/15 = 8/15 ≈ 0.53333."""
        items = [
            ["true", "true"],
            ["false", "false"],
            ["true", "true"],
            ["false", "true"],
        ]
        expected = 8.0 / 15.0
        assert krippendorff_alpha_nominal(items) == pytest.approx(expected, abs=1e-6)

    def test_three_label_nominal_perfect_agreement(self) -> None:
        """α generalizes to non-binary nominal codes; perfect agreement on
        a 3-class label set must still return 1.0 (sanity-check that the
        function isn't accidentally binary-only)."""
        items = [
            ["pass", "pass"],
            ["fail", "fail"],
            ["alert", "alert"],
            ["pass", "pass"],
            ["fail", "fail"],
        ]
        assert krippendorff_alpha_nominal(items) == pytest.approx(1.0)

    def test_missing_one_rater_per_item_drops_that_pair(self) -> None:
        """Items with < 2 present ratings are SKIPPED, not counted as
        disagreement. Drives this expectation by interleaving partial rows
        with perfect-agreement rows and asserting α=1.0 (which would NOT
        hold if the partial rows leaked into the disagreement count)."""
        items = [
            ["true", "true"],  # counted
            ["true", ""],  # skipped — only one rater
            ["false", "false"],  # counted
            ["", "false"],  # skipped
            ["true", "true"],  # counted
        ]
        assert krippendorff_alpha_nominal(items) == pytest.approx(1.0)


class TestKrippendorffAlphaPermutationInvariance:
    """Property test (Pattern 1): re-ordering raters WITHIN an item must
    not change α. This guards against a buggy implementation that
    accidentally treats r1 and r2 as ordered (e.g., a directional 'r1
    disagrees with r2' count instead of an unordered pairwise distance)."""

    def test_swapping_rater_order_preserves_alpha(self) -> None:
        items_original = [
            ["true", "false"],
            ["false", "true"],
            ["true", "true"],
            ["false", "false"],
            ["true", "false"],
        ]
        items_swapped = [[b, a] for a, b in items_original]
        a_original = krippendorff_alpha_nominal(items_original)
        a_swapped = krippendorff_alpha_nominal(items_swapped)
        # Use math.isclose because both are float; identical inputs but
        # the path through combinations() differs slightly.
        assert math.isclose(a_original, a_swapped, abs_tol=1e-12)


# ───────────────────────────────────────────────────────────────────────────
# landis_koch_band — exact boundary classification (cited from spec)
# ───────────────────────────────────────────────────────────────────────────


class TestLandisKochBand:
    """Bands are integral to Stage 5 acceptance reporting; boundary
    values are spelled out so a future tweak to the function can't
    silently re-classify e.g. 0.80 as 'almost perfect'."""

    @pytest.mark.parametrize(
        "alpha,band",
        [
            (-0.5, "poor"),
            (-0.0001, "poor"),
            (0.0, "slight"),
            (0.20, "slight"),
            (0.2001, "fair"),
            (0.40, "fair"),
            (0.4001, "moderate"),
            (0.60, "moderate"),
            (0.6001, "substantial"),
            (0.80, "substantial"),
            (0.8001, "almost perfect"),
            (1.0, "almost perfect"),
        ],
    )
    def test_band_boundaries(self, alpha: float, band: str) -> None:
        assert landis_koch_band(alpha) == band


# ───────────────────────────────────────────────────────────────────────────
# normalize_bool_label — pinned mapping, no fuzzy intent inference
# ───────────────────────────────────────────────────────────────────────────


class TestNormalizeBoolLabel:
    """The α gate accepts only a fixed set of truthy/falsy spellings; any
    other value passes through unchanged (so the α computation skips it
    as a missing rating, not silently coerces it to a class)."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", "true"),
            ("True", "true"),
            ("TRUE", "true"),
            ("t", "true"),
            ("Y", "true"),
            ("y", "true"),
            ("yes", "true"),
            ("1", "true"),
            ("false", "false"),
            ("False", "false"),
            ("FALSE", "false"),
            ("f", "false"),
            ("N", "false"),
            ("no", "false"),
            ("0", "false"),
            ("", ""),
            ("   ", ""),
            ("maybe", "maybe"),  # passthrough — α treats as a 3rd class
            ("partially", "partially"),
        ],
    )
    def test_normalizes_canonical_spellings_passes_through_others(
        self, raw: str, expected: str
    ) -> None:
        assert normalize_bool_label(raw) == expected


# ───────────────────────────────────────────────────────────────────────────
# compute_disagreement_diff — what the adjudicator sees
# ───────────────────────────────────────────────────────────────────────────


class TestComputeDisagreementDiff:
    """Failure paths first, then the happy-path contract."""

    def test_empty_rows_returns_empty_list(self) -> None:
        """No rows ⇒ no disagreements. Must not crash; returns []."""
        assert compute_disagreement_diff([]) == []

    def test_no_disagreements_returns_empty_list(self) -> None:
        """All raters agree everywhere ⇒ adjudication has nothing to do."""
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-002", "r1_goal_met": "false", "r2_goal_met": "false"},
        ]
        assert compute_disagreement_diff(rows) == []

    def test_skips_rows_with_missing_ratings(self) -> None:
        """A row where either rater hasn't filled in their column is NOT
        a disagreement (there's nothing to disagree with yet). Must skip
        cleanly — listing it as a disagreement would surface false
        adjudication requests."""
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": ""},
            {"item_id": "GJ-002", "r1_goal_met": "", "r2_goal_met": "false"},
        ]
        assert compute_disagreement_diff(rows) == []

    def test_reports_mixed_disagreements_preserving_order(self) -> None:
        """Happy path: two of four rows differ. Returned diff preserves
        input order (so the adjudicator's CSV mirrors the sheet order)
        and uses normalized spellings (so the adjudicator sees the
        canonical 'true'/'false', not the raw 'Y'/'N')."""
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-002", "r1_goal_met": "Y", "r2_goal_met": "N"},  # disagree
            {"item_id": "GJ-003", "r1_goal_met": "false", "r2_goal_met": "false"},
            {
                "item_id": "GJ-004",
                "r1_goal_met": "false",
                "r2_goal_met": "1",
            },  # disagree
        ]
        diff = compute_disagreement_diff(rows)
        assert diff == [
            {"item_id": "GJ-002", "r1": "true", "r2": "false"},
            {"item_id": "GJ-004", "r1": "false", "r2": "true"},
        ]

    def test_alternate_column_name(self) -> None:
        """compute_disagreement_diff(column='failure_mode') runs the same
        comparison against r1_failure_mode / r2_failure_mode. Catches a
        column-prefix hardcoding bug."""
        rows = [
            {
                "item_id": "GJ-008",
                "r1_failure_mode": "fabricated-progress",
                "r2_failure_mode": "fluent-evasion",
            },
            {
                "item_id": "GJ-001B",
                "r1_failure_mode": "",
                "r2_failure_mode": "",
            },
        ]
        diff = compute_disagreement_diff(rows, column="failure_mode")
        assert diff == [
            {
                "item_id": "GJ-008",
                "r1": "fabricated-progress",
                "r2": "fluent-evasion",
            },
        ]


# ───────────────────────────────────────────────────────────────────────────
# apply_adjudication — populates the gold columns under invariants
# ───────────────────────────────────────────────────────────────────────────


class TestApplyAdjudication:
    """The adjudication step turns a labeled sheet into a frozen gold-set.
    Failure paths first."""

    def test_rejects_decision_for_non_disagreement(self) -> None:
        """Adjudication is only valid for items that genuinely disagree.
        A decision keyed by an item the raters agreed on indicates the
        adjudicator is working off a stale diff. MUST raise."""
        rows = [
            {
                "item_id": "GJ-001",
                "r1_goal_met": "true",
                "r2_goal_met": "true",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
        ]
        decisions = {"GJ-001": {"goal_met": "true", "failure_mode": ""}}
        with pytest.raises(ValueError, match=r"(?i)not a disagreement|already agree"):
            apply_adjudication(rows, decisions)

    def test_rejects_unresolved_disagreement(self) -> None:
        """If the raters disagree on a row and the decisions dict doesn't
        cover it, the adjudication is incomplete. MUST raise — silently
        leaving the gold column blank would let a half-adjudicated set
        flow into Phase 6."""
        rows = [
            {
                "item_id": "GJ-002",
                "r1_goal_met": "true",
                "r2_goal_met": "false",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
        ]
        with pytest.raises(ValueError, match=r"(?i)unresolved|missing decision"):
            apply_adjudication(rows, {})

    def test_rejects_invalid_goal_met_decision_value(self) -> None:
        """Decisions must be canonical 'true'/'false'. A typo like 'tru'
        or 'maybe' must be caught up-front, not after the sheet is
        written and Phase 6 trips on its own schema validation."""
        rows = [
            {
                "item_id": "GJ-002",
                "r1_goal_met": "true",
                "r2_goal_met": "false",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
        ]
        decisions = {"GJ-002": {"goal_met": "maybe", "failure_mode": ""}}
        with pytest.raises(ValueError, match=r"(?i)goal_met.*'maybe'|invalid"):
            apply_adjudication(rows, decisions)

    def test_acceptance_populates_only_disagreement_rows(self) -> None:
        """Happy path: 4 rows, 2 disagreements. After apply_adjudication
        the two disagreement rows get their adjudicated_* columns filled
        from the decisions; the two agreement rows are left UNTOUCHED
        (the gold column is implicit-from-agreement, not re-stamped here;
        Phase 6 assembly handles the canonicalization)."""
        rows = [
            {
                "item_id": "GJ-001",
                "r1_goal_met": "true",
                "r2_goal_met": "true",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
            {
                "item_id": "GJ-002",
                "r1_goal_met": "true",
                "r2_goal_met": "false",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
            {
                "item_id": "GJ-003",
                "r1_goal_met": "false",
                "r2_goal_met": "false",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
            {
                "item_id": "GJ-004",
                "r1_goal_met": "false",
                "r2_goal_met": "true",
                "adjudicated_goal_met": "",
                "adjudicated_failure_mode": "",
            },
        ]
        decisions = {
            "GJ-002": {"goal_met": "false", "failure_mode": "fluent-evasion"},
            "GJ-004": {"goal_met": "true", "failure_mode": ""},
        }
        out = apply_adjudication(rows, decisions)
        # disagreements populated
        assert out[1]["adjudicated_goal_met"] == "false"
        assert out[1]["adjudicated_failure_mode"] == "fluent-evasion"
        assert out[3]["adjudicated_goal_met"] == "true"
        assert out[3]["adjudicated_failure_mode"] == ""
        # agreements untouched
        assert out[0]["adjudicated_goal_met"] == ""
        assert out[0]["adjudicated_failure_mode"] == ""
        assert out[2]["adjudicated_goal_met"] == ""
        assert out[2]["adjudicated_failure_mode"] == ""
