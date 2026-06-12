/**
 * One-off GCP live verification: pause → edit → resume (task_understanding Phase 4).
 */
import { test, expect } from "../fixtures/auth.fixture";

test.describe.configure({ mode: "serial", timeout: 180_000 });

test("live GCP: pause → edit → save & resume → user_edited card", async ({
  authenticatedPage: page,
}) => {
  let capturedThreadId: string | null = null;
  page.on("request", (req) => {
    const url = req.url();
    if (url.includes("/api/run/understanding/") && req.method() === "POST") {
      const m = url.match(/\/api\/run\/understanding\/([^/?]+)/);
      if (m) capturedThreadId = decodeURIComponent(m[1]!);
    }
  });

  await page.goto("/");
  const composer = page.locator("textarea[aria-label='Compose message']");
  await expect(composer).toBeVisible({ timeout: 30_000 });

  await composer.fill(
    "Create /workspace/verify-edit.txt with the text 'live-gcp-check', then read it back with file_io and show the contents.",
  );
  await page.locator("button[aria-label='Send']").click();

  const card = page.locator("[data-testid='task-understanding-card']");
  await expect(card).toBeVisible({ timeout: 120_000 });
  await expect(card).toHaveAttribute("data-source", /generated|deterministic/);

  await page.locator("[data-testid='understanding-edit']").click();
  await expect(card).toHaveAttribute("data-editing", "true");

  await page
    .locator("[data-testid='understanding-intent-input']")
    .fill("Only verify the live GCP edit round trip.");
  await page
    .locator("[data-testid='understanding-condition-input-0']")
    .fill("The file verify-edit.txt exists with live-gcp-check");
  await page.locator("[data-testid='understanding-save']").click();

  const message = page.locator("[data-testid='assistant-message']");
  await expect(message).toHaveAttribute("data-state", "complete", {
    timeout: 180_000,
  });
  await expect(card).toHaveAttribute("data-source", "user_edited");
  await expect(card).toContainText("Only verify the live GCP edit round trip.");

  await page.screenshot({
    path: "smoke-screenshots/understanding-edit-live.png",
    fullPage: true,
  });

  test.info().annotations.push({
    type: "thread_id",
    description: capturedThreadId ?? "not-captured-from-understanding-POST",
  });
});
