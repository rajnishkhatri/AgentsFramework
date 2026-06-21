---
type: plan
name: Cloud Cost Comparison Pyramids
overview: Produce a Pyramid-Analysis-style planning artifact comparing AWS / GCP / Azure for the backend in `BACKEND_SOLUTION_ARCHITECTURE.md` across three workload tiers (dev / small-prod / scale-prod), then project a single derivative decision doc `CLOUD_PROVIDER_COMPARISON.md` with per-tier recommendations and a default winner — following the four-phase loop and eight self-validation checks from `docs/analysis/PYRAMID_ANALYSIS.md`.
todos:
  - id: draft_pyramid_a
    content: "Draft Pyramid A (Dev / free-tier): Problem Definition, Issue Tree (4 branches), Hypotheses with thresholds, Evidence table with pricing-page citations, Gaps, Cross-branch, Synthesis, Validation log (8 checks)"
    status: pending
  - id: draft_pyramid_b
    content: "Draft Pyramid B (Small production): same eight subsections, with always-on min-1 cost assumptions explicit"
    status: pending
  - id: draft_pyramid_c
    content: "Draft Pyramid C (Scale production): same eight subsections, with multi-region + HA Postgres + min-5 instances and egress as first-class line items"
    status: pending
  - id: cross_pyramid
    content: Cross-pyramid interactions section comparing the three tier winners and naming the cost component that flips between adjacent tiers
    status: pending
  - id: framing_notes
    content: "Framing-notes appendix: SCQA diagnostic + CQSA ordering choice for the derivative doc + six anti-pattern clearances"
    status: pending
  - id: derivative_doc
    content: "Create `docs/Architectures/CLOUD_PROVIDER_COMPARISON.md` projecting the three pyramids: governing thought, per-tier recommendation table, per-tier cost models, lock-in summary, decision flowchart, open questions"
    status: pending
  - id: readme_update
    content: Add the new comparison doc to `docs/Architectures/README.md` with a one-paragraph summary in the same style as the existing entries
    status: pending
  - id: self_review
    content: Run the validation checklist (§9 of the plan) over both new docs and fix any failures before declaring done
    status: pending
isProject: false
---

# Cloud Provider Comparison — Pyramid-Analysis Plan

## 1. Method (anchored in `docs/analysis/PYRAMID_ANALYSIS.md`)

We mirror the planning file's structure exactly: **three pyramids** (one per workload tier), each running the four-phase loop (Decompose → Hypothesize → Act → Synthesize) and each closing with the **eight self-validation checks** (`completeness`, `non_overlap`, `item_placement`, `so_what`, `vertical_logic`, `remove_one`, `never_one`, `mathematical`). All three pyramids project into **one** derivative doc, framed via a per-doc SCQA appendix that lives only in the planning file.

## 2. Files

