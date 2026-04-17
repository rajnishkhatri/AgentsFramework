{# Token-efficient digest for sprint_story_agent_system.j2
   Full sources: docs/FOUR_LAYER_ARCHITECTURE.md, PLAN_v2.md, docs/STYLE_GUIDE_LAYERING.md,
   research/tdd_agentic_systems_prompt.md. Rule IDs align with prompts/codeReviewer/CodeReviewer_architecture_rules.j2 #}

## Canonical repository map (PLAN_v2 vs style-guide wording)

**When referencing this repository's implementation, use the PLAN_v2 directory map as canonical (`agent/services/`, `agent/components/`, `agent/orchestration/`, `agent/trust/`). Treat `utils/` in the style guide as the conceptual "horizontal services" layer, mapped to `agent/services/` and `agent/utils/` (e.g. `code_analysis.py`, `cloud_providers/`) as listed in PLAN_v2's file tree.**

| Style guide / diagram | Canonical in this repo | Notes |
|----------------------|-------------------------|--------|
| `utils/` (horizontal) | `agent/services/` | Prompt, LLM, guardrails, tools, eval_capture, observability, governance service modules |
| `agents/` (vertical) | `agent/components/` | router, evaluator, schemas, routing_config — no LangGraph imports |
| `governance/` (meta diagram) | `agent/services/governance/` (runtime) + `agent/meta/` (offline optimization) | Meta reads logs and tunes `RoutingConfig`; it does not call orchestration upward |
| Trust foundation | `agent/trust/` | Pure models, protocols, signature — **T1: zero outward imports** |

**Drift control:** Stories must cite paths under `agent/` from the current tree. Bump digest when PLAN_v2 phases or module layout change.

---

## Four layers + trust (placement authority)

- **Trust foundation (`agent/trust/`):** Shared kernel — `AgentFacts`, policies, `ReviewReport`, signatures, `IdentityProvider` / `PolicyProvider` / `CredentialProvider` ports. Adapters live under `agent/utils/cloud_providers/`. No I/O inside kernel modules (T2).
- **Horizontal services (`agent/services/`):** Cross-cutting infrastructure — `prompt_service`, `llm_config`, `guardrails`, `eval_capture`, `tools/`, `governance/` (BlackBox, PhaseLogger, AgentFactsRegistry, GuardRailValidator). **H1:** prompts are `.j2` via PromptService, not embedded strings.
- **Vertical components (`agent/components/`):** Domain logic — `router`, `evaluator`, `schemas`, `routing_config`. **V-rule:** no vertical-to-vertical imports (**AP2**, **DEP.v_no_v**).
- **Orchestration (`agent/orchestration/`):** LangGraph topology only — thin nodes delegating to services/components (**O1**; **DEP.orch_reads_trust**, **DEP.orch_uses_h**, **DEP.orch_calls_v**). **R11:** nothing imports orchestration from below (**DEP.no_upward_to_orch**).
- **Meta (`agent/meta/`):** Offline judge, analysis, drift, optimizer — reads artifacts; may tune `components/routing_config.py`; **must not** call orchestration (**M2**, **AP8**).

**Runtime trust gate (when stories touch identity/policy):** PEP/PDP-style separation stays at ports + adapters; execution records correlate via `workflow_id`, BlackBox, PhaseLogger, and eval_capture targets.

---

## Dependency rules (same IDs as CodeReviewer digest)

Use **DEP.*** rows and **AP1–AP9** from `prompts/codeReviewer/CodeReviewer_architecture_rules.j2` — do not restate the full table here. Story-level guardrails:

- No trust types defined outside `agent/trust/` (**AP6**).
- No horizontal importing vertical (**DEP.h_no_vertical**).
- No vertical↔vertical imports (**DEP.v_no_v** / **AP2**).
- Orchestration stays topology-only; meta never drives live graph execution directly (**AP8**).

---

## Agentic testing pyramid (story tagging)

| Tier | CI | Fit |
|------|-----|-----|
| **L1** | Block merge | `trust/`, pure schemas, deterministic functions |
| **L2** | Block merge | `services/`, `utils/`, contracts, import/architecture tests |
| **L3** | Warn / scheduled | Vertical evals, LLM-as-judge, rubrics |
| **L4** | Nightly / on-demand | Simulations, multi-turn; markers `slow`, `simulation`, `live_llm` — not default CI |

**Failure paths first** for gates (guardrails, signature verification, tool allowlists).

---

## Governance pillars (PLAN_v2)

Stories that touch observability or compliance should name touchpoints: **BlackBox** (recording), **AgentFactsRegistry** (identity), **GuardRailValidator** (validation specs), **PhaseLogger** (decisions/outcomes), **eval_capture** (structured AI I/O), and **`workflow_id`** correlation where applicable.
