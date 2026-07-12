---
title: 'Epic E — Adaptive-Lesson delivery: INTEGRATION Stage-1 brainstorm'
type: brainstorm
epic: E
stage: 1
scope: 'how the design agent''s Adaptive-Lesson artifact (4 beats / 9 blocks / 6 modes) binds to our flat Tutorial schema + Frontend Ring on /learn/skill — NOT re-deciding whether to build the screen'
date: 2026-07-11
status: Open — awaiting human direction gate
artifact: eng-coach-ui-design/lesson-delivery/
parent: docs/plan/preact-parity-epic-E-lesson-generation.brainstorm.md
sibling_design: docs/plan/preact-parity-epic-E-lesson-design.brainstorm.md
board: docs/plan/preact-parity-sprint-board-E.md
method: 'sdd-brainstorm — read all 3 design specs + 2 reference .dc.html; verified repo surface via explore subagent (17 tool-uses, 13-row findings table)'
---

# Epic E — Adaptive-Lesson delivery: INTEGRATION Stage-1 brainstorm

> **What arrived.** The design agent delivered `eng-coach-ui-design/lesson-delivery/` — not a single
> mockup but **two composable content systems + a protocol contract + a Playwright rubric**. This
> brainstorm decides how (and how much of) that model binds to our repo. It does **not** re-open the
> E1 build decision (already {D1 author-bank, lesson-in-E1, resolve-pin} × {A1 flat, B2 LLM-gen}).

## What the artifact actually is (three layers, not one)

| Layer | File | Model | Our current equivalent |
|---|---|---|---|
| **Adaptive-Lesson Protocol** | `specs/Adaptive-Lesson-Protocol.md` | 4 narrative **beats** (ground/tension/question/rule) × **6 learner modes** → a reordering engine (hidden SCQA) + an **invisibility contract** | *nothing* — no beat, no mode |
| **Lesson-Block schema** | `specs/Lesson-Block-Schema.md` + `.json` | 9 typed **blocks** (rule, workedExample, completionTry, annotatedExample, misconceptionCallout, dueChecklist, accuracyStat, selfExplainPrompt, coachEntry) + a **composer/registry** that orders blocks by context | *nothing* — `Tutorial` is one flat record |
| **Design language** | `sources/*.dc.html`, `standalones/*.html` | minimal, no-card, type-as-signal, color-coded; **uses our design system verbatim** (`--color-*`, `--accent`, `radius 13px`, `.btn`) | ✅ tokens resolve (see P-5) |

The two model layers are **nested**: `AL-23` says a beat renders as ≥1 block. So the block schema is the
superset; the beat model is a narrative ordering *on top of* blocks. Both are far richer than what E1
locked (a flat `body_md` + `examples[]`).

---

## Premise audit (integration-relevant; every row verified this session)

