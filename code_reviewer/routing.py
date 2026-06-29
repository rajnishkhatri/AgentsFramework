"""Deterministic path router for the unified, context-routed code reviewer.

WI-1 of ``docs/plan/unified_context_routed_reviewer.plan.md`` — the keystone.

Given a set of changed paths (``git diff --name-only`` output), this module
maps each path to its **owning folder**, the **nearest ancestor ``REVIEW.md``**
enforcement map, and a coarse **language** classification (backend Python vs.
frontend TS/TSX). The reviewer dispatch surfaces (Claude Code skill, Cursor
``.mdc`` globs) and ``meta/code_reviewer.py`` / the frontend runner all call
this single seam so routing is defined in exactly one place.

Design constraints (from the plan §6 Gotchas):

- **Deterministic and L1-pure.** No LLM, no network, no I/O beyond a single
  ``Path.exists()`` probe to resolve the nearest ``REVIEW.md``. An LLM router
  would reintroduce the un-validated-judge problem the whole plan avoids.
- **Stdlib only.** Imports nothing from ``services/``, ``components/``,
  ``trust/``, or any third-party package — only ``pathlib`` + ``dataclasses``
  + ``typing``. This keeps the module importable by both runners and any hook
  without dragging in the four-layer dependency graph.

The ``REVIEW.md`` files themselves are authored in WI-2; this router resolves
*which* one applies even before they all exist (it falls back to the root
``REVIEW.md`` for any folder without its own).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# ── Known owning folders ────────────────────────────────────────────
# Ordered longest-prefix-first so ``scripts/hooks/x.py`` matches
# ``scripts/hooks`` before any shorter prefix. Each entry is a repo-relative
# POSIX prefix. ``""`` (root) is the implicit fallback and is NOT listed here.
KNOWN_FOLDERS: tuple[str, ...] = (
    "scripts/hooks",
    "trust",
    "services",
    "components",
    "orchestration",
    "meta",
    "prompts",
    "frontend",
    "middleware",
)

# Language classification by file suffix. Anything not matched is "other"
# (e.g. ``.md``, ``.json``, ``.yml``) — routed for structural/ADR checks but
# not for language-specific review dimensions.
_BACKEND_SUFFIXES = frozenset({".py"})
_FRONTEND_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})

ROOT_REVIEW_FILE = "REVIEW.md"


@dataclass(frozen=True)
class RouteEntry:
    """One changed path mapped to its review context.

    Attributes:
        path: The original changed path, normalized to POSIX form.
        folder: The owning folder prefix (one of ``KNOWN_FOLDERS``), or
            ``""`` for repo-root files.
        language: ``"backend"`` (Python), ``"frontend"`` (TS/JS), or
            ``"other"``.
        rules_file: Repo-relative path to the nearest-ancestor ``REVIEW.md``
            that governs this path. Always a string; never ``None`` — the root
            ``REVIEW.md`` is the universal fallback even if it does not yet
            exist on disk.
    """

    path: str
    folder: str
    language: str
    rules_file: str


def classify_language(path: str) -> str:
    """Classify a path as ``backend``, ``frontend``, or ``other`` by suffix."""
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in _BACKEND_SUFFIXES:
        return "backend"
    if suffix in _FRONTEND_SUFFIXES:
        return "frontend"
    return "other"


def owning_folder(path: str) -> str:
    """Return the longest known-folder prefix that owns ``path``.

    Matching is on path *segments*, so ``services_old/x.py`` does NOT match
    the ``services`` folder. Returns ``""`` (root) when no known folder owns
    the path.
    """
    norm = PurePosixPath(_normalize(path))
    parts = norm.parts
    best = ""
    for folder in KNOWN_FOLDERS:
        folder_parts = PurePosixPath(folder).parts
        if parts[: len(folder_parts)] == folder_parts:
            # Longest-prefix wins (more segments = more specific).
            if len(folder_parts) > len(PurePosixPath(best).parts) or best == "":
                best = folder
    return best


def resolve_rules_file(
    folder: str,
    *,
    repo_root: Path | None = None,
) -> str:
    """Resolve the nearest-ancestor ``REVIEW.md`` for an owning folder.

    Walks from ``folder`` up to the repo root, returning the first
    ``<dir>/REVIEW.md`` that exists on disk. Falls back to the root
    ``REVIEW.md`` (always, even if absent) so the reviewer always has a
    rules file to load.

    When ``repo_root`` is ``None`` the existence probe is skipped and the
    function returns the *expected* path for the folder (folder's own
    ``REVIEW.md`` if a folder is given, else root). This keeps the function
    usable as a pure mapping in unit tests that do not touch the filesystem.
    """
    if not folder:
        return ROOT_REVIEW_FILE

    candidate_dirs = _ancestor_dirs(folder)

    if repo_root is None:
        # Pure mode: the folder's own REVIEW.md is the expected rules file.
        return f"{folder}/{ROOT_REVIEW_FILE}"

    for rel_dir in candidate_dirs:
        rel = ROOT_REVIEW_FILE if rel_dir == "" else f"{rel_dir}/{ROOT_REVIEW_FILE}"
        if (repo_root / rel).is_file():
            return rel
    return ROOT_REVIEW_FILE


def route(
    paths: list[str],
    *,
    repo_root: Path | None = None,
) -> list[RouteEntry]:
    """Map each changed path to its review context.

    This is the seam the dispatch surfaces call. Pure given ``repo_root``
    (it only probes for ``REVIEW.md`` existence, never reads file contents).

    Args:
        paths: Changed paths, typically ``git diff --name-only`` output.
        repo_root: Repo root for resolving the nearest on-disk ``REVIEW.md``.
            When ``None``, ``rules_file`` is the folder's expected
            ``REVIEW.md`` (or root for root files) without an existence probe.

    Returns:
        One ``RouteEntry`` per input path, in input order. Empty/blank paths
        are skipped.
    """
    entries: list[RouteEntry] = []
    for raw in paths:
        norm = _normalize(raw)
        if not norm:
            continue
        folder = owning_folder(norm)
        entries.append(
            RouteEntry(
                path=norm,
                folder=folder,
                language=classify_language(norm),
                rules_file=resolve_rules_file(folder, repo_root=repo_root),
            )
        )
    return entries


def group_by_rules_file(entries: list[RouteEntry]) -> dict[str, list[RouteEntry]]:
    """Group routed entries by their ``rules_file``.

    The reviewer runs once per ``REVIEW.md`` group, loading that enforcement
    map and reviewing all the files it governs together. Insertion order of
    first appearance is preserved (Python dict ordering).
    """
    grouped: dict[str, list[RouteEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.rules_file, []).append(entry)
    return grouped


# ── Private helpers ─────────────────────────────────────────────────


def _normalize(path: str) -> str:
    """Normalize a changed path to a clean repo-relative POSIX string."""
    if path is None:
        return ""
    text = str(path).strip().replace("\\", "/")
    # Strip a leading "./" and any leading slash; collapse trivial cases.
    while text.startswith("./"):
        text = text[2:]
    text = text.lstrip("/")
    return text


def _ancestor_dirs(folder: str) -> list[str]:
    """Return ``folder`` and each ancestor dir down to root ("")."""
    dirs: list[str] = []
    current = PurePosixPath(folder)
    while True:
        dirs.append(str(current) if str(current) != "." else "")
        if str(current) in (".", ""):
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    if "" not in dirs:
        dirs.append("")
    return dirs


__all__ = [
    "RouteEntry",
    "KNOWN_FOLDERS",
    "ROOT_REVIEW_FILE",
    "classify_language",
    "owning_folder",
    "resolve_rules_file",
    "route",
    "group_by_rules_file",
]
