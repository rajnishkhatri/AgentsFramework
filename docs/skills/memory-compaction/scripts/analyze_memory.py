#!/usr/bin/env python3
"""Analyze a Claude Code MEMORY.md index for compaction.

MEMORY.md is the always-loaded memory index: it is re-injected into context at the
start of every session for a project, and any session can append to it. It only ever
grows, so it drifts over budget silently. The harness truncates the load past a hard
limit (~24.4 KB), which *silently hides* every memory below the cut line — the topic
files still exist but nothing points to them, so recall never reaches them.

This script does the deterministic measurement so the skill doesn't re-derive it by
hand each time: total size, per-line hook lengths (by CHARACTER, not byte — the index
is full of multi-byte UTF-8 like — → ≤ § × that inflate byte counts ~1.5x), dangling
links, orphan topic files, and entries that self-mark as resolved/superseded (prune
candidates). It writes a JSON report to stdout; the skill reads it to plan edits.

Usage:
    python analyze_memory.py [MEMORY_DIR]

MEMORY_DIR defaults to the directory resolved from the current Claude Code project
(see resolve_memory_dir). Pass it explicitly when you already know the path.
"""

from __future__ import annotations

import json
import os
import re
import sys

# An index line is a markdown list item. The canonical shape is:
#   - [Title](topic-file.md) — hook text
# but a line may intentionally carry no .md link (e.g. it points at a repo doc in
# plain text). We treat the text after the first " — " (em dash) as the hook.
LIST_RE = re.compile(r"^- ")
LINK_RE = re.compile(r"\]\(([A-Za-z0-9._-]+\.md)\)")
HOOK_SPLIT = " — "  # em dash, the convention separator between title and hook

# Phrases an entry uses to mark itself done — strong signal it's a prune candidate.
RESOLVED_MARKERS = ("RESOLVED", "SUPERSEDED", "superseded", "DEPRECATED")

HOOK_SOFT_LIMIT = 120  # target ceiling for a hook (characters)
HOOK_HARD_LIMIT = 150  # never exceed


def resolve_memory_dir(explicit: str | None = None) -> str:
    """Find the project's memory directory.

    Claude Code stores per-project memory at
    ~/.claude/projects/<encoded-cwd>/memory/, where <encoded-cwd> is the absolute
    project path with every '/' replaced by '-'. We derive it from CLAUDE_PROJECT_DIR
    (set by the harness) or the current working directory, so the skill stays portable
    across projects instead of hardcoding one path.
    """
    if explicit:
        return explicit
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    encoded = project.replace("/", "-")
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "projects", encoded, "memory")


def extract_hook(line: str) -> str:
    """Return the hook text (everything after the title/link, then the em-dash).

    Titles themselves can contain an em dash (e.g. "Cloudflare removed — BFF on Cloud
    Run"), so we can't just split on the first " — ". Anchor on the end of the
    `](file.md)` link first; if there's no link (a deliberately plain-text entry),
    fall back to the first separator after the `[Title]` bracket.
    """
    m = LINK_RE.search(line)
    rest = line[m.end() :] if m else line
    idx = rest.find(HOOK_SPLIT)
    return rest[idx + len(HOOK_SPLIT) :].strip() if idx != -1 else ""


def analyze(memory_dir: str) -> dict:
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    if not os.path.isfile(memory_md):
        return {
            "error": f"MEMORY.md not found at {memory_md}",
            "memory_dir": memory_dir,
        }

    with open(memory_md, encoding="utf-8") as fh:
        raw = fh.read()
    size_bytes = len(raw.encode("utf-8"))
    lines = raw.splitlines()
    items = [ln for ln in lines if LIST_RE.match(ln)]

    # Per-line hook measurement (by character).
    long_hooks = []
    hook_lengths = []
    for ln in items:
        hook = extract_hook(ln)
        n = len(hook)
        hook_lengths.append(n)
        if n > HOOK_HARD_LIMIT:
            long_hooks.append({"chars": n, "line": ln})

    # Links referenced in the index, and which ones dangle (no file on disk).
    linked = []
    for ln in items:
        linked.extend(LINK_RE.findall(ln))
    linked_set = set(linked)
    dangling = sorted(
        f for f in linked_set if not os.path.isfile(os.path.join(memory_dir, f))
    )
    duplicate_links = sorted(f for f in linked_set if linked.count(f) > 1)

    # Topic files on disk that the index never points to (orphans = unreachable detail).
    topic_files = [
        f for f in os.listdir(memory_dir) if f.endswith(".md") and f != "MEMORY.md"
    ]
    orphans = sorted(f for f in topic_files if f not in linked_set)

    # Prune candidates: index entries that self-describe as resolved/superseded.
    resolved = [
        {"line": ln, "markers": [m for m in RESOLVED_MARKERS if m in ln]}
        for ln in items
        if any(m in ln for m in RESOLVED_MARKERS)
    ]

    avg_hook = round(sum(hook_lengths) / len(hook_lengths)) if hook_lengths else 0

    return {
        "memory_dir": memory_dir,
        "memory_md": memory_md,
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 1),
        "entry_count": len(items),
        "topic_file_count": len(topic_files),
        "hook_avg_chars": avg_hook,
        "hook_max_chars": max(hook_lengths) if hook_lengths else 0,
        "hooks_over_soft": sum(1 for n in hook_lengths if n > HOOK_SOFT_LIMIT),
        "hooks_over_hard": len(long_hooks),
        "long_hooks": long_hooks,
        "dangling_links": dangling,
        "duplicate_links": duplicate_links,
        "orphan_topic_files": orphans,
        "resolved_candidates": resolved,
    }


def main() -> int:
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    report = analyze(resolve_memory_dir(explicit))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
