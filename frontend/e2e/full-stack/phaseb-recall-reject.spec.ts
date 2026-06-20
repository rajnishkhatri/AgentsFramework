/**
 * Tier 3 — Phase B recall→reject→re-run validation against deployed Cloud Run.
 *
 * DRIVER + CAPTURE: per reject-corpus case CRUD-seeds memories under identity.owner
 * (so eval disclosure joins recalled keys to the panel), drives run-1 (recall +
 * disclosure screenshot), reject (soft-suppress), run-2 (exclusion screenshot).
 * DOM asserts only that the eval disclosure rendered recalled rows; ALL governance
 * scoring (C1/C3/C4/C5) is the offline analyzer on Langfuse traces.
 *
 * Plan: docs/plans/chat_persistence_phaseb_gcp_e2e_validation.plan.md
 *
 * On-demand only (@t3); never per-commit CI. Requires MEMORY_ENABLED=1 revision:
 *   TEST_PROFILE=mem pnpm test:e2e:phaseb   (memui FE → phaseb BE; WorkOS auth)
 *   TEST_PROFILE=phaseb pnpm test:e2e:phaseb  (E2E_BYPASS_AUTH only works locally)
 *
 * Optional:
 *   PHASEB_CASE_FILTER=PHASEB-UNITS
 *   PHASEB_SMOKE=1           — first case only
 *   PHASEB_JSONL / PHASEB_ARTIFACT_DIR — override output paths
 *
 * JSONL schema (one row per run): case, run, trace_id, session_id, user_id,
 *   query, reject_key?, recalled_row_keys, screenshot_path, finished_at, base_url.
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect, STORAGE_STATE_PATH } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
  composer,
} from "../fixtures/helpers";
import {
  filterPhasebCases,
  smokePhasebCases,
  type PhasebRejectCase,
  type SeedMemory,
} from "../fixtures/phaseb_reject_corpus";

const CASES: PhasebRejectCase[] =
  process.env.PHASEB_SMOKE === "1"
    ? smokePhasebCases()
    : filterPhasebCases({
        caseFilter: process.env.PHASEB_CASE_FILTER,
        limit: process.env.PHASEB_LIMIT
          ? Number(process.env.PHASEB_LIMIT)
          : undefined,
      });

const OUTPUT_JSONL =
  process.env.PHASEB_JSONL ??
  path.join(process.cwd(), "..", "cache", "phaseb_reject", "probe_batch.jsonl");

const ARTIFACT_DIR =
  process.env.PHASEB_ARTIFACT_DIR ??
  path.join(process.cwd(), "e2e", "artifacts", "phaseb");

const REPO_ROOT = path.resolve(process.cwd(), "..");

/** reject_key captured by the reject step — run-2 reads it (serial ordering). */
const rejectedKeyByCase = new Map<string, string>();

function rotateArtifactOnce(): void {
  if (process.env.PHASEB_JSONL_APPEND === "1") return;
  try {
    if (fs.existsSync(OUTPUT_JSONL) && fs.statSync(OUTPUT_JSONL).size > 0) {
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      fs.renameSync(OUTPUT_JSONL, `${OUTPUT_JSONL}.${stamp}.bak`);
    }
  } catch {
    // best-effort
  }
}
rotateArtifactOnce();

function appendCapture(row: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(OUTPUT_JSONL), { recursive: true });
  fs.appendFileSync(OUTPUT_JSONL, `${JSON.stringify(row)}\n`, "utf8");
}

function screenshotRelPath(absPath: string): string {
  const resolved = path.resolve(absPath);
  if (resolved.startsWith(`${REPO_ROOT}${path.sep}`)) {
    return path.relative(REPO_ROOT, resolved);
  }
  return resolved;
}

async function seedMemoriesViaCrud(
  page: import("@playwright/test").Page,
  seeds: SeedMemory[],
): Promise<void> {
  for (const m of seeds) {
    const res = await page.request.post("/api/memory", {
      data: {
        content: m.text,
        type: m.type,
        key: m.key,
        salience: m.salience ?? null,
      },
    });
    if (!res.ok()) {
      throw new Error(`crud-seed failed (${res.status()}) for key=${m.key}`);
    }
  }
}

