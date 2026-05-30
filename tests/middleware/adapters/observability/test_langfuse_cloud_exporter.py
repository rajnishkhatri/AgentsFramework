"""L2 tests for LangfuseCloudExporter — contract-driven TDD.

Tests the hardened exporter (Phase 1 of Langfuse GCP Integration plan):
  - Trace grouping: two export_event() calls with same trace_id → one trace, two children
  - Kill switch: LANGFUSE_ENABLED=false makes all methods no-ops
  - release_trace(): clears in-memory handle so next call opens a new trace
  - Init failure: logs WARNING, returns None, never raises
  - shutdown: calls flush on SDK client

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD with mock SDK client
Anti-patterns avoided: Tautological (no reimplementation), Mock Addiction (single mock of SDK boundary)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


class FakeNotFoundError(Exception):
    """Mirrors the SDK's 404 when a dataset does not exist yet."""


class FakeObservation:
    """Fake observation returned by FakeLangfuseClient.start_observation().

    Mirrors the SDK v4 nesting API: a span object exposes ``start_observation``
    to create a manual child (``parent.start_observation(...)``). Children are
    recorded on the owning client so tests can assert the hierarchy.
    """

    def __init__(self, data: dict, client: "FakeLangfuseClient | None" = None) -> None:
        self.data = data
        self._client = client
        self.ended = False

    def end(self, **kwargs: object) -> None:
        self.ended = True
        self.data["ended"] = True
        if "output" in kwargs:
            self.data["output"] = kwargs.get("output")

    def start_observation(
        self,
        *,
        name: str,
        as_type: str = "span",
        input: dict | None = None,
        metadata: dict | None = None,
        **kwargs,
    ) -> "FakeObservation":
        unknown = set(kwargs) - FakeLangfuseClient._SDK_KWARGS
        if unknown:
            raise TypeError(
                "LangfuseSpan.start_observation() got an unexpected keyword "
                f"argument {sorted(unknown)[0]!r}"
            )
        child_data = {
            "trace_id": self.data.get("trace_id"),
            "name": name,
            "input": input,
            "as_type": as_type,
            "metadata": metadata,
            "parent_name": self.data.get("name"),
            **kwargs,
        }
        if self._client is not None:
            self._client.children.append(child_data)
        return FakeObservation(child_data, self._client)


