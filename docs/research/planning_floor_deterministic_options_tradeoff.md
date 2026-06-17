# Deterministic planning floor — options trade-off & cost-benefit study

**Status:** research decision note — **2026-06-17**
**Scope:** Picks the *next* deterministic-only improvement to the L0/L1/L2 planning floor, and decides whether it is worth building. A **focused menu of three adoptable options + a do-nothing baseline**, each with a trade-off ledger and a cost-benefit cell, grounded in a fresh offline measurement and verified 2025–2026 external research. **Hard constraint: no LLM in routing or decomposition** — any LLM stays in the GoalJudge overlay, outside the floor.
**Companion to:** [`planning_depth_ontology_floor_research.md`](planning_depth_ontology_floor_research.md) — that note owns the *conceptual schema* (the mini-ontology in its §5, the rollout phases in its §7, the anti-patterns in its §9). **This note owns the decision**: which option, in which order, at what cost. It references the schema by section rather than re-printing it.
**Verdict (one line):** The L0-collapse problem is **already fixed** (Phase 0); the residual failure is **L2 under-promotion on multi-marker prose** (1/12 offline). The highest-ROI next step is **Option C (evidence checker)** — the only option that adds a *new capability* rather than re-notating existing rules — built shadow-first; Options A/B are maintainability refactors worth doing later, not now.

Protocol IDs (L0/L1/L2 depth, T0–T3 tiers, OBP/LP layering) are defined in [`planning_pipeline_tiered_loops.design.md`](../plans/planning_pipeline_tiered_loops.design.md) §A Protocol Registry.

---

## 1. Context & scope

The shipped floor is two deterministic stages, both LLM-free:

| Stage | Module | Mechanism |
|-------|--------|-----------|
| Depth (L0/L1/L2) | [`components/router.py:97`](../../components/router.py) `select_planning_depth` | Additive lexical score + L1 rescue floors + L2 incident promotion; per-task `task_tool_results_count` scoping (GJ-012 fix) |
| Decomposition | [`components/plan_builder.py`](../../components/plan_builder.py) `_extract_branches` / `derive_success_conditions` / `validate_plan_mece` | 4-tier regex split; caps L0=1/L1=3/L2=5; ≤6 conditions + generic tail; MECE structure gate |

Replan rebuilds **deterministically** ([`react_loop.py:862`](../../orchestration/react_loop.py), via `build_plan_artifact`); `build_plan_artifact_llm` always falls back to the floor. Consumers: `synthesis_validator` (L1/L2 gates), `evaluate_task_outcome` (keyword overlap), GoalJudge overlay (CORRUPT-SUCCESS).

**This is not a bug hunt.** Phase 0–3 shipped and were live-validated (`planning_pipeline_tiered_loops.plan.md` §8.1: depth 0.917, replan 0.900, escalation precision 1.000). The question is purely: *what is the next deterministic increment, and is it worth the cost?*

The companion note surveyed an ontology upgrade path but left three gaps that block a decision — no quantified current baseline, no option-vs-option trade-off, no cost-benefit. This note fills all three.

---

## 2. Current-state measurement

### 2.1 The collapse is fixed — residual is *systematic* under-promotion, not collapse

The first baseline was a 12-row, depth-only probe (`diagnose_planning_strata.py`). It has since been **superseded** by a coverage-matrix-driven, **multi-surface** corpus — `cache/goaljudge_eval/planning_floor_strata.jsonl` (59 rows, built by `scripts/build_planning_floor_corpus.py`) — that stresses all five floor surfaces, not just depth. Fresh offline run, **2026-06-17**, `python scripts/diagnose_planning_floor.py` (pure, no LLM, no network, no deploy):

```
## per-surface scorecard
  depth        27/31  ( 87.1%)
  branches     11/11  (100.0%)
  conditions    4/4   (100.0%)
  mece          5/5   (100.0%)
  replan        8/8   (100.0%)
  OVERALL      55/59  ( 93.2%)
## DIVERGENCES (4) — all family=l2-under-promote (multi-marker prose -> capped L1)
```

**Trajectory:**