| # | Premise | Status | Evidence |
|---|---------|--------|----------|
| P-1 | `Tutorial` is flat: `{id, subject, skill_id, body_md, examples[], generated_from, reviewed}` — **no** `beats`/`blocks`/`mode`/`faded`/`misconception` field | **verified** | `frontend/lib/wire/engine_entities.ts:273-282` |
| P-2 | `Tutorial` / `ProgressPoint` have **zero non-test consumers**; only the two DB implementers + the interface decl reference `getTutorial`/`listProgressPoints` | **verified** | `drizzle_engine_db.ts:612,629`; `in_memory_engine_db.ts:340,344`; no UI/hook callers |
| P-3 | **No write path exists** — no `insertTutorial`/`upsertTutorial` on the `EngineDb` interface; `seedTutorial` is test/in-memory-only | **verified** | `engine_db.ts:159-162` (read-only interface); `in_memory_engine_db.ts:81-83` (test seed) |
| P-4 | `misconception` is **already a real DB column** (nullable, author-captured) on `Question` **and** `TestItem` (ADR-0027/C2 migration) — the artifact's `misconceptionCallout` has a genuine data anchor, but it's per-**item** free text, NOT a per-**skill** tag library | **verified** | `engine_entities.ts:76-77,136-152`; `frontend/drizzle/0001_add_misconception_to_test_item.sql` |
| P-5 | Every base token the artifact assumes resolves in **light + dark**: `--color-bg/fg/muted/border/surface/warning/success` + `--accent`; the 6 bucket accents exist as **`--color-bucket-<name>`** (the artifact's `--b-punct` shorthand is a **naming reconciliation**, not a gap) | **verified** | `frontend/app/generated-theme.css:4-25` (light), `:46-69` (dark) |
| P-6 | The route `frontend/app/(coach)/learn/skill/` **does not exist** (404); `nav_model.ts` marks `skill` `comingSoon:true`; its comment names `getTutorial`/`listProgressPoints` as the deferred "second ADR-0006 amendment" | **verified** | `find` output; `nav_model.ts:73-75` |
| P-7 | `missesOnSkill` is a **live** join (`use_coach.ts:111` → `coach_surface_vm.ts:83-100`) but a **miss-count aggregate**, not a misconception-tag surfacing | **verified** | cited files |
| P-8 | The `.dc.html` sources are a **runtime DC component system** (`<x-dc>`, `sc-for`, `sc-if`, `DCLogic`), NOT React/Next — they load a design-system bundle. They are a **visual reference**, not portable code | **verified** | `sources/*.dc.html` head loads `_ds/agentsframework-ui-*/`; `<script type="text/x-dc">` |

**Corrected framing carried in:** the artifact is a **design + contract reference**, not a drop-in. Two of its
three layers (beats, blocks) have **no home in the wire kernel** and would each be an ⚠️ Ask-first schema
change to `Tutorial` (a `wire/` module — W2 says Python is the source of truth, so a `Tutorial` field add
is a **cross-language** change, not a frontend-only one). The design language layer, by contrast, ports
cleanly (P-5). **The central integration question is therefore: how much of the model do we absorb into
the schema now vs. keep as a forward-compatible seam vs. reject as over-scope for E1.**

---

## D0 — is there a present defect to close first?

No. The system is **not live** on this surface — the route 404s and `getTutorial` returns `null` for every
skill (P-2, P-6). There is no open defect to close ahead of the capability work; the risk is entirely
*forward* (forging provenance — see [[preact-s3-bounded-session-spec]]), which the directions below carry.
So no D0; the six directions stand.

---

## Directions (how much of the artifact model to integrate)

**Ordering axis:** each direction absorbs *more* of the artifact's model into durable schema. I-1 the least
(render-only), I-6 the most (full block composer). The gate is choosing the right point on this ramp for E1.

### I-1 — **Design-language only; ignore both model layers** *(high-prob; follows the shipped `SummaryView.tsx` pattern)*
Keep `Tutorial` flat exactly as-is. Build the `/learn/skill` route as a React screen that renders `body_md`
(via `react-markdown` per §2 stack) + `examples[]` as a ✓ list, styled with the artifact's **visual
language** (no-card, type-as-signal, `--accent` scoping, `radius 13px`, brand-CTA AA split). The 4-beat / 9-block
/ 6-mode machinery is **not built**. This is the sibling design brainstorm's leading D1 direction, re-confirmed
against the richer artifact.
- **Tradeoff:** ships E1 with zero schema change, zero cross-language wire churn, fastest path. But throws
  away the artifact's actual *thesis* (adaptive re-sequencing) — we'd be taking its CSS and dropping its brain.
- **What breaks if chosen:** nothing architectural. The cost is *pedagogical*: the lesson is static, so the
  §7.1 faded ladder and mode-adaptation become P2/P3 re-work, and the design agent's core contribution is shelved.
- **Invariant stressed:** none. This is the null-integration baseline.

### I-2 — **Flat schema + one reserved seam for the block model** *(high-prob; mirrors the S3 "seam-not-forge" discipline)*
I-1's render, **plus** one deliberate forward-compatibility seam: render `body_md`+`examples[]` today, but
structure the *component tree* as a proto-`LessonBlock` registry with exactly the `rule` block implemented,
and an **annotated empty slot** where `workedExample`/`completionTry`/`misconceptionCallout` will mount. No
schema change; the seam is component-only.
- **Tradeoff:** near-I-1 cost, but the P2 diff becomes "add a block type + a render branch" (the artifact's own
  `Extending` recipe) rather than a layout rewrite. Slightly more E1 code for a much cleaner P2.
- **What breaks if chosen:** risk of a **G1 new-abstraction** flag if the one-block "registry" looks like
  speculative generality. Mitigate by keeping it a plain `switch(block.type)` with one case, not a class hierarchy.
- **Invariant stressed:** G1 (new-abstraction gate) — must justify the registry buys the P2 path.

### I-3 — **Absorb the 9-block schema into `Tutorial` (blocks, no modes)** *(exploratory; content-as-data shift)*
Extend `Tutorial` from `{body_md, examples[]}` to `{blocks: LessonBlock[]}` (a discriminated union mirroring
`lesson-blocks-schema.json`). Build the composer/registry for real. **Skip** the beat/mode reordering — blocks
render in authored order. This is the artifact's `Lesson-Block-Schema.md` **without** `Adaptive-Lesson-Protocol.md`.
- **Tradeoff:** unlocks worked-example/completion-try/misconception blocks (the CLT pedagogy) as *first-class
  authored data* — the real payload. But `Tutorial` is a **`wire/` kernel** (W1/W2): adding `blocks[]` is a
  cross-language schema change (Python source-of-truth + `__python_schema_baseline__.json` diff + the B2 generator
  must now emit blocks). This is a **⚠️ Ask-first + ADR** change of real size.
- **What breaks if chosen:** the B2 tutorial generator (`tutorial_generation.py` + `tutorial_generator.j2`) must
  emit *validated block JSON*, and the provenance cascade must verify **each block type** (a worked-example with a
  wrong step is worse than a flat rule with a wrong sentence). Bigger authoring/verification surface.
- **Invariant stressed:** W2 (wire mirrors Python — cross-language change), G1, and the ADR ratchet (schema-shape ADR).

### I-4 — **Absorb blocks AND the beat/mode engine** *(exploratory; the artifact's full thesis)*
I-3 **plus** the `Adaptive-Lesson-Protocol`: author all four beats, add a mode selector driven by learner state
(the `selectMode` protocol §5), render with the invisibility contract. This is the artifact *as designed*.
- **Tradeoff:** delivers adaptive re-sequencing — genuinely novel and the design agent's headline. But it is a
  **large** durable commitment: schema carries beats, a `selectMode` translator consumes v2 outer-loop signals
  (`mastery`/`missTag`/`due`), and the invisibility contract becomes a **testable requirement** (`AL-AC-2` — no
  S/C/Q/A ever surfaces). The artifact even ships the Playwright suite for it (`tests/adaptive-lesson.spec.js`).
- **What breaks if chosen:** E1 stops being a parity screen and becomes a **new engine concept** (mode selection),
  echoing the [[preact-ui-gap-brainstorm]] "session-length is a NEW engine concept" pattern. Program-rule-#4
  releasability almost certainly forces a split. `selectMode` needs `feelsProblem`/`prefersWorkedExamples` inputs
  we do **not** compute (only `mastery`/`missTag`/`due` exist) — so modes would ship **partially data-fed**, defaulting
  to `new` (safe, per `AL-16`) for most learners → the adaptivity is mostly dormant at launch. `needs-probe` on
  whether the outer loop emits enough signal to make ≥3 modes fire.
- **Invariant stressed:** W2, G1, ADR ratchet, **and** program-rule-#4 (single releasable increment). High.

### I-5 — **Misconception-first slice (the one block with real data)** *(exploratory; under-used-signal lens)*
Ignore beats/modes/most blocks. Build **only** the `misconceptionCallout` block for real, because it is the
**one block backed by live data** (P-4: `misconception` column exists on items; P-7: `missesOnSkill` join is live).
Wire `whyMissed = lib[misconception].label + fix` from the learner's recent misses on this skill. Everything
else stays flat (I-1 render).
- **Tradeoff:** highest *pedagogical value per unit of new schema* — it's the SD-3 "why you missed these" region
  the parity report already wants, and it needs **no `Tutorial` change** (reads item-level `misconception` + the
  existing miss join). But there is **no misconception *tag library*** (taxonomy → label/fix text) — only the raw
  free-text column. So this direction's real work is **authoring that library** (16 tags per the pedagogy spec
  §3.3) + a lookup, not schema.
