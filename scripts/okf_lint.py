#!/usr/bin/env python3
"""OKF (Open Knowledge Format) bundle linter.

Checks that the declared knowledge bundles in this repo conform to the OKF
convention pinned in ``docs/CONVENTIONS_OKF.md``:

  * each bundle has an ``index.md`` and a ``log.md`` (FAIL if missing);
  * every authored ``.md`` carries parseable YAML frontmatter with a non-empty
    ``type`` field (WARN — non-blocking, matches OKF's permissive consumer rule
    so we can backfill incrementally);
  * every relative markdown link and ``[[wiki-link]]`` resolves (WARN on a
    broken link — OKF treats a broken link as not-yet-written knowledge, so it
    is surfaced for rot-visibility but does not fail the run).

Generated eval-evidence trees (``*-workspace`` dirs, ``outputs/``, ``run-*/``)
are NOT authored Concepts and are skipped entirely.

Exit code is non-zero only on a hard structural failure: a declared bundle that
does not exist, or a bundle missing its ``index.md`` / ``log.md``.

Pure stdlib, no third-party dependency — mirrors the other standalone utilities
under ``scripts/``. Run from the repo root::

    python scripts/okf_lint.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Bundles we have formally declared as OKF-conformant.
# Add a path here when a directory is promoted to a managed knowledge bundle.
# Note: ``docs/recipes`` itself is NOT listed — it is a bundle-of-bundles with a
# top-level index.md only; its content lives in the five topic sub-bundles below,
# which avoids double-counting the nested recipe files.
DECLARED_BUNDLES: tuple[str, ...] = (
    "docs/skills",
    "research",
    "docs/recipes/gcp",
    "docs/recipes/goaljudge",
    "docs/recipes/governance",
    "docs/recipes/guardrails",
    "docs/recipes/memory_extractor",
    # Phase 3 — rest of docs/ (Stage 3A: zero-coupling bundles)
    "docs/vision",
    "docs/contributing",
    "docs/handbooks",
    "docs/StructuredReasoning",
    "docs/walk-through",
    "docs/deploy",
    # Phase 3 (Stage 3B: test-coupled bundles)
    "docs/explainability",
    "docs/Architectures",
    # Phase 3 (Stage 3C: plan dirs — plans flat; plan multi-level)
    "docs/plans",
    "docs/plan",
    "docs/plan/adapter",
    "docs/plan/frontend",
    "docs/plan/services",
    "docs/plan/sprint",
    "docs/plan/trust",
    # Phase 3 (Stage 3D: relocated root files → thematic bundles)
    "docs/style-guides",
    "docs/guides",
    "docs/analysis",
    "docs/reviews",
    "docs/adr",
)

RESERVED = {"index.md", "log.md", "README.md"}

# Path segments that mark generated eval-evidence / run artifacts rather than
# authored Concepts. Any .md whose relative path contains one of these segments
# is skipped (not linted, not counted).
EVIDENCE_SEGMENTS = ("outputs",)
EVIDENCE_SUFFIXES = ("-workspace",)  # dir-name suffix, e.g. *-workspace
_RUN_DIR = re.compile(r"^run-\d+$")

# Markdown inline link: [text](target).  We ignore anchors and external URLs.
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Wiki link: [[name]] (optionally [[name|alias]]).
_WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# Fenced code block (``` or ~~~) and inline code span (`...`). Stripped before
# link scanning so shell/code syntax like `if [[ -n "$X" ]]` isn't mistaken for
# a wiki-link, and code containing [text](paren) isn't mistaken for a link.
_FENCE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans (link scanning only)."""
    text = _FENCE.sub("", text)
    return _INLINE_CODE.sub("", text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_block(text: str) -> str | None:
    """Return the raw YAML frontmatter block, or None if absent.

    We only need to detect presence of a non-empty ``type:`` key, so a light
    line scan beats pulling in a YAML parser.
    """
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def _has_nonempty_type(frontmatter: str) -> bool:
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("type:"):
            value = stripped[len("type:") :].strip().strip("'\"")
            return bool(value)
    return False


def _is_external(target: str) -> bool:
    target = target.strip()
    return (
        target.startswith(("http://", "https://", "mailto:", "#"))
        or target.startswith("<")  # angle-bracket autolinks / placeholders
    )


def _link_resolves(source: Path, target: str, root: Path) -> bool | None:
    """True/False if a markdown link target exists; None to skip (external/anchor).

    A link counts as resolved if it exists EITHER relative to the source file's
    directory (normal markdown) OR relative to the repo root. Docs frequently
    link source files as ``services/x.py`` (repo-root-relative), which is a valid,
    working reference even though it doesn't resolve from the doc's own folder.
    """
    target = target.split("#", 1)[0].strip()  # drop anchor
    if not target or _is_external(target):
        return None
    if target.startswith("/"):
        return (root / target.lstrip("/")).exists()
    candidates = (
        (source.parent / target),
        (root / target),
    )
    return any(c.exists() for c in candidates)


def _is_evidence(md: Path, bundle_dir: Path) -> bool:
    """True if ``md`` lives in a generated eval-evidence/run-artifact tree."""
    parts = md.relative_to(bundle_dir).parts
    for part in parts:
        if part in EVIDENCE_SEGMENTS or _RUN_DIR.match(part):
            return True
        if any(part.endswith(suffix) for suffix in EVIDENCE_SUFFIXES):
            return True
    return False


def _wiki_name_resolves(name: str, bundle_dir: Path) -> bool:
    """A [[name]] link resolves if ``<name>.md`` exists somewhere in the bundle."""
    name = name.strip()
    if not name:
        return False
    return any(p.stem == name for p in bundle_dir.rglob("*.md"))


def main() -> int:
    root = _repo_root()
    failures: list[str] = []
    warnings: list[str] = []

    for bundle in DECLARED_BUNDLES:
        bundle_dir = root / bundle
        if not bundle_dir.is_dir():
            failures.append(f"{bundle}: declared bundle directory does not exist")
            continue

        for reserved in ("index.md", "log.md"):
            if not (bundle_dir / reserved).is_file():
                failures.append(f"{bundle}: missing required {reserved}")

        # Nested declared bundles own their own files — don't double-lint them
        # when walking a parent bundle (e.g. docs/plan vs docs/plan/adapter).
        nested = tuple(
            root / b
            for b in DECLARED_BUNDLES
            if b != bundle and (root / b).is_relative_to(bundle_dir)
        )

        for md in sorted(bundle_dir.rglob("*.md")):
            if any(md.is_relative_to(n) for n in nested):
                continue  # owned by a deeper declared bundle
            if _is_evidence(md, bundle_dir):
                continue  # generated artifact, not an authored Concept
            rel = md.relative_to(root)
            text = _read(md)

            # type-frontmatter check (WARN only)
            if md.name not in RESERVED:
                fm = _frontmatter_block(text)
                if fm is None or not _has_nonempty_type(fm):
                    warnings.append(f"{rel}: missing non-empty `type` frontmatter")

            # Strip code so shell/code syntax isn't mistaken for a link.
            prose = _strip_code(text)

            # markdown link resolution (WARN on broken — not-yet-written knowledge)
            for target in _MD_LINK.findall(prose):
                ok = _link_resolves(md, target, root)
                if ok is False:
                    warnings.append(f"{rel}: broken link -> {target}")

            # wiki-link resolution (WARN on broken)
            for name in _WIKI_LINK.findall(prose):
                if not _wiki_name_resolves(name, bundle_dir):
                    warnings.append(f"{rel}: broken wiki-link -> [[{name}]]")

    for w in warnings:
        print(f"WARN  {w}")
    for f in failures:
        print(f"FAIL  {f}")

    print(
        f"\nokf_lint: {len(DECLARED_BUNDLES)} bundle(s), "
        f"{len(warnings)} warning(s), {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
