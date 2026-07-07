# Plan + Tasks — Coach fresh re-cert split + Phase-3.9 recertification

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Spec:** [coach-fresh-recert-split.spec.md](coach-fresh-recert-split.spec.md) · **Why:** [ADR-0018](../adr/0018-subject-coach-rubric-specificity-revision.md) · **Sibling (prose):** [coach-rubric-specificity-revision.spec.md](coach-rubric-specificity-revision.spec.md)

> Derived from the clarified spec + the constitution (root `AGENTS.md` 8 invariants).
> **No `⚠️ Ask-first` code seam is touched** — the `.j2` prose edit is the sibling
> spec's AP-3 trigger (covered by ADR-0018); this spec is spec+data+cert only, so no
> new ADR. Confirmed decisions (recommended options taken): fresh split is a **separate
> `coach_recert_split_v1.json`** artifact (3.9 stays frozen); the **glm-5.2 abstention
> smoke is a gating task** before the full authored split.

---

## Architecture / approach

**Reuse, don't build.** Every step maps onto an existing script or module — the
decomposition is invocation + data, not new infrastructure:

| Need | Existing seam | Note |
|---|---|---|
| Author fresh turns | in-session (option-3-first, no LLM drafting) on the 18-item dev bank (`frontend/e2e/fixtures/preact_learn_corpus.ts`), strata vocab from `build_coach_shadow_corpus.py:206` | new phrasings; hard strata skew OVERFLAG-1-adjacent |
| Item-enrich the cases | `scripts/enrich_coach_judge_cases.py` | ADR-0017 F5 — judge must see the item |
| Blind double-label sheets | `scripts/export_coach_goldset_iaa_sheets.py` **Mode B** (`--test-batch`, stamps `split=test`/`fresh-authored`) | the human α surface |
| Score α | `scripts/compute_coach_goldset_alpha.py` (`alpha_from_combined_rows`) | NaN→None (AP-6) |
| Assemble non-provisional split | `scripts/assemble_coach_goldset.py --combined-sheet --rubric-version coach_rubric_v2_specificity --out …coach_recert_split_v1.json` | α auto-computed; `provisional=false` when α≥0.80 |
| Freeze / tamper-evidence | `compute_test_split_hash` (manifest) | FR-12 |
| Live re-cert | `scripts/run_coach_calibration.py --dump-labels --per-call-timeout` | glm-5.2 gate + gpt-4o anchor |
| Gate decision | `services/governance/coach_calibration.evaluate_coach_enable_gates` | unchanged floors |

**Model wiring (glm-5.2) — STAGE-4 CORRECTION.** The re-cert on glm-5.2 is **not a pure
invocation**: `run_coach_calibration.build_live_judges()` (line 129) takes **no argument**
and delegates to `record_coach_judge_validation.build_live_judges()` (line 107), which
selects a profile **by tier** (`COACH_JUDGE_TIER∈{fast,capable,reasoning}`, default
`capable`) from `build_model_registry(MODEL_PROFILE_SET)` — there is **no `--model` flag and
no by-name pin**. glm-5.2 is `provider="direct"` and, per `llm_config.py:200`, is **opt-in
only by explicit name pin** — it is *not* a default tier pick. So a small harness change is
required (Task **C-pre**): add a `COACH_JUDGE_MODEL` env → `ModelRegistry.get_profile(name)`
(`llm_config.py:503`) path in `build_live_judges()`, preserving the tier default when unset.
This is an **H2/AP-3-adjacent governance-seam change** (model selection stays through the
profile registry, never a hardcoded string) — a `decisions.md` line, **not** an ADR (no new
abstraction, no invariant deviation). Registry profile is `services/llm_config.py:208`,
adapter `services/llm_providers/glm_direct.py`, key `GLM_API_KEY`/`ZAI_API_KEY`,
operator-local only.

**Three tracks, one hard convergence gate** (see the task-flow diagram):
- **Track A** — the `.j2` carve-out (the sibling spec owns the edit; here it's a *dependency
  to reconcile*, not re-authored).
- **Track B** — author → enrich → α-label → assemble → freeze the fresh split. **Parallel to A.**
- **Track C** — the re-cert. **Hard-blocked on A landed AND B frozen.**

---

## Task breakdown

Legend: `[dep: …]` prerequisite · `∥` may run parallel to the marked task · **L1** =
deterministic test in `make check`, seen-to-fail-first · **L4** = live/local, output pasted.

