"""L1 deterministic tests for the unified reviewer path router (WI-1).

100% deterministic, no LLM, no network. Verifies the keystone routing seam:
a changed path maps to the right owning folder, language, and nearest-ancestor
``REVIEW.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_reviewer.routing import (
    KNOWN_FOLDERS,
    ROOT_REVIEW_FILE,
    RouteEntry,
    classify_language,
    group_by_rules_file,
    owning_folder,
    resolve_rules_file,
    route,
)


# ── classify_language ────────────────────────────────────────────────


class TestClassifyLanguage:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("trust/models.py", "backend"),
            ("frontend/app/page.tsx", "frontend"),
            ("frontend/lib/wire/events.ts", "frontend"),
            ("frontend/next.config.mjs", "frontend"),
            ("prompts/codeReviewer/v3/system.j2", "other"),
            ("docs/plan/x.md", "other"),
            ("REVIEW.md", "other"),
        ],
    )
    def test_classification(self, path: str, expected: str):
        assert classify_language(path) == expected

    def test_suffix_case_insensitive(self):
        assert classify_language("frontend/App.TSX") == "frontend"
        assert classify_language("trust/Models.PY") == "backend"


# ── owning_folder ────────────────────────────────────────────────────


class TestOwningFolder:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("trust/models.py", "trust"),
            ("services/governance/black_box.py", "services"),
            ("components/router.py", "components"),
            ("orchestration/react_loop.py", "orchestration"),
            ("meta/code_reviewer.py", "meta"),
            ("prompts/codeReviewer/v3/system.j2", "prompts"),
            ("frontend/app/page.tsx", "frontend"),
            ("middleware/server.py", "middleware"),
            ("scripts/hooks/post_edit_ruff.py", "scripts/hooks"),
            ("README.md", ""),
            ("pyproject.toml", ""),
        ],
    )
    def test_longest_prefix_match(self, path: str, expected: str):
        assert owning_folder(path) == expected

    def test_scripts_hooks_beats_scripts(self):
        # scripts/hooks/ is the more specific owner; bare scripts/ is not a
        # known folder so a non-hooks scripts file routes to root.
        assert owning_folder("scripts/hooks/pre_bash_guard.py") == "scripts/hooks"
        assert owning_folder("scripts/deploy_gcp.sh") == ""

    def test_segment_boundary_not_substring(self):
        # "services_old/" must not match the "services" folder.
        assert owning_folder("services_old/legacy.py") == ""

    def test_leading_dot_slash_normalized(self):
        assert owning_folder("./trust/models.py") == "trust"


# ── resolve_rules_file (pure mode, no filesystem) ────────────────────


class TestResolveRulesFilePure:
    def test_folder_maps_to_own_review_md(self):
        assert resolve_rules_file("frontend") == "frontend/REVIEW.md"
        assert resolve_rules_file("trust") == "trust/REVIEW.md"
        assert resolve_rules_file("scripts/hooks") == "scripts/hooks/REVIEW.md"

    def test_root_maps_to_root_review_md(self):
        assert resolve_rules_file("") == ROOT_REVIEW_FILE


# ── resolve_rules_file (on-disk fallback) ────────────────────────────


class TestResolveRulesFileOnDisk:
    def test_nearest_ancestor_when_folder_review_absent(self, tmp_path: Path):
        # Only the root REVIEW.md exists -> a folder with none falls back to root.
        (tmp_path / "REVIEW.md").write_text("# root")
        (tmp_path / "frontend").mkdir()
        assert resolve_rules_file("frontend", repo_root=tmp_path) == "REVIEW.md"

    def test_folder_own_review_preferred(self, tmp_path: Path):
        (tmp_path / "REVIEW.md").write_text("# root")
        (tmp_path / "frontend").mkdir()
        (tmp_path / "frontend" / "REVIEW.md").write_text("# fe")
        assert (
            resolve_rules_file("frontend", repo_root=tmp_path) == "frontend/REVIEW.md"
        )

    def test_root_fallback_even_if_root_review_absent(self, tmp_path: Path):
        # Nothing on disk -> still returns the root REVIEW.md path.
        assert resolve_rules_file("trust", repo_root=tmp_path) == "REVIEW.md"

    def test_nested_folder_walks_up(self, tmp_path: Path):
        # scripts/hooks has no REVIEW.md but root does -> root.
        (tmp_path / "REVIEW.md").write_text("# root")
        (tmp_path / "scripts" / "hooks").mkdir(parents=True)
        assert resolve_rules_file("scripts/hooks", repo_root=tmp_path) == "REVIEW.md"


# ── route (the public seam) ──────────────────────────────────────────


class TestRoute:
    def test_frontend_tsx_routes_to_frontend_fe(self):
        [entry] = route(["frontend/components/Composer.tsx"])
        assert entry == RouteEntry(
            path="frontend/components/Composer.tsx",
            folder="frontend",
            language="frontend",
            rules_file="frontend/REVIEW.md",
        )

    def test_trust_py_routes_to_trust_backend(self):
        [entry] = route(["trust/signature.py"])
        assert entry.folder == "trust"
        assert entry.language == "backend"
        assert entry.rules_file == "trust/REVIEW.md"

    def test_root_file_routes_to_root_review(self):
        [entry] = route(["pyproject.toml"])
        assert entry.folder == ""
        assert entry.language == "other"
        assert entry.rules_file == ROOT_REVIEW_FILE

    def test_blank_paths_skipped(self):
        assert route(["", "   ", "trust/x.py"]) == [
            RouteEntry("trust/x.py", "trust", "backend", "trust/REVIEW.md")
        ]

    def test_order_preserved(self):
        entries = route(["frontend/a.tsx", "trust/b.py", "meta/c.py"])
        assert [e.folder for e in entries] == ["frontend", "trust", "meta"]

    def test_known_folders_all_route_to_themselves(self):
        # Every known folder routes a representative file to its own REVIEW.md.
        for folder in KNOWN_FOLDERS:
            sample = f"{folder}/sample.py"
            [entry] = route([sample])
            assert entry.folder == folder
            assert entry.rules_file == f"{folder}/REVIEW.md"


# ── group_by_rules_file ──────────────────────────────────────────────


class TestGroupByRulesFile:
    def test_groups_share_one_rules_file(self):
        entries = route(
            [
                "frontend/a.tsx",
                "frontend/b.ts",
                "trust/c.py",
            ]
        )
        grouped = group_by_rules_file(entries)
        assert set(grouped) == {"frontend/REVIEW.md", "trust/REVIEW.md"}
        assert len(grouped["frontend/REVIEW.md"]) == 2
        assert len(grouped["trust/REVIEW.md"]) == 1

    def test_first_appearance_order_preserved(self):
        entries = route(["meta/a.py", "trust/b.py", "meta/c.py"])
        grouped = group_by_rules_file(entries)
        assert list(grouped) == ["meta/REVIEW.md", "trust/REVIEW.md"]

    def test_empty_input_returns_empty(self):
        assert group_by_rules_file([]) == {}

    def test_within_group_order_matches_input(self):
        # Entries sharing a rules_file must appear in the group in input order,
        # not deduplicated or reordered — the v3 submission renders them in that
        # order and the reviewer reads top-to-bottom.
        entries = route(
            ["trust/zeta.py", "frontend/a.tsx", "trust/alpha.py", "trust/mid.py"]
        )
        grouped = group_by_rules_file(entries)
        trust_paths = [e.path for e in grouped["trust/REVIEW.md"]]
        assert trust_paths == ["trust/zeta.py", "trust/alpha.py", "trust/mid.py"]


# ── route() with repo_root (the production integration path) ──────────
#
# `meta/code_reviewer._build_routed_groups` calls `route(..., repo_root=AGENT_ROOT)`,
# so the on-disk rules_file resolution is load-bearing. The pure-mode TestRoute
# class above does not exercise it; these do.


class TestRouteWithRepoRoot:
    def test_mixed_on_disk_resolution(self, tmp_path: Path):
        # frontend has its own REVIEW.md; trust does not -> falls back to root.
        (tmp_path / "REVIEW.md").write_text("# root")
        (tmp_path / "frontend").mkdir()
        (tmp_path / "frontend" / "REVIEW.md").write_text("# fe")
        (tmp_path / "trust").mkdir()
        (tmp_path / "trust" / "models.py").write_text("# trust")

        entries = route(
            ["frontend/a.tsx", "trust/b.py", "pyproject.toml"],
            repo_root=tmp_path,
        )
        assert entries == [
            RouteEntry("frontend/a.tsx", "frontend", "frontend", "frontend/REVIEW.md"),
            RouteEntry("trust/b.py", "trust", "backend", "REVIEW.md"),
            RouteEntry("pyproject.toml", "", "other", "REVIEW.md"),
        ]

    def test_all_folders_fall_back_to_root_when_only_root_exists(self, tmp_path: Path):
        (tmp_path / "REVIEW.md").write_text("# root")
        for folder in KNOWN_FOLDERS:
            (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        entries = route(
            [f"{folder}/x.py" for folder in KNOWN_FOLDERS],
            repo_root=tmp_path,
        )
        assert {e.rules_file for e in entries} == {"REVIEW.md"}

    def test_repo_root_does_not_change_folder_or_language(self, tmp_path: Path):
        # repo_root only affects rules_file resolution; folder + language stay
        # purely path-derived.
        (tmp_path / "REVIEW.md").write_text("# root")
        [entry] = route(["frontend/app/page.tsx"], repo_root=tmp_path)
        assert entry.folder == "frontend"
        assert entry.language == "frontend"


# ── route() input normalization (defensive paths production relies on) ──


class TestRouteNormalization:
    def test_empty_input_returns_empty(self):
        assert route([]) == []

    def test_backslashes_normalized_to_posix(self):
        [entry] = route(["trust\\models.py"])
        assert entry.path == "trust/models.py"
        assert entry.folder == "trust"

    def test_leading_slash_stripped(self):
        [entry] = route(["/trust/models.py"])
        assert entry.path == "trust/models.py"
        assert entry.folder == "trust"

    def test_repeated_dot_slash_collapsed(self):
        [entry] = route(["././trust/models.py"])
        assert entry.path == "trust/models.py"
        assert entry.folder == "trust"

    def test_whitespace_stripped(self):
        [entry] = route(["  trust/models.py  "])
        assert entry.path == "trust/models.py"
        assert entry.folder == "trust"


# ── RouteEntry frozen contract ────────────────────────────────────────


class TestRouteEntryFrozen:
    def test_entry_is_immutable(self):
        [entry] = route(["trust/models.py"])
        with pytest.raises(Exception):  # FrozenInstanceError (dataclasses)
            entry.folder = "frontend"  # type: ignore[misc]

    def test_entries_equal_when_fields_equal(self):
        # Value equality is what makes group_by_rules_file + merge logic safe.
        a = RouteEntry("trust/x.py", "trust", "backend", "trust/REVIEW.md")
        b = RouteEntry("trust/x.py", "trust", "backend", "trust/REVIEW.md")
        assert a == b
        assert hash(a) == hash(b)
