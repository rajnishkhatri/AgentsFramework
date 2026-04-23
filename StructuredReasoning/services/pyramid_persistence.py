"""Persist pyramid ``analysis_output`` JSON to the workflow cache.

PR 1 walking-skeleton scope: write a single ``analysis.json`` per
workflow under ``<cache_dir>/pyramid/<workflow_id>/``. PR 3 will extend
this with ``analysis_iter<N>.json`` files plus a ``final.json`` symlink.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("StructuredReasoning.services.pyramid_persistence")


def write_analysis(
    *,
    cache_dir: Path | str,
    workflow_id: str,
    analysis_dict: dict[str, Any],
    filename: str = "analysis.json",
) -> Path:
    """Write ``analysis_dict`` to ``<cache_dir>/pyramid/<workflow_id>/<filename>``.

    Returns the absolute path of the written file. Creates parent
    directories as needed. Overwrites an existing file at the same path
    -- callers that want per-iteration history pass distinct
    ``filename`` values (e.g. ``analysis_iter2.json``).
    """
    cache_dir = Path(cache_dir)
    out_dir = cache_dir / "pyramid" / workflow_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    out_path.write_text(json.dumps(analysis_dict, indent=2, sort_keys=True))
    logger.info(
        "Pyramid analysis written to %s (%d bytes)",
        out_path,
        out_path.stat().st_size,
    )
    return out_path
