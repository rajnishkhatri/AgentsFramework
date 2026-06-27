"""Build the static L4 gate meta-benchmark fixture from the archived corpus.

One-shot conversion (R3.1 TDD step): labels every sample in
``r2_local_samples.json`` (70 real gpt-4o-mini regenerations, exact deployed
prompt, deploy ``tierA-prod-2026.06.0-e72920c``) with the punct-strip
grounding transform verified in ``r2_dot_verify.py`` (20/20 recovery, 48/50
stability, strictly monotone vs V0), and freezes the labels into
``tests/fixtures/task_understanding/gate_benchmark_v1.json``.

The labeling transform is INLINED — not imported from production — so the
labels are anchored to the evidence as verified on 2026-06-12 and cannot
drift if production constants change later. The benchmark test then asserts
production ``validate_conditions`` reproduces these labels (Pattern 5,
record/replay; no gate logic in the test itself — TAP-1 clean).

Run from repo root: python docs/research/goaljudge_tu_gate_longterm_plan/build_gate_benchmark_fixture.py
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVIDENCE_DIR.parents[2]
CORPUS = EVIDENCE_DIR / "r2_local_samples.json"
OUT = REPO_ROOT / "tests" / "fixtures" / "task_understanding" / "gate_benchmark_v1.json"

# ── frozen copy of the gate constants as deployed/verified (commit e72920c…
# HEAD 2026-06-12); see components/task_understanding.py for the live ones ──
_STOPWORDS = frozenset(
    """a an and are as at be been by for from has have in into is it its of on
    or that the their then there these this to was were will with without not
    no do does did done must should can could would you your the final answer
    agent task""".split()
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9._/-]*")
_MIN, _MAX, _MAXLEN = 2, 7, 200


def _base_tokens(text: str) -> set[str]:
    """V0 tokenizer: stopword-filter on RAW tokens (trailing punct intact)."""
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


def _strip(tokens: set[str]) -> set[str]:
    """The verified punct-strip: edge-strip '._/-' AFTER the stopword filter
    (exact r2_dot_verify.py order — the monotonicity proof depends on it)."""
    return {t.strip("._/-") for t in tokens} - {""}


def _grounding_fails(conditions: list[str], task: str, *, strip: bool) -> list[int]:
    xf = _strip if strip else (lambda s: s)
    task_tokens = xf(_base_tokens(task))
    return [
        i
        for i, c in enumerate(conditions)
        if task_tokens and not (xf(_base_tokens(c)) & task_tokens)
    ]


def _other_gate_issues(conditions: list[str]) -> list[str]:
    issues = []
    if not (_MIN <= len(conditions) <= _MAX):
        issues.append("count")
    if any(len(c) > _MAXLEN for c in conditions):
        issues.append("length")
    normalized = [" ".join(c.lower().split()) for c in conditions]
    if len(normalized) != len(set(normalized)):
        issues.append("dupe")
    return issues


# Adversarial on-vocabulary probe set from r2_gate_sim.py — fabricated
# requirements phrased fluently. The lexical gate is a topicality filter
# (longterm-plan finding #4): probes sharing a content token with the task
# GROUND and pass. The fixture pins that bound honestly.
ADVERSARIAL = [
    "The agent books a flight to Paris.",
    "The response includes a Python script that mines Bitcoin.",
    "The answer lists at least five French recipes.",
    "The agent emails the quarterly report to Bob.",
    "The output is a haiku about autumn leaves.",
    "The agent backs up the database before midnight.",
]


def main() -> None:
    corpus = json.loads(CORPUS.read_text())
    must_accept, must_reject = [], []
    skipped_unparsed = 0

    for group, origin in (
        ("failed", "failed_case_resample"),
        ("passing", "passing_case_resample"),
    ):
        for case, rec in sorted(corpus[group].items(), key=lambda kv: int(kv[0])):
            task = rec["task"]
            for s, conditions in enumerate(rec["samples"]):
                if conditions and conditions[0].startswith("<unparsed"):
                    skipped_unparsed += 1
                    continue
                other = _other_gate_issues(conditions)
                assert not other, (
                    f"non-grounding gate trip in corpus: {case}/{s} {other}"
                )
                fixed_fails = _grounding_fails(conditions, task, strip=True)
                v0_fails = _grounding_fails(conditions, task, strip=False)
                entry = {
                    "id": f"{group}-{int(case):02d}-s{s}",
                    "origin": origin,
                    "case": int(case),
                    "task": task,
                    "conditions": conditions,
                    "v0_rejected": bool(v0_fails),
                }
                if fixed_fails:
                    entry["ungrounded_indexes"] = fixed_fails
                    must_reject.append(entry)
                else:
                    must_accept.append(entry)

    # Adversarial matrix: per-probe single-condition grounding vs each
    # failed-case task, under the FIXED transform.
    adversarial = []
    for case, rec in sorted(corpus["failed"].items(), key=lambda kv: int(kv[0])):
        for probe in ADVERSARIAL:
            grounds = not _grounding_fails([probe], rec["task"], strip=True)
            adversarial.append(
                {
                    "case": int(case),
                    "task": rec["task"],
                    "probe": probe,
                    "grounds": grounds,
                }
            )

    # ── verification against the archived evidence numbers ──
    n_failed_accept = sum(
        1 for e in must_accept if e["origin"] == "failed_case_resample"
    )
    n_v0_rejected = sum(1 for e in must_accept if e["v0_rejected"])
    leaks = [(a["probe"], a["case"]) for a in adversarial if a["grounds"]]
    print(f"unparsed skipped: {skipped_unparsed}")
    print(
        f"must_accept: {len(must_accept)} (failed-case {n_failed_accept}, "
        f"v0_rejected {n_v0_rejected})"
    )
    print(f"must_reject: {len(must_reject)}")
    for e in must_reject:
        for i in e["ungrounded_indexes"]:
            print(f"  [{e['id']}] cond[{i}]: {e['conditions'][i][:90]}")
    print(f"adversarial leaks (known-pass): {leaks}")

    assert n_failed_accept == 20, "expected ALL 20 failed-case samples to recover"
    assert len(must_accept) + len(must_reject) + skipped_unparsed == 70
    assert ("The agent emails the quarterly report to Bob.", 10) in leaks

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fixture = {
        "_meta": {
            "name": "task_understanding gate meta-benchmark v1",
            "built": "2026-06-12",
            "source": str(CORPUS.relative_to(REPO_ROOT)),
            "source_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
            "deploy": "tierA-prod-2026.06.0-e72920c",
            "labeling": (
                "punct-strip grounding (stopword-filter raw tokens, then edge-"
                "strip '._/-') as verified in r2_dot_verify.py; real model "
                "outputs, no synthetic entries. must_accept entries with "
                "v0_rejected=true are the trailing-punctuation false positives "
                "R3 fixes; must_reject are genuinely invented requirements; "
                "adversarial entries with grounds=true are the documented "
                "topicality bound (longterm-plan finding #4) — a lexical gate "
                "CANNOT catch on-vocabulary fabrication."
            ),
        },
        "must_accept": must_accept,
        "must_reject": must_reject,
        "adversarial": adversarial,
    }
    OUT.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
