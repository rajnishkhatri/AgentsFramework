"""Seed importer promotion path (Phase 6 — ADR-0013 clause 1, FR-25).

The ``convert:test01`` demotion realized on the Python side: a seed enters the
governed bank at ``reviewed=false`` and is promoted ONLY by the FR-23 cascade
(re-verification, incl. the independent-solver key gate). The converter's
self-stamped ``reviewed:true`` is retroactively unearned — ``demote_seed_row``
strips it on entry, so the cascade is the sole reviewer for imported items just
as for generated ones (one cascade, both families). On promotion the cascade
re-stamps ``generated_by="<model>@<run_id>"``, so ``"test01-import"`` never
appears on a ``reviewed=true`` row (ADR-0015 clause 6).

Pure apart from the injected solver + the seed read; no live LLM here.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from components.test_item_generation import (
    Solver,
    TestItemCascadeVerdict,
    run_test_item_cascade,
)

__all__ = ["demote_seed_row", "promote_seed"]


def demote_seed_row(row: dict[str, Any]) -> dict[str, Any]:
    """Neutralize a seed row's self-asserted review gate (FR-25.1): drop it to
    ``reviewed=false`` on entry. Content (stem/choices/declared key) survives —
    the cascade re-verifies it. ``generated_by`` is left as the import marker;
    a passing cascade re-stamps it (the promoted row never keeps it)."""
    demoted = dict(row)
    demoted["reviewed"] = False
    demoted.setdefault("generated_by", "test01-import")
    return demoted


async def promote_seed(
    seed_path: Path,
    *,
    solver: Solver,
    existing_stems: Sequence[str],
    generated_by: str,
) -> TestItemCascadeVerdict:
    """Read a neutral seed, demote every row, and run the SAME FR-23 cascade to
    promote. Returns the cascade verdict: ``passed`` rows are the promoted
    (re-stamped, ``reviewed=true``) bank rows; ``quarantined`` rows failed
    re-verification (import lineage lives in the eval_capture stream, not a
    persisted column — ADR-0015 clause 6)."""
    seed_rows = [demote_seed_row(r) for r in json.loads(seed_path.read_text())]
    # The cascade takes a generator reply string; wrap the demoted rows in the
    # same ``{"items": [...]}`` envelope so one cascade serves both families.
    reply = json.dumps({"items": seed_rows})
    return await run_test_item_cascade(
        reply,
        subject="act-english",
        solver=solver,
        existing_stems=existing_stems,
        generated_by=generated_by,
    )
