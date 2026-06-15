#!/usr/bin/env python
"""Build the synthetic planning-stress corpus for the T3 tiered-loops stress run.

The corpus stresses all four phases of the tiered-reasoning ladder (e2e-stress
plan §3): depth recognition (Phase 0), the replan gate (Phase 1), reflexion +
budget (Phase 2), and escalation precision (Phase 3). Each row carries a prompt
plus the per-phase EXPECTATION the trace-analysis half scores against — never an
exact-prose assertion (T3 is non-deterministic; we score aggregate rates).

Source of truth lives here (Python) so the FE JSON and any Python-side reader
stay in sync, mirroring ``export_goaljudge_registry_json.py``. The depth phase
REUSES the committed depth-strata fixture (the exact rows Phase 0 fixed) rather
than reinventing them.

Regenerate after editing the rows below:
    python scripts/build_planning_stress_corpus.py

Output: frontend/e2e/fixtures/planning_stress_corpus.json
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
DEPTH_STRATA = FIXTURES_DIR / "goaljudge_depth_strata.json"
OUT_PATH = FIXTURES_DIR / "planning_stress_corpus.json"

# Deterministic trace_id namespace (same idiom as the registry export so the
# join key is stable across regenerations and the analysis can pre-compute it).
_NS = uuid.NAMESPACE_DNS


def _trace_id(case_id: str) -> str:
    return uuid.uuid5(_NS, case_id).hex


def _row(
    *,
    case: str,
    prompt: str,
    phase: str,
    rationale: str,
    want_depth: str | None = None,
    want_replan: bool | None = None,
    want_reflexion: bool | None = None,
    want_terminates_at_budget: bool | None = None,
    want_escalation: str | None = None,
    # ── Phase 4 (T3 fan-out) expectations; see t3_fanout_corpus.plan.md §5 ──
    want_fanout: bool | None = None,
    want_branch_count: int | None = None,
    want_join_synthesizes: bool | None = None,
    want_survives_partial: bool | None = None,
    axis: list[str] | None = None,
) -> dict:
    """One corpus row. Only the expectation keys relevant to ``phase`` are set;
    the analysis half reads them by phase, so absent keys are simply not scored.
    """
    row: dict = {
        "case": case,
        # gj_id is the regex-conforming id the gj: thread bridge requires
        # (^GJ-STRESS-\d+$); the descriptive `case` is for humans / the report.
        # Assigned sequentially in build_corpus() after all rows are collected.
        "gj_id": None,
        "prompt": prompt,
        "phase": phase,
        "rationale": rationale,
        # trace_id is taken VERBATIM by parse_goaljudge_thread_id (it does not
        # re-derive from the id), so the middleware adopts this exact value as the
        # Langfuse trace_id — that is the analysis join key. Keyed off the
        # descriptive case so it stays stable if gj_id numbering shifts.
        "trace_id": _trace_id(case),
        "session_id": f"session-{case.lower()}",
    }
    if want_depth is not None:
        row["want_depth"] = want_depth
    if want_replan is not None:
        row["want_replan"] = want_replan
    if want_reflexion is not None:
        row["want_reflexion"] = want_reflexion
    if want_terminates_at_budget is not None:
        row["want_terminates_at_budget"] = want_terminates_at_budget
    if want_escalation is not None:
        row["want_escalation"] = want_escalation
    if want_fanout is not None:
        row["want_fanout"] = want_fanout
    if want_branch_count is not None:
        row["want_branch_count"] = want_branch_count
    if want_join_synthesizes is not None:
        row["want_join_synthesizes"] = want_join_synthesizes
    if want_survives_partial is not None:
        row["want_survives_partial"] = want_survives_partial
    if axis is not None:
        row["axis"] = axis
    return row


# Map a depth-strata `stratum` label to its intended depth (the want).
def _depth_from_stratum(stratum: str) -> str:
    # e.g. "depth:L2:adversarial:bare-complex" -> "L2"
    parts = stratum.split(":")
    return parts[1] if len(parts) > 1 else "L0"


def _depth_rows() -> list[dict]:
    """Phase 0 — reuse the committed depth-strata rows verbatim (the exact
    cases Phase 0 fixed: short strong-verb floors, long narratives, enum/conj
    L2, adversarial bare-complex). want_depth derives from the stratum label."""
    strata = json.loads(DEPTH_STRATA.read_text())
    rows: list[dict] = []
    for r in strata:
        want = _depth_from_stratum(r["stratum"])
        rows.append(
            _row(
                case=f"STRESS-DEPTH-{r['id'].split('-')[-1]}",
                prompt=r["prompt"],
                phase="depth",
                want_depth=want,
                rationale=f"depth-strata {r['stratum']} -> {want}",
            )
        )
    return rows


def _replan_rows() -> list[dict]:
    """Phase 1 — brittle-plan rows: the first tool call plausibly fails or
    returns surprising output, so plan_is_stale fires -> replan_count >= 1.
    Stable controls must NOT replan (precision)."""
    return [
        _row(
            case="STRESS-REPLAN-missing-config-01",
            prompt=(
                "Read /workspace/nonexistent_config.yaml and apply the database "
                "migration it describes. If the file is missing, decide how to "
                "proceed and continue."
            ),
            phase="replan",
            want_replan=True,
            rationale="first read fails (missing file) -> surprising result rebuilds the plan",
        ),
        _row(
            case="STRESS-REPLAN-garbage-input-02",
            prompt=(
                "Write the text 'not-json-at-all {{{' to /workspace/data.json, "
                "then parse it as JSON and summarize the records it contains."
            ),
            phase="replan",
            want_replan=True,
            rationale="parse step fails on garbage written in step 1 -> replan",
        ),
        _row(
            case="STRESS-REPLAN-shifting-target-03",
            prompt=(
                "List the files in /workspace/reports/, then open the most recent "
                "one and extract its total. If the directory is empty, create a "
                "starter report instead."
            ),
            phase="replan",
            want_replan=True,
            rationale="empty/absent dir flips the plan branch -> replan",
        ),
        _row(
            case="STRESS-REPLAN-dependent-chain-04",
            prompt=(
                "Read /workspace/seed.txt to get a filename, then read THAT file "
                "and report its first line. Recover gracefully if either is absent."
            ),
            phase="replan",
            want_replan=True,
            rationale="second read depends on first's surprising content -> replan",
        ),
        _row(
            case="STRESS-REPLAN-tool-error-05",
            prompt=(
                "Run the shell command 'cat /workspace/does_not_exist_42.log' and "
                "summarize the errors in it; if it is not there, say so and stop."
            ),
            phase="replan",
            want_replan=True,
            rationale="shell tool error on first call -> surprising result -> replan",
        ),
        # ── stable controls (precision): 0 replans expected ──
        _row(
            case="STRESS-REPLAN-control-stable-06",
            prompt=(
                "Write the number 42 to /workspace/answer.txt, then read it back "
                "and confirm it says 42."
            ),
            phase="replan",
            want_replan=False,
            rationale="control: both tool calls succeed cleanly -> NO replan",
        ),
        _row(
            case="STRESS-REPLAN-control-stable-07",
            prompt=(
                "Create /workspace/hello.txt containing the word hello, then read "
                "it back to verify."
            ),
            phase="replan",
            want_replan=False,
            rationale="control: clean write+read -> NO replan",
        ),
        _row(
            case="STRESS-REPLAN-control-stable-08",
            prompt="Echo the phrase 'pipeline ok' verbatim.",
            phase="replan",
            want_replan=False,
            rationale="control: zero-tool trivial task -> NO replan",
        ),
        _row(
            case="STRESS-REPLAN-control-stable-09",
            prompt=(
                "Write 'line one' to /workspace/a.txt and 'line two' to "
                "/workspace/b.txt, then read both back."
            ),
            phase="replan",
            want_replan=False,
            rationale="control: independent clean writes -> NO replan",
        ),
        _row(
            case="STRESS-REPLAN-control-stable-10",
            prompt="Write the current plan summary as 'done' to /workspace/state.txt.",
            phase="replan",
            want_replan=False,
            rationale="control: single clean write -> NO replan",
        ),
    ]


def _reflexion_rows() -> list[dict]:
    """Phase 2 — hard, under-specified tasks where a single pass is likely
    partial/failed against derived success conditions, so reflexion re-enters
    and must hit the budget ceiling (no thrash). Clean controls must not."""
    return [
        _row(
            case="STRESS-REFLEXION-underspecified-01",
            prompt=(
                "Make the checkout flow correct. Find every place a price is "
                "computed and ensure tax is applied consistently."
            ),
            phase="reflexion",
            want_reflexion=True,
            want_terminates_at_budget=True,
            rationale="vague 'make it correct' -> first pass partial -> re-enter, bounded",
        ),
        _row(
            case="STRESS-REFLEXION-multi-criteria-02",
            prompt=(
                "Write a migration plan that is reversible, zero-downtime, and "
                "validated against the current schema. All three properties must hold."
            ),
            phase="reflexion",
            want_reflexion=True,
            want_terminates_at_budget=True,
            rationale="3 hard success conditions -> likely unmet on pass 1 -> reflect",
        ),
        _row(
            case="STRESS-REFLEXION-incomplete-prone-03",
            prompt=(
                "Audit the auth module for security issues and produce a complete "
                "list with a fix for each. Do not miss any category."
            ),
            phase="reflexion",
            want_reflexion=True,
            want_terminates_at_budget=True,
            rationale="completeness criterion -> partial first pass -> reflect, ceiling",
        ),
        _row(
            case="STRESS-REFLEXION-contradiction-prone-04",
            prompt=(
                "Optimize the query for both lowest latency and lowest memory; "
                "justify that both targets are met simultaneously."
            ),
            phase="reflexion",
            want_reflexion=True,
            want_terminates_at_budget=True,
            rationale="tension between criteria -> unmet -> bounded reflexion",
        ),
        _row(
            case="STRESS-REFLEXION-verify-hard-05",
            prompt=(
                "Refactor the rate limiter so it is correct under concurrent "
                "access and prove the invariant holds. Concurrency correctness is required."
            ),
            phase="reflexion",
            want_reflexion=True,
            want_terminates_at_budget=True,
            rationale="hard-to-satisfy proof criterion -> reflect, must stop at budget",
        ),
        # ── clean controls (no re-entry): trivial, single-pass success ──
        _row(
            case="STRESS-REFLEXION-control-trivial-06",
            prompt="Write the word 'ok' to /workspace/ok.txt and read it back.",
            phase="reflexion",
            want_reflexion=False,
            rationale="control: trivially satisfiable -> success -> NO reflexion",
        ),
        _row(
            case="STRESS-REFLEXION-control-trivial-07",
            prompt="Echo the phrase 'reflexion control' verbatim.",
            phase="reflexion",
            want_reflexion=False,
            rationale="control: zero-condition task -> success -> NO reflexion",
        ),
        _row(
            case="STRESS-REFLEXION-control-trivial-08",
            prompt="Read the first line of /workspace/ok.txt and print it.",
            phase="reflexion",
            want_reflexion=False,
            rationale="control: single read -> success -> NO reflexion",
        ),
        _row(
            case="STRESS-REFLEXION-control-trivial-09",
            prompt="Write 'value=1' to /workspace/cfg.txt.",
            phase="reflexion",
            want_reflexion=False,
            rationale="control: single clean write -> success -> NO reflexion",
        ),
        _row(
            case="STRESS-REFLEXION-control-trivial-10",
            prompt="Confirm that 2 plus 2 equals 4.",
            phase="reflexion",
            want_reflexion=False,
            rationale="control: trivial fact -> success -> NO reflexion",
        ),
    ]


def _escalation_rows() -> list[dict]:
    """Phase 3 — escalation precision (scored SEPARATELY from entry accuracy).
    Confidently-wrong-prone -> escalate (recall); trivial controls -> no
    escalate (precision); no-tool prose-thrash -> escalate (D3)."""
    return [
        # ── should escalate (recall): failed/partial verdict under budget ──
        _row(
            case="STRESS-ESCALATION-wrong-prone-01",
            prompt=(
                "Compute the exact number of prime numbers below 1,000,000 and "
                "state the single integer. Your answer must be exactly correct."
            ),
            phase="escalation",
            want_escalation="reflect",
            rationale="hard exact-answer -> likely failed verdict -> escalate",
        ),
        _row(
            case="STRESS-ESCALATION-wrong-prone-02",
            prompt=(
                "Without using any tools, recall the full text of RFC 9110 section "
                "9.3.1 verbatim. Exactness is required."
            ),
            phase="escalation",
            want_escalation="reflect",
            rationale="unverifiable-from-memory -> failed verdict -> escalate",
        ),
        _row(
            case="STRESS-ESCALATION-partial-prone-03",
            prompt=(
                "List every HTTP status code and its exact RFC definition. The "
                "list must be complete with no omissions."
            ),
            phase="escalation",
            want_escalation="reflect",
            rationale="completeness impossible in one pass -> partial -> escalate",
        ),
        # ── prose-thrash (D3): no-tool repetition -> escalate ──
        _row(
            case="STRESS-ESCALATION-prose-thrash-04",
            prompt=(
                "Keep restating your plan to solve world hunger in detail, over "
                "and over, without taking any concrete action or using any tool."
            ),
            phase="escalation",
            want_escalation="reflect",
            rationale="no-tool prose repetition -> D3 prose_repeat -> escalate",
        ),
        _row(
            case="STRESS-ESCALATION-prose-thrash-05",
            prompt=(
                "Describe at length how you would approach this, then describe it "
                "again the same way, without doing anything."
            ),
            phase="escalation",
            want_escalation="reflect",
            rationale="no-tool prose repetition -> D3 -> escalate",
        ),
        # ── clean controls (precision): success -> NO escalate ──
        _row(
            case="STRESS-ESCALATION-control-clean-06",
            prompt="Write 'escalation control' to /workspace/esc.txt and read it back.",
            phase="escalation",
            want_escalation="done",
            rationale="control: clean success -> NO escalate (false-positive guard)",
        ),
        _row(
            case="STRESS-ESCALATION-control-clean-07",
            prompt="Echo the phrase 'no escalation needed' verbatim.",
            phase="escalation",
            want_escalation="done",
            rationale="control: trivial success -> NO escalate",
        ),
        _row(
            case="STRESS-ESCALATION-control-clean-08",
            prompt="Read the first line of /workspace/esc.txt and print it.",
            phase="escalation",
            want_escalation="done",
            rationale="control: single read success -> NO escalate",
        ),
        _row(
            case="STRESS-ESCALATION-control-clean-09",
            prompt="Confirm the file /workspace/esc.txt exists by reading it.",
            phase="escalation",
            want_escalation="done",
            rationale="control: clean verify -> NO escalate",
        ),
        _row(
            case="STRESS-ESCALATION-control-clean-10",
            prompt="State that the current date format is ISO-8601.",
            phase="escalation",
            want_escalation="done",
            rationale="control: trivial fact -> success -> NO escalate",
        ),
    ]


def _fanout_rows() -> list[dict]:
    """Phase 4 — T3 supervisor / parallel fan-out (t3_fanout_corpus.plan.md §4).

    Four families dimensioned by the §2 decision-space axes (tagged in ``axis``
    for the coverage matrix the analyzer prints, §6):

      - independent: genuinely parallel -> ``want_fanout=True`` (the happy path).
      - decline: sequentially-dependent, incl. SEEDED near-miss traps that LOOK
        parallel but chain -> ``want_fanout=False`` (the GAIA single-agent-wins
        guard; the load-bearing family).
      - fault: a branch is engineered to fail/time-out/straggle ->
        ``want_survives_partial=True`` (the MAST bound on a live trace). Timing
        modes carry a magic objective token (``__FAULT_TIMEOUT__`` /
        ``__FAULT_SLOW__``) the env-gated worker fault-hook reads (§4.3a);
        hard-error/degraded modes inject purely through the prompt.
      - control: trivial single-step work -> ``want_fanout=False`` (precision
        guard), incl. an at-the-floor 2-trivial-writes boundary.

    Scoring is per t3_fanout_corpus.plan.md §7: fan-out PRECISION (decline +
    control are the negatives; a near-miss fanned out is the GAIA-failure ``fp``
    cell) + partial-survival rate for the fault rows. Calibration-first.
    """
    return _fanout_independent_rows() + _fanout_decline_rows() + (
        _fanout_fault_rows() + _fanout_control_rows()
    )


def _fanout_independent_rows() -> list[dict]:
    """§4.1 — genuinely parallel; want_fanout=True, branch_count>=2, join synthesizes."""
    ind = lambda **kw: _row(  # noqa: E731 - local shorthand, keeps the table readable
        phase="fanout",
        want_fanout=True,
        want_join_synthesizes=True,
        **kw,
    )
    return [
        ind(
            case="FANOUT-independent-trip-research-01",
            prompt=(
                "Research, independently and in parallel, the typical August cost of three "
                "unrelated things: (a) a rental car in Lisbon for a week, (b) a 4-star hotel "
                "in Lisbon for a week, and (c) a round-trip economy flight between Lisbon and "
                "London. Report all three figures. None of the three depends on the others."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="3 independent cost lookups, no shared date constraint -> fan out",
        ),
        ind(
            case="FANOUT-independent-restaurant-survey-02",
            prompt=(
                "Find one highly-rated restaurant for each of three unrelated cuisines — "
                "Italian, Thai, and sushi — and report each one's rating and price band. "
                "The three picks are independent of each other."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="3 independent cuisine lookups -> fan out",
        ),
        ind(
            case="FANOUT-independent-gift-shortlist-03",
            prompt=(
                "Shortlist one gift under $50 for each of three different people: a runner, "
                "a baker, and a gamer. Each shortlist is independent of the others."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="3 independent shortlists -> fan out",
        ),
        ind(
            case="FANOUT-independent-multidoc-summary-04",
            prompt=(
                "You are given three unrelated documents in /workspace/docs/: a.txt, b.txt, "
                "and c.txt. Summarize the key finding of each document independently. The "
                "summaries do not depend on each other."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="canonical GAIA multi-doc fan-out -> fan out",
        ),
        ind(
            case="FANOUT-independent-multidoc-extract-05",
            prompt=(
                "Extract the publication year from each of four separate sources in "
                "/workspace/sources/ (s1.txt, s2.txt, s3.txt, s4.txt). Report the four years. "
                "Each extraction is independent."
            ),
            want_branch_count=4,
            axis=["A:independent", "B:4", "C:obvious"],
            rationale="4 independent extractions -> fan out",
        ),
        ind(
            case="FANOUT-independent-policy-checks-06",
            prompt=(
                "Independently verify each of three separate account conditions: (a) the "
                "account is in good standing, (b) the email is verified, and (c) two-factor "
                "auth is enabled. None of the three checks depends on another; report each."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="Tau2-style independent policy checks -> fan out",
        ),
        ind(
            case="FANOUT-independent-multitab-lookup-07",
            prompt=(
                "Look up the current price of three unrelated products independently: a "
                "stainless water bottle, a USB-C cable, and a desk lamp. Report all three "
                "prices. The lookups are independent."
            ),
            want_branch_count=3,
            axis=["A:independent", "B:3", "C:obvious"],
            rationale="WebArena-style independent lookups -> fan out",
        ),
        ind(
            case="FANOUT-independent-two-branch-08",
            prompt=(
                "Report two unrelated things independently: the weekend weather forecast for "
                "Denver and the weekend weather forecast for Miami. Neither depends on the other."
            ),
            want_branch_count=2,
            axis=["A:independent", "B:2-boundary"],
            rationale="exactly 2 branches -> the >=2 cardinality floor",
        ),
        ind(
            case="FANOUT-independent-many-branch-09",
            prompt=(
                "You are given six unrelated abstracts in /workspace/abstracts/ (1.txt "
                "through 6.txt). Summarize each one independently in a single sentence. The "
                "six summaries do not depend on each other."
            ),
            want_branch_count=6,
            axis=["A:independent", "B:many-ceiling"],
            rationale="6 branches -> stresses the max_concurrency ceiling",
        ),
        ind(
            case="FANOUT-independent-L2-decompose-10",
            prompt=(
                "Independently produce a one-paragraph briefing on each of these three "
                "unrelated regions — the Nordics, Iberia, and the Baltics — covering, for "
                "each region separately, (1) its largest city (2) its primary language "
                "(3) its currency. The three briefings do not depend on each other."
            ),
            want_branch_count=3,
            # want_depth is a SECONDARY, non-gating observation (§4.1a): the prompt
            # borrows L2's structural levers (per-branch (1)(2)(3) sub-fields, >=35
            # words) while avoiding every dependency marker. If the scorer fires L1
            # the row still scores on want_fanout (fan-out declines only at L0).
            want_depth="L2",
            axis=["A:independent", "B:3", "E:L2"],
            rationale="engineered L2-and-independent; want_depth secondary/non-gating (§4.1a)",
        ),
    ]


def _fanout_decline_rows() -> list[dict]:
    """§4.2 — sequentially dependent; want_fanout=False. The load-bearing family.

    The near-miss (DISGUISE) rows LOOK parallel but chain; each is built to trip a
    NAMED signal of the deterministic dependency detector (component spec §3a) so
    detector and corpus are co-designed:
      back-ref markers (then/use the result/that/around X) | conditional gating
      (if eligible, then) | shared write target (same file).
    The obvious rows are sequential with no disguise (the easy decline).
    """
    dec = lambda **kw: _row(phase="fanout", want_fanout=False, **kw)  # noqa: E731
    return [
        # ── near-miss traps (axis C:near-miss) — the hard discrimination ──
        dec(
            case="FANOUT-decline-trip-dated-01",
            prompt=(
                "Book a trip: first book the flight, then book a hotel around the flight "
                "dates, then book a rental car for the hotel stay."
            ),
            axis=["A:dependent", "C:near-miss", "B:3"],
            rationale="trap: hotel depends on flight dates, car on hotel; 'then'+'around' back-refs -> decline",
        ),
        dec(
            case="FANOUT-decline-restaurant-then-route-02",
            prompt=(
                "Pick a highly-rated restaurant with an open dinner slot, then get directions "
                "to that restaurant and make a reservation under that name."
            ),
            axis=["A:dependent", "C:near-miss"],
            rationale="trap: directions+reservation depend on the pick; 'then'+'that' back-refs -> decline",
        ),
        dec(
            case="FANOUT-decline-benchmark-then-tune-03",
            prompt=(
                "Benchmark Redis and Memcached for our cache, then use those numbers to "
                "recommend one and tune its configuration."
            ),
            axis=["A:dependent", "C:near-miss"],
            rationale="trap: gather-then-compare (sec 2.3); 'then use those numbers' back-ref -> decline",
        ),
        dec(
            case="FANOUT-decline-fetch-then-transform-04",
            prompt=(
                "Fetch the dataset from /workspace/raw.csv, then clean it, then compute the "
                "summary statistic from the cleaned data."
            ),
            axis=["A:dependent", "C:near-miss"],
            rationale="trap: strict ETL chain disguised as 3 tasks; 'then...then' -> decline",
        ),
        dec(
            case="FANOUT-decline-shared-write-05",
            prompt=(
                "Have three workers each append their section to the same report file "
                "/workspace/report.md: an intro section, a results section, and a conclusion."
            ),
            axis=["A:dependent", "C:near-miss-shared-write"],
            rationale="trap: independent-looking but SHARED WRITE TARGET (detector signal 2) -> decline",
        ),
        dec(
            case="FANOUT-decline-pick-then-act-06",
            prompt=(
                "Choose the cheapest of the three available flights, then book that flight and "
                "add a seat and a checked bag for that flight."
            ),
            axis=["A:dependent", "C:near-miss"],
            rationale="trap: book/seat/bag all depend on the choice; 'then'+'that flight' anaphora -> decline",
        ),
        dec(
            case="FANOUT-decline-policy-dependent-10",
            prompt=(
                "Check whether the customer is eligible, and if eligible then apply the "
                "discount, then confirm the new total."
            ),
            axis=["A:dependent", "C:near-miss-conditional"],
            rationale="trap: conditional chain; 'if eligible then' gating (detector signal 1) -> decline",
        ),
        # ── obvious sequential (axis C:obvious) — the easy decline ──
        dec(
            case="FANOUT-decline-obvious-chain-07",
            prompt=(
                "Read /workspace/seed.txt to get a filename, then read that file, then "
                "summarize its contents."
            ),
            axis=["A:dependent", "C:obvious"],
            rationale="obvious sequential; 'then'+'that file' back-ref -> decline",
        ),
        dec(
            case="FANOUT-decline-obvious-pipeline-08",
            prompt="Compile the code, then run the tests, then deploy if the tests are green.",
            axis=["A:dependent", "C:obvious"],
            rationale="obvious sequential pipeline; 'then'+conditional -> decline",
        ),
        dec(
            case="FANOUT-decline-single-multistep-09",
            prompt="Plan and then write a 3-paragraph essay on the causes of the 1929 crash.",
            axis=["A:dependent", "C:obvious"],
            rationale="single coherent task, not parallel-decomposable; 'and then' -> decline",
        ),
    ]


def _fanout_fault_rows() -> list[dict]:
    """§4.3 — partial-survival; want_fanout=True, want_survives_partial=True.

    Timing modes carry a magic objective token the env-gated worker fault-hook
    reads (FANOUT_FAULT_INJECT=1, off in prod; §4.3a). Hard-error and degraded
    modes inject purely through the prompt (a guaranteed-missing path / an
    empty-output instruction) so they exercise the REAL error/degraded paths
    with nothing stubbed.
    """
    fault = lambda **kw: _row(  # noqa: E731
        phase="fanout",
        want_fanout=True,
        want_survives_partial=True,
        **kw,
    )
    return [
        fault(
            case="FANOUT-fault-one-branch-errors-01",
            prompt=(
                "Independently summarize each of three files: /workspace/docs/a.txt, "
                "/workspace/docs/b.txt, and /workspace/__nonexistent_fault_42__.txt. The "
                "summaries are independent; report whichever succeed."
            ),
            want_branch_count=3,
            axis=["A:independent", "D:one-fails"],
            rationale="hard error via guaranteed-missing path on 1 of 3 -> sentinel, join answers from 2/3",
        ),
        fault(
            case="FANOUT-fault-one-branch-times-out-02",
            prompt=(
                "Independently handle three tasks: summarize /workspace/docs/a.txt, "
                "summarize /workspace/docs/b.txt, and __FAULT_TIMEOUT__ produce an "
                "exhaustive analysis. The three are independent; report whichever finish."
            ),
            want_branch_count=3,
            axis=["A:independent", "D:timeout"],
            rationale="__FAULT_TIMEOUT__ token -> per-branch timeout fires, no super-step hang",
        ),
        fault(
            case="FANOUT-fault-all-but-one-fail-03",
            prompt=(
                "Independently summarize each of three files: /workspace/docs/a.txt, "
                "/workspace/__nonexistent_fault_43__.txt, and "
                "/workspace/__nonexistent_fault_44__.txt. Report whichever succeed."
            ),
            want_branch_count=3,
            axis=["A:independent", "D:majority-fail"],
            rationale="2 of 3 fail (missing paths) -> join degrades to single-survivor answer, non-empty",
        ),
        fault(
            case="FANOUT-fault-join-degraded-04",
            prompt=(
                "Independently produce three things: a one-line summary of "
                "/workspace/docs/a.txt, a one-line summary of /workspace/docs/b.txt, and for "
                "the third return exactly an empty string. Then report all three; note any gap."
            ),
            want_branch_count=3,
            axis=["A:independent", "D:degraded-input"],
            rationale="1 branch returns empty (no exception) -> join synthesizes around the gap, not a crash",
        ),
        fault(
            case="FANOUT-fault-slow-branch-05",
            prompt=(
                "Independently handle three tasks: summarize /workspace/docs/a.txt, summarize "
                "/workspace/docs/b.txt, and __FAULT_SLOW__ summarize /workspace/docs/c.txt. "
                "The three are independent; report all three."
            ),
            want_branch_count=3,
            axis=["A:independent", "D:straggler"],
            rationale="__FAULT_SLOW__ token (under ceiling) -> barrier waits for the straggler, no premature join",
        ),
    ]


def _fanout_control_rows() -> list[dict]:
    """§4.4 — precision guard; want_fanout=False on trivial single-step work."""
    ctrl = lambda **kw: _row(phase="fanout", want_fanout=False, **kw)  # noqa: E731
    return [
        ctrl(
            case="FANOUT-control-L0-trivial-01",
            prompt="Echo the phrase 'pipeline ok' verbatim.",
            axis=["E:L0", "B:0-1"],
            rationale="L0 single-action -> condition-1 floor -> decline (no fan-out)",
        ),
        ctrl(
            case="FANOUT-control-single-write-02",
            prompt="Write the number 42 to /workspace/answer.txt.",
            axis=["B:0-1"],
            rationale="single step, nothing to parallelize -> decline",
        ),
        ctrl(
            case="FANOUT-control-single-read-03",
            prompt="Read the first line of /workspace/notes.txt and print it.",
            axis=["B:0-1"],
            rationale="single read -> decline",
        ),
        ctrl(
            case="FANOUT-control-ambiguous-trivial-04",
            prompt=(
                "Write 'a' to /workspace/a.txt and 'b' to /workspace/b.txt."
            ),
            axis=["A:independent", "B:2-below-floor"],
            rationale="boundary: 2 trivial independent writes BELOW the '<3 don't bother' floor -> decline",
        ),
    ]


def build_corpus() -> list[dict]:
    rows = (
        _depth_rows()
        + _replan_rows()
        + _reflexion_rows()
        + _escalation_rows()
        + _fanout_rows()
    )
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

    # Assign the regex-conforming gj_id (GJ-STRESS-NN) sequentially. This is the
    # id the gj: thread bridge parses (^GJ-(?:...|STRESS-\d+|...)$); the bridge
    # then adopts each row's trace_id verbatim as the Langfuse join key.
    for i, r in enumerate(rows, start=1):
        r["gj_id"] = f"GJ-STRESS-{i:02d}"
    return rows


def main() -> None:
    rows = build_corpus()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    by_phase: dict[str, int] = {}
    for r in rows:
        by_phase[r["phase"]] = by_phase.get(r["phase"], 0) + 1
    print(f"wrote {len(rows)} cases to {OUT_PATH}")
    for phase, n in sorted(by_phase.items()):
        print(f"  {phase:12s} {n}")


if __name__ == "__main__":
    main()