async function cleanupSeededMemories(
  page: import("@playwright/test").Page,
  caseRow: PhasebRejectCase,
): Promise<void> {
  for (const m of caseRow.seed_memory) {
    await page.request
      .delete(`/api/memory/${encodeURIComponent(m.key)}`)
      .catch(() => {});
  }
}

async function newThreadIfAvailable(
  page: import("@playwright/test").Page,
): Promise<void> {
  const btn = page.locator(
    "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
  );
  if ((await btn.count()) > 0) {
    await btn.first().click();
  }
}

async function readRecalledRowKeys(
  page: import("@playwright/test").Page,
): Promise<string[]> {
  const rows = page.locator("[data-testid^='recalled-memory-']");
  const count = await rows.count();
  const keys: string[] = [];
  for (let i = 0; i < count; i++) {
    const testId = (await rows.nth(i).getAttribute("data-testid")) ?? "";
    const m = testId.match(/^recalled-memory-(.+)$/);
    if (m?.[1]) keys.push(m[1]!);
  }
  return keys;
}

/** Backend-minted trace_id shown in eval mode (F-R7 — never client-generated). */
async function readTraceIdFromChip(
  page: import("@playwright/test").Page,
): Promise<string> {
  const chip = page.getByTestId("trace-chip");
  await expect(chip).toBeVisible({ timeout: 30_000 });
  const text = (await chip.textContent()) ?? "";
  const m = text.match(/([a-f0-9]{32})/i);
  if (!m?.[1]) {
    throw new Error(`trace-chip missing trace id: ${text}`);
  }
  return m[1];
}

async function captureDisclosure(
  page: import("@playwright/test").Page,
  shotId: string,
): Promise<string> {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  const disclosure = page.getByTestId("recalled-memories");
  const disclosurePath = path.join(ARTIFACT_DIR, `${shotId}-disclosure.png`);
  if ((await disclosure.count()) > 0) {
    await disclosure.first().screenshot({ path: disclosurePath });
  }
  const fullPath = path.join(ARTIFACT_DIR, `${shotId}-full.png`);
  await page.screenshot({ path: fullPath, fullPage: true });
  await test.info().attach(`${shotId}-full.png`, {
    path: fullPath,
    contentType: "image/png",
  });
  return screenshotRelPath(fullPath);
}

async function runProbeTurn(
  page: import("@playwright/test").Page,
  caseRow: PhasebRejectCase,
  opts?: { minRecalledRows?: number },
): Promise<{ traceId: string; responseText: string; recalledRowKeys: string[] }> {
  const minRows = opts?.minRecalledRows ?? caseRow.expect_min_recall_run1;
  await page.unroute("**/api/run/stream").catch(() => {});
  await page.goto(`/?eval=${encodeURIComponent(caseRow.case)}`);
  await newThreadIfAvailable(page);
  await sendMessage(page, caseRow.query);
  const response = await waitForResponse(page, { timeoutMs: 150_000 });
  await page
    .locator("[data-state='complete']")
    .first()
    .waitFor({ state: "visible", timeout: 150_000 });
  await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
  const responseText = (await response.textContent()) ?? "";
  await expect
    .poll(async () => (await readRecalledRowKeys(page)).length, {
      timeout: 30_000,
    })
    .toBeGreaterThanOrEqual(minRows);
  const recalledRowKeys = await readRecalledRowKeys(page);
  const traceId = await readTraceIdFromChip(page);
  return { traceId, responseText, recalledRowKeys };
}

