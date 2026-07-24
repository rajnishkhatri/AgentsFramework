"""Architecture gate: T R.14 — deploy-time flag↔var guard (FR-A4/§6 cutover, FR-G1).

Finding 2 (expanded) from the coach-v3 end-to-end review: the build-time
``NEXT_PUBLIC_FF_DURABLE_ENGINE`` flag can diverge from the Terraform
``enable_durable_engine`` var. Concretely — an operator builds a flag-OFF
image, pins its digest in ``terraform.tfvars``, then later flips
``enable_durable_engine = true`` WITHOUT rebuilding. Cloud Run runtime env
cannot change an already-inlined ``NEXT_PUBLIC_*`` bundle, so the deployed
revision silently stays on ``InMemoryEngineDb`` while the operator believes
the durable engine is live. The reverse (flag-ON image, var OFF) is equally
dangerous — a shadow→canary that quietly becomes canary.

T R.5 (``test_durable_engine_build_flag.py``) tombstoned the BUILD-path half
(Docker ARG/ENV + ``--build-arg`` + TF var). This module tombstones the
DEPLOY-path half:

  (a) ``Dockerfile.frontend`` bakes the flag value into a final-image LABEL so
      the pinned digest is self-describing — ``docker inspect`` returns what
      the image was built with.
  (b) ``scripts/deploy_gcp.sh`` has a guard that reads the PINNED
      ``frontend_image`` digest + ``enable_durable_engine`` from tfvars,
      inspects the image's label, and FAILS on mismatch — before the Terraform
      apply that would route traffic to the mismatched revision.

Part (b) of the task also commits ``seed_engine_content.counts.json`` +
``seed_sources/*.json`` so the parity gate
(``test_engine_seed_source_parity.py``) runs in CI; that is covered by the
files being git-tracked, asserted here as a tracked-file gate.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCKERFILE = _REPO_ROOT / "frontend/Dockerfile.frontend"
_DEPLOY = _REPO_ROOT / "scripts/deploy_gcp.sh"
_TFVARS_EXAMPLE = _REPO_ROOT / "infra/gcp/terraform.tfvars.example"

_FLAG_ENV = "NEXT_PUBLIC_FF_DURABLE_ENGINE"
_LABEL_KEY = "org.agentsframework.ff_durable_engine"
_TF_VAR = "enable_durable_engine"

# Files T R.14 (b) requires to be git-tracked so the parity gate runs in CI.
_TRACKED_SEED_FILES = [
    _REPO_ROOT / "frontend/drizzle/seed_engine_content.counts.json",
    _REPO_ROOT / "frontend/lib/adapters/engine/seed_sources/skills.json",
    _REPO_ROOT / "frontend/lib/adapters/engine/seed_sources/tutorials.json",
    _REPO_ROOT / "frontend/lib/adapters/engine/seed_sources/content_strings.json",
    _REPO_ROOT / "frontend/lib/adapters/engine/seed_sources/blueprints.json",
]


def _runner_stage(dockerfile: str) -> str:
    """Slice the final (runner) stage — from the last FROM to EOF."""
    matches = list(
        re.finditer(
            r"^FROM\b[^\n]*\bAS\s+runner\b(.*?)(?=^FROM\b|\Z)",
            dockerfile,
            flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
    )
    assert matches, "Dockerfile.frontend must declare a runner (final) stage"
    return matches[-1].group(1)


class TestDockerfileBakesFlagLabel:
    def test_runner_stage_declares_flag_arg_and_label(self) -> None:
        """T R.14 (a): the final image must self-describe its build flag.

        ``NEXT_PUBLIC_*`` is inlined at ``next build`` in the BUILDER stage; the
        RUNNER stage is a fresh ``FROM`` so labels set there are what
        ``docker inspect`` returns for the deployed image. The runner must
        re-declare the ARG (ARGs are per-stage) and emit a LABEL keyed by
        ``org.agentsframework.ff_durable_engine`` so the deploy guard can read
        it off the pinned digest without the build context.
        """
        text = _DOCKERFILE.read_text()
        runner = _runner_stage(text)
        arg_match = re.search(
            rf"^\s*ARG\s+{_FLAG_ENV}(?:=|\s|$)",
            runner,
            flags=re.MULTILINE,
        )
        label_match = re.search(
            rf"^\s*LABEL\s+{_LABEL_KEY}\s*=",
            runner,
            flags=re.MULTILINE,
        )
        assert arg_match is not None, (
            f"Dockerfile.frontend runner stage must re-declare ARG {_FLAG_ENV} "
            "so the LABEL can reference it (ARGs do not cross FROM boundaries)."
        )
        assert label_match is not None, (
            f"Dockerfile.frontend runner stage must emit "
            f"LABEL {_LABEL_KEY}=$({_FLAG_ENV}) so the pinned digest is "
            "self-describing and the deploy guard can read what was built."
        )
        # The LABEL value must reference the ARG (not a hardcoded literal),
        # otherwise a flag flip without a rebuild would be undetectable.
        label_line = re.search(
            rf"^\s*LABEL\s+{_LABEL_KEY}\s*=\s*(.+)$",
            runner,
            flags=re.MULTILINE,
        )
        assert label_line is not None
        assert _FLAG_ENV in label_line.group(1), (
            f"LABEL {_LABEL_KEY} must reference $({_FLAG_ENV}) (the ARG), not a "
            f"hardcoded literal — got: {label_line.group(1).strip()!r}"
        )


class TestDeployScriptFlagVarGuard:
    def test_deploy_script_declares_guard_function(self) -> None:
        """T R.14 (b): a named guard reads tfvars + image label and compares."""
        text = _DEPLOY.read_text()
        # A named function whose body references both the tfvars var and the
        # label key, and which fails (non-zero) on mismatch.
        guard_fn = re.search(
            r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{",
            text,
            flags=re.MULTILINE,
        )
        assert guard_fn is not None, "deploy_gcp.sh must define functions"

        # Find a function whose body mentions the label key AND the tfvars var
        # AND a mismatch/fail path. Function-name agnostic — match intent.
        fn_pattern = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*?)^\}",
            flags=re.MULTILINE | re.DOTALL,
        )
        guard_found = False
        for m in fn_pattern.finditer(text):
            body = m.group(2)
            if (
                _LABEL_KEY in body
                and _TF_VAR in body
                and ("mismatch" in body.lower() or "fail" in body.lower())
            ):
                guard_found = True
                break
        assert guard_found, (
            "deploy_gcp.sh must define a guard function that reads "
            f"enable_durable_engine + the pinned frontend_image label "
            f"({_LABEL_KEY}) and fails on mismatch (T R.14 b)."
        )

    def test_deploy_script_guard_reads_pinned_frontend_image_from_tfvars(self) -> None:
        """T R.14 (b): the guard inspects the PINNED digest, not a just-built tag.

        The divergence risk is specifically a stale pin: operator flips the var
        without rebuilding. The guard must read ``frontend_image`` from tfvars
        (the pinned @sha256 ref), not the local just-built tag — otherwise it
        only proves the build was self-consistent (tautological) and misses the
        stale-pin case.
        """
        text = _DEPLOY.read_text()
        fn_pattern = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*?)^\}",
            flags=re.MULTILINE | re.DOTALL,
        )
        guard_body = None
        for m in fn_pattern.finditer(text):
            body = m.group(2)
            if _LABEL_KEY in body and _TF_VAR in body:
                guard_body = body
                break
        assert guard_body is not None, (
            "deploy_gcp.sh flag↔var guard function not found (see "
            "test_deploy_script_declares_guard_function)."
        )
        assert "frontend_image" in guard_body, (
            "the flag↔var guard must read `frontend_image` from tfvars (the "
            "pinned @sha256 digest) — inspecting a just-built local tag is "
            "tautological and misses the stale-pin divergence case."
        )

    def test_deploy_script_guard_inspects_image_label(self) -> None:
        """T R.14 (b): the guard reads the label via docker inspect (or equivalent)."""
        text = _DEPLOY.read_text()
        fn_pattern = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*?)^\}",
            flags=re.MULTILINE | re.DOTALL,
        )
        guard_body = None
        for m in fn_pattern.finditer(text):
            body = m.group(2)
            if _LABEL_KEY in body and _TF_VAR in body:
                guard_body = body
                break
        assert guard_body is not None
        # docker inspect --format or docker image inspect with the label key.
        inspects_label = (
            "docker inspect" in guard_body
            or "docker image inspect" in guard_body
            or "crane config" in guard_body
            or "skopeo inspect" in guard_body
        )
        assert inspects_label, (
            "the flag↔var guard must inspect the pinned image's "
            f"{_LABEL_KEY} label via `docker inspect` (or crane/skopeo) — "
            "the label is the only deploy-time witness of what was built."
        )

    def test_phase_frontend_invokes_guard_before_apply(self) -> None:
        """T R.14 (b): the guard runs in phase_frontend BEFORE tofu_gate/apply.

        Traffic is TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST 100% on apply, so a
        mismatch must abort before the apply that would route traffic to the
        bad revision. (Running it in phase_images only would miss a later
        stale-pin flip.)
        """
        text = _DEPLOY.read_text()
        phase_match = re.search(
            r"^phase_frontend\(\)\s*\{(.*?)^\}",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert phase_match is not None, "deploy_gcp.sh must define phase_frontend()"
        body = phase_match.group(1)
        # Locate the guard invocation (any function whose body references the
        # label key — we already proved one exists). We just need SOME call
        # inside phase_frontend that precedes tofu_gate.
        fn_pattern = re.compile(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*?)^\}",
            flags=re.MULTILINE | re.DOTALL,
        )
        guard_fn_names = [
            m.group(1)
            for m in fn_pattern.finditer(text)
            if _LABEL_KEY in m.group(2) and _TF_VAR in m.group(2)
        ]
        assert guard_fn_names, "flag↔var guard function not found"
        guard_call = None
        for name in guard_fn_names:
            call_match = re.search(rf"\b{name}\b", body)
            if call_match:
                guard_call = call_match
                break
        assert guard_call is not None, (
            f"phase_frontend must invoke the flag↔var guard "
            f"({guard_fn_names[0]!r}) before routing traffic."
        )
        # Match the actual `tofu_gate` *call line* (whitespace-prefixed, not
        # inside a `#` comment or a quoted string) — a comment that mentions
        # tofu_gate must not be mistaken for the apply invocation.
        apply_call = re.search(r"(?m)^[ \t]*tofu_gate\b", body)
        assert apply_call is not None, "phase_frontend must call tofu_gate"
        assert guard_call.start() < apply_call.start(), (
            "the flag↔var guard must run BEFORE tofu_gate in phase_frontend — "
            "a mismatch must abort before the apply that routes traffic."
        )


class TestSeedSourcesTrackedForCi:
    def test_seed_counts_ledger_and_seed_sources_exist_on_disk(self) -> None:
        """T R.14 (b): the parity gate reads these from disk; they must exist."""
        missing = [str(p) for p in _TRACKED_SEED_FILES if not p.is_file()]
        assert missing == [], (
            "T R.14 (b): seed parity sources missing on disk: "
            f"{missing}. test_engine_seed_source_parity.py cannot run in CI."
        )

    def test_seed_counts_ledger_matches_known_inventory(self) -> None:
        """T R.14 (b) / FR-G1: the ledger pins the canonical per-source counts."""
        import json

        ledger = json.loads(
            (_REPO_ROOT / "frontend/drizzle/seed_engine_content.counts.json").read_text(
                encoding="utf-8"
            )
        )
        assert ledger == {
            "test_item": 987,
            "hint": 7857,
            "skill": 6,
            "tutorial": 1,
            "content_string": 3,
            "test_blueprint": 1,
        }, (
            "seed_engine_content.counts.json must pin the canonical FR-G1 "
            f"inventory; got {ledger!r}"
        )
