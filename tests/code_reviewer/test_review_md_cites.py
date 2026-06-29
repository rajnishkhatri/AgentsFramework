"""L2 cite-resolves lint for every REVIEW.md enforcement map (WI-2 verification).

Every ``rule_id`` cited in a ``REVIEW.md`` must resolve to a real token in the
``AGENTS.md`` named by its ``source`` column. A dangling cite is a lint failure
(plan §6 gotcha). Also asserts the cite-don't-copy invariant by spot-checking
that the authored REVIEW.md files exist and are non-trivial.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_reviewer.cite_lint import (
    _source_folder,
    detect_mojibake,
    find_review_files,
    lint_encoding,
    lint_review_file,
    main,
    parse_cites,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_REVIEW_FOLDERS = {
    "REVIEW.md",
    "trust/REVIEW.md",
    "services/REVIEW.md",
    "components/REVIEW.md",
    "orchestration/REVIEW.md",
    "meta/REVIEW.md",
    "prompts/REVIEW.md",
    "frontend/REVIEW.md",
    "middleware/REVIEW.md",
    "scripts/hooks/REVIEW.md",
}


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def test_all_expected_review_files_exist():
    found = {_rel(p) for p in find_review_files(REPO_ROOT)}
    missing = EXPECTED_REVIEW_FOLDERS - found
    assert not missing, f"Missing REVIEW.md enforcement maps: {sorted(missing)}"


@pytest.mark.parametrize(
    "rel_path",
    sorted(EXPECTED_REVIEW_FOLDERS),
)
def test_every_cite_resolves(rel_path: str):
    review_path = REPO_ROOT / rel_path
    violations = lint_review_file(review_path, repo_root=REPO_ROOT)
    assert not violations, "Unresolved cites:\n" + "\n".join(
        f"  {v.review_file}: {v.rule_id} -> {v.source} ({v.reason})" for v in violations
    )


@pytest.mark.parametrize(
    "rel_path",
    sorted(EXPECTED_REVIEW_FOLDERS),
)
def test_review_file_has_cites(rel_path: str):
    review_path = REPO_ROOT / rel_path
    cites = parse_cites(review_path, repo_root=REPO_ROOT)
    assert cites, f"{rel_path} has no parseable rule_id|source cite table"


def test_repo_wide_lint_clean():
    """No REVIEW.md anywhere in the repo has a dangling cite."""
    all_violations = []
    for review_path in find_review_files(REPO_ROOT):
        all_violations.extend(lint_review_file(review_path, repo_root=REPO_ROOT))
    assert not all_violations, "Repo-wide cite violations:\n" + "\n".join(
        f"  {v.review_file}: {v.rule_id} -> {v.source} ({v.reason})"
        for v in all_violations
    )


def test_parse_cites_handles_multiple_tables(tmp_path: Path):
    """parse_cites must collect rows from *every* qualifying table in a REVIEW.md.

    Regression guard: an earlier version broke out of the scan after the first
    table ended, so the root REVIEW.md's "ADR ratchet" table (ADR.1 / G1 / G8)
    was silently skipped — a false-green that hid the very cite WI-5 claimed to
    make mechanically checkable.
    """
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Architecture Invariants\n"
        "1. **Dependencies flow downward only.**\n"
        "## Decision records\n"
        "ADR.1 — Ask first. G1 — new-abstraction gate. G8 — test-mass-rewrite gate.\n"
    )
    review = tmp_path / "REVIEW.md"
    review.write_text(
        "# Map\n\n"
        "## Always-on\n\n"
        "| rule_id | source | detection | severity | reviewer dimension |\n"
        "|---|---|---|---|---|\n"
        "| Invariant #1 | AGENTS.md §Architecture Invariants | AST | critical | D1 |\n"
        "\n"
        "## ADR ratchet\n\n"
        "| rule_id | source | detection | severity | reviewer dimension |\n"
        "|---|---|---|---|---|\n"
        "| ADR.1 | AGENTS.md §Decision records | AST | warning | D2 |\n"
        "| G1 | AGENTS.md §Decision records | LLM | warning | D2 |\n"
        "| G8 | AGENTS.md §Decision records | LLM | warning | D3 |\n"
    )
    cites = parse_cites(review, repo_root=tmp_path)
    tokens = [c.token for c in cites]
    assert "Invariant #1" in tokens
    assert "ADR.1" in tokens, "parse_cites skipped the second table (regression)"
    assert "G1" in tokens
    assert "G8" in tokens
    # And every cite resolves cleanly.
    assert not lint_review_file(review, repo_root=tmp_path)


# ── CLI (main / `python -m code_reviewer.cite_lint`) ──────────────────
#
# P1-2: the module used to have no __main__ block, so
# `python -m code_reviewer.cite_lint` imported and exited 0 *without linting
# anything* — a false-green a hook or CI would read as "clean". These tests
# pin the real CLI contract: --root discovery, --files subset, exit codes,
# and the default-cwd behavior.


def _write_clean_repo(root: Path) -> None:
    """Build a minimal repo whose single REVIEW.md cites resolve cleanly."""
    (root / "AGENTS.md").write_text(
        "# Architecture Invariants\n1. **Dependencies flow downward only.**\n"
    )
    (root / "REVIEW.md").write_text(
        "# Map\n\n"
        "| rule_id | source | detection | severity | reviewer dimension |\n"
        "|---|---|---|---|---|\n"
        "| Invariant #1 | root AGENTS.md §Architecture Invariants | AST | critical | D1 |\n"
    )


def _write_dirty_repo(root: Path) -> None:
    """Build a repo whose REVIEW.md cites a token absent from AGENTS.md."""
    (root / "AGENTS.md").write_text(
        "# Architecture Invariants\n1. **Downward only.**\n"
    )
    (root / "REVIEW.md").write_text(
        "# Map\n\n"
        "| rule_id | source | detection | severity | reviewer dimension |\n"
        "|---|---|---|---|---|\n"
        "| G42 | root AGENTS.md §Decision records | LLM | warning | D2 |\n"
    )


class TestCiteLintCli:
    def test_clean_repo_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        _write_clean_repo(tmp_path)
        assert main(["--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out
        assert "0 cite violations" in out

    def test_dirty_repo_exits_one_and_reports(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        _write_dirty_repo(tmp_path)
        assert main(["--root", str(tmp_path)]) == 1
        out = capsys.readouterr().out
        assert "G42" in out
        assert "1 cite violation" in out

    def test_files_subset_skips_dirty_sibling(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        # Two REVIEW.md files: one clean (trust), one dirty (root). Passing
        # --files pointing only at the clean one must exit 0 — proving --files
        # restricts scope rather than always discovering everything.
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Downward only.**\n"
        )
        (tmp_path / "trust").mkdir()
        (tmp_path / "trust" / "AGENTS.md").write_text("# Trust\nTRUST_PURITY.no_io.\n")
        (tmp_path / "trust" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| TRUST_PURITY.no_io | AGENTS.md §Trust | AST | critical | D1 |\n"
        )
        (tmp_path / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| G42 | root AGENTS.md §Decision records | LLM | warning | D2 |\n"
        )
        assert main(["--root", str(tmp_path), "--files", "trust/REVIEW.md"]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out
        assert "G42" not in out

    def test_files_missing_path_counted_as_violation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        # A --files path that doesn't exist must not crash; it's reported and
        # counted so CI sees a non-zero exit rather than a traceback.
        (tmp_path / "AGENTS.md").write_text("# x\n")
        assert main(["--root", str(tmp_path), "--files", "nope/REVIEW.md"]) == 1
        out = capsys.readouterr().out
        assert "file not found" in out

    def test_empty_root_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        # No REVIEW.md anywhere under root -> nothing to lint, exit 0 (not an
        # error). Distinguish from the silent-no-op bug: we print a message.
        assert main(["--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "no REVIEW.md files found" in out

    def test_default_root_is_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        # With no --root, the CLI lints cwd. Guards against a regression where
        # the default silently points somewhere unexpected.
        _write_clean_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert main([]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out

    def test_files_absolute_path_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ):
        _write_clean_repo(tmp_path)
        review = tmp_path / "REVIEW.md"
        assert main(["--root", str(tmp_path), "--files", str(review)]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out


# ── Cross-folder cite guard (P2-11) ────────────────────────────────────
#
# A per-folder REVIEW.md must cite its *own* folder's AGENTS.md or the root
# AGENTS.md — never another folder's. Citing e.g. trust/AGENTS.md from
# meta/REVIEW.md breaks locality: the folder's enforcement map should
# depend only on its own rules plus the inter-layer invariants owned by
# root. This guards the class of bug the unified-reviewer critical review
# flagged as P2-11.


class TestCrossFolderCiteGuard:
    def test_source_folder_resolves_own_bare_agents(self, tmp_path: Path):
        """A bare ``AGENTS.md`` cite resolves to the REVIEW.md's own folder."""
        (tmp_path / "meta").mkdir()
        review = tmp_path / "meta" / "REVIEW.md"
        assert (
            _source_folder("AGENTS.md §L4 testing rules", review, repo_root=tmp_path)
            == "meta"
        )

    def test_source_folder_resolves_explicit_folder(self, tmp_path: Path):
        """``meta/AGENTS.md §...`` resolves to ``meta`` regardless of REVIEW.md location."""
        review = tmp_path / "meta" / "REVIEW.md"
        assert (
            _source_folder(
                "meta/AGENTS.md §L4 testing rules", review, repo_root=tmp_path
            )
            == "meta"
        )

    def test_source_folder_resolves_root_qualifier(self, tmp_path: Path):
        """``root AGENTS.md`` resolves to ``""`` (the repo root) from any folder."""
        (tmp_path / "meta").mkdir()
        review = tmp_path / "meta" / "REVIEW.md"
        assert (
            _source_folder(
                "root AGENTS.md §Architecture Invariants", review, repo_root=tmp_path
            )
            == ""
        )

    def test_source_folder_root_review_bare_agents_is_root(self, tmp_path: Path):
        """The root REVIEW.md's bare ``AGENTS.md`` cite resolves to ``""`` (root),
        not ``"."`` — so it doesn't false-trigger as a cross-folder cite."""
        review = tmp_path / "REVIEW.md"
        assert (
            _source_folder(
                "AGENTS.md §Architecture Invariants", review, repo_root=tmp_path
            )
            == ""
        )

    def test_cross_folder_cite_is_flagged(self, tmp_path: Path):
        """meta/REVIEW.md citing trust/AGENTS.md is a cross-folder violation."""
        (tmp_path / "AGENTS.md").write_text("# root\n")
        (tmp_path / "trust").mkdir()
        (tmp_path / "trust" / "AGENTS.md").write_text(
            "# Trust\nTAP-4 failure paths first.\n"
        )
        (tmp_path / "meta").mkdir()
        (tmp_path / "meta" / "AGENTS.md").write_text(
            "# Meta\nTAP-4 failure paths first (meta).\n"
        )
        (tmp_path / "meta" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| TAP-4 (failure paths first) | trust/AGENTS.md §L1 testing rules | AST | warning | D3 |\n"
        )
        violations = lint_review_file(
            tmp_path / "meta" / "REVIEW.md", repo_root=tmp_path
        )
        assert len(violations) == 1
        assert "cross-folder" in violations[0].reason
        assert "trust" in violations[0].reason

    def test_own_folder_cite_is_clean(self, tmp_path: Path):
        """meta/REVIEW.md citing meta/AGENTS.md is clean (locality holds)."""
        (tmp_path / "meta").mkdir()
        (tmp_path / "meta" / "AGENTS.md").write_text(
            "# Meta\nTAP-4 failure paths first.\n"
        )
        (tmp_path / "meta" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| TAP-4 (failure paths first) | meta/AGENTS.md §L4 testing rules | AST | warning | D3 |\n"
        )
        violations = lint_review_file(
            tmp_path / "meta" / "REVIEW.md", repo_root=tmp_path
        )
        assert violations == []

    def test_root_cite_from_nested_folder_is_clean(self, tmp_path: Path):
        """A nested folder may always cite root AGENTS.md (inter-layer invariants)."""
        (tmp_path / "AGENTS.md").write_text(
            "# Architecture Invariants\n1. **Dependencies flow downward only.**\n"
        )
        (tmp_path / "meta").mkdir()
        (tmp_path / "meta" / "AGENTS.md").write_text("# Meta\n")
        (tmp_path / "meta" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| Invariant #1 | root AGENTS.md §Architecture Invariants | AST | critical | D1 |\n"
        )
        violations = lint_review_file(
            tmp_path / "meta" / "REVIEW.md", repo_root=tmp_path
        )
        assert violations == []


