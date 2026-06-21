# Context Compression / Context Engineering for the Runtime Pipeline

> **Status:** Design-space map + **executable C1+C2 plan ready** (updated 2026-06-21). §1–§7 are the brainstorm/design map; **§B1-R** / **§B2-R** are the external-research scans for B1 (compaction) and B2 (anti-truncation floor); **§8** is the executable implementation plan for C1+C2, with the B2 findings folded into Steps 1/3/4/5/6 and the C2 gate. Not yet built — default-OFF, prod byte-identical until a tagged revision.
> **Builds on:** the memory research corpus [`docs/research/memory/`](../research/memory/) (MemoryBank 3-tier + Ebbinghaus decay, A-MEM linking, Search-o1, working-memory trimming/summarization, token-cost math) and the shipped Hermes A1/A2/A3 + enable-policy work ([`hermes_adoptions_design.md`](../research/memory/hermes_adoptions_design.md)).
> **Scope (confirmed with user):** the *runtime context pipeline* (NOT the OKF knowledge-plane). Optimize for all four goals — token cost, long-horizon fidelity, injected-context quality, architectural rigor — with rigor as the binding constraint.

## Context

**Why now.** The long-term *memory* layer (Hermes A1/A2/A3 + the enable-policy guard) is built and gated. The next lever is the **runtime context pipeline** — how the LangGraph agent assembles, accumulates, and compresses what reaches the model on *every* LLM call, within a run and across a thread. The research collected in `docs/research/memory/` is the conceptual menu; this doc maps it onto the **actual live seams** so we don't propose greenfield for what exists, and picks a phased, eval-gated path.

---

## 1. The live pipeline today (ground truth, from code)

The agent hot path assembles context in `orchestration/react_loop.py::call_llm_node`:

```
system_prompt = render("system_prompt", additional_instructions = planning_instructions + recalled_memories)
lc_messages   = [SystemMessage(system_prompt)] + list(state["messages"])      # ← ENTIRE history, every call
llm.call(lc_messages, ...)
```

What accumulates in `AgentState` (`orchestration/state.py`) and **rides forward uncompressed**:
- `messages` (MessagesState, append-only) — **the dominant token driver**; full transcript re-sent each lap.
- `reasoning_trace` (`operator.add`), `step_results` / `tool_results` (`_append_list*`), `files` (`_merge_dict`) — all append-only, persisted across checkpoints; never trimmed between turns.

The **only** compression that exists today:
- `services/summarizer.py` — `should_compact_trajectory(current_token_count, threshold)` + `build_compaction_summary(...)`. Deterministic, **lossy**, fires at `trajectory_compaction_token_threshold = 3000` (`base_config.py:39`). It keeps the **last 3** trace entries + last 3 tool names, hard-truncates at fixed char counts (`[:120]/[:280]/[:200]`), offloads to `files[".agent_offload/..."]`, and **replaces `reasoning_trace`** with a one-line summary. It sets `truncation_applied=True`.
- The recall read-side filters (`components/memory_context.py`: `filter_recall_records` + `render_recall_block`) — A2 relevance floor + exact-text dedup + A3 `[confirmed]/[inferred]` tiers. Quality-gates *recalled memories*, not the conversation.

Token accounting: `current_token_count` / `total_input_tokens` / `total_output_tokens` from Claude `usage_metadata` only (no tokenizer; no pre-call estimate).

### The core gap (one sentence)
**`summarizer.py` compacts the cheap thing (`reasoning_trace`) and never touches the expensive thing (`messages`)** — so on a long thread the model re-reads the entire transcript every lap, the trajectory summary is a blind fixed-char truncation with no selection or eval, and there is no tiering, no decay, no pinned-facts, and no in-loop retrieval. Everything the research describes is unbuilt on the message path.

---

## 2. Research → live seam map (what binds where)

| Research concept (docs/research/memory) | Live seam it binds onto | Status today |
|---|---|---|
| **Working-memory trimming** (FIFO window, `MAX_CONTEXT_TOKENS`, `PINNED_FACTS`) | `call_llm_node` message stacking (`react_loop.py:1581`) | ❌ none — full history always sent |
| **Rolling / windowed / update-in-place summarization** | `summarizer.py` (extend from trajectory→messages) | ⚠️ stub: trajectory only, deterministic, no eval |
| **MemoryBank 3-tier** (hot turns / warm summaries / cold portrait) | thread state + `LongTermMemoryService` | ⚠️ partial: cold ≈ long-term memory; **no hot/warm split** on the message path |
| **Ebbinghaus decay + access-strengthening** | `MemoryRecord.metadata` (`stored_at` exists; add `last_accessed`/`access_count`); `consolidate()` eviction order | ❌ none — A1 evicts by salience, no time-decay, recall doesn't strengthen |
| **A-MEM linking** (note graph, similarity backlinks) | `LongTermMemoryService` + Mem0 backend | ❌ none — flat store, no typed links |
| **Search-o1 in-reasoning retrieval** | the react loop itself (retrieve mid-thought, condense, continue) | ❌ none — recall fires once at `route_node`, not in-loop |
| **Selective retrieval ("20% context")** | recall top-k + the A2 floor | ⚠️ partial: A2 floor exists; not applied to message history |
| **Reason-in-Documents condensation** | tool-result handling (`tool_results` ride raw) | ❌ none — raw tool output accumulates |

**Reuse, don't rebuild:** the A2/A3 filter functions, `ConsolidationOutcome`, the `MEMORY_CONSOLIDATED` carrier shape, the eval-probe scaffold (`agentsframework-eval-probe`), `eval_capture`, and the four-layer invariants are all in place and directly reusable.

---

## 3. The design space (the brainstorm menu)

Five candidate moves, ordered by leverage-per-risk. Each names the seam and the goal(s) it serves.