| When | Metric | Source |
|------|--------|--------|
| Pre-Phase-0 | **14 of 17** depth rows collapsed to **L0** (systemic) | `planning_pipeline_tiered_loops.plan.md` §2 |
| Post-Phase-0 (depth-only, 12 rows) | 11/12 = 92%, zero L0 collapse | `diagnose_planning_strata.py` (superseded) |
| **Post-Phase-0 (multi-surface, 59 rows, 2026-06-17)** | **OVERALL 55/59 = 93.2%**; branches/conditions/mece/replan all **100%**; depth **27/31 = 87.1%**; **all 4 misses are the same family** (L2 under-promotion); **zero L0 collapse** | `diagnose_planning_floor.py` (this run) |
| Post-fix (live) | depth **0.917** | `plan.md` §8.1 |

The multi-surface run **sharpens the earlier finding**: where the 12-row probe showed the L2→L1 miss as a single row (could have been noise), the 59-row corpus seeds **four** multi-marker prose variants (`audit+design+refactor`, `redesign+migrate+refactor`, `investigate+design+refactor`, `architecture+design+migrate`) and **all four** cap at L1 (`moderate-complexity-initial-task`). The under-promotion is **systematic, not incidental** — it is the single coherent residual failure mode of the depth surface. The other four surfaces are clean on the designed corpus.

> **Integrity note.** Ground-truth `want_*` values were authored from intent, then checked against actual `got_*`; divergences are printed, never silently matched. One authored expectation (`branch-enum-1`, want=3) was found wrong on review — the extractor correctly treats the lead-in clause "Do the rollout in order:" as its own branch (4 total) — and was corrected to match the *right* intent, with a separate pure-enum row added. That correction is why this is a baseline, not a snapshot.

### 2.2 What this means for the options

Any proposed improvement must be judged against a floor that is **93.2% overall / 0.917 live**, with three of four non-depth surfaces at 100% on the designed corpus. The only coherent residual is **L2 under-promotion on multi-marker prose** — a depth false-negative, not a collapse, and the *only* thing a depth-axis option (A/B) could move. This reframes the cost-benefit sharply: a large re-architecture to recover one prose-shaped boundary is poor ROI; a cheap, shadow-only capability that closes a *different* gap (evidence, not depth) is better value.

### 2.3 The oracle is now large enough to characterize — but not yet to validate a rule engine

The depth oracle was 11 rows; the new multi-surface corpus is **59 rows across five surfaces** with seeded adversarial traps (L2-under-promote ×4, long-path-L0 ×2, path-safe ×2, noun-phrase ×2). This is enough to **characterize a baseline** and regression-guard all five surfaces. It is **still not** a validation set for a multi-feature rule engine (Option A would want ≥9 features × ~7 task classes, plus independent — not trap-tuned — rows). **Growing toward ~80–100 rows with held-out cases remains a precondition before *consuming* any A/B rule engine**; the current 59 are the right size to *measure against* now. (Same discipline as the T3 fan-out corpus, `t3_fanout_corpus.plan.md`.)

---

## 3. The options menu

Deterministic-only. Each maps to a section of the companion note's conceptual schema.

| # | Option | What changes | Schema ref | New capability? |
|---|--------|--------------|-----------|-----------------|
| **0** | **Do nothing** — keep the lexical scorer | nothing | — | no (null hypothesis) |
| **A** | **Feature-vector rule table** — `extract_task_features()` + ordered rules with a `rationale:` field, replacing the additive score | companion §5 `depth_rules`, §6 L0 layer | **mostly no** — ~80% re-notation of rules already in `router.py:116-227` |
| **B** | **Verb/task-class taxonomy** — frozen `verb_class_map.json` replaces the growing substring marker lists | companion §5.3, §6 L1 layer | partial — same triggers, cleaner source |
| **C** | **Evidence checker** — `check_expected_evidence(plan, tool_results)`: expected vs observed *evidence type* per subtask, shadow-first | companion §4.5, §7 Phase D | **yes** — the only option that closes a gap the floor cannot reach today |
| — | *Rejected controls* | Full OWL/SHACL reasoner; HTN-heavy method libraries; any LLM-in-floor | companion §9 | see §6.3 |

**Honest framing (carried from the critical review of the companion note):** Option A's `depth_rules` — `post-tool-synthesis`, `incident-diagnosis`, `strong-intent-verb` — are the *exact* rules already living as well-commented `if` statements in `router.py`. Porting them to YAML is a **maintainability change, not a capability change**; its one genuinely new signal is evidence-type counting (`multi-evidence-composite`). The doc must not sell a re-notation as an "ontology upgrade."

