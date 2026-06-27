#!/usr/bin/env python
"""Download the LongMemEval (MIT) dataset into the gitignored local cache.

This is an OPTIONAL operator tool — the committed corpus
(`frontend/e2e/fixtures/memory_multisession_corpus.json`, built by
`scripts/build_memory_multisession_corpus.py`) is self-contained and does NOT
depend on this download. Run this only if you want to grow the corpus from the
real LongMemEval haystacks.

The downloaded JSON lands in `cache/longmemeval/` which is gitignored — it is
NOT committed to the repo (LongMemEval is MIT so it *could* be, but bundling a
multi-megabyte third-party dataset in-tree is undesirable; see
`LICENSES/LongMemEval-MIT.txt` for attribution).

    python scripts/fetch_longmemeval.py            # default: longmemeval_oracle
    python scripts/fetch_longmemeval.py --file longmemeval_s

Source: https://huggingface.co/datasets/xiaowu0162/longmemeval (MIT).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = AGENT_ROOT / "cache" / "longmemeval"

_REPO_ID = "xiaowu0162/longmemeval"
# The upstream files (per the dataset card); oracle is the smallest/most useful
# for deriving compact cases.
_KNOWN_FILES = (
    "longmemeval_oracle",
    "longmemeval_s",
    "longmemeval_m",
)


def fetch(file_stem: str) -> Path:
    """Download one LongMemEval file into the cache; return the local path."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:  # pragma: no cover - operator-tool guard
        print(
            "huggingface_hub is not installed. Install it in the venv first:\n"
            "    .venv/bin/pip install huggingface_hub",
            file=sys.stderr,
        )
        raise SystemExit(2)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local = hf_hub_download(
        repo_id=_REPO_ID,
        filename=file_stem,
        repo_type="dataset",
        local_dir=str(CACHE_DIR),
    )
    return Path(local)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        default="longmemeval_oracle",
        help=f"upstream file stem (known: {', '.join(_KNOWN_FILES)})",
    )
    args = parser.parse_args(argv)

    path = fetch(args.file)
    print(f"downloaded {args.file} -> {path}")
    print(
        "NOTE: this file is in the gitignored cache and is NOT committed. "
        "See LICENSES/LongMemEval-MIT.txt for attribution."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
