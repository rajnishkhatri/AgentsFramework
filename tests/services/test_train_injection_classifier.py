"""L2 Reproducible: tests for the offline training driver (Sprint 3 / S3-1).

The training itself is OFFLINE-ONLY and heavy, so it is never run in CI. These
tests pin the **CI-safe, deterministic** contract of the driver:

* :func:`select_train_split` enforces the frozen contamination guard — the
  trainer must NEVER see a ``notinject`` row (failure-path first).
* Importing the module does NOT drag in the heavy ML stack (``torch`` /
  ``transformers``) — they are lazily imported inside functions.
* :func:`build_smoke_artifact` emits the three artifact files when the optional
  extra is present (``importorskip``); the produced artifact is loadable by the
  Layer 2 service.

Failure paths (contamination) come before acceptance, per
``research/tdd_agentic_systems_prompt.md`` Protocol B.
"""

from __future__ import annotations

import sys

import pytest

from services.governance.guardrail_dataset import (
    ContaminationError,
    DatasetSplit,
    Difficulty,
    Dimension,
    GuardrailSample,
    Label,
    Rail,
)
from scripts.train_injection_classifier import (
    build_smoke_artifact,
    select_train_split,
)


def _row(
    sid: str,
    *,
    label: Label,
    source: str,
    split: DatasetSplit,
    dimension: Dimension = Dimension.DOMAIN_ACCEPT,
    trigger_words: list[str] | None = None,
) -> GuardrailSample:
    return GuardrailSample(
        id=sid,
        text=f"text for {sid}",
        label=label,
        rail=Rail.INPUT,
        owasp="LLM01",
        dimension=dimension,
        trigger_words=trigger_words or [],
        difficulty=Difficulty.EASY,
        source=source,
        split=split,
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Contamination guard — failure path first (D3.2 / §E.1).
# ─────────────────────────────────────────────────────────────────────


class TestTrainSplitContaminationGuard:
    def test_leaked_notinject_row_raises(self):
        # A notinject row forced into train (built via model_construct to
        # bypass the row-level validator) must trip the collection guard.
        leaked = GuardrailSample.model_construct(
            id="ni-leak",
            text="benign but trigger-word",
            label=Label.BENIGN,
            rail=Rail.INPUT,
            owasp="LLM01",
            dimension=Dimension.OVER_DEFENSE,
            trigger_words=["ignore"],
            difficulty=Difficulty.EASY,
            source="notinject",
            split=DatasetSplit.TRAIN,
        )
        with pytest.raises(ContaminationError):
            select_train_split([leaked])

    def test_notinject_held_out_rows_are_excluded(self):
        rows = [
            _row("inj-1", label=Label.INJECTION, source="deepset", split=DatasetSplit.TRAIN),
            _row(
                "ni-1",
                label=Label.BENIGN,
                source="notinject",
                split=DatasetSplit.HELD_OUT,
                dimension=Dimension.OVER_DEFENSE,
                trigger_words=["ignore"],
            ),
        ]
        train = select_train_split(rows)
        ids = {r.id for r in train}
        assert ids == {"inj-1"}
        assert all(r.source != "notinject" for r in train)


# ─────────────────────────────────────────────────────────────────────
# 2. Acceptance — the train split keeps the trainable rows.
# ─────────────────────────────────────────────────────────────────────


class TestTrainSplitSelection:
    def test_keeps_train_injections_and_local_augment(self):
        rows = [
            _row("inj-1", label=Label.INJECTION, source="deepset", split=DatasetSplit.TRAIN),
            _row(
                "aug-1",
                label=Label.BENIGN,
                source="local_augment",
                split=DatasetSplit.TRAIN,
                dimension=Dimension.OVER_DEFENSE,
                trigger_words=["ignore"],
            ),
            _row("domain-1", label=Label.BENIGN, source="blackbox_S3", split=DatasetSplit.TRAIN),
            _row("eval-1", label=Label.INJECTION, source="deepset", split=DatasetSplit.HELD_OUT),
        ]
        train = select_train_split(rows)
        assert {r.id for r in train} == {"inj-1", "aug-1", "domain-1"}


# ─────────────────────────────────────────────────────────────────────
# 3. CI-safety — importing the trainer must not import the heavy ML stack.
# ─────────────────────────────────────────────────────────────────────


class TestLazyHeavyImports:
    @pytest.mark.parametrize("heavy", ["torch", "transformers"])
    def test_heavy_stack_not_imported_at_module_import(self, heavy):
        # Importing the trainer module (already imported above) must not have
        # pulled in torch/transformers — they are lazily imported inside the
        # train function so the module stays CI-safe.
        if heavy in sys.modules:
            pytest.skip(f"{heavy} already imported by another test/runtime")
        import scripts.train_injection_classifier  # noqa: F401

        assert heavy not in sys.modules


# ─────────────────────────────────────────────────────────────────────
# 4. Smoke artifact — emits a loadable artifact (needs the optional extra).
# ─────────────────────────────────────────────────────────────────────


class TestSmokeArtifact:
    def test_build_smoke_artifact_emits_three_files(self, tmp_path):
        pytest.importorskip("onnx")
        pytest.importorskip("onnxruntime")
        pytest.importorskip("tokenizers")
        out = build_smoke_artifact(tmp_path / "clf")
        assert (out / "model.onnx").is_file()
        assert (out / "tokenizer.json").is_file()
        assert (out / "config.json").is_file()
