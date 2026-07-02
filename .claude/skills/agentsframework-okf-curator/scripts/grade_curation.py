#!/usr/bin/env python3
"""Discriminating grader for OKF-curation outputs.

The first eval pass used assertions that only checked "did it produce a lint-clean
file", which any capable model passes with or without the skill — so the benchmark
couldn't tell the skill apart from baseline. These checks probe the things the skill
actually teaches and that baseline runs tend to get wrong:

  * a feature recipe lands INSIDE a declared topic sub-bundle (not a flat orphan),
    and a NEW topic is registered in DECLARED_BUNDLES + linked from the parent index;
  * research lands in the AUTHORED home (root `research/`), not the EXCLUDED
    `docs/research/` evidence tree, and isn't mis-tagged `recipe`;
  * a drift report labels match types and explains its window, and edits nothing.

Run against a single run's `outputs/` dir; prints a grading.json-shaped result.

    python grade_curation.py --eval document-feature --outputs <run>/outputs
    python grade_curation.py --eval file-research     --outputs <run>/outputs
    python grade_curation.py --eval drift-check       --outputs <run>/outputs
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re


def _read(p: str) -> str:
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return ""


def _fm_type(p: str) -> str | None:
    t = _read(p)
    if not t.startswith("---\n"):
        return None
    try:
        block = t[4 : t.index("\n---\n", 3)]
    except ValueError:
        return None
    for line in block.splitlines():
        if line.strip().startswith("type:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def _transcript(outputs: str) -> str:
    return _read(os.path.join(outputs, "transcript.md")).lower()


def _concept_files(outputs: str) -> list[str]:
    out = []
    for f in glob.glob(os.path.join(outputs, "*.md")):
        bn = os.path.basename(f).lower()
        if bn in ("transcript.md",) or "index" in bn or "log" in bn:
            continue
        out.append(f)
    return out


def _lint_zero(outputs: str) -> bool:
    t = _read(os.path.join(outputs, "lint_result.txt")).lower()
    return any(
        k in t for k in ("exit code: 0", "exit_code=0", "exit code:0", "0 failure")
    )


def grade_document_feature(outputs: str) -> list[dict]:
    tr = _transcript(outputs)
    concept = _concept_files(outputs)
    c = concept[0] if concept else None
    in_topic_bundle = bool(re.search(r"recipes/[a-z_]+/", tr)) and "recipes/" in tr
    flat_orphan = bool(re.search(r"recipes/\d+[_a-z]*\.md", tr)) and not in_topic_bundle
    registered = "declared_bundles" in tr or "declared bundles" in tr
    parent_linked = "recipes/index" in tr or "parent" in tr and "index" in tr
    return [
        {
            "text": "recipe has type frontmatter",
            "passed": bool(c) and _fm_type(c) is not None,
            "evidence": f"type={_fm_type(c) if c else None}",
        },
        {
            "text": "recipe lands inside a topic sub-bundle (not a flat orphan)",
            "passed": in_topic_bundle and not flat_orphan,
            "evidence": f"topic-bundle={in_topic_bundle}, flat-orphan={flat_orphan}",
        },
        {
            "text": "new topic registered in DECLARED_BUNDLES",
            "passed": registered
            or not in_topic_bundle,  # only required if a new topic dir was made
            "evidence": f"registered={registered}",
        },
        {
            "text": "linked from the parent recipes index",
            "passed": parent_linked or not in_topic_bundle,
            "evidence": f"parent-index-linked={parent_linked}",
        },
        {
            "text": "okf_lint exits 0",
            "passed": _lint_zero(outputs),
            "evidence": f"lint0={_lint_zero(outputs)}",
        },
    ]


def grade_file_research(outputs: str) -> list[dict]:
    tr = _transcript(outputs)
    concept = _concept_files(outputs)
    c = concept[0] if concept else None
    # "filed in root research/" = the transcript names a root research/ path (research/<file>.md)
    # and NOT a docs/research/<file>.md destination. Count destination-style mentions, not
    # incidental references to the excluded dir (which the agent may name to say it AVOIDED it).
    root_research = bool(re.search(r"(?<!docs/)\bresearch/[a-z0-9_]+\.md", tr))
    filed_in_docs_research = bool(re.search(r"\bdocs/research/[a-z0-9_]+\.md", tr))
    authored_home = root_research and not filed_in_docs_research
    avoids_evidence = not filed_in_docs_research
    ttype = _fm_type(c) if c else None
    tags = ""
    if c:
        m = re.search(r"tags:\s*\[([^\]]*)\]", _read(c))
        tags = m.group(1) if m else ""
    not_mistagged = "recipe" not in tags
    return [
        {
            "text": "research filed in AUTHORED home (root research/), not excluded evidence",
            "passed": authored_home and avoids_evidence,
            "evidence": f"authored={authored_home}, avoids-docs/research={avoids_evidence}",
        },
        {
            "text": "note has a research-appropriate type (not mis-tagged 'recipe')",
            "passed": ttype is not None and not_mistagged,
            "evidence": f"type={ttype}, tags=[{tags}]",
        },
        {
            "text": "research bundle index + log updated",
            "passed": bool(glob.glob(os.path.join(outputs, "*index*.md")))
            and bool(glob.glob(os.path.join(outputs, "*log*.md"))),
            "evidence": "index+log present",
        },
        {
            "text": "okf_lint exits 0",
            "passed": _lint_zero(outputs),
            "evidence": f"lint0={_lint_zero(outputs)}",
        },
    ]


def grade_drift_check(outputs: str) -> list[dict]:
    rep = _read(os.path.join(outputs, "drift_report.txt"))
    tr = _transcript(outputs)
    edited = [
        os.path.basename(f)
        for f in glob.glob(os.path.join(outputs, "*.md"))
        if os.path.basename(f) != "transcript.md"
    ]
    labels_match = (
        "[path]" in rep or "match type" in rep.lower() or "symbol" in rep.lower()
    )
    explains_window = (
        "window" in rep.lower() or "docs-only" in rep.lower() or "--since" in rep
    )
    return [
        {
            "text": "drift report produced",
            "passed": len(rep) > 200,
            "evidence": f"len={len(rep)}",
        },
        {
            "text": "report-only (no docs created/edited)",
            "passed": len(edited) == 0,
            "evidence": f"extra-md={edited}",
        },
        {
            "text": "labels match type (path vs symbol)",
            "passed": labels_match,
            "evidence": f"labelled={labels_match}",
        },
        {
            "text": "explains the drift window choice",
            "passed": explains_window,
            "evidence": f"window-explained={explains_window}",
        },
    ]


GRADERS = {
    "document-feature": grade_document_feature,
    "file-research": grade_file_research,
    "drift-check": grade_drift_check,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True, choices=sorted(GRADERS))
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--write", help="path to write grading.json")
    args = ap.parse_args()
    expectations = GRADERS[args.eval](args.outputs)
    result = {"expectations": expectations}
    if args.write:
        json.dump(result, open(args.write, "w"), indent=2)
    p = sum(1 for e in expectations if e["passed"])
    print(json.dumps(result, indent=2))
    print(f"\n{p}/{len(expectations)} passed", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
