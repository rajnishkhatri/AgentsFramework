"""Coach gold-set dataset — ``coach_goldset_v1`` row type + assembly (Task 3.7).

Mirrors the GoalJudge gold-set module (``goaljudge_goldset_dataset.py``) for the
Subject-Coach ``answer_leakage`` label. It provides:

* :class:`CoachGoldsetItem` — one labeled row, ``extra="forbid"``, with the
  contamination firewall (synthetic ⇒ dev-only), the fail-open ban
  (``answer_leakage`` required), and the taxonomy gate (unknown ``leak_channel``
  rejected — gold labels are authored, not soft-coerced like the judge's).
* :func:`compute_test_split_hash` — SHA-256 tamper-evidence over the test split.
* :func:`alpha_answer_leakage` — human–human IAA, REUSING
  ``services.governance.iaa.krippendorff_alpha_nominal`` (NaN → None per AP-6).
* :func:`build_coach_goldset_manifest` — the frozen ``CoachGoldsetManifest``.

**Invariant #7 (services ↛ components):** this module MUST NOT import from
``components/``. The 5 ``LeakChannel`` values are mirrored LOCALLY here (the
``eval_capture.py`` "mirror a shape, don't import it upward" pattern); a drift
test keeps them aligned with ``components/schemas.py`` by value, without importing.

**No live LLM** — pure file/label I/O. Deterministic → L1, runs in ``make check``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

# Reuse the GoalJudge split/provenance enums (same services/governance/ package —
# shared value types, not a cross-service call: AP-2 is about service *instances*).
from services.governance.goaljudge_goldset_dataset import (
    GoldsetProvenance,
    GoldsetSplit,
)

__all__ = [
    "GoldsetSplit",
    "GoldsetProvenance",
    "LEAK_CHANNELS",
    "COACH_FAILURE_MODES",
    "CoachGoldsetItem",
    "CoachGoldsetManifest",
    "compute_test_split_hash",
    "alpha_answer_leakage",
    "build_coach_goldset_manifest",
    "leak_class_share",
]

# ── LeakChannel — mirrored LOCALLY (Invariant #7: no components import) ───────
# Kept verbatim-aligned with ``components.schemas.LeakChannel`` by a drift test
# that reads the file text (never imports across the layer). ADR-0017 FR-12 pattern.
LEAK_CHANNELS: frozenset[str] = frozenset(
    {
        "rule-naming",
        "socratic-clothing",
        "strong-implication",
        "criterion-then-verdict",
        "cross-question",
    }
)

# The coach axial taxonomy (coach_axial_v1) defines pedagogy categories A1–A4 +
# the B1/A3 leakage bridge — it has NO separate agent failure-mode code set (unlike
# GoalJudge). ``failure_mode`` is therefore a reserved-optional field: always None
# for now; the empty set means any non-null value is a hard reject (FR-3).
COACH_FAILURE_MODES: frozenset[str] = frozenset()

_PASS_AXES = (
    "mistake_identification_pass",
    "mistake_location_pass",
    "actionability_pass",
    "coherence_pass",
    "productive_struggle_pass",
    "illusion_of_competence_pass",
)


class CoachGoldsetItem(BaseModel):
    """One labeled row for ``coach_goldset_v1`` (spec FR-6).

    Only ``answer_leakage`` is a REQUIRED gold label (the sole gated class,
    FR-G6.2). The six pedagogy ``*_pass`` axes are ``bool | None`` — ``None`` means
    the fixture did not constrain that axis (AP-6: never a fabricated bool).
    """

    model_config = {"extra": "forbid"}

    item_id: str = Field(min_length=1)
    mode: str
    question: str
    learner_utterance: str
    coach_reply: str

    # The sole required gold label + its optional channel.
    answer_leakage: bool
    leak_channel: str | None = None

    # Pedagogy axes — reported telemetry (FR-G5.7); None = unconstrained.
    mistake_identification_pass: bool | None = None
    mistake_location_pass: bool | None = None
    actionability_pass: bool | None = None
    coherence_pass: bool | None = None
    productive_struggle_pass: bool | None = None
    illusion_of_competence_pass: bool | None = None

    failure_mode: str | None = None
    stratum: str = ""
    split: GoldsetSplit
    provenance: GoldsetProvenance
    taxonomy_version: str = "coach_axial_v1"

    @field_validator("mode")
    @classmethod
    def _valid_mode(cls, value: str) -> str:
        if value not in {"pre_submit", "post_feedback"}:
            raise ValueError(f"unknown mode {value!r}")
        return value

    @field_validator("leak_channel", mode="before")
    @classmethod
    def _valid_leak_channel(cls, value: object) -> str | None:
        # Gold rows are AUTHORED — an unknown channel is a hard reject (unlike the
        # judge's soft-coerce-to-None telemetry path, ADR-0017 F1).
        if value is None:
            return None
        if isinstance(value, str):
            if value in LEAK_CHANNELS:
                return value
            raise ValueError(
                f"unknown leak_channel {value!r}; expected one of {sorted(LEAK_CHANNELS)}"
            )
        raise ValueError(
            f"leak_channel must be a string or null, got {type(value).__name__}"
        )

    @field_validator("failure_mode", mode="before")
    @classmethod
    def _valid_failure_mode(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() in {"none", "null"}:
                return None
            if stripped not in COACH_FAILURE_MODES:
                raise ValueError(
                    f"unknown failure_mode {stripped!r}; expected one of "
                    f"{sorted(COACH_FAILURE_MODES)} or null"
                )
            return stripped
        raise ValueError(
            f"failure_mode must be a string or null, got {type(value).__name__}"
        )

    @model_validator(mode="after")
    def _firewall_and_consistency(self) -> CoachGoldsetItem:
        # FR-1: contamination firewall — synthetic never leaves the dev split.
        if (
            self.provenance == GoldsetProvenance.SYNTHETIC
            and self.split != GoldsetSplit.DEV
        ):
            raise ValueError(
                "contamination firewall: provenance=synthetic requires split=dev"
            )
        # FR-3 (consistency): a channel named on a non-leak row is a contradiction.
        if self.leak_channel is not None and not self.answer_leakage:
            raise ValueError(
                "leak_channel set while answer_leakage=false (gold-row contradiction)"
            )
        return self


class CoachGoldsetManifest(BaseModel):
    """The frozen assembly output (spec FR-8)."""

    model_config = {"extra": "forbid"}

    frozen_at: str
    test_split_hash: str
    row_counts: dict[str, int]
    human_alpha_answer_leakage: float | None
    rubric_version: str
    taxonomy_version: str
    provisional: bool
    leak_class_share: float | None = None


def compute_test_split_hash(items: Iterable[CoachGoldsetItem]) -> str:
    """SHA-256 over the canonical-JSON of the sorted-by-``item_id`` TEST rows.

    Sensitive to any field change on any test row (FR-5): a mismatch at cert time
    (3.8) means the test split was tuned on. Mirrors the GoalJudge hash contract.
    """
    test_rows = sorted(
        (i for i in items if i.split == GoldsetSplit.TEST),
        key=lambda i: i.item_id,
    )
    canonical = json.dumps(
        [r.model_dump(mode="json") for r in test_rows],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def alpha_answer_leakage(
    labels_a: Sequence[bool], labels_b: Sequence[bool]
) -> float | None:
    """Human–human IAA on ``answer_leakage``, via the repo's canonical Krippendorff.

    REUSES ``services.governance.iaa.krippendorff_alpha_nominal`` (never
    reimplemented). That function returns ``NaN`` when undecidable (empty, or no
    item with ≥2 raters); we map ``NaN`` → ``None`` so the manifest's
    ``float | None`` contract holds and AP-6 is satisfied (``None``, not a fabricated
    ``0.0``).
    """
    from services.governance.iaa import krippendorff_alpha_nominal

    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a and labels_b must be the same length")
    items = [[str(a).lower(), str(b).lower()] for a, b in zip(labels_a, labels_b)]
    alpha = krippendorff_alpha_nominal(items)
    return None if math.isnan(alpha) else alpha


def leak_class_share(items: Sequence[CoachGoldsetItem]) -> float | None:
    """Fraction of rows with ``answer_leakage=true`` (FR-7, report-only)."""
    if not items:
        return None
    leaks = sum(1 for i in items if i.answer_leakage)
    return leaks / len(items)


def build_coach_goldset_manifest(
    items: Sequence[CoachGoldsetItem],
    *,
    frozen_at: str,
    rubric_version: str = "coach_rubric_v1_revised",
    taxonomy_version: str = "coach_axial_v1",
    human_alpha_answer_leakage: float | None = None,
    provisional: bool | None = None,
    row_floor: int = 200,
) -> CoachGoldsetManifest:
    """Freeze a manifest (FR-4/7/8).

    ``provisional`` is forced True when the row count is below ``row_floor`` OR the
    human α is missing (fail-closed: a small/unlabeled set must refuse the cert).
    An explicit ``provisional=True`` also forces it. It clears to False ONLY when
    all floors pass AND α ≥ 0.80 (FR-9).
    """
    row_counts = {
        "total": len(items),
        "dev": sum(1 for i in items if i.split == GoldsetSplit.DEV),
        "test": sum(1 for i in items if i.split == GoldsetSplit.TEST),
        "leak": sum(1 for i in items if i.answer_leakage),
    }
    below_floor = len(items) < row_floor
    alpha_ok = (
        human_alpha_answer_leakage is not None and human_alpha_answer_leakage >= 0.80
    )
    is_provisional = bool(provisional) or below_floor or not alpha_ok
    return CoachGoldsetManifest(
        frozen_at=frozen_at,
        test_split_hash=compute_test_split_hash(items),
        row_counts=row_counts,
        human_alpha_answer_leakage=human_alpha_answer_leakage,
        rubric_version=rubric_version,
        taxonomy_version=taxonomy_version,
        provisional=is_provisional,
        leak_class_share=leak_class_share(items),
    )
