---
type: decision-record
title: 'ADR-0031: Retire the abandoned infra/dev-tier (Neon) OpenTofu stack'
status: accepted
created: 2026-07-14
updated: 2026-07-14
owner: rajnish.khatri
related: 0000-template.md
tags: [decision-record, infra, gcp, g8]
---

# ADR-0031: Retire the abandoned infra/dev-tier (Neon) OpenTofu stack

**Status:** Accepted — 2026-07-14.
**Related:** [AGENTS.md](../../AGENTS.md) §"Boundaries" (⚠️ Ask first — infra topology change) and §G8 (test-mass-rewrite gate); [scripts/deploy_piece_c.sh](../../scripts/deploy_piece_c.sh) (the in-repo warning that already documents dev-tier as abandoned); commit `8888949` ("close Sprints 0-4 V3-Dev-Tier rollout") — the stack's last substantive change.
**Audience:** Anyone who might run `tofu apply` against a dev-tier stack, resurrect Neon as the dev substrate, or wonder where the `agent-middleware` Cloud Run service came from.

---

## Context

A prior session decommissioned an **orphan Cloud Run service**, `agent-middleware`, in GCP project `agent-prod-gcp-dev` (region `us-central1`). It ran the `us-docker.pkg.dev/cloudrun/container/hello` placeholder image, served nothing real, and was referenced by no live service or repo config. It was deleted out-of-band with `gcloud run services delete agent-middleware`. The live topology is now exactly the two services `infra/gcp/*.tf` declares: `agent-backend-combined` and `agent-frontend`.

But the orphan was **not** created by `infra/gcp/`. It was created by a separate, abandoned OpenTofu stack at `infra/dev-tier/` — the Neon free-tier "V3 dev-tier" substrate (Cloud Run scale-to-zero + Neon free Postgres + Cloudflare Pages/Edge). That stack still declares the service in `infra/dev-tier/cloud-run.tf` (`resource "google_cloud_run_v2_service" "middleware"` named `agent-middleware`, plus a dedicated runtime SA `agent-middleware-runtime`). **Any `tofu apply` against the dev-tier stack would recreate the orphan we just deleted.** This ADR closes that resurrection path.

Evidence the stack is dead, not merely quiet:

- **Git history.** The last substantive dev-tier commit is `8888949` ("close Sprints 0-4 V3-Dev-Tier rollout") — a wrap-up. The only later touch, `3b89b4e` (2026-06-27), is a repo-wide ruff-baseline sweep, not dev-tier work. Every change since (WorkOS auth, PreAct parity epics A–F, pgvector memory cutover) targets `infra/gcp/` and the app.
- **In-repo docs already declare it abandoned.** `scripts/deploy_piece_c.sh:65-72` calls `agent-middleware` "an orphaned V3-dev-tier service on the `hello` placeholder" and the `neon-database-url` secret part of "the **abandoned** infra/dev-tier (Neon) stack"; its Terraform-apply step against dev-tier was already removed (`:88`). `frontend/lib/adapters/thread_store/pg_thread_repo.test.ts:127` calls Neon "the abandoned dev-tier stack."
- **Zero runtime coupling.** Nothing in `trust/`, `services/`, `components/`, `orchestration/`, or `middleware/` imports or invokes the stack. The `middleware/composition.py` "v3 = dev-tier" references are a **profile-name string**, not a dependency on the Terraform stack. The live backend reads `database-url` (Cloud SQL over a unix socket), never `neon-database-url`.
- **The `neon-database-url` secret is bleed.** In project `agent-prod-gcp-dev`, its only IAM grantee is the `agent-middleware-runtime` SA — the very SA this stack owns.

This is an ⚠️ Ask first / ADR trigger (infra topology change); `tests/architecture/test_adr_ratchet.py` enforces that an `infra/` change ships a new `docs/adr/*`.

---

## Decision

Retire the **entire** `infra/dev-tier/` OpenTofu stack. Concretely:

