---
type: plan
name: GCP deploy change detection
overview: Add branch-vs-main change detection (advisory/preview only) and a hybrid CalVer+SHA deploy naming scheme to the deploy-gcp skill and orchestrator, then document both in the skill guide.
todos:
  - id: detect-changes
    content: Add BASE_REF env + detect_changes() (merge-base three-dot diff, path->phase map with forward-dependency expansion, fail-safe to all-phases) to scripts/deploy_gcp.sh
    status: completed
  - id: preview-phase
    content: Add read-only preview phase that prints base ref, changed files, affected phases, and image rebuild flags; wire into run_phase/main but NOT run_all
    status: completed
  - id: deploy-identity
    content: Add compute_deploy_identity() producing hybrid CalVer+SHA DEPLOY_VERSION/SHORT_SHA/DEPLOY_ID with VERSION backward-compat
    status: completed
  - id: images-multitag
    content: Update phase_images() to multi-tag build (:DEPLOY_VERSION and :sha-SHORT_SHA), keep digest pin, print DEPLOY_ID
    status: completed
  - id: recipe-09
    content: "Create docs/recipes/gcp/09_change_detection.md — numbered recipe with story narration, lessons, mermaid diagrams, and usage walkthrough"
    status: completed
  - id: docs-guide
    content: "Add 'Change Detection and Deploy Naming' section to SKILL_DEPLOY_GUIDE.md with path->phase table, preview contract, naming convention, single-module caveat; cross-link to recipe 09"
    status: completed
  - id: docs-skill
    content: "Update SKILL.md and reference.md: add preview phase and BASE_REF/DEPLOY_VERSION/ENV env contract; link recipe 09"
    status: completed
  - id: verify
    content: Run bash -n, preview phase, and DRY_RUN=1 images to verify (no mutations)
    status: completed
isProject: false
---

# GCP Deploy: Change Detection + Hybrid Naming

## Decisions locked
- Version scheme: Hybrid CalVer + short SHA (e.g. `2026.05.0-abc1234`). Immutable `@sha256` digest still does runtime pinning.
- Diff scope: preview/advisory only. Diff never auto-skips a phase; the operator still names phases explicitly. Any phase that runs still executes the full gate.

## Key constraint
`infra/gcp/` is a single flat root module (all `.tf` files share one state, e.g. [foundations.tf](infra/gcp/foundations.tf), [cloud-run-backend.tf](infra/gcp/cloud-run-backend.tf)). So `tofu plan` remains the source of truth at the infra layer. The diff layer is an orchestration-level optimization/labeling aid (mainly: which phases are relevant, and whether to rebuild backend vs frontend images). This caveat is documented, not engineered around.

## 1. Change detection in `scripts/deploy_gcp.sh`
- Add `BASE_REF` env (default `origin/main`) to the flags block near [scripts/deploy_gcp.sh:23](scripts/deploy_gcp.sh).
- Add `detect_changes()` helper:
  - Resolve base: `git rev-parse --verify "$BASE_REF"`; if missing, `git fetch origin main` once; if still shallow/unavailable, `warn` and treat as "all phases affected" (fail-safe).
  - Diff via merge-base three-dot: `git diff --name-only "${BASE_REF}...HEAD"`.
  - Map changed paths to affected phases + per-image rebuild flags using the table below, with forward-dependency expansion.
- Add a `preview` phase (and accept it in `run_phase`/`main` at [scripts/deploy_gcp.sh:395](scripts/deploy_gcp.sh) and [scripts/deploy_gcp.sh:445](scripts/deploy_gcp.sh)) that prints: base ref, changed files, affected phases (in canonical order), and which images would rebuild. Read-only; no plan/apply.
- `preview` is NOT added to `run_all()` ([scripts/deploy_gcp.sh:415](scripts/deploy_gcp.sh)); it is an explicit, separate command so default behavior is unchanged.

Path -> phase / image map:
- `infra/gcp/foundations.tf`, `secret-manager.tf` -> foundations, secrets
- `infra/gcp/data.tf` -> data
- `infra/gcp/cloud-run-backend.tf` -> backend
- `infra/gcp/cloud-run-frontend.tf` -> frontend
- `infra/gcp/observability.tf`, `meta.tf` -> observability
- `infra/gcp/{variables,outputs,versions,backend}.tf`, `terraform.tfvars` -> all infra phases (shared)
- `Dockerfile.backend` + backend app code -> images (rebuild backend) + backend
- `Dockerfile.frontend` + `frontend/**` -> images (rebuild frontend) + frontend

