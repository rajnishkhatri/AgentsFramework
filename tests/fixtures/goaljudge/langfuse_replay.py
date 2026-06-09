"""Langfuse verdict-replay loader — the §8.3 confirmation-gate swap seam.

The offline shadow harness (`test_goal_judge_shadow_offline.py`) replays a
**recorded** (canned) verdict per anchor today. That pins wiring + registry
alignment but is *not* the behavioral gate. This module is the documented swap
point described in the spec §10.2 / plan §8.3:

    > swap each ``ShadowTrace.recorded_verdict`` for the Langfuse-replayed
    > verdict and the same assertions become the real §10.2 behavioral gate.

It loads judge verdicts that were produced by a **real** model run (exported
from Langfuse after the G3 batch re-run), keyed by ``trace_id``, and resolves
them to the registry IDs the shadow table uses. The verdict JSON it returns is
the exact shape ``GoalJudge._parse_verdict`` already consumes — so flipping the
harness from "recorded" to "replayed" needs **no test changes**, only a source
that points at the export.

Determinism boundary (AGENTS.md H1). This module runs **no model**. It reads a
JSON file that a human/operator produced out-of-band (see the G3 batch runbook)
and is wired so that, absent that file, the harness keeps using the recorded
verdicts and stays green. The real export is git-ignored; a tiny committed
sample (`langfuse_replay_sample.json`) exercises the load path in CI.

Export file shape (either form is accepted)::

    # Form A — explicit verdict per trace
    [{"trace_id": "cbfe845...", "verdict": {"goal_met": false, ...}}, ...]

    # Form B — EvalRecord-shaped (services/eval_capture.py), target=goal_judge
    [{"trace_id": "cbfe845...", "target": "goal_judge",
      "ai_response": {"goal_met": false, ...}}, ...]

``ai_response`` may be a dict or a JSON string (some sinks stringify it); both
are handled.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ── trace_id → registry_id (spec §"Trace ID reference (§8 anchors)") ──────────
# The registry (`case_registry.py`) carries NO trace_id, so the join lives here.
# Source of truth: goaljudge_stage4_a2_rubric_spec.md, kept verbatim. If the
# spec table changes, update this map (and only this map).
TRACE_ID_TO_REGISTRY_ID: dict[str, str] = {
    "4298808fa78b5be8aec7c6b8066df70f": "GJ-001B",
    "face2f6f6fef5ef29af8bfbcd3ff9dde": "GJ-003B",
    "cbfe84539b675824a1eb08b331204b8d": "GJ-008",
    "f9008daa07745de8be9ab18d0ff8fa24": "GJ-010",
    "13bd732b9c14568586a6bdc1b52e3397": "GJ-011",
    "69b7a49520a35d3ca23ece4563036be0": "GJ-012",
    "0e86b4c80e635630bda692828fda9d8e": "GJ-013",
    "33f0ae39a23b5ef8962e9a4034ec8ea9": "GJ-019",
}

# Env var pointing at the real (git-ignored) export. When unset, the harness
# keeps replaying recorded verdicts. When set, the shadow run becomes behavioral.
EXPORT_ENV_VAR = "GOALJUDGE_LANGFUSE_EXPORT"

# Committed sample (load-path smoke only — NOT a real model run).
SAMPLE_EXPORT_PATH = Path(__file__).with_name("langfuse_replay_sample.json")

_VERDICT_KEYS = {"goal_met", "criteria_met", "partial_fraction", "rationale"}


class ReplayExportError(RuntimeError):
    """Raised when an export is malformed, empty, or missing a needed anchor."""


def _coerce_verdict(raw: Any, *, trace_id: str) -> dict[str, Any]:
    """Pull a verdict dict out of one export row (Form A or Form B)."""
    if not isinstance(raw, dict):
        raise ReplayExportError(f"{trace_id}: export row is not an object")

    # Form A: explicit verdict payload.
    if "verdict" in raw:
        verdict = raw["verdict"]
    # Form B: EvalRecord-shaped — verdict lives in ai_response.
    elif "ai_response" in raw:
        verdict = raw["ai_response"]
    else:
        # Bare row that *is* the verdict (no envelope).
        verdict = raw

    if isinstance(verdict, str):  # some sinks stringify ai_response
        verdict = json.loads(verdict)
    if not isinstance(verdict, dict):
        raise ReplayExportError(f"{trace_id}: resolved verdict is not an object")
    if not _VERDICT_KEYS & verdict.keys():
        raise ReplayExportError(
            f"{trace_id}: object has none of {sorted(_VERDICT_KEYS)} — not a verdict"
        )
    return verdict


def load_replayed_verdicts(path: str | os.PathLike[str]) -> dict[str, dict[str, Any]]:
    """Read an export file and return ``registry_id -> verdict dict``.

    Rows whose ``trace_id`` is not a known anchor (see
    :data:`TRACE_ID_TO_REGISTRY_ID`) are ignored — an export may legitimately
    carry the full batch. Raises :class:`ReplayExportError` on a malformed file
    or a row missing its ``trace_id``.
    """
    p = Path(path)
    rows = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ReplayExportError(f"{p}: top level must be a JSON array")

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or "trace_id" not in row:
            raise ReplayExportError(f"{p}: every row needs a trace_id")
        trace_id = str(row["trace_id"])
        registry_id = TRACE_ID_TO_REGISTRY_ID.get(trace_id)
        if registry_id is None:
            continue  # not an anchor — fine, skip it
        out[registry_id] = _coerce_verdict(row, trace_id=trace_id)
    return out


def replay_source(path: str | os.PathLike[str] | None = None) -> dict[str, str]:
    """Return ``registry_id -> verdict_json`` for the harness to replay.

    Resolution order:
      1. explicit ``path`` argument, else
      2. the :data:`EXPORT_ENV_VAR` env var.

    Returns ``{}`` when neither is set — the caller then falls back to the
    recorded verdicts, so the offline harness stays green with no export. The
    JSON strings returned are byte-for-byte what ``GoalJudge._parse_verdict``
    consumes, so the harness swap is invisible to its assertions.
    """
    resolved = path or os.environ.get(EXPORT_ENV_VAR)
    if not resolved:
        return {}
    verdicts = load_replayed_verdicts(resolved)
    return {rid: json.dumps(v) for rid, v in verdicts.items()}
