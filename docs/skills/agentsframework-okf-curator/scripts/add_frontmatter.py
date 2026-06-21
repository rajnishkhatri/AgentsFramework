#!/usr/bin/env python3
"""Prepend OKF `type`/`title`/`description`/`tags` frontmatter to markdown Concepts.

Design goals (hard-won from the docs/ OKF conversion):
  * **Pure prepend** — the existing body (H1 and everything after) is left
    byte-identical. The script asserts this invariant before writing.
  * **Idempotent** — a file that already starts with `---` is skipped, so you can
    re-run after adding a few new files.
  * **Clean descriptions** — markdown links in the source prose are reduced to their
    text and truncation happens on a word boundary, so a half-a-link never leaks into
    frontmatter (which would then pollute the catalog and trip the linter).

`title`  := the file's first `# ` H1 (fallback: filename stem).
`description` := first non-empty, non-heading prose line, normalized, ≤180 chars.
Per-file `type` overrides: `--override RELPATH=type` (repeatable), relative to TARGET.

If a file already HAS frontmatter but no `type` (e.g. a native plan-mode file with
`name:`/`overview:`/`todos:`), use --insert-type-if-missing to insert a single
`type:` key into the existing block instead of skipping — never wrap or clobber.

Usage:
    python add_frontmatter.py docs/recipes/gcp --type runbook --tag "recipe, gcp"
    python add_frontmatter.py docs/plans --type plan --tag plan --insert-type-if-missing
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RESERVED = {"index.md", "log.md", "README.md"}


def _h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _description(text: str, fallback: str) -> str:
    in_fence = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith(("#", ">", "|", "---", "- ", "* ", "<!--")):
            continue
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)            # bold
        line = re.sub(r"`([^`]+)`", r"\1", line)                # inline code
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)    # md link -> text
        line = line.replace("[", "").replace("]", "")
        sentence = re.split(r"(?<=[.!?])\s", line)[0]
        if len(sentence) > 180:
            sentence = sentence[:180].rsplit(" ", 1)[0]
        return sentence.rstrip()
    return fallback


def _yaml_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _block_bounds(text: str) -> tuple[int, int] | None:
    if not text.startswith("---\n"):
        return None
    try:
        return 4, text.index("\n---\n", 3)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="dir (recursed) relative to cwd")
    ap.add_argument("--type", required=True)
    ap.add_argument("--tag", required=True, help="comma-joined tag list, e.g. 'recipe, gcp'")
    ap.add_argument("--override", action="append", default=[], help="RELPATH=type")
    ap.add_argument("--no-recurse", action="store_true")
    ap.add_argument("--insert-type-if-missing", action="store_true",
                    help="for files with frontmatter lacking `type`, insert a type key")
    args = ap.parse_args()

    overrides = dict(ov.split("=", 1) for ov in args.override)
    base = Path(args.target)
    if not base.is_dir():
        print(f"ERROR: {args.target} is not a directory")
        return 1

    md_iter = base.glob("*.md") if args.no_recurse else base.rglob("*.md")
    patched = skipped = inserted = 0
    for md in sorted(md_iter):
        if md.name in RESERVED:
            continue
        text = md.read_text(encoding="utf-8")
        rel = str(md.relative_to(base))
        ctype = overrides.get(rel, args.type)

        bounds = _block_bounds(text)
        if bounds is not None:
            if not args.insert_type_if_missing:
                skipped += 1
                continue
            start, end = bounds
            block = text[start:end]
            if any(l.strip().startswith("type:") for l in block.splitlines()):
                skipped += 1
                continue
            md.write_text(text[:start] + f"type: {ctype}\n" + text[start:], encoding="utf-8")
            inserted += 1
            continue

        title = _h1(text) or md.stem
        desc = _description(text, title)
        fm = (
            "---\n"
            f"type: {ctype}\n"
            f"title: {_yaml_quote(title)}\n"
            f"description: {_yaml_quote(desc)}\n"
            f"tags: [{args.tag}]\n"
            "---\n\n"
        )
        new_text = fm + text
        assert new_text.endswith(text), "pure-prepend invariant violated"
        md.write_text(new_text, encoding="utf-8")
        patched += 1

    print(f"{args.target}: prepended={patched} type-inserted={inserted} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
