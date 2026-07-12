# E1a Manual UI Walkthrough — `/learn/skill` adaptive lesson

**Epic:** E1a · **Spec:** [`docs/plan/preact-parity-epic-E1a.spec.md`](../../docs/plan/preact-parity-epic-E1a.spec.md) · **Tasks:** [`preact-parity-epic-E1a.tasks.md`](../../docs/plan/preact-parity-epic-E1a.tasks.md) · **ADR:** [`0028-lesson-content-read-path.md`](../../docs/adr/0028-lesson-content-read-path.md)

This runbook validates the **Skill lesson** surface shipped in this session (T1–T17).
Tick each `[ ]` as you confirm it. Prefer a hard refresh (`Cmd+Shift+R`) when a part
says so — the in-memory engine bag resets on full reload.

> `/learn` is a **pure on-device engine** (InMemoryEngineDb + Garvit seed + lesson seed).
> Middleware is optional for every part below. Ignore `ECONNREFUSED` on coach-marker /
> chat routes in the Next log — they do not block the skill surface.

---

## What you should expect to SEE (acceptance bar)

| # | Surface | Expect |
|---|---------|--------|
| A | Nav | **Skill** is a live control (not Coming soon) → `/learn/skill` |
| B | newSkill lesson | Eyebrow `New skill · first lesson`; main blocks ground → … → completionTry; exactly one `▸ start here` |
| C | Interactive | Self-explain echoes under the rule; completionTry grades locally; **Practice this skill** → focused quiz |
| D | Honest absence | Missing/unknown `skillId` → 404; skill without seed → empty (“Lesson coming”) |
| E | returning | After a due miss on Punctuation: eyebrow `Returning · clear the debt`; annotated + rule; rail checklist + Coach seam |
| F | Summary CTA | **See full lesson** is a live link to `/learn/skill?skillId=…` |

### Seed (why the copy looks like this)

