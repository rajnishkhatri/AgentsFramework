#!/usr/bin/env python3
"""SubagentStop hook — advise-only deterministic reviewer on architecture seams.

Wired in ``.claude/settings.local.json`` under ``hooks.SubagentStop``. When a
subagent finishes and its work touched an architecture seam (``trust/``, a new
``services/`` package, an ``orchestration/`` graph node, or any ⚠️ Ask-first
trigger), run the *deterministic* v3 reviewer over the changed files and feed
any findings back to the parent agent.

Contract (Claude Code hooks; see scripts/hooks/AGENTS.md):
  * stdin  : JSON describing the SubagentStop event (read defensively; HOOK-3).
  * exit 0 : no seam touched, or reviewer approves — silent.
  * exit 2 : advisory findings on stderr, fed back to the agent. **Phase 1 is
             advise-only** — never block. The certified-but-costly LLM judge is
             NOT invoked here (no per-turn live LLM); only the deterministic
             path runs. Graduating to a hard block on REJECT is a Phase-2
             follow-up, recorded once the false-positive rate is measured.

Cite-don't-copy: this hook never restates rules. It runs the same deterministic
reviewer the `code-review` skill and CI invoke (``run_deterministic_review_v3``)
and points the agent at the skill / folder ``REVIEW.md`` for detail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_stdin() -> dict | None:
    """Drain the SubagentStop payload. Malformed/empty → None (HOOK-3)."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _changed_files() -> tuple[list[str], list[str]]:
    """``(changed, added)`` working-tree files vs HEAD. ([], []) on git error."""

    def _run(extra: list[str]) -> list[str]:
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only", *extra, "HEAD"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if proc.returncode != 0:
            return []
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    return _run([]), _run(["--diff-filter=A"])


def _touches_seam(changed: list[str], added: list[str]) -> bool:
    """True when the diff touches an architecture seam worth a deterministic pass.

    Seams: the trust kernel, the graph topology, or any ⚠️ Ask-first trigger
    (which ``detect_adr1_missing`` already encodes — reuse it, don't restate the
    list). A new ``services/`` package is itself an Ask-first trigger, so the
    ADR.1 detector covers it; we add ``trust/`` and ``orchestration/`` as the two
    standing seams that always merit a routed deterministic check.
    """
    try:
        from utils.code_analysis import detect_adr1_missing
    except Exception:
        detect_adr1_missing = None

    if detect_adr1_missing is not None:
        adr = detect_adr1_missing(changed, added_files=added)
        if adr.get("triggers"):
            return True

    norm = [p.replace("\\", "/") for p in changed]
    return any(p.startswith("trust/") or p.startswith("orchestration/") for p in norm)


def main() -> int:
    payload = _read_stdin()
    if payload is None:
        return 0  # HOOK-3: bad payload is a clean no-op.

    changed, added = _changed_files()
    if not changed or not _touches_seam(changed, added):
        return 0  # nothing seam-relevant changed.

    # Run the same deterministic reviewer CI + the skill use. Import lazily so a
    # non-seam turn never pays the import cost.
    try:
        from meta.code_reviewer import AGENT_ROOT, run_deterministic_review_v3
        from trust.review_schema import Severity, Verdict
    except Exception:
        print(
            "[subagent_stop_review] could not import the reviewer; skipping. "
            'Run `pip install -e ".[dev]"`.',
            file=sys.stderr,
        )
        return 0

    py_or_ts = [
        p
        for p in changed
        if p.endswith((".py", ".ts", ".tsx")) and (REPO_ROOT / p).exists()
    ]
    if not py_or_ts:
        return 0

    try:
        report = run_deterministic_review_v3(
            py_or_ts, repo_root=AGENT_ROOT, added_files=added
        )
    except Exception as exc:  # never let a reviewer crash interrupt the agent
        print(
            f"[subagent_stop_review] reviewer errored, skipping: {exc}", file=sys.stderr
        )
        return 0

    criticals = [
        f
        for d in report.dimensions
        for f in d.findings
        if f.severity == Severity.CRITICAL
    ]
    warnings = [
        f
        for d in report.dimensions
        for f in d.findings
        if f.severity == Severity.WARNING
    ]

    # Stay silent unless there is something actionable. Deterministic mode always
    # leaves D2/D3/D5 in `gaps` (they need the LLM), so gaps alone must NOT fire
    # the sensor — that would make it shout on every seam change. Fire only on a
    # real finding or a non-approve verdict.
    if report.verdict == Verdict.APPROVE and not criticals and not warnings:
        return 0

    lines = [
        f"[subagent_stop_review] deterministic reviewer verdict: {report.verdict.value} "
        f"({len(criticals)} critical, {len(warnings)} warning).",
    ]
    for f in criticals[:10]:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        lines.append(f"  CRITICAL [{f.rule_id}] {loc} — {f.description}")
    for f in warnings[:10]:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        lines.append(f"  warning  [{f.rule_id}] {loc} — {f.description}")
    if report.gaps:
        lines.append("  gaps (not evaluated): " + "; ".join(report.gaps[:5]))
    lines.append(
        "  This is an advise-only sensor (Phase 1) — fix criticals, then run the "
        "`code-review` skill or `make review` for the full routed report. Rules "
        "live in each folder's REVIEW.md / AGENTS.md."
    )
    print("\n".join(lines), file=sys.stderr)
    return 2  # advisory feedback — does not block (Phase 1).


if __name__ == "__main__":
    sys.exit(main())
