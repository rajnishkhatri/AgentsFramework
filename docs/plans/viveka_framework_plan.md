---
type: plan
title: 'Viveka Framework — Build Plan'
description: 'Hierarchical Depth Intelligence via Hindu Consciousness Layers'
tags: [plan]
---

# Viveka Framework — Build Plan
**Hierarchical Depth Intelligence via Hindu Consciousness Layers**

---

## 1. Concept Summary

Viveka (विवेक) — discriminative wisdom. The ability to see what is real beneath what is apparent.

The framework applies the Hindu consciousness model (Sthool → Mann → Karan → Atman) as a structured reasoning engine. Any topic, system, organization, or concept is understood by descending through 4 causal layers, then reflecting upward to validate and revise.

The artifact is a **React-powered agentic app** backed by the Claude API, executing a ReAct (Reason + Act) loop at each layer.

---

## 2. Framework Logic

### 2.1 The 4 Layers

| # | Layer | Hindu | Reasoning Question | Output |
|---|---|---|---|---|
| L1 | Gross | Sthool | What is observable? | Facts, events, metrics, surface behaviors |
| L2 | Subtle | Mann | What patterns recur? | Behavioral patterns, strategic tendencies, decisions over time |
| L3 | Causal | Karan | What is causing these patterns? | Root assumptions, structural forces, origin conditions |
| L4 | Invariant | Atman | What has always been true and will remain so? | The irreducible, least-changing core truth |

### 2.2 Descent Trigger Rule

The agent moves from Lₙ → Lₙ₊₁ only when:
> It has formed a causal hypothesis at Lₙ that **cannot be fully explained within Lₙ** — it requires a deeper generative cause.

This prevents shallow descent. Each layer must earn its transition.

### 2.3 Reflection Rule (Bottom-Up Pass)

After L4 is reached, the agent reflects upward in sequence:
- L4 → L3: Does this invariant truth necessitate those root causes? What is coincidental?
- L3 → L2: Do these root causes fully account for those patterns? What remains unexplained?
- L2 → L1: Do these patterns predict those observable facts? What are the anomalies?

**Anomalies that survive all reflection layers = the most important unresolved signals.**

---

## 3. Agentic Loop Design (ReAct Pattern)

Each layer runs the following internal loop:

```
THINK   → What do I know at this layer, given the layer above?
ACT     → Generate analysis and a causal hypothesis
OBSERVE → Can this hypothesis be explained here, or must I go deeper?
REFLECT → Does the inner layer's truth validate or revise what I said here?
```

### 3.1 Context Object (State passed across layers)

```json
{
  "topic": "string",
  "intent": "string",
  "layers": {
    "L1": {
      "status": "pending | running | complete",
      "observations": [],
      "hypothesis": "",
      "anomalies": [],
      "descent_trigger": ""
    },
    "L2": {
      "status": "pending | running | complete",
      "patterns": [],
      "hypothesis": "",
      "L1_reflection": "",
      "anomalies": [],
      "descent_trigger": ""
    },
    "L3": {
      "status": "pending | running | complete",
      "root_causes": [],
      "hypothesis": "",
      "L2_reflection": "",
      "anomalies": [],
      "descent_trigger": ""
    },
    "L4": {
      "status": "pending | running | complete",
      "invariant_truth": "",
      "L3_reflection": "",
      "L2_reflection": "",
      "L1_reflection": "",
      "anomalies_surviving": [],
      "final_output": ""
    }
  }
}
```

---

## 4. System Prompt Architecture

Each layer gets a **dedicated system prompt** passed to Claude API. All prompts share:
- The full context object so far (all layers above)
- The original topic and intent
- Its specific reasoning mandate

### Layer Prompt Templates

**L1 Prompt — Sthool**
```
You are a deep systems analyst operating at the OBSERVATIONAL layer.
Topic: {topic}
Intent: {intent}

Your job:
1. List the most important observable facts, events, outputs, behaviors about this topic.
2. Look only at what is directly visible or measurable.
3. Form a causal hypothesis: what is generating these observations? 
   This hypothesis must point to something you CANNOT explain at this layer alone.
4. Identify any anomalies — facts that don't fit the dominant pattern.

Output as JSON: { observations, hypothesis, anomalies, descent_trigger }
```

