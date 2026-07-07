# Coach RE-CERT Gold-set — Labeling & Audit Findings (2026-07-06)

Status of the Phase-3.9 re-cert instrument after double-labeling, α scoring, freeze,
a rubric-naive third probe, and cross-checking annotator 1's self-audit.

> **✅ OUTCOME (2026-07-06): Phase-3.9 answer-leakage judge CERTIFIED.** GLM-5.2 re-hosted on
> Fireworks (ADR-0019) cleared the FR-9 exit bar — 3× temp-0 replays, all ENABLE, TNR 1.0 /
> TPR 1.0 / κ pass, **zero-flip** (see §"CERTIFIED" below). The Z.ai serving stalls that
> blocked the cert are gone on Fireworks' own engine. `COACH_LEAKAGE_GATE_ENABLED` stays OFF
> (the live-gate flip is a separate Phase-5 step).

---

## 1. Double-labeling result — α = 1.0000, PASS

- Annotator 2 sheet ([coach_goldset_annotator2_sheet.csv](coach_goldset_annotator2_sheet.csv))
  labeled per the v2 rubric (survivor count → mode → carve-out vs channel), blind to
  annotator 1. Every row carries a survivor-count/channel note.
- **47/47 raw agreement with annotator 1** (both 35 `false` / 12 `true`, matching the
  `R-CLEAN-*`/`R-LEAK-*` design). Krippendorff's α (nominal) = **1.0000** — PASS vs the
  ≥ 0.80 bar. Disagreement diff (`cache/coach_recert/recert_alpha_disagreements.csv`)
  is empty.
- Adjudication trivially complete (zero r1≠r2 rows); merged sheet:
  [coach_goldset_combined_sheet.csv](coach_goldset_combined_sheet.csv).
- **Frozen:** [`tests/fixtures/coach_goldset/coach_recert_split_v1.json`](../../../../tests/fixtures/coach_goldset/coach_recert_split_v1.json)
  — 47 non-provisional rows, 12 leaks / 35 clean, all `test` split,
  `human_alpha_answer_leakage: 1.0`, `rubric_version: coach_rubric_v2_specificity`,
  `test_split_hash` stamped (SHA-256 tamper-evidence). Written to a recert-specific
  filename so round-1 `coach_goldset_v1.json` is untouched. (Assembled via
  `assemble_coach_goldset.py --combined-sheet … --rubric-version coach_rubric_v2_specificity
  --row-floor 30`; the `--row-floor` override + `--rubric-version` threading are the
  fresh-recert Task B4-pre fix — the α ≥ 0.80 gate, α = 1.0 here, is the non-provisional
  guarantee for a fresh authored split under the 200-row corpus proxy.)
- The split behaved as designed: the oversampled OVERFLAG-1 clean patterns (open probes,
  rule-teaching, partial sorts) all labeled `false` with full agreement; all `R-LEAK-*`
  rows held `true`.

## 2. Rubric-naive probe (annotator 3) — reproduces the round-1 failure mode

Sheet: [coach_goldset_annotator3_sheet.csv](coach_goldset_annotator3_sheet.csv) —
labeled by gut standard ("did the reply give the answer away?") with the rubric
machinery deliberately not applied. **Diagnostic sidecar only — NOT part of the frozen
gold.**

- **TPR on leaks: 12/12 = 1.000** — real leaks are obvious with or without a rubric.
- **TNR on clean: 33/35 = 0.9429 — below the 0.95 floor**, same failure shape as the
  round-1 gpt-4o REFUSE (TNR 0.9186): intuition over-flags clean teaching, never
  under-flags leaks.
- Both false positives are open probes whose correct answer maps to one letter:
  **R-CLEAN-24** (opener vs closer) and **R-CLEAN-29** (causation direction). The §4.2
  carve-out (learner must answer the probe AND map it) is exactly where calibration
  earns its keep.
- α(r1 or r2 vs r3) = 0.8937; three-way α(r1,r2,r3) = 0.9280 — still above 0.80, drop
  concentrated entirely in those two rows.
- Caveat: the r3 pass was rubric-*unapplied*, not rubric-*unseen* (same labeler had
  read the walkthrough for the r2 pass).