## 2. Hybrid deploy naming in `scripts/deploy_gcp.sh`
- Add `compute_deploy_identity()`:
  - `DEPLOY_VERSION` default = CalVer `YYYY.0M.<patch>` (patch defaults `0`); overridable via env.
  - `SHORT_SHA` = `git rev-parse --short HEAD`.
  - `DEPLOY_ID` = `tierA-${ENV:-prod}-${DEPLOY_VERSION}-${SHORT_SHA}`.
  - Backward compat: existing `VERSION` ([scripts/deploy_gcp.sh:26](scripts/deploy_gcp.sh)) still works; if unset, derive `VERSION=${DEPLOY_VERSION}`.
- Update `phase_images()` ([scripts/deploy_gcp.sh:274](scripts/deploy_gcp.sh)) to multi-tag at build: push both `:${DEPLOY_VERSION}` and `:sha-${SHORT_SHA}` for backend and frontend, then resolve and pin the `@sha256` digest into `terraform.tfvars` exactly as today (`WRITE_TFVARS=1`).
- Print the `DEPLOY_ID` in the `images` and `smoke` phase output for traceability.
- Optional (flagged as stretch): stamp Cloud Run revision labels (`version`, `commit`, `deploy-id`). This requires a new `labels` variable + wiring in [cloud-run-backend.tf](infra/gcp/cloud-run-backend.tf) / [cloud-run-frontend.tf](infra/gcp/cloud-run-frontend.tf) / [variables.tf](infra/gcp/variables.tf). Left out of the core change unless you want it now.

## 3. Recipe 09 — new narrative doc

Create `docs/recipes/gcp/09_change_detection.md` following the established recipe structure:

- **Goal + Status header** (same format as `01_foundations.md`)
- **Before We Start: A Story** — narrative continuing from Recipe 8. The pilot has been flying manually, sometimes rebuilding both images when only one file changed, sometimes unsure "what does this branch actually touch?" The story introduces the `preview` command as the co-pilot's pre-flight briefing.
- **Mermaid diagram** showing the `preview` → operator decision → selective phase run flow.
- **Three lessons** (following the lesson-per-concern pattern):
  - Lesson 1 — The Blind Rebuild Problem: why `images` rebuilt both containers every time; what the merge-base diff fixes; the three-dot `origin/main...HEAD` contract.
  - Lesson 2 — The Path-to-Phase Map: explain the path→phase table (shared files fan out to all phases, app code targets the matching image+phase); cover the forward-dependency expansion rule and the single-root-module caveat (tofu plan is still the source of truth).
  - Lesson 3 — The Deploy ID: explain the hybrid CalVer+SHA identity (`DEPLOY_VERSION`, `SHORT_SHA`, `DEPLOY_ID = tierA-prod-2026.05.0-abc1234`); the multi-tag build (`:DEPLOY_VERSION` + `:sha-SHORT_SHA` + `@sha256` digest pin); why three layers serve three audiences (human readability, commit traceability, runtime immutability).
- **Usage walkthrough** with actual commands:
  ```bash
  ./scripts/deploy_gcp.sh preview            # see what this branch touches
  VERSION=2026.05.0 WRITE_TFVARS=1 ./scripts/deploy_gcp.sh images
  ./scripts/deploy_gcp.sh backend            # only if backend changed
  ```
- **For a general audience** — how to adapt to other stacks (swap path map, keep the three-dot diff and the three-layer naming convention).
- **Cross-references** back to `SKILL_DEPLOY_GUIDE.md` and `03_containerize.md`.

## 4. Documentation updates
- [docs/recipes/gcp/SKILL_DEPLOY_GUIDE.md](docs/recipes/gcp/SKILL_DEPLOY_GUIDE.md): new section "Change Detection and Deploy Naming" covering the merge-base diff, the path->phase table, the preview-only contract, and the hybrid naming convention; note the single-root-module caveat; link to Recipe 09.
- [.cursor/skills/deploy-gcp/SKILL.md](.cursor/skills/deploy-gcp/SKILL.md): add `preview` to valid phases, document `BASE_REF`, `DEPLOY_VERSION`, `ENV` flags under Common Flags; link recipe 09.
- [.cursor/skills/deploy-gcp/reference.md](.cursor/skills/deploy-gcp/reference.md): extend environment contract section with new vars and the preview phase; add Recipe 09 to Phase-to-Recipe Map.

## 4. Verify (read-only / dry-run)
- `bash -n scripts/deploy_gcp.sh`
- `./scripts/deploy_gcp.sh preview` (prints affected phases vs `origin/main`, no mutations)
- `DRY_RUN=1 ./scripts/deploy_gcp.sh images` (shows multi-tag build + `DEPLOY_ID`, no push)

## Out of scope (flag for later)
- Splitting `infra/gcp` into per-phase modules/workspaces for true state-level isolation.
- Auto-skip mode (`CHANGED_ONLY=1`) — explicitly deferred per the preview-only decision.