1. Delete the `infra/dev-tier/` directory (all `.tf`, `README.md`, `.tflint.hcl`, `terraform.tfvars.example`, `features/`, `policies/`).
2. Delete the four dev-tier-bound test files and the dev-tier root conftest/tfvars they use: `tests/infra/{test_cloud_run.py, test_neon.py, test_secret_manager.py, test_cross_cutting.py, conftest.py, test.tfvars}`. **Keep** `tests/infra/_hcl_helpers.py` and `tests/infra/__init__.py` — the live `tests/infra/gcp/` suite imports the helper.
3. Drop the now-orphaned `infra` pytest marker from `pyproject.toml` (markers list + `not infra` in `addopts`). The live gcp suite uses the separate `infra_gcp` marker; `norecursedirs = ["infra"]` still keeps the whole `tests/infra` tree out of the default `pytest` run. The `infra` optional-dependency extra (`python-hcl2`) stays — the gcp suite needs it.
4. Fix only the docs/config that present dev-tier as **live/current** (the code-reviewer path routing in `code_reviewer/frontend/runner.py` + `prompts/codeReviewer/frontend/*.j2`, and `infra/RUNBOOK.md` Stage A). Leave the ~30 historical narrative references (spike reports, sprint boards, plan logs) untouched — they are an accurate record of what happened.

The stale GCP resources (`neon-database-url` secret, `agent-middleware-runtime` SA) are **not** deleted by this change. The code/Terraform change alone closes the recreation path; the cloud cleanup is optional, outward-facing, and left to a deliberate `gcloud` run (commands recorded in the retirement session and the deletion checklist).

---

## Options considered & rejected

| Option | What it does | Why rejected |
|---|---|---|
| **(b) Minimal trim** | Keep the stack; remove only the `agent-middleware` `google_cloud_run_v2_service` + `agent-middleware-runtime` SA from `cloud-run.tf`; update the tests asserting they exist. | Leaves a half-alive Neon stack (`neon.tf`, `secret-manager.tf`) provisioning a database the live backend never reads, and `test_neon.py` asserting a Neon DB that doesn't exist. Preserves the exact "migrate Neon, run against Cloud SQL" confusion that `deploy_piece_c.sh` spends 20 lines warning about. Trimming one resource out of an abandoned stack is *more* dead code left to rot than deleting the stack. |
| **Keep as-is + a warning comment** | Add a "do not apply" banner to `cloud-run.tf`. | A comment is not an enforcement. The `tofu apply` resurrection path stays open; `tests/infra` keeps asserting the orphan must exist. |
| **Delete the GCP secret + SA in this change** | Also `gcloud` -delete the stale `neon-database-url` secret and `agent-middleware-runtime` SA. | Outward-facing and irreversible; belongs to a deliberate, separately-confirmed step, not bundled into a repo diff. Kept as follow-on work. |

---

## Rationale

Option (a) wins because the stack is genuinely dead (git history + the repo's own warnings) and its blast radius is clean and bounded. Deleting the whole stack removes the resurrection path *and* the standing confusion in one move, where (b) would preserve both. The one real constraint — the live gcp test suite borrows `tests/infra/_hcl_helpers.py` — is honored by keeping the helper and `__init__.py`, so `pytest tests/infra/ -m infra_gcp` stays green (131 passed, 1 skipped) after removal.

---

## Consequences

- **Removes 32 `infra`-marked tests** (all dev-tier: `test_cloud_run.py`/`test_neon.py`/`test_secret_manager.py`/`test_cross_cutting.py`). Per **G8**, these are deleted because the resource they assert is *intentionally* gone — not because the assertions were weak. The justification token for `tests/architecture/test_no_test_weakening.py` lives in the deletion commit message.
- **The dev-tier substrate is no longer expressible as IaC.** If the free-tier Neon path is ever wanted again, it is re-created from git history + this ADR, deliberately — not resurrected by an accidental `apply`. That is the intended cost.
- **Live gcp stack untouched.** `infra/gcp/`, `tests/infra/gcp/`, `tests/infra/_hcl_helpers.py`, and the `infra` dependency extra all survive; the `infra_gcp` suite is the surviving IaC gate.
- **Outstanding cloud cleanup (out of scope here).** The `neon-database-url` secret and `agent-middleware-runtime` SA in `agent-prod-gcp-dev` remain until a deliberate `gcloud` delete. Until then they are inert bleed (the secret's only grantee is the SA; nothing reads either).

---

## Supersedes / related

- Closes the resurrection path for the orphan removed in the prior decommission session; complements the in-repo warning in [scripts/deploy_piece_c.sh](../../scripts/deploy_piece_c.sh).
- The live topology is canonically declared by [infra/gcp/](../../infra/gcp/) (`agent-backend-combined`, `agent-frontend`) and gated by `tests/infra/gcp/` (`-m infra_gcp`).
- Related gate: [AGENTS.md](../../AGENTS.md) §G8; the deletion carries the required justification token.