class FakeLangfuseClient:
    """In-memory stand-in for the Langfuse SDK v4 client.

    ``start_observation`` deliberately mirrors the **real** SDK v4.5.1
    signature exactly — no ``**kwargs`` catch-all. A catch-all is what hid the
    S1 BlackBox-relay bug: the exporter passed an unsupported ``id`` kwarg, the
    old fake silently absorbed it, and CI stayed green while 100% of BlackBox
    observations threw ``TypeError`` against the strict real SDK. Rejecting
    unknown kwargs here turns that class of regression into a CI failure.
    """

    # Exact keyword set accepted by langfuse>=4 ``Langfuse.start_observation``.
    _SDK_KWARGS = frozenset(
        {
            "trace_context",
            "name",
            "as_type",
            "input",
            "output",
            "metadata",
            "version",
            "level",
            "status_message",
            "completion_start_time",
            "model",
            "model_parameters",
            "usage_details",
            "cost_details",
            "prompt",
        }
    )

    def __init__(self) -> None:
        self.traces: dict[str, dict] = {}
        self.spans: list[dict] = []
        self.children: list[dict] = []
        self.flushed = False
        self.scores: list[dict] = []
        self.datasets: set[str] = set()
        self.dataset_items: list[dict] = []

    def start_observation(
        self,
        *,
        trace_context: dict | None = None,
        name: str,
        as_type: str = "span",
        input: dict | None = None,
        metadata: dict | None = None,
        **kwargs,
    ) -> FakeObservation:
        # Reject anything outside the real SDK signature (mirrors the strict
        # keyword-only contract of langfuse>=4 ``start_observation``).
        unknown = set(kwargs) - self._SDK_KWARGS
        if unknown:
            raise TypeError(
                "Langfuse.start_observation() got an unexpected keyword "
                f"argument {sorted(unknown)[0]!r}"
            )
        trace_id = (trace_context or {}).get("trace_id", "unknown")
        if trace_id not in self.traces:
            self.traces[trace_id] = {"id": trace_id}
        span_data = {
            "trace_id": trace_id,
            "name": name,
            "input": input,
            "as_type": as_type,
            "metadata": metadata,
            **kwargs,
        }
        self.spans.append(span_data)
        return FakeObservation(span_data, self)

    # NOTE: deliberately NO ``score`` method. SDK v4 renamed trace scoring to
    # ``create_score``; the old ``Langfuse.score`` attribute is gone. Omitting it
    # here turns a regression back to ``client.score(...)`` into an
    # AttributeError (the second hidden-failure bug class) rather than a pass.
    def create_score(
        self,
        *,
        name: str,
        value: float | str,
        trace_id: str | None = None,
        comment: str | None = None,
        **kwargs,
    ) -> None:
        self.scores.append(
            {
                "name": name,
                "value": value,
                "trace_id": trace_id,
                "comment": comment,
            }
        )

    def create_dataset(self, *, name: str, **kwargs) -> dict:
        # Idempotent upsert by name (mirrors POST /api/public/v2/datasets).
        self.datasets.add(name)
        return {"name": name}

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input: dict | None = None,
        id: str | None = None,
        metadata: dict | None = None,
        **kwargs,
    ) -> dict:
        # Mirror the real SDK: inserting into a non-existent dataset 404s. This
        # is the bug that dropped every compliance item — the exporter must
        # ensure the dataset exists first.
        if dataset_name not in self.datasets:
            raise FakeNotFoundError(
                f"Dataset {dataset_name} not found for project test"
            )
        item = {
            "dataset_name": dataset_name,
            "input": input,
            "id": id,
            "metadata": metadata,
        }
        self.dataset_items.append(item)
        return item

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def fake_client() -> FakeLangfuseClient:
    return FakeLangfuseClient()


@pytest.fixture
def exporter(fake_client: FakeLangfuseClient) -> LangfuseCloudExporter:
    return LangfuseCloudExporter(
        public_key="pk-test",
        secret_key="sk-test",
        host="https://cloud.langfuse.com",
        sdk_client=fake_client,
    )


# ─────────────────────────────────────────────────────────────────────
# Trace Grouping Contract
# ─────────────────────────────────────────────────────────────────────


