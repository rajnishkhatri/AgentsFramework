# S3.1 Manual UI Walkthrough — Round-Robin Skill Rotation

**Sprint:** S3.1 · **Spec:** [`docs/plan/preact-quiz-skill-rotation.spec.md`](../../docs/plan/preact-quiz-skill-rotation.spec.md) · **ADR:** [`docs/adr/0024-quiz-skill-rotation-round-robin.md`](../../docs/adr/0024-quiz-skill-rotation-round-robin.md) · **PR:** [#136](https://github.com/rajnishkhatri/AgentsFramework/pull/136)

This runbook validates **only the S3.1 change** — the fix for *"after completing /
finishing a skill, the next skill is always sentence-completion."* Follow it top to
bottom; tick each `[ ]` box as you confirm it.

> This is a companion to the broader S3 runbook
> [`validate_s3_bounded_session.md`](validate_s3_bounded_session.md) (which covers
> `target_count` + within-session no-repeat). If you only want to confirm the
> rotation fix, this file is self-contained.

---

## The bug, in one line

Within-session serving is **read-only** (S3 / FR-13 — no `skill_state` write), so
mastery is **frozen** for the whole session. The old scheduler sorted the pool
**weakest-mastery first**, which is a *fixed* order for a frozen session — so once
the due skills drained, the same next-weakest skill (`s-sent`, sentence-completion)
was served **every time**. It was never hardcoded; it was an emergent fixed point.

## The fix, in one line

Rotation is now the **primary** sort key: the scheduler serves the
**least-recently-served skill first** (`servedSkillIds`, newest-first, derived from
the session's `attempt` rows), and only breaks ties by the old weakest → due → id
order. A just-served skill goes to the **back** of the line, so the session cycles
across skills instead of parking on one.

---

## What you should expect to SEE (the acceptance bar)

Over a walk of ~8 items, answering each and pressing **Next**:

1. **No skill is served twice in a row.** (The core fix.)
2. **The walk spreads across ≥3 distinct skills** — it *rotates*.
3. In particular, **sentence-completion is no longer the perpetual "next"** — it
   takes exactly its turn in the cycle and then yields.

### Reference: the dev seed (why the topics rotate the way they do)

The dev preview seeds learner **"Maya"** with this mastery spread
([`lib/adapters/engine/_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts)). The
quiz questions themselves come from the governed **171-item bank** (ADR-0021).

| Skill id  | Topic (as it reads in the stem)      | Seed mastery | Due now? |
|-----------|--------------------------------------|:------------:|:--------:|
| `s-punc`  | **Punctuation** (commas, semicolons) |     0.28     |   ✅ (weakest → served **first**) |
| `s-org`   | **Organization** (transitions)       |     0.40     |   ✅ |
| `s-gram`  | **Grammar & Usage** (verb form)      |     0.55     |   ✅ |
| `s-sent`  | **Sentence Structure** (fused/run-on)|     0.61     |   — |
| `s-rhet`  | **Rhetorical Skills** (word choice)  |     0.74     |   — |
| `s-style` | **Style** (redundancy, wordiness)    |     0.82     |   — |

Punctuation is the weakest, so it is **still served first** (rotation is opt-in and
backward-compatible — FR-1). After that, the session **rotates**.

---

## Part 0 — Start the UI

You can drive this with the Claude Code preview server (recommended) or a plain
`pnpm dev`.

- [ ] **0.1** From the repo root, the app is running on **http://localhost:3000**.
  The dev preview uses `E2E_BYPASS_AUTH=1` so there is **no WorkOS sign-in** to get
  past for `/learn`.

> `/learn` is a **pure on-device engine** — no Python backend. If you see
> `ECONNREFUSED` on `/api/threads`, `/api/models`, or `/api/memory` in the server
> log, **ignore it** — those are the chat/coach routes reaching for the (not-running)
> middleware. They do **not** affect the quiz.

- [ ] **0.2** Open **http://localhost:3000/learn/quiz**. A **Punctuation** item
  loads first — the stem reads *"Which choice punctuates the items in the series
  correctly?"* (Maya's weakest skill served first.)

---

## Part 1 — Watch the rotation (the fix)

- [ ] **1.1** Note the **topic of the first item** (Punctuation).
- [ ] **1.2** Answer it: pick any choice → **"Submit answer"** → the Feedback panel
  appears → **"Next question →"**.
- [ ] **1.3** Note the **topic of the second item**. ✅ **EXPECT:** it is a
  **different** topic (e.g. Organization — *"Which choice best introduces the
  sentence…"*), **not** another Punctuation item.
- [ ] **1.4** Repeat for **~8 items total**, jotting the topic of each.
- [ ] **1.5** ✅ **EXPECT:** the sequence **cycles across skills** and **no two
  consecutive items share a skill**. A representative walk (verified live on
  `424d8cc`) looks like:

  ```
  Punctuation → Organization → Grammar → Sentence structure →
  Rhetoric → Style → Punctuation → Organization
  ```

  The key observations:
  - **No skill appears twice in a row.**
  - **Sentence structure (`s-sent`) appears exactly once, mid-cycle** — the old bug
    made it the perpetual next; now it takes its turn and yields. **This is the
    fix.**
  - The cycle **wraps** back to Punctuation after the least-recently-served skill
    (Punctuation, served longest ago) rotates back to the front.

### Fast way to confirm it deterministically (optional)

The item root carries a **test-only `data-skill`** attribute (added in S3.1 so the
Playwright spec can read the served skill without guessing from prose — it is **not**
visible UI; the skill name is not rendered until S4). In DevTools → Console:

```js
document.querySelector("[data-skill]").getAttribute("data-skill")
// → "s-punc" on the first item, "s-org" on the next, …
```

- [ ] **1.6** *(optional)* Run that after each **Next** and confirm the `data-skill`
  value **changes every time** and never repeats consecutively.

---

## Part 2 — Backward-compatibility & purity (the guardrails)

- [ ] **2.1 (FR-1 — weakest-first still holds on a fresh session).** Reload
  **http://localhost:3000/learn/quiz** (fresh session, empty served set). ✅
  **EXPECT:** the first item is **Punctuation** again — with nothing served yet,
  rotation is a no-op and the weakest-first behaviour is unchanged.
- [ ] **2.2 (FR-9 — no repeats, inherited from S3).** Across the whole ~8-item walk,
  ✅ **EXPECT:** you **never** see the **same question stem** twice. Rotation reorders
  *which skill* is tried first; the S3 no-repeat guarantee is untouched.
- [ ] **2.3 (No console errors).** With DevTools → Console open through the walk, ✅
  **EXPECT: zero errors.** (Verified live: the 8-item walk produced no console
  errors.)

---

## Part 3 — Focus deep-link (honest scope note — READ THIS)

The Summary/Dashboard can deep-link into the quiz with `?focus=<skillId>` (e.g.
**http://localhost:3000/learn/quiz?focus=s-gram**), which opens the session in
**drill** mode.

- [ ] **3.1** Open **http://localhost:3000/learn/quiz?focus=s-gram**.

> ✅ **2026-07-10:** Drill now pins to `skill_focus` (FR-A5) in `openQuizItem` —
> `?focus=s-gram` serves only Grammar items (no cross-skill rotation in drill).
> Adaptive sessions still rotate (Parts 1–2). Re-check: 3.1 opens; items stay on
> the focused skill.

---

## What is NOT in scope for S3.1 (do not treat as a bug)

- [ ] **No visible skill label / progress bar.** The served skill is exposed only as
  the test-only `data-skill` attribute; a rendered "12 of 30" progress bar and a
  visible skill name are **S4** (deferred). Verify rotation via the topic of each
  item or the `data-skill` read.
- [ ] **The Drizzle store is not exercised.** The rotation read has a Drizzle
  (`listSessionSkillIds`) implementation, but `InMemoryEngineDb` is the only wired
  engine store today, so the browser walk exercises the in-memory path. (Deferred
  Drizzle parity test noted in the PR.)

---

## Sign-off

- [ ] **Part 1** — ~8-item walk rotates across ≥3 skills; **no skill twice in a row**;
  sentence-completion takes exactly one turn (the bug is fixed).
- [ ] **Part 2.1** — fresh reload still serves Punctuation first (FR-1 backward-compat).
- [ ] **Part 2.2** — no repeated question stem across the walk (FR-9 intact).
- [ ] **Part 2.3** — no console errors.
- [ ] **Part 3** — `?focus=` opens; items stay on the focused skill (FR-A5).

If Part 1 and Part 2 are ticked, the S3.1 rotation fix is validated in the live UI:
the "always sentence-completion" behaviour is gone, replaced by a clean round-robin,
with the S3 no-repeat guarantee and weakest-first fallback both preserved.

---

### Automated backstop (already green — for reference)

You do **not** need to run these for the manual walkthrough, but they are the
programmatic proof behind it:

```bash
cd frontend
# Real-seam harness (adds the FR-3 real-bank rotation check to the S3 suite):
./node_modules/.bin/tsx scripts/validate_s3_bounded_session.ts     # → 22 passed, 0 failed

# Live Playwright (real browser, learn-e2e project) — the same 8-item walk:
npx playwright test --project=learn-e2e e2e/learn/quiz-rotation.spec.ts   # → 2 passed
```
