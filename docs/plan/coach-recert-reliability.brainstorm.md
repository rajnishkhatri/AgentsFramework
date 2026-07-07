---
type: brainstorm
title: 'Brainstorm — glm-5.2 re-cert reliability (provider stalls vs the FR-9 bar)'
status: gate-passed
created: 2026-07-06
owner: Rajnish Khatri
related: coach-fresh-recert-split.spec.md, 0018-subject-coach-rubric-specificity-revision.md, decisions.md
---

# SDD Stage 1 — Brainstorm: closing FR-9 against intermittent glm-5.2 stalls

**Problem (as posed).** The Phase-3.9 re-cert on `glm-5.2` (`provider="direct"`, Z.ai)
suffers intermittent provider **stalls** — a call occasionally never returns, timing out
even at 180s, hitting a *different* row each run. Abstains contaminate the TNR denominator
run-to-run, so the FR-9 bar (≥3 temp-0 zero-flip replays, each TNR≥0.95 ∧ TPR≥0.90 ∧
κ≥0.75) is hard to satisfy. The judge has a fast-exception retry, but the harness's outer
`asyncio.wait_for` cancels it on timeout. **User's proposed direction:** add a fallback
model (Opus-4.8) beside glm-5.2 for rate-limits/timeouts.

---

## Premise audit (checked against the working tree, not memory)

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | The outer `wait_for` cancels the judge's own retry on timeout | **verified** | `run_coach_calibration.py:197` wraps the whole `evaluate()` in `asyncio.wait_for(timeout=per_call_timeout)`; the judge's retry loop (`subject_coach_judges.py` `for attempt in range(1,_MAX_ATTEMPTS+1)`) is *inside* that budget, so a >timeout stall cancels the coroutine before attempt 2. |
| P2 | FR-8 binds the cert to ONE judge model (glm-5.2) | **verified** | spec FR-8: "THE judge model SHALL be `glm-5.2` via the direct provider". A mid-cert per-call swap ⇒ a **mixed-judge** confusion matrix. |
| P3 | A per-call fallback to Opus mid-run changes the meaning of the cert | **verified** (repo + external) | The cert claim is "*this judge* holds the TNR floor". External best practice agrees: model-downgrade/fallback is a **generation** pattern; for evaluation it "changes the meaning of the result by introducing inconsistent scoring criteria" (FutureAGI field guide). |
| P4 | The gates evaluator is model-agnostic (doesn't read which model produced a label) | **verified** | `grep model services/governance/coach_calibration.py` → no match; `cert_from_labels` scores whatever boolean map it's handed. So a mixed-judge run would score green with **no signal** that two models were blended — the danger is silent. |
| P5 | FR-11 already blesses abstention-drop (a timed-out row leaves the confusion) | **verified** | spec FR-11: "IF a judge call abstains … THEN that row SHALL be dropped from the confusion for that replay (never scored `false`)". So an intersection-denominator close-out is **spec-aligned**, not a workaround. |
| P6 | FR-9 does NOT define the DENOMINATOR (full 35 vs scored-only) across replays | **verified (gap)** | FR-9 says "no single run dips below any floor" but never states whether each run's TNR is computed on all 35 clean or only its scored-clean. With per-run stalls hitting different rows, this is **underspecified** — any direction must pin it. |
| P7 | glm-5.1 exists as a litellm-mapped sibling in the same profile set | **verified** | `llm_config.py:218` `name="glm-5.1", litellm_id="zai/glm-5.1"`; profile-set default tier is glm-5.1. A *same-family* fallback exists in-repo. |
| P8 | The stalls are stalls, not slow-bounded generation | **verified (empirical)** | 90s run timed out on R-CLEAN-05/-20; 180s run timed out on R-CLEAN-**07** (different row, exceeded even 180s). Toy calls were 20/20 at max 8.6s. ⇒ intermittent socket-level stall, not a fixed per-row cost. |
| P9 | The cert's `model` field is stamped from the run-time env, decoupled from `--dump-labels` | **verified (footgun)** | `run_coach_calibration.py:299` `model` comes from `build_live_judges()` → `COACH_JUDGE_MODEL` env; nothing ties it to the output filename. **This already bit us:** `recert_labels_run1.jsonl` is a gpt-4o run (0 abstain, 35 TN, cert.model=gpt-4o) written under the "run1" (glm) name because the env var didn't take in that shell. |

**Re-framing forced by the audit.** The user's proposed direction (Opus fallback for glm)
is **refuted as a *cert* mechanism** by P2/P3/P4: a mid-cert model swap silently produces a
mixed-judge confusion matrix the evaluator can't detect, breaking the FR-8 single-model
claim *and* the FR-10 comparability logic (the whole point of FR-10 is that the model is
held constant so the before/after delta is attributable to the prose). It remains valid for
*other* goals (a resilient **production** leakage-telemetry judge, where FR-8 doesn't
apply). So the corrected problem splits into two goals on a shared substrate — the human
gate should pick which one this work serves:

- **Goal A (certification):** get 3 clean, *single-model* glm-5.2 replays to close FR-9.
- **Goal B (production resilience):** a leakage judge that survives provider outages at
  runtime (where a fallback chain IS the right pattern).

**D0 (blocking hygiene, do regardless of the pick).** P9 is a live provenance defect that
already corrupted an artifact. Until the harness stamps the *actual* judge model into the
labels (or refuses a model/filename mismatch), **any** FR-9 evidence is untrustworthy —
we literally can't tell a glm run from a gpt-4o run without fingerprinting abstains by hand.
Fix this first; it gates every other direction that produces cert evidence.

---

## Directions

### High-probability (follow existing repo patterns)

**D1 — Harness retry-on-timeout (per-attempt timeout, retry the same model).**
Move the timeout *inside* a retry loop in `replay_test_split_rows`: each attempt gets its
own `wait_for(timeout=T)`; on `TimeoutError` retry up to N with backoff+jitter; only after
N do we abstain (FR-11). Follows the judge's own retry shape (`subject_coach_judges.py`) and
the external consensus ("retry the same provider first; per-attempt timeout beats one long
timeout"). *Stresses:* nothing architectural (script-layer). *What breaks if chosen:* a
persistently-stalled row costs N×T wall-time before abstaining — cap N=2, T=120. *Serves
Goal A* — same model, so the cert stays single-model. **Recommended lead for FR-9.**

**D2 — Accept stalls; define FR-9 on the intersection denominator (spec-only + a helper).**
Don't fight the stalls. Amend FR-9 to state the denominator explicitly: score zero-flip on
the **rows all 3 replays scored** (intersection), each run still needing TNR≥0.95 on *its*
scored-clean set. Add a tiny cross-run analyzer that reports the intersection + per-run
floors + any tn↔fp flip. Leans on FR-11 (P5) which already drops abstains. *Stresses:*
none (spec + read-only script). *What breaks:* if stalls are frequent the intersection
shrinks below the "≥20 clean" FR-4 power floor — measure first (`gated-on-data`: run1 glm
scored 33/35, run3-pre 30/35, so intersection ≈ 30 ⇒ still ≥20 ✓). *Serves Goal A*, cheapest.

**D3 — Provider-side: raise/timeout-tune the glm_direct httpx client + connection reuse.**
`glm_direct.py:55` builds a fresh `AsyncClient(timeout=self._timeout)` — a single scalar
timeout (connect+read+write+pool all = T). Split it: short connect timeout, longer read
timeout, and reuse one client across calls (today a new client per provider instance). A
stalled *connect* would fail fast and retry (with D1); a legit long *read* gets its budget.
*Stresses:* Invariant #2-adjacent — `glm_direct.py` is a Trust-boundary adapter, stays
httpx-only ✓. *What breaks:* if the stall is server-side mid-stream, connect-timeout
tuning won't catch it (needs D1's retry). *Serves both goals* (adapter is shared).

### Exploratory (different abstraction / integration)

**D4 — Fallback CHAIN, but as a PRODUCTION resilience feature, explicitly NOT the cert
(Goal B).** Build glm-5.2 → Opus-4.8 fallback in the *runtime* leakage judge path
(behind `COACH_LEAKAGE_GATE_ENABLED`, which is still OFF), with a `judge_model` field
stamped per verdict so a fallback is *auditable* (mirrors the guardrail `decision_stage`
audit pattern, `services/guardrails.py`). The **cert** stays single-model (D1/D2). This is
the user's idea, re-homed where FR-8 doesn't forbid it and where external best practice
endorses it (provider-rotation for outages). *Stresses:* ⚠️ Ask-first — new fallback
abstraction on the judge seam ⇒ **needs an ADR**. *What breaks:* scope — this is a
production-hardening feature, not an FR-9 closer; doing it *instead of* D1 leaves the cert
blocked. *Serves Goal B only.*

**D5 — Switch the cert model to glm-5.1 (litellm-mapped, known-good path).** P7: glm-5.1
is the profile-set default, mapped natively by litellm (no direct adapter, no thinking-mode
stall class). Re-cert on glm-5.1 instead of glm-5.2. *Stresses:* re-opens the FR-8 model
decision (decisions.md chose glm-5.2 deliberately) and the ADR-0018 "which model gates"
call ⇒ back to **sdd-spec**. *What breaks:* glm-5.1 is a *different, weaker* model — it may
not hold the TNR floor the way glm-5.2's run1 did (TNR 1.0); we'd be trading a reliability
problem for a possible accuracy regression, unmeasured. *needs-probe* (one glm-5.1 replay).
*Serves Goal A* but changes the certified artifact.

**D6 — Demand-side: shrink the live-call surface with a deterministic pre-pass +
committed-label replay (make most calls not happen).** Two moves: (a) the router/guardrail
cascade precedent (`components/router.py`, `services/guardrails.py` regex→classifier→LLM)
— a cheap deterministic pre-filter can't decide leakage (it's semantic, ADR-0018 rejected a
keyword whitelist), so this half **doesn't apply** here (honest: the judgment must stay with
the LLM). (b) The *useful* half: once 3 clean glm replays exist, **commit the labels** so
CI/repeat verification replays them offline (the `run_coach_calibration` pure core already
does this — `cert_from_labels` reads a committed boolean map with zero live calls). This
doesn't close FR-9 (you still need the 3 live runs once) but it means we **never re-run the
flaky live pass** for regression — the stall problem becomes a one-time cost. *Stresses:*
none. *What breaks:* nothing; this is do-regardless hygiene for *after* FR-9 clears.
*Serves Goal A's durability.*

