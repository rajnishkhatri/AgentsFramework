"""L2 contract tests for the Stage 5 α gate CLI.

Pyramid layer:  L2 Reproducible (TDD Protocol B — Contract-Driven TDD)
Architecture:   ``tests/scripts/`` — drives
                ``scripts/compute_goaljudge_stage5_alpha.py``
                via ``subprocess`` against synthetic CSVs, mirroring
                ``tests/scripts/test_compute_goaljudge_stage4_iaa_kappa.py``.

These tests prove the CLI's *behavior*, not the α math. The L1 file
``tests/services/governance/test_iaa.py`` already pins the math
(externally-derived expected values, AP-1 guarded). This file proves:

* The CLI exits 0 on perfect agreement and reports ``PASS`` at α=1.0.
* The CLI surfaces a clear, parseable ``FAIL`` line below the gate
  (per Stage 5 acceptance: α ≥ 0.8).
* The new ``--diff`` flag writes a disagreement diff CSV that
  downstream adjudication can consume directly — Phase 5 step 4
  ("re-label only the disagreement rows") depends on this.

Anti-patterns guarded against:

* AP-1 Tautological — no re-running of the α formula; expected
  outcomes are PASS/FAIL strings and CSV columns, not floats derived
  from the same code path.
* AP-2 Mock addiction — zero mocks; subprocess + tmp_path = real CLI.
* AP-5 Live LLM in CI — no LLM, no Langfuse, no network.
* AP-6 Gap blindness — both PASS and FAIL paths are tested (gate
  contracts are equally interesting in both directions).
* AP-7 Cross-layer dependency leak — ``tests/scripts/`` may import
  from ``scripts/`` and ``services/``, NOT from ``components/``
  or ``orchestration/``.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "compute_goaljudge_stage5_alpha.py"


def _write_sheet(
    path: Path,
    rows: list[dict[str, str]],
    *,
    extra_fieldnames: tuple[str, ...] = (),
) -> None:
    """Write a minimal Stage 5 sheet to ``path`` with the columns the α
    script reads (``r1_goal_met`` / ``r2_goal_met``) plus any extras."""
    fieldnames = ["item_id", "r1_goal_met", "r2_goal_met", *extra_fieldnames]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ───────────────────────────────────────────────────────────────────────────
# Failure path: a sheet that does NOT meet the gate must surface FAIL.
# ───────────────────────────────────────────────────────────────────────────


class TestAlphaGateFail:
    """The script's job is to report PASS/FAIL deterministically; a mid-α
    sheet must produce a clear FAIL line so CI / annotators don't misread
    a near-threshold result as a pass."""

    def test_mixed_disagreement_below_threshold_reports_fail(
        self, tmp_path: Path
    ) -> None:
        """Construct 10 items where 6/10 disagree on the binary unit.
        This drives α well below 0.8 (~ −0.4 by the canonical formula)
        and MUST report ``gate=FAIL``. The exact α value is not asserted
        here (that's L1's job); only the gate direction."""
        rows = [
            {"item_id": f"GJ-{i:03d}", "r1_goal_met": "true", "r2_goal_met": "false"}
            for i in range(6)
        ] + [
            {"item_id": f"GJ-{i:03d}", "r1_goal_met": "true", "r2_goal_met": "true"}
            for i in range(6, 10)
        ]
        sheet = tmp_path / "mid_alpha.csv"
        _write_sheet(sheet, rows)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(sheet)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "gate=FAIL" in proc.stdout
        assert "(threshold α ≥ 0.8)" in proc.stdout


# ───────────────────────────────────────────────────────────────────────────
# Acceptance path: perfect agreement passes the gate cleanly.
# ───────────────────────────────────────────────────────────────────────────


class TestAlphaGatePass:
    """Mirror of the κ pass test (``test_cohen_kappa_perfect_agreement``).
    Catches: a refactor that introduces a hidden truthiness flip would
    break this."""

    def test_perfect_agreement_reports_pass_and_alpha_one(self, tmp_path: Path) -> None:
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-002", "r1_goal_met": "false", "r2_goal_met": "false"},
            {"item_id": "GJ-003", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-004", "r1_goal_met": "false", "r2_goal_met": "false"},
        ]
        sheet = tmp_path / "perfect.csv"
        _write_sheet(sheet, rows)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(sheet)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "alpha=1.0000" in proc.stdout
        assert "gate=PASS" in proc.stdout


# ───────────────────────────────────────────────────────────────────────────
# --diff: the disagreement CSV is the adjudicator's working copy.
# ───────────────────────────────────────────────────────────────────────────


class TestAlphaGateDiffOutput:
    """Phase 5 step 4 ('re-label only the disagreement rows') depends on
    a per-row diff. The CLI's ``--diff OUT.csv`` flag MUST emit a CSV
    where each row identifies an item and the two diverging labels."""

    def test_diff_flag_emits_disagreement_rows_only(self, tmp_path: Path) -> None:
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-002", "r1_goal_met": "true", "r2_goal_met": "false"},
            {"item_id": "GJ-003", "r1_goal_met": "false", "r2_goal_met": "false"},
            {"item_id": "GJ-004", "r1_goal_met": "Y", "r2_goal_met": "N"},
        ]
        sheet = tmp_path / "sheet.csv"
        diff = tmp_path / "diff.csv"
        _write_sheet(sheet, rows)

        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(sheet),
                "--diff",
                str(diff),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        with diff.open(encoding="utf-8") as fh:
            diff_rows = list(csv.DictReader(fh))

        assert [r["item_id"] for r in diff_rows] == ["GJ-002", "GJ-004"]
        # Normalized spellings — adjudicator sees canonical 'true'/'false'.
        assert diff_rows[0]["r1"] == "true"
        assert diff_rows[0]["r2"] == "false"
        assert diff_rows[1]["r1"] == "true"
        assert diff_rows[1]["r2"] == "false"

    def test_diff_flag_absent_does_not_write_file(self, tmp_path: Path) -> None:
        """Back-compat: today's invocations (no --diff) must NOT write
        anything beyond stdout, so existing scripts and notebooks aren't
        broken."""
        rows = [
            {"item_id": "GJ-001", "r1_goal_met": "true", "r2_goal_met": "true"},
            {"item_id": "GJ-002", "r1_goal_met": "true", "r2_goal_met": "false"},
        ]
        sheet = tmp_path / "sheet.csv"
        _write_sheet(sheet, rows)

        before = set(tmp_path.iterdir())
        subprocess.run(
            [sys.executable, str(SCRIPT), str(sheet)],
            capture_output=True,
            text=True,
            check=True,
        )
        after = set(tmp_path.iterdir())
        assert before == after, "no extra files should be created without --diff"
