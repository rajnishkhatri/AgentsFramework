# Adaptive Lesson — Binding Decisions (E1 /learn/skill)

**Resolves:** the D1–D8 + I1 binding memo. **Status:** ratified (design intent).
**References:** `Adaptive-Lesson-Protocol.md` (AL-*), `Lesson-Block-Schema.md`, `English Coach - Lesson Composer.dc.html`, `English Coach - Lesson (Adaptive).dc.html`.

Each ruling states the call, whether it matches your lean, and the reason. Decision IDs match your memo 1:1. Two blockers (D1, D3) are marked ⛔.

---

## 0 · Framing — is the 3-context composer a faithful subset?

**Verdict: faithful in stance, with two honest gaps — one of which is a real decision, not a loss.**

The three contexts preserve the load-bearing thing: the three **opening stances** — familiar-first (`newSkill`), error-first (`returning`), rule-first (`refresher`) — and the reorder-not-rewrite spirit (AL-10). The four modes you drop (`struggling`, `worked`, `diagnostic`, `annotated`) branch on signals your outer loop does not emit (`feelsProblem`, `prefersWorkedExamples`, `prefersVisual`, `justMissed`). **A mode you cannot trigger from state is not a lost capability — it is unreachable code.** Dropping them costs nothing you could have shipped honestly. AL-16 (default → `new`/`newSkill`) and the AL-25/AL-AC-8 a11y half survive. So: yes, ship the 3 contexts.

Two things to log, not to fear:

