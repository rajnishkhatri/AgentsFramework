---
type: log
title: 'Lightweight decision log (intent debt, long tail)'
---

# Lightweight decision log

> Append-only, newest first. 2–4 lines per **small** decision: what was decided,
> the alternative rejected, and why. This is the low-friction sibling of the full
> ADRs — use a numbered ADR (`0000-template.md`) for big/structural decisions that
> need Context/Options/Rationale/Consequences; use this for the long tail of
> non-obvious-but-small choices that would otherwise go uncaptured. Lower the bar,
> capture more intent debt. (Playbook: Comprehension-Debt runbook, Part B.)

- 2026-07-01 — **Coach surface is routed under `/learn`, not `/`** (Phase 1.1). The
  design/plan placed the Dashboard at `app/(coach)/page.tsx`, which resolves to `/` —
  but `app/page.tsx` (the chat landing) already owns `/`, and Next.js route groups add
  nothing to the URL, so both pages would resolve to `/` → a build-time parallel-page
  collision. Decision: anchor the whole coach surface under a base segment `COACH_BASE`
  (`/learn`): Dashboard=`/learn`, Quiz=`/learn/quiz`, etc.; `/` stays the chat landing.
  Rejected: (a) coach at `/coach` — would double as `/coach/coach` for the Coach screen;
  (b) coach replaces `/` and chat moves to `/chat` — larger blast radius (touches the
  existing chat app's routing + every link to `/`). `COACH_BASE` is the single source of
  truth in `nav_model.ts`; a regression test forbids any screen routing to `/`.
- 2026-07-01 — **`CoachAgentClient` is not an engine port** (reconciliation). ADR-0006's
  port table + `SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md` §3 + the agent brainstorm §4
  list `CoachAgentClient` as an 8th "engine port over the AG-UI SSE transport." The built
  code ships **no** such port: the coach rides the existing **chat `AgentRuntimeClient`** —
  `use_coach` wraps `use_agent_run` (see `frontend/lib/translators/coach_message_vm.ts`
  header). Decision: the coach is a **consumer of the chat runtime port**, not an engine
  port; the engine bounded context stays **7 ports** (→ 8 with ADR-0011's `LearnerReadRepo`,
  still not the coach). Rejected materializing a `coach_agent_client.ts` engine port — it
  would duplicate the AG-UI transport already confined to the chat adapters (ADR-0006 itself
  rejects a new coach transport). Captured so the doc-vs-code divergence doesn't read as a
  missing port. See [SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §5.1/§7.
- 2026-06-30 — ADR-0007 capability-gating derives the coach's bound tool set from
  a **build-time capability list** (`build_graph(bound_capabilities=…)`), not per-run
  from the `agent_capabilities` resolved into state. Rejected per-run binding: it
  would force the `call_llm` node to recompute tool schemas each turn (build-once is
  the current contract) for a benefit — one graph serving many identities — the
  coach doesn't need. Matches the ADR's "graph-build boundary" wording. Flag OFF by
  default (`capability_gating_enabled`); the run-time `authorization_service` PEP is
  unaffected and complementary (bind-time filter + run-time authz).
- 2026-06-28 — ADR.1 ratchet mechanism = a git-diff **arch-test**
  (`tests/architecture/test_adr_ratchet.py`), not a Stop hook. Rejected the
  Stop-hook trigger (harness v2 item 2.1's first option): a hook can't capture the
  typed human answer the gate wants (honest limit), is version-dependent, and
  doesn't run in CI. The arch-test wires the already-shipped pure detector
  (`detect_adr1_missing`) against the merge-base diff and is version-independent.
  Waiver: an `ADR-OK: <reason>` token in a commit message of the range.
- 2026-06-28 — `.cursor/hooks.json` `afterFileEdit` kept `failClosed:false`.
  Rejected flipping it to `true` (the harness plan's blanket contract). Why: the
  post-edit ruff hook is advisory formatting (HOOK-1 never-block-on-edit); a
  formatter hiccup must not block an edit. Scoped deviation, documented inline in
  the file. The safety gate `beforeShellExecution` stays `failClosed:true`.
