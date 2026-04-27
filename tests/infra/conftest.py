"""tests/infra/conftest.py

Shared fixtures for the Sprint 2 OpenTofu test suite.

Strategy (validate-now-apply-later, per Sprint 2 clarifications):

  * **No cloud credentials needed.** All assertions run against the parsed
    HCL tree (`python-hcl2`) plus `tofu validate` syntactic checks. Real
    `tofu plan -out` JSON is reserved for the apply-time CI job once the
    user provides cloud credentials.

  * **Failure paths first** (TAP-4, AGENTS.md §Testing Anti-Patterns). Per
    story, rejection-style assertions (e.g. "min_instance_count must NOT
    be > 0", "secret_data must NEVER be a literal containing `KEY`")
    precede acceptance-style assertions in the test files.

  * **Single parse per session.** `parsed_hcl` is session-scoped so the
    suite stays fast (<1s for the full set). The file walker is in this
    module so individual tests stay declarative.

  * **L2 contract style** per the TDD prompt (Protocol B): tests assert the
    *contract* the sprint board's acceptance criteria put on each resource,
    not the implementation detail of which exact fields exist. A different
    valid HCL shape that meets the contract should still pass.
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


# python-hcl2 v8 keeps source-literal quotes around strings and emits
# `__comments__` blocks by default. We want clean Python dicts so test
# assertions read naturally; these options strip both.
_HCL_LOAD_OPTIONS = SerializationOptions(
    with_comments=False,
    strip_string_quotes=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Marker registration — `pytest tests/infra/` opt-in only.
# ─────────────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register the `infra` marker so `--strict-markers` accepts it.

    The root pyproject.toml's pytest `addopts` already excludes infra tests
    from the default `pytest tests/` run via `-m 'not slow and not
    simulation and not live_llm'`; we additionally namespace via this
    marker so a future `pytest -m infra` runs only the IaC suite.
    """
    config.addinivalue_line(
        "markers",
        "infra: marks tests as Sprint 2 OpenTofu/HCL infrastructure tests.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Path constants
# ─────────────────────────────────────────────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_DIR = REPO_ROOT / "infra" / "dev-tier"
POLICIES_DIR = INFRA_DIR / "policies"


# ─────────────────────────────────────────────────────────────────────────────
# Session fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def infra_dir() -> Path:
    """Absolute path to infra/dev-tier/. Asserted to exist so TDD-style
    'red' failures point at a missing directory rather than a None deref."""
    assert INFRA_DIR.is_dir(), (
        f"Expected infra dir at {INFRA_DIR}; Sprint 2 §Epic 2.1 requires "
        "this directory to host all V3-Dev-Tier OpenTofu stacks."
    )
    return INFRA_DIR


@pytest.fixture(scope="session")
def tf_files(infra_dir: Path) -> list[Path]:
    """All .tf files under infra/dev-tier/. Excludes test fixtures and any
    nested module subdirectories (Sprint 2 has none)."""
    return sorted(infra_dir.glob("*.tf"))


@pytest.fixture(scope="session")
def parsed_hcl(tf_files: list[Path]) -> dict[str, Any]:
    """Parse every .tf file once. Returns a single merged dict where every
    top-level key (resource, data, variable, output, locals, terraform,
    provider) is a list of declarations across all files.

    `python-hcl2` returns each file as a dict with list values. We merge
    by extending lists so the suite can ask 'is there a
    google_cloud_run_v2_service named middleware?' without caring which
    .tf file declared it.
    """
    merged: dict[str, list[Any]] = {}
    for tf_path in tf_files:
        with tf_path.open("r", encoding="utf-8") as fh:
            tree = hcl2.load(fh, serialization_options=_HCL_LOAD_OPTIONS)
        for top_key, items in tree.items():
            # `__comments__` is suppressed by SerializationOptions but defend
            # against any future shape change anyway.
            if top_key.startswith("__"):
                continue
            merged.setdefault(top_key, []).extend(items)
    return merged


@pytest.fixture(scope="session")
def resources(parsed_hcl: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat list of `{type, name, attrs}` dicts, one per resource block.

    `python-hcl2` shapes resources as ``{"resource": [{"type": {"name":
    {...attrs...}}}, ...]}``; that nesting is hostile to assertions, so
    we flatten into a list of small dicts here.
    """
    flat: list[dict[str, Any]] = []
    for entry in parsed_hcl.get("resource", []):
        for resource_type, named in entry.items():
            for resource_name, attrs in named.items():
                flat.append(
                    {
                        "type": resource_type,
                        "name": resource_name,
                        "attrs": attrs,
                    }
                )
    return flat


@pytest.fixture(scope="session")
def data_sources(parsed_hcl: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat list of `data` blocks, same shape as `resources`."""
    flat: list[dict[str, Any]] = []
    for entry in parsed_hcl.get("data", []):
        for data_type, named in entry.items():
            for data_name, attrs in named.items():
                flat.append(
                    {
                        "type": data_type,
                        "name": data_name,
                        "attrs": attrs,
                    }
                )
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


# Utility helpers (find_resources, get_one, unwrap_block) live in
# tests/infra/_hcl_helpers.py so test modules can import them directly.
# Importing them here just to keep the public surface stable.


# ─────────────────────────────────────────────────────────────────────────────
# Optional `tofu validate` fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def tofu_binary() -> str | None:
    """Discover the OpenTofu binary; tests requiring it skip when absent.

    Per Sprint 2 §S2.1.1 acceptance the canonical CLI is `tofu`. We do
    NOT fall back to `terraform` — `versions.tf` only supports OpenTofu
    by virtue of `required_version` and OpenTofu-specific features may
    leak in over time.
    """
    return shutil.which("tofu")


@pytest.fixture(scope="session")
def tofu_validate_result(
    tofu_binary: str | None,
    infra_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    """Run `tofu init -backend=false` then `tofu validate -json` once per
    session against an isolated working copy of infra/dev-tier/.

    Skips the suite if `tofu` is not installed locally — the workstation
    setup script (infra/dev-tier/README.md §Local prereqs) installs it,
    but a fresh clone may not yet have done so.
    """
    if tofu_binary is None:
        pytest.skip("OpenTofu not installed (brew install opentofu)")

    workdir = tmp_path_factory.mktemp("tofu-validate")
    # Mirror only the .tf files into the temp workdir so we don't touch
    # the source tree's .terraform/ cache.
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
        return {
            "stage": "init",
            "returncode": init.returncode,
            "stderr": init.stderr,
            "stdout": init.stdout,
        }

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
    return {
        "stage": "validate",
        "returncode": validate.returncode,
        "json": parsed,
        "stderr": validate.stderr,
        "stdout": validate.stdout,
    }


__all__ = ["INFRA_DIR", "POLICIES_DIR"]
