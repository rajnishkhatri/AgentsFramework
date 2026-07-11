# PreACT English Coach — E1 `/learn/skill` Implementation Specification

**Version:** 1.0 · **Status:** Build-ready · **Scope:** the single-skill Learn surface (the adaptive lesson, block-composed)
**Companion to:** `PreACT-English-Coach-v2-Implementation-Spec.md` (the two-loop tutor; §5 = outer-loop signals this surface consumes) · `Adaptive-Lesson-Protocol.md` (beat model + `selectLessonContext`, AL-*) · `Lesson-Block-Schema.md` (block catalog + composer) · `Adaptive-Lesson-Decisions.md` (the ratified binding decisions D1–D8 / I1 / A1–A3 this spec implements)
**Reference implementation (source of truth):** `English Coach - Learn Skill (E1).dc.html` — the full 3-context surface (`newSkill` inductive · `returning` · `refresher`) driven by `selectLessonContext`, with the prototype **inspector** exposing the selector across five learner-state scenarios. `English Coach - E1a newSkill.dc.html` is the focused single-context (`newSkill`) artifact; where the two agree they are identical, and the multi-context file is authoritative.

> **How to read this document.** Engineering requirements + technical design for the `/learn/skill` screen. Every behavior, block, recipe, and binding below is **derived from the reference prototype** and the ratified decisions, and is intended to be reproduced 1:1. The reference is a `.dc.html` visual/behavioral spec; production re-authors it natively (per the memo's §4 bind plan) — so this spec states *behavior and pedagogy*, which are framework-agnostic. Where production must go beyond the prototype (real learner signals, persisted content, the coach handoff), the prototype behavior is the **reference/fallback** and the production requirement is marked **[PROD]**.
>
> **Traceability contract.** Requirements are numbered `FR-CTX-*` (context selection), `FR-CMP-*` (composer), `FR-BLK-*` (blocks), `FR-IX-*` (interaction), `DATA-*`, `GUARD-*`, `NFR-*`, `AC-*`. Every requirement cross-references the decision (`D#`, `I1`, `A#`) and/or protocol rule (`AL-*`) it implements. §9 maps every state field and rendered value to its source. Identifiers in `monospace` are the exact names in the reference code.

---

## 1. Scope & Goals

### 1.1 What E1 is
`/learn/skill` is the **single-skill teaching surface**: one English skill's content, expressed as an **ordered list of typed blocks** the composer selects and orders by the learner's **context**. It is the shipping form of the Adaptive Lesson — the 4-beat model (`Adaptive-Lesson-Protocol.md`) projected onto the 3-context block composer (`Lesson-Block-Schema.md`), because the outer loop emits only `{mastery, missTag, due}` and cannot drive the 6-mode beat engine (D0/framing; `Adaptive-Lesson-Decisions.md` §0).

### 1.2 In scope
- **`selectLessonContext`** — the state → context selector (§4; D1). The net-new contract that decides which surface every learner sees on entry.
- **The block composer** — recipe → order/zone → role-token resolution → render; the end-on-resolution guard (§5; D2/A3/AL-13).
- **The block catalog (12 blocks)** — the 9 v1 blocks + 3 beat-promotions (`ground`, `question`, `pitfall`); their role/zone, render contract, and the interactive ones (`completionTry` D3, `selfExplainPrompt` D4) (§6).
- **The three contexts** — `newSkill` (inductive), `returning`, `refresher`, each an ordered recipe; the misconception-callout honesty tiers (D6/I1); accuracy data-gating (D7); cross-skill due list (D8); skill-pinned coach entry (D4c, seam only in E1a).
- **The a11y half of the invisibility contract** (AL-25 / AL-AC-8): role color always carries a text label (§7, §8).
- Light + dark; offline/deterministic (no LLM on this surface in E1); the sidebar + tab-bar shell retained.

### 1.3 Out of scope (this surface)
- The **6-mode SCQA beat engine** (`selectMode`, the mode tabs, "Tuned for you" strip) — deferred; its selection signals aren't emitted by the outer loop (framing verdict). The SCQA *sequencing* invisibility rules (AL-18/19/20) therefore bind nothing here (§8).
- The **cross-miss aggregated** misconception callout ("Your pattern · X") and the **`fix`** line — deferred to E1b behind a reviewed tag-clustering pipeline (D6-1/I1 tier-1; N-5).
- The **live coach conversation** — the `coachEntry` block is a skill-pinned *entry point* only; the conversation surface and the lesson→coach seed contract ride E1b (D4c).
- Authoring UI; the item bank + inner/outer loop engines (specified in the v2 spec); multi-learner.

### 1.4 Target surface
A core screen inside the desktop app shell (sidebar + top bar), **not** a sandboxed iframe (per CSP) — re-authored natively. Reference frame: `$preview` width **1180**, main content ≤ ~760px + a 258px rail. Design system: **AgentsFramework UI** (§2.4 of the v2 spec) — same tokens and components; `--accent` is the skill's bucket token (§2.3).

### 1.5 The decisions this surface binds (index)
`D1` selector · `D2` end-on-resolution guard · `D3` completionTry inert-to-scheduler · `D4` self-explain shown-back-local · `D5` render-time composition · `D6` verbatim single-miss callout, no fix · `D7` accuracy gated on data, ≠ mastery · `D8` cross-skill due list · `I1` callout fallback tiers · `A1` 3 beat-promotion blocks · `A2` carry opener, drop color-dots · `A3` end on the win. Full rationale: `Adaptive-Lesson-Decisions.md`. §13 maps each to requirements here.

---

## 2. System Architecture

### 2.1 The composer pipeline
```
entry(/learn/skill, learnerState) ─────────────────────────────────────────────┐
  ctx   = selectLessonContext({firstExposure, masteryPct, dueMisses, requested}) │  §4 · D1
  recipe= RECIPE[ctx]            // ordered block tags (main) + rail tags         │  §5 · D5
  vms   = recipe.map(tag => build(tag, DATA[skill][tag], resolveRole(role,ctx)))  │  §6
  main  = vms.filter(zone==='main');  rail = vms.filter(zone==='rail')            │
  guard(main)                     // end-on-resolution                            │  §5.3 · D2/A3
  root.style['--accent'] = SKILL_ACCENT[skill]                                    │
  render(shell, hero(ctx,state), main, rail)   // unknown/no-data tags skipped    │  §5 · D7
```
`FR-CMP-1` The screen is a **function of context**, not a hand-built layout: change the context and the same content recomposes (D5; `Lesson-Block-Schema` thesis). `FR-CMP-2` Block **order** and each block's resolved `role`/`zone`/`tint` are computed by the composer/translator **upstream** — the rendered block receives resolved tokens and holds no domain logic (memo §4; D5).

### 2.2 Reference recomposition mechanism (normative behavior, not markup)
In the reference DC every block is a literal section carrying a context-derived `{order, disp}` (a flex `order` + `display:flex|none`); the composer computes `S[tag] = {order, disp}` per render (`renderVals`). Production MAY render only the selected blocks instead of toggling all — the **observable contract** is identical: the blocks in `RECIPE[ctx]` appear in that order in the correct zone, and no others (`FR-CMP-1`). The reference approach is documented in §9.

### 2.3 Relationship to the two loops
`/learn/skill` is **outer-loop-adjacent**: it consumes the outer loop's signals and writes almost nothing back.
- **Consumes:** `mastery[skill]` (v2 `DATA-13` / [PROD] estimator `FR-OL-P1`), recent `missTag` (v2 `ResultRec.missTag`, `DATA-12`), and `due` (v2 [PROD] scheduler `FR-OL-P3`). These are exactly the three signals `selectLessonContext` is allowed (D1; AL-15).
- **Writes:** nothing to mastery or the FSRS schedule. `Scheduler.review()` remains the sole writer (v2 §2.3, §5.5); the teaching-surface interactions (`completionTry`, `selfExplainPrompt`) are ephemeral (D3/D4, §7). The only outbound actions are **navigation**: the `dueChecklist` drill deep-links and the `completionTry` "Practice this skill →" both route into the Practice/drill surface (the outer loop), which is where attempts are recorded.

### 2.4 Role → token resolution
`FR-CMP-3` Each block declares a semantic `role` (`neutral | accent | accentDashed | accentSoft | warning | success`); the composer resolves role → tint at render (`Lesson-Block-Schema` "Color = meaning"). Reference `roleStyle(role) → {border, background, ink, borderStyle}`:

| role | border | background | ink | style |
|---|---|---|---|---|
| `neutral` | `--color-border` | `--color-surface` | `--color-muted` | solid |
| `accent` | mix(accent 35%, border) | mix(accent 6%, bg) | mix(accent 55%, fg) | solid |
| `accentDashed` | mix(accent 48%, border) | transparent | mix(accent 55%, fg) | **dashed** |
| `accentSoft` | mix(accent 30%, border) | mix(accent 5%, bg) | mix(accent 55%, fg) | solid |
| `warning` | mix(warning 38%, border) | mix(warning 9%, bg) | `--color-warning` | solid |
| `success` (accents) | mix(success 32%, transp) | mix(success 15%, bg) | `--color-success` | solid |

`DATA-STYLE-1` No color/type/spacing outside AgentsFramework tokens. `DATA-STYLE-2` `accentDashed` renders **transparent background + dashed border** (the "active task" affordance) — never a filled card. `DATA-STYLE-3` **[PROD]** two bind-time deltas are owned by the consumer: alias `--accent` to the `--color-bucket-*` naming (`Skill.accent_var` already carries the right token per skill), and reconcile the literal `13px`/`14px` radius against `--radius-sm` (memo §4).

---

## 3. Data Model

### 3.1 Learner-state input (selector inputs)
```ts
interface LearnerState {
  firstExposure: boolean;        // no prior session for this skill
  masteryPct: number | null;     // v2 mastery[skill]; null when unknown/first exposure
  dueMisses: number;             // count of due review items for this skill (whole-skill; §3.5, D8)
  requested?: LessonContext;     // explicit learner/teacher pick — overrides (AL-17)
}
type LessonContext = 'newSkill' | 'returning' | 'refresher';
```
`DATA-CTX-1` These are the **only** inputs to `selectLessonContext` (D1; AL-15). The mode-engine signals (`feelsProblem`, `prefersWorkedExamples`, `prefersVisual`, `justMissed`) are **not** available and MUST NOT be invented. `DATA-CTX-2` `masteryPct` is the v2 mastery/retrievability estimate; it is **not** answer-accuracy (§3.4, D7).

### 3.2 Block catalog (12 tags)
Extends the v1 9-tag catalog (`Lesson-Block-Schema`) with 3 beat-promotions (A1). Each block: `zone` (`main|rail`), `role` (§2.4), authored fields.

| tag | zone | role | key fields | context(s) | decision |
|---|---|---|---|---|---|
| `ground` | main | neutral | `title, body` | newSkill (lead) | A1 |
| `pitfall` | main | warning | `label, body` (+ `framing: 'mid'\|'parting'`) | newSkill (mid) · refresher (parting) | A1, A3 |
| `question` | main | accent | `prompt` | newSkill | A1 |
| `selfExplainPrompt` | main | accentSoft | `prompt` | newSkill | D4 |
| `rule` | main | neutral (success accents) | `title, body, examples[]` | **all** | — |
| `workedExample` | main | accent | `sentence, steps[], answer` | newSkill | — |
| `completionTry` | main | accentDashed | `sentence, promptHint, choices[]` | newSkill (terminal) | D3, A3 |
| `misconceptionCallout` | main | warning | `eyebrow, body` (no `fix`) | returning, tagged | D6, I1 |
| `annotatedExample` | main | accent | `examples[] (pre/clause/post/essential/callouts)` | returning · refresher | — |
| `dueChecklist` | rail | neutral | `title, items[] (skill, cta)` | returning | D8 |
| `accuracyStat` | rail | accent | `value, caption, bars[]` | any with history | D7 |
| `coachEntry` | rail | accent | `label, body, cta` (skill-pinned) | returning | D4c |

`DATA-BLK-1` The **tension beat role** (`warning`) has **two block treatments** selected by context (A1): `pitfall` (generic, structural — no miss data) at first exposure and as the refresher parting caution; `misconceptionCallout` (miss-specific) on return. They are the same beat, different content. `DATA-BLK-2` `ground` and `question` are dedicated blocks (not `rule`-in-situation-form / a bare prompt) — honoring the distinct beat roles + colors (A1; supersedes the AL-23 sketch). `DATA-BLK-3` The reference authors the refresher parting caution as a separate `pitfall` instance with `framing:'parting'` (distinct copy from the newSkill `framing:'mid'` instance); production MAY model this as one block type with a `framing` field or two authored instances.

### 3.3 Composed block view-model
```ts
interface BlockVM {
  tag: string; zone: 'main'|'rail'; role: Role;
  border: string; background: string; ink: string; borderStyle: 'solid'|'dashed'; // resolved (§2.4)
  order: number;             // position within its zone for this context
  /* + the block's own resolved fields */
}
```
`DATA-BLK-4` `role`/`zone`/tint/`order` are **render-time** outputs of the composer, **not** persisted content (D5). `DATA-BLK-5` The **durable authored content** is the raw pieces per skill: the one-line `rule` + `examples[]` (exists in the wire type), the per-item misconception tag (exists; §3.4), and the net-new **teaching assets** — `workedExample.steps`, the `completionTry` item, `annotatedExample.callouts`, `selfExplainPrompt.prompt`, plus the `ground`/`question`/`pitfall` copy. `DATA-BLK-6` **[PROD] ADR scope:** add *optional typed teaching fields* to the skill content type; do **NOT** add `blocks[]`/`zone`/`role`/`context`/`beats` to the persisted wire (D5). The block/beat **order is not authored content**.

### 3.4 Misconception tag → callout (D6 / I1)
The `returning` lead callout is backed by the **single newest due miss's** verbatim, author-written, one-line tag (v2 `lib[tag].label` / the free-text miss note; present on ~27% of items). It is rendered **verbatim** (so it cannot leak the answer) — the same binding the Session-Summary screen already ships.
```ts
interface CalloutVM { tier: 1|2|3; show: boolean; eyebrow: string; body: string; } // no `fix` in E1
```
`DATA-CALL-1` **Three-tier honesty ladder** keyed to available evidence (I1):
- **Tier 1** — a *recurring* tag (same/clustered tag on ≥2 due misses): eyebrow `"Your pattern · {theme}"` + aggregate body. **[PROD], E1b only** (needs the reviewed tag-clustering pipeline; no controlled taxonomy exists today).
- **Tier 2** — newest due miss **tagged** (~27%, E1 available): eyebrow `"On your last miss · {skillName}"` (a single-item, lower-confidence claim — **never** "Your pattern" on n=1), `body` = that one verbatim tag. `show:true`.
- **Tier 3** — due miss **untagged** (~73%, E1): `show:false` — **hide the callout**; `returning` then leads with `annotatedExample`. (Reject the neutral miss-count line: it asserts severity without diagnosis — I1 rejects (B).)

`DATA-CALL-2` **No `fix` line in E1** (D6-2): no field backs it and any authored corrective text risks the answer-leakage lint (v2 §3.6). The resolution lives in the `rule` block below (which the composed lesson ends on for returning — §5.3). `fix` returns only with authored, provenance-tracked, leak-linted text (E1b).

### 3.5 Accuracy & due data (D7 / D8)
```ts
interface AccuracyVM { value: string; bars: number[]; caption: string; } // answer-accuracy, NOT mastery
interface DueItem { skill: SkillKey; label: string; drillHref: string; }   // whole-skill granularity
```
`DATA-ACC-1` `accuracyStat.value` is **true answer-accuracy over a real session window** — the share of items answered correctly — **not** the FSRS mastery/retrievability scalar (D7-2). Conflating them is a known dashboard bug; rendering mastery under an "Accuracy" label ships that bug. **[PROD]** build the accuracy aggregation over recent sessions. `DATA-ACC-2` If the accuracy aggregation has **no data** (true first exposure), the block **self-omits** (§5.4). `DATA-DUE-1` `dueChecklist.items[]` are **whole due skills** from the scheduler's `due_at` (D8-A) — the scheduler knows due-ness only at whole-skill granularity. The intra-skill micro-topic checklist is **[PROD], E1b** authored content (needs sub-skill signals). `DATA-DUE-2` Each due row's `drillHref` deep-links to a **skill-pinned** drill for *that* row's skill (D8-ii; the scheduler skill-pin supports it).

---

## 4. Context Selection — `selectLessonContext` (D1)

The net-new contract that decides which surface a learner sees on every entry to `/learn/skill`. It is the faithful 6→3 projection of the protocol's `selectMode` (`Adaptive-Lesson-Protocol` §5, folded into §5.1).

### 4.1 Algorithm (normative)
```
selectLessonContext({ firstExposure, masteryPct, dueMisses, requested }):
  if requested                           → requested     // FR-CTX-5 · AL-17 analog: explicit pick wins
  if firstExposure or masteryPct == null → 'newSkill'    // FR-CTX-2 · AL-16 analog: safe default
  if masteryPct >= 80 and dueMisses == 0 → 'refresher'   // FR-CTX-3 · the one transferable anchor (§5)
  if dueMisses > 0                       → 'returning'    // FR-CTX-4 · review debt — tagged or not
  else                                   → 'newSkill'     // FR-CTX-2 · learning; nothing due — keep teaching
```
`FR-CTX-1` **Projection map:** `struggling`/`diagnostic` (and `worked`-when-due) collapse to `returning`; `worked`/`annotated`-when-not-due are indistinguishable from teaching without the `prefers*` signals, so they fold to `newSkill` (framing verdict). `FR-CTX-2` **Default = `newSkill`** on first exposure or unknown mastery (D1-d; AL-16). `newSkill` also fires for "learning, `<80`, nothing due" — so it is **not** first-exposure-only (§5.4, D7). `FR-CTX-3` **`refresher`** requires `masteryPct >= 80` **and** `dueMisses == 0`; floor = **80**, verbatim from `selectMode` (D1-c). `FR-CTX-4` **`returning`** flip is `dueMisses > 0` — **no mastery threshold gates it** (D1-a). `FR-CTX-5` `requested` (explicit learner/teacher pick) overrides the diagnosis (AL-17).

### 4.2 Tag vs due-ness (D1-b)
`FR-CTX-6` **Due-ness selects the context; a misconception tag never does.** A tag on a *non-due* miss does **not** force `returning` (the scheduler owns re-surfacing). Within `returning`, the newest due miss's tag *populates* the callout (§3.4); an **untagged** due miss still routes to `returning` (there is debt) and the callout self-hides (I1 tier 3). `FR-CTX-7` Therefore the `returning` recipe MUST tolerate a **missing lead block** (§5.2).

### 4.3 Label nuance (non-blocking)
`FR-CTX-8` Because `newSkill` also serves "learning, nothing due," the **visible** hero label MUST be state-aware — e.g. "New skill · first lesson" on true first exposure, a softer "Continue · {skill}" otherwise (reference `heroEyebrow`). The context *id* is unchanged; only the label softens (D1 label nuance).

---

## 5. The Block Composer

### 5.1 Context recipes (normative)
| context | main (ordered) | rail | ends on | source |
|---|---|---|---|---|
| **`newSkill`** *(inductive)* | `ground → pitfall → question → selfExplainPrompt → rule → workedExample → completionTry` | `accuracyStat` *(if history)* | `completionTry` (the win) | A1/A3/D4/D7 |
| **`returning`** | tagged: `misconceptionCallout → annotatedExample → rule` · untagged: `annotatedExample → rule` | `dueChecklist → accuracyStat → coachEntry` | `rule` (the fix) | D6/I1/D2/D8/D4c |
| **`refresher`** | `rule → annotatedExample → pitfall(parting)` | `accuracyStat` | `pitfall` (parting caution) | AL-13 exception |

`FR-CMP-4` `newSkill` is **inductive** — ground → tension → question → rule (discovery-first), reconciling the block layer to the protocol's `new` = SCQA arc (A/framing). The earlier rule-first recipe was the `refresher` = ASC ordering mislabeled and is retired. `FR-CMP-5` `refresher` is **rule-first (ASC)** — high mastery, quick check; rule leads, a quick annotated glance, then a parting caution.

### 5.2 Missing-lead tolerance
`FR-CMP-6` When the `returning` callout is hidden (tier 3, untagged), the recipe drops its lead and the surface leads with `annotatedExample` — the composer's "unknown/empty tags skipped" rule (`Lesson-Block-Schema` runtime contract) covers this; no layout gap, no placeholder (FR-CTX-7).

### 5.3 End-on-resolution guard (D2 / A3 / AL-13)
`FR-CMP-7` The **main zone ends on the deepest available resolution**:
- `newSkill` — the applied **win** (`completionTry`), or its consolidation (`selfExplainPrompt`) if no try; **never** on `pitfall`/`misconceptionCallout` unless the `rule` precedes it.
- `returning` — the **`rule`/fix** (never end on the `misconceptionCallout`).
- `refresher` — permitted exception: ends on the **parting `pitfall`** *because the `rule` already led* (AL-13 refresher exception).

`FR-CMP-8` The mid-recipe `rule` in `newSkill` is **not** an AL-13 violation: AL-13 forbids ending on tension *before the rule appears*; here the rule appears (the discovery payoff), then is applied. "Resolution" = the *win* at the block layer, the `rule` at the beat layer — the same "end resolved" principle at two depths (A3). `FR-CMP-9` The **rail** (`dueChecklist`/`accuracyStat`/`coachEntry`) is ambient and **exempt** from the guard.

### 5.4 Accuracy data-gating (D7)
`FR-CMP-10` `accuracyStat` is gated on **data availability, not on the context label**: no session history → the block self-omits; history exists → it renders. So at true first exposure (`newSkill`, `firstExposure`) there is **no rail**; for a learning-state `newSkill` (history exists) the rail carries accuracy (D7-1; FR-CTX-2). `FR-CMP-11` Empty-state and forward-placeholder are **rejected** — a 6-bar trend on a skill with zero sessions is fabricated; absence is the honest render (D7-1). `FR-CMP-12` When the accuracy aggregation is unavailable, **omit** rather than substitute the mastery scalar (D7-2; DATA-ACC-1).

---

## 6. Block Catalog — render & interaction contracts

Shared: every block renders inside a role-tinted container (§2.4) with a **text label** in its role color (never color alone — AL-25/AL-AC-8, §8).

### 6.1 Teaching blocks (newSkill)
`FR-BLK-1` **`ground`** (neutral) — "What you already know"; a reminder, not new info ("the learner nods"; AL beat validation). Carries the **opener marker** (§6.4).
`FR-BLK-2` **`pitfall`** (warning, `framing:'mid'`) — "Where it trips you up"; the skill's **structural** trap, **generic, no miss data** (D6/A1): the wrong choice flips meaning; the hard cases cluster after "which"/"who". Distinct from `misconceptionCallout` (DATA-BLK-1).
`FR-BLK-3` **`question`** (accent) — "The question"; the single framing question the tension forces ("So how do you tell when a clause actually needs its commas?").
`FR-BLK-4` **`rule`** (neutral + success accents) — "The rule"; the removal-test heuristic + the highlighted worked sentence. Present in **all** contexts. When a self-explain note exists (newSkill only), it renders the note-echo (§6.2).
`FR-BLK-5` **`workedExample`** (accent, `●●●`) — full step-by-step model + answer chip.

### 6.2 `selfExplainPrompt` (accentSoft) — D4
`FR-BLK-6` Placed **before the `rule`** in `newSkill` (the "explain before the instructional explanation" effect). Free-text is **shown back locally as the learner's own note, never stored, never scored** (D4 = option b). `FR-BLK-7` The note is echoed in the `rule` block as a compare-to-rule chip — "You guessed: '{note}' — did the rule match your thinking?" — realizing D4's compare payoff. `FR-BLK-8` Writes **nothing** to the scheduler (same principle as D3). `FR-BLK-9` **Forward-compatible with the coach handoff (c):** the same local note MAY later seed the coach in E1b without re-architecting; deferring (c) here does not make (b) a throwaway (D4).
Reference: `onNote` sets `state.note`; the textarea is **uncontrolled-observed** (no bound `value`) so re-render never disturbs the caret; `hasNote = ctx==='newSkill' && note.trim().length>0` gates the echo.

### 6.3 `completionTry` (accentDashed) — D3 / A3
`FR-BLK-10` **Inert to the scheduler, interactive locally** (D3 = option a, sharpened). A faded worked example (`●●○` vs `●●●`) — scaffolded, low-stakes practice inside the teaching moment.
`FR-BLK-11` **Interactive:** the `correct` flag **reaches the DOM**; a click grades immediately — the picked choice shows ✓/✗, and on a miss the correct choice is revealed with a one-line why + the removal-test nudge; a "↺ Try again" resets. On success the block shows the forward "Practice this skill →" CTA (closing on the win, A3).
`FR-BLK-12` **Records nothing:** no attempt is logged, no mastery moves, no FSRS interval changes. `Scheduler.review()` stays the sole writer (v2 §2.3). A learner-visible honesty line states "Practice — not recorded. Your review schedule doesn't move here."
`FR-BLK-13` **No answer-branching:** a wrong pick does **not** change what the lesson shows next (local reveal only) — the lesson is already composed for this context; branching-on-answer is gated on signals unavailable mid-lesson (E1b+).
Reference: `pick(i)` sets `state.tryPicked`; `resetTry` clears it; the choice VMs (`✓/✗`, tint, weight) and the feedback tone/body are computed in `renderVals`.

### 6.4 Beat affordances (A2)
`FR-BLK-14` **Carry the opener marker (AL-12).** The lead block (`ground` in inductive `newSkill`) shows a "▸ start here" marker — wayfinding + reassurance at the top of a guided sequence. Exactly one opener. Reference prop `openerMarker` (default on).
`FR-BLK-15` **Drop the color-dot sequence (AL-14)** on the block composer. Its purpose is to make a *variable* order legible; with a fixed context order and no mode-switch it tracks nothing and reads as decorative machinery (A2; minimal-direction / don't-expose-the-machinery). Role colors already carry meaning inline. **Reintroduce only** if a visible context switch (returning/refresher tabs) later shares the surface.

### 6.5 Returning / refresher blocks
`FR-BLK-16` **`misconceptionCallout`** (warning) — eyebrow + verbatim single-miss body, **no fix** (§3.4; D6/I1). Tiered `show` per DATA-CALL-1.
`FR-BLK-17` **`annotatedExample`** (accent) — marked-up examples: a non-essential clause fenced in accent with numbered callouts (removal test → fence), and an essential clause in muted with a "no commas" callout. Present in `returning` + `refresher`.
`FR-BLK-18` **`dueChecklist`** (rail, neutral) — titled cross-skill "Also due for review"; **whole due skills** with per-row skill-pinned "Drill →" (D8; §3.5). **Not** an intra-skill checklist and **not** shown in `newSkill`.
`FR-BLK-19` **`accuracyStat`** (rail, accent) — value + 6-bar trend + caption; the numeric % **always rendered alongside** the bars (AL-AC-8), and a footnote asserting it is **distinct from mastery** ("Not your mastery estimate ({masteryPct}%) — accuracy is a different number") (D7-2). Reference hand-builds the 6-bar chart from the single-fill progressbar idiom (memo §4).
`FR-BLK-20` **`coachEntry`** (rail, accent) — **skill-pinned entry point** to the Socratic coach ("hint-first, never the answer … pinned to {skill}"). E1: the button is the **seam**; the lesson→coach seed contract (pin the coach to a skill, open in a lesson-context mode) is authored in **E1b** (D4c). `returning` only.

---

## 7. Interaction, Guards & State

### 7.1 Reference state model
```ts
state = { dark: boolean, scenario: ScenarioKey, tryPicked: number|null, note: string }
```
`FR-IX-1` The only durable-feeling state is `note` and `tryPicked`, both **local and ephemeral** (cleared on scenario change; never persisted). `scenario` is a **[PROTO]** control (§9.3); production replaces it with the real `LearnerState` from the outer loop. Handlers: `toggleTheme`, `setScenario(k)` (resets `tryPicked`), `pick(i)`, `resetTry`, `onNote(e)`.

### 7.2 Guards
`GUARD-NOWRITE-1` No `/learn/skill` interaction writes mastery or the FSRS schedule; `Scheduler.review()` is the sole writer (D3/D4; v2 §2.3). Verified: `completionTry` and `selfExplainPrompt` mutate only local component state.
`GUARD-ACC-1` `accuracyStat` never renders the mastery/retrievability scalar under the "Accuracy" label; if true accuracy is unavailable, the block is omitted, not substituted (D7-2; FR-CMP-12).
`GUARD-CALL-1` The callout never asserts a recurring "pattern" on a single miss; tier-2 uses a single-item eyebrow, tier-3 hides (I1; DATA-CALL-1). No `fix` line ships in E1 (D6-2).
`GUARD-LEAK-1` The verbatim miss tag is shown **as written** and MUST NOT be transformed into corrective text that could leak the answer (same predicate as the v2 leakage lint, §3.6); tags are author-authored to not name the answer.
`GUARD-END-1` The main zone never ends on a tension block before the rule has appeared (FR-CMP-7/8; AL-13).

### 7.3 Accessibility
`NFR-A11Y-1` WCAG-AA contrast for every token pairing, light + dark (v2 NFR-A11Y-1). `NFR-A11Y-2` **Role color carries a text label, never color alone** (AL-25 / AL-AC-8) — every block has a labeled eyebrow; `completionTry` grades with ✓/✗ glyphs + a text feedback line; the accuracy chart carries its numeric value + an `aria-label`. `NFR-A11Y-3` Keyboard operability + visible focus for choices, drill links, coach button, theme toggle, and the composer textarea. `NFR-A11Y-4` `completionTry` feedback is announced (`role="status"`). `NFR-A11Y-5` Touch targets ≥44px.

---

## 8. Invisibility Contract — scope on this surface

`FR-INV-1` **AL-18/19/20 bind nothing here.** They govern the 6-mode SCQA *sequencing* (hide S/C/Q/A letters, Situation/Complication terms, ordering codes); E1 ships **no SCQA engine**, so there is nothing to hide (framing verdict). The reference's mode tabs / "Tuned for you" strip / color-dot sequence are **not** produced (A2; FR-BLK-15).
`FR-INV-2` **AL-25 / AL-AC-8 is the one surviving, non-negotiable rule:** every block renders in the minimal language (role color + type-as-signal, no color as the sole signal), theme-aware, with a text label always accompanying color (NFR-A11Y-2). This is the invisibility contract's a11y half, kept regardless (memo §4).

---

## 9. Traceability (prototype → implementation)

### 9.1 Derived-per-render values (`renderVals`)
| Computed | From | Role |
|---|---|---|
| `sc` = SCENARIOS[scenario] | `state.scenario` | **[PROTO]** stand-in for real `LearnerState` |
| `{ctx, rule}` = `selectContext(sc)` | `sc.{fe,mastery,due}` | the D1 selector (§4) + trace string |
| `tagged`, `hasHistory` | `sc.tagged`, `!sc.fe` | callout tier (I1), accuracy gate (D7) |
| `mainRecipe`, `railRecipe` | `ctx`, `tagged`, `hasHistory` | the recipes (§5.1) |
| `S[tag] = {order, disp}` | recipe index per tag | recomposition (§2.2) |
| `acc = {value, bars}` | `ctx` | accuracy VM (**[PROD]** real aggregation; §3.5) |
| `tryChoices`, `tryFb*`, `tryGotIt/TryAgain` | `state.tryPicked` | `completionTry` grade (§6.3) |
| `hasNote`, `noteEcho` | `state.note`, `ctx` | self-explain echo (§6.2) |
| `heroEyebrow`, `showMastery`, `heroDue*` | `ctx`, `sc.{mastery,due}` | state-aware hero (FR-CTX-8) |

### 9.2 Context → layout (the observable contract)
| scenario (`sc`) | inputs `{fe, mastery, due, tagged}` | `selectContext` → | main (order) | rail |
|---|---|---|---|---|
| `firstExposure` | `{T, null, 0, —}` | `newSkill` | ground·pitfall·question·selfExplain·rule·worked·try | — (no history) |
| `learning` | `{F, 42, 0, —}` | `newSkill` | *(same as above)* | accuracy |
| `returning` | `{F, 49, 4, tagged}` | `returning` | misc·annotated·rule | due·accuracy·coach |
| `returningUntagged` | `{F, 52, 3, untagged}` | `returning` | annotated·rule *(callout hidden)* | due·accuracy·coach |
| `refresher` | `{F, 88, 0, —}` | `refresher` | rule·annotated·pitfall(parting) | accuracy |

`FR-TRACE-1` These five scenarios are the reference demonstration set (they exercise every branch of §4.1 + the I1 tag/untag toggle + the D7 gate). **[PROD]** they are replaced by the live `LearnerState`; the mapping (inputs → ctx → layout) is the contract.

### 9.3 The inspector is [PROTO] instrumentation
`FR-TRACE-2` The reference's dashed **"Prototype · learner-state → context"** band (scenario chips + the live `{firstExposure, mastery, dueMisses} → fired-rule` trace) is a build-time inspector, gated by the `showInspector` prop. It MUST NOT ship to learners; it is the executable demonstration that `selectLessonContext` behaves per §4. Production surfaces none of it — the learner sees only the composed lesson (FR-INV-1). The `openerMarker` prop (§6.4) is a design toggle, not production config.

### 9.4 Static reference copy → data source [PROD] (must be wired)
| Static in reference | Bind to |
|---|---|
| Skill = "Non-essential commas" / accent | selected bucket + `Skill.accent_var` |
| `masteryPct` per scenario (42/49/52/88) | v2 `mastery[skill]` / [PROD] estimator (FR-OL-P1) |
| `dueMisses` per scenario (0/4/3) | [PROD] scheduler due count (FR-OL-P3) |
| Callout body (verbatim tag) | newest due miss's `missTag` note (v2 `ResultRec.missTag` → `lib`); tiered (I1) |
| `accuracyStat` value + bars | [PROD] real answer-accuracy aggregation over recent sessions (DATA-ACC-1) |
| `dueChecklist` rows (skill names) | scheduler `due_at` whole-skill list (D8) |
| ground/pitfall/question/worked/annotated/try copy | authored per-skill teaching assets (DATA-BLK-5) |
| `heroEyebrow` label | state-aware label from `ctx` + `firstExposure` (FR-CTX-8) |
`FR-DATA-BIND-1` Every row is a required binding; none may ship hardcoded. `FR-DATA-BIND-2` The surface MUST accept the target skill as a parameter (the reference fixes Punctuation / non-essential commas).

---

## 10. Non-Functional

`NFR-PERF-1` First paint < 100 ms; blocks are inline-styled and paint top-to-bottom as they stream (no blocking CSS). Only truly runtime values (context-driven `order/disp`, the self-explain echo, the try grade) are late-bound. `NFR-OFFLINE-1` The entire surface is **deterministic and offline** — no LLM dependency in E1 (the coach conversation, the only network need, is E1b). `NFR-THEME-1` Light + dark via `data-theme`; `--accent` and all tokens re-resolve. `NFR-STATE-1` `/learn/skill` is a **read-mostly** surface: it reads outer-loop signals and holds only ephemeral local UI state; it persists nothing (contrast the quiz, v2 §10.3).

---

## 11. Acceptance Criteria (testable)

Context selection — `AC-1` `selectLessonContext` returns `newSkill` for `firstExposure` or `masteryPct==null`; `refresher` only when `masteryPct>=80 && dueMisses==0`; `returning` for any `dueMisses>0`; else `newSkill` (§4.1). `AC-2` `requested` overrides all of the above (AL-17). `AC-3` A misconception tag on a non-due miss does **not** change the context; only `dueMisses>0` routes to `returning` (D1-b).

Composition — `AC-4` Each context renders exactly its recipe blocks in order, in the correct zone, and no others (§5.1). `AC-5` `newSkill` is inductive (`ground` leads, `completionTry` ends the main zone); `refresher` is rule-first and ends on the parting `pitfall`; `returning` ends on `rule` (§5.1/5.3). `AC-6` The main zone never ends on a tension block before the rule appears (GUARD-END-1).

Callout tiers — `AC-7` `returning` with a tagged newest due miss shows the callout with a single-item "On your last miss" eyebrow (not "Your pattern"); untagged hides the callout and the surface leads with `annotatedExample` (I1; FR-CTX-7). `AC-8` No `fix` line renders in any E1 callout (D6-2).

Accuracy & due — `AC-9` `accuracyStat` is absent at true first exposure and present when history exists — gated on data, not on the `newSkill` label (D7-1). `AC-10` The accuracy value renders alongside the bars and is labeled distinct from mastery; the hero mastery and the rail accuracy are different numbers with different labels (D7-2; AL-AC-8). `AC-11` `dueChecklist` lists whole skills with per-row skill-pinned drill links, only in `returning` (D8).

Interactivity — `AC-12` `completionTry` grades on click (✓/✗, reveals the correct choice on a miss) and records **no** attempt / moves **no** mastery (GUARD-NOWRITE-1); a wrong pick does not change subsequent blocks (FR-BLK-13). `AC-13` The self-explain note is echoed back in the `rule` block and is never stored/scored (D4). `AC-14` Exactly one "▸ start here" opener (on the lead block); no color-dot sequence renders (A2).

Invisibility & a11y — `AC-15` No screen state shows an S/C/Q/A letter, a Situation/Complication term, or an ordering code; no mode tabs / "Tuned for you" strip (FR-INV-1). `AC-16` Every role-colored block carries a text label; feedback is never color-alone; correct in light + dark (AL-25/AL-AC-8). `AC-17` The prototype inspector is absent when `showInspector` is off (production default).

---

## 12. Phasing & Open Questions

### 12.1 Phasing
**E1a (LEARN / newSkill) — unblocked, buildable now.** `selectLessonContext` (D1) + `completionTry` disposition (D3) are the two blockers, both resolved; `newSkill` (inductive), the `ground`/`pitfall`/`question` blocks (A1), self-explain (D4), accuracy gating (D7), and the end-on-win guard (D2/A3) all land here.
**E1b (returning / refresher).** The verbatim single-miss callout (D6/I1 tier-2/3), `annotatedExample`, `dueChecklist` (D8), `accuracyStat` for history states (D7-2 aggregation), `refresher` (ASC), and the **skill-anchored coach entry seed contract** (D4c). Also: the tier-1 aggregate callout behind the reviewed tag-clustering pipeline (N-5), and the intra-skill due checklist if sub-skill signals arrive.
**Consumer-owned (memo §4, no design answer):** `--accent` → `--color-bucket-*` aliasing, radius reconciliation, the upstream role→token translator, the hand-built 6-bar chart, the AA brand-CTA contrast split, and native re-authoring of the shell.

### 12.2 Open questions
`OQ-1` The exact answer-accuracy window for `accuracyStat` (last N sessions vs rolling) and how it is aggregated (DATA-ACC-1). `OQ-2` The reviewed tag-clustering pipeline that unlocks the tier-1 aggregate callout — taxonomy, review cadence, leak-lint (I1 tier-1; D6-1). `OQ-3` The lesson→coach seed contract: how a skill-pinned, lesson-context coach entry is expressed when there is no active `question_id` (D4c). `OQ-4` Whether the refresher parting caution is one `pitfall` block with a `framing` field or two authored instances (DATA-BLK-3). `OQ-5` Whether an authored intra-skill coverage checklist replaces the cross-skill due list once sub-skill signals exist (D8-B).

---

## 13. Decision → Requirement Traceability

| Decision (`Adaptive-Lesson-Decisions.md`) | Requirements / sections here |
|---|---|
| **D1** state → context selector | §4 (`selectLessonContext`); FR-CTX-1..8; AC-1/2/3; DATA-CTX-1/2 |
| **D2** end-on-resolution guard | §5.3; FR-CMP-7/8/9; GUARD-END-1; AC-6 |
| **D3** completionTry inert-to-scheduler, interactive | §6.3; FR-BLK-10/11/12/13; GUARD-NOWRITE-1; AC-12 |
| **D4** self-explain shown-back-local | §6.2; FR-BLK-6/7/8/9; AC-13 |
| **D5** render-time composition | §2.1; FR-CMP-1/2; DATA-BLK-4/5/6 |
| **D6** verbatim single-miss callout, no fix | §3.4; FR-BLK-16; DATA-CALL-1/2; GUARD-CALL-1; AC-7/8 |
| **D7** accuracy gated on data, ≠ mastery | §5.4; FR-CMP-10/11/12; FR-BLK-19; GUARD-ACC-1; DATA-ACC-1/2; AC-9/10 |
| **D8** cross-skill due list | §3.5; FR-BLK-18; DATA-DUE-1/2; AC-11 |
| **I1** callout fallback tiers | §3.4; DATA-CALL-1; FR-CTX-7; AC-7 |
| **A1** 3 beat-promotion blocks | §3.2; DATA-BLK-1/2/3; FR-BLK-1/2/3 |
| **A2** carry opener, drop color-dots | §6.4; FR-BLK-14/15; AC-14 |
| **A3** end on the win | §5.1/5.3; FR-CMP-4/7/8; AC-5 |
| **Framing** faithful 6→3 subset | §1.1; FR-CTX-1; FR-INV-1 |
| **AL-25 / AL-AC-8** color+label | §8; FR-INV-2; NFR-A11Y-2; AC-16 |

---

*End of E1 `/learn/skill` Implementation Specification. Normative and derived 1:1 from `English Coach - Learn Skill (E1).dc.html` + `Adaptive-Lesson-Decisions.md`; where they disagree, treat the prototype as the reference for behavior and this spec for production requirements, and reconcile explicitly. This surface consumes the v2 outer-loop signals (`PreACT-English-Coach-v2-Implementation-Spec.md` §5) and writes none of them.*