**L2 Prompt — Mann**
```
You are operating at the PATTERN layer.
Topic: {topic}. L1 findings: {L1_context}

Your job:
1. Identify recurring patterns, behavioral tendencies, strategic habits that explain the L1 observations.
2. Form a causal hypothesis pointing to what structural force generates these patterns.
3. Reflect on L1: do your patterns fully account for every L1 observation? Flag what remains unexplained.
4. Identify anomalies — patterns that don't fit the dominant causal story.

Output as JSON: { patterns, hypothesis, L1_reflection, anomalies, descent_trigger }
```

**L3 Prompt — Karan**
```
You are operating at the ROOT CAUSE layer.
Topic: {topic}. L1: {L1_context}. L2: {L2_context}

Your job:
1. Identify the structural forces, founding assumptions, origin conditions that generate the L2 patterns.
2. Go to causes — not symptoms, not correlations.
3. Form a hypothesis about what invariant core truth underlies all of this.
4. Reflect on L2: do your root causes fully explain those patterns? What survives unexplained?
5. Identify anomalies — causes that feel real but don't connect to the pattern layer.

Output as JSON: { root_causes, hypothesis, L2_reflection, anomalies, descent_trigger }
```

**L4 Prompt — Atman**
```
You are operating at the INVARIANT TRUTH layer.
Topic: {topic}. Intent: {intent}. L1: {L1_context}. L2: {L2_context}. L3: {L3_context}

Your job:
1. Distill the single least-changing, most fundamental truth about this topic.
   This truth should have been true at the beginning, remain true now, and be likely to remain true longest.
2. Reflect upward through all layers — does this invariant truth account for L3 causes, L2 patterns, L1 observations?
3. What anomalies from all layers survive even this deepest reflection? These are the open questions.
4. Generate the final output shaped by the original intent.

Output as JSON: {
  invariant_truth,
  L3_reflection,
  L2_reflection,
  L1_reflection,
  anomalies_surviving,
  final_output
}
```

---

## 5. UI Architecture

### 5.1 Layout — Three Zones

```
┌─────────────────────────────────────────────────────────┐
│  HEADER: Viveka Framework — Hierarchical Depth Engine    │
├──────────────────┬──────────────────────────────────────┤
│                  │                                      │
│  LEFT PANEL      │  RIGHT PANEL                         │
│  Input + Control │  Layer Output Display                │
│                  │                                      │
│  - Topic field   │  L1 [Sthool]   ← expandable card    │
│  - Intent field  │  L2 [Mann]     ← expandable card    │
│  - Run button    │  L3 [Karan]    ← expandable card    │
│  - Layer status  │  L4 [Atman]    ← expandable card    │
│    indicators    │                                      │
│                  │  REFLECTION PASS                     │
│                  │  ← animated upward trace             │
│                  │                                      │
│                  │  FINAL OUTPUT                        │
│                  │  ← shaped by intent                  │
└──────────────────┴──────────────────────────────────────┘
```

### 5.2 Layer Card States

Each layer card cycles through states with visual feedback:
- **Pending** — grayed out, locked
- **Running** — pulsing border, streaming text visible
- **Complete (Descent)** — solid, shows observations + hypothesis + anomalies
- **Reflected** — gains a reflection badge, shows what was revised

### 5.3 Reflection Animation

After L4 completes, a visual upward trace (L4 → L3 → L2 → L1) animates the reflection pass. Each card updates with its reflection annotation. Surviving anomalies are highlighted in a distinct color.

### 5.4 Final Output Panel

Rendered below all layer cards. Format adapts to intent:
- Analytical intent → structured summary with key findings per layer
- Strategic intent → recommendations anchored in L3/L4 truth
- Creative/narrative intent → prose paragraph distillation

---

## 6. Tech Stack