---

## 4. Trade-off ledger

Rated against the **current** (fixed, 0.917) floor — not the broken one.

| Axis | 0 · Do nothing | A · Feature table | B · Verb taxonomy | C · Evidence checker |
|------|----------------|-------------------|-------------------|----------------------|
| **Recognition lift** (depth accuracy) | — (92% / 0.917) | low — recovers the L2→L1 miss *if* a `multi-evidence` rule is added; else neutral | low — same triggers, fewer edge cases | **none** (different axis — see below) |
| **False-promote risk** | known/bounded | medium — a rule table can over-fire if features are coarse; needs the grown oracle | low | n/a (read-only shadow) |
| **Surface-form robustness** | brittle (regex/substring) | same | **better** — verb classes generalize over lemmas | n/a |
| **Evidence-awareness** | **none** — conditions are branch text, not evidence types | none | none | **yes** — distinguishes file / shell / live-API evidence (closes the §3 "Depth ≠ evidence" failure) |
| **Reproducibility / L1 CI** | full | full (pure data) | full | full (pure function) |
| **Layer cleanliness (LP/OBP)** | clean | clean (component data) | clean | clean (pure component, shadow carrier) |
| **Explainability** | rule-name only | **rule-id + matched features** | + verb class | + per-subtask met/unmet evidence verdict |

**Read of the ledger:** A and B compete on the *depth* axis where the floor is already strong (low lift, real regression risk). C operates on a *different* axis (evidence) where the floor scores **zero today** and where GoalJudge's CORRUPT-SUCCESS check currently has no deterministic counterpart. C is the only option whose benefit is not bounded by the 92%/0.917 ceiling.

---

## 5. Cost-benefit study

Effort in rough engineer-days (S ≤2d, M 3–5d, L >5d). Latency anchored to published deterministic-vs-LLM numbers (§6.4).

| Option | Eng. effort | Runtime latency | Maintenance | Oracle/test cost | Rollout risk | Expected benefit |
|--------|-------------|-----------------|-------------|------------------|--------------|------------------|
| **0 · Do nothing** | 0 | ~0 (already deterministic, μs–ms) | status quo (regex sprawl at its limit) | 0 | none | none — accepts the 1/12 L2 miss + no evidence axis |
| **A · Feature table** | **M** (incl. grow oracle to ~30–40 rows) | ~same (still deterministic, <10ms; cf. ~2–5ms parser vs ~3,447ms LLM, §6.4) | **lower long-run** (add a rule row, not a regex edge case) | **M** — oracle must grow *before* cutover or parity is meaningless | **medium** — behavior-neutral port + 1 new rule; risk is silent regression vs the 0.917 baseline | low depth lift + big maintainability win |
| **B · Verb taxonomy** | **S–M** | ~same | lower (frozen JSON vs growing substring lists) | S (reuse grown oracle) | low | robustness on paraphrase; small |
| **C · Evidence checker** | **M–L** | **+1 pure pass over `tool_results` (<10ms, no LLM)** | new module + per-subtask evidence templates | M (new shadow assertions; no judge calibration needed initially) | **low** — shadow-only first, gates nothing until proven | **high** — first deterministic evidence-aware signal; complements GoalJudge CORRUPT-SUCCESS; published soundness pattern (§6.1) |

**The cost asymmetry that decides it:** Options A/B spend M-level effort (most of it on growing the oracle) to chase a low, capped depth lift. Option C spends comparable effort to add a capability that does not exist anywhere in the deterministic floor today, ships **shadow-only** (so rollout risk is near-zero — it gates nothing until it earns trust, mirroring the GoalJudge `deterministic → shadow → consume` discipline), and has an external **soundness proof** behind its mechanism (ChatHTN verifier task, §6.1).

**The "do nothing" case is real.** At 0.917 live with the collapse fixed, the floor may simply be good enough; the honest baseline cost of every other option is the opportunity cost of not spending those days on the still-unbuilt T3 nodes or the open governance-trace acceptance gate (`plan.md` §8). This note recommends C *because* it adds a new axis cheaply and safely — not because the floor is failing.

