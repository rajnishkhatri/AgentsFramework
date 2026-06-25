# Model Selection Pipeline — End-to-End Design & Evaluation

**Date:** 2026-06-25 (rev 2 — second critical pass, all seams re-read from live code)
**Scope:** how a model is chosen and executed for every agent step, across all
layers — UI → wire → graph state → router → LLM execution → litellm dispatch —
plus the A/B harness's parallel pin path. Written from the current code (commit
`771933b`) to evaluate the design for latent issues before the full offline A/B
sweep.

**Rev-2 method:** every claim below was re-verified against the actual source at
the exact line — `frontend/lib/translators/ui_input_to_agent_request.ts:49-58`,
`agent_ui_adapter/adapters/runtime/langgraph_runtime.py:146-232`,
`orchestration/react_loop.py:1007-1018 / 1597 / 1632-1642 / 2151-2183`,
`components/router.py:309-403`, `services/llm_config.py:218-297`,
`components/routing_config.py:15-29`. The decision (this session) is **reject the
proposed default-model changes, keep current defaults, then fix F1 + F2**; this
review is the gate before those fixes. Three findings are NEW vs rev 1 (F8/F9/F10).

---

## 1. The end-to-end path (happy path, one step)

```
USER picks model in Composer dropdown
  │  ChatShell.selectedModel  (state; seeded by ?model= URL or dropdown)
  ▼
uiInputToAgentRequest()  frontend/lib/translators/ui_input_to_agent_request.ts:58
  │  rides input.pinned_model = <name>   ("Auto"/undefined → omit → no pin)
  ▼
RunCreateRequest.input  (open dict; NO wire-schema change, .strict() intact)
  ▼
langgraph_runtime  spreads run input into initial graph state
  │  state["pinned_model"] = <name>
  ▼
route node (react_loop.py)  select_model(..., pinned_model=state["pinned_model"])
  │  → (profile, reason)
  │  WRITES state["selected_model"] = profile.name      (:1597)
  │        state["routing_reason"]  = reason
  │        state["model_history"]  += {step, model, tier, reason}
  ▼
call_llm_node (react_loop.py:1632-1642)
  │  model_name = state.get("selected_model", agent_config.default_model)   (:1637)
  │  try:    profile = llm_service.get_profile(model_name)                  (:1640)
  │  except KeyError:  profile = agent_config.models[0]  (or default_fast)  (:1642)
  │       ▲ SILENT divergence point — see F8: if selected_model names a
  │         profile NOT in LLMService._profiles, the EXECUTED model is
  │         models[0], but the model_used carrier still reads selected_model.
  ▼
LLMService.get_llm(profile)  services/llm_config.py:267-297
  │  kwargs = {model: profile.litellm_id, max_tokens: profile.max_output_tokens,
  │            streaming: True}
  │  if profile.supports_temperature: kwargs["temperature"] = 0   (:295-296)
  │  return ChatLiteLLM(**kwargs)
  ▼
provider call (litellm dispatches by litellm_id PREFIX: openai/ anthropic/ deepseek/)
  │  resp = await llm.ainvoke(...)
  │  response_text(resp)  services/llm_config.py:218-251 — collapses provider
  │       content shapes to answer text; DROPS thinking blocks via AIMessage.text.
  │       ▲ F9: an all-thinking response (no text block) → "" even with tokens>0.
  ▼
STEP_EXECUTED carrier records model=state["selected_model"]  (react_loop.py:2183)
  (Recording pillar — the model the ROUTER chose, NOT necessarily get_llm's profile)
```

**Verified resume-leg invariant (langgraph_runtime.py:226-232):** on a non-resume
run the runtime spreads `{**graph_input, ...}` into `stream_input`, so
`input.pinned_model` → `state["pinned_model"]`. On resume, `stream_input = None`
(:230) and the **checkpoint** already carries `pinned_model` — so a turn-1 pin
persists across every later turn of the thread with no re-seed. Confirmed, not
assumed.

**Two distinct state keys (deliberate, easy to confuse):**
- `pinned_model` — the **input** pin (read by the router). Set once from the UI/
  harness; never written back by the graph.
- `selected_model` — the router's **per-step output** (write-back at :1597); what
  `call_llm` executes and what the runtime reads back for UI display
  (`langgraph_runtime.py:715`). Reusing `selected_model` as the pin input would
  make step-2+ misread step-1's routed model as a pin — which is exactly the
  bug the offline harness hit when it seeded the wrong key (fixed `771933b`).

