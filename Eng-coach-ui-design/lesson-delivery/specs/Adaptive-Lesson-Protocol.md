# Adaptive Lesson — Spec, Schema & Protocol Contract

**Version:** 1.0 · **Status:** Build-ready
**Reference implementations:** `English Coach - Lesson (Adaptive).dc.html` (production form — framework invisible) · `English Coach - Lesson (SCQA).dc.html` (labeled explainer — framework visible)
**Related:** `Lesson-Block-Schema.md` + `lesson-blocks-schema.json` (block system) · `PreACT-English-Coach-v2-Implementation-Spec.md` (outer-loop learner signals)

> **What this is.** A normative contract for the Adaptive Lesson: one skill's teaching content expressed as four reorderable **narrative beats**, sequenced by the learner's **mode** through a hidden ordering engine derived from the McKinsey **SCQA** framework. The framework drives sequencing but **never surfaces** on screen. Requirements are numbered `AL-*`; acceptance criteria `AL-AC-*`.

---

## 1. Scope

A single-skill lesson that **re-sequences the same content** to match the learner's cognitive state, in the minimal, color-coded, type-as-signal style. In scope: the beat model, the mode→ordering table, the runtime compose + render rules, the invisibility contract, and mode selection from learner state. Out of scope (cross-referenced): the item bank + coaching loops (v2 spec), the block catalog (block schema).

---

## 2. Model

### 2.1 Beats — four narrative roles
A lesson is authored as four beats. Each has a hidden ordering role (its SCQA letter — **never rendered**), a plain on-screen label, a semantic color, and a validation rule.

| Beat id | (hidden role) | On-screen label | Color role | Purpose | Validation |
|---|---|---|---|---|---|
| `ground` | S — Situation | "What you already know" | neutral (muted) | Familiar shared footing | Must **remind, not inform** — the learner nods |
| `tension` | C — Complication | "Where it trips you up" | warning (amber) | The specific, felt difficulty / misconception | Must be **concrete + consequential** (the exact slip, quantified: "your last 4 misses…") |
| `question` | Q — Question | "The question" | accent (teal) | The decision the tension forces | Must be **specific to this skill**, not generic |
| `rule` | A — Answer | "The rule" | success (green) | The resolution + worked example | Must **directly answer** the question, be actionable, and carry the annotated example |

`AL-1` The four beats are the complete content model of a lesson. `AL-2` Beat color roles are fixed and consistent with `Lesson-Block-Schema.md`: ground=neutral, tension=warning, question=accent, rule=success. `AL-3` The on-screen labels are plain language; the SCQA letters are **authoring metadata only** (§6 invisibility).

### 2.2 Modes — learner states → ordering
Six modes, each a fixed beat sequence (the hidden SCQA ordering). `↓` = dropped beat.

| Mode | (hidden ordering) | Beat sequence | Drops | When it applies |
|---|---|---|---|---|
| `new` | SCQA | ground → tension → question → rule | — | First exposure; unfamiliar; learning |
| `struggling` | CSQA | tension → ground → question → rule | — | Knows it, **feels** the problem, frustrated |
| `refresher` | ASC | rule → ground → tension | question | High mastery; quick check |
| `worked` | CQSA | tension → question → ground → rule | — | Learns by seeing it modeled |
| `diagnostic` | CSA | tension → ground → rule | question | Lead with the exact, named slip |
| `annotated` | QSCA | question → ground → tension → rule | — | Curiosity-first / visual contrast |

`AL-4` The mode→sequence table is normative. `AL-5` Two SCQA orderings are intentionally **unused** for a cooperative learner: `QSC` (no resolution) and `AQSC` "Bold Redirect" — the latter is reserved for a future **overconfident-but-wrong** state (lead with the rule to correct a false belief). `AL-6` Each mode carries a plain-language `diag` (why this learner) and `rationale` (why this order) — both **free of SCQA vocabulary** (no "Situation/Complication/…", no letters, no ordering codes).

---

## 3. Schema (types)

```ts
type BeatId = 'ground' | 'tension' | 'question' | 'rule';
type ModeId = 'new' | 'struggling' | 'refresher' | 'worked' | 'diagnostic' | 'annotated';

interface Beat {
  id: BeatId;
  role: 'neutral' | 'warning' | 'accent' | 'success';   // → color (block-schema roles)
  label: string;          // plain, on-screen (e.g. "Where it trips you up")
  body: RichText;         // may carry bold/italic/underline emphasis + the worked example
}

interface Mode {
  id: ModeId;
  label: string;          // on-screen (e.g. "Returning / struggling")
  seq: BeatId[];          // ordering; length 3 or 4; a beat absent from seq is dropped
  diag: string;           // plain "why this learner" — NO framework terms
  rationale: string;      // plain "why this order" — NO framework terms
}

interface Lesson {
  skill: string;          // e.g. "Non-essential commas"
  beats: Record<BeatId, Beat>;   // all four authored
  masteryPct: number;
}
```

`AL-7` A lesson authors **all four** beats regardless of mode; the mode selects which appear and in what order. `AL-8` `body` is `RichText` (structured/markup), not a plain string — emphasis (bold key term, italic coach voice, underlined tested span, color) is part of the content and must survive rendering. `AL-9` `seq` MUST be one of the six sequences in §2.2; a custom `seq` requires a documented mode.

---

## 4. Ordering & composition rules

