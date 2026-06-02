# GoalJudge — GCP Compatibility Plan (make the flags *settable* for validation)

> **Deliverable.** Implementation **plan only** — this document changes **no** source, test, or infra files.
> It specifies the exact diffs (as fenced code blocks) needed to make the **GoalJudge** feature and its
> [UI + Langfuse validation walkthrough](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md)
> actually runnable on the deployed **GCP Cloud Run** environment. Apply nothing.
>
> **Date:** 2026-06-02. **Scope:** the *deployment ring* only — wire `GOAL_JUDGE_ENABLED` and a new
> `GOAL_JUDGE_DOWNGRADE_ENABLED` env toggle into the production entrypoint
> [`middleware/app_prod.py`](../../middleware/app_prod.py), declare them on the Cloud Run service
> ([`infra/gcp/cloud-run-backend.tf`](../../infra/gcp/cloud-run-backend.tf)), and document the validation
> surface. **No `trust/`, `components/`, or `services/` domain-logic change. No new graph node.**
>
> **Consumer:** [`docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md`](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md)
> Step 0a (flag-wiring), Step 2 (posture confirm), Steps 5–7 (export + verify).
> **Safety authority:** [`docs/research/fix2_goaljudge_rubric_feasibility_pyramid.md`](../research/fix2_goaljudge_rubric_feasibility_pyramid.md) §2.8
> (false-downgrade enable-policy), [`docs/plans/fix2_goaljudge_remediation_f1_f4.plan.md`](fix2_goaljudge_remediation_f1_f4.plan.md).
> **Layering authority:** [`AGENTS.md`](../../AGENTS.md), [`docs/STYLE_GUIDE_LAYERING.md`](../STYLE_GUIDE_LAYERING.md).
>
> **What this plan does NOT do.** It does **not** authorize a production enable of either flag. It only makes
> them *settable* so a validator can exercise the shadow and downgrade-on postures. Production default stays
> **OFF** for both; flipping `GOAL_JUDGE_DOWNGRADE_ENABLED=true` in prod remains gated on the §2.8 calibration
> follow-on (see [§7 Risk & safety](#7-risk--safety)).

---

## Table of contents

- [1. Frontmatter recap](#1-frontmatter-recap)
- [2. Executive summary](#2-executive-summary)
- [3. Change A — env-var wiring in `middleware/app_prod.py`](#3-change-a--env-var-wiring-in-middlewareapp_prodpy)
- [4. Change B — dev-entrypoint parity (`middleware/__main__.py`)](#4-change-b--dev-entrypoint-parity-middleware__main__py)
- [5. Change C — GCP deploy surface (IaC + gcloud)](#5-change-c--gcp-deploy-surface-iac--gcloud)
- [6. Posture matrix](#6-posture-matrix)
- [7. Telemetry / export compatibility on GCP](#7-telemetry--export-compatibility-on-gcp)
- [8. Consolidated file-touch map](#8-consolidated-file-touch-map)
- [9. Verification / exit criteria](#9-verification--exit-criteria)
- [10. Risk & safety](#10-risk--safety)
- [11. Architecture compliance](#11-architecture-compliance)
- [12. Assumptions & TODOs](#12-assumptions--todos)
- [13. References](#13-references)

---

## 1. Frontmatter recap

| Field | Value |
|---|---|
| Deliverable | Plan document only — **no source/test/infra edits** in this change. |
| Goal | Make `goal_judge_enabled` + `goal_judge_downgrade_enabled` **settable** on the deployed Cloud Run backend so the GoalJudge walkthrough's Posture A (shadow) and Posture B (downgrade-on) can be exercised on GCP. |
| Flag posture | Production defaults stay `False`/`False`. This plan adds env *plumbing*, not an enable. |
| Layers touched | **Deployment ring only:** `middleware/app_prod.py` (entrypoint config plumbing), `middleware/__main__.py` (dev parity), `infra/gcp/cloud-run-backend.tf` (IaC env declaration). No `trust/`, `components/`, `services/`, no new graph node. |
| Field-name authority | [`services/base_config.py:40,46`](../../services/base_config.py) — `goal_judge_enabled`, `goal_judge_downgrade_enabled`. |
| Parse-pattern authority | [`middleware/__main__.py:304-306`](../../middleware/__main__.py) — `os.environ.get(NAME, "").strip().lower() in ("1", "true", "yes")`. **Reused verbatim; no new convention invented.** |
| Known blocker surfaced | The `eval_capture` console formatter is **printf, not JSON**, so the verdict axes (`would_downgrade`, `graceful_failure`, `partial_fraction`) do **not** reach Cloud Logging as structured `jsonPayload` today (see [§7.3](#73-blocker-g3--eval_capture-extras-are-dropped-by-the-console-formatter)). Flagged as a required follow-on; out of strict env-wiring scope. |

---

## 2. Executive summary

A just-completed [validation walkthrough](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md)
found GoalJudge **cannot be validated on GCP today** for two reasons:

1. **Flags not env-wired in production.** The production entrypoint
   [`middleware/app_prod.py:128-133`](../../middleware/app_prod.py) builds `AgentConfig(...)` with **no**
   reference to either flag — both fall back to the `base_config` defaults of `False`. The only env toggle
   in the codebase is `GOAL_JUDGE_ENABLED`, read **only** by the dev entrypoint
   [`middleware/__main__.py:304-306`](../../middleware/__main__.py). There is **no** `GOAL_JUDGE_DOWNGRADE_ENABLED`
   wiring anywhere. So neither posture (shadow / downgrade-on) can be set on the deployed Cloud Run service.
2. **Telemetry split (and a deeper formatter blocker).** Several `GoalVerdict` axes land in `eval_capture`,
   not Langfuse — so a validator needs both surfaces. On GCP this is worse than a "split": the `eval_capture`
   console handler uses a **plain printf formatter** that drops the `extra=` payload, so the axes do not
   reach Cloud Logging as queryable structured fields at all (see [§7](#7-telemetry--export-compatibility-on-gcp)).

This plan closes (1) with a 1-helper + 2-field diff in `app_prod.py`, declares both vars in the Cloud Run IaC
so the posture is reproducible, and gives the `gcloud run services update` commands for ad-hoc posture flips.
It documents (2) precisely — including the **G3 blocker** that the walkthrough's `jsonPayload.target="goal_judge"`
query will **not** match until the formatter is made structured — and recommends the minimal follow-on.

Three changes, ordered:

1. **Change A (required).** `app_prod.py`: add a `_flag()` helper mirroring the dev entrypoint and wire both
   fields into the `AgentConfig(...)` call.
2. **Change B (recommended, parity).** `__main__.py`: add the `goal_judge_downgrade_enabled` env toggle so the
   dev entrypoint and prod entrypoint parse the same two vars the same way.
3. **Change C (required for reproducibility).** `infra/gcp/cloud-run-backend.tf`: declare both env vars (default
   `"false"`) in the backend container; plus the imperative `gcloud` fallback for per-posture flips.

---

## 3. Change A — env-var wiring in `middleware/app_prod.py`

### 3.1 Verified current state

`os` is already imported ([`middleware/app_prod.py:31`](../../middleware/app_prod.py)) and `AgentConfig` is
imported from `services.base_config` ([line 61](../../middleware/app_prod.py)). The construction is:

```128:133:middleware/app_prod.py
    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
    )
```

Neither `goal_judge_enabled` nor `goal_judge_downgrade_enabled` is passed, so both default to `False`
([`services/base_config.py:40,46`](../../services/base_config.py)).

The dev entrypoint already parses one of them, and this is the pattern to mirror **verbatim**:

```304:306:middleware/__main__.py
        goal_judge_enabled=os.environ.get("GOAL_JUDGE_ENABLED", "").strip().lower()
        in ("1", "true", "yes"),
    )
```

### 3.2 Proposed diff (before → after)

Add a module-level helper next to the other `_resolve_*` helpers (e.g., immediately after
`_resolve_prod_search_provider()` at [`app_prod.py:83-89`](../../middleware/app_prod.py)), reusing the dev
entrypoint's exact accept-set `("1", "true", "yes")`:

```python
# middleware/app_prod.py — NEW helper (insert after _resolve_prod_search_provider, ~line 90)
def _flag(name: str) -> bool:
    """Parse a boolean env toggle. Mirrors middleware/__main__.py:304-306 exactly
    (accept-set ("1","true","yes"); production-safe default = False when unset)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")
```

Then wire both fields into the `AgentConfig(...)` call:

**Before** ([`app_prod.py:128-133`](../../middleware/app_prod.py)):

```python
    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
    )
```

**After:**

```python
    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
        # Deployment-ring config plumbing (not domain logic). Both default
        # False when the env var is unset — production stays dark unless an
        # operator sets the var for validation. See base_config.py:40,46.
        goal_judge_enabled=_flag("GOAL_JUDGE_ENABLED"),
        goal_judge_downgrade_enabled=_flag("GOAL_JUDGE_DOWNGRADE_ENABLED"),
    )
```

### 3.3 Why this is safe

- **Production-safe defaults.** Unset env var → `_flag()` returns `False` → identical to today's behavior.
- **No new convention.** Same accept-set and same `os.environ.get(...).strip().lower()` shape as the dev path;
  the helper just removes the inline duplication for two flags instead of one.
- **Field names confirmed** against [`services/base_config.py:40,46`](../../services/base_config.py)
  (`goal_judge_enabled`, `goal_judge_downgrade_enabled`).

---

## 4. Change B — dev-entrypoint parity (`middleware/__main__.py`)

The dev entrypoint wires `GOAL_JUDGE_ENABLED` but **not** the downgrade flag. For parity (so a validator can
reproduce Posture B locally and so both entrypoints read the same two vars), add the second toggle. The minimal
consistent approach is the same inline expression already used (no helper needed in dev, but you *may* factor
out a `_flag()` to match `app_prod.py` — optional).

**Before** ([`__main__.py:299-306`](../../middleware/__main__.py)):

```python
    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
        goal_judge_enabled=os.environ.get("GOAL_JUDGE_ENABLED", "").strip().lower()
        in ("1", "true", "yes"),
    )
```

**After:**

```python
    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
        goal_judge_enabled=os.environ.get("GOAL_JUDGE_ENABLED", "").strip().lower()
        in ("1", "true", "yes"),
        goal_judge_downgrade_enabled=os.environ.get(
            "GOAL_JUDGE_DOWNGRADE_ENABLED", ""
        ).strip().lower()
        in ("1", "true", "yes"),
    )
```

> **Recommendation:** apply Change B. It is one field, default-off, and prevents drift between the two
> entrypoints (otherwise `app_prod` understands `GOAL_JUDGE_DOWNGRADE_ENABLED` but a local `python -m middleware`
> run silently ignores it, which would confuse anyone reproducing Posture B off-GCP).

---

## 5. Change C — GCP deploy surface (IaC + gcloud)

### 5.1 How env vars reach Cloud Run (verified)

The deployed backend is the single Cloud Run service `agent-backend-combined`
([`infra/gcp/cloud-run-backend.tf:20-24`](../../infra/gcp/cloud-run-backend.tf)). It is a **multi-container**
service: the ingress backend container plus a `searxng` sidecar
([lines 245-277](../../infra/gcp/cloud-run-backend.tf)). Plain (non-secret) env vars are declared as
`env { name = ... value = ... }` blocks inside the backend `containers {}` block — e.g.
`GCP_EXECUTION_ENV`, `AGENT_OFFLOAD_DIR`, `BLACKBOX_RELAY_MODE`
([lines 87-237](../../infra/gcp/cloud-run-backend.tf)). Secrets use `value_source.secret_key_ref`
([lines 145-225](../../infra/gcp/cloud-run-backend.tf)). **This is the IaC env-var block — found and verified.**

Apply path: `tofu apply` of `cloud-run-backend.tf`, wrapped by
[`scripts/deploy_gcp.sh backend`](../../scripts/deploy_gcp.sh) → `phase_backend()` → `tofu_gate()`
([deploy_gcp.sh:460-473, 241-261](../../scripts/deploy_gcp.sh)). URL/region/project resolve via
`tofu -chdir=infra/gcp output -raw backend_url|gcp_region|gcp_project_id`
([`outputs.tf:57-65,98-106`](../../infra/gcp/outputs.tf); `gcp_region` default `us-central1`,
[`variables.tf:25-28`](../../infra/gcp/variables.tf)), exactly as
[`scripts/smoke_gcp.sh:37-46,119-122`](../../scripts/smoke_gcp.sh) does.

### 5.2 (a) IaC change — declare both vars (reproducible)

Add two plain env blocks to the **backend** container (alongside the existing public env vars, e.g. right after
the `AGENT_OFFLOAD_DIR` block at [lines 99-102](../../infra/gcp/cloud-run-backend.tf)). Default `"false"` so the
declared, reproducible baseline is dark; operators flip per posture via §5.3.

```hcl
# infra/gcp/cloud-run-backend.tf — inside resource.google_cloud_run_v2_service.backend_combined
#   → template → containers (the backend container, NOT the searxng sidecar),
#   alongside the other public env { } blocks (~after line 102).

      # ── GoalJudge validation flags (deployment-ring plumbing) ───────────
      #
      # Default "false": the judge ships dark in production. An operator sets
      # these per posture for the GoalJudge UI+Langfuse validation walkthrough.
      # Flipping GOAL_JUDGE_DOWNGRADE_ENABLED=true in a real prod profile is
      # gated on the §2.8 calibration follow-on — do NOT enable by default.
      # Parsed by middleware/app_prod.py:_flag() (accept-set "1"/"true"/"yes").

      env {
        name  = "GOAL_JUDGE_ENABLED"
        value = "false"
      }

      env {
        name  = "GOAL_JUDGE_DOWNGRADE_ENABLED"
        value = "false"
      }
```

> Declaring them (even at `"false"`) is preferable to leaving them unset because (i) it documents the contract
> in IaC, and (ii) it prevents a later `tofu apply` from *reverting* an ad-hoc `gcloud` posture flip silently —
> see the [§5.3 caveat](#53-b-imperative-gcloud-fallback-ad-hoc-posture-flips).

### 5.3 (b) Imperative `gcloud` fallback (ad-hoc posture flips)

For validation you typically flip postures faster than a `tofu apply` cycle. Use `gcloud run services update`:

```bash
# Resolve project/region the same way the smoke script does.
export GCP_PROJECT="$(tofu -chdir=infra/gcp output -raw gcp_project_id)"
export GCP_REGION="$(tofu -chdir=infra/gcp output -raw gcp_region)"   # default us-central1

# Posture A (shadow): judge ON, downgrade OFF
gcloud run services update agent-backend-combined \
  --project="$GCP_PROJECT" --region="$GCP_REGION" \
  --update-env-vars GOAL_JUDGE_ENABLED=true,GOAL_JUDGE_DOWNGRADE_ENABLED=false

# Posture B (downgrade-on): both ON
gcloud run services update agent-backend-combined \
  --project="$GCP_PROJECT" --region="$GCP_REGION" \
  --update-env-vars GOAL_JUDGE_ENABLED=true,GOAL_JUDGE_DOWNGRADE_ENABLED=true

# Return to dark baseline when done
gcloud run services update agent-backend-combined \
  --project="$GCP_PROJECT" --region="$GCP_REGION" \
  --update-env-vars GOAL_JUDGE_ENABLED=false,GOAL_JUDGE_DOWNGRADE_ENABLED=false
```

> **⚠️ Multi-container caveat (TODO to verify).** `agent-backend-combined` runs two containers
> ([`cloud-run-backend.tf:44,245`](../../infra/gcp/cloud-run-backend.tf)). On multi-container services
> `gcloud run services update --update-env-vars` targets the **ingress** container; if your `gcloud` version
> requires it, scope explicitly with `--container=<backend-container-name>`. The backend container has **no
> explicit `name`** in the IaC (only the sidecar is named `searxng`), so confirm the effective container name
> with `gcloud run services describe agent-backend-combined --region=$GCP_REGION --format=yaml` before relying
> on `--container`.
>
> **⚠️ Drift caveat.** An ad-hoc `gcloud` env change creates a **new Cloud Run revision** and will be
> **reverted** by the next `tofu apply` of `cloud-run-backend.tf` (which reasserts the `"false"` baseline from
> §5.2). For a posture that must survive redeploys, set the value in the `.tf` (§5.2) instead. This is why §5.2
> exists even though §5.3 is faster for validation.

---

## 6. Posture matrix

There is **no `/config` endpoint**; posture is confirmed from telemetry after one throwaway run (walkthrough
Step 2). The `would_downgrade` / `downgrade_applied` fields come from the `goal_judge` `eval_capture` record
([`react_loop.py:1311-1325`](../../orchestration/react_loop.py)); `goal_met` / `downgrade_reason` come from the
Langfuse `task.completed` observation ([`react_loop.py:1335-1356`](../../orchestration/react_loop.py)).

| Posture | `GOAL_JUDGE_ENABLED` | `GOAL_JUDGE_DOWNGRADE_ENABLED` | Expected behavior | How to confirm from telemetry |
|---|:---:|:---:|---|---|
| **Dark (prod default)** | `false` / unset | `false` / unset | Judge does **not** run; deterministic heuristic only. | **No** `goal_judge` `eval_capture` record exists for the run. |
| **A — Shadow** | `true` | `false` (or unset) | Judge runs and records a verdict + `would_downgrade`, but **never** mutates outcome. | `goal_judge` record present; `ai_response.would_downgrade=true` possible, but `ai_response.downgrade_applied=false` for every run; Langfuse `downgrade_reason=null` even when `goal_met=false`. |
| **B — Downgrade-on** | `true` | `true` | A `goal_met=false` verdict on a clean `success` outcome downgrades strictly `success → partial`. | `goal_judge` record with `ai_response.downgrade_applied=true`; Langfuse `outcome=partial`, `downgrade_reason="goal_judge"`. |

Gate semantics verified in [`react_loop.py:1290-1307`](../../orchestration/react_loop.py): `would_downgrade =
(verdict.goal_met is False and task_outcome.outcome == "success")`; the mutation only fires when
`goal_judge_downgrade_enabled` is true; the transition is runtime-asserted strictly `success → partial`.

> **Confirmation depends on the G3 fix ([§7.3](#73-blocker-g3--eval_capture-extras-are-dropped-by-the-console-formatter)).**
> Today the `downgrade_applied` / `would_downgrade` fields are **not** queryable in Cloud Logging (printf
> formatter drops them). Until G3 is addressed, Posture A vs. B can only be distinguished on GCP from the
> **Langfuse** side (`downgrade_reason` / `outcome` on `task.completed`), not from `eval_capture`.

---

## 7. Telemetry / export compatibility on GCP

### 7.1 Langfuse half (works on GCP)

`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are injected as secrets and `LANGFUSE_HOST` as a plain env var on
the backend container ([`cloud-run-backend.tf:135-138,177-195`](../../infra/gcp/cloud-run-backend.tf)), and the
in-process BlackBox→Langfuse relay runs in `app_prod`'s lifespan
([`app_prod.py:207-211`](../../middleware/app_prod.py)). So the Langfuse `task.completed` axes
(`outcome`, `goal_met`, `criteria_met`, `unmet_conditions`, `downgrade_reason`, `termination_reason`) reach
Langfuse Cloud and are exportable via the SDK helpers
([`tests/synthetic/blackbox/langfuse_assertions.py`](../../tests/synthetic/blackbox/langfuse_assertions.py):
`fetch_trace_details:124`, `fetch_trace_observations:142`).

### 7.2 `eval_capture` half — intended path

`eval_capture.record(target="goal_judge", ...)` ([`react_loop.py:1311-1325`](../../orchestration/react_loop.py))
emits via the `services.eval_capture` logger ([`eval_capture.py:49`](../../services/eval_capture.py)), which is
routed to the `evals` **and** `console` handlers ([`logging.json:129-133`](../../logging.json)). The `console`
handler is a `StreamHandler` to `stderr` ([`logging.json:10-14`](../../logging.json)). On Cloud Run, container
`stderr`/`stdout` is captured into Cloud Logging — **so the console handler is the right transport in
principle.** The record dict carries `target`, `task_id` (== `trace_id`/`workflow_id`), `user_id`, and the full
`ai_response` (`verdict.model_dump()` + `would_downgrade` + `downgrade_applied`)
([`eval_capture.py:34-48`](../../services/eval_capture.py); [`react_loop.py:1317-1321`](../../orchestration/react_loop.py)).

### 7.3 Blocker G3 — `eval_capture` extras are dropped by the console formatter

**Verified gap.** The `eval_capture` record is emitted as `logger.info("AI Response", extra=eval_record)`
([`eval_capture.py:49`](../../services/eval_capture.py)). The `console`/`evals` handlers both use the formatter
named `"json"`, whose format string is **printf, not JSON**:

```4:8:logging.json
        "json": {
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
```

A default `logging.Formatter` only renders the fields named in that format string. The `extra=` keys (`target`,
`task_id`, `ai_response`, `user_id`, …) are attached to the `LogRecord` but are **not serialized** — the emitted
line is just `<asctime> services.eval_capture INFO AI Response`. Consequences on Cloud Run:

- The line is plain text → Cloud Logging stores it as **`textPayload`**, not `jsonPayload`. So the walkthrough's
  query `jsonPayload.target="goal_judge"` (Step 2 / Step 6) **matches nothing**.
- Even a `textPayload:"goal_judge"` substring search fails — the literal text is only `AI Response`.
- The full file copy in `logs/evals.log` is written to the container's ephemeral tmpfs under
  `AGENT_OFFLOAD_DIR` semantics and is **not** exported off the instance, so the `eval_capture`-only axes
  (`graceful_failure`, `partial_fraction`, `per_criterion`, `rationale`, `would_downgrade`) are effectively
  **unreachable from GCP** as structured data today.

**This contradicts the walkthrough's field-location map** (which assumes `jsonPayload.target="goal_judge"` is
queryable on Cloud Run, [walkthrough §Field-location map and Step 2](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md)).
It is a real blocker for telemetry items 5–6 of the validation, independent of the flag wiring.

**Recommended follow-on (out of strict env-wiring scope — track separately).** Make the structured logging
actually structured so Cloud Run parses it into `jsonPayload`. Minimal option, a JSON formatter on the
`console`/`evals` handlers that serializes `extra` (e.g. `pythonjsonlogger.jsonlogger.JsonFormatter` with a
format listing the eval fields, or a small custom `logging.Formatter` subclass). This is a `logging.json` /
`services/observability.py` change — **config plumbing, not domain logic**, but it touches a shared services
config file rather than `middleware/`, so it is **explicitly out of this plan's scope** and listed as
[TODO T3](#12-assumptions--todos). Until it lands, GCP validators must reconstruct the `eval_capture`-only axes
from **Langfuse plus the local `logs/evals.log`** captured during a dev/local run, not from Cloud Logging.

### 7.4 `gcloud logging read` commands (post-G3)

Once G3 is fixed (records emitted as JSON), the verdict axes are queryable as written in the walkthrough:

```bash
# All goal_judge eval_capture records in the last 2h (post-G3: jsonPayload populated)
gcloud logging read \
  'resource.labels.service_name="agent-backend-combined" AND jsonPayload.target="goal_judge"' \
  --project="$GCP_PROJECT" --limit=50 --freshness=2h --format=json \
  > logs/evals_gcp.json
```

**Pre-G3 fallback** (today): there is no structured-field query. Either (i) land G3 first, or (ii) run the
P1–P5 matrix against a **local** `python -m middleware` instance (where `logs/evals.log` is durable) and export
the `eval_capture` half from that file, joining on `trace_id`/`task_id` with the GCP Langfuse traces. The
walkthrough's `load_eval_capture_verdicts()` already reads `logs/evals.log` line-delimited JSON
([walkthrough Step 6](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md)).

---

## 8. Consolidated file-touch map

| File | Change | Lines (verified) | Layer | In this plan's scope? |
|---|---|---|---|---|
| [`middleware/app_prod.py`](../../middleware/app_prod.py) | Add `_flag()` helper; pass both fields to `AgentConfig(...)`. | helper ~after 89; call 128-133 | Deployment ring | ✅ Change A (required) |
| [`middleware/__main__.py`](../../middleware/__main__.py) | Add `goal_judge_downgrade_enabled` env toggle (parity). | 299-306 | Deployment ring (dev) | ✅ Change B (recommended) |
| [`infra/gcp/cloud-run-backend.tf`](../../infra/gcp/cloud-run-backend.tf) | Declare two `env {}` blocks (`"false"` baseline) in the backend container. | insert ~after 102 | Infra | ✅ Change C (required) |
| [`logging.json`](../../logging.json) / [`services/observability.py`](../../services/observability.py) | Structured/JSON formatter so `eval_capture` extras reach Cloud Logging `jsonPayload`. | formatter 4-8; handlers 10-14,27-32 | Services (observability) | ⛔ **Out of scope** — tracked as [TODO T3](#12-assumptions--todos) |

No `trust/`, `components/`, or domain `services/` logic changes. No new graph node. No `Dockerfile` change
(the entrypoint just reads new env at process start).

---

## 9. Verification / exit criteria

Runnable checklist proving each posture works on GCP end-to-end. Reuses the walkthrough's prompt matrix
(P1–P5) and the repo's tested Langfuse helpers — no new check invented.

### 9.1 Pre-deploy (local)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
pip install -e ".[dev]"

# Judge/gate logic green offline (walkthrough Step 1)
python -m pytest -p no:logfire tests/components/test_goal_judge.py -q
python -m pytest -p no:logfire tests/orchestration/test_goal_judge_gate.py -q
```

- [ ] Both suites green (judge parse/clamp/redaction; gate success→partial only when flag ON).

### 9.2 Deploy with the flag wiring

- [ ] Change A applied to `app_prod.py`; (optionally) Change B to `__main__.py`; Change C to
  `cloud-run-backend.tf`.
- [ ] Rebuild + redeploy the backend image+service:
  `WRITE_TFVARS=1 ./scripts/deploy_gcp.sh images && ./scripts/deploy_gcp.sh backend`
  ([deploy_gcp.sh:378-473](../../scripts/deploy_gcp.sh)).
- [ ] `./scripts/smoke_gcp.sh` PASS (`/healthz`, frontend root, and SSE with `BEARER_TOKEN`).

### 9.3 Per-posture validation (run for Posture A, then Posture B)

```bash
export BACKEND_URL="$(tofu -chdir=infra/gcp output -raw backend_url)"
export FRONTEND_URL="$(tofu -chdir=infra/gcp output -raw frontend_url)"
export GCP_PROJECT="$(tofu -chdir=infra/gcp output -raw gcp_project_id)"
export GCP_REGION="$(tofu -chdir=infra/gcp output -raw gcp_region)"
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_PUBLIC_KEY="<pk-lf-...>"; export LANGFUSE_SECRET_KEY="<sk-lf-...>"

# Set posture (§5.3), then confirm it took effect (Step 2):
#   A: GOAL_JUDGE_ENABLED=true,GOAL_JUDGE_DOWNGRADE_ENABLED=false
#   B: GOAL_JUDGE_ENABLED=true,GOAL_JUDGE_DOWNGRADE_ENABLED=true
```

- [ ] **Posture confirmed (Step 2).** Run one throwaway prompt in the UI; verify a `goal_judge` verdict exists
  (Langfuse `task.completed` carries `goal_met`; once G3 lands, `gcloud logging read jsonPayload.target="goal_judge"`
  returns the record). No record ⇒ judge is OFF ⇒ env wiring/posture not effective.
- [ ] **Run P1–P5** verbatim from the [walkthrough prompt matrix](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md#the-prompt-matrix-p1p5);
  record each `trace_id`.
- [ ] **Posture A:** every `goal_met=false` run shows Langfuse `downgrade_reason=null` and `outcome` unchanged;
  shadow `would_downgrade` visible in `eval_capture` (post-G3, or via local `logs/evals.log`).
- [ ] **Posture B:** P2/P3/P5 (`goal_met=false`, clean `success`) flip to `outcome=partial`,
  `downgrade_reason="goal_judge"`; P1 (`goal_met=true`) stays `success`.
- [ ] **Export + axis coverage** via the walkthrough's Step 6 script joining Langfuse + `eval_capture`, then the
  Step 7 assertions:
  ```bash
  python -c "
  from tests.synthetic.blackbox.langfuse_assertions import (
      fetch_trace_observations, assert_no_redacted_content)
  for r in assert_no_redacted_content('<trace_id>', ['alice.smith@example.com','sk-proj-abc123']):
      print(r)
  "
  ```
- [ ] `assert_no_redacted_content` ([langfuse_assertions.py:286](../../tests/synthetic/blackbox/langfuse_assertions.py))
  passes for any secret used; ≥1 row each for `goal_met=True/False`, `graceful_failure=True`,
  `partial_fraction ∈ (0,1)` (P1–P4 strata).

### 9.4 Reset

- [ ] Return service to dark baseline (`GOAL_JUDGE_ENABLED=false,GOAL_JUDGE_DOWNGRADE_ENABLED=false`) — or rely
  on the next `tofu apply` reasserting the §5.2 `"false"` baseline.

---

## 10. Risk & safety

| Risk | Mitigation |
|---|---|
| Production accidentally enables the judge/gate. | Both env vars default `"false"` in IaC (§5.2) and `_flag()` defaults `False` when unset (§3). Dark unless an operator explicitly sets the var. |
| Flipping `GOAL_JUDGE_DOWNGRADE_ENABLED=true` in a real prod profile causes undeserved `success → partial` downgrades. | **Not authorized by this plan.** Production-enable is gated on the §2.8 false-downgrade enable-policy (precision ≥0.90 / ≤2% false-downgrade on `goal_met=False`, recall ≥0.70 floor, red-team flip ≤5%, κ≥0.6, default-off until met — [`fix2_goaljudge_rubric_feasibility_pyramid.md`](../research/fix2_goaljudge_rubric_feasibility_pyramid.md) §2.8). This plan only makes the flag **settable for validation**. |
| Ad-hoc `gcloud` posture flip silently reverted by a later `tofu apply`. | §5.3 drift caveat; for durable postures set the value in `.tf` (§5.2). |
| Validator believes a posture is active but it is not (no `/config` endpoint). | Step 2 telemetry confirmation gate in §9.3; Langfuse-side confirmation works today even pre-G3. |
| `eval_capture` axes silently missing on GCP. | G3 documented (§7.3); validation falls back to local `logs/evals.log` until the structured-formatter follow-on lands. |

The walkthrough's own sign-off rule is preserved: **do not flip `goal_judge_downgrade_enabled` on in
production** until the review's F1–F3 are closed and the P5/red-team flip rate is ≤ 5%.

---

## 11. Architecture compliance

Confirmed against [`AGENTS.md`](../../AGENTS.md) boundaries:

- **Only the deployment ring + infra are touched.** `middleware/app_prod.py` and `middleware/__main__.py` are
  entrypoints; the new `_flag()` is **config plumbing** that reads env and passes booleans into the existing
  `AgentConfig` Pydantic model — it contains **no domain logic** (no routing/evaluation/gate decision). The
  gate decision itself remains where it already is, in `orchestration/react_loop.py`, unchanged.
- **No upward dependency / no new convention.** The parse pattern is copied verbatim from the existing dev
  entrypoint; no model name is hardcoded (H2 untouched); no prompt is added (H1 untouched).
- **`trust/`, `components/`, and domain `services/` are untouched** — no shared-type change, no re-signing, no
  new horizontal service, no new graph node (the AGENTS.md "⚠️ Ask first" items are all avoided).
- The one item that would touch `services/` (the G3 structured-formatter fix) is deliberately **excluded** from
  this plan and tracked as a follow-on so this change stays inside the middleware+infra boundary.

---

## 12. Assumptions & TODOs

| # | Item | Status |
|---|---|---|
| T1 | `gcloud run services update --update-env-vars` targets the correct (ingress/backend) container on the multi-container `agent-backend-combined` service. The backend container has no explicit `name` in IaC. | **Assumption — verify** with `gcloud run services describe ... --format=yaml`; use `--container=<name>` if required (§5.3). |
| T2 | `GCP_REGION` resolves to `us-central1` unless overridden in `terraform.tfvars` ([`variables.tf:25-28`](../../infra/gcp/variables.tf)). | Verified default; per-deploy value comes from `tofu output -raw gcp_region`. |
| T3 | **G3 blocker:** the `eval_capture` console formatter is printf, so verdict axes do **not** reach Cloud Logging as `jsonPayload` ([§7.3](#73-blocker-g3--eval_capture-extras-are-dropped-by-the-console-formatter)). | **Verified gap; out of scope.** Track a follow-on to add a structured JSON formatter to the `console`/`evals` handlers in [`logging.json`](../../logging.json). Until then, GCP validation reconstructs the `eval_capture` axes from a local run's `logs/evals.log`. |
| T4 | The walkthrough's field-location map assumes `jsonPayload.target="goal_judge"` is queryable on GCP. | **Contradicted by T3** until the formatter follow-on lands; flagged to the walkthrough author. |
| T5 | `app_prod` reads new env at process start; a posture change requires a new Cloud Run revision (which `gcloud run services update` creates). | Verified — config is read once in `_build_components()` ([`app_prod.py:107-179`](../../middleware/app_prod.py)); no hot-reload. |
| T6 | The dev entrypoint Change B is optional for GCP validation but recommended for parity. | Decision: recommend applying (§4). |

---

## 13. References

- [`middleware/app_prod.py`](../../middleware/app_prod.py) — production entrypoint; `AgentConfig` build (128-133), `os` import (31), `base_config` import (61).
- [`middleware/__main__.py`](../../middleware/__main__.py) — dev entrypoint; `GOAL_JUDGE_ENABLED` parse (304-306).
- [`services/base_config.py`](../../services/base_config.py) — `goal_judge_enabled` (40), `goal_judge_downgrade_enabled` (46).
- [`infra/gcp/cloud-run-backend.tf`](../../infra/gcp/cloud-run-backend.tf) — Cloud Run backend service; public env blocks (87-237), secrets (145-225), searxng sidecar (245-277), service name (22).
- [`infra/gcp/outputs.tf`](../../infra/gcp/outputs.tf) — `backend_url` (98-101), `backend_service_name` (103-106), `gcp_project_id` (57-60), `gcp_region` (62-65).
- [`infra/gcp/variables.tf`](../../infra/gcp/variables.tf) — `gcp_region` default (25-28).
- [`scripts/deploy_gcp.sh`](../../scripts/deploy_gcp.sh) — deploy phases; `phase_backend`/`tofu_gate` (460-473, 241-261).
- [`scripts/smoke_gcp.sh`](../../scripts/smoke_gcp.sh) — health/SSE smoke; URL resolution (37-46), gcloud log query example (119-127).
- [`orchestration/react_loop.py`](../../orchestration/react_loop.py) — judge wiring (450-464), gate + shadow signal (1290-1307), `eval_capture` record (1311-1325), Langfuse `task.completed` (1335-1356).
- [`services/eval_capture.py`](../../services/eval_capture.py) — record dict (34-48), emit (49).
- [`logging.json`](../../logging.json) — `json` formatter (4-8), console handler (10-14), `evals`/`console` routing (27-32, 129-133).
- [`tests/synthetic/blackbox/langfuse_assertions.py`](../../tests/synthetic/blackbox/langfuse_assertions.py) — `fetch_trace_details` (124), `fetch_trace_observations` (142), `assert_no_redacted_content` (286), `fetch_compliance_bundle` (708).
- [`docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md`](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md) — the consumer of this plan (Step 0a, Step 2, Steps 5–7).
- [`docs/research/fix2_goaljudge_rubric_feasibility_pyramid.md`](../research/fix2_goaljudge_rubric_feasibility_pyramid.md) — §2.8 false-downgrade enable-policy.
- [`docs/plans/fix2_goaljudge_remediation_f1_f4.plan.md`](fix2_goaljudge_remediation_f1_f4.plan.md) — sibling plan (style + posture conventions).
- [`AGENTS.md`](../../AGENTS.md) — layer boundaries and anti-patterns.
