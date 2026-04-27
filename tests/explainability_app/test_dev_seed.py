"""Tests for dev_seed -- failure-paths-first.

Verifies the seeder produces valid hash chains and deterministic output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from explainability_app.dev_seed import generate_workflows
from services.governance.black_box import BlackBoxRecorder


def test_dev_seed_tampered_chain_detected(tmp_path: Path) -> None:
    """Fail-first: a tampered event breaks hash chain verification."""
    cache_dir = tmp_path / "cache"
    wf_ids = generate_workflows(cache_dir, count=1, seed=99)
    wf_id = wf_ids[0]

    trace_file = cache_dir / "black_box_recordings" / wf_id / "trace.jsonl"
    lines = trace_file.read_text().strip().split("\n")
    assert len(lines) >= 2

    tampered = json.loads(lines[1])
    tampered["details"]["TAMPERED"] = True
    lines[1] = json.dumps(tampered)
    trace_file.write_text("\n".join(lines) + "\n")

    recorder = BlackBoxRecorder(cache_dir / "black_box_recordings")
    export = recorder.export(wf_id)
    assert export["hash_chain_valid"] is False


def test_dev_seed_produces_valid_chain(tmp_path: Path) -> None:
    """Acceptance: untampered seed data has a valid hash chain."""
    cache_dir = tmp_path / "cache"
    wf_ids = generate_workflows(cache_dir, count=2, seed=42)

    recorder = BlackBoxRecorder(cache_dir / "black_box_recordings")
    for wf_id in wf_ids:
        export = recorder.export(wf_id)
        assert export["hash_chain_valid"] is True, f"Chain invalid for {wf_id}"
        assert export["event_count"] >= 3


def test_dev_seed_is_deterministic(tmp_path: Path) -> None:
    """AC4: same seed produces identical workflow IDs."""
    cache1 = tmp_path / "run1"
    cache2 = tmp_path / "run2"
    ids1 = generate_workflows(cache1, count=3, seed=42)
    ids2 = generate_workflows(cache2, count=3, seed=42)
    assert ids1 == ids2


def test_dev_seed_produces_phase_decisions(tmp_path: Path) -> None:
    """AC2: each workflow has at least one routing and one evaluation decision."""
    cache_dir = tmp_path / "cache"
    wf_ids = generate_workflows(cache_dir, count=3, seed=42)

    for wf_id in wf_ids:
        decisions_file = cache_dir / "phase_logs" / wf_id / "decisions.jsonl"
        assert decisions_file.exists(), f"No decisions for {wf_id}"
        decisions = [
            json.loads(line)
            for line in decisions_file.read_text().strip().split("\n")
            if line.strip()
        ]
        phases = {d["phase"] for d in decisions}
        assert "routing" in phases, f"No routing decision for {wf_id}"
        assert "evaluation" in phases, f"No evaluation decision for {wf_id}"


def test_dev_seed_idempotent(tmp_path: Path) -> None:
    """AC5: re-running creates new workflow IDs, never overwrites."""
    cache_dir = tmp_path / "cache"
    ids1 = generate_workflows(cache_dir, count=2, seed=42)
    ids2 = generate_workflows(cache_dir, count=2, seed=99)
    assert set(ids1).isdisjoint(set(ids2))

    recordings_dir = cache_dir / "black_box_recordings"
    all_dirs = [d.name for d in recordings_dir.iterdir() if d.is_dir()]
    assert len(all_dirs) == 4
