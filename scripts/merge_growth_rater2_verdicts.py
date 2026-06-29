"""Merge the 36 frozen rater-2 verdicts into the rebuilt 45-item growth worksheet.

After ``build_l2l3_growth_blind_set`` rebuilt the blind set with a 5th arm (45
items) and ``build_growth_detailed_worksheet`` regenerated the blank detailed
worksheet, the 36 original rater-2 verdicts (frozen, keyed by stable item_ids)
must be carried forward so the human only grades the 9 NEW items.

Reads the backed-up 36-item answered worksheet for verdict lines, walks the new
45-item blank worksheet, fills the 36 known verdicts, leaves 9 blank, and writes
the merged answered worksheet the freeze reads. Also prints the 9 new items'
case + model_answer so the operator can grade them blind (no arm identity).

Does NOT open ``l2l3_growth_arm_key.sealed.json`` — new items are identified by
set-difference of item_ids (present in the 45-set, absent from the 36-answered
set), which leaks no arm identity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

AD = Path(__file__).resolve().parent.parent / "cache" / "model_ab_answer"
BLANK = AD / "l2l3_growth_rater_worksheet_detailed.md"
OLD_ANSWERED = AD / "l2l3_growth_rater_worksheet_detailed_answered.md.bak36"
NEW_ANSWERED = AD / "l2l3_growth_rater_worksheet_detailed_answered.md"
BLIND = AD / "l2l3_growth_blind_items.jsonl"

ITEM_RE = re.compile(r"^#### Item `([0-9a-f]{32})`")
BLANK_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\* `______`")
ANSWERED_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\* `(correct|partial|wrong)`")


def parse_answered(path: Path) -> dict[str, str]:
    """item_id -> the full `**Verdict:** ...` line from the old answered worksheet."""
    out: dict[str, str] = {}
    cur: str | None = None
    for line in path.read_text().splitlines():
        m = ITEM_RE.match(line)
        if m:
            cur = m.group(1)
            continue
        if ANSWERED_VERDICT_RE.match(line) and cur:
            out[cur] = line
            cur = None
    return out


def main() -> None:
    old_verdicts = parse_answered(OLD_ANSWERED)
    print(f"loaded {len(old_verdicts)} frozen rater-2 verdicts from backup")

    blank_lines = BLANK.read_text().splitlines()
    merged: list[str] = []
    cur_id: str | None = None
    filled = 0
    new_ids: list[str] = []
    for line in blank_lines:
        m = ITEM_RE.match(line)
        if m:
            cur_id = m.group(1)
            if cur_id not in old_verdicts:
                new_ids.append(cur_id)
            merged.append(line)
            continue
        if BLANK_VERDICT_RE.match(line) and cur_id:
            if cur_id in old_verdicts:
                merged.append(old_verdicts[cur_id])
                filled += 1
            else:
                merged.append(line)  # leave blank for the human
            cur_id = None
            continue
        merged.append(line)

    NEW_ANSWERED.write_text("\n".join(merged) + "\n")
    print(f"wrote merged answered worksheet -> {NEW_ANSWERED}")
    print(
        f"  carried forward {filled} frozen verdicts; {len(new_ids)} new items left blank"
    )

    # Print the 9 new items (arm-free) for the operator to grade.
    blind = {
        json.loads(l)["item_id"]: json.loads(l)
        for l in BLIND.read_text().splitlines()
        if l.strip()
    }
    print(f"\n=== {len(new_ids)} NEW ITEMS TO GRADE (blind — no arm identity) ===\n")
    for i, iid in enumerate(new_ids, 1):
        it = blind[iid]
        ans = it["model_answer"]
        print(
            f"--- NEW ITEM {i}/{len(new_ids)} — case: {it['case']} — item_id: {iid} ---"
        )
        print(f"prompt: {it['prompt'][:240]}...")
        print(f"rubric must_have_facts: {it['rubric'].get('must_have_facts', [])}")
        print(f"model_answer ({len(ans)} chars):")
        print(ans)
        print()


if __name__ == "__main__":
    main()
