# Spec — PreACT English Coach · UI Requirements

> **Scope discipline.** This is a **UI-only** spec. It is the testable *what* of the
> user-facing surface, derived faithfully from the `PreAct/UI-Design/` prototype
> (7 screens × 3 surfaces, design system, component inventory, interaction + nav maps).
> It deliberately does **not** spec the quiz engine, FSRS scheduler, data persistence,
> content-generation pipeline, or backend — those belong to a separate
> `preact-english-coach-engine.spec.md` (see `PreAct/QUIZ-APP-RESEARCH.md`). Where the
> UI consumes those (coach replies, question content, mastery numbers) this spec
> defines the **UI contract** only and names the upstream as a dependency.
>
> Acceptance criteria use **EARS** so each one is directly testable:
> - **Ubiquitous:** `THE SYSTEM SHALL <behavior>.`
> - **Event-driven:** `WHEN <trigger> THE SYSTEM SHALL <behavior>.`
> - **State-driven:** `WHILE <state> THE SYSTEM SHALL <behavior>.`
> - **Unwanted:** `IF <condition> THEN THE SYSTEM SHALL <behavior>.`
> - **Optional:** `WHERE <feature is present> THE SYSTEM SHALL <behavior>.`

**Status:** Accepted — 2026-06-30 (was Draft 2026-06-29)
**Owner:** Rajnish Khatri

> **Reconciled at acceptance (2026-06-30).** The FRs below are ratified as written; three
> *decision-framing* points are superseded by later-ratified artifacts and MUST be read
> through them:
> 1. **"Turbo monorepo" + "Capacitor shells" as new ADR triggers** (§1, §5, §9) are
>    **superseded.** No `turbo.json` / `pnpm-workspace.yaml` exists — `frontend/` is a single
>    standalone `agent-frontend` package, below the monorepo adoption bar. The native shells
>    are **already Accepted under [ADR-0001](../adr/0001-native-shell-tauri-capacitor.md)**
>    (Tauri 2 macOS + Capacitor 7 iOS over the live-`server.url` model). See the implementation
>    plan's **D2** trade-off analysis. Turbo is *deferred*, not a trigger (decision trigger:
>    a second shared-package consumer).
> 2. **7-screen scope** (§1 Goal, §9 DoD): Screens **6 (Skill detail / FR-H)** and
>    **7 (Progress / FR-I)** — the *subjective plane* — are **deferred** to a follow-up gated
>    on an **ADR-0006 read-port amendment** (no public engine port surfaces `getTutorial` /
>    `listProgressPoints`). See plan **D1**. Dashboard/Summary links to them ship
>    disabled ("coming soon"), never dead (FR-B5).
> 3. **The one genuinely new trigger** is the **client↔BFF coach streaming contract +
>    `subject-coach-english` persona**, tracked as **[ADR-0007](../adr/0007-subject-coach-agent-tool-capability-gating.md)** — to be ratified before the coach flag flips on.
>
> **Related:**
- Source prototype + design system: `PreAct/UI-Design/` (`design-spec.md` = source of truth, README index, 3 `.dc.html` prototypes, Playwright e2e)
- Engine/content sibling spec (separate): `PreAct/QUIZ-APP-RESEARCH.md`
- Process: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` (this is the Stage-2 `spec.md` artifact)
- Template: `docs/plan/_spec_template.md`

---

## 1. Goal

Deliver the user-facing surface of a **personal, adaptive PreACT/ACT English coaching
app** for a single learner ("Maya"), so she can drill grammar items in focus mode, get
Socratic + always-explained feedback, converse with a live AI coach, and watch her
mastery and projected score move from **24 (63%) → 28 (~80%)**. The UI must reproduce
the prototype's calm, low-pressure, Socratic experience across **desktop, iPhone, and
iPad** as one responsive web app shipped via a **Turbo monorepo** (macOS) and
**Capacitor shells** (iOS: iPhone + iPad).

## 2. Context

The brainstorm (SDD Stage 1) is settled: `PreAct/UI-Design/` is a hi-fi, end-to-end
wired prototype and `QUIZ-APP-RESEARCH.md` is the engineering direction. This spec is the
first Stage-2 artifact — the **UI requirements** — extracted from those.

Forces / decisions pinned at clarify time (2026-06-29):
- **Surfaces:** all three, responsive (Turbo macOS + Capacitor iOS for iPhone & iPad).
- **Coach:** a **live streaming AI coach** (not the prototype's scripted keyword-routed
  replies, not the offline-only generation from the research). The typing indicator
  reflects a real pending stream; the coach is history-aware. This aligns the UI with the
  AgentsFramework streaming-agent backend (CopilotKit/AG-UI shape) and **supersedes** the
  prototype's scripted-reply behavior, which was a prototype affordance only.
- **Design system:** tokens are **normative** — the warm cream/charcoal/terracotta base,
  the 6 derived bucket accents, the type scale, radii, the signature underlined-span, and
  the feedback-state palette are requirements, not suggestions (§3.A, §3 per-screen).
- Single learner; **auth is out of scope** (deferred, as in the prototype). No
  multi-user/teacher views.

> **Constitution note (runbook §2):** this UI lives in the **Frontend Ring**
> (`frontend/` + `middleware/`), governed by `STYLE_GUIDE_FRONTEND.md`. It must not
> reach across into the trust kernel / services / orchestration except through the
> middleware BFF. The streaming coach is consumed over the BFF, not by the UI calling an
> LLM directly (§5).

---

## 3. Functional requirements (EARS)

Grouped: **A** design-system (normative tokens), **B** global shell & navigation,
**C–I** the seven screens, **J** responsive/surface variants, **K** theme &
accessibility. Failure-path (`IF…THEN`) requirements are written alongside their happy
path. Each FR maps to ≥1 test in §8.

### A. Design system — normative tokens

- **FR-A1.** THE SYSTEM SHALL render the light base palette with `--color-bg #f9f7f5`,
  `--color-fg #1f1e1d`, `--color-muted #7d7a75`, `--color-accent #d87758`,
  `--color-danger #c0392b`, `--color-success #2f8f5b`, `--color-warning #a9741f`, and
  surface/sunken/selected/border derived from fg as specified in `design-spec.md` §2.1.