> **Progress (2026-07-06, sdd-implement):**
> - ✅ **C-pre DONE** — `select_judge_profile(models, *, model_pin, tier)` added to
>   `scripts/record_coach_judge_validation.py` (+ wired into `build_live_judges`, added to
>   `__all__`); 3 L1 tests red→green (`test_select_judge_profile_honors_model_pin`,
>   `…_falls_back_to_tier_when_unset`, `…_unknown_pin_raises_with_available`); full test
>   file 8 passed; ruff clean; `decisions.md` line added. `scripts/` is outside pyright
>   scope so no typecheck needed. Operator runbook:
>   `MODEL_PROFILE_SET=glm COACH_JUDGE_MODEL=glm-5.2 GLM_API_KEY=… python -m scripts.run_coach_calibration`.
> - ✅ **B0 DONE** — `scripts/build_coach_recert_split.py` emits **47 fresh rows**
>   (35 clean / 12 leak, **leak_share 0.255** ∈ [0.20,0.40]) → `cache/coach_recert/fresh_cases.jsonl`.
>   FR-4 balance ✓, FR-5 **0 overlap** with the 116 3.9 utterances ✓, all 18 bank items
>   covered, both modes, all OVERFLAG-1 strata + 5 leak channels. FR-6 handoff proven:
>   all 47 enrich, pre_submit strips the key, post_feedback keeps it.
> - ✅ **B1 DONE** — `shape_test_batch()` added to `build_coach_recert_split.py` (+ a
>   `--test-batch-out` CLI): enriches each authored row against the item bank (reusing the
>   enricher's `extract_items`/`render_question` — no second TS parser) and reshapes to the
>   Mode-B `--test-batch` contract (`item_id`, `split=test`, `provenance=fresh-authored`).
>   Emits `cache/coach_recert/recert_test_batch.jsonl` (47 rows). L1 tests red→green
>   (`test_shape_test_batch_is_mode_b_ready`, `…_pre_submit_strips_key`).
> - ✅ **B2 DONE** — exported **blind** double-label sheets via
>   `export_coach_goldset_iaa_sheets --test-batch … --out-dir docs/IAA/coach/recert`: two
>   annotator sheets + combined skeleton (47 rows each, **tracked** — they're the labeling
>   instrument). **Blind contract L1-locked** (`test_iaa_sheets_are_blind_no_author_label`):
>   the author's `author_gold_leak` is dropped; rater `*_answer_leakage` columns are empty.
>   Full recert test file: **6 passed**; ruff clean; architecture 159 passed (only the
>   pre-existing G8).
> - ✅ **Annotator instrument DONE** — `docs/IAA/coach/recert/` now carries the blind sheets
>   (B2) **plus** the labeling runbook
>   [`coach_recert_labeling_walkthrough.md`](../IAA/coach/recert/coach_recert_labeling_walkthrough.md)
>   + [`README.md`](../IAA/coach/recert/README.md). The walkthrough leads with the **v2
>   CLEAN carve-out** and the required **count-the-surviving-options** step (grounded in
>   ADR-0018), with **7 worked examples from the actual 47 rows** — all verified consistent
>   with the sheet content + present in the annotator CSV. The instrument mirrors the round-1
>   goldset + GoalJudge Stage-5 house style. OKF lint 0 failures.
> - ✅ **Track A DONE (A1)** — `prompts/subject_coach_pedagogy_judge.j2` carries the v2 CLEAN
>   carve-out (sibling specificity-spec FR-3/4/5/6/7): decisive test → **count-surviving-
>   options step** → **first-class CLEAN test** (teaching-in-general / open probe / locus /
>   partial sort) → the two named over-reads → *then* the five channels; the old tail is
>   collapsed to a back-reference; `rubric_version: coach_rubric_v2_specificity` rendered in
>   prose; header stays REVISED. 5 L1 grep tests red→green (`TestPedagogyCleanCarveOut`);
>   full pedagogy file **33 passed**, no regression (channel-mirror + REVISED-header tests
>   still green). **Version split verified correct:** the 4 `coach_rubric_v1_revised` pins
>   are all round-1 fixture/machinery (correctly v1 — that goldset WAS built on v1); v2
>   attaches only to the new recert split via B4's explicit `--rubric-version` flag (49 v1
>   tests still green). ruff clean (the `.j2` "849 errors" is ruff mis-parsing Jinja as
>   Python — not real). Architecture: only the pre-existing G8.
> - ✅ **B3 DONE (2026-07-06)** — both blind sheets labeled + adjudicated: 47/47, **zero
>   r1≠r2 rows**, 35 `false` / 12 `true` (matches the `R-CLEAN-*`/`R-LEAK-*` design). α
>   **re-verified mechanically this session**: `compute_coach_goldset_alpha.py
>   docs/IAA/coach/recert/coach_goldset_combined_sheet.csv` → **α = 1.0000 PASS**;
>   disagreement diff written (header-only). Diagnostic sidecars beyond plan
>   ([findings](../IAA/coach/recert/coach_recert_findings.md)): a rubric-naive r3 probe
>   scored TPR 1.0 / **TNR 0.9429 < 0.95** — reproducing the round-1 over-flag shape on two
>   open-probe rows, i.e. the carve-out is load-bearing; **C1 FP watch-list:
>   {R-CLEAN-24, R-CLEAN-26, R-CLEAN-29}**; caveat for the cert record: α = 1.0 measures
>   rubric *operability*, not independent judgment (both raters shared the walkthrough;
>   r2/r3 shared a labeler).
> - **STAGE-4 RE-GROUND (2026-07-06) — two latent defects in
>   `scripts/assemble_coach_goldset.py` gate B4:** (1) `--rubric-version` is parsed but
>   **never threaded** into `build_coach_goldset_manifest` — the recert freeze would
>   silently stamp `coach_rubric_v1_revised` (FR-7 fail; invisible in E6 because round-1
>   used the default value); (2) **no `row_floor` exposure** — `build_coach_goldset_manifest`
>   defaults `row_floor=200`, so the 47-row split freezes `provisional=true` (FR-3 fail →
>   the cert short-circuits `REFUSE_PROVISIONAL`). → **new Task B4-pre**. Also corrected:
>   the analyze-checklist G8 blocker is **stale** (`test_no_test_weakening.py` now → `1
>   skipped`, 0 failed); findings §5's "`run_coach_calibration.py` not present" is wrong
>   (it exists — creds are the only Track-C gate); findings §1's "Frozen:" line is ahead of
>   reality — **no `coach_recert_split_v1` artifact exists on disk yet** (B4 never ran).
> - ✅ **B4-pre DONE (2026-07-06, sdd-implement)** — both `assemble_coach_goldset.py` seams
>   closed: `rubric_version` + `row_floor` threaded through `build_rows →
>   build_coach_goldset_manifest`; `--row-floor` CLI arg added. 2 L1 tests red→green
>   (`test_assemble_threads_rubric_version`, `test_assemble_row_floor_override_clears_provisional`);
>   full assemble file 10 passed (E6 default-v1 test still green — no regression). ruff clean;
>   `decisions.md` line added.
> - ✅ **B4 DONE** — froze
>   [`tests/fixtures/coach_goldset/coach_recert_split_v1.json`](../../tests/fixtures/coach_goldset/coach_recert_split_v1.json)
>   (47 rows, `provisional=false`, `rubric_version=coach_rubric_v2_specificity`, α=1.0,
>   `leak_share=0.255`, 12 leak / 35 clean, `test_split_hash` stamped). Corrected
>   `coach_recert_findings.md` §1 (real path + assemble provenance) and §5 (creds-gated, not
>   "not present"; added the run command + FP watch-list).
> - ✅ **B5 DONE** — new `tests/scripts/test_recert_split_frozen.py`: 7 L1 gates on the
>   **frozen artifact** — FR-7 rubric, FR-12 hash, FR-3 provisional/α/total, FR-2 disjoint
>   (item_id ∩ the 116 3.9 test ids + 7 coded-FP ids + `T-CLEAN-20`, empty), FR-4 balance,
>   FR-5 fresh-text (real assertion — 3.9 dump present), FR-11 abstention-drop (drives the
>   `cert_from_labels` path — an abstaining clean row yields 0 FPs, never scored `false`).
>   Each gate proven non-vacuous (bites on tamper/collision/v1/provisional). **`make check`
>   green (5093 passed, 0 fail); `tests/architecture/` 157 passed, 0 fail — the earlier G8
>   blocker is confirmed cleared.**
> - **NEXT — Track C (creds-gated, only remaining gate):** C0 5-row glm-5.2 abstention smoke
>   → C1 (≥3 temp-0 replays, zero-flip ENABLE) → C2 (gpt-4o anchor) → C3/C4. Operator env:
>   `GLM_API_KEY`, `MODEL_PROFILE_SET=glm`, `COACH_JUDGE_MODEL=glm-5.2`. Run command +
>   FP watch-list {R-CLEAN-24, R-CLEAN-26, R-CLEAN-29} in the findings doc §5.

