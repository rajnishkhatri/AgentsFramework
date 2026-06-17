# Tier 1 results — TaskUnderstanding checklist length vs depth cap

**Status:** executed result note — **2026-06-17** · Tier 1 of [`planning_floor_outcome_validation.design.md`](planning_floor_outcome_validation.design.md) §3.
**Run:** `python scripts/diagnose_understanding_vs_depth.py --capture --samples 3` → 84 fast-tier `gpt-4o-mini` calls captured once to `cache/goaljudge_eval/planning_floor_understanding.jsonl` (28 depth-surface prompts × 3 samples). Re-score is free and deterministic: `python scripts/diagnose_understanding_vs_depth.py`.
**Question (design §0):** does the deterministic floor *under-budget steps* on the trap prompts — would firing L2 instead of L1 give the task the steps its real checklist needs?

**Bottom line (one line):** **Partial, qualified yes** — the three multi-marker prose traps stably need a 4-item checklist at an L1 cap of 3, demonstrated offline. But the signal is **softer than the design hoped**: an L0-cap caveat (below) shows checklist length over-counts steps by a constant, so this is *corroborating* evidence for the Option-A depth rule, **not** a clean causal proof. The expensive live A/B (Tier 2) remains the only thing that could turn "needs more checklist items" into "produces a better answer."

---

## 1. The headline finding

| trap (fired **L1**, cap 3) | checklist len ×3 samples | spread | verdict |
|----------------------------|--------------------------|--------|---------|
| `depth-l2-trap-1` "Audit the current deployment architecture, design a migration…" | `4, 4, 4` | 0 | **over cap** |
| `depth-l2-trap-2` "Redesign the ingestion pipeline, migrate the existing jobs…" | `4, 4, 4` | 0 | **over cap** |
| `depth-l2-trap-3` "Investigate the recurring OOM, design a memory-budget guard, and refactor…" | `4, 4, 4` | 0 | **over cap** |
| `depth-l2-trap-4` "Architect a multi-region failover story, design the data replication…" | `3, 3, 3` | 0 | **at cap** |

**3 of the 4** L2-under-promote traps return a checklist of **4 grounded conditions** when the floor budgeted **3** steps (L1). That is the floor giving the task fewer planning steps than its own success checklist enumerates — the under-budgeting the design set out to detect, shown without an agent run. The result is **rock-stable** (spread 0 across three independent samples), so it is a real property of these prompts, not LLM jitter.

This **strengthens the walkthrough's root-cause note**: multi-marker prose tops out at additive score 2 → fires `moderate-complexity-initial-task` (L1) → caps at 3 steps, while the task provably wants 4. It raises the ROI of the Option A `distinct_marker_count >= 3 -> L2` rule named in [`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) §7.

## 2. The honesty caveats (why this is *corroborating*, not *proof*)

### 2a. The L0 over-count — the signal over-reads by a constant

Grouping every captured checklist by its **fired** depth:

| fired depth (cap) | samples | min / median / max effective len | over-cap rate |
|-------------------|---------|-----------------------------------|---------------|
| **L0** (cap 1) | 16 | 2 / 3 / 3 | **100%** |
| **L1** (cap 3) | 45 | 2 / 3 / 5 | 47% |
| **L2** (cap 5) | 18 | 3 / 4 / 5 | 0% |

**Every L0 task is "over cap"** — "Print the current working directory" yields a 3-item checklist (the command is correct, the output names the directory, the path is accurate). That is *correct behavior* for TaskUnderstanding and *not* an under-planning bug: a one-action task still has two-to-three acceptance checks. **The cap is a planning-*step* budget; the checklist is an acceptance-*criteria* count** — they are not the same unit, and the checklist runs ~1–2 items richer than the step budget at every depth. So `checklist_len > cap` over-reads by a roughly constant offset. The trap finding survives this only because the traps clear the bar by the *same* margin the comparable correctly-fired L1 rows do **not** (`depth-l1-3/4`, `oracle-4/8` sit at 3), i.e. the traps are distinguishable *relative to* their L1 peers, not in absolute terms. That relative reading is the load-bearing part; the absolute `>cap` framing is the weak part.

### 2b. Three verdict flips — boundary jitter, honestly inconclusive

| row | lens | reading |
|-----|------|---------|
| `depth-l1-1` (lone-marker investigate, correctly L1) | `4, 3, 3` | straddles cap 3 |
| `count-fresh-2` (count-scope fresh, L1) | `4, 3, 3` | straddles cap 3 |
| `oracle-7` (lone-marker refactor, L1) | `4, 3, 3` | straddles cap 3 |

All three are **correctly-fired L1 rows** (not under-promotions) whose checklist length jitters across the cap boundary — one sample of 4, two of 3. The `--samples 3` variance guard (design VD-3) is what surfaced these; a single sample would have silently mislabeled them. They are **not** counted as under-budgeting. Their existence is the reason the headline is "qualified": the 4-vs-3 line that the traps clear is exactly the line ordinary L1 prompts wobble across, so the trap margin is *thin*.

### 2c. `depth-l2-trap-4` does not confirm

`depth-l2-trap-4` ("Architect a multi-region failover story…") stably returns **3** — exactly the L1 cap. Either the prompt is genuinely L1-sized (a `want_depth=L2` **corpus-label** question, not a floor failure), or TaskUnderstanding's 7-item ceiling is compressing a genuinely-large task. Tier 1 cannot distinguish these; recorded as a corpus-review item, not a floor verdict.

### 2d. One gate rejection

`depth-l0-trap-2` (long-path L0) was **gate-rejected** all three samples — the model produced conditions sharing no content token with the long absolute path, so the anti-hallucination grounding gate (correctly) rejected them. Excluded from the verdict; it is a TaskUnderstanding-grounding artifact, not a depth signal.

## 3. What this does and does not license

- **Does:** confirm offline that multi-marker prose traps (3/4) carry a checklist the L1 step-cap cannot cover, stably. This is real corroboration for an Option-A depth rule and lowers the urgency of a live A/B *for the existence of under-budgeting*.
- **Does not:** prove that firing L2 yields a *better answer*. Checklist length is an acceptance-criteria proxy, over-reads cap by a constant (§2a), and the trap margin is one item — the width of ordinary L1 jitter (§2b). Causal "deeper → better" still needs Tier 2.

**Recommendation (unchanged from design §5, now evidence-backed):** fold this into [`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) §7 as *supporting* evidence for Option A's depth rule, **and treat Tier 2 (live GoalJudge A/B) as still-required if a stakeholder needs causal proof** — Tier 1 raised confidence in *under-budgeting* but the §2 caveats keep it short of *outcome* proof. If Option A is built, these 3 stable traps + their L1 peers are the natural regression fixture.

---

*Reproduce:* re-score is offline/deterministic (`python scripts/diagnose_understanding_vs_depth.py`); re-**capture** spends 84 fast-tier calls and will produce different exact wording (LLM), but the §1/§2 structure is stable (traps 1–3 spread 0). Fixture: `cache/goaljudge_eval/planning_floor_understanding.jsonl`.
