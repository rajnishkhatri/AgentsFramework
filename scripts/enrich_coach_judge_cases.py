"""Task 3.6 (data-plane fix) — enrich coach judge cases with the ITEM the judge grades.

The pedagogy leak judge decides ``answer_leakage`` by asking "after this reply, is
MORE THAN ONE answer option still live?" (ADR-0017 decisive test). That test is
**impossible to run without the answer options** — yet the recorder historically
passed only the bare ``question_id`` string (``q-gram-1``) to the judge, so the
judge reasoned about the rule in the abstract and missed every indirect leak
(A2/A3/B1 false negatives). See ADR-0017 "Accepted risk — small positive cell".

This script resolves each case's ``question_id`` against the ground-truth item bank
(``frontend/e2e/fixtures/preact_learn_corpus.ts`` — the corpus the fixtures were
AUTHORED against; the coach replies quote its wording verbatim) and writes a
rendered ``question`` block into each case. The block mirrors
``components/coach_context._render_question``:

* pre_submit → passage + stem + choices only. The answer key is STRIPPED so the
  judge decides leakage blind (it must not be able to cheat by seeing the key).
* post_feedback → the same, PLUS the revealed answer letter (the app has already
  disclosed it; the cross-question leak channel needs it).

It is a one-time/refresh enrichment: read cases.jsonl → add ``question`` → write
cases.jsonl. The item bank lives in TS; we transcribe the 6 referenced items here
rather than couple the Python recorder to a TS parser.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TS_CORPUS = REPO_ROOT / "frontend/e2e/fixtures/preact_learn_corpus.ts"

_LETTERS = "ABCD"


def extract_items(ts_path: Path) -> dict[str, dict[str, Any]]:
    """Parse the ``q({ ... })`` item rows out of the TS corpus.

    Returns ``{question_id: {context_html, stem, choices, answer_letter}}``. Only
    the fields the judge needs are extracted; ``per_choice_rationale`` etc. are
    intentionally left out (the judge grades the coach turn, not the answer key).
    """
    src = ts_path.read_text(encoding="utf-8")
    items: dict[str, dict[str, Any]] = {}
    # One item per physical line: q({ id: "...", ... context_html: "...", stem:
    # "...", choices: CH("a","b","c","d"), answer_letter: "B", ... })
    for block in re.findall(r"q\(\{[^\n]*id:\s*\"q-[^\"]+\"[^\n]*\}\)", src):
        qid = re.search(r'id:\s*"([^"]+)"', block).group(1)
        ctx = re.search(r'context_html:\s*"((?:[^"\\]|\\.)*)"', block).group(1)
        stem = re.search(r'stem:\s*"((?:[^"\\]|\\.)*)"', block).group(1)
        ch_group = re.search(
            r'choices:\s*CH\(("(?:[^"\\]|\\.)*"(?:\s*,\s*"(?:[^"\\]|\\.)*")*)\)',
            block,
        ).group(1)
        choices = re.findall(r'"((?:[^"\\]|\\.)*)"', ch_group)
        ans = re.search(r'answer_letter:\s*"([A-D])"', block).group(1)
        items[qid] = {
            "context_html": ctx.replace("<u>", "").replace("</u>", ""),
            "stem": stem,
            "choices": choices,
            "answer_letter": ans,
        }
    return items


def render_question(item: dict[str, Any], *, post_feedback: bool) -> str:
    """Render an item into the judge-facing question block.

    Mirrors ``components/coach_context._render_question`` field order (passage /
    question / choices / answer). The answer letter appears ONLY post_feedback.
    """
    lines: list[str] = []
    if item.get("context_html"):
        lines.append(f"- passage: {item['context_html']}")
    if item.get("stem"):
        lines.append(f"- question: {item['stem']}")
    if item.get("choices"):
        lines.append("- choices:")
        for i, label in enumerate(item["choices"]):
            lines.append(f"  - {_LETTERS[i]}) {label}")
    if post_feedback and item.get("answer_letter"):
        lines.append(f"- correct answer: {item['answer_letter']}")
    return "\n".join(lines)


def enrich(cases_path: Path, items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        qid = case.get("question_id")
        item = items.get(qid)
        if item is None:
            raise SystemExit(
                f"case {case.get('case_id')!r} references question_id {qid!r} "
                f"absent from the TS corpus {TS_CORPUS}"
            )
        post = case.get("mode") == "post_feedback"
        case["question"] = render_question(item, post_feedback=post)
        rows.append(case)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=REPO_ROOT / "tests/fixtures/coach_judge_validation/cases.jsonl",
    )
    parser.add_argument("--ts-corpus", type=Path, default=TS_CORPUS)
    args = parser.parse_args(argv)

    items = extract_items(args.ts_corpus)
    rows = enrich(args.cases, items)
    args.cases.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(
        f"enriched {len(rows)} cases with rendered question blocks "
        f"(from {len(items)} TS items) → {args.cases}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
