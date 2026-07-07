# Spec — Coach leakage judge re-cert on Fireworks-hosted open-weight models

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Related:** [brainstorm](coach-recert-reliability.brainstorm.md) (Stage-1 gate) ·
[fresh-recert spec](coach-fresh-recert-split.spec.md) (FR-8/9/10/11 this inherits) ·
[ADR-0018](../adr/0018-subject-coach-rubric-specificity-revision.md) (the cert this unblocks) ·
[decisions.md](../adr/decisions.md) (glm-5.2/Z.ai choice this reverses) ·
`services/llm_providers/glm_direct.py` · `trust/protocols.py` (`LLMProvider` port).

---

## 1. Goal

Certify the Phase-3.9 coach **answer-leakage** judge on an **open-weight, cross-family**
model served by a **reliable API host (Fireworks AI)**, closing the FR-9 exit bar that the
`glm-5.2`-on-Z.ai path could not reach because of intermittent provider stalls. GLM-5.2
already cleared the bar on *quality* (TNR 1.00/0.97, TPR 1.0 on the frozen 47-row split); the
only blocker was Z.ai's serving layer. This change makes the judge **host** a
protocol-conforming config seam so GLM-5.2 (and cross-family alternatives) run on Fireworks,
then re-runs the unchanged cert.

## 2. Context

Five live model probes (`coach-recert-reliability.brainstorm.md`) established that capability
is the binding constraint on TNR — only the strongest models hold TNR≥0.95 with TPR=1.0;
Opus/Sonnet/Haiku over-flag or miss a leak. GLM-5.2 is the open-weight option that passes,
but Z.ai stalls (calls hang >180s on random rows — confirmed by external research as a Z.ai
capacity/serving issue, **not** the model). The repo already has the extension substrate: a
`runtime_checkable` `LLMProvider` protocol (`trust/protocols.py:74`), one direct adapter
(`GLMDirectProvider`, whose `base_url` is already a constructor param), a factory
(`get_direct_provider`), and the registry integration (`_DirectChatModel` +
`profile.provider=="direct"` at `llm_config.py:524`). Fireworks is therefore a **new
`provider="direct"` profile + host resolution behind the same port** — no architectural
divergence. The judge model is pinned by the existing `COACH_JUDGE_MODEL` seam (FR-8); no
CI live calls (creds-gated, local, like the glm path). This spec also fixes a **provenance
defect** surfaced live: `run_coach_calibration.py` stamps the cert `model` from the run-time
env, which mislabeled two gpt-4o runs as glm.

**Clarify decisions (Stage-2):** (1) host selection = **new profile per host**
(`glm-5.2-fireworks`), pinned via `COACH_JUDGE_MODEL`, no new env knob; (2) design = **extend
the existing `LLMProvider`/direct-adapter/registry pattern**, grammar-JSON is an *optional
adapter capability behind the port*, not a special path; (3) screening = **all four
candidates up front, then certify the winner**.

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (missing Fireworks key fails closed).** IF a `*-fireworks` judge profile is selected
  and `FIREWORKS_API_KEY` is unset THEN the factory SHALL raise a typed
  `ConfigurationError` naming the missing env var (mirroring the existing GLM key check),
  never fall back to Z.ai or another host silently.
- **FR-2 (no host cross-talk).** IF the Z.ai `glm-5.2` profile is selected THEN it SHALL
  resolve `GLM_API_KEY`/`ZAI_API_KEY` and the Z.ai base URL unchanged; a Fireworks profile
  SHALL NOT alter the Z.ai path (the two hosts are independent profiles).
- **FR-3 (provenance — actual model stamped).** WHEN a calibration run dumps labels and
  writes a cert THE recorded `model` SHALL be the judge profile actually used (its `name`),
  and each dumped label row SHALL carry that model id, so a run's host+model is recoverable
  from its artifacts without fingerprinting. (Closes the run1/run2 mislabel.)
- **FR-4 (Fireworks host adapter, protocol-conforming).** THE Fireworks direct provider
  SHALL satisfy the `LLMProvider` port (`trust/protocols.py`) exactly as `GLMDirectProvider`
  does — POST an OpenAI-compatible `/chat/completions` to `https://api.fireworks.ai/inference/v1`
  with a Bearer `FIREWORKS_API_KEY`, mapping the response to `LLMCompletion`. No caller
  outside `services/llm_providers/` SHALL hardcode the Fireworks base URL (H2).
- **FR-5 (host-specific model id).** WHERE a profile targets Fireworks THE wire model id
  SHALL be the Fireworks form (`accounts/fireworks/models/<model>`), carried by the profile,
  distinct from Z.ai's bare `glm-5.2` — selected by profile, not string-munged in the caller.
