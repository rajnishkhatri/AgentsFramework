---
type: decision-record
title: 'ADR-0019: Fireworks host adapter for the coach leakage judge (glm-5.2/Z.ai reversal)'
status: accepted
created: 2026-07-06
updated: 2026-07-06
owner: Rajnish Khatri
related: coach-recert-fireworks-rehost.spec.md, coach-recert-fireworks-rehost.plan.md, coach-recert-reliability.brainstorm.md, 0018-subject-coach-rubric-specificity-revision.md, decisions.md
tags: [decision-record]
---

# ADR-0019: Fireworks host adapter for the coach leakage judge (glm-5.2/Z.ai reversal)

**Status:** Accepted — 2026-07-06 (the re-cert it enabled CLEARED the FR-9 exit bar the same
day: GLM-5.2 on Fireworks, 3× temp-0 ENABLE, TNR 1.0 / TPR 1.0, zero-flip — see
[findings](../IAA/coach/recert/coach_recert_findings.md) §CERTIFIED + the committed
`recert_labels_fw_run{1,2,3}.jsonl`).
**Related:** [spec](../plan/coach-recert-fireworks-rehost.spec.md) ·
[plan](../plan/coach-recert-fireworks-rehost.plan.md) ·
[brainstorm](../plan/coach-recert-reliability.brainstorm.md) (Stage-1 gate) ·
[ADR-0018](0018-subject-coach-rubric-specificity-revision.md) (the cert this unblocks).
**Audience:** anyone reconsidering the coach judge's host/model, or adding a second direct
LLM host.

---

## Context

The Phase-3.9 coach **answer-leakage** judge must clear the FR-9 exit bar (≥3 temperature-0
replays on the frozen 47-row fresh split, every run TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip)
before its `COACH_LEAKAGE_GATE_ENABLED` flag can ever flip. Two forces collided:

1. **Capability is the binding constraint on TNR.** Five live model probes (recorded in the
   brainstorm) established that only the strongest models hold TNR≥0.95 *with* TPR=1.0; weaker
   models either over-flag clean teaching (OVERFLAG-1, the ADR-0018 failure) or miss indirect
   leaks. GLM-5.2 is the one **open-weight** model that passes on quality.
2. **The passing model's host is unreliable.** `glm-5.2` runs today through a direct adapter
   (`services/llm_providers/glm_direct.py`) against **Z.ai** (`https://api.z.ai/api/paas/v4`).
   Z.ai's serving layer **stalls**: individual judge calls hang >180s on random rows, and the
   stalls hit *different* rows each run — so the zero-flip requirement (no run dips below any
   floor) cannot be met, not because the model is wrong but because the serving is
   nondeterministic. External research (`docs/research/eng-coach-judge/`) attributes this to
   Z.ai capacity/MoE-batch behavior, **not** the model weights, and points to re-hosting the
   same open weights on a reliable inference host (Fireworks AI) — which also offers dedicated
   endpoints (temp-0 determinism) and grammar-constrained JSON.

The repo already has the extension substrate: a `runtime_checkable` `LLMProvider` port
(`trust/protocols.py:74`), one direct adapter whose `base_url` is already a constructor param,
a factory (`get_direct_provider`), and registry integration (`_DirectChatModel` +
`profile.provider=="direct"` at `llm_config.py:524`). So "run GLM-5.2 on Fireworks instead of
Z.ai" is a **new host behind the same port**, but it is still an ⚠️ Ask-first change: it adds a
host on the trust-boundary direct-adapter, and it **reverses** the `decisions.md` glm-5.2/Z.ai
choice. Hence this ADR.

A provenance defect surfaced during the live probes and is fixed alongside (do-regardless):
`run_coach_calibration.py`'s cert `model` is derived from the run-time profile, but the
per-row dump carried **no** model id, so two `gpt-4o` runs whose env hadn't switched were
mislabeled as glm and only caught by fingerprinting.

## Decision

