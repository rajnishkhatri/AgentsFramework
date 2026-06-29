"""L2 tests for the REVIEW.md scaffolding + drift helper (P1-3).

Pins three contracts:

1. ``discover_rule_tokens`` agrees with ``cite_lint._RULE_TOKEN`` on what counts
   as a rule token (the two tools cannot disagree).
2. ``scaffold_review_md`` emits a thin, parseable, cite-don't-copy skeleton that
   the cite-lint itself accepts, and refuses to overwrite an existing map.
3. ``review_md_drift`` reports AGENTS.md rule tokens not yet cited, and treats
   root invariants as cited-by-default so they don't masquerade as drift for
   every folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_reviewer.cite_lint import lint_review_file, parse_cites
from code_reviewer.review_scaffold import (
    RuleToken,
    discover_root_invariants,
    discover_rule_tokens,
    main,
    review_md_drift,
    scaffold_review_md,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── discover_rule_tokens ─────────────────────────────────────────────


class TestDiscoverRuleTokens:
    def test_finds_all_token_families(self, tmp_path: Path):
        agents = tmp_path / "trust" / "AGENTS.md"
        agents.parent.mkdir()
        agents.write_text(
            "## What belongs here\n"
            "Putting a service-specific type here is anti-pattern AP-1.\n"
            "## G4 — comprehension gate\n"
            "G4 content.\n"
            "## L1 testing\n"
            "TAP-1 and TAP-4 apply.\n"
            "TRUST_PURITY.no_io is enforced.\n"
            "FD1 also mentioned for cross-reference.\n"
        )
        tokens = discover_rule_tokens(agents, repo_root=tmp_path)
        ids = [t.token for t in tokens]
        assert ids == ["AP-1", "G4", "TAP-1", "TAP-4", "TRUST_PURITY.no_io", "FD1"]

    def test_dedup_by_token_first_appearance_order(self, tmp_path: Path):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("AP-1 first.\nAP-1 again later.\nAP-2 after.\n")
        tokens = discover_rule_tokens(agents, repo_root=tmp_path)
        assert [t.token for t in tokens] == ["AP-1", "AP-2"]

    def test_context_is_nearest_preceding_heading(self, tmp_path: Path):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Section A\nAP-1 here.\n### Subsection\nAP-2 here.\n")
        tokens = discover_rule_tokens(agents, repo_root=tmp_path)
        by_token = {t.token: t.context for t in tokens}
        assert by_token["AP-1"] == "Section A"
        assert by_token["AP-2"] == "Subsection"

    def test_missing_agents_returns_empty(self, tmp_path: Path):
        assert (
            discover_rule_tokens(tmp_path / "nope" / "AGENTS.md", repo_root=tmp_path)
            == []
        )

    def test_source_label_for_folder_and_root(self, tmp_path: Path):
        (tmp_path / "trust").mkdir()
        folder_agents = tmp_path / "trust" / "AGENTS.md"
        folder_agents.write_text("AP-1.\n")
        # Root AGENTS.md with a literal token (the numbered "N." invariant
        # form is discovered by discover_root_invariants, not here — that
        # split is intentional and tested in TestDiscoverRootInvariants).
        (tmp_path / "AGENTS.md").write_text("ADR.1 ask-first.\n")

        [folder_tok] = discover_rule_tokens(folder_agents, repo_root=tmp_path)
        assert folder_tok.source == "trust/AGENTS.md"

        root_tokens = discover_rule_tokens(tmp_path / "AGENTS.md", repo_root=tmp_path)
        assert root_tokens and root_tokens[0].source == "root AGENTS.md"


class TestDiscoverRootInvariants:
    def test_extracts_numbered_invariants(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants — STRICTLY ENFORCED\n\n"
            "1. **Dependencies flow downward only.**\n"
            "2. **Trust kernel has ZERO outward dependencies.**\n"
            "3. **Components are framework-agnostic.**\n"
        )
        out = discover_root_invariants(tmp_path)
        assert [t.token for t in out] == [
            "Invariant #1",
            "Invariant #2",
            "Invariant #3",
        ]
        assert all(t.source == "root AGENTS.md" for t in out)
        assert all(t.context == "Architecture Invariants" for t in out)

    def test_no_invariants_heading_returns_empty(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text("1. **Some other numbered list.**\n")
        assert discover_root_invariants(tmp_path) == []

    def test_missing_root_agents_returns_empty(self, tmp_path: Path):
        assert discover_root_invariants(tmp_path) == []


# ── scaffold_review_md ──────────────────────────────────────────────


class TestScaffoldReviewMd:
    def _setup_repo(self, root: Path) -> Path:
        (root / "AGENTS.md").write_text(
            "# Architecture Invariants — STRICTLY ENFORCED\n\n"
            "1. **Dependencies flow downward only.**\n"
            "2. **Trust kernel has ZERO outward dependencies.**\n"
        )
        trust = root / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text(
            "## What belongs here\n"
            "AP-1 anti-pattern.\n"
            "## G4\n"
            "G4 gate.\n"
            "## L1 testing\n"
            "TAP-1 and TAP-4.\n"
        )
        return trust

    def test_skeleton_has_header_and_one_row_per_token(self, tmp_path: Path):
        trust = self._setup_repo(tmp_path)
        text = scaffold_review_md(trust, repo_root=tmp_path)
        assert text.startswith("# trust/ — Reviewer Enforcement Map")
        # AP-1, G4, TAP-1, TAP-4 from trust/AGENTS.md + Invariant #1, #2 from root.
        review = tmp_path / "trust" / "REVIEW.md"
        review.write_text(text)
        cite_tokens = [c.token for c in parse_cites(review, repo_root=tmp_path)]
        assert set(cite_tokens) == {
            "AP-1",
            "G4",
            "TAP-1",
            "TAP-4",
            "Invariant #1",
            "Invariant #2",
        }

    def test_skeleton_passes_cite_lint(self, tmp_path: Path):
        # The scaffold must produce a map that the cite-lint itself accepts —
        # otherwise the bootstrap hands the author a file that fails the gate.
        trust = self._setup_repo(tmp_path)
        text = scaffold_review_md(trust, repo_root=tmp_path)
        review = tmp_path / "trust" / "REVIEW.md"
        review.write_text(text)
        violations = lint_review_file(review, repo_root=tmp_path)
        assert not violations, "scaffolded REVIEW.md failed cite_lint:\n" + "\n".join(
            f"  {v.rule_id} -> {v.source} ({v.reason})" for v in violations
        )

    def test_placeholder_columns_present_and_unfilled(self, tmp_path: Path):
        trust = self._setup_repo(tmp_path)
        text = scaffold_review_md(trust, repo_root=tmp_path)
        # Every data row carries the LLM / warning / — placeholders so the
        # author can grep for what still needs curation.
        review = tmp_path / "trust" / "REVIEW.md"
        review.write_text(text)
        rows = [
            line
            for line in text.splitlines()
            if line.startswith("| ") and "rule_id" not in line and "---" not in line
        ]
        assert rows, "scaffold produced no data rows"
        for row in rows:
            assert "| LLM | warning | — |" in row, f"row missing placeholders: {row}"

    def test_does_not_fold_root_invariants_twice_when_already_in_folder_agents(
        self, tmp_path: Path
    ):
        # If a folder AGENTS.md literally restates "Invariant #1", we must not
        # duplicate it in the scaffold (dedup by token).
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("Inline (Invariant #1) restated.\nAP-1.\n")
        text = scaffold_review_md(trust, repo_root=tmp_path)
        review = trust / "REVIEW.md"
        review.write_text(text)
        tokens = [c.token for c in parse_cites(review, repo_root=tmp_path)]
        assert tokens.count("Invariant #1") == 1
        assert "AP-1" in tokens

    def test_root_folder_scaffold_uses_root_agents(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n## Decision records\n"
            "ADR.1 ask-first. G1 new-abstraction.\n"
        )
        text = scaffold_review_md(tmp_path, repo_root=tmp_path)
        review = tmp_path / "REVIEW.md"
        review.write_text(text)
        tokens = [c.token for c in parse_cites(review, repo_root=tmp_path)]
        assert "Invariant #1" in tokens
        assert "ADR.1" in tokens
        assert "G1" in tokens


# ── review_md_drift ─────────────────────────────────────────────────


class TestReviewMdDrift:
    def test_no_drift_when_all_folder_rules_cited(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("## Rules\nAP-1. AP-2.\n")
        (trust / "REVIEW.md").write_text(
            "# Map\n\n"
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md §Rules | LLM | warning | D4 |\n"
            "| AP-2 | trust/AGENTS.md §Rules | LLM | warning | D4 |\n"
        )
        assert review_md_drift(trust / "REVIEW.md", repo_root=tmp_path) == []

    def test_drift_reports_uncited_tokens(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("## Rules\nAP-1. AP-2. AP-3.\n")
        (trust / "REVIEW.md").write_text(
            "# Map\n\n"
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md §Rules | LLM | warning | D4 |\n"
        )
        drift = review_md_drift(trust / "REVIEW.md", repo_root=tmp_path)
        assert [t.token for t in drift] == ["AP-2", "AP-3"]

    def test_root_invariants_not_reported_as_drift(self, tmp_path: Path):
        # Root invariants live in root AGENTS.md, not the sibling — they must
        # not show up as drift for every folder that doesn't re-cite them.
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n2. **Trust zero.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1.\n")
        (trust / "REVIEW.md").write_text(
            "# Map\n\n"
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md | LLM | warning | D4 |\n"
        )
        drift = review_md_drift(trust / "REVIEW.md", repo_root=tmp_path)
        assert drift == []

    def test_no_sibling_agents_returns_empty(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text("# x\n1. **y.**\n")
        folder = tmp_path / "lonely"
        folder.mkdir()
        (folder / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| Invariant #1 | root AGENTS.md | AST | critical | D1 |\n"
        )
        assert review_md_drift(folder / "REVIEW.md", repo_root=tmp_path) == []


# ── CLI ─────────────────────────────────────────────────────────────


class TestReviewScaffoldCli:
    def _setup_repo(self, root: Path) -> Path:
        (root / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = root / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1. G4.\n")
        return trust

    def test_folder_writes_scaffold_when_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        self._setup_repo(tmp_path)
        assert main(["--root", str(tmp_path), "--folder", "trust"]) == 0
        out = capsys.readouterr().out
        assert "scaffolded trust/REVIEW.md" in out
        review = tmp_path / "trust" / "REVIEW.md"
        assert review.is_file()
        # The written file must pass cite_lint (bootstrap does not hand the
        # author a file that fails the gate).
        assert not lint_review_file(review, repo_root=tmp_path)

    def test_folder_refuses_to_overwrite(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        trust = self._setup_repo(tmp_path)
        review = trust / "REVIEW.md"
        review.write_text("# hand-curated map\n")
        assert main(["--root", str(tmp_path), "--folder", "trust"]) == 1
        out = capsys.readouterr().out
        assert "refusing to overwrite" in out
        assert review.read_text() == "# hand-curated map\n"

    def test_folder_missing_dir_reports_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        (tmp_path / "AGENTS.md").write_text("# x\n")
        assert main(["--root", str(tmp_path), "--folder", "nope"]) == 1
        out = capsys.readouterr().out
        assert "folder not found" in out

    def test_folder_accepts_absolute_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        trust = self._setup_repo(tmp_path)
        assert main(["--root", str(tmp_path), "--folder", str(trust)]) == 0
        out = capsys.readouterr().out
        assert "scaffolded" in out
        assert (trust / "REVIEW.md").is_file()

    def test_check_reports_drift_and_exits_zero_by_default(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1. AP-2. AP-3.\n")
        (trust / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md | LLM | warning | D4 |\n"
        )
        # Also a clean folder to prove the report distinguishes.
        services = tmp_path / "services"
        services.mkdir()
        (services / "AGENTS.md").write_text("H1.\n")
        (services / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| H1 | services/AGENTS.md | LLM | warning | D5 |\n"
        )
        assert main(["--root", str(tmp_path), "--check"]) == 0
        out = capsys.readouterr().out
        assert "AP-2" in out and "AP-3" in out
        assert "drift token(s)" in out
        assert "no drift" in out  # the services folder line

    def test_check_strict_exits_one_on_drift(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1. AP-2.\n")
        (trust / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md | LLM | warning | D4 |\n"
        )
        assert main(["--root", str(tmp_path), "--check", "--strict"]) == 1

    def test_check_no_drift_exits_zero_clean_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1.\n")
        (trust / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md | LLM | warning | D4 |\n"
        )
        assert main(["--root", str(tmp_path), "--check"]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out and "0 drift" in out

    def test_check_empty_root_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        assert main(["--root", str(tmp_path), "--check"]) == 0
        out = capsys.readouterr().out
        assert "no REVIEW.md files found" in out

    def test_check_strict_clean_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        # --strict with no drift is still exit 0 (strict only escalates drift).
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        trust = tmp_path / "trust"
        trust.mkdir()
        (trust / "AGENTS.md").write_text("AP-1.\n")
        (trust / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | trust/AGENTS.md | LLM | warning | D4 |\n"
        )
        assert main(["--root", str(tmp_path), "--check", "--strict"]) == 0

    def test_folder_and_check_are_mutually_exclusive(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        with pytest.raises(SystemExit) as exc:
            main(["--root", str(tmp_path), "--folder", "trust", "--check"])
        # argparse exits 2 on usage errors.
        assert exc.value.code == 2

    def test_no_mode_is_required(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        with pytest.raises(SystemExit) as exc:
            main(["--root", str(tmp_path)])
        assert exc.value.code == 2


# ── Real-repo smoke (the existing REVIEW.md / AGENTS.md pairs) ──────


class TestRealRepoDrift:
    """Smoke against the actual repo: every existing REVIEW.md must parse and
    its drift report must be obtainable without crashing. We do NOT assert
    zero drift here — drift is informational curation, not a gate (the hard
    gate is cite_lint, tested in test_review_md_cites.py)."""

    def test_drift_runs_for_every_existing_review_md(self):
        from code_reviewer.cite_lint import find_review_files

        review_paths = find_review_files(REPO_ROOT)
        assert review_paths, "expected the repo to have REVIEW.md files"
        for review_path in review_paths:
            # Must not raise; result is informational.
            drift = review_md_drift(review_path, repo_root=REPO_ROOT)
            assert isinstance(drift, list)
            for t in drift:
                assert isinstance(t, RuleToken)
                assert t.source.endswith("AGENTS.md")
