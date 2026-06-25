# Deploy Plan — Model Picker + A/B Prereqs (GCP Tier A)

**Status:** PLAN (not started). Created 2026-06-24.
**Skill:** `.cursor/skills/deploy-gcp` (phased OpenTofu, non-negotiable gate order, human gates).
**What ships:** commit `b61d2fd` "feat(model-picker): wire H2 registry, user pin routing, and UI
picker" — the 3-set registry, `pinned_model` router branch, `GET /models`, Composer dropdown,
left-panel reorg, DeepSeek V4 set, and `scripts/model_ab_eval.py`.

## TL;DR

The deploy is **mostly a new image** (backend + frontend) — the model picker, router pin, `/models`,
and the DeepSeek *registry* are all in code, byte-identical Auto behavior with `MODEL_PROFILE_SET`
unset. **Three secret/infra deltas are required**, all in the same `secrets` phase:

1. **`ANTHROPIC_API_KEY` value is stale** — the key was **rotated 2026-06-24** (new key in `.env`,
   len 108 `sk-ant…`). TF *wiring* is fine, but the deployed Secret Manager value is the OLD (likely
   revoked) key → Anthropic 401s until a new secret **version** is pushed. Rotate it alongside DeepSeek
   (Terraform-managed; Cloud Run reads `version="latest"`).
2. **`DEEPSEEK_API_KEY` is NOT in infra** (secret + backend env + IAM all missing) → DeepSeek pins
   will 401. REQUIRED if the A/B includes DeepSeek arms.
3. **`/models` lists one set only** → the 8-arm UI-pin sweep needs the registry's `"all"` union
   meta-set (a code change, ships in the image) + `MODEL_PROFILE_SET=all` env (a TF env block).

**Pre-deploy guard (decided): smoke BOTH provider keys locally first** (Part 0) — one real Anthropic
call + one real DeepSeek call through the runtime's own `LLMService.get_llm` path, reading the same
`.env` values that will be pushed to Secret Manager. A bad/revoked key is caught in seconds, before a
full GCP cycle.

**The synthetic-data generation + most A/B prep are pure-local and network-free → they run fully in
parallel with the GCP deploy.** Only the *live A/B run itself* depends on the finished deploy.

---

## Part 0 — Local key smoke (REQUIRED before deploy; avoids a wasted GCP cycle)

Both keys are in `.env` (verified, names+lengths only): `ANTHROPIC_API_KEY` len 108 `sk-ant…` (the new
rotated key), `DEEPSEEK_API_KEY` len 35 `sk-03f…`. LiteLLM reads provider keys from the **process env**
at call time — so a local call through `services/llm_config.LLMService.get_llm` exercises the **exact
same key + dispatch path** the deployed container will use. If a key is revoked, this 401s locally in
one call.

**0.1 — One real call per provider** via a tiny smoke script (`scripts/smoke_provider_keys.py`, or an
inline `.venv/bin/python` snippet):
- Load `.env`; build `LLMService` with a 1-profile config per provider — `anthropic/claude-haiku-4-5`,
  then `deepseek/deepseek-v4-flash` (cheapest of each → fractions of a cent).
- `await svc.invoke(profile, [{"role":"user","content":"Reply with the single word: ok"}])`.
- Assert non-empty; print **provider + model + latency + token usage ONLY** — never the key.
- A 401 / `AuthenticationError` ⇒ that key is bad; STOP and fix `.env` before deploying.

**0.2 — Gate.** Both must return a non-empty completion. Anthropic green confirms the rotated key
works; DeepSeek green confirms the new key + the `deepseek/` LiteLLM dispatch both work. Only then push
these values to Secret Manager (Part B `secrets`) — a **known-good-key** deploy, not hope-and-check.

> Cost: 2 cheap completions, well under a cent. Never in CI (real calls) — a one-shot operator
> pre-deploy gate, like GCP `preflight`.