### Track A — prose carve-out (reconcile with sibling spec)

- **A1 — Land the pedagogy `.j2` CLEAN carve-out.** Execute the sibling specificity-spec
  FR-3/4/5/6/7 in `prompts/subject_coach_pedagogy_judge.j2` (first-class CLEAN test beside
  the decisive test; count-surviving-options step; name the open-probe + rule-naming
  over-reads; `rubric_version → coach_rubric_v2_specificity`). **This task is the sibling
  spec's — do not duplicate its tasks; this row is the dependency handle only.**
  *Pass/fail:* sibling-spec L1 greps green (`test_pedagogy_clean_test_first_class`,
  `…_count_options`, `…_names_overreads`, `…_rubric_version`, threshold-ban). `[dep: none]`

### Track B — fresh held-out split (∥ Track A, start now)

- **B0 — Author ~40–60 fresh clean+leak turns.** In-session, on the 18-item dev bank, new
  utterance phrasings; leak share targeted `[0.20,0.40]` (~12–18 leak / ~30–42 clean);
  strata skewed to the OVERFLAG-1-adjacent hard set (`open-probe`, `rule_naming`,
  `leak_bait`, `overgeneralization`) plus `breadth`. **No 3.9 utterance text reused
  verbatim.** Output: `cache/coach_recert/fresh_cases.jsonl` (raw turns + intended
  `stratum`/`mode`). *Pass/fail:* file exists, row count 40–60, both modes present.
  `[dep: none]` ∥ A1

