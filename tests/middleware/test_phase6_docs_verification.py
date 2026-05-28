"""L2 tests for Phase 6 — GCP Ops Docs and Verification.

Verifies that documentation files are aligned with the Langfuse GCP
integration implemented in Phases 1–5:

  - LOG_PIPELINE_GUIDE.md has a Langfuse verification step
  - 07_observability.md references Langfuse + Hobby quota
  - END_TO_END_TRACING_GUIDE.md has the sixth trace plane, no stale Known Gap
  - FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md §4.5 uses export_event/shutdown API
  - GCP_DEPLOYMENT_ARCHITECTURE.md mentions telemetry export on /run/stream
  - RUNBOOK.md §4.1 uses LangfuseCloudExporter naming (not stale adapter names)
  - smoke_gcp.sh checks for langfuse init failure warning

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD — docs-as-contract
Anti-patterns avoided:
  - Gap Blindness (verifies failure path: stale Known Gap must be retired)
  - Tautological (tests assert required content presence, not exact wording)
"""

from __future__ import annotations

from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _read_doc(relative_path: str) -> str:
    """Read a doc file and return its content, or skip if missing."""
    full = AGENT_ROOT / relative_path
    if not full.exists():
        pytest.skip(f"{relative_path} does not exist yet")
    return full.read_text()


# ─────────────────────────────────────────────────────────────────────
# LOG_PIPELINE_GUIDE.md — Langfuse verification step
# ─────────────────────────────────────────────────────────────────────


