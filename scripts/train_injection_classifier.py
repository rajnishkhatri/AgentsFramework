#!/usr/bin/env python
"""Offline fine-tune + ONNX export for the injection classifier (Sprint 3 / S3-1).

``f2-train``. Fine-tunes a prompt-injection classifier from
``protectai/deberta-v3-base-prompt-injection-v2`` using PIGuard **MOF**
(*Mitigating Over-defense for Free*) and exports a **quantized ONNX** artifact
that the Layer 2 service ``services/governance/injection_classifier.py`` loads
at runtime.

This script is **OFFLINE ONLY** and never runs in CI:

* The heavy ML stack (``torch`` / ``transformers`` / ``onnx`` /
  ``onnxruntime``) is imported **lazily inside functions**, so importing this
  module is cheap and CI-safe — the deterministic, CI-relevant helpers
  (:func:`select_train_split`, :func:`build_smoke_artifact`) can be tested
  without the heavy stack on the import path.
* Training is gated behind the ``train`` subcommand and requires the full ML
  stack + a GPU/CPU budget; CI never invokes it.

Artifact distribution (``GUARDRAILS_DIMENSION_SPACE.md`` §C / D3.3): the
~184MB DeBERTa weights are **never committed**. Ship a quantized ONNX artifact
via git-LFS or fetch-at-build, plus a tiny **smoke model** (this script's
``smoke`` subcommand) so CI can exercise the real ONNX inference path
deterministically without the production weights.

PIGuard MOF (summary): the over-defense failure mode is a *trigger-word
shortcut* — the model learns "scary word ⇒ injection". MOF adds an auxiliary
objective on the over-defense / hard-negative examples (the Sprint 2
``local_augment`` benign-but-trigger-word rows) that penalizes confident
rejection of benign trigger-word prompts, *for free* — i.e. with no extra
labeled attack data, only the augmented negatives. NotInject stays **held-out**
(never trained on); it is the over-defense *test* set scored by the Sprint 4
gate.

Subcommands:
    train  — fine-tune + export the quantized ONNX artifact (offline, heavy)
    smoke  — build the tiny CI smoke artifact (onnx + tokenizers, no training)

Run:
    python scripts/train_injection_classifier.py smoke --out models/smoke_clf
    python scripts/train_injection_classifier.py train \\
        --dataset data/guardrail_dataset.jsonl --out models/injection_clf
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python scripts/train_injection_classifier.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.governance.guardrail_dataset import (  # noqa: E402
    NOTINJECT_SOURCE,
    DatasetSplit,
    GuardrailSample,
    Label,
    assert_no_contamination,
    load_jsonl,
)
from services.governance.injection_classifier import (  # noqa: E402
    ARTIFACT_CONFIG,
    ARTIFACT_MODEL,
    ARTIFACT_TOKENIZER,
)

logger = logging.getLogger("scripts.train_injection_classifier")

# Base model fine-tuned from (DeBERTa-v3, protectai v2). Documented, not
# hardcoded into the runtime service.
BASE_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
# Label order in the exported artifact: index 1 is the INJECTION class.
INJECTION_INDEX = 1
SMOKE_MAX_LENGTH = 64


# ─────────────────────────────────────────────────────────────────────
# CI-safe helpers (no heavy imports) — exercised by L2 tests.
# ─────────────────────────────────────────────────────────────────────


def select_train_split(samples: list[GuardrailSample]) -> list[GuardrailSample]:
    """Return the trainable rows: the ``train`` split with NotInject excluded.

    Enforces the frozen contamination guard (``GUARDRAILS_DIMENSION_SPACE.md``
    §E.1 / D3.2) two ways before returning:

    1. :func:`assert_no_contamination` fails loudly if any ``notinject`` row is
       already mislabeled into the train split.
    2. ``notinject``-sourced rows are then defensively dropped regardless of
       split, so the trainer can NEVER see the held-out over-defense set.
    """
    assert_no_contamination(samples)
    return [
        s
        for s in samples
        if s.split is DatasetSplit.TRAIN and s.source != NOTINJECT_SOURCE
    ]


def _smoke_vocab() -> dict[str, int]:
    """Tiny vocab for the CI smoke tokenizer (attack markers + specials)."""
    specials = ["[UNK]", "[PAD]"]
    # Strong, unambiguous attack markers only — the smoke model exercises the
    # ONNX *plumbing* deterministically; it is NOT the trained over-defense
    # model (that is the real artifact scored by the Sprint 4 gate).
    markers = [
        "ignore",
        "disregard",
        "forget",
        "reveal",
        "bypass",
        "dan",
        "jailbreak",
        "unrestricted",
    ]
    vocab = {tok: i for i, tok in enumerate(specials)}
    for tok in markers:
        vocab[tok] = len(vocab)
    return vocab


def build_smoke_artifact(out_dir: str | Path) -> Path:
    """Build the tiny CI smoke artifact (ONNX model + tokenizer + config).

    Deterministic and self-contained: a WordLevel tokenizer over a tiny vocab
    and a hand-weighted bag-of-tokens ONNX graph
    (``logits = Σ_t mask_t · E[id_t]``). Attack-marker tokens carry positive
    class-1 (INJECTION) weight; every other token contributes a small class-0
    (BENIGN) bias, so a clear override attack lands in the INJECTION band and
    plain natural language lands in the BENIGN band — enough to prove the
    service's real ONNX inference path without the ~184MB production weights.

    Requires the optional ``guardrails`` extra (``onnxruntime`` + ``tokenizers``)
    plus ``onnx`` + ``numpy``; imported lazily so this module stays CI-safe.
    """
    import json

    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    from tokenizers import Tokenizer, models, normalizers, pre_tokenizers

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    vocab = _smoke_vocab()
    inv_markers = {tok for tok in vocab if tok not in ("[UNK]", "[PAD]")}

    # ── Tokenizer: lowercase + whitespace WordLevel over the tiny vocab. ──
    tokenizer = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    tokenizer.normalizer = normalizers.Lowercase()
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(out / ARTIFACT_TOKENIZER))

    # ── Embedding matrix E[vocab, 2]: [class0_benign, class1_injection]. ──
    vocab_size = len(vocab)
    emb = np.zeros((vocab_size, 2), dtype=np.float32)
    for tok, idx in vocab.items():
        if tok in inv_markers:
            emb[idx, 1] = 3.0  # strong INJECTION signal
        elif tok == "[PAD]":
            emb[idx] = (0.0, 0.0)  # padding contributes nothing
        else:  # [UNK] / ordinary words → small BENIGN bias
            emb[idx, 0] = 0.5

    # ── ONNX graph: logits = ReduceSum_t( Gather(E, ids) * mask ). ──
    emb_init = numpy_helper.from_array(emb, name="embedding")
    nodes = [
        helper.make_node("Gather", ["embedding", "input_ids"], ["gathered"], axis=0),
        helper.make_node("Cast", ["attention_mask"], ["mask_f"], to=TensorProto.FLOAT),
        helper.make_node("Unsqueeze", ["mask_f", "axis2"], ["mask_e"]),
        helper.make_node("Mul", ["gathered", "mask_e"], ["masked"]),
        helper.make_node("ReduceSum", ["masked", "axis1"], ["logits"], keepdims=0),
    ]
    axis1 = numpy_helper.from_array(np.array([1], dtype=np.int64), name="axis1")
    axis2 = numpy_helper.from_array(np.array([2], dtype=np.int64), name="axis2")
    graph = helper.make_graph(
        nodes,
        "injection_smoke_classifier",
        inputs=[
            helper.make_tensor_value_info(
                "input_ids", TensorProto.INT64, ["batch", "seq"]
            ),
            helper.make_tensor_value_info(
                "attention_mask", TensorProto.INT64, ["batch", "seq"]
            ),
        ],
        outputs=[
            helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", 2])
        ],
        initializer=[emb_init, axis1, axis2],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_operatorsetid("", 13)])
    model.ir_version = 9
    onnx.checker.check_model(model)
    onnx.save(model, str(out / ARTIFACT_MODEL))

    (out / ARTIFACT_CONFIG).write_text(
        json.dumps(
            {
                "base_model": BASE_MODEL,
                "injection_index": INJECTION_INDEX,
                "max_length": SMOKE_MAX_LENGTH,
                "artifact": "smoke",
                "id2label": {"0": "BENIGN", "1": "INJECTION"},
            },
            indent=2,
        )
    )
    logger.info("Built smoke injection-classifier artifact at %s", out)
    return out


# ─────────────────────────────────────────────────────────────────────
# Offline training (heavy; never CI). Imports lazily.
# ─────────────────────────────────────────────────────────────────────


def train_and_export(
    dataset_path: str | Path,
    out_dir: str | Path,
    *,
    epochs: int = 3,
    mof_weight: float = 0.5,
    quantize: bool = True,
) -> Path:
    """Fine-tune from ``BASE_MODEL`` with PIGuard MOF and export quantized ONNX.

    OFFLINE ONLY. Trains exclusively on :func:`select_train_split` of the
    frozen dataset (NotInject excluded). The MOF auxiliary loss penalizes
    confident rejection of the benign-but-trigger-word hard negatives
    (``local_augment`` rows), curing trigger-word shortcut bias.

    Lazily imports ``torch`` / ``transformers`` / ``onnxruntime`` so this
    module imports without the heavy stack.
    """
    import torch
    from torch.nn import functional as F
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    samples = load_jsonl(dataset_path)
    train_rows = select_train_split(samples)
    if not train_rows:
        raise SystemExit("no trainable rows after contamination filtering")
    logger.info("training on %d rows (NotInject excluded)", len(train_rows))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)

    texts = [r.text for r in train_rows]
    labels = torch.tensor([1 if r.label is Label.INJECTION else 0 for r in train_rows])
    # MOF mask: benign hard-negatives (trigger words present, benign label).
    mof_mask = torch.tensor(
        [
            1.0 if (r.label is Label.BENIGN and r.trigger_words) else 0.0
            for r in train_rows
        ]
    )

    model.train()
    for epoch in range(epochs):
        enc = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
        optimizer.zero_grad()
        logits = model(**enc).logits
        ce = F.cross_entropy(logits, labels)
        # MOF: extra penalty on injection-class confidence for benign hard
        # negatives — discourages the trigger-word shortcut "for free".
        probs = F.softmax(logits, dim=-1)[:, INJECTION_INDEX]
        mof = (mof_mask * probs.pow(2)).sum() / max(mof_mask.sum(), 1.0)
        loss = ce + mof_weight * mof
        loss.backward()
        optimizer.step()
        logger.info(
            "epoch %d: ce=%.4f mof=%.4f loss=%.4f",
            epoch,
            float(ce),
            float(mof),
            float(loss),
        )

    _export_onnx(model, tokenizer, out, quantize=quantize)
    return out


def _export_onnx(model, tokenizer, out: Path, *, quantize: bool) -> None:
    """Export a HuggingFace model to (optionally quantized) ONNX + tokenizer."""
    import json

    import torch

    model.eval()
    dummy = tokenizer(
        "export sample",
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=SMOKE_MAX_LENGTH,
    )
    input_names = list(dummy.keys())
    raw_path = out / "model.raw.onnx"
    torch.onnx.export(
        model,
        tuple(dummy[k] for k in input_names),
        str(raw_path),
        input_names=input_names,
        output_names=["logits"],
        dynamic_axes={k: {0: "batch", 1: "seq"} for k in input_names}
        | {"logits": {0: "batch"}},
        opset_version=14,
    )

    final_path = out / ARTIFACT_MODEL
    if quantize:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(str(raw_path), str(final_path), weight_type=QuantType.QInt8)
        raw_path.unlink(missing_ok=True)
    else:
        raw_path.rename(final_path)

    tokenizer.save_pretrained(str(out))
    # tokenizers' fast tokenizer also writes tokenizer.json; ensure present.
    fast = out / "tokenizer.json"
    if fast.exists() and fast != out / ARTIFACT_TOKENIZER:
        fast.rename(out / ARTIFACT_TOKENIZER)
    (out / ARTIFACT_CONFIG).write_text(
        json.dumps(
            {
                "base_model": BASE_MODEL,
                "injection_index": INJECTION_INDEX,
                "max_length": SMOKE_MAX_LENGTH,
                "artifact": "quantized" if quantize else "fp32",
            },
            indent=2,
        )
    )
    logger.info("Exported ONNX artifact to %s (quantize=%s)", out, quantize)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="fine-tune + export quantized ONNX")
    p_train.add_argument("--dataset", type=Path, required=True)
    p_train.add_argument("--out", type=Path, required=True)
    p_train.add_argument("--epochs", type=int, default=3)
    p_train.add_argument("--mof-weight", type=float, default=0.5)
    p_train.add_argument("--no-quantize", action="store_true")

    p_smoke = sub.add_parser("smoke", help="build the tiny CI smoke artifact")
    p_smoke.add_argument("--out", type=Path, required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    if args.command == "smoke":
        out = build_smoke_artifact(args.out)
        print(f"smoke artifact → {out}")
        return 0
    if args.command == "train":
        out = train_and_export(
            args.dataset,
            args.out,
            epochs=args.epochs,
            mof_weight=args.mof_weight,
            quantize=not args.no_quantize,
        )
        print(f"artifact → {out}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