**Add Fireworks AI as a second `provider="direct"` host behind the existing `LLMProvider`
port, and re-certify the coach leakage judge on Fireworks-hosted GLM-5.2** (screening
cross-family reasoning candidates — DeepSeek-R1 / Qwen3-235B / LN-Ultra, whichever Fireworks
serves — on the same frozen split first). Fireworks is selected by a **new `-fireworks`
`ModelProfile`** (`provider="direct"`, wire id `accounts/fireworks/models/<model>` carried in
`litellm_id`), resolved by a Fireworks branch in `get_direct_provider` reading
`FIREWORKS_API_KEY`. The Z.ai `glm-5.2` path is left byte-identical. **This reverses the
`decisions.md` glm-5.2/Z.ai host choice for the coach judge** — Z.ai stays a valid registered
host, but the certified judge runs on Fireworks.

Also: stamp the actual judge model into **every** dumped label row (FR-3), so a mislabeled run
can't recur.

## Options considered & rejected

**Host / model direction** (the five-probe scoreboard + host research from the brainstorm):

| Option | TNR/TPR on the split | Why rejected (or chosen) |
|--------|----------------------|--------------------------|
| **glm-5.2 on Z.ai** (status quo) | 1.00 / 1.00 quality, but **stalls** | Rejected as the *cert* path: intermittent >180s hangs on random rows break FR-9 zero-flip. Kept as a registered host (FR-2). |
| **glm-5.2 on Fireworks** | quality proven on Z.ai; host reliable | **CHOSEN** — open-weight, passes on quality, reliable host + dedicated-endpoint temp-0 + grammar-JSON. |
| Opus-4.8 | over-flags; no temp-0 (drops the param) + verbosity omits `answer_leakage` | Rejected: proprietary, same-family self-enhancement bias, and empirically over-flags. |
| claude-sonnet-4-6 | TNR 0.914, **missed a leak** | Rejected: below floor + a false-negative (worse than over-flag for a leak detector). |
| claude-haiku-4-5 | TNR 0.857 (over-flags) | Rejected: over-flags clean teaching (the ADR-0018 failure mode), below floor. |
| gpt-4o | TNR 1.0 | Kept as the **non-gating comparability anchor** (FR-12), not the cert judge: proprietary + same-family bias; the goal is an open-weight cross-family judge. |

**Host provider** (breadth / depth / economy research):

- **Fireworks AI** — CHOSEN: direct host (own inference engine, not a reseller), ~202 models
  incl. the open-weight reasoning family, **dedicated endpoints** (the FR-10 temp-0 lever) and
  grammar-constrained JSON (the optional FR-8 lever), OpenAI-compatible surface (reuses the
  httpx direct adapter, no SDK, no new dependency).
- **Together AI** — rejected (for now): comparable direct host + breadth, but no additional
  lever over Fireworks for this need; Fireworks' dedicated-endpoint determinism story is the
  deciding factor.
- **OpenRouter** — rejected: a *router* (303+ models) but adds a 5.5% fee and, more decisively,
  fp4-quant / provider-routing variance that works *against* temp-0 zero-flip — the opposite of
  what FR-10 needs.

**Mechanism** (how the host is selected):

- **A new `-fireworks` profile, dispatched by name family in `get_direct_provider`** — CHOSEN.
  Mirrors the existing GLM dispatch exactly (host derived from the model family), needs **zero**
  schema change, keeps H2 (no host string in any caller — the host lives in
  `services/llm_providers/`).