---

## Dependency structure & the real decision

```
D0 (provenance stamp) ──┬─► D1 (harness retry-on-timeout) ──► FR-9 close ──► D6 (commit labels)
   [do regardless]      ├─► D2 (intersection denominator)  ──┘
                        └─► D3 (httpx timeout split) ── helps D1
D4 (prod fallback chain, ADR) ── independent, Goal B, behind the OFF flag
D5 (glm-5.1 swap) ── re-opens spec, Goal A-alt
```

- **D0 is blocking and non-optional** — a present provenance defect (already corrupted
  `run1`) outranks every capability. Do it first whatever else is picked.
- **The real fork is Goal A vs Goal B**, and they're not exclusive: **D1 (+D0, +D2 as the
  denominator rule)** is the minimal, single-model path to actually *close FR-9* — no ADR,
  script-layer only, follows the repo's own retry shape and the external "retry-same-model-
  first" consensus. **D4** is the user's fallback idea, valid but re-homed to *production*
  resilience (Goal B) where FR-8 doesn't apply — it needs an ADR and does **not** close the
  cert. Picking D4 *instead of* D1 leaves 3.9 blocked; picking it *after* is a clean
  follow-on.
- **D5** trades the reliability problem for an unmeasured accuracy risk (weaker model) and
  re-opens a settled decision — only if D1 can't tame the stalls.

