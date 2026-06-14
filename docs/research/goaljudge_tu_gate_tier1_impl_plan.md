# TaskUnderstanding gate — Tier-1 implementation plan (post-R3 → 2b)

**Date:** 2026-06-13 · **Branch:** `feat/goaljudge-stage6-calibration`
**Predecessor:** R3 PASSED in prod — gate-pass 98/101 = 97.0% (≥96 bar),
coverage 95.1%, shadow invariant 101/101, both fixes (punct-strip + cross-turn
staleness) verified live (`goaljudge_stage2a_shadow_round3.md`,
`docs/reviews/governance_audit_04fa2506_2026-06-13.md`).
**Long-term context:** `docs/research/goaljudge_tu_gate_longterm_plan.md`.

This plan turns the R3 report's "next step" recommendation into a sequenced,
TDD-gated, compliance-checked implementation. It is **backend-only**, touches
**no wire schema / frontend / middleware**, and leaves the **frozen 2b α
baseline (`plan_builder` floor) untouched** throughout Tier 1 so the consume
gate measures one variable.

---

## 0. Goal and gating logic

The program's terminal objective is to flip `success_conditions_source` from
`shadow` to `generated` (the **2b consume gate**) so the GoalJudge scores each
run against task-specific conditions instead of the generic deterministic floor
that capped judge-vs-gold α at 0.50. R3 cleared the *shadow* bar; before the
*consume* flip, three defects that are harmless in shadow become live-quality
risks the moment the generated conditions are actually consumed:

1. **All-or-nothing grounding false positive** — a legitimate condition about
   the *answer's shape* (a recommendation, a verification, an action) shares no
   token with the *task's* vocabulary, so the whole artifact is discarded and
   the run falls back to the generic floor. In shadow this only dents gate-pass
   (3/101). **Consumed**, it silently denies short / action / recommendation
   tasks their task-specific conditions — exactly the rows where the floor is
   weakest. (`4b8c3f68` pakistan; R3 fallbacks 002/038/065.)
2. **GoalJudge self-contradictory verdicts** are unauditable — the judge marked
   a generic-tail condition UNMET citing "no evidence of reading all four files"
   on an answer whose own `evidence_digest` showed 8 reads (`0b54f4e1`), and
   said "did not read cherries.txt" with cherries in the digest (`3921c61b`).
   We cannot offline-diagnose these because the rejected/contradicted
   condition-vs-evidence pairing is not archived as artifact text — the **same
   blind-diagnosis trap** that made round 2's root cause wrong.
3. **`synthesis_validator` is an unbenchmarked deterministic gate with the
   identical `[a-zA-Z]{4,}` bug class** as the pre-R3 `_content_tokens`, and it
   sits **before the judge in the critical path** (react_loop.py:1429 flips a
   `success` outcome to `failure`). A true completion can be wrongly looped, and
   nothing measures its false-positive rate.

Tier 1 = retire #1 (unblock the flip cleanly), make #2 auditable (so Stage B can
be evidence-driven, not blind), and benchmark #3 (so we never ship another
unmeasured lexical gate). Then Tier 2 = the 2b α replay + flip.

**Sequencing rationale (cheapest unblock first, landmine before flip):**
`#1 → #3 → #2 → 2b`. #1 is the one-variable change the flip actually waits on;
#3 prevents a known pre-judge landmine from corrupting the α corpus; #2 is
audit-trail only (no behavior change) and can land any time but is cheapest to
verify alongside #3. The flip (2b) is last and gated on all three.

**Process rules in force** (long-term plan): (a) no diagnosis without artifact
text; (b) every deterministic gate ships a must-accept/must-reject L4
meta-benchmark BEFORE it gates production; (c) quote binomial power with any
verdict; (d) one variable per round.

---

## Item 1 — generic-condition grounding exemption

**File:** `components/task_understanding.py::validate_conditions`
**Risk class:** loosens an anti-hallucination gate → must be bounded + benchmarked.

### Design