# ── Mojibake / encoding guard (P3) ─────────────────────────────────────
#
# A REVIEW.md or AGENTS.md round-tripped through the wrong codec silently
# corrupts the section markers the cite-lint depends on: ``§`` becomes
# ``Â§`` (Latin-1 of UTF-8), ``?`` (lossy ASCII placeholder), or U+FFFD.
# These tests pin the detector's high-confidence signals.


class TestMojibakeGuard:
    def test_replacement_char_is_flagged(self):
        assert detect_mojibake("foo \ufffd bar") == ["U+FFFD replacement char x1"]

    def test_latin1_of_utf8_bigram_is_flagged(self):
        # `§` (U+00A7, UTF-8 0xC2 0xA7) mis-decoded as Latin-1 -> `Â§`.
        defects = detect_mojibake("AGENTS.md \xc2\xa7 Anti-patterns")
        assert len(defects) == 1
        assert "mojibake bigram" in defects[0]
        assert "Â§" in defects[0]

    def test_emdash_mojibake_fragment_is_flagged(self):
        # `—` (U+2014, UTF-8 0xE2 0x80 0x94) mis-decoded -> `â€"`.
        defects = detect_mojibake("title \u00e2\u20ac\u2014 text")
        assert any("â€" in d for d in defects)

    def test_clean_text_with_section_and_emdash_is_clean(self):
        """Genuine UTF-8 ``§`` and ``—`` must NOT be flagged — the detector
        catches the *mis-decoded* forms, not the correct ones."""
        assert detect_mojibake("clean text with \u00a7 and \u2014 only") == []

    def test_lone_lead_char_without_nonascii_follower_is_clean(self):
        """A lone ``Â`` (no following non-ASCII) is not flagged — avoids false
        positives on legit names that happen to contain a C1 letter."""
        assert detect_mojibake("a plain \u00c2 in ascii context") == []

    def test_invalid_utf8_bytes_are_flagged(self, tmp_path: Path):
        f = tmp_path / "bad.md"
        f.write_bytes(b"good \xff\xfe bad bytes")
        defects = lint_encoding(f)
        assert any("invalid UTF-8" in d for d in defects)

    def test_lost_section_marker_placeholder_is_flagged(self, tmp_path: Path):
        """A REVIEW.md source cell ``services/AGENTS.md ?Anti-patterns`` — the
        ``?`` is a lossy-ASCII placeholder for ``§``. ``lint_review_file``
        catches it via the encoding pass."""
        (tmp_path / "AGENTS.md").write_text("# root\n")
        (tmp_path / "services").mkdir()
        (tmp_path / "services" / "AGENTS.md").write_text(
            "# Services\nAP-1 trust types.\n"
        )
        (tmp_path / "services" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| AP-1 | services/AGENTS.md ?Anti-patterns | LLM | warning | D4 |\n"
        )
        violations = lint_review_file(
            tmp_path / "services" / "REVIEW.md", repo_root=tmp_path
        )
        enc = [v for v in violations if v.rule_id == "<encoding>"]
        assert enc, (
            f"expected an encoding violation; got {[v.reason for v in violations]}"
        )
        assert "lost section marker" in enc[0].reason

    def test_mojibake_in_review_md_is_reported_as_encoding_violation(
        self, tmp_path: Path
    ):
        """A REVIEW.md containing U+FFFD is flagged by ``lint_review_file``."""
        (tmp_path / "AGENTS.md").write_text("# root\n1. **Downward only.**\n")
        (tmp_path / "REVIEW.md").write_text(
            "# Map \ufffd\n\n"
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| Invariant #1 | root AGENTS.md \u00a7Architecture Invariants | AST | critical | D1 |\n"
        )
        violations = lint_review_file(tmp_path / "REVIEW.md", repo_root=tmp_path)
        enc = [v for v in violations if v.rule_id == "<encoding>"]
        assert enc and any("U+FFFD" in v.reason for v in enc)

    def test_main_flags_mojibake_in_agents_md(self, tmp_path: Path, capsys):
        """``main`` scans every AGENTS.md under root for mojibake — a corrupted
        source-of-truth file is caught in the same CLI pass as cite lint."""
        (tmp_path / "AGENTS.md").write_text("# root\n1. **Downward only.**\n")
        (tmp_path / "trust").mkdir()
        # Mojibake `Â§` on disk: the text "Â§" encoded as UTF-8 is bytes
        # `\xc3\x82\xc2\xa7`. (This is what a `§` round-tripped through
        # Latin-1 looks like once re-saved as UTF-8.)
        (tmp_path / "trust" / "AGENTS.md").write_text(
            "# Trust\nTAP-4 failure paths first \u00c2\u00a7 L1.\n"
        )
        (tmp_path / "trust" / "REVIEW.md").write_text(
            "| rule_id | source | detection | severity | reviewer dimension |\n"
            "|---|---|---|---|---|\n"
            "| TAP-4 | trust/AGENTS.md \u00a7L1 testing rules | AST | warning | D3 |\n"
        )
        assert main(["--root", str(tmp_path)]) == 1
        out = capsys.readouterr().out
        assert "trust/AGENTS.md" in out
        assert "mojibake" in out

    def test_clean_repo_still_clean_with_encoding_scan(self, tmp_path: Path, capsys):
        """A repo with correct UTF-8 throughout passes the encoding scan too."""
        _write_clean_repo(tmp_path)
        assert main(["--root", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "clean:" in out
