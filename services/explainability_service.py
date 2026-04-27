"""ExplainabilityService: read-only aggregator over governance artifacts.

Scans cache/black_box_recordings/, cache/phase_logs/, cache/agent_facts/,
and logs/*.log to provide structured views for the explainability dashboard.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("services.explainability")


class WorkflowSummary(BaseModel):
    workflow_id: str
    started_at: datetime | None = None
    event_count: int = 0
    status: str = "unknown"
    primary_agent_id: str | None = None


class ExplainabilityService:
    def __init__(self, recordings_dir: Path | str, phase_logs_dir: Path | str | None = None) -> None:
        self._recordings_dir = Path(recordings_dir)
        self._phase_logs_dir = Path(phase_logs_dir) if phase_logs_dir else None

    def list_workflows(self, since: datetime | None = None) -> list[WorkflowSummary]:
        if not self._recordings_dir.exists():
            return []

        summaries: list[WorkflowSummary] = []
        for wf_dir in self._recordings_dir.iterdir():
            if not wf_dir.is_dir():
                continue
            trace_file = wf_dir / "trace.jsonl"
            if not trace_file.exists():
                continue
            summary = self._parse_workflow(wf_dir.name, trace_file)
            if summary is None:
                continue
            if since is not None and summary.started_at is not None:
                if summary.started_at < since:
                    continue
            summaries.append(summary)

        summaries.sort(
            key=lambda s: s.started_at or datetime.min,
            reverse=True,
        )
        return summaries

    def _parse_workflow(self, workflow_id: str, trace_file: Path) -> WorkflowSummary | None:
        events: list[dict] = []
        for line in trace_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping corrupted line in %s/%s",
                    workflow_id,
                    trace_file.name,
                )
                continue

        if not events:
            return None

        started_at: datetime | None = None
        status = "in_progress"
        primary_agent_id: str | None = None

        for event in events:
            event_type = event.get("event_type", "")
            if event_type == "task_started" and started_at is None:
                ts_str = event.get("timestamp")
                if ts_str:
                    try:
                        started_at = datetime.fromisoformat(ts_str)
                    except ValueError:
                        pass
            if event_type == "task_completed":
                status = "completed"
            if event_type == "error_occurred":
                status = "error"

            details = event.get("details", {})
            if details.get("agent_id") and primary_agent_id is None:
                primary_agent_id = details["agent_id"]

        return WorkflowSummary(
            workflow_id=workflow_id,
            started_at=started_at,
            event_count=len(events),
            status=status,
            primary_agent_id=primary_agent_id,
        )