---

## 2. The router decision order (`select_model`, components/router.py:309)

First match wins, top to bottom:

| # | Branch | Condition | Picks | Reason carrier |
|---|---|---|---|---|
| 1 | budget pressure | cost_fraction ≥ budget_downgrade_threshold | fast tier | `budget-downgrade` |
| 1.5 | **user pin** | `pinned_model` set & resolvable | the pinned profile | `user-pinned:<name>` |
| — | pin miss | `pinned_model` set, NOT in registry | (falls through) | prefix `pin-miss:<name>->auto` |
| 2 | retryable error | last_error_type == retryable | same model as last | `retry-after-backoff` |
| 3 | escalation | consecutive_errors ≥ N & budget left | reasoning tier (→ capable fallback) | `escalate-after-N-failures` |
| 4 | first step | step_count == 0 | capable tier | `capable-for-planning` |
| 5 | steady state | (default) | fast tier | `steady-state-fast` |

**Design properties that are CORRECT and worth preserving:**
- **Pin is placed after budget (1) but before tiers (2-5):** a pin can't blow the
  cost cap, but otherwise overrides Auto. Sound.
- **Pin-miss is auditable, never silent:** an unresolvable pin records
  `pin-miss:<name>->auto | <branch>` rather than masquerading as an Auto choice.
  Strong governance posture.
- **Escalation counts capable+reasoning** against the budget, so escalations stay
  bounded once the escalated tier is `reasoning` (Opus).
- **First-match on registry ORDER is the safety contract:** fast→[0 fast],
  capable→[first capable], reasoning→[first reasoning]. The registry order per set
  encodes the Auto stack.

---

## 3. The registry (services/llm_config.py)

`build_model_registry(set) -> (models, default_model)`; sets:

| set | order (first fast / capable / reasoning) | default | Auto-safe? |
|---|---|---|---|
| openai | gpt-4o-mini / gpt-4o / — (no reasoning) | gpt-4o-mini | yes (prod default) |
| anthropic | haiku-4-5 / sonnet-4-6 / opus-4-8 | haiku-4-5 | yes |
| deepseek | v4-flash / v4-flash-capable / v4-pro | v4-flash | yes |
| **all** | gpt-4o-mini / gpt-4o / **opus-4-8** | gpt-4o-mini | **NO — pin-only** |

- Pins resolve by exact `name` (`_pick_profile_by_name`); a pin only works if the
  model is IN the active set. The default `openai` set has 2 models, so pinning a
  Claude/DeepSeek model on it MISSES → the offline harness must build pinned arms
  from `all` (fixed `771933b`).
- `all` is a UNION for the UI dropdown / pin sweeps. Its first reasoning is
  `opus-4-8`, so an **Auto** run on `all` escalates into Opus — which is why the
  comment says "PIN-ONLY, never route Auto here."

---

## 4. Findings (evaluation)

