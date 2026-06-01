"""L4 wiring: the ONNX injection classifier is loaded in the live graph (S3-2/S4-2).

Backs the sprint-board claim that ``build_graph`` wires the classifier into the
input-rail cascade via ``classifier=InjectionClassifier.maybe_load()``. Two
binary outcomes (Protocol D / failure-first):

* **Default checkout degrades.** In a vanilla environment (no optional
  ``guardrails`` extra and/or no artifact) the guardrail ``build_graph``
  constructs has ``classifier is None`` — graceful degrade, no raise. This is
  the deterministic, CI-safe assertion that runs on every commit.
* **Wire is real end-to-end.** When the extra is present, a smoke artifact is
  built, ``INJECTION_CLASSIFIER_DIR`` points at it, and the constructed
  guardrail's ``classifier is not None`` — proving the load path is reached
  from the live graph. ``importorskip``s the extra (self-skips in CI).

The guardrail is a local in ``build_graph``; the constructed instance is
captured by wrapping the real ``InputGuardrail`` so the test inspects the
actual object the production path builds (no deep mock — Anti-Pattern 2).
"""

from __future__ import annotations

from unittest.mock import patch

from orchestration import react_loop
from orchestration.react_loop import build_graph
from services.base_config import AgentConfig
from services.governance.injection_classifier import _ARTIFACT_DIR_ENV
from services.guardrails import InputGuardrail


def _config() -> AgentConfig:
    return AgentConfig(
        default_model="test-model",
        max_steps=5,
        max_cost_usd=1.0,
        models=[],
    )


def _build_and_capture_guardrail() -> InputGuardrail:
    """Build the graph and return the ``InputGuardrail`` it constructed."""
    captured: list[InputGuardrail] = []
    real_cls = react_loop.InputGuardrail

    def _wrapper(*args, **kwargs):
        instance = real_cls(*args, **kwargs)
        captured.append(instance)
        return instance

    with patch.object(react_loop, "InputGuardrail", side_effect=_wrapper):
        build_graph(_config())

    assert len(captured) == 1, "expected exactly one input guardrail to be built"
    return captured[0]


def test_default_checkout_degrades_to_no_classifier(monkeypatch):
    """Vanilla environment: the wired ``maybe_load()`` degrades to ``None``."""
    # Point the artifact dir at a guaranteed-empty location so the classifier
    # degrades regardless of whether the optional extra happens to be installed.
    monkeypatch.setenv(_ARTIFACT_DIR_ENV, "/nonexistent/injection_classifier_dir")
    guard = _build_and_capture_guardrail()
    assert guard._classifier is None


def test_classifier_wired_when_extra_and_artifact_present(tmp_path, monkeypatch):
    """End-to-end wire: extra + artifact ⇒ ``build_graph`` loads the classifier."""
    import pytest

    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    pytest.importorskip("onnx")
    pytest.importorskip("numpy")
    from scripts.train_injection_classifier import build_smoke_artifact

    artifact_dir = build_smoke_artifact(tmp_path / "smoke_clf")
    monkeypatch.setenv(_ARTIFACT_DIR_ENV, str(artifact_dir))

    guard = _build_and_capture_guardrail()
    assert guard._classifier is not None
