# T3 Fan-out — GCP Stress Deploy Runbook (Stage B)

> **You run this.** Step-by-step deploy + live-validation for T3 (Phase 4), the
> on-demand half the offline Stage A cannot cover. Grounded against the LIVE
> environment on 2026-06-15 (service names, project, registry, image refs all
> read from `gcloud`, not assumed). Executes **Stage B** of
> [`t3_implementation_and_validation.plan.md`](t3_implementation_and_validation.plan.md) §3.
>
> **Authorities:** deploy-gcp skill ("Tiered-Loops Stress Revision"),
> playwright-agentic-e2e skill, [`infra/RUNBOOK.md`](../../infra/RUNBOOK.md) §1.2.

---

## 0. Live facts (verified 2026-06-15)

| Thing | Value |
|---|---|
| Project | `agent-prod-gcp-dev` |
| Region | `us-central1` |
| Backend service | `agent-backend-combined` (Dockerfile: `Dockerfile.backend`) |
| Frontend service | `agent-frontend` (Dockerfile: `frontend/Dockerfile.frontend`) |
| Artifact Registry | `us-central1-docker.pkg.dev/agent-prod-gcp-dev/agent-backend` |
| Corpus | `frontend/e2e/fixtures/planning_stress_corpus.json` (29 `phase="fanout"` rows) — already on main |
| Stress profile | `frontend/e2e/testing.profiles.yml` (`stress:` block; URL auto-filled in B3) |

```bash
export PROJECT=agent-prod-gcp-dev
export REGION=us-central1
export REPO=us-central1-docker.pkg.dev/$PROJECT/agent-backend
export TAG=t3-stress-$(date +%Y%m%d)
gcloud config set project $PROJECT
```

---

## ⚠️ The one deviation from the deploy-gcp skill

The skill's recipe **reuses the live prod image digest** and only flips env vars.
That works for the Step-0 loop flags because they were already compiled into the
prod image. **It does NOT work for T3** — the fan-out code lives on the
`feat/t3-supervisor-fanout` branch and is **not in the prod image**. Setting
`T3_FANOUT_ENABLED=1` on the prod binary would be a silent no-op (no fan-out
fork to enable).

**So Step 1 below BUILDS a new image from this branch first**, then tags *that*
image `stress`. Everything after Step 1 follows the skill verbatim.

> **Prod safety:** every `gcloud run ... update` here uses `--tag stress
> --no-traffic`. Prod traffic is never touched. Teardown (Step 6) is mandatory.

---

## 1. Build & push the T3 image (the extra step the skill omits)

```bash
# Be on the T3 branch with a clean tree.
git checkout feat/t3-supervisor-fanout
git status   # expect clean (Stage A committed)

# Auth Docker to Artifact Registry (once per machine).
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build the backend image from this branch (linux/amd64 — Cloud Run is amd64;
# on Apple Silicon you MUST pass --platform or the container won't boot).
docker build --platform linux/amd64 -f Dockerfile.backend \
  -t $REPO/agent-backend:$TAG .
docker push $REPO/agent-backend:$TAG
```

> The frontend image does **not** change for T3 (no frontend code touched). The
> frontend stress revision in Step 3 reuses the live frontend digest and only
> repoints `MIDDLEWARE_URL` — exactly as the skill describes.

---

## 2. Backend stress revision (loops-on + T3-on + fault-inject)

```bash
gcloud run services update agent-backend-combined --region $REGION \
  --image "$REPO/agent-backend:$TAG" \
  --tag stress --no-traffic \
  --update-env-vars \
REFLEXION_ENABLED=1,PLANNING_PLAN_SOURCE=generated,MAX_REFLEXION_ATTEMPTS=2,T3_FANOUT_ENABLED=1,FANOUT_FAULT_INJECT=1

# Capture the tagged backend URL (Cloud Run assigns the hash — do not guess).
BACKEND_STRESS_URL=$(gcloud run services describe agent-backend-combined \
  --region $REGION \
  --format='value(status.traffic)' | tr ';' '\n' | grep -i stress)
echo "$BACKEND_STRESS_URL"
# Expect: https://stress---agent-backend-combined-<hash>-uc.a.run.app
```

- `T3_FANOUT_ENABLED=1` → the fan-out fork is live (default OFF in prod).
- `FANOUT_FAULT_INJECT=1` → honors the `__FAULT_TIMEOUT__` / `__FAULT_SLOW__`
  corpus tokens. **This flag is acceptable ONLY on a `--tag stress` revision**
  (plan §5 risk: "fault-injection leaks to prod"). It is never set on prod.
- The loop flags are needed because `plan_source=generated` is what lets the
  supervisor's decompose LLM run (else it declines `no-generator`).

> If the revision fails to start, check it: `gcloud run revisions list
> --service agent-backend-combined --region $REGION` then
> `gcloud logging read "resource.labels.service_name=agent-backend-combined" --limit=50 --freshness=10m`.

---

## 3. Frontend stress revision + fill the profile

