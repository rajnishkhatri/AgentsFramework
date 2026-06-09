/**
 * Shared Playwright helpers for chat interactions.
 *
 * Selectors are intentionally permissive (multiple options separated by
 * commas) so the same helper works against the current implementation and
 * tolerates minor markup changes. Each helper accepts an optional timeout
 * so callers can tighten the budget when running against a backend.
 */

import { expect, type Locator, type Page } from "@playwright/test";

const COMPOSER_SELECTORS = [
  "[data-testid='composer']",
  "textarea[aria-label='Compose message']",
  "textarea",
  "[contenteditable='true']",
].join(", ");

// The assistant turn is rendered by `components/chat/StreamingMarkdown.tsx`
// as an <article> whose streamed text lives in a nested
// `div[aria-live='polite']` (the live region is the DIV, NOT the article --
// FE-AP-5). We therefore target that content DIV as the primary handle.
// `[aria-live='polite']` deliberately excludes Next.js's route announcer,
// which is `div[aria-live='assertive'][role='alert']`. The remaining
// entries are structural/legacy fallbacks for other surfaces.
const MESSAGE_SELECTORS = [
  "article div[aria-live='polite']",
  "[data-testid='message-content']",
  "[role='log']",
  ".message-content",
].join(", ");

const SEND_SELECTORS = [
  "[data-testid='send-button']",
  "button[aria-label='Send']",
  "button:has-text('Send')",
].join(", ");

/** Returns the first matching composer locator. */
export function composer(page: Page): Locator {
  return page.locator(COMPOSER_SELECTORS).first();
}

/** Returns the first matching send-button locator. */
export function sendButton(page: Page): Locator {
  return page.locator(SEND_SELECTORS).first();
}

/** Returns a locator over assistant message regions. */
export function messages(page: Page): Locator {
  return page.locator(MESSAGE_SELECTORS);
}

/**
 * Fill the composer with `text` and submit.
 *
 * `Composer.tsx` submits on **plain Enter**; Meta/Ctrl/Shift+Enter are treated
 * as newline (the U_KBD contract enforced by
 * `frontend/scripts/check_composer_keyboard.ts`). We therefore press plain
 * Enter as the primary path. As a fallback — for cases where the composer is
 * not focused, an IME composition swallowed the key, or remote DOM drift — we
 * click the Send button if Enter did not kick off `POST /api/run/stream`
 * within `submitFallbackMs`.
 */
export async function sendMessage(
  page: Page,
  text: string,
  opts?: { timeoutMs?: number; submitFallbackMs?: number },
): Promise<void> {
  const c = composer(page);
  await c.waitFor({ timeout: opts?.timeoutMs ?? 10_000 });
  await c.fill(text);

  // Arm the request watcher before pressing Enter so we don't miss a fast
  // submit. A rejection here (timeout) just means Enter didn't submit.
  const submitFired = page
    .waitForRequest(
      (req) => req.method() === "POST" && /\/api\/run\/stream\b/.test(req.url()),
      { timeout: opts?.submitFallbackMs ?? 2_000 },
    )
    .then(() => true)
    .catch(() => false);

  await c.press("Enter");

  if (!(await submitFired)) {
    // Enter did not submit (unfocused composer, IME, DOM drift) — use the
    // Send button as a deterministic fallback.
    const btn = sendButton(page);
    if ((await btn.count()) > 0) {
      await btn.first().click();
    }
  }
}

/**
 * Wait until the assistant response text has **settled** (non-empty and stable
 * across `stableSamples` consecutive reads), then return the message locator.
 *
 * `StreamingMarkdown` renders a live *status feed*: "Using tools: …" lines are
 * progressively replaced by the streamed answer. We poll the content region and
 * return once the trimmed text stops changing. This captures the full answer for
 * runs that stream one (observed streaming 19→905+ chars over several seconds on
 * Cloud Run) and faithfully captures the status line for runs that never emit a
 * rendered answer.
 *
 * NOTE on what "settled" means: do NOT assume `busy=false` / composer-enabled
 * implies the stream finished. On Cloud Run we observed runs where the composer
 * is never disabled and the DOM stays frozen at "Using tools: file_io…" — the
 * final answer is simply never rendered for that run. The text-stability poll
 * is therefore the source of truth, not the composer state.
 *
 * We avoid gating on the SSE response object's `finished()`: behind the
 * `page.route` thread-bridge intercept it does not resolve for the long-lived
 * event stream and hung the entire 180s test timeout.
 */
export async function waitForResponse(
  page: Page,
  opts?: { timeoutMs?: number; stableSamples?: number; sampleGapMs?: number },
): Promise<Locator> {
  const m = messages(page).first();
  const timeout = opts?.timeoutMs ?? 30_000;
  const gap = opts?.sampleGapMs ?? 700;
  const needStable = opts?.stableSamples ?? 3;
  const deadline = Date.now() + timeout;

  // Ensure the region exists and has produced *some* text.
  await expect
    .poll(async () => ((await m.textContent()) ?? "").trim().length, { timeout })
    .toBeGreaterThan(0);

  // Confirm the rendered text has stopped changing.
  let last = "";
  let stable = 0;
  while (Date.now() < deadline) {
    const cur = ((await m.textContent()) ?? "").trim();
    if (cur.length > 0 && cur === last) {
      if (++stable >= needStable) return m;
    } else {
      stable = 0;
      last = cur;
    }
    await page.waitForTimeout(gap);
  }
  return m;
}

/**
 * Wait until the composer is enabled (i.e. the agent run has finished or
 * been cancelled). Mirrors the SS2.5 expectation that Stop re-enables the
 * composer within ~1s.
 */
export async function waitForComposerReady(
  page: Page,
  opts?: { timeoutMs?: number },
): Promise<void> {
  await expect(composer(page)).toBeEnabled({ timeout: opts?.timeoutMs ?? 10_000 });
}
