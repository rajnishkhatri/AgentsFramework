"""Axial-coding emit gate (FR-1 / FR-2 / FR-4 / FR-4a / FR-13).

This is the *how* of the skill's one hard rule: **no assertion may be emitted
from an unpartitioned aggregate.** The checker reads the two human-filled
artifacts — the inventory CSV (one row per code, with ``axis`` + ``category``)
and the categories CSV (one row per category, with ``axis`` / ``polarity`` /
``binary_check`` / optional ``dimension``) — and refuses (non-zero exit, naming
the offender) unless the partition is complete and every category is testable.

FR-1  every code carries a valid axis before any count/emit.
FR-2  every category has a non-empty ``binary_check`` (the un-testable reject).
FR-4  categories exist with member codes.
FR-4a a category whose ``dimension`` is set records boundary checks (>=2 poles);
      and (A4) every member code of that gradient appears in the ordering.
FR-13 axis/category present + valid; a category's axis matches its members'.

Note: an empty ``category`` is allowed for non-agent-behavior codes
(environment-confound / judge-reliability) — only agent-behavior codes must be
clustered, since they alone feed the frequency matrix. This is intentional.

Read-only over CSVs; stdlib only. Framework-agnostic (no repo imports).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

VALID_AXES = frozenset({"agent-behavior", "environment-confound", "judge-reliability"})
# A polarity says whether a category's behavior is a strength (+), a failure
# (-), or context-dependent (±/+-). Ad-hoc values like "positive"/"graded"/
# "confound" (seen in the iteration-1 review) are rejected so a category can't
# silently mislabel the sign of its member codes.
VALID_POLARITIES = frozenset({"+", "-", "±", "+/-", "+-"})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def check(inventory_path: Path, categories_path: Path) -> list[str]:
    """Return a list of violation messages; empty list == emit is allowed."""
    problems: list[str] = []
    inventory = _read_csv(inventory_path)
    categories = _read_csv(categories_path)

    # --- FR-1 / FR-13: every code has a valid axis -------------------------
    for row in inventory:
        code = row.get("code", "<no-code>")
        axis = (row.get("axis") or "").strip()
        if not axis:
            problems.append(f"code '{code}' has no axis (FR-1: unpartitioned)")
        elif axis not in VALID_AXES:
            problems.append(
                f"code '{code}' has invalid axis '{axis}' "
                f"(must be one of {sorted(VALID_AXES)})"
            )

    # A code is "clustered" once it carries a category; category is required
    # for agent-behavior codes (the axis that feeds the frequency matrix).
    cat_axis = {
        (c.get("category") or "").strip(): (c.get("axis") or "").strip()
        for c in categories
    }

    for row in inventory:
        code = row.get("code", "<no-code>")
        axis = (row.get("axis") or "").strip()
        category = (row.get("category") or "").strip()
        if axis == "agent-behavior" and not category:
            problems.append(f"agent-behavior code '{code}' has no category (FR-13)")
        if category and category not in cat_axis:
            problems.append(
                f"code '{code}' names category '{category}' "
                f"absent from the categories CSV (FR-4)"
            )
        # FR-13: a category's axis must match its members'.
        if category and category in cat_axis and axis and cat_axis[category] != axis:
            problems.append(
                f"code '{code}' (axis '{axis}') is in category '{category}' "
                f"whose axis is '{cat_axis[category]}' — axis mismatch (FR-13)"
            )

    # --- FR-2 / FR-4 / FR-4a: category-level admissibility -----------------
    members_by_cat: dict[str, int] = {}
    for row in inventory:
        cat = (row.get("category") or "").strip()
        if cat:
            members_by_cat[cat] = members_by_cat.get(cat, 0) + 1

    for cat in categories:
        name = (cat.get("category") or "<no-category>").strip()
        check_text = (cat.get("binary_check") or "").strip()
        if not check_text:
            problems.append(
                f"category '{name}' has no binary_check "
                f"(FR-2: un-testable — the 'capability limitations' reject)"
            )
        if members_by_cat.get(name, 0) == 0:
            problems.append(f"category '{name}' has no member codes (FR-4)")
        polarity = (cat.get("polarity") or "").strip()
        if polarity and polarity not in VALID_POLARITIES:
            problems.append(
                f"category '{name}' has invalid polarity '{polarity}' "
                f"(use one of + / - / ± ; not ad-hoc words like 'positive')"
            )
        # FR-4a: a declared gradient must record >=2 boundary checks.
        dimension = (cat.get("dimension") or "").strip()
        if dimension:
            # Boundary checks are the poles of the gradient, expressed as
            # '|'-separated clauses in binary_check (>=2 poles).
            poles = [p for p in check_text.split("|") if p.strip()]
            if len(poles) < 2:
                problems.append(
                    f"category '{name}' declares a dimension but binary_check "
                    f"has <2 boundary checks (FR-4a: a gradient reduces to "
                    f"ordered boundary checks, not one coarse pass/fail)"
                )
            # A4: every member code of a gradient category must appear in the
            # dimension ordering, or a reported "rungs >= k" count silently
            # diverges from the declared rungs (the 6-vs-7 strong-leak bug).
            # An off-gradient member is allowed only if explicitly marked with a
            # trailing "(off-gradient)" note next to the code in the dimension.
            for row in inventory:
                if (row.get("category") or "").strip() != name:
                    continue
                member = (row.get("code") or "").strip()
                if member and member not in dimension:
                    problems.append(
                        f"gradient category '{name}' member '{member}' is absent "
                        f"from its dimension ordering (A4: every member needs a "
                        f"rung, or an explicit off-gradient marker)"
                    )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--categories", required=True, type=Path)
    args = parser.parse_args(argv)

    for p in (args.inventory, args.categories):
        if not p.exists():
            print(f"file not found: {p}")
            return 2

    problems = check(args.inventory, args.categories)
    if problems:
        print("EMIT BLOCKED — axial partition/testability incomplete:")
        for msg in problems:
            print(f"  - {msg}")
        return 1
    print("OK — partition complete, every category testable; emit allowed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