- **What breaks if chosen:** the leakage discipline — `whyMissed` text must never reveal the answer (DATA-7 /
  hint-leakage lint, same gate as hints [[coach-bank-hints-brainstorm]]). And it surfaces `misconception` values
  that were author-captured but never before *rendered* → data-quality exposure.
- **Invariant stressed:** the recalled-content/leakage discipline (enumerate every surface: label, fix, evidence).

### I-6 — **Full composer as a generated-UI artifact (iframe)** *(exploratory; wrong-abstraction check)*
Treat the whole adaptive lesson as an **agent-emitted generative-UI widget** rendered in the sandboxed iframe
(`useComponent`, §15) rather than native React — the artifact is *already* self-contained HTML.
- **Tradeoff:** near-zero React work; the artifact's standalone HTML could render almost as-is. But this is the
  **wrong abstraction**: generative-UI iframes are for *agent-authored, per-turn* artifacts (charts, diagrams),
  not a *core navigational screen*. It would violate the CSP/sandbox intent (a primary screen behind
  `sandbox="allow-scripts"`), break a11y/focus/routing, and can't bind to typed engine reads. **Named to be
  rejected** — it's the tempting shortcut the artifact's HTML-completeness invites.
- **What breaks if chosen:** F-R1 (no domain logic escaping to an opaque iframe), the a11y contract (U4/U5), and
  the whole point of the typed wire layer. Reject.
