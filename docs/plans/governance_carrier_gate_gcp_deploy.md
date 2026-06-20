---
type: plan
title: 'Carrier-gate — GCP deploy guide & required config'
description: 'Status: deploy guide — 2026-06-17.'
tags: [plan]
---

# Carrier-gate — GCP deploy guide & required config

**Status:** deploy guide — **2026-06-17**. Companion to the [`deploy-gcp` skill](../../.cursor/skills/deploy-gcp/SKILL.md); this is the **change-specific** layer (what the carrier-gate work needs from GCP), not a re-doc of the phased workflow.
**Covers:** the three deploy postures for the governance carrier gate — **(A) shadow** (default, ships now), **(B) prod enforce** (degrade), **(C) fault-injection validation** (the live gap-catch proof, on a throwaway tagged revision). Each names the *exact* config and which gate order applies.

---

## 0. The one thing to know first

The carrier gate's runtime behavior is controlled by **two env flags**, both **default-OFF**, read by `middleware/composition.py` into `AgentConfig`:

| Env var | → AgentConfig field | Default | Effect when set |
|---------|---------------------|---------|-----------------|
| `CARRIER_GATE_ENFORCE_ENABLED` | `carrier_gate_enforce_mode` (derived) | unset → `"off"` | `1` + prod (`GCP_EXECUTION_ENV=cloudrun`) → `degrade`; `1` + local → `raise` |
| `CARRIER_GATE_FAULT_INJECT` | `carrier_gate_fault_inject` | unset → `false` | `1` → the `__DROP_CARRIER:<phase>__` prompt token suppresses a carrier (**validation only — NEVER prod**) |

**Neither flag is in `infra/gcp/cloud-run-backend.tf` today.** Exactly like the tiered-loops flags (deploy-gcp skill §Tiered-Loops), a plain `backend` apply will **not** set them. This is the load-bearing fact:

- **Posture A (shadow)** needs **no config change** — the gate is unconditional code; the flags stay unset → `off`. A normal `backend` apply ships it.
- **Posture B (prod enforce)** needs the enforce flag added to Terraform (gated) **or** an out-of-band revision.
- **Posture C (fault-injection)** is a throwaway tagged revision, never touches managed infra.

> **Mode derivation is automatic.** The prod backend already sets `GCP_EXECUTION_ENV=cloudrun` (`cloud-run-backend.tf:90`), which `composition.py` resolves to `agent_env="prod"`. So `CARRIER_GATE_ENFORCE_ENABLED=1` on the prod revision derives **`degrade`** (loud trace, never blocks) — you do **not** set the mode directly, only the enable flag.

---

## Posture A — Shadow (DEFAULT, ships now, zero config change)

This is what's deployed today and what the e2e validation ran against (CLEAN, gap-rate 0.000). The gate records `source:"carrier_gate"` carriers at every wired phase; nothing blocks.

```bash
# Nothing flag-related to set. Ship the new image through the normal phase:
./scripts/deploy_gcp.sh backend
# (then frontend if the FE changed — the carrier-gate change is backend-only)
```

- **Gate order:** the standard phased apply (`tofu plan → tofu show → conftest → terraform-compliance → tofu apply`). Since **no `infra/` file changes for Posture A**, the plan/policy steps are no-ops for these edits — they pass clean.
- **Required secrets:** none new. Langfuse keys (the relay sink) are **already** in `cloud-run-backend.tf` (`LANGFUSE_HOST` :152, `LANGFUSE_PUBLIC_KEY` :194, `LANGFUSE_SECRET_KEY` :204).
- **Verify:** run the e2e carrier-gate spec against the prod frontend (`TEST_PROFILE=prod`) and the analyzer (`--carrier-gate`); expect full coverage, 0 alerts. See [`governance_carrier_gate_e2e_report.md`](governance_carrier_gate_e2e_report.md) §1.

---

## Posture B — Prod enforce (degrade) — GATED, evidence-required

Only after: Phase-1 shadow false-positive rate ≈ 0 over N runs **+** a successful Posture-C fault-injection run **+** explicit approval. Two paths (same choice the tiered-loops flags face):

### B.1 — Terraform promotion (the right way for a lasting prod flip)
Add **one** env block to `cloud-run-backend.tf`, mirroring the `GOAL_JUDGE_ENABLED` block (`:136-139`) verbatim in shape:

```hcl
# Governance carrier-gate enforcement (Phase 2). Prod (GCP_EXECUTION_ENV=cloudrun)
# derives "degrade": a missing-pillar gap is annotated loudly on the trace, the run
# never blocks. Promoted on Phase-1 calibration evidence + the fault-injection proof.
env {
  name  = "CARRIER_GATE_ENFORCE_ENABLED"
  value = "true"
}
# CARRIER_GATE_FAULT_INJECT is deliberately ABSENT — fault injection must NEVER
# run on prod traffic (it suppresses real carriers). It lives only on the throwaway
# Posture-C tagged revision.
```

Then run the **full gate order** and the `backend` phase:

```bash
./scripts/deploy_gcp.sh preview        # advisory: confirms cloud-run-backend.tf is the only change
./scripts/deploy_gcp.sh backend        # runs tofu plan → conftest → terraform-compliance → apply
```

