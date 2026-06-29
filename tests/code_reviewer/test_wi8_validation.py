"""WI-8 tests: fixture well-formedness + the validation math (no live LLM).

The recorded-verdict gate test is skip-gated on ``verdicts.json`` being
present (mirrors the L3 fixture in ``tests/meta/test_code_reviewer.py``): CI
must NOT make live LLM calls, so a human runs
``scripts/record_code_reviewer_validation.py`` with an API key to populate the
recording; the test then replays it through ``validate_judge`` and asserts the
gate passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code_reviewer.routing import KNOWN_FOLDERS
from meta.code_reviewer_validation import (
    CASES_JSON,
    VERDICTS_JSON,
    load_recorded,
    run_validation_cli,
    validate_recorded,
)

FIXTURE_DIR = CASES_JSON.parent


# ───────────────────────────────────────────────────────────────────────────
# Fixture well-formedness
# ───────────────────────────────────────────────────────────────────────────


def _load_manifest() -> dict:
    return json.loads(CASES_JSON.read_text())


class TestWi8FixtureWellFormed:
    def test_manifest_parses_and_has_gate(self):
        m = _load_manifest()
        assert m["gate"]["tpr_min"] == 0.90
        assert m["gate"]["tnr_min"] == 0.90
        assert "detection_convention" in m

    def test_twenty_cases_ten_clean_ten_violating(self):
        cases = _load_manifest()["cases"]
        assert len(cases) == 20
        clean = [c for c in cases if c["gold_goal_met"] is True]
        violating = [c for c in cases if c["gold_goal_met"] is False]
        assert len(clean) == 10
        assert len(violating) == 10

    def test_every_case_files_exist_on_disk(self):
        for c in _load_manifest()["cases"]:
            for rel in c["files"]:
                assert (FIXTURE_DIR / "cases" / c["id"] / rel).is_file(), (
                    f"{c['id']}: missing file {rel}"
                )

    def test_every_case_folder_is_known_or_root(self):
        for c in _load_manifest()["cases"]:
            assert c["folder"] in set(KNOWN_FOLDERS) | {""}, (
                f"{c['id']}: folder {c['folder']!r} not routable"
            )

    def test_violating_cases_target_llm_only_rules(self):
        """Every violating case cites a rule_id (the LLM-only failure mode)."""
        for c in _load_manifest()["cases"]:
            if c["gold_goal_met"] is False:
                assert c["rule_id"], f"{c['id']}: violating case has no rule_id"
                assert c["severity"] in {"warning", "critical"}
                assert c["dimension"]

    def test_case_ids_unique(self):
        cases = _load_manifest()["cases"]
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids))

    def test_clean_cases_have_no_rule_id(self):
        for c in _load_manifest()["cases"]:
            if c["gold_goal_met"] is True:
                assert c["rule_id"] is None
                assert c["severity"] is None


# ───────────────────────────────────────────────────────────────────────────
# Validation math (synthetic recordings — no live LLM)
# ───────────────────────────────────────────────────────────────────────────


def _synthetic_manifest(cases: list[dict]) -> dict:
    return {
        "version": 1,
        "gate": {"tpr_min": 0.90, "tnr_min": 0.90},
        "detection_convention": "goal_met = no critical/warning findings",
        "cases": cases,
    }


def _synthetic_verdicts(records: list[dict]) -> dict:
    return {"version": 1, "records": records}


def _case(cid: str, gold: bool) -> dict:
    return {
        "id": cid,
        "folder": "trust",
        "gold_goal_met": gold,
        "rule_id": None,
        "severity": None,
        "dimension": None,
        "description": "",
        "files": [],
    }


def _record(cid: str, detected: bool | None) -> dict:
    return {
        "case_id": cid,
        "gold_goal_met": detected is not None,
        "detected": detected,
        "llm_verdict": "approve",
        "finding_count": 0,
        "actionable_finding_count": 0,
    }


class TestWi8ValidationMath:
    def test_perfect_judge_passes_gate(self, tmp_path):
        """A judge that detects every violation and passes every clean case."""
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        # detected = True for violating (gold False), False for clean (gold True)
        records = [
            _record(c["id"], detected=(c["gold_goal_met"] is False)) for c in cases
        ]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        result = validate_recorded(vpath, cpath)
        assert result.passed, result.reasons
        assert result.rates.tpr == 1.0
        assert result.rates.tnr == 1.0
        assert result.counts.tp == 10
        assert result.counts.tn == 10
        assert result.counts.fp == 0
        assert result.counts.fn == 0

    def test_one_miss_per_side_still_passes_at_090(self, tmp_path):
        """10/10 each side: one false-negative + one false-positive → 0.90/0.90."""
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        # Judge misses one violation (FN) and false-alarms one clean (FP).
        det = []
        for i, c in enumerate(cases):
            if i == 0 and c["gold_goal_met"] is False:
                det.append(False)  # FN: violation not detected
            elif i == 10 and c["gold_goal_met"] is True:
                det.append(True)  # FP: clean flagged
            else:
                det.append(c["gold_goal_met"] is False)
        records = [_record(c["id"], d) for c, d in zip(cases, det, strict=True)]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        result = validate_recorded(vpath, cpath)
        assert result.passed, result.reasons
        assert result.rates.tpr == pytest.approx(0.9)
        assert result.rates.tnr == pytest.approx(0.9)

    def test_two_misses_per_side_fails_gate(self, tmp_path):
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        det = []
        for i, c in enumerate(cases):
            # Miss two violations (FN) and false-alarm two cleans (FP).
            if c["gold_goal_met"] is False and i in (0, 1):
                det.append(False)
            elif c["gold_goal_met"] is True and i in (10, 11):
                det.append(True)
            else:
                det.append(c["gold_goal_met"] is False)
        records = [_record(c["id"], d) for c, d in zip(cases, det, strict=True)]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        result = validate_recorded(vpath, cpath)
        assert not result.passed
        assert result.rates.tpr == pytest.approx(0.8)
        assert result.rates.tnr == pytest.approx(0.8)

    def test_errored_records_dropped_from_both_maps(self, tmp_path):
        """An errored case (detected=None) must not bias the gate."""
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        records = [
            _record(c["id"], detected=(c["gold_goal_met"] is False)) for c in cases
        ]
        # Inject an errored record (detected=None) — it must be dropped, and
        # its case dropped from gold too so the key sets stay aligned.
        records.append(_record("c-0", detected=None))
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        judge, gold, _ = load_recorded(vpath, cpath)
        # c-0 still has a valid (non-errored) record earlier in the list, so it
        # remains; the errored duplicate is simply ignored. 20 aligned keys.
        assert set(judge) == set(gold)
        assert len(judge) == 20
        result = validate_recorded(vpath, cpath)
        assert result.passed

    def test_all_errored_records_yield_empty_gate_fails_closed(self, tmp_path):
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        records = [_record(c["id"], detected=None) for c in cases]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        result = validate_recorded(vpath, cpath)
        # No data → both rates undecidable → fail-closed.
        assert not result.passed
        assert result.rates.tpr is None
        assert result.rates.tnr is None

    def test_missing_verdicts_file_raises_filenotfound(self, tmp_path):
        cpath = tmp_path / "cases.json"
        cpath.write_text(json.dumps(_synthetic_manifest([_case("c-0", False)])))
        with pytest.raises(FileNotFoundError):
            validate_recorded(tmp_path / "absent.json", cpath)

    def test_thresholds_read_from_manifest_gate(self, tmp_path):
        cases = [_case(f"c-{i}", gold) for i, gold in enumerate([False, True])]
        manifest = _synthetic_manifest(cases)
        manifest["gate"] = {"tpr_min": 0.50, "tnr_min": 0.50}
        records = [
            _record("c-0", detected=True),  # tp
            _record("c-1", detected=True),  # fp (clean flagged) → tnr=0.0
        ]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(manifest))

        result = validate_recorded(vpath, cpath)
        assert result.tpr_min == 0.50
        assert result.tnr_min == 0.50
        # tnr=0.0 < 0.50 → fail.
        assert not result.passed


# ───────────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────────


class TestWi8Cli:
    def test_cli_pass_on_perfect_recording(self, tmp_path, capsys):
        cases = [
            _case(f"c-{i}", gold) for i, gold in enumerate([False] * 10 + [True] * 10)
        ]
        records = [
            _record(c["id"], detected=(c["gold_goal_met"] is False)) for c in cases
        ]
        vpath = tmp_path / "verdicts.json"
        cpath = tmp_path / "cases.json"
        vpath.write_text(json.dumps(_synthetic_verdicts(records)))
        cpath.write_text(json.dumps(_synthetic_manifest(cases)))

        rc = run_validation_cli(["--verdicts", str(vpath), "--cases", str(cpath)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "PASS" in out
        assert "TPR" in out

    def test_cli_fail_on_missing_recording(self, tmp_path, capsys):
        cpath = tmp_path / "cases.json"
        cpath.write_text(json.dumps(_synthetic_manifest([_case("c-0", False)])))
        rc = run_validation_cli(
            [
                "--verdicts",
                str(tmp_path / "absent.json"),
                "--cases",
                str(cpath),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 2
        assert "error" in out.lower()


# ───────────────────────────────────────────────────────────────────────────
# Recorded gate — enforced in CI once verdicts.json is present (no live LLM in
# CI; this is a fast recorded-replay). Skips only when the recording is absent.
# ───────────────────────────────────────────────────────────────────────────


class TestWi8RecordedGate:
    """Replay the recorded WI-8 verdicts and assert the gate passes.

    Skips when ``verdicts.json`` is absent (no live LLM call in CI). A human
    runs ``scripts/record_code_reviewer_validation.py`` with an API key to
    populate the recording; this test then certifies the judge.
    """

    def test_recorded_gate_passes(self):
        if not VERDICTS_JSON.exists():
            pytest.skip(
                "WI-8 recording absent. Run "
                "scripts/record_code_reviewer_validation.py with an API key to "
                f"populate {VERDICTS_JSON.relative_to(Path.cwd()) if Path.cwd() in VERDICTS_JSON.parents else VERDICTS_JSON}."
            )
        result = validate_recorded()
        assert result.passed, (
            f"WI-8 gate FAILED: TPR={result.rates.tpr} TNR={result.rates.tnr}; "
            f"reasons={result.reasons}. The honest limit stays — do not commit "
            "a failing recording to flip the gate; improve the v3 prompt and re-run."
        )

    def test_recorded_counts_balanced(self):
        if not VERDICTS_JSON.exists():
            pytest.skip("WI-8 recording absent.")
        result = validate_recorded()
        # 10 gold-negative (violations) + 10 gold-positive (clean) = 20.
        n = result.counts.tp + result.counts.fp + result.counts.fn + result.counts.tn
        assert n == 20, f"expected 20 aligned cases, got {n}"
