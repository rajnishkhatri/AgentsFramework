"""Convert the GAIA-shape model_ab_corpus.json into a harness-scorable jsonl.

Source: frontend/e2e/fixtures/model_ab_corpus.json (31 rows: 19 general +
6 multi-turn + 6 memory). Only the **general** family has a flat single-shot
``prompt`` — the multi-turn/memory rows carry a ``turns`` array and CANNOT be
faithfully replayed by the single-shot offline ``run_case`` (design doc §6 RC3 /
A1.3). They are EXCLUDED here and deferred to the deployed Phase B Playwright
driver, which replays turns.

Output row shape (what model_ab_eval.load_corpus / _drive_arm read):
  - case, gj_id, prompt, trace_id            — driven by the harness
  - phase = "answer"                         — a NON-planning phase so it never
       collides with score_run's planning matchers; the answer scorer keys on it.
  - difficulty                               — the reasoning-eligibility key
       (L2/L3 ⇒ reasoning arms eligible), mirrors isReasoningEligible.
  - want_answer                              — prose description (human context).
  - family                                   — carried for the report.

The ``trace_id`` is preserved from source so a row's identity is stable, but note
the harness keys recordings by ``uuid5(NAMESPACE_DNS, case).hex`` — the scorer's
wf_candidates already starts with that (fix 771933b), so the drive↔score join is
on ``case``, not this trace_id.
"""

from __future__ import annotations

import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "model_ab_corpus.json"
DEFAULT_OUT = AGENT_ROOT / "cache" / "model_ab_answer" / "ui_batch.jsonl"

# A non-planning phase label: score_run buckets it (defaultdict) but credits no
# planning hit — the ANSWER scorer (scripts/model_ab_answer_score.py) is what
# grades these rows. Keeping it distinct from depth/replan/etc. makes the
# separation explicit and avoids the §6 RC2 vacuous-parity trap.
ANSWER_PHASE = "answer"


def convert(source: Path = SOURCE) -> list[dict]:
    """Return the converted general-family rows (offline-eligible)."""
    rows = json.loads(source.read_text())
    out: list[dict] = []
    for r in rows:
        if r.get("family") != "general":
            continue  # multi-turn/memory deferred to Phase B (turns replay)
        prompt = r.get("prompt")
        if not prompt:
            continue  # defensive: a general row without a flat prompt is unusable
        out.append(
            {
                "case": r["case"],
                "gj_id": r.get("gj_id", ""),
                "phase": ANSWER_PHASE,
                "difficulty": r.get("difficulty", ""),
                "family": r.get("family", "general"),
                "trace_id": r["trace_id"],
                "session_id": r.get("session_id", ""),
                "prompt": prompt,
                "want_answer": r.get("want_answer", ""),
            }
        )
    return out


def write_jsonl(rows: list[dict], out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return out


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    rows = convert()
    write_jsonl(rows, out)
    from collections import Counter

    print(f"converted {len(rows)} general rows -> {out}")
    print("difficulty:", dict(Counter(r["difficulty"] for r in rows)))
