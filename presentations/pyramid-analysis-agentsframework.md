# Pyramid Analysis — AgentsFramework for the Open-Source Developer Audience

*Produced per `research/pyramid_react_system_prompt.md` (4-phase loop, MECE enforcement, 8-check validation). Evidence gathered by static exploration of the repo on 2026-06-11. This pyramid's Governing Thought is the SCQA Answer for deck v3.*

---

## Problem Definition

- **Original statement:** Create a pitch for developers who might use the repo, learn the concepts, and star it.
- **Restated question:** *Why should a developer adopt, learn from, or star AgentsFramework — what does it deliver that agent frameworks and tutorials do not, and is each claim verifiable in the repository?*
- **Problem type:** Evaluation
- **Scope:** The repo's verifiable contents as of 2026-06-11. Out of scope: comparisons requiring benchmarks of other frameworks, popularity predictions.
- **Success criteria:** Every evidence item carries a file path; the governing thought survives the Remove-One test.

---

## Governing Thought

> **Star and clone this repo because it open-sources the four things agent demos always leave out — a fine-tuned, eval-gated guardrail stack; a calibrated goal-judge evaluation pipeline with measured human agreement; policy-gated cloud deployment that idles at ~$0; and 40+ recipes that teach you to rebuild every piece — with each claim checkable in the code, and $0 in API keys needed for web search or CI.**

Confidence: **0.84** (strong evidence in all four branches; reduced for the license gap and unverifiable runtime claims — see Gaps).

---

## Issue Tree (ordering: degree — most differentiating first)

```
Root: Why adopt / learn from / star this repo?
├── B1: Security subsystems   — "guardrails" beyond a regex?
├── B2: Evaluation science    — are the evals real or vibes?
├── B3: Operability & cost    — can I actually run this without a bill?
└── B4: Learning scaffolding  — can I learn to build it myself?
```

Classification conventions: guardrail-related ML → B1; goal-judge-related ML → B2; SearXNG → B3 (cost-of-running); test/architecture discipline → B4 (it exists to be learned from). All four hypotheses **confirmed**.

---

## Key Argument 1 — Security: a guardrail stack with an actual trained model and frozen eval gates (dimension: security · confidence 0.9)

| # | Evidence | Source |
|---|---|---|
| 1.1 | Input rail is a 3-stage cascade: deterministic precheck (length 12K cap, regex, base64 decode, Shannon-entropy token detection) → fine-tuned ONNX classifier (reject ≥0.80, accept ≤0.20, else defer) → narrow LLM judge | `services/guardrails.py`, `services/governance/injection_classifier.py` |
| 1.2 | The classifier is a fine-tuned **DeBERTa-v3** (`protectai/deberta-v3-base-prompt-injection-v2`) trained with **PIGuard MOF** (ACL 2025) auxiliary loss against over-defense, exported as INT8-quantized ONNX (~184MB) | `scripts/train_injection_classifier.py` (epochs=3, AdamW lr=2e-5, mof_weight=0.5) |
| 1.3 | CI gate freezes three axes: malicious recall **≥ 0.95** (hard floor), FPR **< 2%** (hard ceiling; Llama-Guard-3 ≈ 4% is the stated comparison), NotInject over-defense accuracy reported | `tests/services/test_guardrail_classifier.py` |
| 1.4 | A **contamination guard** blocks NotInject rows from the train split at row and collection level (`ContaminationError`) — defends against the SafeGuard-style 99.38% inflated-accuracy bug | `services/governance/guardrail_dataset.py` |
| 1.5 | Dataset pipeline is a 6-stage deterministic generator (seed → preprocess → dedup → augment hard-negatives → optional teacher-label → freeze JSONL); frozen eval set of 28 held-out samples | `scripts/generate_guardrail_dataset.py`, `tests/services/fixtures/guardrail_evalset.jsonl` |
| 1.6 | Graceful degrade: missing ONNX artifact or extra → falls back to precheck + judge, never raises; a hand-weighted 8-token smoke ONNX model keeps the real inference path tested in CI | `InjectionClassifier.maybe_load()`, `build_smoke_artifact()` |
| 1.7 | Governance completes the story: SHA-256-chained black-box `trace.jsonl`, signed agent-facts registry (HMAC, GCS-backed, versioned bucket, runtime read-only) | `services/governance/`, `services/governance/agent_facts_gcs_registry.py` |

**So-what chain:** real trained model + frozen gates → guardrails are measurable, not vibes → a developer can copy a production-credible input rail instead of a regex → supports GT ("things demos leave out, checkable in code").

---

## Key Argument 2 — Evaluation: a goal judge built like a research project, with human-agreement receipts (dimension: evaluation rigor · confidence 0.85)

