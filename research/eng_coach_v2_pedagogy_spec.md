---
type: specification
title: PreACT English Coach — v2 Implementation Specification (pedagogy)
description: Normative instructional-design spec for the PreACT English Coach — misconception library, faded worked examples (Skill detail), Hattie & Timperley feedback, content-validation lint, and the deterministic autograder. Source of truth for Epic E lesson structure.
tags: [research, eng-coach, pedagogy, specification]
---

# PreACT English Coach — v2 Implementation Specification

**Version:** 1.0 · **Status:** Build-ready · **Companion to:** `PreACT-English-Coach-Spec.md` (design spec, §11 = v2 overview)
**Reference implementation (source of truth):** `English Coach - Prototype v2.dc.html`

> **How to read this document.** This is an engineering requirements + technical-design spec for building the v2 coaching improvements. Every behavior, data shape, interaction, and binding below is **derived from the reference prototype** and is intended to be reproduced 1:1. Where the production system must go beyond the prototype (real LLM, persistent mastery model, content pipeline), the prototype behavior is stated as the **reference/fallback** and the production requirement is marked **[PROD]**.
>
> **Traceability contract.** Requirements are numbered `FR-*` (functional), `NFR-*` (non-functional), `DATA-*` (data), `ENG-*` (engine), `GUARD-*` (guardrail), `AC-*` (acceptance). §9 maps **every** screen, control, navigation edge, and rendered value to its data source so nothing is left to interpretation. Identifiers in `monospace` are the exact names in the reference code.

---

## 1. Scope & Goals

### 1.1 What v2 adds over v1
v1 depicted coaching with fixed strings. v2 makes it a working **two-loop tutor (VanLehn)** driven by a **misconception-tagged item bank**: an outer loop that selects/spaces items, and an inner loop that responds turn-by-turn with the least assistance sufficient to unstick the learner, never leaking the answer.

### 1.2 In scope
- Data model: item bank, misconception-tag library, session, mastery, result records.
- Inner-loop engine: classify → verify → least-assistance ladder (pump → hint → prompt → assertion) + answer-leakage guard + reasoning trace.
- Outer-loop sequencer: selection, difficulty, spacing, interleaving, mastery-gating, "why this item next".
- Feedback (Hattie feed-up/back/forward), self-explanation, understanding gauge.
- Scaffolding/fading (faded worked examples) and affect handling.
- Full 7-screen desktop app, all interactions and navigation.
- **[PROD]** live-LLM coach contract behind the same guardrails, with the deterministic engine as fallback.
- Evaluation/autograder + acceptance criteria.

### 1.3 Out of scope (this version)
Multi-user/teacher/admin, auth, payments, native shells, real ACT-licensed content, responsive mobile layouts (desktop-scoped, matching v2; mobile is a later phase), authoring UI. Content is authored as data (§3.6).

### 1.4 Target platform
Single-student desktop web app. Design width **1240px** content frame (`$preview` width 1240, height 900). Light + dark themes. AgentsFramework UI design system (§2.4).

---

## 2. System Architecture

### 2.1 The two loops
```
                         ┌─────────────────────────── OUTER LOOP ───────────────────────────┐
                         │  Selects & spaces items by skill / difficulty / due / mastery.    │
                         │  buildSession() → queue[]   ·   nextItem() → advance + record      │
                         │  whyNext() → rationale       ·   mastery{} gates & schedules        │
                         └───────────────┬───────────────────────────────────────────────────┘
                                         │ loads one item
                                         ▼
                         ┌─────────────────────────── INNER LOOP ───────────────────────────┐
   student attempt ────► │ classify → verify → SELECT least-assistance move → (student turn)  │
                         │ escalate only on repeated failure:  pump → hint → prompt → assertion│
                         │ leaks() guards every non-assertion turn  ·  reasoning trace logged  │
                         └───────────────┬───────────────────────────────────────────────────┘
                                         │ solved (correct / prompt-satisfied / asserted)
                                         ▼
                         Feedback (Hattie) → self-explanation → gauge → outer loop advances
```

### 2.2 Logical components
| Component | Responsibility | Reference | Production |
|---|---|---|---|
| **Item bank** | Content + metadata + tagged distractors | `bank[]` (in-memory) | **[PROD]** content store / API + authoring pipeline |
| **Misconception library** | tag → reusable coaching (pump/hint/prompt/assertion) | `lib{}` | **[PROD]** versioned content, same schema |
| **Classifier** | map response → correct \| misconception tag | `classify()` | Deterministic (answer key). MUST stay non-LLM |
| **Grammar/answer verifier** | decide correctness | `choice.correct` flag | Deterministic. MUST stay non-LLM |
| **Inner-loop tutor** | pick move, compose turn, log reasoning | `composeTurn()` | Deterministic fallback + **[PROD]** LLM generator behind guardrails (§8) |
| **Leakage guard** | block answer in pump/hint/prompt | `leaks()` | Deterministic gate on every generated turn (§8.4) |
| **Sequencer** | build/advance queue; mastery | `buildSession()`, `nextItem()`, `mastery{}` | **[PROD]** BKT/IRT + spaced-repetition scheduler (§5.5) |
| **Feedback composer** | Hattie cards, self-explain, gauge | `renderVals().fb` | Deterministic |
| **Coach chat** | history-aware Q&A | `coachReply()` (keyword) | **[PROD]** LLM grounded in item + history (§8) |
| **Telemetry/logging** | per-turn log for review | reasoning trace (in-UI) | **[PROD]** persisted event log (§10.3) |

### 2.3 Client state ownership
In the prototype, all state is a single component `state` object (§9.1). Production keeps the **session/interaction state on the client** for latency, and persists **mastery, results, due schedule, and turn logs** to a backend (§10.3). The coach-generation call is the only network dependency of the inner loop; it must degrade to the deterministic engine when unavailable (§8.5).

### 2.4 Design system binding
All UI uses **AgentsFramework UI** (`_ds/agentsframework-ui-…/styles.css` + `_ds_bundle.js`). Tokens: `--color-bg/-fg/-muted/-accent/-surface/-surface-sunken/-selected/-border/-danger/-success/-warning`; six bucket accents `--b-rhetoric/-usage/-punct/-org/-struct/-concise` (defined in a `<helmet><style>`, light + dark). Components used: `.btn`(`-default/-outline/-ghost/-icon`, `-sm/-md/-lg`), `.badge`(`-accent/-default`), `.nav-item`(`.is-active`), `.tabs-list/.tabs-trigger.active`, `.composer/.composer-box/.composer-input/.composer-send/.composer-iconbtn`, `.separator-h`, `.text-muted`. **DATA-STYLE-1:** no color/type/spacing may be introduced outside these tokens.

---

## 3. Data Model (Axis B — the fuel)

Types are given as TypeScript for precision; a JSON-Schema equivalent is normative for content validation (§3.6). Field names match the reference exactly.

### 3.1 Skill buckets
```ts
type SkillKey = 'punctuation' | 'usage' | 'rhetoric' | 'organization' | 'structure' | 'conciseness';
```
`DATA-1` Each bucket has fixed presentation metadata (name, share-of-test, accent var). Reference `bmeta[]`:

| key | name | share | accent var |
|---|---|---|---|
| rhetoric | Rhetoric | 27% | `--b-rhetoric` |
| usage | Usage | 21% | `--b-usage` |
| punctuation | Punctuation | 19% | `--b-punct` |
| organization | Organization | 19% | `--b-org` |
| structure | Sentence Structure | 8% | `--b-struct` |
| conciseness | Conciseness | 6% | `--b-concise` |