test.describe("Phase B recall→reject (L4: real stack, MEMORY_ENABLED)", () => {
  test.describe.configure({ tag: "@t3" });

  test.skip(
    process.env.MOCK_MIDDLEWARE === "1",
    "Requires real backend — unset MOCK_MIDDLEWARE.",
  );
  test.skip(CASES.length === 0, "No cases — check PHASEB_CASE_FILTER.");

  for (const caseRow of CASES) {
    test.describe.serial(`${caseRow.case}`, () => {
      test.beforeAll(async ({ browser }) => {
        const storageState = path.isAbsolute(STORAGE_STATE_PATH)
          ? STORAGE_STATE_PATH
          : path.join(process.cwd(), STORAGE_STATE_PATH);
        const ctx =
          process.env.E2E_AUTHENTICATED === "1" && fs.existsSync(storageState)
            ? await browser.newContext({ storageState })
            : await browser.newContext();
        const page = await ctx.newPage();
        await page.goto("/");
        await waitForComposerReady(page, { timeoutMs: 60_000 }).catch(() => {});
        if ((await composer(page).count()) === 0) {
          await ctx.close();
          test.skip(true, "Chat shell not rendered — auth required.");
        }
        await seedMemoriesViaCrud(page, caseRow.seed_memory);
        await ctx.close();
      });

      test.afterAll(async ({ browser }) => {
        const storageState = path.isAbsolute(STORAGE_STATE_PATH)
          ? STORAGE_STATE_PATH
          : path.join(process.cwd(), STORAGE_STATE_PATH);
        if (!fs.existsSync(storageState)) return;
        const ctx = await browser.newContext({ storageState });
        const page = await ctx.newPage();
        await cleanupSeededMemories(page, caseRow);
        await ctx.close();
      });

      test(`run-1 recall + disclosure`, async ({ authenticatedPage: page }) => {
        test.setTimeout(240_000);
        const { traceId, responseText, recalledRowKeys } = await runProbeTurn(
          page,
          caseRow,
        );
        expect(responseText.length).toBeGreaterThan(0);
        expect(recalledRowKeys.length).toBeGreaterThanOrEqual(
          caseRow.expect_min_recall_run1,
        );
        const screenshotPath = await captureDisclosure(page, `${caseRow.case}-run1`);
        appendCapture({
          case: caseRow.case,
          mem_id: caseRow.mem_id,
          run: 1,
          trace_id: traceId,
          session_id: `session-${caseRow.mem_id.toLowerCase()}-s1`,
          user_id: caseRow.user_id,
          query: caseRow.query,
          reject_key: null,
          recalled_row_keys: recalledRowKeys,
          seed_snippets: caseRow.seed_snippets,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      });

      test(`reject soft-suppresses one recalled key`, async ({
        authenticatedPage: page,
      }) => {
        test.setTimeout(240_000);
        const { traceId, recalledRowKeys } = await runProbeTurn(page, caseRow);
        expect(recalledRowKeys.length).toBeGreaterThan(0);
        const rejectKey = recalledRowKeys[0]!;
        const patchDone = page.waitForResponse(
          (res) =>
            res.request().method() === "PATCH" &&
            res.url().includes(`/api/memory/${encodeURIComponent(rejectKey)}`),
        );
        await page.getByTestId(`reject-memory-${rejectKey}`).click();
        await patchDone;
        await expect(page.getByTestId(`recalled-memory-${rejectKey}`)).toBeHidden({
          timeout: 15_000,
        });
        rejectedKeyByCase.set(caseRow.case, rejectKey);
        const screenshotPath = await captureDisclosure(
          page,
          `${caseRow.case}-post-reject`,
        );
        appendCapture({
          case: caseRow.case,
          mem_id: caseRow.mem_id,
          run: "reject",
          trace_id: traceId,
          session_id: `session-${caseRow.mem_id.toLowerCase()}-s1`,
          user_id: caseRow.user_id,
          query: caseRow.query,
          reject_key: rejectKey,
          recalled_row_keys: recalledRowKeys.filter((k) => k !== rejectKey),
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      });

      test(`run-2 excludes rejected key from disclosure`, async ({
        authenticatedPage: page,
      }) => {
        test.setTimeout(240_000);
        const rejectKey = rejectedKeyByCase.get(caseRow.case);
        expect(rejectKey, "reject step must run first (serial)").toBeTruthy();

        const run2 = await runProbeTurn(page, caseRow, { minRecalledRows: 0 });
        expect(run2.responseText.length).toBeGreaterThan(0);
        expect(run2.recalledRowKeys).not.toContain(rejectKey);
        const screenshotPath = await captureDisclosure(page, `${caseRow.case}-run2`);
        appendCapture({
          case: caseRow.case,
          mem_id: caseRow.mem_id,
          run: 2,
          trace_id: run2.traceId,
          session_id: `session-${caseRow.mem_id.toLowerCase()}-s2`,
          user_id: caseRow.user_id,
          query: caseRow.query,
          reject_key: rejectKey,
          recalled_row_keys: run2.recalledRowKeys,
          screenshot_path: screenshotPath,
          outcome: "pass",
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "http://localhost:3000",
        });
      });
    });
  }
});
