/**
 * helpers — send a message and wait for a streamed reply, robustly.
 *
 * The two functions that matter for an agent chat:
 *   - sendMessage: submit via the app's shortcut, fall back to the Send button
 *     if the network request didn't fire.
 *   - waitForResponse: wait for the rendered text to SETTLE (non-empty + stable
 *     across N reads) — never on a "finished" signal, never on composer state.
 *
 * Adapt the three selector lists and STREAM_ENDPOINT to your app.
 */

import { expect, type Locator, type Page } from "@playwright/test";

// --- Selectors: prefer data-testid; the rest are resilient fallbacks. --------
const COMPOSER_SELECTORS = [
  "[data-testid='composer']",
  "textarea[aria-label='Compose message']",
  "textarea",
  "[contenteditable='true']",
].join(", ");

// IMPORTANT: scope to the MESSAGE container's live region. A bare [aria-live]
// can match a framework's router announcer (e.g. Next.js uses
// div[aria-live='assertive'][role='alert']) and read empty text.
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

const STREAM_ENDPOINT = /\/api\/run\/stream\b/; // the POST the composer triggers

export function composer(page: Page): Locator {
  return page.locator(COMPOSER_SELECTORS).first();
}
export function sendButton(page: Page): Locator {
  return page.locator(SEND_SELECTORS).first();
}
export function messages(page: Page): Locator {
  return page.locator(MESSAGE_SELECTORS);
}

/**
 * Fill the composer and submit. Primary path is the app's submit key (set it to
 * the real one — many composers treat Cmd/Ctrl+Enter as newline). If the submit
 * request didn't fire within submitFallbackMs, click Send as a deterministic
 * fallback (covers unfocused composer / IME / DOM drift).
 */
export async function sendMessage(
  page: Page,
  text: string,
  opts?: { timeoutMs?: number; submitFallbackMs?: number },
): Promise<void> {
  const c = composer(page);
  await c.waitFor({ timeout: opts?.timeoutMs ?? 10_000 });
  await c.fill(text);

  const submitFired = page
    .waitForRequest((r) => r.method() === "POST" && STREAM_ENDPOINT.test(r.url()), {
      timeout: opts?.submitFallbackMs ?? 2_000,
    })
    .then(() => true)
    .catch(() => false);

  await c.press("Enter"); // <-- set to the app's real submit shortcut

  if (!(await submitFired)) {
    const btn = sendButton(page);
    if ((await btn.count()) > 0) await btn.first().click();
  }
}

/**
 * Wait until the assistant reply text has SETTLED, then return its locator.
 *
 * Why settle and not "finished": a streamed answer grows token by token; there
 * is no reliable single done-event. Do NOT use the SSE response's finished()
 * (can hang behind a long-lived stream / route intercept) and do NOT gate on the
 * composer being re-enabled (some backends never re-enable it). The visible-text
 * stability poll is the source of truth.
 *
 * Returns the locator even on timeout so the caller can capture a partial / a
 * status line — important when a UI renders nothing while the backend succeeded.
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

  await expect
    .poll(async () => ((await m.textContent()) ?? "").trim().length, { timeout })
    .toBeGreaterThan(0);

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

/** Soft confirmation only — never the primary done-signal (see above). */
export async function waitForComposerReady(
  page: Page,
  opts?: { timeoutMs?: number },
): Promise<void> {
  await expect(composer(page)).toBeEnabled({ timeout: opts?.timeoutMs ?? 10_000 });
}
