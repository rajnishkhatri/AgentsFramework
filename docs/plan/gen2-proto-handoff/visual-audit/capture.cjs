/**
 * Paired-state capture: v3 prototype (file://) vs app (localhost:3000).
 * Drives both surfaces through matched journey states, one full-page PNG per state.
 * Output: <OUT>/<seq>-<state>-{proto|app}.png + capture-log.json
 */
const path = require("path");
const fs = require("fs");
const { chromium } = require("/Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend/node_modules/@playwright/test");

const OUT = __dirname;
const PROTO_URL =
  "file:///Users/rajnishkhatri/Documents/AgentsFramework/agent/docs/plan/gen2-proto-handoff/English%20Coach%20-%20Gen2%20Slice%20v3%20-desktop-.html";
const APP = "http://localhost:3000";
const VIEWPORT = { width: 1440, height: 900 };
const log = [];

function note(msg) {
  log.push(msg);
  console.log(msg);
}

async function shot(page, name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  note(`captured ${name}`);
}

async function step(name, fn) {
  try {
    await fn();
  } catch (e) {
    note(`FAILED ${name}: ${String(e).slice(0, 200)}`);
  }
}

// ---------- prototype ----------
async function protoBtn(page, re) {
  const b = page.getByRole("button", { name: re }).first();
  await b.waitFor({ state: "visible", timeout: 8000 });
  await b.click();
}

