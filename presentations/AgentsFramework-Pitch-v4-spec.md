# AgentsFramework Pitch v4 — Slide-by-Slide Spec & Honesty Ledger

**Built:** 2026-06-19, extended 2026-06-20 · **Source:** `AgentsFramework-Pitch-v3.pptx` (11 slides) → **`AgentsFramework-Pitch-v4.pptx` (16 slides)**
**Change:** inserted two new sections after the Architecture slide — **SECTION 1.5 · THE RUNTIME** (3 slides) and **SECTION 1.6–1.7 · WHAT SHIPPED** (2 slides: planning + memory). No v3 content altered; v3 files untouched on disk.

## Why v4 exists

v3 told the *value* story well but was **entirely text** and omitted the runtime mechanics that are the actual differentiator (the five-phase journey, depth×tier orthogonality, the GAIA fan-out guard). The `presentations/` folder already held polished NotebookLM diagrams of exactly this material — but in a clashing beige "blueprint" aesthetic. v4 **rebuilds those three ideas natively** in v3's own design system (Georgia/Calibri, navy `#10172E` / teal `#02C39A`, the S/C tension band, the dark answer card) so the new slides are indistinguishable from native v3 slides, and **gates every claim against the actual code**.

## Design system (extracted from v3 XML, reused verbatim)

| Token | Value |
|---|---|
| Light bg | `#F7F9FD` · Dark bg `#10172E` |
| Accent (teal) | `#02C39A` |
| Card fills | answer card `#10172E` (square corners, **Calibri** title), light card `#EAF0FA`, matrix nav `#1E2761`/`#2A3A6B` |
| Body text | ice `#CADCFC`/`#DDE5F2`/`#8FA3C8`, slate footer `#5A6B8C` |
| Fonts | Georgia (titles) · Calibri (body) · Consolas (code/node names) |
| Geometry | 16:9, 960×540px grid; left teal accent bar; section chip (11pt, `spc=300`); footer |

## The new section (slides 5–7)

### Slide 5 — "One task, five phases — not one hopeful loop"
- **Visual:** 5-card horizontal pipeline (Ingress→Planning→Execution→Evaluation→Exit) with teal `›` connectors; each card = phase tag + real node name (Consolas) + one-line purpose. Bottom strip carries the verify command.
- **Marketing job:** reframes "ReAct loop" (commodity) as a governed five-phase journey (differentiated). Pairs with v3 slide 1's "the demo was the easy part."
- **Honesty ✅:** every node verified in `orchestration/react_loop.py` — `guard_input_node` (739), `route_node` (898), `evaluate_node` (1946), `supervisor_node` (2494), `reasoning_recap_node` (2904). Verify line on slide: `grep -n "def .*_node" orchestration/react_loop.py`.

### Slide 6 — "Two orthogonal axes, one unbreakable floor"
- **Visual:** left = 3×3 matrix (T1/T2/T3 × L0/L1/L2; T3 "Never" at L0, "if ≥2 steps" at L1/L2). Right = native answer card: the deterministic plan floor.
- **Marketing job:** shows depth and pipeline tiers are *independent* (not one-size-fits-all) and that the plan floor survives a bad LLM plan — the "won't brittle-stall" promise.
- **Honesty ✅:** `build_plan_artifact` + `build_plan_artifact_llm` exist (`react_loop.py:43-44`, used at 1135). T3 default-OFF stated honestly: `t3_fanout_enabled: bool = False` (`services/base_config.py:80`) — framed as a *capability*, not a claim it runs by default.

### Slide 7 — "Parallelism that refuses to corrupt"
- **Visual:** left = 5-step decision ladder ending in green `FAN_OUT` (every prior path → DECLINE). Right = a **MEASURED** card with the scoped empirical result.
- **Marketing job:** "decline is the default; a wrong fan-out is corruption, a missed one is cheap." The rarest, most credible content — a guard that *refuses* to parallelize.
- **Honesty ⚠️→✅ (scoped):** `fan_out|decline` + deterministic-floor declines verified in `react_loop.py:2495–2557`. The headline `1.0 precision / fp=0 / 10/10 declines` is **real but from one stress run** (`docs/plans/t3_stage_b_case_walkthrough.md:172,229`). The card therefore says **"MEASURED · T3 STRESS CORPUS"** and **"Small N, designed corpus — … not a population guarantee,"** with the source path printed. This is the deck's single most important honesty guardrail.