### 3.2 Item
```ts
interface Choice {
  l: 'A' | 'B' | 'C' | 'D';   // stable letter, display + answer key
  t: string;                   // choice text (may be "NO CHANGE" or a mark like ":")
  correct?: true;              // present on exactly one choice
  tag?: MisconceptionTag;      // present on every NON-correct choice
}
interface Item {
  id: string;                  // unique, kebab: "<skill>-<concept>-NN"
  skill: SkillKey;
  skillName: string;           // display name (matches §3.1)
  color: string;               // bucket accent var, e.g. "var(--b-punct)"
  standard: string;            // machine code, e.g. "PUN.NONESS.COMMA"
  standardLabel: string;       // human standard, e.g. "Commas — non-essential clauses"
  difficulty: 1 | 2 | 3;
  pre: string;                 // sentence text before the underlined span
  underline: string;           // the tested span (the ACT "underlined portion")
  post: string;                // sentence text after the span
  tail: string;                // trailing context sentence, muted ("" if none)
  stem: string;                // question stem ("Which choice is correct?")
  choices: Choice[];           // exactly 4
  correctLetter: 'A'|'B'|'C'|'D';
  correctText: string;         // the correct choice's text, used in the recap span + leaks()
  whyCorrect: string;          // explanation of the correct answer
  heuristic: string;           // the reusable "worked heuristic" / next-move
  selfExplain: string;         // self-explanation prompt shown on Feedback
  rule: string;                // one-line rule under test
}
```
`DATA-2` `choices.length === 4`. `DATA-3` exactly one choice has `correct:true` and its `l === correctLetter` and its `t === correctText`. `DATA-4` every non-correct choice has a `tag` present in `lib` (§3.3). `DATA-5` `color` MUST be the accent var of `skill`. `DATA-6` `standard` unique-ish machine code; `standardLabel`, `whyCorrect`, `heuristic`, `selfExplain`, `rule` all non-empty.

### 3.3 Misconception tag & library (the linchpin)
```ts
type MisconceptionTag = string; // kebab id, e.g. "drops-commas-brevity"
interface MiscEntry {
  label: string;      // short human name of the error ("Trades punctuation for brevity")
  pump: string;       // ladder rung 0 — highest ICAP, student generates
  hint: string;       // ladder rung 1 — points at the feature
  prompt: string;     // ladder rung 2 — fill-in-the-blank keyword
  assertion: string;  // ladder rung 3 — states the step/answer (MAY reveal)
}
type MiscLibrary = Record<MisconceptionTag, MiscEntry>;
```
**Template slots:** `pump`/`hint`/`prompt`/`assertion` may contain `{underline}` and `{choice}`, replaced at runtime by `fill()` with the item's `underline` and the chosen letter.
`DATA-7` `pump`, `hint`, `prompt` MUST NOT contain the answer (enforced by authoring lint = `leaks()` run against every library string for every item that uses the tag; §3.6, §8.4). `DATA-8` `assertion` MAY reveal. `DATA-9` a tag is reusable across items and skills; coaching is grounded per-item via the template slots.

The 16 shipped tags (see reference `lib{}` for full strings): `drops-commas-brevity`, `that-vs-which`, `recast-ing`, `agrees-with-nearest-noun`, `redundant-restatement`, `wordy-hedge`, `comma-splice`, `transition-contrast-vs-cause`, `colon-needed`, `semicolon-misuse`, `pronoun-agreement-number`, `dangling-modifier`, `fragment-no-verb`. *(13 defined in v2; extend freely — every screen picks up new tags automatically.)*

### 3.4 Session (outer-loop working set)
```ts
interface ResultRec { id: string; skill: SkillKey; skillName: string; color: string;
                      firstTry: boolean; missTag: MisconceptionTag | null; }
interface Session {
  queue: string[];                 // ordered item ids
  pos: number;                     // 0-based index of current item
  results: ResultRec[];            // one per completed item (deduped by id)
  startMastery: Record<SkillKey, number>;  // snapshot at session start (for delta)
  focus: SkillKey;                 // the session's headline skill
}
```
`DATA-10` `results` is deduped by `id` (re-completing an item replaces its record). `DATA-11` `firstTry === (attempts[0] === correctLetter)`. `DATA-12` `missTag` = tag of the first attempted choice when wrong, else `null`.

### 3.5 Mastery
```ts
type Mastery = Record<SkillKey, number>; // 0..100 (%), display + gating signal
```
Reference seed: `{punctuation:49, usage:71, rhetoric:58, organization:66, structure:74, conciseness:81}`. `DATA-13` a confirmed-understood item nudges `mastery[skill] += 4` capped at 99 (`gaugeGot`; §5.4). **[PROD]** replace the flat nudge with a real mastery estimator (§5.5).

### 3.6 Content validation (authoring lint) — normative
Every item, before it enters the bank, MUST pass:
- `DATA-2..6` structural checks above.
- **Leakage lint:** for the item, render each of `pump/hint/prompt` for each distractor tag via `fill()` and assert `leaks(item, text) === false`. Assert `assertion` is present (may leak).
- **Answer-key check:** exactly one `correct`, `correctLetter`/`correctText` consistent.
- **Tag existence:** every `tag` resolves in `lib`.
- **Difficulty present** (1–3) and **skill/color** consistent.
Failing any check blocks publish. This lint is the same predicate the autograder uses (§11) — it is what separates "scaffolding" from "answer leakage".

---

## 4. Inner Loop (Axis A — turn-by-turn tutor)

### 4.1 Per-item state machine
One item is a small machine over these state fields: `selected`, `submittedLetter`, `attempts[]`, `rung` (−1..3), `promptCount`, `coachTurns[]`, `solved`.

| State | Entered when | Coach panel shows | Left action row |
|---|---|---|---|
| **AWAIT_ATTEMPT** | item loaded (`loadItem`) | intro turn only | choices active, **Submit** (disabled until `selected`) |
| **VERIFY→PUMP** | wrong `submitAnswer` → `rung=0` | you-picked + soft-negative verify + **Pump** | (no submit/continue; act in coach panel) |
| **COACHING(rung)** | `escalate` → `rung∈{1,2,3}` | +Hint / +Prompt(input) / +Assertion | coach-panel buttons |
| **SOLVED** | correct submit \| prompt satisfied \| assertion (`rung=3`) | positive verify / assertion | **See the full breakdown →** |

`FR-IL-1` **Attempt-gate:** no coaching move may be produced before `submitAnswer` runs once (guard `GUARD-ATTEMPT`, §7.2). `pick()` is a no-op when `solved`.
`FR-IL-2` `submitAnswer` requires `selected`; it pushes `selected` to `attempts`, sets `submittedLetter`, and:
- **correct →** `coachTurns = [{youPicked}, {coach verify tone:'pos', body:"Yes — that's it. "+item.selfExplain}]`, `solved=true`.
- **wrong →** `coachTurns = [{youPicked}, {coach verify tone:'neg'}, {coach ...composeTurn(item, selected, 0)}]`, `rung=0`.

### 4.2 Decision cascade (executed inside `composeTurn` + `submitAnswer`)
1. **Classify** the response against the item's expectation/misconception set — `classify(item, letter)` returns `{correct}` or `{tag, misc, label}` (the chosen distractor's tag is the signal). `ENG-CLASSIFY`.
2. **Verify** (KR/KCR-lite): brief, non-evaluative acknowledgment (pos on correct, soft-neg on wrong). `ENG-VERIFY`.
3. **Select least-assistance move** by `rung`, escalating only on repeated "still stuck": `moveName(rung) = ['pump','hint','prompt','assertion'][clamp(rung,0,3)]`. `ENG-LADDER`.
4. **Misconception-targeted body** from the tag (`misc[move]` via `fill()`), never a generic rule restatement; deterministic fallbacks only if the tag lacks a rung string. `ENG-COMPOSE`.
5. **Self-explanation** prompt on solve (correct path appends `item.selfExplain`; Feedback shows `selfExplain` field). `ENG-SELFEXPLAIN`.
6. **Gauge understanding** before advancing (Feedback gauge; §5.4). `ENG-GAUGE`.

### 4.3 Escalation ladder & cap
```
rung:  -1  none (AWAIT_ATTEMPT)
        0  PUMP        highest ICAP — student generates            (set by wrong submit)
        1  HINT        points at the relevant feature              (escalate)
        2  PROMPT      fill-in-the-blank keyword; shows text input (escalate; promptCount++)
        3  ASSERTION   states the step/answer — MAY reveal         (escalate → solved)
```
`escalate()`: `rung = min(3, rung+1)`; append `{you:"I'm still stuck."}` + `{coach ...composeTurn(item, submittedLetter, rung)}`; if `move==='prompt'` then `promptCount++`; if `rung>=3` then `solved=true`.
Two resolutions at PROMPT: **(a)** learner answers the blank via `submitPrompt` → positive verify, `solved=true`, **no leak**; **(b)** learner clicks *Show the answer* → `escalate` to ASSERTION (leak).
`FR-IL-3` **Prompt cap.** Reference collapses to one PROMPT rung then ASSERTION; the footnote surfaces `promptCount / cap 3`. **[PROD]** support up to **3** prompt sub-steps (distinct blanks) before ASSERTION fires automatically (the MWPTutor guardrail). Cap is config `PROMPT_CAP=3`.
`FR-IL-4` ASSERTION fires only when the ladder is exhausted (cap reached) **or** the learner explicitly disengages (*Show the answer*). It is the only move allowed to reveal.

