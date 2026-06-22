/**
 * Isolated validation of MEM-BUDGET-overflow-evicts-low-01.
 *
 * The shared MEM_SMOKE rerun showed namespace bleed (the answer carried email,
 * Pacific timezone, metric units, and teal — none of which are this case's
 * seeds, and missed Go/Seattle/tabs/espresso/standing-desk which ARE). Cause:
 * crud-seed cases run under identity.owner (the real WorkOS user) and the
 * owner accumulates memories from prior sessions; the spec's per-case cleanup
 * only deletes the keys IT seeded.
 *
 * This spec wipes ALL of the owner's memories before the case runs, seeds the
 * 6 BUDGET-01 facts, fires the probe, and asserts on content semantically:
 *   - high-salience surviving facts MUST appear
 *   - the lowest-salience fact ("teal") MUST be absent (eviction signal)
 *   - cross-case bleed tokens (email/Pacific/metric) MUST be absent
 *
 * NOTE: the deployed backend on rev agent-backend-combined-00094-rfq has
 *       MEMORY_BUDGET_SEMANTIC unset → default 50 (middleware/composition.py:500),
 *       not 5. The eviction trigger ("6 > 5 → evict lowest-salience") is
 *       structurally unreachable in prod. A passing assertion here therefore
 *       depends on something OTHER than budget consolidation — recall top-k +
 *       relevance scoring + LLM answer shape — and a teal-present result is
 *       expected, not a regression of the eviction code path.
 *
 * Drive only:  TEST_PROFILE=prod E2E_AUTHENTICATED=1 \
 *              pnpm exec playwright test frontend/e2e/full-stack/memory-budget-isolated.spec.ts
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect, STORAGE_STATE_PATH } from "../fixtures/auth.fixture";
import {
  sendMessage,
  waitForResponse,
  waitForComposerReady,
} from "../fixtures/helpers";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const OUTPUT_DIR = path.join(REPO_ROOT, "cache", "memory_multisession");
const SCREENSHOT_DIR = path.join(OUTPUT_DIR, "screenshots_budget_isolated");
const RESULT_JSONL = path.join(OUTPUT_DIR, "budget_isolated.jsonl");

const SEEDS: ReadonlyArray<{
  key: string;
  text: string;
  type: "semantic";
  salience: number;
}> = [
  { key: "f1", text: "Primary language is Go.", type: "semantic", salience: 0.95 },
  { key: "f2", text: "Lives in Seattle.", type: "semantic", salience: 0.9 },
  { key: "f3", text: "Prefers tabs over spaces.", type: "semantic", salience: 0.85 },
  { key: "f4", text: "Drinks espresso.", type: "semantic", salience: 0.8 },
  { key: "f5", text: "Has a standing desk.", type: "semantic", salience: 0.75 },
  { key: "f6", text: "Once mentioned liking the color teal.", type: "semantic", salience: 0.1 },
];

const PROBE_PROMPT = "What are the most important things you know about me?";

// High-salience facts that MUST surface in the answer (any one is acceptable
// as recall evidence; we assert at least one of the top three appears).
const SURVIVOR_TOKENS = ["Go", "Seattle", "tabs"];

// The lowest-salience fact: if eviction worked, this must be absent.
const EVICTED_TOKEN = "teal";

// Cross-case bleed signals from prior MEM_SMOKE owner-namespace pollution.
// If the owner-wipe worked, none of these unrelated facts should appear.
const BLEED_TOKENS = ["email", "Pacific", "metric", "phone"];

async function listAllMemoryKeys(
  page: import("@playwright/test").Page,
): Promise<string[]> {
  const res = await page.request.get("/api/memory");
  if (!res.ok()) {
    throw new Error(`/api/memory list failed (${res.status()})`);
  }
  const body = (await res.json()) as { items?: { key: string }[] };
  return (body.items ?? []).map((i) => i.key);
}

async function wipeOwnerMemories(
  page: import("@playwright/test").Page,
): Promise<{ wiped: number; remaining: number }> {
  const keys = await listAllMemoryKeys(page);
  let wiped = 0;
  for (const key of keys) {
    const res = await page.request.delete(
      `/api/memory/${encodeURIComponent(key)}`,
    );
    if (res.status() === 204 || res.status() === 200) wiped += 1;
  }
  const remaining = (await listAllMemoryKeys(page)).length;
  return { wiped, remaining };
}

async function seedFacts(
  page: import("@playwright/test").Page,
): Promise<void> {
  for (const m of SEEDS) {
    const res = await page.request.post("/api/memory", {
      data: {
        content: m.text,
        type: m.type,
        key: m.key,
        salience: m.salience,
      },
    });
    if (!res.ok()) {
      throw new Error(`seed failed (${res.status()}) for key=${m.key}`);
    }
  }
}

async function readRecalledCount(
  page: import("@playwright/test").Page,
): Promise<number | null> {
  const el = page.locator("[data-testid='recall-indicator']");
  if ((await el.count()) === 0) return 0;
  const text = (await el.first().textContent()) ?? "";
  const m = text.match(/(\d+)\s+memor/i);
  return m ? Number(m[1]) : null;
}

function freshTraceId(): string {
  const g = (globalThis as { crypto?: Crypto }).crypto;
  if (g?.getRandomValues) {
    const buf = new Uint8Array(16);
    g.getRandomValues(buf);
    return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  let s = "";
  while (s.length < 32) s += Math.floor(Math.random() * 16).toString(16);
  return s.slice(0, 32);
}

test.describe.serial(
  "MEM-BUDGET-overflow-evicts-low-01 (isolated, owner-namespace wiped)",
  () => {
    test.skip(
      process.env.MOCK_MIDDLEWARE === "1",
      "Requires real backend — unset MOCK_MIDDLEWARE.",
    );

    test("seeds 6 facts under a clean owner namespace and probes for eviction signal", async ({
      authenticatedPage: page,
    }) => {
      test.setTimeout(240_000);
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
      const traceId = freshTraceId();

      // ── Phase 1: wipe ANY prior owner memories so this case is alone. ──
      const before = await wipeOwnerMemories(page);
      expect(
        before.remaining,
        `owner namespace should be empty after wipe (had ${before.remaining})`,
      ).toBe(0);

      // ── Phase 2: seed the 6 BUDGET-01 facts. ──────────────────────────
      await seedFacts(page);
      const afterSeed = await listAllMemoryKeys(page);
      expect(afterSeed.length).toBe(SEEDS.length);

      // ── Phase 3: drive a probe turn (fresh thread). ───────────────────
      await page.goto("/");
      const newBtn = page.locator(
        "[data-testid='new-thread'], button:has-text('New chat'), button:has-text('New')",
      );
      if ((await newBtn.count()) > 0) await newBtn.first().click();

      await sendMessage(page, PROBE_PROMPT);
      const response = await waitForResponse(page, { timeoutMs: 150_000 });
      await waitForComposerReady(page, { timeoutMs: 5_000 }).catch(() => {});
      const responseText = (await response.textContent()) ?? "";
      const recalledCountDom = await readRecalledCount(page);

      // Screenshot for the verdict artifact.
      const shotPath = path.join(
        SCREENSHOT_DIR,
        `MEM-BUDGET-overflow-evicts-low-01-s1.png`,
      );
      const buf = await page.screenshot({ fullPage: true });
      fs.writeFileSync(shotPath, buf);
      await test
        .info()
        .attach("MEM-BUDGET-overflow-evicts-low-01-s1.png", {
          body: buf,
          contentType: "image/png",
        });

      // Persist the row for post-hoc analysis even if assertions fail below.
      fs.appendFileSync(
        RESULT_JSONL,
        JSON.stringify({
          case: "MEM-BUDGET-overflow-evicts-low-01",
          variant: "isolated_owner_wiped",
          probe_trace_id: traceId,
          prompt: PROBE_PROMPT,
          response_text: responseText.slice(0, 4000),
          response_chars: responseText.length,
          recalled_count_dom: recalledCountDom,
          seeds: SEEDS.map((s) => s.key),
          owner_wipe: before,
          seeded_keys: afterSeed,
          screenshot_path: path.relative(REPO_ROOT, shotPath),
          finished_at: new Date().toISOString(),
          base_url: process.env.BASE_URL ?? "",
        }) + "\n",
      );

      // ── Phase 4: semantic assertions. ─────────────────────────────────
      expect(responseText.length).toBeGreaterThan(0);

      // (a) cross-case bleed MUST be gone after the owner wipe.
      const bleedHits = BLEED_TOKENS.filter((t) =>
        responseText.toLowerCase().includes(t.toLowerCase()),
      );
      expect(
        bleedHits,
        `cross-case bleed tokens leaked despite owner wipe: ${bleedHits.join(", ")} — see ${path.relative(REPO_ROOT, shotPath)}`,
      ).toEqual([]);

      // (b) at least ONE high-salience BUDGET seed must surface (recall
      //     evidence — proves the case's own seeds reached the model).
      const survivorHits = SURVIVOR_TOKENS.filter((t) =>
        responseText.includes(t),
      );
      expect(
        survivorHits.length,
        `no high-salience BUDGET fact surfaced (expected any of ${SURVIVOR_TOKENS.join("/")})`,
      ).toBeGreaterThan(0);

      // (c) the eviction signal: lowest-salience fact MUST be absent.
      //     This will FAIL on the current prod rev because the default
      //     semantic budget is 50, so 6 facts never trigger consolidation.
      //     The failure is the finding (see docs/analysis/MEM_BUDGET_*).
      expect(
        responseText.toLowerCase().includes(EVICTED_TOKEN.toLowerCase()),
        `lowest-salience fact "${EVICTED_TOKEN}" survived — eviction did not fire (likely budget=50 in prod, not 5)`,
      ).toBe(false);
    });

    test.afterAll(async ({ browser }) => {
      // Best-effort teardown: list-then-delete (NOT by client key — the BFF
      // adapter HttpMemoryStore.add hardcodes key:null, so the backend rewrote
      // every seed key to a UUID. Deleting by client-side f1..f6 is a no-op).
      const storageStatePath = path.isAbsolute(STORAGE_STATE_PATH)
        ? STORAGE_STATE_PATH
        : path.join(process.cwd(), STORAGE_STATE_PATH);
      if (!fs.existsSync(storageStatePath)) return;
      const ctx = await browser.newContext({ storageState: storageStatePath });
      const page = await ctx.newPage();
      try {
        const keys = await listAllMemoryKeys(page);
        for (const k of keys) {
          await page.request
            .delete(`/api/memory/${encodeURIComponent(k)}`)
            .catch(() => {});
        }
      } catch {
        // teardown is best-effort
      }
      await ctx.close();
    });
  },
);