## The "what shipped" section (slides 8–9, added 2026-06-20)

### Slide 8 — "From a brittle loop to a tiered reasoning ladder" (last week's planning work)
- **Visual:** four dark cards (T1 / T2 / T3 / §5), each = tier chip + capability + the gating flag pinned at the card bottom; takeaway strip on shadow-first promotion.
- **Marketing job:** shows momentum — the tiered planning ladder that landed Jun 9–15 — while framing every rung as evidence-gated, not hype.
- **Honesty ✅:** `PlanGenerator` (`components/plan_generator.py`), `decide_reentry` (`components/reflexion.py`), `plan_delegations`/`validate_independence` (`components/supervisor_plan.py`), `decide_escalation` (`components/router.py`). Flags default-OFF in `services/base_config.py`: `plan_source="deterministic"`, `reflexion_enabled=False`, `t3_fanout_enabled=False`.

### Slide 9 — "Memory: recall, capture, full audit trail" (this week's memory work)
- **Visual:** three stacked stage cards (RECALL / AUTO-CAPTURE / GOVERN), each carrying its governance carrier signature; right card = durable/swappable/off-by-default backend.
- **Marketing job:** the memory layer that landed Jun 17–19, told through its governance trail (every read/write/reject leaves a carrier) — the audit story is the differentiator.
- **Honesty ✅:** `MemoryAutoCaptureService` (`services/memory_autocapture.py`), `Mem0MemoryBackend` (`services/memory_backends/mem0.py`), `TypedMemory` (`components/memory_extractor.py`). Flags default-OFF: `memory_enabled=False`, `memory_autocapture_enabled=False`. Carriers `MEMORY_RECALLED/STORED/SUPPRESSED/CONSOLIDATED` in `services/governance/black_box.py:61–76`.

## Honesty ledger — what was CUT (and why)

| Material (from supporting assets) | Why cut |
|---|---|
| **Trust scoring / Access Rings** (`+15`/`−50`, Ring 0–3, EMA decay curve) | **Not shipped.** Exists only in `research/tdd_agentic_systems_prompt.md` (a TDD *prompt example*) + `TrustFrameworkAnd Governance.md` (concept). `trust/` has `suspend()`/`IdentityStatus` lifecycle but **no numeric score engine, no EMA, no rings**. Presenting it as built would break v3's covenant "every claim checkable in the code." Verified absent: `grep -rniE "trust.?score|ring_[0-3]" trust/ services/` returns only enum/docstring noise. |
| Blueprint "Latency Threshold Exceeded" / `gpt-4-turbo` call-site annotations | Illustrative diagram garnish; `gpt-4-turbo` also contradicts the repo's "model names never hardcoded / LiteLLM routing" claim. |
| NotebookLM Mind Map PNG | Too dense for a pitch; fine as a `docs/` artifact. |
| Pasting the NotebookLM blueprint renders directly | Clashing beige/blueprint aesthetic; rebuilt natively instead so the deck reads as one visual language. |

## Verification performed

- **Honesty pass:** every concrete claim on slides 5–7 mapped to a repo path/command (above); cut material confirmed absent in shipped code.
- **Visual QA:** rendered via LibreOffice; fresh-eyes subagent review of slides 4–8. Fixed: slide-5 verify-band footer crowding + card baseline misalignment; slides 6/7 dark cards re-styled to match the native answer card (square corners, Calibri title, no teal top bar); slide-7 header de-orphaned.
- **Regression:** v3 `.pptx`/`.pdf` byte-identical on disk; v4 carries all 11 original slides (slide-XML bytes 233K→308K, no media stripped — v3 had none).

## Files

- `AgentsFramework-Pitch-v4.pptx` — editable deck (14 slides)
- `AgentsFramework-Pitch-v4.pdf` — rendered export
- `AgentsFramework-Pitch-v4-spec.md` — this document
- Build script (not committed): `/tmp/build_v4.py` — rebuilds v4 from a fresh v3 copy idempotently.

## Open options (not done — your call)

1. **Track-A visual polish** on existing v3 value slides (guardrail 3-stage cascade strip on slide 8; 4-pillar icon row on the goal-judge slide). Deferred — the value slides already read well; this is optional gilding.
2. **Optional roadmap slide** for the trust-ring *design* (honestly labeled "not yet in `trust/`, see `research/`") if you want the vision on record.