- **FR-A2.** WHILE the theme is dark THE SYSTEM SHALL resolve `--color-bg #241c15`,
  `--color-fg #f9f7f5`, `--color-accent #e5967c`, `--color-danger #e57368`,
  `--color-success #5cba86`, `--color-warning #e3b357`, `--color-surface #322a24`,
  `--color-surface-sunken #3f3831`.
- **FR-A3.** THE SYSTEM SHALL define the six bucket accents (light / dark): Rhetoric
  `#d87758`/`#e5967c`, Usage `#c0863a`/`#d6a45a`, Punctuation `#4f9d8b`/`#6bbfa9`,
  Organization `#7a9450`/`#9bb56e`, Sentence Structure `#5b7fa6`/`#84a6cc`, Conciseness
  `#a06a93`/`#c08fb4`, each exposed to a bucket-scoped element via one local `--c`
  custom property that its dot, value, progress fill, and 30–32% border tint reference.
- **FR-A4.** THE SYSTEM SHALL apply the type scale `sm 1rem` / `base 1.125rem (lh 1.6)`
  / `lg 1.25rem` / `xl 1.5rem` / `2xl 1.75rem` with `-0.02em` heading tracking, and
  render quiz sentences at `1.2–1.35rem / lh 1.8`.
- **FR-A5.** THE SYSTEM SHALL use radii `sm 10px / md 16px / lg 22px`, `999px` for
  pills and bars, and 13–16px for choice/option cards.
