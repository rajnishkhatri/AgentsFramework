"""Entry point: python -m explainability_app [--check]."""

from __future__ import annotations

import argparse
import json
import logging.config
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
LOGGING_CONFIG = AGENT_ROOT / "logging.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Explainability Dashboard API")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and exit without starting the server.",
    )
    args = parser.parse_args()

    if LOGGING_CONFIG.exists():
        with open(LOGGING_CONFIG) as f:
            logging.config.dictConfig(json.load(f))

    from explainability_app.server import DEFAULT_HOST, DEFAULT_PORT, build_app

    app = build_app()

    if args.check:
        print(f"Config OK. Would bind to {DEFAULT_HOST}:{DEFAULT_PORT}")
        sys.exit(0)

    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
