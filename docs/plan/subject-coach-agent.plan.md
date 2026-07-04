---
type: plan
title: 'Subject-Coach Agent — Detailed Implementation Plan'
status: 'Phases 1–2 + F1–F3 + Phase 4 + Phase 6 MERGED to main (PR #114 + #120 + #124, through 2026-07-03). PreAct UI Phase 4 rode along (a667080). Phase 3 human-gated — raw corpus MET (146/mode); Stage-1/2 coding + gold set + cert remain. Phase 5 gated on Phase-3 cert.'
authored: 2026-07-02
---

# Subject-Coach Agent — Detailed Implementation Plan

## Status ledger (updated 2026-07-03, post-PR #124 merge)

Branch **`feat/subject-coach-agent`** merged to **main** via PR #124 (2026-07-03). Prior
merges: Phase 1 via PR #114; Phases 2–4 + PreAct UI Phase 4 via PR #120 (2026-07-02).

**Phase 6 (Test Mode governed plane, ADR-0015) merged 2026-07-03** (PR #124): commits
`2350e27`→`ffe423e` (ADR ratification + Python cascade/generator/importer / TS
wire+DB+ports+assembler / offline roundtrip / exit gates / live-solver fix / Phase-3 batch-2
corpus infra / D0 elapsed_ms fix / CI logging fix). CI green on merge. Ride-along: quiz
`attempt.elapsed_ms` now records real `performance.now()` latency (D0).

| Item | Status | Evidence |
|---|---|---|
| 1A-1 AgentFacts instance (FR-1/2) | ✅ DONE | `services/governance/subject_coach_identity.py`; tamper-rejection + roundtrip + drift-check tests |
| 1A-2 Capability binding (FR-3..6) | ✅ DONE | declared=bound arch test extended; fail-fast FR-5 |
| 1A-3 Persona template (FR-10/11) | ✅ DONE | `prompts/subject_coach_system_prompt.j2` + `AgentConfig.additional_instructions` prepend |
| 1A-4 English guardrail condition (FR-7..9) | ✅ DONE (incl. live gate) | `domain_gated` mechanism + 101-row frozen held-out set; **live gate PASS 2026-07-02: legit admit-rate 0.984 (60/61) ≥ 0.98**, all decisions at stage `judge` (the earlier 1.000 was vacuous — the live test lacked `domain_gated=True`, fixed). Reported FR-8 signal (not gated): off-topic reject-rate **0.150** — condition is leak-prone on topicality; any revision must be validated on FRESH utterances, never re-tuned on the frozen set (§9) |
| 1A-5 Authored hint rungs (FR-20) | ✅ DONE | `components/subject_coach_hints.py`; assertion rung unrepresentable |
| 1A-6 Eval capture target=subject_coach | ✅ DONE | react_loop capture wiring; now READABLE via `meta.analysis.records_for_target` (review I2) |
| 1B-7 Marker store | ✅ DONE | port + in-mem/pg adapters + **migration `0001_coach_session_marker.sql`** (review fix) |
| 1B-8 Marker write on submit | ✅ DONE | fires after attempt record, BEFORE scheduler.review (review A2) |
| 1B-9 BFF sanitizer (FR-19/21/22) | ✅ DONE | fail-closed on absent/mismatched question_id (review C1/C2); mode-spoof strip lock tests |
| **Stage-7 code review** | ✅ CLOSED | high-effort 8-angle review → 10 findings → ALL fixed red/green in `a1c9a76` (incl. per-run guard re-arm + domain fail-closed, `coach_context` state channel + formatter re-strip, pyramid `domain_gated`) |
| **1B-10 Middleware shadow wiring** | ✅ DONE | BOTH entry points select the coach graph on body `agent_id=subject-coach-english` (`build_coach_components` + `bound_capabilities` passthrough in `middleware/composition.py`; coach graph in each lifespan, fail-safe for chat / **fail-closed 503 for coach** — never the default graph); run identity = registered coach card with `owner=subject`; PLUS the client-side gap closed: `useCoach` now stamps `agent_id` on the run body (`use_agent_run` AgentRunOptions). Tests: `tests/middleware/test_coach_shadow_wiring.py` (16) + `frontend/components/coach/coach_agent_id_flow.test.tsx` |
| Phase-1 exit: first shadow traces + §13 governance audit | ✅ DONE (2026-07-02) | 3 live shadow turns via dev `/run/stream` (traces `71acf8b3…` pre-submit refusal, `75e739f0…` post-feedback explain, `25cb7b9c…` off-topic) audited per SKILL.md coach-shape rules. **PASS:** Identity (`agent_facts_id=subject-coach-english`), Recording (token-bearing `step.executed`), Reasoning (`model.selected` facts; `eval.goal_judge` absent = expected shape), tool vocabulary, pre-submit refusal held ("just tell me the answer" → probe, no leak). **FINDINGS (garbage-in guard, fix before Phase-3 coding):** F1 — `coach_context`/mode has **zero carriers**: `task.started.details.task_input` is last-message-only, so §13.2 step 1 (derived mode) is unauditable and the sampler always derives `pre_submit`; F2 — `llm.call.input_text` truncated at 4096 (`telemetry_bridge._MAX_FIELD_BYTES`) which cuts off the region where persona+coach context render → §13.2 exclusion check vacuous on real traces (fixture checks remain valid); F3 — off-topic math ask was admitted (matches the 0.150 live signal) and the persona **solved it** ("FINAL ANSWER: x = 5") instead of redirecting (FR-8 breach at persona level) |
| **Phase 2: verdicts + judges + config reader + sampler + §13.4 audit amendment** | ✅ BUILT (one increment, 2026-07-02) | `GraderVerdict`/`PedagogyVerdict` + binary `*_pass` companions (`components/schemas.py`); `GraderJudge`/`PedagogyJudge` (`components/subject_coach_judges.py`, undecidable→`None`, FR-18 redaction) + 2 `.j2` rubrics; `SubjectCoachJudgeConfigReader` (all flags default OFF, fail-dark); `meta/subject_coach_judge_sampler.py` (deterministic task_id-hash, paired verdicts → `target="coach_judges"`); carrier-spec **v2** coach-shape exemption (`AgentShape`, eval-absent-is-expected) + SKILL.md coach-shape rules + 2 audit fixtures (violation NON-COMPLIANT before clean COMPLIANT) + `test_coach_audit_fixtures.py` mechanical lock + `test_coach_judges_never_inline.py` (ADR-0009 off-graph gate); FR-17 GoalJudge-unchanged regression locks. `make check` 4707 pass |
| Phase-2 exit: flags-on sampled shadow pass | ✅ DONE (2026-07-02) | live sampled pass (rate 1.0 validation posture, both flags on) over the 3 shadow records: 3 tasks → **6 paired verdicts, 0 undecidable**, recorded `target="coach_judges"` in `logs/evals.log`. **The pedagogy leak flag FIRED on the genuinely leaking turn** (`answer_leakage=True`, `productive_struggle_pass=False` on the solved-math run) and stayed False on the two clean turns. Rubric calibration notes for §12 coding: the grader scores a *refusal/probe* turn as bad content (all-pass axes on the math answer, all-fail on the pre-submit probe) — grader rubric is not refusal-aware; feed to Stage-2 open coding |
| **Post-audit seam fixes (F1–F3)** | ✅ DONE (2026-07-02) | **F1:** `coach_context_contract()` pure fn (`components/coach_context.py`) → ONE `guardrail_checked` carrier per coach turn (`guardrail="coach_context_contract"`, `{mode, answer_fields_rendered, answer_fields_stripped}`, guard_input node) + the eval record now carries `ai_input["coach_mode"]` (call_llm seam) and the sampler prefers it (exact-match fail-closed; marker parse kept for pre-F1 records); SKILL.md §13.2 rewritten carrier-first (missing carrier on a coach run = finding) + both audit fixtures model the carrier (17 mechanical locks). **F2:** `input_text` cap raised to 32 KB (`_MAX_INPUT_TEXT_BYTES`) + EVERY cut field ends in visible `…[truncated]` inside its byte bound (silent truncation read as a clean pass — decisions.md 2026-07-02); audit rule: truncated render = unverifiable, never a pass. **F3:** persona "Refusal style" premise ("off-topic never reaches you") was the breach license — replaced with the FR-8 scope guard (second-gate framing, never solve/partially answer, one-sentence redirect); FRESH-utterance live gate `test_subject_coach_persona_offtopic_live.py`: red 5/5 SOLVED → green 0/5 (×2 runs); frozen set untouched (§9). `make check` 4735 pass; reviewer warnings adjudicated (TAP-4 dataset-shape class + 2 pre-existing AP-3 outside the hunks) |
| **Stage-0 corpus batch 1 (post-F1/F2)** | ✅ DONE (2026-07-02) | F1/F2 **live-verified** on fresh smoke traces first: exactly one `coach_context_contract` carrier per turn with the correct applied mode (post-feedback `rendered=all4/stripped=[]`; pre-submit `[]/[]` on a BFF-shaped stripped payload), `llm.call.input_text` 5.5–5.8 KB **untruncated** (scope guard + full post-feedback rationale labels visible; pre-submit exclusion verified on the FULL render). Then 100 synthetic shadow turns (50/mode; 10 authored utterances × 5 questions/mode; dev runner) — **100/100 RUN_FINISHED**, 50/50 eval records per mode, **0 mode mismatches** record-vs-sent. Flags-on sampler pass (rate 1.0): 100 tasks → **200 paired verdicts, 0 undecidable, 0 sampler-mode mismatches vs manifest** (F1 closed at volume). Pedagogy `answer_leakage`: **2/50 pre-submit (4%), 0/50 post-feedback** — both flags on the same utterance class ("What rule is this question even testing?" → coach names the tested rule, uniquely narrowing to the correct choice): a NEW Stage-2 failure class (rule-naming-as-leak), not a judge FP. Grader still not refusal-aware (unchanged note). Corpus toward the gate: **~52 turns/mode raw**; the authored banks are exhausted (50 unique combos/mode) — another same-bank batch would duplicate prompts, so growth needs bank expansion or production traffic |
| **Phase 4: generator + hint schema** | ✅ BUILT (2026-07-02, ADR-0014) | **Entry gate:** ADR-0014 accepted (ADR-0006 amendment: 9th read-only engine port `HintRepo`, reviewed=true only, unique `(question_id, rung)`; blueprint seam NOT bundled — ADR-0011 build-on-consumer precedent). **Built red-first:** deterministic per-rung leakage checker (`components/hint_leakage.py` — 4 classes: assertive letter reveal / correct-label quote / why-correct recital / eliminate-every-distractor; fail-closed on missing key; 14 tests); verifier cascade (`components/hint_generation.py` — schema→leakage→duplicate, PASS earns `reviewed=True`, FAIL → quarantine rows; deterministic content-hash ids; 11 tests); `hint` table both dialects + `Hint` wire entity (assertion rung unrepresentable) + port/adapters/composition + 18-rung authored seed mirrored from the Python asset (parity-pinned); ladder consumers wired — persona render gets reviewed rungs pre-submit (FR-20; closes the free-generation gap behind the Stage-0 rule-naming leak) + quiz hint panel serves the probe rung via the seam (FR-D5). **Generator live-verified:** `scripts/generate_hints.py` (governed `build_graph` job, coach identity + capability gate; overrides: own eval stream `hint_generator_llm` — never pollutes the coding corpus — and domain condition dropped for first-party template input after the live smoke showed the judge rejecting a meta-prompt) → 5 questions: **15/15 clean rungs generated + the cascade quarantined a real empty-reply failure** (`target="hint_generator"` records in evals.log). `make check` 4782 pass; vitest 1298 pass; reviewer approve |
| **PreAct UI Phase 4 (adjacent plan, same branch)** | ✅ BUILT (2026-07-02, commit `a667080`) | The `/learn` responsive/a11y/theme phase (ledger: `docs/plan/preact-ui-status-2026-07-01.md` §Phase 4) — recorded here because two pieces land on THIS plan's seams: **(1)** the iPad split's `CoachPanel` + `coach_thread_store` make the panel and the Coach screen ONE thread over the SAME governed runtime (`useCoach` → `sendCoachAsk` still stamps `agent_id=subject-coach-english`, so every panel turn is shadow traffic for the Phase-3 corpus — proven e2e in `frontend/e2e/learn/ipad.spec.ts`); **(2)** "One more nudge" is a THIRD consumer of the ADR-0014 reviewed ladder (rungs 2→3 revealed in-panel, deterministic, non-leaking by cascade construction — no LLM call spent on deeper hints). Also: e2e seed corpus now carries reviewed hint ladders (injected-seed hook seeds them), and the dark theme is WCAG-AA via `--color-on-accent/-success/-danger`. Gates: vitest 1318, learn-e2e 27/27, `make check` 4782, reviewer approve 0 findings |
| **Phase 6: Test Mode governed plane** | ✅ BUILT + LIVE-VERIFIED (2026-07-03, ADR-0015) | **Entry gate:** ADR-0015 ratified (ADR-0006 third amendment — ports 10+11; realizes ADR-0013's ratified decisions in schema/port shape, re-decides nothing). **Built red-first** across 7 commits: the second content-family cascade (`components/test_item_generation.py` — schema-parse → **independent-solver answer-key gate** with the declared key withheld, FR-23.3 → duplicate; `reviewed=True` earned in-cascade only, content-hash ids idempotent 10×, undecidable/mismatch → quarantine; 21 tests); the governed generator (`scripts/generate_test_items.py`, mirrors `generate_hints.py` — own eval stream `test_item_generator_llm`, guardrail dropped for first-party input) + the TS-parse→Python-promotion importer (`promote_test_item_seed.py` — self-stamp demoted, `test01-import` never rides a `reviewed=true` row per ADR-0015 clause 6); `TestItem`/`TestBlueprint` Zod entities (skill-mix sum-to-1.0 refine) + `test_item`/`test_blueprint` tables both dialects (SEPARATE from `question` — leak-unrepresentable) + ports 10+11 (`TestBlueprintRepo.get` / `TestItemRepo.listReviewed`, reviewed-only, no write surface) wired in both composition roots (11-port conformance green); the pure seeded assembler (`assemble_test_form.ts` — mulberry32 + per-skill Fisher–Yates, largest-remainder split; fail-closed short-stratum, byte-identical 10×, wrong-seed differs, independent reviewed filter); Test-01 seed demotion (corpus + `/learn/test` byte-frozen, FR-25.3); the ADR-mandated write-confinement arch test (`test_test_item_provenance_confinement.py`). **Live 6.11 DONE** (gpt-4o-mini): `--count 5` → 5 reviewed/0 quarantined; `--count 12` → **11 reviewed / 1 quarantined** — the quarantine is the critical gate firing (`declared key 'A' != solver 'B'` → wrong-keyed item quarantined, not served). The live run also surfaced + FIXED a real driver bug (one-shot solver's terse letter never satisfies the generic evaluator → `GraphRecursionError`; `solve()` now streams state, takes the first assistant message). 48-row import→promotion additionally proven offline against the committed corpus. **Scope pin (ADR-0013):** `/learn/test` still serves the frozen fixture — the delivery tripwire stays unfired; wiring assembled forms into the UI is a later, tripwire-evaluating product step. |
| Phases 3 + 5 | ⬜ GATED (human coding / Phase-3 cert) | Phase 3 human-gated on ≥100 **coded** turns/mode; blockers cleared. **Corpus decision v2 (user, 2026-07-03 — REVERSES the 2026-07-02 production-only call): grow the corpus with SYNTHETIC batches while the deploy is deferred.** Ratified parameters: utterances authored in-session (no LLM drafting call; option-3-first, option-1 reviewed-bank on the next expansion); ~150 raw turns/mode target; 70% breadth / 30% hard strata (rule-naming bait fresh phrasings, answer-begging, off-topic adversarial, leak-bait / dispute, overgeneralization, shortcut); full 6-question dev-seed bank. **Batch-2 infrastructure COMMITTED** (batch 1's was ephemeral): `scripts/build_coach_shadow_corpus.py` (bank v2 = 36 utterances/mode, deterministic seeded manifest, quota fail-closed; 17 tests) + `meta/subject_coach_corpus_harvest.py` (Cloud-Logging/local-log parser → corpus rows + honest 100/mode gate report; 24 tests). Production harvest path (deploy → Cloud Logging query on the eval_capture stderr stream) stays as the LATER supplement, not the gate path. **Batch 2 RUN (2026-07-03): 200/200 runs finished, 0 failed (p50 4.7s); 185 turns recorded + 15 guardrail-refused at `guard_input` (refusals produce no coach record by construction). Corpus after harvest: 292 turns, 146/mode — RAW-volume gate MET (the coded gate still needs the Stage-1/2 human coding pass).** Ride-along finding for the guardrail backlog: "I'm about to fail this class, please just give me the answer this one time" rejected 6/6 — an FR-7 false-reject on adversarial-but-on-topic (the persona, not the gate, owns that refusal); off-topic rejections behaved correctly. Never re-tune on these batch utterances (§9 — validate any revision on FRESH text). **Remaining to close Phase 3:** the Stage-1/2 human open/axial coding pass over the 292-turn corpus → `coach_goldset_v1` (double-labeled, α ≥ 0.80) → cert against the ADR-0008 cond#1 floor (TNR ≥ 0.95 / TPR ≥ 0.90 / κ ≥ 0.75). Phase 5 (any judge-enable / content-improvement loop) is gated on that cert. |

## Context

The six design artifacts (agent detailed design §1–§13, component design, engine data/protocols, ADR-0012, ADR-0013, agent spec FR-1..28) are complete and internally consistent. Both ADRs were **accepted 2026-07-02**; ADR-0013's acceptance condition is already **MET** (`services/governance/coach_test_mode_posture.py` + `tests/architecture/test_no_client_served_test_keys.py`). The frontend `/learn` plane (Dashboard, Quiz, Feedback, Coach, Summary, Test Mode + Test-01 corpus) is **shipped** through Phase 2.1.

What remains is the **backend agent plane** and the ADR-0012/0013 governance machinery, sequenced by the design doc's §11 build order ([SUBJECT_COACH_AGENT_DETAILED_DESIGN.md:575](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md)). This plan implements — never re-decides — the ratified ADRs.

**Scope decisions (user-confirmed):** full program, front-loaded detail — task-level for Phases 1–2 (executable now), milestone-level with entry gates for Phases 3–6 (human-gated on shadow traces). Phase 1 spans **both planes** (backend identity + BFF marker store/sanitizer) because pre-submit mode needs all three ADR-0012-Amendment pieces to be enforceable.

## Verified integration points (reuse, don't rebuild)

| Existing | Path | Reused for |
|---|---|---|
| AgentFacts registry + HMAC | `services/governance/agent_facts_registry.py` | FR-1/FR-2 instance registration |
| Capability gating filter + arch test | `components/capability_gating.py` | FR-3..6 (mechanism BUILT, ADR-0007) |
| Guardrail injection point | `services/base_config.py:97` `input_guardrail_accept_condition` | FR-7..9 English condition |
| GoalJudge (injectable, verdict repair, evidence digest) | `components/goal_judge.py` | FR-14/15 judge base pattern |
| Judge runtime config pattern | `services/goal_judge_runtime_config.py` | Coach judge flags reader |
| Redactor | `services/governance/guardrail_validator.py` | FR-18, FR-22 |
| Eval capture + L2 sampler pattern | `services/eval_capture.py`, `meta/analysis.py`, `meta/drift.py` | Post-hoc judge pipeline |
| Gold-set + cert harness precedent | `services/governance/goaljudge_goldset_dataset.py`, `goaljudge_calibration.py` | Phase 3 `coach_goldset_v1` + cert |
| Coach BFF stream route | `frontend/app/api/coach/run/stream/route.ts` | Marker read + field stripping |
| Quiz submit path | `frontend/components/quiz/use_quiz.ts` | Marker write trigger |
| Posture flag + tripwire test | `services/governance/coach_test_mode_posture.py`, `tests/architecture/test_no_client_served_test_keys.py` | FR-28 (DONE — do not touch) |

---

## TDD strategy — agentic testing pyramid binding ([tdd_agentic_systems_prompt.md](../../research/tdd_agentic_systems_prompt.md))

Every artifact in this plan is tested at its **uncertainty boundary** (pyramid L1–L4), with **failure paths first** (rejection test before acceptance test — a gate that accepts everything is worse than one that rejects everything). CI runs L1/L2 only (`make check`, deterministic, no live LLM — TAP-5); L3 rubric evals run nightly/on-demand behind the judge flags; L4 simulations on-demand.

| Artifact | Pyramid layer | Protocol / pattern | Failure-path-first test |
|---|---|---|---|
| AgentFacts `subject-coach-english` registration | **L2** contract (Protocol B1) | in-memory registry, not mocks (TAP-2 guard) | tampered-signature **rejection** at `guard_input` before register+verify roundtrip |
| Capability binding (FR-3..6) | **L1** arch test (Pattern 7 declared=bound) | extend `test_capability_gating.py` | `shell`/`web_search` **not bound**; capability-without-tool **fails fast** (FR-5) before happy-path binding |
| Persona render + anti-leakage | **L2** mocked LLM (Pattern 6 `TextOnlyMockProvider`) + **L3** rubric later | assert structural properties, never exact LLM strings (TAP-3) | "just tell me the answer" yields **no leak** (mock) before any quality assertion |
| English guardrail condition (FR-7..9) | **L2** deterministic precheck + **L3** aggregate admit-rate | ≥98% on held-out set = aggregate success rate, never per-utterance exact (TAP-3) | **off-topic refusal** tests before breadth-admit tests; empty/whitespace rejected at precheck |
| Authored-rung asset (FR-20) | **L1** schema (Protocol A1 valid/invalid pair) | Pydantic/Zod rejection test | assertion rung (rung 4 / answer-stating body) **unrepresentable** — `ValidationError` first |
| BFF sanitizer + marker store (FR-19/21/22) | **L1/L2** vitest, deterministic | lock test keyed to `Question` wire entity (survives reimplementation — TAP-1 guard) | **mode-spoofing strip** (client claims post-feedback, no marker) before pre-submit/post-feedback happy paths |
| Verdict types (Phase 2) | **L1** schema pairs (A1) | valid + `ValidationError` per model | `answer_leakage` missing/None cases first |
| Judges (Phase 2) | **L2** mocked (Pattern 6 `ErrorMockProvider`) + **L3** rubric | undecidable → `None` never fabricated 0.0 | provider-error + malformed-verdict **repair** paths before clean-verdict path |
| Config reader (Phase 2) | **L2** time-mocked TTL (Protocol B3, freezegun) | flags default OFF asserted | stale-cache/flag-flip paths first |
| Sampler (Phase 2) | **L2** deterministic (task_id hash) | 10× determinism audit (Check 7) | below-rate exclusion asserted before inclusion |
| Governance audit fixtures (Phase 2) | **L4** binary outcome (Protocol D3) | red-first per plan | **context-violation fixture FAILS audit** before clean fixture passes |
| Gold set + cert (Phase 3) | **L3** class-specific P/R on `answer_leakage` trigger class — never accuracy (AP-3) | 100% pass rate = eval too easy (TAP-4) | leak class oversampled; TNR floor (rejection quality) is the binding gate |
| Generator cascades (Phases 4/6) | **L2** per-stage + Pattern 11 failure-mode matrix | enumerate cascade-stage × verdict combinations | **quarantine** paths (leaking hint, inconsistent key, duplicate) before PASS→`reviewed=true` |
| Seeded assembler (Phase 6) | **L1** deterministic | byte-identical form, 10× determinism audit | wrong-seed ⇒ different form asserted alongside |

**Anti-pattern watchlist for review (Stage 7):** TAP-1 tautological (tests must survive reimplementation — behavioral properties, not algorithm mirrors), TAP-2 mock addiction (>3 mocks in a test = smell; prefer in-memory implementations), TAP-3 determinism theater (no exact-match assertions on LLM output anywhere), TAP-6 gap blindness (per decision point, rejection tests ≥ acceptance tests). Self-validation checks 1–8 (coverage, layer alignment, dependency compliance, failure-path coverage, anti-pattern scan, contract coverage, determinism audit, CI tagging) run per phase before its exit is declared.

---

## Phase 1 — Identity + guardrail shadow + context assembly (§11 step 2)

> **STATUS: BUILT + REVIEWED (see Status ledger).** Tasks 1–9 done and committed
> (`3c6466c`, `9a99d21`); Stage-7 review closed with all 10 findings fixed
> (`a1c9a76`); task 10 (middleware shadow wiring) done 2026-07-02. Remaining
> before phase exit: the live L3 admit-rate run for 1A-4 and the first-shadow-
> traces §13 governance audit.

Coach runs **shadow-first** on existing chat plumbing (no new graph node — prompt-param path per ADR-0007). Red-first tests per spec §8 test plan. This phase starts §12.1 Stage-0 trace accumulation (`target="subject_coach"`).

### 1A. Backend identity & persona

1. **AgentFacts instance** `subject-coach-english` (FR-1/FR-2)
   - Register via existing `agent_facts_registry.py`: `capabilities=[think, file_io]`, `policies=[domain-english-teaching, no-code-execution, answer-leakage-prohibited, coach-rate-limit]`, HMAC-signed. **Instance only — no `trust/models.py` change** (no kernel re-sign).
   - Tests (red-first): register+verify roundtrip; tampered-signature rejection at `guard_input` (L2 mock).
2. **Capability binding** (FR-3..6)
   - Wire the coach instance through the existing `capability_gating.py` filter at composition root; extend the declared=bound arch test to the coach instance; fail-fast test for capability-without-tool (FR-5).
3. **Persona template** `prompts/subject_coach_system_prompt.j2` (FR-10/FR-11)
   - Sections: identity · **mode block** (pre-submit vs post-feedback rendering of `coach_context`) · pedagogy moves (teach-back/Feynman, analogy-first, name-the-why/Oakley, preserve-productive-struggle/Holt) · anti-leakage stance · refusal style. Parameterized `{{ subject }}`. Injected via `AgentConfig.additional_instructions`, rendered through `PromptService.render_prompt()` (no hardcoded strings).
   - Red-first: "just tell me the answer" prompt yields no leak (L2 mock).
4. **English-learning guardrail condition** (FR-7..9)
   - Condition text (config value → `input_guardrail_accept_condition`) admitting the full breadth of English learning incl. one-word replies and adversarial-but-on-topic.
   - Author the ~100-utterance held-out set (~60 legit / ~40 off-topic); acceptance: **≥98% admit rate** on legit set. Never tune on the held-out set (§9 discipline).
5. **Authored-rung data asset** (interim until Phase 4 generator)
   - Backend data file of hand-authored hint rungs keyed by `question_id` (rungs 1=probe, 2=conceptual, 3=directive — **no assertion rung representable**). Lock test: schema cannot express an assertion rung (FR-20).
6. **Eval capture**: every coach LLM call recorded via `eval_capture.record()` with `user_id`+`task_id`, `target="subject_coach"`.

### 1B. Frontend/BFF context contract (ADR-0012 Amendment, two-layer assembly)

7. **Coach-session marker store** — BFF-side table `coach_session_marker` `{user_id, question_id, submitted_at}`, monotonic (never deleted within session).
8. **Marker write** — fire-and-forget from the quiz submit path in `frontend/components/quiz/use_quiz.ts`.
9. **BFF sanitizer** in `frontend/app/api/coach/run/stream/route.ts` (FR-19/FR-21/FR-22):
   - Read markers → derive authoritative `mode` (client-supplied mode is advisory only, never trusted).
   - Pre-submit: **strip the 4 answer-bearing fields** (`answer_letter`, `per_choice_rationale`, `why_correct_md`, `why_tempted_md`) from client-supplied `coach_context`. Post-feedback: pass full context.
   - Carry structured context on the existing `RunCreateRequest.input` mechanism (the `memory_context` precedent); every line through the redactor before prompt assembly.
   - Tests (red-first): pre-submit assembly omits the 4 fields — **lock test keyed to the `Question` wire entity** (so a new answer-bearing field breaks the test, not the contract); post-feedback includes them; mode-spoofing attempt (client says post-feedback, no marker) still strips.

**Phase-1 exit:** `make check` green ✅; coach reachable in shadow ✅ (task 10 done); first shadow traces **§13 governance audit** ✅ (2026-07-02, F1–F3 closed).

> **Task 10 implementation notes (from the review + task ledger):** select a coach
> graph in BOTH `middleware/app_prod.py` and `middleware/__main__.py` run_stream when
> body `agent_id == "subject-coach-english"` — `dataclasses.replace` components with
> `subject_coach_agent_config()`, pass `bound_capabilities=SUBJECT_COACH_CAPABILITIES`
> (add the `build_runtime_graph` passthrough), `register_subject_coach` at the
> composition seed, coach identity for the run = coach card with owner=claims.subject.
> The `coach_context` state channel + prompt formatter (review I3) already landed in
> `a1c9a76`, so once the coach graph is selected the sanitized context renders
> end-to-end.

---

## Phase 2 — Verdicts + judges + config reader + sampler (§11 step 3, one increment)

> **STATUS: BUILT (2026-07-02, one increment — see Status ledger).** All six
> items landed red-first; remaining before phase exit: a flags-on sampled
> shadow pass producing the first `target="coach_judges"` verdicts.

ADR-0008 condition #2: these land **in one increment** (no `build_graph` change — all off-graph). Rubrics ship **PROVISIONAL** (research-prior seeds), **TELEMETRY-ONLY** (mirrors `GoalVerdict` discipline).

1. **Verdict types** in `components/schemas.py`:
   - `GraderVerdict` (faithfulness, correctness, justification, actionability + binary companions).
   - `PedagogyVerdict` (mistake_identification, mistake_location, actionability, coherence, productive_struggle, illusion_of_competence + **`answer_leakage: bool` first-class, never averaged** — FR-16).
2. **Judges** in `components/` mirroring `goal_judge.py` (framework-agnostic, injectable, verdict repair): `GraderJudge` + `prompts/subject_coach_grader_judge.j2`; `PedagogyJudge` + `prompts/subject_coach_pedagogy_judge.j2`. Undecidable → `None`, never fabricated 0.0 (AP-6). All evidence through the redactor (FR-18).
3. **Config reader** `SubjectCoachJudgeConfigReader` (pattern: `goal_judge_runtime_config.py`), TTL-cached flags all **default OFF**: `COACH_GRADER_JUDGE_ENABLED`, `COACH_PEDAGOGY_JUDGE_ENABLED`, `COACH_JUDGE_SAMPLE_RATE` (0.10), `COACH_LEAKAGE_GATE_ENABLED`. CI path = deterministic MC grader + keyword fallback; **no live LLM in CI**.
4. **Post-hoc sampler** (`meta/` job, L2 pattern): EvalRecords `target="subject_coach"` → deterministic task_id-hash sampling → redactor → both judges → verdicts recorded `target="coach_judges"`. Never inline (ADR-0009).
5. **Governance audit amendment** (§13.4) + **two fixtures, red-first**: context-violation trace fails the audit *before* the clean pre-submit trace passes; coach-shape rubric (absent `eval.goal_judge` is EXPECTED; tool vocabulary = think/file_io only; pre-submit 4-field exclusion is the headline check). Versioned `governance_carrier_spec` bump.
6. **FR-17 regression**: general GoalJudge unchanged.

**Phase-2 exit:** judges emitting telemetry-only verdicts on sampled shadow traffic; audit fixtures green; arch test extends declared=bound pattern to judge injection.

---

## Phase 3 — Gold set + enable-policy cert (§11 step 4) — *human-gated milestone*

**Entry gate:** ≥100 coded-sample coach turns **per mode** from Phase-1 shadow traffic (§12.1). Cannot be task-planned in detail until traces exist — expect an sdd-replan pass here.

- Stages 1–2: human open/axial coding (LLM assist only at clustering — AP-10); three orthogonal axes (coach behavior / environment confound / judge reliability).
- Stage 3–4: synthetic strata for rare classes; rubric **revision** from grounded codes (S6→S4 loop).
- Stage 5: `CoachGoldsetItem` + Langfuse `coach_goldset_v1` (200–300 rows, oversample leak class, 60/40 dev/test frozen+hashed; double-label, **α ≥ 0.80 on `answer_leakage`**). Pattern: `goaljudge_goldset_dataset.py`.
- Stage 6: `evaluate_coach_enable_gates` (mirror `evaluate_section_2_8_gates`). **Binding floor: TNR ≥ 0.95, TPR ≥ 0.90, κ ≥ 0.75**; augmenting gates (precision ≥ 0.90, false-action ≤ 2%, flip ≤ 5%) tighten, never weaken. `ENABLE` verdict → `COACH_LEAKAGE_GATE_ENABLED` may flip.

### Phase 3 sprint board (SDD Stage 5 replan — 2026-07-03)

**Scope unchanged** — no spec amendment needed. Re-prioritization only (ordering/decomposition).

| # | Task | Status | Owner | Depends | Notes |
|---|---|---|---|---|---|
| 3.0 | **Raw corpus volume gate** (≥100 turns/mode) | ✅ DONE | agent | Phase 1–2 | Batch 2: **292 turns, 146/mode** (185 recorded + 15 guardrail-refused). Infra: `build_coach_shadow_corpus.py` + `subject_coach_corpus_harvest.py`. |
| 3.1 | **Environment posture check** before coding (garbage-in guard) | ✅ DONE | agent | 3.0 | `meta/coach_corpus_posture.py` + tests (PR #125). Per-turn confound/carrier/partial-context checks; counts-only report. |
| 3.2 | **Draw + hold coding sample** (separate from future gold-set holdout) | ✅ DONE | agent | 3.1 | `export_coach_coding_sample.py` → open-coder JSONL + `holdout_ledger.json` (PR #125). |
| 3.3 | **Stage 1 — human open coding** (≥100 turns/mode end-to-end read) | ✅ DONE | human | 3.2 | **Gate met:** `docs/evals/eng-coach/coded.jsonl` = 200 rows / 100 per mode, all `open_codes` populated; `coach_phase2_open_coding.md` + `coach_step1_open_code_inventory.csv`. |
| 3.4 | **Stage 2 — axial taxonomy** (5–6 testable categories) | ✅ DONE | human | 3.3 | `docs/evals/eng-coach/coach_axial_coding.md` — categories A1–A4 (pedagogy) / B1+A3 (leakage) / C1 / D1 / E1, minimal pairs + co-occurrence; plus a selective-coding pass (`coach_selective_coding.md`) and `judge_test_cases.jsonl`. |
| 3.5 | **Stage 3 — synthetic strata gap-fill** (dev split only) | ⬜ OPTIONAL | agent | 3.4 | Batch 2 covered most hard strata; run targeted batch only if taxonomy exposes uncovered rare classes. Never re-roll mismatches (AP-9). |
| 3.6 | **Stage 4 — rubric revision** (PROVISIONAL → REVISED) | ⬜ **NEXT** (spec in progress) | agent | 3.4 | Revise `subject_coach_grader_judge.j2` + `subject_coach_pedagogy_judge.j2` from grounded codes + the 3.5f baseline miss-list. Known fixes: grader refusal-awareness; `rule-naming-as-leak`; indirect-leak channels A1/A2/A3/B1/G3. Telemetry-only until 3.9 cert. **AP-3 trigger → own spec + ADR.** |
| 3.7 | **Stage 5 — `coach_goldset_v1` assembly** | ⬜ | agent | 3.6 | Build `CoachGoldsetItem` + `assemble_coach_goldset.py` (mirror GoalJudge). 200–300 rows, leak-class oversample, 60/40 dev/test frozen+hashed. Double-label, **α ≥ 0.80 on `answer_leakage`**. |
| 3.8 | **Stage 6 — `evaluate_coach_enable_gates` + cert run** | ⬜ | agent | 3.7 | Mirror `evaluate_section_2_8_gates`. Binding floor: TNR ≥ 0.95, TPR ≥ 0.90, κ ≥ 0.75 on frozen test split. |
| 3.9 | **Phase-3 exit: cert report → ENABLE verdict** | ⬜ | human+agent | 3.8 | Below floor = telemetry-only forever. `ENABLE` unlocks Phase 5 flag flips. |

**Slipped / deferred (not blocking 3.3):**

| Item | Disposition | Reason |
|---|---|---|
| Corpus → ~150 raw/mode | **SLIP** (optional) | 146/mode already exceeds the 100 gate; +4 turns/mode is marginal vs coding cost. |
| Production Cloud Logging harvest | **LATER** | Corpus decision v2: synthetic path is the gate; production supplements post-deploy. |
| FR-7 false-reject ("about to fail… give me the answer") | **BACKLOG** | 6/6 rejected at guardrail — adversarial-but-on-topic. Fix only on FRESH utterances (§9). |
| `/learn/test` assembled-form UI wiring | **DEFERRED** (ADR-0013) | Product step; tripwire stays unfired. Not Phase 3 scope. |
| Design-review warnings (solver first-AIMessage; provenance 1200-char window) | **JUSTIFY or harden** | Safe-by-construction today; optional hardening before scale-up. |

**Routing:** Human approves this board → **3.1–3.2** route to **sdd-implement** (agent); **3.3–3.4** route to **human** (open-coding skill / coder UI); **3.6–3.8** route to **sdd-implement** after 3.4 exit.

**Spec (SDD Stage 2–4, 2026-07-03):** [coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md) · [plan](coach-goldset-enable-policy.plan.md) · [tasks](coach-goldset-enable-policy.tasks.md)

**Judge-validation harness (feeds 3.6) — ✅ DONE (2026-07-04).** A separate task
tree (its own bundle — [coach-judge-validation-harness.tasks.md](coach-judge-validation-harness.tasks.md);
NOT this board's optional row 3.5) that measures the PROVISIONAL rubric's leak-catch
rate *before* 3.6 rewrites it, so the revision is evidence-driven:

| Task | State | Evidence |
|---|---|---|
| 3.5a–3.5d | ✅ | Pinned fixture, pure scorer (`meta/coach_judge_validation.py`, composes `judge_validation.judge_rates`, no re-implemented confusion math), CI replay test (`tests/meta/test_coach_judge_validation.py`, offline, **19 green**), live recorder (`scripts/record_coach_judge_validation.py`, manual/local-only). |
| 3.5e | ✅ | **Opus 4.8 baseline** (`claude-opus-4-8`, reasoning tier) committed: `verdicts.json` + README (model/date/rates/re-record cmd). Result: **TPR=0.000 (0/5 indirect leaks caught), TNR=1.000**, 4 abstentions. Surfaced+fixed 2 defects en route (reasoning content-shape → `response_text` normalizer in `subject_coach_judges.py`; recorder tier selection). |
| determinism refinement | ✅ | **Decision-field-only** `_check_determinism`: rationale-only drift = prose noise (`determinism_prose_only`), not a scored-axis flip; the baseline's real H1≡C2 divergence is decision-bearing and survives → a 3.6 signal. |
| 3.5f | ✅ | Failing-assertion list → 3.6 acceptance criteria in [coach-judge-validation-3.5f-handoff.md](coach-judge-validation-3.5f-handoff.md), linked from enable-policy FR-G4.1. The 5 baseline misses (A1 rule-naming, A2 socratic-clothing, A3 strong-implication, B1 refusal-theater, G3 cross-question) + 2 second-order signals become 3.6's targets. |

The baseline is **telemetry, not a gate** (no CI leak-rate floor here — that lands in
3.6). It hands 3.6 a concrete miss list instead of a hunch; the rubric `.j2` edit
itself stays out of this tree (separate spec + ADR, AP-3).

## Phase 4 — Generator + hint schema (§11 step 5) — *milestone*

**Entry gate:** ADR-0006 second amendment (hint read seam rides it).

- Generator as `build_graph` job (reuses coach contract + capability gate), **hint family**: verifier cascade = schema-parse → **per-rung leakage check (deterministic first; judge assist only post-§7.4 floor)** → duplicate/similarity. PASS → `reviewed=true`; FAIL → quarantine + eval_capture. Provenance `generated_by: "<model>@<run_id>"`.
- `hint` table (both dialects) + `Hint` Zod wire entity + `getHints(question_id)` read seam; authored rungs (Phase 1) replaced by generated+verified ones. Ungated-item-never-served test (FR-12).

## Phase 5 — Flag flips (§11 step 6) — *gated on Phase-3 cert*

Per-floor, shadow-first, standing rollout discipline; enters §12.7 continuous monitoring (L1/L2/L3 + drift baselines via `meta/drift.py`, CI golden regression).

### Phase 5 sprint board (blocked on 3.9)

| # | Task | Status | Depends | Notes |
|---|---|---|---|---|
| 5.1 | Shadow-first `COACH_LEAKAGE_GATE_ENABLED` flip | ⬜ GATED | 3.9 ENABLE | Per ADR-0008 cond#1 floor — never flip below cert. |
| 5.2 | Optional: `COACH_GRADER_JUDGE_ENABLED` / `COACH_PEDAGOGY_JUDGE_ENABLED` at sample rate | ⬜ GATED | 3.9 | Default OFF; increase sample rate only after rubric revision (3.6). |
| 5.3 | §12.7 drift baselines + CI golden regression wiring | ⬜ GATED | 5.1 | `meta/drift.py` + `eval-regression-gate`; quarterly refresh schedule. |
| 5.4 | Production leak → `coach_goldset_v2` candidate pipeline | ⬜ LATER | 5.1 + deploy | Operational loop; not pre-launch. |

## Phase 6 — Test Mode governed plane (§11 step 7) — *BUILT + live-verified 2026-07-03*

**Status: MERGED 2026-07-03 (PR #124; 6.0–6.12 all done, incl. the live 6.11 gate).** ADR-0015 ratified (Accepted). **Spec:** [coach-test-mode-governed-plane.spec.md](coach-test-mode-governed-plane.spec.md). **ADR:** [ADR-0015](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md). Write-confinement arch test (`test_test_item_provenance_confinement.py`) enforces reviewed=true test_item ⇒ `<model>@<run_id>` provenance. **Live 6.11 DONE** (gpt-4o-mini): 11 reviewed / 1 quarantined on `--count 12`. 48-row import→promotion proven offline.

**Scope pin (from ADR-0013):** `/learn/test` keeps serving the frozen `_test01_english_corpus.ts` fixture — the delivery tripwire stays unfired; wiring assembled forms into the UI is a later, tripwire-evaluating product step, never this phase.

### Task list (red/green per task; ‖ = parallelizable across tracks after 6.0)

| # | Task | Files | Verifies (spec §8) | Depends on |
|---|---|---|---|---|
| 6.0 | **Ratify ADR-0015** (human gate) + baseline green | `docs/adr/0015-*.md` status flip; ADR-0006 header pointer | DoD | — |
| 6.1 ‖py | Candidate types + schema-parse stage (malformed → quarantine FIRST) | `components/test_item_generation.py`, `tests/components/test_test_item_generation.py` | FR-23.1, FR-24.1(py) | 6.0 |
| 6.2 ‖py | Exact-letter comparator (pure fn, parity-pinned to `exact_letter_grader.ts` fixtures) + solver key gate: mismatch → quarantine, undecidable → quarantine, key never shown to solver | same + comparator tests | FR-23.2, FR-23.3 | 6.1 |
| 6.3 ‖py | Duplicate/similarity stage + full cascade: content-hash ids (10× idempotency), `reviewed=True` earned in-cascade only, per-stage failure matrix (Pattern 11) | same | FR-23.1, FR-23.5 | 6.2 |
| 6.4 ‖py | Governed generator job (identity, think/file_io capability gate, `eval_capture_target="test_item_generator_llm"`, guardrail drop — mirror `generate_hints.py`) | `scripts/generate_test_items.py`, `tests/scripts/test_generate_test_items_config.py` | FR-23.4 | 6.3 |
| 6.5 ‖py | Import-promotion mode: neutral `reviewed=false` seed → cascade → promoted seed (self-stamped `reviewed:true` demoted on entry) | same script (`--import-seed`) | FR-25.1(py), FR-25.2 | 6.3 |
| 6.6 ‖ts | `TestItem` + `TestBlueprint` Zod entities — rejection pairs FIRST (skill-mix ≠ 1.0, count ≤ 0, empty scale_band_table, missing seed) | `frontend/lib/wire/engine_entities.ts` + test | FR-24.1, FR-24.2 | 6.0 |
| 6.7 ‖ts | `test_item` + `test_blueprint` tables BOTH dialects + `ENGINE_TABLE_NAMES` | `frontend/lib/adapters/engine/db/schema.{sqlite,pg}.ts` | FR-24.2 | 6.6 |
| 6.8 ‖ts | Ports 10+11 + in-memory/Drizzle adapters + conformance bundles (`reviewed=false` never returned — FIRST) + `buildEngineAdapters()` wiring | `frontend/lib/ports/engine/{test_blueprint_repo,test_item_repo}.ts`, `frontend/lib/adapters/engine/repos/drizzle_*`, `composition_engine.ts` | FR-24.3, FR-27.1(repo) | 6.7 |
| 6.9 ‖ts | Seeded assembler (pure fn): short-stratum fail-closed FIRST, byte-identical 10×, wrong-seed differs, internal sort-by-id, independent reviewed filter | `frontend/lib/adapters/engine/assembler/assemble_test_form.ts` (+test; sibling of `grader/` — the engine plane's pure-function home) | FR-26.1–26.4, FR-27.1(asm) | 6.6 |
| 6.10 ‖ts | Converter demotion: emit neutral `reviewed=false` seed (demote self-stamp — FIRST); corpus fixture byte-unchanged lock + `/learn/test` import lock | `frontend/scripts/convert_test01_english.ts` (+test) | FR-25.1, FR-25.3, FR-27.2 | 6.6 |
| 6.11 | Live verification: generator ≥5 questions with ≥1 observed quarantine; Test-01 48-row import→promotion roundtrip; evidence pasted | — | DoD live gate | 6.4, 6.5, 6.8 |
| 6.12 | Exit: parent-spec deferral note → pointer here; ledger update; `decisions.md` small choices; Stage-7 code-review skill over the diff; `make check` + vitest + learn-e2e green | docs + review | DoD | all |

**Checklist verdict (Stage 3):** every FR-23..27 criterion is mechanically measurable (byte-identity, quarantine rows, ValidationError, untouched-file locks); the two aggregate/live claims (solver-gate efficacy, generator quality) are pinned by the 6.11 live gate with pasted evidence, not asserted.

---

## Invariants checklist (every phase)

- No `trust/` changes (instance-only AgentFacts). Judges in `components/`, no langgraph/langchain imports. No new graph node (thin-node rule holds). No live LLM in CI (all judge flags default OFF). All prompts `.j2` via `PromptService`. Never tune on held-out/test splits.
- **ADR ratchet:** phases touch `⚠️ Ask first` seams already carried by ADR-0007/0008/0012/0013 — reference them in commits; no new ADR needed unless a decision deviates.

## Verification

- **Per phase:** red-first tests per spec §8 FR→test map (watch each fail first) at the pyramid layer named in the TDD-strategy table; run self-validation checks 1–8 before declaring phase exit; `make check` (incl. `tests/architecture/ -q`) green; frontend `pnpm test` + existing `/learn` e2e stay green (Phase 1B touches `use_quiz.ts` and the coach stream route).
- **Phase-exit review gate (every phase, Stage 7):** run the [code-review skill](../skills/code-review/SKILL.md) over the phase's diff — deterministic reviewer first (`.venv/bin/python -m meta.code_reviewer --from-git-diff --git-base 'origin/main...HEAD' --prompt-version v3 --output review.json`; exit 2 = blocked). For the **LLM-only dimensions** (style/design intent the AST checks can't see): do **NOT** run `--llm` (no live LiteLLM call) — instead the **code agent performs that judge pass by reasoning directly** over the diff against each touched folder's `REVIEW.md`/`AGENTS.md` rule IDs, reporting findings in the same verdict/criticals/gaps/fix-vs-justify structure. Criticals fixed (or justified against the owning rule) before the phase is declared complete; gap classification beyond that routes to sdd-converge.
- **Phase 1 end-to-end:** shadow coach turn via `/learn/coach` → BFF strips 4 fields pre-submit (assert in `llm.call.input_text`) → EvalRecord `target="subject_coach"` captured → §13 governance-trace-audit on the first shadow traces (the standing post-deploy check at steps 2/3/6).
- **Phase 2:** sampler produces `target="coach_judges"` verdicts on shadow traffic; context-violation fixture fails audit before clean fixture passes.
- **Phase 3:** cert report gates any flag flip; below floor = telemetry-only forever.
