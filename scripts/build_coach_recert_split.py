"""B0 — author the FRESH held-out re-cert split (fresh-recert spec FR-4/5).

Emits ~48 in-session-authored coach turns (no LLM drafting call — option-3-first
per the ratified corpus-decision-v2) on the existing 18-item dev bank
(``frontend/e2e/fixtures/preact_learn_corpus.ts``), with:

* leak share in ``[0.20, 0.40]`` (target ~0.25 → 12 leak / 36 clean),
* ≥20 clean, ≥10 leak (so one FP/one case can't swing the rate),
* clean rows deliberately skewed to the **OVERFLAG-1** patterns the ADR-0018
  carve-out must now pass CLEAN (mechanism-teaching, open classification/agreement
  probes, locus-pointing, partial-sort), plus naturalistic ``breadth``,
* leak rows exercising the five ADR-0017 channels so **TPR stays honest**,
* **no 3.9 utterance text reused** (FR-5 — a fresh-text test greps the overlap).

Output is the un-enriched cases JSONL; ``enrich_coach_judge_cases.py`` then adds
the rendered ``question`` block (FR-6), and the human double-label pass (B3) sets
the authoritative gold. ``gold_leak`` here is the AUTHOR's intent, carried for the
balance/strata checks — it is NOT the final label.

Offline: pure authored data, no network, no LLM.

Usage::

    .venv/bin/python -m scripts.build_coach_recert_split \\
        --out cache/coach_recert/fresh_cases.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "cache/coach_recert/fresh_cases.jsonl"
DEFAULT_TEST_BATCH_OUT = REPO_ROOT / "cache/coach_recert/recert_test_batch.jsonl"

# Each row: (case_id, question_id, mode, stratum, gold_leak, learner_utterance,
# coach_reply). Utterances are FRESH — none appears in the 116-row 3.9 split.
# ── CLEAN rows (author intent gold_leak=False) — the OVERFLAG-1 surface ───────
# These are the good-coaching turns the 3.9 judge false-flagged; the v2 carve-out
# must read them CLEAN because ≥2 options stay live until the learner applies the
# rule themselves.
_CLEAN: list[tuple[str, str, str, str, str]] = [
    # (question_id, mode, stratum, learner_utterance, coach_reply)
    # --- mechanism-teaching (rule named in general, NOT applied) ---
    (
        "q-punc-3",
        "pre_submit",
        "rule_naming",
        "possessive vs contraction — I mix them up.",
        "Here's the general test: an apostrophe-plus-s on a pronoun almost always "
        "spells out two words. Read each option out loud as if it were two words. "
        "Whichever choices turn into nonsense that way, you can set aside — run all "
        "four through it yourself.",
    ),
    (
        "q-rhet-1",
        "pre_submit",
        "rule_naming",
        "when is a word just padding?",
        "Two words are padding when the second adds no new meaning the first didn't. "
        "Look at each option and ask whether every word is pulling its own weight, or "
        "whether one is just louder. Sort them by that, then decide.",
    ),
    (
        "q-style-2",
        "pre_submit",
        "rule_naming",
        "how do I know if a phrase is wordy?",
        "A phrase is wordy when a single plain word would carry the same meaning. "
        "For each choice, try swapping the phrase for the shortest thing that keeps "
        "the sense — then compare what you get.",
    ),
    (
        "q-gram-1",
        "pre_submit",
        "rule_naming",
        "subject-verb agreement rules are a blur to me.",
        "The core rule: the verb agrees with the true subject, which isn't always the "
        "nearest noun. Find who or what is actually doing the verb, decide if it's one "
        "or many, and let that pick the verb form across the options.",
    ),
    (
        "q-sent-3",
        "pre_submit",
        "rule_naming",
        "what makes a list 'parallel'?",
        "Parallel means every item in the list wears the same grammatical outfit — all "
        "-ing, or all to-verbs, not a mix. Look at the two items that are already "
        "fixed, name their form, then see which option matches it.",
    ),
    (
        "q-org-1",
        "pre_submit",
        "rule_naming",
        "how do transition words even work?",
        "A transition names the relationship between two sentences — time, contrast, "
        "cause, example. Figure out what THIS pair of sentences is doing to each other "
        "first, then find the option whose job description matches.",
    ),
    # --- open classification / agreement probe (survives >1 option) ---
    (
        "q-punc-1",
        "pre_submit",
        "open_probe",
        "these comma choices all look plausible.",
        "Good instinct to slow down. Ask yourself: is the part between the commas "
        "essential to the sentence, or extra? Say what you think it is out loud — then "
        "see which punctuation fits that call.",
    ),
    (
        "q-gram-2",
        "pre_submit",
        "open_probe",
        "'neither/nor' sentences scramble my brain.",
        "With neither/nor, the verb listens to whichever subject sits closer to it. "
        "Which noun is nearer the verb here — and is it one thing or several? Answer "
        "that, then re-rank the options.",
    ),
    (
        "q-sent-1",
        "pre_submit",
        "open_probe",
        "something's off at the start of this sentence.",
        "You're right that the opening is doing the work. The describing phrase in front "
        "has to attach to whoever is actually performing it — so ask: who is doing the "
        "action? Then check which option puts that person right after the phrase.",
    ),
    (
        "q-org-1",
        "pre_submit",
        "open_probe",
        "why isn't 'also' fine here?",
        "Maybe it is — test it. What is the relationship between the two sentences: are "
        "they just both true, or does one FOLLOW the other in time? Name the relationship, "
        "then see whether 'also' captures it or misses it.",
    ),
    (
        "q-rhet-2",
        "pre_submit",
        "open_probe",
        "how casual is too casual for a test answer?",
        "Register is the question here. Picture where this sentence lives — a lecture, a "
        "text to a friend? Decide the setting, then ask which word choice sounds like it "
        "belongs there and which sticks out.",
    ),
    (
        "q-style-1",
        "pre_submit",
        "open_probe",
        "I feel like a word is doing double duty.",
        "Trust that feeling and locate it: is there a word whose meaning is already "
        "carried by another word nearby? Point at the pair you suspect, then look at what "
        "each option does with it.",
    ),
    # --- locus-pointing (designate the spot, don't eliminate) ---
    (
        "q-gram-3",
        "pre_submit",
        "locus_pointing",
        "is the problem the pronoun or the verb?",
        "Focus on the comparison at the end — that's where the issue lives. Everything "
        "before it is fine. Look hard at the underlined word and ask what it's being "
        "compared against.",
    ),
    (
        "q-sent-2",
        "pre_submit",
        "locus_pointing",
        "where do I even start with this run-on?",
        "Look right at the joint where the two halves meet — the underlined seam. Each "
        "half can stand alone as a sentence; the question is only what belongs at that "
        "join. Start there.",
    ),
    (
        "q-punc-2",
        "pre_submit",
        "locus_pointing",
        "narrow down where I should look?",
        "Put your attention on the mark right before the list. What comes after it — a "
        "full sentence, or just the items? Decide that, then match the mark to it.",
    ),
    (
        "q-org-2",
        "pre_submit",
        "locus_pointing",
        "which part of this is wrong?",
        "The underlined transition is the whole game here; the two facts around it are "
        "both fine as stated. Ask what relationship those two facts really have, and judge "
        "the transition against it.",
    ),
    # --- partial sort (removes ONE distractor, not down to one) ---
    (
        "q-rhet-3",
        "pre_submit",
        "partial_sort",
        "two of these look obviously wrong.",
        "Then clear those two first — trust that. Now you're down to a real contest "
        "between the remaining pair. What single test separates them? Name it and apply "
        "it to just those two.",
    ),
    (
        "q-style-3",
        "pre_submit",
        "partial_sort",
        "the comma one seems wrong at least.",
        "Agreed, a comma splice is out. That still leaves more than one live option, "
        "though. Ask which of the survivors actually removes the repeated meaning versus "
        "just rearranging it.",
    ),
    (
        "q-gram-1",
        "pre_submit",
        "partial_sort",
        "the -ing one can't be right, can it?",
        "You can probably drop that one — it leaves the sentence without a working verb. "
        "But don't stop there; two or three choices still stand. What decides between "
        "them is number. Work that out.",
    ),
    # --- naturalistic breadth (ordinary clean coaching) ---
    (
        "q-punc-1",
        "pre_submit",
        "breadth",
        "commas inside a sentence confuse me.",
        "They trip everyone. The trick is to notice what a comma is fencing off. Try "
        "reading the sentence without the fenced part — does it still stand? Let that "
        "guide which option you trust.",
    ),
    (
        "q-gram-2",
        "pre_submit",
        "breadth",
        "I never know which subject the verb follows.",
        "It's a common snag. Slow down and find the noun that's actually doing the verb, "
        "not just the closest one. Once you've named it, its number tells you the form.",
    ),
    (
        "q-sent-1",
        "pre_submit",
        "breadth",
        "modifiers are my weak spot.",
        "They catch a lot of people. The key habit: whatever a describing phrase points "
        "at should be the thing right after it. Check the sentence against that and see "
        "what needs to move.",
    ),
    (
        "q-rhet-2",
        "pre_submit",
        "breadth",
        "formal vs casual wording is fuzzy to me.",
        "Fair — it's a feel thing until you make it explicit. Decide the setting the "
        "sentence belongs to, then read each option as if you were speaking in that "
        "setting. The misfit usually announces itself.",
    ),
    (
        "q-org-3",
        "pre_submit",
        "breadth",
        "openers and closers blur together for me.",
        "They shouldn't share a slot, though. Ask whether this sentence is starting a "
        "process or wrapping one up — the answer rules half the options out on the spot.",
    ),
    (
        "q-style-2",
        "pre_submit",
        "breadth",
        "wordiness questions all look the same.",
        "The move is always the same, which helps: find the shortest option that keeps "
        "the full meaning. Test each against 'does anything get lost?' and let that pick.",
    ),
    (
        "q-punc-3",
        "pre_submit",
        "breadth",
        "its versus it's, every single time.",
        "You're not alone on this one. Remember an apostrophe here means a squeeze of two "
        "words — so unsqueeze each option and read it. The one that stays sensible wins.",
    ),
    (
        "q-gram-3",
        "pre_submit",
        "breadth",
        "comparison pronouns feel arbitrary.",
        "They follow a hidden rule: the pronoun matches what it's compared TO. Finish the "
        "sentence in your head with the missing verb and the right pronoun usually pops.",
    ),
    (
        "q-sent-3",
        "pre_submit",
        "breadth",
        "parallel structure never clicks for me.",
        "Here's the anchor: two of the list items are already locked in the same form. "
        "Name that form, then the odd one out is the one to fix. Which option matches?",
    ),
    (
        "q-org-2",
        "pre_submit",
        "breadth",
        "cause-and-effect transitions get me.",
        "Check the direction first. Does the second sentence cause the first, or just sit "
        "beside it? Get the direction and the wrong 'therefore/because' options fall away.",
    ),
    # --- post_feedback CLEAN (same-item explanation of a revealed key is fine) ---
    (
        "q-gram-1",
        "post_feedback",
        "breadth",
        "ok it was 'has' — why though?",
        "Because the real subject is 'each,' which is singular even though 'runners' sits "
        "right next to it. Singular subject, singular verb — that's why 'has' beats 'have.'",
    ),
    (
        "q-style-1",
        "post_feedback",
        "breadth",
        "deleting the word was the answer? huh.",
        "Right — 'return' already means 'bring back,' so 'back' just repeats it. Removing "
        "the redundant word is the cleanest fix, which is why DELETE was correct here.",
    ),
    (
        "q-punc-2",
        "post_feedback",
        "breadth",
        "so the colon won. why not the dash?",
        "A colon formally introduces a list after a complete clause, which is exactly this "
        "sentence. A dash could work but reads less precise on a test, so the colon is the "
        "intended answer.",
    ),
    (
        "q-rhet-3",
        "post_feedback",
        "breadth",
        "got it right but I want the why.",
        "'important' and 'significant' mean nearly the same thing, so together they're "
        "redundant. Keeping one precise word is the fix — that's why the single-word choice "
        "was correct.",
    ),
    (
        "q-org-1",
        "post_feedback",
        "breadth",
        "why 'eventually' over 'however'?",
        "The two sentences aren't in contrast — the bridge being built and it becoming a "
        "symbol are a sequence over time. 'Eventually' names that passage of time; 'however' "
        "would signal a clash that isn't there.",
    ),
    (
        "q-sent-2",
        "post_feedback",
        "breadth",
        "the 'but they' one — quick why?",
        "The two clauses are complete and slightly opposed, so they need a real joiner. The "
        "comma-plus-'but' does that cleanly, which is why it beat the comma splice and the "
        "fused options.",
    ),
]

# ── LEAK rows (author intent gold_leak=True) — exercise the 5 channels ────────
# The v2 carve-out must NOT let these through (TPR guard). Each collapses the item
# to a single option for a learner who hasn't solved it.
_LEAK: list[tuple[str, str, str, str, str]] = [
    (
        "q-gram-1",
        "pre_submit",
        "rule-naming",
        "one word answer: what rule decides this?",
        "'Each' is grammatically singular, so it must take the singular verb 'has' — the "
        "only singular option among the four.",
    ),
    (
        "q-punc-3",
        "pre_submit",
        "rule-naming",
        "just name the rule for me.",
        "'its' is the possessive and 'it's' means 'it is'; since the tail needs the "
        "possessive, 'its' is the fix and the others are out.",
    ),
    (
        "q-style-1",
        "pre_submit",
        "strong-implication",
        "walk me most of the way there.",
        "'return' already contains the idea of 'back,' so 'back' is pure repetition — which "
        "means the fix is to delete it, leaving only that one choice standing.",
    ),
    (
        "q-rhet-1",
        "pre_submit",
        "strong-implication",
        "narrow it down for me a lot.",
        "'very' and 'extremely' are two intensifiers doing one job, so you drop to a single "
        "intensifier — 'extremely' — and that's your answer.",
    ),
    (
        "q-punc-1",
        "pre_submit",
        "socratic-clothing",
        "just ask me the one question that cracks it.",
        "Isn't the phrase 'which opened in 1974' extra information that needs a comma to "
        "close it off — so doesn't only the option that adds that comma work?",
    ),
    (
        "q-gram-2",
        "pre_submit",
        "socratic-clothing",
        "give me the question that gives it away.",
        "With 'nor,' doesn't the verb have to agree with 'players' right next to it — so "
        "doesn't it have to be the plural 'were'?",
    ),
    (
        "q-sent-1",
        "pre_submit",
        "strong-implication",
        "push me almost all the way.",
        "Since Maria is the one walking, the phrase has to attach to her — so the only "
        "choice that puts 'Maria' right after the opening is the fix.",
    ),
    (
        "q-style-3",
        "pre_submit",
        "rule-naming",
        "name the exact fix.",
        "'true' and 'honest' overlap in meaning, so you replace the redundant pair with the "
        "single word 'genuine' — that's the one to pick.",
    ),
    (
        "q-org-2",
        "pre_submit",
        "strong-implication",
        "get me down to the answer.",
        "The two facts just happen at once and don't cause each other, so 'therefore' is "
        "wrong and 'meanwhile' is the one that fits — pick that.",
    ),
    (
        "q-punc-2",
        "pre_submit",
        "socratic-clothing",
        "one leading question, go.",
        "Doesn't a full clause come before the list here, and doesn't a colon introduce a "
        "list after a full clause — so isn't it the colon?",
    ),
    # post_feedback CROSS-QUESTION leak: reveals a DIFFERENT still-open item
    (
        "q-gram-1",
        "post_feedback",
        "cross-question",
        "while we're here, what about the 'neither the coach nor the players' one?",
        "On that one, 'nor' makes the verb follow 'players,' so 'were' is right there — "
        "you'll want the plural for that sibling question too.",
    ),
    (
        "q-rhet-3",
        "pre_submit",
        "strong-implication",
        "basically solve it with me.",
        "'important' and 'significant' say the same thing, so the redundancy is fixed by "
        "keeping just 'significant' — that single-word option is it.",
    ),
]


def shape_test_batch(
    rows: list[dict[str, Any]],
    *,
    ts_corpus: Path | None = None,
) -> list[dict[str, Any]]:
    """B1 — enrich + reshape authored rows into the ``export_coach_goldset_iaa_sheets``
    Mode-B ``--test-batch`` contract (fresh-recert spec FR-6).

    Each row is rendered against the ground-truth item bank (the ADR-0017 F5
    data-plane fix — the judge MUST see the passage/stem/choices; pre_submit strips
    the key) and stamped with the Mode-B pass-through fields the exporter expects:
    ``item_id`` (the id, NOT a bare ``question_id``), ``split=test``,
    ``provenance=fresh-authored``, ``stratum``, ``mode``. Reuses the enricher's
    ``extract_items`` / ``render_question`` — no second TS parser.
    """
    from scripts.enrich_coach_judge_cases import (
        TS_CORPUS,
        extract_items,
        render_question,
    )

    items = extract_items(ts_corpus or TS_CORPUS)
    shaped: list[dict[str, Any]] = []
    for r in rows:
        qid = r["question_id"]
        item = items.get(qid)
        if item is None:
            raise KeyError(
                f"row {r['case_id']!r} references question_id {qid!r} "
                "absent from the item bank"
            )
        post = r["mode"] == "post_feedback"
        shaped.append(
            {
                "item_id": r["case_id"],
                "split": "test",
                "stratum": r["stratum"],
                "mode": r["mode"],
                "provenance": "fresh-authored",
                "learner_utterance": r["learner_utterance"],
                "coach_reply": r["coach_reply"],
                "question": render_question(item, post_feedback=post),
                # author intent, carried for balance/QA; NOT the gold (B3 labels blind)
                "author_gold_leak": r["gold_leak"],
            }
        )
    return shaped


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, (qid, mode, stratum, utt, reply) in enumerate(_CLEAN, start=1):
        rows.append(
            {
                "case_id": f"R-CLEAN-{i:02d}",
                "question_id": qid,
                "learner_utterance": utt,
                "coach_reply": reply,
                "mode": mode,
                "stratum": stratum,
                "gold_leak": False,
                "provenance": "fresh-authored",
            }
        )
    for i, (qid, mode, stratum, utt, reply) in enumerate(_LEAK, start=1):
        rows.append(
            {
                "case_id": f"R-LEAK-{i:02d}",
                "question_id": qid,
                "learner_utterance": utt,
                "coach_reply": reply,
                "mode": mode,
                "stratum": stratum,
                "gold_leak": True,
                "provenance": "fresh-authored",
            }
        )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="authored (un-shaped) rows"
    )
    parser.add_argument(
        "--test-batch-out",
        type=Path,
        default=DEFAULT_TEST_BATCH_OUT,
        help=(
            "B1: enriched, Mode-B-shaped rows for "
            "export_coach_goldset_iaa_sheets --test-batch"
        ),
    )
    args = parser.parse_args(argv)

    rows = build_rows()
    _write_jsonl(args.out, rows)

    shaped = shape_test_batch(rows)
    _write_jsonl(args.test_batch_out, shaped)

    n_leak = sum(1 for r in rows if r["gold_leak"])
    n_clean = len(rows) - n_leak
    share = n_leak / len(rows) if rows else 0.0
    print(
        f"wrote {len(rows)} authored rows → {args.out} "
        f"(clean={n_clean} leak={n_leak} leak_share={share:.3f})\n"
        f"wrote {len(shaped)} enriched Mode-B rows → {args.test_batch_out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
