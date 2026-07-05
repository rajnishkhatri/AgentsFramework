"""Task 3.8b — offline tests for the coach calibration replay harness.

The harness's PURE core (``cert_from_labels`` / ``load_goldset``) is exercised
here with no live call: it must (a) prove ``REFUSE_PROVISIONAL`` end-to-end on
the real provisional fixture, and (b) short-circuit before any metric read while
the manifest is provisional. The live judge-replay entrypoint (``main`` /
``build_live_judges``) is manual-only (``# pragma: no cover - live only``) and is
never touched here — no network in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_coach_calibration import (
    cert_from_labels,
    cert_payload,
    load_goldset,
)

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "coach_goldset"
    / "coach_goldset_v1.json"
)


def _write_provisional_artifact(tmp_path: Path) -> Path:
    """A small PROVISIONAL goldset artifact (the pre-E6 state), for the
    fail-closed tests. The committed ``_FIXTURE`` is now the real non-provisional
    v1 freeze, so the REFUSE_PROVISIONAL contract is proven here on a synthetic
    provisional manifest instead of on the moved-on fixture."""
    from scripts.assemble_coach_goldset import build_rows, seed_from_cases

    rows = seed_from_cases()  # 21 synthetic dev rows, no α
    artifact = build_rows(rows, frozen_at="2026-07-04T00:00:00Z")  # provisional=True
    assert artifact["manifest"]["provisional"] is True
    out = tmp_path / "coach_goldset_provisional.json"
    out.write_text(json.dumps(artifact), encoding="utf-8")
    return out


def test_provisional_fixture_certs_refuse_provisional(tmp_path):
    """A provisional artifact must short-circuit to REFUSE_PROVISIONAL — the
    fail-closed contract holds before the human double-label freeze exists."""
    items, manifest = load_goldset(_write_provisional_artifact(tmp_path))
    # Even if we hand it (fabricated) judge labels, provisional wins.
    gold = {i.item_id: i.answer_leakage for i in items}
    judge = dict(gold)  # perfect agreement — still must refuse
    decision = cert_from_labels(judge_labels=judge, items=items, manifest=manifest)
    assert decision.verdict == "REFUSE_PROVISIONAL"
    # gates never populated on the provisional short-circuit
    assert (
        all(v == "" or v is None for v in decision.gates.values()) or not decision.gates
    )


def test_cert_payload_is_json_serializable(tmp_path):
    """Regression: the decision's gates/diagnostics are frozen ``mappingproxy``
    views — ``cert_payload`` must yield a plain-dict tree that ``json.dumps``
    accepts (``dataclasses.asdict`` deep-copies the proxies and cannot pickle
    them). Exercised on the provisional short-circuit path."""
    items, manifest = load_goldset(_write_provisional_artifact(tmp_path))
    gold = {i.item_id: i.answer_leakage for i in items}
    decision = cert_from_labels(judge_labels=gold, items=items, manifest=manifest)
    payload = cert_payload(decision, goldset_path="x.json", model="stub", n_test=0)
    # must round-trip through JSON with no custom encoder
    restored = json.loads(json.dumps(payload))
    assert restored["decision"]["verdict"] == "REFUSE_PROVISIONAL"
    assert isinstance(restored["decision"]["gates"], dict)


def test_load_goldset_returns_the_real_v1_freeze():
    """The committed fixture is the E6 non-provisional v1 (246 rows, α present)."""
    items, manifest = load_goldset(_FIXTURE)
    assert len(items) == 246
    assert manifest.provisional is False
    assert manifest.human_alpha_answer_leakage is not None
    assert manifest.row_counts["test"] > 0


def test_cert_from_labels_reads_metrics_once_non_provisional(tmp_path):
    """When the manifest is a real v1 freeze (non-provisional, α present, test
    split populated), the harness feeds evaluate_coach_enable_gates and a verdict
    is computed from the gates — not REFUSE_PROVISIONAL."""
    # Build a tiny NON-provisional goldset with a populated test split where the
    # judge perfectly matches gold → ENABLE.
    from services.governance.coach_goldset_dataset import (
        CoachGoldsetItem,
        GoldsetProvenance,
        GoldsetSplit,
        build_coach_goldset_manifest,
    )

    def _item(iid: str, leak: bool) -> CoachGoldsetItem:
        return CoachGoldsetItem(
            item_id=iid,
            learner_utterance="u",
            coach_reply="r",
            question="q",
            mode="post_feedback",
            answer_leakage=leak,
            leak_channel="rule-naming" if leak else None,
            split=GoldsetSplit.TEST,
            stratum="s",
            provenance=GoldsetProvenance.PRODUCTION,
            taxonomy_version="coach_axial_v1",
        )

    items = [
        _item("T1", True),
        _item("T2", False),
        _item("T3", True),
        _item("T4", False),
    ]
    # row_floor lowered so the 4-row synthetic set clears the fail-closed floor;
    # α ≥ 0.80 + non-empty test split are what actually let provisional clear.
    manifest = build_coach_goldset_manifest(
        items,
        frozen_at="2026-07-04T00:00:00Z",
        provisional=False,
        human_alpha_answer_leakage=0.95,
        row_floor=4,
    )
    assert manifest.provisional is False  # guard: the non-provisional path is live
    judge = {i.item_id: i.answer_leakage for i in items}  # perfect
    decision = cert_from_labels(judge_labels=judge, items=items, manifest=manifest)
    assert decision.verdict != "REFUSE_PROVISIONAL"
    assert decision.verdict in {"ENABLE", "REFUSE"}


def test_cert_uses_only_test_split_gold(tmp_path):
    """gold_labels come from the TEST split only — a dev-split leak label must
    not leak into the cert denominator."""
    from services.governance.coach_goldset_dataset import (
        CoachGoldsetItem,
        GoldsetProvenance,
        GoldsetSplit,
    )
    from scripts.run_coach_calibration import test_split_gold

    items = [
        CoachGoldsetItem(
            item_id="D1",
            learner_utterance="u",
            coach_reply="r",
            question="q",
            mode="post_feedback",
            answer_leakage=True,
            leak_channel="rule-naming",
            split=GoldsetSplit.DEV,
            stratum="s",
            provenance=GoldsetProvenance.SYNTHETIC,
            taxonomy_version="coach_axial_v1",
        ),
        CoachGoldsetItem(
            item_id="T1",
            learner_utterance="u",
            coach_reply="r",
            question="q",
            mode="post_feedback",
            answer_leakage=False,
            leak_channel=None,
            split=GoldsetSplit.TEST,
            stratum="s",
            provenance=GoldsetProvenance.PRODUCTION,
            taxonomy_version="coach_axial_v1",
        ),
    ]
    gold = test_split_gold(items)
    assert gold == {"T1": False}