- **New planning artifact (this work's primary output):** `docs/analysis/CLOUD_COMPARISON_PYRAMID_ANALYSIS.md` — three pyramids + cross-pyramid table + framing-notes appendix. Mirrors `docs/analysis/PYRAMID_ANALYSIS.md` 1:1 in structure.
- **New derivative doc (single combined recommendation):** `docs/Architectures/CLOUD_PROVIDER_COMPARISON.md` — per-tier recommendation + default winner + per-tier cost model + lock-in/portability summary.
- **Update:** `docs/Architectures/README.md` — add an entry for the new comparison doc next to the three per-cloud architectures.
- **Inputs (read-only):** `docs/Architectures/AWS_DEPLOYMENT_ARCHITECTURE.md`, `docs/Architectures/GCP_DEPLOYMENT_ARCHITECTURE.md`, `docs/Architectures/AZURE_DEPLOYMENT_ARCHITECTURE.md`, `docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md` §5.5 (persistence/cache) and §3.3 (rings).

## 3. Workload assumptions (documented explicitly in each pyramid's §X.1 Problem Definition and §X.5 Gaps)

Three tiers, each anchored to concrete numbers so cost claims are falsifiable. **Numbers below are the proposed defaults; they will be cited verbatim in the Problem Definition of each pyramid and flagged as `assumption — not measured against live workload` in `missing_data` gaps.**

- **Tier A — Dev / free-tier (mirrors `FRONTEND_PLAN_V3_DEV_TIER` posture):** ~5 internal devs, < 20 SSE sessions/day, ~500 LLM calls/month, ~1 GB traces/month, single region, 1 small Postgres (~10 GB), object storage < 5 GB, **idle cost dominates** (compute may be scale-to-zero acceptable).
- **Tier B — Small production:** ~10–20 concurrent SSE peak, ~50k LLM calls/month, ~50 GB traces/month, single region multi-AZ DB, Postgres ~50 GB, object storage ~200 GB with 90-day retention, **always-on min 1 instance per service** (cold-start breaks SSE UX).
- **Tier C — Scale production:** ~200 concurrent SSE peak, ~2M LLM calls/month, ~1 TB traces/month, multi-region (active-passive), Postgres ~500 GB HA cluster, object storage ~5 TB (90-day hot + archive tier), **min instances ≥ 5 per service**, autoscale ceiling explicit.

## 4. Pyramid skeleton (applied identically to Tier A, B, C)

For each tier we produce one pyramid with:

- **§X.1 Problem definition:** `original_statement`, `restated_question`, `problem_type = decision`, explicit `scope_boundaries` (in/out), `success_criteria` (a measurable monthly-cost band + an SSE-timeout / availability bar).
- **§X.2 Issue tree** — four branches, ordering = **decision** (cost first, then non-cost tiebreakers):
  - `branch_1 — Compute cost`: long-running BFF + Backend FastAPI with SSE, per-tier idle/active mix. ECS Fargate vs Cloud Run vs Azure Container Apps; Frontend on Amplify vs Cloud Run vs Static Web Apps / ACA.
  - `branch_2 — Data plane cost`: managed Postgres (RDS / Cloud SQL / Azure DB for PG Flexible), object storage (S3 / GCS / Blob), NFS for `cache/.agent_offload/` and `cache/.agent_plans/` (EFS / Filestore / Azure Files), streaming sink (Kinesis Firehose / Pub/Sub / Event Hubs).
  - `branch_3 — Network + observability cost`: inter-AZ + egress + LB hours, secrets pricing (Secrets Manager / Secret Manager / Key Vault), logs (CloudWatch / Cloud Logging / Log Analytics).
  - `branch_4 — Non-cost tiebreakers`: SSE timeout headroom (ALB 4000 s vs Cloud Run / HTTPS LB extended timeout vs AFD/AppGW), free-tier / startup credits, portability / lock-in risk against `BACKEND_SOLUTION_ARCHITECTURE.md` invariant I-9 (SDK isolation).
- **§X.3 Hypotheses with confirm/kill thresholds** — one row per branch, each with a numeric threshold (e.g. "confirm if compute monthly ≤ $X for the tier's assumed always-on hours").
- **§X.4 Evidence** — every row cites a source: a public-pricing-page URL **or** the corresponding line in the per-cloud architecture doc (e.g. `AWS_DEPLOYMENT_ARCHITECTURE.md:43` for the ALB 4000 s claim). Confidence column required.
- **§X.5 Gaps** — three categories: `untested_hypotheses`, `missing_data` (e.g. live workload, custom discounts, enterprise agreements), `known_weakness` (list-price-only, no Reserved Instances / CUDs / Savings Plans modeled).
- **§X.6 Cross-branch interactions** — at minimum: compute × egress (Cloud Run / Fargate scale-out fan-out cost), data × egress (cross-AZ NFS reads), tiebreakers × cost (free credits may flip the ranking at Tier A but not Tier C).
- **§X.7 Synthesis** — `governing_thought` is the tier's winner and the margin; 4 inductive arguments, one per branch; at least 2 worked so-what chains.
- **§X.8 Validation log** — all eight checks recorded explicitly. `mathematical` is **applicable** here (unlike `PYRAMID_ANALYSIS.md` where it was `not_applicable`): we verify total monthly cost = compute + data + network + observability + secrets, rounded consistently, and that any "X% cheaper" claim matches the underlying line items.

## 5. Cross-pyramid section

A table mirroring `PYRAMID_ANALYSIS.md` §Cross-pyramid interactions:

- Tier-A winner vs Tier-B winner — do the rankings agree? If not, name the cost component that flipped (likely idle compute on always-on minimums).
- Tier-B winner vs Tier-C winner — do they agree? Identify whether multi-region replication tilts the result.
- A single "default winner" recommendation when the user has not yet committed to a tier (defensible because Tiers A→C cover the lifecycle).

## 6. Framing-notes appendix (internal-only, per `PYRAMID_ANALYSIS.md` §F)

One SCQA framing block for the single derivative doc `CLOUD_PROVIDER_COMPARISON.md`. Per the diagnostic:

- **Audience profile:** architect / FinOps / engineering lead. Trust = neutral-to-skeptical, problem-aware (already knows they need a cloud), mode = decision-maker.
- **Selected ordering:** **CQSA (Tension-Inquiry)** — open with the "all three architectures look identical, so unit cost decides" complication, then the question ("which one wins for our tier?"), then the situation (the workload-tier matrix), then the answer (per-tier table + default winner). Same justification family as the Developer Guide framing in `PYRAMID_ANALYSIS.md` §F.2.
- The six SCQA anti-pattern clearances will be recorded explicitly.

## 7. Derivative doc shape (`docs/Architectures/CLOUD_PROVIDER_COMPARISON.md`)

Projected from the three pyramids, **never citing SCQA terminology**:

1. **Governing thought** — one paragraph: which provider is the cost-effective default for this backend, and at what tier(s) that recommendation holds.
2. **Per-tier recommendation table** — rows = Tier A / B / C, columns = recommended provider, monthly cost band, key reason, key risk.
3. **Per-tier cost model** — three subsections (one per tier) showing the compute + data + network + observability + secrets line items for each of the three providers, with totals.
4. **Lock-in & portability summary** — short table mapping the four code refactors from each per-cloud architecture's §6 ("Required Code Refactoring") against `BACKEND_SOLUTION_ARCHITECTURE.md` invariant I-9 (SDK isolation in `adapters/runtime/`).
5. **Decision criteria flowchart** — small mermaid: "pick a tier → check non-cost gates (SSE timeout, free credits, existing org cloud commit) → recommendation".
6. **Open questions** — surfaced from the `missing_data` gaps in the pyramids (e.g. "needs validation against live workload", "Reserved Instances / CUDs / Savings Plans not modeled").

## 8. Data-sourcing posture (recorded in §X.5 Gaps and §X.4 Evidence of each pyramid)

- **List-price only.** All cost numbers come from each provider's public pricing pages, cited per row. Reserved Instances / CUDs / Savings Plans / Enterprise Agreement discounts are **out of scope** and flagged as `known_weakness`.
- **No live web fetch is performed during pyramid drafting.** Numbers will be drafted as placeholder formulas with units (e.g. `vCPU-hour × $/vCPU-hour × hours/month`) and the pricing-page URL cited; if you want the final dollar numbers filled in, that becomes a separate (still read-only) pass with web fetches once you approve the plan.
- **Egress is modeled explicitly per tier.** Cross-AZ and cross-region egress are first-class line items (`branch_3`) because they are the single most common cost surprise in containerized SSE workloads.

## 9. Validation checklist before completion

For each of the three pyramids:

- [ ] All 8 validation checks recorded with `pass` / `pass with note` / `not_applicable` and a one-line justification.
- [ ] Every "Never" / "must" claim in the synthesis has at least one evidence row.
- [ ] No branch has exactly one child (the `never_one` check).
- [ ] Cost arithmetic is consistent across §X.4 evidence and §X.7 synthesis (the `mathematical` check).

For the derivative doc:

- [ ] Recommendation paragraph matches each tier's `governing_thought` verbatim where they agree, or explicitly names the disagreement where they don't.
- [ ] No SCQA terminology leaks out of the framing-notes appendix.
- [ ] `docs/Architectures/README.md` updated with one entry pointing at the new comparison doc.
