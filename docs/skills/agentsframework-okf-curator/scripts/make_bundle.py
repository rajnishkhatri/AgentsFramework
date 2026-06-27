#!/usr/bin/env python3
"""Generate `index.md` + `log.md` for an OKF bundle from its Concepts' frontmatter.

`index.md` lists every non-reserved `*.md` (directly, or recursively with
--recurse-index) as `- [title](relpath) — description`, read from each file's
frontmatter so the catalog never drifts from the files. `log.md` is seeded with one
dated entry; re-running regenerates `index.md` and re-seeds `log.md` (move existing
log lines you want to keep, or pass --append-log to keep the prior log body).

`--depth-to-root` is the number of `../` needed to reach `docs/CONVENTIONS_OKF.md`
from the bundle dir. A bundle at `docs/<x>/` is depth 1; `docs/<x>/<y>/` is depth 2.
Getting this wrong is the #1 source of a broken convention link in the catalog.

Usage:
    python make_bundle.py docs/recipes/gcp --title "GCP deployment runbooks" --depth-to-root 2
    python make_bundle.py docs/vision --title "Vision" --depth-to-root 1
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

RESERVED = {"index.md", "log.md", "README.md"}


def _fm(path: Path) -> dict[str, str]:
    t = path.read_text(encoding="utf-8")
    if not t.startswith("---\n"):
        return {}
    try:
        block = t[4 : t.index("\n---\n", 3)]
    except ValueError:
        return {}
    d: dict[str, str] = {}
    for line in block.splitlines():
        m = re.match(r"(\w+):\s*(.*)", line)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if v.startswith("'") and v.endswith("'"):
                v = v[1:-1].replace("''", "'")
            d[k] = v
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--title", required=True)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--recurse-index", action="store_true")
    ap.add_argument(
        "--depth-to-root",
        type=int,
        default=None,
        help="(legacy) number of ../ to reach docs/. Prefer --conventions-path "
        "or let the script compute the link automatically.",
    )
    ap.add_argument(
        "--conventions-path",
        default="docs/CONVENTIONS_OKF.md",
        help="path to the convention doc, relative to repo root",
    )
    ap.add_argument(
        "--note",
        default="Declared as an OKF bundle.",
        help="the log.md seed entry text",
    )
    args = ap.parse_args()

    base = Path(args.target)
    # Link to the convention doc, computed relative to THIS bundle dir so it is
    # correct no matter how deep the bundle is (incl. the root `research/` bundle,
    # where a naive `../CONVENTIONS_OKF.md` is wrong — it lives under docs/).
    # --depth-to-root is honoured only as a legacy override.
    if args.depth_to_root is not None:
        conv_link = "../" * args.depth_to_root + "CONVENTIONS_OKF.md"
    else:
        import os as _os

        conv_link = _os.path.relpath(args.conventions_path, base.as_posix())
    files = base.rglob("*.md") if args.recurse_index else base.glob("*.md")
    entries = []
    for f in sorted(files):
        if f.name in RESERVED:
            continue
        d = _fm(f)
        rel = f.relative_to(base).as_posix()
        entries.append(
            f"- [{d.get('title', f.stem)}]({rel}) — {d.get('description', '')}"
        )

    idx = (
        f"# {args.title} — bundle index\n\n"
        f"OKF bundle. Each entry is a typed Concept. See the convention in "
        f"[CONVENTIONS_OKF.md]({conv_link}).\n\n" + "\n".join(entries) + "\n"
    )
    (base / "index.md").write_text(idx, encoding="utf-8")

    log = (
        "---\n"
        "type: log\n"
        f"title: '{args.title} — bundle log'\n"
        "---\n\n"
        f"# {args.title} — bundle log\n\n"
        "Chronological history, newest first (ISO-8601).\n\n"
        f"- {args.date} — {args.note} Convention in "
        f"[CONVENTIONS_OKF.md]({conv_link}); linted by `scripts/okf_lint.py`.\n"
    )
    (base / "log.md").write_text(log, encoding="utf-8")
    print(f"{args.target}: index.md ({len(entries)} entries) + log.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
