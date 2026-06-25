# Together AI vs. Direct Provider — Cost Comparison Report

**Date:** 2026-06-25
**Scope:** The 8 baseline models currently registered in `services/llm_config.py`
**Question:** Is it cheaper to call OpenAI / Anthropic / DeepSeek directly, or to route through Together AI (`TOGETHER_API_KEY`)?

---

## TL;DR / Verdict

**Direct providers win. Do NOT route the current baseline through Together AI.**

1. **Together AI does not host 6 of our 8 models.** It serves **only open-weight models**. GPT-4o, GPT-4o-mini, GPT-5, GPT-5-mini (OpenAI proprietary) and Claude Haiku/Sonnet/Opus (Anthropic proprietary) are **not available on Together at any price** — Together resells *open* OpenAI artifacts (`gpt-oss-120B/20B`, GPT Image, Sora) but **not** the GPT API models, and **zero** Claude models.
2. **For the only overlap — DeepSeek — Together is dramatically more expensive** than DeepSeek's own API: Together's DeepSeek V4 Pro is **~$1.74 / $3.48** per 1M tok vs. our direct DeepSeek cost of **$0.435 / $0.87** — roughly **4× the input, 4× the output**.
3. Together's value is hosting *open models* (Llama 4, Qwen, Kimi, GLM, DeepSeek-as-a-service) for teams without provider keys or who want one unified open-model API. **That is not our situation** — we already hold all three first-party keys and our Auto stacks are built on proprietary tiers.

**Recommendation:** Keep direct provider calls for all 8 baseline models. Only consider Together if we deliberately add an **open-weight arm** (e.g. Llama 4 / Qwen) to the A/B matrix — and even then, compare against direct DeepSeek and other open-model hosts (Fireworks, DeepInfra, Groq), not as a replacement for the proprietary tiers.

---

## The 8 Baseline Models (source: `services/llm_config.py`)

| # | Profile name | litellm_id | Tier | Provider | Direct $/1M in | Direct $/1M out |
|---|---|---|---|---|---|---|
| 1 | `gpt-4o-mini` | `openai/gpt-4o-mini` | fast | OpenAI | $0.15 | $0.60 |
| 2 | `gpt-4o` | `openai/gpt-4o` | capable | OpenAI | $5.00 | $15.00 |
| 3 | `gpt-5-mini` | `openai/gpt-5-mini` | fast | OpenAI | $0.25 | $2.00 |
| 4 | `gpt-5` | `openai/gpt-5` | capable | OpenAI | $1.25 | $10.00 |
| 5 | `claude-haiku-4-5` | `anthropic/claude-haiku-4-5` | fast | Anthropic | $1.00 | $5.00 |
| 6 | `claude-sonnet-4-6` | `anthropic/claude-sonnet-4-6` | capable | Anthropic | $3.00 | $15.00 |
| 7 | `claude-opus-4-8` | `anthropic/claude-opus-4-8` | reasoning | Anthropic | $5.00 | $25.00 |
| 8 | `deepseek-v4-flash` | `deepseek/deepseek-v4-flash` | fast/capable | DeepSeek | $0.14 | $0.28 |
| 8b | `deepseek-v4-pro` | `deepseek/deepseek-v4-pro` | reasoning | DeepSeek | $0.435 | $0.87 |

> Costs converted from the `cost_per_1k_*` fields in the registry (×1000 = per-1M). Flash fills both fast+capable via the `-capable` distinct-name profile, hence "8 models, 9 rows."

---

## Availability on Together AI

| Model | On Together AI? | Notes |
|---|---|---|
| gpt-4o-mini | ❌ No | Proprietary OpenAI API model — not resold |
| gpt-4o | ❌ No | Proprietary OpenAI API model |
| gpt-5-mini | ❌ No | Proprietary OpenAI API model |
| gpt-5 | ❌ No | Proprietary OpenAI API model |
| claude-haiku-4-5 | ❌ No | Together hosts **zero** Anthropic models |
| claude-sonnet-4-6 | ❌ No | Together hosts zero Anthropic models |
| claude-opus-4-8 | ❌ No | Together hosts zero Anthropic models |
| deepseek-v4-flash | ⚠️ Partial | Together lists **V4 Pro**; no standalone "Flash" SKU surfaced |
| deepseek-v4-pro | ✅ Yes | Listed at ~$1.74 / $3.48 per 1M (cached input $0.20) |