**RESULT (2026-06-24, `scripts/smoke_provider_keys.py`): PASS 2/2.**
- `claude-haiku-4-5` OK 2873ms 14/4 tok — **rotated Anthropic key is valid** (not revoked).
- `deepseek-v4-flash` OK 1096ms 11/21 tok — new DeepSeek key + `deepseek/` dispatch work.
- ⚠→✅ **DeepSeek returns structured `thinking` blocks, not a plain string** — `content` was a list
  `['', {'type':'thinking', …}]`. **FIXED 2026-06-24.** Added `services.llm_config.response_text()`
  (reuses LangChain `AIMessage.text` to join text blocks + drop thinking) and applied it at all 7
  answer-extraction sites in `orchestration/react_loop.py` (main call_llm content, evaluate node,
  recap source + output, reflexion critique, fan-out decompose JSON, join). The **streaming/UI path
  was already correct** — `langgraph_runtime._extract_content` already keeps only `type=="text"`
  blocks. Verified: a real DeepSeek call now yields `'Paris'`, not the block-list blob. 12 new tests;
  full suite 3730 pass. No longer a blocker.
- LangSmith `429 Monthly unique traces usage limit exceeded` noise is unrelated (langchain auto-trace
  tenant cap) — did NOT affect the calls; silence with `LANGCHAIN_TRACING_V2=false` if needed.

---

## Part A — What the deploy actually needs (gap analysis)

