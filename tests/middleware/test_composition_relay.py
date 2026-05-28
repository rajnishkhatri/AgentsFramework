"""L2 Contract: Sprint D — Composition + relay mode wiring.

Tests follow Protocol B (Contract-Driven TDD) from
research/tdd_agentic_systems_prompt.md.

Layer: middleware (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

Test categories:
  A. FAILURE PATHS FIRST — invalid relay mode rejects, missing storage dir
  B. RELAY MODE ENV HANDLING — in_process / off / external
  C. COMPOSITION INTEGRATION — black_box_relay wired into MiddlewareAdapters
  D. LIFESPAN LIFECYCLE — relay started as asyncio task, cancelled on exit
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import AsyncMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


class FakeExporter:
    """In-memory TelemetryExporter for testing relay wiring."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.events.append({"name": name, "trace_id": trace_id, "attributes": dict(attributes or {})})

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


_MINIMAL_ENV = {
    "WORKOS_CLIENT_ID": "client_test123",
    "WORKOS_API_KEY": "sk_test_key",
    "MEM0_API_KEY": "m0-test-key",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
    "LANGFUSE_SECRET_KEY": "sk-lf-test",
}


# ─────────────────────────────────────────────────────────────────────
# A. FAILURE PATHS FIRST — invalid relay mode, missing config
# ─────────────────────────────────────────────────────────────────────


class TestRelayModeFailures:
    """Invalid BLACKBOX_RELAY_MODE values should not crash build_adapters;
    the relay should degrade to None/off."""

    def test_unknown_relay_mode_defaults_to_off(self, tmp_path: Path) -> None:
        """An unrecognized mode value treats the relay as off."""
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "banana"}
        adapters = build_adapters(env=env)
        assert adapters.black_box_relay is None

    def test_relay_off_mode_produces_none(self, tmp_path: Path) -> None:
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "off"}
        adapters = build_adapters(env=env)
        assert adapters.black_box_relay is None

    def test_relay_external_mode_produces_none(self) -> None:
        """external mode = out-of-process sidecar handles it; no relay."""
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "external"}
        adapters = build_adapters(env=env)
        assert adapters.black_box_relay is None


# ─────────────────────────────────────────────────────────────────────
# B. RELAY MODE ENV HANDLING — in_process / off / external
# ─────────────────────────────────────────────────────────────────────


class TestRelayModeEnv:
    """BLACKBOX_RELAY_MODE governs whether the relay is wired."""

    def test_default_mode_is_in_process(self) -> None:
        """Absent BLACKBOX_RELAY_MODE defaults to in_process."""
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV}
        adapters = build_adapters(env=env)
        assert adapters.black_box_relay is not None

    def test_explicit_in_process_creates_relay(self) -> None:
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "in_process"}
        adapters = build_adapters(env=env)
        assert adapters.black_box_relay is not None

    def test_relay_uses_configured_storage_dir(self, tmp_path: Path) -> None:
        from middleware.composition import build_adapters

        storage = tmp_path / "bb_recordings"
        storage.mkdir()
        env = {
            **_MINIMAL_ENV,
            "BLACKBOX_RELAY_MODE": "in_process",
            "BLACKBOX_STORAGE_DIR": str(storage),
        }
        adapters = build_adapters(env=env)
        relay = adapters.black_box_relay
        assert relay is not None
        assert relay._storage_dir == storage


# ─────────────────────────────────────────────────────────────────────
# C. COMPOSITION INTEGRATION — relay instance on MiddlewareAdapters
# ─────────────────────────────────────────────────────────────────────


class TestCompositionIntegration:
    """The relay is exposed as a typed field on MiddlewareAdapters."""

    def test_middleware_adapters_has_relay_field(self) -> None:
        from middleware.composition import MiddlewareAdapters

        # Verify field exists in the dataclass
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(MiddlewareAdapters)}
        assert "black_box_relay" in field_names

    def test_relay_is_black_box_to_telemetry_relay_instance(self) -> None:
        from middleware.composition import build_adapters
        from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "in_process"}
        adapters = build_adapters(env=env)
        assert isinstance(adapters.black_box_relay, BlackBoxToTelemetryRelay)

    def test_relay_exporter_is_same_as_adapters_telemetry_exporter(self) -> None:
        """The relay should use the same exporter the rest of the app uses."""
        from middleware.composition import build_adapters

        env = {**_MINIMAL_ENV, "BLACKBOX_RELAY_MODE": "in_process"}
        adapters = build_adapters(env=env)
        relay = adapters.black_box_relay
        assert relay is not None
        assert relay._exporter is adapters.telemetry_exporter


# ─────────────────────────────────────────────────────────────────────
# D. LIFESPAN LIFECYCLE — relay started/stopped via asyncio.create_task
# ─────────────────────────────────────────────────────────────────────


class TestLifespanRelay:
    """The __main__.py lifespan starts/stops the relay as an asyncio task."""

    def test_relay_start_and_stop_in_lifespan(self, tmp_path: Path) -> None:
        """In-process relay is started during lifespan startup and
        stopped/cancelled on shutdown."""
        from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

        storage = tmp_path / "bb"
        storage.mkdir()
        exporter = FakeExporter()
        relay = BlackBoxToTelemetryRelay(
            storage_dir=storage, exporter=exporter, base_delay_s=0.0
        )

        async def _simulate_lifespan() -> bool:
            task = asyncio.create_task(relay.run_forever(interval_s=0.01))
            await asyncio.sleep(0.05)
            relay.stop()
            await task
            return task.done()

        done = asyncio.run(_simulate_lifespan())
        assert done is True

    def test_relay_task_is_cancelled_cleanly(self, tmp_path: Path) -> None:
        """Cancelling the relay task doesn't raise."""
        from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

        storage = tmp_path / "bb"
        storage.mkdir()
        exporter = FakeExporter()
        relay = BlackBoxToTelemetryRelay(
            storage_dir=storage, exporter=exporter, base_delay_s=0.0
        )

        async def _simulate_cancel() -> bool:
            task = asyncio.create_task(relay.run_forever(interval_s=0.01))
            await asyncio.sleep(0.03)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return task.cancelled()

        cancelled = asyncio.run(_simulate_cancel())
        assert cancelled is True
