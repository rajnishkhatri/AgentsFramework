---
type: review
title: 'Governance Trace Audit — memory-ON live run (Piece C deploy)'
description: 'Date: 2026-06-18 (RESOLVED — was PENDING; first carrier-bearing run audited below)'
tags: [review]
---

# Governance Trace Audit — memory-ON live run (Piece C deploy)

**Date:** 2026-06-18 (RESOLVED — was PENDING; first carrier-bearing run audited below)
**Target:** `agent-backend-combined` Cloud Run, `mem` tag, project `agent-prod-gcp-dev`, region `us-central1`.
**Trace audited:** workflow `ef236f957b6c4e64a723bee71d857d5b` · run `a37cf5e5659a4efba01b7ebd281f0a73` · thread `c5f62baf-d2b1-410c-9d61-17544739ac88` · 20 observations · `/tmp/memory_trace_ef236f95.json`
**Full per-trace report:** [`governance_audit_ef236f95_2026-06-18.md`](governance_audit_ef236f95_2026-06-18.md)

---

## VERDICT: **COMPLIANT WITH FINDINGS** — memory seam verified live; run-level corrupt success caught by governance

> **Instrumentation PASS** (memory carriers fire and are observable: `memory.recalled`
> count=3, two `memory.stored` incl. autocapture-shadow; all content-free; same subject
> on every carrier) **· run honesty: claimed success but `goal_met=false` — the judge
> CAUGHT it · next: nothing actionable for the memory deploy.** Plan Verification 4 is
> satisfied: carriers present, content absent, COMPLIANT, no carrier_gate memory alert.

---

## Acceptance bar (plan §Verification 4) — all met

| Requirement | Result | Evidence |
|---|---|---|
| `memory.recalled` carrier present (count, query_len) | ✅ | `{user_id, count: "3", query_len: "21"}` (step 3) |
| `memory.stored` carrier present (key) | ✅ | `{user_id, key: "a37cf5e5…"}` (step 4, run-end) |
| **Memory CONTENT absent from carriers** (privacy) | ✅ | no payload/query/answer text on any carrier — count/len/key/type/salience only |
| Four-pillar verdict healthy | ✅ | Recording PASS, Validation PASS, Reasoning PASS, Identity UNVERIFIABLE-by-shape (resumed run) |
| `identity.owner` == run subject (no cross-user leak) | ✅ | every carrier `user_id == subject == user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX` |
| No memory-attributable `carrier_gate` alert | ✅ | 3 `carrier_gate` checks all `outcome: pass`, `would_enforce: False`, `missing_carriers: "[]"` |

Bonus: **Phase-2 autocapture is live and correctly in SHADOW** — a third
`memory.stored` carries `type: "semantic", salience: "0.8", proposed_only: "True"`
(proposed, not committed).

## Pillar scorecard (summary — full quotes in the per-trace report)

| Pillar | Status | One-line evidence |
|---|---|---|
| Recording | PASS | `step.executed`: `tokens_in: 1456, tokens_out: 34, cost_usd: 0.0002388`; one `llm.call`; `integrity_hash` present |
| Identity | UNVERIFIABLE (by shape) | resumed at step 3 → no `task.started`; `subject` present on run + every carrier |
| Validation | PASS | 6 `guardrail.checked` (output_scan + carrier_gate all pass); no tool calls → no silent failure possible |
| Reasoning | PASS | `model.selected.rationale` + `alternatives` + `decision_id`; one `step.planned` (dedup ✅); `eval.goal_judge` present |

## Corrupt-success check — CAUGHT BY GOVERNANCE (run-level, not instrumentation)

`task.completed`: `outcome: "success"` + `goal_met: false`,
`unmet_conditions: "['my son name is garvit']"`. The agent replied
*"Thank you for sharing, Rajnish!…"* without confirming the name; the judge
flagged it: `goal_met: false`, rationale *"The final answer fails to address the
user's statement about their son's name."* Instrumentation worked — the trace
admits the failure. GIGO caveat: `conditions_source: "deterministic"` (the
condition is a prompt fragment); `downgrade_applied: false` = Stage-2 gate off
(expected). Not a deploy blocker.

---

## How this resolved from PENDING

The first version of this report was **AUDIT PENDING** — the `mem` tag was
healthy with `MEMORY_ENABLED=true` but the only request had been a 401, so no
trace existed. The first *authenticated* run (rev `00083-wal`) then emitted
**zero** memory carriers despite flag-on + real user_id + durable Mem0 — which
was root-caused (NOT a rate limit, neither Langfuse nor Mem0) to a wiring drop
in `middleware/app_prod.py`: `build_combined_app` rebuilt a narrow
`AgentComponents` that dropped `memory_service`/`memory_autocapture`, so the
graph compiled memory-blind. Fixed (graph now built from the full bag) + a
regression guard (`tests/middleware/test_app_prod_memory_wiring.py`). After
rebuild + redeploy, this trace (`ef236f95…`) carries the full carrier set —
resolving the audit.

## Unverifiable in this trace / recommended follow-up

Identity's from-step-0 fields (`agent_name`/`agent_version`/`agent_facts_id`)
are absent because this is a resumed run (3rd turn of the session). Subject is
present, so *who* is answerable, but the registered-agent block is not. A
**from-step-0** authenticated run on the `mem` tag would prove the full Identity
pillar — recommended as a one-time confirmation, not a blocker.

## Side finding (unchanged, low severity)

`agent-middleware` remains an orphaned `hello`-placeholder Cloud Run service
(no traffic, nothing routes to it) — worth deleting for hygiene. Not part of
the memory deploy.
