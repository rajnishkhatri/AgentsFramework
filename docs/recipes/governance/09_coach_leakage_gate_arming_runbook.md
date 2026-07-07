---
type: runbook
title: 'Recipe 9 — Arming the coach answer-leakage gate (off → shadow → enforce)'
description: 'Operational procedure to promote the Phase-5 coach leakage gate from off to shadow to enforce, with the wiring prerequisite, shadow-observation gate, promotion criteria, rollback, and fail-open alerting.'
tags: [recipe, governance, coach]
---

# Recipe 9 — Arming the coach answer-leakage gate (off → shadow → enforce)

**Goal:** Safely promote the certified coach answer-leakage gate from its shipped
`off` state to `shadow` (observe-only) and finally `enforce` (blocks a leaking
coach reply), one reversible step at a time — so the live behavior change is
observable before it acts, and never below the cert floor.

**Status:** The gate is BUILT and ships `off` (commit `ed029b6`, [ADR-0020](../../adr/0020-coach-leakage-gate-rollout.md)).
This runbook is the operational procedure the [Phase-5 spec §9](../../plan/coach-leakage-gate-rollout.spec.md)
deferred as out-of-scope for code. **Step 0 (the composition wire) has LANDED** —
`build_runtime_graph` now forwards `coach_goldset_certified` from the
`COACH_LEAKAGE_CERT_ATTESTED` setting (default off), so arming is now an operator
act (attest the cert + push the mode), no longer a pending code change.

**Prerequisites:**
- Phase 3.9 CERTIFIED — the judge is ENABLE-worthy ([ADR-0019](../../adr/0019-fireworks-host-adapter.md): TNR 1.0/TPR 1.0, 0 FP).
- [ADR-0020](../../adr/0020-coach-leakage-gate-rollout.md) (the inline gate + off/shadow/enforce policy).
- [Phase-5 plan](../../plan/coach-leakage-gate-rollout.plan.md) / [tasks](../../plan/coach-leakage-gate-rollout.tasks.md).
- `FIREWORKS_API_KEY` present in the coach runtime env (the judge runs on `glm-5.2-fireworks`).

---

## How the gate is controlled (the mechanics you'll operate)

The mode is a single config value, `coach_leakage_gate_mode ∈ {off, shadow, enforce}`,
in the `SubjectCoachJudgeRuntimeConfig` document. At runtime
`SubjectCoachJudgeConfigReader` reads it from `COACH_JUDGE_CONFIG_URI` (a `gs://` or
`file://` URI) with a **30 s TTL** (`COACH_JUDGE_CONFIG_TTL_S`, default 30.0). So:

- **A mode change propagates within ~30 s — no redeploy.** Push a new config doc to
  the URI; the next reader refresh picks it up.
- **Fail-dark:** a malformed/unreadable config resolves to `off` (never enforces on
  an unknown posture). A set-but-invalid mode string (`"enfroce"`) also → `off`.
- **`arm()` cert-floor guard:** even a valid `shadow`/`enforce` in the config is
  forced back to `off` unless the runtime was wired with `coach_goldset_certified=True`
  (see Step 0). A config typo can never enforce on an uncertified judge.

| Mode | Runtime cost | Behavior |
|---|---|---|
| `off` (shipped) | zero | never judges, never alters a coach reply |
| `shadow` | 1 judge call/coach turn (per sample) | records a `coach_leakage_gate` carrier with the verdict; **reply always passes unchanged** |
| `enforce` | 1 judge call/turn + ≤1 regeneration on a flagged turn | a flagged reply is regenerated once; if it still leaks → suppressed to a Socratic fallback; judge outage → **fail OPEN** (reply passes) + loud carrier |

Every mode above `off` emits a `coach_leakage_gate` governance carrier
(`guardrail_checked` event, `details.guardrail == "coach_leakage_gate"`) carrying
`mode`, `verdict`, `action`, `trace_id` — the observable audit trail you gate on.

---

## Step 0 — Attest the cert (the arming switch — do this first)

The composition wire has landed: `build_runtime_graph`
(`middleware/composition.py`) forwards `coach_goldset_certified` into `build_graph`,
derived from the `coach_leakage_cert_attested` setting
(`AgentRuntimeSettings`, env **`COACH_LEAKAGE_CERT_ATTESTED`**, **default `False`**).
`arm()` pins the gate `off` unless this is `True`, so **an un-attested deployment
keeps the gate inert regardless of the config mode** (fail-safe).

To arm, set the env var on the coach runtime deployment:

```bash
COACH_LEAKAGE_CERT_ATTESTED=true
```