| Change in `b61d2fd` | Ships via | Infra delta? |
|---|---|---|
| H2 registry, `pinned_model` router, `/models`, Composer dropdown, left-panel, A/B harness | **image** (backend + frontend) | none — new image only |
| `ANTHROPIC_API_KEY` **wiring** consumed by the anthropic set | already wired | ✅ secret+env+IAM exist (`cloud-run-backend.tf:209`, `secret-manager.tf:105`) |
| `ANTHROPIC_API_KEY` **value** — rotated 2026-06-24, deployed secret likely holds a REVOKED key | new secret **version** | ⚠ **must ROTATE** — value is stale; wiring is fine (see A.0 + A.1 #7) |
| **`DEEPSEEK_API_KEY`** (deepseek set / DeepSeek pins) | secret + env + IAM | ❌ **MISSING — must add** (mirror anthropic) |
| **`MODEL_PROFILE_SET`** (Auto-stack selection / `"all"` for `/models`) | backend env block | ❌ not in TF (defaults `"openai"` in `composition.py`) — add a TF-var-driven env block (default `"openai"`, prod-safe) |
| The `"all"` union meta-set so `/models` offers all 8 models for the UI-pin sweep | **image** (1-row `services/llm_config.py` change) | none for the code; needs `MODEL_PROFILE_SET=all` env to take effect |

> **STATUS 2026-06-24:** A.1 items 1–5 + A.2 are **DONE + committed** (`ad4e908`): DeepSeek
> Terraform wiring (variable/secret/env/IAM/output), the `MODEL_PROFILE_SET` env block (default
> `"openai"`), the `"all"` union meta-set, and the Composer per-item testids. `tofu validate` OK; 131
> gcp infra tests + the registry/`/models` tests pass. The content-shape fix is committed (`33d68fb`).
> **Remaining = operator-only:** A.1 #6 (put both keys in the uncommitted `terraform.tfvars`) + the
> Part 0 smoke (already PASSED) + running the deploy phases.

### A.1 — REQUIRED infra edits + the key rotation (before deploy phases)

DeepSeek items 1–4 mirror the existing `anthropic_api_key` pattern exactly. The Anthropic rotation
(item 7) is **values-only** — its wiring already exists, only the secret version changes.

1. **`infra/gcp/variables.tf`** — add `variable "deepseek_api_key" { type=string; sensitive=true }`
   (copy the `anthropic_api_key` block at `:83`).
2. **`infra/gcp/secret-manager.tf`** — add the `deepseek_api_key` secret + version + IAM accessor
   (copy the three `anthropic_api_key` resources at `:105/:120/:126`).
3. **`infra/gcp/cloud-run-backend.tf`** — add the `DEEPSEEK_API_KEY` `env { value_source { secret_key_ref … } }`
   block (copy `:209`) + the IAM dependency in the `depends_on` list (`:319`).
4. **`infra/gcp/outputs.tf`** — add the `deepseek_api_key` secret_id to the outputs map (copy `:45`).
5. **`MODEL_PROFILE_SET` env block** in `cloud-run-backend.tf` — a `var.model_profile_set`-driven
   `env { name="MODEL_PROFILE_SET"; value=var.model_profile_set }` (default `"openai"` in
   `variables.tf` → **prod Auto unchanged**). Set to `"all"` ONLY on the A/B revision (see Part C).
6. **`infra/gcp/terraform.tfvars`** (NEVER committed) — set BOTH keys from the smoke-validated `.env`:
   - `deepseek_api_key = "<DEEPSEEK_API_KEY from .env>"` (new secret).
   - `anthropic_api_key = "<the ROTATED ANTHROPIC_API_KEY from .env>"` (**overwrite the old value** —
     this is the rotation; the same `secrets` apply creates a new `google_secret_manager_secret_version`).
   Read at deploy, never print. (`terraform.tfvars` is gitignored — confirm before writing.)
7. **Anthropic rotation mechanism (no .tf edit).** The `google_secret_manager_secret_version.anthropic_api_key`
   resource already reads `secret_data = var.anthropic_api_key` with `deletion_policy = "ABANDON"`.
   Changing the tfvars value (#6) makes the next `secrets` apply add a NEW secret version; Cloud Run's
   `version = "latest"` (`cloud-run-backend.tf:213`) picks it up on the next backend revision (Part B.4).
   No env-block or `.tf` change is needed for the rotation — **only the value + a backend roll**.
   ⚠ The old version is ABANDONed (not destroyed) — fine; the new latest wins. The backend MUST roll
   (B.4) for the running container to pick up the new version; a `secrets` apply alone does not restart
   the live revision.

### A.2 — REQUIRED code edit (ships in the image, for the UI-pin sweep)

- **`services/llm_config.py`** — add `"all"` to `_MODEL_PROFILE_SETS`: a union list of every distinct
  model (deepseek + anthropic + openai), pin-only ordered so first-match Auto behavior is well-defined
  (default to the cheapest fast model). This is the [[model-ab-extensive-e2e-plan]] task 0.2a — it
  makes `/models` offer all 8 names so the Playwright dropdown can pin each. **Needed only for the
  8-arm UI-pin A/B**, not for the base prod deploy. Add it now so one image covers both.

> If the A/B will be DeepSeek-free for v1, A.1 items 1–4,6 are deferrable and the deploy is a pure
> image bump. Recommend doing the DeepSeek wiring now so the full 8-arm matrix is unblocked.

---

## Part B — Deploy sequence (deploy-gcp skill, gate order preserved)

Follow the skill's **non-negotiable gate order** for every infra phase
(`plan → show → conftest → json → terraform-compliance → apply`). Never skip policy checks.

**B.0a — Local key smoke FIRST (Part 0).** Do NOT enter the deploy phases until both providers return
a non-empty completion locally. A revoked key found here saves the whole GCP cycle below.

**B.0 — Preview (advisory, no mutations) — run after the smoke, in parallel with Part D prep:**
```bash
./scripts/deploy_gcp.sh preview        # prints changed files + affected phases vs origin/main
```
Expect it to flag `secrets`, `backend`, `frontend` (the DeepSeek secret + new images).

**B.1 — Preflight (hard blocker if it fails):**
```bash
./scripts/deploy_gcp.sh preflight
```

**B.2 — Secrets (adds the DeepSeek secret + rotates the Anthropic value):**
```bash
# terraform.tfvars must have BOTH keys set (Part A.1 #6): deepseek_api_key (new) AND the
# rotated anthropic_api_key (overwriting the stale value). Both smoke-validated in Part 0.
./scripts/deploy_gcp.sh secrets
```
This creates the `deepseek-api-key` secret AND a new `anthropic-api-key` secret VERSION. The new
Anthropic version becomes `latest` but the **running** backend still holds the old one until it rolls
in B.4. (No `data` phase — no DB schema change. Skip `foundations` unless `preview` flags it.)

**B.3 — Images (build + push + digest pin):**
```bash
DEPLOY_VERSION=2026.06.0 WRITE_TFVARS=1 ./scripts/deploy_gcp.sh images
```
Builds the new backend+frontend images (incl. the `"all"` meta-set code). **Watch the frontend
build** — it runs in `node:20-alpine` in-container; build-time FE code must stay within Node-20 APIs
([[frontend-docker-node20-vs-local-node22]]). Digest-pin via `WRITE_TFVARS=1`.

**B.4 — Backend (new image + DeepSeek env + MODEL_PROFILE_SET env):**
```bash
./scripts/deploy_gcp.sh backend
```
⚠ This uses `traffic { percent = 100 }` — a **single-step 100% cutover** to the new revision
([[deploy-gcp-skill-default-100pct-traffic]]). The backend stays prod-safe because `MODEL_PROFILE_SET`
defaults `"openai"` (byte-identical Auto). The DeepSeek key just becomes *available*; nothing routes
to it until a pin/flag selects it. **This roll is also what activates the rotated Anthropic key** —
the new revision re-reads `version="latest"` for `ANTHROPIC_API_KEY`, so after B.4 the live backend
holds the new key. (If prod Auto is `openai`, Anthropic isn't on the hot path anyway, but the A/B
`ab` revision in Part C inherits this rotated value.)

**B.5 — Frontend (new image — model dropdown, left-panel, Memory tab):**
```bash
./scripts/deploy_gcp.sh frontend
```

**B.6 — WorkOS human gate** — only if the frontend URL/redirect changed (it shouldn't for an image
bump). Check the redirect-URI triad ([[dev-workos-redirect-uri-port-3000]]) before assuming.

**B.7 — Observability + smoke:**
```bash
./scripts/deploy_gcp.sh observability
./scripts/deploy_gcp.sh smoke
```
Smoke asserts the runtime is live. **Add post-deploy checks** the standard smoke won't cover:
- `GET /models` on the deployed backend returns the expected set (still `openai` by default — the 2
  names; the 8-name union only appears under the `all` A/B revision in Part C).
- One authed run shows `model_used=` non-empty on its `step.executed` carrier (the token-seam
  guard — verify, don't assume; [[mem-tag-run-emitted-no-carriers]]).
- **Rotated-key live confirmation.** On the `ab` revision (Part C, where Anthropic/DeepSeek are
  reachable), pin `claude-haiku-4-5` and `deepseek-v4-flash` via the UI and confirm each returns a
  completion (not a 401). This is the deployed-side echo of the Part 0 local smoke — proves the
  rotated Anthropic value AND the new DeepSeek secret reached the container env correctly. If Part 0
  passed but this 401s, the secret value didn't propagate (check the secret version + that B.4 rolled
  the revision).

---

## Part C — The A/B revision (separate, prod untouched) — links to the A/B plan

The extensive A/B ([[model-ab-extensive-e2e-plan]]) wants `/models` to offer all 8 models, which means
`MODEL_PROFILE_SET=all`. **Do NOT flip prod to `all`.** Mirror the skill's tiered-loops pattern: a
**zero-traffic tagged revision** off the just-pushed digest, prod untouched:

```bash
# Backend "ab" tag from the live digest, MODEL_PROFILE_SET=all (union /models), 0% traffic:
IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-backend-combined --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')
gcloud run services update agent-backend-combined --region us-central1 \
  --image "$IMG" --tag ab --no-traffic \
  --update-env-vars MODEL_PROFILE_SET=all

# Matching frontend "ab" tag pointing at the ab backend (same pattern as the stress tag):
FE_IMG=$(gcloud run revisions describe \
  "$(gcloud run services describe agent-frontend --region us-central1 \
     --format='value(status.latestReadyRevisionName)')" \
  --region us-central1 --format='value(spec.containers[0].image)')
gcloud run services update agent-frontend --region us-central1 \
  --image "$FE_IMG" --tag ab --no-traffic \
  --update-env-vars MIDDLEWARE_URL=https://ab---agent-backend-combined-<hash>-uc.a.run.app
```
Point the Playwright A/B suite at the `ab---agent-frontend-…` URL (reuse
`scripts/fill_stress_profile_url.py`'s pattern — read the real URL off the traffic map, never guess
the hash). Tear down both `ab` tags after the run (`--remove-tags ab`).

> This is the deploy-side bridge to the A/B execution plan. It is OPTIONAL for the base deploy — only
> needed when you actually run the 8-arm sweep. The `ab` revision needs all three provider keys
> (which the backend phase B.4 already wired into the service env).

---

## Part D — What runs IN PARALLEL with the deploy (the user's question)

**Yes — nearly all A/B *preparation* is independent of GCP and runs concurrently with B.1–B.7.**
These touch only the local filesystem / committed fixtures; none call GCP, Cloud Run, or a live model:

| Parallel task | Command | Depends on deploy? |
|---|---|---|
| Build the new benchmark-shaped corpus | `python scripts/build_model_ab_corpus.py` (to author) | ❌ pure-local JSON gen |
| Regenerate the stress corpus | `python scripts/build_planning_stress_corpus.py` | ❌ pure-local |
| Export the GoalJudge 50-case general corpus to FE JSON | `python scripts/export_goaljudge_registry_json.py` | ❌ pure-local |
| Backfill `difficulty` tags on reused corpora (A/B plan §1.3) | corpus-builder edits | ❌ pure-local |
| Write the Playwright driver `model-ab.spec.ts` + typed reader | edits | ❌ code only |
| Write the analyzer `scripts/analyze_model_ab.py` + its unit tests | edits | ❌ no live LLM |
| The `"all"` meta-set code (A.2) + its registry test | edit `services/llm_config.py` | ❌ code (must be in the B.3 image, so author it BEFORE B.3) |
| Composer per-item `data-testid` (A/B plan §0.1) | edit `Composer.tsx` | ❌ code (ship in B.5 image) |
| Local A/B harness smoke (`scripts/model_ab_eval.py`, already shipped) | `make model-ab ARGS="--limit 3 …"` | needs LLM keys but NOT GCP — local |

**Confirmed pure-local:** every corpus builder was grepped for `gcloud`/`google.cloud`/`boto3`/
network clients — none import them (the one `requests` hit in the floor builder is the word
"requests" in a prompt string, not the HTTP lib). Corpus generation writes JSON to
`frontend/e2e/fixtures/` and `cache/`.

**The ONE ordering constraint:** the `"all"` meta-set (A.2) and the Composer `data-testid` (§0.1) are
**code** that must be in the images, so author + commit them **before B.3 (images)**. Everything else
in Part D can proceed at any time, fully overlapped with the apply phases.

**What CANNOT run in parallel:** the *live* A/B Playwright run (Part C + A/B plan Phase 5) — it needs
the finished `ab` revision. The deploy is its hard prerequisite.

### Suggested parallelization

```
Track 1 (deploy, serial — gate order):  preview → preflight → secrets → images → backend → frontend → smoke
Track 2 (A/B prep, parallel, local):    corpus gen + difficulty backfill + driver/analyzer authoring + "all" meta-set + testids
                                          └── (the "all" meta-set + testids must MERGE before Track 1's `images`)
Join point:                              after smoke + Part C `ab` revision  → run the live 8-arm A/B sweep
```

---

## Risks / gates

- **Stale Anthropic key → 401.** The deployed secret holds the OLD (revoked) value; the rotation is
  values-only (new tfvars value → new secret version → backend roll). Mitigated by the Part 0 local
  smoke (catches a bad new key before deploy) + the B.7 deployed re-check. A `secrets` apply WITHOUT a
  backend roll (B.4) leaves the live container on the old version — the roll is mandatory.
- **DeepSeek 401 if the secret isn't wired** (Part A.1) — REQUIRED before any DeepSeek arm.
- **`/models` won't list 8 models without the `all` meta-set + `MODEL_PROFILE_SET=all`** — the UI-pin
  sweep silently can't pin the missing models otherwise (they just won't be in the dropdown).
- **Single-step 100% cutover** (`traffic{percent=100}`) — the backend phase is live immediately; safe
  here only because `MODEL_PROFILE_SET` defaults `"openai"`. Rollback = `--to-revisions <prior>=100`.
- **Frontend Node-20 in-container build** — keep build-time FE code within Node-20 APIs.
- **Never commit `terraform.tfvars`** (holds the DeepSeek key) or print the key value.
- **Prod must NOT be flipped to `all` or `anthropic`/`deepseek`** — those Auto-stack flips are a
  separate evidence-gated decision (after the A/B PROMOTE + a governance-trace-audit pass). This
  deploy keeps prod on `openai`.

## Critical files

- **Infra (edit):** `infra/gcp/variables.tf`, `secret-manager.tf`, `cloud-run-backend.tf`,
  `outputs.tf`, `terraform.tfvars` (uncommitted).
- **Code (must be in the B.3 image):** `services/llm_config.py` (`"all"` meta-set),
  `frontend/components/chat/Composer.tsx` (per-item testids).
- **Deploy:** `scripts/deploy_gcp.sh` (phases), `scripts/fill_stress_profile_url.py` (A/B URL).
- **Parallel (local):** `scripts/build_model_ab_corpus.py` (new), `build_planning_stress_corpus.py`,
  `export_goaljudge_registry_json.py`, `scripts/analyze_model_ab.py` (new).
```
