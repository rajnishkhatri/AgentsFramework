---
type: decision-record
title: 'ADR-0004: Automate code-review integration — deterministic CI gate + advise-only harness sensors'
status: accepted
created: 2026-06-29
updated: 2026-06-29
owner: Rajnish Khatri
related: unified_context_routed_reviewer.plan.md, GATES.md
tags: [decision-record]
---

# ADR-0004: Automate code-review integration

**Status:** Accepted — 2026-06-29.
**Related:** `docs/plan/unified_context_routed_reviewer.plan.md` (WI-6/WI-7/WI-8), `docs/adr/GATES.md`.
**Audience:** Anyone changing the CI gates, the harness hooks, or the reviewer's invocation surface.

---

## Context

The unified context-routed reviewer (`meta/code_reviewer.py`, v3, WI-1…WI-9) is built and the
v3 LLM judge is certified (WI-8: TPR=1.0/TNR=1.0, committed `verdicts.json`). But it was only
ever invoked **on demand** — via the `code-review` skill or a hand-typed CLI. Nothing wired it
into the team's automated gates, so the deterministic checks (D1/D4/D5 + ADR.1 + TAP-2/4 + frontend
FD2/FD3) that cost nothing to run were not running on every PR. Two standing constraints shaped the
wiring: repo policy forbids **live LLM calls in CI**, and Claude Code hooks **cannot capture a typed
human gate answer** (the honest limit recorded in `GATES.md`).

---

## Decision

Wire the reviewer into five integration points, all deterministic-first and advise-leaning:

1. **CI `reviewer` job** (`.github/workflows/python-tests.yml`) — runs `--deterministic-only` on
   PRs, diffing `origin/<base>...HEAD`. **Blocks merge only on `reject` (exit 2)** and on tool error
   (exit 3); `request_changes` (exit 1) is surfaced, non-blocking. Uploads `review.json`.
2. **`make review`** — a thin wrapper over the v3 PR-style CLI (deterministic by default;
   `ARGS="--llm"` opts into the certified judge locally), mirroring `make check` discoverability.
3. **Stop hook** (`scripts/hooks/stop_adr_reminder.py`) — advise-only ADR.1 reminder at turn end,
   reusing the shared `detect_adr1_missing` detector.
4. **SubagentStop hook** (`scripts/hooks/subagent_stop_review.py`) — advise-only deterministic v3
   review when a subagent touches an architecture seam (`trust/`, new `services/`, graph nodes).
5. **PR comment bot** (`.github/workflows/reviewer-comment.yml`) — posts/updates one informational
   PR comment summarizing `review.json`; never changes the merge state.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **LLM reviewer in CI** | Violates the no-live-LLM-in-CI policy (cost, secrets, nondeterminism). The certified judge is exercised instead by the WI-8 *recorded replay* in the `tests` job. |
| **Block CI on `request_changes` (exit ≥1)** | Too noisy for a first rollout before the deterministic false-positive rate is measured. Advise-first: block on `reject` only, graduate later with data. |
| **Per-edit reviewer hook** | Explicit WI-7 decision — cost + latency + noise; even a certified judge should not gate every keystroke. SubagentStop fires once per subagent, on seams only. |
| **Blocking ADR hook with typed-answer capture** | Impossible — hooks have no controlling terminal (the GATES.md honest limit). The Stop/SubagentStop sensors *remind*; the merge-time `test_adr_ratchet.py` is the hard gate. |
| **Duplicate rule prose in hooks/workflows** | Violates cite-don't-copy. Hooks reuse `detect_adr1_missing` / `run_deterministic_review_v3` and point at `REVIEW.md`; they never restate rules. |

---

## Rationale

Deterministic checks are free, reproducible, and already trusted — running them on every PR is pure
upside. Keeping the gate at `reject`-only and the hooks advise-only matches the project's measure-before-
enforce posture and the honest hook limit, while the recorded WI-8 replay keeps the certified judge in the
loop without a live call. Reusing the existing detectors/runner (not re-implementing them) keeps a single
source of truth for the rules.

---

## Consequences

- CI now has a PR-only `reviewer` job and a `reviewer-comment` workflow (needs `pull-requests: write`,
  kept separate from the read-only reviewer job via a `workflow_run` trigger).
- New harness hooks fire on every turn end / subagent stop; both are cheap no-ops off-seam and never block.
- **Follow-up (not in this change):** graduate the SubagentStop hook to block on `reject` once the
  false-positive rate is measured (record that decision in `decisions.md` or a successor ADR).
- **Re-record obligation unchanged:** when the judge model changes, re-run
  `scripts/record_code_reviewer_validation.py`; only commit a new `verdicts.json` if TPR/TNR ≥ 0.90.

---

## Supersedes / related

Implements the PR-integration roadmap for `docs/plan/unified_context_routed_reviewer.plan.md`.
Does not supersede any prior ADR.
