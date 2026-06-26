"""Build the BLINDED L2/L3 adjudication set from harvested answers.

Phase 2 of the blind-adjudication plan (docs/plans/
model_ab_l2l3_blind_adjudication.plan.md). The rater (agent or human) must NOT know
which model produced an answer, or labels inherit the hypothesis bias — this is the
load-bearing guardrail on "agent-as-reviewer". So we emit one anonymized item per
(case x arm) with NO model/arm identifier, shuffled, and write the arm<->item_id
mapping to a SEPARATE sealed file opened only AFTER grading is frozen.

Inputs:
  - cache/model_ab_answer/l2l3_raw_answers.json  ({arm: {case: answer}})
  - cache/model_ab_answer/l2l3_batch.jsonl        (case -> prompt)
  - cache/model_ab_answer/l2l3_answer_keys.json   (case -> rubric facts)

Outputs:
  - cache/model_ab_answer/l2l3_blind_items.jsonl  (NO arm info; the grading input)
  - cache/model_ab_answer/l2l3_arm_key.sealed.json (item_id -> {case, arm}; sealed)

item_id is a stable hash (uuid5 of case|arm|answer) so re-runs are deterministic and
the sealed key round-trips. Empty-answer cells are SKIPPED with a warning (a blank
item can't be graded; surfaced so the operator re-harvests, never silently graded).
The blind item carries ``case`` + ``rubric`` so the rater can grade, but ``case`` is
NOT a model identifier — every arm shares the same 9 cases, so it leaks nothing.
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
RAW = ANSWER_DIR / "l2l3_raw_answers.json"
BATCH = ANSWER_DIR / "l2l3_batch.jsonl"
KEYS = ANSWER_DIR / "l2l3_answer_keys.json"
BLIND_OUT = ANSWER_DIR / "l2l3_blind_items.jsonl"
SEALED_OUT = ANSWER_DIR / "l2l3_arm_key.sealed.json"

# Fixed seed: the shuffle must be reproducible (so re-running yields the same
# blind set), but the order still hides arm grouping from the rater.
SHUFFLE_SEED = 1729


def _prompts_by_case(batch: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in batch.read_text().splitlines():
        line = line.strip()
        if line:
            row = json.loads(line)
            out[row["case"]] = row.get("prompt", "")
    return out


def build_blind_set(
    raw: Path = RAW,
    batch: Path = BATCH,
    keys: Path = KEYS,
    seed: int = SHUFFLE_SEED,
) -> tuple[list[dict], dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Return (blind_items, sealed_key, skipped).

    blind_items: shuffled, NO arm info.
    sealed_key:  item_id -> {case, arm}.
    skipped:     (arm, case) pairs dropped for an empty answer.
    """
    answers = json.loads(raw.read_text())
    prompts = _prompts_by_case(batch)
    rubrics = json.loads(keys.read_text())

    items: list[dict] = []
    sealed: dict[str, dict[str, str]] = {}
    skipped: list[tuple[str, str]] = []

    for arm in sorted(answers):
        for case in sorted(answers[arm]):
            text = answers[arm][case]
            if not text or not text.strip():
                skipped.append((arm, case))
                continue
            item_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{case}|{arm}|{text}").hex
            items.append({
                "item_id": item_id,
                "case": case,
                "prompt": prompts.get(case, ""),
                "rubric": rubrics.get(case, {}),
                "model_answer": text,
            })
            sealed[item_id] = {"case": case, "arm": arm}

    random.Random(seed).shuffle(items)
    return items, sealed, skipped


def write_outputs(
    items: list[dict],
    sealed: dict[str, dict[str, str]],
    blind_out: Path = BLIND_OUT,
    sealed_out: Path = SEALED_OUT,
) -> None:
    blind_out.parent.mkdir(parents=True, exist_ok=True)
    blind_out.write_text("\n".join(json.dumps(it) for it in items) + "\n")
    sealed_out.write_text(json.dumps(sealed, indent=2) + "\n")


# Substrings that would leak an arm/model identity into a blind item. The builder
# never copies arm info into items, but we assert against accidental leakage from
# an answer that names its own model (some models self-identify).
ARM_LEAK_TOKENS = (
    "claude", "haiku", "opus", "sonnet", "gpt-4", "gpt-5", "gpt4", "gpt5",
    "deepseek", "openai", "anthropic", "baseline", "candidate",
)


def leak_scan(items: list[dict]) -> list[tuple[str, str]]:
    """Return (item_id, token) for any arm/model token found in a blind item's
    NON-answer fields (item_id/case/prompt/rubric). The model_answer is exempt: a
    model self-identifying in prose is part of what the rater sees, but it must not
    appear in the structural fields we control."""
    hits: list[tuple[str, str]] = []
    for it in items:
        blob = " ".join([
            it["item_id"], it["case"], it.get("prompt", ""),
            json.dumps(it.get("rubric", {})),
        ]).lower()
        for tok in ARM_LEAK_TOKENS:
            if tok in blob:
                hits.append((it["item_id"], tok))
    return hits


if __name__ == "__main__":
    items, sealed, skipped = build_blind_set()
    write_outputs(items, sealed)
    print(f"wrote {len(items)} blind items -> {BLIND_OUT}")
    print(f"wrote sealed key ({len(sealed)} ids) -> {SEALED_OUT}")
    if skipped:
        print(f"SKIPPED (empty answer) {len(skipped)}:")
        for arm, case in skipped:
            print(f"  {arm}  {case}")
    leaks = leak_scan(items)
    if leaks:
        print(f"LEAK WARNING: arm tokens in structural fields ({len(leaks)}):")
        for iid, tok in leaks[:10]:
            print(f"  {iid}  '{tok}'")
    else:
        print("blinding OK: no arm tokens in structural fields")
