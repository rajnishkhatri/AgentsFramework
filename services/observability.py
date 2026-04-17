"""Per-concern structured logging setup (H4 pattern).

Loads logging.json via logging.config.dictConfig.
Exposes helpers for fetching per-concern loggers.
Also provides FrameworkTelemetry for LangGraph feasibility tracking (STORY-412).
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("services.observability")

_LOGGING_CONFIG_PATH = Path(__file__).resolve().parent.parent / "logging.json"


def setup_logging(config_path: str | Path | None = None) -> None:
    """Load per-concern logging config from JSON file."""
    path = Path(config_path) if config_path else _LOGGING_CONFIG_PATH
    if path.exists():
        with open(path) as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=logging.INFO)


def get_logger(concern: str) -> logging.Logger:
    """Get a logger for the given concern (e.g., 'services.prompt_service')."""
    return logging.getLogger(concern)


class FrameworkTelemetry(BaseModel):
    """LangGraph usage counters for the feasibility gate (STORY-412)."""

    checkpoint_invocations: int = 0
    rollback_invocations: int = 0
    rollback_time_saved_ms: float = 0.0
    auto_trace_insights: int = 0
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def increment_checkpoint(self) -> None:
        self.checkpoint_invocations += 1

    def increment_rollback(self, time_saved_ms: float = 0.0) -> None:
        self.rollback_invocations += 1
        self.rollback_time_saved_ms += time_saved_ms


def save_telemetry(
    telemetry: FrameworkTelemetry,
    output_dir: Path | str = Path("logs"),
) -> None:
    """Persist telemetry to logs/framework_telemetry.jsonl."""
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / "framework_telemetry.jsonl"
        with open(filepath, "a") as f:
            f.write(telemetry.model_dump_json() + "\n")
    except Exception as exc:
        logger.warning("Failed to write telemetry: %s", exc)


class InstrumentedCheckpointer:
    """Wrap a LangGraph checkpointer so it updates :class:`FrameworkTelemetry`.

    Each ``put`` / ``aput`` increments ``checkpoint_invocations``; each
    ``get`` / ``aget`` that returns a non-None state increments
    ``rollback_invocations`` (LangGraph's interrupt/resume path triggers a
    ``get`` to rebuild state, which is the closest signal to a "rollback"
    that the public API exposes).

    All other attribute access falls through to the wrapped instance, so
    methods like ``list``, ``get_tuple``, and ``setup`` keep working
    transparently.

    Notes:
        * ``put_writes`` / ``aput_writes`` (intermediate channel writes)
          are intentionally NOT counted -- STORY-412 maps a "checkpoint"
          to a full ``put`` call.
        * The wrapper is intentionally framework-agnostic: it never
          imports anything from ``langgraph``.
    """

    def __init__(self, inner: Any, telemetry: FrameworkTelemetry) -> None:
        self._inner = inner
        self._telemetry = telemetry

    def put(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner.put(*args, **kwargs)
        self._telemetry.increment_checkpoint()
        return result

    async def aput(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.aput(*args, **kwargs)
        self._telemetry.increment_checkpoint()
        return result

    def get(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner.get(*args, **kwargs)
        if result is not None:
            self._telemetry.increment_rollback()
        return result

    async def aget(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._inner.aget(*args, **kwargs)
        if result is not None:
            self._telemetry.increment_rollback()
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def load_telemetry(
    input_dir: Path | str = Path("logs"),
) -> FrameworkTelemetry:
    """Load the most recent telemetry record, or return defaults."""
    filepath = Path(input_dir) / "framework_telemetry.jsonl"
    if not filepath.exists():
        return FrameworkTelemetry()
    try:
        lines = filepath.read_text().strip().split("\n")
        if lines and lines[-1].strip():
            return FrameworkTelemetry.model_validate_json(lines[-1])
    except Exception as exc:
        logger.warning("Failed to load telemetry: %s", exc)
    return FrameworkTelemetry()
