"""BlackBoxToTelemetryRelay — outbox relay from BlackBox JSONL to Langfuse.

Sprints C + E of the BlackBox→Langfuse plan.

Tails ``cache/black_box_recordings/*/trace.jsonl`` (the transactional outbox),
publishes each event via the ``TelemetryExporter`` port, and tracks per-workflow
byte offsets for at-least-once delivery.  Poison events go to a per-workflow
``.langfuse_failures.jsonl`` dead-letter queue.

Sprint E addition: on observing a ``TASK_COMPLETED`` event, calls
``BlackBoxRecorder.export_for_compliance()`` and publishes the integrity-
verified bundle as a Langfuse dataset item (via ``CompliancePublisher`` port).
Valid chains go to ``agent-compliance-audit``; failures go to
``agent-incident-replay``.  Attaches ``hash_chain_valid`` as a Langfuse score.

Layering invariants (enforced by tests/middleware/sidecars/test_black_box_to_telemetry.py):
  - Zero ``langfuse`` or ``langgraph`` imports.
  - Uses the ``TelemetryExporter`` and ``CompliancePublisher`` ports, never the SDK directly.
  - Mapping + redaction delegated to ``services.governance.black_box_publisher``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from middleware.ports.compliance_publisher import CompliancePublisher
from middleware.ports.telemetry_exporter import TelemetryExporter
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.black_box_publisher import to_export_kwargs

logger = logging.getLogger("middleware.sidecars.black_box_to_telemetry")

__all__ = ["BlackBoxToTelemetryRelay"]


class BlackBoxToTelemetryRelay:
    """Async-capable relay that tails BlackBox JSONL files and publishes to Langfuse.

    Args:
        storage_dir: Root of ``cache/black_box_recordings/``.
        exporter: ``TelemetryExporter`` port implementation.
        compliance_publisher: Optional ``CompliancePublisher`` port for dataset items.
        max_retries: Per-line retry count before DLQ promotion.
        base_delay_s: Base delay for jittered exponential backoff.
    """

    DATASET_AUDIT = "agent-compliance-audit"
    DATASET_INCIDENT = "agent-incident-replay"

    def __init__(
        self,
        storage_dir: Path | str,
        exporter: TelemetryExporter,
        compliance_publisher: CompliancePublisher | None = None,
        *,
        max_retries: int = 5,
        base_delay_s: float = 1.0,
    ) -> None:
        self._storage_dir = Path(storage_dir)
        self._exporter = exporter
        self._compliance_publisher = compliance_publisher
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s
        self._mtimes: dict[str, float] = {}
        self._stopped = False
        self._published_compliance: set[str] = set()

    # ── public API ──────────────────────────────────────────────────

    def run_once(self) -> int:
        """Scan all workflow dirs, publish new events.  Returns count published."""
        if not self._storage_dir.exists():
            logger.debug("Relay storage dir does not exist: %s", self._storage_dir)
            return 0

        total = 0
        for wf_dir in sorted(self._storage_dir.iterdir()):
            if not wf_dir.is_dir():
                continue
            trace_file = wf_dir / "trace.jsonl"
            if not trace_file.exists():
                continue
            published = self._process_workflow(wf_dir, trace_file)
            if published > 0:
                logger.info(
                    "Relay published %d event(s) for workflow %s",
                    published,
                    wf_dir.name,
                )
            total += published
        return total

    async def run_forever(self, interval_s: float = 1.0) -> None:
        """Async loop wrapping ``run_once`` at *interval_s*."""
        while not self._stopped:
            try:
                self.run_once()
            except Exception:
                logger.exception("run_once iteration failed")
            await asyncio.sleep(interval_s)

    def stop(self) -> None:
        """Signal ``run_forever`` to exit after the current iteration."""
        self._stopped = True

    # ── internals ───────────────────────────────────────────────────

    def _process_workflow(self, wf_dir: Path, trace_file: Path) -> int:
        wf_id = wf_dir.name

        current_mtime = trace_file.stat().st_mtime
        if wf_id in self._mtimes and self._mtimes[wf_id] == current_mtime:
            return 0

        offset_file = wf_dir / ".langfuse_offset"
        file_size = trace_file.stat().st_size

        if not offset_file.exists():
            offset_file.write_text("0")

        offset = int(offset_file.read_text().strip())
        if offset >= file_size:
            self._mtimes[wf_id] = current_mtime
            return 0

        with open(trace_file, "rb") as fh:
            fh.seek(offset)
            new_bytes = fh.read()

        new_text = new_bytes.decode("utf-8")

        # Only process complete lines — partial tail deferred to next poll
        if new_text and not new_text.endswith("\n"):
            last_nl = new_text.rfind("\n")
            if last_nl == -1:
                self._mtimes[wf_id] = current_mtime
                return 0
            new_text = new_text[: last_nl + 1]

        bytes_consumed = len(new_text.encode("utf-8"))
        published = 0

        for line in new_text.splitlines():
            if not line.strip():
                continue
            if self._process_line(wf_dir, line):
                published += 1

        offset_file.write_text(str(offset + bytes_consumed))
        self._mtimes[wf_id] = current_mtime
        return published

    def _process_line(self, wf_dir: Path, line: str) -> bool:
        """Parse, map, and export a single JSONL line.  Returns True on success."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                event_data = json.loads(line)
                event = TraceEvent.model_validate(event_data)
                kwargs = to_export_kwargs(event)

                attrs: dict[str, Any] = dict(kwargs["attributes"])
                attrs["__bb_observation_id"] = kwargs["observation_id"]
                attrs["__bb_observation_type"] = kwargs["observation_type"]
                attrs["__bb_level"] = kwargs["level"]
                if event.details:
                    attrs["__output"] = event.details

                self._exporter.export_event(
                    name=kwargs["name"],
                    trace_id=kwargs["trace_id"],
                    attributes=attrs,
                )

                if event.event_type == EventType.TASK_COMPLETED:
                    self._publish_compliance_bundle(event.workflow_id, event.details)

                return True
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries and self._base_delay_s > 0:
                    delay = self._base_delay_s * (2**attempt)
                    jitter = random.uniform(0, delay * 0.5)
                    time.sleep(delay + jitter)

        self._write_dlq(wf_dir, line, str(last_exc))
        return False

    def _publish_compliance_bundle(
        self, workflow_id: str, task_details: dict[str, Any]
    ) -> None:
        """Export compliance bundle as a Langfuse dataset item on TASK_COMPLETED.

        Idempotent: skips if already published for this workflow_id in this session.
        Failures are swallowed per rule O1.
        """
        if self._compliance_publisher is None:
            return
        if workflow_id in self._published_compliance:
            return

        self._published_compliance.add(workflow_id)

        try:
            recorder = BlackBoxRecorder(storage_dir=self._storage_dir)
            bundle = recorder.export_for_compliance(workflow_id)
        except Exception as exc:
            logger.warning(
                "Failed to export compliance bundle for %s: %s", workflow_id, exc
            )
            return

        chain_valid = bundle.get("hash_chain_valid", False)
        outcome = task_details.get("outcome", "")

        try:
            self._compliance_publisher.score_trace(
                trace_id=workflow_id,
                name="hash_chain_valid",
                value=1.0 if chain_valid else 0.0,
                comment=None if chain_valid else "Integrity hash chain broken or invalid",
            )
        except Exception as exc:
            logger.warning(
                "Failed to score trace %s: %s", workflow_id, exc
            )

        try:
            self._compliance_publisher.create_dataset_item(
                dataset_name=self.DATASET_AUDIT if chain_valid else self.DATASET_INCIDENT,
                input_data=bundle,
                item_id=workflow_id,
                metadata={"workflow_id": workflow_id, "chain_valid": chain_valid},
            )
        except Exception as exc:
            logger.warning(
                "Failed to publish compliance dataset item for %s: %s",
                workflow_id, exc,
            )

        if chain_valid and outcome == "failure":
            try:
                self._compliance_publisher.create_dataset_item(
                    dataset_name=self.DATASET_INCIDENT,
                    input_data=bundle,
                    item_id=f"{workflow_id}-incident",
                    metadata={"workflow_id": workflow_id, "reason": "task_failure"},
                )
            except Exception as exc:
                logger.warning(
                    "Failed to publish incident dataset item for %s: %s",
                    workflow_id, exc,
                )

    @staticmethod
    def _write_dlq(wf_dir: Path, line: str, error: str) -> None:
        dlq_file = wf_dir / ".langfuse_failures.jsonl"
        entry = json.dumps(
            {"line": line, "error": error, "timestamp": datetime.now(UTC).isoformat()},
            default=str,
        )
        with open(dlq_file, "a") as fh:
            fh.write(entry + "\n")
        logger.warning("DLQ: poison event in %s: %s", wf_dir.name, error[:120])
