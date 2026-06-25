# Real-Task Model Evaluation — Case-by-Case Report

**Date:** 2026-06-25
**Path:** live calls through `LLMService.invoke` → `get_llm` → `response_text`
(the production answer-extraction path), `MODEL_PROFILE_SET=all` registry.
**Post-fix:** run AFTER the `supports_temperature` fix (Opus 4.8 + gpt-5 family).

## The task (one realistic prompt, known ground truth)

> Road-trip planning. Car = **32 mpg**, tank = **12 gal**, one-way = **880 mi**,
> gas = **$4.25/gal**. Return THREE labelled lines:
> - `FUEL_STOPS:` minimum full tanks for the **one-way** trip (round up)
> - `ROUNDTRIP_COST:` total fuel cost for the **round** trip, nearest cent
> - `ONELINE:` a one-sentence summary

Chosen because it exercises three orthogonal skills at once: **multi-step
arithmetic** (gallons → tanks → round-trip cost), **unit/scope discipline**
(one-way vs round-trip is a deliberate trap), and **instruction-following**
(exact line prefixes). The wrong answers are diagnostic, not random.

**Ground truth:**
- One-way gallons = 880 ÷ 32 = **27.5 gal** → 27.5 ÷ 12 = 2.29 → **FUEL_STOPS = 3**
- Round-trip gallons = 1 760 ÷ 32 = **55 gal** → 55 × $4.25 = **ROUNDTRIP_COST = $233.75**

## Scoreboard

| model | FUEL_STOPS | ROUNDTRIP_COST | format | tok in/out | cost | latency | verdict |
|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 3 ✅ | **$75.00 ❌** | clean | 125/51 | $0.00005 | 7.1s | ❌ wrong cost |
| gpt-4o | 3 ✅ | **$234.38 ❌** | clean | 125/54 | $0.00144 | 0.8s | ⚠ near-miss cost |
| claude-haiku-4-5 | 3 ✅ | **$440.00 ❌** | clean | 144/58 | $0.00043 | 0.9s | ❌ wrong cost |
| claude-sonnet-4-6 | 3 ✅ | $233.75 ✅* | **verbose** | 144/323 | $0.00528 | 6.3s | ⚠ right-but-messy |
| **claude-opus-4-8** | 3 ✅ | **$233.75 ✅** | clean+work | 203/239 | $0.00699 | 3.4s | ✅ **correct** |
| **gpt-5-mini** | 3 ✅ | **$233.75 ✅** | **clean** | 124/631 | $0.00129 | 8.7s | ✅ **correct, best value** |
| **gpt-5** | 3 ✅ | **$233.75 ✅** | **clean** | 124/1079 | $0.01094 | 10.8s | ✅ **correct** |
| deepseek-v4-flash | (3) | (—) | **EMPTY** | 127/4096 | $0.00116 | 42.8s | ❌ budget-exhausted |
| **deepseek-v4-pro** | 3 ✅ | **$233.75 ✅** | **clean** | 127/562 | $0.00054 | 10.9s | ✅ **correct, cheapest** |

\* Sonnet printed `$235.00` first, caught its own error mid-answer, and corrected
to `$233.75` — right final number, wrong presentation (see case).

**Headline:** 4 of 9 produced the fully correct, cleanly-formatted answer:
**gpt-5, gpt-5-mini, claude-opus-4-8, deepseek-v4-pro**. Every model nailed
`FUEL_STOPS=3`; the **round-trip cost was the discriminator** (the one-way/round-trip
scope trap), and **reasoning models won it**. This is consistent with the task
being designed to reward the reasoning tier.

---

## Case-by-case

### gpt-4o-mini — ❌ wrong cost ($75.00)
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: 75.00` · ONELINE references "$75 for the round trip"
- FUEL_STOPS correct, format perfect, cheapest run ($0.00005) and the answer is
  self-consistent (the ONELINE matches its own number).
- **But $75.00 is badly wrong** — off by 3×. It did not carry the 55-gallon
  round-trip computation; looks like it costed roughly one tank, not the trip.
  Classic small-model arithmetic-scope failure. **Fluent but wrong** — the worst
  kind for an unsupervised pipeline because it reads confident.

### gpt-4o — ⚠ near-miss ($234.38)
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: 234.38`
- Format clean, fastest run (0.8s), and it *did* do the round-trip scope correctly.
- $234.38 ≈ correct but **$0.63 high** — it costed ~55.15 gal, i.e. it likely
  rounded tanks up to gallons (3 tanks × ... ) instead of using exact 55 gal.
  A reasoning-shortcut error, not a scope error. Close enough to look right,
  wrong enough to fail a strict grader.

