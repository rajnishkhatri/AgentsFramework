# Open-Weight, API-Hosted LLMs for Reliable Tool Calling in Agentic Loops (Mid-2026)

## TL;DR
- For an open-source multi-agent framework optimizing tool-calling reliability, cost, and latency, the three best picks are **DeepSeek V4 Flash** (best cost-to-reliability ratio, via DeepInfra or DeepSeek's own API with a 98% prompt-cache discount), **gpt-oss-120b on Cerebras or Groq** (best latency/throughput for fast inner-loop tool calls, 1,971 t/s on Cerebras per Artificial Analysis), and **Kimi K2.6 / GLM-5.2-class models** (best raw agentic tool-calling reliability, with K2.6 at exactly 96% on τ²-bench Telecom and GLM-5.2 leading at 99.1%).
- Tool-calling reliability is now dominated by Chinese open-weight labs: GLM-5.2 leads τ²-bench Telecom at 99.1%, GLM-4.5 leads BFCL v3 at 76.7% (77.8% on llm-stats' combined metric), and Kimi, MiniMax, and DeepSeek all post frontier-adjacent agentic scores at 10-100x lower cost than closed models.
- Provider choice matters as much as model choice: native OpenAI-compatible `tools` support is now near-universal across DeepInfra, Fireworks, Together, Groq, Cerebras, SambaNova, Novita, and OpenRouter, but real-world tool-call reliability and prompt-caching support vary materially, and Groq has documented intermittent tool-call validation failures (HTTP 400) under some agent frameworks.

## Key Findings

1. **The open-weight tool-calling field is deep and cheap in mid-2026.** At least eight model families are credible: DeepSeek (V4 Pro/Flash, MIT), Qwen (Qwen3.x, Apache-2.0), GLM/Zhipu (GLM-4.6/5/5.1/5.2, MIT), Kimi/Moonshot (K2/K2.6, Modified-MIT), MiniMax (M2/M2.5, MIT/Modified-MIT), Llama (community license), Mistral (Apache-2.0 small models; Devstral for agentic), and OpenAI gpt-oss (Apache-2.0). All are served through OpenAI-compatible hosted APIs.

2. **Benchmark leadership on agentic tool use is concentrated.** On τ²-bench Telecom, GLM-5.2 leads at 99.1%, with GLM-5 at 98.2%, GLM-5.1 and Qwen3.6 Plus at 97.7%, DeepSeek V4 Pro (Max) at 96.2%, and Kimi K2.6 at exactly 96%. On BFCL v3, GLM-4.5 leads at 76.7% (Artificial Analysis figure; 77.8% on llm-stats' single+multi-turn metric, top of 19 models), with Qwen3 32B at 75.7% and Kimi K2 at 71.1%. Kimi K2 Thinking posted 93% on τ²-bench Telecom, which Artificial Analysis describes verbatim as "the highest score we have independently measured," 6 points ahead of GPT-5 Codex (87%) and MiniMax-M2 (87%).

3. **Cost floor is extraordinarily low.** DeepSeek V4 Flash is $0.14 input / $0.28 output per 1M tokens, with cache hits at $0.0028/M (a 98% discount). gpt-oss-120b runs $0.15/$0.60 on Groq, and DeepInfra is the cheapest of 20 benchmarked providers at $0.05/1M blended ($0.04/1M input). These are roughly 35-100x cheaper than closed frontier models per token.

4. **Specialized silicon transforms agentic loop responsiveness.** Per Artificial Analysis, Cerebras serves gpt-oss-120b at 1,971 t/s with 1.57s time-to-first-token, with Fireworks at 749 t/s and SambaNova at 693 t/s. GPU-based providers (DeepInfra base tier, Together) typically run far slower per token but offer broader catalogs and prompt caching.

5. **Native tool-calling syntax is now table stakes, but reliability is not uniform.** DeepInfra, Fireworks, Together, Groq, Cerebras, SambaNova, Novita, and OpenRouter all expose the OpenAI-compatible `tools` parameter. However, Groq has documented intermittent 400 errors ("Failed to call a function") under some agent harnesses, and some models require `tool_choice: required` to fire reliably.

## Details

### Candidate Model Inventory (mid-2026)

| Model | Lab | License | Params (total/active) | Tool-calling reputation |
|---|---|---|---|---|
| DeepSeek V4 Pro | DeepSeek | MIT | 1.6T / 49B | Frontier-adjacent agentic; 128 parallel calls |
| DeepSeek V4 Flash | DeepSeek | MIT | 284B / 13B | Best cost-to-capability; agentic index 65.3 |
| Qwen3-235B-A22B (2507) | Alibaba | Apache-2.0 | 235B / 22B | Strong, well-supported tool parsers |
| Qwen3-Coder-480B / Next | Alibaba | Apache-2.0 | 480B / 35B | Agentic coding specialist |
| GLM-4.6 | Zhipu/Z.ai | MIT | MoE, 200K ctx | Strong agentic, integrates well in frameworks |
| GLM-5 / 5.1 / 5.2 | Zhipu/Z.ai | MIT | 744B / 40B | τ²-bench Telecom leaders |
| Kimi K2 / K2.6 | Moonshot | Modified-MIT | 1T / 32B | Best agentic stability, long-horizon |
| MiniMax M2 / M2.5 | MiniMax | MIT/Mod-MIT | 230B / 10B | Agentic tool-use specialist, very efficient |
| Llama 4 Scout/Maverick | Meta | Llama community | MoE | Long context; broad provider support |
| Mistral Small 3.x / Devstral | Mistral | Apache-2.0 | 24B dense | Low-latency function calling; Devstral best for agents |
| gpt-oss-120b | OpenAI | Apache-2.0 | 117B / 5.1B | Native tool use; fast inner-loop model |

### Tool-Calling Capability Assessment

**τ²-bench (tau2-bench)** measures policy-adherent, multi-turn tool use across airline, retail, and telecom domains, and is the single most relevant eval for agentic reliability (an agent that completes a task but violates a stated policy fails). Telecom scores (Artificial Analysis / BenchLM):

| Model | τ²-bench Telecom | Notes |
|---|---|---|
| GLM-5.2 | 99.1% | Current leader |
| GLM-5 | 98.2% | |
| GLM-5.1 / Qwen3.6 Plus | 97.7% | |
| DeepSeek V4 Pro (Max) | 96.2% | |
| Kimi K2.6 | 96% | Per Kili Technology, citing Moonshot blog |
| Kimi K2 Thinking | 93% | "Highest score we have independently measured" — Artificial Analysis |
| MiniMax M2 | 77.2 (self-reported τ²-Bench) | llm-stats reports 87.0% telecom-specific |
| Qwen3-235B-A22B Instruct 2507 | 33% | Older generation |

**BFCL (Berkeley Function Calling Leaderboard)** measures call-level accuracy (simple, multiple, parallel, multi-turn via AST evaluation). BFCL v3:

| Model | BFCL v3 | Source |
|---|---|---|
| GLM-4.5 | 76.7 (AA) / 77.8 (llm-stats) | Leaderboard / vendor report |
| Qwen3 32B | 75.7 | Leaderboard |
| Kimi K2 | 71.1 | GLM-4.5 report comparison table |
| Qwen3-235B-A22B | 70.8 | Qwen report |

Key structural insight: BFCL multi-turn scores drop 5-10 points versus single-turn for every model. If your agent makes 5+ sequential tool calls per task, effective accuracy compounds the multi-turn score, not the headline. Tau-bench tests task-level completion across a chain; BFCL tests call-level correctness. Use both lenses.

DeepSeek V4 specifically addresses a multi-step agentic failure mode: V3.2 flushed reasoning context between tool invocations, so each tool call restarted reasoning from scratch; V4 retains chain-of-thought across the full workflow, materially improving long multi-step pipelines. V4 supports up to 128 functions in a single call with parallel execution. On the extreme end of long-horizon capability, Moonshot states verbatim that Kimi K2 Thinking "can execute up to 200-300 sequential tool calls without human interference, reasoning coherently across hundreds of steps."

### Hosted API Provider Mapping

| Provider | Native `tools` | Prompt caching | Catalog breadth | Notable |
|---|---|---|---|---|
| DeepInfra | Yes | Yes (explicit cached input) | Widest open catalog | Cheapest per-token; $0.05 blended gpt-oss |
| Fireworks | Yes | Yes (automatic, serverless) | Broad; fine-tuning | Adaptive speculative decoding; HIPAA/SOC2 |
| Together AI | Yes | Limited | Broad; fine-tuning | SLA-backed; dedicated GPUs |
| Groq | Yes | N/A | Narrow (curated) | Fastest TTFT; documented intermittent 400 tool errors |
| Cerebras | Yes | N/A | Narrow (~4-15 models) | Highest throughput (1,971 t/s gpt-oss) |
| SambaNova | Yes | N/A | Narrow | 693 t/s gpt-oss; serves largest models on few chips |
| Novita | Yes | N/A | Broad | Low cost |
| OpenRouter | Yes (normalized) | Passthrough | 400+ models, 60+ providers | Tool Call Error Rate tracking; failover routing |
| DeepSeek (official) | Yes | Yes (automatic, 98% discount) | DeepSeek only | OpenAI + Anthropic compatible |

OpenRouter is notable for agentic frameworks because it tracks a per-provider **Tool Call Error Rate** on each model page and uses it for "Auto Exacto" provider ordering, plus provider failover that hides mid-trajectory provider failures from the agent.

### Cost Analysis (per 1M tokens, mid-2026)

| Model | Provider | Input | Output | Cache hit |
|---|---|---|---|---|
| DeepSeek V4 Flash | DeepSeek official | $0.14 | $0.28 | $0.0028 |
| DeepSeek V4 Flash | DeepInfra | $0.10 | $0.20 | — |
| DeepSeek V4 Pro | DeepInfra | $1.30 | $2.60 | $0.10 |
| DeepSeek V4 Pro | Fireworks | $1.74 | $3.48 | $0.145 |
| gpt-oss-120b | Groq | $0.15 | $0.60 | — |
| gpt-oss-120b | DeepInfra | $0.04 ($0.05 blended) | — | — |
| gpt-oss-120b | Cerebras | $0.35 | $0.75 | — |
| Kimi K2.6 | DeepInfra | $0.75 | $3.50 | — |
| Kimi K2.6 | Fireworks | $0.95 | $4.00 | — |
| GLM-5.1 | DeepInfra | $1.05 | $3.50 | $0.205 |
| GLM-5.2 | DeepInfra/OpenRouter | ~$1.20 | ~$4.10 | — |
| Qwen3.6 Plus | Together/Fireworks | $0.50 | $3.00 | — |
| MiniMax M2 | MiniMax | $0.30 | $1.20 | — (blended $0.39 at 7:2:1) |

Under agentic load the sticker price misleads. Two levers dominate effective cost:

1. **Prompt caching.** Agent loops resend large stable prefixes (system prompt, tool definitions, codebase context), so cache-hit pricing matters more than headline input price. DeepSeek's automatic cache discount drops V4 Flash input from $0.14 to $0.0028/M (a 98% reduction with no configuration), and DeepInfra exposes an explicit cached-input tier (e.g., $0.205/M on GLM-5.1). Teams paying the least are not negotiating volume discounts; they are engineering cache-hit rates above 70-80% by keeping prefixes byte-for-byte identical.

2. **Output verbosity.** Reasoning/thinking tokens bill at the output rate. Artificial Analysis notes MiniMax M2 "is very verbose, using 120M tokens to complete our Intelligence Index evaluations - equal highest along with Grok 4," so a cheap per-token model can be expensive per task. DeepSeek thinking mode is on by default and can silently inflate output cost; disable it for routine tool calls.

### Latency and Throughput Analysis

| Provider | gpt-oss-120b output speed | TTFT |
|---|---|---|
| Cerebras | 1,971 t/s | 1.57s |
| Fireworks | 749 t/s | — |
| SambaNova | 693 t/s | ~4.18s |
| Together AI | — | ~3.97s |
| Baseten | — | 0.27s (lowest) |
| DeepInfra (base) | ~43 t/s | 0.48s (Turbo tier) |

For real-time agentic loops, throughput compounds across every sequential tool-call turn. A 10-step agent loop on a 60 t/s provider versus a 1,000+ t/s provider is the difference between a sluggish and a snappy agent. Cerebras leads raw throughput; Groq leads consistent low TTFT; SambaNova serves the largest MoE models on the fewest chips. The catch is catalog: Groq and Cerebras serve only models explicitly ported to their silicon (Llama variants, gpt-oss, Kimi K2, Qwen3 32B/235B, GLM-4.7), so the largest or newest flagships may not be available there.

### Trade-off Reasoning

- **Cheapest:** DeepSeek V4 Flash. Frontier-class agentic index (65.3) at the lowest price floor, with near-free cached input. The risk is that it is a recent (April 2026) release with many third-party agentic numbers not yet independently verified, and default thinking mode inflates output tokens.
- **Most reliable tool-caller:** GLM-5.2 / Kimi K2.6. GLM-5.2 leads τ²-bench Telecom (99.1%) and Kimi K2.6 (96%) is specifically praised for recoverable failure modes and consistent tool calling across long sessions. These cost more per token and are larger/slower.
- **Fastest:** gpt-oss-120b on Cerebras (1,971 t/s). Native tool use, Apache-2.0, cheap, ubiquitous provider support. The trade-off: it trails on heavy multi-step agentic coding, and OpenAI never published a numeric BFCL or τ²-bench Telecom score for it (only τ1 Tau-Bench Retail 67.8 / Airline 49.2 from the model card, plus a qualitative "matches o4-mini on TauBench"). Treat it as a fast inner-loop executor paired with a stronger orchestrator.
- **Sweet spot:** DeepSeek V4 Flash on DeepInfra (or DeepSeek's own API for cache economics) as the default agent model, escalating hard steps to GLM-5.2 or Kimi K2.6, and routing latency-critical short tool calls to gpt-oss-120b on Cerebras/Groq.

## Recommendations

**Stage 1 — Default build (start here).** Use **DeepSeek V4 Flash** as the framework's default tool-calling model, served via **DeepInfra** ($0.10/$0.20) for breadth and explicit caching, or via **DeepSeek's official API** when your workload reuses large stable prefixes (the automatic 98% cache-hit discount is the single biggest cost lever for agent loops). It is MIT-licensed, OpenAI- and Anthropic-compatible, supports parallel function calling and JSON mode, has a 1M context, and retains chain-of-thought across tool calls. Benchmark threshold to escalate: if your domain eval shows multi-turn tool-call success below ~85%, or tasks routinely exceed ~8 sequential calls, move to Stage 2 for those task types.

**Stage 2 — Reliability tier for hard tasks.** Route complex, long-horizon, or policy-sensitive trajectories to **Kimi K2.6** (Modified-MIT; 96% τ²-bench Telecom; best-regarded for recoverable failure modes) or **GLM-5.2** (MIT; 99.1% τ²-bench Telecom leader). Serve via DeepInfra (cheapest) or Fireworks (fastest GPU-based). Use a router that escalates only when Flash output quality falls short; do not send all traffic here or you forfeit the cost advantage.

**Stage 3 — Latency-critical inner loop.** For high-frequency, short tool calls where loop responsiveness dominates (real-time agents, voice, rapid retrieval chains), use **gpt-oss-120b on Cerebras** (1,971 t/s, 1.57s TTFT) or **Groq** ($0.15/$0.60, lowest consistent TTFT). Pair it with a stronger orchestrator from Stage 1/2. Mitigate Groq's documented intermittent tool-call 400 errors by setting `tool_choice` explicitly, adding retry-with-lower-temperature logic, or fronting the stack with OpenRouter for automatic provider failover and Tool Call Error Rate-aware routing.

**Cross-cutting:**
- Default to **OpenRouter** as the integration layer if you want one API key, normalized `tools` syntax, failover, and per-provider tool-call reliability telemetry; go direct to DeepInfra/DeepSeek when you want to capture the maximum cache discount.
- Structure every prompt with static content (system prompt, tool definitions) first and variable content last, byte-for-byte stable, to maximize cache-hit rates.
- Disable thinking mode for routine tool calls to avoid paying output rates for invisible reasoning tokens.
- Pin model versions; the field is moving fast and licenses differ. Verify Kimi/MiniMax Modified-MIT redistribution clauses if you redistribute.

## Caveats
- **Benchmark provenance.** Many τ²-bench Telecom and agentic-index figures are vendor-reported or from aggregators (BenchLM, llm-stats, Artificial Analysis) rather than independent reruns. DeepSeek V4 and GLM-5.x numbers in particular derive largely from April 2026 vendor reports. Always run a domain-matched eval on your own tool schemas before committing.
- **Conflicting numbers.** MiniMax M2 τ²-bench appears as both 77.2 (MiniMax self-report, likely a multi-domain average) and 87.0% (llm-stats, telecom-specific). Kimi K2 τ² appears as 66.1 (K2 report, non-thinking), 84.7 (a later non-thinking variant), 93% (K2 Thinking), and 96% (K2.6) — these are different model versions and must not be conflated. Artificial Analysis Intelligence Index versions are not comparable across releases (v4.0 included τ²-Telecom and placed K2.6 at 54; v4.1 swapped to τ³-Banking).
- **gpt-oss-120b gap.** No vendor numeric BFCL or τ²-bench Telecom score exists for gpt-oss-120b; its agentic standing rests on τ1 Tau-Bench and qualitative claims. It is a strong fast/cheap executor but not a verified top-tier agentic orchestrator.
- **Provider quantization.** Cheapest routes (e.g., DeepInfra, some GLM-5.2 hosts) may serve fp4-quantized weights versus fp8 elsewhere; for tool-calling fidelity, test your task before optimizing purely on price.
- **Effective context.** Advertised context windows (1M+) are not fully usable; RULER-style evals show models reliably use only ~50-65% of advertised context, which matters for long agent trajectories.
- **License nuance.** Llama (community license) and Qwen/Kimi/MiniMax restricted-open-weight licenses are fine for a GitHub framework but carry redistribution/attribution conditions (e.g., Kimi K2.6 requires UI attribution above 100M MAU or $20M monthly revenue). True OSI-approved options are Apache-2.0 (Qwen3, gpt-oss, Mistral small, MiniMax M2) and MIT (DeepSeek, GLM-5.x).