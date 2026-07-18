/**
 * @t3 Eng Coach × WorkOS local full-stack validation.
 *
 * Proves authenticated /learn shell + live coach turn against real WorkOS
 * session + local BFF + local middleware (no E2E_BYPASS_AUTH, no MOCK_MIDDLEWARE,
 * no page.route mock of /api/coach/run/stream).
 *
 * Spec: docs/plan/eng-coach-workos-e2e-local.spec.md (FR-2,3,5,7,8).
 * Companion unauth redirect: e2e/coach-auth-guard.spec.ts (FR-1).
 *
 * Cadence: on-demand / local only — not per-commit CI.
 */

import { test, expect, type Page } from "../fixtures/auth.fixture";

const BYPASS = process.env.E2E_BYPASS_AUTH === "1";
const MOCK_MW = process.env.MOCK_MIDDLEWARE === "1";
const AUTHENTICATED = process.env.E2E_AUTHENTICATED === "1";

const HOSTED_LOGIN_RE = /authkit\.|workos\.|\/api\/auth|\/sign-in|sign-in/i;

function isHostedLoginUrl(url: URL): boolean {
  return HOSTED_LOGIN_RE.test(url.href) || HOSTED_LOGIN_RE.test(url.pathname);
}

/** Strip transient status prefixes before emptiness checks (TAP-3). */
function stripStatusPrefixes(text: string): string {
  return text
    .replace(/^Using tools:[^\n]*\n?/gim, "")
    .replace(/^Thinking\.{0,3}\s*/gim, "")
    .trim();
}

/**
 * Settle-poll the coach [role=log] until text is non-empty and stable.
 * Do not reuse chat waitForResponse — it prefers article aria-live and
 * watches /api/run/stream (wrong for coach).
 */
async function waitForCoachLogSettle(
  page: Page,
  opts?: { timeoutMs?: number; stableMs?: number },
): Promise<string> {
  const timeoutMs = opts?.timeoutMs ?? 90_000;
  const stableMs = opts?.stableMs ?? 1_500;
  const log = page.locator("[role='log']");
  await expect(log).toBeVisible({ timeout: 15_000 });

  const deadline = Date.now() + timeoutMs;
  let last = "";
  let lastChange = Date.now();

  while (Date.now() < deadline) {
    const raw = (await log.innerText().catch(() => "")) ?? "";
    const cleaned = stripStatusPrefixes(raw);
    if (cleaned !== last) {
      last = cleaned;
      lastChange = Date.now();
    } else if (cleaned.length > 0 && Date.now() - lastChange >= stableMs) {
      return cleaned;
    }
    await page.waitForTimeout(250);
  }

  throw new Error(
    `Coach log did not settle to non-empty text within ${timeoutMs}ms ` +
      `(last cleaned length=${last.length})`,
  );
}

test.describe("@t3 coach WorkOS local (FR-3/FR-7)", () => {
  test.skip(
    BYPASS,
    "E2E_BYPASS_AUTH=1 — cannot claim WorkOS gate under bypass (FR-2)",
  );
  test.skip(
    MOCK_MW,
    "MOCK_MIDDLEWARE=1 — T3 must hit real local middleware (FR-8 / Q-C5)",
  );
  test.skip(
    !AUTHENTICATED,
    "E2E_AUTHENTICATED!=1 — needs real WorkOS storageState (FR-5)",
  );

  test("FR-3 /learn shell renders for authenticated session", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/learn", { waitUntil: "domcontentloaded" });
    await expect
      .poll(() => isHostedLoginUrl(new URL(page.url())), { timeout: 15_000 })
      .toBe(false);

    const focus = page.getByTestId("today-focus");
    const primary = page.getByRole("navigation", { name: "Primary" });
    await expect(focus.or(primary).first()).toBeVisible({ timeout: 20_000 });
  });

  test("FR-3 /learn/coach shell renders for authenticated session", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/learn/coach", { waitUntil: "domcontentloaded" });
    await expect
      .poll(() => isHostedLoginUrl(new URL(page.url())), { timeout: 15_000 })
      .toBe(false);

    const log = page.locator("[role='log']");
    const composer = page.locator("textarea").first();
    const primary = page.getByRole("navigation", { name: "Primary" });
    await expect(log.or(composer).or(primary).first()).toBeVisible({
      timeout: 20_000,
    });
  });

  test("FR-7 live coach turn settles non-empty assistant text", async ({
    authenticatedPage: page,
  }) => {
    // Settle budget is 90s; leave headroom above Playwright's default 60s.
    test.setTimeout(120_000);
    // FR-8: by construction — no page.route on /api/coach/run/stream.
    await page.goto("/learn/coach", { waitUntil: "domcontentloaded" });
    await expect
      .poll(() => isHostedLoginUrl(new URL(page.url())), { timeout: 15_000 })
      .toBe(false);

    const composer = page.getByRole("textbox", { name: "Compose message" });
    await expect(composer).toBeVisible({ timeout: 15_000 });
    // Do NOT use helpers.sendMessage — it watches /api/run/stream, not coach.
    // pressSequentially (not fill) so React controlled state enables Send.
    await composer.click();
    await composer.fill("");
    await composer.pressSequentially("What is a comma splice?", { delay: 15 });

    const send = page.getByRole("button", { name: "Send" });
    await expect(send).toBeEnabled({ timeout: 5_000 });

    const streamPosted = page.waitForRequest(
      (req) =>
        req.method() === "POST" &&
        /\/api\/coach\/run\/stream\b/.test(req.url()),
      { timeout: 15_000 },
    );
    await send.click();
    await streamPosted;

    const settled = await waitForCoachLogSettle(page, { timeoutMs: 90_000 });
    expect(settled.length, "settled coach log must be non-empty").toBeGreaterThan(
      0,
    );
  });

  test("FR-5 / FR-8 greeting ≠ Garvit and demo focus slate absent", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/learn", { waitUntil: "domcontentloaded" });
    await expect
      .poll(() => isHostedLoginUrl(new URL(page.url())), { timeout: 15_000 })
      .toBe(false);

    const greeting = page.getByTestId("dashboard-greeting");
    await expect(greeting).toBeVisible({ timeout: 20_000 });
    await expect(greeting).not.toContainText("Garvit");

    // Fresh slate: no demo punctuation-at-28% focus banner (honest empty / no focus).
    await expect(page.getByTestId("today-focus")).toHaveCount(0);
  });
});
