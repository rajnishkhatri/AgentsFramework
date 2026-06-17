# Carrier-gate E2E validation — Playwright (T3) + Langfuse export + analysis

**Status:** plan — **2026-06-17**. No code yet; written while the carrier-gate Phase-1 build is committed + deploying.
**Goal:** prove the shadow carrier gate ([`governance_trace_enforcement_gate.impl.md`](governance_trace_enforcement_gate.impl.md), Phase 1) works **end-to-end on the deployed stack** — the `source: "carrier_gate"` shadow carriers are emitted at the wired phase boundaries, survive the BlackBox→Langfuse relay intact, and an analyzer reads them into a per-phase **shadow-calibration verdict**. This verdict is the §5 exit gate: it's how we learn whether the warn signal is *true signal vs false-positive* before anyone considers Phase 2 (enforce).
**Method:** [`docs/skills/playwright-agentic-e2e`](../skills/playwright-agentic-e2e/SKILL.md) (tier model + verify-the-run-server-side) paired with the repo's existing T3 harness; the analysis half reuses [`docs/skills/governance-trace-audit`](../skills/governance-trace-audit/SKILL.md) rubric as the oracle.

---

## 1. What we are validating (and what we are NOT)

The carrier gate is **shadow/warn — it never blocks**, so the DOM tells us nothing about it (a run with a missing carrier still renders a normal answer). This is a textbook **skill §5 case: "a green DOM assertion proves the frontend rendered; for an agentic system you must prove the backend did the right thing via traces."** The validation lives almost entirely in the trace-analysis half.

**In scope (the claims to prove on the deployed stack):**
1. **Emission** — every wired boundary that runs (INITIALIZATION, ROUTING, MODEL_INVOCATION, OUTPUT_VALIDATION, and TOOL_EXECUTION when a tool runs) emits a `guardrail.checked` carrier with `details.source == "carrier_gate"`.
2. **Relay fidelity** — the carrier's `details` survive `black_box_publisher.redact_details` to Langfuse with usable types: `source`/`phase`/`run_shape`/`outcome` as strings, `would_enforce` as a real bool, `missing_pillars`/`missing_carriers` as a real list (NOT stringified). **This is the #1 risk — see §4.**
3. **Calibration verdict (the point)** — over a corpus of normal runs, what is the per-phase **gap rate** (`outcome == "alert"`)? On healthy traffic it should be ~0; any alert is either a real seam defect or a false-positive to triage. This rate is the Phase-2 go/no-go input.
4. **No-block invariant** — a run that *did* produce a gap (if any) still completed and rendered an answer (DOM cross-check), confirming shadow semantics in production.

**Out of scope:** Phase-2 enforce (not built); COMPLETION boundary (deliberately unwired — its `eval.goal_judge` is in the eval-overlay sink, conditional, and outcome-dependent; see impl §build-log); asserting exact LLM prose (skill: assert structure/provenance, never wording); throughput.

---

## 2. Reuse map (do NOT reinvent — extend the existing T3 stack)

The planning-stress T3 effort already built every piece of plumbing this needs. The carrier-gate validation is a **thin extension**, not a new harness.