**Hypotheses for the lead (D0+D1+D2):**
- *Works because* — the stalls are intermittent (P8), so a per-attempt timeout + one retry
  turns "a different row abstains each run" into "almost every row scores", giving the full
  35-row denominator FR-9 wants; and where a row still stalls twice, D2's intersection rule
  (spec-blessed by FR-11, P5) handles it honestly.
- *Safe because* — it's **single-model** (P2/P3 preserved: the cert stays glm-5.2-only, no
  mixed-judge matrix, FR-10 comparability intact), the evaluator is unchanged (P4), and the
  retry is idempotent (a judge scoring call has no side effects — the external idempotency
  caveat about "don't retry create_invoice" doesn't bind a read-only eval call).

---

## D7 — Re-cert on Opus-4.8 INSTEAD of glm-5.2 (user-requested, reverses a same-day decision)

**Framing correction (verified).** This is **against the current agreement**: decisions.md
(2026-07-06) records *"Re-cert model = `glm-5.2` … **chosen by the user over gpt-4o/Opus**"*
— Opus was already weighed and rejected. Revisiting is legitimate (the glm stalls are new
evidence), but this is a **decision reversal**, not a new option, so it routes back through
sdd-spec on the model choice (like D5).

| Fact (verified) | Implication for D7 |
|---|---|
| Opus-4.8 is **litellm-native** (`anthropic/claude-opus-4-8`, not `provider="direct"`) — `llm_config.py:82` | **Kills the stall class.** The stalls are specific to the glm *direct httpx adapter* + thinking mode; Opus rides the standard LiteLLM path. This is the real strength of the idea. |
| Opus **omitted `answer_leakage` on 4/22** cases under long reasoning; scored **0/5** on indirect leaks pre-v2 (ADR-0017) | **Not a free win.** Opus had its own judge-compliance issues on *this* judge. ADR-0017's rubric hardening + the un-buriable-field change targeted exactly that, but D7 needs a fresh Opus run to confirm the 4/22 omissions are gone. `needs-probe`. |
| `supports_temperature=False` for Opus-4.8 (`llm_config.py`) | Opus-4.8 **can't take `temperature=0`** — the FR-9 bar is defined as "**temperature-0** replays". Opus runs at its default temperature, so "temp-0 zero-flip" is not literally satisfiable; the stability bar would need re-interpretation (its own drift profile). A real spec wrinkle. |
| 3.9 REFUSE baseline was **gpt-4o**; FR-10 anchor holds the model constant | With Opus as cert model, the gpt-4o anchor still gives a same-family before/after — comparability is **preserved** (no worse than glm, arguably cleaner since Opus is reliable). |
| **The gpt-4o anchor on the fresh split is already PERFECT** (TNR 1.0 / TPR 1.0 / 0 abstain, 35/35) | **The sharpest observation:** a reliable reasoning model already clears the bar flawlessly on this split. If the goal is "a *reliable* model certs ENABLE", gpt-4o *already did* — the question is whether the certified judge must be glm-5.2 (a deliberate pick for cost/openness) or whether any reliable reasoning model suffices. |

**D7 tradeoffs.** *For:* removes the reliability problem at the root (no direct-adapter
stalls) → FR-9's 3 clean runs become easy; Opus is a strong reasoning judge. *Against:*
(a) reverses a same-day deliberate decision (needs the *why* — presumably cost/openness of
glm-5.2 is outweighed by reliability); (b) `temperature=False` breaks the literal "temp-0"
FR-9 wording — needs a spec amendment on what "zero-flip stability" means for a
non-temp-0 model; (c) Opus's 4/22 field-omission history on this judge is unverified
post-v2 — `needs-probe`; (d) **cost** — Opus-4.8 is materially pricier per call than
glm-5.2, and the coach leakage judge is a per-turn runtime cost if the gate ever flips.
*Stresses:* re-opens FR-8 + the decisions.md model choice ⇒ **sdd-spec**, likely a short
ADR documenting the reversal rationale.

**The under-asked question D7 surfaces:** *why does the certified judge have to be glm-5.2
at all?* If cost/open-weight was the reason (likely), that's a real constraint and Opus
trades it away. If it was arbitrary, the perfect gpt-4o anchor says the cheapest path to a
defensible ENABLE might be **cert on gpt-4o** (already done, already perfect) — no new runs,
no reliability problem, no cost premium over Opus. That belongs in the spec discussion.

### D7 PROBE RESULT (Opus-4.8 live on the fresh split, 2026-07-06)

Ran `MODEL_PROFILE_SET=all COACH_JUDGE_MODEL=claude-opus-4-8`. Partial (26/47 when sampled):
**25 tn / 1 abstain / 0 stalls / 0 timeouts.** Two verified findings:

1. **Opus does NOT stall** — the litellm-native path has none of the glm direct-adapter
   thinking-mode stall class (the D7 hypothesis, confirmed). This is the reliability win.
2. **BUT the ADR-0017 field-omission is REAL and reproduced** — R-CLEAN-13 abstained with
   `unparseable/incomplete verdict`: Opus emitted `{"answer_leakage": false, "rationale":
   "…≥2 live, so no leakage"}` — **correct leakage judgment** — but **omitted all six
   `*_pass` fields**, so strict `PedagogyVerdict.model_validate` rejected it (the 6 pass
   fields are REQUIRED, `components/schemas.py:277-282`). Under long reasoning Opus drops
   the pedagogy-axis fields.

**The key structural insight:** the **leakage cert reads ONLY `answer_leakage`**
(`run_coach_calibration.py:160,214`), yet a verdict is discarded for missing 12 pedagogy
fields the cert never uses. So Opus is being failed on fields irrelevant to the
certification. This is a **schema-strictness × verbose-model** mismatch, not an Opus
capability gap — Opus got the one field that matters right on the abstained row. It reframes
D7: Opus is *reliable* (no stalls) but needs either (a) a **leakage-only lenient parse** for
the cert path (accept a verdict that has `answer_leakage` even if pedagogy axes are absent —
mirrors how `leak_channel` is already soft-coerced so a cosmetic miss can't erase a correct
leak call), or (b) a max_tokens/prompt nudge so Opus stops truncating the schema. Option (a)
is the ADR-0017-consistent move and is small; it also would have salvaged glm's parse-class
abstains. **This is now the real D7 spec question**, not the temp-0 wrinkle alone.

### D8 — Re-cert on a SMALLER Claude judge (Haiku-4.5) to dodge Opus's verbosity

If Opus's *over-reasoning* is what drops schema fields, a compact-output model avoids the
cause. Grounding (verified):

| Fact | Implication |
|---|---|
| `claude-haiku-4-5` reachable via `all` set, **`provider=litellm`** (`llm_config.py`) | litellm-native → **no glm stall class** (same reliability win as Opus). |
| `claude-haiku-4-5` **`supports_temperature=True`** | **Satisfies FR-9's literal "temperature-0" bar** — the wrinkle that blocks Opus (`supports_temperature=False`) does not apply. Cleaner than D7. |
| Haiku is the **certified code-reviewer judge**: TPR=1.0/TNR=1.0 (n=20), `claude-haiku-4-5-20251001` (`unified_context_routed_reviewer.plan.md:520`) | **Haiku-as-structured-judge is a proven in-repo pattern**, not a gamble — it reliably emits strict structured verdicts, which is exactly the compliance Opus lacked. |
| `fast` tier, cheapest candidate | Addresses the likely **cost/open-weight** reason glm-5.2 was picked — no Opus cost premium. |
| Self-enhancement-bias caveat (`harness_adoption_critical_review`, arXiv 2606.19544): a Claude judge scoring Claude arms | Note for the spec, **not a blocker** here — binary leakage classification is the scoped-task case; the coach-under-judgement isn't necessarily Claude. |
| **No `claude-sonnet-5` in the registry** — the Sonnet present is `claude-sonnet-4-6` (also litellm, `supports_temp=True`, `capable` tier) | "Sonnet 5" isn't wired; the real candidates are **Haiku-4.5** (fast/cheap) and **Sonnet-4-6** (capable/mid). |

**D8 vs D7:** Haiku keeps Opus's reliability win, *adds* temp-0 capability (no FR-9 wording
amendment), *removes* the cost premium, and its structured-output compliance is
already-certified — likely dodging the R-CLEAN-13 field-omission entirely. Risk: a smaller
model *may* not hold the TNR floor as firmly on the hard clean rows (R-CLEAN-24/26/29). One
probe run settles it. `needs-probe`. Sonnet-4-6 is the middle option if Haiku under-holds.