---

## 6. External research (verified 2026-06-17)

### 6.1 ChatHTN — the soundness pattern behind Option C

Munoz-Avila, Aha & Rizzo, *ChatHTN: Interleaving Approximate (LLM) and Symbolic HTN Planning*, NeuS 2025 ([arXiv 2505.11814](https://arxiv.org/abs/2505.11814)). The system is **provably sound** — "any plan it generates correctly achieves the input tasks" — via a **verifier task**: after any decomposition, append a no-effect primitive whose preconditions equal the compound task's *expected effects*; if they don't hold in the resulting state, the plan is rejected. **The deterministic-only subset** is everything *except* the LLM decomposition fallback: method-precondition checks, state transitions, and **verifier validation** are all symbolic. Option C is exactly this verifier, applied to observed `tool_results` instead of a simulated state.

### 6.2 Planning Ontology — feature→capability routing (Option A)

[ai4society Planning Ontology](https://ai4society.github.io/planning-ontology/) (CODS 2024; live). Core insight reused by Option A: *don't score raw text — extract structured features, then route by feature→capability rules*, with SPARQL-style explanations. Supports the rule-table form but not a full reasoner (see §6.3).

### 6.3 SHACL-with-ontologies is EXPTIME-complete — why the formal path is rejected

Oudshoorn, Ortiz & Simkus, *SHACL Validation in the Presence of Ontologies* (*Artificial Intelligence* vol. 352, 2026; [arXiv 2507.12286](https://arxiv.org/abs/2507.12286)). Result: "even very simple ontologies make the problem **EXPTIME-complete**, and PTIME-complete in data complexity." The blow-up is in **ontology/shape size**, not data — exactly the dimension a growing plan-shape library would expand. This is the cost argument for the companion note's OD-2 default (**in-repo Pydantic shapes, not pySHACL/OWL**) and for keeping the rule engine fixed-parameter tractable (companion §4.7). Full OWL/SHACL on every route is a **rejected control**.

### 6.4 Deterministic parsing cost — why "stay deterministic" is the cheap option

Non-LLM intent classifiers run **~2–5ms at $0 marginal cost** vs **~3,447ms for a zero-shot LLM (~700× latency)**, with higher accuracy on bounded label sets ([Voiceflow hybrid-classification benchmark](https://www.voiceflow.com/pathways/benchmarking-hybrid-llm-classification-systems)). This quantifies the floor's existing advantage: every option in §3 keeps routing in the μs–ms, $0 regime. The latency/cost column in §5 is anchored here.

> **Citation hygiene:** the companion note's §11 carries four 2025/2026 external cites (NSVIF, NeurIPS embodied planning, HVR, an "agentic KG" tutorial) that were *not* re-verified here and should be treated as **conceptual analogies, not adopted systems** — none of the options above use SHACL, OWL, VerbNet, or FrameNet as dependencies. The four references in this §6 were each fetched and confirmed on 2026-06-17.

---

## 7. Recommendation & rollout

**Recommended order — by ROI, not by the companion note's A→B→C→D:**

1. **C (evidence checker) first** — the only new capability; shadow-only; gates nothing; near-zero rollout risk; soundness-backed. Closes the "Depth ≠ evidence" failure the depth options cannot touch.
2. **A (feature table) as a refactor** — when regex maintenance pain justifies it; framed honestly as behavior-neutral re-notation + the one `multi-evidence` rule that recovers the L2→L1 miss.
3. **B (verb taxonomy) as cleanup** — folds into A's feature extraction.
4. **0 (do nothing) is a legitimate outcome** — if the team prefers to spend the days on the unbuilt T3 nodes or the open governance-trace gate, the 0.917 floor is defensible as-is.

**Tier 1 validation evidence (added 2026-06-17, [`planning_floor_outcome_validation.tier1_results.md`](planning_floor_outcome_validation.tier1_results.md)).** An offline TaskUnderstanding-vs-cap probe (84 fast-tier calls, captured once) found **3 of the 4** multi-marker prose traps stably return a **4-item** success checklist while the floor budgets only **3** steps (L1) — *corroborating* the §2.1 systematic under-promotion and raising Option A's `multi-evidence`/`distinct_marker_count>=3 -> L2` ROI. **Caveat that keeps this from being decisive:** checklist length over-reads the step cap by a roughly constant offset (every L0 task is "over cap" too — an acceptance-criteria count is not a planning-step budget), and the trap margin is one item — the width of ordinary L1 sample jitter. So this lifts confidence in *under-budgeting* but is **not** causal "deeper → better answer" proof; that still needs the live A/B (Tier 2).

**Hard preconditions for any of A/B/C:**
- **Grow the oracle to ~30–40 dimensioned rows first** (§2.3) — otherwise parity testing is meaningless.
- **Shadow-first, oracle-parity-gated** — same `deterministic → shadow → consume` rollout as GoalJudge/TaskUnderstanding (companion §7).
- **Preserve the inline rationale** — when porting rules to data, carry a `rationale:` field so the load-bearing comments in `router.py:158-167` (the comma-then-and gating logic) are not lost.

---

## 8. Open decisions (carried from companion §12, pruned to the real ones)

| ID | Question | Recommendation |
|----|----------|----------------|
| **OD-1** | Ontology data location — `components/` JSON vs `trust/` types? | Types in `trust/`, rule tables in `components/`/`config/`. |
| **OD-3** | Evidence checker — gate or shadow-only? | **Shadow-only** until calibration confirms lift (this is what makes Option C low-risk). |
| **OD-5** *(new)* | Build any of A/B/C now, or defer to T3 / governance-trace work? | **Defer A/B; consider C** — C is the only positive-ROI option, and only if the oracle is grown first. |
| **OD-6** *(new)* | Run Tier 2 (live GoalJudge A/B) now that Tier 1 is done? | **Defer** — Tier 1 corroborated under-budgeting (3/4 traps) but its §2 caveats keep it short of causal proof; only escalate to Tier 2 if a stakeholder needs "deeper → better answer" end-to-end, and only after the `PLANNING_DEPTH_FORCE` hook + token budget are approved. |

*(Companion OD-2 and OD-4 are resolved: OD-2 → in-repo Pydantic, per §6.3 EXPTIME; OD-4 → manual curated map, FrameNet dump deferred.)*

---

## 9. References

### Internal

| Resource | Path |
|----------|------|
| Conceptual schema (companion) | [`planning_depth_ontology_floor_research.md`](planning_depth_ontology_floor_research.md) |
| Depth selection | [`components/router.py`](../../components/router.py) |
| Plan builder / floor | [`components/plan_builder.py`](../../components/plan_builder.py) |
| Offline diagnostic (baseline source) | [`scripts/diagnose_planning_strata.py`](../../scripts/diagnose_planning_strata.py) |
| Depth oracle (11 rows) | [`cache/goaljudge_eval/depth_strata_rich.jsonl`](../../cache/goaljudge_eval/depth_strata_rich.jsonl) |
| Recorded live metrics (0.917 / 14-of-17) | [`planning_pipeline_tiered_loops.plan.md`](../plans/planning_pipeline_tiered_loops.plan.md) §2, §8.1 |
| Protocol registry (L0–L2, T0–T3, OBP) | [`planning_pipeline_tiered_loops.design.md`](../plans/planning_pipeline_tiered_loops.design.md) §A |

### External (each fetched & verified 2026-06-17)

| Topic | Reference |
|-------|-----------|
| Verifier-task soundness (Option C) | Munoz-Avila, Aha, Rizzo — ChatHTN, NeuS 2025 — [arXiv 2505.11814](https://arxiv.org/abs/2505.11814) |
| Feature→capability routing (Option A) | [Planning Ontology, ai4society](https://ai4society.github.io/planning-ontology/) |
| OWL/SHACL EXPTIME cost (reject rationale) | Oudshoorn, Ortiz, Simkus — *Artificial Intelligence* 352 (2026) — [arXiv 2507.12286](https://arxiv.org/abs/2507.12286) |
| Deterministic-vs-LLM cost/latency | [Voiceflow hybrid-classification benchmark](https://www.voiceflow.com/pathways/benchmarking-hybrid-llm-classification-systems) |

---

*Decision artifact only. No implementation is implied until a plan/issue references a specific option above. The deterministic-only constraint is non-negotiable for the floor; LLM use is confined to the GoalJudge overlay.*