```bash
# Reuse the live frontend digest (no frontend code change for T3).
FE_IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-frontend --region $REGION \
     --format='value(status.latestReadyRevisionName)')" \
  --region $REGION --format='value(spec.containers[0].image)')

# Point the frontend's MIDDLEWARE_URL at the backend stress tag.
gcloud run services update agent-frontend --region $REGION \
  --image "$FE_IMG" --tag stress --no-traffic \
  --update-env-vars "MIDDLEWARE_URL=${BACKEND_STRESS_URL}"

# Auto-fill the tagged FRONTEND url into the stress test profile (reads the
# real hash off the traffic map; refuses to stamp a placeholder).
python scripts/fill_stress_profile_url.py
git diff frontend/e2e/testing.profiles.yml   # confirm base_url updated to stress---agent-frontend-...
```

---

## 4. Smoke first (protects the batch — Langfuse quota has 429'd before)

```bash
cd frontend
TEST_PROFILE=stress STRESS_PHASE=fanout STRESS_SMOKE=1 pnpm test:e2e:stress
cd ..
```

**Gate before the full batch:** confirm the fan-out carriers actually emit on a
live trace — one fan-out row should show `delegation_requested` per branch and a
`join` carrier. Check via Cloud Logging (B-verify command below) for one smoke
`thread_id`. If carriers are absent, STOP — do not burn the batch.

---

## 5. Full batch + verify + analyze

### 5a · Run the batch
```bash
cd frontend
TEST_PROFILE=stress STRESS_PHASE=fanout pnpm test:e2e:stress
cd ..
```
(Spec is chromium-only + 600s global timeout, already wired. `filterCases`
filters dynamically on `phase`, so `STRESS_PHASE=fanout` works.)

**Playwright-skill non-negotiables (don't paraphrase them away):** assert
*structure + provenance, not exact LLM prose*; **settle-poll** the rendered text,
never `finished()`; scope to `article div[aria-live="polite"]`.

### 5b · Server-side verification (a green DOM only proves the frontend rendered)
> NOTE: `scripts/verify_run.py` (named in the plan) does **not exist** in the
> repo — use Cloud Logging directly. Cross-check a fan-out row landed N
> `delegation_requested` events, and a decline row landed **zero**:

```bash
# Replace <thread_id> with the session/thread from the run (e.g. session-fanout-...).
gcloud logging read \
  "resource.labels.service_name=agent-backend-combined AND textPayload:delegation_requested AND textPayload:<thread_id>" \
  --region $REGION --limit=50 --freshness=1h \
  --format='value(timestamp, jsonPayload.message, textPayload)'
```
Confirm: ≥2 `delegation_requested` on a `FANOUT-independent-*` row; **0** on a
`FANOUT-decline-*` row. This is the seam-observability check the DOM can't show.

### 5c · Analyze + gate (read from Langfuse — Cloud Run tmpfs is ephemeral)
```bash
export LANGFUSE_PUBLIC_KEY=...    # from your Langfuse project
export LANGFUSE_SECRET_KEY=...
export LANGFUSE_HOST=...          # if self-hosted

# Calibration first (records rates, never fails):
python scripts/analyze_planning_traces.py --source langfuse --calibration

# Read the headline numbers:
#   fanout_confusion.precision  — target >= 0.9   (the fp cell = GAIA failures)
#   partial_survival_rate       — target == 1.0   (fault rows survive)
#   fanout_confusion.recall     — REPORTED, not gated (a missed fan-out is cheap)

# Once the bars look right, enforce them:
python scripts/analyze_planning_traces.py --source langfuse --gate
echo "exit=$?"   # 0 == bars met
```

---

## 6. Teardown — MANDATORY (these are live tags)

```bash
gcloud run services update-traffic agent-backend-combined --region $REGION --remove-tags stress
gcloud run services update-traffic agent-frontend          --region $REGION --remove-tags stress

# Verify both tags are gone (a stale stress tag consumes a revision slot and is
# URL-reachable):
gcloud run services describe agent-backend-combined --region $REGION --format='value(status.traffic)'
gcloud run services describe agent-frontend          --region $REGION --format='value(status.traffic)'
```

> Optionally delete the throwaway image: it costs a few cents/month in AR.
> `gcloud artifacts docker images delete $REPO/agent-backend:$TAG`

---

## 7. After the run (back to me / next session)

- **Stage C — governance audit:** paste a from-step-0 fan-out trace; run the
  `governance-trace-audit` skill (corrupt-success FIRST, per-branch `delegation_*`
  carrier check). Saves `docs/reviews/governance_audit_<wf8>_<date>.md`.
- **Stage D — open-coding (optional):** hand-code the near-miss ⚠ declines.
- **DoD §4 close-out:** the live run flips the 3 remaining DoD bars — Observable
  (Stage C), Decline-correct ≥0.9 (5c), MAST-bounded fault rows (5b/5c).

---

## Quick checklist

- [ ] 1. Build + push T3 image from `feat/t3-supervisor-fanout`
- [ ] 2. Backend `--tag stress` (loops+T3+fault env) → capture `BACKEND_STRESS_URL`
- [ ] 3. Frontend `--tag stress` (`MIDDLEWARE_URL`=backend stress) + `fill_stress_profile_url.py`
- [ ] 4. Smoke (`STRESS_SMOKE=1`) → confirm per-branch carriers on a live trace
- [ ] 5a. Full batch · 5b. Cloud Logging verify · 5c. analyze `--calibration` then `--gate`
- [ ] 6. **Teardown both stress tags** (mandatory)
- [ ] 7. Stage C audit + DoD close-out
