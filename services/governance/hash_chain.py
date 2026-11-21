"""Append-only JSONL files with a chained SHA-256 integrity hash.

Shared by the BlackBox trace and the PhaseLogger decision log. Each row's
``integrity_hash`` covers the row plus the previous row's hash, so an edited or
reordered row breaks the chain at that point.

Three failure modes the bare chain cannot see are handled here:

- **Concurrent writers** — reading the tail and appending is one critical
  section under an exclusive ``flock``.
- **Torn writes** — a partial last line (crash mid-write) is fenced onto its
  own line before the next append, skipped when chaining, and reported as
  corrupt on verification.
- **Dropped tails** — a ``<file>.head`` anchor stores the row count, so a file
  with fewer rows than were appended is reported as truncated.

The chain is unkeyed: it detects accidental damage and naive edits, not an
adversary who can rewrite the file *and* its anchor.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("services.governance.hash_chain")

GENESIS_HASH = "0" * 64
HASH_KEY = "integrity_hash"
_TAIL_BLOCK_SIZE = 64 * 1024


@dataclass
class ChainReport:
    """Outcome of verifying one chained JSONL file."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    chain_valid: bool = True
    broken_at_index: int | None = None
    broken_expected_hash: str | None = None
    broken_actual_hash: str | None = None
    corrupt_line_count: int = 0
    truncated: bool = False
    unhashed_row_count: int = 0

    @property
    def intact(self) -> bool:
        """Chain verifies, nothing is corrupt, and no rows are missing."""
        return self.chain_valid and not self.corrupt_line_count and not self.truncated


def compute_hash(row: dict[str, Any], prev_hash: str) -> str:
    """SHA-256 over the canonical row (without its own hash) plus ``prev_hash``."""
    body = {k: v for k, v in row.items() if k != HASH_KEY}
    payload = json.dumps(body, sort_keys=True, default=str) + prev_hash
    return hashlib.sha256(payload.encode()).hexdigest()


def _head_path(path: Path) -> Path:
    return path.with_name(path.name + ".head")


def _parse_row(line: bytes | str) -> dict[str, Any] | None:
    try:
        row = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return row if isinstance(row, dict) else None


def tail_hash(path: Path) -> str:
    """Hash of the last well-formed chained row, read from the end of the file.

    Reads backwards in blocks, so the cost is bounded by the last row's size
    rather than the file's. Torn or unhashed trailing lines are skipped.
    """
    if not path.exists():
        return GENESIS_HASH
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()
        buffer = b""
        while position > 0:
            step = min(_TAIL_BLOCK_SIZE, position)
            position -= step
            f.seek(position)
            buffer = f.read(step) + buffer
            lines = buffer.split(b"\n")
            # The first piece may be the tail of a longer line unless we have
            # reached the start of the file.
            complete = lines if position == 0 else lines[1:]
            for line in reversed(complete):
                if not line.strip():
                    continue
                row = _parse_row(line)
                if row is not None and row.get(HASH_KEY):
                    return str(row[HASH_KEY])
    return GENESIS_HASH


def _read_head(path: Path) -> dict[str, Any] | None:
    head = _head_path(path)
    if not head.exists():
        return None
    try:
        data = json.loads(head.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _count_rows(path: Path) -> int:
    count = 0
    with open(path, "rb") as f:
        for line in f:
            if line.strip() and _parse_row(line) is not None:
                count += 1
    return count


def _ends_with_newline(path: Path) -> bool:
    size = path.stat().st_size
    if size == 0:
        return True
    with open(path, "rb") as f:
        f.seek(size - 1)
        return f.read(1) == b"\n"


def append_chained(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    """Append ``row`` with its chained hash; returns the row as written.

    The tail read, the write and the head-anchor update run under one
    exclusive lock, so interleaved writers extend a single chain.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = {k: v for k, v in row.items() if k != HASH_KEY}
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            head = _read_head(path)
            prior_count = (
                int(head.get("count", 0)) if head is not None else _count_rows(path)
            )
            if not _ends_with_newline(path):
                # Fence a torn previous write onto its own line.
                f.write("\n")
            written[HASH_KEY] = compute_hash(written, tail_hash(path))
            f.write(json.dumps(written, default=str) + "\n")
            f.flush()
            _head_path(path).write_text(
                json.dumps({"count": prior_count + 1, "last_hash": written[HASH_KEY]})
            )
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return written


def verify_chain(path: Path) -> ChainReport:
    """Re-hash every row of ``path`` and report breaks, corruption, truncation.

    Rows written before chaining existed carry no hash; they are returned and
    counted in ``unhashed_row_count`` but do not break the chain.
    """
    report = ChainReport()
    if not path.exists():
        return report

    prev_hash = GENESIS_HASH
    with open(path, "rb") as f:
        for raw in f:
            if not raw.strip():
                continue
            row = _parse_row(raw)
            if row is None:
                report.corrupt_line_count += 1
                continue
            stored = row.get(HASH_KEY, "")
            if not stored:
                report.unhashed_row_count += 1
                report.rows.append(row)
                continue
            expected = compute_hash(row, prev_hash)
            if stored != expected:
                report.chain_valid = False
                if report.broken_at_index is None:
                    report.broken_at_index = len(report.rows)
                    report.broken_expected_hash = expected
                    report.broken_actual_hash = stored
            prev_hash = stored
            report.rows.append(row)

    head = _read_head(path)
    if head is not None and len(report.rows) < int(head.get("count", 0)):
        report.truncated = True
    return report


__all__ = [
    "GENESIS_HASH",
    "HASH_KEY",
    "ChainReport",
    "append_chained",
    "compute_hash",
    "tail_hash",
    "verify_chain",
]