class TestTraceGrouping:
    """Two export_event() calls with same trace_id produce one trace with two children."""

    def test_first_export_creates_trace(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        assert "trace-001" in fake_client.traces

    def test_second_export_reuses_trace(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.export_event(name="tool.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1, "Should create only one trace"

    def test_two_exports_same_trace_produce_two_child_spans(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="run.started",
            trace_id="trace-001",
            attributes={"run_id": "run-1"},
        )
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell"},
        )
        assert len(fake_client.spans) == 2

    def test_different_trace_ids_create_separate_traces(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.export_event(name="run.started", trace_id="trace-002")
        assert len(fake_client.traces) == 2

    def test_child_span_carries_event_name(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell"},
        )
        assert fake_client.spans[0]["name"] == "tool.started"

    def test_child_span_carries_attributes_as_input(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell", "tool_call_id": "tc-1"},
        )
        assert fake_client.spans[0]["input"] == {
            "tool_name": "shell",
            "tool_call_id": "tc-1",
        }


# ─────────────────────────────────────────────────────────────────────
# release_trace() Contract
# ─────────────────────────────────────────────────────────────────────


class TestReleaseTrace:
    """release_trace() clears the in-memory handle; next call opens a fresh trace."""

    def test_release_drops_handle(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.release_trace("trace-001")
        exporter.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.spans) == 2
        assert fake_client.flushed is True

    def test_release_nonexistent_trace_is_noop(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        # Should not raise
        exporter.release_trace("nonexistent-trace")


# ─────────────────────────────────────────────────────────────────────
# LANGFUSE_ENABLED Kill Switch
# ─────────────────────────────────────────────────────────────────────


class TestKillSwitch:
    """LANGFUSE_ENABLED=false makes every method a silent no-op."""

    def test_disabled_export_event_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 0
        assert len(fake_client.spans) == 0

    def test_disabled_shutdown_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.shutdown()
        assert fake_client.flushed is False

    def test_disabled_release_trace_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.release_trace("trace-001")  # Should not raise

    def test_enabled_by_default(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        """When LANGFUSE_ENABLED is not set, exporter is active."""
        exporter.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1

    def test_enabled_true_explicit(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1


# ─────────────────────────────────────────────────────────────────────
# Init Failure Handling (O1)
# ─────────────────────────────────────────────────────────────────────


class TestInitFailure:
    """Init failure logs WARNING, returns None client, never raises."""

    def test_init_failure_logs_warning_and_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("connection refused"),
            create=True,
        ):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
            )
            # Force client init by calling export_event
            exp.export_event(name="run.started", trace_id="trace-001")
        assert "langfuse client init failed" in caplog.text

    def test_init_failure_export_event_does_not_raise(self) -> None:
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("connection refused"),
            create=True,
        ):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
            )
            # Must not raise
            exp.export_event(name="run.started", trace_id="trace-001")


# ─────────────────────────────────────────────────────────────────────
# Export Failure Handling (O1)
# ─────────────────────────────────────────────────────────────────────


class TestExportFailure:
    """Export failures are swallowed silently (O1)."""

    def test_export_event_swallows_sdk_exception(self) -> None:
        broken_client = MagicMock()
        broken_client.start_observation.side_effect = RuntimeError("SDK crash")
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=broken_client,
        )
        # Must not raise
        exp.export_event(name="run.started", trace_id="trace-001")

    def test_release_trace_swallows_exception(self) -> None:
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=MagicMock(),
        )
        # Force internal state then break it
        exp._traces = None  # type: ignore[attr-defined]
        # Must not raise
        exp.release_trace("trace-001")


# ─────────────────────────────────────────────────────────────────────
# export_event() bool contract (relay success signal)
# ─────────────────────────────────────────────────────────────────────


class TestExportEventReturnValue:
    """``export_event`` returns True on publish/no-op, False on swallowed error.

    This is the relay's success signal: it lets the BlackBox relay distinguish a
    real publish from a swallowed failure so swallowed failures get dead-lettered
    instead of being silently counted as published.
    """

    def test_returns_true_on_success(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        assert exporter.export_event(name="run.started", trace_id="t-1") is True

    def test_returns_false_on_swallowed_sdk_exception(self) -> None:
        broken_client = MagicMock()
        broken_client.start_observation.side_effect = RuntimeError("SDK crash")
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=broken_client,
        )
        assert exp.export_event(name="run.started", trace_id="t-1") is False

    def test_returns_true_when_disabled(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        # Intentional no-op is success, not a failure to dead-letter.
        assert exp.export_event(name="run.started", trace_id="t-1") is True

    def test_returns_true_when_client_unavailable(self) -> None:
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("connection refused"),
            create=True,
        ):
            exp = LangfuseCloudExporter(public_key="pk-test", secret_key="sk-test")
            assert exp.export_event(name="run.started", trace_id="t-1") is True


# ─────────────────────────────────────────────────────────────────────
# BlackBox relay hints — `id` kwarg regression guard (S1 root cause)
# ─────────────────────────────────────────────────────────────────────