- **FR-6 (model pin reaches the Fireworks profile).** WHEN `COACH_JUDGE_MODEL=glm-5.2-fireworks`
  (with the profile set that contains it) THE built `PedagogyJudge` SHALL use that profile
  (`provider="direct"`, Fireworks host), via the existing `select_judge_profile` pin — no new
  selection knob (H2, mirrors FR-8).
- **FR-7 (screening harness).** THE re-cert SHALL support running the frozen
  `coach_recert_split_v1.json` against **each** candidate profile
  ({`glm-5.2`, `deepseek-r1`, `qwen3-235b`, and `ln-ultra` IF Fireworks serves it}) on
  Fireworks, recording per-candidate TNR / TPR / κ / abstain, to rank before the full cert.
  A candidate Fireworks does not serve SHALL be recorded as `unavailable`, not fabricated.
- **FR-8 (grammar-JSON is optional, behind the port).** WHERE a `direct` profile enables
  structured output THE adapter MAY send Fireworks `response_format` (JSON-schema) to force
  the `PedagogyVerdict` required fields; this SHALL be an adapter capability toggled by
  profile/param, not a Fireworks-specific branch in the calibration harness, and SHALL be
  **off by default** (GLM passed without it). (Research caveat recorded: on Fireworks
  `response_format` disables reasoning output → the rubric already lives in the prompt.)
- **FR-9 (exit bar — UNCHANGED, inherited from fresh-recert FR-9).** WHEN the re-cert runs on
  the winning candidate THE decision SHALL be `ENABLE` only if, across **≥3 temperature-0
  replays**, **every** run clears **TNR ≥ 0.95 AND TPR ≥ 0.90 AND κ ≥ 0.75** (zero-flip —
  no single run dips below any floor). Abstentions SHALL drop from the confusion (FR-11 of
  the fresh-recert spec), never scored `false`.
- **FR-10 (determinism posture).** THE cert SHALL run against a Fireworks endpoint chosen to
  minimize MoE temp-0 nondeterminism (dedicated endpoint where available); IF the zero-flip
  check fails on a shared endpoint THEN the honest outcome SHALL be a recorded non-ENABLE
  (telemetry-only), never a floor relaxation.
- **FR-11 (no live LLM in CI).** THE Fireworks re-cert AND screening SHALL be manual/local
  (creds-gated); CI SHALL replay committed labels offline only (unchanged posture). The
  operator runbook SHALL note `FIREWORKS_API_KEY` must be **exported to the shell** (the repo
  does not auto-load the operator env).
- **FR-12 (comparability anchor retained).** THE gpt-4o anchor on the same frozen split
  (already recorded, TNR 1.0) SHALL remain the diagnostic before/after reference (fresh-recert
  FR-10), non-gating.

## 4. Non-functional / constraints

- **Architecture (invariants):** the adapter stays in `services/llm_providers/` importing only
  `trust/` + stdlib + httpx (Trust-boundary adapter rule); no caller learns the host string
  (H2); shared types stay in `trust/` (AP-1). No `langgraph`/`langchain` import.
- **⚠️ Ask-first → ADR required:** a new host on the trust-boundary direct-adapter + the
  model/host **reversal** of the decisions.md `glm-5.2`/Z.ai choice → an ADR (Context /
  Options / Rationale incl. the five-probe scoreboard + host research / Consequences).
- **No new pyproject dependency:** Fireworks rides the existing `httpx` direct-adapter path;
  no SDK. (If a dep is later wanted, that is a separate ⚠️ Ask-first.)
- **Secrets never through the agent:** `FIREWORKS_API_KEY` handling is env-only; the
  `.env`-read hook stays authoritative; the agent cannot run the live cert.

## 5. Out of scope

- Flipping `COACH_LEAKAGE_GATE_ENABLED` (a separate human Phase-5 step, unchanged — this spec
  aims a REFUSE at ENABLE, it does not gate the live coach).
- Self-hosting / batch-invariant kernels (research Stage-3 — only if dedicated-endpoint
  zero-flip fails).
- A cross-family **ensemble** judge (research Stage-4 — deferred).
- Rubric changes (the v2 carve-out stands; this is a host/model change only).

## 6. Acceptance / verification (maps to §8 tests, filled at plan/tasks time)

Every FR above maps to ≥1 test. Offline L1/L2 (adapter host resolution, key fail-closed,
provenance stamp, pin→profile, screening-record shape) run in `make check`; the live FR-9
cert is the manual creds-gated exit gate, its committed labels replayed offline in CI.

## 7. Open questions (for clarify / plan)

- Exact Fireworks model ids for DeepSeek-R1 / Qwen3-235B / LN-Ultra (catalog check at
  screening time — FR-7 records `unavailable` for any not served).
- Whether a Fireworks **dedicated** endpoint is provisioned now or the first cert runs on
  shared serverless (FR-10 makes a shared-endpoint zero-flip failure an honest non-ENABLE,
  not a blocker to *trying*).