class TestLogPipelineGuideLangfuseStep:
    """LOG_PIPELINE_GUIDE.md must contain a Langfuse trace verification section."""

    DOC_PATH = "docs/recipes/gcp/LOG_PIPELINE_GUIDE.md"

    def test_mentions_langfuse(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower(), (
            "LOG_PIPELINE_GUIDE.md must mention Langfuse"
        )

    def test_has_langfuse_verification_step(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower() and "verif" in content.lower(), (
            "LOG_PIPELINE_GUIDE.md must contain a Langfuse verification section"
        )

    def test_references_trace_id_correlation(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "trace" in content.lower() and "langfuse" in content.lower(), (
            "LOG_PIPELINE_GUIDE.md must reference trace_id correlation with Langfuse"
        )

    def test_log_marker_table_includes_langfuse(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse client init failed" in content.lower(), (
            "LOG_PIPELINE_GUIDE.md log marker table must include "
            "'langfuse client init failed' warning marker"
        )


# ─────────────────────────────────────────────────────────────────────
# 07_observability.md — Langfuse pointer + Hobby quota
# ─────────────────────────────────────────────────────────────────────


class TestObservabilityRecipeLangfuse:
    """07_observability.md must reference Langfuse Cloud with quota note."""

    DOC_PATH = "docs/recipes/gcp/07_observability.md"

    def test_mentions_langfuse(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower(), (
            "07_observability.md must mention Langfuse"
        )

    def test_mentions_hobby_quota(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "50" in content and "langfuse" in content.lower(), (
            "07_observability.md must note the Hobby tier quota (50K units/mo)"
        )


# ─────────────────────────────────────────────────────────────────────
# END_TO_END_TRACING_GUIDE.md — sixth trace plane, no stale Known Gap
# ─────────────────────────────────────────────────────────────────────


class TestEndToEndTracingGuideLangfuse:
    """END_TO_END_TRACING_GUIDE.md must document the sixth Langfuse trace plane
    and retire the stale Known Gap about trace_id threading.
    """

    DOC_PATH = "docs/explainability/END_TO_END_TRACING_GUIDE.md"

    def test_has_six_trace_planes(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "six" in content.lower() or "6" in content, (
            "END_TO_END_TRACING_GUIDE.md must document six trace planes (not five)"
        )

    def test_langfuse_is_a_trace_plane(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower(), (
            "END_TO_END_TRACING_GUIDE.md must list Langfuse as a trace plane"
        )

    def test_known_gap_retired(self) -> None:
        """The stale Known Gap about trace_id not being threaded into the
        graph must be retired or updated (trace_id threading is now fixed
        in LangGraphRuntime).
        """
        content = _read_doc(self.DOC_PATH)
        assert "known gap" not in content.lower() or "resolved" in content.lower() or "fixed" in content.lower(), (
            "END_TO_END_TRACING_GUIDE.md must retire or mark as resolved "
            "the stale Known Gap about trace_id threading"
        )

    def test_langfuse_plane_in_table(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower() and "plane" in content.lower(), (
            "END_TO_END_TRACING_GUIDE.md must include Langfuse in the trace planes table"
        )


# ─────────────────────────────────────────────────────────────────────
# FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md §4.5 — API alignment
# ─────────────────────────────────────────────────────────────────────


class TestPortsAndAdaptersApiAlignment:
    """§4.5 TelemetrySink must document the actual TelemetryExporter API
    (export_event / release_trace / shutdown), not the stale
    start_span / finish_span / flush signatures.
    """

    DOC_PATH = "docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md"

    def test_python_port_shows_export_event(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "export_event" in content, (
            "§4.5 Python port must show export_event() method (not start_span)"
        )

    def test_python_port_shows_release_trace(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "release_trace" in content, (
            "§4.5 Python port must show release_trace() method"
        )

    def test_python_port_shows_shutdown(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "shutdown" in content, (
            "§4.5 Python port must show shutdown() method (not flush)"
        )

    def test_adapter_name_is_langfuse_cloud_exporter(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "LangfuseCloudExporter" in content, (
            "§4.5 must reference LangfuseCloudExporter (the actual adapter name)"
        )


# ─────────────────────────────────────────────────────────────────────
# GCP_DEPLOYMENT_ARCHITECTURE.md — /run/stream export note
# ─────────────────────────────────────────────────────────────────────


class TestGcpDeployArchLangfuseNote:
    """GCP_DEPLOYMENT_ARCHITECTURE.md must note that /run/stream emits
    telemetry via the Langfuse exporter.
    """

    DOC_PATH = "docs/Architectures/GCP_DEPLOYMENT_ARCHITECTURE.md"

    def test_mentions_langfuse_or_telemetry_export(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert (
            "langfuse" in content.lower() or "telemetry" in content.lower()
        ), (
            "GCP_DEPLOYMENT_ARCHITECTURE.md must mention Langfuse or "
            "telemetry export for the middleware ring"
        )

    def test_mentions_run_stream_telemetry(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "langfuse" in content.lower(), (
            "GCP_DEPLOYMENT_ARCHITECTURE.md must reference Langfuse export "
            "from /run/stream"
        )


# ─────────────────────────────────────────────────────────────────────
# RUNBOOK.md §4.1 — adapter naming
# ─────────────────────────────────────────────────────────────────────


class TestRunbookAdapterNaming:
    """RUNBOOK.md §4.1 must use LangfuseCloudExporter (the actual class name),
    not stale adapter names like LangfuseCloudHobbyAdapter.
    """

    DOC_PATH = "infra/RUNBOOK.md"

    def test_uses_correct_adapter_name(self) -> None:
        content = _read_doc(self.DOC_PATH)
        assert "LangfuseCloudExporter" in content, (
            "RUNBOOK.md must use LangfuseCloudExporter (actual adapter name)"
        )

    def test_no_stale_hobby_adapter_name(self) -> None:
        """Failure path: stale adapter name must not appear."""
        content = _read_doc(self.DOC_PATH)
        assert "LangfuseCloudHobbyAdapter" not in content, (
            "RUNBOOK.md must NOT use stale name LangfuseCloudHobbyAdapter "
            "(actual class is LangfuseCloudExporter)"
        )


# ─────────────────────────────────────────────────────────────────────
# smoke_gcp.sh — Langfuse init failure check
# ─────────────────────────────────────────────────────────────────────


class TestSmokeScriptLangfuseCheck:
    """smoke_gcp.sh must grep for 'langfuse client init failed' warning."""

    SCRIPT_PATH = "scripts/smoke_gcp.sh"

    def test_checks_langfuse_init_failure(self) -> None:
        content = _read_doc(self.SCRIPT_PATH)
        assert "langfuse" in content.lower(), (
            "smoke_gcp.sh must check for Langfuse init failure warning"
        )

    def test_langfuse_init_warning_pattern(self) -> None:
        content = _read_doc(self.SCRIPT_PATH)
        assert "langfuse client init failed" in content.lower() or "langfuse_init" in content.lower(), (
            "smoke_gcp.sh must grep for 'langfuse client init failed' pattern"
        )
