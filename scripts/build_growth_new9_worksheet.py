"""Build a focused rater-2 worksheet for ONLY the 9 new growth items.

After the 5th arm was added, the 9 new (case x arm) items need human rater-2
verdicts. The full 45-item detailed worksheet is more than the human needs to
re-grade (the 36 original verdicts are frozen). This emits one section per new
item with the full case context (prompt, fixture contents, worked ground truth,
rubric) and a fillable ``**Verdict:**`` line in the exact format
``freeze_l2l3_growth_into_seed.parse_rater2`` reads, so filled verdicts merge
without re-parsing.

New items are identified by set-difference (in the 45-set, absent from the
36-answered backup) — NO sealed-key opening, no arm identity leaked.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from seed_model_ab_l2l3_workspace import GROUND_TRUTH_BY_CASE  # noqa: E402
from scripts.build_growth_detailed_worksheet import CASE_META, CASE_ORDER, _read_fixture  # noqa: E402

AGENT_ROOT = Path(__file__).resolve().parent.parent
AD = AGENT_ROOT / "cache" / "model_ab_answer"
BLIND = AD / "l2l3_growth_blind_items.jsonl"
OLD_ANSWERED = AD / "l2l3_growth_rater_worksheet_detailed_answered.md.bak36"
OUT = AD / "l2l3_growth_new9_rater2_worksheet.md"

ITEM_RE = re.compile(r"^#### Item `([0-9a-f]{32})`")
ANSWERED_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\* `(correct|partial|wrong)`")


def _old_item_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for line in path.read_text().splitlines():
        m = ITEM_RE.match(line)
        if m:
            ids.add(m.group(1))
    return ids


def main() -> None:
    blind = {
        json.loads(l)["item_id"]: json.loads(l)
        for l in BLIND.read_text().splitlines()
        if l.strip()
    }
    old_ids = _old_item_ids(OLD_ANSWERED)
    new_ids = set(blind) - old_ids
    # Group new items by case, order by CASE_ORDER.
    by_case: dict[str, list[dict]] = {}
    for iid in new_ids:
        it = blind[iid]
        by_case.setdefault(it["case"], []).append(it)

    L: list[str] = []
    L.append("# L2/L3 GROWTH — Rater-2 Worksheet for the 9 NEW items (5th arm)")
    L.append("")
    L.append(
        "Grade each item below **correct / partial / wrong** against the rubric. You are "
        "BLIND to which model produced each answer. Each section gives: the **prompt**, "
        "the **fixture files** the model read, the **worked ground truth**, the **rubric**, "
        "then the model answer with a **Verdict** line to fill."
    )
    L.append("")
    L.append(
        "> Do NOT open `l2l3_growth_arm_key.sealed.json`. Fill only the `**Verdict:**` lines. "
        "Some answers are clipped at the 500-char harvest boundary — judge on what is visible."
    )
    L.append("")
    L.append(
        f"**Items to grade: {len(new_ids)}** (one new item per case, cases 16–24)."
    )
    L.append("")
    L.append("---")
    L.append("")

    n = 0
    for case in CASE_ORDER:
        items = by_case.get(case, [])
        if not items:
            continue
        n += 1
        meta = CASE_META[case]
        gt = GROUND_TRUTH_BY_CASE[case]
        for it in items:
            prompt = it["prompt"]
            rubric = it["rubric"]
            ans = it["model_answer"]

            L.append(f"## Item {n}/{len(new_ids)} — `{case}`")
            L.append("")
            L.append("### Prompt (input)")
            L.append("")
            L.append(f"> {prompt}")
            L.append("")
            L.append("### Fixture files (what the model read)")
            L.append("")
            for rel in meta["fixtures"]:
                L.append(f"**`workspace/{rel}`**")
                L.append("")
                L.append("```")
                L.append(_read_fixture(rel).rstrip("\n"))
                L.append("```")
                L.append("")
            L.append("### Worked ground truth")
            L.append("")
            L.append(meta["worked"])
            L.append("")
            L.append(f"> **GRADING:** {meta['grading']}")
            L.append("")
            L.append("### Rubric (must-have facts)")
            L.append("")
            for fact in rubric.get("must_have_facts", gt.facts):
                L.append(f"- {fact}")
            av = rubric.get("acceptable_variation", list(gt.notes))
            if av:
                L.append("")
                L.append(f"*Acceptable variation:* {'; '.join(av)}")
            L.append("")
            L.append(f"#### Item `{it['item_id']}`")
            L.append("")
            clipped = len(ans) >= 498
            if clipped:
                L.append(
                    "> ⚠️ This answer is clipped at the 500-char harvest boundary — "
                    "the load-bearing conclusion may be cut off. Judge on what is visible."
                )
                L.append("")
            L.append("**Model answer**")
            L.append("")
            L.append("```text")
            L.append(ans.rstrip("\n"))
            L.append("```")
            L.append("")
            L.append("**Verdict:** `______` (correct / partial / wrong) — *reason:*")
            L.append("")
        L.append("---")
        L.append("")

    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT} ({len(new_ids)} new items across {len(by_case)} cases)")
    print(
        "fill the '**Verdict:** `______`' lines, then run merge_growth_rater2_new_verdicts.py"
    )


if __name__ == "__main__":
    main()
