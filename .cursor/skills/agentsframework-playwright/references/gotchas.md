# Gotchas Catalog (AgentsFramework)

Every entry here cost real debugging time. Read before you start; each has the
symptom, the root cause, and the fix.

## Table of contents
- [1. Stale `.env` masquerading as bad credentials](#1-stale-env)
- [2. Headless Chromium renders WorkOS in Afrikaans](#2-afrikaans-locale)
- [3. The live region is a DIV, not the article](#3-live-region-div)
- [4. Don't wait on finished() or composer state](#4-wait-by-settle)
- [5. Captured text includes the status feed](#5-status-feed-prefix)
- [6. Fake session is local-only](#6-fake-session-local-only)
- [7. Cloud Logging: jsonPayload.message, not textPayload](#7-jsonpayload-message)
- [8. Don't overwrite the GoalJudge config object](#8-goal-judge-config)
- [9. No git stash for A/B testing](#9-no-git-stash)

## 1. Stale .env

**Symptom:** T3 sign-in fails; it *looks* like WorkOS rejected `E2E_USER_EMAIL` /
`E2E_USER_PASSWORD`.

**Root cause (observed):** the credentials were correct — the failure was a
**stale on-disk repo-root `.env`**. An editor had the right values in an unsaved
`Untitled` buffer while the file on disk was old; `global-setup.ts` reads the file
on disk (`loadRootEnvFile()` reads `../​.env`), so it used stale values.

**Fix:** before concluding "bad password", verify the actual on-disk `.env`
(`cat`/`grep` the key — never print the secret value). Save the buffer. The
"wrong/expired password" verdict was WRONG once already; don't repeat it. Real
WorkOS rejection surfaces as the explicit `invalid email/password` body text that
`waitForAppReturn` detects.

## 2. Afrikaans locale

**Symptom:** WorkOS hosted login renders in Afrikaans (`Gaan voort`, `Teken in`);
`has-text('Continue')` / `has-text('Sign in')` selectors miss.

**Root cause:** headless Chromium picks its locale from `Accept-Language`; without
pinning it can choose `af-ZA`. A normal Chrome profile stays English, so it only
bites in automation.

**Fix:** `e2e/fixtures/browser-context.ts` exports `E2E_BROWSER_CONTEXT` pinning
`locale: "en-US"` + an `Accept-Language` header. It's already applied in
`global-setup.ts` and `auth.fixture.ts`. Reuse it for any new context you create.
The sign-in selectors also include the Afrikaans strings as a belt-and-braces
fallback (`Gaan voort`, `Teken in`).

## 3. Live region DIV

**Symptom:** the response locator reads empty text even though the answer is
visibly on screen.

**Root cause:** the assistant turn is rendered by
`components/chat/StreamingMarkdown.tsx` as an `<article>` whose streamed text lives
in a **nested `div[aria-live='polite']`** — the live region is the DIV, not the
article (this is FE-AP-5). A bare `[aria-live]` selector matches **Next.js's route
announcer** (`div[aria-live='assertive'][role='alert']`), which is empty.

**Fix:** target `article div[aria-live='polite']` (the primary entry in
`MESSAGE_SELECTORS` in `e2e/fixtures/helpers.ts`). Prefer a `data-testid` if you
add one to the message container.

## 4. Wait by settle

**Symptom:** tests hang to the full 180s timeout, or report "done" while the
answer is still streaming / never arrives.

**Root cause:** two bad ready-signals. (a) The SSE response object's `finished()`
does **not** resolve behind the `page.route` thread-bridge intercept for the
long-lived stream — it hangs the whole test. (b) **Composer state is unreliable**:
on Cloud Run, runs were observed frozen at "Using tools: file_io…" with the
composer **never re-enabled**, so gating on `toBeEnabled()` both false-positives
and never-fires.

**Fix:** `waitForResponse` in `e2e/fixtures/helpers.ts` polls the rendered text
and returns once it's non-empty and **stable across `stableSamples` reads**
(default 3, 700ms gap). It returns the locator even on timeout so you capture
whatever rendered. `waitForComposerReady` is a *soft* confirmation only — call it
with `.catch(() => {})`, never as the gate. (Historical note: an earlier fix used
a `watchRunStream`/`response.finished()` approach — it was reverted in favor of
this text-settle poll. If you see that pattern in old notes, it's stale.)

## 5. Status feed prefix

**Symptom:** "how many runs rendered an answer?" gives wildly different numbers
depending on the heuristic (e.g. 21/22 vs 11/22).

**Root cause:** `StreamingMarkdown` is a live **status feed** — "Using tools: X…"
lines are progressively *replaced* by the streamed answer. The captured
`response_text` of a **fully-answered** run therefore *also* begins with
`Using tools: …`. A naive `len > 0` or `startswith("Using tools")` check
miscounts both ways.

**Fix:** strip leading status segments before measuring. Regex out
`(Using tools:[^…]*…)+` from the start, then check what remains. The companion
skill's `verify_run.py --status-prefix "Using tools:"` does exactly this. Also:
`cache/goaljudge_eval/ui_batch.jsonl` is **append-only** and accumulates re-runs —
**dedupe last-write-wins per `case_id`** (`--dedupe`) before computing the split,
or raw row counts mislead (the file has had 27 rows for 22 distinct cases).

## 6. Fake session local-only

**Symptom:** tempting to set `E2E_FAKE_SESSION=1` against Cloud Run to skip
sign-in.

**Root cause:** the fake cookie is sealed with the *local* `WORKOS_COOKIE_PASSWORD`.
The production server unseals with **its** secret; a mismatch yields an
unauthenticated app, and minting prod sessions is not something to do anyway.

**Fix:** `E2E_FAKE_SESSION=1` is for **local** targets only (visual/component
tests). Against Cloud Run use real sign-in (`E2E_AUTHENTICATED=1` + creds). The
sealed cookie must match production `WORKOS_COOKIE_PASSWORD` — which you should not
be reading.

## 7. jsonPayload.message

**Symptom:** `gcloud logging read … textPayload=~"…"` returns nothing, so it looks
like the backend never logged the bridge/saturation line.

**Root cause:** the backend logs structured JSON; the line lands in
**`jsonPayload.message`**, not `textPayload`.

**Fix — the working query:**
```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   AND resource.labels.service_name="agent-backend-combined"
   AND jsonPayload.message=~"goaljudge_saturation"' \
  --project=agent-prod-gcp-dev \
  --freshness=1h \
  --format='value(timestamp, jsonPayload.message)' \
  --limit=200
```
Dedupe by the per-run id before counting (retries / multiple replicas duplicate
lines). The `thread=session-gj-XXX` form appears in the log line; the bridge sends
`thread_id = gj:{case_id}:{trace_id}` and the backend resolves it to the registry
`session_id`.

## 8. GoalJudge config

**Do not overwrite** `gs://agent-prod-gcp-dev-agent-facts/ops/goal_judge_config.json`.
The shadow posture there is `goal_judge_enabled=true`,
`goal_judge_downgrade_enabled=false` (observe, never downgrade). Read it to confirm
posture (e.g. via `/healthz` or a `gsutil cat`); don't write it.

## 9. No git stash

**Don't** use `git stash push` / `pop` to A/B-compare test variants here. The repo
carries unrelated stashes, so popping yours produces conflicts. Compare by copying
files or using a worktree instead.