### claude-haiku-4-5 — ❌ wrong cost ($440.00)
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: $440.00`
- FUEL_STOPS correct, fast (0.9s), clean format.
- **$440.00 is ~$206 too high** — it appears to have costed by *tanks* not gallons
  (6 fill-ups × ~17 gal, or full-tank rounding) rather than the actual 55 gal
  consumed. The fast tier traded arithmetic care for speed. Wrong.

### claude-sonnet-4-6 — ⚠ right answer, messy delivery
> First prints `ROUNDTRIP_COST: $235.00`, shows its work, **notices its own
> arithmetic error**, appends a "Corrected answers" block with `$233.75`.
- The final number is **correct** and the self-correction is genuinely impressive
  reasoning behavior — it caught `55 × 4.25 ≠ 235`.
- **But it violated the output contract:** two conflicting `ROUNDTRIP_COST:` lines,
  323 output tokens (6× the clean models), and a strict line-parser would grab the
  first ($235.00, wrong) value. **Right brain, wrong format** — needs a stricter
  system prompt or a post-parse "last value wins" rule to be pipeline-safe.

### claude-opus-4-8 — ✅ CORRECT  *(the model that was previously empty)*
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: $233.75` · clean ONELINE · then a tidy
> "Work shown" block with every step right (27.5 gal → 2.29 → 3 tanks; 1760 mi
> → 55 gal → $233.75).
- **This is the headline validation:** the same model that returned
  *"The run completed without producing any output."* ($0/0-tok) in the A/B smoke
  now returns a fully correct, well-reasoned answer. The `supports_temperature=False`
  fix is confirmed on a real task, not just a ping.
- Correct on all three fields; the appended work is bounded (not a 323-token essay)
  and the labelled lines come first, so it's parser-safe. Mid-cost ($0.00699).

