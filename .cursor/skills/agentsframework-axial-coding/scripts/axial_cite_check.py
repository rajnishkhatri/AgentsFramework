"""Exemplar-ID fidelity check (A5 — the missing prose-emit gate).

The emit step (rubric assertions + judge test-case candidates) is prose/JSON
written by hand, with no gate — so a cited exemplar can point at a trace that
doesn't exist, or at a trace that doesn't carry the code the assertion claims.
Both happened in the iteration-2 review (a `no-teach-back` assertion cited a
trace lacking that code, plus a dangling `08…` id).

This check takes the coded JSONL as ground truth and a list of citations
(``trace_id`` + the ``code`` the citation claims the trace exhibits) and reports
every citation that (a) resolves to no trace, or (b) resolves but the trace does
not carry the claimed code. Citations can be given as a JSON file
(``[{"trace_id": "...", "code": "..."}, ...]``) or extracted by the caller.

Read-only, stdlib only, framework-agnostic. trace_id prefixes are supported
(an 8-char prefix matches the full id) since write-ups cite prefixes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_codes_by_trace(coded_path: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for line in coded_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tid = str(row.get("trace_id", ""))
        if tid:
            out[tid] = set(row.get("open_codes") or [])
    return out


def _resolve(prefix: str, codes_by_trace: dict[str, set[str]]) -> list[str]:
    """Return full trace_ids matching an id or id-prefix."""
    if prefix in codes_by_trace:
        return [prefix]
    return [tid for tid in codes_by_trace if tid.startswith(prefix)]


def check_citations(coded_path: Path, citations: list[dict[str, str]]) -> list[str]:
    """Return violation messages; empty == every citation is faithful."""
    codes_by_trace = _load_codes_by_trace(coded_path)
    problems: list[str] = []
    for cite in citations:
        tid = str(cite.get("trace_id", "")).strip()
        claimed = str(cite.get("code", "")).strip()
        matches = _resolve(tid, codes_by_trace)
        if not matches:
            problems.append(
                f"cited trace '{tid}' resolves to NO trace in the coded set "
                f"(dangling id)"
            )
            continue
        if len(matches) > 1:
            problems.append(
                f"cited trace prefix '{tid}' is ambiguous ({len(matches)} matches)"
            )
            continue
        if claimed and claimed not in codes_by_trace[matches[0]]:
            problems.append(
                f"cited trace '{tid}' does NOT carry the claimed code "
                f"'{claimed}' (its codes: {sorted(codes_by_trace[matches[0]])})"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", required=True, type=Path)
    parser.add_argument(
        "--citations",
        required=True,
        type=Path,
        help="JSON: [{'trace_id': ..., 'code': ...}, ...]",
    )
    args = parser.parse_args(argv)
    for p in (args.coded, args.citations):
        if not p.exists():
            print(f"file not found: {p}")
            return 2
    citations = json.loads(args.citations.read_text(encoding="utf-8"))
    problems = check_citations(args.coded, citations)
    if problems:
        print("CITATION CHECK FAILED — emitted exemplars don't match the data:")
        for msg in problems:
            print(f"  - {msg}")
        return 1
    print("OK — every cited exemplar resolves and carries its claimed code.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
