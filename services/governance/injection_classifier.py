"""ONNX prompt-injection classifier (Layer 2, Sprint 3 / S3-2).

The model stage of the Input-rail cascade documented in
``docs/Architectures/GUARDRAILS_DIMENSION_SPACE.md`` §B/§C. It slots into the
*ambiguous* (``DEFER``) branch of the deterministic pre-check
(``services/guardrails.py``): a fine-tuned DeBERTa-v3 injection classifier,
exported to a quantized ONNX artifact, run with deterministic argmax.

Why a classifier and not just the LLM judge?

* **Deterministic.** ONNX Runtime inference with frozen weights is a pure
  function of the input bytes — zero flake — so it runs as a **real L2 test in
  CI**, never a live API call. This is the key win over the non-deterministic
  judge (``research/tdd_agentic_systems_prompt.md`` Anti-Pattern 3/5).
* **Trigger-word-shortcut-resistant.** Trained with PIGuard MOF on the
  non-NotInject split (Sprint 2), it learns *intent*, not vocabulary, so the
  S3/S5/S6 over-defense frames are accepted (Sprint 4 gate).

Three-way band (mirrors the pre-check contract):

    INJECTION  — confident attack            → reject
    BENIGN     — confident clean              → accept
    UNCERTAIN  — between the thresholds       → defer to the narrow LLM judge

Graceful degrade (frozen contract, §D): the optional ``guardrails`` extra
(``onnxruntime`` + ``tokenizers``) and the ONNX artifact are BOTH optional.
:meth:`InjectionClassifier.maybe_load` returns ``None`` — never raises — when
either is absent, and the input rail falls back to *pre-check + narrow LLM
judge*.

Layer compliance (AGENTS.md invariant #4 / §C): this module imports only
stdlib + Pydantic, with ``onnxruntime`` / ``tokenizers`` / ``numpy`` imported
lazily behind a guard. NO ``langgraph`` / ``langchain``. It takes the input
string as a parameter and returns a verdict — no upward (``components/``)
imports (invariant #7).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

logger = logging.getLogger("services.governance.injection_classifier")


# ─────────────────────────────────────────────────────────────────────
# Tunables (config convention: numeric knobs live in code, not the prompt).
# The meta-optimizer may tune these without touching policy prose.
# ─────────────────────────────────────────────────────────────────────

# injection_probability >= this → confident INJECTION (reject).
INJECTION_REJECT_THRESHOLD = 0.80
# injection_probability <= this → confident BENIGN (accept).
BENIGN_ACCEPT_THRESHOLD = 0.20
# Anything strictly between the two thresholds is UNCERTAIN → defer to judge.

# Artifact file names inside the artifact directory.
ARTIFACT_MODEL = "model.onnx"
ARTIFACT_TOKENIZER = "tokenizer.json"
ARTIFACT_CONFIG = "config.json"

# Where the quantized ONNX artifact lives by default. The ~184MB weights are
# NEVER committed (§C); the directory is absent in a default checkout, so
# maybe_load() degrades. Override with the env var or the maybe_load() arg.
_ARTIFACT_DIR_ENV = "INJECTION_CLASSIFIER_DIR"
_DEFAULT_ARTIFACT_DIR = (
    Path(__file__).resolve().parent / "artifacts" / "injection_classifier"
)

# Default config when an artifact ships none: protectai/deberta-v3 labels
# {0: SAFE, 1: INJECTION}, max sequence length 512.
_DEFAULT_INJECTION_INDEX = 1
_DEFAULT_MAX_LENGTH = 512
# ONNX input names this runner knows how to feed (subset selected per model).
_KNOWN_INPUT_NAMES = ("input_ids", "attention_mask", "token_type_ids")


class ClassifierBand(str, Enum):
    """Three-way verdict band (parallels :class:`PreCheckVerdict`)."""

    INJECTION = "injection"  # confident → reject
    BENIGN = "benign"  # confident → accept
    UNCERTAIN = "uncertain"  # → defer to the narrow LLM judge


@dataclass(frozen=True)
class ClassifierVerdict:
    """Outcome of :meth:`InjectionClassifier.classify`."""

    band: ClassifierBand
    injection_probability: float


def default_artifact_dir() -> Path:
    """Resolve the artifact directory (env override → packaged default)."""
    override = os.environ.get(_ARTIFACT_DIR_ENV)
    return Path(override) if override else _DEFAULT_ARTIFACT_DIR


def guardrails_extra_available() -> bool:
    """Return whether the optional ``guardrails`` extra is importable.

    Uses :func:`importlib.util.find_spec` so it does not import (and pay the
    cost of) the heavy runtimes just to answer the question.
    """
    return all(
        importlib.util.find_spec(mod) is not None
        for mod in ("onnxruntime", "tokenizers", "numpy")
    )


def artifact_available(artifact_dir: str | Path | None = None) -> bool:
    """Return whether a complete ONNX artifact exists in ``artifact_dir``."""
    base = Path(artifact_dir) if artifact_dir is not None else default_artifact_dir()
    return all((base / name).is_file() for name in (ARTIFACT_MODEL, ARTIFACT_TOKENIZER))


def decide_band(
    injection_probability: float,
    *,
    reject_threshold: float = INJECTION_REJECT_THRESHOLD,
    accept_threshold: float = BENIGN_ACCEPT_THRESHOLD,
) -> ClassifierBand:
    """Pure band decision from an injection probability.

    Deterministic and side-effect-free (no ONNX, no I/O) so it is unit-tested
    on every commit regardless of whether the optional extra is installed.
    """
    if injection_probability >= reject_threshold:
        return ClassifierBand.INJECTION
    if injection_probability <= accept_threshold:
        return ClassifierBand.BENIGN
    return ClassifierBand.UNCERTAIN


class InjectionClassifier:
    """Deterministic ONNX injection classifier behind the input-rail cascade.

    Construct via :meth:`maybe_load` (graceful degrade) in production; the
    direct constructor takes an already-loaded ONNX session + tokenizer and is
    handy for tests that build a tiny smoke artifact.
    """

    def __init__(
        self,
        session: Any,
        tokenizer: Any,
        *,
        injection_index: int = _DEFAULT_INJECTION_INDEX,
        max_length: int = _DEFAULT_MAX_LENGTH,
        reject_threshold: float = INJECTION_REJECT_THRESHOLD,
        accept_threshold: float = BENIGN_ACCEPT_THRESHOLD,
    ) -> None:
        self._session = session
        self._tokenizer = tokenizer
        self._injection_index = injection_index
        self._max_length = max_length
        self._reject_threshold = reject_threshold
        self._accept_threshold = accept_threshold
        # The ONNX graph input names we must feed (intersection of what the
        # model declares and what this runner knows how to build).
        declared = {i.name for i in session.get_inputs()}
        self._input_names = [n for n in _KNOWN_INPUT_NAMES if n in declared]

    @classmethod
    def maybe_load(
        cls,
        artifact_dir: str | Path | None = None,
        *,
        reject_threshold: float = INJECTION_REJECT_THRESHOLD,
        accept_threshold: float = BENIGN_ACCEPT_THRESHOLD,
    ) -> InjectionClassifier | None:
        """Load the classifier, or return ``None`` to degrade (never raises).

        Returns ``None`` when the optional extra is unavailable, the artifact
        is missing, or loading fails for any reason. Callers treat ``None`` as
        "skip the classifier stage" — the frozen graceful-degrade contract
        (``GUARDRAILS_DIMENSION_SPACE.md`` §D).
        """
        base = (
            Path(artifact_dir) if artifact_dir is not None else default_artifact_dir()
        )
        if not guardrails_extra_available():
            logger.info(
                "injection_classifier: optional 'guardrails' extra absent; "
                "degrading to pre-check + narrow LLM judge"
            )
            return None
        if not artifact_available(base):
            logger.info(
                "injection_classifier: artifact missing under %s; degrading "
                "to pre-check + narrow LLM judge",
                base,
            )
            return None
        try:
            import onnxruntime  # noqa: PLC0415 - lazy, behind the extra guard
            from tokenizers import Tokenizer  # noqa: PLC0415

            session = onnxruntime.InferenceSession(
                str(base / ARTIFACT_MODEL),
                providers=["CPUExecutionProvider"],
            )
            tokenizer = Tokenizer.from_file(str(base / ARTIFACT_TOKENIZER))
            cfg = cls._load_config(base)
            tokenizer.enable_truncation(max_length=cfg["max_length"])
            return cls(
                session,
                tokenizer,
                injection_index=cfg["injection_index"],
                max_length=cfg["max_length"],
                reject_threshold=reject_threshold,
                accept_threshold=accept_threshold,
            )
        except Exception:  # noqa: BLE001 - degrade, never break the input rail
            logger.warning(
                "injection_classifier: failed to load artifact under %s; "
                "degrading to pre-check + narrow LLM judge",
                base,
                exc_info=True,
            )
            return None

    @staticmethod
    def _load_config(base: Path) -> dict[str, int]:
        path = base / ARTIFACT_CONFIG
        if not path.is_file():
            return {
                "injection_index": _DEFAULT_INJECTION_INDEX,
                "max_length": _DEFAULT_MAX_LENGTH,
            }
        raw: Mapping[str, Any] = json.loads(path.read_text())
        return {
            "injection_index": int(
                raw.get("injection_index", _DEFAULT_INJECTION_INDEX)
            ),
            "max_length": int(raw.get("max_length", _DEFAULT_MAX_LENGTH)),
        }

    def injection_probability(self, text: str) -> float:
        """Return P(injection) ∈ [0, 1] via deterministic ONNX argmax/softmax."""
        import numpy as np  # noqa: PLC0415 - lazy, behind the extra guard

        encoding = self._tokenizer.encode(text)
        ids = encoding.ids[: self._max_length]
        mask = encoding.attention_mask[: self._max_length]
        feeds: dict[str, Any] = {}
        for name in self._input_names:
            if name == "input_ids":
                value = ids
            elif name == "attention_mask":
                value = mask
            else:  # token_type_ids — single-sequence input is all zeros
                value = [0] * len(ids)
            feeds[name] = np.asarray([value], dtype=np.int64)

        logits = np.asarray(self._session.run(None, feeds)[0])[0]
        # Numerically stable softmax.
        shifted = logits - np.max(logits)
        exp = np.exp(shifted)
        probs = exp / np.sum(exp)
        return float(probs[self._injection_index])

    def classify(self, text: str) -> ClassifierVerdict:
        """Score ``text`` and return a banded :class:`ClassifierVerdict`."""
        prob = self.injection_probability(text)
        band = decide_band(
            prob,
            reject_threshold=self._reject_threshold,
            accept_threshold=self._accept_threshold,
        )
        logger.debug(
            "injection_classifier verdict",
            extra={
                "band": band.value,
                "injection_probability": round(prob, 4),
                "input_preview": text[:80],
            },
        )
        return ClassifierVerdict(band=band, injection_probability=prob)