| # | Evidence | Source |
|---|---|---|
| 2.1 | `GoalJudge` is **reference-free and evidence-grounded**: verdicts must cite the tool trajectory, not the agent's narration ("the detective refuses to trust the confession") | `components/goal_judge.py` (221 lines), `prompts/goal_judge_system_prompt.j2` |
| 2.2 | Failure taxonomy of **16 codes in 5 axes** (semantic, corrupt-success, error-handling, feasibility, process quality) derived via grounded-theory open/axial coding | `components/schemas.py` `GOAL_FAILURE_MODES`, `docs/recipes/goaljudge/` |
| 2.3 | Full 7-stage methodology documented as a reusable skill: trace collection → open coding (≥100 traces) → axial coding (IAA ≥ 0.80) → synthetic data → rubric → gold set (~250 items, α ≥ 0.8) → calibration → CUSUM monitoring; 25-reference bibliography | `.cursor/skills/llm-eval-grounded-theory/` (372-line SKILL.md) |
| 2.4 | **Measured human agreement:** Stage 4 rubric IAA **κ = 1.0** (5 anchors, two blind annotators, 2026-06-09); Stage 5 pilot gold set **α = 0.8846** (43 items); 101-row combined sheet shipped as v0.9 | `docs/IAA/goalJudge/README.md`, `docs/IAA/goalJudge/goldset/` |
| 2.5 | **Red-teamed for CoT-gaming:** 6 fabricated-progress cases + 7 synthetic stress cases; flip-rate gates 5% hard / 10% soft; offline pins keep evidence-grounding rules in the prompt under CI | `tests/components/test_goal_judge_redteam*.py`, `test_goal_judge_stress*.py` (62 goal-judge tests across 6 files) |
| 2.6 | Enable-policy gates before the judge can act: precision ≥0.90 on `goal_met=False`, false-downgrade ≤2%, recall ≥0.70, flip ≤5%, κ/α ≥0.6 — **default off (shadow) until all pass**, toggled at runtime via GCS/file-backed config with 30s TTL | `.cursor/skills/llm-eval-grounded-theory/reference.md` §2.8, `services/goal_judge_runtime_config.py` (305 lines) |
| 2.7 | 3-level drift monitoring: performance (2σ weekly), judge calibration (Cohen's κ ≥ 0.75 monthly), governance integrity (HMAC verification) — alerts emitted into the governance trail | `meta/drift.py` |

**So-what chain:** taxonomy + IAA + gates → the eval pipeline is calibrated against humans before it's allowed to act → a developer gets a working template for the hardest open problem in agents (knowing if they worked) → supports GT.

---

## Key Argument 3 — Operability: deploys with policy-as-code and idles at hobby cost, web search included free (dimension: cost & operations · confidence 0.85)

| # | Evidence | Source |
|---|---|---|
| 3.1 | Two IaC tiers: dev-tier (Cloud Run scale-to-zero + Neon free Postgres + Cloudflare Pages) at **$5–30/mo** (Cloudflare Pro dominates the bill), and GCP Tier A (Cloud SQL db-f1-micro ~$7.67/mo, max 4 instances, optional $50 budget alarm) | `infra/dev-tier/README.md`, `infra/RUNBOOK.md`, `infra/gcp/` |
| 3.2 | **13 OPA/Rego policy files + 11 Gherkin feature files** gate every apply: no plaintext secrets, no allUsers IAM, scale-to-zero enforced, SSE cache bypass — **108 conftest assertions + 38 infra pytest checks**, mutation-tested (flipping a value fires the gates) | `infra/*/policies/*.rego`, `infra/*/features/*.feature`, `tests/infra/` |
| 3.3 | Web search costs **$0 and zero API keys**: self-hosted SearXNG sidecar (localhost or Cloud Run, port 8888, scale-to-zero), behind a hexagonal `WebSearchProvider` port with a stub for CI | `services/tools/search/`, `docker-compose.searxng.yml`, `docs/recipes/gcp/10_web_search_searxng.md` |
| 3.4 | Search results are security-processed: every snippet runs the retrieval rail sanitizer (indirect-injection stripping, modifications logged); failures are terminal (`ok=False`) and a no-progress detector (threshold 3, hard limit 5) stops loop-on-dead-backend | `services/tools/web_search.py`, `orchestration/react_loop.py`, `tests/services/test_web_search.py` (15+ cases, failure-first) |
| 3.5 | Observability relay: black-box JSONL outbox → Langfuse with at-least-once byte-offset delivery, dead-letter queue (5 retries), compliance bundles routed to `agent-compliance-audit` vs `agent-incident-replay` datasets by chain-integrity check | `middleware/sidecars/black_box_to_telemetry.py` (347 lines) |
| 3.6 | Phased deploy orchestration (preflight → … → smoke) with two mandatory human gates (DB migration, WorkOS redirect), digest-pinned images, CalVer+SHA deploy IDs | `scripts/deploy_gcp.sh`, `.cursor/skills/deploy-gcp/SKILL.md` |
| 3.7 | A documented graduation ladder (Stage A→B→C→D) where every substrate swap is composition-root-only — no port/adapter code changes | `infra/RUNBOOK.md`, `middleware/composition.py` |

**So-what chain:** policy-gated IaC + free search + scale-to-zero → a student or indie dev can run the full stack for roughly the price of a coffee → "production-grade" stops being gatekept by cloud budgets → supports GT.

---

## Key Argument 4 — Learning: 40+ recipes and the reasoning prompts that built the repo are part of the repo (dimension: learnability · confidence 0.8)

| # | Evidence | Source |
|---|---|---|
| 4.1 | **40+ teaching recipes** in `docs/recipes/`: GCP (13), guardrails (9, "five-door" security metaphor), governance (7, flight-recorder narrative), goal judge (3), standalone TDD/validation (6+) — each with Goal, Prerequisites, Steps, Human Review Gate, Verify, Rollback, Cost notes | `docs/recipes/` |
| 4.2 | Recipes use a **dual-audience format**: "for this workspace" (exact paths/commands) and "for a general audience" (any LangGraph app, any Next.js stack) — designed for readers who want to port the pattern | e.g. `docs/recipes/gcp/00_adapters.md` |
| 4.3 | The meta-tooling is included: the **SCQA reframing prompt, Pyramid Principle ReACT prompt, and TDD-for-agentic-systems prompt** ship in `research/`, and the pyramid agent is runnable via `StructuredReasoning/cli_pyramid.py` | `research/*.md`, `StructuredReasoning/` |
| 4.4 | Architecture is a teachable artifact: 4 layers enforced by **12 CI gate modules**; 2,500 test functions (53.6K lines of tests vs 26.7K app — 2:1) with 0 live LLM calls in CI; 23 Jinja2 prompt templates, zero prompt strings in Python | `tests/architecture/`, repo-wide audit 2026-06-11 |
| 4.5 | Skills for agentic IDEs included (deploy-gcp, llm-eval-grounded-theory) — the repo teaches your coding agent, not just you | `.cursor/skills/` |

**So-what chain:** recipes + included prompts + enforced architecture → the repo is a curriculum, not just a codebase → stars come from "I learned something I can reuse" → supports GT.

---

## Gaps (confidence reducers — also the honest-slide material)

| Gap | Severity | Impact |
|---|---|---|
| **No LICENSE file yet** — README says treat as all-rights-reserved. For a stars/adoption pitch this is the single biggest blocker; "use it in your project" is legally not yet true. | **High** | Must fix (or announce) before promotion |
| Test suite not executed in this audit (requires Python 3.13; audit sandbox has 3.10). Counts are static; "passing" status rests on CI config + README badge, not independent run. | Medium | Phrase as counts + CI design, not green-build claims |
| ~20 live-LLM/infra-marked tests failing in local pytest cache (excluded from CI by design). | Low | Disclose; it's also a credibility asset |
| Production ONNX classifier weights (~184MB) not committed — users must run the training script; runtime quality claims (recall/FPR) are gate thresholds, not numbers I re-measured. | Medium | State as "gated thresholds," not measured-by-me |
| Repo public visibility and current star count unverified from this environment. | Low | Avoid "join N developers" claims |

**Cross-branch interactions:** B1's eval gates reuse B2's frozen-gate philosophy (one discipline, two applications — presented as separate dimensions of value, not double-counted). B3's near-zero cost is what makes B4's recipes practically followable. The license gap (Gaps) interacts with **all** branches for the adoption goal.

---

## Validation Log

| Check | Result | Details |
|---|---|---|
| Completeness | Pass | Security / evals / operations / learning covers the adopt-learn-star decision space; popularity excluded by scope |
| Non-overlap | Pass | Conventions documented (guardrail-ML→B1, judge-ML→B2, SearXNG→B3, discipline→B4) |
| Item placement | Pass | 1.2→B1 only; 2.4→B2 only; 3.3→B3 only |
| So-what | Pass | Chains recorded per argument |
| Vertical logic | Pass | "Why star it?" → because security, evals, ops, learning — exactly the four arguments |
| Remove-one | Pass | Dropping any single argument leaves three independent reasons; GT survives |
| Never-one | Pass | No single-child groupings |
| Mathematical | Pass | 26.7K + 53.6K + 27.7K = 108K LOC; $5–30/mo per RUNBOOK cost table |

**Iteration count:** 1 · **Tools:** 4 parallel repo-exploration agents + direct file reads · **Presentation note:** Argument 2 (evaluation science) is the rarest content on the internet and the strongest viral candidate; the license gap must be resolved or explicitly addressed on the closing slide.