This is the **code-level cert attestation** — it asserts the deployed leakage judge
is the ADR-0019-certified `glm-5.2-fireworks` (ADR-0008 cond#1 floor met). The config
`coach_leakage_gate_mode` is the **operational lever**. Both must agree for the gate
to act: attestation off ⇒ `arm` forces `off` even if the config says `enforce`;
attestation on + config `off` ⇒ still inert (the default).

**Do not** set `COACH_LEAKAGE_CERT_ATTESTED=true` on any deployment whose leakage
judge is not the certified `glm-5.2-fireworks` — the attestation is the one place the
runtime trusts the operator that the cert applies.

**Verify Step 0:** with `COACH_LEAKAGE_CERT_ATTESTED=true` and a config carrying
`coach_leakage_gate_mode: "shadow"`, a coach turn emits a `coach_leakage_gate`
carrier with `mode: "shadow"`. With the attestation absent/false, no carrier appears
(armed `off`) — proven by
`tests/middleware/test_coach_shadow_wiring.py::TestCoachLeakageCertAttestation`.

---

## Step 1 — Promote to `shadow` (observe-only)

1. Push a config doc to `COACH_JUDGE_CONFIG_URI` with `coach_leakage_gate_mode: "shadow"`
   (keep the deprecated `coach_leakage_gate_enabled` absent or `false` — the explicit
   mode wins). Bump `updated_by`/`updated_at` for the audit trail.
2. Wait one TTL (~30 s). Confirm the reader picked it up: `/healthz` posture echoes
   `leakage_gate_mode: "shadow"`, or a coach turn emits a shadow carrier.
3. **Observe — do not promote yet.** Shadow blocks nothing; it only records verdicts.

### The shadow-observation gate — what to watch (from the carriers)

Query the `coach_leakage_gate` carriers (BlackBox → Langfuse) over a representative
window (aim for ≥ a few hundred coach turns across modes/strata):

| Signal | Read from | Green-to-promote |
|---|---|---|
| **Verdict distribution** | `details.verdict` (`clean`/`leak`/`unavailable`) | leak rate is plausible for the corpus (the cert saw ~0.175 leak share); a wildly high `leak` rate = over-flag risk, revisit before enforce |
| **`unavailable` rate** | `details.verdict == "unavailable"` | low (judge availability is healthy); a high rate means enforce would fail-open often — fix host/timeout first |
| **Would-suppress frequency** | shadow verdict `leak` count (what enforce *would* have regenerated/suppressed) | matches expectation from the cert; no surprise cliff on a particular stratum |
| **Added latency** | judge-call latency in the phase/step carriers | within the coach turn's latency budget; enforce adds the same call inline |
| **Spot-check the leaks** | pull the `trace_id`s where `verdict == "leak"` | the flagged replies are genuinely leaking (sample-audit a handful — trust-but-verify the 0-FP cert on live traffic) |

**Promotion criteria (all must hold):** a full observation window with the leak-rate
in the expected band, a low `unavailable` rate, latency within budget, and a manual
spot-audit confirming the shadow `leak` verdicts are real leaks (no live over-flag
regression vs the frozen-split cert).

---

## Step 2 — Promote to `enforce`

1. Push a config doc with `coach_leakage_gate_mode: "enforce"`. Same ~30 s propagation.
2. Confirm `/healthz` posture → `leakage_gate_mode: "enforce"` and that coach turns
   now emit carriers with `action ∈ {allow, regenerate, suppress, fail_open}` (not
   just `shadow_record`).
3. **Watch the first live enforce window closely** (below).

### What enforce does per turn

- `verdict == clean` → `action: allow`, reply unchanged.
- `verdict == leak` → regenerate once with a no-leak directive → re-judge:
  - retry clean → `action: regenerate`, emit the regenerated reply.
  - retry still leaks → `action: suppress`, emit the Socratic fallback (the leaking
    text — original AND regen — is never emitted).
- `verdict == unavailable` (judge outage/timeout) → `action: fail_open`, **reply
  passes unchanged** + a loud carrier. Availability over a rare leak during an outage.

---

## Monitoring & alerting (stand up before Step 2)

Alert on the `coach_leakage_gate` carriers:

- **`action == "fail_open"` rate** — this is a leak-safety hole open during a judge
  outage. A spike means the judge host is degraded; page and investigate the Fireworks
  host / timeout. A sustained non-trivial fail-open rate is grounds to roll back to
  `shadow` (you're paying enforce's latency without its guarantee).
- **`action == "suppress"` rate** — learners are getting the fallback instead of a
  coaching reply. A spike means either real leak pressure or an over-flag regression;
  cross-check against the shadow baseline.
- **`action == "regenerate"` rate** — the extra-LLM-call cost signal; watch for a cost
  cliff.
- **Verdict `unavailable` rate** — the leading indicator for fail-open; alert before it
  becomes a fail-open spike.

---

## Rollback (any step, any time)

**Rollback is a single config push — no redeploy.** Set
`coach_leakage_gate_mode: "off"` (or `"shadow"` to keep observing without acting) at
`COACH_JUDGE_CONFIG_URI`; the next reader refresh (~30 s) reverts. Because the mode is
config-driven and the reader fails dark, a bad enforce rollout is ~30 s from neutralized.

Emergency: if the config store itself is unreachable, the reader serves the last-good
posture (stale) or fails dark to `off` — a config outage cannot *silently arm* the gate,
only leave it where it was or turn it off.

---

## Verification

- **Step 0 wired:** a coach turn under `mode: "shadow"` emits a `coach_leakage_gate`
  carrier; before the wire, none appears (armed `off`).
- **Shadow is observe-only:** carriers show `action: "shadow_record"`, and coach
  replies are byte-identical to the pre-shadow behavior (diff a sample).
- **Enforce acts:** a known-leaking reply produces `action ∈ {regenerate, suppress}`
  and the emitted text never contains the leak; a healthy judge yields no `fail_open`.
- **Rollback works:** push `off`, wait one TTL, confirm `/healthz` posture flips and
  carriers stop.
- **CI still green:** the gate ships `off` by default; `make check` is green at
  `ed029b6` (5156 passed). Arming touches config + one composition wire, not the
  test-gated code paths.
