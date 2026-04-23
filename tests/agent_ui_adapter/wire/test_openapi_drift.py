"""US-8.1 / US-8.3 — committed openapi.yaml MUST match the live exporter.

The repo carries a committed ``openapi.yaml`` at the repo root as the
single source of truth for downstream codegen (frontend wire types in
``frontend/lib/wire-types.ts``). This test fails if the exporter's
output drifts from the committed artifact, forcing the developer to
regenerate via ``scripts/regenerate_wire_artifacts.sh`` before merge.

Pure Python / no Node required, so it runs on every CI matrix entry,
including environments where the frontend toolchain is not installed.

Failure paths first per AGENTS.md TAP-4:
- Missing artifact -> AssertionError pointing at the regen command
- Drift -> AssertionError with the first 40 lines of unified diff
"""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml

from agent_ui_adapter.wire.export_openapi import _build_spec


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_OPENAPI = REPO_ROOT / "openapi.yaml"
REGEN_HINT = (
    "Run scripts/regenerate_wire_artifacts.sh (or "
    "`python -W ignore -m agent_ui_adapter.wire.export_openapi > openapi.yaml`) "
    "and commit the result."
)


def _expected_yaml() -> str:
    """Re-derive the YAML the exporter would emit, deterministically."""
    return yaml.safe_dump(_build_spec(), sort_keys=True, default_flow_style=False)


def test_committed_openapi_yaml_exists() -> None:
    assert COMMITTED_OPENAPI.exists(), (
        f"openapi.yaml not committed at repo root ({COMMITTED_OPENAPI}). "
        + REGEN_HINT
    )


def test_committed_openapi_yaml_parses() -> None:
    """Sanity: the committed file is valid YAML mapping with OpenAPI shape."""
    parsed = yaml.safe_load(COMMITTED_OPENAPI.read_text())
    assert isinstance(parsed, dict)
    assert parsed.get("openapi", "").startswith("3.1"), (
        "openapi.yaml is not OpenAPI 3.1. " + REGEN_HINT
    )
    assert "paths" in parsed and "components" in parsed


def test_committed_openapi_yaml_matches_live_exporter() -> None:
    """The drift gate: any change to wire/* MUST be reflected in openapi.yaml."""
    actual = COMMITTED_OPENAPI.read_text()
    expected = _expected_yaml()
    if actual == expected:
        return
    diff = "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile="openapi.yaml (committed)",
            tofile="openapi.yaml (regenerated)",
            n=2,
        )
    )
    diff_preview = "".join(diff.splitlines(keepends=True)[:40])
    raise AssertionError(
        "Committed openapi.yaml is out of sync with the live exporter.\n"
        f"{REGEN_HINT}\n\n--- diff (first 40 lines) ---\n{diff_preview}"
    )
