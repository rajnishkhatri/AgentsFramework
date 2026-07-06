# Spec — Coach fresh held-out re-cert split + Phase-3.9 recertification (glm-5.2)

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Related:** [ADR-0018](../adr/0018-subject-coach-rubric-specificity-revision.md) (the *why* — the CLEAN carve-out, **Accepted**) ·
[specificity spec](coach-rubric-specificity-revision.spec.md) (the sibling *what* — the `.j2` prose edit, FR-1..FR-9) ·
[enable-policy](coach-goldset-enable-policy.spec.md) (ADR-0008 cond#1 floor) ·
[parent ledger](subject-coach-agent.plan.md) (Task 3.9 REFUSE → 3.10).

> **Scope split (read first).** The sibling *specificity spec* already covers the
> `subject_coach_pedagogy_judge.j2` prose carve-out and the re-cert **exit bar shape**.
> This spec covers the one thing ADR-0018 named "the biggest piece of work" and left in
> its `Open #1`: **producing the FRESH held-out split** the re-cert must score on, plus
> **pinning the two open re-cert decisions** (split source, model) and **operationalizing
> "with margin"** into a testable rule. Where the two specs overlap (the exit bar), this
> one is authoritative on the *split* and *margin*; the specificity spec stays
> authoritative on the *prose*.

---

## 1. Goal

Produce a **fresh, human α-labeled clean+leak split** — disjoint from the 3.9 116-row
test split and the 7 coded FP rows — and run the Phase-3.9 recertification of the coach
`answer_leakage` judge on it (post-carve-out `.j2`), so the ADR-0008 cond#1 gate can
reach **ENABLE with margin** on *unseen* text. For the Subject-Coach maintainers gating
the Phase-5 `COACH_LEAKAGE_GATE_ENABLED` flip.

## 2. Context

Task 3.9 certed **REFUSE** on `coach_goldset_v1` (gpt-4o): TPR 0.966 ✓, κ ✓, **TNR
0.9186 ✗** (floor ≥0.95; confusion TP28/FN1/**FP7**/TN79, +1 abstain `T-CLEAN-20`
dropped from the denominator). Open coding of the 7 FPs axial-collapsed to one category
**OVERFLAG-1** (mechanism-teaching / open probe / locus-pointing read as item-collapse;
**0** gold-dispute, **0** incoherent-read). ADR-0018 (Accepted 2026-07-06) chose a
prose-only CLEAN carve-out; the specificity spec covers that edit.

The carve-out is **reverse-engineered from those 7 FPs**. Per ADR-0018 §9 and its named
n=7 circularity risk, it **must not be validated on the rows it was fit to** — the 3.9
test split is now "seen." A **fresh** held-out split is therefore the gating prerequisite,
not an afterthought (ADR-0018 Consequences "Follow-on"; specificity-spec Open #1). This
spec builds that split and runs the re-cert.

**Two decisions were open (specificity-spec Open #2/#3); this spec settles them** (also
recorded in `docs/adr/decisions.md`):

- **Split source = in-session authored.** ~40–60 fresh clean+leak turns on the **same
  6-question dev item bank**, new phrasings/strata, then human α-labeled — matching the
  ratified "corpus decision v2" (option-3-first, no LLM drafting call) and how batch-2
  was built. Fastest path to a labeled disjoint split with a controlled leak/clean mix.
- **Re-cert model = `glm-5.2`** (`provider="direct"`, `services/llm_providers/glm_direct.py`,
  reads `GLM_API_KEY`/`ZAI_API_KEY`). **This is a change from 3.9's gpt-4o** and its cost
  is stated as an accepted risk in §5/§7: it **breaks the direct before/after
  comparability** the ADR-0018 argument leans on. Mitigation: FR-10 additionally records a
  **gpt-4o replay** on the same fresh split as the comparability anchor (diagnostic, does
  not gate).
- **"With margin" = TNR ≥ 0.95 held across a zero-flip replay** (§FR-9): the floor is
  kept at 0.95 but must hold across **≥3 temperature-0 replays** with **no single run
  dipping below** — handling the measured ~1-row temp-0 drift by *stability*, not by a
  higher headroom number.

## 3. Functional requirements (EARS)

Failure paths (recall + §9 disjointness) FIRST.

- **FR-1 (recall must not regress — the guarding failure path).** IF the re-cert on the
  fresh split shows any ADR-0017 indirect-leak channel going undetected THEN the revision
  SHALL be REFUSED: every replay's TPR SHALL be ≥ 0.90 (`tpr_min`), not only the mean.
- **FR-2 (fresh-split disjointness — §9, the hard gate).** THE fresh split's `item_id`s
  SHALL be disjoint from (a) the 116 `coach_goldset_v1` test-split ids AND (b) the 7 coded
  FP `trace_id`s (`T-CLEAN-03/12/16/17/19/29`, `T-UL-01`) AND (c) `T-CLEAN-20`; a
  deterministic L1 test SHALL assert the empty intersection and fail if any id recurs.
- **FR-3 (fresh split is human α-labeled, non-provisional).** THE fresh split SHALL carry
  a double-labeled `answer_leakage` gold with Krippendorff α ≥ 0.80 (reusing
  `alpha_answer_leakage`), and its manifest SHALL stamp `provisional=false`; a provisional
  split SHALL short-circuit the cert to `REFUSE_PROVISIONAL` (unchanged fail-closed).
- **FR-4 (controlled clean/leak balance).** THE fresh split SHALL contain **both**
  classes with a leak share in `[0.20, 0.40]` (mirrors 3.9's 29/87 ≈ 0.25) and **≥ 20
  clean rows** (so TNR has a denominator where a single FP moves it < ~0.05) and **≥ 10
  leak rows** (so TPR is not decided by one case); `leak_class_share` SHALL be asserted in
  range.
- **FR-5 (fresh authored, item-bank-reused, strata-fresh).** THE fresh turns SHALL be
  authored in-session on the existing 6-question dev bank with **new utterance phrasings
  and strata** (breadth + the OVERFLAG-1-adjacent hard strata: open-probe, rule-named,
  locus-pointing, strong-implication), and SHALL NOT reuse any 3.9 utterance text
  verbatim (§9 — a fresh-text test greps for 3.9 utterance overlap).
- **FR-6 (item-enrichment parity).** WHEN the fresh cases are recorded THE rendered
  `question` block SHALL be resolved from the ground-truth item bank via the existing
  `enrich_coach_judge_cases.py` path (ADR-0017 F5 — the judge MUST see the passage/stem/
  choices, pre_submit strips the key), never the bare `question_id`.
- **FR-7 (re-cert runs post-carve-out `.j2`).** THE re-cert SHALL replay the fresh split
  through the judge rendering `rubric_version = coach_rubric_v2_specificity` (the
  carve-out from the specificity spec MUST be landed first); a re-cert against
  `coach_rubric_v1_revised` SHALL be rejected as stale.
- **FR-8 (re-cert model = glm-5.2, creds-gated, local-only).** WHEN the live re-cert runs
  THE judge model SHALL be `glm-5.2` via the direct provider; the run SHALL be
  manual/local (`GLM_API_KEY` in the operator env) and SHALL NOT be wired to `make check`
  or CI. A gpt-4o replay on the same split SHALL additionally be recorded (FR-10).
- **FR-9 (exit bar — ENABLE with margin as zero-flip stability).** WHEN the fresh re-cert
  runs THE decision SHALL be `ENABLE` only if, across **≥3 temperature-0 replays**,
  **every** run satisfies TNR ≥ 0.95 AND TPR ≥ 0.90 AND κ ≥ 0.75 — i.e. **no single run
  dips below any floor** (zero-flip). A mean-passing set with any sub-floor run SHALL NOT
  be ENABLE.
- **FR-10 (comparability anchor — diagnostic, non-gating).** THE re-cert SHALL record a
  gpt-4o replay on the fresh split alongside the glm-5.2 gate run, so the before(3.9
  gpt-4o REFUSE)/after delta is attributable to the prose and not confounded by the model
  swap; this replay is diagnostic-only and SHALL NOT change the ENABLE/REFUSE verdict.
- **FR-11 (abstention handling — AP-6).** IF a judge call abstains (provider timeout /
  unparseable) THEN that row SHALL be dropped from the confusion for that replay (never
  scored `false`), mirroring the 3.9 `T-CLEAN-20` handling and the replay harness.
- **FR-12 (tamper-evidence).** THE frozen fresh split SHALL carry a
  `compute_test_split_hash` SHA-256 over its test rows in the manifest, so a later silent
  edit to the "held-out" surface is detectable.

## 4. Data model / contracts

**No new types.** The fresh split is a second `coach_goldset_v*` artifact
(`{rows, manifest}`) built from the **existing** `CoachGoldsetItem` /
`CoachGoldsetManifest` types (`services/governance/coach_goldset_dataset.py`) — same
`extra="forbid"`, same required `answer_leakage`, same taxonomy gate, same
`GoldsetSplit`/`GoldsetProvenance`. The re-cert reuses `evaluate_coach_enable_gates`
(`services/governance/coach_calibration.py`) and the `run_coach_calibration` replay
harness unchanged (`--dump-labels --per-call-timeout` from 3.9). The one new *value* is
the artifact path (e.g. `tests/fixtures/coach_goldset/coach_recert_split_v1.json`) and its
manifest `rubric_version = coach_rubric_v2_specificity`.

> **Naming decision:** author as a **separate artifact** (`coach_recert_split_v1`), not a
> grown `coach_goldset_v1`. Rationale: the 3.9 split must stay byte-frozen as the
> historical REFUSE evidence (FR-2 disjointness is easier to assert across two files than
> within one), and a separate file makes "this is the unseen surface" structurally clear.

## 5. Invariants & security boundaries

- **No live LLM in CI (hard):** the glm-5.2 re-cert AND the gpt-4o anchor are
  manual/local, creds-gated (`GLM_API_KEY`); CI replays only the committed post-run
  labels offline via the `run_coach_calibration` pure core. FR-8 forbids a `make check`
  wire.
- **Secrets never flow through the agent:** `GLM_API_KEY` lives in the operator's local
  `.env` (the `pre_bash_guard` hook blocks agent `.env` reads — confirmed this session);
  the spec references the **name** only, never the value.
- **Invariant #7 (services ↛ components):** the goldset module already mirrors
  `LeakChannel` locally with a drift test; no change. **Invariant #2 (trust purity):**
  `PedagogyVerdict` is a `components/` type — no `trust/` change, no re-sign.
- **prompts/ H1 / AP-3 (config split):** the margin (TNR ≥ 0.95, zero-flip) is a **code
  floor** in `COACH_ENABLE_THRESHOLDS` / the replay-count in the harness, NOT a number in
  the `.j2` (the `.j2` edit is the sibling spec's; this spec adds no template threshold).

## 6. Edge cases

- **Fresh split accidentally re-samples a 3.9 utterance** → FR-5 fresh-text grep + FR-2 id
  disjointness both fire; author must rephrase. (Belt and suspenders because id-disjoint
  but text-identical would still be contamination.)
- **α < 0.80 on the double-label** → the split is not usable as gold (FR-3); resolve
  disagreements or add rows before the cert, exactly as the 3.9 human pass did.
- **glm-5.2 abstains at a higher rate than gpt-4o** (direct provider, different timeout
  profile) → FR-11 drops abstentions per replay; if abstentions exceed ~10% of any class,
  the replay is inconclusive, not a pass — re-run with the `--per-call-timeout` raised
  (the 3.9 replay-hang lesson).
- **Zero-flip fails on 1 of 3 runs** (a clean row flips tn→fn) → NOT ENABLE (FR-9); this
  is the exact temp-0 drift the zero-flip rule exists to catch. Route to sdd-replan:
  either the carve-out needs another prose pass (back to the specificity spec) or the
  margin is genuinely knife-edge → telemetry-only (ADR-0018 option E).
- **Leak share drifts out of `[0.20,0.40]`** while authoring → FR-4 asserts and fails the
  build; rebalance before labeling.

## 7. Non-functional requirements

- **Cost/latency:** ~40–60 rows × ≥3 replays × 2 models (glm-5.2 gate + gpt-4o anchor) ≈
  a few hundred live calls, local/on-demand — accepted, off the CI hot path.
- **Determinism:** the exit bar is an **L4 aggregate over replays** (zero-flip stability),
  not an L1 exact assertion; the disjointness/balance/fresh-text checks are **L1
  deterministic** and run in `make check`.
- **Reversibility:** additive — a new fixture file + a `decisions.md` note + ledger update;
  no schema/data migration; the 3.9 artifact is untouched.
- **Comparability caveat (accepted):** gating on glm-5.2 while 3.9 was gpt-4o means the
  headline before/after is cross-model; FR-10's gpt-4o anchor is the mitigation, and this
  caveat is recorded in `decisions.md`.

## 8. Test plan

Failure-path (recall + §9 disjointness + balance) first. L1 rows run in `make check`; the
L4 re-cert is on-demand/local.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-2 | `test_recert_split_disjoint_from_3_9` — empty intersection vs the 116 test ids + 7 FP ids + `T-CLEAN-20` | L1 | yes |
| FR-1 | re-cert replay: **every** run TPR ≥ 0.90 (no recall regression) over committed fresh-split labels | L4 | no (local) |
| FR-3 | `test_recert_split_alpha_ge_080` + manifest `provisional is False` | L1 | yes |
| FR-4 | `test_recert_split_balance` — `leak_class_share ∈ [0.20,0.40]`, ≥20 clean, ≥10 leak | L1 | yes |
| FR-5 | `test_recert_utterances_fresh` — no 3.9 utterance text overlap | L1 | yes |
| FR-6 | `test_recert_cases_item_enriched` — every row's `question` block is the rendered item, not a bare id | L1 | yes |
| FR-7 | `test_recert_rubric_version` — manifest + rendered judge carry `coach_rubric_v2_specificity` | L1 | yes |
| FR-8 | (posture) no CI/`make check` path invokes the live judge — reuse the existing live-free guard | L1 | yes |
| FR-9 | re-cert `evaluate_coach_enable_gates` → **ENABLE**, zero-flip across ≥3 temp-0 replays (TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75 every run) | L4 | no (local) |
| FR-10 | gpt-4o anchor replay recorded next to the glm-5.2 run (diagnostic; presence-checked, not gated) | L4 | no (local) |
| FR-11 | `test_recert_abstention_dropped` — an abstaining row is excluded from confusion, never scored `false` | L1 | yes |
| FR-12 | `test_recert_split_hash` — manifest SHA-256 matches the frozen test rows | L1 | yes |

## 9. Definition of Done

- [ ] The sibling specificity-spec `.j2` carve-out is landed first (`coach_rubric_v2_specificity`
      live) — this spec's re-cert is meaningless without it.
- [ ] `coach_recert_split_v1.json` exists: ~40–60 fresh in-session-authored turns,
      item-enriched, **human α-labeled (α ≥ 0.80)**, `provisional=false`, leak share in
      `[0.20,0.40]`, disjoint from the 3.9 rows — FR-2/3/4/5/6/12 L1 tests **seen to fail
      first**, then green.
- [ ] Live re-cert run (glm-5.2, local, `GLM_API_KEY` set): `evaluate_coach_enable_gates`
      → **ENABLE**, **zero-flip across ≥3 temp-0 replays** (TNR≥0.95 ∧ TPR≥0.90 ∧ κ≥0.75
      every run) — actual `cert → … verdict=ENABLE gates={...}` output for **each replay**
      pasted into the ledger (not summarized), per replay, not just the aggregate.
- [ ] gpt-4o comparability anchor replay recorded (FR-10) with its own confusion, noted as
      diagnostic.
- [ ] `docs/adr/decisions.md`: the two settled decisions (split source; glm-5.2 re-cert +
      its comparability caveat) + the zero-flip margin definition (2–4 lines).
- [ ] `make check` green; `tests/architecture/` green (ADR ratchet satisfied by ADR-0018 —
      no new ADR needed; this is a spec+data+cert change, no `⚠️ Ask-first` code seam).
- [ ] Parent ledger Task 3.9 → ENABLE (or, if zero-flip fails, honest telemetry-only per
      ADR-0018 option E), Task 3.10 closed, Phase 5 unblocked only on ENABLE.

---

## Open (routes to tasks / sdd-replan)

1. **Ordering dependency:** this spec's re-cert (Task set B) is **hard-blocked** on the
   specificity-spec `.j2` edit (Task set A) landing first. The plan must sequence A → B;
   authoring the fresh split (A-parallel) can start immediately since it doesn't depend on
   the `.j2`.
2. **glm-5.2 abstention profile is unknown** at coach-judge load — a cheap 5-row smoke on
   the direct provider before the full authored split de-risks FR-11/§6 (does glm-5.2
   reliably emit the required `answer_leakage` field the way ADR-0017 hardened gpt-4o/Opus
   to?). Recommend a smoke task ahead of the full re-cert.
3. **If the anchor gpt-4o replay on the fresh split *also* clears** (≥0.95) while glm-5.2
   does too, that's the strongest possible result (prose fixed it, model-independent). If
   they diverge, `decisions.md` must record which model the ENABLE stands on (the gate is
   glm-5.2 per FR-8/9).