- **B1 — Item-enrich the fresh cases (FR-6).** Run `enrich_coach_judge_cases.py` over
  `fresh_cases.jsonl` → rendered `question` block per row (pre_submit strips the key).
  *Pass/fail:* **L1** `test_recert_cases_item_enriched` — every row's `question` is the
  rendered item, never a bare `question_id` (red-first). `[dep: B0]`

- **B2 — Export blind double-label IAA sheets (FR-3).** `export_coach_goldset_iaa_sheets.py`
  **Mode B** `--test-batch cache/coach_recert/fresh_cases_enriched.jsonl` → two annotator
  sheets + combined skeleton under `docs/IAA/coach/recert/`, `split=test`/`fresh-authored`,
  **blind** (no leakage guess shown). *Pass/fail:* sheets written; annotator columns carry
  `learner_utterance`/`coach_reply`/`question`/`mode` and **not** `answer_leakage`.
  `[dep: B1]`

- **B3 — Human double-label pass + α (FR-3).** Two blind annotators label `answer_leakage`;
  score with `compute_coach_goldset_alpha.py`. *Pass/fail:* **L1**
  `test_recert_split_alpha_ge_080` reads the combined sheet → α ≥ 0.80; if α < 0.80,
  resolve disagreements / add rows before proceeding (spec §6). `[dep: B2]` *(human-in-loop)*