**6 of 8 models are simply not purchasable through Together.** Routing them through Together is not an option — it's not a price question, it's an availability question.

---

## Cost head-to-head — the only overlap (DeepSeek)

| Model | Direct DeepSeek $/1M in | Direct $/1M out | Together $/1M in | Together $/1M out | Together premium |
|---|---|---|---|---|---|
| DeepSeek V4 Pro | $0.435 | $0.87 | **$1.74** | **$3.48** | **~4.0× in / ~4.0× out** |
| DeepSeek V4 Flash | $0.14 | $0.28 | n/a (no Flash SKU) | n/a | — |

Even Together's **cached-input** rate ($0.20/1M) is *worse* than DeepSeek-direct's non-cached input ($0.435 only on Pro; Flash is $0.14) once you account for DeepSeek's own automatic prefix caching, which already makes our repeated ReAct prefix near-free at the source.

### Illustrative per-task cost (reasoning tier, ~10k in / 2k out — a typical planning turn)

| Path | Input cost | Output cost | Total / task |
|---|---|---|---|
| DeepSeek V4 Pro **direct** | 10k × $0.435/1M = $0.00435 | 2k × $0.87/1M = $0.00174 | **$0.0061** |
| DeepSeek V4 Pro **via Together** | 10k × $1.74/1M = $0.0174 | 2k × $3.48/1M = $0.00696 | **$0.0244** |

→ **~4× more expensive per task through Together**, for the *same* model.

---

## Why Together is more expensive here (and when it isn't)

- **Together is an inference host for open-weight models.** Its margin is the GPU compute it provisions; it does not get DeepSeek's first-party / volume pricing, so its DeepSeek rate sits well above source.
- **It cannot resell proprietary APIs.** OpenAI's GPT API models and all Anthropic models are closed — Together (like Fireworks/DeepInfra/Groq) can only serve open weights. For closed models the *only* economical path is the provider's own API (or Azure/Bedrock/Vertex enterprise routes).
- **Together becomes attractive only** when you (a) want an **open model** we don't currently run (Llama 4 Maverick $0.27/$0.85, Qwen 3.6, Kimi K2.6, GLM 5.1), (b) lack the first-party key, or (c) want a single unified open-model API. None of these apply to today's baseline.

---

## Recommendation

1. **Keep all 8 baseline models on direct provider calls.** No change to `services/llm_config.py` routing.
2. **Do not add a `together` profile set** for the current models — 6 are unavailable and the 1–2 DeepSeek overlaps cost ~4× more.
3. **If** we want an open-weight A/B arm later, evaluate Together *only* for genuinely open models (Llama 4, Qwen), and **benchmark its DeepSeek price against DeepSeek-direct and 2+ other open hosts** (Fireworks / DeepInfra / Groq) before committing — Together is rarely the cheapest open-model host, just a convenient one.
4. **Cheapest-overall by tier today (all direct):**
   - fast → `deepseek-v4-flash` ($0.14/$0.28) or `gpt-4o-mini` ($0.15/$0.60)
   - capable → `deepseek-v4-flash` again, then `gpt-5` ($1.25/$10)
   - reasoning → `deepseek-v4-pro` ($0.435/$0.87) by a wide margin vs. Opus 4.8 ($5/$25)

---

## Sources

- Together AI Pricing — https://www.together.ai/pricing
- Together AI DeepSeek V4 Pro model page — https://www.together.ai/models/deepseek-v4-pro
- Together AI serverless models (open-weight catalog) — https://docs.together.ai/docs/serverless/models
- Together.ai API pricing guide 2026 — https://www.aipricing.guru/together-pricing/
- DeepSeek official pricing — https://api-docs.deepseek.com/quick_start/pricing
- Open vs closed-source model hosting (Together = open only) — https://deepinfra.com/blog/open-vs-closed-source-ai-models
- Registry costs: `services/llm_config.py` (this repo)
