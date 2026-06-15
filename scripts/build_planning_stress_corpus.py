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
) -> dict:
    """One corpus row. Only the expectation keys relevant to ``phase`` are set;
    the analysis half reads them by phase, so absent keys are simply not scored.
    """
    row: dict = {
        "case": case,
        "prompt": prompt,
        "phase": phase,
        "rationale": rationale,
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


def build_corpus() -> list[dict]:
    rows = (
        _depth_rows()
        + _replan_rows()
        + _reflexion_rows()
        + _escalation_rows()
    )
    # Guard: case ids must be unique (a dup would collide trace_ids and silently
    # overwrite a capture row).
    seen: set[str] = set()
    for r in rows:
        if r["case"] in seen:
            raise ValueError(f"duplicate case id: {r['case']}")
        seen.add(r["case"])
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
