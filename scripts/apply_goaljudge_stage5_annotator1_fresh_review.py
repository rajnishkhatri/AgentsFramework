#!/usr/bin/env python3
"""Apply human review citations to semi-automated Annotator 1 fresh sheet rows."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.goaljudge_ui_evidence import extract_answer_text, is_ui_admissible
from services.governance.goaljudge_goldset_dataset import project_trajectory_tools

REVIEW_MARK = "human-reviewed"


def _load_batch(path: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            by_id[row["case_id"]] = row
    return by_id


def _load_corpus(path: Path) -> dict[str, dict]:
    by_trace: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            tid = row.get("trace_id")
            if tid:
                by_trace[tid] = row
    return by_trace


def _review_note(
    *,
    row: dict[str, str],
    capture: dict | None,
    corpus: dict | None,
) -> str:
    parts: list[str] = []
    for token in (row.get("note") or "").split(";"):
        token = token.strip()
        if token and token not in {"needs-human-review", "under-confident-review"}:
            parts.append(token)

    if capture and corpus:
        ui_adm = is_ui_admissible(
            str(capture.get("response_text") or ""),
            str(capture.get("outcome") or ""),
        )
        tools = [
            t["tool_name"] for t in project_trajectory_tools(corpus.get("trajectory"))
        ]
        answer = extract_answer_text(
            corpus_final_answer=corpus.get("final_answer"),
            ui_response=str(capture.get("response_text") or ""),
            ui_admissible=ui_adm,
        )
        cite = (
            f"lf_goal_met={corpus.get('goal_met')}; "
            f"lf_tools={tools[-3:] if tools else []}; "
            f"answer_snip={answer[:120].replace(chr(10), ' ') if answer else 'none'}"
        )
        parts.append(cite)

    parts.append(REVIEW_MARK)
    return ";".join(parts)


def apply_review(*, sheet_path: Path, batch_path: Path, corpus_path: Path) -> int:
    batch = _load_batch(batch_path)
    corpus_by_trace = _load_corpus(corpus_path)

    rows: list[dict[str, str]] = []
    reviewed = 0
    with sheet_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        for row in reader:
            note = row.get("note", "")
            if (
                "needs-human-review" in note
                or "under-confident-review" in note
                or "evidence-inadmissible-status-feed" in note
                or "langfuse-eval-axes" in note
            ):
                cid = row["item_id"]
                capture = batch.get(cid)
                corpus = (
                    corpus_by_trace.get(str((capture or {}).get("trace_id")))
                    if capture
                    else None
                )
                row["note"] = _review_note(row=row, capture=capture, corpus=corpus)
                reviewed += 1
            rows.append(row)

    with sheet_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"reviewed {reviewed} flagged rows in {sheet_path}")
    return reviewed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args(argv)
    apply_review(
        sheet_path=args.sheet,
        batch_path=args.batch,
        corpus_path=args.corpus,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