- **Add a `host`/`base_url`/`api_key_env` field to `ModelProfile`** — rejected. `ModelProfile`
  (`services/base_config.py`) is a generic config type consumed by every layer; adding host
  fields for a two-host need is heavier than warranted, and a config-type change is itself an
  ⚠️ Ask-first. Revisit if a *third* direct host arrives (the "build the abstraction on the
  second/third consumer" rule) — at three hosts, prefix-dispatch stops scaling and the field
  earns its place.
- **A Fireworks-specific branch inside the calibration harness** — rejected. Puts a host string
  in a caller (H2 violation) and duplicates the adapter's job; the harness stays host-agnostic
  (it drives whatever profile `build_live_judges` selected).

**Grammar-JSON (FR-8):**

- **Off by default, an optional adapter capability behind the port** — CHOSEN. GLM passed the
  bar without it, and the research caveat is that Fireworks `response_format` *disables
  reasoning output* (the rubric already lives in the prompt) — so forcing it could hurt. It is a
  deferred, flag-gated adapter param, never a harness branch.
- **Always-on grammar-constrained JSON** — rejected for the reasoning-output caveat above.

## Rationale

The chosen path is the *minimum* change that removes the one thing blocking FR-9 (Z.ai serving
nondeterminism) while keeping every architectural invariant: it reuses the proven adapter parse
path, adds no dependency, changes no schema, keeps the host string out of every caller (H2),
and leaves the trust-kernel contract untouched. It keeps the judge **open-weight and
cross-family** (the self-enhancement-bias mitigation the research calls for), where the
proprietary anchors (gpt-4o, Opus) are same-family. The five-probe scoreboard is the empirical
basis for rejecting the weaker models rather than a capability assumption — the failure was
measured, not guessed (mirroring ADR-0017's "empirically falsified" discipline). The `host`
field is rejected on the four-layer "build the abstraction on the second consumer" rule: two
hosts don't earn a schema change; three would.

## Consequences

- **New constraint:** a `*-fireworks` judge profile requires `FIREWORKS_API_KEY` exported to
  the operator shell (the repo doesn't auto-load `.env`); the factory fails closed with a typed
  `ConfigurationError` naming the var if it's missing (FR-1) — never a silent host fallback.
- **The cert judge's host is now Fireworks, not Z.ai** — the `decisions.md` glm-5.2/Z.ai line is
  reversed (a companion line points here). Z.ai remains a registered, working host for any other
  use; only the *certified coach judge* moves.
- **Accepted risk — shared-endpoint nondeterminism (FR-10):** if the first cert runs on
  Fireworks *serverless* (not a dedicated endpoint) and the zero-flip check fails, the honest
  outcome is a recorded non-ENABLE (telemetry-only), **never** a floor relaxation. Mitigation:
  provision a dedicated endpoint before the gating cert; a shared-endpoint run is diagnostic.
- **Accepted risk — candidate availability:** Fireworks may not serve DeepSeek-R1 / Qwen3-235B /
  LN-Ultra under the assumed ids; the screening harness records `unavailable` honestly (FR-7)
  rather than fabricating a score. GLM-5.2 is the lead; the others are screened, not assumed.
- **No live LLM in CI (unchanged):** the screen + cert are manual/local, creds-gated; CI replays
  the committed labels offline. The agent cannot run the live cert (secrets never through the
  agent).
- **Follow-on:** grammar-JSON (FR-8) and self-hosting / batch-invariant kernels stay deferred
  (research Stage-3/4) — only pursued if the dedicated-endpoint zero-flip still fails.
- **Provenance:** every dumped label row now carries `judge_model` (FR-3); a future env-drift
  like the run1/run2 mislabel is visible per-row, not only in the cert header. **Verified on
  the cert:** all three runs' cert `model` and every row's `judge_model` read
  `glm-5.2-fireworks` — the mislabel that motivated FR-3 cannot recur.

**Outcome (live, 2026-07-06 — the ADR delivered).** The screen ran all four served candidates on
the frozen 47-row split; GLM-5.2 won decisively (TNR 1.0, 0 FP) while every cross-family
candidate reproduced the ADR-0018 OVERFLAG-1 failure or stalled: DeepSeek-V4-Pro 6 FP
(TNR 0.824), GPT-OSS-120B 10 FP (TNR 0.714, REFUSE), Kimi-K2.6 stalled every row. This is the
capability gradient the brainstorm predicted, confirmed on identical rows — GLM-5.2 is the judge
on merit, not luck. The slug needed a live correction (`glm-5.2` → `glm-5p2`; Fireworks encodes
the version dot as `p`) — exactly the FR-7 confirm-at-screening step. **GLM-5.2 was serverless-
available (no dedicated endpoint needed);** the 3× cert cleared on serverless at a 180s timeout
(the stalls dropped to 0–1/run, vs Z.ai's frequent-and-shifting) — the FR-10 dedicated-endpoint
lever stayed unused. A harness bug the live run exposed (a per-row 404 swallowed into an abstain
would mask an unserved model as "47 abstains") was fixed with a fail-fast availability probe.

## Supersedes / related

Extends the direct-provider pattern established with `GLMDirectProvider`; reverses the
`decisions.md` glm-5.2/Z.ai host choice for the coach judge (companion line added there);
unblocks [ADR-0018](0018-subject-coach-rubric-specificity-revision.md)'s named FR-9 exit bar.
Does not supersede any ADR. Pairs with the Fireworks-rehost spec/plan/tasks.