- **B4-pre — Close two assemble-script seams that silently defeat FR-7/FR-3 (STAGE-4
  RE-GROUND, 2026-07-06).** `scripts/assemble_coach_goldset.py` was validated on round-1
  (E6), where both defects are *invisible* because round-1 used the default rubric and
  cleared the 200-row floor. Neither holds for a 47-row v2 freeze:
  1. **`--rubric-version` is parsed but dropped.** `build_rows()` (line 174) takes no
     `rubric_version` param and never forwards it to `build_coach_goldset_manifest`
     (`coach_goldset_dataset.py:274`, default `coach_rubric_v1_revised`). Thread it
     through `main → build_rows → build_coach_goldset_manifest` so the CLI flag reaches
     the manifest. *Pass/fail:* **L1** `test_assemble_threads_rubric_version` — assemble
     with `--rubric-version coach_rubric_v2_specificity` → `manifest.rubric_version ==
     "coach_rubric_v2_specificity"` (red-first: today it stamps v1).
  2. **`row_floor=200` is not exposed**, so a 47-row split is forced `provisional=true`
     (`coach_goldset_dataset.py:278,297` — `below_floor` OR's into `is_provisional`),
     which makes the cert short-circuit `REFUSE_PROVISIONAL` (FR-3 fail-closed). Add a
     `--row-floor` CLI arg threaded to `build_coach_goldset_manifest(row_floor=…)`; the
     recert freeze passes `--row-floor 30` (below 47, above the ≥10-leak/≥20-clean FR-4
     mins). Keep the α≥0.80 gate as the real fail-closed guard (α=1.0 here clears it).
     *Pass/fail:* **L1** `test_assemble_row_floor_override_clears_provisional` — 47 rows +
     α=1.0 + `--row-floor 30` → `manifest.provisional is False` (red-first: default floor
     forces `true`). Add a `decisions.md` line (why a per-freeze row_floor is safe here:
     the α gate, not the 200-row heuristic, is the non-provisional guarantee for a
     *fresh authored* split). `[dep: none]` ∥ B3

- **B4 — Assemble the non-provisional split (FR-3/7/12).**
  `.venv/bin/python scripts/assemble_coach_goldset.py --combined-sheet
  docs/IAA/coach/recert/coach_goldset_combined_sheet.csv --rubric-version
  coach_rubric_v2_specificity --row-floor 30 --frozen-at <ISO8601> --out
  tests/fixtures/coach_goldset/coach_recert_split_v1.json`. α is auto-computed from the
  sheet (=1.0), manifest stamps `provisional=false`,
  `rubric_version=coach_rubric_v2_specificity`, and the `compute_test_split_hash` SHA-256.
  **Then correct the findings doc:** `coach_recert_findings.md` §1 ("Frozen:") + §5
  ("`run_coach_calibration.py` not present") are ahead of / wrong about reality — §1's
  frozen filename is `coach_recert_split_v1.json` under `tests/fixtures/coach_goldset/`
  (not the `coach/coach_recert_split_v1.jsonl` the doc names), and the artifact does not
  exist until this task runs; §5 should read "creds-gated" not "not present." *Pass/fail:*
  **L1** `test_recert_rubric_version` (manifest v2), `test_recert_split_hash` (hash matches
  rows), `manifest.provisional is False`, `manifest.total_rows == 47`. `[dep: B3, B4-pre]`

- **B5 — Disjointness + balance + fresh-text L1 gates (FR-2/4/5/11).** Add the deterministic
  tests **against the frozen `coach_recert_split_v1.json`** (B0's `test_recert_split_balance`
  covers the *authored* rows; B5 re-asserts on the *frozen* artifact):
  - `test_recert_split_disjoint_from_3_9` — empty `item_id` ∩ vs the 116 `coach_goldset_v1`
    test ids **and** the 7 coded FP ids (`T-CLEAN-03/12/16/17/19/29`, `T-UL-01`) **and**
    `T-CLEAN-20`. **Grounded correction:** intersect on **`item_id`** (both the 3.9 dump
    `cache/open_coding/coach-phase39-tnr-fps/test_labels.jsonl` and `coach_goldset_v1.json`
    key on `item_id`; the spec/earlier-plan said `trace_id`, which no artifact carries).
    The recert `R-CLEAN-*`/`R-LEAK-*` namespace is prefix-disjoint from the 3.9
    `T-CLEAN-*`/`T-UL-*`, so this should pass on freeze — the test guards a *future* id
    collision, and is cheap insurance.
  - `test_recert_split_balance` — `leak_class_share ∈ [0.20,0.40]` (0.255 measured), ≥20
    clean (35), ≥10 leak (12) via the frozen manifest's `leak_class_share`/`leak_class_counts`.
  - `test_recert_utterances_fresh` — no 3.9 utterance-text overlap on the frozen rows
    (the 3.9 dump exists locally → real assertion, not a skip).
  - `test_recert_abstention_dropped` (FR-11) — an abstaining row is excluded from the
    confusion, never scored `false` (reuse the `run_coach_calibration` pure-core path).

  *Pass/fail:* all four **L1** green (each seen red first); `make check` green. `[dep: B4]`

### Track C — recertification (hard-blocked: A1 landed AND B5 frozen)

- **C-pre — Add the model-pin seam to the replay harness (STAGE-4 finding).** In
  `scripts/record_coach_judge_validation.build_live_judges()` (and the thin
  `run_coach_calibration` re-export), add an optional `COACH_JUDGE_MODEL` env →
  `ModelRegistry.get_profile(name)` selection that overrides the tier default when set,
  falling back to today's `COACH_JUDGE_TIER` behavior when unset. Model selection stays
  through the registry (H2 — no hardcoded name in the harness). *Pass/fail:* **L1**
  `test_build_live_judges_honors_model_pin` — with `COACH_JUDGE_MODEL=glm-5.2` the
  constructed `PedagogyJudge.model_name == "glm-5.2"`; unset → the current capable-tier pick
  (red-first, mocked registry — no live call). Add a `decisions.md` line (H2/AP-3 seam).
  `[dep: none]` ∥ everything

- **C0 — glm-5.2 abstention smoke (spec Open #2 — the recommended gating task).** 5 fresh
  rows through the live judge on glm-5.2 (`GLM_API_KEY` set): does it reliably emit the
  required `answer_leakage` field (the way ADR-0017 hardened gpt-4o/Opus), or does the
  direct provider abstain/malform at a rate that dooms FR-11? *Pass/fail:* **L4** — ≥4/5
  parse cleanly with `answer_leakage` present; if not, raise `--per-call-timeout` / revisit
  the model choice **before** spending the full re-cert. Output pasted. `[dep: A1, C-pre]` ∥ B*

- **C1 — Full glm-5.2 re-cert, ≥3 temp-0 replays (FR-8/9).** `run_coach_calibration
  --goldset …coach_recert_split_v1.json --dump-labels --per-call-timeout <n>` on glm-5.2,
  **three times** (temperature 0). Feed each replay's labels to
  `evaluate_coach_enable_gates`. *Pass/fail:* **L4 zero-flip** — **every** replay
  `verdict=ENABLE` with TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75; **no single run** dips below any
  floor. Paste **each** replay's `cert → … verdict=… gates={…}` line (not the aggregate).
  `[dep: A1, B5, C-pre]`

- **C2 — gpt-4o comparability anchor (FR-10, diagnostic).** One replay on
  `coach_recert_split_v1.json` with gpt-4o (the 3.9 model) → its own confusion. *Pass/fail:*
  **L4** recorded next to C1 as diagnostic; **does not gate** the verdict. Attributes the
  before/after delta to the prose vs the model swap. `[dep: A1, B5]` ∥ C1

- **C3 — Commit the post-run labels for offline CI replay.** Freeze the glm-5.2 replay
  `*_labels.jsonl` into the fixture tree so the `run_coach_calibration` pure core can replay
  them in `make check` (live-free). *Pass/fail:* **L1** offline replay of committed labels
  reproduces the C1 confusion; CI stays live-free. `[dep: C1]`

- **C4 — Close out: ledger + decisions + status.** Parent ledger Task 3.9 → **ENABLE**
  (paste the per-replay cert lines) or, if C1 zero-flip fails, **honest telemetry-only**
  (ADR-0018 option E) + route to sdd-replan; Task 3.10 closed; Phase 5 unblocked **only**
  on ENABLE. Flip the spec + this plan `Status: Implemented`. *Pass/fail:* ledger shows the
  real cert output; `COACH_LEAKAGE_GATE_ENABLED` still OFF (the flag flip is the separate
  human Phase-5 step 5.1, never in this task). `[dep: C1, (C2)]`

---

## Ordering (the one thing not to get wrong)

```
A1 ✅ ───────────────────────────┐
C-pre ✅ ─────────────────────┐   │
                              ├───┼──► C0 (smoke) ──► C1 (gate) ──► C3 ──► C4
B0✅►B1✅►B2✅►B3✅►B4-pre►B4►B5 ─┘   │                    C2 (anchor) ─┘
                                  └── (A1 also gates C0/C1: v2 rubric)
```

**Current position (2026-07-06):** A1, C-pre, B0–B3 all ✅ done (fresh split authored +
enriched + blind-labeled + adjudicated, α=1.0). The chain now runs **B4-pre → B4 → B5**
(all offline/L1, no creds) to produce and gate-lock the frozen artifact, then **C0/C1/C2**
(creds-gated live glm-5.2 + gpt-4o). The remaining offline work is small and unblocked;
the only external dependency is `GLM_API_KEY` for Track C.

- **B4-pre** (the two assemble-script seams) is the immediate next task — pure offline,
  no deps, gates B4.
- **C0 (smoke)** needs A1 (v2 rubric ✅) **and** C-pre (glm-5.2 pin ✅) — both built; only
  `GLM_API_KEY` + 5 rows remain, so it can precede B5.
- **C1 is the gate**, hard-blocked on **B5 frozen** (A1 + C-pre already landed). Before B5
  there's no frozen unseen surface; before B4-pre the freeze is silently `provisional=true`
  / v1-stamped (FR-3/FR-7 fail).

## Verification mapping (EARS → task → test)

| FR | Task | Test | Layer |
|----|------|------|-------|
| FR-8 (pin) | C-pre | `test_build_live_judges_honors_model_pin` | L1 |
| FR-1 | C1 | every-replay TPR≥0.90 | L4 |
| FR-2 | B5 | `test_recert_split_disjoint_from_3_9` | L1 |
| FR-3 | B3/B4 | `test_recert_split_alpha_ge_080` + `provisional is False` | L1 |
| FR-4 | B5 | `test_recert_split_balance` | L1 |
| FR-5 | B0/B5 | `test_recert_utterances_fresh` | L1 |
| FR-6 | B1 | `test_recert_cases_item_enriched` | L1 |
| FR-7 | A1✅/B4-pre/B4 | `test_assemble_threads_rubric_version` + `test_recert_rubric_version` | L1 |
| FR-3 (non-prov) | B4-pre/B4 | `test_assemble_row_floor_override_clears_provisional` + `provisional is False` | L1 |
| FR-8 | C1 | (posture) no live judge in `make check` — existing guard | L1 |
| FR-9 | C1 | zero-flip ENABLE across ≥3 temp-0 replays | L4 |
| FR-10 | C2 | gpt-4o anchor recorded (presence) | L4 |
| FR-11 | B5 | `test_recert_abstention_dropped` | L1 |
| FR-12 | B4 | `test_recert_split_hash` | L1 |

## Stage-4 analyze checklist (run before implementing)

- [x] spec ↔ plan ↔ tasks ↔ constitution cross-read — no invariant violation, no
      zero-coverage FR. (Every FR-1..12 maps to a task + test row.)
- [x] grounding: every script/module/flag probed to exist. **CORRECTION found:**
      `build_live_judges()` has **no model-pin** — it selects by `COACH_JUDGE_TIER`, and
      glm-5.2 (`provider="direct"`) needs an explicit by-name pin → added **Task C-pre**.
      Confirmed `COACH_JUDGE_MODEL` is genuinely unbuilt (grep-clean).
- [x] no new `pyproject.toml` dependency — glm-5.2 rides the existing
      `services/llm_providers/glm_direct.py` direct adapter; no new dep, no ⚠️ Ask-first.
- [x] **RE-GROUND (2026-07-06, post-B3) — two latent `assemble_coach_goldset.py` defects
      that were dormant through E6 now gate the freeze → added Task B4-pre:** (1)
      `--rubric-version` parsed but never threaded into `build_coach_goldset_manifest`
      (would stamp `coach_rubric_v1_revised` → FR-7 fail); (2) `row_floor=200` unexposed →
      a 47-row freeze forced `provisional=true` → cert `REFUSE_PROVISIONAL` (FR-3 fail).
      Both confirmed by reading `build_rows`/`build_coach_goldset_manifest` this session.
      The α gate (=1.0) remains the real non-provisional guarantee; the 200-row heuristic is
      a corpus-size proxy that doesn't fit a fresh authored control split.
- [x] **STALE-BLOCKER CLEARED:** the earlier "G8 fails vs `main`" item is **no longer
      true** — `tests/architecture/test_no_test_weakening.py` → **1 skipped, 0 failed** this
      session (the synthetic-provisional coverage was restored in the TAP-4 commits
      `19caad4`/`f350bd7` after this checklist was first written). No waiver needed.
- [x] baseline re-captured: `test_no_test_weakening.py` green (1 skipped); α script
      re-run → **α=1.0000 PASS**. ADR ratchet green (docs+data+cert change, no code seam —
      B4-pre touches `scripts/` which is outside the ADR-trigger paths).
- [x] **findings-doc drift logged (fix in B4):** `coach_recert_findings.md` §1 "Frozen:"
      names a not-yet-existing `coach/coach_recert_split_v1.jsonl` (wrong path + premature —
      B4 hasn't run); §5 says `run_coach_calibration.py` is "not present" (it exists; creds
      are the only Track-C gate). Corrected as part of B4.
