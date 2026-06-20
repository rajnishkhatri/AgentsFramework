# Chat Persistence Phase B — GCP deploy + E2E validation (Playwright screenshots + Langfuse trace eval)

> **Status:** Planning doc. Specifies the work to **deploy the Phase B build to Cloud Run and validate it
> end-to-end** — Playwright drives the recall→reject loop and captures screenshots; the Langfuse traces are
> scored against the governance contract + the Phase B claims by an analyzer; eval tests gate the verdict.
> **It changes no product source** (Phase B is already implemented + unit/e2e-green locally — see
> [`chat_persistence_memory_integration.plan.md`](chat_persistence_memory_integration.plan.md), "Phase A + Phase B
> IMPLEMENTED"). It specifies the deploy + validation harness.
>
> **Date:** 2026-06-19.
> **Validates:** [[chat-persistence-phaseb-recall-reject]] — recall carries **keys**; reject = **soft-suppress**
> (metadata flag, recall excludes it next run); the eval disclosure renders the joined items.
> **Reuses (do NOT reinvent):**
> - [`deploy-gcp`](../../.cursor/skills/deploy-gcp/SKILL.md) — phased OpenTofu apply + the **out-of-band tagged
>   zero-traffic stress revision** pattern (prod untouched).
> - [`memory_multisession_e2e_stress.plan.md`](memory_multisession_e2e_stress.plan.md) — the corpus → stress-spec
>   → analyzer → governance-audit spine + the per-case **`mem:` user bridge** (avoids the user_id-collapse defect).
> - [`governance_carrier_gate_e2e_validation.plan.md`](governance_carrier_gate_e2e_validation.plan.md) — the proven
>   **DRIVER+CAPTURE spec + Langfuse export + analyzer scorer + verdict report** triad.
> - [`scripts/analyze_memory_traces.py`](../../scripts/analyze_memory_traces.py) — recall/store carrier extractors,
>   `.env` loader, `probe_trace_id`→Langfuse join, `score_run`, `gate_failures`. **Extend, don't fork.**
> - Skills: [`playwright-agentic-e2e`](../skills/playwright-agentic-e2e/SKILL.md) (tier model, settle-poll,
>   storageState, **§5 prove-it-in-traces**), [`agentsframework-playwright`](../skills/agentsframework-playwright/SKILL.md)
>   (workspace binding), [`governance-trace-audit`](../skills/governance-trace-audit/SKILL.md) (4-pillar oracle).

---

## 0. TL;DR — the shape of the work

A **three-artifact validation** (mirrors the carrier-gate triad), plus a **deploy step** and a **screenshot
capture** the user asked for:

```
 deploy (tagged, zero-traffic)  →  Playwright DRIVER+CAPTURE  →  Langfuse export + analyzer  →  eval-gated verdict
 ─────────────────────────────     ──────────────────────────     ──────────────────────────     ──────────────────
 Phase B image to a `phaseb`       recall→reject loop on the       analyze_memory_traces.py +     gate_failures() hard-0
 tag on agent-backend-combined     deployed FE; per case:          NEW suppress extractor +       gates + a generated
 + matching agent-frontend tag;    fresh trace_id, mem: bridge,    recall-keys assertion;         verdict report. Eval
 prod traffic untouched.           SCREENSHOT of the eval          reads carriers from the live   tests = the oracle the
                                   disclosure + reject.            traces, not the DOM.           analyzer scores against.
```

**The one-line invariant being proven (skill §5):** a green screenshot proves the *frontend rendered* the recalled
list and the Reject button — it does **not** prove the backend recalled the right keys or that a rejected memory is
**actually excluded from the next recall**. That backend truth lives in the **Langfuse traces**, scored by the
analyzer against eval expectations. The screenshots are evidence-of-UX; the traces are evidence-of-behavior.

**On-demand only.** No live-model run in CI (AGENTS.md: never run live LLM calls in CI). Tagged `@t3`,
chromium-only (the T1-too-slow rule), run by hand against the deployed tag.

---

## 1. What we are validating (and what we are NOT)

**In scope — the Phase B claims to prove on the deployed stack:**

| # | Claim | Where proven |
|---|-------|--------------|
| C1 | **Recall emits keys.** A run that recalls memories emits a `MEMORY_RECALLED` carrier whose `details` carry the recalled **keys** (not just `count`), and the keys match what was injected. | Langfuse trace (analyzer) |
| C2 | **Eval disclosure renders the joined items.** In `?eval=` mode the per-turn `recalled-memories` disclosure lists `recalled-memory-{key}` rows with content joined from the panel. | Screenshot + DOM |
| C3 | **Reject soft-suppresses.** Clicking `reject-memory-{key}` issues `PATCH /api/memory/{key} {suppressed:true}`; the row is **retained** (still listable) but flagged. | Network + a follow-up GET (DOM) |
| C4 | **Suppression excludes from recall (the point).** A **second** run over the same query/user, AFTER the reject, recalls the same family of memories **minus the rejected key** — proven by the second run's `MEMORY_RECALLED` keys. This is the behavior a screenshot cannot show. | Langfuse trace (analyzer), two-run case |
| C5 | **Privacy invariant holds on the wire.** The `MEMORY_RECALLED` carrier `details` carry keys + count but **never payload content** (after `redact_details`). | Langfuse trace (analyzer) |
| C6 | **No-block / graceful.** A reject failure (or a recall-backend hiccup) never breaks the chat; the answer still renders. | DOM + screenshot |

**Out of scope:** Phase A persistence (already validated — `chat-persistence.spec.ts`); the autocapture write-back
gate (separate workstream, [[memory-autocapture-enable-policy-enforced]]); asserting exact LLM prose (skill: assert
structure/provenance, never wording); throughput; un-suppress UX from this surface (covered by unit tests; the
PATCH `suppressed:false` path is exercised at the handler/adapter layer, not the deployed e2e).

---

## 2. Reuse map — extend the existing stack

| Existing asset | Reused for | Extension needed for Phase B |
|----------------|-----------|------------------------------|
| `deploy-gcp` SKILL §"Tiered-Loops Stress Revision" | the **tagged zero-traffic revision** recipe (prod untouched) | a `phaseb` tag instead of `stress`; set `MEMORY_ENABLED=1` on the backend tag; `fill_stress_profile_url.py` → a `phaseb` profile |
| `frontend/e2e/full-stack/memory-multisession.spec.ts` | DRIVER+CAPTURE: per-case fresh `trace_id` (`freshTraceId()`), the **`mem:{caseUser}` thread bridge** (the user_id-collapse fix), JSONL row, FE-AP-7 (never send client trace_id) | a **two-run reject case** (run → reject → re-run) + **screenshot capture** at the disclosure + post-reject states |
| `frontend/e2e/testing.profiles.yml` + `load-profile.ts` | `TEST_PROFILE=…` fills UNSET env for the deployed target | a `phaseb` profile (or reuse `stress`) → BASE_URL at the deployed frontend tag |
| `scripts/analyze_memory_traces.py` | `_recall_carriers`/`_store_carriers`, `.env` loader, `probe_trace_id`→Langfuse join, `score_run`, `gate_failures`, corpus-merge + printer | **`_suppress_carriers()`** extractor + a **recall-keys** field in the recall extractor + C1/C4/C5 scorers + a `reject` phase in `score_run` |
| `frontend/e2e/fixtures/memory_multisession_corpus.{ts,json}` | corpus shape (per-case user, query, expectations) | a small **reject corpus** (≥3 cases): recall→reject→re-run, with `expect_recalled_keys_run1` / `expect_excluded_key_run2` |
| `governance-trace-audit` skill / `trust/governance_carrier_spec.py` | the 4-pillar oracle the analyzer scores against | the recall/store/suppress carriers must each satisfy the Recording pillar (a carrier even on the degraded path) |

**Principle (identical split to carrier-gate + planning-stress):** the spec is a **DRIVER+CAPTURE** (DOM outcome +
screenshot + `trace_id` only); **all** governance/behavior scoring is the **offline analyzer** reading Langfuse.

---

## 3. Deliverables

1. **A `MEMORY_SUPPRESSED` carrier on the suppress path** *(small product change — the only one).* Today
   `suppress()` logs a metadata-only line but emits **no governance carrier**, so the analyzer cannot see a reject
   in the trace (C3/C4 would be DOM-only). Add a `MEMORY_SUPPRESSED` BlackBox carrier at the
   `PATCH /agent/memory/{key}` handler (both `agent_ui_adapter/server.py` and `middleware/app_prod.py`) with
   `details = {user_id, key, suppressed: bool}` — counts/ids only, never content (the privacy invariant). Mirrors
   the existing `MEMORY_STORED`/`MEMORY_RECALLED` carrier shape. Add a `MEMORY_SUPPRESSED = "memory_suppressed"`
   member to `services/governance/black_box.py::EventType` (sits beside `MEMORY_RECALLED`/`MEMORY_STORED`); it is an
   internal carrier type, not a UI wire event, so **no openapi/drift regen** is needed (unlike the Phase B
   `memory_recalled.keys` change, which did regen). *(Failure-first tests: a suppress with no recordings dir is a
   no-op; a suppress emits exactly one carrier with the flag; the carrier `details` hold no payload content.)*

2. **Driver+capture spec** — `frontend/e2e/full-stack/phaseb-recall-reject.spec.ts` (sibling of
   `memory-multisession.spec.ts`). Per reject-corpus case:
   - **Run 1:** open `/?eval={case}`, send the case query under the `mem:{caseUser}` bridge, settle-poll the answer,
     **screenshot** the `recalled-memories` disclosure (`page.getByTestId('recalled-memories').screenshot()` +
     a full-page shot), assert ≥1 `recalled-memory-{key}` row (the only DOM assertion).
   - **Reject:** click `reject-memory-{rejectKey}`, assert the row leaves the list (DOM), **screenshot** the
     post-reject state.
   - **Run 2:** re-send the same query (fresh `trace_id`), settle, screenshot — assert the rejected row is **absent**
     from the new disclosure.
   - Write a JSONL row per run: `{case, run, trace_id, session_id, user_id, query, reject_key, recalled_row_keys,
     screenshot_path, finished_at, base_url}`. Screenshots → `frontend/e2e/artifacts/phaseb/{case}-{run}.png`.
   - Tagged `@t3`, on-demand, chromium-only. Needs `E2E_BYPASS_AUTH=1` OR a `storageState` (the disclosure is
     eval-gated and the shell needs a session — the spec auto-skips on the composer-count guard otherwise).

3. **Analyzer extension** — in `scripts/analyze_memory_traces.py`:
   - `_suppress_carriers(events)` — filter to `event_type endswith memory_suppressed`.
   - Recall extractor gains a **`keys`** read (`details.get("keys")`), tolerating the relay's list-vs-string
     coercion (reuse the planning analyzer's `_as_list`/`_as_bool` coercers — `redact_details` may stringify).
   - `score_run` gains a **`reject` phase**: per case it joins run-1 and run-2 by `(case, user_id)` and scores
     **C1** (run-1 recall keys non-empty + ⊇ expected), **C4** (run-2 recall keys = run-1 keys **minus** the
     rejected key), **C5** (no content substring in any recall carrier `details`), **C3** (a `MEMORY_SUPPRESSED`
     carrier for the rejected key exists between the two runs).
   - `gate_failures()` gains **hard-0 gates**: `reject_not_excluded` (C4 violated on any case → the headline
     defect), `recall_keys_missing` (C1), `content_leaked_in_carrier` (C5), `suppress_carrier_missing` (C3).

4. **Verdict report** — `docs/plans/chat_persistence_phaseb_e2e_report.md` (generated). Per-case table
   (run-1 keys / rejected key / run-2 keys / excluded?), the four hard-0 gate results, a **screenshot index**
   (relative paths the user/reviewer can open), and a CALIBRATION verdict (`VALIDATED` only if all hard-0 gates
   pass AND the join actually resolved — guard against the known "all 404 → false GATE PASSED" trap, below).

5. **Eval tests as the oracle** — the reject corpus's per-case `expect_*` fields ARE the eval assertions; the
   analyzer's `gate_failures()` is the pass/fail. Optionally register the reject corpus as a Langfuse **dataset**
   (reuse `scripts/langfuse_dataset_client.py`) so the recall-exclusion behavior is a tracked eval over time, not a
   one-shot.

---

## 4. Known live traps to design around (learned the hard way — see memory notes)

These already bit the multi-session run ([[memory-multisession-e2e-corpus]]) and the stress harness
([[stress-harness-traceid-superposition]]). The spec/analyzer MUST defend against each or the verdict is a lie:

- **T1 — user_id collapse.** Without the per-case `mem:{user}` thread bridge, every case collapses to the one real
  WorkOS user → recall pools across users and C4 is meaningless. **Use the `mem:` bridge** (it must be DEPLOYED on
  the backend tag — verify the tagged revision is the Phase-B image, not an older one).
- **T2 — probe↔trace join.** `probe_trace_id` (client-minted in the JSONL) must equal the Langfuse trace id, else
  every fetch 404s and the analyzer scores an **empty** event set as PASS. The analyzer already has the
  `probe_trace_id`→Langfuse join (`_load_langfuse_events_for_row`); the report's verdict MUST fail-closed when the
  join resolves **0 events** for a row (don't let "no carriers found" read as "no gaps").
- **T3 — `.env` not loaded.** `analyze_memory_traces._load_env()` already fixes this; confirm a bare
  `--source langfuse` invocation actually authenticates (a 401/empty fetch must not pass).
- **T4 — trace_id superposition.** Per-run `freshTraceId()` (already in the multi-session spec) — never a static
  per-case id, or run-1 and run-2 carriers superimpose under one trace and C4 is unscoreable.
- **T5 — relay type coercion.** `black_box_publisher.redact_details` stringifies non-allowlisted keys. The new
  `keys` list and `suppressed` bool may arrive as `"['k1']"` / `"True"`. Either allowlist them in the publisher
  (preferred — `_SAFE_*` lists) OR coerce in the analyzer. **Decide in §6; allowlisting is cleaner and keeps the
  carrier honest.**

---

## 5. Deploy procedure (prod untouched — the deploy-gcp tagged-revision recipe)

Phase B's only infra-relevant need is `MEMORY_ENABLED=1` on a backend that runs the Phase-B image. Reuse the
**out-of-band zero-traffic tagged revision** (no OpenTofu mutation → no policy gate needed; throwaway, no traffic):

```bash
# 1. Backend: serve the Phase-B image under a `phaseb` tag, 0% traffic, memory on.
#    (Build/push the Phase-B image first via `./scripts/deploy_gcp.sh images` if not already pinned.)
IMG=<phase-b digest-pinned image>           # NOT the current prod digest unless it already has Phase B
gcloud run services update agent-backend-combined --region us-central1 \
  --image "$IMG" --tag phaseb --no-traffic \
  --update-env-vars MEMORY_ENABLED=1

# 2. Frontend: matching zero-traffic tag whose MIDDLEWARE_URL points at the phaseb backend tag.
FE_IMG=<phase-b frontend digest-pinned image>
gcloud run services update agent-frontend --region us-central1 \
  --image "$FE_IMG" --tag phaseb --no-traffic \
  --update-env-vars MIDDLEWARE_URL=https://phaseb---agent-backend-combined-<hash>-uc.a.run.app

# 3. Fill the phaseb profile from the real traffic map (never hand-guess the hash).
python scripts/fill_stress_profile_url.py --tag phaseb   # extend the script's --tag arg, or add a `phaseb` profile

# 4. Smoke ONE case first, then the corpus.
#    (Add a `test:e2e:phaseb` script to frontend/package.json, modeled on the
#     existing `test:e2e:mem` — points playwright at the new spec, chromium,
#     a long global-timeout for the two-run cases.)
TEST_PROFILE=phaseb PHASEB_SMOKE=1 pnpm test:e2e:phaseb
TEST_PROFILE=phaseb pnpm test:e2e:phaseb

# 5. Tear down both tags after the run.
gcloud run services update-traffic agent-backend-combined --region us-central1 --remove-tags phaseb
gcloud run services update-traffic agent-frontend --region us-central1 --remove-tags phaseb
```

> **Gate before trusting any number:** assert the tagged revision is actually the Phase-B image (the `mem:` bridge +
> the `keys`/suppress carriers must be present) — a deploy-script lesson from
> [[memory-deploy-placeholder-image-defect]]: a tagged revision off a stale image silently invalidates the whole run.
> Confirm with one authenticated `/run/stream` hit that emits a `MEMORY_RECALLED` carrier carrying `keys`.

**Promote to prod (separate, evidence-gated decision):** only after a `VALIDATED` verdict, add `MEMORY_ENABLED`
to `infra/gcp/cloud-run-backend.tf` (Terraform var, default OFF — mirror `GOAL_JUDGE_ENABLED`) and run the full
deploy-gcp gate order + `backend` phase. Never flip it on the prod-traffic revision as a shortcut.

---

## 6. Open decisions (resolve before building)

1. **Suppress carrier — emit it? (recommended yes).** Without §3.1 the reject is DOM-only and C3/C4 lose their
   trace evidence. Cheap, mirrors existing carriers. → **Decision: emit `MEMORY_SUPPRESSED`.**
2. **Relay type fidelity — allowlist vs analyzer-coerce (recommended allowlist).** Add `keys`→safe-list and
   `suppressed`→safe-bool in `black_box_publisher` so the carrier stays honestly typed end-to-end, vs coercing in
   the analyzer. Allowlist keeps the carrier truthful for any future reader.
3. **Auth for the deployed e2e — `E2E_BYPASS_AUTH=1` vs `storageState`.** Bypass is simplest for a throwaway tag;
   storageState is closer to prod. → default **bypass on the phaseb tag** (it's zero-traffic, never prod).
4. **Eval-dataset registration (optional).** Register the reject corpus as a Langfuse dataset now (tracked
   regression of recall-exclusion) vs defer. → defer unless the user wants continuous eval.

## 7. Validation of THIS plan's harness (meta)

Backend: `pytest tests/` + `tests/architecture/` for the new carrier + publisher allowlist. Frontend:
`vitest run` + `tsc` for any spec-helper changes; `playwright test --project=chromium-desktop` for the new spec
(smoke one case). Analyzer: a unit test feeding synthetic two-run event sets to `score_run`'s `reject` phase
(C4 pass + C4 fail + empty-join fail-closed) — the analyzer must catch its own blind spots before it scores live.
```
