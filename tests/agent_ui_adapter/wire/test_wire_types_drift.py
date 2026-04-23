"""US-8.2 / US-8.3 — committed wire-types.ts MUST match openapi-typescript.

Pairs with ``test_openapi_drift.py``: this test re-runs the Node codegen
(``npx openapi-typescript``) against the committed ``openapi.yaml`` and
asserts the output is byte-identical to the committed
``frontend/lib/wire-types.ts``.

Skipped if Node / npx is not available so the broader CI suite still
runs in lean Python-only environments. The dedicated codegen CI job
(``.github/workflows/wire-codegen.yml``) installs Node and runs this
test as a non-skipped check.

Failure paths first per AGENTS.md TAP-4:
- Missing artifact -> AssertionError with regen hint
- Missing Node -> pytest.skip (explicit, not a hidden xfail)
- Codegen subprocess failure -> AssertionError with stderr surfaced
- Drift -> AssertionError with first 40 lines of unified diff
"""

from __future__ import annotations

import difflib
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_OPENAPI = REPO_ROOT / "openapi.yaml"
COMMITTED_WIRE_TYPES = REPO_ROOT / "frontend" / "lib" / "wire-types.ts"
FRONTEND_DIR = REPO_ROOT / "frontend"
NODE_MODULES_BIN = FRONTEND_DIR / "node_modules" / ".bin" / "openapi-typescript"
REGEN_HINT = (
    "Run scripts/regenerate_wire_artifacts.sh (or "
    "`cd frontend && npm install && npm run regen:wire-types`) "
    "and commit the result."
)


def _node_available() -> bool:
    return shutil.which("npx") is not None or NODE_MODULES_BIN.exists()


def test_committed_wire_types_exists() -> None:
    assert COMMITTED_WIRE_TYPES.exists(), (
        f"frontend/lib/wire-types.ts not committed at {COMMITTED_WIRE_TYPES}. "
        + REGEN_HINT
    )


def test_committed_wire_types_has_expected_shape() -> None:
    """Pure-text smoke: surface symbols downstream code depends on exist."""
    content = COMMITTED_WIRE_TYPES.read_text()
    assert "export interface paths" in content
    assert "export interface components" in content
    assert "export interface operations" in content


def test_committed_wire_types_matches_openapi_typescript_codegen(
    tmp_path: Path,
) -> None:
    """The drift gate: regen MUST produce byte-equal output."""
    if not COMMITTED_OPENAPI.exists():
        pytest.fail(
            "openapi.yaml is missing; cannot regenerate wire-types.ts. "
            + REGEN_HINT
        )
    if not _node_available():
        pytest.skip(
            "openapi-typescript codegen requires Node/npx. The wire-codegen "
            "CI job installs Node and runs this test without the skip."
        )
    if not NODE_MODULES_BIN.exists():
        pytest.skip(
            "frontend/node_modules not installed; "
            "run `cd frontend && npm install` to enable this drift check."
        )

    regenerated = tmp_path / "wire-types.ts"
    proc = subprocess.run(
        [str(NODE_MODULES_BIN), str(COMMITTED_OPENAPI), "-o", str(regenerated)],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "openapi-typescript codegen failed:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    actual = COMMITTED_WIRE_TYPES.read_text()
    expected = regenerated.read_text()
    if actual == expected:
        return
    diff = "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile="frontend/lib/wire-types.ts (committed)",
            tofile="frontend/lib/wire-types.ts (regenerated)",
            n=2,
        )
    )
    diff_preview = "".join(diff.splitlines(keepends=True)[:40])
    raise AssertionError(
        "Committed frontend/lib/wire-types.ts is out of sync with the "
        "openapi-typescript codegen.\n"
        f"{REGEN_HINT}\n\n--- diff (first 40 lines) ---\n{diff_preview}"
    )