| Existing asset | Reused for | Extension needed |
|----------------|-----------|------------------|
| `frontend/e2e/full-stack/planning-stress.spec.ts` | DRIVER+CAPTURE pattern: one case/test, fresh `trace_id` per run (`freshTraceId()` — the superposition fix), JSONL row + screenshot, `gj:{case}:{trace_id}` thread bridge, FE-AP-7 (never send client trace_id) | A sibling spec OR a `STRESS_PHASE=carrier` mode — drives a small **generic prompt set** (the gate fires on *every* run, so we don't need the planning corpus; any prompts that exercise the wired phases will do) |
| `scripts/analyze_planning_traces.py` | `--source langfuse` fetch (`_load_langfuse_events`, retries, host/keys), flatten observations→event dicts, carrier extractors, `score_run` phase dispatch | A new `_carrier_gate_events(events)` extractor + a `carrier` phase scorer producing the per-phase coverage + gap-rate scorecard |
| `scripts/validate_blackbox_langfuse.py` | BlackBox→Langfuse **parity** checker (drives BFF, asserts observations land) | Reference for the relay-fidelity assertion (§4); may add a carrier-gate scenario, or assert relay inside the analyzer |
| `frontend/e2e/testing.profiles.yml` + `load-profile.ts` | `TEST_PROFILE=stress` fills UNSET env for the deployed target | A `carrier` profile (or reuse `stress`) pointing BASE_URL at the deployed revision |
| `frontend/e2e/observability.spec.ts` | the `trace_id` provenance + console-silence T3 idiom | pattern reference |
| `docs/skills/governance-trace-audit/SKILL.md` | the four-pillar rubric = the analyzer's oracle (already transcribed into `trust/governance_carrier_spec.py`) | the analyzer cross-checks the live carriers against the spec's per-phase requirements |

**Principle:** the spec is a DRIVER+CAPTURE (DOM outcome + `trace_id` only); ALL governance scoring is the offline analyzer reading Langfuse. Identical split to planning-stress.

---

## 3. Deliverables

1. **Driver spec** — `frontend/e2e/full-stack/carrier-gate.spec.ts` (or a `carrier` mode in the stress spec). Drives ~6–10 generic prompts (a couple plain-answer, a couple tool-using so TOOL_EXECUTION fires, one long-ish multi-step so MODEL_INVOCATION/ROUTING repeat). Per case: fresh `trace_id`, send via composer, `waitForResponse` settle-poll, assert **non-empty answer rendered** (the only DOM assertion — shadow gate is invisible in UI), write a JSONL row `{case, trace_id, session_id, prompt, response_chars, used_tool, outcome, finished_at, base_url}`. On-demand only, never per-commit CI (real model). Tagged `@t3`.
2. **Analyzer extension** — in `scripts/analyze_planning_traces.py`: `_carrier_gate_events()` (filter flattened events to `event_type == guardrail_checked AND details.source == "carrier_gate"`) + a `carrier` phase in `score_run` that emits, **per phase**: emitted? (coverage), `outcome` (pass/alert), `missing_pillars`, and run-level the **gap rate** across the batch. Reuses the corpus-merge + printer machinery already there.
3. **Verdict report** — `docs/plans/governance_carrier_gate_e2e_report.md` (generated, like `t3_stage_b_case_report.md`): per-phase coverage table + gap-rate + a CALIBRATION verdict (`SIGNAL` if gaps trace to real seam defects, `CLEAN` if ~0 gap on healthy traffic, `FALSE-POSITIVE` if gaps fire on legitimate skips → spec needs a fix before Phase 2). Includes the relay-fidelity check result.
4. **Relay-fidelity assertion** (§4a) — proven once on a real trace, recorded in the report.
5. **Publisher level fix** (§4b — REQUIRED, on the critical path) — ✅ **DONE 2026-06-17.** `_level_for` raises a `carrier_gate` `outcome:"alert"` carrier to Langfuse `WARNING` + L2 publisher tests. *(Both §4 relay fixes are now landed as working changes on top of the Phase-1 commit `2f8f6b0`; the validation run's first executable step — the §4a relay pre-flight — should still confirm the live trace matches before trusting numbers.)*

---

## 4. The #1 risk: does `details` survive the relay — and at the right LEVEL?

**Verified against `black_box_publisher.py` (2026-06-17) — two real defects, not hypotheticals. ✅ BOTH FIXED 2026-06-17 (this session) — recorded below for the record; the validation run can now trust the relayed carriers.**

### 4a. Type fidelity — `redact_details` will stringify the gate's new keys
`redact_details` keeps native types ONLY for an allowlisted `_SAFE_BOOL_KEYS` / `_SAFE_NUMERIC_KEYS`; **every other value falls to `redact_text(str(value))`**. The carrier-gate keys are not allowlisted, so confirmed:

| Key | Emitted | After relay | Analyzer must |
|-----|---------|-------------|---------------|
| `source` / `phase` / `run_shape` / `outcome` | str | str (clean) | read directly |
| `would_enforce` | bool `true` | **`"True"` (string)** | use existing `_as_bool` coercer ✔ |
| `missing_pillars` / `missing_carriers` | list[str] | **`"['identity']"` (stringified list)** | **needs a new `_as_list` coercer** |
| `spec_version` | int | **`"1"` (string)** | use existing `_as_int` ✔ |

**Action — option (b), coerce in the analyzer (confirmed necessary, not just preferred):** the analyzer already coerces Langfuse-stringified bools/ints (`_as_bool`/`_as_int`); add an `_as_list` that parses the stringified list. Do NOT touch the publisher's redaction allowlist just for telemetry shape — coercing on read is the established pattern and keeps the redaction policy single-purpose.
> **✅ DONE (2026-06-17):** `_as_list` added to `scripts/analyze_planning_traces.py` (parses both native-list and the `ast.literal_eval`-able stringified shape; empty/missing→`[]`; unparseable→single-element, never raises). Test `test_langfuse_stringified_list_coerces` in `tests/scripts/test_analyze_planning_traces.py` (13 pass).

### 4b. **Observability defect — a real gap relays at `DEBUG`, indistinguishable from a clean pass**
`_level_for` raises a `GUARDRAIL_CHECKED` to Langfuse level `WARNING` **only when `details.blocked` / `redacted` / `failed_rules` are truthy**. The carrier-gate alert sets none of those — it signals via `outcome:"alert"` + `would_enforce:true`. So **a genuine missing-carrier gap is published at `DEBUG`, the same level as a clean pass** → it becomes filterable noise in Langfuse. This directly defeats the gate's entire purpose (the arXiv 2603.01548 "never a silent skip" property): the inline check would *find* the skip but the relay would *bury* it.

**Action (publisher fix, REQUIRED before the validation run is meaningful):** extend `_level_for` so a `carrier_gate` carrier with `outcome == "alert"` (or `would_enforce` truthy) maps to `WARNING`. One added condition in the existing `GUARDRAIL_CHECKED` branch; covered by an L2 publisher test. This is a small, contained change — but it is **on the critical path**: without it, §6's gap-rate is computed over carriers that a human watching Langfuse would never have seen surfaced.
> **✅ DONE (2026-06-17):** `_level_for` in `services/governance/black_box_publisher.py` now maps `source == "carrier_gate"` + (`outcome == "alert"` or `would_enforce`) → `WARNING`; a `carrier_gate` pass stays `DEBUG` (the provable negative). Tests in `tests/services/governance/test_black_box_publisher.py` (`test_carrier_gate_alert_is_warning`, `…_via_would_enforce_alone…`, `test_carrier_gate_pass_is_debug`); 91 pass.

*(Both findings mirror the trace-explainability token-seam lesson: a carrier is only worth what actually exports, at a level someone will actually look at.)*

---

## 5. Run procedure (deployed stack)

```bash
# 0. Confirm the deployed revision carries the carrier-gate code (it's flag-free —
#    the shadow gate is always on once deployed; no env toggle like T3_FANOUT).
#    Verify the deployed image is post-commit.

# 1. Drive the UI against the deployment (skill §4 remote-target playbook):
export BASE_URL=https://<deployed-revision-url>
export E2E_AUTHENTICATED=1                      # + WorkOS creds in repo-root .env (global-setup)
cd frontend && TEST_PROFILE=stress pnpm exec playwright test e2e/full-stack/carrier-gate.spec.ts \
  --project=chromium-desktop
#    → writes cache/carrier_gate/ui_batch.jsonl (one row/case, fresh trace_id each)

# 2. Let Langfuse ingest settle (~30–60s), then analyze server-side:
python scripts/analyze_planning_traces.py --source langfuse --phase carrier \
  --batch cache/carrier_gate/ui_batch.jsonl
#    → per-phase coverage + gap-rate scorecard → the verdict report
```

**Gotchas to carry in (from memory / prior T3 runs):**
- **Fresh `trace_id` per run** is mandatory — the static-trace_id superposition defect made an earlier report non-reproducible. The stress spec's `freshTraceId()` already does this; the carrier spec must copy it, not the static-corpus pattern.
- **Stale `.env` auth** + the `article div[aria-live="polite"]` selector (NOT the Next.js route announcer) + stream-finished settle-wait — all documented in the goaljudge-gcp-playwright gotcha.
- **LangSmith 429s** are harmless ingest noise; Langfuse is the relevant sink here.
- The `gj:{case}:{trace_id}` thread-id bridge is what lets the analyzer find the trace; reuse the exact format the middleware expects (`^GJ-STRESS-\d+$` case-id shape, or whatever the carrier spec's case ids are — match the regex).

---

## 6. Acceptance

- **Emission:** ≥1 carrier-gate event per wired phase that ran, across the batch (INITIALIZATION + ROUTING + MODEL_INVOCATION + OUTPUT_VALIDATION on every run; TOOL_EXECUTION on the tool cases).
- **Relay fidelity:** `would_enforce` reads as a usable bool and `missing_pillars` as a usable list in the analyzer (§4 resolved).
- **Calibration verdict rendered:** per-phase gap rate computed; verdict ∈ {CLEAN / SIGNAL / FALSE-POSITIVE} with each non-clean gap triaged to a cause.
- **No-block proven:** every case rendered a non-empty answer (DOM) regardless of gap (shadow semantics hold in prod).
- **Reproducible:** fresh trace_id per run; re-running the analyzer on the same `ui_batch.jsonl` yields the same scorecard (no superposition).

---

## 7. Open decisions

| ID | Question | Recommendation |
|----|----------|----------------|
| CE-1 | New spec file vs `STRESS_PHASE=carrier` mode in planning-stress.spec.ts? | **New small spec** — the gate fires on any prompt, so it needs neither the planning corpus nor the stress machinery; a focused `carrier-gate.spec.ts` is clearer and cheaper. Reuse the helpers/fixtures, not the corpus. |
| CE-2 | Where does relay-fidelity (§4) get asserted — analyzer or `validate_blackbox_langfuse.py`? | **Analyzer**, as a pre-flight on the first trace (it already has the coercers); keep `validate_blackbox_langfuse.py` for the broader parity sweep. |
| CE-3 | Prompt set | **~6–10 generic**: 2 plain-answer, 2–3 tool-using (TOOL_EXECUTION coverage), 1 multi-step. No oracle/`want_*` needed — on healthy traffic the expectation is "all pass"; the gate's job is to surface the exceptions. |
| CE-4 | Do we need a deliberately-broken run to prove gap-detection live? | **Not in this slice** — the L2 failure-mode matrix already proves gap detection deterministically offline; forcing a live seam defect is hard to stage and risks confusing the calibration baseline. Calibrate on healthy traffic first; a fault-injection live test is a follow-up if the gap rate is suspiciously zero. |
| CE-5 | CI cadence | **On-demand / release-gate only** (skill golden rule — real model, non-deterministic). Never per-commit. |

*Plan only. Sequenced AFTER the deploy lands; the §4 relay pre-flight is the first executable step and gates trusting any number.*
