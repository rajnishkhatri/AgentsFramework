# agentsframework-eval-probe — Worked Examples

Two seams in this repo already walked the probe path. They are the proof the recipe is real and
repeatable here — one for each end of the tiered ramp. Read the one closest to your seam.

- **Guardrails** = the **Tier-A exemplar.** A cheap deterministic check, live on 100% of traffic,
  shipped without ever building a gating judge. Most seams should look like this.
- **GoalJudge** = the **full judge-track exemplar.** Open coding all the way to a calibrated judge
  behind a fail-closed enable-gate and a runtime flag. The expensive path, earned.

---

## Example A — Guardrails (Tier-A, ships fast)

**Seam:** input/output guardrail. **Altitude:** span (one validation call). **Outcome:** a live L1
deterministic probe, no judge, no gold set.

### How it maps to the phases

| Phase | What happened |
|---|---|
| 0 prioritize | Injection / PII leakage was a known high-harm first-failure — worth a 100% probe. |
| 1 seam + altitude | Span: each input is validated in isolation. Recording via the standard capture path. |
| 2 open coding | Read real adversarial + benign inputs; first-failures = injection, PII leak, key leak, over-length. |
| 3 taxonomy | Binary, evidence-grounded categories: PII present / API-key present / over-length / injection pattern. |
| 4 **Tier-A probe** | `guardrail_validator.py` — pure regex/entropy checks → `ValidationResult` (severity + fail-action), on 100% of traffic. Frozen benchmark = `guardrail_dataset` (must-block adversarial / must-pass benign). |
| 5–7 | **Stopped at Tier-A.** A narrow LLM judge exists only on the DEFER/UNCERTAIN band, not as a gating judge — exactly the canon's "save the judge for persistent generalization failures." |

### The artifacts to copy

- **The L1 check shape:** `GuardRailValidator.validate(content) -> list[ValidationResult]`, with
  rule factories `pii_rules()`, `api_key_rules()`, `length_rule(max_length)`. Pure, L1, zero
  framework imports. This is the template for *any* deterministic Tier-A check.
- **The frozen benchmark:** `scripts/generate_guardrail_dataset.py` builds the must-block /
  must-pass corpus; the CI regression scores it deterministically.
- **A working interactive probe to read end-to-end:** `scripts/probe_guardrail.py` — runs the
  deterministic pre-check (no keys), optionally the smoke ONNX classifier, optionally the narrow
  live judge on uncertain bands. The cleanest single file to learn the Tier-A pattern from.

**The lesson:** the guardrail seam never needed Stages 5–7. It caught its failures with a 100%
deterministic check and a frozen benchmark. When your Tier-A data doesn't justify a gating judge,
**this is what done looks like** — don't manufacture a judge to feel thorough.

---

## Example B — GoalJudge (full judge track, on-demand)

**Seam:** goal/outcome judge (does the run satisfy the task's success conditions?). **Altitude:**
trace (the verdict depends on the whole run, not one call). **Outcome:** a calibrated LLM judge
behind a fail-closed §2.8 enable-gate and a runtime flag — currently held at shadow by design.

### How it maps to the phases

| Phase | What happened |
|---|---|
| 0–3 | Open coding → axial taxonomy of judge failure modes (fabricated-progress, fluent-evasion, corrupt-success, …); synthetic strata for scarce cases. |
| 4 Tier-A | Deterministic process floors + the pre-judge `synthesis_validator` gate (which flips success→failure *before* the judge). |
| 5 gold set + IAA | A double-labeled gold set; κ/α via `services/governance/iaa.py`; **dev/test split**, the 2b α baseline frozen byte-identical so the consume gate measures one variable. |
| 6 calibration + gate | `goaljudge_calibration.py` — L1-pure: `confusion_counts` → `precision_recall_fd` → `evaluate_section_2_8_gates` → a fail-closed `GateDecision`. Headline TPR/TNR; §2.8 thresholds (precision ≥ 0.90, recall ≥ 0.70, FD ≤ 0.02, flip ≤ 0.05, κ ≥ 0.6). |
| 7 loop + flip | Drift via `meta/drift.py`; the terminal action is a **runtime-config flip** (`goal_judge_downgrade_enabled`, `success_conditions_source`) via `GoalJudgeRuntimeConfigReader` — **not a code change**. The skill produces the decision; a human flips the flag. |

### The artifacts to copy

- **The enable-gate shape:** `evaluate_section_2_8_gates(...)` returning a `GateDecision`,
  fail-closed on undecidable or provisional inputs. The template for any per-seam gate.
- **The golden-number test:** the L1 suite pins TP=69 FP=8 FN=8 TN=12 ⇒ α=0.4987 so the math can't
  drift silently. Mirror this for any generalized evaluator.
- **The fail-closed floor gate:** `gate_goldset_v1_floors(manifest)` raises on `provisional=true`,
  blank `test_split_sha256`, or any floor gap — and the evaluator calls it *first*, returning
  `REFUSE_PROVISIONAL` before reading a metric. Today the gold set is v0.9 provisional (101 rows,
  hash `ad5eccc0…`), so the evaluator *cannot* emit ENABLE — by design. This is the model for "a
  seam that hasn't earned its judge stays shadow."

**The lesson:** GoalJudge earned the expensive track because its failures were persistent and
high-stakes (a wrong downgrade corrupts a real success). Even so, **acting waits behind a flag a
human flips** — the gate evaluates, it never acts. For GoalJudge-specific operation (the exact flip
path, current gold-set state, landmines), defer to the
[`agentsframework-eval`](../agentsframework-eval/SKILL.md) skill; this skill only uses GoalJudge as
the generalization anchor.

---

## What the two share (the pattern this skill generalizes)

1. **Failures were observed before any check was written** — open coding strictly preceded the
   rubric, in both.
2. **The cheap deterministic check shipped first**, on 100% of traffic, with a frozen benchmark.
3. **The expensive judge was earned, not assumed** — Guardrails never needed it; GoalJudge did, and
   only after a gold set + calibration justified it.
4. **The acting decision is fail-closed and human-gated** — a gate evaluates; a human flips the
   flag or merges the promotion.
5. **Everything writes to the same Recording substrate** (`eval_capture` → `eval_telemetry`, same
   `trace_id`), so the probe data and the trace audit see the same truth.
