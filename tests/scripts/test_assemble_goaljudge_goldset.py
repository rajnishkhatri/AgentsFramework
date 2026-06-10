"""L2 contract tests for ``scripts/assemble_goaljudge_goldset.py``.

Pyramid layer:  L2 Reproducible (TDD Protocol B — Contract-Driven TDD)
Architecture:   ``tests/scripts/`` — drives the assembly CLI via
                ``subprocess`` against synthetic CSV fixtures + temp
                manifest output paths. Mirrors the existing
                ``test_compute_goaljudge_stage5_alpha.py`` shape.

The CLI's job (per Tier 3 plan §"Phase 6"):

1. Read the adjudicated full sheet CSV.
2. Per row, construct a validated ``GoldsetItem`` (firewall enforced).
3. Assert assembly invariants (cell coverage + goal_met=false share +
   firewall).
4. Compute the test-split SHA-256.
5. Load into Langfuse via the injected ``LangfuseDatasetClient`` (the
   ``--dry-run`` flag skips this; tests always use it).
6. Write the v1 manifest JSON to the configured path.

Tests prove the contract end-to-end against:

* a well-formed CSV ⇒ exit 0; manifest has all required keys; correct
  total/dev/test counts and goal_met_false_share;
* a firewall-violating CSV (synthetic+test) ⇒ non-zero exit with a
  clear stderr message;
* an invariant-violating CSV (e.g. 50% goal_met=true) ⇒ non-zero exit
  with a clear stderr message.

Anti-patterns guarded against (per ``research/tdd_agentic_systems_prompt.md``):

* AP-1 Tautological — every expected count and key is hand-derived from
  the synthetic CSV, not by re-running the script's math.
* AP-2 Mock addiction — zero mocks; subprocess + tmp_path = real CLI.
* AP-5 Live LLM in CI — ``--dry-run`` keeps Langfuse out; tests are
  offline by construction.
* AP-6 Gap blindness — both failure paths (firewall + invariant) are
  tested, not just the happy path.
* AP-7 Cross-layer dependency leak — ``tests/scripts/`` imports
  ``services/governance/`` (lower layer); zero ``components/`` /
  ``orchestration/`` imports.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "assemble_goaljudge_goldset.py"


# ───────────────────────────────────────────────────────────────────────────
# Fixture builder
# ───────────────────────────────────────────────────────────────────────────


_SHEET_FIELDS: tuple[str, ...] = (
    "item_id", "split", "provenance",
    "stratum", "domain",
    "planning_depth", "tool_cluster",
    "task", "claim", "evidence_summary",
    "r1_goal_met", "r1_graceful_failure", "r1_partial_fraction", "r1_failure_mode",
    "r2_goal_met", "r2_graceful_failure", "r2_partial_fraction", "r2_failure_mode",
    "adjudicated_goal_met", "adjudicated_failure_mode",
    "rubric_version", "note",
)


def _make_row(**overrides: str) -> dict[str, str]:
    base: dict[str, str] = {f: "" for f in _SHEET_FIELDS}
    base.update({
        "item_id": "GJ-001",
        "split": "dev",
        "provenance": "production",
        "stratum": "representative",
        "domain": "file_io",
        "planning_depth": "L1",
        "tool_cluster": "file-only",
        "task": "do thing",
        "claim": "did thing",
        "evidence_summary": "tool evidence",
        "r1_goal_met": "false",
        "r2_goal_met": "false",
        "r1_partial_fraction": "0.5",
        "r2_partial_fraction": "0.5",
        "r1_failure_mode": "subtask-dropped",
        "r2_failure_mode": "subtask-dropped",
        "adjudicated_goal_met": "false",
        "adjudicated_failure_mode": "subtask-dropped",
        "rubric_version": "stage4_confirmed",
    })
    base.update(overrides)
    return base


def _write_sheet(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_SHEET_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


# ───────────────────────────────────────────────────────────────────────────
# Acceptance: a well-formed CSV produces a manifest with the right shape.
# ───────────────────────────────────────────────────────────────────────────


class TestAssembleCliSuccess:
    """The end-to-end happy path: 10-row CSV → manifest with required
    keys + correct counts. Failure-path tests follow."""

    def test_well_formed_csv_writes_manifest(self, tmp_path: Path) -> None:
        # Hand-derived expectations:
        #   total = 10
        #   dev = 7, test = 3
        #   false = 8, true = 2 ⇒ false_share = 0.80
        rows: list[dict[str, str]] = []
        for i in range(7):
            rows.append(
                _make_row(
                    item_id=f"GJ-D-{i:02d}",
                    split="dev",
                    provenance="production",
                    adjudicated_goal_met="false",
                    adjudicated_failure_mode="subtask-dropped",
                )
            )
        # 2 dev items flipped to goal_met=true
        rows[0]["adjudicated_goal_met"] = "true"
        rows[0]["adjudicated_failure_mode"] = ""
        rows[1]["adjudicated_goal_met"] = "true"
        rows[1]["adjudicated_failure_mode"] = ""
        # 3 test items (all production, all false)
        for i in range(3):
            rows.append(
                _make_row(
                    item_id=f"GJ-T-{i:02d}",
                    split="test",
                    provenance="production",
                    adjudicated_goal_met="false",
                    adjudicated_failure_mode="subtask-dropped",
                )
            )

        sheet = tmp_path / "sheet.csv"
        manifest = tmp_path / "manifest.json"
        _write_sheet(sheet, rows)

        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--sheet", str(sheet),
                "--manifest", str(manifest),
                "--dry-run",
                # Lower the floors so a 10-row test exercises the
                # invariant path; production floors require ~250 items.
                "--min-goal-met-false-share", "0.60",
                # 10-row fixture can't satisfy the production D1/D5
                # floors (which require ~250 items). The CLI's
                # production gate keeps them on; smoke runs opt out.
                "--skip-cell-coverage",
                "--frozen-at", "2026-06-09T00:00:00Z",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        # Exit 0 ⇒ no exception; CLI's stdout should mention success.
        assert "manifest" in proc.stdout.lower()

        # Manifest shape — externally derived expected values:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["dataset_name"] == "goaljudge_goldset_v1"
        assert payload["total_items"] == 10
        assert payload["dev_count"] == 7
        assert payload["test_count"] == 3
        # 8 / 10 = 0.80
        assert payload["goal_met_false_share"] == 0.80
        # All 12 required keys present
        for key in [
            "dataset_name", "total_items", "dev_count", "test_count",
            "test_split_sha256", "rubric_version", "frozen_at",
            "stratum_distribution", "planning_depth_distribution",
            "tool_cluster_distribution", "failure_mode_distribution",
            "goal_met_false_share",
        ]:
            assert key in payload, f"manifest missing required key {key!r}"
        # Distribution dicts contain the expected sheet labels
        assert payload["planning_depth_distribution"]["L1"] == 10
        assert payload["tool_cluster_distribution"]["file-only"] == 10
        # test_split_sha256 is non-blank (the whole point of freezing)
        assert payload["test_split_sha256"]


# ───────────────────────────────────────────────────────────────────────────
# Failure: firewall violation surfaces with non-zero exit.
# ───────────────────────────────────────────────────────────────────────────


class TestAssembleCliFirewall:
    """A synthetic-in-test row violates the contamination firewall. The
    CLI MUST exit non-zero AND surface a clear stderr message — silent
    fallthrough would let contaminated rows enter the gold set."""

    def test_synthetic_in_test_split_exits_nonzero(self, tmp_path: Path) -> None:
        rows = [
            _make_row(
                item_id="GJ-X",
                split="test",
                provenance="synthetic",  # firewall violation
                adjudicated_goal_met="false",
                adjudicated_failure_mode="subtask-dropped",
            ),
        ]
        sheet = tmp_path / "sheet.csv"
        manifest = tmp_path / "manifest.json"
        _write_sheet(sheet, rows)

        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--sheet", str(sheet),
                "--manifest", str(manifest),
                "--dry-run",
                "--frozen-at", "2026-06-09T00:00:00Z",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        combined = proc.stdout + proc.stderr
        assert "firewall" in combined.lower() or "synthetic" in combined.lower()
        assert not manifest.exists(), \
            "manifest must not be written when assembly fails"


# ───────────────────────────────────────────────────────────────────────────
# Failure: invariant violation (50% goal_met=true) surfaces clearly.
# ───────────────────────────────────────────────────────────────────────────


class TestAssembleCliInvariant:
    """If the labeled set has a goal_met=false share below the floor, the
    CLI MUST exit non-zero. This is the 'labels collapsed' guard that
    catches sourcing-pass + labeling-collapse."""

    def test_low_false_share_exits_nonzero(self, tmp_path: Path) -> None:
        # 6 true / 4 false ⇒ share = 0.40 ⇒ below 0.60 floor
        rows: list[dict[str, str]] = []
        for i in range(6):
            rows.append(
                _make_row(
                    item_id=f"GJ-T-{i:02d}",
                    adjudicated_goal_met="true",
                    adjudicated_failure_mode="",
                )
            )
        for i in range(4):
            rows.append(
                _make_row(
                    item_id=f"GJ-F-{i:02d}",
                    adjudicated_goal_met="false",
                    adjudicated_failure_mode="subtask-dropped",
                )
            )

        sheet = tmp_path / "sheet.csv"
        manifest = tmp_path / "manifest.json"
        _write_sheet(sheet, rows)

        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--sheet", str(sheet),
                "--manifest", str(manifest),
                "--dry-run",
                "--min-goal-met-false-share", "0.60",
                "--frozen-at", "2026-06-09T00:00:00Z",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        combined = (proc.stdout + proc.stderr).lower()
        assert "goal_met" in combined or "share" in combined
        assert not manifest.exists()
