"""Architecture gate: T R.5 — durable-engine flag in the production bundle (FR-A4/§6).

Finding 6 from the coach-v3 end-to-end review: ``NEXT_PUBLIC_FF_DURABLE_ENGINE`` is
build-time-inlined, but ``Dockerfile.frontend`` / ``deploy_gcp.sh`` / Terraform never
supplied it, so every deployed browser stayed on ``InMemoryEngineDb``.

This module tombstones the build-path half: Docker ARG/ENV before ``pnpm build``,
``--build-arg`` from ``phase_images``, and a non-``NEXT_PUBLIC_*`` TF deployment var
that ``deploy_gcp.sh`` maps into the build-arg (default OFF for shadow→canary).
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCKERFILE = _REPO_ROOT / "frontend/Dockerfile.frontend"
_DEPLOY = _REPO_ROOT / "scripts/deploy_gcp.sh"
_VARIABLES = _REPO_ROOT / "infra/gcp/variables.tf"
_TFVARS_EXAMPLE = _REPO_ROOT / "infra/gcp/terraform.tfvars.example"
_CLIENT_FLAG_READERS = (
    _REPO_ROOT / "frontend/lib/adapters/engine/engine_client.ts",
    _REPO_ROOT / "frontend/lib/composition_engine_browser.ts",
)

_FLAG_ENV = "NEXT_PUBLIC_FF_DURABLE_ENGINE"
_TF_VAR = "enable_durable_engine"


def _builder_stage(dockerfile: str) -> str:
    """Slice from builder stage header through the next FROM (or EOF)."""
    match = re.search(
        r"^FROM\b[^\n]*\bAS\s+builder\b(.*?)(?=^FROM\b|\Z)",
        dockerfile,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    assert match is not None, "Dockerfile.frontend must declare a builder stage"
    return match.group(1)


class TestDurableEngineBuildFlag:
    def test_browser_flag_readers_use_static_next_public_access(self) -> None:
        """Next only inlines direct ``process.env.NEXT_PUBLIC_*`` member access."""
        direct_read = f"process.env.{_FLAG_ENV}"
        for path in _CLIENT_FLAG_READERS:
            text = path.read_text()
            assert direct_read in text, (
                f"{path.relative_to(_REPO_ROOT)} must read {direct_read} directly; "
                "dynamic process.env[key] access is undefined in the browser bundle "
                "and silently leaves durable progress disabled"
            )

    def test_dockerfile_declares_durable_engine_build_arg_before_pnpm_build(
        self,
    ) -> None:
        """T R.5 (a): ARG must exist in the builder stage ahead of ``pnpm build``."""
        text = _DOCKERFILE.read_text()
        builder = _builder_stage(text)
        arg_match = re.search(
            rf"^\s*ARG\s+{_FLAG_ENV}(?:=|\s|$)",
            builder,
            flags=re.MULTILINE,
        )
        build_match = re.search(
            r"^\s*RUN\s+pnpm\s+build\b", builder, flags=re.MULTILINE
        )
        assert arg_match is not None, (
            f"Dockerfile.frontend builder must declare ARG {_FLAG_ENV} "
            "(NEXT_PUBLIC_* is inlined at next build; runtime Cloud Run env cannot flip it)"
        )
        assert build_match is not None, (
            "Dockerfile.frontend builder must run pnpm build"
        )
        assert arg_match.start() < build_match.start(), (
            f"ARG {_FLAG_ENV} must appear BEFORE `RUN pnpm build` so the value is inlined"
        )

    def test_dockerfile_exports_durable_engine_env_for_next_build(self) -> None:
        """T R.5 (a): ENV must bind the ARG so ``next build`` sees the flag."""
        builder = _builder_stage(_DOCKERFILE.read_text())
        env_match = re.search(
            rf"^\s*ENV\s+{_FLAG_ENV}=",
            builder,
            flags=re.MULTILINE,
        )
        build_match = re.search(
            r"^\s*RUN\s+pnpm\s+build\b", builder, flags=re.MULTILINE
        )
        assert env_match is not None, (
            f"Dockerfile.frontend builder must ENV {_FLAG_ENV}=… before pnpm build"
        )
        assert build_match is not None
        assert env_match.start() < build_match.start(), (
            f"ENV {_FLAG_ENV} must appear BEFORE `RUN pnpm build`"
        )

    def test_deploy_passes_durable_engine_build_arg(self) -> None:
        """T R.5 (a): phase_images must pass the flag into the frontend image build."""
        text = _DEPLOY.read_text()
        # Match the live frontend docker build (not a comment-only mention).
        frontend_builds = list(
            re.finditer(
                r"docker\s+build\b[^\n]*Dockerfile\.frontend[^\n]*",
                text,
            )
        )
        assert frontend_builds, (
            "scripts/deploy_gcp.sh must invoke docker build … Dockerfile.frontend"
        )
        # Also allow multi-line builds: look for --build-arg near Dockerfile.frontend
        # within phase_images (or the whole script if the build spans lines).
        has_build_arg = bool(
            re.search(
                rf"--build-arg\s+{_FLAG_ENV}=",
                text,
            )
        )
        assert has_build_arg, (
            f"deploy_gcp.sh must pass --build-arg {_FLAG_ENV}=… when building "
            "Dockerfile.frontend (setting the var only at Playwright/runtime cannot "
            "change an already-compiled NEXT_PUBLIC_* bundle)"
        )

    def test_tf_declares_enable_durable_engine_not_next_public(self) -> None:
        """T R.5 (a): TF deployment var exists; name must not start with NEXT_PUBLIC_."""
        text = _VARIABLES.read_text()
        assert re.search(
            rf'variable\s+"{_TF_VAR}"\s*\{{',
            text,
        ), (
            f'infra/gcp/variables.tf must declare variable "{_TF_VAR}" '
            "(operator knob for the durable-engine image build; mapped to the Docker "
            "build-arg by deploy_gcp.sh — not a Cloud Run runtime NEXT_PUBLIC_* env)"
        )
        # FE-AP-18 / test_cross_cutting: never a TF var named NEXT_PUBLIC_*.
        assert not re.search(
            rf'variable\s+"{_FLAG_ENV}"\s*\{{',
            text,
        ), (
            f'TF must not declare variable "{_FLAG_ENV}" — NEXT_PUBLIC_* names are '
            "forbidden in infra/ (exposed-to-browser convention)"
        )

    def test_tf_enable_durable_engine_defaults_false(self) -> None:
        """Shadow→canary: prod stays InMemory until an operator flips the knob + rebuilds."""
        text = _VARIABLES.read_text()
        match = re.search(
            rf'variable\s+"{_TF_VAR}"\s*\{{(.*?)^\}}',
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert match is not None, f'missing variable "{_TF_VAR}"'
        body = match.group(1)
        assert re.search(r"default\s*=\s*false\b", body), (
            f"{_TF_VAR} must default to false (shadow→canary; flag-on requires "
            "explicit tfvars + frontend image rebuild)"
        )

    def test_tfvars_example_documents_durable_engine_build(self) -> None:
        """Operators must see the rebuild requirement next to the deployment var."""
        text = _TFVARS_EXAMPLE.read_text()
        assert _TF_VAR in text, f"terraform.tfvars.example must document {_TF_VAR}"
        assert _FLAG_ENV in text or "--build-arg" in text, (
            "terraform.tfvars.example must mention the Docker build-arg / "
            f"{_FLAG_ENV} so operators know a rebuild is required"
        )