### 4.4 Engine algorithms (reference semantics — normative)
```
choiceOf(item,l)      = item.choices.find(c => c.l===l)
classify(item,l):
  ch = choiceOf(item,l)
  if !ch            → {correct:false, unknown:true}
  if ch.correct     → {correct:true, choice:ch}
  else              → {correct:false, choice:ch, tag:ch.tag, misc:lib[ch.tag]||{}, label:misc.label}
fill(s,item,l)        = s.replaceAll('{underline}', item.underline).replaceAll('{choice}', l)
composeTurn(item,l,rung):
  cls  = classify(item,l);  move = moveName(rung);  m = cls.misc||{}
  body = fill(m[move], item, l)  ||  fallback(move, item)     // see §4.4a
  leak = (move==='assertion')
  reason = [ {Classify: "Chose "+l+" → "+(label||'off-target')+[tag]},
             {Verify:   "Negative (soft) — non-evaluative of the person"},
             {Select:   moveTitle(move)+" — "+moveWhy(move)},
             {Leakage:  leak ? "Answer revealed (ladder exhausted)"
                              : (leaks(item,body) ? "⚠ would leak — regenerate" : "✓ no answer token")} ]
  return {move, body, leak, cls, reason}
```
**§4.4a fallbacks** (only when a tag omits a rung): pump→"What made you pick that? Try reading the sentence again without the underlined part."; hint→`item.heuristic`; prompt→"In one word: the rule this tests is about ___."; assertion→`item.whyCorrect + " So the correct choice is " + item.correctLetter + "."`.

### 4.5 Leakage contract (GUARD-LEAK) — normative
```
leaks(item, text):
  t  = lower(text)
  ct = lower(item.correctText) with [.,;] stripped, trimmed
  letterHit = wordBoundary(item.correctLetter) in t  AND  /answer|choice|option|correct/ in t
  textHit   = ct.length > 6  AND  t.includes(ct)
  return letterHit OR textHit
```
`GUARD-LEAK-1` Every **pump/hint/prompt** turn MUST satisfy `leaks(item, body)===false` before it is shown. In the deterministic engine this is guaranteed by content lint (§3.6). **[PROD]** the LLM pipeline runs `leaks()` on generated text and regenerates/falls back on a hit (§8.4).
`GUARD-LEAK-2` The reasoning trace's **Leakage** line MUST reflect the true check result for every turn (audit trail).
`GUARD-LEAK-3` `leaks()` is intentionally conservative for short/symbolic answers (e.g. `":"`, `"is"`): `textHit` requires `ct.length>6`, so short answers rely on `letterHit` + content lint + prompt phrasing that never pairs the letter with "answer/choice/option/correct". **[PROD]** strengthen for short answers by also blocking the exact `correctText` token and near-synonyms (§8.4).

### 4.6 Reasoning-trace contract (ENG-TRACE)
Every coach turn produced by `composeTurn` carries `reason: {k,v}[]` with keys **Classify · Verify · Select · Leakage** (correct/prompt-satisfied turns carry a reduced trace). The trace is rendered when `showReasoning` is on and is the human-reviewable **turn log**. **[PROD]** persist each `reason` record with `{itemId, rung, move, chosen, leakResult, timestamp}` (§10.3, §11).

### 4.7 Inner-loop functional requirements
`FR-IL-5` The ladder indicator reflects `rung`: rungs `≤ rung` filled (accent; ASSERTION filled = success green), current rung label emphasized (`vals.ladder`).
`FR-IL-6` Each coach turn renders move tag (Pump/Hint/Prompt/Assertion) + a leakage badge: non-assertion → "· no answer 🛡"; assertion → "· answer revealed".
`FR-IL-7` `tryAgain` clears `selected` + `submittedLetter` (returns to AWAIT_ATTEMPT) while preserving `coachTurns` and `rung`.
`FR-IL-8` Coach panel auto-scrolls to newest turn (`componentDidUpdate` → `_coachEl.scrollTop = scrollHeight`).

---

## 5. Outer Loop (session sequencing)

### 5.1 Session construction (`buildSession`)
Reference queue (10 items) demonstrates the four sequencing rules:
```
order = [ punc-noness-01, usage-sva-01, punc-colon-01, rhet-transition-01, struct-splice-01,
          usage-pronoun-01, org-modifier-01, struct-fragment-01, concise-redund-01, concise-wordy-01 ]
return { queue: order, pos: 0, results: [], startMastery: {...mastery}, focus: 'punctuation' }
```
`FR-OL-1` **Weakest+due first:** open on the lowest-mastery, due bucket (`focus`). `FR-OL-2` **Interleave:** consecutive items SHOULD differ in `skill` (build discrimination). `FR-OL-3` **Space, don't mass:** repeats of a skill are distributed, not adjacent. `FR-OL-4` **Easy wins late:** difficulty-1 items placed after harder ones to sustain momentum. `FR-OL-5` `startMastery` snapshot taken at start for the Summary delta.

### 5.2 "Why this item next" (`whyNext(item,pos)`)
`FR-OL-6` Every item shows a rationale: pos 0 → "`{skillName}` is your weakest, most-due bucket — opens at difficulty `{difficulty}`."; if previous item's skill differs → "Interleaved after `{prevSkillName}` — identify which rule applies…"; else → "Spaced return to `{skillName}` at difficulty `{difficulty}` — distributed, not massed."

### 5.3 Advancement & result recording (`nextItem`)
```
item     = current()
firstTry = attempts[0] === item.correctLetter
missTag  = firstTry ? null : (choiceOf(item, attempts[0]).tag ?? null)
rec      = {id, skill, skillName, color, firstTry, missTag}
results  = dedupeById(session.results, rec)        // replace existing rec for this id
pos+1 ≥ queue.length  →  view='summary' (persist results)
else                  →  session.pos++, view='quiz', loadItem(queue[pos+1])
```
`FR-OL-7` Advancement is available only from Feedback (**Next question →** / **Finish session →**; label from `fb.nextLabel` = last-item test). `FR-OL-8` completing the last item routes to Summary.

### 5.4 Mastery update & gauge
`FR-OL-9` `gaugeGot` sets `gauge='got'` and `mastery[currentSkill] += 4` (cap 99); UI note: "mastery nudged up and this skill is spaced further out." `FR-OL-10` `gaugeFuzzy` sets `gauge='fuzzy'`; UI note: "the outer loop will re-surface this pattern sooner, with a worked example first." `FR-OL-11` gauge state drives the **[PROD]** scheduler (§5.5): *got* → longer interval + higher mastery evidence; *fuzzy* → shorter interval + worked-example-first re-surface.

### 5.5 [PROD] Production sequencer requirements
`FR-OL-P1` **Mastery model:** replace flat `+4` with a per-skill estimator (BKT or IRT-lite) updated from correctness, `firstTry`, ladder depth reached, gauge, and latency. Persist per learner.
`FR-OL-P2` **Mastery-gate:** an item/skill above difficulty D is eligible only when the prerequisite skill/difficulty is at/above the mastery threshold (desirable difficulties gated on acquisition). Do not interleave/space a skill not yet minimally acquired.
`FR-OL-P3` **Spaced repetition:** schedule re-tests with expanding intervals (e.g. 1d → 3d → 7d), advanced/retreated by gauge + correctness; "due" = interval elapsed. Drives the Dashboard "Due" badges and Skill "Due for review".
`FR-OL-P4` **Interleaving policy:** once basics acquired, mix skill types to train rule discrimination; before acquisition, keep blocked practice.
`FR-OL-P5` **Adaptive difficulty:** step difficulty by recent performance; on a frustration signal (§7.3) step down and insert a worked example.
`FR-OL-P6` **Selection inputs:** `{mastery, dueSchedule, recentErrors(missTag frequency), difficulty, share-of-test weighting}`. Output an ordered queue + a `whyNext` rationale string per item (FR-OL-6 must remain satisfiable from real signals).

---

## 6. Feedback (Hattie & Timperley consolidation)

Reached from the Quiz **See the full breakdown →** (`goFeedback`) once `solved`. All content is **response-specific**, computed from `chosen = submittedLetter ?? attempts[0] ?? correctLetter` and `firstTry`.

