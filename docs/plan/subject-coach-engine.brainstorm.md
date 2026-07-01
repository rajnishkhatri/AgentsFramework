# Brainstorm — Configurable Subject-Coach Engine (English first, open for Math/Science/…)

> **SDD Stage-1 artifact** (`brainstorm`). This is the *idea-expansion* doc: it
> establishes the invariant-vs-variant split, surveys current best practice, and
> proposes a target architecture + candidate options with trade-offs. It does **not**
> decide (that's the ADRs at Stage-2/4) and contains **no code**.
>
> **Status:** Draft — 2026-06-30 · **Owner:** Rajnish Khatri
> **Related:**
> - UI spec (English, shipping): [`preact-english-coach-ui.spec.md`](preact-english-coach-ui.spec.md)
> - Engine/content sibling spec (to be written): `preact-english-coach-engine.spec.md`
> - Transport decision (prior brainstorm turn): Drizzle + Route Handlers + SSE-over-BFF; **no GraphQL** (single client, uniform shapes, SSE-native coach)
> - Process: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` (Stage-1)

---

## 1. Intent (restated)

Build the English coach as the **first instance of a generic, configurable Subject-Coach
engine**. The *pedagogy, flow, and UI shell stay constant*; only the *subject* is swapped
in via configuration + content — never a code fork. Adding "Math coach" should be
**authoring a config bundle + content**, not cloning the codebase.

Two governing constraints pinned at clarify time (2026-06-30):

- **Two configurability planes** (not one):
  - **Deterministic / objective plane** — all UI text, screen names, labels, copy,
    skill taxonomy, and flow are **CMS-configurable** (authored data, zero code).
  - **Subjective / dynamic plane** — questions, coach replies, rubrics, explanations
    are **LLM-generated** per subject via the existing agent pipeline.
- **Open/Closed Principle is the law**: **closed for the present** (ship English now —
  concrete, don't over-build), **open for the future** (every subject-specific decision
  sits behind a stable seam so new subjects are added by *extension, not modification*).

Roadmap: **English first, ship ASAP** → then *general/open-ended* (any subject). So
abstractions must not bake in ACT-English assumptions — but we deliberately resist
building the generic machinery before its second consumer exists (the OCP discipline:
*design the seam now, build the second plugin only when Math arrives*).

> **The trap this doc is written to avoid.** "Make it configurable for any subject"
> invites speculative generality — the most expensive mistake in a v1. Uncle Bob's own
> framing: a plugin architecture is the *consummation* of OCP, but you earn it by
> refactoring an extension point in *when the second case appears*, not by predicting all
> cases up front. ([Clean Coder — OCP](http://blog.cleancoder.com/uncle-bob/2014/05/12/TheOpenClosedPrinciple.html))

---

## 2. The core move: separate the *invariant engine* from the *variant subject*

Everything reduces to one question: **what is the same across English / Math / Science,
and what differs?** Invariant → engine (closed). Variant → config + plugins (open).

| Concern | Invariant (engine — closed) | Variant (per-subject — open) |
|---|---|---|
| **Flow** (Dashboard→Quiz→Feedback→Coach→Summary) | ✅ same state machine for every subject | — |
| **Spaced repetition / scheduler** (FSRS) | ✅ subject-agnostic algorithm | due-cards data only |
| **Mastery / progress model** | ✅ the *mechanism* (track per-skill mastery, project a score) | the *taxonomy* (6 ACT-English buckets) + the *scoring map* (mastery→ACT 24→28) |
| **UI shell + design tokens** | ✅ component library, layout, theming, a11y, surfaces | the *text in it* (labels, screen names, copy) → CMS |
| **Question lifecycle** (present → answer → grade → explain) | ✅ the *protocol* | the *item type* (ACT underlined-span vs Math symbolic vs Science figure) → plugin |
| **Coach** (Socratic, streaming, history-aware) | ✅ the *conversation engine* over the BFF | the *subject persona + prompt templates* → config |
| **Answer checking** | ✅ the *port* (`grade(item, answer) → verdict`) | the *strategy* (exact-match letter vs numeric/symbolic equivalence vs rubric) → plugin |
| **Content** (questions, rationales) | ✅ the *storage + view-model contract* | the *content itself* → LLM-generated or authored |

**Result:** the English coach you're shipping is just the engine + **one** subject pack
("ACT English"). Math = a second subject pack against the same engine.

---

## 3. External research — what current best practice says (2026)

Four domains feed this design. Each finding is tagged with how it lands here.

### 3.1 Clean Architecture / OCP / Plugins
- *"Plugin systems are the ultimate consummation of OCP — dependencies point from the
  plugin to the system, never the reverse; the system doesn't know about the plugins."*
  ([Clean Architecture, Ch.8](https://www.oreilly.com/library/view/clean-architecture-a/9780134494272/ch8.xhtml),
  [Clean Coder](http://blog.cleancoder.com/uncle-bob/2014/05/12/TheOpenClosedPrinciple.html))
  → **Lands as:** subject packs depend on engine interfaces; the engine has **zero**
  imports of any subject. This mirrors your existing Python invariant #1 ("dependencies
  flow downward only") — the same rule, applied to subjects.
- *Ports must be abstract/tech-neutral; adapters thin; "each port should have ≥2 adapters
  — one mock, one real."* ([Hexagonal — jmgarridopaz](https://jmgarridopaz.github.io/content/hexagonalarchitecture.html),
  [Ports & Adapters](https://medium.com/wearewaes/ports-and-adapters-as-they-should-be-6aa5da8893b))
  → **Lands as:** you already do this (`lib/ports/thread_store.ts` + Neon/mock adapters).
  Extend the *same* pattern to subject seams (`ItemType`, `Grader`, `SkillTaxonomy`).
- React-specific OCP: extend components via **composition + config props + a registry**,
  not by editing the component. ([OCP in React — cekrem](https://cekrem.github.io/posts/open-closed-principle-in-react/))
  → **Lands as:** a **question-renderer registry** keyed by item-type; the Quiz screen
  renders `registry[item.type]`, never a `switch (subject)`.

### 3.2 Adaptive-learning platform architecture
- *"Content-agnostic system infrastructure where teaching teams author course content"*
  (Smart Sparrow lineage); content as **discrete learning objects with defined relations
  → a hierarchy aligned to outcomes.* ([Devox 2026](https://devoxsoftware.com/blog/the-next-wave-of-adaptive-learning-and-strategic-roadmap-2026/),
  [Forasoft](https://www.forasoft.com/blog/article/e-learning-software-development-how-to))
  → **Lands as:** a generic content model — `Subject → Skill → Item` — where the *shape*
  is fixed but the *instances* are per-subject. The 6 buckets become rows, not types.
- *"Serious 2026 platforms combine an LLM tutor for explanation with a BKT/DKT layer for
  routing: the LLM talks, the knowledge-tracer picks the next item."*
  ([Devox](https://devoxsoftware.com/blog/the-next-wave-of-adaptive-learning-and-strategic-roadmap-2026/))
  → **Lands as:** clean separation — **deterministic router/scheduler** (FSRS picks next
  item; subject-agnostic) vs **LLM coach** (explains; subject-flavored). Don't let the
  LLM drive scheduling. This matches your repo's existing deterministic-floor philosophy.

### 3.3 Headless CMS for the deterministic/objective plane
- 2026 norm: **schema-level i18n** — locale is a field parameter; *same field structure,
  different values*; "a single source of truth so marketing changes a slogan and it
  updates everywhere without touching code." ([Hygraph](https://hygraph.com/use-cases/headless-cms-localization),
  [Storyblok](https://www.storyblok.com/lp/localization-cms),
  [Kontent.ai](https://kontent.ai/learn/plan/plan-localization/localization-strategy-in-a-headless-cms))
  → **Lands as:** the objective plane (UI strings, screen names, taxonomy labels, flow
  copy) is a **typed content schema served via API** — and *subject* is just another
  axis alongside *locale*. "ACT English" and "Algebra I" are two entries of the same
  schema; future Spanish-language Math is `(subject=math, locale=es)` for free.
  **This is the key reuse:** treat **subject as a dimension of localization**.

### 3.4 LLM generation + grading for the subjective/dynamic plane
- **Verification-first generation/grading is the 2026 consensus**: strict grading
  contracts, **deterministic verification + canonicalization**, bounded semantic repair,
  provenance logging (GradeAgentOps); rubrics must be *explicit, criterion-separated,
  calibrated.* ([GradeAgentOps](https://doi.org/10.3390/ai7060198),
  [Rubric-Conditioned Grading](https://arxiv.org/pdf/2601.08843),
  [Rubrics survey](https://github.com/RUC-NLPIR/Rubrics_Survey))
  → **Lands as:** never trust a raw LLM grade. The `Grader` port returns a verdict that a
  **deterministic verifier canonicalizes** (letter-match for English MC; symbolic
  equivalence for Math; rubric-criterion for free-response). You already built this exact
  pattern — the GoalJudge "correctness cascade" (deterministic answer-verifier in front
  of the LLM judge). **Reuse it as the Grader contract.**
- Generation should be **structured-output + offline-gated**: generate items to a typed
  schema, validate, store; don't generate on the hot path.
  → **Lands as:** an offline **content-generation pipeline** (a `reactLoop` spin-off, as
  you proposed) that emits `Item` records conforming to the engine's item schema, gated
  by a verifier before they reach a learner.

---

## 4. Target architecture (the seams)

Three rings, dependencies pointing **inward only** (engine knows nothing of subjects):

```
┌─────────────────────────────────────────────────────────────────┐
│  SUBJECT PACKS (open — add freely)                                │
│   act-english/   ·   algebra-i/   ·   science-reasoning/   ·  …   │
│   each provides:                                                  │
│     • CMS content bundle  (objective plane: strings, taxonomy)    │
│     • prompt templates    (coach persona, hint/explain prompts)   │
│     • item-type plugin(s) (renderer + grader strategy)            │
│     • scoring map         (mastery → projected subject score)     │
└───────────────▲───────────────────────────────────▲──────────────┘
                │ implements engine interfaces       │ supplies data
┌───────────────┴───────────────────────────────────┴──────────────┐
│  ENGINE (closed — stable contracts)                               │
│   • Flow state machine (Dashboard→Quiz→Feedback→Coach→Summary)    │
│   • FSRS scheduler / next-item router (deterministic)             │
│   • Mastery + projection mechanism                                │
│   • UI shell + design tokens + question-renderer REGISTRY         │
│   • Coach conversation engine (SSE over BFF)                      │
│   • PORTS:  ItemType · Grader · SkillTaxonomy · ContentSource ·   │
│             CoachPersona · ScoringMap · ContentRepo               │
└───────────────────────────────────────────────────────────────────┘
                │ uses
┌───────────────┴───────────────────────────────────────────────────┐
│  INFRA (existing) — Drizzle/Postgres · Headless CMS · BFF · agent  │
└────────────────────────────────────────────────────────────────────┘
```

**Engine ports to introduce (the OCP extension points):**

| Port | Engine asks… | English answers… | Math would answer… |
|---|---|---|---|
| `SkillTaxonomy` | "what skills exist for this subject?" | the 6 ACT buckets | algebra/geometry/… strands |
| `ItemType` (+ renderer in registry) | "how do I render/collect an answer?" | underlined-span MC | symbolic input + LaTeX |
| `Grader` | "is this answer right? (canonicalized)" | letter exact-match | numeric/symbolic equivalence |
| `CoachPersona` | "how does the coach talk here?" | Socratic English prompts | Socratic Math prompts |
| `ScoringMap` | "mastery → projected score?" | →ACT 24→28 | →SAT-Math / target |
| `ContentSource` | "where do items come from?" | LLM pipeline / authored | same engine, diff prompts |
| `ContentRepo` (objective) | "give me the UI text for (subject, screen, locale)" | CMS query | CMS query |

The engine ships with **exactly one** binding (`act-english`). That is OCP done right:
the seams exist, but we don't build `algebra-i` until Math is real.

---

## 5. Candidate options (the decision the ADRs will settle)

### Decision A — the objective/text plane (UI strings + taxonomy)
| Option | What | Pros | Cons |
|---|---|---|---|
| **A1. External headless CMS** (Hygraph/Storyblok/Sanity) | Subject+locale as schema dimensions, served via API | Battle-tested i18n, non-dev authoring UI, subject==locale reuse | New vendor, new ⚠️ Ask-first dependency + BFF caching seam |
| **A2. In-repo config bundles** (typed JSON/MDX per subject) | Content as versioned files behind a `ContentRepo` port | Zero new infra, git-versioned, type-checked, ships fastest | No non-dev authoring UI; "CMS" is a repo edit |
| **A3. DB-backed config** (Postgres table behind `ContentRepo`) | Reuse existing Drizzle/Neon; rows keyed by (subject, key, locale) | Reuses infra you have; runtime-editable later | Build a tiny authoring surface yourself eventually |
| → **Lean:** **A2 now → A3/A1 later.** Ship English with in-repo typed bundles behind the `ContentRepo` port (closed). Because it's a *port*, swapping to a real CMS later is an adapter change, not a rewrite (open). |

### Decision B — the subjective/dynamic plane (questions + coach)
| Option | What | Pros | Cons |
|---|---|---|---|
| **B1. Coach = `reactLoop` spin-off sub-agent** | Fork a subject-parameterized coach agent from the existing ReAct loop | Reuses your whole agent stack, governance, telemetry; SSE-native | New graph node → ⚠️ Ask-first + ADR (engine spec §5 already flags it) |
| **B2. Offline content-gen pipeline** | A generator (also a `reactLoop` job) emits typed `Item`s, verifier-gated, stored | No live-LLM on hot path; deterministic tests; provenance | Need a generation+verification harness per item-type |
| → **Lean:** **both, but separate them.** B1 for the *live coach* (FR-F streaming); B2 for *question content* (offline, gated). Grading goes through the **GoalJudge correctness-cascade** pattern you already have, generalized into the `Grader` port. |

### Decision C — how much engine to build *now*
| Option | What | Verdict |
|---|---|---|
| **C1. Build the full plugin engine now** | All ports + registry + a generic subject loader | ❌ Speculative generality; violates "closed for present"; slows English ship |
| **C2. Ship English monolithically, refactor later** | No seams; extract when Math arrives | ❌ Risks baking ACT assumptions so deep that extraction is a rewrite |
| **C3. Ship English *through* the seams, with one binding** | Define the ports; implement only `act-english`; no generic loader yet | ✅ **This.** OCP: the seam exists, the second plugin doesn't. Cheapest path that keeps the future open. |

---

## 6. The "don't-bake-it-in" checklist (what shipping English must NOT assume)

These are the concrete ACT-English assumptions in the current UI spec that must sit
*behind a seam* even in v1, or extraction later becomes a rewrite:

- ❌ "6 buckets" hard-coded → ✅ `SkillTaxonomy` returns N skills (English happens to be 6).
- ❌ `switch` on bucket/subject in components → ✅ renderer **registry** keyed by item-type.
- ❌ ACT-score (24→28) wired into the mastery UI → ✅ `ScoringMap` produces the displayed score.
- ❌ Underlined-span assumed in the Quiz screen → ✅ Quiz renders `registry[item.type]`.
- ❌ English coach prompts inline in code → ✅ `CoachPersona`/prompt templates as config.
- ❌ UI copy as string literals → ✅ resolved via `ContentRepo(subject, key, locale)`.

Each maps to one engine port in §4. **If a PR for the English coach hard-codes any of the
left column, it has closed a door OCP wanted open.** (Candidate as a Frontend-Ring
architecture-test / review-template field — same "template-as-enforcement" tactic the
code-review skill uses.)

---

## 7. Open questions for Stage-2 (plan/ADRs)

1. **CMS choice (Decision A):** confirm A2-now/A3-later, or commit to an external CMS up
   front? (Drives the `ContentRepo` adapter + a new dependency ADR if external.)
2. **Item-type schema:** what's the minimal generic `Item` shape that fits underlined-span
   *and* a future numeric/symbolic Math item without leaking either? (Math's answer-
   equivalence is the hardest stressor — design the `Grader` contract against it now even
   if unimplemented.)
3. **Coach agent fork (Decision B1):** the actual ⚠️ Ask-first / new-graph-node ADR.
   How is the subject injected into the `reactLoop` spin-off — prompt-param vs distinct
   node vs sub-graph?
4. **Generation gating (Decision B2):** what verifier gates LLM-generated items per
   item-type before a learner sees them? (Reuse the GoalJudge cascade.)
5. **Where does the engine *live*?** Frontend-Ring (UI engine) vs a shared package vs
   partly in `orchestration/` (coach agent). The transport decision already pinned the
   UI in the Frontend Ring; the coach agent is backend.

---

## 8. Recommendation (one line)

**Ship the English coach as `engine + one subject pack`, defining the seven ports in §4
but implementing only the `act-english` binding (Option C3 / A2 / B1+B2 separated, grading
via the existing GoalJudge cascade).** Closed for English-now; open for Math-next — with
the §6 checklist as the guardrail that keeps it open.

---

### Sources
- [Clean Architecture, Ch.8 — OCP](https://www.oreilly.com/library/view/clean-architecture-a/9780134494272/ch8.xhtml) ·
  [Clean Coder — The Open Closed Principle](http://blog.cleancoder.com/uncle-bob/2014/05/12/TheOpenClosedPrinciple.html) ·
  [OCP in React — cekrem](https://cekrem.github.io/posts/open-closed-principle-in-react/)
- [Hexagonal Architecture — jmgarridopaz](https://jmgarridopaz.github.io/content/hexagonalarchitecture.html) ·
  [Ports & Adapters as they should be](https://medium.com/wearewaes/ports-and-adapters-as-they-should-be-6aa5da8893b)
- [Devox — Next Wave of Adaptive Learning 2026](https://devoxsoftware.com/blog/the-next-wave-of-adaptive-learning-and-strategic-roadmap-2026/) ·
  [Forasoft — Build an Adaptive Learning Platform 2026](https://www.forasoft.com/blog/article/e-learning-software-development-how-to)
- [Hygraph — Headless CMS Localization](https://hygraph.com/use-cases/headless-cms-localization) ·
  [Storyblok — Localization CMS](https://www.storyblok.com/lp/localization-cms) ·
  [Kontent.ai — Localization strategy](https://kontent.ai/learn/plan/plan-localization/localization-strategy-in-a-headless-cms)
- [GradeAgentOps — verification-first LLM grading](https://doi.org/10.3390/ai7060198) ·
  [Rubric-Conditioned LLM Grading](https://arxiv.org/pdf/2601.08843) ·
  [Rubrics survey — RUC-NLPIR](https://github.com/RUC-NLPIR/Rubrics_Survey)
