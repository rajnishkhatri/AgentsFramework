"""Out-of-process CLI driver for the BlackBox→Langfuse relay.

Sprint D of the BlackBox→Langfuse plan.

Usage::

    # From the repo root (loads .env automatically)
    python -m middleware.sidecars

    # Custom poll interval
    RELAY_POLL_INTERVAL_S=2.0 python -m middleware.sidecars

This entrypoint reuses ``build_adapters()`` from ``middleware/composition.py``
for all wiring (Langfuse keys, storage dir, relay instance), then calls
``relay.run_forever()`` in a blocking asyncio loop.

Designed for production deployment as a Cloud Run sidecar container where
the relay runs independently of the main agent process.

Layering invariants (enforced by tests/architecture/test_middleware_layer.py):
  - Zero ``langfuse`` or ``langgraph`` imports.
  - Zero imports from ``components/``, ``orchestration/``, ``governance/``, ``meta/``.
  - Uses ``build_adapters()`` for wiring, never instantiates adapters directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(AGENT_ROOT / ".env")
sys.path.insert(0, str(AGENT_ROOT))

from middleware.composition import build_adapters  # noqa: E402

logger = logging.getLogger("middleware.sidecars.__main__")


def main() -> None:
    """Build the relay via composition and run it forever."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    env = dict(os.environ)
    env.setdefault("BLACKBOX_RELAY_MODE", "in_process")

    adapters = build_adapters(env=env)
    relay = adapters.black_box_relay

    if relay is None:
        logger.error(
            "No relay configured (BLACKBOX_RELAY_MODE=%s). "
            "Set BLACKBOX_RELAY_MODE=in_process to enable the relay.",
            env.get("BLACKBOX_RELAY_MODE", ""),
        )
        sys.exit(1)

    interval = float(os.environ.get("RELAY_POLL_INTERVAL_S", "1.0"))
    logger.info(
        "Starting BlackBox→Langfuse relay (poll_interval=%.1fs, storage=%s)",
        interval,
        relay._storage_dir,
    )

    loop = asyncio.new_event_loop()

    def _shutdown(signum: int, frame: object) -> None:
        logger.info("Received signal %d, stopping relay...", signum)
        relay.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(relay.run_forever(interval_s=interval))
    finally:
        loop.close()
        logger.info("Relay stopped.")


if __name__ == "__main__":
    main()