- **FR-A6.** THE SYSTEM SHALL render the **underlined span** (the ACT "underlined
  portion") with accent background @16%, a 2.5px solid accent bottom-border, 5px top
  radius, `font-weight:600`, and `box-decoration-break:clone` so it wraps cleanly.
- **FR-A7.** WHEN the same span is shown in the post-answer recap THE SYSTEM SHALL
  re-color it with the **success** treatment to mark the correct text.
- **FR-A8.** THE SYSTEM SHALL never convey a feedback state by color alone: every
  correct / review / wrong state SHALL pair color with an icon and a text label
  (e.g. `✓` + "CORRECT ANSWER", `↺`/`!` + "REVIEW", "YOUR CHOICE").

### B. Global shell & navigation

- **FR-B1.** THE SYSTEM SHALL provide global navigation reaching all seven screens via
  the surface-appropriate model: a persistent **sidebar** on desktop and iPad (sidebar
  items: Home / Practice / Coach / Progress — prototype `ipad` test), and a **bottom tab
  bar** on iPhone. *Refinement from the prototype `iphone` test:* the iPhone bottom tab
  bar carries **three** persistent tabs (**Home / Practice / Progress**); **Coach is
  contextual on iPhone** — reached from the flow (Feedback→Coach), not a 4th persistent
  bottom tab. (Desktop/iPad expose Coach as a peer; iPhone does not. See §8.1 open item.)
- **FR-B2.** WHILE the active surface is iPhone AND the active screen is a focus screen
  (Quiz, Feedback, Coach, Summary) THE SYSTEM SHALL hide the bottom tab bar and provide
  a back affordance — concretely a **"✕" close** — that returns to the prior screen
  (prototype `iphone` test: ✕ from Quiz returns to Dashboard).
- **FR-B3.** WHERE the desktop single-screen prototype shell is present THE SYSTEM SHALL
  show numbered flow-step pills (1 Dashboard · 2 Quiz · 3 Feedback · 4 Coach ·
  5 Summary) that highlight the active step and act as jump-nav to any of the five.
- **FR-B4.** THE SYSTEM SHALL implement the core flow
  `Dashboard → Quiz → Feedback → Coach → Summary` with the recommended drill from
  Summary looping back to Quiz, and SHALL honor every route in the navigation map
  (`design-spec.md` §8) — including Dashboard→Skill detail (bucket card),
  Feedback→Coach ("Ask the coach"), Coach→Summary ("Wrap up"), Summary→Skill detail
  ("See full explanation"), Skill→Quiz ("Drill this skill").
- **FR-B5.** IF a navigation control has no destination wired THEN THE SYSTEM SHALL NOT
  ship it (no dead controls — every control routes; cf. prototype "fully wired").

### C. Dashboard / Home (Screen 1)

- **FR-C1.** THE SYSTEM SHALL show a greeting with day-part + learner name and the
  score-goal line (current → goal, e.g. "26 → 28").
- **FR-C2.** THE SYSTEM SHALL render a **Today's-focus banner** for the weakest+due
  skill (the canonical sample: Punctuation) with a primary CTA "Start adaptive session"
  that routes to Quiz.
- **FR-C3.** THE SYSTEM SHALL render the **skill-mastery grid** of all six bucket cards;
  each card SHALL show the bucket name, mastery %, share-of-test %, a bucket-colored
  progress bar, and a "Due" badge when due.
- **FR-C4.** WHEN a bucket card is activated THE SYSTEM SHALL route to that bucket's
  Skill detail screen.
- **FR-C5.** THE SYSTEM SHALL show secondary actions "Drill a skill" and "Review my
  misses (N)", and a right-rail (desktop) / row (iPad) carrying score-goal progress, a
  streak count, a weekly-sessions strip (7 dots), and a "Coach note".

### D. Quiz / Drill (Screen 2 — most important)

- **FR-D1.** THE SYSTEM SHALL render a slim top bar with End-session, "Question N / M"
  + a session progress bar, the bucket badge, and a timer with a dismiss control.
- **FR-D2.** THE SYSTEM SHALL render the item column (≤760px on desktop): the context
  sentence carrying the underlined span (FR-A6), the stem, and four choice rows where
  choice A is "NO CHANGE".
- **FR-D3.** WHEN a choice row is activated THE SYSTEM SHALL mark it selected (accent
  border + filled letter-tile), clear any prior selection, and enable Submit.
- **FR-D4.** WHILE no choice is selected THE SYSTEM SHALL keep "Submit answer" disabled
  (0.6 opacity, non-actionable).
- **FR-D5.** WHEN "Get a hint" is activated THE SYSTEM SHALL toggle a dashed-accent hint
  card containing a Socratic guiding question, flip its label to "Hide hint", and SHALL
  NOT reveal the correct answer.
- **FR-D6.** THE SYSTEM SHALL render "Reveal answer" as a visually distinct,
  low-emphasis (ghost) control separate from "Get a hint".
- **FR-D7.** WHEN "Submit answer" is activated (a choice being selected) THE SYSTEM
  SHALL route to Feedback with the selected letter carried as context.
- **FR-D8.** WHEN the timer dismiss control is activated THE SYSTEM SHALL hide the clock
  and flip the icon to a restore affordance (⊘ ↔ ⏱).

### E. Post-answer Feedback (Screen 3 — core teaching moment)

- **FR-E1.** THE SYSTEM SHALL render the result banner, a sentence recap with the
  correct span in success coloring (FR-A7), the reviewed-choices list, "Why A is
  correct", "Why [your pick] tempted you", the rule under test, and the action row.
- **FR-E2.** WHEN the learner submitted the correct answer (A) THE SYSTEM SHALL show the
  success banner ("Exactly right.") and frame B as the trap most students fall for.
- **FR-E3.** IF the learner submitted a wrong answer (B/C/D) THEN THE SYSTEM SHALL show
  the soft banner ("Not quite — and that's useful.") and render *that distractor's*
  specific rationale.
- **FR-E4.** THE SYSTEM SHALL style each reviewed choice by state: correct (success
  border @45%, bg @9–10%, solid success letter-tile, "CORRECT ANSWER"); chosen-wrong
  (danger border @45%, bg @9%, solid danger letter-tile, "YOUR CHOICE"); other
  (neutral border, surface bg, muted letter-tile).
- **FR-E5.** THE SYSTEM SHALL provide "Ask the coach" (→ Coach, item in context) and
  "Next question →" (→ Summary in the prototype flow).

### F. AI Coach chat (Screen 4 — live streaming)

- **FR-F1.** THE SYSTEM SHALL render a coach header (avatar + "Your Coach" + Wrap-up), a
  context rail (current item + a history-awareness line, e.g. "3 of last 5 comma items
  missed" + the three coach modes), the conversation, and a composer (quick-reply chips
  + input + send).
- **FR-F2.** WHEN the learner sends a message (send button, Enter, or a quick-reply
  chip) THE SYSTEM SHALL append a learner bubble (accent, right), show the typing
  indicator, and auto-scroll to the newest message.
- **FR-F3.** WHILE a coach reply is streaming THE SYSTEM SHALL display the 3-dot typing
  indicator and progressively render the streamed tokens into a coach bubble (surface,
  left) — the indicator reflects a **real pending/streaming response**, not a fixed
  delay.
- **FR-F4.** IF the coach stream fails or times out THEN THE SYSTEM SHALL replace the
  typing indicator with a recoverable error state (retry affordance) and SHALL NOT leave
  a permanently-spinning indicator.
- **FR-F5.** THE SYSTEM SHALL distinguish coach bubbles (surface, left, ~74–80% max
  width) from learner bubbles (accent, right) with a rounded tail.
- **FR-F6.** THE SYSTEM SHALL keep the coach thread history-aware within the session so
  the rail and replies reference the learner's actual recent items.

### G. Session Summary (Screen 5)

- **FR-G1.** THE SYSTEM SHALL render a misconception-framed title, three stat tiles
  (score e.g. 7/10, mastery delta e.g. +8%, time e.g. 12 min), a coach misconception
  write-up (accent card), a recommended-next card, and the action row.
- **FR-G2.** THE SYSTEM SHALL provide "Start recommended drill" (→ Quiz), "See full
  explanation lesson" (→ Skill detail), and "Done for today" (→ Dashboard).
- **FR-G3.** THE SYSTEM SHALL frame the summary around the misconception found, not the
  raw score alone (the write-up names the pattern, e.g. conciseness overriding
  punctuation).

### H. Skill detail / Tutorial (Screen 6)

- **FR-H1.** THE SYSTEM SHALL render a header tinted with the bucket color (dot + name +
  share-of-test + "Drill this skill"), and a two-column body: left = "The rule, in one
  line" with ✓ examples + an auto-built "Why you missed these"; right = an accuracy bar
  chart (last 6 sessions) + a "Due for review" list.
- **FR-H2.** WHEN "Drill this skill" is activated THE SYSTEM SHALL route to Quiz scoped
  to that skill.

### I. Progress / Analytics (Screen 7)

- **FR-I1.** THE SYSTEM SHALL render a header ("Your progress", items-reviewed + streak),
  range tabs (30 days / All time), a projected-score trend line (with a goal guide line),
  and mastery-by-bucket bars each with % and a Due flag.
- **FR-I2.** WHEN a range tab is activated THE SYSTEM SHALL switch the active tab, the
  trend caption, and the trend-line data (prototype `ipad` test: "Goal 28 · on track" for
  30 days → "Goal 28 · since September" for All time).

### J. Responsive / surface variants

- **FR-J1.** WHILE the surface is desktop THE SYSTEM SHALL constrain content to ≤1180px,
  render the dashboard mastery grid in 3 columns, give Coach a context rail, and center
  Quiz at ≤760px.
- **FR-J2.** WHILE the surface is iPhone (≤393pt) THE SYSTEM SHALL render a single
  column, a 2-column mastery grid, a bottom tab bar, full-width chat + composer, and SHALL
  pin Quiz actions (Get-a-hint + Submit) in a sticky footer with the hint inline.
- **FR-J3.** WHILE the surface is iPad (11" landscape) THE SYSTEM SHALL render a
  persistent sidebar, a 3-column mastery grid, and SHALL render **Quiz as a split**: the
  item + choices + Submit ("Submit answer") on the left and a persistent **live coach
  panel** on the right (labeled e.g. "Socratic mode · watching this item") that feeds the
  **same** coach thread (FR-F). Concretely (prototype `ipad` test): a message typed into
  the panel ("Ask about this item…") SHALL appear in the full Coach screen's thread — the
  panel and the Coach screen are one thread, not two.
- **FR-J3a.** WHERE the iPad split coach panel is present THE SYSTEM SHALL offer a
  **deeper-hint** affordance ("One more nudge") that reveals a more specific hint *in the
  panel*, distinct from the item's own "Get a hint" (FR-D5) — a two-tier hint on iPad.
  Neither tier reveals the answer (FR-D5).
- **FR-J4.** THE SYSTEM SHALL keep each device surface's view/selection/coach-thread
  state independent where multiple surfaces are shown together.

### K. Theme & accessibility

- **FR-K1.** WHEN the theme toggle is activated THE SYSTEM SHALL flip `data-theme`
  between light and dark and re-resolve every token, including the six bucket accents.
- **FR-K2.** THE SYSTEM SHALL meet WCAG-AA contrast, be fully keyboard-navigable, and
  SHALL never use color as the sole signal (reinforces FR-A8).
- **FR-K3.** WHILE the pointer is coarse (touch) THE SYSTEM SHALL render interactive
  targets ≥44px and SHALL keep body type ≥1rem.

---

## 4. Data model / contracts

This UI spec defines only the **view-model contracts** the UI consumes; the persistent
schema (Skill / Question / QuizSession / Attempt / SkillState / Tutorial) is owned by the
engine spec. UI-facing shapes:

- **BucketCardVM** `{ bucket, name, masteryPct, shareOfTestPct, due:boolean, accentVar }`
- **QuizItemVM** `{ questionId, contextHtml (with underlined-span markup), stem,
  choices:[{ letter, label, isNoChange }], bucket, index, total }`
- **FeedbackVM** `{ selectedLetter, correctLetter, perChoice:[{ letter, state:
  'correct'|'chosen-wrong'|'other', rationaleMd }], whyCorrectMd, whyTemptedMd, ruleMd }`
- **CoachMessage** `{ role:'coach'|'learner', contentMd, streaming:boolean }` plus a
  **coach stream contract**: an SSE/streaming token channel over the **middleware BFF**
  (AG-UI shape) — the UI subscribes, renders tokens progressively (FR-F3), and surfaces
  an error terminal state (FR-F4). The reply *source* (live agent) is an engine/backend
  dependency, not defined here.
- **ProgressVM** `{ range:'30d'|'all', trendPoints[], goal, items, streak, buckets[] }`
- **Theme** `'light'|'dark'` persisted per learner/device.

No trust-kernel types are touched.

## 5. Invariants & security boundaries

- **Architecture invariants:** this is **Frontend Ring** work (`frontend/` +
  `middleware/`), governed by `STYLE_GUIDE_FRONTEND.md`. It does not touch the Python
  four-layer invariants (#1–#8) directly. The one hard boundary: **the UI consumes the
  coach stream through the middleware BFF, never by calling an LLM/provider directly** —
  no API keys in the client; the client subscribes to a BFF endpoint.
- **Security:** auth deferred (single learner) — but the spec SHALL NOT bake in any
  assumption that blocks adding auth later (the BFF boundary is the seam). No secrets in
  the client bundle. Live coach calls run server-side (BFF), never on the CI hot path.
- **ADR triggers:** introducing the Turbo monorepo, the Capacitor shells, and a new
  client↔BFF streaming contract are **new-abstraction / new-integration** decisions
  (`AGENTS.md` ⚠️ Ask first → G1). These are *plan-stage* ADRs (Stage 2/4), flagged here
  so the plan raises them rather than this UI spec deciding them.

## 6. Edge cases

- **No selection at Submit** — Submit stays disabled (FR-D4); never submits an empty pick.
- **Hint requested but never answered** — hint toggling must not advance state or leak
  the answer (FR-D5).
- **Coach stream interrupted / network drop** — terminal error + retry, no infinite
  spinner (FR-F4).
- **Empty data states** — zero misses ("Review my misses (0)"), a brand-new skill with no
  history (Skill detail "Why you missed these" empty), no trend data yet (Progress) —
  each SHALL render an explicit empty state, not a fabricated value.
- **Theme toggled mid-stream** — token re-resolve must not drop the in-flight coach
  stream (FR-K1 + FR-F3 coexist).
- **iPad split + iPhone stacked simultaneously** — independent per-surface state (FR-J4);
  but **within** the iPad surface the split panel and the Coach screen are ONE thread
  (FR-J3), not independent — don't conflate cross-surface isolation with intra-surface
  sharing.
- **Coach on iPhone has no bottom tab** — reaching Coach mid-flow then backing out must
  land on the prior screen, not a non-existent Coach tab (FR-B1/B2 refinement).
- **Timer dismissed then session resumed** — dismissed state persists for the session;
  restore affordance remains reachable (FR-D8).

## 7. Non-functional requirements

- **Streaming latency:** typing indicator appears within ~100ms of send; first coach
  token renders as soon as the BFF stream yields (no artificial fixed delay — this is the
  explicit departure from the prototype's ~0.95s canned timeout).
- **Theme switch:** re-theme is instantaneous (CSS-variable swap, no reflow jank).
- **Offline posture:** the quiz/drill/feedback/progress surfaces SHALL function on cached
  content (Capacitor local-first); only the **live coach** requires connectivity, and its
  unavailable state is a defined error (FR-F4), not a crash.
- **Determinism for tests:** all non-coach UI behavior is deterministic (L1); the coach
  stream is mocked in UI tests (no live LLM in CI).
- **Reversibility:** no destructive user action in the UI; navigation is non-lossy.

## 8. Test plan

UI tests run via Playwright (the prototype already ships an e2e suite under
`PreAct/UI-Design/tests/`), mirrored per surface. Coach streaming is **mocked** in CI
(no live LLM). Failure-path tests precede happy-path.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-A1/A2/K1 | `theme.spec::tokens_resolve_light_and_dark` | L1 | yes (web CI) |
| FR-A3 | `tokens.spec::six_bucket_accents_present_both_themes` | L1 | yes |
| FR-A6/A7 | `quiz.spec::underlined_span_accent_then_success_in_recap` | L1 | yes |
| FR-A8/K2 | `a11y.spec::feedback_state_never_color_only` | L1 | yes |
| FR-B1/B2 | `nav.spec::iphone_tabs_hidden_in_focus_modes` | L1 | yes |
| FR-B4/B5 | `nav.spec::every_route_reachable_no_dead_controls` | L1 | yes |
| FR-D3/D4 | `quiz.spec::submit_disabled_until_choice_then_enabled` | L1 | yes |
| FR-D5 | `quiz.spec::hint_toggles_socratic_and_never_reveals_answer` | L1 | yes |
| FR-D7/E2 | `feedback.spec::correct_pick_A_celebrates` | L1 | yes |
| FR-E3/E4 | `feedback.spec::wrong_pick_B_gives_distractor_specific_soft_feedback` | L1 | yes |
| FR-F2/F3 | `coach.spec::send_streams_tokens_with_typing_then_bubble` (mocked stream) | L2 | yes |
| FR-F4 | `coach.spec::stream_failure_shows_retry_not_infinite_spinner` | L1 | yes |
| FR-I2 | `progress.spec::range_tab_switches_caption_and_trend` | L1 | yes |
| FR-B2 | `iphone.spec::focus_mode_close_x_returns_to_dashboard` | L1 | yes |
| FR-J2 | `iphone.spec::sticky_quiz_footer_and_2col_mastery` | L1 | yes |
| FR-J3 | `ipad.spec::quiz_split_with_persistent_live_coach_panel` | L1 | yes |
| FR-J3a | `ipad.spec::panel_message_lands_in_shared_coach_thread; one_more_nudge_deeper_hint` | L1 | yes |
| FR-K3 | `a11y.spec::touch_targets_min_44px_on_coarse_pointer` | L1 | yes |

> The architecture tests in `tests/architecture/` are Python-layer and do not gate this
> Frontend-Ring spec; the equivalent constitution here is `STYLE_GUIDE_FRONTEND.md` +
> the per-surface Playwright suite.

### 8.1 Traceability to the existing prototype tests

The design agent already shipped a per-surface Playwright suite at
[`preact/ui-design/tests/e2e/`](../../preact/ui-design/tests/e2e/) —
[`english-coach.spec.js`](../../preact/ui-design/tests/e2e/english-coach.spec.js) (desktop),
[`english-coach.iphone.spec.js`](../../preact/ui-design/tests/e2e/english-coach.iphone.spec.js),
[`english-coach.ipad.spec.js`](../../preact/ui-design/tests/e2e/english-coach.ipad.spec.js).
These run against the standalone prototype export and are the **behavioral oracle** for
this spec: when the real app is built, the §8 tests inherit these assertions (re-pointed
at the built UI via `APP_URL`/`DEVICE_URL`). The mapping below is the source of truth for
which FR each existing test already exercises; the concrete strings the tests assert are
noted so the real-UI tests reproduce the same observable contract.

| FR | Prototype test (file · title) | Concrete contract the test pins |
|---|---|---|
| FR-B1/B2 | iphone · `boots…bottom tab bar` / `tabs reach Practice, Progress, Home` | Tabs **Home / Practice / Progress**; focus mode exits via **"✕"** back to Dashboard |
| FR-B1 | ipad · `boots…persistent sidebar` | Sidebar **Home / Practice / Coach / Progress** |
| FR-B3 | desktop · `header flow-step pills jump between screens` | Numbered pills jump-nav |
| FR-B4 | desktop · `walks the full loop end to end` | Dashboard→Quiz→Feedback→Coach→Summary→recommended-drill→Quiz |
| FR-C4/H1 | all · `bucket card opens Skill detail` | Rhetoric card → "The rule, in one line" / "Why you missed these" |
| FR-D3/D4/D7 | desktop · `submit is gated until a choice is selected` | Submit disabled → select "NO CHANGE" → enabled |
| FR-D5 | desktop+iphone · `hint toggles open and closed (and is not the answer)` | Hint copy "(Coach )hint — not the answer"; toggles "Get a hint"↔"Hide hint" |
| FR-D8/D1 | iphone+ipad · timer in the Quiz test | Timer shows **"14:32"**, `[title="Show / hide timer"]` dismisses it |
| FR-E2 | desktop+ipad · `correct pick (A — NO CHANGE) celebrates` | "Exactly right." + "Why A is correct" |
| FR-E3/E4 | all · `wrong pick (B) gives gentle, distractor-specific feedback` | "Not quite — and that's useful." + "Why B tempted you" + "Why A is correct" |
| FR-E5/G1 | desktop · `Feedback -> Next question goes to Summary` | Next → "Nice work — you found the pattern." |
| FR-F2/F6 | all · `typed message gets a coached reply` / `chip routes…` | Send/Enter/chip → history-aware coached reply; "Sees your history" rail |
| FR-G1/G2 | all · full-loop + `Start recommended drill` | Summary stats + recommended-drill card re-opens Quiz |
| FR-H2 | all · `Drill this skill launches the Quiz` | "Drill this skill" → "Which choice is correct?" |
| FR-I2 | desktop+ipad · `range tabs switch the projected-score trend` | "Goal 28 · on track" → "Goal 28 · since September" |
| FR-J2 | iphone · `submit gating, hint, and dismissible timer` | iPhone Quiz: "Submit" (not "Submit answer"), inline hint, sticky actions |
| FR-J3/J4 | ipad · `split Quiz with live coach panel` / `in-drill coach panel posts into the Coach thread` | Persistent "Socratic mode · watching this item" panel; **panel message appears in the shared Coach thread**; deeper-hint "One more nudge" |
| FR-K1 | iphone · `header toggle themes the whole page` | `[data-theme]` flips light↔dark |

> **Surface-string drift the prototype exposes (resolve at build, do not silently
> normalize):**
> - **Desktop** primary CTA is **"Start adaptive session"** (FR-C2); **iPhone/iPad** use
>   **"Start session"**, and the Quiz submit button is **"Submit"** (iPhone) vs **"Submit
>   answer"** (desktop/iPad). The build must pick canonical copy per surface or unify —
>   §8 tests should assert the chosen string, not assume one.
> - **iPhone bottom tab bar** shows **3** tabs on Dashboard (Home / Practice / Progress) —
>   Coach is reached from within the flow (Feedback→Coach), **not** as a 4th persistent
>   tab. This **refines FR-B1** (which lists "Home / Practice / Coach / Progress"): on
>   iPhone, Coach is contextual, not a bottom-tab peer. See the open item below.

### 8.2 Coverage the prototype tests do NOT reach (UI gaps to author fresh)

The prototype is scripted, so these spec'd behaviors have **no existing oracle** and are
fresh test targets when the real UI is built:
- **Live streaming coach** (FR-F3/F4) — the prototype uses canned ~0.95s replies, not a
  real stream; the typing-indicator-reflects-real-pending and the stream-failure-retry
  states must be tested against a **mocked SSE stream**, not the prototype.
- **Design-system token values** (FR-A1/A2/A3/A6) — the prototype renders them but the
  tests don't assert exact hex/var values; the real `theme.spec`/`tokens.spec` verify them.
- **a11y** (FR-A8/K2/K3) — no axe assertions in the prototype suite; `@axe-core/playwright`
  is added fresh.
- **Empty/edge states** (§6: zero misses, brand-new skill, no trend data) — the prototype
  ships only the populated happy-path fixture.

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first*.
- [ ] Web/e2e suite green across all three surfaces (desktop, iPhone, iPad).
- [ ] `make check` green for any Python/middleware touched; Frontend lint/typecheck green.
- [ ] Frontend-Ring boundary held: UI consumes the coach stream only via the BFF, no
      client-side LLM/provider call, no secrets in the bundle (§5).
- [ ] ADRs filed for the Turbo monorepo, Capacitor shells, and the client↔BFF streaming
      contract (the ⚠️ Ask-first triggers in §5), with `index.md` + `log.md` entries.
- [ ] Design tokens match `design-spec.md` §2 exactly (normative — verified, not asserted).
- [ ] Actual command/test output pasted (not summarized) for the verification claims.