### D8 PROBE RESULT (Haiku-4.5 live, 2026-07-06) — REFUSE, the risk materialized

`cert.model=claude-haiku-4-5`, verdict **REFUSE**: **TNR 0.8571** (5 FP / 35 clean), TPR 1.0,
0 abstain, 0 stalls. The reliability/compliance hypothesis held (no field-omission, no
stalls, temp-0 fine) — **but Haiku isn't capable enough to apply the v2 carve-out**. Its 5
FPs (R-CLEAN-09/30/32/34/35) are on **different rows than the known-hard watch-list**
{24,26,29} — rows Opus, gpt-4o, and glm all passed. It regresses into the **OVERFLAG-1
failure mode ADR-0018 exists to fix**: reads mechanism-teaching as item-collapse. This
confirms the leakage judgment is **capacity-sensitive** (consistent with ADR-0017): the
carve-out needs a strong reasoner, so the trade is **Opus's verbosity vs Haiku's
over-flagging** — and Haiku's costs the whole TNR floor. **D8 rejected as the cert model.**

### Four-way probe scoreboard (all on the frozen 47-row fresh split, v2 rubric)

| Model | Provider | temp-0? | TNR | TPR | abstain | stalls | verdict | Blocker |
|---|---|---|---|---|---|---|---|---|
| **gpt-4o** | litellm | ✓ | **1.000** (35/35) | 1.0 | 0 | none | **ENABLE** | none — clean |
| **Opus-4.8** | litellm | ✗ | **1.000** (34/34) | 1.0 | 1 (schema) | none | **ENABLE** | temp-0 wording + 1 verbosity-abstain |
| **glm-5.2** | direct | ✓ | 1.000 (33) / 0.967 (30) | 1.0 | 2–5 | **YES** | ENABLE* | intermittent stalls (the whole problem) |
| **Haiku-4.5** | litellm | ✓ | **0.857** (30/35) | 1.0 | 0 | none | **REFUSE** | not capable enough (OVERFLAG-1) |