class TestBlackBoxRelayHints:
    """The exporter must NOT forward the unsupported ``id`` kwarg to the SDK.

    Regression guard for the S1 root cause: the exporter used to set
    ``start_observation(id=...)``, which raises ``TypeError`` on the real SDK v4
    and was swallowed (rule O1), dropping 100% of BlackBox observations.
    """

    def test_fake_client_rejects_unknown_kwargs(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        # The fake now mirrors the strict real SDK signature.
        with pytest.raises(TypeError, match="unexpected keyword argument 'id'"):
            fake_client.start_observation(
                trace_context={"trace_id": "t-1"},
                name="task.started",
                id="bb-event-1",  # type: ignore[call-arg]
            )

    def test_bb_observation_id_does_not_reach_sdk(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        result = exporter.export_event(
            name="task.started",
            trace_id="t-1",
            attributes={
                "__bb_observation_id": "bb-event-1",
                "__bb_observation_type": "agent",
                "task": "demo",
            },
        )
        # Export succeeds (no TypeError swallowed) ...
        assert result is True
        assert len(fake_client.spans) == 1
        span = fake_client.spans[0]
        # ... and neither the relay hint nor an `id` kwarg leaked through.
        assert "id" not in span
        assert "__bb_observation_id" not in (span.get("metadata") or {})
        assert "__bb_observation_id" not in (span.get("input") or {})
        assert span["as_type"] == "agent"


# ─────────────────────────────────────────────────────────────────────
# score_trace() — SDK v4 create_score regression guard
# ─────────────────────────────────────────────────────────────────────


class TestScoreTrace:
    """score_trace must use the SDK v4 ``create_score`` API, not ``.score``.

    Regression guard: the exporter used to call ``client.score(...)``, which
    raised ``AttributeError`` on the real SDK v4 (no such method) and was
    swallowed per rule O1 — so ``hash_chain_valid`` never reached Langfuse.
    """

    def test_real_sdk_has_no_score_attribute(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        # The fake mirrors the strict v4 surface: ``score`` is gone.
        assert not hasattr(fake_client, "score")
        assert hasattr(fake_client, "create_score")

    def test_score_trace_records_score(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.score_trace(
            trace_id="t-1", name="hash_chain_valid", value=1.0
        )
        assert len(fake_client.scores) == 1
        score = fake_client.scores[0]
        assert score["trace_id"] == "t-1"
        assert score["name"] == "hash_chain_valid"
        assert score["value"] == 1.0

    def test_score_trace_passes_comment(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.score_trace(
            trace_id="t-2",
            name="hash_chain_valid",
            value=0.0,
            comment="Integrity hash chain broken or invalid",
        )
        assert fake_client.scores[0]["comment"] == (
            "Integrity hash chain broken or invalid"
        )


# ─────────────────────────────────────────────────────────────────────
# create_dataset_item() — dataset-must-exist regression guard
# ─────────────────────────────────────────────────────────────────────


class TestCreateDatasetItem:
    """create_dataset_item must ensure the dataset exists first.

    Regression guard: SDK v4 does not auto-create the dataset, so the first
    insert into a fresh dataset 404'd and was swallowed per rule O1 — dropping
    every compliance audit item.
    """

    def test_fake_rejects_item_for_unknown_dataset(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with pytest.raises(FakeNotFoundError, match="not found"):
            fake_client.create_dataset_item(
                dataset_name="agent-compliance-audit", input={"x": 1}
            )

    def test_create_dataset_item_creates_dataset_first(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.create_dataset_item(
            dataset_name="agent-compliance-audit",
            input_data={"hash_chain_valid": True},
            item_id="wf-1",
            metadata={"workflow_id": "wf-1"},
        )
        # Dataset was upserted ...
        assert "agent-compliance-audit" in fake_client.datasets
        # ... and the item landed.
        assert len(fake_client.dataset_items) == 1
        item = fake_client.dataset_items[0]
        assert item["dataset_name"] == "agent-compliance-audit"
        assert item["id"] == "wf-1"
        assert item["input"] == {"hash_chain_valid": True}

    def test_create_dataset_item_swallows_errors(self) -> None:
        broken = MagicMock()
        broken.create_dataset.side_effect = RuntimeError("network down")
        exp = LangfuseCloudExporter(
            public_key="pk-test", secret_key="sk-test", sdk_client=broken
        )
        # Must not raise (rule O1).
        exp.create_dataset_item(
            dataset_name="agent-compliance-audit", input_data={"x": 1}
        )


# ─────────────────────────────────────────────────────────────────────
# Shutdown Contract
# ─────────────────────────────────────────────────────────────────────


class TestShutdown:
    """shutdown() calls flush on the SDK client."""

    def test_shutdown_calls_flush(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.shutdown()
        assert fake_client.flushed is True

    def test_shutdown_swallows_flush_failure(self) -> None:
        broken_client = MagicMock()
        broken_client.flush.side_effect = RuntimeError("flush failed")
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=broken_client,
        )
        # Must not raise
        exp.shutdown()


# ─────────────────────────────────────────────────────────────────────
# I6 — Step-span nesting (real SDK v4 nesting, not synthetic ids)
# ─────────────────────────────────────────────────────────────────────


class TestStepSpanNesting:
    """Children carrying ``__bb_parent_observation_id`` nest under a real step span.

    Regression guard for I6: the exporter used to forward the publisher's
    synthetic ``workflow:step:N`` string as ``parent_observation_id``, which
    matched no real observation — so nesting silently did nothing (and against
    the strict SDK signature it would have raised + been swallowed). The fix
    creates one live step span per ``(trace, step)`` and uses the SDK's real
    ``parent.start_observation`` nesting API.
    """

    def test_child_event_creates_one_step_span(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="step.planned",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:2", "k": "v"},
        )
        step_spans = [s for s in fake_client.spans if s["name"] == "step.2"]
        assert len(step_spans) == 1
        assert step_spans[0]["as_type"] == "span"

    def test_step_span_created_once_per_trace_step(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        for _ in range(3):
            exporter.export_event(
                name="tool.called",
                trace_id="wf-1",
                attributes={"__bb_parent_observation_id": "wf-1:step:2"},
            )
        step_spans = [s for s in fake_client.spans if s["name"] == "step.2"]
        assert len(step_spans) == 1, "step span must be created once and reused"
        assert len(fake_client.children) == 3, "all three children nest under it"

    def test_children_nest_under_step_span(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:5"},
        )
        assert len(fake_client.children) == 1
        assert fake_client.children[0]["parent_name"] == "step.5"

    def test_different_steps_get_separate_spans(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:1"},
        )
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:2"},
        )
        names = {s["name"] for s in fake_client.spans if s["name"].startswith("step.")}
        assert names == {"step.1", "step.2"}

    def test_synthetic_parent_id_never_reaches_sdk(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:2", "tool": "shell"},
        )
        child = fake_client.children[0]
        assert "parent_observation_id" not in child
        assert "__bb_parent_observation_id" not in (child.get("metadata") or {})
        assert "__bb_parent_observation_id" not in (child.get("input") or {})

    def test_generation_child_carries_native_fields(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        """The I5 native fields flow through the nested generation child."""
        exporter.export_event(
            name="model.selected",
            trace_id="wf-1",
            attributes={
                "__bb_parent_observation_id": "wf-1:step:1",
                "__bb_observation_type": "generation",
                "__bb_model": "gpt-4o-mini",
                "__bb_usage": {"input": 10, "output": 5, "total": 15},
                "__bb_cost": 0.0012,
            },
        )
        child = fake_client.children[0]
        assert child["as_type"] == "generation"
        assert child["model"] == "gpt-4o-mini"
        assert child["usage_details"] == {"input": 10, "output": 5, "total": 15}
        assert child["cost_details"] == {"total": 0.0012}

    def test_release_trace_ends_step_spans(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:1"},
        )
        step_span = next(s for s in fake_client.spans if s["name"] == "step.1")
        assert step_span.get("ended") is not True  # still open mid-run
        exporter.release_trace("wf-1")
        assert step_span.get("ended") is True
        assert fake_client.flushed is True
        # A subsequent event for the same step opens a fresh span.
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:1"},
        )
        assert len([s for s in fake_client.spans if s["name"] == "step.1"]) == 2

    def test_nesting_failure_does_not_propagate(self) -> None:
        broken = MagicMock()
        broken.start_observation.side_effect = RuntimeError("SDK crash")
        exp = LangfuseCloudExporter(
            public_key="pk-test", secret_key="sk-test", sdk_client=broken
        )
        # Must not raise; returns False so the relay dead-letters.
        result = exp.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:1"},
        )
        assert result is False


# ─────────────────────────────────────────────────────────────────────
# I8 — per-trace event_id idempotency (duplicate terminal events)
# ─────────────────────────────────────────────────────────────────────


class TestEventIdIdempotency:
    """A repeated BlackBox ``event_id`` for a trace exports exactly one observation.

    Regression guard for I8: the at-least-once relay (background poll +
    SSE-finally drain) can hand the exporter the same ``task.completed`` /
    ``step.executed`` line twice, and SDK v4 cannot upsert on a caller id — so
    duplicates surfaced with identical metadata ``event_id``. The exporter now
    drops the second export per ``(trace_id, event_id)``.
    """

    def test_duplicate_event_id_exports_once(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        attrs = {"__bb_observation_id": "ev-1", "event_id": "ev-1", "k": "v"}
        assert exporter.export_event(
            name="task.completed", trace_id="wf-1", attributes=dict(attrs)
        ) is True
        assert exporter.export_event(
            name="task.completed", trace_id="wf-1", attributes=dict(attrs)
        ) is True
        assert len(fake_client.spans) == 1, "second export of same event_id is a no-op"

    def test_distinct_event_ids_each_export(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="step.executed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        )
        exporter.export_event(
            name="step.executed", trace_id="wf-1", attributes={"event_id": "ev-2"}
        )
        assert len(fake_client.spans) == 2

    def test_same_event_id_different_trace_both_export(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="task.completed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        )
        exporter.export_event(
            name="task.completed", trace_id="wf-2", attributes={"event_id": "ev-1"}
        )
        assert len(fake_client.spans) == 2, "dedup is scoped per-trace, not global"

    def test_events_without_event_id_are_not_deduped(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        # Direct domain-bridge events (run.started, etc.) carry no event_id and
        # must never be dropped as duplicates.
        exporter.export_event(name="run.started", trace_id="wf-1")
        exporter.export_event(name="run.started", trace_id="wf-1")
        assert len(fake_client.spans) == 2

    def test_failed_export_is_not_marked_seen(self) -> None:
        """A swallowed failure must be retryable, not silently deduped away."""
        broken = MagicMock()
        broken.start_observation.side_effect = RuntimeError("SDK crash")
        exp = LangfuseCloudExporter(
            public_key="pk-test", secret_key="sk-test", sdk_client=broken
        )
        assert exp.export_event(
            name="task.completed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        ) is False
        # Recover the client; the retry must now go through (not be deduped).
        good = FakeLangfuseClient()
        exp._sdk_client = good
        assert exp.export_event(
            name="task.completed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        ) is True
        assert len(good.spans) == 1

    def test_release_trace_clears_seen_set(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="task.completed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        )
        exporter.release_trace("wf-1")
        # A re-used trace_id starts fresh after the run boundary.
        exporter.export_event(
            name="task.completed", trace_id="wf-1", attributes={"event_id": "ev-1"}
        )
        assert len(fake_client.spans) == 2

    def test_release_trace_is_idempotent(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        """Calling release_trace twice (bridge + SSE finally) must be safe."""
        exporter.export_event(
            name="tool.called",
            trace_id="wf-1",
            attributes={"__bb_parent_observation_id": "wf-1:step:1"},
        )
        exporter.release_trace("wf-1")
        # Second release is a no-op: no error, no double-flush crash.
        exporter.release_trace("wf-1")
        step_span = next(s for s in fake_client.spans if s["name"] == "step.1")
        assert step_span.get("ended") is True


# ─────────────────────────────────────────────────────────────────────
# Port Protocol Compliance
# ─────────────────────────────────────────────────────────────────────


class TestPortCompliance:
    """LangfuseCloudExporter satisfies TelemetryExporter Protocol."""

    def test_is_telemetry_exporter(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        from middleware.ports.telemetry_exporter import TelemetryExporter

        assert isinstance(exporter, TelemetryExporter)