| Piece | Source | What it gives you |
|-------|--------|-------------------|
| Learner **Garvit** | [`_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts) | `s-punc` mastery **28%**, due; other buckets as on Home |
| Lesson (one skill) | [`_lesson_seed.ts`](../lib/adapters/engine/_lesson_seed.ts) | Full teaching fields for **`s-punc`** only (`generated_from: hand:rajnish@2026-07-11`) |

**Cold open** of `/learn/skill?skillId=s-punc` → context **`newSkill`**
(Garvit has a skill row + mastery &lt; 80 + no miss attempts yet).

**After one wrong answer** on a Punctuation quiz item → context **`returning`**
(due miss on a due skill).

**Refresher recipe with full blocks** needs mastery ≥ 80 and no due misses *on a
skill that has lesson content*. Only `s-punc` is seeded; its mastery is 28%, so the
full refresher main zone is **not** reachable in this drop without code changes.
Part 7 checks context selection on a high-mastery empty skill instead; recipe order
for refresher stays unit-covered (`skill_detail_vm.test.ts`).

---

## Part 0 — Boot the UI

From `frontend/`:

```bash
cd frontend
E2E_BYPASS_AUTH=1 pnpm dev
```

- [ ] **0.1** Open **http://localhost:3000/learn** — Home loads for Garvit (not WorkOS login).
- [ ] **0.2** Hard-refresh once so you are not on a stale HMR shell.

Optional (quiets chat noise only):

```bash
# repo root
source .venv/bin/activate && python -m middleware
```

---

## Part 1 — Nav activation (T16 / FR-20)

Stay on **http://localhost:3000/learn**.

- [ ] **1.1** Sidebar / tab bar shows a **Skill** item (not greyed “Coming soon”).
- [ ] **1.2** Click **Skill**. URL is `/learn/skill` (no `skillId`) → **Lesson not found**
  (`[data-testid="skill-detail-404"]`). That is correct — the screen is live; the route
  needs a skill id.
- [ ] **1.3** Confirm **Progress** is still Coming soon (unchanged by E1a).

---

## Part 2 — newSkill happy path (T6 / T9 / T11 / T12 / FR-7 / FR-11 / FR-19)

Open **http://localhost:3000/learn/skill?skillId=s-punc** (full navigation).

- [ ] **2.1** Root `[data-testid="skill-detail"]` is visible; attribute
  `data-context="newSkill"`.
- [ ] **2.2** Eyebrow reads **New skill · first lesson**; title is the Punctuation skill name
  (from taxonomy — typically **Punctuation** / Non-essential commas labeling per seed).
- [ ] **2.3** Main column order (scroll top → bottom), each with `data-testid="block-…"`:

  | Order | `data-testid` | Spot-check copy |
  |-------|---------------|-----------------|
  | 1 | `block-ground` | “You already use commas every day…” |
  | 2 | `block-pitfall` | “…pair of commas while another needs none…” |
  | 3 | `block-question` | “So how do you tell when a clause actually needs its commas?” |
  | 4 | `block-selfExplainPrompt` | “Before you read the rule — take a guess…” |
  | 5 | `block-rule` | Removal-test body (`body_md`) |
  | 6 | `block-workedExample` | “My kitchen, which provides…” |
  | 7 | `block-completionTry` | “The teacher, who grades fairly…” |

- [ ] **2.4** Exactly **one** opener marker (`[data-testid="opener-marker"]`) on the
  ground block — text like **▸ start here**. No color-dot-only sequence without labels.
- [ ] **2.5** ✅ **ABSENT** on newSkill: misconception callout, due checklist, Coach seam,
  accuracy / trend chart (E1a carve-out — `accuracyStat` self-omits). Rail may be empty /
  missing (`skill-rail` absent or empty).

**DevTools (optional):**

```js
document.querySelector('[data-testid="skill-detail"]')?.getAttribute('data-context')
// → "newSkill"
[...document.querySelectorAll('[data-testid^="block-"]')].map(el => el.getAttribute('data-testid'))
```

---

## Part 3 — Self-explain local echo (T14 / FR-14)

Stay on the newSkill lesson (`s-punc`). Do **not** reload yet.

- [ ] **3.1** In `[data-testid="self-explain-input"]`, type a short guess
  (e.g. `when it adds extra detail`).
- [ ] **3.2** Under the **rule** block, an echo chip appears
  (`[data-testid="note-echo"]`) containing your text (e.g. “You guessed: …”).
- [ ] **3.3** Clear the input to whitespace only → echo chip **disappears**.
- [ ] **3.4** ✅ Network / mastery: answering the self-explain does **not** create quiz
  attempts or change Home mastery bars (reload Home later if you want a visual check —
  Punctuation should still be ~28%).

---

## Part 4 — completionTry + Practice CTA (T13 / T15 / FR-12 / FR-13 / FR-15)

Still on the newSkill lesson.

### Wrong then right (local only)

- [ ] **4.1** Click the **wrong** choice (`[data-testid="try-choice-1"]` —
  “Delete the commas”).
- [ ] **4.2** Feedback (`[data-testid="try-feedback"]`) shows miss / reveal; **Try again**
  (`try-again`) appears. Blocks above the try do **not** change.
- [ ] **4.3** Click **Try again**, then the **correct** choice (`try-choice-0` —
  “Keep both commas”).
- [ ] **4.4** Success feedback; **Practice this skill** CTA
  (`[data-testid="practice-skill-cta"]`) is visible.
- [ ] **4.5** CTA `href` is `/learn/quiz?focus=s-punc`. Click it.
- [ ] **4.6** Land on quiz with `?focus=s-punc`; item is Punctuation-scoped
  (`[data-testid="quiz-context"]` visible).

✅ **Scheduler inert:** these try clicks must not behave like quiz Submit (no feedback
banner from the adaptive session, no session score change from the lesson alone).

---

## Part 5 — Honest empty / 404 (T11 / FR-3 / FR-19)

- [ ] **5.1** **http://localhost:3000/learn/skill** → `skill-detail-404` / “Lesson not found”.
- [ ] **5.2** **http://localhost:3000/learn/skill?skillId=s-nope** → same 404-equivalent.
- [ ] **5.3** **http://localhost:3000/learn/skill?skillId=s-gram** (Grammar — no lesson seed)
  → `[data-testid="skill-detail-empty"]` with skill title + **Lesson coming — nothing to
  show yet.** Never a fabricated ground/rule block.

---

## Part 6 — returning context after a miss (T7 / T8 / T10 / T12 / FR-6a–6e)

Build a due miss on Punctuation, then reopen the lesson **without a full page
reload** — the engine bag is in-memory; pasting a URL into the address bar reseeds
Garvit and drops the miss.

1. From Home, click **Practice** (sidebar — soft nav).
2. Answer **wrong** on the first item (usually Punctuation) → **Submit** → see feedback.
3. Click **Finish** → Summary, then either:
   - soft-navigate to `/learn/skill?skillId=s-punc` (App Router / in-app link), or
   - if Summary recommends another skill, open Skill via an in-app navigation that
     keeps the same tab session (do **not** hard-refresh).
4. Confirm `data-context="returning"`.

- [ ] **6.1** `data-context="returning"`; eyebrow **Returning · clear the debt**.
- [ ] **6.2** Main zone does **not** show the long newSkill SCQA chain. Expect
  `annotatedExample` + `rule` (and a **misconception callout** only if the missed
  question has an authored `misconception` tag).
- [ ] **6.3** If the callout is present (`block-misconceptionCallout` /
  `[data-testid="callout-body"]`): body is the **verbatim** tag from the question —
  no “Your pattern · …” aggregate, no corrective rewrite.
- [ ] **6.4** If the miss was **untagged**: callout is **absent**; surface leads with
  annotated examples (no miss-count placeholder line).
- [ ] **6.5** Rail (`[data-testid="skill-rail"]`) shows:
  - **due checklist** of other due skills (not only the current one), and
  - a **Coach** entry seam (`[data-testid="coach-entry-seam"]`).
- [ ] **6.6** ✅ Still **no** accuracy / trend chart in the rail.

---

## Part 7 — refresher selection without lesson content (T7 / FR-4 carve-out)

Open **http://localhost:3000/learn/skill?skillId=s-style** (Style · mastery **82%**, not due,
no lesson seed).

- [ ] **7.1** Empty state (`skill-detail-empty`) — no fabricated refresher blocks.
- [ ] **7.2** (Optional unit sanity) Confirms selector would choose `refresher` for this
  mastery/due combo; full `rule → annotated → pitfall(parting)` order is asserted in
  `lib/translators/skill_detail_vm.test.ts`, not in this UI drop.

> There is **no** `?context=` override on the page yet. Do not expect to force
> `newSkill` / `returning` / `refresher` via the URL.

---

## Part 8 — Summary “See full lesson” live link (T17 / FR-20)

1. Hard-refresh **http://localhost:3000/learn**.
2. Practice → answer (wrong is fine) → **Finish** → land on Summary
   (`/learn/summary?session=…`).

- [ ] **8.1** Three actions visible: Start next / **See full lesson** / Done.
- [ ] **8.2** **See full lesson** (`[data-testid="summary-see-lesson"]`) is a **link**,
  not a disabled button; `href` matches `/learn/skill?skillId=…`.
- [ ] **8.3** Click it → skill lesson loads for that `skillId` (for Punctuation /
  `s-punc`: full lesson; for an unseeded recommended skill: honest empty).

---

## Part 9 — Optional engine / provenance checks (T1–T5 / T6 arch)

Not required for a UI pass, but useful if you want to confirm the ADR seam outside the browser:

```bash
# frontend unit / architecture
cd frontend
pnpm exec vitest run \
  lib/wire/engine_entities.test.ts \
  lib/adapters/engine/db/schema.parity.test.ts \
  lib/adapters/engine/db/to_tutorial.test.ts \
  lib/adapters/engine/repos/drizzle_tutorial_repo.test.ts \
  lib/adapters/engine/repos/drizzle_progress_repo.test.ts \
  tests/architecture/test_engine_port_conformance.test.ts \
  lib/translators/select_lesson_context.test.ts \
  lib/translators/newest_due_miss.test.ts \
  lib/translators/skill_detail_vm.test.ts \
  components/learn/use_skill_detail.test.ts \
  components/learn/SkillDetailView.test.tsx \
  components/shell/nav_model.test.ts

# repo-root provenance gate
cd ..
pytest tests/architecture/test_tutorial_provenance_confinement.py -q
```

- [ ] **9.1** Vitest suite above green.
- [ ] **9.2** Provenance pytest green.

---

## Pass / fail summary

| Part | Covers | Pass? | Notes |
|------|--------|-------|-------|
| 0 Boot | — | | |
| 1 Nav live | T16 | | |
| 2 newSkill blocks | T6, T9, T11, T12 | | |
| 3 Self-explain | T14 | | |
| 4 completionTry + CTA | T13, T15 | | |
| 5 404 / empty | T11 | | |
| 6 returning | T7, T8, T10, T12 | | |
| 7 refresher (empty) | T7 | | |
| 8 Summary lesson link | T17 | | |
| 9 Unit/arch (opt) | T1–T6 | | |

**Automated companions** (already green in this session; not a substitute for the walk):

```bash
cd frontend
E2E_BYPASS_AUTH=1 pnpm exec playwright test --project=learn-e2e \
  e2e/learn/skill-lesson.spec.ts \
  e2e/learn/summary-payoff.spec.ts
```

---

## Task → walkthrough map

| Tasks | Where validated |
|-------|-----------------|
| T1–T5 engine ports / schema | Part 9 (optional) + implied by Parts 2–6 loading |
| T6 lesson seed + provenance | Parts 2 + 9 |
| T7 context selector | Parts 2, 6, 7 |
| T8 newest-due-miss | Part 6 callout / hide |
| T9–T10 recipes | Parts 2 + 6 (+ unit for refresher) |
| T11 route shell | Parts 1–2, 5 |
| T12 block renderers | Parts 2, 6 |
| T13–T15 interactivity + CTA | Parts 3–4 |
| T16 nav flip | Part 1 |
| T17 summary link | Part 8 |