- This is a **real managed-infra change**, so the policy gates run for real — do not skip them.
- **Reversible:** remove the env block + re-apply, or roll back the revision.

### B.2 — Out-of-band tagged revision (faster, for a bounded prod-enforce trial)
If you want enforce on a *fraction* of prod or a time-boxed trial without a Terraform change, use a tagged revision off the live image (prod traffic untouched):

```bash
IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-backend-combined --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')

gcloud run services update agent-backend-combined --region us-central1 \
  --image "$IMG" --tag enforce --no-traffic \
  --update-env-vars CARRIER_GATE_ENFORCE_ENABLED=1
# Tagged URL: https://enforce---agent-backend-combined-<hash>-uc.a.run.app
```
Bypasses the OpenTofu/policy workflow only because it mutates no managed infra (no traffic, throwaway). **Never** flip `CARRIER_GATE_ENFORCE_ENABLED` on the prod-traffic revision as a shortcut — that's a silent prod behavior change with no policy gate.

---

## Posture C — Fault-injection validation (the live gap-catch proof)

A **throwaway, zero-traffic** tagged revision with **both** flags ON, to watch the alarm ring end-to-end. Prod stays untouched. This is the run that justifies Posture B.

```bash
IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-backend-combined --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')

# Both flags ON. enforce derives "degrade" (prod env) so the run still completes;
# fault-inject arms the __DROP_CARRIER__ token.
gcloud run services update agent-backend-combined --region us-central1 \
  --image "$IMG" --tag cgfault --no-traffic \
  --update-env-vars CARRIER_GATE_ENFORCE_ENABLED=1,CARRIER_GATE_FAULT_INJECT=1

# Point a matching zero-traffic FRONTEND tag at the cgfault backend (the FE reaches
# the backend via MIDDLEWARE_URL — same bridge the stress revision uses):
FE_IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-frontend --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')
gcloud run services update agent-frontend --region us-central1 \
  --image "$FE_IMG" --tag cgfault --no-traffic \
  --update-env-vars MIDDLEWARE_URL=https://cgfault---agent-backend-combined-<hash>-uc.a.run.app
```

Then drive a prompt carrying the token and analyze:

```bash
BASE_URL=https://cgfault---agent-frontend-<hash>-uc.a.run.app E2E_AUTHENTICATED=1 \
  CARRIER_CASE_FILTER=GJ-STRESS-901 \
  pnpm exec playwright test e2e/full-stack/carrier-gate.spec.ts --project=chromium-desktop
# (use a prompt containing __DROP_CARRIER:initialization__ — add a fault case to the
#  spec, or pass it inline; the token only fires because the revision has the flag)

python scripts/analyze_planning_traces.py --source langfuse --carrier-gate \
  --jsonl cache/carrier_gate/ui_batch.jsonl
#   → expect: total alerts ≥ 1 AND the "ENFORCED ≥ 1 (Phase-2 acted: degrade)" line
```

**Tear down both tags afterward** (a fault-inject revision must not linger):
```bash
gcloud run services update-traffic agent-backend-combined --region us-central1 --remove-tags cgfault
gcloud run services update-traffic agent-frontend         --region us-central1 --remove-tags cgfault
```

---

## Config summary (what each posture touches)

| Posture | `infra/` change? | Policy gate runs? | Env set | Traffic risk |
|---------|------------------|-------------------|---------|--------------|
| **A shadow** (now) | none | n/a (no-op) | none | none |
| **B.1 prod enforce** (Terraform) | +1 env block in `cloud-run-backend.tf` | **yes — full order** | `CARRIER_GATE_ENFORCE_ENABLED=true` | prod (degrade only, never blocks) |
| **B.2 prod enforce** (tagged) | none | bypassed (no managed infra) | `CARRIER_GATE_ENFORCE_ENABLED=1` | zero (no-traffic tag) |
| **C fault-injection** (tagged) | none | bypassed | both flags `=1` | zero (no-traffic tag) |

---

## Safety rules (carrier-gate-specific, on top of the skill's)

- **`CARRIER_GATE_FAULT_INJECT` must NEVER reach a prod-traffic revision** — it suppresses real carriers (corrupts the trace). It belongs only on a throwaway `--tag cgfault --no-traffic` revision. Keep it **out** of `cloud-run-backend.tf` entirely (Posture B.1 adds only the enforce flag).
- **`degrade` is the only prod enforce mode** — derived automatically from `GCP_EXECUTION_ENV=cloudrun`. It annotates + continues; it never blocks a user run. `raise` is dev/CI only (it would fail prod requests — that is why prod derives degrade, not raise).
- **Calibration before flipping B** — Posture B is gated on the Posture-C proof + an N-run shadow FP≈0. Flipping enforce before the alarm is shown to ring (and not false-fire) is the "gating before calibration is theater" trap.
- Standard skill rules still apply: never commit `terraform.tfvars` or secrets; digest-pin images; `preflight` failures are hard blockers.

---

*Deploy guide. Posture A is the only one cleared to ship now; B is gated on the C proof + approval.*
