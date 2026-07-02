---
type: plan
title: 'Subject-Coach Agent — Detailed Implementation Plan'
status: 'Phase 1 built + reviewed; 1B-10 middleware shadow wiring OPEN'
authored: 2026-07-02
---

# Subject-Coach Agent — Detailed Implementation Plan

## Status ledger (updated 2026-07-02)

All work lives on branch **`feat/subject-coach-agent`** — commits `3c6466c` (backend 1A),
`9a99d21` (frontend 1B), `a1c9a76` (Stage-7 review remediation). `make check` green
(4613 passed); frontend vitest green (120 files / 1279 tests).

| Item | Status | Evidence |
|---|---|---|
| 1A-1 AgentFacts instance (FR-1/2) | ✅ DONE | `services/governance/subject_coach_identity.py`; tamper-rejection + roundtrip + drift-check tests |
| 1A-2 Capability binding (FR-3..6) | ✅ DONE | declared=bound arch test extended; fail-fast FR-5 |
| 1A-3 Persona template (FR-10/11) | ✅ DONE | `prompts/subject_coach_system_prompt.j2` + `AgentConfig.additional_instructions` prepend |
| 1A-4 English guardrail condition (FR-7..9) | ✅ DONE (offline) | `domain_gated` mechanism + 101-row frozen held-out set; **live ≥98% admit gate still needs a user-shell run** (hook blocks .env): `.venv/bin/python -m pytest tests/services/governance/test_subject_coach_guardrail_live.py -m live_llm -q -s` |
| 1A-5 Authored hint rungs (FR-20) | ✅ DONE | `components/subject_coach_hints.py`; assertion rung unrepresentable |
| 1A-6 Eval capture target=subject_coach | ✅ DONE | react_loop capture wiring; now READABLE via `meta.analysis.records_for_target` (review I2) |
| 1B-7 Marker store | ✅ DONE | port + in-mem/pg adapters + **migration `0001_coach_session_marker.sql`** (review fix) |
| 1B-8 Marker write on submit | ✅ DONE | fires after attempt record, BEFORE scheduler.review (review A2) |
| 1B-9 BFF sanitizer (FR-19/21/22) | ✅ DONE | fail-closed on absent/mismatched question_id (review C1/C2); mode-spoof strip lock tests |
| **Stage-7 code review** | ✅ CLOSED | high-effort 8-angle review → 10 findings → ALL fixed red/green in `a1c9a76` (incl. per-run guard re-arm + domain fail-closed, `coach_context` state channel + formatter re-strip, pyramid `domain_gated`) |
| **1B-10 Middleware shadow wiring** | ⬜ OPEN — next | `/run/stream` must select a coach graph on body `agent_id=subject-coach-english` (BOTH `middleware/app_prod.py` AND `__main__.py`); without it shadow traces never accumulate → Phase 3 entry gate blocked |
| Phase-1 exit: first shadow traces + §13 governance audit | ⬜ BLOCKED on 1B-10 | audit runs on first `target="subject_coach"` traces |
| Phases 2–6 | ⬜ NOT STARTED | Phase 2 executable after 1B-10; Phase 3 human-gated on ≥100 coded turns/mode |

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
> (`a1c9a76`). Remaining before phase exit: task 10 (middleware shadow wiring,
> below) and the live L3 admit-rate run for 1A-4.

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

**Phase-1 exit:** `make check` green ✅; coach reachable in shadow ⬜ (needs task 10 — `/run/stream` currently ignores body `agent_id`); first shadow traces get a **§13 governance audit** ⬜ before any coding starts (garbage-in guard).

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

## Phase 4 — Generator + hint schema (§11 step 5) — *milestone*

**Entry gate:** ADR-0006 second amendment (hint read seam rides it).

- Generator as `build_graph` job (reuses coach contract + capability gate), **hint family**: verifier cascade = schema-parse → **per-rung leakage check (deterministic first; judge assist only post-§7.4 floor)** → duplicate/similarity. PASS → `reviewed=true`; FAIL → quarantine + eval_capture. Provenance `generated_by: "<model>@<run_id>"`.
- `hint` table (both dialects) + `Hint` Zod wire entity + `getHints(question_id)` read seam; authored rungs (Phase 1) replaced by generated+verified ones. Ungated-item-never-served test (FR-12).

## Phase 5 — Flag flips (§11 step 6) — *milestone*

Per-floor, shadow-first, standing rollout discipline; enters §12.7 continuous monitoring (L1/L2/L3 + drift baselines via `meta/drift.py`, CI golden regression).

## Phase 6 — Test Mode governed plane (§11 step 7) — *milestone*

**Entry gate:** Phase 4's schema-amendment window (test_blueprint rides the same ADR-0006 train). ADR-0013 already accepted; FR-28 already BUILT.

- **Test-item generator family** (FR-23): cascade = schema-parse → **answer-key self-consistency via `ExactLetterGrader` (critical gate)** → duplicate/similarity.
- **`TestBlueprint`** table + Zod entity + `getTestBlueprint(id)` seam + **deterministic seeded assembler** (fixed seed + frozen bank ⇒ byte-identical form; e2e byte-stability re-based on seed) (FR-24/26).
- **`convert:test01` → seed importer** (FR-25): rows enter `reviewed=false`, cascade re-verifies (`reviewed=true` earned, not assumed). Only `reviewed=true` served (FR-27).
- Option A stays (keys in bundle) unless a tripwire fires — the flag flip is a reviewed code diff + ADR-0013 re-open, never this plan.

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
