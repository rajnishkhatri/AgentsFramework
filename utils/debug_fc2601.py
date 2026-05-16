"""Temporary NDJSON helper for Cursor debug session fc2601 (remove after verified)."""

from __future__ import annotations

import json
import time
from typing import Any

DEBUG_LOG_PATH = (
    "/Users/rajnishkhatri/Documents/AgentsFramework/agent/.cursor/debug-fc2601.log"
)
SESSION_ID = "fc2601"


def debug_fc2601(
    *,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any],
) -> None:
    # region agent log
    try:
        line = json.dumps(
            {
                "sessionId": SESSION_ID,
                "timestamp": int(time.time() * 1000),
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
            },
            separators=(",", ":"),
            default=str,
        )
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    # endregion agent log