- **The `question` beat has no block home.** In the 6-mode model Q is a first-class narrative unit (the decision the tension forces). The block catalog has no question block, so beats→blocks silently drops Q. Fine for `returning`/`refresher` (they'd drop Q anyway). But `newSkill` = the `new` mode, which *keeps* Q — so `newSkill` loses a beat the full design keeps. **Cheap fix:** carry Q as a one-line framing question between the worked example and the try (one line of authored content, no new signal). Optional, but it's the only place the subset is lossy against intent.
- **`newSkill` as authored inverts the `new` mode's arc — flagging because it feeds D2.** The `new` beat mode is discovery/inductive: ground → tension → question → **rule** (rule *last*, AL-13). The composer's `newSkill` is expository/deductive: **rule** → worked → try → selfExplain (rule *first*, index 0). These are opposite pedagogies on the same content. Neither is wrong, but pick deliberately — see D2. (The rest of this doc assumes you keep the composer's deductive `newSkill`, since that's what's authored and what "ends on a win" describes.)

---

## 1 · D1 ⛔ — the state → context selector (net-new contract)

**Ruling — matches your lean, with the boundaries nailed down.** Author `selectLessonContext()` using only `{firstExposure, masteryPct, dueMisses, requested}`. It is the faithful 6→3 projection of §5 `selectMode`: `struggling`/`diagnostic` (and `worked`-when-due) collapse into `returning`; `worked`/`annotated`-when-not-due are indistinguishable from teaching without the `prefers*` signals, so they fold into `newSkill`.

```
selectLessonContext({ firstExposure, masteryPct, dueMisses, requested }):
  if requested                            → requested     // AL-17 analog: explicit pick always wins
  if firstExposure or masteryPct == null  → 'newSkill'    // AL-16 analog: safe default (D1d)
  if masteryPct >= 80 and dueMisses == 0  → 'refresher'   // the one transferable anchor from §5 (D1c)
  if dueMisses > 0                        → 'returning'    // review debt to clear (D1a/D1b)
  else                                    → 'newSkill'     // mastery < 80, nothing due — keep teaching
```

- **(a) newSkill → returning flip.** There is **no mastery threshold** for this flip — it is `dueMisses > 0`, full stop. Mastery gates only `refresher` (≥ 80). One due miss flips a learner to `returning`; below that the surface stays `newSkill` regardless of mastery (until ≥ 80 with nothing due → `refresher`).
- **(b) Tag vs due-ness.** **Due-ness selects; the tag does not.** A misconception tag on a *non-due* miss does **not** force `returning` — the scheduler owns re-surfacing. Within `returning`, the newest **due** miss's tag *populates* the callout (D6); an untagged due miss still routes to `returning` (there is debt) and the callout self-hides (I1 tier 3). So `returning`'s recipe must tolerate a missing lead block.
- **(c) refresher.** Requires `dueMisses == 0` **and** `masteryPct >= 80`. Floor = **80**, verbatim from §5. The ladder order guarantees `refresher` is only reachable when nothing is due (a due miss is tested first and wins).
- **(d) Unknown / first exposure.** → `newSkill` (AL-16 analog).

**Label nuance (non-blocking):** the context id `newSkill` also fires for "still learning, nothing due" — not just first exposure. Don't show a hard "New skill" label to a 60%-mastery learner; make the *visible* label state-aware (e.g. "Learn" on true first exposure, softer otherwise). The context id is unchanged.

---

## 2 · D2 — does AL-13 (end-on-resolution) govern the composer?

**Ruling — keep it as an explicit main-zone guard; matches your lean, restated for the block layer.** Do **not** retire AL-13 to beat-only. Retiring it risks a `returning` learner left staring at their error with no fix below — exactly what AL-13 exists to prevent.

Restate what "resolution" means per layer:
- **Beat layer:** resolution = the `rule` beat.
- **Block layer:** resolution = the **actionable win** — `completionTry` (or its consolidation `selfExplainPrompt`) for `newSkill`; the `rule`/`annotatedExample` fix for `returning`. The `rule` *block* is reference; the *win* is the learner doing it.

**The guard (block-layer AL-13):** the **main zone** must end on a resolution block — the win/consolidation for `newSkill`, the rule/fix for `returning` — and must **never end on `misconceptionCallout`** unless the rule/fix already appears above it. The **rail** (`accuracyStat`/`dueChecklist`/`coachEntry`) is exempt — it is ambient, not the narrative spine. `newSkill` leading with `rule` (index 0) is permitted; AL-13 governs the ending, not the opener.

---

## 3 · D3 ⛔ — completionTry: real graded rep or inert?

**Ruling — (a) inert *to the scheduler*, but interactive locally. Matches your lean, with one sharpening you must build.** The current composer renders dead buttons (the `correct` flag never reaches the DOM); that is a fidelity gap, not the intent. "No attempt recorded" ≠ "dead mock."

- **No persistence.** `completionTry` records **no** attempt, moves **no** mastery, touches **no** FSRS. `Scheduler.review()` stays the sole writer of skill state, fed only by the real Practice/drill surface. Reason: it's a *faded* worked example (●●○ vs ●●●) — scaffolded, hint-supported practice inside the teaching moment. Its promptHint nearly gives the answer; feeding that into FSRS would contaminate the mastery signal and let a warm-up game the schedule. Both wrong.
- **But interactive.** The `correct` flag **must** reach the DOM: click → immediate local grade (✓/✗) + reveal the one-line why. A wrong pick reveals the correct choice and the removal-test nudge.
- **A wrong pick does not change what the lesson shows next.** Local reveal only; the lesson is already composed for this context. Answer-branching is an E1b+ capability gated on signals you don't have mid-lesson.

Net: interactive-but-ephemeral. The "doable win" is a *felt* success, not a measurement.

---

## 4 · D4 — selfExplainPrompt: where does the free text go?

**Ruling — (b) shown back locally as the learner's own note; not stored, not scored.** Slightly beyond your (a)/(b) lean, landing on (b), and deferring (c).

The self-explanation effect comes from articulating; it's *strengthened* when the learner can see their words next to the rule that follows (the block sits before the explanation precisely so their answer becomes a reference point). Pure discard (a) keeps the generation effect but throws away the compare-to-rule payoff for one line of local state. (b) costs nothing (local component state, no persistence, no wire change) and is strictly more complete. Writes nothing to the scheduler (same principle as D3).

**Defer (c).** Handing text to the coach couples E1a to the skill-anchored coach entry contract you're (correctly) staging for E1b. Note (b) is forward-compatible: the same local note later seeds the coach with no re-architecting — so (b) is the right stepping stone, not a throwaway.

---

## 5 · D5 — where does blocks[] live?

**Ruling — render-time composition. Matches your lean, and it is core design intent, not just your plumbing preference.** The block system's thesis (schema, line 1): "a lesson is data — an ordered list of typed blocks — not a hand-built layout … change the context, not the code, and the screen recomposes." `compose()` is explicitly runtime. Persisting the composed order per skill would freeze the lesson to one context and destroy the adaptivity that is the system's whole reason to exist.

- **Not authored/persisted:** the block/beat **order**, and `role`/`zone`/`context`. These are resolved by the composer/translator from block `type` + context, upstream (as your §4 bind note already plans). The three context recipes are **shared config/code**, identical across all skills — not per-skill content.
- **Authored/persisted (raw pieces):** the one-line `rule` + `examples[]` (you have this), the per-item misconception tag (you have this), and the net-new per-skill **teaching assets** — worked-example steps, the `completionTry` item, `annotatedExample` callouts, the `selfExplainPrompt` text.

**So your ADR is smaller than D5 feared:** add *optional typed teaching fields* to the skill content type; do **not** add `blocks[]`/`zone`/`role`/`context`/`beats` to the wire. Confirmed: block/beat order is **not** authored content you persist.

---

## 6 · D6 — misconceptionCallout body/fix

**Ruling — (1) verbatim single-miss tag now, with the eyebrow reframed (see I1); (2) drop `fix` from v1. Matches your lean.**

- **(1)** A single-miss verbatim tag is acceptable for v1; the aggregate is a *stronger* version, not a *load-bearing* one. The block's purpose is to name the diagnosed error before teaching — a verbatim tag serves that. **But** don't render "Your pattern · X" over an `n=1` tag; that asserts a pattern you didn't compute. Reframe the eyebrow to a single-item claim (I1 tier 2). The aggregate waits for the reviewed tag-clustering pipeline (N-5/E1b).
- **(2)** Drop `fix`. No field backs it (don't synthesize corrective text with no provenance), and any authored corrective line risks your answer-leakage lint. **The fix already lives in the `rule` block below** — the callout *names* the error, the rule *fixes* it (clean split, and consistent with D2/AL-13: the lesson ends on the rule/fix). `fix` returns only when authored, provenance-tracked, leak-linted text exists (E1b).

---

## 7 · D7 — accuracyStat on a first-exposure surface

**Ruling — (1) omit when there's no data; (2) true accuracy for returning/refresher. Matches your lean, with one refinement: gate on data, not on the context label.**

- **(1)** A 6-bar trend on a skill with zero sessions is a fabricated chart — reject empty-state (b) and forward placeholder (c); absence is cleaner. **But** per D1, `newSkill` isn't only first exposure (it also fires for "learning, <80%, nothing due," where history may exist). So the rule is **"no session history → block self-omits; history exists → render"** — gate on data availability, not on the context being `newSkill`. (The `compose()` "unknown/empty tags skipped" rule already gives you this hook.)
- **(2)** **Yes — true answer-accuracy over a real session window; never the FSRS mastery/retrievability scalar.** The block is named `accuracyStat` and captioned "Last 6 sessions" — it claims share-correct, a *different quantity* from retrievability. Rendering the mastery scalar under an "Accuracy" label ships the known dashboard bug into the lesson. If the accuracy aggregation isn't ready, **omit** (per §1) rather than substitute — omission is honest, substitution is a bug. Mastery keeps its own honest, separately-labeled home (the "49% mastery" hero stat). Two stats, two labels, never crossed (AL-AC-8 spirit).

---

## 8 · D8 — dueChecklist: whole skills or intra-skill?

**Ruling — (A) whole due skills from `due_at`, with two constraints; (B) deferred. Partial override of the lean's framing.**

The mock's four comma sub-topics were illustrative and are **not buildable** from a whole-skill due signal — so don't fake an intra-skill checklist. Ship (A), but:

- **(i) Frame it as cross-skill "Due for review," not an intra-skill checklist.** Rows are whole due skill names driven by `due_at`. Don't title it "Clear these 4 [comma things]."
- **(ii) It belongs only where clearing debt is the point — `returning` (optionally `refresher`). Never in `newSkill`.** First-exposure / low-mastery-nothing-due has no debt (consistent with D1 and D7's data-gating).
- **cta → skill-pinned drill: yes,** and pin *per row* to that specific due skill (row-level deep link), so the action is "drill *this* skill," not a vague bulk clear.
- **(B) intra-skill micro-topics** remain a future authored-content feature (a static per-skill coverage map + sub-skill signals) — a different block from "due," gated to E1b+. Not v1.

---

## 9 · I1 — misconceptionCallout fallback ladder

**Ruling — (A) when the newest due miss is tagged; (C) hide when untagged; reject (B). Matches your lean.** A three-tier honesty ladder keyed to the evidence that actually exists:

1. **Recurring tag** (same/clustered tag on ≥ 2 due misses — E1b only): eyebrow "Your pattern · {theme}" + aggregate body. *(Full-strength D6; not v1.)*
2. **Newest due miss tagged** (~27%, v1): eyebrow reframed to a single-item, lower-confidence claim — **"On your last miss · {skill}"**, *not* "Your pattern" — body = that one verbatim tag. **= (A).**
3. **Due miss untagged** (~73%, v1): **hide the callout. = (C) as the floor.** `returning` then leads with `annotatedExample`/`rule` (its recipe must tolerate the missing lead block, per D1b).

**Reject (B).** A naked miss-count ("4 recent misses") asserts severity without diagnosis — it names a quantity, not the slip, so it fails the block's purpose and just adds an anxiety number with nothing actionable. Better to show nothing.

**`fix` line: absent in every v1 tier** (per D6-2). When a callout shows, it ends at the body; the resolution is the `rule` block below.

---

## What this unblocks

- **E1a (newSkill / LEARN) can start now:** D1 (selector) + D3 (completionTry) are the two blockers and are resolved above; D2, D4, D5, D6-behavior, D7-behavior and the a11y half of the invisibility contract also land on newSkill and are resolved.
- **E1b (returning / refresher):** D6 aggregate, I1 tier-1, D8 (B), and the skill-anchored coach entry (D4c) ride here.
- **Untouched by this doc (your call, per §4 of the memo):** token aliasing (`--accent` → `--color-bucket-*`), radius reconciliation, React/Tailwind re-authoring, the upstream role→token translator, the hand-built 6-bar chart, and the AA contrast split. My rulings are pedagogy/behavior and framework-agnostic — they port to any of those.

---

# Round 2 — reconciling the beat layer into the newSkill block composer

You adopted the **inductive** arc for `newSkill` (correctly — my own §2.2 makes `new` = SCQA = ground → tension → question → rule; the composer's rule-first recipe was the `refresher` = ASC ordering wearing the `new` label). Prototype: `English Coach - E1a newSkill.dc.html`. Spec folded into Protocol §5.1 + AL-13 block-layer clause, and the Block-Schema catalog (+3) / New-skill recipe.

## A1 — promote 3 beats to block types; generic first-exposure tension

**Ruling — faithful. Same tension beat role, two block treatments. Your role/zone reads are correct.** Add `ground` (neutral/main), `question` (accent/main), `pitfall` (warning/main). Your AL-2 color reads hold.

- **The tension question:** yes — a **generic, no-miss-data** first-exposure tension is faithful and *distinct* from `misconceptionCallout`. They are two treatments of the **one** tension/warning beat, selected by context: at first exposure `pitfall` names the skill's **structural** trap ("a clause can need a pair of commas — or none — and the wrong choice flips the meaning"); on return `misconceptionCallout` names the learner's **miss-specific** pattern. This tracks §2.1 exactly — the beat's purpose is "the specific, felt difficulty"; the *quantified slip* is the returning ideal, the *structural trap* is the honest first-exposure form (a new learner has no misses to quantify). The copy is already written generically in `…(Adaptive).dc.html`.
- **Endorse dedicated blocks** over AL-23's `ground → rule(situation)` / `question → prompt` sketch — dedicated blocks honor the distinct beat roles and colors instead of overloading `rule`.

## A2 — carry the beat affordances onto the composer?

**Ruling — carry AL-12 (opener); drop AL-14 (color dots).** Deciding rather than defaulting.

- **AL-12 "▸ start here" → carry it** onto the lead block (`ground`). Cheap wayfinding + reassurance at the top of a guided sequence; reinforces discover-first. One opener.
- **AL-14 color-dot sequence → drop** for the block composer. Its job is to make a *variable* order legible; with a **fixed** inductive order and no mode-switch it tracks nothing and reads as decorative machinery (against the minimal / don't-expose-the-machinery spirit — and each block's role color already carries meaning inline). Reintroduce only if a visible context switch (returning/refresher tabs) later shares the surface.

## A3 — where does inductive newSkill end?

**Ruling — end on the `completionTry` win. Your lean is right, and it reconciles AL-13 + D2 rather than choosing between them.** Both rules say "end resolved"; they differ only in resolution *depth*:

- Beat layer — `rule` is the deepest block available → end on `rule`.
- Block layer — *application* blocks exist after the rule → **applying** the rule (`completionTry`) is a deeper resolution than **stating** it → end on the win.

The mid-recipe `rule` is not an AL-13 violation: AL-13 forbids ending on tension *before the rule appears*; here the rule appears (the discovery payoff), then is applied. Formalized as the block-layer guard in Protocol AL-13. So the inductive `newSkill` main zone is: **ground → pitfall → question → selfExplain → rule → workedExample → completionTry** (self-explain sits before the rule — D4's compare-to-rule payoff — and the applied win closes).
