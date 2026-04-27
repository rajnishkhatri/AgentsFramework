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

const MESSAGE_SELECTORS = [
  "[data-testid='message-content']",
  "article[aria-live='polite']",
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
 * Fill the composer with `text` and submit via the platform-correct
 * keyboard shortcut (Cmd+Enter on macOS, Ctrl+Enter elsewhere).
 */
export async function sendMessage(
  page: Page,
  text: string,
  opts?: { timeoutMs?: number },
): Promise<void> {
  const c = composer(page);
  await c.waitFor({ timeout: opts?.timeoutMs ?? 10_000 });
  await c.fill(text);
  const mod = process.platform === "darwin" ? "Meta" : "Control";
  await c.press(`${mod}+Enter`);
}

/**
 * Wait until at least one assistant response region is visible. Returns the
 * locator so callers can chain text-content assertions.
 */
export async function waitForResponse(
  page: Page,
  opts?: { timeoutMs?: number },
): Promise<Locator> {
  const m = messages(page).first();
  await m.waitFor({ timeout: opts?.timeoutMs ?? 30_000 });
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
