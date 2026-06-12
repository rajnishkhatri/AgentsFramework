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
import os
import random
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from middleware.ports.compliance_publisher import CompliancePublisher
from middleware.ports.telemetry_exporter import TelemetryExporter
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import PhaseLogger
from services.governance.black_box_publisher import (
    redact_compliance_bundle,
    redact_details,
    to_export_kwargs,
)

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

    # Phase 1 (E1/E9): terminal verdict fields lifted from TASK_COMPLETED details
    # to trace-level Langfuse scores so a run is triageable from the list view.
    # ``goal_met`` is a bool → 0.0/1.0; the rest are already 0..1 numerics.
    _OUTCOME_SCORE_FIELDS: tuple[str, ...] = (
        "goal_met",
        "criteria_met",
        "task_completion_score",
    )

    def __init__(
        self,
        storage_dir: Path | str,
        exporter: TelemetryExporter,
        compliance_publisher: CompliancePublisher | None = None,
        *,
        agent_facts_registry: Any = None,
        max_retries: int = 5,
        base_delay_s: float = 1.0,
    ) -> None:
        self._storage_dir = Path(storage_dir)
        self._exporter = exporter
        self._compliance_publisher = compliance_publisher
        # E7: forwarded into ``export_for_compliance`` so the compliance bundle
        # carries ``identity_cards`` (the Identity pillar was dead without it).
        self._agent_facts_registry = agent_facts_registry
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s
        self._mtimes: dict[str, float] = {}
        self._stopped = False
        self._published_compliance: set[str] = set()
        # I8: single-writer serialization. ``run_forever`` (background poll) and
        # ``drain_workflow`` (SSE finally) can both target the same workflow; a
        # per-workflow lock guarantees only one reader advances the byte offset
        # at a time so the trace tail is never read — and exported — twice.
        self._wf_locks: dict[str, threading.Lock] = {}
        self._wf_locks_guard = threading.Lock()

    # ── public API ──────────────────────────────────────────────────

    def set_agent_facts_registry(self, registry: Any) -> None:
        """Inject the AgentFacts registry after construction (E7).

        The composition root builds the relay (adapters factory) and the
        registry (components factory) independently and joins them later; this
        setter mirrors ``eval_telemetry.set_sink`` so the relay can forward the
        registry into ``export_for_compliance`` without the adapters factory
        importing the components/registry (avoids AP-2 coupling).
        """
        self._agent_facts_registry = registry

    def run_once(self) -> int:
        """Scan all workflow dirs, publish new events.  Returns count published."""
        exists = self._storage_dir.exists()
        if not exists:
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

    def drain_workflow(self, workflow_id: str) -> int:
        """Synchronously process all pending events for a specific workflow.

        Called from the SSE finally block to ensure relay events are in
        the SDK buffer before flush().
        """
        wf_dir = self._storage_dir / workflow_id
        trace_file = wf_dir / "trace.jsonl"
        if not wf_dir.is_dir() or not trace_file.exists():
            return 0
        return self._process_workflow(wf_dir, trace_file)

    # ── internals ───────────────────────────────────────────────────

    def _workflow_lock(self, wf_id: str) -> threading.Lock:
        """Return the (lazily created) per-workflow single-writer lock."""
        with self._wf_locks_guard:
            lock = self._wf_locks.get(wf_id)
            if lock is None:
                lock = threading.Lock()
                self._wf_locks[wf_id] = lock
            return lock

    @staticmethod
    def _write_offset_atomic(offset_file: Path, value: int) -> None:
        """Persist the byte offset atomically (write temp + ``os.replace``).

        A partial/torn offset write would let the relay re-read (and re-export)
        the trace tail on the next poll. ``os.replace`` is atomic on POSIX, so a
        reader either sees the old offset or the new one, never a truncated one.
        """
        tmp = offset_file.with_name(offset_file.name + ".tmp")
        tmp.write_text(str(value))
        os.replace(tmp, offset_file)

    def _process_workflow(self, wf_dir: Path, trace_file: Path) -> int:
        wf_id = wf_dir.name

        # I8: serialize all readers of this workflow's outbox so a concurrent
        # poll + drain cannot both consume the same offset window.
        with self._workflow_lock(wf_id):
            file_stat = trace_file.stat()
            current_mtime = file_stat.st_mtime
            file_size = file_stat.st_size

            offset_file = wf_dir / ".langfuse_offset"
            if not offset_file.exists():
                self._write_offset_atomic(offset_file, 0)

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

            # Advance the offset BEFORE releasing the lock so the next reader
            # starts past the bytes we just consumed.
            self._write_offset_atomic(offset_file, offset + bytes_consumed)
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
                    attrs["__output"] = redact_details(event.details)

                if "parent_observation_id" in kwargs:
                    attrs["__bb_parent_observation_id"] = kwargs["parent_observation_id"]
                if "model" in kwargs:
                    attrs["__bb_model"] = kwargs["model"]
                if "usage" in kwargs:
                    attrs["__bb_usage"] = kwargs["usage"]
                if "cost" in kwargs:
                    attrs["__bb_cost"] = kwargs["cost"]

                exported = self._exporter.export_event(
                    name=kwargs["name"],
                    trace_id=kwargs["trace_id"],
                    attributes=attrs,
                )

                # ``export_event`` swallows SDK errors per rule O1 and signals a
                # genuine (non-no-op) failure by returning ``False``. Treat that
                # as a poison line so it is dead-lettered instead of being
                # silently counted as published (the bug class that previously
                # dropped every BlackBox observation). ``None`` is treated as
                # success for backward compatibility with older exporters.
                if exported is False:
                    self._write_dlq(
                        wf_dir, line, "exporter swallowed export failure"
                    )
                    return False

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
            phase_logger = PhaseLogger(storage_dir=self._storage_dir.parent / "phase_logs")
            bundle = recorder.export_for_compliance(
                workflow_id,
                agent_facts_registry=self._agent_facts_registry,
                phase_logger=phase_logger,
            )
        except Exception as exc:
            logger.warning(
                "Failed to export compliance bundle for %s: %s", workflow_id, exc
            )
            return

        chain_valid = bundle.get("hash_chain_valid", False)
        outcome = task_details.get("outcome", "")

        # E1/E9: publish the terminal verdict as trace-level scores. Best-effort
        # and independent of the bundle publish (O1).
        self._publish_outcome_scores(workflow_id, task_details)

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
                input_data=redact_compliance_bundle(bundle),
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
                    input_data=redact_compliance_bundle(bundle),
                    item_id=f"{workflow_id}-incident",
                    metadata={"workflow_id": workflow_id, "reason": "task_failure"},
                )
            except Exception as exc:
                logger.warning(
                    "Failed to publish incident dataset item for %s: %s",
                    workflow_id, exc,
                )

    def _publish_outcome_scores(
        self, workflow_id: str, task_details: dict[str, Any]
    ) -> None:
        """Publish goal_met / criteria_met / task_completion_score as trace scores.

        Fields absent or ``None`` in the terminal details are skipped (a rejected
        or budget-exceeded terminal shape need not carry every field — we never
        fabricate a score). ``goal_met`` (bool) maps to 0.0/1.0. Per-field and
        overall failures are swallowed (O1) so scoring never blocks the run or
        the bundle publish.
        """
        if self._compliance_publisher is None:
            return
        for field in self._OUTCOME_SCORE_FIELDS:
            value = task_details.get(field)
            if value is None:
                continue
            try:
                numeric = 1.0 if value is True else 0.0 if value is False else float(value)
            except (TypeError, ValueError):
                continue
            try:
                self._compliance_publisher.score_trace(
                    trace_id=workflow_id,
                    name=field,
                    value=numeric,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to publish outcome score %s for %s: %s",
                    field, workflow_id, exc,
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