## 3. Annotator 1 self-audit — verified, one gap, one weak argument

The audit's factual claims check out against the sheet (35/12, no empty notes, notes
read as described, minimal-pair citations present). No label changes warranted. Findings
on the audit itself:

- **R-CLEAN-24 confirmed as the fragile row by three independent signals:** A1's audit
  calls it most-likely-to-split; the r2 note recorded explicit hesitation; the naive r3
  pass actually flipped it to `true`.
- **Audit watch-list incomplete:** A1 flagged R-CLEAN-26 as second-riskiest, but the
  naive probe stumbled on **R-CLEAN-29** (not flagged by the audit) and sailed past 26.
  Union watch-list: **{R-CLEAN-24, R-CLEAN-26, R-CLEAN-29}**.
- **Weak argument in the audit:** its defense of R-CLEAN-24 ("C/D drop as closers,
  leaving A vs B → 2 live") doesn't hold — A ("In conclusion") is also a closer. The
  sturdy defense is straight §4.2: the learner must still classify the sentence and
  each option, so ≥2 stay live for a not-yet-solved learner. Any note tightening should
  cite that, not the A-vs-B survivor arithmetic.
- Audit follow-ups: #2 (second rater + α) done — PASS; #3 (adjudication prep) moot;
  #1 (tighten notes on 24/26/17) is archive-only — the merge drops `rN_note` columns,
  so combined sheet and frozen JSONL are unaffected.

## 4. Caveats to carry into the cert record

1. **Calibration, not independence:** both scored raters labeled from the same
   walkthrough (and the r2/r3 passes shared a labeler). α = 1.0 measures rubric
   operability, not fully independent human judgment. A truly outside human rater would
   be the real control for the stratum-anchoring / confirmation-bias concern
   (`R-CLEAN-*`/`R-LEAK-*` prefixes align 47/47 with labels).
2. **Watch-list for the glm-5.2 re-cert FP analysis:** R-CLEAN-24, R-CLEAN-26,
   R-CLEAN-29. If the judge false-positives anywhere, expect it there — all three are
   open probes / partial sorts whose correct answer collapses to one letter *after* the
   learner does the work.

## 5. Next step (creds-gated)

The offline chain is complete: the fresh split is **frozen** (§1) and the B4-pre
assemble-script fix landed. The only remaining gate is credentials for the live run.

- **`scripts/run_coach_calibration.py` exists** (the replay harness; the earlier "not
  present" note was wrong). The model-pin seam (`COACH_JUDGE_MODEL`, Task C-pre) and the
  v2 `.j2` carve-out (Task A1) are both already built — glm-5.2 is reachable and the
  rubric it renders is v2.
- **Run (local, creds in env):**
  `MODEL_PROFILE_SET=glm COACH_JUDGE_MODEL=glm-5.2 GLM_API_KEY=… .venv/bin/python -m
  scripts.run_coach_calibration --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json
  --dump-labels cache/coach_recert/recert_labels.jsonl --per-call-timeout 90 --out
  cache/coach_recert/coach_recert_cert.json`.
- **Recommended first:** the C0 5-row glm-5.2 abstention smoke (does the direct provider
  reliably emit `answer_leakage`?) before spending the full replay.
- **Exit bar (spec FR-9):** ≥3 temperature-0 replays, every run clearing TNR ≥ 0.95 AND
  TPR ≥ 0.90 AND κ ≥ 0.75 (zero-flip), plus a non-gating gpt-4o comparability replay
  (FR-10). **FP watch-list for the run:** {R-CLEAN-24, R-CLEAN-26, R-CLEAN-29} (§3–§4).

### C1 attempt 2026-07-06 — ALL 47 abstained (credential, not code)

A first C1 run returned `provider error; verdict undecidable` on **every** row →
verdict REFUSE with all gates `undecidable` (empty denominators). This is **not** a
rubric result — the judge never ran; the FR-11 fail-closed path dropped the abstentions
(`false_positives=0`, none scored `false`), exactly as designed.

**Root cause = expired/invalid Z.ai token, diagnosed via a one-call probe** through the
real harness path (`select_judge_profile → get_direct_provider → acompletion`):

```
GLM returned HTTP 401: {"error":{"code":"401","message":"token expired or incorrect"}}
```

The probe **proves the GLM direct extension is healthy**: the request reached
`https://api.z.ai/api/paas/v4/chat/completions`, the model id `glm-5.2` was accepted
(401 = auth, not 404/400 model-rejection), and the adapter parsed the error cleanly. So
**no compatibility work is needed** — unlike DeepSeek (which rides LiteLLM natively,
`litellm_id="deepseek/deepseek-v4-flash"`), GLM already has its purpose-built direct
adapter (`services/llm_providers/glm_direct.py`) because LiteLLM does not map `zai/glm-5.2`.
The extension is done; the only blocker is a **valid, unexpired `GLM_API_KEY`** from the
Z.ai account (a credential-lifecycle issue outside the repo). Re-run C0 → C1 once a fresh
token is in the operator env; nothing in the code changes.

### C1 replay #1 (fresh key) — ENABLE, but 1-of-≥3 and abstain-noisy

With a working key, one full replay completed
(`cache/coach_recert/coach_recert_cert_run3.json`, `recert_labels_run3.jsonl`):

| Metric | Value | Floor | |
|---|---|---|---|
| **TPR** (leak recall) | **1.000** (12/12) | ≥ 0.90 | ✅ zero recall regression |
| **TNR** (clean specificity) | **0.9667** (29/30) | ≥ 0.95 | ✅ **but 1 clean row of margin** |
| **κ** | pass | ≥ 0.75 | ✅ |
| verdict | **ENABLE** | | precision 0.923, FAR 0.033 |

Confusion: TP 12 / FP 1 / FN 0 / TN 29, **abstain 5**. The v2 carve-out worked: round-1
had **7 FPs / 87 clean**; this run has **1 FP / 30 scored-clean**. The single FP is
**R-CLEAN-29** — on the pre-registered watch-list {R-CLEAN-24, R-CLEAN-26, R-CLEAN-29}
(§3–§4); the naive r3 probe also flagged it. So the residual miss is a known-hard
causation-direction row, not a new failure mode.

**Two reasons this is NOT yet ENABLE-certified:**
1. **1 replay, not ≥3 (FR-9 zero-flip).** TNR clears by a single clean row (0.9667; the
   floor needs ≤1.5 FP on 30, this has 1). A 2nd FP in another replay → 28/30 = 0.933 =
   FAIL. A knife-edge single run is exactly what the ≥3-zero-flip rule guards against.
2. **Abstain-noise makes TNR non-comparable across runs.** Run3 scored TNR on a 30-row
   denominator (35 clean − 5 abstained: R-CLEAN-01/07/09/20/25). The judge has **no
   retry** ([`components/subject_coach_judges.py:90`](../../../../components/subject_coach_judges.py) —
   `except Exception: return None`, AP-6 fail-closed by design), so transient Z.ai errors
   abstain whichever rows they hit, and the set differs run-to-run — "zero-flip" can't be
   verified when each replay measures a different clean subset.

**Open decision (unresolved):** add bounded retry to the judge (attacks the root cause →
all replays see the full 47) **vs.** run the remaining replays as-is and analyze whether
abstains are low/stable enough to conclude. Runs 1 and 2 of the 3-replay command did not
write artifacts (only run3 landed); C2 (gpt-4o anchor) and ≥2 more glm replays still owed.

### Error-mix probe (2026-07-06) — abstains are NOT rate/timeout; timeout+pacing ruled out

A read-only diagnostic fired **20 back-to-back GLM calls at the same 90s timeout**:
**20/20 ok, 0 failed**, latency min 1.4s / median 1.8s / **max 8.6s** (vs the 90s ceiling),
no 429, no 5xx. So the endpoint is healthy and **neither raising `--per-call-timeout` nor
pacing has anything to act on** — the transient abstains are not rate-limits or fixed-
timeout cutoffs.

The abstains also don't correlate with payload: run3's 5 abstained rows (R-CLEAN-01/07/09/
20/25) have reply lengths 158–246, squarely inside the non-abstain range (116–215), spread
across strata, and **all 5 are `R-CLEAN-*` in run positions 1–25; every `R-LEAK-*` row
(36–47) succeeded**. The run logged `provider error` (judge line 90, the *call* raised),
not `unparseable verdict` (line 107) — so these are exceptions on the heavier thinking-mode
judge generation (long v2 rubric prompt, `max_output_tokens=8192`), not the toy 16-token
calls the probe made. **Implication:** the only knob that addresses intermittent per-call
provider exceptions is **bounded retry** in the judge; the chosen timeout+pacing path is
evidence-contradicted. Re-decision owed.

### FIX LANDED: bounded retry in the judge (2026-07-06)

`components/subject_coach_judges.py` now retries a **transient provider error** up to
`_MAX_ATTEMPTS=3` with backoff (0.5s·2^n), wrapping **only** the provider call — a
malformed-JSON verdict is deterministic and is not retried. AP-6 preserved: exhausted
retries → `None`, never a fabricated verdict. 3 red-first L1 tests
(`TestProviderRetry`: recover-after-1-fail, exhaust→None, parse-not-retried), `make check`
green (5096 passed). Decision logged in [`../../../adr/decisions.md`](../../../adr/decisions.md).
**This should drive abstains toward 0**, making the FR-9 zero-flip TNR comparable across
replays. **Next:** re-run the ≥3 glm-5.2 replays (below) + the C2 gpt-4o anchor.

### C2 gpt-4o comparability anchor (FR-10, non-gating) — the v2 fix is VALIDATED

The gpt-4o replay on the fresh split (`cache/coach_recert/coach_recert_cert_gpt4o.json`)
is the clean before/after ADR-0018 was built to produce — **same model, same axis**, only
the rubric + split change:

| | Round 1 (v1 rubric, 116-row seen split) | Re-cert (v2 rubric, 47-row fresh split) |
|---|---|---|
| **TNR** | **0.9186 FAIL** (7 FP / 87 clean) | **1.000** (0 FP / 35 clean) |
| **TPR** | 0.966 | 1.000 (12/12) |
| verdict | **REFUSE** | **ENABLE** |

Confusion: TP 12 / FP 0 / FN 0 / TN 35 / abstain 0, precision 1.0, FAR 0.0. Because the
model is held constant, the **TNR 0.9186→1.000 jump is attributable to the rubric prose**,
exactly ADR-0018's causal claim: the OVERFLAG-1 category (mechanism-teaching read as
item-collapse) that caused all 7 round-1 FPs is gone — gpt-4o passes all 35 clean rows on a
split it was never fit to (§9-clean), *including* R-CLEAN-29 (the row glm-5.2 still trips).

**Caveat (honest):** FR-9 gates on **glm-5.2**, not gpt-4o — this anchor is diagnostic. It
proves the *rubric* is sound, so any residual glm FP is a **model-specificity gap, not a
rubric defect**. The ENABLE verdict still rides on the 3 glm-5.2 zero-flip replays.

### TWO abstain modes — the retry covers only one (correction, 2026-07-06)

The first post-retry glm replay surfaced `TIMEOUT (>90s) → abstain` lines — a **different**
failure than run3's fast `provider error` abstains. Root cause of the distinction:
`run_coach_calibration.py:197` wraps the **entire** `evaluate()` call (all 3 internal
retries) in a **single** `asyncio.wait_for(timeout=per_call_timeout)`. So:

- **Fast transient exception** (run3's 5 abstains, calls that raised in <90s) → the judge's
  bounded retry recovers them ✅.
- **Genuine slow call (>90s)** → `wait_for` cancels the *whole* coroutine at 90s **before**
  the retry can reach attempt 2 — so a timeout abstain is **not** retried; the heavy
  glm-5.2 thinking-mode generation on some rows simply needs more wall-time than 90s.

This **corrects the earlier toy-probe read**: 16-token toy calls maxed at 8.6s, but the
*real* judge call (full v2 rubric + thinking mode) occasionally exceeds 90s. So for the
timeout-mode abstains, **raising `--per-call-timeout` is the correct lever** (the retry
addresses only the fast-exception mode). Open: pick a timeout with margin over the real
judge-call p95 (measure, or set ≥180s) and re-run the 3 glm replays.

**glm-5.2 run1 (POST-retry, timeout 90) — ENABLE, TNR 1.0 / TPR 1.0:** confusion TP 12 /
FP 0 / FN 0 / TN 33, **abstain 2** (only R-CLEAN-05, R-CLEAN-20 — both `TIMEOUT (>90s)`;
the retry eliminated run3's 5 fast-transient abstains). Two reads: (a) the retry works —
remaining abstains are timeout-mode only; (b) **R-CLEAN-29 scored `tn` here** (it was the
lone FP in pre-retry run3) — the exact tn↔fp knife-edge ADR-0018 predicted, so ≥3 zero-flip
runs remain necessary, not one clean run. TNR is on **33** scored-clean (35 − 2 timeouts),
so the denominator still isn't full — **raise the timeout to 180s and re-run 3× for a
clean 35-row zero-flip comparison** (retry + realistic timeout → expected ~0 abstains).

**Timeouts are STALLS, not slow-but-bounded generation (2026-07-06).** A re-run at
`--per-call-timeout 180` still produced a timeout abstain — but on **R-CLEAN-07**, not the
R-CLEAN-05/-20 that hung at 90s. The *which-row-hangs* set shifts run-to-run and a call
exceeded even 180s, so the cause is an **intermittent provider-side stall** (a call that
occasionally never returns), not specific rows needing more wall-time (those would clear at
180). Implication: bumping the timeout higher just moves the unlucky row; it won't reach 0
abstains. The realistic close-out is either (a) accept ~1–2 stall-abstains per run as noise
and apply zero-flip to the **rows all 3 runs scored** (intersection denominator), or (b) a
harness-level per-call *retry-on-timeout* (distinct from the judge's fast-exception retry,
which the outer `wait_for` cancels) — a bigger change than 3.9 warrants right now.

---

## Fireworks re-host — offline build LANDED (ADR-0019, 2026-07-06)

The stall is Z.ai's **serving layer**, not the model (external research
`docs/research/eng-coach-judge/` confirms; the *which-row-hangs* shift above is the
signature of MoE-batch/capacity nondeterminism). Decision (ADR-0019): re-host GLM-5.2 on
**Fireworks AI** and re-cert there; screen cross-family reasoning candidates first. The
offline seam is built + `make check`-green (spec/plan/tasks under `docs/plan/coach-recert-fireworks-rehost.*`):

- **Fireworks adapter** `services/llm_providers/fireworks_direct.py` — thin subclass of
  `GLMDirectProvider` (same OpenAI-compatible wire), base_url `…/inference/v1`, error label
  `fireworks`; the proven parse path (thinking-strip, tool-map) is inherited.
- **Factory** `get_direct_provider` — a `-fireworks` branch checked **before** the glm
  branch (the ordering hazard: `glm-5.2-fireworks` matches both `startswith("glm")` *and* the
  suffix — suffix-first is load-bearing, else the judge silently runs on Z.ai). Missing
  `FIREWORKS_API_KEY` ⇒ typed `ConfigurationError`, never a Z.ai fallback (FR-1).
- **Profiles** `services/llm_config.py` `_FIREWORKS_PROFILES` + `MODEL_PROFILE_SET=fireworks`
  (default `glm-5.2-fireworks`): the GLM-5.2 lead + 3 candidates (`deepseek-r1-fireworks`,
  `qwen3-235b-fireworks`, `ln-ultra-fireworks`) — wire ids `accounts/fireworks/models/<slug>`.
- **Provenance (FR-3, do-regardless):** every dumped label row now carries `judge_model`
  (`replay_test_split_rows(..., model=…)`) — the run1/run2 mislabel (env not switched) is now
  visible per-row, not only in the cert header.
- **Screening harness** `scripts/screen_coach_candidates.py` — per-candidate TNR/TPR/κ/abstain
  on the frozen split; a candidate Fireworks doesn't serve is recorded `unavailable`, not a
  fabricated 0.0 (FR-7). A **fail-fast availability probe** (one cheap direct call before the
  47-row replay) surfaces a 404 as `unavailable` immediately — WITHOUT it the judge's bounded
  retry swallows a per-row 404 into an abstain, so an unserved model would masquerade as "47
  abstains" and burn 47×3 calls (found + fixed on the first live screen, 2026-07-06).

**Catalog slug correction (live, 2026-07-06 — the FR-7 confirm-at-screening step).** The first
screen 404'd on `accounts/fireworks/models/glm-5.2` ("Model not found … not deployed"). The key
authed fine (no 401); the SLUG was wrong: **Fireworks encodes a version dot as `p`** — GLM-5.2
is `glm-5p2`, not `glm-5.2`. The account's serverless catalog (`GET /v1/models`) served 7
models; the three cross-family candidates originally guessed (`deepseek-r1`, `qwen3-235b-a22b`,
`llama-nemotron-ultra`) are **NOT serverless** on this account (`deepseek-r1` is "Serverless:
Not supported" — dedicated-only). Profiles updated to the confirmed-served set: lead
**`glm-5p2`** + cross-family **`deepseek-v4-pro`**, **`kimi-k2p6`**, **`gpt-oss-120b`**. GLM-5.2
(the Z.ai quality lead) IS serverless-available on Fireworks — no dedicated endpoint needed.

### Operator runbook — LIVE re-cert (manual, creds-gated; the agent cannot run this)

`FIREWORKS_API_KEY` lives in the operator `.env` and **must be exported to the shell** (the
repo does not auto-load it; the agent is blocked from reading `.env`).

```bash
export FIREWORKS_API_KEY=…   # the real key, from your .env

# 1. SCREEN all candidates on the frozen 47-row split → pick the winner
MODEL_PROFILE_SET=fireworks .venv/bin/python -m scripts.screen_coach_candidates \
    --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json \
    --out cache/coach_eval/fireworks_screen.json
# winner = GLM-5.2 lead unless a candidate beats it on TNR/TPR/κ at the same ~0 abstain.

# 2. CERT the winner ≥3× at temp-0 (dedicated endpoint if provisioned — FR-10)
for i in 1 2 3; do
  MODEL_PROFILE_SET=fireworks COACH_JUDGE_MODEL=glm-5.2-fireworks \
  .venv/bin/python -m scripts.run_coach_calibration \
      --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json \
      --dump-labels docs/IAA/coach/recert/recert_labels_fw_run${i}.jsonl \
      --out cache/coach_eval/coach_recert_fw_run${i}.json \
      --per-call-timeout 180
done
```

**ENABLE only if** all 3 runs clear **TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip** (no run dips
below any floor — FR-9). Commit the `recert_labels_fw_run{1,2,3}.jsonl` (CI replays them
offline — FR-11). A shared-endpoint zero-flip failure is a **recorded non-ENABLE**, never a
floor relaxation (FR-10). `COACH_LEAKAGE_GATE_ENABLED` stays **OFF** — flipping it is a
separate human Phase-5 step.

### Fireworks screening result (live, 2026-07-06) — GLM-5.2 WINS decisively

All 4 served candidates screened on the frozen 47-row split (12 leak / 35 clean). GLM-5.2
holds TNR 1.0 with ZERO false positives while every cross-family candidate over-flags or
stalls — the capability gradient the brainstorm predicted, now confirmed on identical rows:

| Candidate (Fireworks slug) | TNR | TPR | Abstain | Confusion | Verdict |
|----------------------------|-----|-----|---------|-----------|---------|
| **glm-5p2** (WINNER) | **1.00** (33/33) | **1.00** | 2 (stall) | TP12 FP0 FN0 TN33 | ✅ quality passes |
| deepseek-v4-pro | 0.824 (28/34) | 1.00 | 1 | **FP6** | ❌ over-flags (OVERFLAG-1) |
| kimi-k2p6 | — | — | every row | — | ❌ stalls (>90s) every call |
| gpt-oss-120b | 0.714 (25/35) | 1.00 | 0 | **FP10** | ❌ REFUSE, worst over-flagger |

**Read:** the three cross-family reasoning models all reproduce the ADR-0018 OVERFLAG-1
failure (reading clean teaching as item-collapse) — DeepSeek-V4-Pro 6 FP, GPT-OSS-120B 10 FP —
or are too slow at the v2-rubric thinking load to score at all (Kimi). GLM-5.2's 6 FP on the
3.9 gpt-4o cert (TNR 0.9186) is GONE here (0 FP): the ADR-0018 v2 rubric carve-out + GLM's
capability together hold the line. GLM-5.2 is the judge; the open item is its **2/47 occasional
stalls** (down from Z.ai's frequent-and-shifting), a latency/determinism issue → the FR-10
dedicated-endpoint lever (or a 180s timeout + intersection-denominator across the 3 replays).
The abstained rows differ run-to-run (R-CLEAN-14/-18 here), the same intermittent-stall
signature, so a dedicated endpoint is the clean path to a full-35-row zero-flip.

### Operator runbook — GLM-5.2 3× cert (the winner)

```bash
export FIREWORKS_API_KEY=…
# 3× temp-0 cert on the winner (serverless; raise timeout to reduce stalls).
for i in 1 2 3; do
  MODEL_PROFILE_SET=fireworks COACH_JUDGE_MODEL=glm-5.2-fireworks \
  .venv/bin/python -m scripts.run_coach_calibration \
      --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json \
      --dump-labels docs/IAA/coach/recert/recert_labels_fw_run${i}.jsonl \
      --out cache/coach_eval/coach_recert_fw_run${i}.json \
      --per-call-timeout 180
done
```

If the 2-stall noise blocks a clean zero-flip on serverless, provision a Fireworks **dedicated
endpoint** for `glm-5p2` (FR-10) and re-point the profile's `litellm_id` to the endpoint id —
removes the serverless MoE-batch nondeterminism. `COACH_LEAKAGE_GATE_ENABLED` stays OFF until
the 3× zero-flip clears.

### ✅ CERTIFIED — GLM-5.2 3× cert CLEARS FR-9 (serverless, 180s, 2026-07-06)

The 3× temp-0 cert on `glm-5.2-fireworks` (serverless, `--per-call-timeout 180`) met the exit
bar. Mechanically verified by diffing the three committed label files
(`recert_labels_fw_run{1,2,3}.jsonl`):

| Run | Confusion | TNR | TPR | κ | Abstain | Verdict |
|-----|-----------|-----|-----|---|---------|---------|
| run1 | TP12 FP0 FN0 TN35 | **1.0** | **1.0** | pass | 0 | ENABLE |
| run2 | TP12 FP0 FN0 TN35 | **1.0** | **1.0** | pass | 0 | ENABLE |
| run3 | TP12 FP0 FN0 TN34 | **1.0** | **1.0** | pass | 1 (R-CLEAN-29 stall) | ENABLE |

**Zero-flip CONFIRMED:** every row scored in ≥2 runs got the identical label in all of them
(0 flips). `R-CLEAN-29` is an *abstain* in run3 (one >180s stall — dropped from the denominator
per FR-11), **not** a label flip (it was `tn` in runs 1&2, never flipped to `fp`). TNR holds
1.0 on the scored-clean rows regardless. All three runs `verdict=ENABLE`, all gates pass.

**FR-9 exit bar MET** — ≥3 temp-0 replays, every one TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75, zero-flip.
Phase-3.9 answer-leakage judge is **CERTIFIED** on GLM-5.2-on-Fireworks. This is the out-of-sample
enable cert ADR-0017 named + ADR-0018's exit bar. Result vs the 3.9 gpt-4o cert that started this
(REFUSE, TNR 0.9186, 7 FP): **0 FP now** — the ADR-0018 v2 rubric carve-out + GLM-5.2 capability
+ a reliable host together close it.

**Still gated (unchanged):** `COACH_LEAKAGE_GATE_ENABLED` stays **OFF** — flipping the live
leakage gate is a separate human **Phase-5** step (spec §5; this cert aimed a REFUSE at ENABLE,
it does not itself gate the live coach). The committed `recert_labels_fw_run{1,2,3}.jsonl` are
the CI-replayable offline evidence (FR-11).
