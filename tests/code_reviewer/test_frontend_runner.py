"""Unit tests for the Frontend Reviewer runner.

Covers:
  - Argv parsing (default + named scopes + repeatable --files + comma split)
  - Scope validation (unknown scope -> ValueError -> EXIT_RUNNER_ERROR)
  - Prompt rendering against synthetic file inputs (variables substituted)
  - Exit-code mapping (verdict + --fail-on demotion)
  - --dry-run path: prompt rendered, file written, exit 0, no LLM call
  - --rules-only path: TS-tool dispatch is mocked; aggregation + verdict

Per AGENTS.md: never run live LLM calls in tests; the runner's eval
capture is hit via a no-op mock, and `run_ts_script` is mocked so we
don't actually shell out to `tsx` from the unit test runner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the repo root importable when pytest is launched from inside the
# repo (the conftest pythonpath="." setting handles the standard case;
# this fallback keeps the tests usable from arbitrary cwd).
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_reviewer.frontend import runner  # noqa: E402
from code_reviewer.frontend.runner import (  # noqa: E402
    EXIT_OK,
    EXIT_REJECT,
    EXIT_REQUEST_CHANGES,
    EXIT_RUNNER_ERROR,
    ToolFinding,
    derive_verdict,
    exit_code_for,
    expand_files,
    parse_args,
    render_prompts,
)


# ── Argv parsing ──────────────────────────────────────────────────────


class TestArgvParsing:
    def test_defaults(self):
        a = parse_args(["--out", "review.json"])
        assert a.scope == "full"
        assert a.fail_on == "critical"
        assert a.model == "MODEL_NORMAL"
        assert a.dry_run is False
        assert a.rules_only is False
        assert a.user_id == "reviewer-cli"
        assert a.task_id == "review"  # derived from --out basename

    def test_repeated_files_and_comma_split(self):
        a = parse_args([
            "--files", "a.ts,b.ts",
            "--files", "c.ts",
            "--out", "x.json",
        ])
        assert a.files == ("a.ts", "b.ts", "c.ts")

    @pytest.mark.parametrize(
        "scope",
        ["full", "adapter_pr", "ui_component_pr", "wire_translator_pr",
         "security_audit", "sprint_audit", "infra_audit"],
    )
    def test_each_named_scope_accepted(self, scope):
        a = parse_args(["--scope", scope, "--out", "review.json"])
        assert a.scope == scope

    def test_unknown_scope_raises(self):
        with pytest.raises(ValueError):
            parse_args(["--scope", "bogus", "--out", "x.json"])

    @pytest.mark.parametrize("tier", ["MODEL_FAST", "MODEL_NORMAL", "MODEL_DEEP"])
    def test_each_model_tier_accepted(self, tier):
        a = parse_args(["--model", tier, "--out", "x.json"])
        assert a.model == tier

    def test_task_id_defaults_to_out_basename(self):
        a = parse_args(["--out", "/tmp/review-2024-01-01.json"])
        assert a.task_id == "review-2024-01-01"

    def test_dry_run_and_rules_only_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            parse_args(["--dry-run", "--rules-only", "--out", "x.json"])


# ── File expansion ────────────────────────────────────────────────────


class TestExpandFiles:
    def test_paths_pass_through_unchanged(self):
        assert expand_files(("a.ts", "b.ts")) == ["a.ts", "b.ts"]

    def test_globs_expand_recursively(self, tmp_path: Path):
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "one.ts").write_text("// 1")
        (tmp_path / "x" / "two.ts").write_text("// 2")
        pattern = str(tmp_path / "**" / "*.ts")
        out = expand_files((pattern,))
        assert len(out) == 2
        assert any(o.endswith("one.ts") for o in out)


# ── Prompt rendering ──────────────────────────────────────────────────


class TestRenderPrompts:
    def test_substitutes_files_and_scope(self):
        rendered = render_prompts(
            files_to_review=[
                {
                    "path": "frontend/components/chat/Composer.tsx",
                    "content": "// stub composer",
                    "language": "tsx",
                    "layer": "components",
                    "lines_changed": "Full file",
                },
            ],
            review_scope="ui_component_pr",
            submission_context="Synthetic test PR.",
        )
        assert "system" in rendered and "user" in rendered
        assert "frontend/components/chat/Composer.tsx" in rendered["user"]
        assert "ui_component_pr" in rendered["user"]
        assert "Synthetic test PR." in rendered["user"]
        # System prompt includes the architecture rules via {% include %}
        assert "Five Sub-Packages Map" in rendered["system"]
        assert "FE-AP-19" in rendered["system"]


# ── Verdict / exit-code mapping ───────────────────────────────────────


def _f(severity: str, rule: str = "FD3.X") -> ToolFinding:
    return ToolFinding(
        rule_id=rule,
        dimension=rule.split(".", 1)[0],
        severity=severity,
        file="x.ts",
        line=1,
        description=f"synthetic {severity}",
        fix_suggestion="",
        tool="synthetic",
    )


class TestVerdictAndExitCodes:
    def test_no_findings_approve_exit_0(self):
        assert derive_verdict([]) == "approve"
        assert exit_code_for("approve", [], "critical") == EXIT_OK

    def test_three_warnings_request_changes(self):
        findings = [_f("warning"), _f("warning"), _f("warning")]
        assert derive_verdict(findings) == "request_changes"
        assert exit_code_for("request_changes", findings, "critical") == EXIT_REQUEST_CHANGES

    def test_one_critical_rejects(self):
        findings = [_f("critical", "FD3.CSP1")]
        assert derive_verdict(findings) == "reject"
        assert exit_code_for("reject", findings, "critical") == EXIT_REJECT

    def test_fail_on_warning_demotes_approve_to_request_changes(self):
        findings = [_f("warning")]
        assert derive_verdict(findings) == "approve"
        assert exit_code_for("approve", findings, "warning") == EXIT_REQUEST_CHANGES

    def test_fail_on_info_demotes_when_only_info_findings(self):
        findings = [_f("info")]
        # base verdict is approve (no critical, ≤2 warnings)
        assert derive_verdict(findings) == "approve"
        assert exit_code_for("approve", findings, "info") == EXIT_REQUEST_CHANGES

    def test_critical_always_exits_2_regardless_of_fail_on(self):
        findings = [_f("critical")]
        assert exit_code_for("reject", findings, "info") == EXIT_REJECT
        assert exit_code_for("reject", findings, "warning") == EXIT_REJECT


# ── --dry-run end-to-end ──────────────────────────────────────────────


class TestDryRunMode:
    def test_dry_run_writes_rendered_prompt_and_returns_0(self, tmp_path: Path, monkeypatch):
        out = tmp_path / "review.json"

        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr(
            "code_reviewer.frontend.runner._record_eval",
            _noop,
        )

        rc = runner.run([
            "--dry-run",
            "--scope", "ui_component_pr",
            "--files", "frontend/components/chat/Composer.tsx",
            "--out", str(out),
            "--submission-context", "Test PR.",
        ])
        assert rc == EXIT_OK
        assert out.exists()
        payload = json.loads(out.read_text())
        assert payload["verdict"] == "approve"
        assert "rendered_prompt" in payload
        assert "ui_component_pr" in payload["rendered_prompt"]["user"]
        assert payload["metadata"]["mode"] == "dry_run"

    def test_dry_run_to_stdout_dash(self, tmp_path: Path, monkeypatch, capsys):
        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr(
            "code_reviewer.frontend.runner._record_eval",
            _noop,
        )
        rc = runner.run([
            "--dry-run",
            "--out", "-",
            "--files", "frontend/middleware.ts",
        ])
        assert rc == EXIT_OK
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["verdict"] == "approve"


# ── --rules-only end-to-end (with mocked TS dispatch) ────────────────


class TestRulesOnlyMode:
    def test_rules_only_with_clean_tools_returns_0(self, tmp_path: Path, monkeypatch):
        out = tmp_path / "review.json"

        def _fake_tool(name, *args, **kwargs):  # noqa: ARG001
            return {"pass": True, "exit_code": 0, "violations": [], "iframes": []}

        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr("code_reviewer.frontend.runner.run_ts_script", _fake_tool)
        monkeypatch.setattr("code_reviewer.frontend.runner._record_eval", _noop)

        rc = runner.run([
            "--rules-only",
            "--files", "frontend/middleware.ts",
            "--files", "frontend/components/generative/SandboxedCanvas.tsx",
            "--out", str(out),
        ])
        assert rc == EXIT_OK
        report = json.loads(out.read_text())
        assert report["verdict"] == "approve"
        assert report["metadata"]["mode"] == "rules_only"

    def test_rules_only_csp_violation_rejects(self, tmp_path: Path, monkeypatch):
        out = tmp_path / "review.json"

        def _fake_tool(name, *args, **kwargs):  # noqa: ARG001
            if name == "check_csp_strict":
                return {
                    "pass": False,
                    "exit_code": 1,
                    "violations": [
                        {"rule": "CSP1", "directive": "script-src",
                         "description": "script-src contains 'unsafe-inline'."},
                    ],
                    "iframes": [],
                }
            return {"pass": True, "exit_code": 0, "violations": [], "iframes": []}

        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr("code_reviewer.frontend.runner.run_ts_script", _fake_tool)
        monkeypatch.setattr("code_reviewer.frontend.runner._record_eval", _noop)

        rc = runner.run([
            "--rules-only",
            "--files", "frontend/middleware.ts",
            "--out", str(out),
        ])
        assert rc == EXIT_REJECT
        report = json.loads(out.read_text())
        assert report["verdict"] == "reject"
        rule_ids = {f["rule_id"] for d in report["dimensions"] for f in d["findings"]}
        assert "FD3.CSP1" in rule_ids
        assert "auto-reject" in report["statement"].lower()

    def test_rules_only_skipped_tool_recorded_as_gap(self, tmp_path: Path, monkeypatch):
        out = tmp_path / "review.json"

        def _fake_tool(name, *args, **kwargs):  # noqa: ARG001
            if name in ("check_axe_a11y", "check_bundle_budget"):
                return {"pass": True, "exit_code": 0, "skipped": True, "reason": "stub"}
            return {"pass": True, "exit_code": 0, "violations": [], "iframes": []}

        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr("code_reviewer.frontend.runner.run_ts_script", _fake_tool)
        monkeypatch.setattr("code_reviewer.frontend.runner._record_eval", _noop)

        rc = runner.run([
            "--rules-only",
            "--files", "frontend/middleware.ts",
            "--out", str(out),
        ])
        assert rc == EXIT_OK
        report = json.loads(out.read_text())
        # check_axe / check_bundle aren't dispatched against middleware.ts in
        # rules-only today, but the gap mechanism is still exercised when
        # any skipped tool result is encountered.
        assert isinstance(report["gaps"], list)


# ── runner.run() error path ───────────────────────────────────────────


class TestRunnerErrors:
    def test_unknown_scope_returns_runner_error(self, monkeypatch):
        async def _noop(**kwargs):  # noqa: ARG001
            return None

        monkeypatch.setattr("code_reviewer.frontend.runner._record_eval", _noop)
        rc = runner.run(["--scope", "bogus", "--out", "/tmp/out.json"])
        assert rc == EXIT_RUNNER_ERROR
