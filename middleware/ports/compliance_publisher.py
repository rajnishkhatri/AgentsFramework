"""CompliancePublisher port -- vendor-neutral contract for compliance dataset operations.

Sprint E of the BlackBox→Langfuse plan.

Defines the protocol for publishing compliance bundles as dataset items
and attaching integrity scores to traces.  The relay sidecar depends on
this port; the concrete implementation lives in
``middleware/adapters/observability/langfuse_cloud_exporter.py``.

**Rule O1 (telemetry never blocks):** implementations MUST swallow
failures silently — raising in the publisher must NEVER abort the relay.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["CompliancePublisher"]


@runtime_checkable
class CompliancePublisher(Protocol):
    """Application-contract port for compliance dataset publishing."""

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input_data: dict[str, Any],
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a dataset item into a named Langfuse dataset.

        MUST NOT raise — per O1, telemetry failures are silent.
        """
        ...

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """Attach a numeric score to a trace.

        MUST NOT raise — per O1, telemetry failures are silent.
        """
        ...
