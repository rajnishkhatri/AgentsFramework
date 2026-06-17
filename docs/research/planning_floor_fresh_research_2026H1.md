# Fresh research scan — deterministic planning floor (2026 H1)

**Status:** research-refresh note — **2026-06-17**. New external evidence (all Q1/Q2 2026, each fetched & dated below) re-examined against the deterministic L0/L1/L2 floor.
**Why:** the prior anchors ([`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) §6) were ChatHTN (NeuS 2025) + the SHACL-EXPTIME result (2026). This scan asks: has anything *newer* changed the call — the "no LLM in the floor" constraint, the depth-vs-evidence priority, or the do-nothing baseline?
**Companions:** [`planning_depth_ontology_floor_research.md`](planning_depth_ontology_floor_research.md) (schema), [`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) (decision), [`planning_floor_outcome_validation.tier1_results.md`](planning_floor_outcome_validation.tier1_results.md) (Tier 1 evidence).

**Bottom line (one line):** the 2026 literature **strengthens, not overturns** the current design — deterministic-control-plane-with-LLM-only-on-escalation is now an explicitly-benchmarked best practice (93% LLM-call reduction), and "don't generate a plan per query" is independently confirmed (83% token cut, 0.6% loss). The one genuine tension: the strongest *verifiers* and *routers* shipping in 2026 are **learned**, which prices our hard determinism constraint honestly — it costs some ceiling, bought with reproducibility/auditability.

---

## 1. What changed the picture (load-bearing finds)

### 1.1 Deterministic control-plane, LLM only on no-path — now benchmarked (93%)
**Graph-Based Self-Healing Tool Routing for Cost-Efficient LLM Agents**, [arXiv 2603.01548](https://arxiv.org/abs/2603.01548) (2 Mar 2026). A **cost-weighted tool graph with Dijkstra shortest-path** does routing deterministically; on tool failure, edges are reweighted to ∞ and the path recomputed; **the LLM is invoked only when no feasible path exists** (goal demotion / escalation). Result: **93% fewer control-plane LLM calls (9 vs 123)** across 19 scenarios at ReAct-equivalent correctness, plus *"binary observability — every failure is either a logged reroute or an explicit escalation, never a silent skip."*

> **Why it matters here.** This is the closest external mirror yet of our architecture: a **deterministic floor** that decides routing/depth, with the **LLM reserved for the escalation edge** (our HYBRID cascade — LLM override on the ESCALATION edge, not at entry). It is dated, benchmarked, and quantifies the prize (fewer LLM calls + auditability) we were asserting on principle. The "binary observability, never a silent skip" line is independent corroboration of the open **governance-trace** workstream — the floor's value is partly that every decision is a logged, explainable artifact.

### 1.2 "Don't plan per-query" — independently confirmed (83% token cut)
**Do We Always Need Query-Level Workflows? (SCALE)**, [arXiv 2601.11147](https://arxiv.org/abs/2601.11147) (16 Jan 2026). Argues a **small set of reusable task-level workflows** covers as many queries as bespoke per-query workflow generation, validated by *self-prediction with few-shot calibration* instead of full execution. **83% token reduction, 0.61% average performance degradation.**

> **Why it matters here.** This is empirical backing for the floor's core bet: **a cheap, upfront, reusable depth/shape decision beats generating a fresh plan for every request.** It also independently lands on the same instinct as our Tier 1 design — *predict/calibrate offline rather than execute to measure.* Reinforces the **do-nothing-is-legitimate** baseline: the marginal value of a richer floor is bounded when a coarse reusable one already covers most traffic.

### 1.3 The dual-signal router is SOTA — but its structural half is *learned*
**CASTER: Context-Aware Strategy for Task Efficient Routing**, [arXiv 2601.19793](https://arxiv.org/abs/2601.19793) (27 Jan 2026). A **"Dual-Signal Router combining semantic embeddings with structural meta-features to estimate task difficulty"**; **72.4% cost reduction** at equal success, **beating heuristic routing and FrugalGPT** across SWE/data/science/security. Self-optimizes via on-policy negative feedback (learned).

> **Why it matters here.** The **structural-meta-features** half is *exactly* our Phase A feature vector (`subtask_count_est`, enumeration, verb class, …). So the feature-table direction is live SOTA, **vindicating Phase A's shape**. The honest catch: CASTER's edge comes from (a) a *semantic-embedding* signal and (b) *learning from its own failures* — both **outside our deterministic constraint**. It "beats heuristic routing," and our floor *is* heuristic routing. This prices the constraint: pure-deterministic leaves measurable cost-routing gains on the table that a small learned/embedding signal would capture. It does **not** argue for an LLM *in* the floor — it argues an embedding/feedback signal *alongside* it is where the frontier is.

### 1.4 The strongest plan verifier is learned (GNN), beating rule-based AND LLM verifiers
**GNNVerifier: Graph-based Verifier for LLM Task Planning**, [arXiv 2603.14730](https://arxiv.org/abs/2603.14730) (18 Mar 2026). Treats a plan as a task-dependency graph; a **trained GNN** checks prerequisites/ordering/dependency consistency (expected transitions vs proposed structure). **Beats rule-based and LLM-based verifiers** on verification accuracy and lifts downstream success.

> **Why it matters here.** This is the ceiling for our **Phase D / Option C deterministic evidence checker**. A learned verifier wins on accuracy — so a *rule-based* evidence checker should be sold on **soundness + auditability + zero-train-cost + shadow-safety**, not raw accuracy. It also validates the *structure*: verify a plan as expected-vs-observed over a dependency graph (our `check_expected_evidence(plan, tool_results)`), just with rules instead of a GNN. Keeps the ChatHTN verifier-task pattern current.

### 1.5 Failure taxonomy puts the numbers on "where the floor earns its keep"
**MAST — Multi-Agent System Failure Taxonomy** (Cemri et al., NeurIPS 2025; widely applied through 2026; 1,600+ traces). 14 modes in 3 buckets: **Specification & System Design 41.8%** (includes *poor task decomposition*), Inter-Agent Misalignment 36.9%, **Task Verification & Termination 21.3%**.

> **Why it matters here.** Two of the three biggest buckets are *exactly* the floor's two axes: **decomposition** (depth/branching — the Spec/Design bucket) and **verification** (the evidence axis — Phase D). It quantifies the priority our Tier 1 reached qualitatively: depth errors are real and costly (largest bucket), and the *verification* axis (21.3%) is a distinct, large, separately-addressable failure class — the one our floor scores zero on today. (MAST is multi-agent-scoped; decomposition + verification modes transfer to single-agent; the inter-agent bucket does not — consistent with our single-supervisor scope.)

---

## 2. What did NOT change (constraint holds)

- **No 2026 result argues for an LLM inside the routing/decomposition floor.** Every cost win above comes from *removing* LLM calls from the control plane (1.1) or *predicting instead of executing* (1.2). The LLM stays at the escalation edge / overlay — our existing stance.
- **The SHACL/OWL EXPTIME rejection still stands** ([arXiv 2507.12286], cited prior). Nothing new revives a heavyweight formal reasoner on the hot path; in-repo Pydantic shapes remain right.
- **ChatHTN verifier-task soundness** ([arXiv 2505.11814]) remains the soundness pattern for Phase D; GNNVerifier (1.4) is the learned alternative we deliberately decline.

---

## 3. Net effect on the recommendations

| Prior recommendation | Fresh-research effect | Revised stance |
|----------------------|----------------------|----------------|
| **Deterministic floor, LLM only on escalation** | **Strengthened** — benchmarked at 93% fewer LLM calls + binary observability (1.1) | Keep; cite 2603.01548 as the dated external precedent in the architecture/governance docs. |
| **Phase D (evidence checker) first** | **Strengthened** — verification is its own 21.3% MAST bucket (1.5); learned verifiers win accuracy but a rule checker wins soundness/audit/shadow-safety (1.4) | Keep Phase D as first build; sell it on soundness+auditability, not accuracy parity with a GNN. |
| **Phase A depth rule = refactor-when-justified** | **Mixed** — structural meta-features are live SOTA (1.3, vindicates the shape) BUT the SOTA edge needs an embedding/feedback signal we won't add | Keep demoted. If depth ROI is ever pursued *beyond* parity, the frontier move is a **shadow embedding/feedback signal alongside** the rules (explicitly outside the floor), not a richer rule table. |
| **Do-nothing on depth is legitimate** | **Strengthened** — reusable coarse routing covers most traffic at 83% token savings (1.2) | Keep; the bar for "a richer floor pays" is now externally quantified as high. |
| **No LLM in the floor (hard constraint)** | **Priced honestly** — costs some cost-routing/verification ceiling vs learned SOTA (1.3, 1.4) | Keep the constraint, but record the *measured* trade: we trade a bounded accuracy/cost-efficiency ceiling for reproducibility, auditability, zero training, and shadow-safety. |

**One genuinely new idea worth logging (not a recommendation yet):** SCALE's *calibrated self-prediction instead of execution* (1.2) is methodologically the same move as our Tier 1 (predict under-budgeting offline rather than run an A/B). If Tier 2 is ever greenlit, a SCALE-style calibrated predictor could be a *cheaper* third option between Tier 1 (offline proxy) and Tier 2 (full live A/B).

---

## 4. References (each fetched & dated 2026-06-17)

| Topic | Reference | Date |
|-------|-----------|------|
| Deterministic graph routing, LLM-on-no-path, 93% call cut, binary observability | [arXiv 2603.01548](https://arxiv.org/abs/2603.01548) | 2 Mar 2026 |
| Task-level vs query-level workflows; 83% tokens / 0.61% loss; predict-not-execute | [arXiv 2601.11147](https://arxiv.org/abs/2601.11147) (SCALE) | 16 Jan 2026 |
| Dual-signal router (semantic + structural meta-features), 72.4% cost, beats heuristic/FrugalGPT (learned) | [arXiv 2601.19793](https://arxiv.org/abs/2601.19793) (CASTER) | 27 Jan 2026 |
| Learned GNN plan verifier beats rule-based + LLM verifiers (ceiling for Phase D) | [arXiv 2603.14730](https://arxiv.org/abs/2603.14730) (GNNVerifier) | 18 Mar 2026 |
| Failure taxonomy: decomposition (41.8% bucket) + verification (21.3%) are the floor's two axes | MAST, Cemri et al., NeurIPS 2025 | 2025, applied 2026 |
| (carried) Verifier-task soundness | [arXiv 2505.11814](https://arxiv.org/abs/2505.11814) (ChatHTN) | NeuS 2025 |
| (carried) SHACL+ontology EXPTIME → reject OWL/SHACL on hot path | [arXiv 2507.12286](https://arxiv.org/abs/2507.12286) | 2026 |

**Citation hygiene:** GNNVerifier, CASTER, SCALE, and 2603.01548 abstracts were fetched & dated 2026-06-17; MAST figures are from secondary 2026 summaries of the NeurIPS 2025 paper (not re-derived from the 1,600-trace dataset). One robotics symbolic-verification paper (MDPI MLKE 8(1):22) was relevant but returned HTTP 403 — not cited rather than cited unseen.

---

*Research only. No implementation implied. Feeds the recommendation revisions in the two companion notes' §7.*