### F1 — RoutingConfig.default_model ignores MODEL_PROFILE_SET (LATENT, low severity)
`RoutingConfig.default_model` has `default_factory=_default_model_name`, which
calls `build_model_registry()` with **no arg** → always the `openai` default
(`gpt-4o-mini`). `RoutingConfig()` is constructed with no override
(`run_goaljudge_synthetic_batch.py:121`; composition does not pass one either).
So under `anthropic`/`deepseek`, `routing_config.default_model` is STILL
`gpt-4o-mini` — a model not in those sets.
- **Why it doesn't bite today:** `default_name` is only used in `_fallback_profile`
  / `_select_same_model`, and `_fallback_profile` returns `agent_config.models[0]`
  (the set's true fast default) when `default_name` isn't found. Plus Branches 1/5
  reach `_fallback_profile` only if `_pick_profile_by_tier(fast)` returns None —
  which never happens for a well-formed set. So the wrong value is masked.
- **When it WOULD bite:** any set whose order violates "fast model first," or a
  future code path that trusts `routing_config.default_model` directly.
- **Fix (cheap, recommended):** pass `default_model` into `RoutingConfig(...)` at
  both construction sites from the same `build_model_registry(set)` call that
  builds `AgentConfig`, OR have `_default_model_name` read `MODEL_PROFILE_SET`.
  Add a test: under `anthropic`, `routing_config.default_model == claude-haiku-4-5`.

### F2 — `all` set + Auto = Opus escalation (BY DESIGN, needs a guardrail in the harness)
A pinned arm on `all` is safe (pin overrides routing). But a **set arm** must
never use `all` for Auto (it would escalate into Opus on failures, skewing cost).
- **Status:** correct by documentation, not enforced. The offline harness's
  set-arm path uses `--candidate-set {openai,anthropic,deepseek}` — fine. But
  nothing PREVENTS `--candidate-set all`.
- **Fix (cheap):** reject `--baseline-set all` / `--candidate-set all` in the
  harness arg validation (set arms are Auto; `all` is pin-only).

### F3 — empty-output failure classes (FIXED, verify in A3)
Two classes, both fixed in `services/llm_config.py` (`c70ffa9`):
(a) `temperature=0` rejected by opus-4-8/gpt-5/gpt-5-mini → `supports_temperature`;
(b) reasoning-budget exhaustion (deepseek-flash at 4096) → `max_output_tokens=8192`.
- **Residual risk:** even at 8192 a pathological prompt could exhaust budget. The
  analyzer should treat `reasoning≈max_output_tokens && text==""` as an explicit
  "budget-exhausted" outcome (Phase A2 guard), not a silent empty/PROMOTE.

### F4 — analyzer false-PROMOTE on empty output (OPEN, Phase A2)
`diff_summaries` defaults to PROMOTE on cost when the phase table is empty (corpus
rows carry no `want_*`). An empty $0 answer then reads as PROMOTE. Add an
empty-output / zero-token ⇒ HOLD guard before the full sweep.

### F5 — GoalJudge model is shared infra across arms (HANDLED)
Every arm also runs the GoalJudge evaluator on the capable-tier model (gpt-4o
under openai/all). The integrity check now allows the first-capable model in each
arm's expected set (`771933b`), so it's not flagged as contamination. Document
that the judge's cost is included in per-arm cost (it runs once per case on every
arm equally, so it's a constant offset — fair for comparison, but note it).

### F6 — token/cost carrier fidelity (VERIFIED locally, Langfuse weak)
Cost/tokens come from the STEP_EXECUTED `cost_usd`/`usage` carriers in the local
black-box recordings — confirmed flowing in A0. The Langfuse trace-join has the
known Hermes-path 404 gap, so per-phase *reasoning-trace* audit is weaker offline;
the A/B verdict does not depend on it. (Deployed Phase B closes this if needed.)

### F7 — pin honored only at the route node, re-evaluated each step (CORRECT, note it)
The router runs EVERY step and re-reads `pinned_model` from state, so the pin
persists across all steps of a run (state carries it). A pinned arm therefore runs
the pinned model on every step EXCEPT where Branch 1 (budget) preempts it — a pin
does not override the budget cap. For A/B cost measurement this means a pinned
expensive model can still downgrade under budget pressure; surface this in the
report (it's correct behavior, but explains any stray fast-tier steps).

### F8 — `call_llm` execute-vs-record divergence on a missing profile (NEW, LATENT)
The route node writes `state["selected_model"] = profile.name` (:1597), and
`call_llm_node` reads it back (:1637) then resolves the profile via
`llm_service.get_profile(model_name)`. On `KeyError` it falls to
`agent_config.models[0]` (:1642). But the per-step Recording carrier
(`model=state.get("selected_model","")` at :2151/:2168/:2183) reports the **name
the router wrote**, NOT the profile `get_llm` actually ran.
- **The honesty gap:** if `selected_model` ever holds a name NOT in
  `LLMService._profiles` (keyed by `name` over `config.models`), the agent
  EXECUTES `models[0]` while the trace CLAIMS the routed name. The A/B integrity
  guard (which trusts `model_used`) would read a *clean* match while a different
  model actually answered — a false-clean, the worst kind for an A/B.
- **Why it doesn't bite today:** every router branch returns a profile from
  `agent_config.models`, and `LLMService` is built from that same list — so the
  written name is always in `_profiles`. The two are the same object graph.
- **When it WOULD bite:** a path that seeds `selected_model` DIRECTLY into input
  (the OLD harness bug's key) on a narrow set → `get_profile` KeyError → silently
  runs `models[0]` while the carrier shows the seeded name. The fixed harness uses
  `pinned_model` (resolved by the router against `agent_config.models`), so it's
  safe — this documents WHY the input key choice is load-bearing for *honesty*,
  not just routing.
- **Fix (cheap, pair with F1):** in `call_llm`'s `except KeyError`, set
  `selected_model` to the actually-run profile name before the STEP carrier
  emits (or record `model_resolution=fallback:<requested>-><models[0]>`) so
  execute and record can never silently disagree. Test: seed
  `selected_model="nonexistent"`, assert the STEP carrier names `models[0]`.

### F9 — third empty-output class: all-thinking response (NEW, feeds A2 guard)
F3 fixed two empty-output classes (temperature reject, budget exhaustion). A
THIRD exists at the `response_text` seam (`services/llm_config.py:218-251`): it
collapses provider content via `AIMessage(content=...).text`, which **joins text
blocks and DROPS thinking blocks**. A reasoning model that spends its whole (even
8192-token) budget on `thinking` and emits NO `text` block returns `""` with
**non-zero tokens and non-zero cost**.
- **Distinct from F3:** F3's budget class is "ran out of room"; F9 is "produced
  output, but all of it was thinking." Both look like empty answers, but F9 has
  tokens>0 and cost>0 — a zero-token guard misses it.
- **Implication for A2 (analyzer empty-output⇒HOLD guard):** trip on
  `answer=="" REGARDLESS of token count`. Distinguish `answer=="" && tokens>0`
  ("all-thinking / no-answer") from `answer=="" && tokens==0` ("budget/silent") —
  both ⇒ HOLD, but legible in the report. Sharpens F4.

### F10 — `RoutingConfig.default_model` = two unsynchronized registry reads (NEW, refines F1)
`components/routing_config.py:15-29`: the `default_factory` calls
`build_model_registry()` with **no arg**, so it returns the *openai* default
(`gpt-4o-mini`) regardless of the active `MODEL_PROFILE_SET`. Rev 1 (F1) framed
this as "stale literal"; the precise statement is that `routing_config.default_model`
and `agent_config.models` come from **two independent registry reads** that can
disagree — the field always reads the openai default, `AgentConfig` reads the env
set. Same fix as F1; the sharper test: under `MODEL_PROFILE_SET=anthropic`, assert
BOTH `agent_config.default_model` AND `routing_config.default_model` ==
`claude-haiku-4-5` (proving ONE registry call, not two).

---

## 4b. Decision (this session): defaults stay as-is

The proposed per-set default changes (openai→gpt-5-mini, anthropic→haiku-4-5,
deepseek→v4-pro) were **rejected** after the cost/benefit pass:
- The "default" slot is the **fast steady-state** model (runs on most turns), so
  cost-sensitivity is highest there. gpt-5-mini (~$0.69 blended) is ~2.6× gpt-4o-
  mini (~$0.26); deepseek-v4-pro as default would pay 3× flash on every routine
  turn and invert the proven "Flash-everywhere, Pro-on-escalation" design.
- The user's real insight (fast tier spans a 14× cost range; gpt-5-mini ≈
  deepseek-pro blended) is a **tier-fill / which-set-to-promote** judgment — what
  the A/B is FOR — NOT a default-slot change.
- **Therefore:** run the A/B on the CURRENT defaults (unbiased baseline), measure
  quality-per-dollar, then set defaults from evidence. Non-binding, revisitable
  post-A/B. The set-arm comparison (`--candidate-set deepseek` vs `openai`)
  directly answers "is deepseek the cheapest viable Auto stack?"

---

## 5. Severity summary

| # | Finding | Severity | Action |
|---|---|---|---|
| F1 | RoutingConfig.default_model stale vs set | Low (masked) | **FIXED** — factory reads `MODEL_PROFILE_SET` + explicit pass at builders |
| F2 | `all` set arm would Auto-escalate to Opus | Low (doc-only today) | **FIXED** — harness rejects `--*-set all` (non-zero exit) |
| F3 | empty-output (temp + budget) | **was High** | FIXED `c70ffa9`; verify A3 |
| F4 | analyzer false-PROMOTE on empty | Medium | Phase A2 guard (sharpened by F9) |
| F5 | judge model shared across arms | Handled | Document cost offset |
| F6 | Langfuse join weak offline | Low | Phase B if trace audit needed |
| F7 | pin preempted by budget | None (correct) | Surface in report |
| F8 | call_llm execute-vs-record divergence on missing profile | Low (latent, honesty) | **FIXED** — fallback emits `model_resolution_fallback` carrier + truths-up `selected_model` channel |
| F9 | 3rd empty class: all-thinking (tokens>0, text="") | Low→feeds A2 | A2 guard trips on `text==""` regardless of tokens |
| F10 | RoutingConfig.default_model = 2 unsynced registry reads | Low (= F1 root) | **FIXED** with F1 (one registry read; test asserts both defaults track set) |

**Net (rev 2):** the model-selection design is sound — the pin/Auto/escalation
ordering, the pin-miss honesty (Branch 1.5 + `_with_pin_miss`), the registry-order
safety contract, and the resume-leg pin-persistence are all CORRECT and verified
against live code. The real defects were the empty-output classes (F3, fixed) and
the harness key/scope bugs (fixed `771933b`). The three NEW findings are all LOW /
latent: F8 (execute-vs-record honesty edge), F9 (a third empty-output shape the A2
guard must catch), F10 (refines F1's root cause). **Decided this session: keep
current defaults, then do F1+F2 (both cheap).** F8 folds cheaply into the F1 change;
F9 folds into the A2 guard. None blocks the corpus conversion (A1/A3); F1/F2/F8 are
correctness/honesty hardening best done before the full sweep so the integrity
guard can't be fooled.

---

## 6. Why the planning pipeline can't measure model-A/B quality (A3a finding)

**Status:** empirically confirmed 2026-06-25 by the A3a smoke (run
`a3a_smoke_073729`, `gpt-4o-mini` vs `claude-haiku-4-5`, 4-row compaction corpus).
The run exited 0 with **VERDICT: PROMOTE** — and that verdict is **hollow**. This
section records *why*, so no one reads a planning-corpus PROMOTE as a model-quality
signal, and lists what the planning pipeline would need to actually serve as an
A/B instrument.

### 6.1 What A3a actually showed
- **The pipeline is mechanically sound** (this was the smoke's real job): drive →
  pin → score → cost → artifacts, exit 0. Integrity HONEST and clean — baseline
  ran `gpt-4o-mini`, candidate ran `claude-haiku-4-5` (`routing_reason:
  user-pinned:claude-haiku-4-5`), 0 mismatches, 4/4 rows scored. F5 handled (the
  GoalJudge `gpt-4o` shared-infra model allowed in both arms' expected sets). Cost
  plumbing real: candidate **12.4×** baseline ($0.038 vs $0.003/task).
- **The verdict is hollow for THREE structural reasons** (below). The PROMOTE
  reflects "both arms were equally NOT measured," not "candidate ≥ baseline on
  quality."

### 6.2 Root causes — why a planning verdict ≠ a model-quality verdict

**RC1 — `score_run` measures planning-CONTROL behavior, not answer QUALITY.**
`analyze_planning_traces.score_run` credits a "hit" only when a control signal
fires correctly for its phase: depth selection, replan count, reflexion re-entry,
escalation/fan-out confusion matrix, compaction fold. These are properties of the
*orchestration loop* (did the router/planner do the right structural thing), NOT
of the *model's answer* (was the output correct/useful). A model swap mostly moves
**answer quality** and **cost**; it moves planning-control behavior only
secondarily. So the planning scorer is largely blind to the variable an A/B exists
to measure. (Architectural, not a bug — `score_run` was built for the planning-
ladder workstream, a different question.)

**RC2 — phase floors of 0.0 make non-measurement read as parity.**
`compaction` (and several phases) carry a floor of `0.0`. The parity gate is
`candidate ≥ baseline − tolerance`. When BOTH arms score `0.0` (because the signal
never fired — see RC3), `0.0 ≥ 0.0` passes ✅. Two non-measurements compare equal
and the verdict promotes. The `defaultdict` in `score_run` compounds this: an
unmatched phase silently buckets as `n+1, hits=0` rather than erroring, so a
mis-shaped corpus degrades quietly to "all misses = parity."

**RC3 — single-shot offline runs don't reach the states the phases need.**
The compaction phase only scores rows that ACTUALLY fold a long message history;
a fresh single-shot `run_case` never accumulates the turns to trigger a fold, so
`want_compaction` rows record zero folds on every arm regardless of model. The
same shape hits replan/reflexion/escalation (they need repeated failures or
multi-step trajectories the corpus doesn't drive offline). The planning phases are
**stateful/multi-step by construction**; the offline A/B drive is single-shot.

**RC4 — the corpus tasks are unsatisfiable in the harness sandbox (the seed gap).**
The 4 rows reference `workspace/configs/cfg-*.yaml` files that are never seeded, so
the agent correctly can't find them and GoalJudge scores `goal_met: false` on both
arms. The run measured "model behavior on an impossible task," which is noise for a
quality comparison. (This is the GEN-L1 seed gap, A1.2, generalized — the file-IO
tool sandboxes to `WORKSPACE_DIR`, so an absent fixture = a guaranteed-fail task.)

### 6.3 Recommendations — IF we adopt the planning pipeline as an A/B instrument

Graded by scope. **A/B-suitability** items are the minimum to make a planning
corpus usable for a model decision; **broader pipeline** items are deeper
observations the A3a run hinted at, worth fixing regardless of the A/B.

#### A/B-suitability (bounded to this feature)
- **R1 (the real fix): score ANSWER QUALITY, not just control behavior.** A model
  A/B needs a `want_answer`-based scorer (exact/substring/numeric for deterministic
  L1; GoalJudge `criteria_met`/`goal_met` for fuzzy) as the primary unit of
  comparison, with cost/tokens/latency alongside. This is exactly the **A3b**
  answer-scorer — the planning scorer is a *secondary* lens (does the swap regress
  routing behavior), never the headline.
- **R2: seed the corpus fixtures deterministically.** A `seed_*` helper writes
  every file a prompt references under `WORKSPACE_DIR`, with contents whose correct
  answer is known (so R1 can grade it). Idempotent, machine-independent. Without
  this every file-task is a guaranteed fail = noise.
- **R3: make phase floors meaningful or exclude unscoreable phases.** Either raise
  floors above 0.0 (so non-measurement can't pass), or have the harness EXCLUDE a
  phase from the verdict when neither arm produced a scoreable signal (report it as
  `UNMEASURED`, not `parity ✅`). A floor of 0.0 + defaultdict-quiet-miss is a
  false-PROMOTE trap (cf. F4).
- **R4: gate on signal presence.** Before trusting a phase delta, assert the phase
  actually fired on ≥1 arm (non-zero `hits` OR a real confusion-matrix cell).
  Zero-signal-on-both ⇒ `UNMEASURED`, surfaced in the report, never folded into
  PROMOTE. (Generalizes the A2 empty-output⇒HOLD guard to "empty-SIGNAL⇒UNMEASURED.")

#### Broader pipeline critique (out of strict A/B scope, but surfaced by A3a)
- **R5: single-shot vs multi-turn fidelity is a structural test gap.** The stateful
  phases (compaction/replan/reflexion/escalation) cannot be exercised by a
  single-shot offline driver. To test them at all — for ANY purpose, not just A/B —
  the harness needs a **multi-step / multi-turn driver** that builds the history
  the phase needs (the deployed Phase B Playwright driver does this; offline does
  not). Until then, offline planning metrics on these phases are structurally
  unreliable, and any green on them should be read as "didn't fire," not "passed."
- **R6: GoalJudge-as-shared-infra is a real, unpriced cost confound.** Every arm
  runs the GoalJudge evaluator on the capable-tier model (`gpt-4o` here) once per
  case. A3a's per-task cost INCLUDES that judge call on both arms. It's a constant
  offset (fair for A/B comparison) but it INFLATES the absolute $/task and would
  mislead a "what does this model cost in prod" reading. Recommendation: report the
  judge cost as a SEPARATE line from the agent-model cost, so the model-attributable
  cost is legible. (Extends F5.)
- **R7: compaction-trigger realism.** The compaction corpus encodes long-history
  fold expectations that only manifest under real accumulated context. The
  trigger conditions (history length, token pressure) should be documented and the
  corpus should either (a) pre-load a synthetic long history, or (b) be marked
  multi-turn-only (R5). As-is, the compaction rows are inert offline.
- **R8: the `score_run` defaultdict should fail loud on an unknown phase.** Today an
  unrecognized `phase` string buckets silently as all-misses. For an A/B (or any)
  consumer, an unknown phase is a corpus/shape error, not "0 hits" — it should
  raise or be flagged, so a mis-shaped corpus can't masquerade as a regression.

### 6.4 Decision implication
The planning pipeline is **not** the A/B instrument; it is at most a *secondary
regression lens* (R1). The headline model-quality verdict comes from the **answer
corpus + answer scorer (A3b)** with deterministic fixtures (R2). The A3a run's only
honest output was the mechanical validation in §6.1 — which is exactly what a smoke
is for. Proceed to A3b for the substantive cross-model signal; treat planning
metrics as a "did the swap break routing behavior" check, gated by R3/R4 so they
can't false-PROMOTE.
