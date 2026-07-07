---
type: log
title: 'Lightweight decision log (intent debt, long tail)'
---

# Lightweight decision log

> Append-only, newest first. 2–4 lines per **small** decision: what was decided,
> the alternative rejected, and why. This is the low-friction sibling of the full
> ADRs — use a numbered ADR (`0000-template.md`) for big/structural decisions that
> need Context/Options/Rationale/Consequences; use this for the long tail of
> non-obvious-but-small choices that would otherwise go uncaptured. Lower the bar,
> capture more intent debt. (Playbook: Comprehension-Debt runbook, Part B.)

- 2026-07-06 — **Coach golden-regression gate (Phase-5 task 5.3): floor+zero-flip on the COMMITTED runs, reuse the certified evaluator, `meta/` home, no new ADR.** The gate (`meta/coach_regression_gate.py` + `scripts/coach_regression_gate.py`) recomputes the ADR-0019 floor from the 3 committed `recert_labels_fw_run{1,2,3}.jsonl` and fails on floor breach / cross-run flip / malformed artifact. **Decision A — reuse `evaluate_coach_enable_gates` per run** (the certified floor logic verbatim) rather than re-wire `coach_confusion`→`tnr`/`≥`; keeps ONE source of truth and dodged a `*_min` threshold-key trap (Analyze finding). **Decision B — the ADR-0019 floors ARE the reference; no pinned-baseline 2σ delta** (`meta/drift.py detect_performance_drift` is the drop-in when live traffic gives a distribution — a later task; the 3-run sample can't support a variance model). **Decision C — abstention handling (FR-5b, surfaced by the gate itself):** run3's `R-CLEAN-29` has `judge_leak=null`/`confusion="abstain"`; it is DROPPED from the confusion denominator + the flip check exactly as the cert scored it (46/47, still ENABLE), not treated as malformed. **Decision D — no CI/Makefile change:** the always-on pytest test rides `pytest tests/` (both `make check` and CI), and `eval_regression_gate.py` (the mirrored pattern) has no dedicated CI step either, so a coach-only step would be an inconsistent one-off. **No new ADR** — the gate ENFORCES the existing ADR-0019 decision (references it), adds no abstraction. Rejected: extending `eval_regression_gate.py` (its substring-pass-rate model ≠ verdict-confusion; G1 — a shared base earns nothing). Bundle: `docs/plan/coach-regression-gate.{spec,plan,tasks}.md`.

- 2026-07-06 — **Coach re-cert judge host REVERSED: glm-5.2 on Z.ai → glm-5.2 on Fireworks AI** (structural; full record in [ADR-0019](0019-fireworks-host-adapter.md)). The line below (2026-07-06 "(2) Re-cert model = glm-5.2 … reads `GLM_API_KEY`") chose glm-5.2 on Z.ai; the model choice stands, but the **host** moves to Fireworks because Z.ai's serving stalls (>180s hangs on random rows) break the FR-9 zero-flip requirement — a serving problem, not a model problem (external research + five-probe scoreboard in [ADR-0019](0019-fireworks-host-adapter.md)). Z.ai stays a registered host; only the certified coach judge moves. Operator runbook updates to `MODEL_PROFILE_SET=fireworks COACH_JUDGE_MODEL=glm-5.2-fireworks FIREWORKS_API_KEY=… python -m scripts.run_coach_calibration …`.

- 2026-07-06 — **PedagogyJudge/GraderJudge retry transient provider errors (bounded, 3 attempts); parse failures are NOT retried; AP-6 still holds** (coach C1 re-cert abstain fix; `components/subject_coach_judges.py`). The first working-key glm-5.2 re-cert abstained on 5/47 rows with `provider error; verdict undecidable`, yet a 20-call diagnostic at the same 90s timeout was **20/20 ok (max 8.6s)** — so the failure is an **intermittent per-call exception on the heavy thinking-mode judge call**, not a rate-limit or fixed-timeout cutoff (timeout/pacing had nothing to act on; the user's first instinct to raise those was evidence-ruled-out by the probe). Wrapped **only** the provider `invoke` in a retry-with-backoff (0.5s·2^n, `_MAX_ATTEMPTS=3`); the JSON parse is deterministic so a malformed verdict is **not** retried (would just burn calls). Fail-closed invariant preserved: exhausted retries → `None`, never a fabricated verdict / defaulted `answer_leakage=False` (AP-6). `_sleep` is an injected param (default `asyncio.sleep`) so the 3 red-first L1 tests (recover-after-1-fail, exhaust→None, parse-not-retried) run without waiting and with zero live calls (TAP-2/TAP-4). Rejected `tenacity` (a new dep = ⚠️ Ask-first, for a 6-line loop) and rejected retrying the whole `_verdict` incl. parse (masks deterministic schema bugs as flakiness). Motivated by the [ADR-0018](0018-subject-coach-rubric-specificity-revision.md) exit bar: abstain-noise makes the FR-9 zero-flip TNR non-comparable across replays (each run scored a different clean subset), so near-zero abstains are a prerequisite to *reading* the re-cert, not a metric change.

- 2026-07-06 — **Coach re-cert freeze exposes a per-build `--row-floor`; the α gate (not the 200-row heuristic) is the non-provisional guarantee for a fresh authored split** (fresh-recert [spec](../plan/coach-fresh-recert-split.spec.md) FR-3/FR-7; Task B4-pre). `scripts/assemble_coach_goldset.py` had two seams dormant through round-1 (E6): `--rubric-version` was parsed but never threaded into `build_coach_goldset_manifest` (would silently stamp `coach_rubric_v1_revised` → FR-7 fail), and `row_floor` was hardcoded at 200 in the manifest builder, so the 47-row recert split was forced `provisional=true` → the cert short-circuits `REFUSE_PROVISIONAL` (FR-3 fail). Threaded `rubric_version` + `row_floor` through `build_rows → build_coach_goldset_manifest` and added a `--row-floor` CLI arg; the recert freeze uses `--row-floor 30` (< 47, > the ≥10-leak/≥20-clean FR-4 mins). **Why safe:** the 200-row floor is a corpus-*size* proxy for a harvested set; for a fresh *authored* control split the α ≥ 0.80 double-label gate (α = 1.0 here) is the real fail-closed guarantee, and it still forces `provisional` back on if unmet. Rejected hardcoding v2 in the builder (round-1 v1 freezes must stay reproducible — the default is unchanged) and rejected dropping the floor globally (harvested sets still want the 200 proxy). Both fixes red-first L1-tested (`test_assemble_threads_rubric_version`, `test_assemble_row_floor_override_clears_provisional`).

- 2026-07-06 — **Coach re-cert judge model is pinned by NAME (`COACH_JUDGE_MODEL`), not tier** (fresh-recert [spec](../plan/coach-fresh-recert-split.spec.md) FR-8; Task C-pre). `scripts/record_coach_judge_validation.build_live_judges` selected the judge profile only by `COACH_JUDGE_TIER`, which cannot reach `glm-5.2`: glm-5.2 is `provider="direct"`, opt-in-by-pin (`llm_config.py:200`), and lives only in `MODEL_PROFILE_SET=glm` whose *tier* default is `glm-5.1` — so a tier-only override picks the wrong GLM. Added a pure `select_judge_profile(models, *, model_pin, tier)` helper (L1-tested offline, so `build_live_judges` stays `# pragma: no cover - live only`): an explicit `COACH_JUDGE_MODEL` pin wins and raises `KeyError` naming the pin + available names if absent (mirrors `LLMService.get_profile`); unset → the prior capable-tier behavior, unchanged. Selection stays **inside the registry** (H2 — no hardcoded model string in the harness). Rejected a `--model` CLI flag (env keeps parity with the existing `COACH_JUDGE_TIER`/`MODEL_PROFILE_SET` knobs) and rejected mocking the whole `LLMService` in the test (TAP-2 — the pure helper needs zero mocks). Operator runbook for the 3.9 re-cert: `MODEL_PROFILE_SET=glm COACH_JUDGE_MODEL=glm-5.2 GLM_API_KEY=… python -m scripts.run_coach_calibration …`.

- 2026-07-06 — **Phase-3.9 fresh re-cert: split source, judge model, and the "margin" definition** (settles [specificity-spec](../plan/coach-rubric-specificity-revision.spec.md) Open #2/#3; scoped by [coach-fresh-recert-split.spec.md](../plan/coach-fresh-recert-split.spec.md)). **(1) Split source = in-session authored** (~40–60 fresh clean+leak turns on the existing 6-question dev bank, new phrasings/strata, human α-labeled) — rejected the synthetic batch-2b harvest (needs a deploy/log round; emergent not-controlled leak mix) and a new item-bank (largest effort, new items need answer-key self-consistency too). **(2) Re-cert model = `glm-5.2`** (`provider="direct"`, reads `GLM_API_KEY`) — chosen by the user over gpt-4o/Opus. **Accepted caveat:** this **breaks the direct before/after comparability** the ADR-0018 argument leans on (3.9 REFUSE was gpt-4o), so the re-cert *also* records a **gpt-4o replay on the same fresh split** as a diagnostic comparability anchor (FR-10, non-gating); the ENABLE gate stands on glm-5.2. **(3) "With margin" = TNR ≥ 0.95 held zero-flip across ≥3 temperature-0 replays** (no single run dips below any floor) — rejected a higher headroom number (e.g. TNR≥0.97) in favor of *stability* to catch the measured ~1-row temp-0 drift, and rejected TNR≥0.98 (risks over-tightening the carve-out and re-admitting leaks).

- 2026-07-04 — **`CoachGoldsetItem.failure_mode` is a reserved-optional field
  (empty taxonomy), gated on `leak_channel` instead.** The coach axial taxonomy
  (`coach_axial_v1`) defines pedagogy categories A1–A4 + the B1/A3 leakage bridge —
  it has NO separate agent failure-mode code set (unlike GoalJudge's
  `GOAL_FAILURE_MODES`), and no `cases.jsonl` row carries `failure_mode`. Decision:
  `COACH_FAILURE_MODES = frozenset()` (any non-null value hard-rejects, FR-3); the
  real taxonomy gate binds on the 5 `leak_channel` values. Rejected: copying
  GoalJudge's failure-mode enum (wrong axis — those are goal-completion codes, not
  coaching-leak codes). `failure_mode` stays for forward-compat with the enable-policy
  manifest shape.
- 2026-07-04 — **Coach judge goldset: `cases.jsonl` is derived, kept in lockstep
  with source `judge_test_cases.jsonl`.** Task 3.6 replan corrected 3 mislabeled
  positives (A1/A2/B1) in BOTH files (FR-14). Rejected: treating `cases.jsonl` as
  canonical and letting the source drift — the source is the human-coded origin and
  a future re-enrich would reintroduce the mislabels. Why: the enrich script reads
  `question_id` from cases; a stale source silently re-poisons any regenerate.
- 2026-07-03 — **D0 elapsed timing: page wiring is typechecked, not RTL-asserted**
  (review "not checked" gap, JUSTIFY). `QuizPage.onSubmit` computes
  `elapsedMsFrom(state.presentedAt, performance.now())` and forwards it to `submit`;
  this wiring is glue (F-R1) and typechecked. Rejected a page-level RTL test: it
  would mock `useRouter` + `useEngine` + `useSurface` + `buildBrowserRuntimeClient`
  and stub `performance.now`, then drive the async open→answer→submit chain — high
  mock cost asserting *wiring*, not logic, with no page-RTL harness precedent under
  `app/(coach)/`. The elapsed *contract* is already locked deterministically at two
  layers: `elapsedMsFrom` unit tests (FR-2/4/5) + the reducer clock-less contract
  guard. Low-ROI glue test deliberately skipped (§20). Spec:
  `docs/plan/quiz-attempt-elapsed-timing.spec.md`.
- 2026-07-03 — **Phase-6 test-item solver comparator: single-letter extraction,
  ambiguous→undecidable** (`components/test_item_generation.py::extract_solver_letter`).
  Parity-pinned to `ExactLetterGrader` (a verdict is a letter, compared exactly):
  the comparator pulls the one choice letter a chatty reply names ("The answer is C
  because…" → "C"); a reply naming zero or ≥2 distinct valid letters is undecidable
  → quarantine (never guessed). Rejected importing the TS grader across the language
  boundary (ADR-0015 keeps the dual-literal defense) and a bare `.strip()=="C"`
  exact-match (the live solver returns prose, not a lone letter). Out-of-range-only
  letters are ignored, so such a reply is undecidable.
- 2026-07-03 — **Seeded assembler count split = largest-remainder rounding**
  (`assemble_test_form.ts::stratumCounts`). `blueprint.count × skill_mix[skill]`
  rarely lands on integers; independent per-skill `Math.round` can sum to count±1
  (a short or over-full form). Largest-remainder keeps the parts summing to exactly
  `count`, tie-broken by sorted skill id so the split never depends on object key
  order; the PRNG stream is consumed in sorted-skill order so a fixed seed is
  byte-stable regardless of `skill_mix` key order. Rejected per-skill round
  (off-by-one forms) and floor-only (drops units).

- 2026-07-03 — **Quiz `attempt.elapsed_ms` real timing (D0 fix).** The former
  hardcoded `elapsedMs: 0` (quiz/page.tsx) is replaced by a real per-item latency:
  `item_loaded` stamps `presentedAt = performance.now()` on the reducer's answering
  state, and `onSubmit` records `elapsedMsFrom(presentedAt, performance.now())`.
  Chose a **monotonic** clock (`performance.now()`) over `Date.now()` so a wall-clock
  adjustment mid-answering can't yield a negative elapsed; the helper clamps `≥ 0`
  and rounds to whole ms. Chose **wall-clock** elapsed (present→submit) over
  active-focus (blur-pause) timing — active-focus is materially more complex and not
  needed for the field's intent (out of scope, spec §2.1). Start timestamp lives in
  reducer state (not a page `useRef`) so timing is node-testable and the page stays
  glue-only (F-R1). No wire/schema/DB change — the column already existed; only its
  source was fabricated. A clock-less `item_loaded` (transition-only tests) stores
  **`NaN`, not `0`**, so the `elapsedMsFrom` `!Number.isFinite` guard stays the single
  authority on "no start captured"; a finite-`0` default was rejected (review FD2) —
  `elapsedMsFrom(0, now)` returns `now`, re-fabricating the exact elapsed D0 kills
  (locked by a red-first contract-guard test). No ⚠️ Ask-first trigger ⇒ no ADR. Spec:
  `docs/plan/quiz-attempt-elapsed-timing.spec.md`.
- 2026-07-03 — **Coach-judge float repair: (1.0, 1.5] clamps to 1.0; only >1.5
  rescales /100** (`_rescale_percentages`, post-merge review W2). The old `>1.0`
  cutover silently inverted a slight 0..1 overshoot into a near-zero score
  (1.5 → 0.015) — a corrupt signal feeding future calibration. Band rationale:
  a real percentage-scale reply lands well above 1.5 (a 1.5% axis score is not
  a plausible verdict), so everything in the band is an overshoot to clamp.
  Rejected leaving it justified-only (GoalJudge precedent covers clamping, not
  this inversion) and rejected rejecting the band outright as unrepairable —
  a 1.02 from a 0..1-scale model is unambiguous.

- 2026-07-02 — **`llm.call.input_text` truncation posture: raised cap + visible
  marker** (§13 audit finding F2). `input_text` alone gets 32 KB
  (`_MAX_INPUT_TEXT_BYTES`) so the persona + coach-context render region is
  auditable; every cut field now ends in `…[truncated]` inside its byte bound.
  Rejected keeping 4 KB + a pre-truncation answer-field scan in the bridge: that
  would hardcode coach domain fields into generic middleware and only answer one
  audit question, while a silent cut stays a vacuous pass everywhere else.

- 2026-07-02 — **DEP layer rules exempt test modules.** `classify_layer` matches the
  first path part in `LAYER_DIRS`, so `tests/services/...` graded as the services layer
  and the reviewer bot rejected PR #120 over a live test's legitimate `components`
  import. `check_dependency_rules` now short-circuits for tests/-tree, `test_*.py`, and
  `conftest.py` paths. Rejected relocating the test instead: the bot would re-trip on
  the next cross-layer test (instance fix); package invariants stay enforced by
  `tests/architecture/` and the unchanged package-path scan.

- 2026-07-02 — **`user_max_cost_per_task` deleted, not wired.** The per-task budget
  override (PLAN.md Story 5.1) had two reads in `orchestration/react_loop.py` and zero
  writers — one read was against a hardcoded empty dict, so it could never fire; the
  global `AgentConfig.max_cost_usd` cap is what actually enforces budget. Rejected wiring
  it through the runtime adapter: no per-user budget store or UI field exists to supply a
  value, so plumbing would be a writer-without-producer (ratchet rule: delete aspirational
  code). Reintroduction path documented in `tests/architecture/test_no_dead_config_knobs.py`.
- 2026-07-02 — **Stage-1 brainstorm premise audit runs before direction generation;
  `refuted` load-bearing premises force a re-pose.** Rejected advisory-only handling
  ("publish refutation but continue on the stated framing") — it preserves direction
  selection atop stale premises, the failure seen across the session's brainstorms.
  Blocking semantics resolved as *correct-and-continue*: the agent re-poses the
  corrected framing in the same document and generates directions over the corrected
  space; the human gate is the confirmation point. Rejected present-and-wait (a full
  round-trip before any directions) — the eval-loop runs that corrected-and-continued
  scored 100% and drew reviewer praise; a mid-brainstorm stop doubles latency for the
  common case where the correction is obvious. Spec: `docs/plan/sdd-brainstorm-hardening.spec.md`.

- 2026-07-02 — **PostCompact hooks CANNOT return `additionalContext` (CC 2.1.185).** A
  live `/compact` rejected `postcompact_reinject.py`'s output with `Hook JSON output
  validation failed — (root): Invalid input`: the harness hook-output schema has no
  PostCompact case, only `UserPromptSubmit` / `PostToolUse` / `PostToolBatch` / `Stop` /
  `SubagentStop` accept `additionalContext`. The S3 design (and this plan's "verified facts")
  had assumed PostCompact would accept it — wrong. Decision: the AGENTS.md re-inject must
  re-home on a schema-accepted event. **RESOLVED same day: re-homed to `SessionStart`
  gated on `source == "compact"`** (`postcompact_reinject.py` → `sessionstart_reinject.py`).
  Official CC docs confirm `SessionStart` accepts `additionalContext` and exposes a
  `compact` source that fires after auto/manual compaction, so the gate reproduces the
  post-compaction timing without injecting on startup/resume/clear. Rejected leaving it on
  PostCompact (non-functional) and `UserPromptSubmit` (fires every turn, needs a
  just-compacted guard). Pure detection/budget helpers + tests transferred unchanged (10
  tests, incl. a new non-compact-source silent-no-op). See
  `docs/research/agenticengineeringplaybook/sdd_lifecycle_harness_integration.plan.md` "S3
  defect".
- 2026-07-02 — **Coach trace-audit binding: coach-shape rules, no new carriers** (agent
  design doc §13). Two rulings: (1) `eval.goal_judge` absent on a completed coach run is
  the EXPECTED shape (ADR-0009 — judgment is post-hoc in the `coach_judges` stream), a
  shape rule mirroring the audit skill's resumed-run Identity precedent, not a weakening;
  (2) the derived `mode`/`question_id` audit evidence rides `task.started`'s recorded
  input — rejected a new observation name/sidecar (curate volume, never truth; the §13.2
  context-contract check reads existing carriers). Amendment lands as a versioned
  `governance_carrier_spec` bump at build step 3, red-first via two coach fixtures.
- 2026-07-02 — **Subject-Coach judge calibration runs the full `llm-eval-grounded-theory`
  lifecycle** (agent design doc §12) instead of a bare three-source bootstrap. ADR-0008
  cond#1's floor (TNR ≥ 0.95 / TPR ≥ 0.90 / κ ≥ 0.75) stays binding; the §12.6
  enable-policy only adds stricter gates (precision, false-action, flip, α, frozen split)
  — augmentation, not amendment, so no ADR change. Judge rubrics ship PROVISIONAL at
  build step 3 (research-prior seeds, telemetry-only); human open/axial coding on shadow
  traces revises them before any gold-set labeling or cert. Rejected: a new ADR (no
  accepted decision changes) and a separate eval design doc (§12 keeps the Stage-4
  sibling-doc structure).
- 2026-07-02 — **Post-compaction re-inject hook is advisory `additionalContext`, bounded
  ≤10 KB** (`scripts/hooks/sessionstart_reinject.py`, SessionStart matcher `compact`,
  HOOK-4; originally wired on PostCompact — see the S3-defect entry above for why it moved).
  Re-injects only the *nested* `AGENTS.md` guides of subtrees with uncommitted changes (root
  is auto-reloaded by the harness — duplicating it wastes the compaction). Rejected
  transcript parsing for "active subtree" (brittle, version-dependent) in favor of
  `git diff` + untracked files; rejected unbounded injection (defeats compaction —
  over budget degrades to a re-read path list). First hook to emit the
  `hookSpecificOutput` JSON shape; contract added as HOOK-4 in `scripts/hooks/AGENTS.md`.
- 2026-07-02 — **Skills mirrors become tracked + mechanically synced.** `.claude/skills/`
  un-gitignored; `scripts/sync_skills.py` (+ `make skills-sync`) copies canonical
  `docs/skills/` → `.claude/skills/` + `.cursor/skills/`; parity arch-test fails CI on
  drift. Why: auto-trigger requires skills in a discovery path — the old "mirror by hand"
  convention had already drifted (`deploy-gcp` mirror-only; `agentsframework-eval-probe`
  copies diverged). Rejected user-level `~/.claude/skills` install (not versioned with the
  repo; invisible to teammates/CI) and docs/skills-only (zero auto-detection).
- 2026-07-01 — **ADR-0005 number collision kept, disambiguated by suffix.** Two records
  share number 0005: `0005-subject-coach-engine-home-and-substrate.md` and
  `0005-reflections-task-id-guard-cross-turn-leak.md` (created on parallel workstreams).
  Decision: keep both, cite the latter as "ADR-0005-reflections"; suffix-disambiguation is
  the accepted convention for a collision discovered post-merge. Rejected renumbering —
  both are linked from `index.md`/`log.md`/design docs and commit messages; breaking those
  references costs more than the numbering wart. New ADRs must still take the next free
  number (0012 is next).
- 2026-07-01 — **Coach surface is routed under `/learn`, not `/`** (Phase 1.1). The
  design/plan placed the Dashboard at `app/(coach)/page.tsx`, which resolves to `/` —
  but `app/page.tsx` (the chat landing) already owns `/`, and Next.js route groups add
  nothing to the URL, so both pages would resolve to `/` → a build-time parallel-page
  collision. Decision: anchor the whole coach surface under a base segment `COACH_BASE`
  (`/learn`): Dashboard=`/learn`, Quiz=`/learn/quiz`, etc.; `/` stays the chat landing.
  Rejected: (a) coach at `/coach` — would double as `/coach/coach` for the Coach screen;
  (b) coach replaces `/` and chat moves to `/chat` — larger blast radius (touches the
  existing chat app's routing + every link to `/`). `COACH_BASE` is the single source of
  truth in `nav_model.ts`; a regression test forbids any screen routing to `/`.
- 2026-07-01 — **`CoachAgentClient` is not an engine port** (reconciliation). ADR-0006's
  port table + `SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md` §3 + the agent brainstorm §4
  list `CoachAgentClient` as an 8th "engine port over the AG-UI SSE transport." The built
  code ships **no** such port: the coach rides the existing **chat `AgentRuntimeClient`** —
  `use_coach` wraps `use_agent_run` (see `frontend/lib/translators/coach_message_vm.ts`
  header). Decision: the coach is a **consumer of the chat runtime port**, not an engine
  port; the engine bounded context stays **7 ports** (→ 8 with ADR-0011's `LearnerReadRepo`,
  still not the coach). Rejected materializing a `coach_agent_client.ts` engine port — it
  would duplicate the AG-UI transport already confined to the chat adapters (ADR-0006 itself
  rejects a new coach transport). Captured so the doc-vs-code divergence doesn't read as a
  missing port. See [SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §5.1/§7.
- 2026-06-30 — ADR-0007 capability-gating derives the coach's bound tool set from
  a **build-time capability list** (`build_graph(bound_capabilities=…)`), not per-run
  from the `agent_capabilities` resolved into state. Rejected per-run binding: it
  would force the `call_llm` node to recompute tool schemas each turn (build-once is
  the current contract) for a benefit — one graph serving many identities — the
  coach doesn't need. Matches the ADR's "graph-build boundary" wording. Flag OFF by
  default (`capability_gating_enabled`); the run-time `authorization_service` PEP is
  unaffected and complementary (bind-time filter + run-time authz).
- 2026-06-28 — ADR.1 ratchet mechanism = a git-diff **arch-test**
  (`tests/architecture/test_adr_ratchet.py`), not a Stop hook. Rejected the
  Stop-hook trigger (harness v2 item 2.1's first option): a hook can't capture the
  typed human answer the gate wants (honest limit), is version-dependent, and
  doesn't run in CI. The arch-test wires the already-shipped pure detector
  (`detect_adr1_missing`) against the merge-base diff and is version-independent.
  Waiver: an `ADR-OK: <reason>` token in a commit message of the range.
- 2026-06-28 — `.cursor/hooks.json` `afterFileEdit` kept `failClosed:false`.
  Rejected flipping it to `true` (the harness plan's blanket contract). Why: the
  post-edit ruff hook is advisory formatting (HOOK-1 never-block-on-edit); a
  formatter hiccup must not block an edit. Scoped deviation, documented inline in
  the file. The safety gate `beforeShellExecution` stays `failClosed:true`.
- 2026-07-03 — `meta/subject_coach_corpus_harvest.py`: `harvest_corpus`'s gate
  report covers only the rows it returns; `main` re-summarizes the union with the
  existing corpus file for the operator verdict. Why: the pure function can't see
  the on-disk corpus, and a gate verdict over a partial view would read as met/
  unmet dishonestly. Also promoted the sampler's `_mode_of`/`_latest_turn_per_task`
  to public (`mode_of`/`latest_turn_per_task`) rather than importing privates.
- 2026-07-04 — `services/governance/coach_calibration.py` (Task 3.8) is **fully
  self-contained**: it defines its own `CoachConfusion` 2×2 tally + rate helpers
  (`tpr`/`tnr`/`precision`/`false_action_rate`/`flip_rate`) and imports **nothing**
  from `goaljudge_calibration`. This re-tallies a leak-class confusion matrix that
  AP-6 nominally warns against duplicating. Why: the coach leak-class 2×2 is a
  distinct, trivial 4-line count, and full decoupling keeps coach governance
  independent of GoalJudge's cert evolution (different positive class, different
  binding floors TPR≥0.90/TNR≥0.95/κ≥0.75). The κ is NOT re-derived — it reuses the
  shared `services.governance.iaa.krippendorff_alpha_nominal` (NaN→None). No `meta/`
  import (services↛meta). Kept the tally trivially correct so the duplication
  carries no logic risk.
- 2026-07-04 — Task 3.7c (coach gold-set human IAA) mirrors the GoalJudge Stage-5
  instrument shape (`docs/IAA/coach/goldset/`: README protocol + two blind
  annotator sheets + combined skeleton) rather than inventing a new one. Why: the
  house double-label pattern is proven; α is scored on the single gated axis
  `answer_leakage` (not the six pedagogy pass-axes, which the judge scores).
  `scripts/compute_coach_goldset_alpha.py` reuses
  `iaa.krippendorff_alpha_nominal` (NaN→None, never a fake 0.0) — no forked math.
- 2026-07-04 — Task 3.8b (`scripts/run_coach_calibration.py`) does NOT pre-guard
  the provisional manifest; it passes the labels straight to
  `evaluate_coach_enable_gates` and lets the evaluator's `_is_v1_freeze` own the
  `REFUSE_PROVISIONAL` short-circuit. Why: keep the fail-closed rule in ONE place
  (the L1 evaluator), so the harness can't drift from it. `cert_payload` builds
  the JSON dict field-by-field instead of `dataclasses.asdict` — `asdict`
  deep-copies the decision's frozen `mappingproxy` gate/diagnostic views and
  raises `TypeError: cannot pickle 'mappingproxy'`. Regression-tested.
- 2026-07-05 — Coach corpus-expansion FR-5 amended mid-implement (sdd-replan): the
  292-turn shadow corpus carries **no leak label** (leakage is a property of the
  coach_reply, revealed only by E4 human labeling), so `sample_coach_dev_rows.py`
  cannot target a *measured* leak share. It oversamples by a **bait-signal proxy**
  on the learner utterance ("just tell me the answer", "which concept to look up",
  "definitely wrong") — raising the leak prior — and the actual `leak_class_share`
  is measured post-labeling and reported in the manifest. Alternative (label a
  bigger pool then sample to hit 0.20–0.25 exactly) was rejected: it inflates the
  labeling burden past the ~210 min-burden decision. The test batch (E2) carries
  the guaranteed channel coverage instead.
- 2026-07-05 — Coach E4 (round-2 double-label) uses **two independent human
  raters** + an adjudicator (not human-vs-judge, not one-person-two-passes). Why:
  α must measure genuine inter-annotator agreement; a judge-as-rater is partly
  circular (the judge is what the cert tests) and a single-person double-pass
  measures intra-rater consistency, which overstates trust. The α-fail recovery is
  **bounded to 2 revise-relabel rounds**, then STOP + escalate — prevents
  over-fitting the walkthrough guideline to these specific rows / endless
  re-labeling. Playbook: `docs/plan/coach-goldset-e2e4-human-playbook.{spec,plan}.md`.
- 2026-07-05 — Coach E6 (non-provisional re-freeze) treats the **adjudicated IAA
  combined sheet as the single source of truth** for the freeze, not a re-merge of
  the dev sample + test batch + labels from three files. Why: the combined sheet is
  what E4 actually blessed — it already carries the join (dev synthetic + test
  fresh-authored), item context, and the gold `adjudicated_answer_leakage`; a
  parallel re-assembly path could silently drift from the labeled artifact.
  `rows_from_combined_sheet` **fails closed on a blank adjudicated cell** (never
  defaults a missing adjudication to a label — that would invent gold), and
  `build_rows` runs `assert_dev_test_disjoint` so a contaminated freeze can't be
  written. `leak_channel` stays **null** on every gold row: raters labeled only the
  binary `answer_leakage` (the sole gated axis), so a per-row channel would be a
  fabricated attribution (AP-6); the firewall permits a null channel on a leak row.
  The three pre-E6 tests that asserted the *fixture* was provisional were repointed
  (G8-aware) at a synthetic provisional artifact so the `REFUSE_PROVISIONAL`
  contract stays covered while the committed fixture legitimately advances to the
  246-row non-provisional v1 (α=0.834, test split 116 / 29-leak). Rejected keeping
  those tests on the shared fixture (they'd assert a now-false fact) and rejected
  deleting them (loses fail-closed coverage). E7 (live cert) reads it.
  `scripts/assemble_coach_goldset.py --combined-sheet`.
- 2026-07-06 — Coach Phase-5 leakage-gate **replan**: the enforce design puts the
  certified answer-leakage judge **inline** in `orchestration/evaluate_node`, which
  `tests/architecture/test_coach_judges_never_inline.py` forbids (it enforces
  **ADR-0009** — coach judges are OFF-GRAPH / `meta/`-sampler-only). Decision:
  **ADR-0020 supersedes ADR-0009 *with conditions*** rather than delete the gate.
  Why a supersede, not a test edit: ADR-0009 is Accepted, names answer-leakage as a
  risk of inline *Reflexion* (convergence toward the answer), and defines a reversal
  trigger. A leak-**safety** gate is the opposite intent, and all three ADR-0009
  reversal preconditions are met — (a) `reflections` cross-turn leak fixed
  (ADR-0005); (b) a coach-specific leak-aware judge, not the task-failure critique;
  (c) the judge is certified TNR 1.0/TPR 1.0 on the frozen split (ADR-0019). The
  OFF-GRAPH rule is **narrowed, not deleted**: the Reflexion/GoalJudge/sampler inline
  path stays forbidden; the leakage gate gets ONE named, declared binding (spec
  FR-12/FR-13). Rejected alternatives: delete-the-arch-test (loses the Reflexion
  guard), middleware-enforce (same arch test forbids middleware, same ADR cost),
  shadow-only-defer-enforce (defensible, smaller — but drops the enforce goal the
  cert was for). T1–T3 (pure decision + config mode) landed before the blocker and
  are graph-clean, so they stand. New gating task P0.5 ships the ADR + narrowed test
  together (ratchet + G8 no-test-weakening require it).
  Bundle: `docs/plan/coach-leakage-gate-rollout.{spec,plan,tasks}.md`.
- 2026-07-06 — Coach Phase-5 **post-review polish + Step 0** (no new ADR — both are
  changes *within* the already-ADR'd ADR-0020 seam, not a new one). **M1/M2** (design
  review): the regen directive moved from a hardcoded `_COACH_NO_LEAK_DIRECTIVE`
  constant to `prompts/coach_regenerate_no_leak.j2` rendered via `PromptService`
  (AP-3); the `evaluate_node` call-site deduped the double `get_profile` call and the
  `judge`/`regenerate` params tightened from `Any` → `LeakageJudge` /
  `Callable[..., Awaitable[str]]`. **Step 0**: `build_runtime_graph` now forwards
  `coach_goldset_certified` from a new `COACH_LEAKAGE_CERT_ATTESTED` setting (default
  OFF) — the composition wire Recipe 9 flagged, so `arm()` can honour shadow/enforce
  on an attested deployment (fail-safe: un-attested ⇒ pinned off). Why no ADR: the
  inline binding, the enforcement policy, and the graph contract are all unchanged —
  ADR-0020 already governs them; these only refactor the act and thread an existing
  `build_graph` param through composition. The `stop_adr_reminder` hook re-fires on
  the dirty `react_loop.py` but the merge-time `test_adr_ratchet.py` passes (nothing
  un-ADR'd in range). Also: a pre-existing G8 blocker on the branch
  (`ed029b6`'s arch-test rename lacked per-test `# G8-OK:` waivers) was cleared with
  two named waiver comments.