- **Invariant stressed:** §15 sandbox intent + F-R1. (Anti-direction — documents why not.)

---

## Dependency structure

- **Sequenced:** I-3/I-4 (schema absorption) **block** on a `Tutorial` wire change → Python-side + baseline diff +
  B2-generator update → each is an ADR predecessor. I-5 blocks on **authoring the misconception library**, not on schema.
- **Independent / do-regardless (no gate):** the **design-language** port (P-5 tokens), the **route shell**
  (`app/(coach)/learn/skill/page.tsx`), the **`comingSoon:false` flip** + 2 dormant entry points, and the
  **`TutorialRepo` port + composition wiring** (needed by *every* direction that renders a tutorial at all).
  These are shared substrate under I-1…I-5 alike — build regardless of the model-depth pick.
- **The real decision is a capability-depth axis, not a yes/no:** I-1 (render) → I-2 (seam) → I-3 (blocks) →
  I-4 (blocks+modes). More absorbed model = more durable pedagogy **and** more cross-language schema + provenance
  surface + releasability pressure. I-5 is *orthogonal* — a data-backed slice that can ride on top of any of I-1..I-4.

---

## Leading direction: **I-2 (flat + reserved block seam) for E1, with I-5's misconception slice as the one data-backed block, and I-3/I-4 explicitly deferred to a schema ADR**

Rationale traces to the locked E1 decisions and the verified surface:
- E1 already chose **A1 flat now → faded cards to P2**. I-2 is the faithful integration of that: render flat,
  but shape the tree so the artifact's block registry is the P2 diff (its own `Extending` recipe), not a rewrite.
- **I-5 rides on top** because `misconceptionCallout` is the **only** block with live data (P-4/P-7) and it *is*
  the SD-3 region parity already wants — so E1 gets one real, pedagogically-load-bearing block "for free"
  (no `Tutorial` change), while the rest stay flat.
