# Model A/B — Phased Strategy (offline-first)

**Date:** 2026-06-25
**Decision:** isolate the A/B (a model-behavior question) from UI/delivery
validation. Drive the ranking on the offline harness (real graph, no deploy, no
browser); spend the expensive deployed-E2E budget exactly once, as a delivery
gate, after the backend pipeline is clean.

**Why offline-first (the load-bearing fact):** `scripts/model_ab_eval.py` runs
the IDENTICAL compiled graph / router / tools / governance carriers as prod. It
pins a model the same way the UI does (`selected_model` → router `pinned_model`
branch) and reads real model-identity / cost / token / latency carriers from the
black-box recordings. The only things it does NOT exercise are the Cloud Run
wrapper, BFF/SSE transport, WorkOS auth, and the browser — none of which are
*model-behavior* variables, and all of which we already proved work (smoke run 3:
Opus/flash/pro answered live through the deployed UI).

**Honest limit:** the offline Langfuse trace-join has the known Hermes-path 404
gap, so per-phase *reasoning-trace* audit is weaker offline. But
cost/tokens/latency/outcome/model-identity come through the LOCAL carriers, so the
A/B verdict does not depend on the Langfuse join. Trace-level reasoning audit is a
Phase-B (deployed) concern, not a ranking blocker.

---

## Phase A — Offline A/B over the frozen corpus (NO deploy, NO browser) ← START HERE

The whole A/B ranking happens here. Fast, flake-free, cheap to iterate: when a
pipeline bug surfaces (e.g. the next temperature-class defect), fix it in code and
re-run in minutes — not a 60-min deploy+browser cycle.

- **A0. Smoke the harness path** (`--limit 2`, one cheap pair) — prove the offline
  drive + score + report works end-to-end before the full sweep. ~2 real calls.
- **A1. Seed the GEN-L1 workspace files** (`/workspace/nums/{a,b,c}.txt`) so the
  general-L1 case tests summation, not file-absence. (Found in RUN2 §3.)
- **A2. Analyzer empty-output⇒HOLD guard** — a candidate that returns empty / zero
  tokens must NOT read as PROMOTE (the RUN2 §4 false-PROMOTE trap). Add to
  `diff_summaries` / the verdict path; unit-test it.
- **A3. Full offline A/B**: baseline = `gpt-4o`; each candidate pinned vs baseline
  over the frozen corpus — `claude-haiku-4-5`, `claude-sonnet-4-6`,
  `claude-opus-4-8`, `gpt-4o-mini`, `gpt-5-mini`, `gpt-5`, `deepseek-v4-flash`,
  `deepseek-v4-pro`. Plus the whole-stack set arms (`--candidate-set anthropic` /
  `deepseek` vs `--baseline-set openai`) to answer "should Auto flip?".
  - Cost control: Opus/Pro/gpt-5 restricted to reasoning-eligible rows (same
    eligibility predicate as the UI driver); cheap arms over the full corpus.
- **A4. Cross-model report**: cost/task, tokens, latency p50/p95, outcome, routing
  correctness, PROMOTE/HOLD per arm. This is the artifact the model decision rests
  on.
- **Exit criteria:** every arm answers (no empty output), integrity clean (model
  identity matches pin), verdicts produced, no pipeline defect outstanding.

## Phase B — Deployed-E2E delivery gate (ONE small smoke, not the A/B)

After Phase A is clean, confirm the *deployed prod path* faithfully serves what
the offline harness measured. Not to re-derive rankings.

- **B1. Commit** the URL-seed model pin (chat-shell `initialModel` + `?model=`) +
  the temp/budget fix (already committed `c70ffa9`).
- **B2. Redeploy abtest FE** (URL-seed pin) — abtest BE already on the fixed image
  (`00107-jam`). 0% traffic, prod untouched.
- **B3. One 22-run smoke** via the URL-seed driver (no dropdown click) against the
  abtest env: confirm auth/SSE/Cloud Run deliver non-empty answers + screenshots +
  the reasoning arms (Opus/flash/pro) answer live.
- **Exit criteria:** deployed smoke matches offline expectations (non-empty,
  pin honored, costs in the same ballpark).

## Phase C — UI-picker validation (separate, last)

The dropdown `model-option-*` click was the source of the browser-crash timeouts;
it's deferred per decision. Validate it on its own once the A/B is done.

- **C1. Small dropdown smoke** (a few models, picker click path) + Playwright
  `retries:1` and/or fresh-context-per-test to absorb the crash flake.
- **C2. (optional)** keep the URL-seed as the canonical A/B pin; the dropdown is a
  user affordance, validated independently.

---

## Sequencing notes
- Phase A is pure-local — runs with zero deploy dependency, parallel to nothing
  blocking.
- Phase B needs the abtest FE redeploy; Phase C can follow or run parallel to B.
- Teardown after B/C: `gcloud run services update-traffic
  agent-{backend-combined,frontend} --region us-central1 --remove-tags abtest`.
- Prod NEVER flips `MODEL_PROFILE_SET` off `openai` until a separate
  evidence-gated decision post-A/B.