The lexical grounding gate is a **topicality filter, not an anti-fabrication
gate** (long-term plan finding #4): a condition that reuses one task token is
"about this task"; a condition about the answer's *shape* legitimately reuses
none. R3 proved the residual fallbacks are all this class, never fabrications.

Mirror the two exemptions already accepted in the codebase:

- `source == "user_edited"` already **skips grounding entirely** (the human is
  the authority) — `validate_conditions` line 123.
- The Stage-B evidence-quote prototype budgets **≤1 null** evidence span.

**Exempt at most ONE condition from grounding** per artifact. Concretely: run
the grounding check on every condition, collect the ungrounded indexes, and only
emit a `grounding gate` issue if **two or more** conditions are ungrounded. One
ungrounded condition is tolerated (the answer-shape criterion); two-plus still
signals an off-topic checklist and is rejected.

This is strictly safer than `N−1`-of-`N` tolerance (which scales the budget with
list length): the budget is a **constant 1**, independent of count, so a
6-condition checklist can still only "spend" one ungrounded slot. It also
subsumes the `GENERIC_TAIL_CONDITION` — the appended tail is itself an
answer-shape condition and is the most common single offender.

### Exact change (illustrative — TDD drives the final form)

```python
    if source != "user_edited":
        task_tokens = _content_tokens(task_input)
        if task_tokens:
            ungrounded = [
                index
                for index, condition in enumerate(conditions)
                if not (_content_tokens(condition) & task_tokens)
            ]
            # Topicality filter, not anti-fabrication (longterm plan #4): one
            # condition may legitimately describe the answer's SHAPE (a
            # recommendation / verification / action) and reuse no task token —
            # mirrors the user_edited grounding skip and the Stage-B ≤1 null
            # budget. Two+ ungrounded still signals an off-topic checklist.
            if len(ungrounded) > _MAX_UNGROUNDED:
                for index in ungrounded:
                    issues.append(
                        f"grounding gate: condition {index} shares no content "
                        "token with the task input"
                    )
```

with `_MAX_UNGROUNDED = 1` as a named module constant beside `_MIN_CONDITIONS`.
The issue strings are unchanged (the benchmark replay parses indexes from them).

### TDD (RED first)

Extend `tests/fixtures/task_understanding/gate_benchmark_v1.json` and the replay
in `tests/components/test_task_understanding_gate_benchmark.py`:

- **Add as `must_accept` (known-reject-now / must-accept-after):** the three R3
  fallbacks (002 "compare three approaches … recommend", 038 "wc -m … verify
  the count", 065 "customer refund … how should I proceed") and the `4b8c3f68`
  pakistan case ("what about pakistan?" with a "≤200 words" length condition).
  Tag each with the new flag `single_ungrounded: true` and the offending index,
  so the fixture documents that exactly one condition is ungrounded by design.
- **Guard the bound is still tight — add as `must_reject`:** a synthetic
  two-ungrounded artifact (e.g. pakistan with BOTH a "≤200 words" condition AND
  a fabricated "the answer cites three sources" condition — two answer-shape
  conditions, neither grounded). This proves the budget is a hard `1`, not "skip
  grounding when short".
- The existing adversarial matrix (the 30-pair off-topic probes, 1 known leak)
  must stay GREEN — a single off-topic probe condition is the tolerated slot, so
  re-confirm those probes pair a grounded condition with the off-topic one (they
  do: each probe is one off-topic sentence). If any adversarial row would now
  flip to "grounds" because its *only* condition is the probe, split it so the
  budget is exercised, not bypassed.

L4 component cases in `test_task_understanding.py`: one-ungrounded artifact
passes `validate_conditions` (no issues); two-ungrounded raises with both
indexes; `user_edited` still skips entirely; a fully-grounded list is unchanged.

### Blast radius

| Surface | Change |
| --- | --- |
| `components/task_understanding.py` | `_MAX_UNGROUNDED=1`; budget logic in `validate_conditions` |
| `tests/fixtures/.../gate_benchmark_v1.json` | +4 must-accept, +1 must-reject; bump `_meta` to v1.1 + source sha |
| `tests/components/test_task_understanding_gate_benchmark.py` | replay honors `single_ungrounded`; new must-reject |
| `tests/components/test_task_understanding.py` | +3–4 L4 budget cases |

**Not touched:** `plan_builder` floor (frozen 2b baseline — the floor never runs
`validate_conditions`; only the generated path does, so the α baseline is
untouched **by construction**), prompt `.j2` (one variable), wire schemas,
frontend, middleware, judge.

### Compliance

- AGENTS.md #3 (framework-agnostic): pure function, no new imports. ✅
- Process rule #2 (benchmark before gating): the fixture is extended **RED
  first**, the four cases proven reject-now, then green after the change. ✅
- IAA fixed-baseline: generated path only; floor unchanged. ✅
- One variable per round: grounding budget only; prompt, retry, telemetry all
  unchanged. ✅

### Expected result

Projected shadow gate-pass 98/101 → **~101/101** (the three fallbacks recover).
Re-drive is **optional** for Tier 1 (offline benchmark is the gate); a
confirmation re-drive can fold into the 2b drive. **Binomial note:** at n=101
needing ≥96, a true-0.99 generator passes ~1.00 — a re-drive that comes back
<99/101 would signal a *new* defect, not noise.

---

## Item 2 — GoalJudge audit-trail (archive the contradicted condition)

**File:** `components/goal_judge.py` (+ its react_loop publish seam)
**Risk class:** observability only — **no verdict-behavior change**.

### Why

The dominant false-verdict source, now that the conditions pipeline is healthy,
is the fast-tier judge contradicting its own `evidence_digest` on a specific
condition (4-trace pattern: `3921c61b`, `0b54f4e1`, `4b8c3f68`, `04fa2506`).
We currently cannot simulate a fix offline because the **per-condition verdict +
the evidence the judge cited for it** is not archived as artifact text — the
identical blind-diagnosis trap that produced round 2's wrong root cause. This
item closes that gap so **Stage B (condition-vs-answer NLI) can be designed
against real artifacts, not inferred blind.**

### Design

Apply the R3 telemetry pattern (carry artifact text, not just symptom strings)
to the judge:

- Ensure the judge's structured output already carries, per condition, `{text,
  met: bool, evidence}` (verify against `components/schemas.py` GoalJudge result
  — if `evidence` per condition is absent, that is the change; if present, this
  item is publish-seam only).
- In the eval-capture publish seam (mirror `publish_goal_judge` / the R3
  `eval.task_understanding` span), archive on every verdict a compact
  `criteria[]` of `{index, met, evidence_excerpt}` so a contradiction
  (`met=false` while `evidence_excerpt` supports it) is reconstructable offline.
  O1 contract: publish MUST NOT raise.
- **No new gate, no downgrade enablement.** The known `would_downgrade: true`
  on correct runs stays disabled until Stage B lands — this item only makes the
  defect *visible*, it does not act on it.

### TDD

Component test: a GoalJudge result with a `met=false` condition still produces a
publish payload containing that condition's text + cited evidence excerpt;
publish-raises-are-swallowed (O1) test stays green.

### Blast radius

| Surface | Change |
| --- | --- |
| `components/goal_judge.py` / `components/schemas.py` | per-condition evidence in result (only if absent) |
| react_loop publish seam | archive `criteria[]` excerpts in the judge eval span |
| `tests/components/test_goal_judge*.py` | +1 archival case; O1 swallow case unchanged |

**Not touched:** judge prompt, verdict thresholds, downgrade gate, wire schema.

### Compliance

O1 (judge publish never raises) preserved; H5 (one eval_capture per invocation)
unchanged — this enriches the existing capture, adds none. ✅

---

## Item 3 — meta-benchmark `synthesis_validator` (the next landmine)

**File:** `components/synthesis_validator.py` + new fixture + new test
**Risk class:** measure-then-decide — benchmark is the deliverable; a code fix
only if the benchmark proves a false-positive rate.

### Why this is load-bearing, not housekeeping

`validate_synthesis` runs at react_loop.py:1423–1438 on **every successful
terminal answer** and, if `confidence < 0.6`, **flips `outcome` from `success`
to `failure`** — *before the GoalJudge runs*. Its `_branch_covered`
(`synthesis_validator.py:25`) uses:

```python
tokens = re.findall(r"[a-zA-Z]{4,}", branch.lower())  # SAME bug class as pre-R3 _content_tokens
...
return any(token in answer_lc for token in tokens[:3])
```

Three independent defects, none benchmarked:
- **No edge-punctuation handling** — the exact bug R3 just fixed in
  `_content_tokens`. `branch="status.txt"` tokenizes to `status`, `txt`; an
  answer saying "wrote status.txt" still matches, but `wc`-style 2-char tokens
  (`wc`, `OK`) are dropped by the `{4,}` floor entirely.
- **`{4,}` floor drops short but load-bearing tokens** (`OK`, `wc`, command
  names) — a correct answer about a short branch can score 0 coverage.
- **`tokens[:3]` only checks the first three tokens** of a branch — a branch
  whose distinguishing term is 4th+ is judged on its preamble.

A false positive here loops a genuinely-complete answer (or routes it to the
judge as `failure`), which is **worse than the TU gate's blast radius** because
it is not shadow-gated — it is live today.

### Design

**Step 3a (always): build the meta-benchmark — no code change.**
Create `tests/fixtures/synthesis_validator/synthesis_benchmark_v1.json` with the
same must-accept / must-reject structure as the TU gate benchmark:
- **must-cover** (true completions that should score ≥0.6 coverage): drawn from
  the goldset multi-branch L2 tasks paired with hand-written correct answers,
  plus deliberate edge cases (short-token branches `OK`/`wc`, path branches
  `status.txt`, branches whose key term is 4th+).
- **must-not-cover** (genuinely incomplete answers that should loop): an answer
  addressing only one of three branches.
Add `tests/components/test_synthesis_validator_benchmark.py` replaying it through
`validate_synthesis` (or `_branch_covered` directly for the unit slice).

**Step 3b (only if 3a goes RED): apply the same edge-strip + floor fix.**
If the benchmark proves false positives (it will on the short-token /
trailing-punct cases), port the R3 fix: replace `[a-zA-Z]{4,}` with a tokenizer
that edge-strips punctuation and keeps ≥2-char content tokens, and drop the
`[:3]` truncation (or justify it). **This is its own one-variable change** with
its own RED→GREEN, *after* 3a establishes the baseline — never bundled blind.

**Critical constraint:** `validate_synthesis` is **not** part of the 2b α
baseline (it gates outcome classification, not the success_conditions the judge
scores), so fixing it does **not** contaminate the α comparison. But it DOES
change live behavior, so it ships on its own measured PR, not folded into the
flip.

### Blast radius

| Surface | Change |
| --- | --- |
| `tests/fixtures/synthesis_validator/synthesis_benchmark_v1.json` | new (3a) |
| `tests/components/test_synthesis_validator_benchmark.py` | new (3a) |
| `components/synthesis_validator.py` | tokenizer fix (3b, conditional) |

**Not touched (3a):** nothing in production. **3b** touches only the tokenizer;
`validate_synthesis`'s thresholds (0.6, 0.4 penalty, L2-only, ≥2-branch gate)
are unchanged unless the benchmark demands otherwise.

### Compliance

AGENTS.md #3 (framework-agnostic, already is); process rule #2 (benchmark BEFORE
any fix — 3a precedes 3b by design). ✅

---

## Tier 2 — 2b consume gate (the flip)

**Gated on Items 1 + 3 landing** (Item 2 is audit-only, not blocking but cheap
to co-ship).

### Steps

1. **Goldset replay α vs the frozen deterministic baseline.** Run the GoalJudge
   over the 101-row goldset with `success_conditions_source=generated`, compute
   judge-vs-gold agreement (Krippendorff's α on `goal_met`), compare to the
   deterministic-floor α (0.50) AND to a frozen run. The R3 punct fix and the
   Item-1 exemption touched only `validate_conditions` — the `plan_builder`
   floor is byte-identical — so the comparison is clean (IAA discipline).
2. **κ-vs-α note** (from `goaljudge-stage5-goldset-plan`): report the right
   statistic for the design; don't conflate pairwise κ with the multi-rater α
   the program tracks.
3. **Acceptance:** generated α materially exceeds 0.50 with the goldset's
   binomial/bootstrap CI not straddling the baseline. If it clears, flip the GCS
   flag `success_conditions_source=generated` (30s TTL, no redeploy — same flip
   path as the shadow flip on `ops/goal_judge_config.json`); rollback doc as
   before.
4. **Do NOT enable the downgrade gate** at the flip — the judge still
   false-negatives the generic tail (`would_downgrade: true` on correct runs);
   that waits on Stage B.

### Multi-turn precondition (already met)

The cross-turn staleness fix (`task_understanding_task_id` sibling key) is
shipped + prod-verified (`0b54f4e1`), so multi-turn goldset rows no longer judge
turn N against turn-1 conditions. If any α-corpus rows are multi-turn, this is a
hard precondition — confirmed satisfied.

---

## Tier 3 — Stage B (evidence-quotes → local NLI), post-flip

Unchanged from the long-term plan; Item 2's audit trail is its **input**:
1. Evidence-quote schema in shadow (per-condition `{text, evidence}`, ≤1 null
   budget; deterministic substring check). Prototype: 16/16 verbatim, naive
   prompt 8/16 (over-declares nulls — the safe direction).
2. Local ONNX NLI/grounding verifier (MiniCheck 770M / AlignScore 355M,
   threshold ~0.7 per NeMo practice) following the
   `services/governance/injection_classifier.py` pattern (`maybe_load` graceful
   degrade, three-band, optional `guardrails` extra). Reused **judge-side** for
   condition-vs-answer entailment — the fix for the 4-trace self-contradiction
   defect. Only after this lands does the **downgrade gate** get enabled.

---

## Tier 4 — corpus & scale (parallel, non-blocking)

- Promote `gate_benchmark_v1.json` (and the new `synthesis_benchmark_v1.json`)
  to a **versioned, append-only** corpus — every future live defect adds a
  fixture row before its fix (the "closed evaluation loop").
- Wave-2 goldset to ~150 prompts (gates v1 of the goldset; binomial power at
  n≥150 per `goaljudge-stage5-goldset-plan`).

---

## Sequenced task list

| # | Task | Gate | Re-drive? |
| --- | --- | --- | --- |
| 1 | Item 1: grounding exemption (RED fixture → GREEN) | offline benchmark + L4 | optional, fold into 2b |
| 2 | Item 3a: synthesis_validator meta-benchmark (measure) | benchmark exists + runs | no |
| 3 | Item 3b: synthesis tokenizer fix (only if 3a RED) | RED→GREEN benchmark | no (own PR) |
| 4 | Item 2: GoalJudge audit-trail (archive contradicted condition) | O1 + archival test | no |
| 5 | Tier 2: 2b α replay; flip if α ≫ 0.50 | live goldset α + CI | YES (the 2b drive) |
| 6+ | Tier 3 Stage B; Tier 4 corpus/wave-2 | per long-term plan | per stage |

**Recommended order:** 1 → 2 → (3 if RED) → 4 → 5. Items 1–4 are all offline /
CI-safe and can land in one or two PRs; only step 5 needs a live drive + the GCS
flip (user-run).

## Verification (offline, CI-safe — no live LLM)

```
.venv/bin/python -m pytest \
  tests/components/test_task_understanding.py \
  tests/components/test_task_understanding_gate_benchmark.py \
  tests/components/test_synthesis_validator_benchmark.py \
  tests/components/test_goal_judge*.py \
  tests/orchestration/test_task_understanding_wiring.py -q
```

Each item RED-first on its new fixture/cases, then GREEN. Full regression:
`.venv/bin/python -m pytest tests/components tests/orchestration -q`
(skip `-k 'not swap_radius'` only if a services/+agent_ui_adapter co-change
trips the advisory — not triggered here).

## Acceptance

- Item 1: the 4 known-fallback cases flip reject→accept; the 2-ungrounded
  must-reject stays rejected; adversarial matrix unchanged.
- Item 3a: benchmark exists and runs; its verdict (false-positive rate of
  `validate_synthesis`) is recorded. 3b only if 3a is RED.
- Item 2: judge eval span archives per-condition evidence excerpts; O1 holds.
- Tier 2: generated α ≫ 0.50 (CI clears baseline) before any flip; downgrade
  gate stays OFF.
- Frozen 2b baseline (`plan_builder` floor) is byte-identical across all of
  Tier 1.
