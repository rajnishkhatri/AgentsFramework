"""L2 parity tests for the Cursor ``.cursor/rules/*.mdc`` dispatch surface (WI-7).

These guards pin the Cursor side of the unified, context-routed reviewer to the
same content chain the Claude Code skill + ``meta/code_reviewer.py`` v3 path use:

- every folder the deterministic router knows (``routing.KNOWN_FOLDERS``) has a
  matching ``.mdc`` whose ``globs`` auto-attaches for that subtree;
- each ``.mdc`` body is a **thin pointer** — it names the folder's ``REVIEW.md``
  and the canonical dispatch CLI, and it does **not** restate rule prose (no
  rule tables, no ``AGENTS.md`` content duplication);
- the root ``code-review-dispatch.mdc`` is Agent-Requested (rich description,
  no globs, ``alwaysApply: false``) and covers the root fallback case;
- the dispatch command is identical across every ``.mdc`` (single source of
  truth, no drift).

Rationale: ``REVIEW.md`` cites ``AGENTS.md``; ``.mdc`` points at ``REVIEW.md``.
Three thin layers, one content source (``AGENTS.md``). If a ``.mdc`` starts
restating rule prose, or its glob drifts off the router's owning-folder set,
the path-routing parity with the CLI reviewer breaks silently — these tests
catch that.

Stdlib-only frontmatter parser (no pyyaml dependency) so the guard is portable
and matches the cite-lint philosophy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from code_reviewer import routing

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / ".cursor" / "rules"

# Folder → .mdc slug. ``scripts/hooks`` maps to the ``hooks-review.mdc`` filename
# (the on-disk folder name with a slash would be an awkward filename; the slug
# drops the parent). Every other folder uses its own name as the slug.
FOLDER_TO_SLUG: dict[str, str] = {
    "scripts/hooks": "hooks",
    "trust": "trust",
    "services": "services",
    "components": "components",
    "orchestration": "orchestration",
    "meta": "meta",
    "prompts": "prompts",
    "frontend": "frontend",
    "middleware": "middleware",
}

ROOT_DISPATCH_MDC = "code-review-dispatch.mdc"
ALL_MDC_NAMES = [
    *(f"{FOLDER_TO_SLUG[f]}-review.mdc" for f in routing.KNOWN_FOLDERS)
] + [ROOT_DISPATCH_MDC]
CANONICAL_DISPATCH_CMD = (
    "python -m meta.code_reviewer --from-git-diff --git-base HEAD "
    "--prompt-version v3 --output review.json"
)


# ── Stdlib frontmatter parser ───────────────────────────────────────


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split a ``.mdc`` into (frontmatter dict, body).

    Frontmatter is the YAML-ish block between the first two ``---`` fences.
    The parser handles the flat ``key: value`` shape Cursor ``.mdc`` files use:
    ``alwaysApply`` (bool), ``globs`` (string or inline list), ``description``
    (string, may span the rest of the line). Raises ``ValueError`` if the file
    has no frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening '---' frontmatter fence")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("missing closing '---' frontmatter fence") from exc

    fm: dict[str, object] = {}
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"malformed frontmatter line: {raw!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            fm[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        elif value.lower() in {"true", "false"}:
            fm[key] = value.lower() == "true"
        else:
            fm[key] = value.strip("\"'")
    body = "\n".join(lines[end + 1 :])
    return fm, body


def _load_mdc(name: str) -> tuple[dict[str, object], str, Path]:
    path = RULES_DIR / name
    if not path.is_file():
        pytest.fail(f".mdc missing: {path}")
    fm, body = _parse_frontmatter(path.read_text())
    return fm, body, path


def _join_continuations(body: str) -> str:
    """Join shell-style backslash line continuations so a multi-line command in
    a fenced block matches its single-line canonical form. Consumes the
    whitespace around the backslash so ``HEAD \\n    --x`` → ``HEAD --x``."""
    return re.sub(r"\s*\\\s*\n\s*", " ", body)


def _folder_mdc_name(folder: str) -> str:
    return f"{FOLDER_TO_SLUG[folder]}-review.mdc"


# ── Per-folder coverage ─────────────────────────────────────────────


class TestPerFolderMdcCoverage:
    def test_every_known_folder_has_an_mdc(self):
        missing = [
            f
            for f in routing.KNOWN_FOLDERS
            if not (RULES_DIR / _folder_mdc_name(f)).is_file()
        ]
        assert not missing, f"folders without a .mdc: {missing}"

    def test_no_extra_folder_mdcs_outside_known_set(self):
        known = {_folder_mdc_name(f) for f in routing.KNOWN_FOLDERS}
        known.add(ROOT_DISPATCH_MDC)
        extras = [p.name for p in RULES_DIR.glob("*-review.mdc") if p.name not in known]
        # A folder-named *-review.mdc that isn't in the known set would silently
        # advertise a REVIEW.md the router never routes to.
        assert not extras, f"unexpected *-review.mdc files: {extras}"

    def test_folder_to_slug_covers_every_known_folder(self):
        # If a new folder is added to routing.KNOWN_FOLDERS without a slug here,
        # the parity surface silently drops it. This test makes that loud.
        assert set(routing.KNOWN_FOLDERS) == set(FOLDER_TO_SLUG), (
            "FOLDER_TO_SLUG is out of sync with routing.KNOWN_FOLDERS — "
            f"missing: {set(routing.KNOWN_FOLDERS) - set(FOLDER_TO_SLUG)}; "
            f"stale: {set(FOLDER_TO_SLUG) - set(routing.KNOWN_FOLDERS)}"
        )


# ── Frontmatter shape ───────────────────────────────────────────────


class TestFrontmatterShape:
    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_always_apply_is_false(self, folder: str):
        fm, _, _ = _load_mdc(_folder_mdc_name(folder))
        assert fm.get("alwaysApply") is False, (
            f"{folder}: per-folder .mdc must be auto-attached (alwaysApply: false), "
            "not always-apply (context bloat on every session)"
        )

    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_has_globs(self, folder: str):
        fm, _, _ = _load_mdc(_folder_mdc_name(folder))
        globs = fm.get("globs")
        assert globs, f"{folder}: per-folder .mdc must have globs to auto-attach"

    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_has_description(self, folder: str):
        fm, _, _ = _load_mdc(_folder_mdc_name(folder))
        desc = fm.get("description")
        assert isinstance(desc, str) and desc.strip(), (
            f"{folder}: per-folder .mdc needs a non-empty description "
            "(Cursor uses it for Agent-Requested fallback)"
        )

    def test_root_dispatch_is_agent_requested(self):
        fm, _, _ = _load_mdc(ROOT_DISPATCH_MDC)
        assert fm.get("alwaysApply") is False, (
            "root dispatch .mdc must not be always-apply (context bloat)"
        )
        assert "globs" not in fm, (
            "root dispatch .mdc is Agent-Requested (description-driven); "
            "it must not carry globs"
        )
        desc = fm.get("description")
        assert isinstance(desc, str) and len(desc) > 40, (
            "root dispatch .mdc needs a rich description so Cursor loads it "
            "on 'review my changes' requests"
        )


# ── Glob → owning-folder parity (the keystone tie) ──────────────────


class TestGlobMatchesOwningFolder:
    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_glob_prefix_is_folder_subtree(self, folder: str):
        fm, _, _ = _load_mdc(_folder_mdc_name(folder))
        globs = fm["globs"]
        patterns = globs if isinstance(globs, list) else [globs]
        # Every glob pattern must be rooted at the owning folder, e.g.
        # ``frontend/**`` for frontend/, ``scripts/hooks/**`` for scripts/hooks/.
        for pat in patterns:
            assert pat.startswith(f"{folder}/") or pat == folder, (
                f"{folder}: glob {pat!r} is not rooted at the owning folder"
            )

    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_glob_subtree_matches_router_owning_folder(self, folder: str):
        # Cross-check with the deterministic router: a sample path inside the
        # folder's subtree must route back to that folder, and the .mdc's glob
        # must cover that same subtree. This ties the Cursor surface to the
        # keystone so the two cannot drift.
        sample = f"{folder}/sample_file.py"
        assert routing.owning_folder(sample) == folder, (
            f"router does not own {sample} as {folder!r} — router/.mdc mismatch"
        )
        fm, _, _ = _load_mdc(_folder_mdc_name(folder))
        globs = fm["globs"]
        patterns = globs if isinstance(globs, list) else [globs]
        # The glob must match the sample path's prefix.
        assert any(
            sample.startswith(p.rstrip("/*") + "/") or p == folder for p in patterns
        ), f"{folder}: no glob pattern covers the router-owned sample {sample}"


# ── Thin-pointer contract (cite, never copy) ────────────────────────


class TestThinPointer:
    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_body_points_at_folder_review_md(self, folder: str):
        _, body, _ = _load_mdc(_folder_mdc_name(folder))
        expected_review = f"{folder}/REVIEW.md"
        assert expected_review in body, (
            f"{folder}: .mdc body must point at {expected_review}"
        )

    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_body_does_not_restate_rule_prose(self, folder: str):
        _, body, _ = _load_mdc(_folder_mdc_name(folder))
        # A rule table (markdown pipe table) in a .mdc means rule prose has
        # leaked into the path-pointer layer — the cite-don't-copy invariant.
        assert "| rule_id |" not in body, (
            f"{folder}: .mdc restates a rule table — it must cite REVIEW.md, not copy it"
        )
        assert "|---|" not in body, (
            f"{folder}: .mdc contains a markdown table — thin pointer only, no prose"
        )

    def test_root_dispatch_does_not_restate_rule_prose(self):
        _, body, _ = _load_mdc(ROOT_DISPATCH_MDC)
        assert "| rule_id |" not in body
        assert "|---|" not in body


# ── Dispatch command parity (single source of truth) ────────────────


class TestDispatchCommand:
    @pytest.mark.parametrize("name", ALL_MDC_NAMES)
    def test_canonical_dispatch_command_present(self, name: str):
        _, body, _ = _load_mdc(name)
        normalized = _join_continuations(body)
        assert CANONICAL_DISPATCH_CMD in normalized, (
            f"{name}: canonical dispatch command missing or drifted. "
            f"Expected: {CANONICAL_DISPATCH_CMD!r}"
        )

    def test_dispatch_command_is_identical_across_all_mdcs(self):
        # No .mdc may carry a divergent invocation (e.g. a different
        # --prompt-version or a stray --llm baked in) — that would silently
        # split the dispatch surface.
        for name in ALL_MDC_NAMES:
            _, body, _ = _load_mdc(name)
            normalized = _join_continuations(body)
            # Reject a v2/v1 invocation sneaking in alongside the canonical one.
            for bad in ("--prompt-version v2", "--prompt-version v1"):
                assert bad not in normalized, (
                    f"{name}: found legacy {bad!r} — v3 is the unified path"
                )

    @pytest.mark.parametrize("folder", list(routing.KNOWN_FOLDERS))
    def test_body_states_honest_limit(self, folder: str):
        _, body, _ = _load_mdc(_folder_mdc_name(folder))
        # The WI-8 honest limit must appear so the .mdc never over-promises
        # gate-grade LLM verdicts.
        assert "WI-8" in body and "gate-grade" in body, (
            f"{folder}: .mdc must state the WI-8 honest limit on LLM verdicts"
        )


# ── hooks.json: no per-edit reviewer hook (deterministic-first) ─────


class TestHooksJsonDispatchDecision:
    def test_hooks_json_documents_no_per_edit_reviewer_hook(self):
        import json

        hooks = json.loads((REPO_ROOT / ".cursor" / "hooks.json").read_text())
        comment = hooks.get("_comment_wi7", "")
        assert "WI-7" in comment and "WI-8" in comment, (
            ".cursor/hooks.json must document the WI-7 decision (no per-edit "
            "reviewer hook; LLM verdicts not gate-grade until WI-8)"
        )

    def test_hooks_json_has_no_reviewer_hook_entry(self):
        import json

        hooks = json.loads((REPO_ROOT / ".cursor" / "hooks.json").read_text())
        all_hooks = []
        for entries in hooks.get("hooks", {}).values():
            all_hooks.extend(entries)
        for entry in all_hooks:
            cmd = entry.get("command", "")
            # The reviewer must not be wired as a per-edit/per-shell hook —
            # it's dispatched on demand via the CLI pointed at by the .mdc files.
            assert "meta.code_reviewer" not in cmd, (
                f"reviewer wired as a hook ({cmd!r}) — deterministic-first: "
                "no un-validated LLM judge on every keystroke"
            )