async function captureProto(browser) {
  const page = await browser.newPage({ viewport: VIEWPORT });
  await page.goto(PROTO_URL, { waitUntil: "load" });
  await page.waitForTimeout(1200); // bundler boot

  await step("proto quiz idle", async () => {
    await protoBtn(page, /^2\s*Quiz$/);
    await page.waitForTimeout(400);
    await shot(page, "01-quiz-idle-proto");
  });

  await step("proto ack+rung1", async () => {
    await protoBtn(page, /^B\s/);
    await page.waitForTimeout(200);
    await protoBtn(page, /^Submit answer$/);
    await page.waitForTimeout(600);
    await shot(page, "02-ack-rung1-proto");
  });

  await step("proto rung2", async () => {
    await protoBtn(page, /Show me more|I'm still stuck|I’m still stuck/);
    await page.waitForTimeout(600);
    await shot(page, "03-rung2-proto");
  });

  await step("proto exhaustion", async () => {
    for (let i = 0; i < 3; i++) {
      const walk = page.getByRole("button", { name: /Walk me through it/ });
      if ((await walk.count()) > 0 && (await walk.first().isVisible())) break;
      const more = page
        .getByRole("button", { name: /Show me more|I'm still stuck|I’m still stuck/ })
        .first();
      if ((await more.count()) === 0) break;
      await more.click();
      await page.waitForTimeout(600);
    }
    await shot(page, "04-exhaustion-proto");
  });

  await step("proto walkthrough feedback", async () => {
    await protoBtn(page, /Walk me through it/);
    await page.waitForTimeout(800);
    await shot(page, "05-walkthrough-feedback-proto");
  });

  await step("proto feedback tab", async () => {
    await protoBtn(page, /^3\s*Feedback$/);
    await page.waitForTimeout(500);
    await shot(page, "06-feedback-tab-proto");
  });

  await step("proto coach tab", async () => {
    await protoBtn(page, /^4\s*Coach$/);
    await page.waitForTimeout(500);
    await shot(page, "07-coach-proto");
  });

  await step("proto summary tab", async () => {
    await protoBtn(page, /^5\s*Summary$/);
    await page.waitForTimeout(500);
    await shot(page, "08-summary-proto");
  });

  await step("proto dashboard tab", async () => {
    await protoBtn(page, /^1\s*Dashboard$/);
    await page.waitForTimeout(500);
    await shot(page, "09-dashboard-proto");
  });

  // fresh run: wrong -> try again -> correct (coached solve)
  await step("proto coached-solve feedback", async () => {
    await page.goto(PROTO_URL, { waitUntil: "load" });
    await page.waitForTimeout(1200);
    await protoBtn(page, /^2\s*Quiz$/);
    await page.waitForTimeout(400);
    await protoBtn(page, /^B\s/);
    await page.waitForTimeout(200);
    await protoBtn(page, /^Submit answer$/);
    await page.waitForTimeout(600);
    await protoBtn(page, /Let me try again/);
    await page.waitForTimeout(400);
    await protoBtn(page, /^A\s/);
    await page.waitForTimeout(200);
    const submit = page.getByRole("button", { name: /^Submit answer$/ });
    if ((await submit.count()) > 0) await submit.first().click();
    await page.waitForTimeout(800);
    await shot(page, "10-coached-solve-proto");
  });

  await page.close();
}

// ---------- app ----------
const tid = (page, id) => page.locator(`[data-testid='${id}']`);

async function appSubmitWrong(page) {
  // Try A; if it was correct (feedback), advance and try B.
  await tid(page, "choice-A").first().click();
  await tid(page, "quiz-submit").click();
  const coached = tid(page, "quiz-coached-section");
  const feedback = tid(page, "feedback-banner");
  await Promise.race([
    coached.waitFor({ state: "visible", timeout: 10000 }),
    feedback.waitFor({ state: "visible", timeout: 10000 }),
  ]);
  if (await feedback.isVisible()) {
    await tid(page, "quiz-next").click();
    await page.locator("[data-skill]").first().waitFor({ timeout: 10000 });
    await tid(page, "choice-B").first().click();
    await tid(page, "quiz-submit").click();
    await coached.waitFor({ state: "visible", timeout: 10000 });
  }
}

async function captureApp(browser) {
  const page = await browser.newPage({ viewport: VIEWPORT });
  await page.goto(`${APP}/learn/quiz`, { waitUntil: "networkidle" });

  await step("app quiz idle", async () => {
    await tid(page, "quiz-progress").waitFor({ timeout: 15000 });
    const hintToggle = await tid(page, "quiz-hint-toggle").count();
    if (hintToggle > 0) note("WARNING: quiz-hint-toggle present — commit_first flag looks OFF");
    await shot(page, "01-quiz-idle-app");
  });

  await step("app ack+rung1", async () => {
    await appSubmitWrong(page);
    await shot(page, "02-ack-rung1-app");
  });

  await step("app rung2", async () => {
    await tid(page, "quiz-nudge").click();
    await page.waitForTimeout(500);
    await shot(page, "03-rung2-app");
  });

  await step("app exhaustion", async () => {
    for (let i = 0; i < 3; i++) {
      if (await tid(page, "quiz-escape").isVisible().catch(() => false)) break;
      const n = tid(page, "quiz-nudge");
      if ((await n.count()) === 0) break;
      await n.click();
      await page.waitForTimeout(500);
    }
    await tid(page, "quiz-escape").waitFor({ timeout: 5000 });
    await shot(page, "04-exhaustion-app");
  });

  await step("app walkthrough feedback", async () => {
    await tid(page, "quiz-escape").click();
    await tid(page, "feedback-banner").waitFor({ timeout: 10000 });
    await shot(page, "05-walkthrough-feedback-app");
  });

  await step("app coached-solve feedback", async () => {
    await tid(page, "quiz-next").click();
    await page.locator("[data-skill]").first().waitFor({ timeout: 10000 });
    // wrong first
    await tid(page, "choice-A").first().click();
    await tid(page, "quiz-submit").click();
    const coached = tid(page, "quiz-coached-section");
    const feedback = tid(page, "feedback-banner");
    await Promise.race([
      coached.waitFor({ state: "visible", timeout: 8000 }),
      feedback.waitFor({ state: "visible", timeout: 8000 }),
    ]);
    if (await feedback.isVisible()) {
      // A was correct: this is a first-try feedback; still capture as bonus then move on
      await shot(page, "10b-firsttry-feedback-app");
      await tid(page, "quiz-next").click();
      await page.locator("[data-skill]").first().waitFor({ timeout: 10000 });
      await tid(page, "choice-B").first().click();
      await tid(page, "quiz-submit").click();
      await coached.waitFor({ state: "visible", timeout: 8000 });
    }
    // now in coached loop: switch letters until correct
    for (const L of ["B", "C", "D", "A"]) {
      const c = tid(page, `choice-${L}`);
      if ((await c.count()) === 0) continue;
      await c.first().click().catch(() => {});
      await tid(page, "quiz-submit").click().catch(() => {});
      await page.waitForTimeout(700);
      if (await feedback.isVisible().catch(() => false)) break;
    }
    await feedback.waitFor({ timeout: 5000 });
    await shot(page, "10-coached-solve-app");
  });

  await step("app end-session result", async () => {
    const end = page.locator("button").filter({ hasText: /End session/ }).first();
    await end.click();
    await page.waitForTimeout(1500);
    await shot(page, "08-end-session-result-app");
    note(`end-session landed on: ${page.url()}`);
  });

  await step("app summary direct", async () => {
    await page.goto(`${APP}/learn/summary`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await shot(page, "08b-summary-direct-app");
  });

  await step("app coach page", async () => {
    await page.goto(`${APP}/learn/coach`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await shot(page, "07-coach-app");
  });

  await step("app dashboard", async () => {
    await page.goto(`${APP}/learn`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await shot(page, "09-dashboard-app");
  });

  await page.close();
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  await captureProto(browser);
  await captureApp(browser);
  await browser.close();
  fs.writeFileSync(path.join(OUT, "capture-log.json"), JSON.stringify(log, null, 2));
  note("done");
})();
