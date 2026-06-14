#!/usr/bin/env python3
"""Grade iteration-1 answers against assertions. Writes grading.json per run dir.

Assertions are keyword/concept presence checks over the answer.md text — objective and
reproducible. Each assertion has a `text` (human label), a matcher, and produces
{text, passed, evidence} as the viewer expects.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import sys as _sys
ROOT = Path(_sys.argv[1]).resolve() if len(_sys.argv) > 1 else Path(__file__).resolve().parent


def any_of(*patterns: str):
    rxs = [re.compile(p, re.I) for p in patterns]
    def match(text: str) -> tuple[bool, str]:
        for rx in rxs:
            m = rx.search(text)
            if m:
                return True, m.group(0)[:120]
        return False, ""
    return match


def all_of(*patterns: str):
    rxs = [re.compile(p, re.I) for p in patterns]
    def match(text: str) -> tuple[bool, str]:
        hits = []
        for rx in rxs:
            m = rx.search(text)
            if not m:
                return False, f"missing: {rx.pattern}"
            hits.append(m.group(0)[:60])
        return True, " | ".join(hits)
    return match


def absent_or_negated(bad_pattern: str, *negators: str):
    """Pass if `bad_pattern` is absent, OR every occurrence is within ~30 chars of a
    negator (never/no/avoid). Fails only when the bad construct is actually proposed.
    """
    bad = re.compile(bad_pattern, re.I)
    negs = [re.compile(n, re.I) for n in negators]
    def match(text: str) -> tuple[bool, str]:
        proposed = []
        for m in bad.finditer(text):
            window = text[max(0, m.start() - 35): m.end() + 5]
            if not any(n.search(window) for n in negs):
                proposed.append(window.strip()[:80])
        if proposed:
            return False, "proposed (not negated): " + proposed[0]
        return True, "absent or only negated"
    return match


# eval_name -> list of (assertion_text, matcher)
ASSERTIONS = {
    "eval-0-plan-builder-trace-altitude": [
        ("Picks TRACE altitude (not span) for the planner", any_of(r"trace[- ]altitude", r"altitude:\s*trace", r"\btrace\b.{0,40}altitude")),
        ("Justifies altitude by trajectory dependence", any_of(r"trajectory", r"whole .{0,20}run", r"depends on the .{0,15}plan")),
        ("Identifies the real seam (router/select_planning_depth) since plan_builder is deterministic", any_of(r"select_planning_depth", r"router", r"deterministic.{0,40}(upstream|router|no LLM|no model)")),
        ("Capture payload carries planning_depth + depth_reason for trace scoring", all_of(r"planning_depth", r"depth_reason|reason")),
        ("Starts with Phase 0 / open coding BEFORE a judge", all_of(r"phase 0", r"open coding")),
        ("Ships a Tier-A deterministic L1 check first", all_of(r"tier-?a", r"\bL1\b", r"deterministic")),
        ("Defers the gold-set/judge track as on-demand", any_of(r"on-?demand", r"only .{0,20}(if|when) tier-?a", r"did \*?\*?not\*?\*? build a judge", r"earned")),
        ("Cadence-first loop trigger (2-4 weeks)", any_of(r"2[–\-]4 ?week", r"cadence")),
        ("Includes the bias-corrected success rate θ̂", any_of(r"θ̂", r"theta", r"bias-?corrected", r"p_obs")),
        ("References the fail-closed §2.8 enable-gate", any_of(r"fail-?closed", r"§2\.8", r"GateDecision", r"REFUSE")),
        ("Does NOT propose a 1-5 Likert judge (binary only)", absent_or_negated(r"1[\-–]5", r"never", r"\bno\b", r"\bnot\b", r"avoid", r"instead of")),
    ],
    "eval-1-summarizer-tier-a-greenfield": [
        ("Ships a Tier-A deterministic L1 check (100%)", all_of(r"tier-?a", r"deterministic", r"100%")),
        ("L1 check lives in services/ with no framework imports", any_of(r"services/.*\.py.{0,80}no .{0,15}framework", r"no .{0,5}(framework|components|langgraph).{0,30}import", r"grep -nE")),
        ("Adds an offline CI regression row", all_of(r"benchmark", r"regression|run_eval")),
        ("Uses python -m meta.run_eval to score", any_of(r"meta\.run_eval", r"meta/run_eval")),
        ("Open coding precedes the rubric", all_of(r"open coding", r"phase 2")),
        ("Explicitly says NOT to build a judge on day one", any_of(r"did \*?\*?not\*?\*? build a judge", r"do not pre-?build a judge", r"stop at tier-?a", r"not .{0,20}graduate to a judge", r"probably skip")),
        ("Picks an altitude explicitly (span)", any_of(r"altitude:?\s*span", r"\bspan\b.{0,30}altitude", r"altitude.{0,20}span")),
        ("Notes the seam is deterministic (no LLM) → truncation/omission failures", any_of(r"no LLM", r"no model", r"deterministic.{0,40}(concatenat|string|slic|truncat)", r"truncation")),
        ("Requires the telemetry publish/sink, not just eval_capture.record", any_of(r"publish_", r"langfuse sink", r"sink adapter", r"eval_telemetry")),
        ("100% framed as compaction invocations (rare), not all traffic", any_of(r"100% of .{0,20}(compaction|invocation)", r"rarely.{0,15}fire", r"only .{0,15}(under token|compaction)")),
    ],
    "eval-2-which-seam-next-prioritizer": [
        ("Reaches for the transition failure matrix", any_of(r"transition failure matrix", r"first-?failure matrix", r"error-?propagation")),
        ("Data-driven, explicitly NOT by gut/intuition", any_of(r"don'?t (pick|choose|instrument) by (gut|vibe|intuition)", r"not .{0,10}by (gut|vibe|intuition)")),
        ("Rows/cols = last-clean-state x first-failure-state", all_of(r"row", r"column", r"first[- ]failure")),
        ("Reuses existing first-failure attribution sources", all_of(r"guardrail_validator", r"goal_judge", r"synthesis_validator")),
        ("Notes the meta/analysis.py aggregator is not yet built", any_of(r"not yet", r"not built", r"planned deliverable", r"planned function", r"no transition-?matrix function", r"does not yet|doesn'?t yet|still a planned", r"isn'?t built")),
        ("Picks the highest-count cell as the next seam", any_of(r"highest[- ]count cell", r"highest .{0,15}cell", r"top cell")),
        ("Run the matrix anyway on thin data (directional)", any_of(r"anyway", r"directional", r"even .{0,15}(72|thin|hand)", r"hand[- ]aggregat")),
        ("Re-attributes the completion/evaluation attribution sink", any_of(r"attribution sink", r"re-?attribut", r"completion.{0,20}sink")),
    ],
}


def grade_run(eval_name: str, run_dir: Path) -> dict:
    rd = run_dir / "run-1" if (run_dir / "run-1").exists() else run_dir
    answer = rd / "outputs" / "answer.md"
    text = answer.read_text() if answer.exists() else ""
    expectations = []
    for assertion_text, matcher in ASSERTIONS[eval_name]:
        passed, evidence = matcher(text)
        expectations.append({"text": assertion_text, "passed": bool(passed), "evidence": evidence})
    return {"expectations": expectations}


def main() -> None:
    iteration = ROOT
    for eval_dir in sorted(iteration.glob("eval-*")):
        eval_name = eval_dir.name
        if eval_name not in ASSERTIONS:
            continue
        for variant in ("with_skill", "without_skill"):
            run_dir = eval_dir / variant
            if not run_dir.exists():
                continue
            grading = grade_run(eval_name, run_dir)
            rd = run_dir / "run-1" if (run_dir / "run-1").exists() else run_dir
            (rd / "grading.json").write_text(json.dumps(grading, indent=2))
            n_pass = sum(e["passed"] for e in grading["expectations"])
            n = len(grading["expectations"])
            print(f"{eval_name:42s} {variant:14s} {n_pass}/{n}")


if __name__ == "__main__":
    main()