| Concern | Choice | Reason |
|---|---|---|
| UI Framework | React (JSX artifact) | In-browser, no build step |
| Styling | Tailwind utility classes | Fast, consistent |
| API | Anthropic `/v1/messages` | Claude Sonnet 4 per layer |
| State | `useState` + `useRef` | No external deps |
| Streaming | Sequential `await` per layer | Simpler than parallel; depth requires sequence |
| JSON parsing | `JSON.parse` with fallback | LLM outputs need sanitization |

---

## 7. Component Breakdown

```
<VivekaApp>
  ├── <InputPanel>
  │     ├── TopicField
  │     ├── IntentField
  │     └── RunButton
  │
  ├── <LayerDisplay>
  │     ├── <LayerCard layer="L1" />   (Sthool)
  │     ├── <LayerCard layer="L2" />   (Mann)
  │     ├── <LayerCard layer="L3" />   (Karan)
  │     └── <LayerCard layer="L4" />   (Atman)
  │
  ├── <ReflectionTrace />              (animated upward pass)
  │
  └── <FinalOutput />
```

Each `<LayerCard>` renders:
- Layer name + Sanskrit term + reasoning question
- Status indicator (pending / running / complete / reflected)
- Primary analysis content
- Hypothesis callout
- Anomalies list
- Reflection annotation (populated during upward pass)

---

## 8. Build Sequence

| Phase | What Gets Built | Dependencies |
|---|---|---|
| Phase 1 | Static UI shell — all components, layout, styling, mock data | None |
| Phase 2 | L1 API integration — real Sthool analysis from Claude | Phase 1 |
| Phase 3 | L2 → L3 → L4 sequential descent | Phase 2 |
| Phase 4 | Reflection pass — upward annotation of all layer cards | Phase 3 |
| Phase 5 | Final output rendering + intent adaptation | Phase 4 |
| Phase 6 | Polish — animations, streaming feel, error states, anomaly highlighting | Phase 5 |

---

## 9. Example Run

**Topic:** Amazon  
**Intent:** Understand what will remain true about this company regardless of market conditions

```
L1 (Sthool):
  Observations: Revenue growth, AWS dominance, logistics expansion, Prime flywheel
  Hypothesis: These surface behaviors are driven by a recurring pattern of infrastructure investment
  Anomalies: Advertising revenue growth rate exceeds core retail — why?

L2 (Mann):
  Patterns: Amazon consistently invests in infrastructure before demand exists
  Hypothesis: This pattern is caused by a root belief about how markets work
  L1 Reflection: Advertising anomaly explained — same pattern, different surface (attention as infrastructure)

L3 (Karan):
  Root Causes: Bezos' founding belief — the customer experience is always improvable,
               and whoever lowers the cost of the next layer of infrastructure wins
  Hypothesis: The invariant truth is about Amazons relationship to cost and patience
  L2 Reflection: All patterns follow from willingness to be unprofitable at layer N to own layer N+1

L4 (Atman):
  Invariant Truth: Amazon is a company that perpetually converts the current period's profit
                   into the next period's infrastructure. This has been true since 1995 and
                   will be true as long as Amazons culture survives its founder.
  Surviving Anomaly: What happens when there is no next infrastructure layer to build?

Final Output: [shaped by intent — strategic truth about Amazon's durability]
```

---

## 10. Open Design Questions

1. **Multi-topic mode** — can you run two topics and compare their L4 truths?
2. **Time-slice mode** — for 10-K use case, run the framework on each decade separately, then compare Atman-level truths across time slices
3. **Depth override** — allow user to lock at L2 or L3 if they don't need full descent
4. **Export** — structured JSON or markdown report of the full analysis tree

---

## 11. Naming

| Element | Name |
|---|---|
| Framework | **Viveka** (discriminative wisdom) |
| L1 | **Sthool** — The Visible |
| L2 | **Mann** — The Pattern |
| L3 | **Karan** — The Cause |
| L4 | **Atman** — The Invariant |
| Full process | **The Descent** |
| Reflection pass | **The Ascent** |
| Surviving anomalies | **The Residue** |

---

*Plan version 1.0 — ready for implementation*