**Conclusion across probes:** reliability and capability trade off. The only candidate that
is **reliable AND capable AND temp-0** on this split is **gpt-4o** — and its run is already
banked (perfect). Opus is capable+reliable but not temp-0 (needs an FR-9 amendment). Haiku
is reliable+temp-0 but not capable. glm-5.2 is capable+temp-0 but not reliable (stalls).
This strongly reframes the model choice back toward **gpt-4o as the cert** (the one that
clears every axis with zero new work), unless open-weight/cost is a hard requirement that
excludes it.

### D9 PROBE RESULT (Sonnet-4-6 live, 2026-07-06) — REFUSE, worst of the reliable models

`cert.model=claude-sonnet-4-6`, verdict **REFUSE**, and it fails on THREE axes at once —
strictly worse than Opus:
- **TNR 0.9143 FAIL** (3 FP: R-CLEAN-05/09/25) — partial OVERFLAG-1 (better than Haiku's
  0.857, still under floor).
- **TPR 0.9091 — MISSED A LEAK** (`R-LEAK-07: fn`). **The only model in the whole
  exploration to drop a real leak** (all others were TPR 1.0). A leak detector that misses
  leaks is the worst failure mode — worse than over-flagging.
- **Stalled** (`R-LEAK-03: TIMEOUT >120s`) — so stalls are **not purely a glm/direct-adapter
  thing**; a Claude litellm model hung too, though far rarer than glm.