- **I-3/I-4 are deferred, not rejected** — they're the artifact's real value, but absorbing `blocks[]`/`beats`
  into a `wire/` kernel is a cross-language schema ADR (W2) and I-4 additionally trips program-rule-#4. Those
  earn their own spec + ADR once E1 ships and we've measured whether the outer loop even emits enough signal to
  make modes fire (the I-4 `needs-probe`).

**Hypotheses:**
- *Works because* every visual primitive the render needs already exists in siblings + tokens (P-5), the one
  data-backed block reuses the live miss join (P-7) + existing `misconception` column (P-4), and the flat render
  reuses `react-markdown` (§2). It's recombination, not new infrastructure.
- *Safe because* it changes **no `wire/` schema** (no cross-language churn), pairs every filled accent with its
  `on-*` foreground (AA), keeps the sidebar + tab bar (non-focus screen, per sibling P-5), and the misconception
  text goes through the **same leakage lint as hints** so no answer leaks (I-5's stressed discipline).
- *Forward-compatible because* the reserved seam means the P2 upgrade to real blocks is additive (a block type +
  a render case + a generator change), and the mode engine (I-4) layers *above* the block composer (`AL-23`)
  without disturbing it.

**Do-regardless hygiene (build under any pick):** `TutorialRepo` port + composition wiring · route shell ·
`comingSoon:false` flip + 2 dormant entry points · token naming reconciliation (`--b-punct` → `--color-bucket-*`).

---

## Human gate — pick the integration depth (independent tracks)

1. **E1 lesson-model depth** (pick one): **I-1** render-only · **I-2** flat + reserved block seam *(recommended)* ·
   **I-3** absorb blocks into `Tutorial` (schema ADR) · **I-4** blocks + adaptive modes (schema ADR + likely split).
2. **Misconception slice (I-5)** — ride the one data-backed `misconceptionCallout` block on top of the depth pick
   *(recommended yes — it's the SD-3 region and needs no schema change)*, or defer the whole "why you missed" region to P2.
3. **Faded ladder / adaptive modes** — confirm these stay **P2/P3** (deferred to a schema ADR after we probe
   outer-loop signal), or pull the mode engine into E1 now (I-4).
4. **Do-regardless (no gate, just confirm):** design-language token port · route shell + repo/composition wiring ·
   `comingSoon:false` flip · leakage-lint on any rendered misconception text.

> **Note on the artifact's own spec/tests.** `Adaptive-Lesson-Protocol.md` (the `AL-*` requirements) and
> `tests/adaptive-lesson.spec.js` are **the design agent's contract for the full I-4 model** — they become our
> acceptance criteria *only if* we pick I-3/I-4. Under I-2 they are reference, not obligation. Don't inherit the
> `AL-AC-*` acceptance rubric wholesale into the E1 spec unless the depth pick actually builds that layer.

## Open integration questions (gate with the depth pick)

1. **Schema home for blocks (if I-3/I-4):** does `blocks[]` live on `Tutorial` (wire kernel, cross-language) or
   in a *new* `LessonPlan` wire type that references a flat `Tutorial`? (Latter isolates the churn.)
2. **Mode-signal probe (blocks I-4):** does the v2 outer loop actually emit `feelsProblem`/`prefersWorkedExamples`,
   or only `mastery`/`missTag`/`due`? If only the latter, ≥3 of 6 modes are dormant at launch → is partial adaptivity
   worth the schema cost now? (`needs-probe` — measure before committing to I-4.)
3. **Misconception library authoring (I-5):** the 16-tag taxonomy (pedagogy spec §3.3) — author it in `research/`
   → generate → leakage-lint → review (the hint cascade), or start with the raw free-text column and no library?
4. **Token reconciliation:** rename in a shared map (`--b-punct → --color-bucket-punctuation`) at the composition
   seam, or teach the render to read `--color-bucket-*` directly? (Latter — no new indirection.)
5. **DC-vs-React:** the `.dc.html` sources are non-portable (P-8) — confirm we treat them as **visual spec only**
   and re-author in React/Tailwind, not attempt to run the DC runtime in Next.
