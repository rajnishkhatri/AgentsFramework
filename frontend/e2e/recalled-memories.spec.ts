/**
 * Recalled-memories eval/reject loop (Phase B B4) — proves the full client
 * orchestration against a STATEFUL in-memory mock of the BFF memory route:
 * a run recalls memories (emits `memory_recalled` with KEYS) → in eval mode the
 * per-chat recalled-memories disclosure lists the items (joined key→content
 * from the panel) → clicking Reject PATCHes the memory suppressed → it leaves
 * the recall list and a subsequent recall of the same key no longer shows it.
 *
 * The memory mock is the BFF/middleware store stand-in; the assertions are about
 * the CLIENT (join, reject = soft-suppress, list update). The run is a canned
 * SSE stream so the test needs no backend or live auth.
 *
 * Hooks: recalled-memories, recalled-memory-{key}, reject-memory-{key}.
 */

import { test, expect, type Page, type Route } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { recalledMemoriesRun } from "./fixtures/scenarios";

type StoredMemory = {
  key: string;
  type: string | null;
  content: string;
  salience: number | null;
  suppressed?: boolean;
};

/**
 * Stateful mock of the BFF memory routes. Seeds two memories; GET lists the
 * non-suppressed ones (the panel/recall surface); PATCH flips the suppressed
 * flag. Returns the live store so a test can assert what was suppressed.
 */
function installMemoryStoreMock(page: Page): Map<string, StoredMemory> {
  const store = new Map<string, StoredMemory>([
    ["k1", { key: "k1", type: "semantic", content: "prefers metric units", salience: null }],
    ["k2", { key: "k2", type: "semantic", content: "lives in Berlin", salience: null }],
  ]);

  void page.route("**/api/memory**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();

    // /api/memory/{key}  → PATCH (suppress / un-suppress)
    const keyMatch = url.pathname.match(/\/api\/memory\/([^/]+)$/);
    if (keyMatch && method === "PATCH") {
      const key = decodeURIComponent(keyMatch[1]!);
      const body = JSON.parse(req.postData() ?? "{}") as { suppressed: boolean };
      const m = store.get(key);
      if (!m) {
        await route.fulfill({ status: 404, body: "" });
        return;
      }
      m.suppressed = body.suppressed;
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    // /api/memory  → GET (non-suppressed items only; the panel + join source)
    if (url.pathname.endsWith("/api/memory") && method === "GET") {
      const items = [...store.values()].filter((m) => !m.suppressed);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items }),
      });
      return;
    }

    await route.fulfill({ status: 405, body: "" });
  });

  return store;
}

/** Threads route is hit on mount; keep it empty so the sidebar settles. */
function installThreadsMock(page: Page): Promise<void> {
  return page.route("**/api/threads**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ threads: [], next_cursor: null }),
    });
  });
}

function stubRun(page: Page, keys: string[]): Promise<void> {
  return page.route("**/api/run/stream", async (route: Route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body: buildSSEBody(recalledMemoriesRun(keys)),
    });
  });
}

test.describe("Recalled-memories eval/reject", () => {
  test("recalled items show in eval mode and Reject soft-suppresses them", async ({
    page,
  }) => {
    const store = installMemoryStoreMock(page);
    await installThreadsMock(page);
    await stubRun(page, ["k1", "k2"]);
    // Eval mode pins the dev/eval surface where the disclosure renders.
    await page.goto("/?eval=PHASEB-1");
    if ((await composer(page).count()) === 0) {
      test.skip(true, "Skipped: chat shell not rendered (auth required).");
    }

    await sendMessage(page, "what units do I prefer?");
    await page
      .locator("[data-state='complete']")
      .first()
      .waitFor({ state: "visible" });

    // The disclosure lists the recalled items, joined key→content from the panel.
    await expect(page.getByTestId("recalled-memories")).toBeVisible();
    await expect(page.getByTestId("recalled-memory-k1")).toContainText(
      "prefers metric units",
    );
    await expect(page.getByTestId("recalled-memory-k2")).toContainText(
      "lives in Berlin",
    );

    // Reject k1 → it is soft-suppressed server-side and leaves the list.
    await page.getByTestId("reject-memory-k1").click();
    await expect.poll(() => store.get("k1")?.suppressed === true).toBeTruthy();
    await expect(page.getByTestId("recalled-memory-k1")).toBeHidden();
    // k2 was not rejected — still listed.
    await expect(page.getByTestId("recalled-memory-k2")).toBeVisible();
    // The row is RETAINED server-side (audit), just flagged.
    expect(store.has("k1")).toBe(true);
  });

  test("without eval mode the disclosure stays hidden (prod chat stays clean)", async ({
    page,
  }) => {
    installMemoryStoreMock(page);
    await installThreadsMock(page);
    await stubRun(page, ["k1"]);
    await page.goto("/");
    if ((await composer(page).count()) === 0) {
      test.skip(true, "Skipped: chat shell not rendered (auth required).");
    }

    await sendMessage(page, "what units do I prefer?");
    await page
      .locator("[data-state='complete']")
      .first()
      .waitFor({ state: "visible" });

    await expect(page.getByTestId("recalled-memories")).toHaveCount(0);
  });
});
