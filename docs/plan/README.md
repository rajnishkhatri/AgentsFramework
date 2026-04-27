# Plans Index

This directory holds all planning artifacts in the repo, organized by the four-layer architecture (plus the outer adapter ring and sprint/process plans).

For the architectural rules these plans target, see [docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](../Architectures/FOUR_LAYER_ARCHITECTURE.md), [docs/STYLE_GUIDE_LAYERING.md](../STYLE_GUIDE_LAYERING.md), [docs/STYLE_GUIDE_PATTERNS.md](../STYLE_GUIDE_PATTERNS.md), and the workspace-wide rules in [AGENTS.md](../../AGENTS.md).

System-wide plans (cross-layer) remain at the repo root: [PLAN.md](../../PLAN.md) (3-layer original) and [PLAN_v2.md](../../PLAN_v2.md) (4-layer with trust kernel).

## Layout

```
docs/plan/
├── README.md                    <- this file
├── trust/                       <- Trust Foundation layer plans
│   ├── TRUST_FOUNDATION_PROTOCOLS_PLAN.md
│   └── TRUST_PLAN_REVIEW_REPORT.md
├── frontend/                    <- Frontend layer plans (Pareto-alternative versions)
│   ├── FRONTEND_PLAN.md                    <- v0 (AWS App Runner, deferred Pyramid panel)
│   ├── FRONTEND_PLAN_V1.md                 <- v1 (revision 2; AWS, disciplined)
│   ├── FRONTEND_PLAN_V2_FRONTIER.md        <- frontier flagship (GCP + multi-cloud DR, full UX)
│   └── FRONTEND_PLAN_V3_DEV_TIER.md        <- dev-tier (V2-Frontier on free / PAYG substrates)
├── adapter/                     <- Outer adapter ring (frontend <-> backend)
│   ├── AGENT_UI_ADAPTER_PLAN.md            <- implementation spec (current)
│   └── AGENT_UI_ADAPTER_PLAN_V1.1.md       <- planning meta-artifact / design rationale
└── sprint/                      <- Sprint / process plans
    └── SPRINT_PHASE4_PLAN.md
```

## By layer

### Trust Foundation (`trust/`)

| Plan | Purpose | Status |
|------|---------|--------|
| [TRUST_FOUNDATION_PROTOCOLS_PLAN.md](trust/TRUST_FOUNDATION_PROTOCOLS_PLAN.md) | Cloud-agnostic protocol definitions (`IdentityProvider`, `PolicyProvider`, `CredentialProvider`) and AWS IAM PoC | Implemented in `trust/protocols.py`, `utils/cloud_providers/` |
| [TRUST_PLAN_REVIEW_REPORT.md](trust/TRUST_PLAN_REVIEW_REPORT.md) | Plan-vs-implementation review of the trust foundation | Review complete; three behavioral gaps documented |

### Frontend (`frontend/`)

Three forward-looking parallel alternatives, plus the original v0 plan kept for lineage. Choose one; do not stack them.

| Plan | Substrate | Cost band (dev) | UX bar |
|------|-----------|-----------------|--------|
| [FRONTEND_PLAN.md](frontend/FRONTEND_PLAN.md) | AWS App Runner + Vercel | $60-90/mo | Beta-grade; defers Pyramid panel |
| [FRONTEND_PLAN_V1.md](frontend/FRONTEND_PLAN_V1.md) | AWS-native, ECS Fargate | $150-180/mo | Beta; Pyramid in v1.5 |
| [FRONTEND_PLAN_V2_FRONTIER.md](frontend/FRONTEND_PLAN_V2_FRONTIER.md) | GCP primary + AWS DR | $540-890/mo | Claude-Artifacts class, day 1 |
| [FRONTEND_PLAN_V3_DEV_TIER.md](frontend/FRONTEND_PLAN_V3_DEV_TIER.md) | GCP free tier + Cloudflare + Neon | $5-30/mo (Stage A) | V2-Frontier UX on free substrates; graduates per quota |

### Adapter (outer ring `agent_ui_adapter/`)

| Plan | Purpose |
|------|---------|
| [AGENT_UI_ADAPTER_PLAN.md](adapter/AGENT_UI_ADAPTER_PLAN.md) | Implementation spec for the `agent_ui_adapter/` package: AG-UI wire contract, single `AgentRuntime` port, hexagonal adapters consuming horizontal services |
| [AGENT_UI_ADAPTER_PLAN_V1.1.md](adapter/AGENT_UI_ADAPTER_PLAN_V1.1.md) | Design rationale and edit lineage (v0 -> v1 -> v1.1) for the implementation spec |

### Sprint / process

| Plan | Purpose |
|------|---------|
| [SPRINT_PHASE4_PLAN.md](sprint/SPRINT_PHASE4_PLAN.md) | Phase 4 sprint: meta-optimization, drift detection, CodeReviewer agent, LangGraph feasibility gate |

## Conventions

- **Pyramid Principle structure**: most plans follow [research/pyramid_react_system_prompt.md](../../research/pyramid_react_system_prompt.md) (governing thought, MECE issue tree, evidence, validation log, gap analysis).
- **Plan lineage**: when a plan supersedes another, the new file declares `Supersedes: <old_file>` near the top. Old plans remain as audit trail.
- **Cross-references**: plans link to each other and to repo-root files using relative paths from this directory (e.g., `../../AGENTS.md`, `../../../services/foo.py`).
- **System-wide plans stay at repo root**: [PLAN.md](../../PLAN.md), [PLAN_v2.md](../../PLAN_v2.md). They describe the whole system rather than a single layer.

## Adding a new plan

1. Pick the layer it targets (trust, frontend, adapter, sprint, or system-wide).
2. Place it in the matching subfolder, or at repo root for system-wide plans.
3. Add a row to the relevant table above.
4. If it supersedes an existing plan, declare so in the new file's header and keep the old one as audit trail.
