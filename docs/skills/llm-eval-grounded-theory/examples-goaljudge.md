# GoalJudge Worked Example

This repo implements the [llm-eval-grounded-theory](SKILL.md) pipeline for the binary `goal_met` judge that gates `success → partial` downgrade. Use this index when applying the generic handbook here.

---

## Stage map

| Generic stage | GoalJudge artifact |
|---------------|-------------------|
| Stage 0 — Traces | `eval_capture.record()` with `user_id` + `task_id`; Langfuse export |
| Stage 1–2 — Open/axial coding | [01_axial_coding_failure_taxonomy.md](../../recipes/goaljudge/01_axial_coding_failure_taxonomy.md) |
| Stage 3 — Synthetic | [goaljudge_synthetic_saturation_corpus.plan.md](../../plans/goaljudge_synthetic_saturation_corpus.plan.md) |
| Stage 4 — Rubric (A2 corrupt-success) | [02_stage4_a2_rubric.md](../../recipes/goaljudge/02_stage4_a2_rubric.md) |
| Stage 5 — Gold set | [goaljudge_stage5_goldset.plan.md](../../plans/goaljudge_stage5_goldset.plan.md) |
| Stage 6 — Calibration + §2.8 gates | [fix2_goaljudge_rubric_feasibility_pyramid.md](../../research/fix2_goaljudge_rubric_feasibility_pyramid.md) §2.8 |
| Stage 7 — Shadow/monitoring | [15_goaljudge_runtime_config_toggle.md](../../recipes/15_goaljudge_runtime_config_toggle.md) |

---

## Canonical documents

| Document | Purpose |
|----------|---------|
| [00_overview.md](../../recipes/goaljudge/00_overview.md) | Detective metaphor; three orthogonal axes; Step 0–8 pipeline |
| [goaljudge_evaluation_pipeline_open_axial_coding_rubric.md](../../research/goaljudge_evaluation_pipeline_open_axial_coding_rubric.md) | Full playbook Stages 1–6 + references R1–R20 |
| [fix2_goaljudge_rubric_feasibility_pyramid.md](../../research/fix2_goaljudge_rubric_feasibility_pyramid.md) | Enable-policy gates; Option B rollout |
| [goaljudge_stage4_a2_rubric.plan.md](../../plans/goaljudge_stage4_a2_rubric.plan.md) | Stage 4 implementation plan |
| [goaljudge_stage5_goldset.plan.md](../../plans/goaljudge_stage5_goldset.plan.md) | Stage 5 schema, stratification, contamination firewall |
| [goaljudge_stage5_goldset_tier_review.md](../../reports/goaljudge_stage5_goldset_tier_review.md) | Current tier/blocker status |

---

## Code seams

| Component | Path | Role |
|-----------|------|------|
| Judge component | `components/goal_judge.py` | Trajectory-aware evaluation |
| Verdict schema | `components/schemas.py` (`GoalVerdict`) | Analytic rubric output contract |
| Judge prompt | `prompts/goal_judge_system_prompt.j2` | Rubric encoded as prompt (H1) |
| Gold set service | `services/governance/goaljudge_goldset_dataset.py` | Langfuse dataset CRUD; contamination firewall |
| Eval capture | `services/eval_capture.py` | Trace substrate for all LLM calls |
| Runtime toggle | GCS-backed config via Recipe 15 | Shadow / downgrade / dark posture |

---

## GoalJudge-specific gates

From §2.8 enable-policy ([fix2 pyramid](../../research/fix2_goaljudge_rubric_feasibility_pyramid.md)):

| Gate | Threshold |
|------|-----------|
| Precision on `goal_met=False` | ≥ 0.90 |
| False-downgrade rate (clean successes) | ≤ 2% |
| Recall on `goal_met=False` | ≥ 0.70 |
| CoT-gaming red-team flip | ≤ 5% (soft 10%) |
| κ vs human labels | ≥ 0.6 |
| Flag posture | `goal_judge_downgrade_enabled=False` until all met |

**Code vs Confirmation gate (Stage 4):** Provisional A2 rubric may ship in shadow; gold-set labeling and downgrade enable require Confirmation (confirmed rubric + IAA).

---

## IAA artifacts (this session)

| Report | Path |
|--------|------|
| Stage 4 A2 IAA pass 1 | [goaljudge_stage4_a2_iaa_pass1_results.md](../../IAA/goalJudge/goaljudge_stage4_a2_iaa_pass1_results.md) |
| Stage 4 A2 IAA results | [goaljudge_stage4_a2_iaa_results.md](../../IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md) |

---

## Three-axis quick reference

From [Recipe 0](../../recipes/goaljudge/00_overview.md):

| Axis | Question | Example |
|------|----------|---------|
| A — agent behavior | Did the agent deviate? | `partial-counted-as-full` |
| B — confound | Could a perfect agent have failed? | Shell allowlist blocked required tool |
| C — judge reliability | Is the verdict wrong? | `goal_met=true` contradicted by evidence |

Top mode picked for Stage 4: **A2 · corrupt-success** (agent narrates success; evidence contradicts).

---

## Walkthroughs

- Axial coding manual walkthrough: [05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md](../../walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md)
- UI/Langfuse validation (Stage 0 companion): `docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md` (when present)

---

## TDD placement (AGENTS.md)

- L3 offline CoT-gaming red-team pin: [fix2_goaljudge_remediation_f1_f4.plan.md](../../plans/fix2_goaljudge_remediation_f1_f4.plan.md) §5.1
- L4 gate failure-mode matrix: orchestration downgrade wrapper reads **only** `goal_met`
