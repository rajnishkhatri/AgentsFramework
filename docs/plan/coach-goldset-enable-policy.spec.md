# Spec — Coach gold set + enable-policy cert (Phase 3: §12.1–12.6)

**Status:** Revised — 2026-07-03 (critical review pass; clarify C9–C12 added; Stage-4 cross-check fixes applied — 6 missing tests added, 3.7b test file + 3.2b dependency; **Task-3.3 executable expansion folded into FR-G3.1** — FR-G3.1.1–.12 + §8 tests, from the 3.3 SDD spec pass; Stage-4 caught the `outcomes.jsonl`-has-no-answer join defect → reuse `build_coder_rows`)
**Owner:** Rajnish Khatri
**Related:**
- [subject-coach-agent.plan.md](subject-coach-agent.plan.md) (Phase 3 sprint board 3.0–3.9; Phase 5 gated on 3.9)
- [subject-coach-agent.spec.md](subject-coach-agent.spec.md) (parent spec §7 NFR floor; FR-14..18 judges; ADR-0008 cond#1)
- [ADR-0008](../adr/0008-subject-coach-judges-grader-and-pedagogy.md) (acceptance condition #1 — the κ/TPR/TNR floor this cert closes)
- Design doc §12 ([SUBJECT_COACH_AGENT_DETAILED_DESIGN.md](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md))
- Precedents: `services/governance/goaljudge_goldset_dataset.py`, `goaljudge_calibration.py`, `scripts/assemble_goaljudge_goldset.py`
- Corpus infra (BUILT): `scripts/build_coach_shadow_corpus.py`, `meta/subject_coach_corpus_harvest.py`
- Open-coding ops: [agentsframework-open-coding/SKILL.md](../skills/agentsframework-open-coding/SKILL.md)

> **Scope discipline.** This spec owns Phase 3 only — the grounded-theory pipeline from
> environment posture through `coach_goldset_v1` freeze and the `evaluate_coach_enable_gates`
> cert that unlocks Phase 5 flag flips. It does **not** re-spec the coach runtime (Phases 1–2),
> hint/test generators (Phases 4/6), or Phase 5 rollout / §12.7 monitoring (separate plan
> slice after `ENABLE`). It **implements** ADR-0008 condition #1; it does not amend ADR-0008.

---

## Clarify decisions (ratified 2026-07-03)

| # | Ambiguity | Decision | Evidence |
|---|---|---|---|
| C1 | Corpus growth path while deploy deferred | **Synthetic batches are the gate path**; production Cloud Logging harvest is a later supplement only | Plan corpus decision v2; batch 2 = 292 turns (146/mode) |
| C2 | Raw-volume vs coded-volume gate | **≥100 coded turns/mode** is the binding Phase-3 entry; raw 146/mode already MET and is necessary but not sufficient | Design §12.1; `GATE_TURNS_PER_MODE=100` in harvest |
| C3 | Action-trigger class | **`answer_leakage` only** gates enable; all other judge axes are reported telemetry | ADR-0008; design §12.6 |
| C4 | Binding metric floor | **TNR ≥ 0.95, TPR ≥ 0.90, κ ≥ 0.75** on frozen test split; augmenting gates (precision ≥ 0.90, false-action ≤ 2%, flip ≤ 5%, human α ≥ 0.80) tighten, never weaken | Parent spec §7; design §12.6 table |
| C5 | Gold-set sizing / split | **200–300 rows**, leak-class oversample, **60/40 dev/test** frozen+hashed at assembly; synthetic rows **dev only** (contamination firewall) | Mirror `GoldsetItem` firewall pattern |
| C6 | Human coding tooling | Reuse **agentsframework-open-coding** coder UI; coach export adapter produces coder-compatible JSONL (task_id as trace key when Langfuse absent) | `serve_open_coder.py`, `export_coded_to_dataset.py` |
| C7 | Rubric posture through cert | Judges stay **telemetry-only** (`COACH_*_ENABLED=false`) until cert `ENABLE`; rubric revision (Stage 4) labels gold set, never the reverse | Design §12.0 provisional-first loop |
| C8 | Optional strata gap-fill | **Run only if** axial taxonomy (Stage 2) exposes uncovered rare classes; never re-roll mismatches (AP-9) | Plan task 3.5 OPTIONAL |
| C9 | Posture data source | **EvalRecord-only** posture from `logs/evals.log` / harvest stream: `coach_mode` carrier (+ legacy marker fallback via `mode_of`); **not** a blackbox `guardrail_checked` join (that is the §13 governance-audit fixture path, already built) | `react_loop.py:2373–2378`; `meta/subject_coach_judge_sampler.mode_of` |
| C10 | Holdout ledger | Deterministic **SHA-256(task_id, seed)** holdout file (`holdout_ledger.json`) disjoint from coding export; same seed reproduces split | Mirror `freeze_l2l3_goldset_seed.py` discipline |
| C11 | Open-coder wire shape | Export maps `trace_id←task_id`, `prompt←learner_utterance`, `final_answer←coach_reply`; carry `mode`, `question_id`, `provenance`, `stratum` in metadata | `serve_open_coder._validate_jsonl` requires `trace_id` |
| C12 | Eval-capture truncation | Harvest rows use eval-capture caps (**200** char `task_input`, **500** char `coach_reply`, **no** truncation marker). Open coding uses these caps; **gold-set assembly joins batch manifest** for full text | `react_loop.py:2374,2386` |

---

## Critical review notes (2026-07-03)

Honest gaps found in the first draft and fixed below:

| Severity | Finding | Resolution |
|---|---|---|
| **CRITICAL** | FR-G1.1 referenced blackbox `coach_context_contract` carriers not present on `EvalRecord` harvest rows | C9 + revised FR-G1.1 use eval-log `coach_mode` / `mode_of` |
| **CRITICAL** | FR-G1.2 referenced `llm.call.input_text` + `…[truncated]` — wrong layer; eval capture hard-caps without marker | C12 + revised FR-G1.2 marks `partial_context`; gold-set joins manifest |
| **HIGH** | FR-G2.1 holdout had **zero** automated test in §8 | Added test + FR-G2.4 field-map FR |
| **HIGH** | Coded-vs-raw gate (C2) not enforced after posture filter | FR-G2.5 shortfall report |
| **HIGH** | Open-coder requires `trace_id`/`prompt`/`final_answer`; spec only named coach fields | FR-G2.4 + C11 |
| **MEDIUM** | `components/coach_context.coach_context_contract` path wrong (module is `.py`) | Fixed in §4 |
| **MEDIUM** | `failure_mode` frozen set undefined until axial doc; 3.7a dependency understated | Task 3.6b extracts taxonomy artifact |
| **MEDIUM** | Design §12.6 production-only precision subset absent from FR-G6 | FR-G6.6 diagnostic report |
| **LOW** | Parent plan 3.2 cited `push_open_codes_to_langfuse.py` for Stage-1 coding | Stage-1 uses `export_coach_coding_sample.py` + `serve_open_coder.py`; Langfuse push is post-coding optional |
| **CRITICAL** | Stage-4 cross-check: 6 FRs had no automated test in §8 (FR-G4.2, G4.3, G5.5, G5.7, G6.3, G6.7) | Added 6 named tests to §8 (FR-G4.2/G4.3 → judge-prompts; FR-G5.5/G5.7 → goldset-dataset; FR-G6.3/G6.7 → calibration) |
| **HIGH** | Task 3.7b (assembly) listed no test file | Added `tests/services/test_coach_goldset_dataset.py` to 3.7b file list (Option A — assembly invariants share the dataset test module) |
| **MEDIUM** | Task 3.7b missing dependency on 3.2b (holdout ledger seeds test-split candidacy per FR-G5.4) | Added 3.2b to 3.7b `Depends` column |

---

## 1. Goal

Close **ADR-0008 condition #1**: produce a human-grounded, frozen **`coach_goldset_v1`**
and an **`evaluate_coach_enable_gates`** cert report so the platform can decide — with
recorded evidence — whether the Pedagogy judge's **`answer_leakage`** flag is trustworthy
enough to flip **`COACH_LEAKAGE_GATE_ENABLED`** (Phase 5). Until `ENABLE`, the flag stays
telemetry-only forever.

## 2. Context

Phases 1–2 shipped the coach shadow path, judges, and sampler; Phase 4/6 shipped governed
content families. The judges' rubrics are **PROVISIONAL** (research-prior seeds). Batch-2
shadow corpus infrastructure landed in PR #124: **292 raw turns, 146/mode**, with known
failure surfaces (rule-naming-as-leak, grader not refusal-aware, FR-7 adversarial false-reject
backlog).

The GoalJudge program already walked this path (`goaljudge_goldset_v1` →
`evaluate_section_2_8_gates`). Phase 3 mirrors that artifact family for the coach's
**leak-class** gate field, with mode (`pre_submit` | `post_feedback`) as a mandatory
stratification dimension (leak is only *defined* pre-submit per ADR-0012).

**Ratified constraints this spec implements, never re-opens:**
- Never tune guardrail/persona/judge prompts on the frozen test split (§9 discipline).
- No live LLM on the CI hot path; cert replay is on-demand behind flags.
- No `trust/models.py` change; no new graph node; judges remain off-graph in `components/`.

---

## 3. Functional requirements (EARS)

Failure paths first within each family (TAP-4).

### FR-G1 — Environment posture (garbage-in guard)

- **FR-G1.1** IF a coach `EvalRecord`'s derived mode (`mode_of`, preferring
  `ai_input["coach_mode"]` when present) disagrees with the batch manifest mode for that
  `task_id` THEN THE SYSTEM SHALL classify the turn as an **environment confound** and
  SHALL exclude it from the coach-behavior coding sample (never count as a coach failure).
- **FR-G1.2** IF a coach turn lacks a verifiable mode carrier (`coach_mode` absent AND no
  legacy post_feedback marker in `ai_input.task_input`) THEN THE SYSTEM SHALL classify it
  as an **environment confound** (pre-F1 or malformed capture).
- **FR-G1.3** IF a row is pre_submit AND eval-capture truncated `task_input` at 200 chars
  (always when source length > 200 — no marker is recorded) THEN THE SYSTEM SHALL mark it
  **`partial_context`**: eligible for open coding, **excluded from gold-set test-split
  holdout candidacy** (full-text join required at assembly — FR-G5.6).
- **FR-G1.4** WHEN the posture checker runs over a harvest input THEN THE SYSTEM SHALL
  emit `{coding_eligible, confound_rows, partial_context_rows, report}` with counts only —
  never a fabricated quality score (AP-6).

### FR-G2 — Corpus draw + coding-sample holdout

- **FR-G2.1** WHEN drawing the Stage-1 coding sample THEN THE SYSTEM SHALL hold out a
  **disjoint** row set (deterministic hash ledger — C10) reserved for `coach_goldset_v1`
  test split candidacy; no `task_id` appears in both coding sample and holdout ledger.
- **FR-G2.2** THE SYSTEM SHALL write the holdout ledger to a versioned path
  (`cache/coach_shadow/holdout_ledger.json` or caller `--holdout-out`) so re-runs with the
  same seed reproduce the split.
- **FR-G2.3** THE SYSTEM SHALL export coding-eligible rows to open-coder-compatible JSONL
  with required keys **`trace_id`**, **`prompt`**, **`final_answer`** (C11 field map) plus
  metadata (`mode`, `question_id`, `provenance`, `stratum` when known).
- **FR-G2.4** IF a row fails posture confound rules (FR-G1.1–G1.2) THEN THE SYSTEM SHALL
  NOT include it in the coding export.
- **FR-G2.5** WHEN posture filtering completes THE SYSTEM SHALL report per-mode counts; IF
  any mode has fewer than **`GATE_TURNS_PER_MODE` (100)** coding-eligible rows THEN THE
  SYSTEM SHALL emit an explicit **shortfall** (AP-6 — never imply the coded gate is met
  from raw harvest counts alone).

### FR-G3 — Human open + axial coding (process gates)

- **FR-G3.1** WHEN Stage-1 open coding runs THE **human coder** SHALL read ≥100 coach
  turns end-to-end **per mode** before saturation is declared (~20 consecutive traces
  adding no new code — AP-10: LLM assist only at clustering, never first-pass coding).

  > **Task 3.3 executable expansion** (folded in from the 3.3 clarify pass, 2026-07-03).
  > Decisions: code the **merged coding-eligible** pool (`merged_batch2_2b_manifest.json`
  > joined to `batch2{,b}/outcomes.jsonl`, ~122 pre / ~115 post) — **not** the 169-row
  > `batch2b_coding_sample.jsonl`, which under-fills both modes; saturation is attested by a
  > **per-mode saturation log** (checkable, not prose); coded cases are additionally upserted
  > to a Langfuse review dataset. The coder + exporter are **reused** from the open-coding
  > skill (no new service/node/abstraction/dependency → no ADR trigger). Failure paths first
  > (TAP-4):
  >
  > - **FR-G3.1.1** IF the cases builder is asked to include a turn the posture checker
  >   classifies as `confound` or refused THEN THE SYSTEM SHALL exclude it from `cases.json`
  >   (only `coding_eligible` + `partial_context`; parity with FR-G1.x/FR-G2.5).
  > - **FR-G3.1.2** IF either mode's eligible pool yields fewer than **100** rows THEN THE
  >   builder SHALL exit non-zero naming the short mode (fail-closed against a silent
  >   sub-floor session — the exact defect the 169-row sample would introduce).
  > - **FR-G3.1.3** IF a coding-eligible EvalRecord cannot be resolved to full learner/coach
  >   text (the manifest join in the reused `build_coder_rows` yields no answer) THEN the
  >   builder SHALL surface it as an error and exclude it — no blank-answer cards (AP-6 — no
  >   fabricated placeholder). *(Stage-4: the answer/text lives in `logs/evals.log`
  >   EvalRecords + batch `manifest.json`, NOT `outcomes.jsonl` — reuse the export's join,
  >   don't re-derive one.)*
  > - **FR-G3.1.4** IF the coded JSONL contains a row whose `open_codes` is empty THEN THE
  >   verification step SHALL report that row's `trace_id` and the per-mode uncoded count
  >   (the memo-not-a-code trap; skill Step-4 guard).
  > - **FR-G3.1.5** WHEN the cases builder runs THE SYSTEM SHALL write `cases.json` with ≥100
  >   rows per mode, each carrying `trace_id, mode, stratum, question_id, prompt,
  >   final_answer` (+ extra manifest keys, which survive round-trip into dataset metadata).
  >   *(A `--cap-per-mode` bound is supported — deterministic prefix of the seeded sort — to
  >   cap the human reading load AT the floor; a cap below `min_per_mode` is rejected. 3.3e
  >   caps at 100/mode → 200 cards.)*
  > - **FR-G3.1.6** WHEN the cases builder runs THE SYSTEM SHALL order rows so each mode is a
  >   contiguous block (saturation is judged per mode → the human reads one mode as one run).
  > - **FR-G3.1.7** WHEN the builder selects rows under a fixed seed THE SYSTEM SHALL be
  >   deterministic (same seed → same `cases.json` row set and order).
  > - **FR-G3.1.8** WHEN the human declares saturation THE SYSTEM SHALL record, per mode in
  >   `coach_phase2_open_coding.md`, the trace index of the last-new-code and the length of
  >   the trailing no-new-code run (≈20) — saturation independently checkable, not asserted.
  > - **FR-G3.1.9** THE SYSTEM SHALL persist `coach_step1_open_code_inventory.csv` with the
  >   GoalJudge inventory columns (`code, short_definition, source_doc, first_seen_case,
  >   alias_note, example, example_ref`), one row per distinct code.
  > - **FR-G3.1.10** THE SYSTEM SHALL persist `coach_phase2_open_coding.md` with: method (incl.
  >   the AP-10 human-first statement), the per-mode saturation log (FR-G3.1.8), the
  >   code-frequency table, and downstream insights for axial coding — mirroring
  >   `goaljudge_phase2_open_coding.md`.
  > - **FR-G3.1.11** WHERE Langfuse persistence is enabled THE SYSTEM SHALL upsert the coded
  >   cases to dataset `coach-phase3-open-coding` idempotently (item id = `uuid5(trace_id)`),
  >   with `input={prompt, mode, question_id}`, `expected_output=final_answer`,
  >   `metadata={open_codes, memo, stratum, …}`, and a `source_trace_id` back-link.
  > - **FR-G3.1.12** THE Langfuse export SHALL default to a **dry run**; it SHALL write only
  >   when `--write` is passed after the dry run is eyeballed.
- **FR-G3.2** WHEN Stage-2 axial coding completes THE **human coder** SHALL produce 5–6
  **testable** coach-behavior categories with environment confound and judge-reliability
  axes split out; **IAA ≥ 0.80** on category assignment.
- **FR-G3.3** THE SYSTEM SHALL persist artifacts:
  `docs/research/coach_phase2_open_coding.md`,
  `docs/research/coach_step1_open_code_inventory.csv`,
  `docs/research/coach_phase3_axial_coding.md`,
  `docs/research/coach_evaluation_pipeline_open_axial_coding_rubric.md`.

### FR-G4 — Rubric revision (PROVISIONAL → REVISED)

- **FR-G4.1** WHEN the axial taxonomy is frozen THE SYSTEM SHALL revise
  `prompts/subject_coach_grader_judge.j2` and `prompts/subject_coach_pedagogy_judge.j2`
  from grounded codes — including **refusal-aware** grader criteria and an explicit
  **`rule-naming-as-leak`** binarized check — and SHALL mark prompt headers **REVISED**
  (no longer PROVISIONAL). **Acceptance criteria** for this revision are the baseline
  judge failures recorded in
  [coach-judge-validation-3.5f-handoff.md](coach-judge-validation-3.5f-handoff.md)
  (Task 3.5f): both `gpt-4o` and `claude-opus-4-8` score TPR=0.000 on the 5 indirect
  leaks — the revision passes only when a re-recorded baseline flips those to catches
  while holding controls (TNR=1.000).
- **FR-G4.2** IF a rubric criterion cannot be mapped to a taxonomy category THEN THE
  SYSTEM SHALL NOT ship it (orphan criteria are a spec violation).
- **FR-G4.3** WHILE rubrics are REVISED but cert is incomplete THE SYSTEM SHALL keep
  `COACH_LEAKAGE_GATE_ENABLED=false` and all judge LLM flags default OFF.

### FR-G5 — `CoachGoldsetItem` + `coach_goldset_v1` assembly

- **FR-G5.1** THE SYSTEM SHALL define `CoachGoldsetItem` in `services/governance/` with
  `extra="forbid"`, fields per design §12.5 sketch, and a **contamination firewall**:
  `provenance=synthetic` ⇒ `split=dev` only (mirror `GoldsetItem`).
- **FR-G5.2** IF `answer_leakage` is missing on a gold row THEN THE SYSTEM SHALL reject
  assembly (`ValidationError`) — never default to `False` (fail-open forbidden).
- **FR-G5.3** IF `failure_mode` is set and not in the frozen taxonomy set THEN THE SYSTEM
  SHALL reject the row at parse time.
- **FR-G5.4** WHEN assembling `coach_goldset_v1` THE SYSTEM SHALL produce **200–300 rows**
  with leak-class oversample, 60/40 dev/test split, test-split SHA-256 frozen at assembly,
  and Langfuse dataset name **`coach_goldset_v1`** (version bumps → `coach_goldset_v2`, never
  in-place edits). Holdout ledger rows (FR-G2.1) seed test-split candidacy; synthetic rows
  remain dev-only (firewall).
- **FR-G5.5** WHEN double-labeling completes THE SYSTEM SHALL require **α ≥ 0.80 on
  `answer_leakage`** (human–human) before the manifest is marked cert-ready; undecidable α
  ⇒ refuse (AP-6).
- **FR-G5.6** WHEN assembling gold-set rows from eval-harvest sources THE SYSTEM SHALL join
  the batch manifest (or equivalent source-of-truth) to recover **full** `task_input` and
  `coach_turn` text when eval capture truncated them (C12).
- **FR-G5.7** THE `CoachGoldsetItem` pedagogy axes SHALL include **`mistake_location_pass`**
  (live `PedagogyVerdict` field) alongside the §12.5 sketch axes — reported telemetry, not
  gating.

### FR-G6 — Enable-policy cert (`evaluate_coach_enable_gates`)

- **FR-G6.1** IF the gold-set manifest is provisional or fails assembly invariants THEN
  THE SYSTEM SHALL return verdict **`REFUSE_PROVISIONAL`** before reading any metric
  (mirror `evaluate_section_2_8_gates`).
- **FR-G6.2** WHEN evaluating on the **frozen test split** THE SYSTEM SHALL compute
  class-specific metrics on `answer_leakage` (positive = leak): **TPR ≥ 0.90**, **TNR ≥
  0.95**, **κ ≥ 0.75** — binding gates; undecidable metric ⇒ **`REFUSE`**.
- **FR-G6.3** WHERE augmenting gates apply THE SYSTEM SHALL also evaluate **precision ≥
  0.90**, **false-action rate ≤ 2%** on clean turns, **flip rate ≤ 5%** (soft 10%), and
  SHALL report ECE **diagnostic-only** (never gated).
- **FR-G6.4** WHEN all binding + augmenting gates pass on the frozen test split THE SYSTEM
  SHALL emit verdict **`ENABLE`** with per-gate pass/fail reasons; THE SYSTEM SHALL NOT
  flip runtime flags automatically (human Phase-5 step).
- **FR-G6.5** IF any binding gate fails THEN THE SYSTEM SHALL emit **`REFUSE`** and the
  leakage flag SHALL remain telemetry-only.
- **FR-G6.6** WHERE the frozen test split contains **`provenance=production`** rows THE
  SYSTEM SHALL also report **precision on that subset** (diagnostic — design §12.6
  augmentation; base-rate-sensitive, never weakens binding gates).
- **FR-G6.7** WHERE non-gating judge axes are present on replay THE SYSTEM SHALL report
  per-criterion κ and mark axes below **0.6** as **unreliable telemetry** (design §12.6;
  diagnostic-only, never gates `ENABLE`).

### FR-G7 — Optional synthetic strata gap-fill

- **FR-G7.1** WHERE the axial taxonomy exposes an uncovered rare stratum THE SYSTEM MAY
  run a targeted synthetic batch (`build_coach_shadow_corpus.py` quota mode) into **dev
  split only**.
- **FR-G7.2** IF a synthetic row's mode or manifest slot mismatches THE SYSTEM SHALL
  record the mismatch and SHALL NOT re-roll the utterance (AP-9).

---

## 4. Data model / contracts

| Contract | Shape (sketch) | Home |
|---|---|---|
| `CoachCorpusRow` | `{task_id, mode, learner_utterance, coach_reply, …}` | `meta/subject_coach_corpus_harvest.py` (exists) |
| `PostureReport` | `{coding_eligible, confound_rows, partial_context_rows, per_mode, shortfall}` | `meta/coach_corpus_posture.py` (new) |
| `HoldoutLedger` | `{seed, task_ids: [...], created_at}` | `cache/coach_shadow/holdout_ledger.json` |
| `CoderExportRow` | `{trace_id, prompt, final_answer, mode, question_id, provenance, stratum?, meta}` | `scripts/export_coach_coding_sample.py` JSONL |
| `CoachGoldsetItem` | design §12.5 + `mistake_location_pass`; provenance enum mirrors `GoldsetProvenance` | `services/governance/coach_goldset_dataset.py` (new) |
| `COACH_FAILURE_MODES` | frozen set parsed from axial taxonomy artifact | loaded in `coach_goldset_dataset.py` (task 3.6b) |
| `COACH_GOLDSET_V1` | `"coach_goldset_v1"` | constant mirroring `GOALJUDGE_GOLDSET_V1` |
| `CoachGoldsetManifest` | `{frozen_at, test_split_hash, row_counts, human_alpha_answer_leakage, rubric_version, taxonomy_version}` | assembly output JSON |
| `CoachEnableGateDecision` | `{verdict: ENABLE\|REFUSE\|REFUSE_PROVISIONAL, gates: {...}, reasons: [...]}` | `services/governance/coach_calibration.py` (new) |
| `COACH_ENABLE_THRESHOLDS` | TPR/TNR/κ/precision/false-action/flip mapping | same module |

**No `trust/models.py` change** — no kernel re-sign trigger.

---

## 5. Invariants & security boundaries

| Invariant | How this spec holds it |
|---|---|
| #1 Downward deps | Posture + harvest in `meta/`; goldset + cert in `services/governance/`; rubrics in `prompts/` |
| #2 Trust purity | No `trust/` edits |
| #3/#4 Framework-agnostic | No `langgraph`/`langchain` in new governance modules |
| #6 Thin nodes | No graph changes; cert is offline |
| #8 Meta reads logs | Posture/harvest read `EvalRecord` streams only |
| AP-6 | Undecidable metrics → `None` / `REFUSE`, never fabricated pass |
| AP-9 | Record mismatches; never silently re-roll synthetic inputs |
| AP-10 | Human first-pass coding; LLM assist clustering only |
| Live LLM in CI | Cert replay + judge calls are on-demand; CI uses pure L1 metric tests with pinned fixtures |

---

## 6. Edge cases

- **Guardrail-refused turns** (no `target=subject_coach` record) — excluded by construction; never coded.
- **Eval-capture 200/500 caps** — open coding sees truncated text; gold-set assembly must manifest-join (C12).
- **Pre-F1 records** (no `coach_mode`) — confound unless legacy marker resolves mode; batch-2 synthetic should be F1+.
- **Post-feedback "leak" labels** — treat as confound for the leak gate (answer already visible); still coded for pedagogy axes.
- **Batch utterances used for guardrail tuning** — never reused for prompt/rubric revision validation (§9); FRESH text only.
- **Duplicate task_id on re-harvest** — dedupe via existing `existing_task_ids`; report `deduped` count.
- **Single-rater gold row** — fail assembly (double-label required for gate field).
- **All-leak or all-clean test split** — TPR/TNR undecidable ⇒ `REFUSE`.
- **Empty production-only test subset** — FR-G6.6 reports `N/A` (expected pre-launch); never weakens binding gates.
- **Langfuse unavailable** — local manifest + JSONL export remains authoritative; Langfuse upsert is optional in `--dry-run`.

---

## 7. Non-functional requirements

- **Pyramid layering:** posture/export/assembly invariants = **L1**; human coding = **L3** process gate; cert metrics = **L1** pure functions; full cert replay = **L3** on-demand.
- **Determinism:** test-split hash and coder export ordering are deterministic given input + seed.
- **Reversibility:** `COACH_LEAKAGE_GATE_ENABLED` stays `false` until human accepts `ENABLE` report (Phase 5).
- **Cost:** full cert replay is bounded to frozen test split (~80–120 rows); not in CI.

---

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|---|---|---|---|
| FR-G1.1 | `tests/meta/test_coach_corpus_posture.py::test_mode_manifest_mismatch_is_confound` | L1 | yes |
| FR-G1.2 | `…::test_missing_coach_mode_carrier_is_confound` | L1 | yes |
| FR-G1.3 | `…::test_partial_context_excluded_from_holdout` | L1 | yes |
| FR-G1.4 | `…::test_report_counts_only_no_quality_score` | L1 | yes |
| FR-G2.1 | `tests/scripts/test_export_coach_coding_sample.py::test_holdout_disjoint_from_coding_sample` | L1 | yes |
| FR-G2.2 | `…::test_holdout_ledger_deterministic_by_seed` | L1 | yes |
| FR-G2.3 | `…::test_coder_jsonl_trace_id_field_map` | L1 | yes |
| FR-G2.4 | `…::test_confound_excluded_from_export` | L1 | yes |
| FR-G2.5 | `…::test_posture_shortfall_when_under_gate` | L1 | yes |
| FR-G3.1.2 | `tests/scripts/test_build_coach_open_coding_cases.py::test_rejects_submfloor_mode` | L1 | yes |
| FR-G3.1.3 | `…::test_rejects_unjoined_trace_id` | L1 | yes |
| FR-G3.1.1 | `…::test_excludes_confound_and_refused` | L1 | yes |
| FR-G3.1.5 | `…::test_cases_have_min_100_per_mode_and_required_keys` | L1 | yes |
| FR-G3.1.6 | `…::test_modes_are_contiguous_blocks` | L1 | yes |
| FR-G3.1.7 | `…::test_deterministic_for_fixed_seed` | L1 | yes |
| FR-G3.1.4 | `tests/scripts/test_verify_coded_open_codes.py::test_flags_empty_open_codes_rows` | L1 | yes |
| FR-G3.1.9 | `tests/scripts/test_build_coach_open_code_inventory.py::test_csv_has_goaljudge_columns` | L1 | yes |
| FR-G3.1.11 | `tests/scripts/test_export_open_coding_dataset.py::test_item_shape_and_idempotent_id` (dry-run, no network) | L1 | yes |
| FR-G3.1.12 | `…::test_defaults_to_dry_run_no_write` | L1 | yes |
| FR-G3.1.8, .10 | Manual gate — per-mode saturation log + phase2 doc + inventory CSV exist | L3 | no (human) |
| FR-G3.2, G3.3 | Manual gate — axial artifacts exist + IAA worksheet (Task 3.4) | L3 | no (human) |
| FR-G4.1 | `tests/components/test_subject_coach_judge_prompts.py::test_rubric_headers_revised` | L1 | yes |
| FR-G4.2 | `…::test_no_orphan_rubric_criteria` | L1 | yes |
| FR-G4.3 | `…::test_judge_flags_default_off_until_enable` | L1 | yes |
| FR-G5.1 | `tests/services/test_coach_goldset_dataset.py::test_synthetic_dev_firewall` | L1 | yes |
| FR-G5.2 | `…::test_missing_answer_leakage_rejected` | L1 | yes |
| FR-G5.3 | `…::test_unknown_failure_mode_rejected` | L1 | yes |
| FR-G5.4 | `…::test_assembly_invariants_and_test_hash` | L1 | yes |
| FR-G5.5 | `…::test_manifest_refuses_without_human_alpha` | L1 | yes |
| FR-G5.6 | `…::test_manifest_join_restores_full_text` | L1 | yes |
| FR-G5.7 | `…::test_pedagogy_axes_include_mistake_location_pass` | L1 | yes |
| FR-G6.1 | `tests/services/test_coach_calibration.py::test_provisional_manifest_refuse` | L1 | yes |
| FR-G6.2 | `…::test_binding_floor_pass_and_fail` | L1 | yes |
| FR-G6.2 | `…::test_undecidable_metric_refuse` | L1 | yes |
| FR-G6.3 | `…::test_augmenting_gates_precision_false_action_flip` | L1 | yes |
| FR-G6.4 | `…::test_enable_never_flips_flags` | L1 | yes |
| FR-G6.6 | `…::test_production_subset_precision_reported` | L1 | yes |
| FR-G6.7 | `…::test_low_kappa_axis_marked_unreliable` | L1 | yes |

**Red/green discipline:** every automated FR above must be written failure-first. Human
FR-G3 gates are satisfied by artifact presence + recorded IAA, not mocked coding.

---

## 9. Out of scope (deferred)

- Phase 5 flag flips and §12.7 drift monitoring — separate plan after `ENABLE`.
- Production Cloud Logging harvest as the primary corpus path — supplement only.
- FR-7 guardrail false-reject fix — backlog; fresh utterances only if pursued.
- `/learn/test` assembled-form UI — ADR-0013 product step.
- Fine-tuning judges — only if prompt+rubric path plateaus (design §12.6 creation path note).

---

## 10. Definition of Done

- [ ] FR-G1–G2 posture + export implemented; **3.2b** pasted showing ≥100 coding-eligible/mode (or documented shortfall).
- [ ] FR-G3 human artifacts committed; IAA ≥ 0.80 recorded.
- [ ] FR-G4 revised rubrics merged; headers marked REVISED.
- [ ] FR-G5 `coach_goldset_v1` frozen manifest + test-split hash; human α ≥ 0.80 on `answer_leakage`.
- [ ] FR-G6 cert report pasted (ENABLE or REFUSE with gate table) from on-demand replay.
- [ ] `make check` green; no invariant violations.
- [ ] Parent plan ledger Phase 3 row updated; small choices → `decisions.md` if any.