**D9 rejected.** Sonnet-4-6 is worse than Opus on every axis (lower TNR, missed a leak Opus
caught, and stalled where Opus didn't). It confirms the capability gradient: the carve-out
needs a *strong* reasoner, and only the largest models (gpt-4o, Opus) clear TNR while
holding TPR=1.0.

### FINAL five-way scoreboard (frozen 47-row fresh split, v2 rubric)

| Model | Open-wt | Reliable | temp-0 | **TNR** | **TPR** | abstain | Verdict |
|---|---|---|---|---|---|---|---|
| **gpt-4o** | ✗ | ✓ | ✓ | **1.000** | **1.0** | 0 | **ENABLE** ✅ clean on every axis |
| **Opus-4.8** | ✗ | ✓ | ✗ | 1.000 | 1.0 | 1 | ENABLE (needs temp-0 amendment + lenient parse) |
| glm-5.2 | ✓ | ✗ stalls | ✓ | 1.0/0.97 | 1.0 | 2–5 | ENABLE* unstable |
| Sonnet-4-6 | ✗ | ~ (1 stall) | ✓ | 0.914 | **0.909 missed leak** | 1 | **REFUSE** |
| Haiku-4.5 | ✗ | ✓ | ✓ | **0.857** | 1.0 | 0 | **REFUSE** |

**Decision-ready.** Capability is the binding constraint on TNR: only gpt-4o and Opus (the
two strongest) hold TNR≥0.95 with TPR=1.0. Of those, **gpt-4o is clean on every axis and its
perfect run is already banked** — the cheapest defensible ENABLE. The open-weight desire
(glm-5.2) collides with its provider-stall reliability. **The empirical fork is now just:
gpt-4o (proprietary, done, perfect) vs is-open-weight-a-hard-requirement** — if yes, the
path is fix-glm-reliability (D1 harness retry-on-timeout), not a model swap (all the
smaller/open alternatives either over-flag or stall).

### External research integration ([docs/research/eng-coach-judge/](../research/eng-coach-judge/), 2026-07-06)

An independent research pass (JudgeBench, C2-Faith, "Play Favorites" bias study, MoE
determinism literature) **converges with the five-probe sweep and reframes the fork toward
fixing GLM's HOSTING, not swapping models:**

- **The stalls are confirmed as Z.ai serving-layer/capacity, NOT the model** (Z.ai GitHub
  issue #83: ~2 days near-total outage, "capacity issue, not per-account"). **Re-hosting
  GLM-5.2 on Fireworks AI** (own-engine, uptime SLA, reference-validated GLM benchmarks,
  MIT license) is presented as the *highest-probability* path — GLM already cleared the bar
  (TNR 1.00/0.97), so "fix hosting" beats "re-validate a fresh model from scratch."
- **Capability-is-binding is corroborated:** JudgeBench is hard (GPT-4o vanilla 50.9% ≈
  random; reasoning models dominate, o3-mini 80.86, LN-Ultra 79.14, DeepSeek-R1 73.14). And
  it **predicts our exact failures**: high-recall reasoning models can hide high FPR
  (DeepSeek-V3.1: 94.7% detection / 29.6% FPR = the OVERFLAG-1 pattern Haiku/Sonnet showed).
- **temp-0 zero-flip is reframed as a SERVING problem** (MoE batch-nondeterminism on shared
  endpoints), fixable via dedicated/self-hosted batch-invariant kernels — i.e. the
  R-CLEAN-29 run-to-run flip is partly infrastructure, not just model drift.
- **Cross-family bias:** if the coach is GPT/Claude-generated, a proprietary GPT/Claude
  judge is self-preference-biased; an open-weight judge (GLM/DeepSeek/Qwen) is cross-family
  *for free*. This is a real mark AGAINST gpt-4o/gpt-5/Opus as the long-term judge.
- **Research's ranked open-weight shortlist:** (1) GLM-5.2 on Fireworks, (2) DeepSeek-R1 or
  LN-Ultra (cross-family reasoning), (3) Qwen3-235B (Apache-2.0, best strict-JSON). GPT-4o
  retained only as a proven tie-break/disagreement-labeling anchor, not the primary judge.

**Net effect on the decision.** The research argues the model-swap search (Opus→Haiku→
Sonnet→gpt-5) is the *lower*-value path — every swap needs a fresh cert — while GLM already
passed and is blocked only by a *fixable hosting* problem. So the two live directions are
now: **(A) re-host GLM-5.2 on Fireworks** (keeps the open-weight judge that already works),
or **(B) cert on gpt-4o** (proprietary, done, but self-preference-biased + not the research's
recommendation). gpt-5 is a probe the user requested but the research does not endorse
(proprietary, `supports_temp=False`, same-family bias).

### API-host comparison — Fireworks vs Together vs OpenRouter (research, 2026-07-06)

Constraint confirmed: **no self-hosting infra needed** — all three are API-hosted
(OpenAI-compatible `/chat/completions`), and the existing `glm_direct.py` already takes a
`base_url` (Z.ai is just the default), so switching host = base_url + key env swap.

| Axis | **Fireworks AI** | **Together AI** | **OpenRouter** |
|---|---|---|---|
| Architecture | Direct host (own GPUs) | Direct host (own GPUs) | **Router** (routes to other providers) |
| Model breadth | ~202 (owned) | ~200+ (owned) | **~303** (routed, widest) |
| GLM-5.2 | ✓ **day-zero, own engine** | ✓ | ✓ (~29 upstream listings) |
| Pricing model | per-token, ZDR, **50% cached-input discount**, 6000 RPM ceiling | per-token | per-token + **5.5% platform fee** (no model markup) |
| GLM cost (per verdict ~2–3k in) | ~$0.005–0.02 | ~similar | routed price + 5.5% |
| **Quantization control** | **own engine, reference-validated** (91.4% vs 91.2%) — pin full precision | direct, characterizable | **RISK: routes to whichever backend (may be fp4/fp8)** → drift |
| **Dedicated endpoint** (determinism) | ✓ **on-demand dedicated** (single-tenant, fixed-batch) | ✓ dedicated SLAs | ✗ (shared, provider-of-the-moment) |
| **JSON-schema / grammar** | ✓ **JSON-schema + BNF grammar mode** (forces required fields → kills the abstain-on-omission problem) | ✓ schema modes | varies by upstream |

**Read for THIS judge (temp-0 + precise decisions + no infra):**
- **Fireworks — best for the judge.** Own-engine (no quant surprise), **dedicated endpoints**
  for the MoE temp-0/zero-flip risk, and **grammar-constrained JSON** that structurally
  prevents the Opus/glm field-omission abstains. The research already singled it out for the
  *judge* specifically. Cheapest-ish on GLM + cached-input discount. This is the flexibility
  that matters *here* (determinism + schema), even if not the widest catalog.
- **OpenRouter — best for breadth/exploration, WORST for the gating judge.** ~303 models
  through one key is ideal for *trying* candidates (DeepSeek-R1, Qwen3, LN-Ultra) cheaply —
  but as a router it may silently land on an fp4 backend and has no dedicated endpoint, i.e.
  the exact quantization-drift + shared-batch-nondeterminism the research warns flips a
  borderline TNR run. Fine for telemetry / candidate-screening, not the certified verdict.
- **Together — solid middle.** Direct host, dedicated SLAs, ~200 models; less
  judge-specifically characterized than Fireworks but a fine mainstream direct-host option.

**Synthesis for "flexibility, breadth, depth, economical":** they optimize different axes —
**OpenRouter wins breadth/flexibility-to-explore + one-key economy for screening**;
**Fireworks wins depth-for-the-judge** (determinism controls + grammar JSON + reference
precision) at comparable per-token cost. The natural play is **both**: OpenRouter to cheaply
screen the research's cross-family candidates (DeepSeek-R1 / Qwen3-235B / LN-Ultra) on the
47-row set, then run the *certified* verdict on **Fireworks** (dedicated + grammar) for the
model that wins. Sources:
[pricepertoken](https://pricepertoken.com/endpoints/compare/fireworks-vs-together) ·
[Fireworks GLM-5.2 day-zero](https://fireworks.ai/blog/glm-5p2) ·
[Fireworks structured-output docs](https://docs.fireworks.ai/serverless/pricing) ·
[OpenModels/host comparison](https://blog.alephant.io/openmodels-vs-openrouter-together-fireworks-deepinfra-2026/).

---

**External sources.** [FutureAGI — LLM fallback strategy field guide](https://futureagi.com/blog/what-is-llm-fallback-strategy-2026/) ·
[Maxim — retries/fallbacks/circuit-breakers](https://www.getmaxim.ai/articles/retries-fallbacks-and-circuit-breakers-in-llm-apps-a-production-guide/) ·
[Judge Reliability Harness (arXiv 2603.05399)](https://arxiv.org/html/2603.05399v1) ·
[CallSphere — retry backoff+jitter with tenacity](https://callsphere.ai/blog/retry-strategies-llm-api-calls-exponential-backoff-jitter-tenacity).
Consensus: for **transient/timeout** failures, retry the **same** model first (per-attempt
timeout, capped attempts, backoff+jitter); reserve **different-model** fallback for full
provider outage; and **never** swap judge models mid-evaluation (it changes what the score
means).

---

## Stage-1 HUMAN GATE decision (2026-07-06) — advance to sdd-spec

Decided after five live model probes + external judge research + host research:

- **Judge model:** **GLM-5.2** as the lead certified judge (open-weight/MIT, cross-family
  vs a GPT/Claude coach, already cleared quality: TNR 1.00/0.97, TPR 1.0), **plus screen**
  the research's cross-family reasoning candidates — **DeepSeek-R1, Qwen3-235B, LN-Ultra**
  (whichever Fireworks actually serves) — on the frozen 47-row set as alternatives /
  fallback. (Opus/Sonnet/Haiku empirically rejected: over-flag TNR or miss a leak.)
- **Host:** **Fireworks AI for BOTH screening and the certified verdict** — one provider/key,
  consistent full-precision serving (no router fp4 drift), **dedicated endpoint** for the
  temp-0/zero-flip MoE determinism risk, and **grammar-constrained JSON** to structurally
  prevent the field-omission abstains seen on Opus/glm. Caveat to carry into the spec:
  **verify Fireworks' catalog** — LN-Ultra may not be served there; screen only what it hosts.
- **Enabling change:** `glm_direct.py` already accepts `base_url` (Z.ai is just the default);
  make **host/base_url/key a config seam** (env-driven, registry-wired, H2-clean) so
  Fireworks — or any OpenAI-compatible host — is a config value, not code. Then re-run the
  **unchanged FR-9 cert** (≥3 temp-0 replays, every one TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75,
  zero-flip) on the frozen `coach_recert_split_v1.json`.
- **Do-regardless hygiene (D0), carried forward:** stamp the **actual judge model into the
  labels / cert** (the run-time-env `model` field already mislabeled run1/run2 as gpt-4o);
  and consider **grammar-JSON as the leakage-only-lenient-parse substitute** (it forces the
  required fields, so no schema-omission abstain).
- **⚠️ Ask-first / ADR at spec time:** the host-config seam on the trust-boundary adapter +
  the model/host reversal from decisions.md's glm-5.2/Z.ai choice → needs an ADR.
- **Blocked on:** a **Fireworks API key** (external; the cert can't run without it).

**Next:** → **sdd-spec** with this direction. Advance when the key is available (or spec the
host-config seam + screening harness now, and gate the live runs on the key).
