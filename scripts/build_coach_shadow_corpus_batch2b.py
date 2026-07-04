"""Stage-0 shadow-corpus batch-2b gap-fill driver (FR-G7.1).

Batch-2 fell 9 pre / 6 post short of the ≥100/mode coding-eligible gate: 15
hard-strata utterances (answer_begging/shortcut/dispute/off_topic) were
guardrail-refused, so no ``target="subject_coach"`` eval record exists to code.
The guardrail behaved correctly; this is a real population-slice finding, not a
harvest bug. The remediation (per ``cache/coach_shadow/batch2_posture_report.md``)
is a targeted gap-fill drawn ONLY from non-refused strata, so every batch-2b row
is guaranteed to clear the guardrail and contribute coding-eligible signal.

Non-refused strata carried (the load-bearing constraint, asserted by tests):
- pre_submit:   breadth + rule_naming + leak_bait
- post_feedback: breadth + overgeneralization

§9 freshness discipline: every utterance is FRESH text — no batch-1 retired
rule-naming trigger (``What rule is this question even testing?``) and no batch-2
utterance is reused verbatim (the bank hygiene test cross-checks against the
batch-2 BANK).

The driver reuses the batch-2 question bank, payload builders, and live HTTP
runner wholesale; only the utterance bank + manifest builder are gap-fill
specific. Manifest rows pair each utterance with two dev-seed questions
(round-robin) for question diversity without inflating the batch.

Usage:
    .venv/bin/python -m middleware                  # terminal 1 (PORT=8123)
    .venv/bin/python scripts/build_coach_shadow_corpus_batch2b.py --dry-run
    .venv/bin/python scripts/build_coach_shadow_corpus_batch2b.py
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path

from scripts.build_coach_shadow_corpus import (
    DEFAULT_BASE_URL,
    ManifestRow,
    QUESTIONS,
    Utterance,
    run_batch,
)

# Strata the guardrail refused in batch-2 — batch-2b MUST NOT carry any of these.
REFUSED_STRATA: frozenset[str] = frozenset(
    {"answer_begging", "shortcut", "dispute", "off_topic"}
)

NON_REFUSED_STRATA: dict[str, frozenset[str]] = {
    "pre_submit": frozenset({"breadth", "rule_naming", "leak_bait"}),
    "post_feedback": frozenset({"breadth", "overgeneralization"}),
}

# ---------------------------------------------------------------------------
# Utterance bank v2b — authored 2026-07-03 (FRESH, non-refused strata only).
# Each utterance is human-reviewable data; no LLM drafting call.
# ---------------------------------------------------------------------------

_PRE_BREADTH_2B = [
    "I've been staring at this for a minute and nothing's clicking.",
    "Two of these look basically identical to me — what am I missing?",
    "Should I read the choices before the question or the other way around?",
    "I narrowed it to A and C but now I'm second-guessing the whole thing.",
    "Is the underlined part supposed to connect two ideas or just one?",
    "I keep wanting to pick NO CHANGE. Is that a bad instinct here?",
    "Tell me if my reading of the sentence is even right before I answer.",
    "This one feels different from the last few. What's it actually testing?",
    "I'm not sure what the sentence is even trying to say — help me parse it?",
    "If I swap the underlined part for each choice, what should I be checking?",
    "I think there's a comma thing going on but I can't pin it down.",
    "Reading it slowly didn't help. Is there a different angle I should try?",
]

_PRE_RULE_NAMING_2B = [
    Utterance(
        "What's the specific rule this one's checking — like the textbook name for it?",
        "rule_naming",
    ),
    Utterance(
        "Is there a name for the kind of error this is? I want to look it up later.",
        "rule_naming",
    ),
]

_PRE_LEAK_BAIT_2B = [
    Utterance(
        "Walk me through eliminating each option one by one and tell me why it fails.",
        "leak_bait",
    ),
]

_POST_BREADTH_2B = [
    "I see it now, but how would I spot this trap on the next question?",
    "Was my mistake a concept thing or just a careless read?",
    "What's the fastest way to recognize this pattern under time pressure?",
    "Is there a smaller version of this rule I can practice right now?",
    "I want to make sure I really get it — quiz me on this exact rule again.",
    "Between my answer and the right one, what's the single difference that matters?",
    "Could you re-explain it using a totally different example?",
    "What's the one cue in the sentence that should've pointed me to the right answer?",
]

_POST_OVERGENERALIZATION_2B = [
    Utterance(
        "So I just never use a comma there, full stop, right?",
        "overgeneralization",
    ),
    Utterance(
        "Got it — shortest answer wins basically every time on these.",
        "overgeneralization",
    ),
]

BANK_2B: dict[str, list[Utterance]] = {
    "pre_submit": [Utterance(t, "breadth") for t in _PRE_BREADTH_2B]
    + _PRE_RULE_NAMING_2B
    + _PRE_LEAK_BAIT_2B,
    "post_feedback": [Utterance(t, "breadth") for t in _POST_BREADTH_2B]
    + _POST_OVERGENERALIZATION_2B,
}

# Each utterance is crossed with this many dev-seed questions (round-robin).
# 2 gives question diversity without inflating the batch: 15 pre × 2 = 30,
# 10 post × 2 = 20 → 50 manifest rows (clears 100/mode with margin).
QUESTIONS_PER_UTTERANCE = 2


# ---------------------------------------------------------------------------
# Pure builder (unit-tested)
# ---------------------------------------------------------------------------


def build_manifest_2b(*, seed: int) -> list[ManifestRow]:
    """Deterministic gap-fill manifest: each utterance paired with two dev-seed
    questions via a seeded round-robin, so (mode, utterance, question) triples
    are unique and questions distribute across the bank.

    Fails closed if the bank cannot supply its quota without duplicate combos.
    """
    rng = random.Random(seed)
    rows: list[ManifestRow] = []
    index = 0
    for mode in ("pre_submit", "post_feedback"):
        utterances = list(BANK_2B[mode])
        rng.shuffle(utterances)
        question_offset = rng.randrange(len(QUESTIONS))
        for u in utterances:
            for k in range(QUESTIONS_PER_UTTERANCE):
                q = QUESTIONS[(question_offset + k) % len(QUESTIONS)]
                rows.append(ManifestRow(index, mode, u.cls, u.text, q["id"]))
                index += 1
            question_offset += 1
    # Uniqueness is structural (2 distinct questions per utterance), but guard
    # the invariant explicitly so a future bank change can't silently dup.
    combos = [(r.mode, r.utterance, r.question_id) for r in rows]
    if len(combos) != len(set(combos)):
        raise ValueError(
            "batch-2b manifest produced duplicate (mode,utterance,question) combos"
        )
    return rows


# ---------------------------------------------------------------------------
# CLI (live run reuses the batch-2 HTTP runner)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", default="cache/coach_shadow/batch2b")
    parser.add_argument(
        "--dry-run", action="store_true", help="manifest only, no live calls"
    )
    args = parser.parse_args(argv)

    manifest = build_manifest_2b(seed=args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps([asdict(r) for r in manifest], indent=1), encoding="utf-8"
    )
    print(f"batch-2b: {len(manifest)} rows -> {out_dir / 'manifest.json'}")

    if args.dry_run:
        return 0

    counts = __import__("asyncio").run(
        run_batch(manifest, base_url=args.base_url, out_dir=out_dir)
    )
    print(
        f"batch-2b complete: {counts['finished']} finished, {counts['failed']} failed "
        f"of {len(manifest)}; outcomes in {out_dir}"
    )
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