### B1 — Compact the *message history*, not just the trajectory  *(cost ↑↑, fidelity ↑, rigor)*
Today `summarizer.py` is pointed at the wrong list. Extend the same threshold-triggered seam to the real driver: when `current_token_count` crosses a budget, fold the **oldest** N message turns into a single summary `SystemMessage` and keep the last K turns verbatim (the research's "hybrid: K live turns + rolling summary"). Two sub-flavors:
- **B1-det** (deterministic): structured extract (task, decisions, open constraints, last tool I/O) — extends `build_compaction_summary`, no LLM, no new latency, CI-testable. Ship first.
- **B1-llm** (v1.5): a cheap-tier summarizer call for prose turns — better fidelity, +100–400ms, must be eval-gated.

This is the single highest-leverage change: it's where the 65–73% token savings in the research's cost math actually live. **The external research (§B1-R) re-orders the first move inside B1 — see below.**

---

## B1-R — External research on message-history compaction (2025 best practices)

Targeted scan of arXiv (2025), production agent SDKs (OpenHands, Gemini-CLI, Claude Code), and the framework we're on (LangChain/LangGraph). Eight findings, ordered by how directly they reshape B1. **The headline: the field has largely concluded that the *simplest* compaction — masking/clearing old tool observations while keeping the reasoning trace — matches LLM summarization at half the cost. That flips B1's emphasis: do observation-clearing FIRST, summarization only when that's not enough.**

### R1. Observation masking ≈ LLM summarization, at half the cost — the "complexity trap"
The strongest single result. JetBrains Research, *"The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization for Agent Context Management"* (NeurIPS 2025 DL4Code; [arXiv:2508.21433](https://arxiv.org/abs/2508.21433), [code](https://github.com/JetBrains-Research/the-complexity-trap)). On SWE-bench Verified: **observation masking** (replace *old tool outputs* with a placeholder, keep the agent's reasoning messages intact) costs **$0.61/instance vs $1.29 raw (−52.7%)** and actually **beats** LLM-Summary ($0.64) on both cost *and* solve rate (54.8% vs 53.8% raw, with Qwen3-Coder-480B). Mechanism: keep the most recent **M = 10 turns'** observations verbatim, replace all older observation *content* with a fixed placeholder string ("Previous N lines omitted for brevity."); never touch reasoning/action messages. M=10 is the ablated optimum (M=5 underperforms, M=20 degrades). A hybrid (mask + summarize-on-overflow) shaves a further 7–11%.
→ **Implication for B1:** the cheapest, lowest-risk, *deterministic, no-LLM* move is to clear/placeholder **old `tool_results`/ToolMessages** (which `react_loop` already accumulates raw), not to summarize prose turns. This is a stronger "ship first" than B1-det's prose extract. **Anthropic agrees explicitly** ([Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)): *"tool result clearing is one of the safest, lightest-touch forms of compaction… once a tool has been called deep in the message history, why would the agent need to see the raw result again?"*

### R2. Compact at a *fraction of the window*, not a fixed token count — resolves §6 Q1
Convergent across sources. Anthropic compacts when "nearing the context window limit"; TokenPilot ([arXiv:2606.17016](https://arxiv.org/html/2606.17016)) triggers at **40% of a 500k window**; LangChain `SummarizationMiddleware` supports `("fraction", 0.3)` natively. ACON ([arXiv:2510.00615](https://arxiv.org/html/2510.00615v1)) uses **separate** thresholds for history (T_hist≈4096) vs observations (T_obs≈1024) — observations get clipped sooner because they're verbose and low-value.
→ **Resolves §6 Q1:** use a **window-fraction** trigger, and use **two** thresholds (observations clipped aggressively/early, reasoning history summarized later). The current single `3000` flat threshold is both too low and undifferentiated.

### R3. Keep last-K verbatim + one summary message, with pair-integrity — the canonical shape (and it's already in LangChain)
LangChain's `SummarizationMiddleware` ([source](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/summarization.py)) *is* the B1 reference implementation. Defaults: keep last **20** messages, trim-to-summarize at **4000** tokens. `keep` supports `("messages", N)` / `("tokens", N)` / `("fraction", f)`. `_find_safe_cutoff_point()` never splits an AIMessage's `tool_calls` from its ToolMessage (if the cutoff lands on a ToolMessage it collects the `tool_call_id`s and walks backward to include the issuing AIMessage) and preserves system messages. Old messages are removed via `RemoveMessage(id=REMOVE_ALL_MESSAGES)` then rebuilt as `[summary, *preserved_recent]`. Its `DEFAULT_SUMMARY_PROMPT` preserves four buckets: **SESSION INTENT / SUMMARY (decisions, rejected options) / ARTIFACTS (files+paths) / NEXT STEPS** — a ready-made template for B1-det's structured extract and B2's pinned set.
→ **Implication:** B1's shape is validated and the cutoff-safety logic (don't orphan a tool result) is a *must-have* we'd otherwise miss. We can borrow the bucket schema + safe-cutoff algorithm without taking the dependency.

### R4. Compaction MUST rewrite persisted state, not just the per-call list — resolves §6 Q4 (and it's a known bug)
The exact failure mode our §6 Q4 worried about is a **documented LangChain bug** ([deepagents#2876](https://github.com/langchain-ai/deepagents/issues/2876)): `SummarizationMiddleware` builds a bounded list for the *LLM call* but its `Command.update` never removes pre-cutoff messages from state. Because the message reducer is **append-only** (← exactly our `AgentState.messages`), checkpoints grow unbounded: write-amplification (multi-MB checkpoints/step), resumption cost, and the old content lives in *both* state and the offload file. Gemini-CLI has the **same defect** twice ([#20803](https://github.com/google-gemini/gemini-cli/issues/20803), [#21335](https://github.com/google-gemini/gemini-cli/discussions/21335)): "session resume restores full uncompressed history… context-window overflow makes the session unusable."
→ **Resolves §6 Q4:** compaction must emit a `RemoveMessage`-style state mutation (drop pre-cutoff, insert summary) so the **checkpointer reloads the compacted transcript**. Per-run-only compaction silently re-bloats on resume. This is the single biggest *correctness* trap in B1 — our append-only `messages` + `_append_list` reducers make us structurally vulnerable to it.

### R5. Validate-after-compact (the "probe" turn) — upgrades C2 from nice-to-have to a known production pattern
Gemini-CLI runs a **Probe turn after summarization** where the model checks whether critical info was lost; it also added a hard `COMPRESSION_FAILED_EMPTY_SUMMARY` guard after discovering empty summaries silently wiped context ([gemini-cli #16500 self-verification](https://github.com/google-gemini/gemini-cli/issues/16500)). Anthropic's tuning advice: *"start by maximizing recall to ensure your compaction prompt captures every relevant piece of information,"* then tighten.
→ **Implication for C2 + B2:** the eval-probe's **constraint-preservation hard gate** isn't gold-plating — it's the consensus fix for the #1 LLM-summarization failure (silent fact loss). Add the cheap deterministic guards too: non-empty summary, pinned-facts still present, token count strictly decreased.

### R6. Cache-aware compaction: rare big folds beat per-turn trimming — a cost trap that can *negate* B1
The counter-intuitive one. Aggressively mutating context every turn **shatters the prompt-prefix and the KV-cache**; the prefill/cache-invalidation penalty can *override* the text-token savings (TokenPilot [2606.17016](https://arxiv.org/html/2606.17016); *Still* [2606.07878](https://arxiv.org/html/2606.07878); the prefix-stability analysis). With prompt caching, *every* change to which messages are included invalidates the cached prefix.
→ **Implication for B1 trigger design:** compact **infrequently in large batches** (cross a high-water mark → one big fold) rather than trimming a turn each lap, so the prefix stays stable between folds and prompt-cache hits survive. This sharpens §6 Q1 *and* the trigger hysteresis: add a cooldown so we don't re-compact every step.

### R7. Flat "summarize everything into one blob" causes context-rot — keep structure
Gemini-CLI is actively moving *off* flat compaction toward **union-find / hierarchical** compaction ([#22877](https://github.com/google-gemini/gemini-cli/issues/22877), [discussion #26488](https://github.com/google-gemini/gemini-cli/discussions/26488)): *"flat compaction is lossy at the wrong granularity… facts, decisions, and constraints vanish unpredictably."* ACON's distilled-compressor and "surgical, not blanket" framing says the same.
→ **Implication:** don't collapse history to a single opaque paragraph. Keep the **structured buckets** (R3) and the **pinned set** (B2) as separate, addressable fields — which also makes the C2 eval gate checkable per-bucket. Defers (does not adopt) the heavier union-find/A-MEM-graph approaches — consistent with our "flat store sufficient" out-of-scope call, but worth a seam.

### R8. ACON — when you *do* summarize, optimize the prompt against failures, and you can distill it cheap
ACON ([arXiv:2510.00615](https://arxiv.org/html/2510.00615v1)) compresses both history and observations via an LLM whose **compression prompt is optimized from contrastive failure pairs** (tasks that pass uncompressed but fail compressed → feedback → refined guideline), then **distilled into a small model** (Qwen/Phi) that retains >95% of teacher quality. Result: 26–54% token reduction at ~baseline accuracy (AppWorld 56.5% vs 56.0%); enables small agents to jump 20–46%.
→ **Implication for B1-llm (v1.5):** if/when we add the LLM summarizer, (a) tune its prompt on our *own* failing traces (we have the eval-probe + corpus to generate contrastive pairs), and (b) a small/cheap-tier model is sufficient — don't pay frontier-tier for summarization. This is the eval-gated, calibrate-don't-guess discipline applied to the summarizer prompt itself.

### Net effect on the B1 design

| Brainstorm assumption | What the research says | Change |
|---|---|---|
| B1-det = structured prose extract, ship first | **Observation/tool-result clearing** is cheaper, safer, deterministic, and matches summarization (R1, Anthropic) | **Re-order:** ship *tool-result clearing* first; prose summary is the second step |
| Single token threshold `3000` (§6 Q1) | Window-**fraction** trigger; **two** thresholds (obs ≪ history) (R2, ACON) | Fraction-of-window + split obs/history thresholds + cooldown |
| Fold oldest → one summary `SystemMessage` | Right shape, but: don't orphan tool-pairs; replace via `RemoveMessage`; keep **structured buckets** not a blob (R3, R4, R7) | Adopt LangChain's safe-cutoff + state-rewrite + bucket schema |
| Per-run compaction, §6 Q4 "do we need cross-turn?" | **Yes, mandatory** — append-only state re-bloats on resume (R4) | Compaction rewrites checkpointed state, not just the call list |
| C2 eval probe as a quality nicety | It's the consensus fix for silent fact-loss; everyone ships a validate/probe step (R5) | Constraint-preservation = **hard gate**, plus empty-summary + token-decrease guards |
| Cost savings are monotonic in trimming | Per-turn trimming can **negate** savings via KV-cache invalidation (R6) | Compact in **rare large batches** with hysteresis, prefix-stable between folds |
| LLM summarizer = frontier model, expensive | Cheap/distilled model retains >95%; tune prompt on our own failures (R8) | B1-llm uses cheap tier; prompt calibrated from contrastive traces |

**Bottom line:** B1 is even higher-leverage than the brainstorm assumed, *and* the lowest-risk first slice changed — **clear old tool observations (deterministic, no LLM, ~half the cost) before touching prose summarization** — with two non-obvious must-haves the research surfaced: (1) **rewrite persisted state** or it re-bloats on resume, and (2) **compact rarely in big batches** or KV-cache churn eats the savings.

### B2 — Pinned facts / anti-truncation floor  *(fidelity ↑↑, rigor)*
A compaction that drops a hard constraint ("budget = $5k", "must not use nuts") is the failure mode the research's `PINNED_FACTS` knob exists for. Mirror the **memory safety-floor** we just built (`LongTermMemoryService(safety_floor=...)`): a pinned set (success-conditions from `task_understanding`, explicit user constraints) that compaction may **never** summarize away. Reuses the floor concept; binds onto the existing `task_understanding` artifact in state. **The external research (§B2-R) sharpens this substantially — pinning is necessary but not sufficient; see below.**

---

## B2-R — External research on pinned facts / anti-truncation floors (2025 best practices)

Targeted scan of arXiv (2025–26) constraint-retention + persistent-fact + structured-eviction work, plus prompt-placement guidance. Six findings. **The headline is a correction: keeping a constraint in the context is NOT the same as keeping it obeyed. "Do-not" constraints decay to ~20% compliance by ~turn 25 purely from attentional dilution — and pinning them to the system prompt / KV-cache does *nothing* to stop it. B2 therefore needs two parts: (a) a structural floor that survives *compaction*, and (b) tail re-injection that survives *attentional dilution*.**

### S1. Omission constraints decay, commission constraints persist — the core asymmetry (the most important finding)
*"Omission Constraints Decay While Commission Constraints Persist in Long-Context LLM Agents"* ([arXiv:2604.20911](https://arxiv.org/html/2604.20911v1)). Measured, with p<10⁻³³: **commission** constraints (must-DO: "include incident ID", "begin with STATUS:") hold ~**100%** at every depth, while **omission** constraints (must-NOT: "never use bullet points", "never disclose credentials") fall from **~73% at turn 5 → 20% at turn 25** (Mistral Large 3). A model can obey a commission and violate an omission *in the same response*. **Token count, not turn count, is the failure predictor** (β̂=+0.19, p=3.4×10⁻⁸; turn-depth p=0.78) — i.e. it's attentional distance from the rule, not elapsed turns. "Safe Turn Depth" before omission compliance crosses 50%: Qwen-3.5 ≈ 7 turns, Mistral-Large-3 ≈ 10.6 (~15k tokens); some models (Gemma-4-31B) immune past 25.
→ **Implication for B2:** the pinned set is **not uniform** — negative/prohibition constraints are the fragile class and need active defense; positive success-conditions mostly take care of themselves. **Crucially: "pinning the system prompt to the KV cache… does not protect the policy document from attentional dilution at deep context positions."** So a B2 that only copies constraints into the *summary header* (top of context) will still silently fail the do-not rules. The paper's two deployable defenses are **(A) periodic re-injection** of omission constraints every k turns (k≈ the model's Safe Turn Depth) and **(B) a safe-token-budget cap** that forces a compaction/reset before the decay threshold.

### S2. Placement: non-negotiable rules go at the END (recency), best is BOTH ends
Convergent prompt-engineering evidence: LLMs attend most to the **start (primacy) and end (recency)**; the interior is "lost in the middle." Production reports moving a critical rule from middle→end lifting compliance 78%→96%; adherence to system-prompt rules visibly degrades past ~80k tokens and **mid-conversation reminders refresh the rule via recency**. Claude Code itself double-reinforces its security declaration at **both** the top and the bottom of the prompt.
→ **Implication for B2:** the pinned floor should appear at the **tail of the assembled context** (just before the live turns), and ideally also at the head — *double reinforcement*. This is the concrete placement the omission paper (S1) left unmeasured. It also means our current stacking (`[SystemMessage(system_prompt)] + messages`) puts constraints only at the *top* — the weakest spot for the fragile omission class on a long thread.

### S3. Facts as first-class objects — store structurally, never as prose, so compaction selects *which* not *how-to-summarize*
*"Facts as First Class Objects: Knowledge Objects for Persistent LLM Memory"* ([arXiv:2603.17781](https://arxiv.org/pdf/2603.17781)). A fact is a discrete addressable object (claim + type + provenance + stable id), extracted "at granularity matching the original content," not aggregated. Compaction happens at the **retrieval stage (selective inclusion), not the storage stage (summarization)** — so numerical values, edge cases, and explicit negations survive verbatim. Guidance #4 is exactly our case: **"store 'NOT applicable under X' as a first-class fact"**; #5: "facts once inserted cannot be summarized; only retrieved selectively."
→ **Implication for B2:** the pinned set should be a list of **atomic, verbatim, addressable constraint strings** (one per fact), copied into the fold **verbatim** — never paraphrased into the prose summary. This is precisely what makes the "every pinned string present post-fold" hard gate (C2) a clean exact-substring check. Validates B2's verbatim-copy design and says: keep each constraint atomic (split compound rules) so the gate is per-constraint.

### S4. CWL — a deterministic *protection hierarchy* with an inviolable floor that surfaces rather than degrades
*"Beyond Compaction: Structured Context Eviction for Long-Horizon Agents"* (CWL, [arXiv:2606.11213](https://arxiv.org/html/2606.11213)). LLM-free, deterministic graduated eviction over a typed dependency graph. Its **protected classes are an explicit hierarchy**: user turns (inviolable — "never evicted regardless of token pressure"), the prologue (system prompt + tool defs + initial user context), active episodes, and causal antecedents. The load-bearing rule for us: **"if the budget cannot be met without touching user turns, the system surfaces the condition rather than silently degrading."**
→ **Implication for B2:** model the floor as a **protection hierarchy**, not a flat pin-list: (1) user-authored constraints + success-conditions = inviolable; (2) if even the last-K + pinned floor still exceeds budget, **fail loud** (emit a carrier / refuse to over-compact) rather than dropping a constraint silently. This is the "never calibrate away a dropped safety constraint" hard-zero, now with a named precedent. Also reframes B1's observation-clearing as the *graduated* level that runs *before* we ever touch anything protected.

### S5. Re-injection is the live-defense; the structural floor is the compaction-defense — they're two different jobs
Synthesizing S1+S2+S4: there are **two distinct loss channels** and B2 must cover both. **(i) Compaction loss** — a fold paraphrases the constraint away → defended by the *structural verbatim floor* (S3) + the post-fold presence gate (C2). **(ii) Attentional-dilution loss** — the constraint is present but ignored at depth → defended by *tail re-injection* (S1/S2), independent of whether a fold happened. A short thread that never triggers compaction can still violate a do-not rule at turn 20. The brainstorm conflated these; they need separate mechanisms.

### S6. Token-budget cap as the backstop (ties B2 to B1's trigger)
S1's defense (B) — cap cumulative tokens at a "safe-token-budget" derived from the model's Safe Turn Depth — is the *same knob* as B1's fraction-of-window compaction trigger (§B1-R R2). Setting the B1 trigger fraction at/below the model's empirical STB makes compaction itself the constraint-decay backstop: we never let the thread run past the depth where omission compliance collapses without a fold + re-injection.
→ **Implication:** B1's `context_compact_trigger_fraction` should be **calibrated to the model's Safe Turn Depth**, not picked arbitrarily — a concrete answer to §6 Q1's open sub-question (what fraction). Lower-STD models (Qwen-class) get a lower fraction.

### Net effect on the B2 design

| Brainstorm assumption | What the research says | Change |
|---|---|---|
| Pin constraints into the summary header; that protects them | Pinning to system-prompt/KV-cache does **not** stop attentional decay; do-not rules hit ~20% by turn 25 (S1) | Add **tail re-injection** every k turns as a *separate* mechanism from the structural floor |
| All pinned facts are equivalent | **Omission (must-NOT) constraints are the fragile class**; commission (must-DO) mostly self-preserve (S1) | Tag pinned items by polarity; prioritize negative constraints for re-injection |
| Place the floor at top of the fold | Non-negotiable rules belong at the **END** (recency); best is **both** ends (S2) | Render the floor at the tail of assembled context (and head) — double reinforcement |
| Pin set = prose lines in the summary | Store **atomic, verbatim, addressable** constraint objects; compaction selects *which*, never *how-to-summarize* (S3) | One constraint per pinned string, copied verbatim, never paraphrased; split compound rules |
| Floor is a flat "never drop" list | Model it as a **protection hierarchy**; if budget can't be met without touching it, **fail loud** not silent (S4) | Inviolable tier + surface-the-condition carrier instead of silent over-compaction |
| Compaction is the only loss channel | **Two** channels: compaction-loss vs attentional-dilution-loss — different defenses (S5) | Structural floor (compaction) AND tail re-injection (dilution), both required |
| Trigger fraction is a free parameter | Cap at the model's empirical **Safe Turn Depth** / safe-token-budget (S1-B, S6) | Calibrate B1's trigger fraction to STD; lower for low-STD models |

**Bottom line for B2:** pinning is necessary but **not sufficient**. The floor must be (1) **structural + verbatim + atomic** so a fold can't paraphrase it away, (2) **polarity-aware** because "do-not" rules are the ones that fail, (3) **re-injected at the tail** every k≈Safe-Turn-Depth turns to beat attentional dilution (a *separate* job from compaction), (4) a **protection hierarchy that fails loud** rather than silently dropping a constraint, and (5) tied to a **token-budget cap** calibrated to the model's Safe Turn Depth — which is also the principled value for B1's compaction trigger.

### B3 — Tiered working memory (hot / warm / cold)  *(cost ↑, fidelity ↑, quality ↑)*
Make the three-tier MemoryBank model explicit on the message path: **hot** = last K verbatim turns; **warm** = rolling summaries (B1 output) + recalled long-term memories (A2/A3 already filter these); **cold** = the durable `LongTermMemoryService`. This is mostly *organizing* B1+recall into one assembled context block with a clear budget per tier, rather than the current "system_prompt + everything" stack. Gives a single place to enforce a per-tier token budget.

### B4 — Decay + access-strengthening on long-term memory  *(quality ↑, fidelity ↑)*
The biggest research-vs-live gap the Explore surfaced. Add `last_accessed`/`access_count` to `MemoryRecord.metadata` (we already stamp `stored_at`); `recall()` strengthens on hit; `consolidate()` blends an Ebbinghaus retention score with salience for eviction order. Pure `services/` change, reuses the A1 consolidation seam. Lower urgency (budgets already bound growth) but closes the "stale facts never fade" gap and improves *which* memories survive.

### B5 — Search-o1 style in-loop retrieval  *(quality ↑↑, cost ↓ per-token-value)*
Highest sophistication, highest cost-risk. Let the agent retrieve mid-reasoning (not just once at `route_node`) and condense before continuing. The research flags ~15–30% overhead — reserve for high-value analytical tasks, behind a flag, only after B1–B3 land. Likely a **defer-with-seam** verdict (like A4), not a v1.

---

## 4. Recommended phasing

Mirrors the memory-layer discipline: default-OFF flags, shadow-measure, eval-gate, then flip. Prod byte-identical until a `--tag` revision.

| Phase | Ships | Flag | Goal served | Gated on |
|---|---|---|---|---|
| **C1** | **B1-det** — message-history compaction (observation-clearing first, then oldest→summary, keep last K) + **B2** pinned-facts floor | `CONTEXT_COMPACT_MESSAGES`, `CONTEXT_KEEP_LAST_K` | cost, fidelity | backward-compatible (default off = today) |
| **C2** | **Eval probe** on the compaction seam (does the summary preserve task/decisions/constraints? token-reduction ratio?) | — | rigor | `agentsframework-eval-probe` (L1 deterministic + L2 sampled judge) |
| **C3** | **B3** tiered assembly — one context-builder with per-tier budgets (folds B1 + recall) | `CONTEXT_TIER_BUDGETS` | cost, fidelity, quality | C1 live + C2 probe green |
| **v1.5** | **B1-llm** (cheap-tier summarizer) + **B4** decay/strengthening | `CONTEXT_SUMMARIZE_LLM`, `MEMORY_DECAY` | quality | C2 probe covers summary fidelity; consolidation eval |
| **v2** | **B5** Search-o1 in-loop retrieval | `CONTEXT_INLOOP_RETRIEVAL` | quality | B1–B3 live; high-value-task signal |

**Rationale:** C1 is the cost win and the most code is already there (re-point `summarizer.py`). C2 makes compaction trustworthy *before* we let an LLM do it (the research warns lossy summaries silently drop facts — that's a swallowed-failure class the eval-probe + a "constraint-preservation" hard gate must catch). C3 is organization, not new capability. v1.5/v2 are the sophistication tier, deferred behind seams exactly like A4.

---

## 5. Architectural rigor (the binding constraint)

Every move must hold the four-layer invariants the rest of the codebase enforces:
- **B1/B2/B4** are `services/` logic (extend `summarizer.py`, `long_term_memory.py`) — framework-clean (I-4), no `components/` import (I-5), pure + deterministic where possible (L1).
- **B3** context assembly stays a thin reader in `orchestration/` (I-7) — it passes budgets, the selection/summarize logic lives in `services/`/`components/`.
- **Governance:** a compaction that drops content is a Validation-pillar event — emit a **content-free** carrier (`tokens_before/after`, `turns_folded`, `pinned_kept`; never the dropped text), the same pattern as `MEMORY_CONSOLIDATED`. Non-required enrichment (no `default_spec()` change → drift-guard green).
- **Eval (cardinal rule 6):** the keep-last-K window, any summarizer, and any decay curve are **calibrated, not guessed** — default-off, shadow-measure token-reduction + constraint-preservation, then flip. Constraint-preservation is a **hard gate** (never calibrate away a dropped budget/safety constraint), mirroring the memory PII-flip hard-zero.
- **Flags:** all default-OFF, prod parity until a tagged revision — the `MEMORY_ENABLED` / enable-policy precedent.

---

## 6. Open questions (status after the B1-R research)

1. ~~**Compaction trigger:** single token threshold vs window-fraction? What fraction?~~ **RESOLVED (R2 + B2-R S6):** window-fraction trigger with **two** thresholds (obs early ~T_obs, history later ~T_hist) + a cooldown (R6). The fraction is **not free** — calibrate it at/below the model's empirical **Safe Turn Depth** / safe-token-budget (§B2-R S1/S6), so compaction itself backstops omission-constraint decay. Lower-STD models (Qwen-class ~7 turns) get a lower fraction than Mistral-class (~10 turns). Calibration is an eval task, not a guess.
2. ~~**B1-det vs B1-llm first?**~~ **RE-FRAMED by research (R1):** the cheapest deterministic first slice is **tool-result/observation clearing** (≈half the cost, matches summarization, no LLM) — *not* the prose extract. C1 ships observation-clearing as the first move, with prose/LLM summary as a later step.
3. **Decay (B4) priority:** budgets already bound growth, so decay is a quality refinement, not a fix. Worth it in v1.5, or defer to v2 with A4 (both want the same feedback signal)? *(still open)*
4. ~~**Per-thread vs per-run compaction?**~~ **RESOLVED by research (R4):** cross-turn is **mandatory, not optional** — our append-only `messages` + `_append_list` reducers will re-bloat on checkpoint resume (the documented LangChain/Gemini-CLI bug) unless compaction emits a `RemoveMessage`-style state rewrite. The only open call is the offload format for dropped content (file vs long-term memory).

---

## 7. Verification (design-level; concrete commands in §8)

- **Unit (L1/L2):** message-compaction preserves task + pinned constraints; token-count strictly decreases; deterministic 10×; failure-paths-first (empty history, all-pinned, single-turn).
- **Eval probe (C2):** `agentsframework-eval-probe` on the compaction seam — L1 deterministic constraint-preservation (hard gate) + L2 sampled judge on summary fidelity + token-reduction ratio reported.
- **Architecture:** `pytest tests/architecture` — I-4/I-5/I-7 hold for the new `services/` logic and the thin `orchestration/` reader.
- **Governance:** the compaction carrier is content-free (audit a representative trace); drift-guard green (no `default_spec()` change).
- **Live (on-demand):** a tagged `--no-traffic` revision with `CONTEXT_COMPACT_MESSAGES=true` on a long multi-turn corpus; assert token-per-run drops and no constraint-loss regression (extend the multi-session harness).

---

## Critical files (design map)

- `services/summarizer.py` — extend from trajectory→message-history compaction (B1); add the pinned-facts floor (B2).
- `orchestration/react_loop.py:1581` (`call_llm_node` message stacking) + `:2044` (compaction trigger site) — the seam to compact `messages`, not just `reasoning_trace`.
- `orchestration/state.py` — `messages`, `reasoning_trace`, `current_token_count`, `truncation_applied`; the budget/tier signals (B3).
- `components/memory_context.py` — reuse `filter_recall_records`/`render_recall_block` as the warm-tier formatter (B3).
- `services/long_term_memory.py` — `consolidate()` + `MemoryRecord.metadata` for decay/strengthening (B4); reuse the `safety_floor` pattern for B2.
- `services/base_config.py` + `middleware/composition.py` — new `CONTEXT_*` flags, threaded like the memory flags.
- `services/governance/` — a content-free compaction carrier (clone the `memory_consolidation_carrier.py` shape).

## Out of scope (recorded)
OKF knowledge-plane "compression" (separate surface, not chosen); A-MEM note-graph linking (no demand; flat store sufficient); a tokenizer dependency in `services/` (use API `usage_metadata` like A1 avoided tiktoken); promoting any flag to live-traffic prod (no `--tag` here, on request only); committing.

---

# 8. Executable implementation plan — C1 + C2 (the B1 slice)

> Grounded in the B1-R research (§B1-R) and verified against live code. §1–§7 are the design-space map; **this section is what to build.** Reflects the research's re-ordering: **observation-clearing first (deterministic, no LLM), then the structured fold, then the eval gate.** Default-OFF, prod byte-identical until a tagged revision.

## Why this is the right slice (Context)

`services/summarizer.py` compacts `reasoning_trace` (cheap, append-only, ~bounded) and **never touches `state["messages"]`** — the dominant token driver re-sent in full every lap (`react_loop.py:1583`). The external evidence (§B1-R) says the highest-leverage, lowest-risk first move is **not** prose summarization but **clearing old tool-observation content** (The Complexity Trap, NeurIPS 2025: ~half the cost, *beats* LLM-summary on solve rate, fully deterministic). Two correctness traps must be respected or the work is worse than useless: compaction **must rewrite checkpointed state** (append-only `messages` re-bloats on resume — documented LangChain bug deepagents#2876) and must fire **rarely in big batches** (per-turn trimming shatters the KV-cache prefix and can negate the savings).

## Verified live anchors (from code)

- `react_loop.py:1581-1583` — `existing_messages = state.get("messages", [])` then `[SystemMessage(system_prompt)] + list(existing_messages)`. The full-history stack. **Read-side seam.**
- `react_loop.py:2044-2059` — the *only* live compaction trigger; sets `result["reasoning_trace"]`/`result["files"]`/`truncation_applied`, **never `result["messages"]`**. **Write-side seam** (this node returns a state-update dict → correct place to emit `RemoveMessage`).
- `react_loop.py:349, 477` — `ToolMessage(content=message_output, tool_call_id=tool_id)`. The `content` field + `tool_call_id` are exactly what observation-masking replaces/keys on.
- `services/base_config.py:20` `context_window: int` (= `128000` at :163) — real field for the fraction trigger; **no new config to read the window.**
- `services/base_config.py:39` `trajectory_compaction_token_threshold: int = 3000` — the flat threshold to supersede.
- `services/summarizer.py` — `should_compact_trajectory` + `build_compaction_summary`; extend, don't replace.

## C1 — Step by step

### Step 1 — `services/summarizer.py`: add deterministic, pure message-compaction (no LLM)

Add four pure functions (framework-clean, I-4; unit-testable; no `langchain` import — operate on a minimal typed view, see Step 2):

1. **`mask_old_observations(messages, *, keep_last_m=10, placeholder=...)`** — the Complexity-Trap mechanism. For each tool-observation older than the last `M` turns, replace its **content** with a fixed placeholder (e.g. `"[observation cleared — {n} chars omitted; tool={name}]"`); leave reasoning/assistant/human messages **untouched**. `M=10` is the ablated optimum (5 underperforms, 20 degrades — §B1-R R1). Content-free by construction (we drop text, we don't relocate it into a carrier).
2. **`find_safe_cutoff(messages, keep_last_k)`** — port LangChain's `_find_safe_cutoff_point` (§B1-R R3): if the cutoff lands on a tool-result, walk back to include the AIMessage that issued the matching `tool_call_id`s, so a tool call is **never orphaned** from its result. Preserve any system message.
3. **`build_message_compaction(messages, *, keep_last_k, pinned)`** → returns the structured fold for the dropped prefix using the LangChain bucket schema (§B1-R R3/R7, keep structure — no opaque blob): `SESSION INTENT / SUMMARY (decisions, rejected options) / ARTIFACTS (files+paths) / NEXT STEPS`, plus a **PINNED** block (B2) of atomic, polarity-tagged constraint strings copied verbatim and never summarized. Deterministic extract first (B1-det); the LLM variant is v1.5.
4. **`build_constraint_floor(pinned, *, polarity_filter="must-not")`** (B2, §B2-R S2/S5) → a compact verbatim `SystemMessage`-content string for **tail re-injection** (recency-slot defense against attentional dilution). Filters to the fragile `must-not` class by default (§B2-R S1). Pure; rendered independent of compaction.

Keep the existing trajectory functions; the new ones are additive.

### Step 2 — message-shape adapter (keep `services/` framework-clean, I-4/I-5)

`summarizer.py` must not import `langchain_core`. Define a tiny stdlib view (`role`, `content`, `tool_call_id`, `tool_calls`) and convert at the boundary in `orchestration/`. Mirrors how A1 kept `long_term_memory.py` framework-clean. The orchestration adapter maps `BaseMessage` ↔ this view and back.

### Step 3 — trigger: fraction-of-window + dual thresholds + cooldown (`base_config.py`)

Supersede the flat `3000` (§B1-R R2/R6). Add config (defaults chosen to be **no-op vs today** when the flag is off):
- `context_compact_messages_enabled: bool = False` (master flag, `CONTEXT_COMPACT_MESSAGES`).
- `context_compact_trigger_fraction: float = 0.6` — compact reasoning history at 60% of `context_window`.
- `context_observation_clear_fraction: float = 0.3` — clear observations earlier (obs ≪ history, ACON).
- `context_keep_last_k: int = 10` (`CONTEXT_KEEP_LAST_K`) — verbatim recent turns / mask window M.
- `context_compact_cooldown_steps: int = 5` — hysteresis; no re-compaction within K steps of the last fold (R6, prefix stability).
- `context_constraint_reinject_turns: int = 0` (`CONTEXT_CONSTRAINT_REINJECT_TURNS`) — B2 tail re-injection cadence; 0 = off. **Calibrate to the model's Safe Turn Depth** (§B2-R S1/S6: ~7 Qwen-class, ~10 Mistral-class). Note `context_compact_trigger_fraction` should likewise be set at/below the model's safe-token-budget, not picked arbitrarily (§B2-R S6).

Add `compaction_trigger_tokens(context_window, fraction)` helper (pure). Keep `trajectory_compaction_token_threshold` for the unchanged trajectory path.

### Step 4 — wire the write-side state rewrite (`react_loop.py:2044`)

Gate on the new flag. When `context_compact_messages_enabled` AND token-count ≥ fraction trigger AND cooldown elapsed:
1. `masked = mask_old_observations(view(messages), keep_last_m=K)` (cheap path; may be enough).
2. If still over the history fraction: `cutoff = find_safe_cutoff(masked, K)`, `summary = build_message_compaction(masked[:cutoff], keep_last_k=K, pinned=...)`.
3. **Emit the state rewrite** (the R4 fix — the part the LangChain bug got wrong):
   ```python
   result["messages"] = [
       RemoveMessage(id=REMOVE_ALL_MESSAGES),
       SystemMessage(content=summary),          # structured buckets + PINNED floor (head copy)
       *preserved_recent,                        # last-K verbatim, pairs intact
       SystemMessage(content=constraint_floor),  # §B2-R S2: tail re-injection (recency) — do-not rules
   ]
   ```
   This makes the **checkpointer reload the compacted transcript** — no resume re-bloat. The floor appears at **both** head and tail (§B2-R S2 double-reinforcement); the tail copy is the live-defense against attentional dilution. Record `last_compaction_step` in state for the cooldown. Keep the existing `reasoning_trace`/offload write for the dropped text (file offload, not a carrier).
4. Set `truncation_applied=True`; stamp `tokens_before`/`tokens_after`/`turns_folded`/`pinned_kept` for the carrier (Step 6).

### Step 5 — anti-truncation floor (B2): two defenses, not one

The §B2-R research splits B2 into **two distinct loss channels**, each needing its own mechanism. Both are pure `services/summarizer.py` logic (I-4), no LLM.

**5a — Structural floor (defends against *compaction* loss).** Source the pinned set from `state["task_understanding"]` success-conditions + explicit user constraints (already in state). Build it as a list of **atomic, verbatim constraint objects** (one rule per string, compound rules split), each **polarity-tagged** `must-do` / `must-not` (§B2-R S1/S3). `build_message_compaction` copies them **verbatim** into a `PINNED` block — never paraphrased into prose. Post-condition: every pinned string is an exact substring of the fold output (hard invariant, like the memory `safety_floor`).

**5b — Tail re-injection (defends against *attentional-dilution* loss).** New pure fn `build_constraint_floor(pinned, *, polarity_filter="must-not")` → a compact `SystemMessage` rendered at the **tail** of assembled context (recency slot, §B2-R S2), re-emitted every `context_constraint_reinject_turns` turns **regardless of whether a fold happened** (§B2-R S5 — a short thread that never compacts can still violate a do-not rule by turn ~20). Prioritizes `must-not` constraints (the fragile class, §B2-R S1). This is a *separate* trigger from compaction; it binds at the read-side seam (`react_loop.py:1581-1583`), appending the floor after `existing_messages`.

**5c — Fail-loud protection hierarchy (§B2-R S4, CWL).** If last-K verbatim + the pinned floor *still* exceed budget, do **not** silently drop a constraint — emit a `CONTEXT_FLOOR_EXCEEDED` signal on the carrier (Step 6) and decline to over-compact (keep the floor, accept the overrun). The floor is the inviolable tier; user-authored constraints + success-conditions are never evictable. This is the named precedent for our "never calibrate away a dropped safety constraint" hard-zero.

**Config (added in Step 3):** `context_constraint_reinject_turns: int = 0` (0 = off; calibrate to the model's Safe Turn Depth, §B2-R S1 — e.g. ~7 for Qwen-class, ~10 for Mistral-class). Default 0 keeps prod byte-identical.

### Step 6 — governance carrier (content-free), cloning the consolidation shape

Emit a `CONTEXT_COMPACTED` carrier with **counts only** (`tokens_before/after`, `turns_folded`, `observations_cleared`, `pinned_kept`, `keep_last_k`, plus B2: `constraint_floor_count`, `must_not_count`, `floor_reinjected` bool, `floor_exceeded` bool from §B2-R S4) — **never the dropped text or the constraint strings**, mirroring `services/governance/memory_consolidation_carrier.py`. Non-required enrichment (no `default_spec()` change) → drift-guard stays green.

## C2 — the eval gate (the research's consensus "probe", as a hard gate)

`agentsframework-eval-probe` on the compaction seam, two layers:
- **L1 deterministic (hard gates, CI):** (a) every pinned constraint string is an exact substring post-fold — checked **per-constraint, polarity-aware**, with `must-not` constraints additionally present in the **tail** floor (§B2-R S1/S2); (b) summary non-empty (the Gemini-CLI `COMPRESSION_FAILED_EMPTY_SUMMARY` guard, §B1-R R5); (c) `tokens_after < tokens_before` strictly; (d) no orphaned tool-result (every ToolMessage in the kept slice has its AIMessage); (e) **fail-loud**: when the floor can't fit budget, `floor_exceeded` is set and compaction is declined rather than dropping a constraint (§B2-R S4). **Any failure = block / fall back to no-compaction** (fail-safe, like the memory enable-policy).
- **L2 sampled judge (reported, not gated v1):** summary fidelity vs the dropped prefix (did a decision/constraint silently vanish — the context-rot failure, R7); token-reduction ratio. Feeds the B1-llm prompt calibration later (contrastive failures → ACON-style prompt tuning, R8).

## Verification (end-to-end)

```bash
# L1/L2 unit — failure-paths-first
OTEL_SDK_DISABLED=true LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" \
  .venv/bin/python -m pytest tests/services/test_summarizer.py -q     # mask/cutoff/fold/pinned
# four-layer invariants hold for new services/ logic + thin orchestration reader
.venv/bin/python -m pytest tests/architecture -q                      # I-4/I-5/I-7
# flag OFF ⇒ byte-identical to today
.venv/bin/python -m pytest tests/orchestration/test_react_loop.py -q
```
- **Determinism:** mask/cutoff/fold run 10× identical; empty history, single-turn, all-pinned, no-tool-results edge cases.
- **State-rewrite proof:** assert post-compaction `state["messages"]` length drops and a checkpoint round-trip reloads the *compacted* list (guards the R4 re-bloat bug directly).
- **Governance:** audit one trace — carrier is counts-only; drift-guard green.
- **Live (on-demand, separate):** tagged `--no-traffic` rev, `CONTEXT_COMPACT_MESSAGES=true`, long multi-turn corpus (extend the multi-session harness); assert tokens-per-run drops, prompt-cache hit-rate doesn't collapse (R6), zero pinned-constraint loss.

## Build order (smallest reversible steps)

1. `summarizer.py` pure fns + unit tests (mask → safe-cutoff → fold → pinned) — **no wiring, no behavior change.**
2. `base_config.py` flags/helpers (all default-OFF/no-op).
3. `react_loop.py` write-side rewrite behind the flag + the message-view adapter.
4. Governance carrier (counts-only) + its audit test.
5. C2 eval-probe L1 hard gates; L2 reported.
6. (Separate, on request) tagged live validation.

## Deferred to v1.5+ (seams left, not built)
- **B1-llm:** cheap/distilled-tier summarizer for prose turns; prompt calibrated from C2 contrastive failures (ACON, R8). The fold function takes a pluggable summarizer arg so this is a swap, not a rewrite.
- **B3 tiered assembly / B4 decay / B5 in-loop retrieval** — unchanged from §4.
