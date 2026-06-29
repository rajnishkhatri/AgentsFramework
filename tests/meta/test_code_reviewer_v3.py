"""L1/L2 tests for the WI-6 v3 unified, context-routed reviewer path.

Covers: v3 config acceptance, the routed deterministic review (backend AST,
ADR.1, TAP-2/TAP-4, frontend TS fold), routed-groups payload construction,
the v3 LLM injection (rules_file_content + deterministic_findings), and the
``--from-git-diff`` CLI flag.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta.code_reviewer import (
    CodeReviewerAgent,
    _git_diff_files,
    _V3_FD7_AUTO_REJECT_RULE_IDS,
    _V3_HIGH_CONF_WARNING_QUORUM,
    _V3_WARNING_CONFIDENCE_THRESHOLD,
    apply_v3_verdict_policy,
    run_code_reviewer_cli,
    run_deterministic_review_v3,
)
from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig
from trust.review_schema import Certificate, ReviewFinding, Severity, Verdict

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── v3 config acceptance ──────────────────────────────────────────────


class TestReviewConfigV3:
    def test_v3_is_accepted(self):
        cfg = ReviewAgentConfig(
            name="v3-run",
            files=["trust/enums.py"],
            prompt_version="v3",
            output_json="out.json",
        )
        assert cfg.prompt_version == "v3"

    def test_v1_v2_still_accepted(self):
        for v in ("v1", "v2"):
            cfg = ReviewAgentConfig(
                name=f"{v}-run",
                files=["trust/enums.py"],
                prompt_version=v,
                output_json="out.json",
            )
            assert cfg.prompt_version == v

    def test_unknown_version_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ReviewAgentConfig(
                name="bad",
                files=["trust/enums.py"],
                prompt_version="v4",
                output_json="out.json",
            )

    def test_agent_rejects_unknown_version(self):
        with pytest.raises(ValueError):
            CodeReviewerAgent(prompt_version="v4")

    def test_agent_accepts_v3(self):
        agent = CodeReviewerAgent(prompt_version="v3")
        assert agent._prompt_version == "v3"
        assert (
            agent._system_prompt_template()
            == "codeReviewer/v3/CodeReviewer_system_prompt"
        )
        assert agent._submission_prompt_template() == (
            "codeReviewer/v3/CodeReviewer_review_submission"
        )


# ── run_deterministic_review_v3 ───────────────────────────────────────


class TestDeterministicReviewV3:
    def test_clean_trust_file_approves(self, tmp_path):
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "enums.py").write_text(
            "from enum import Enum\n\n\nclass Foo(Enum):\n    A = 1\n"
        )
        report = run_deterministic_review_v3(["trust/enums.py"], repo_root=tmp_path)
        assert report.verdict == Verdict.APPROVE
        assert report.files_reviewed == ["trust/enums.py"]
        # Routed group logged.
        assert any("Routed group" in line for line in report.validation_log)

    def test_trust_io_import_rejects_with_d4_critical(self, tmp_path):
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "bad.py").write_text("import logging\n")
        report = run_deterministic_review_v3(["trust/bad.py"], repo_root=tmp_path)
        assert report.verdict == Verdict.REJECT
        d4 = next(d for d in report.dimensions if d.dimension == "D4")
        assert any(f.severity == Severity.CRITICAL for f in d4.findings)
        # Findings carry repo-relative paths, not absolute.
        assert all(f.file == "trust/bad.py" for f in d4.findings)

    def test_adr1_trigger_with_no_adr_emits_d2_warning(self, tmp_path):
        # An Ask-first trigger (pyproject.toml) with no docs/adr/ file.
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        report = run_deterministic_review_v3(["pyproject.toml"], repo_root=tmp_path)
        d2 = next((d for d in report.dimensions if d.dimension == "D2"), None)
        assert d2 is not None
        assert any(f.rule_id == "ADR.1" for f in d2.findings)

    def test_adr1_relief_when_adr_present(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0042-some-decision.md").write_text("# ADR 0042\n")
        report = run_deterministic_review_v3(
            ["pyproject.toml", "docs/adr/0042-some-decision.md"],
            repo_root=tmp_path,
        )
        # No ADR.1 finding when an ADR was filed in the same diff.
        d2 = next((d for d in report.dimensions if d.dimension == "D2"), None)
        assert d2 is None or all(f.rule_id != "ADR.1" for f in d2.findings)

    def test_tap2_mock_abuse_emits_d3_warning(self, tmp_path):
        tests_dir = tmp_path / "tests" / "trust"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_x.py").write_text(
            "from unittest.mock import MagicMock, patch, Mock\n"
            "def test_a():\n"
            "    m1 = MagicMock(); m2 = MagicMock(); m3 = MagicMock(); m4 = Mock()\n"
            "    assert m1 and m2 and m3 and m4\n"
        )
        report = run_deterministic_review_v3(
            ["tests/trust/test_x.py"], repo_root=tmp_path
        )
        d3 = next((d for d in report.dimensions if d.dimension == "D3"), None)
        assert d3 is not None
        assert any(f.rule_id == "TAP-2" for f in d3.findings)

    def test_nonexistent_file_skipped(self, tmp_path):
        report = run_deterministic_review_v3(["trust/missing.py"], repo_root=tmp_path)
        assert report.verdict == Verdict.APPROVE
        assert report.files_reviewed == []
        assert any("not found" in line for line in report.validation_log)

    def test_frontend_fold_emits_fd_finding(self, tmp_path):
        """TS predicates are folded in via findings_from_tool (mocked)."""
        fe_dir = tmp_path / "frontend" / "app"
        fe_dir.mkdir(parents=True)
        (fe_dir / "page.tsx").write_text(
            "export default function Page() { return null }\n"
        )
        # Mock applicable_tools (so csp runs for a .tsx) + run_ts_script
        # (so we don't need tsx installed).
        fake_raw = {
            "pass": False,
            "exit_code": 1,
            "violations": [
                {"rule": "CSP1", "description": "unsafe-inline in CSP"},
            ],
        }
        with (
            patch(
                "meta.code_reviewer.applicable_tools",
                return_value=[("check_csp_strict", ["frontend/app/page.tsx"])],
            ),
            patch("meta.code_reviewer.run_ts_script", return_value=fake_raw),
        ):
            report = run_deterministic_review_v3(
                ["frontend/app/page.tsx"], repo_root=tmp_path
            )
        fd3 = next((d for d in report.dimensions if d.dimension == "FD3"), None)
        assert fd3 is not None
        assert any(f.rule_id == "FD3.CSP1" for f in fd3.findings)
        assert all(f.file == "frontend/app/page.tsx" for f in fd3.findings)

    def test_frontend_missing_tsx_surfaces_as_gap_not_crash(self, tmp_path):
        fe_dir = tmp_path / "frontend"
        fe_dir.mkdir(parents=True)
        (fe_dir / "Composer.tsx").write_text("export const C = () => null\n")
        with patch(
            "meta.code_reviewer.run_ts_script",
            return_value={"pass": False, "exit_code": 2, "error": "tsx not installed"},
        ):
            report = run_deterministic_review_v3(
                ["frontend/Composer.tsx"], repo_root=tmp_path
            )
        # No finding emitted; the error is logged, not raised.
        assert report.verdict == Verdict.APPROVE
        assert any("error" in line for line in report.validation_log)


# ── _build_routed_groups ──────────────────────────────────────────────


class TestBuildRoutedGroups:
    def test_reads_real_review_md_for_trust(self):
        agent = CodeReviewerAgent(prompt_version="v3")
        groups = agent._build_routed_groups(["trust/enums.py"], repo_root=AGENT_ROOT)
        assert len(groups) == 1
        g = groups[0]
        assert g["rules_file"] == "trust/REVIEW.md"
        assert "rule_id" in g["rules_file_content"]  # the enforcement table
        assert g["files"][0]["path"] == "trust/enums.py"
        assert g["files"][0]["language"] == "backend"
        assert g["files"][0]["language_hint"] == "python"

    def test_falls_back_to_root_review_md_when_folder_lacks_one(self, tmp_path):
        # tmp_path has no frontend/REVIEW.md and no root REVIEW.md → marker.
        fe_dir = tmp_path / "frontend"
        fe_dir.mkdir(parents=True)
        (fe_dir / "page.tsx").write_text("export default function Page() {}\n")
        agent = CodeReviewerAgent(prompt_version="v3")
        groups = agent._build_routed_groups(["frontend/page.tsx"], repo_root=tmp_path)
        g = groups[0]
        assert "not found" in g["rules_file_content"]
        assert g["files"][0]["language"] == "frontend"
        assert g["files"][0]["language_hint"] == "tsx"

    def test_groups_by_rules_file(self):
        agent = CodeReviewerAgent(prompt_version="v3")
        groups = agent._build_routed_groups(
            ["trust/enums.py", "services/base_config.py"],
            repo_root=AGENT_ROOT,
        )
        rules_files = {g["rules_file"] for g in groups}
        assert "trust/REVIEW.md" in rules_files
        assert "services/REVIEW.md" in rules_files


# ── _review_v3 LLM injection ──────────────────────────────────────────


class TestReviewV3LLMInjection:
    def test_deterministic_only_returns_deterministic_report(
        self, tmp_path, monkeypatch
    ):
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "enums.py").write_text("from enum import Enum\n")
        monkeypatch.setattr("meta.code_reviewer.AGENT_ROOT", tmp_path)
        agent = CodeReviewerAgent(
            llm_service=None,
            prompt_service=None,
            prompt_version="v3",
        )
        import asyncio

        report = asyncio.run(
            agent._review_v3(["trust/enums.py"], None, added_files=None)
        )
        assert report.verdict == Verdict.APPROVE

    def test_llm_receives_routed_groups_and_deterministic_findings(
        self, tmp_path, monkeypatch
    ):
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "bad.py").write_text("import logging\n")  # D4 critical
        monkeypatch.setattr("meta.code_reviewer.AGENT_ROOT", tmp_path)

        captured: dict = {}

        class FakePromptService:
            def render_prompt(self, template: str, **kwargs):
                if "system" in template or template.endswith("system_prompt"):
                    return "SYSTEM"
                # submission — capture the routed-groups payload.
                captured["submission_kwargs"] = kwargs
                captured["template"] = template
                return "SUBMISSION"

        class FakeLLM:
            async def invoke(self, profile, messages):
                return MagicMock(
                    content=json.dumps(
                        {
                            "verdict": "approve",
                            "statement": "ok",
                            "confidence": 0.9,
                            "dimensions": [],
                            "gaps": [],
                            "validation_log": [],
                            "files_reviewed": [],
                        }
                    )
                )

        with patch("meta.code_reviewer.eval_capture.record", new=AsyncMock()):
            import asyncio

            agent = CodeReviewerAgent(
                llm_service=FakeLLM(),
                prompt_service=FakePromptService(),
                prompt_version="v3",
            )
            report = asyncio.run(
                agent._review_v3(["trust/bad.py"], "diff text", added_files=None)
            )

        # The v3 submission template was rendered with routed_groups + findings.
        assert captured["template"] == "codeReviewer/v3/CodeReviewer_review_submission"
        kwargs = captured["submission_kwargs"]
        assert "routed_groups" in kwargs
        assert len(kwargs["routed_groups"]) == 1
        # tmp_path has no trust/REVIEW.md → router falls back to root REVIEW.md.
        assert kwargs["routed_groups"][0]["rules_file"] == "REVIEW.md"
        # Deterministic findings were serialized into the submission.
        det = kwargs["deterministic_findings"]
        assert "TRUST_PURITY" in det  # the D4 critical from `import logging`
        assert kwargs["submission_context"] == "diff text"
        # Merge: deterministic critical → reject verdict.
        assert report.verdict == Verdict.REJECT


# ── CLI --from-git-diff ───────────────────────────────────────────────


class TestCLIFromGitDiff:
    def test_from_git_diff_v3_deterministic(self, tmp_path, monkeypatch):
        # Build a fake repo root with a clean trust file.
        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "enums.py").write_text("from enum import Enum\n")
        monkeypatch.setattr("meta.code_reviewer.AGENT_ROOT", tmp_path)
        monkeypatch.setattr(
            "meta.code_reviewer._git_diff_files",
            lambda base: (["trust/enums.py"], ["trust/enums.py"]),
        )
        exit_code = run_code_reviewer_cli(
            [
                "--from-git-diff",
                "--prompt-version",
                "v3",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert exit_code == 0  # approve
        out = json.loads((tmp_path / "out.json").read_text())
        assert out["verdict"] == "approve"

    def test_from_git_diff_requires_no_files_flag(self, monkeypatch, tmp_path):
        monkeypatch.setattr("meta.code_reviewer.AGENT_ROOT", tmp_path)
        monkeypatch.setattr(
            "meta.code_reviewer._git_diff_files",
            lambda base: ([], []),
        )
        # No --files, no --from-git-diff → error 3.
        assert run_code_reviewer_cli(["--prompt-version", "v3"]) == 3

    def test_git_diff_files_uses_git(self, monkeypatch):
        """_git_diff_files shells out to git and parses name-only output."""
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "trust/enums.py\nservices/base_config.py\n"
        fake_proc.stderr = ""
        with patch("subprocess.run", return_value=fake_proc):
            changed, added = _git_diff_files("HEAD")
        assert changed == ["trust/enums.py", "services/base_config.py"]
        # added uses a second call with --diff-filter=A; same mock → same list.
        assert added == ["trust/enums.py", "services/base_config.py"]

    def test_git_diff_files_empty_on_error(self, monkeypatch):
        fake_proc = MagicMock()
        fake_proc.returncode = 1
        fake_proc.stderr = "fatal: bad rev"
        fake_proc.stdout = ""
        with patch("subprocess.run", return_value=fake_proc):
            changed, added = _git_diff_files("HEAD")
        assert changed == [] and added == []


# ── v1/v2 path is unchanged (regression guard) ───────────────────────


class TestV1V2Unchanged:
    def test_v1_default_still_works(self):
        from meta.code_reviewer import run_deterministic_review

        report = run_deterministic_review([str(AGENT_ROOT / "trust" / "enums.py")])
        assert report.verdict == Verdict.APPROVE

    def test_v3_default_off(self):
        # The CLI default is still v1, not v3.
        agent = CodeReviewerAgent()
        assert agent._prompt_version == "v1"


# ── WI-9: calibrated verdict policy ───────────────────────────────────


def _finding(
    *,
    rule_id: str,
    dimension: str,
    severity: Severity,
    confidence: float = 1.0,
    file: str = "trust/x.py",
) -> ReviewFinding:
    return ReviewFinding(
        rule_id=rule_id,
        dimension=dimension,
        severity=severity,
        file=file,
        line=1,
        description="test finding",
        fix_suggestion="",
        confidence=confidence,
        certificate=Certificate(
            premises=["[P1] test"],
            traces=[],
            conclusion=f"{rule_id} FAIL -- test",
        ),
    )


class TestApplyV3VerdictPolicy:
    """Calibration matrix for the WI-9 severity+confidence verdict policy."""

    def test_clean_approves(self):
        verdict, statement, demoted = apply_v3_verdict_policy([])
        assert verdict == Verdict.APPROVE
        assert demoted == []

    def test_d1_critical_rejects(self):
        # Architectural critical auto-rejects.
        f = _finding(
            rule_id="DEP.trust_no_upward", dimension="D1", severity=Severity.CRITICAL
        )
        verdict, _stmt, demoted = apply_v3_verdict_policy([f])
        assert verdict == Verdict.REJECT
        # Critical is not demoted (only low-confidence warnings are).
        assert demoted[0].severity == Severity.CRITICAL

    def test_d4_critical_rejects(self):
        f = _finding(rule_id="TRUST_PURITY", dimension="D4", severity=Severity.CRITICAL)
        verdict, _stmt, _demoted = apply_v3_verdict_policy([f])
        assert verdict == Verdict.REJECT

    def test_fd7_auto_reject_rule_rejects(self):
        # An FD7 security-critical anti-pattern auto-rejects even outside D1/D4.
        f = _finding(
            rule_id="FE-AP-18",
            dimension="FD7",
            severity=Severity.CRITICAL,
        )
        verdict, _stmt, _demoted = apply_v3_verdict_policy([f])
        assert verdict == Verdict.REJECT
        # Every named FD7 rule is recognized.
        assert _V3_FD7_AUTO_REJECT_RULE_IDS == frozenset(
            {"FE-AP-4", "FE-AP-6", "FE-AP-7", "FE-AP-12", "FE-AP-18", "FE-AP-19"}
        )

    def test_other_dimension_critical_is_request_changes(self):
        # A critical outside D1/D4/FD7-auto-reject trips request_changes, not reject.
        f = _finding(rule_id="D5.AP2", dimension="D5", severity=Severity.CRITICAL)
        verdict, _stmt, _demoted = apply_v3_verdict_policy([f])
        assert verdict == Verdict.REQUEST_CHANGES

    def test_subquorum_high_confidence_warnings_approve(self):
        # Two high-confidence warnings: below the quorum of 3 → approve.
        assert _V3_HIGH_CONF_WARNING_QUORUM == 3
        fs = [
            _finding(
                rule_id="W1", dimension="D2", severity=Severity.WARNING, confidence=0.9
            ),
            _finding(
                rule_id="W2", dimension="D2", severity=Severity.WARNING, confidence=0.8
            ),
        ]
        verdict, _stmt, _demoted = apply_v3_verdict_policy(fs)
        assert verdict == Verdict.APPROVE

    def test_quorum_high_confidence_warnings_request_changes(self):
        # Three high-confidence warnings meet the quorum → request_changes.
        fs = [
            _finding(
                rule_id="W1", dimension="D2", severity=Severity.WARNING, confidence=0.9
            ),
            _finding(
                rule_id="W2", dimension="D2", severity=Severity.WARNING, confidence=0.8
            ),
            _finding(
                rule_id="W3", dimension="D2", severity=Severity.WARNING, confidence=0.75
            ),
        ]
        verdict, stmt, _demoted = apply_v3_verdict_policy(fs)
        assert verdict == Verdict.REQUEST_CHANGES
        assert "high-confidence" in stmt

    def test_low_confidence_cosmetics_demoted_to_info_and_do_not_gate(self):
        # 598-file format baseline: many low-confidence cosmetic warnings must
        # NOT trip request_changes — they demote to INFO notes.
        assert _V3_WARNING_CONFIDENCE_THRESHOLD == 0.7
        fs = [
            _finding(
                rule_id=f"FMT.{i}",
                dimension="D2",
                severity=Severity.WARNING,
                confidence=0.4,
            )
            for i in range(598)
        ]
        verdict, _stmt, demoted = apply_v3_verdict_policy(fs)
        assert verdict == Verdict.APPROVE
        # Every cosmetic was demoted to INFO.
        assert all(f.severity == Severity.INFO for f in demoted)
        assert all("demoted to note" in f.description for f in demoted)

    def test_mixed_cosmetic_and_high_confidence_warning_quorum_uses_high_conf_only(
        self,
    ):
        # 2 high-confidence + 50 cosmetics: only the 2 high-confidence count → approve.
        fs = [
            _finding(
                rule_id="W1", dimension="D2", severity=Severity.WARNING, confidence=0.9
            ),
            _finding(
                rule_id="W2", dimension="D2", severity=Severity.WARNING, confidence=0.85
            ),
        ] + [
            _finding(
                rule_id=f"FMT.{i}",
                dimension="D2",
                severity=Severity.WARNING,
                confidence=0.3,
            )
            for i in range(50)
        ]
        verdict, _stmt, demoted = apply_v3_verdict_policy(fs)
        assert verdict == Verdict.APPROVE
        # Cosmetics demoted; the two high-confidence warnings stay warnings.
        warnings = [f for f in demoted if f.severity == Severity.WARNING]
        assert len(warnings) == 2

    def test_confidence_boundary_inclusive_at_threshold(self):
        # confidence == 0.7 is a gate-tripper (>=); 598 of them → request_changes.
        f = _finding(
            rule_id="W1", dimension="D2", severity=Severity.WARNING, confidence=0.7
        )
        fs = [f] * 3
        verdict, _stmt, _demoted = apply_v3_verdict_policy(fs)
        assert verdict == Verdict.REQUEST_CHANGES

    def test_confidence_just_below_threshold_demotes(self):
        # confidence 0.69 is a cosmetic → demoted, does not gate.
        f = _finding(
            rule_id="W1", dimension="D2", severity=Severity.WARNING, confidence=0.69
        )
        verdict, _stmt, demoted = apply_v3_verdict_policy([f])
        assert verdict == Verdict.APPROVE
        assert demoted[0].severity == Severity.INFO

    def test_critical_takes_precedence_over_warning_quorum(self):
        # A D5 critical + 5 high-confidence warnings → request_changes (critical),
        # not reject (D5 is not a reject dimension).
        crit = _finding(rule_id="D5.AP2", dimension="D5", severity=Severity.CRITICAL)
        warns = [
            _finding(
                rule_id=f"W{i}",
                dimension="D2",
                severity=Severity.WARNING,
                confidence=0.9,
            )
            for i in range(5)
        ]
        verdict, stmt, _demoted = apply_v3_verdict_policy([crit, *warns])
        assert verdict == Verdict.REQUEST_CHANGES
        assert "critical" in stmt


class TestMergeCosmeticDemotion:
    """The _merge_reports path demotes low-confidence LLM cosmetics and applies
    the calibrated policy (regression guard for WI-9 at the merge seam)."""

    def test_low_confidence_llm_warnings_do_not_gate_in_merge(
        self, tmp_path, monkeypatch
    ):
        import asyncio

        trust_dir = tmp_path / "trust"
        trust_dir.mkdir()
        (trust_dir / "enums.py").write_text("from enum import Enum\n")
        monkeypatch.setattr("meta.code_reviewer.AGENT_ROOT", tmp_path)

        # LLM emits 5 low-confidence cosmetic warnings — must demote to notes and
        # approve (the deterministic half is clean).
        llm_payload = {
            "verdict": "request_changes",
            "statement": "cosmetics",
            "confidence": 0.6,
            "dimensions": [
                {
                    "dimension": "D2",
                    "name": "Style Guide Adherence",
                    "status": "partial",
                    "hypotheses_tested": 5,
                    "hypotheses_confirmed": 5,
                    "hypotheses_killed": 0,
                    "findings": [
                        {
                            "rule_id": f"FMT.{i}",
                            "dimension": "D2",
                            "severity": "warning",
                            "file": "trust/enums.py",
                            "line": i,
                            "description": "format nit",
                            "fix_suggestion": "",
                            "confidence": 0.4,
                            "certificate": {
                                "premises": ["[P1] x"],
                                "traces": [],
                                "conclusion": "FMT FAIL",
                            },
                        }
                        for i in range(5)
                    ],
                }
            ],
            "gaps": [],
            "validation_log": [],
            "files_reviewed": ["trust/enums.py"],
        }

        class FakePromptService:
            def render_prompt(self, template: str, **kwargs):
                return "SYSTEM" if "system" in template else "SUBMISSION"

        class FakeLLM:
            async def invoke(self, profile, messages):
                return MagicMock(content=json.dumps(llm_payload))

        with patch("meta.code_reviewer.eval_capture.record", new=AsyncMock()):
            agent = CodeReviewerAgent(
                llm_service=FakeLLM(),
                prompt_service=FakePromptService(),
                prompt_version="v3",
            )
            report = asyncio.run(
                agent._review_v3(["trust/enums.py"], "diff", added_files=None)
            )

        # Low-confidence cosmetics demoted → approve, not request_changes.
        assert report.verdict == Verdict.APPROVE
        d2 = next(d for d in report.dimensions if d.dimension == "D2")
        # All findings demoted to INFO notes.
        assert all(f.severity == Severity.INFO for f in d2.findings)
        # The dimension dropped from PARTIAL to PASS (notes are not violations).
        assert d2.status.value == "pass"