### 6.1 Blocks (top→bottom) and bindings
| Block | Content | Source |
|---|---|---|
| Top bar | counter + progress + skill badge | `q.counter`, `q.progressw`, `q.skillName/skillColor` |
| **Result banner** | icon+title+sub; adapts to `firstTry` | `fb.icon/iconInk/iconBg/bannerBg/bannerBd/title/sub` |
| Sentence recap | full sentence, correct span in **success** color | `q.pre` + `q.correctText` + `q.post` |
| **Feed-up · goal** | the standard + why it matters | `fb.hattie[0]` (`head=standardLabel`) |
| **Feed-back · gap** | the specific misconception (or "no gap") | `fb.hattie[1]` (`head=label`, `body=fill(misc.hint‖whyCorrect)`) |
| **Feed-forward · next** | the worked heuristic | `fb.hattie[2]` (`body=heuristic`) |
| Choices reviewed | per-choice correct/chosen/off styling + note | `fb.choices[]` |
| **Self-explanation** | prompt + textarea + gauge | `fb.selfExplainPrompt`, `selfExplain`, `fb.gotCls/fuzzyCls/gaugeNote` |
| Rule + actions | rule line · Ask the coach · Next | `q.rule`, `askCoach`, `nextItem`, `fb.nextLabel` |

`FR-FB-1` Banner: `firstTry` → ✓/success, "Exactly right — first try."; else ↺/accent, "You got there. Here's the pattern to keep." + sub "You first chose `{chosen}` — `{label}`. The correct answer is `{correctLetter}`."
`FR-FB-2` Feed-back card uses the chosen distractor's **misconception hint** (leakage-safe, targeted) as the gap description — not a generic rule restatement; on `firstTry` shows "No gap — clean solve."
`FR-FB-3` Choices-reviewed: correct → success + `whyCorrect`; chosen-wrong → danger + `label`.; other → neutral, no note. (Matches §2.6 of the design spec.)
`FR-FB-4` One chunk per card (CLT). `FR-FB-5` `nextItem` label is "Finish session →" on the last queued item, else "Next question →".
`FR-FB-6` **Ask the coach** routes to Coach (`askCoach → go('coach')`) carrying the item context (§9.2).

---

## 7. Scaffolding, Fading & Affect

### 7.1 Faded worked examples (Skill detail)
Backward fading across three cards; data `skill.faded[]` each `{kind, sub, prob, steps:[{t, done|blank}], answer}`, transformed to `{bd, dots, steps:[{t,mark,ink,style}], blankRow, solo, answer}`.
| Card | Scaffold (`dots`) | Steps | Terminal |
|---|---|---|---|
| **Worked example** | ●●● | all steps `done` (✓) | `answer` chip ("Keep both commas.") |
| **Completion problem** | ●●○ | last step `blank` (?) | `blankRow` "your turn — fill the last step" |
| **Independent** | ○○○ | none | `solo` "You solve it — no steps given." |
`FR-SC-1` Fading order is worked → completion → independent (each removes one more worked step). `FR-SC-2` **[PROD]** which card the learner is served is **adaptive to mastery** (higher mastery → start later in the fade) to avoid the **expertise-reversal effect**; the three-card display is the authoring/reference form.

### 7.2 Guardrails
`GUARD-ATTEMPT` (help-abuse): no hint/coaching before an attempt — enforced in the reference by only producing turns inside `submitAnswer`/`escalate`, and surfaced as the footnote "Guardrail: an attempt is required before any hint." **[PROD]** also flag rapid repeated *Show the answer* as help-abuse and re-assert scaffolding.
`GUARD-SOCRATIC` (anti-looping / learned-helplessness): bound Socratic turns — the ladder is finite and caps at ASSERTION (`PROMPT_CAP`, FR-IL-3/4). **[PROD]** detect persistent unproductive confusion (N nudges without progress) → rescue with a more direct step, do not loop.
`GUARD-FADE` (expertise reversal): fading MUST be adaptive to demonstrated mastery (FR-SC-2), not fixed.

