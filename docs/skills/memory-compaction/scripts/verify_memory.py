#!/usr/bin/env python3
"""Verify a compacted MEMORY.md against the budget + integrity contract.

Run this AFTER re-hooking/pruning. It is the gate that proves the compaction was
lossless and effective. Every check that matters for "did we break recall?" lives
here, so the skill never has to eyeball it.

Measures hooks by CHARACTER (the index is full of multi-byte UTF-8 — → ≤ § × that
make byte-length overstate things ~1.5x; counting bytes was the trap that produced
false 'too long' failures during manual compaction).

Usage:
    python verify_memory.py [MEMORY_DIR] [--target-kb 12]

Exit code 0 = all checks pass; 1 = at least one failure.
"""
from __future__ import annotations

import os
import re
import sys

LIST_RE = re.compile(r"^- ")
LINK_RE = re.compile(r"\]\(([A-Za-z0-9._-]+\.md)\)")
HOOK_SPLIT = " — "
HOOK_HARD_LIMIT = 150


def _hook(line: str) -> str:
    # Anchor on the link end first — titles can contain the em-dash separator.
    m = LINK_RE.search(line)
    rest = line[m.end():] if m else line
    i = rest.find(HOOK_SPLIT)
    return rest[i + len(HOOK_SPLIT):].strip() if i != -1 else ""


def verify(memory_dir: str, target_kb: float) -> list[tuple[str, bool, str]]:
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    raw = open(memory_md, encoding="utf-8").read()
    items = [ln for ln in raw.splitlines() if LIST_RE.match(ln)]
    size_kb = round(len(raw.encode("utf-8")) / 1024, 1)

    # Budget.
    checks = [("size", size_kb <= target_kb, f"{size_kb} KB (target ≤{target_kb} KB)")]

    # Hook length (hard ceiling, by character).
    over = [ln for ln in items if len(_hook(ln)) > HOOK_HARD_LIMIT]
    checks.append(("hook_length", not over,
                   f"{len(over)} hook(s) over {HOOK_HARD_LIMIT} chars"))

    # Links: unique, no dups.
    linked = []
    for ln in items:
        linked.extend(LINK_RE.findall(ln))
    dups = sorted({f for f in linked if linked.count(f) > 1})
    checks.append(("no_duplicate_links", not dups, f"dups: {dups or 'none'}"))

    # No dangling links (every linked .md must exist on disk).
    linked_set = set(linked)
    dangling = sorted(f for f in linked_set if not os.path.isfile(os.path.join(memory_dir, f)))
    checks.append(("no_dangling_links", not dangling, f"dangling: {dangling or 'none'}"))

    # No orphans: every topic file must be represented in the index (as a link OR
    # named in plain text — a deliberately-unlinked entry still counts).
    topic = [f for f in os.listdir(memory_dir) if f.endswith(".md") and f != "MEMORY.md"]
    missing = [f for f in topic if f not in raw and f[:-3] not in raw]
    checks.append(("no_orphan_topic_files", not missing, f"unreferenced: {missing or 'none'}"))

    return checks


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = 12.0
    if "--target-kb" in sys.argv:
        target = float(sys.argv[sys.argv.index("--target-kb") + 1])
    memory_dir = args[0] if args else None
    if not memory_dir:
        # Reuse the resolver from the analyzer for portability.
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from analyze_memory import resolve_memory_dir  # noqa: E402
        memory_dir = resolve_memory_dir()

    results = verify(memory_dir, target)
    all_pass = True
    for name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"{flag}  {name}: {detail}")
    print("\nALL CHECKS PASS" if all_pass else "\nSOME CHECKS FAILED")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
