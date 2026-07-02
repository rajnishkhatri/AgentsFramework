#!/usr/bin/env python3
"""Relocate docs and rewrite EVERY reference to them, safely.

Moving a doc is the one OKF operation that can silently break things: links that
point AT it, and the moved file's OWN outbound relative links, all shift. This
tool moves files and rewrites both directions, by RESOLVED TARGET (not blind
string replace), covering the three reference forms that bit us in practice:
  1. markdown links            `[text](path)` / `[text](../path)`
  2. agent context @-mentions  `@docs/NAME.md`  (LOAD-BEARING in AGENTS.md)
  3. bare path mentions        `docs/NAME.md`, `agent/docs/NAME.md`

Always dry-run first (`--plan`). Untracked files fall back to a plain `mv` when
`git mv` fails. After applying, verify with `git status` rename count + a repo-wide
grep that no reference resolves to an OLD location.

Move spec: repeatable `--move OLD_RELPATH=NEW_RELPATH`, both relative to `docs/`.

Usage:
    python relocate.py --plan  --move STYLE_GUIDE_LAYERING.md=style-guides/STYLE_GUIDE_LAYERING.md
    python relocate.py --apply --move STYLE_GUIDE_LAYERING.md=style-guides/STYLE_GUIDE_LAYERING.md \
                               --move USER_MANUAL.md=guides/USER_MANUAL.md
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

DOCS = Path("docs")
SCAN_SUFFIXES = {".py", ".md", ".ts", ".tsx", ".json", ".toml", ".txt", ".yml", ".yaml"}
SKIP_DIRS = {"node_modules", ".venv", ".git", "__pycache__", ".next", "dist", "build"}

_MD_LINK = re.compile(r"(?<!\!)(\[[^\]]*\]\()([^)]+)(\))")
_AT_MENTION = re.compile(r"@((?:agent/)?docs/[A-Za-z0-9_./-]+\.md)")
_BARE_DOCS = re.compile(r"(?<![\w@.])((?:agent/)?docs/[A-Za-z0-9_./-]+\.md)")


def _iter_text_files():
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if Path(fn).suffix in SCAN_SUFFIXES:
                yield Path(dirpath) / fn


def _docs_rel(token: str) -> str | None:
    """Strip optional `agent/` prefix; return the docs-relative path or None."""
    t = token
    if t.startswith("agent/docs/"):
        return t[len("agent/docs/") :]
    if t.startswith("docs/"):
        return t[len("docs/") :]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--plan", action="store_true", help="dry run (default)")
    g.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--move",
        action="append",
        default=[],
        required=True,
        help="OLD=NEW, both relative to docs/",
    )
    args = ap.parse_args()

    old2new = dict(m.split("=", 1) for m in args.move)
    apply = args.apply

    def resolves_to_moved(source: Path, target: str) -> str | None:
        raw = target.split("#", 1)[0].strip()
        if not raw or raw.startswith(("http://", "https://", "mailto:", "#", "<")):
            return None
        for base in (source.parent, Path(".")):
            try:
                rel = (base / raw).resolve().relative_to(DOCS.resolve()).as_posix()
            except (ValueError, OSError):
                continue
            if rel in old2new:
                return rel
        dr = _docs_rel(raw)
        return dr if dr in old2new else None

    # census
    refs: dict[str, set[str]] = {o: set() for o in old2new}
    for f in _iter_text_files():
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in _MD_LINK.finditer(text):
            o = resolves_to_moved(f, m.group(2))
            if o:
                refs[o].add(str(f))
        for rx in (_AT_MENTION, _BARE_DOCS):
            for m in rx.finditer(text):
                dr = _docs_rel(m.group(1))
                if dr in old2new:
                    refs[dr].add(str(f))

    print("== MOVE MAP ==")
    for o, n in old2new.items():
        print(f"  docs/{o:42} -> docs/{n}   ({len(refs[o])} referencing files)")
    if not apply:
        print("\n(plan only; re-run with --apply)")
        return 0

    # move (git mv; plain mv fallback for untracked); idempotent
    for o, n in old2new.items():
        (DOCS / n).parent.mkdir(parents=True, exist_ok=True)
        src, dst = DOCS / o, DOCS / n
        if dst.exists() and not src.exists():
            continue
        if not src.exists():
            print(f"  WARN missing source: docs/{o}")
            continue
        r = subprocess.run(
            ["git", "mv", str(src), str(dst)], capture_output=True, text=True
        )
        if r.returncode != 0:
            src.rename(dst)
            print(f"  (untracked) mv docs/{o} -> docs/{n}")

    # rewrite inbound refs (everywhere) + outbound refs (in the moved files)
    def rewrite(path: Path) -> bool:
        text = path.read_text(encoding="utf-8")
        orig = text

        def md_sub(m):
            target = m.group(2)
            o = resolves_to_moved(path, target)
            if not o:
                return m.group(0)
            anchor = "#" + target.split("#", 1)[1] if "#" in target else ""
            new_target = os.path.relpath(DOCS / old2new[o], path.parent) + anchor
            return m.group(1) + new_target + m.group(3)

        def at_sub(m):
            dr = _docs_rel(m.group(1))
            return f"@docs/{old2new[dr]}" if dr in old2new else m.group(0)

        def bare_sub(m):
            tok, dr = m.group(1), _docs_rel(m.group(1))
            if dr not in old2new:
                return m.group(0)
            prefix = "agent/docs/" if tok.startswith("agent/") else "docs/"
            return prefix + old2new[dr]

        text = _MD_LINK.sub(md_sub, text)
        text = _AT_MENTION.sub(at_sub, text)
        text = _BARE_DOCS.sub(bare_sub, text)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            return True
        return False

    # also fix the moved files' OWN outbound relative links (depth changed)
    for o, n in old2new.items():
        moved = DOCS / n
        if not moved.exists():
            continue
        text = moved.read_text(encoding="utf-8")
        old_parent = (DOCS / o).parent

        def out_sub(m):
            target = m.group(2)
            raw = target.split("#", 1)[0]
            anchor = target[len(raw) :]
            if not raw or raw.startswith(("http", "mailto:", "#", "/", "<")):
                return m.group(0)
            old_abs = (old_parent / raw).resolve()
            if not old_abs.exists():
                return m.group(0)
            new_rel = os.path.relpath(old_abs, moved.parent)
            return (
                m.group(1) + new_rel + anchor + m.group(3)
                if new_rel != raw
                else m.group(0)
            )

        new_text = _MD_LINK.sub(out_sub, text)
        if new_text != text:
            moved.write_text(new_text, encoding="utf-8")

    changed = sum(rewrite(f) for f in _iter_text_files())
    print(
        f"\nmoved={len(old2new)}; rewrote inbound references in {changed} files "
        "(outbound links in moved files fixed separately)"
    )
    print(
        "VERIFY: git status rename count, then grep that no ref resolves to an OLD path, "
        "then `python scripts/okf_lint.py`."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