### 7.3 Affect (first-class states)
`FR-AF-1` Encouragement is tied to **process/effort and specific progress**, never empty praise — reference examples: verify "Not quite — but this tells us exactly what to work on."; Summary `selfFix` "Once the coach flagged it, you carried the fix to the later items — that transfer is the goal." (No bare "Great job!").
`FR-AF-2` **Productive confusion** is named at an impasse rather than avoided.
`FR-AF-3` **[PROD]** monitor the confusion → frustration → boredom transition (D'Mello & Graesser) from signals `{consecutive wrong, time-on-item, ladder depth, rapid disengagement}`; intervene **before** disengagement by easing difficulty (FR-OL-P5) + a worked step. `fuzzy` gauge and deep-ladder items are the reference proxies for this signal.

---

## 8. LLM Coach Contract [PROD]

The deterministic engine (§4) is the **fallback and the correctness oracle**. The LLM adds natural, history-aware phrasing for inner-loop turns and chat — **inside** the guardrails. It never decides correctness or sequencing.

### 8.1 Responsibility split (normative)
| MUST stay deterministic (non-LLM) | MAY be LLM-generated |
|---|---|
| Correctness (`choice.correct`), `classify()`, `correctLetter` | Wording of pump / hint / prompt bodies |
| Move selection & escalation (`rung`, ladder, cap) | Wording of the assertion (from grounded facts) |
| `leaks()` leakage gate | Coach-chat replies (grounded) |
| Sequencing, mastery, scheduling | Self-explanation acknowledgment phrasing |
| Reasoning-trace `Classify/Select/Leakage` facts | The `Verify` phrasing |

### 8.2 Inner-loop generation contract
**Input** (server builds; never trusts client for the answer key):
```json
{ "item": { "id","skill","standard","difficulty","pre","underline","post","tail","stem",
            "choices":[{"l","t"}], "correctLetter", "whyCorrect","heuristic","rule" },
  "chosenLetter": "B",
  "misconception": { "tag","label","pump","hint","prompt","assertion" },
  "rung": 0, "move": "pump",
  "history": [ { "role":"coach|student","text":"…" } ],
  "constraints": { "mayRevealAnswer": false, "maxWords": 60, "oneChunk": true } }
```
**Output:**
```json
{ "body": "…natural coaching line…", "usedTemplateSlots": ["underline"] }
```
`FR-LLM-1` The system prompt MUST instruct: stay on `move`; target `misconception.tag`; use the library rung string as the semantic anchor; **never** output the correct letter/value when `mayRevealAnswer=false`; one chunk; non-evaluative of the person; ground only in provided `item` facts (no invented rules).
`FR-LLM-2` `move` and `rung` are chosen by the deterministic ladder and passed in — the model does not escalate itself.

### 8.3 Chat contract
`FR-LLM-3` Coach chat (replaces `coachReply` keyword routing) is grounded in `{currentItem, diagnosed misconception, learner history/mastery}`; the three quick-reply chips map to intents `explain-rule | similar-item | show-pattern`. Replies obey the same no-leak rule while an item is unsolved.

### 8.4 Guardrail enforcement pipeline (server)
```
1. Gate:     require attempt (chosenLetter present)                        [GUARD-ATTEMPT]
2. Ground:   assemble input from verified item content + tag library
3. Route:    strong model for generation                                   [FR-LLM-4 model routing]
4. Generate: body ← LLM(input)
5. Check:    if !constraints.mayRevealAnswer and leaks(item, body):        [GUARD-LEAK]
                regenerate once with stricter instruction;
                if still leaks → FALLBACK to deterministic composeTurn()   [§8.5]
6. Strengthen (short answers): also reject if body contains correctText token
             or a listed near-synonym                                      [GUARD-LEAK-3]
7. Log:      persist {itemId, rung, move, chosen, model, leakResult, body} [§10.3]
```
`FR-LLM-4` **Model routing:** route inner-loop tutoring to a strong model; offload deterministic checks (grammar-rule verification, classification, leakage) to non-LLM logic (the Khanmigo arithmetic-reliability lesson: don't let the model adjudicate what code can verify).
`FR-LLM-5` Every generated turn passes `leaks()` **server-side** before returning; a leak is a hard block, not a warning.

### 8.5 Deterministic fallback
`FR-LLM-6` If the LLM is unavailable, times out, or fails the leakage gate twice, the client/server MUST fall back to `composeTurn()` (§4.4) so the inner loop always functions offline and safely. The learner-visible behavior degrades only in phrasing richness, never in correctness or safety.

---

## 9. Total Traceability (prototype → implementation, 1:1)

This section is normative and exhaustive: **every** state field, navigation edge, interactive control, and rendered value in the reference prototype is mapped so the implementation reproduces it exactly.

### 9.1 Global state model
All UI state is one object (`state`). Type · role · lifecycle · writers · readers. (`current() = itemById(itemId) ?? bank[0]`.)

| Field | Type | Role | Written by | Read by (UI) |
|---|---|---|---|---|
| `dark` | bool | theme light/dark | `toggleTheme` | `themeAttr`, `sunDisp/moonDisp`, `themeLabel` |
| `view` | `dashboard\|quiz\|feedback\|coach\|summary\|skill\|progress` | active screen | `go`, `startSession`, `goFeedback`, `nextItem` | `isDashboard/isQuiz/…`, `navItems.cls`, `flowSteps` |
| `timerOn` | bool | quiz timer visible | `toggleTimer` | quiz top bar clock, `timerIcon` |
| `showReasoning` | bool | reasoning-trace visible | `toggleReasoning` | `coachTurns[].showReason`, `reasoningLabel` |
| `progressRange` | `30d\|all` | analytics range | `setRange` | `rangeTabs`, `trendPoints/Delta/Sub` |
| `draft` | string | coach composer text | `onDraft`, `sendMessage` | coach input value |
| `coachTyping` | bool | typing indicator | `sendMessage` (timeout) | coach typing dots |
| `chat` | `{from,body}[]` | coach conversation | seed, `sendMessage` | coach `chat[]` bubbles |
| `session` | `Session\|null` | outer-loop working set | `buildSession`/`startSession`, `nextItem` | `q.counter/progressw`, `whyNext`, `summary.*` |
| `itemId` | string\|null | current item id | `loadItem` | everything via `current()` |
| `selected` | letter\|null | current selection (pre-submit) | `pick`, `tryAgain`, `loadItem` | choice highlight, `submitDisabled` |
| `submittedLetter` | letter\|null | locked submitted choice | `submitAnswer`, `tryAgain`, `loadItem` | `showSubmit`, choice ✗ mark, feedback `chosen` |
| `attempts` | letter[] | attempts this item | `submitAnswer`, `loadItem` | `firstTry`, `resultLabel`, `nextItem` record |
| `rung` | int −1..3 | ladder position | `submitAnswer`(0), `escalate`, `loadItem`(−1) | `ladder[]`, `ctrl` buttons/footnote |
| `promptCount` | int | prompts used | `escalate`, `loadItem` | `ctrl.footnote` |
| `coachTurns` | turn[] | inner-loop transcript | `loadItem`,`submitAnswer`,`escalate`,`submitPrompt` | coach panel `coachTurns[]` |
| `promptDraft` | string | fill-in-blank input | `onPromptDraft`,`submitPrompt`,`loadItem` | prompt input value |
| `selfExplain` | string | learner's self-explanation | `onSelfExplain`, `loadItem` | feedback textarea |
| `gauge` | `null\|got\|fuzzy` | understanding check | `gaugeGot`,`gaugeFuzzy`,`loadItem` | gauge button state, `fb.gaugeNote` |
| `solved` | bool | item resolved | `submitAnswer`,`escalate`,`submitPrompt`,`loadItem` | choice lock, `showContinue`, gates Feedback |
| `mastery` | `Record<SkillKey,number>` | per-skill % | seed, `gaugeGot` | `buckets[]`, `skill.pct`, `summary.delta` |

**Turn record shapes in `coachTurns`:** `{intro:true}` (opening instruction) · `{youPicked:letter}` (learner echo) · `{who:'coach'|'you', move?, body, tone?, reason?}` (verify/pump/hint/prompt/assertion). **Non-state refs:** `_coachEl`,`_chatEl` (scroll nodes), `_rt` (chat reply timer).

`DATA-STATE-1` `loadItem(id)` resets the entire inner-loop group to: `{selected:null, submittedLetter:null, attempts:[], rung:−1, promptCount:0, coachTurns:[{intro:true}], promptDraft:'', selfExplain:'', gauge:null, solved:false}`. Persisted-across-items: `session`, `mastery`, `chat`, `dark`, `timerOn`, `showReasoning`.

### 9.2 Navigation map (every edge)
`view` transitions and session side-effects. **`startSession`** = `buildSession()` then `view='quiz'` then `loadItem(queue[0])` (fresh session + item). `go(v)` = set `view=v` only.

| Origin (screen) | Control | Handler | → Result |
|---|---|---|---|
| **Header (all)** | Flow pill "Dashboard" | `go('dashboard')` | Dashboard |
| Header (all) | Flow pill "Quiz" | `startSession` | Quiz (new session) |
| Header (all) | Flow pill "Feedback" | `go('feedback')` | Feedback (current item) |
| Header (all) | Flow pill "Coach" | `go('coach')` | Coach |
| Header (all) | Flow pill "Summary" | `go('summary')` | Summary |
| Header (all) | Theme toggle | `toggleTheme` | *(no nav)* |
| **Sidebar (dash/skill/progress)** | Dashboard | `go('dashboard')` | Dashboard |
| Sidebar | Practice | `startSession` | Quiz (new session) |
| Sidebar | Skills | `go('skill')` | Skill |
| Sidebar | Progress | `go('progress')` | Progress |
| Sidebar | Coach | `go('coach')` | Coach |
| **Dashboard** | Focus banner | `startSession` | Quiz (new session) |
| Dashboard | Bucket card ×6 | `go('skill')` | Skill |
| Dashboard | "Drill a skill" | `startSession` | Quiz |
| Dashboard | "Review my misses (12)" | `reviewMisses` (=`startSession`) | Quiz |
| **Quiz** | "✕ End session" | `go('dashboard')` | Dashboard |
| Quiz | Timer toggle | `toggleTimer` | *(no nav)* |
| Quiz | Choice ×4 | `pick(l)` | *(no nav; sets `selected`)* |
| Quiz | "Submit answer" | `submitAnswer` | *(no nav; → coaching/solved)* |
| Quiz | "Hide/Show reasoning" | `toggleReasoning` | *(no nav)* |
| Quiz | "Let me try again" | `tryAgain` | *(no nav; → AWAIT_ATTEMPT)* |
| Quiz | "I'm still stuck →" / "Show the answer" | `escalate` | *(no nav; rung+1)* |
| Quiz | Prompt input ↑ | `submitPrompt` | *(no nav; → solved)* |
| Quiz | "See the full breakdown →" | `goFeedback` | Feedback |
| **Feedback** | "This clicked ✓" | `gaugeGot` | *(no nav; mastery+4)* |
| Feedback | "Still fuzzy" | `gaugeFuzzy` | *(no nav)* |
| Feedback | self-explain textarea | `onSelfExplain` | *(no nav)* |
| Feedback | "✦ Ask the coach" | `askCoach` (=`go('coach')`) | Coach |
| Feedback | "Next question →" / "Finish session →" | `nextItem` | Quiz (next item) **or** Summary (if last) |
| **Coach** | "← Back" | `goDashboard` | Dashboard |
| Coach | "Wrap up session →" | `goSummary` | Summary |
| Coach | chips ×3 | `ask(text)` → `sendMessage` | *(no nav)* |
| Coach | composer ↑ / Enter | `sendDraft` / `onChatKey` | *(no nav)* |
| **Summary** | "Start recommended drill →" | `startSession` | Quiz (new session) |
| Summary | "See full explanation lesson" | `goSkillFocus` (=`go('skill')`) | Skill |
| Summary | "Done for today" | `goDashboard` | Dashboard |
| **Skill** | "Drill this skill" | `startSession` | Quiz |
| **Progress** | Range tab ×2 | `setRange(r)` | *(no nav)* |

`FR-NAV-1` Global flow pills + theme toggle appear on every screen; the sidebar appears on Dashboard/Skill/Progress; Quiz/Feedback/Coach/Summary use their own top bars (focus/back). `FR-NAV-2` `navItems.cls` = `nav-item is-active` when `n.view===view`. `FR-NAV-3` `flowSteps` renders 5 numbered pills; the active one (by `view`) is accent-filled. `FR-NAV-4` "Practice"/"Quiz"/"Drill"/"Review"/"recommended drill" all start a **fresh** session (reset queue+item); "Feedback"/"Coach"/"Summary" pills navigate without resetting.

### 9.3 Interaction inventory
Every interactive control: precondition/guard → handler → state + engine change → UI result → edge cases. Simple toggles grouped at the end.

**Quiz — item column**
| Control | Guard | Handler | State + engine change | UI result | Edge cases |
|---|---|---|---|---|---|
| Choice tile ×4 | `!solved` | `pick(l)` | `selected=l` | tile → accent border + filled letter-tile; **Submit** enabled | no-op when `solved`; after a wrong submit, tapping a tile changes `selected` but Submit is hidden until `tryAgain` |
| Submit answer | `selected` truthy (`submitDisabled=!selected`) | `submitAnswer` | `attempts.push(selected)`, `submittedLetter=selected`, `classify()`; **correct**→`solved=true`, `coachTurns=[youPicked, verify⁺(+selfExplain)]`; **wrong**→`rung=0`, `coachTurns=[youPicked, verify⁻, composeTurn(…,0)=PUMP]` | Submit row hides; coach turns render; ladder lights PUMP; wrong choice gets ✗; on correct, choices lock + **See the full breakdown →** appears | no-op if `!selected`; disabled styling at 0.6 opacity |
| See the full breakdown → | `solved` (`showContinue`) | `goFeedback` | `view='feedback'` | Feedback screen for this item | only visible once `solved` |

**Quiz — coach panel (inner loop)**
| Control | Guard | Handler | State + engine change | UI result | Edge cases |
|---|---|---|---|---|---|
| Hide/Show reasoning | — | `toggleReasoning` | `showReasoning=!` | each coach turn shows/hides its Classify/Verify/Select/Leakage trace | persists across items |
| Let me try again | `submittedLetter` set, `!solved` | `tryAgain` | `selected=null`, `submittedLetter=null` | returns to AWAIT_ATTEMPT (Submit row back); **`coachTurns`, `rung`, `promptCount` preserved** | keeps the transcript so context isn't lost |
| I'm still stuck → | `submittedLetter` set, `!solved`, `rung<2` | `escalate` | `rung=min(3,rung+1)`; append `[you"still stuck", composeTurn(…,rung)]`; `promptCount++` if new move=`prompt` | next rung's turn appears; ladder advances (HINT→PROMPT) | label of this button = "I'm still stuck →" while `rung<2` |
| Show the answer | `submittedLetter` set, `!solved`, `rung≥2` | `escalate` | `rung→3`, ASSERTION turn (`leak=true`), `solved=true` | assertion turn (success-tinted, "· answer revealed"); choices reveal correct ✓; continue button appears | same handler as above; label switches at `rung≥2` |
| Prompt input (text) | `showPromptInput` (current move=`prompt`) | `onPromptDraft`/`onPromptKey` | `promptDraft=value`; Enter → `submitPrompt` | input reflects typing | only rendered at PROMPT rung |
| Prompt send ↑ | `promptDraft` non-empty | `submitPrompt` | append `[you=value, verify⁺ "named the mechanism"]`, `solved=true`, `promptDraft=''` | resolves **without** revealing answer (no leak); continue appears | empty draft → no-op |

**Feedback**
| Control | Guard | Handler | State + engine change | UI result | Edge cases |
|---|---|---|---|---|---|
| This clicked ✓ | — | `gaugeGot` | `gauge='got'`, `mastery[skill]=min(99,+4)` | button → filled; note "mastery nudged up… spaced further out"; Dashboard/Progress bars reflect new mastery | idempotent-ish (repeat adds +4 again — **[PROD]** guard to once per item) |
| Still fuzzy | — | `gaugeFuzzy` | `gauge='fuzzy'` | button → filled; note "re-surface sooner, worked example first" | — |
| Self-explain textarea | — | `onSelfExplain` | `selfExplain=value` | textarea reflects text | **[PROD]** persist + optionally LLM-score (§11) |
| ✦ Ask the coach | — | `askCoach`=`go('coach')` | `view='coach'` | Coach screen (item context in rail) | — |
| Next / Finish → | — | `nextItem` | record `ResultRec` (dedupe), `pos++` or → summary | next item (fresh inner-loop) or Summary | last item → Summary; label from `fb.nextLabel` |

**Coach chat**
| Control | Guard | Handler | State + engine change | UI result | Edge cases |
|---|---|---|---|---|---|
| Composer input | — | `onDraft` | `draft=value` | input reflects text | — |
| Send ↑ / Enter | `draft` non-empty (`onChatKey`: Enter && !shift) | `sendDraft`→`sendMessage` | append user msg; `draft=''`; `coachTyping=true`; after 900ms append `coachReply(text)`; `coachTyping=false` | user bubble → typing dots → coach bubble; auto-scroll | Shift+Enter = newline; empty → no-op; `clearTimeout` guards double-send |
| Chip ×3 | — | `ask('Explain the rule simply'\|'Give me a similar item'\|'Show my comma pattern')` | as `sendMessage` | same as send | `coachReply` routes by keyword: `rule` / `similar\|example\|fresh` / `pattern\|comma\|miss\|wrong` / else Socratic |

**Progress / global toggles**
| Control | Guard | Handler | State + engine change | UI result | Edge cases |
|---|---|---|---|---|---|
| Range tab ×2 | — | `setRange('30d'\|'all')` | `progressRange=r` | active tab + `trendPoints/Delta/Sub` swap | — |
| Timer toggle (quiz) | — | `toggleTimer` | `timerOn=!` | clock shows/hides; icon `⊘`↔`⏱` | dismissible-timer (anxiety reduction) |
| Theme toggle (header) | — | `toggleTheme` | `dark=!` | `data-theme` flips; all tokens + bucket accents re-resolve | persists across screens |

`FR-IX-1` All disabled/locked states derive from `solved`, `submittedLetter`, `selected` — never from ad-hoc flags. `FR-IX-2` The prompt-satisfied path (`submitPrompt`) MUST resolve without leaking (contrast with `escalate`→ASSERTION which reveals). `FR-IX-3` Coach-chat reply latency is simulated at 900 ms in the reference; **[PROD]** replace with real streaming (typing indicator while pending).

### 9.4 UI ↔ data-model binding (every rendered value → its source)
`vals` = `renderVals()` output. Each row: rendered element → `vals` key → ultimate source. `item = current()`.

**Header (all screens)**
| Element | `vals` key | Source |
|---|---|---|
| `data-theme` wrapper | `themeAttr` | `dark` |
| ☀/☾ + label | `sunDisp`,`moonDisp`,`themeLabel` | `dark` |
| Flow pills ×5 (n, label, styles, onClick) | `flowSteps[]` | `view` (active), fixed `flowBase` |

**Dashboard**
| Element | `vals` key | Source |
|---|---|---|
| Sidebar items ×5 (icon,label,active,onClick) | `navItems[]` | `view`, fixed `navBase` |
| Bucket card ×6: name, share | `buckets[].name/share` | `bmeta` |
| Bucket card: `pct`, bar width `pctw`, accent `color`, `due`, onClick | `buckets[].pct/pctw/color/due/onClick` | `mastery[key]`, `bmeta`, `go('skill')` |
| Focus banner CTA | `startSession` | — |
| "Drill a skill" / "Review my misses" | `startSession` / `reviewMisses` | — |
| Greeting, score-goal 26→28, streak 9, 3/3, week strip, coach note | *(static copy)* | §9.5 [PROD] |

**Quiz**
| Element | `vals` key | Source |
|---|---|---|
| Counter / progress bar | `q.counter`,`q.progressw` | `session.pos`, `queue.length` |
| Skill badge + difficulty | `q.skillName`,`q.skillColor`,`q.difficulty` | `item` |
| Why-this-next | `q.whyNext` | `whyNext(item,pos)` |
| Sentence pre/underline/post/tail | `q.pre/underline/post/tail` | `item` |
| Stem | `q.stem` | `item.stem` |
| Choice tiles ×4 (letter,text,border,fill,ink,mark,lock,cursor,opacity,onClick) | `q.choices[]` | `item.choices` × `selected`/`submittedLetter`/`solved` |
| Submit row (show, disabled, label, hint) | `q.showSubmit`,`q.submitDisabled`,`q.submitLabel`,`q.attemptHint` | `submittedLetter`,`selected` |
| Continue row (show, result label/ink) | `q.showContinue`,`q.resultLabel`,`q.resultInk` | `solved`, `attempts[0]` vs `correctLetter` |
| Reasoning toggle label | `reasoningLabel` | `showReasoning` |
| Ladder pips ×4 (fill, ink, label) | `ladder[]` | `rung` |
| Coach turns (avatar,dir,bubble colors,body,moveTag,moveBg/Ink,leakTag/Ink,showReason,reason[]) | `coachTurns[]` | `state.coachTurns` × `showReasoning`; move colors from `moveMap` |
| Prompt input (show, value) | `ctrl.showPromptInput`,`ctrl.promptDraft` | `rung`(=prompt), `promptDraft` |
| Coach buttons (label,cls,onClick) + footnote | `ctrl.buttons`,`ctrl.footnote` | `submittedLetter`,`solved`,`rung`,`promptCount` |
| Timer clock / icon | `timerOn`,`timerIcon` | `timerOn` |

**Feedback**
| Element | `vals` key | Source |
|---|---|---|
| Banner icon/colors/title/sub | `fb.icon/iconInk/iconBg/bannerBg/bannerBd/title/sub` | `firstTry`, `chosen`, `chCls.label`, `item.correctLetter` |
| Recap span | `q.pre`,`q.correctText`,`q.post` | `item` |
| Feed-up card | `fb.hattie[0]` | `item.standardLabel`,`skillName` |
| Feed-back card | `fb.hattie[1]` | `firstTry` ? — : `chCls.label` + `fill(misc.hint‖whyCorrect)` |
| Feed-forward card | `fb.hattie[2]` | `item.heuristic` |
| Choices reviewed ×4 (kind,tag,note,colors,weight) | `fb.choices[]` | `item.choices` × `chosen`; note = `whyCorrect`‖`misc.label` |
| Self-explain prompt / textarea | `fb.selfExplainPrompt` / `selfExplain` | `item.selfExplain` / state |
| Gauge buttons + note | `fb.gotCls`,`fb.fuzzyCls`,`fb.gaugeNote` | `gauge` |
| Rule line | `q.rule` | `item.rule` |
| Next button label | `fb.nextLabel` | `session.pos` vs last |

**Coach**
| Element | `vals` key | Source |
|---|---|---|
| Conversation bubbles | `chat[]` | `state.chat` |
| Typing indicator | `coachTyping` | `state.coachTyping` |
| Chips ×3 | `askRule`,`askSimilar`,`askPattern` | `ask(text)` |
| Composer value/handlers | `draft`,`onDraft`,`sendDraft`,`onChatKey` | `state.draft` |
| Wrap-up / Back | `goSummary` / `goDashboard` | — |
| Rail: current item, diagnosed misconception, modes | *(static copy)* | §9.5 [PROD] |

**Summary**
| Element | `vals` key | Source |
|---|---|---|
| Header focus | `summary.focusName` | `session.focus` |
| Score / delta / minutes | `summary.score/delta/minutes` | `results` firstTry count, `mastery−startMastery`, (minutes static) |
| Sequence chips (label,color,mark,ink) | `summary.sequence[]` | `results[]` |
| Misconception label/body/selfFix | `summary.misconceptionLabel/Body/selfFix` | dominant `missTag` → `lib[tag]` + `fill()` |
| Recommended + sub | `summary.recommended/recommendedSub` | dominant `missTag` |

**Skill**
| Element | `vals` key | Source |
|---|---|---|
| Name / share / accuracy % | `skill.name/share/pct` | `mastery.punctuation` *(reference fixed to punctuation)* |
| Rule + ✓ examples | `skill.rule`,`skill.examples[]` | authored (bank/lib-derived) |
| Faded cards ×3 (kind,dots,steps[mark/ink/style],blankRow,answer,solo,bd) | `skill.faded[]` | authored + transform |
| Why you missed these | `skill.whyMissed` | `lib['drops-commas-brevity'].label + hint` |
| Accuracy bars ×6 | `skill.bars[]` | static heights *(→ [PROD] history)* |
| Due for review | `skill.due` | static *(→ [PROD] scheduler)* |

**Progress**
| Element | `vals` key | Source |
|---|---|---|
| Range tabs ×2 | `rangeTabs[]` | `progressRange` |
| Trend delta/sub + polyline | `trendDelta`,`trendSub`,`trendPoints` | `progressRange` *(→ [PROD] score history)* |
| Mastery bars ×6 | `buckets[]` | `mastery` |
| Header counts (147 items, 9-day) | *(static copy)* | §9.5 [PROD] |

### 9.5 Static copy → data source [PROD] (must be wired)
The reference hardcodes learner-specific copy that production MUST bind to real data. Nothing else may remain hardcoded.
| Static in reference | Bind to |
|---|---|
| Greeting date/time, "Maya" | learner profile + clock |
| Dashboard focus-banner text | sequencer `focus` + mastery + due |
| Score goal 26 / 28 / start 24 | learner target + latest projected score |
| Streak "9", "3/3 this week", week strip | activity telemetry |
| Coach note text | latest diagnosed pattern |
| "Review my misses (12)" count | error log size |
| Quiz clock "14:32" | live session timer |
| Coach rail "Commas · non-essential", "Trades punctuation for brevity" | `current()` + last diagnosed `missTag` (currently hardcoded) |
| Summary "12 min" | session duration |
| Skill screen (fixed to Punctuation) | selected bucket (parameterize `skill` by the bucket that routed here) |
| Skill accuracy bars, "4 comma items", "Due Today" | per-skill history + scheduler |
| Progress "147 items", "9-day streak", trend polylines | analytics store |
`FR-DATA-BIND-1` Every §9.5 item is a required data binding; none may ship hardcoded. `FR-DATA-BIND-2` The Skill screen MUST accept the target bucket as a parameter (the reference always shows Punctuation); bucket cards + "See full explanation lesson" pass the intended `SkillKey`.

---

## 10. Non-Functional Requirements

### 10.1 Accessibility
`NFR-A11Y-1` WCAG-AA contrast for all token pairings (light + dark). `NFR-A11Y-2` Feedback never by color alone — pair with icon + text (✓/✗/↺, uppercase tag labels), as the reference does. `NFR-A11Y-3` Full keyboard operability: choices, ladder buttons, composer (Enter sends, Shift+Enter newline), tabs, nav; visible focus (`.btn:focus-visible`). `NFR-A11Y-4` Touch targets ≥44px on coarse pointers (design-system touch layer). `NFR-A11Y-5` Honor `prefers-reduced-motion` (disable `coachdot`/`turnin`/`screenin`). `NFR-A11Y-6` Dismissible timer (anxiety reduction) is a requirement, not decoration. `NFR-A11Y-7` Coach turns + feedback announced to assistive tech (aria-live on the coach transcript and result banner).

### 10.2 Performance
`NFR-PERF-1` First paint of any screen < 100 ms from state change (inline-styled, no blocking CSS). `NFR-PERF-2` Inner-loop deterministic turn is synchronous (0 network). `NFR-PERF-3` **[PROD]** LLM turn budget: first token < 1.2 s, full turn < 4 s; show typing indicator; **hard fallback to deterministic** on breach (§8.5). `NFR-PERF-4` Coach transcript auto-scroll must not thrash layout (single `scrollTop` write in `componentDidUpdate`).

### 10.3 Telemetry, logging & privacy
`NFR-LOG-1` Persist a per-turn event: `{learnerId, sessionId, itemId, rung, move, chosenLetter, correct, leakResult, latencyMs, model?, timestamp}` — this IS the reasoning trace, made durable (Khanmigo "log every turn" guardrail). `NFR-LOG-2` Persist per-item results (`ResultRec`), gauge, self-explanation text, and mastery updates. `NFR-PRIV-1` Single-learner tool; minimize PII (first name only); self-explanation text is learner content — store encrypted, never send to third parties beyond the coach model under a data-processing agreement. `NFR-PRIV-2` Provide export/delete of learner data. `NFR-PRIV-3` Content sent to the LLM is limited to item facts + necessary history (§8.2); never send the answer key styled as "the answer" in a way that could echo back (the model receives `correctLetter` only to *avoid* it under `mayRevealAnswer:false`).

### 10.4 Theming / offline
`NFR-THEME-1` Light + dark via `data-theme`; all six bucket accents re-resolve. `NFR-OFFLINE-1` The full inner + outer loop MUST work offline on the deterministic engine; only richer phrasing + persistence require the network.

---

## 11. Evaluation & Autograder

### 11.1 The scaffolding-vs-leakage autograder (authoritative, deterministic)
`EVAL-1` For every item × every distractor tag × rung ∈ {pump,hint,prompt}: render via `fill()` and assert `leaks(item,text)===false`. For `assertion`: assert present (reveal allowed). This is the same predicate as content lint (§3.6) and the runtime gate (§8.4) — one definition of "leakage" across authoring, runtime, and grading. `EVAL-2` A distractor with no resolvable tag, or a leaking pump/hint/prompt, **fails the build**. `EVAL-3` Assert answer-key integrity (exactly one `correct`, `correctLetter/correctText` consistent) and ladder monotonicity (`moveName` order).

### 11.2 Misconception-classification accuracy
`EVAL-4` Maintain a golden set of (response → expected tag) pairs. `classify()` is deterministic for MCQ (distractor → tag) so accuracy is 100% by construction for the reference; the metric matters **[PROD]** when free-response or partial input is classified — target ≥ 0.9 agreement with human labels before shipping a non-deterministic classifier; until then, keep classification deterministic.

### 11.3 LLM-as-judge (phrasing quality) — with the caveat
`EVAL-5` Use an LLM judge only to score **phrasing quality** of generated turns (on-move, targeted, non-evaluative, one-chunk) — never to decide correctness or leakage (those stay deterministic, §8.1). `EVAL-6` **Caveat (2023–2026 evidence):** generic LLM judges correlate poorly with human pedagogy labels; therefore (a) calibrate the judge against a human-labeled rubric sample, (b) report judge–human agreement, (c) gate releases on the deterministic checks (EVAL-1/3) + human spot-review, not on the LLM judge alone. `EVAL-7` Track a "leakage escape rate" = generated turns that passed the model but were caught by `leaks()`; target 0 shipped, monitor trend.

### 11.4 Test harness
`EVAL-8` Unit tests: `classify`, `moveName`, `leaks`, `fill`, `composeTurn`, `buildSession`, `whyNext`, `nextItem`, `gaugeGot`. `EVAL-9` Integration (flows): full inner-loop escalations, prompt-satisfied vs assertion paths, feedback adaptivity, session advance→summary, all §9.2 nav edges. `EVAL-10` Content lint runs in CI on every bank change (§3.6). Reference already ships Playwright coverage for v1 surfaces (`tests/`); extend to v2.

---

## 12. Acceptance Criteria (testable)

Inner loop — `AC-1` No coach turn is produced before an attempt (Given a freshly loaded item, no pump/hint/prompt exists until Submit runs). `AC-2` A wrong submit produces exactly: youPicked + soft-negative verify + PUMP (rung 0). `AC-3` Escalation order is pump→hint→prompt→assertion; the ladder indicator matches `rung`. `AC-4` No pump/hint/prompt turn satisfies `leaks(item,body)` (checked for all 10 items × distractors). `AC-5` The assertion appears only after reaching the prompt cap or the learner clicks *Show the answer*, and it is the only turn badged "answer revealed". `AC-6` Answering the prompt (`submitPrompt`) resolves the item without any leaking turn. `AC-7` Each coach turn's reasoning trace shows Classify/Verify/Select/Leakage with the true leak result. `AC-8` `tryAgain` returns to AWAIT_ATTEMPT while preserving `coachTurns` and `rung`.

Feedback — `AC-9` Banner + Feed-back card are response-specific: choosing B vs C yields different gap text (the chosen distractor's misconception). `AC-10` First-try correct shows "No gap — clean solve"; worked-through shows the misconception. `AC-11` `This clicked ✓` raises `mastery[skill]` by 4 (cap 99) and the Dashboard/Progress bars reflect it.

Outer loop — `AC-12` A session queue interleaves skills (no two adjacent same-skill unless spacing requires) and places difficulty-1 items late. `AC-13` Every item shows a `whyNext` rationale consistent with its position (open/interleave/spaced). `AC-14` Completing the last queued item routes to Summary; Summary's sequence + misconception reflect the actual `results`.

Scaffolding/affect — `AC-15` Faded examples render worked(●●●)→completion(●●○)→independent(○○○) with the completion card blanking the last step. `AC-16` No empty praise: positive feedback references a specific process/result.

Navigation — `AC-17` Every edge in §9.2 works; Practice/Drill/Quiz-pill/recommended-drill start a fresh session; Feedback/Coach/Summary pills navigate without resetting. `AC-18` Theme toggle re-resolves all tokens incl. bucket accents on every screen.

LLM [PROD] — `AC-19` A generated turn that fails `leaks()` twice falls back to the deterministic turn; the learner still advances. `AC-20` The model never adjudicates correctness/sequencing (verified by contract tests that correctness comes from `choice.correct`).

---

## 13. Pedagogy → Implementation Traceability

| Source / principle | Requirements / sections |
|---|---|
| VanLehn two-loop (outer select/space, inner turn-by-turn) | §2.1, §4, §5; FR-OL-*, FR-IL-* |
| EMT-style classify against expectation/misconception | §4.2, `classify()`; DATA-4, DATA-7 |
| Verification-first (KR/KCR-lite), elaborated over bare | §4.2 step 2; FR-FB-1/2 |
| ICAP (pump highest → assertion lowest) | §4.3 ladder; ENG-LADDER |
| Assistance dilemma / least-assistance-first + cap | §4.3, FR-IL-3/4; `PROMPT_CAP` |
| Answer-leakage line (no reveal until exhausted/disengage) | §4.5, GUARD-LEAK-*, §8.4; AC-4/5/6 |
| Hattie & Timperley feed-up/back/forward | §6; FR-FB-2; AC-9/10 |
| Self-explanation + gauge understanding | §4.2 steps 5–6; §6; FR-OL-9/10 |
| Contingent scaffolding + backward fading + expertise-reversal | §7.1; FR-SC-1/2; GUARD-FADE |
| Help-abuse / learned-helplessness guards | §7.2; GUARD-ATTEMPT/SOCRATIC; AC-1 |
| Affect: process praise, productive confusion, D'Mello transition | §7.3; FR-AF-1/2/3; AC-16 |
| Retrieval / spacing / interleaving / mastery-gating | §5.1, §5.5; FR-OL-2/3/4, FR-OL-P2/3/4 |
| Worked-example & faded-example effects | §7.1; AC-15 |
| CLT one-chunk-per-turn | §4.2, FR-FB-4; §8.2 constraints |
| LLM guardrails (Khanmigo/MWPTutor): attempt-gate, no-answer-token, grounding, logging, model routing | §8; FR-LLM-1..6; NFR-LOG-1 |
| Autograder scaffolding-vs-leakage + LLM-as-judge caveat | §11; EVAL-1..7 |

---

## 14. Assumptions, Open Questions & Phasing

### 14.1 Assumptions
Single learner ("Maya"); MCQ items (4 choices, one correct); one misconception tag per distractor; desktop-first; the deterministic engine is the correctness/safety oracle even when the LLM is enabled.

### 14.2 Open questions (decide before/within build)
`OQ-1` Mastery model choice (BKT vs IRT-lite) and thresholds for gating (FR-OL-P1/2). `OQ-2` Spaced-repetition interval schedule + how gauge/latency move it (FR-OL-P3). `OQ-3` `PROMPT_CAP` value and whether multiple distinct blanks per item are authored (FR-IL-3). `OQ-4` Which model(s) for tutoring vs chat, and cost/latency budget (FR-LLM-4). `OQ-5` Free-response items? (would move classification off the deterministic path — EVAL-2/4 implications). `OQ-6` Human-review cadence for LLM turns + the judge rubric (EVAL-5/6). `OQ-7` Multi-tag distractors (a distractor exhibiting two misconceptions) — schema allows one today.

### 14.3 Phasing
**P1 (parity):** deterministic engine + full data model + 7 screens + content lint + acceptance suite = the reference, productionized with real persistence of results/mastery. **P2 (adaptivity):** real mastery model + spaced-repetition scheduler + adaptive fading + affect signals (§5.5, §7). **P3 (LLM):** live coach + chat behind guardrails with deterministic fallback + LLM-as-judge phrasing eval (§8, §11.3). **P4:** content scale-up (bank growth via lint), responsive/mobile, multi-learner — out of this spec.

---

*End of v2 Implementation Specification. This document is normative and derived 1:1 from `English Coach - Prototype v2.dc.html`; where they disagree, treat the prototype as the reference for behavior and this spec for production requirements, and reconcile explicitly.*