`AL-10` **Reorder, don't rewrite.** The engine only changes beat order and visibility; beat `body` content is constant across modes (language-register tuning is the optional §7 extension).
`AL-11` **Element-drop.** A 3-beat ordering (`refresher`, `diagnostic`) omits `question`. The omitted beat's content MUST remain reachable as optional drill-down (it is not deleted from the lesson, only from the default flow).
`AL-12` **Lead emphasis.** The first beat in `seq` is the opener: it gets a "▸ start here" marker and MAY receive a size/weight bump. Exactly one opener.
`AL-13` **End on resolution.** A self-contained lesson SHOULD end on `rule`. Permitted exception: `refresher` (ASC) ends on `tension` as a parting caution, because the rule already led. Never end on `tension` when the rule has not yet appeared.
`AL-14` **Sequence indicator.** The current order is shown as a **color-dot sequence** (dots in beat-role colors, in `seq` order, arrow-separated) — **never letters**.

---

## 5. Mode selection protocol (from learner state)

In the reference, the mode is a manual switcher (demo). **[PROD]** the mode is derived from learner state — the same signals the v2 outer loop already computes.

```
selectMode({ firstExposure, masteryPct, feelsProblem, dueMisses, lastMissTag, requested }):
  if requested                         → requested        // explicit learner/teacher choice
  if firstExposure                     → 'new'
  if masteryPct >= 80 and dueMisses==0 → 'refresher'
  if lastMissTag and justMissed        → 'diagnostic'     // a miss just happened → name it
  if dueMisses > 0 and feelsProblem    → 'struggling'
  if prefersWorkedExamples             → 'worked'
  if prefersVisual                     → 'annotated'
  else                                 → 'new'            // safest default
```

`AL-15` Selection inputs are the v2 outer-loop signals (`mastery`, recent `missTag`, due schedule) — do not invent a parallel model (cross-ref v2 spec §5). `AL-16` When state is unknown/ambiguous, default to `new` (SCQA) — the safest ordering. `AL-17` `requested` (an explicit pick) always wins, so a learner/teacher can override the diagnosis.

---

## 6. Invisibility contract (the defining rule)

`AL-18` **No SCQA surface.** The rendered lesson MUST NOT display: the letters S/C/Q/A, the terms "Situation/Complication/Question/Answer", or ordering codes ("SCQA", "CSQA", …). These exist only as authoring metadata and internal engine state.
`AL-19` Beats render with their **plain labels** (§2.1) in their **role color**. The order shows as **color dots** (§4). The rationale strip uses plain language ("Tuned for you · {mode}" + a human sentence).
`AL-20` The labeled `…(SCQA).dc.html` explainer is the **only** surface allowed to show the framework, and only for internal/design use.

---

## 7. Language register per mode — [PROD, optional]

Beyond reordering, SCQA Step 4 tunes *voice*. Optional enhancement: per-mode tone on the same content.

| Mode | Register |
|---|---|
| `new` | patient, scaffolding, defining terms |
| `struggling` | empathetic, naming the frustration, second-person |
| `refresher` | terse, assumes competence |
| `worked` | procedural, step-by-step |
| `diagnostic` | direct, specific to the exact miss |
| `annotated` | visual, minimal prose, show-don't-tell |

`AL-21` Register tuning MUST preserve facts and the rule; it changes emphasis/wording only. `AL-22` If register tuning is not implemented, all modes share one authored `body` (the reference behavior).

---

## 8. Integration

`AL-23` **Above the block composer.** The Adaptive ordering sequences the four *beats*; each beat MAY render as one or more `LessonBlock`s (block schema): `rule` → `rule`+`annotatedExample`+`workedExample`; `tension` → `misconceptionCallout`; `ground` → `rule`(situation form); `question` → a prompt. The beat is the narrative unit; blocks are its presentation. `AL-24` **Reuses v2 signals** for mode selection (§5). `AL-25` Renders in the minimal design language: role color, type-as-signal, no card backgrounds (per the settled minimal direction), theme-aware, color never the sole signal (label + color).

---

## 9. Acceptance criteria

`AL-AC-1` Selecting each of the six modes reorders the four beats to the exact §2.2 sequence, and `refresher`/`diagnostic` hide the `question` beat. `AL-AC-2` No screen state shows an S/C/Q/A letter, a Situation/Complication/Question/Answer label, or an ordering code (§6). `AL-AC-3` Exactly one beat shows the "start here" opener marker, matching `seq[0]`. `AL-AC-4` The color-dot sequence matches `seq` order and beat-role colors. `AL-AC-5` Every mode except `refresher` ends on `rule`; `refresher` ends on `tension`. `AL-AC-6` Beat bodies are identical across modes (reorder-not-rewrite), unless §7 register tuning is enabled. `AL-AC-7` `[PROD]` `selectMode` returns `new` for unknown state and honors `requested`. `AL-AC-8` Renders correctly in light + dark; role colors carry a text label, never color alone.

---

## 10. Cross-references

- **Block system:** `Lesson-Block-Schema.md`, `lesson-blocks-schema.json` — a beat's presentation is one or more blocks.
- **Learner signals:** `PreACT-English-Coach-v2-Implementation-Spec.md` §5 (outer loop) — the source of `selectMode` inputs.
- **Design language:** the settled minimal + typographic direction (`…(Minimal).dc.html`, `…(Typographic).dc.html`).

*Normative for the Adaptive Lesson. Derived 1:1 from the reference implementations; where they disagree, the clean `…(Adaptive).dc.html` is the behavioral reference and this contract the production spec.*
