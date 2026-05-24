"""tests/infra/gcp/conftest.py

Shared fixtures for the GCP Tier A OpenTofu test suite (Recipe 1+).

Strategy (validate-now-apply-later, parallel to tests/infra/conftest.py):

  * **No cloud credentials needed.** All assertions run against the parsed
    HCL tree (`python-hcl2`) plus `tofu validate` syntactic checks. Real
    `tofu plan -out` JSON is reserved for the apply-time CI job once the
    operator provides cloud credentials per docs/recipes/gcp/HUMAN_SETUP.md.

  * **Failure paths first** (TAP-4, AGENTS.md §Testing Anti-Patterns):
    rejection-style assertions precede acceptance-style in all test modules.

  * **Single parse per session.** `parsed_hcl` is session-scoped so the
    suite runs in <1s. The file walker is here; individual tests stay
    declarative.

  * **L2 contract style** — tests assert the *contract* each acceptance
    criterion puts on the resource, not the implementation detail of which
    exact fields exist in which file.

Key difference from tests/infra/conftest.py: INFRA_DIR points at
`infra/gcp/` instead of `infra/dev-tier/`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import hcl2
import pytest
from hcl2.utils import SerializationOptions


_HCL_LOAD_OPTIONS = SerializationOptions(
    with_comments=False,
    strip_string_quotes=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Marker registration
# ─────────────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "infra_gcp: marks tests as GCP Tier A OpenTofu/HCL infrastructure tests.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Path constants
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]
INFRA_DIR = REPO_ROOT / "infra" / "gcp"
POLICIES_DIR = INFRA_DIR / "policies"


# ─────────────────────────────────────────────────────────────────────────────
# Session fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def infra_dir() -> Path:
    assert INFRA_DIR.is_dir(), (
        f"Expected GCP infra dir at {INFRA_DIR}; Recipe 1 requires "
        "this directory to host all Tier A OpenTofu stacks."
    )
    return INFRA_DIR


@pytest.fixture(scope="session")
def tf_files(infra_dir: Path) -> list[Path]:
    """All .tf files directly under infra/gcp/ (excludes nested modules)."""
    return sorted(infra_dir.glob("*.tf"))


@pytest.fixture(scope="session")
def parsed_hcl(tf_files: list[Path]) -> dict[str, Any]:
    """Parse every .tf file once; return a merged dict keyed by HCL block type."""
    merged: dict[str, list[Any]] = {}
    for tf_path in tf_files:
        with tf_path.open("r", encoding="utf-8") as fh:
            tree = hcl2.load(fh, serialization_options=_HCL_LOAD_OPTIONS)
        for top_key, items in tree.items():
            if top_key.startswith("__"):
                continue
            merged.setdefault(top_key, []).extend(items)
    return merged


@pytest.fixture(scope="session")
def resources(parsed_hcl: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat list of {type, name, attrs} dicts, one per resource block."""
    flat: list[dict[str, Any]] = []
    for entry in parsed_hcl.get("resource", []):
        for resource_type, named in entry.items():
            for resource_name, attrs in named.items():
                flat.append({"type": resource_type, "name": resource_name, "attrs": attrs})
    return flat


@pytest.fixture(scope="session")
def variables(parsed_hcl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Mapping of variable name → its declaration dict."""
    out: dict[str, dict[str, Any]] = {}
    for entry in parsed_hcl.get("variable", []):
        for var_name, attrs in entry.items():
            out[var_name] = attrs
    return out


@pytest.fixture(scope="session")
def outputs(parsed_hcl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Mapping of output name → its declaration dict."""
    out: dict[str, dict[str, Any]] = {}
    for entry in parsed_hcl.get("output", []):
        for out_name, attrs in entry.items():
            out[out_name] = attrs
    return out


@pytest.fixture(scope="session")
def locals_block(parsed_hcl: dict[str, Any]) -> dict[str, Any]:
    """Merged locals from all .tf files."""
    merged: dict[str, Any] = {}
    for entry in parsed_hcl.get("locals", []):
        if isinstance(entry, dict):
            merged.update(entry)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Optional `tofu validate` fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def tofu_binary() -> str | None:
    return shutil.which("tofu")


@pytest.fixture(scope="session")
def tofu_validate_result(
    tofu_binary: str | None,
    infra_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    """Run `tofu init -backend=false` then `tofu validate -json` once per
    session against an isolated working copy of infra/gcp/.

    Skips if `tofu` is not installed; the HUMAN_SETUP.md §prereqs installs it.
    """
    if tofu_binary is None:
        pytest.skip("OpenTofu not installed (brew install opentofu)")

    workdir = tmp_path_factory.mktemp("tofu-validate-gcp")
    for tf in infra_dir.glob("*.tf"):
        (workdir / tf.name).write_text(tf.read_text(encoding="utf-8"))

    init = subprocess.run(
        [tofu_binary, "init", "-backend=false", "-input=false", "-no-color"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if init.returncode != 0:
        return {"stage": "init", "returncode": init.returncode, "stderr": init.stderr, "stdout": init.stdout}

    validate = subprocess.run(
        [tofu_binary, "validate", "-json", "-no-color"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        parsed = json.loads(validate.stdout)
    except json.JSONDecodeError:
        parsed = {}
    return {"stage": "validate", "returncode": validate.returncode, "json": parsed, "stderr": validate.stderr, "stdout": validate.stdout}


__all__ = ["INFRA_DIR", "POLICIES_DIR"]
