"""Smoke test for Stage 4 IAA κ computation script."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


def test_cohen_kappa_perfect_agreement(tmp_path: Path):
    sheet = tmp_path / "sheet.csv"
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["case_id", "r1_a2_fail", "r2_a2_fail"],
        )
        writer.writeheader()
        writer.writerow({"case_id": "GJ-010", "r1_a2_fail": "Y", "r2_a2_fail": "Y"})
        writer.writerow({"case_id": "GJ-001B", "r1_a2_fail": "N", "r2_a2_fail": "N"})

    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "compute_goaljudge_stage4_iaa_kappa.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(sheet)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "kappa=1.0000" in proc.stdout
    assert "gate=PASS" in proc.stdout
