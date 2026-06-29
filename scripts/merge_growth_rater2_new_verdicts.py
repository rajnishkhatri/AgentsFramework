"""Merge the human's 9 new-item verdicts into the full answered worksheet.

After the human fills ``l2l3_growth_new9_rater2_worksheet.md``, this reads those
9 verdicts and fills the matching blank ``**Verdict:**`` lines in the full
45-item answered worksheet (``l2l3_growth_rater_worksheet_detailed_answered.md``)
so ``freeze_l2l3_growth_into_seed`` can parse all 45 rater-2 verdicts.

Verifies every one of the 45 item_ids has a verdict after the merge, and that
the 9 new verdicts parse to a valid label. No sealed-key opening.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

AD = Path(__file__).resolve().parent.parent / "cache" / "model_ab_answer"
NEW9 = AD / "l2l3_growth_new9_rater2_worksheet.md"
ANSWERED = AD / "l2l3_growth_rater_worksheet_detailed_answered.md"
BLIND = AD / "l2l3_growth_blind_items.jsonl"

ITEM_RE = re.compile(r"^#### Item `([0-9a-f]{32})`")
BLANK_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\* `______`")
ANSWERED_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\* `(correct|partial|wrong)`")


def parse_verdicts(path: Path) -> dict[str, str]:
    """item_id -> the full `**Verdict:** <label> ...` line."""
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
    new9 = parse_verdicts(NEW9)
    if len(new9) != 9:
        print(f"WARNING: expected 9 filled verdicts in {NEW9}, found {len(new9)}")
        if not new9:
            raise SystemExit(
                "no filled verdicts found — fill the '**Verdict:**' lines first"
            )

    answered_lines = ANSWERED.read_text().splitlines()
    merged: list[str] = []
    cur_id: str | None = None
    filled = 0
    for line in answered_lines:
        m = ITEM_RE.match(line)
        if m:
            cur_id = m.group(1)
            merged.append(line)
            continue
        if BLANK_VERDICT_RE.match(line) and cur_id:
            if cur_id in new9:
                merged.append(new9[cur_id])
                filled += 1
            else:
                merged.append(line)
            cur_id = None
            continue
        merged.append(line)

    ANSWERED.write_text("\n".join(merged) + "\n")
    print(f"merged {filled} new verdicts into {ANSWERED}")

    # Verify all 45 item_ids now have a verdict.
    all_ids = {
        json.loads(l)["item_id"] for l in BLIND.read_text().splitlines() if l.strip()
    }
    final = parse_verdicts(ANSWERED)
    missing = all_ids - set(final)
    print(f"total answered: {len(final)}/{len(all_ids)}")
    if missing:
        print(f"STILL MISSING ({len(missing)}):")
        for iid in sorted(missing):
            print(f"  {iid}")
        raise SystemExit(1)
    print(
        "all 45 rater-2 verdicts present — ready to run freeze_l2l3_growth_into_seed.py"
    )


if __name__ == "__main__":
    main()
