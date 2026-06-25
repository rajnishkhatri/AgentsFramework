#!/usr/bin/env python
"""Build the benchmark-shaped synthetic corpus for the extensive model A/B sweep.

The new set (model_ab_extensive_e2e.plan.md §1.2) is shaped after the public
agentic benchmarks — synthetic prompts, so no dataset license entanglement, the
same approach as ``build_planning_stress_corpus.py``:

  - general (GAIA L1–L2 shape): multi-step tool tasks with a verifiable answer;
    a mix of routine L1 (<=5 steps) and harder L2 (5–10 steps) rows. The L1 rows
    are the ROUTINE ones the eligibility filter must drop for the reasoning arms.
  - multi-turn (τ²-bench shape): dual-control customer-service-style tasks with a
    policy constraint, expressed as a ``turns`` array (the spec sends them
    sequentially in one thread). difficulty L2.
  - memory (LoCoMo/LongMemEval shape): multi-session recall tasks. difficulty L2.

``difficulty`` is the ELIGIBILITY KEY: the reasoning arms (``claude-opus-4-8`` /
``deepseek-v4-pro``) run ONLY on rows that are ``difficulty ∈ {L2,L3}`` OR
``family ∈ {stress, multi-turn}`` — the predicate lives in ONE place, the typed
reader ``frontend/e2e/fixtures/model_ab_corpus.ts`` (``isReasoningEligible``), so
the driver, the cost estimator, and the analyzer all agree. Roughly half the
``general`` rows are L1 so that filter is exercised.

Source of truth lives here (Python) so the FE JSON and any Python-side reader
stay in sync, mirroring ``build_planning_stress_corpus.py`` /
``export_goaljudge_registry_json.py``. The deterministic ``uuid5`` trace-id
namespace makes the Langfuse join key stable across regenerations and
pre-computable by the analysis half.

Regenerate after editing the rows below:
    .venv/bin/python scripts/build_model_ab_corpus.py

Output: frontend/e2e/fixtures/model_ab_corpus.json
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

FIXTURES_DIR = AGENT_ROOT / "frontend" / "e2e" / "fixtures"
OUT_PATH = FIXTURES_DIR / "model_ab_corpus.json"

# Deterministic trace_id namespace (same idiom as the registry/stress export so
# the join key is stable across regenerations and the analysis can pre-compute it).
_NS = uuid.NAMESPACE_DNS

# The three families this builder authors. ``stress`` and the reused memory
# corpora live elsewhere (plan §1.1); this builder owns the GAIA/τ²/LoCoMo-shaped
# NEW set across general / multi-turn / memory.
FAMILIES = ("general", "multi-turn", "memory")
DIFFICULTIES = ("L1", "L2", "L3")


def _trace_id(case_id: str) -> str:
    return uuid.uuid5(_NS, case_id).hex


def _row(
    *,
    case: str,
    family: str,
    difficulty: str,
    prompt: str | None = None,
    turns: list[str] | None = None,
    rationale: str | None = None,
    want_answer: str | None = None,
    want_policy: str | None = None,
) -> dict:
    """One corpus row.

    A single-shot case carries ``prompt``; a multi-turn (τ²-shaped) case carries
    ``turns`` (a scripted message sequence the spec sends in one thread). Exactly
    one of the two is set — the build guard below asserts it. ``difficulty`` +
    ``family`` are the eligibility key (the reasoning arms run only on the
    eligible subset; the predicate lives in the typed reader).
    """
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r} (expected one of {FAMILIES})")
    if difficulty not in DIFFICULTIES:
        raise ValueError(
            f"unknown difficulty {difficulty!r} (expected one of {DIFFICULTIES})"
        )
    if (prompt is None) == (turns is None):
        raise ValueError(
            f"{case}: exactly one of prompt / turns must be set "
            "(single-shot vs multi-turn)"
        )
    row: dict = {
        "case": case,
        # gj_id is the regex-conforming id the gj: thread bridge requires
        # (^GJ-ABXY-\d+$ family); the descriptive `case` is for humans / report.
        # Assigned sequentially in build_corpus() after all rows are collected.
        "gj_id": None,
        "family": family,
        "difficulty": difficulty,
        # trace_id is taken VERBATIM by the thread bridge (it does not re-derive
        # from the id), so the middleware adopts this exact value as the Langfuse
        # trace_id — the analysis join key. Keyed off the descriptive case so it
        # stays stable if gj_id numbering shifts.
        "trace_id": _trace_id(case),
        "session_id": f"session-{case.lower()}",
    }
    if prompt is not None:
        row["prompt"] = prompt
    if turns is not None:
        row["turns"] = turns
    if rationale is not None:
        row["rationale"] = rationale
    # Optional expectation hooks the analyzer's --judge pass can score against;
    # absent keys are simply not scored (same posture as the stress corpus).
    if want_answer is not None:
        row["want_answer"] = want_answer
    if want_policy is not None:
        row["want_policy"] = want_policy
    return row


# ── general (GAIA L1–L2 shape) ─────────────────────────────────────────────────


def _general_rows() -> list[dict]:
    """GAIA-shaped general assistant tasks: multi-step tool work with a
    verifiable answer. L1 rows are ROUTINE (<=5 steps) — these are exactly the
    cases the reasoning arms must SKIP (eligibility filter); L2 rows are the
    harder 5–10-step multi-step tasks the reasoning arms SHOULD see.
    """
    return [
        # ── L1 routine (<=5 steps) — reasoning arms SKIP these ──
        _row(
            case="GEN-L1-read-sum-01",
            family="general",
            difficulty="L1",
            prompt=(
                "Read the three files /workspace/nums/a.txt, /workspace/nums/b.txt "
                "and /workspace/nums/c.txt — each holds a single integer. Report "
                "their sum."
            ),
            want_answer="the integer sum of the three files",
            rationale="3-step read + add; routine GAIA L1 — reasoning arms skip",
        ),
        _row(
            case="GEN-L1-lookup-format-02",
            family="general",
            difficulty="L1",
            prompt=(
                "Read /workspace/contact.txt, extract the email address it "
                "contains, and report just the domain part (after the @)."
            ),
            want_answer="the email domain",
            rationale="single read + extract; routine L1",
        ),
        _row(
            case="GEN-L1-count-lines-03",
            family="general",
            difficulty="L1",
            prompt=(
                "Count how many non-empty lines are in /workspace/log.txt and "
                "report the count as a single integer."
            ),
            want_answer="the non-empty line count",
            rationale="single read + count; routine L1",
        ),
        _row(
            case="GEN-L1-pick-max-04",
            family="general",
            difficulty="L1",
            prompt=(
                "Read /workspace/scores.csv (a header row then rows of name,score) "
                "and report the name with the highest score."
            ),
            want_answer="the top-scoring name",
            rationale="single read + argmax; routine L1",
        ),
        _row(
            case="GEN-L1-convert-unit-05",
            family="general",
            difficulty="L1",
            prompt=(
                "Read the distance in miles from /workspace/distance.txt, convert "
                "it to kilometres (1 mile = 1.60934 km), and report the result "
                "rounded to one decimal place."
            ),
            want_answer="the distance in km to one decimal",
            rationale="read + single arithmetic; routine L1",
        ),
        _row(
            case="GEN-L1-write-readback-06",
            family="general",
            difficulty="L1",
            prompt=(
                "Write the word 'ready' to /workspace/status.txt, then read it back "
                "and confirm the file contains exactly that word."
            ),
            want_answer="confirmation the file says ready",
            rationale="clean write + read-back; routine L1",
        ),
        _row(
            case="GEN-L1-extract-field-13",
            family="general",
            difficulty="L1",
            prompt=(
                "Read /workspace/profile.json and report the value of its 'name' "
                "field."
            ),
            want_answer="the name field value",
            rationale="single read + field lookup; routine L1",
        ),
        _row(
            case="GEN-L1-sort-list-14",
            family="general",
            difficulty="L1",
            prompt=(
                "Read /workspace/words.txt (one word per line) and report the words "
                "sorted alphabetically, comma-separated."
            ),
            want_answer="the alphabetically sorted words",
            rationale="single read + sort; routine L1",
        ),
        _row(
            case="GEN-L1-bool-check-15",
            family="general",
            difficulty="L1",
            prompt=(
                "Read the integer in /workspace/n.txt and report whether it is even "
                "or odd."
            ),
            want_answer="even or odd",
            rationale="single read + parity; routine L1",
        ),
        _row(
            case="GEN-L1-first-match-16",
            family="general",
            difficulty="L1",
            prompt=(
                "Read /workspace/access.log and report the first line that contains "
                "the word 'denied'."
            ),
            want_answer="the first matching line",
            rationale="single read + first-match; routine L1",
        ),
        # ── L2 harder (5–10 steps) — reasoning arms RUN these ──
        _row(
            case="GEN-L2-multi-file-reconcile-07",
            family="general",
            difficulty="L2",
            prompt=(
                "In /workspace/invoices/ there are five invoice files "
                "(inv-1.txt … inv-5.txt). Each has an 'amount:' line and a "
                "'status:' line. Sum the amounts of only the invoices whose status "
                "is 'paid', then write that subtotal to /workspace/out/paid.txt and "
                "report it. Read every invoice before computing."
            ),
            want_answer="the subtotal of paid invoices, also written to out/paid.txt",
            rationale="5 reads + filter + sum + write + report; GAIA L2 multi-step",
        ),
        _row(
            case="GEN-L2-cross-ref-lookup-08",
            family="general",
            difficulty="L2",
            prompt=(
                "Read /workspace/orders.csv (order_id,customer_id) and "
                "/workspace/customers.csv (customer_id,region). For each order, "
                "resolve its customer's region, then report how many orders fall in "
                "each region as a sorted list 'region: count'."
            ),
            want_answer="per-region order counts",
            rationale="two reads + join + group-by + sort; L2",
        ),
        _row(
            case="GEN-L2-pipeline-transform-09",
            family="general",
            difficulty="L2",
            prompt=(
                "Read /workspace/events.log. Keep only the lines containing 'ERROR', "
                "extract the timestamp at the start of each, count errors per hour, "
                "and report the single hour with the most errors. Write the full "
                "per-hour table to /workspace/out/errors_by_hour.txt as well."
            ),
            want_answer="the peak error hour plus the per-hour table file",
            rationale="read + filter + parse + bucket + argmax + write; L2",
        ),
        _row(
            case="GEN-L2-multi-source-synthesis-10",
            family="general",
            difficulty="L2",
            prompt=(
                "You have three reports in /workspace/reports/ (q1.txt, q2.txt, "
                "q3.txt), each ending with a 'TOTAL: N' line. Read all three, compute "
                "the quarter-over-quarter growth rate between consecutive quarters, "
                "and report both growth rates (q1→q2 and q2→q3) as percentages to "
                "one decimal place."
            ),
            want_answer="the two QoQ growth percentages",
            rationale="3 reads + two derived computations + format; L2",
        ),
        _row(
            case="GEN-L2-verify-and-fix-11",
            family="general",
            difficulty="L2",
            prompt=(
                "Read /workspace/config.json. Validate that it has both a 'host' and "
                "a 'port' key and that 'port' is an integer between 1 and 65535. If "
                "anything is missing or invalid, write a corrected version to "
                "/workspace/out/config.fixed.json using host='localhost' and "
                "port=8080 for any bad field, and report exactly what you changed."
            ),
            want_answer="the validation result and list of corrections made",
            rationale="read + validate + conditional repair + write + report; L2",
        ),
        _row(
            case="GEN-L2-dependency-resolve-12",
            family="general",
            difficulty="L2",
            prompt=(
                "Read /workspace/deps.txt where each line is 'A -> B' meaning A "
                "depends on B. Produce a valid install order (a topological sort) "
                "such that every dependency is installed before the thing that needs "
                "it, and report the order. If there is a cycle, report which nodes "
                "form it instead."
            ),
            want_answer="a valid topological install order (or the cycle)",
            rationale="read + graph build + toposort + cycle-detect; L2 reasoning-heavy",
        ),
        # ── L3 complex (deep multi-step, the escalation/reasoning tier's home) ──
        _row(
            case="GEN-L3-constraint-solve-13",
            family="general",
            difficulty="L3",
            prompt=(
                "In /workspace/schedule/ there are availability files for five "
                "people (p1.txt … p5.txt), each listing the 30-minute slots they are "
                "free on Monday. Find a single 30-minute slot that works for at least "
                "four of the five people, preferring the earliest such slot, and "
                "report it together with who can and cannot attend. If no slot works "
                "for four people, say so and report the best slot you found."
            ),
            want_answer="the earliest slot covering >=4 people plus the attendee split",
            rationale="5 reads + intersection search + threshold + tie-break; L3 complex",
        ),
        _row(
            case="GEN-L3-multi-hop-synthesis-14",
            family="general",
            difficulty="L3",
            prompt=(
                "Read /workspace/papers/ (paper-1.txt … paper-4.txt). Each paper "
                "cites others by their number in a 'cites:' line. Build the citation "
                "graph, find the paper cited by the most others, then summarise THAT "
                "paper's key claim and explain which papers depend on it and why. "
                "Read every paper before answering."
            ),
            want_answer="the most-cited paper, its claim, and its dependents",
            rationale="4 reads + graph + argmax + dependent-trace + synthesis; L3 multi-hop",
        ),
        _row(
            case="GEN-L3-iterative-refine-15",
            family="general",
            difficulty="L3",
            prompt=(
                "Read /workspace/budget.csv (category,planned,actual). Identify every "
                "category over budget, compute the total overrun, then propose a set "
                "of cuts to under-budget categories that fully offsets the overrun "
                "WITHOUT cutting any category below its actual spend. Report the "
                "proposed cuts and verify the offset balances to zero."
            ),
            want_answer="a balanced set of offsetting cuts with the verification",
            rationale="read + filter + optimise under constraints + self-verify; L3 complex",
        ),
    ]


# ── multi-turn (τ²-bench shape) ────────────────────────────────────────────────


def _multiturn_rows() -> list[dict]:
    """τ²-bench-shaped dual-control tasks: the user reveals constraints over
    several turns and a POLICY must be adhered to. Each carries a ``turns`` array
    the spec sends sequentially in one thread (the model stays pinned across
    turns — confirming the multi-step pin path). family=multi-turn makes the
    whole set reasoning-eligible; difficulty L2.
    """
    return [
        _row(
            case="MT-retail-return-window-01",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "Hi, I want to return an item I bought.",
                "It's a pair of headphones, order #A1042, delivered 40 days ago.",
                "Can I still get a refund?",
            ],
            want_policy=(
                "POLICY: returns allowed only within 30 days of delivery; 40 days "
                "is outside the window, so the agent must decline a refund and "
                "offer store credit / an exchange instead — never approve the refund."
            ),
            rationale="τ²-style: refund eligibility revealed over turns; policy = 30-day window",
        ),
        _row(
            case="MT-airline-change-fee-02",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "I need to change my flight.",
                "Booking reference QZ88, it's a Basic Economy fare.",
                "I don't want to pay any fee — can you waive it?",
            ],
            want_policy=(
                "POLICY: Basic Economy fares are non-changeable / non-refundable; "
                "the agent must NOT waive the fee or process a free change, and "
                "should explain the fare rule and offer the paid options only."
            ),
            rationale="τ²-style: fare class constrains the action; policy = no free change on Basic",
        ),
        _row(
            case="MT-telecom-plan-downgrade-03",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "I'd like to lower my monthly bill.",
                "I'm currently on the Premium plan and I'm still under contract.",
                "Just switch me to the cheapest plan today, please.",
            ],
            want_policy=(
                "POLICY: mid-contract downgrades incur an early-change adjustment and "
                "cannot take effect immediately; the agent must disclose the "
                "adjustment and the next-cycle effective date, not silently downgrade."
            ),
            rationale="τ²-style: contract status gates the downgrade; policy = disclose + defer",
        ),
        _row(
            case="MT-bank-dispute-verification-04",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "I want to dispute a charge on my card.",
                "It's a $230 charge from yesterday I don't recognise.",
                "Can you just reverse it right now?",
            ],
            want_policy=(
                "POLICY: a dispute cannot be filed until identity is verified and the "
                "transaction details are confirmed; the agent must complete "
                "verification first and never promise an immediate reversal."
            ),
            rationale="τ²-style: identity verification gates the action; policy = verify before dispute",
        ),
        _row(
            case="MT-saas-seat-upgrade-05",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "We need to add more seats to our subscription.",
                "We're on the Starter plan and want to go from 5 to 25 seats.",
                "Can we keep the Starter per-seat price for all of them?",
            ],
            want_policy=(
                "POLICY: Starter is capped at 10 seats; scaling to 25 requires moving "
                "to a higher tier at that tier's per-seat price — the agent must not "
                "promise Starter pricing beyond the cap."
            ),
            rationale="τ²-style: plan cap constrains the upgrade; policy = tier change required",
        ),
        _row(
            case="MT-insurance-claim-eligibility-06",
            family="multi-turn",
            difficulty="L2",
            turns=[
                "I'd like to file a claim for water damage.",
                "It's a flood from the river behind my house last week.",
                "My policy covers water damage, so I'm covered, right?",
            ],
            want_policy=(
                "POLICY: standard water-damage cover EXCLUDES flood from external "
                "bodies of water unless a flood rider is present; the agent must "
                "check for the rider and not confirm coverage outright."
            ),
            rationale="τ²-style: exclusion clause constrains the claim; policy = check flood rider",
        ),
    ]


# ── memory (LoCoMo / LongMemEval shape) ────────────────────────────────────────


def _memory_rows() -> list[dict]:
    """LoCoMo / LongMemEval-shaped multi-session recall tasks. Each ``turns``
    array seeds facts in early turns and tests recall (extraction / multi-session
    reasoning / temporal / knowledge-update) in a later turn — the spec sends
    them in one thread, but the recall turn depends on earlier-session memory.
    family=memory; difficulty L2 (multi-session reasoning is inherently complex).
    """
    return [
        _row(
            case="MEM-extraction-recall-01",
            family="memory",
            difficulty="L2",
            turns=[
                "Just so you know, my daughter Mia is allergic to peanuts.",
                "We're also vegetarian at home.",
                "Suggest a quick weeknight dinner the whole family can eat.",
            ],
            want_policy=(
                "RECALL: the suggestion must be both peanut-free AND vegetarian — "
                "the model must carry both facts forward from the earlier turns."
            ),
            rationale="LongMemEval extraction: two facts seeded, both must constrain the answer",
        ),
        _row(
            case="MEM-knowledge-update-02",
            family="memory",
            difficulty="L2",
            turns=[
                "My favourite city to visit is Paris.",
                "Actually, I changed my mind — Tokyo is my favourite now.",
                "What's my favourite city?",
            ],
            want_answer="Tokyo (the updated value, not Paris)",
            rationale="LongMemEval knowledge-update: later fact overrides the earlier one",
        ),
        _row(
            case="MEM-temporal-reasoning-03",
            family="memory",
            difficulty="L2",
            turns=[
                "I started a new job on the 1st of March.",
                "My probation period is three months.",
                "When does my probation end?",
            ],
            want_answer="end of May (1 March + 3 months)",
            rationale="LongMemEval temporal: combine a date and a duration across turns",
        ),
        _row(
            case="MEM-multisession-reasoning-04",
            family="memory",
            difficulty="L2",
            turns=[
                "I'm planning a trip with my brother and my friend Sam.",
                "My brother is vegan and Sam can't do spicy food.",
                "Pick one cuisine that works for everyone on the trip.",
            ],
            want_policy=(
                "RECALL: the cuisine must satisfy BOTH constraints gathered across "
                "turns (vegan-friendly AND mild) — multi-session reasoning over two "
                "separately-stated facts."
            ),
            rationale="LoCoMo multi-session reasoning: combine two constraints stated apart",
        ),
        _row(
            case="MEM-abstention-05",
            family="memory",
            difficulty="L2",
            turns=[
                "I have two cats, Luna and Max.",
                "Luna is a tabby.",
                "What breed is my dog?",
            ],
            want_policy=(
                "ABSTENTION: no dog was ever mentioned — the model must say it has "
                "no record of a dog, NOT invent one (the LongMemEval abstention "
                "ability)."
            ),
            rationale="LongMemEval abstention: the asked-for entity was never seeded — must decline",
        ),
        _row(
            case="MEM-long-history-recall-06",
            family="memory",
            difficulty="L2",
            turns=[
                "My membership number is 7741-A.",
                "I usually order the medium roast.",
                "I'm based in the Pacific timezone.",
                "My partner's name is Alex.",
                "Remind me — what's my membership number?",
            ],
            want_answer="7741-A (recalled across several intervening turns)",
            rationale="LoCoMo long-history: target fact buried under intervening turns",
        ),
    ]


def build_corpus() -> list[dict]:
    rows = _general_rows() + _multiturn_rows() + _memory_rows()
    # Guard: case ids must be unique (a dup would collide trace_ids and silently
    # overwrite a capture row).
    seen: set[str] = set()
    seen_trace: set[str] = set()
    for r in rows:
        if r["case"] in seen:
            raise ValueError(f"duplicate case id: {r['case']}")
        seen.add(r["case"])
        if r["trace_id"] in seen_trace:
            raise ValueError(f"duplicate trace_id for case: {r['case']}")
        seen_trace.add(r["trace_id"])

    # Assign the regex-conforming gj_id (GJ-ABXY-NN) sequentially. The gj: thread
    # bridge adopts each row's trace_id verbatim as the Langfuse join key; the id
    # itself is the bridge-parseable handle. Per-family prefix keeps the report
    # readable (the bridge regex must allow these — see the spec's thread route).
    family_tag = {"general": "GENL", "multi-turn": "MULT", "memory": "MEMO"}
    counters: dict[str, int] = {}
    for r in rows:
        tag = family_tag[r["family"]]
        counters[tag] = counters.get(tag, 0) + 1
        r["gj_id"] = f"GJ-AB{tag}-{counters[tag]:02d}"
    return rows


def main() -> None:
    rows = build_corpus()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    by_family: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    for r in rows:
        by_family[r["family"]] = by_family.get(r["family"], 0) + 1
        by_difficulty[r["difficulty"]] = by_difficulty.get(r["difficulty"], 0) + 1
    print(f"wrote {len(rows)} cases to {OUT_PATH}")
    for family, n in sorted(by_family.items()):
        print(f"  family {family:12s} {n}")
    for diff, n in sorted(by_difficulty.items()):
        print(f"  diff   {diff:12s} {n}")


if __name__ == "__main__":
    main()
