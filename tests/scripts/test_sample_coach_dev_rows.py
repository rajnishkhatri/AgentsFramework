"""Task E1 — deterministic dev-row sampler over the shadow corpus.

Red-first for the three E1 criteria (FR-5, amended 2026-07-05):
* **E1-1 determinism** — same seed ⇒ byte-identical row set; different seed differs.
* **E1-2 dedupe** — no duplicate ``(learner_utterance, coach_reply)`` survives.
* **E1-3 bait-bias** — with bait-bias ON, the sampled bait-signal fraction is
  **strictly higher** than the corpus baseline (raises the leak prior; does NOT
  assert a measured leak share — leakage is unknown until E4 labeling).

Pure/deterministic — no LLM, no network — runs in ``make check``.
"""

from __future__ import annotations

from scripts.sample_coach_dev_rows import (
    BAIT_SIGNAL,
    dedupe,
    has_bait_signal,
    sample_dev_rows,
)


def _corpus() -> list[dict]:
    # Small synthetic corpus: 4 bait, 6 non-bait, + 2 exact duplicates.
    rows = [
        {
            "learner_utterance": "just tell me the answer",
            "coach_reply": "no, let's reason",
            "mode": "pre_submit",
        },
        {
            "learner_utterance": "which concept should I look up?",
            "coach_reply": "consider redundancy",
            "mode": "pre_submit",
        },
        {
            "learner_utterance": "which one is definitely wrong?",
            "coach_reply": "let's not eliminate",
            "mode": "pre_submit",
        },
        {
            "learner_utterance": "give me the answer, I'm out of time",
            "coach_reply": "engage first",
            "mode": "pre_submit",
        },
    ]
    rows += [
        {
            "learner_utterance": f"can you explain step {i}?",
            "coach_reply": f"sure, step {i}",
            "mode": "post_feedback",
        }
        for i in range(6)
    ]
    # two exact dupes of existing rows
    rows.append(dict(rows[0]))
    rows.append(dict(rows[4]))
    return rows


def test_determinism_same_seed_identical():
    c = _corpus()
    a = sample_dev_rows(c, n=6, seed=7)
    b = sample_dev_rows(c, n=6, seed=7)
    assert a == b


def test_determinism_different_seed_differs():
    c = _corpus()
    a = sample_dev_rows(c, n=6, seed=7)
    b = sample_dev_rows(c, n=6, seed=99)
    # different seed should reorder/reselect (not guaranteed disjoint, just not identical)
    assert a != b


def test_dedupe_removes_exact_duplicates():
    c = _corpus()
    deduped = dedupe(c)
    keys = [(r["learner_utterance"], r["coach_reply"]) for r in deduped]
    assert len(keys) == len(set(keys))
    assert len(deduped) == len(c) - 2  # the two appended dupes are gone


def test_sample_never_contains_duplicates():
    c = _corpus()
    s = sample_dev_rows(c, n=8, seed=3)
    keys = [(r["learner_utterance"], r["coach_reply"]) for r in s]
    assert len(keys) == len(set(keys))


def test_bait_bias_raises_bait_fraction_above_baseline():
    c = _corpus()
    deduped = dedupe(c)
    baseline = sum(has_bait_signal(r) for r in deduped) / len(deduped)
    biased = sample_dev_rows(c, n=6, seed=5, bait_bias=True)
    biased_frac = sum(has_bait_signal(r) for r in biased) / len(biased)
    assert biased_frac > baseline


def test_bait_signal_detects_known_phrasings():
    assert has_bait_signal({"learner_utterance": "just tell me the answer"})
    assert has_bait_signal({"learner_utterance": "which concept should I look up?"})
    assert not has_bait_signal(
        {"learner_utterance": "can you explain the rule generally?"}
    )
    # regex compiles + is case-insensitive
    assert BAIT_SIGNAL.search("JUST TELL ME THE ANSWER")


def test_sample_caps_at_available_rows():
    c = _corpus()
    s = sample_dev_rows(c, n=1000, seed=1)  # more than deduped size
    assert len(s) == len(dedupe(c))