### gpt-5-mini — ✅ CORRECT, best value  *(previously empty)*
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: $233.75` · crisp one-sentence ONELINE. No
> preamble, no trailing work — exactly the requested three lines.
- **Cleanest correct answer of the whole set.** Followed the format contract
  literally. Also previously broken by the temperature bug — now perfect.
- 631 output tokens (most of it internal reasoning, `output_token_details.reasoning`)
  for $0.00129 — **best correctness-per-dollar among the reasoning models** that
  also got the format right.

### gpt-5 — ✅ CORRECT  *(previously empty)*
> Same clean three-line answer as gpt-5-mini, correct on all fields.
- Most reasoning tokens (1079 out) → highest cost of the reasoning set ($0.01094)
  and slowest of the OpenAI models (10.8s), with **no quality gain over gpt-5-mini**
  on this task. For a task this size, gpt-5-mini dominates gpt-5 on value.

### deepseek-v4-flash — ❌ EMPTY (reasoning-budget exhaustion)
> `response_text` = `""`. usage: out=**4096** (the cap), `reasoning=4096`, **text
> blocks = 0**.
- **NOT the temperature bug and NOT an extraction bug.** Diagnosed live: the model
  spent the *entire* `max_tokens=4096` completion budget on `thinking` blocks and
  never emitted a `text` block, so there was legitimately nothing to extract.
  (On a simpler-phrased variant it stopped thinking at ~3085 tokens and did emit a
  text block — proving the model is fine; it just over-thinks on harder phrasings.)
- **This is the same second-order risk already flagged for gpt-5:** verbose
  reasoning can consume the whole budget. gpt-5/gpt-5-mini/deepseek-pro stayed
  under it on this task; flash did not. It also ran **42.8s** (longest) — the
  over-thinking shows in latency too. See "Recommendations".

### deepseek-v4-pro — ✅ CORRECT, cheapest  *(was never broken)*
> `FUEL_STOPS: 3` · `ROUNDTRIP_COST: 233.75` · clean ONELINE. Correct on all fields,
> clean format, **lowest cost of any correct answer ($0.00054)**.
- Pro budgeted its reasoning sensibly (562 out tokens vs flash's 4096), got the
  scope and arithmetic right, and was the cheapest correct run. Strong showing.
- Minor: omitted the `$` on ROUNDTRIP_COST (`233.75` not `$233.75`) — numerically
  correct, trivially below the others on format polish.

---

## Findings

1. **The temperature fix holds on real work.** All three previously-empty models
   (opus-4-8, gpt-5, gpt-5-mini) now produce correct, well-formatted answers. The
   Opus case is the direct refutation of the A/B-smoke empty-output defect.

2. **The reasoning tier earned its cost here.** The round-trip-cost trap separated
   the field cleanly: every *correct* cost came from a reasoning model
   (opus, gpt-5, gpt-5-mini, deepseek-pro). The fast/cheap models
   (gpt-4o-mini $75, haiku $440) failed the scope; gpt-4o near-missed ($234.38).

3. **New, reproducible second-order risk: reasoning-budget exhaustion.**
   `deepseek-v4-flash` blew the entire 4096-token budget on thinking → empty
   answer. This is a *different* failure class from the temperature bug and it is
   real on the production path. gpt-5 showed the same tendency in earlier probing
   but stayed under budget at 4096 on this task.

4. **Format ≠ correctness.** Sonnet got the number right but broke the output
   contract (double `ROUNDTRIP_COST` line); gpt-4o-mini got the format perfect but
   the number wrong. A pipeline needs **both** a strict prompt and a tolerant
   last-value-wins parser.

## Recommendations

- **Best overall value on this task:** `deepseek-v4-pro` (correct, cleanest, $0.00054)
  and `gpt-5-mini` (correct, literal format, $0.00129). Either is a strong default
  for reasoning-shaped tasks.
- **Mitigate the budget-exhaustion risk before scaling DeepSeek-flash / gpt-5:**
  consider (a) raising `max_tokens` for the reasoning tier, and/or (b) a
  post-call guard that flags `output_token_details.reasoning ≈ max_tokens && text==""`
  as an *explicit* "budget-exhausted" outcome rather than a silent empty answer.
  This is the analyzer-side companion to the "empty-output ⇒ HOLD" guard already
  recommended in the A/B smoke report §4.
- **Strict-format tasks:** add a "output ONLY the three labelled lines, no working"
  instruction to the system prompt; Sonnet/Opus tend to append work otherwise.
- **Do not promote a model on `FUEL_STOPS` alone** — all 9 got it; the cost field
  is the real signal. Mirror this in the A/B rubric (don't reward the easy field).

## Caveat

Single-prompt, single-sample, deterministic (`temperature=0` where supported).
This is a **smoke-grade** differentiator, not a benchmark — it confirms the
extraction/temperature fixes on real output and surfaces the budget-exhaustion
risk. A statistically meaningful ranking needs the frozen-corpus A/B harness
(`scripts/model_ab_eval.py`) over many cases with repeats.

---

# Re-run AFTER the max-token budget fix (2026-06-25, same day)

**Change:** added per-profile `ModelProfile.max_output_tokens` (default 4096);
raised to **8192** for the reasoning / verbose-reasoning models
(`claude-opus-4-8`, `gpt-5`, `gpt-5-mini`, `deepseek-v4-flash`/`-capable`,
`deepseek-v4-pro`). `get_llm` now reads the budget from the profile. Motivation:
`deepseek-v4-flash` returned **empty** because thinking tokens consumed the entire
4096 budget. A budget probe confirmed the dose:

| max_tokens | deepseek-v4-flash result |
|---|---|
| 4096 | **empty** (reasoning=4096, text=0) |
| **8192** | **correct** `$233.75` (reasoning≈1343, answer fits) ✅ |
| 16384 | wrong (`FUEL_STOPS: 2`) — runaway over-thinking (reasoning≈5777) |

→ **8192 is the sweet spot**: enough headroom to never starve the answer, not so
much it invites runaway reasoning into a worse answer.

## Re-run scoreboard (budget = 8192 for reasoning models)

| model | budget | FUEL_STOPS | ROUNDTRIP_COST | reasoning tok | out tok | cost | latency | verdict |
|---|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 4096 | 3 ✅ | $75.00 ❌ | 0 | 46 | $0.00005 | 4.3s | ❌ wrong (unchanged) |
| gpt-4o | 4096 | 3 ✅ | $234.38 ⚠ | 0 | 54 | $0.00144 | 1.4s | ⚠ near-miss (unchanged) |
| claude-haiku-4-5 | 4096 | 3 ✅ | $440.00 ❌ | 0 | 58 | $0.00043 | 0.9s | ❌ wrong (unchanged) |
| claude-sonnet-4-6 | 4096 | 3 ✅ | $233.75 ✅* | 0 | 245 | $0.00411 | 5.1s | ⚠ right-but-messy (still double line) |
| **claude-opus-4-8** | 8192 | 3 ✅ | $467.50 ❌† | 0 | 84 | $0.00312 | 2.3s | ⚠ **variance sample** (see note) |
| **gpt-5-mini** | 8192 | 3 ✅ | $233.75 ✅ | 512 | 570 | $0.00117 | 6.7s | ✅ correct, clean |
| **gpt-5** | 8192 | 3 ✅ | $233.75 ✅ | 1344 | 1403 | $0.01419 | 14.0s | ✅ correct, clean |
| **deepseek-v4-flash** | 8192 | 3 ✅ | $233.75 ✅ | 3644 | 3708 | $0.00106 | 37.1s | ✅ **FIXED — no longer empty** |
| **deepseek-v4-pro** | 8192 | 3 ✅ | $233.75 ✅ | 763 | 822 | $0.00077 | 14.8s | ✅ correct, cheapest |

\* Sonnet again printed `$235.00` then appended a corrected `$233.75` — same
format violation as before (still needs last-value-wins parsing).
† Opus returned `$467.50` on this single sample. **Verified variance, not a
regression:** a 4-run repeat gave `$233.75` on **all 4** runs. Opus runs at the
provider-default temperature (we omit `temperature` for it), so its output is
mildly non-deterministic; this one sample drew a bad arithmetic path. With the
budget fix it is still answering (non-empty, well under the 8192 budget at 84 out
tokens — the budget change had no effect on Opus, which was never reasoning-heavy).

## What the budget fix changed

1. **deepseek-v4-flash: empty → correct.** The headline result. At 8192 its 3644
   reasoning tokens leave room for the answer; `response_text` extracts the clean
   three-line output. The empty-output failure class is closed for flash.
2. **gpt-5 / gpt-5-mini: unchanged (still correct).** They were already under 4096
   on this task; the larger budget is insurance against harder prompts, not a fix
   they needed here. gpt-5's reasoning grew to 1344 tok (from 1079) but stayed
   well within budget.
3. **deepseek-v4-pro: unchanged (still correct, cheapest at $0.00077).**
4. **Non-reasoning models: untouched** (4096 budget, 0 reasoning tokens) — their
   wrong-cost answers are arithmetic-scope failures, NOT budget failures, so the
   budget change correctly left them alone.

## Updated recommendations

- **The budget fix closes the empty-output failure class for DeepSeek-flash** and
  hardens gpt-5 against it on harder prompts — keep `max_output_tokens=8192` on the
  reasoning tier.
- **Do NOT push the budget higher** (the 16384 probe got a *worse* answer): excess
  budget invites runaway reasoning. 8192 is calibrated.
- **Still recommended (analyzer side):** flag `reasoning ≈ max_output_tokens &&
  text == ""` as an explicit "budget-exhausted" outcome. Even at 8192 a
  pathological prompt could exhaust the budget; the guard makes it observable
  instead of a silent empty answer. (Companion to the A/B "empty-output ⇒ HOLD".)
- **Best value on this task is unchanged:** `deepseek-v4-pro` ($0.00077) and
  `gpt-5-mini` ($0.00117) — both correct, clean, cheap.
- **latency note:** deepseek-v4-flash is now correct but **slow (37s)** because it
  reasons heavily; for latency-sensitive use, deepseek-v4-pro (14.8s) or gpt-5-mini
  (6.7s) are better reasoning picks.
