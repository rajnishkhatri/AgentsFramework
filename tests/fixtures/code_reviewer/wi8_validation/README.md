# WI-8 — CodeReviewer judge validation fixture

Labeled fixture for validating the v3 code-reviewer **LLM judge** (WI-8 of
`docs/plan/unified_context_routed_reviewer.plan.md`).

## What this measures

The v3 LLM judge's **detection accuracy**, isolated from the (already-trusted)
deterministic half. 20 cases — 10 clean, 10 violating — each targeting an
**LLM-only** rule ID (a rule with no AST detector). The gate is TPR/TNR ≥ 0.90
via `meta.judge_validation.validate_judge`.

**`goal_met` convention (detection, not verdict policy).** A case is "met"
(judge says clean) iff the LLM emits **no critical/warning finding**. This
isolates judge *detection* (WI-8) from verdict-*policy* calibration (WI-9):
the v3 policy `>2 warnings → REQUEST_CHANGES` means a single warning yields
`APPROVE`, so using the verdict as the gate signal would falsely score a
detected-and-warned violation as "met". Notes/info do not count as failure
detection.

## Files

- `cases.json` — manifest (id, folder, gold_goal_met, rule_id, files).
- `cases/<id>/<repo-relative path>` — each case's file content.
- `verdicts.json` — recorded LLM verdicts (absent until the recording script
  is run with an API key; CI skips when absent, mirroring the L3 fixture).

## Recording procedure (one-off, requires an API key)

CI must NOT make live LLM calls. A human runs the recording script once to
populate `verdicts.json`; the CI test then replays the recorded verdicts
through `validate_judge` and asserts the gate passes.

1. Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / `LITELLM_API_KEY`).
2. From the repo root:

   ```bash
   python scripts/record_code_reviewer_validation.py
   ```

   This materializes each case into a temp tree (with the folder's `REVIEW.md`
   so routing resolves), runs `CodeReviewerAgent.review_v3_llm_only` over it,
   and writes `verdicts.json` (per-case LLM verdict, raw response, finding
   count, and the detection boolean).

3. Inspect `verdicts.json`. If TPR/TNR < 0.90, the judge is **not** validated —
   the honest limit ("LLM verdicts are not gate-grade") stays until the v3
   prompt is improved and the recording re-run. Do not commit a failing
   `verdicts.json` to flip the gate; iterate the prompt first.

4. Commit `verdicts.json`.

## Validate (offline, no API key)

```bash
python -m meta.code_reviewer_validation
```

Reads `verdicts.json` + `cases.json`, runs `validate_judge`, prints TPR/TNR +
Rogan-Gladen, exits non-zero if the gate fails.
