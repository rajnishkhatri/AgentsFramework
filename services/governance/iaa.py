"""Inter-annotator agreement primitives for GoalJudge Stage 5.

Pyramid layer:   L1 Deterministic — pure-stdlib functions.
Architecture:    Horizontal (services/governance/). Imported by both the
                 Stage 5 α-gate CLI (``scripts/compute_goaljudge_stage5_alpha.py``)
                 and the Phase 6 assembly script. No I/O, no logging, no LLM.

Public API:

* :func:`krippendorff_alpha_nominal` — Krippendorff's α for nominal labels
  with ≥ 2 raters and partial coverage tolerated.
* :func:`landis_koch_band` — verbal band classifier (Landis & Koch 1977).
* :func:`normalize_bool_label` — canonical truthy/falsy spelling, leaves
  anything else untouched (so α treats it as a separate class or a
  missing rating depending on emptiness).
* :func:`compute_disagreement_diff` — list of (item_id, r1, r2) rows where
  the two raters disagree on a given suffix column (default ``goal_met``).
* :func:`apply_adjudication` — populate ``adjudicated_*`` columns under
  invariants: every disagreement must have a decision; no decision may
  target a row the raters agreed on.

Design discipline (per ``research/tdd_agentic_systems_prompt.md``):

* AP-1 Tautological — α is computed via the canonical Krippendorff
  combinatorial formula; tests cite the formula and substitute by hand.
* AP-6 Gap blindness — empty / single-rater / single-class inputs return
  ``float('nan')`` explicitly rather than 0.0 (which would imply a real
  claim about chance agreement on a non-dataset).
* AP-7 Cross-layer dependency leak — zero imports from ``components/``,
  ``orchestration/``, or other ``services/`` submodules. Pure stdlib.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

# ───────────────────────────────────────────────────────────────────────────
# Vocabulary constants (mirrored, *not* imported, from sibling modules to
# preserve L1 purity).
# ───────────────────────────────────────────────────────────────────────────

_TRUTHY: frozenset[str] = frozenset({"true", "t", "yes", "y", "1"})
_FALSY: frozenset[str] = frozenset({"false", "f", "no", "n", "0"})
_VALID_ADJUDICATED_GOAL_MET: frozenset[str] = frozenset({"true", "false"})


# ───────────────────────────────────────────────────────────────────────────
# Krippendorff α — canonical nominal formula
# ───────────────────────────────────────────────────────────────────────────


def krippendorff_alpha_nominal(items: Sequence[Sequence[str]]) -> float:
    """Krippendorff's α for nominal data with ≥ 2 raters.

    ``items`` is a sequence of per-item rater labels (empty strings denote
    'this rater did not label this item'). The function returns ``NaN``
    for under-defined inputs — see the table below — rather than 0.0,
    because 0.0 is a real claim about chance agreement and would mislead
    a downstream gate.

    Edge behavior:

    +--------------------------------------------+-------------+
    | Condition                                  | Result      |
    +============================================+=============+
    | ``items`` is empty                         | ``NaN``     |
    +--------------------------------------------+-------------+
    | No item has ≥ 2 non-empty raters           | ``NaN``     |
    +--------------------------------------------+-------------+
    | Only one nominal class appears overall     | ``NaN``     |
    +--------------------------------------------+-------------+
    | Two raters, perfect agreement              | 1.0         |
    +--------------------------------------------+-------------+
    | Two raters, total disagreement             | < 0.0       |
    +--------------------------------------------+-------------+

    Implementation note: the function is a direct transcription of the
    nominal-distance formula

        α = 1 − Do/De,
        Do = (1/Σm_pairs) Σ_pairs δ(a,b),     δ = 0 if a==b else 1,
        De = 1 − Σ_c c·(c−1) / (n·(n−1)),

    where ``c`` is each label class's tally and ``n`` is the total number
    of non-empty ratings. No SciPy / external library dependency.
    """
    do_num = do_den = 0
    all_labels: Counter[str] = Counter()
    for labels in items:
        present = [x for x in labels if x]
        m = len(present)
        if m < 2:
            continue
        all_labels.update(present)
        for a, b in combinations(present, 2):
            do_den += 1
            do_num += int(a != b)
    if do_den == 0:
        return float("nan")
    do = do_num / do_den
    n = sum(all_labels.values())
    if n < 2:
        return float("nan")
    de = 1 - sum(c * (c - 1) for c in all_labels.values()) / (n * (n - 1))
    return 1 - (do / de) if de else float("nan")


def landis_koch_band(alpha: float) -> str:
    """Landis & Koch (1977) verbal classifier for κ / α magnitudes.

    Boundary convention (cited by Stage 5 acceptance docs):

    * < 0           — "poor"
    * (0, 0.20]     — "slight"
    * (0.20, 0.40]  — "fair"
    * (0.40, 0.60]  — "moderate"
    * (0.60, 0.80]  — "substantial"
    * (0.80, 1.00]  — "almost perfect"
    """
    if alpha < 0:
        return "poor"
    if alpha <= 0.20:
        return "slight"
    if alpha <= 0.40:
        return "fair"
    if alpha <= 0.60:
        return "moderate"
    if alpha <= 0.80:
        return "substantial"
    return "almost perfect"


# ───────────────────────────────────────────────────────────────────────────
# Boolean label normalization
# ───────────────────────────────────────────────────────────────────────────


def normalize_bool_label(raw: str) -> str:
    """Map common truthy/falsy spellings to canonical ``"true"``/``"false"``.

    Anything not in the pinned set is returned *unchanged* (lower-cased
    strips and whitespace removed). Empty strings stay empty. Non-canonical
    values pass through so α treats them as a distinct class — never silently
    coerce 'maybe' to 'true' or 'false'.
    """
    value = (raw or "").strip().lower()
    if value in _TRUTHY:
        return "true"
    if value in _FALSY:
        return "false"
    return value


# ───────────────────────────────────────────────────────────────────────────
# Disagreement diff
# ───────────────────────────────────────────────────────────────────────────


def compute_disagreement_diff(
    rows: Sequence[Mapping[str, Any]],
    *,
    column: str = "goal_met",
) -> list[dict[str, str]]:
    """Return the rows where r1 and r2 disagree on the named suffix column.

    Output order mirrors input order so the adjudicator's CSV can be
    sorted/diffed against the labeling sheet without surprise.

    Rows where either rater hasn't filled in their column are *skipped*
    (no disagreement yet — one rater hasn't spoken). Skipping is the same
    contract as :func:`krippendorff_alpha_nominal`: an empty cell is
    'missing data', not a class.

    Output shape per element:

    .. code-block:: python

        {"item_id": "GJ-002", "r1": "true", "r2": "false"}
    """
    r1_col = f"r1_{column}"
    r2_col = f"r2_{column}"
    diff: list[dict[str, str]] = []
    for row in rows:
        r1 = normalize_bool_label(str(row.get(r1_col, "")))
        r2 = normalize_bool_label(str(row.get(r2_col, "")))
        if not r1 or not r2:
            continue
        if r1 == r2:
            continue
        diff.append({"item_id": str(row.get("item_id", "")), "r1": r1, "r2": r2})
    return diff


# ───────────────────────────────────────────────────────────────────────────
# Adjudication apply — produces the gold column under invariants
# ───────────────────────────────────────────────────────────────────────────


def apply_adjudication(
    rows: Sequence[Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    """Populate ``adjudicated_goal_met`` / ``adjudicated_failure_mode`` on
    each disagreement row, leave agreement rows untouched.

    Invariants enforced (raised as ``ValueError`` with a descriptive
    message; the script + future Phase 6 caller catch and surface):

    1. Every row whose r1/r2 disagree on ``goal_met`` MUST have a decision.
       Missing decision ⇒ ``"unresolved disagreement"``.
    2. No decision may target a row whose r1/r2 actually agree.
       Stray decision ⇒ ``"not a disagreement"``.
    3. ``goal_met`` decisions must be canonical ``"true"`` or ``"false"``.
       Anything else (typo, empty, 'maybe') ⇒ ``"invalid goal_met"``.

    Returns a fresh list of dict copies — callers can write the result
    back through :class:`csv.DictWriter` without mutating the input.
    """
    # Compute the disagreement set up-front so both checks can reference it.
    disagreements = {d["item_id"] for d in compute_disagreement_diff(rows)}

    # Invariant 2: every decision targets a real disagreement.
    for item_id in decisions:
        if item_id not in disagreements:
            raise ValueError(
                f"decision for {item_id!r} is not a disagreement: "
                "r1 and r2 already agree (or one is missing)."
            )

    # Invariant 1: every disagreement has a decision.
    missing = sorted(disagreements - set(decisions))
    if missing:
        raise ValueError(
            "unresolved disagreement(s); missing decision for: "
            + ", ".join(repr(x) for x in missing)
        )

    # Invariant 3 + write-through.
    out: list[dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        item_id = str(row.get("item_id", ""))
        if item_id in disagreements:
            decision = decisions[item_id]
            goal_met = str(decision.get("goal_met", "")).strip().lower()
            if goal_met not in _VALID_ADJUDICATED_GOAL_MET:
                raise ValueError(
                    f"invalid goal_met decision for {item_id!r}: "
                    f"{goal_met!r}; must be 'true' or 'false'."
                )
            new_row["adjudicated_goal_met"] = goal_met
            new_row["adjudicated_failure_mode"] = str(
                decision.get("failure_mode", "")
            )
        out.append(new_row)
    return out
