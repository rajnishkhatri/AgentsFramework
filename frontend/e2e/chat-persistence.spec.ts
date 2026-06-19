/**
 * Durable chat persistence — full client loop (plan §A4).
 *
 * Proves the "save all chats" wiring end-to-end against a STATEFUL in-memory
 * mock of the BFF thread routes: send a message → the client auto-creates the
 * thread row (POST /api/threads with the agent-minted id) and persists the
 * completed turn (POST /api/threads/{id}/messages) → the thread appears in
 * Recents → a reload resumes the transcript from the durable store.
 *
 * The mock is the BFF's durable store stand-in; the assertions are about the
 * CLIENT orchestration (auto-create, same-id continuity, per-turn persist,
 * resume replay), which is what Phase A adds. The run itself is a canned SSE
 * stream so the test needs no backend or live auth.
 *
 * Hooks: thread-row-{id}, assistant-message, data-state=complete.
 */

import { test, expect, type Page, type Route } from "@playwright/test";
import { sendMessage, composer } from "./fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "./fixtures/sse-mock";
import { plainMarkdown } from "./fixtures/scenarios";

const NOW = new Date().toISOString();

type StoredMessage = { role: string; content: string; turn_id?: string };
type StoredThread = {
  thread_id: string;
  user_id: string;
  title: string;
  messages: StoredMessage[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

/**
 * Install a stateful mock of the BFF thread + memory routes. Returns the live
 * store so a test can assert what was persisted. The route matcher
 * distinguishes the messages-append sub-route from the create/list/get routes.
 */
function installThreadStoreMock(page: Page): Map<string, StoredThread> {
  const store = new Map<string, StoredThread>();

  // Memory list is fetched on mount; keep it empty so the panel settles.
  void page.route("**/api/memory*", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  void page.route("**/api/threads**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();
    // /api/threads/{id}/messages  → append a turn
    const appendMatch = url.pathname.match(/\/api\/threads\/([^/]+)\/messages$/);
    if (appendMatch && method === "POST") {
      const id = decodeURIComponent(appendMatch[1]!);
      const body = JSON.parse(req.postData() ?? "{}") as {
        user: string;
        assistant: string;
        turn_id: string;
      };
      const t = store.get(id);
      if (!t) {
        await route.fulfill({ status: 404, body: "" });
        return;
      }
      if (!t.messages.some((m) => m.turn_id === body.turn_id)) {
        t.messages.push(
          { role: "user", content: body.user, turn_id: body.turn_id },
          { role: "assistant", content: body.assistant, turn_id: body.turn_id },
        );
      }
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    // /api/threads/{id}  → get one
    const getMatch = url.pathname.match(/\/api\/threads\/([^/]+)$/);
    if (getMatch && method === "GET") {
      const id = decodeURIComponent(getMatch[1]!);
      const t = store.get(id);
      await route.fulfill(
        t
          ? { status: 200, contentType: "application/json", body: JSON.stringify(t) }
          : { status: 404, body: "" },
      );
      return;
    }
    // /api/threads  → create
    if (url.pathname.endsWith("/api/threads") && method === "POST") {
      const body = JSON.parse(req.postData() ?? "{}") as {
        user_id: string;
        thread_id?: string;
        metadata?: { first_message?: string };
      };
      const id = body.thread_id ?? `srv-${store.size + 1}`;
      const title = body.metadata?.first_message ?? "New chat";
      const thread: StoredThread = {
        thread_id: id,
        user_id: body.user_id,
        title,
        messages: [],
        created_at: NOW,
        updated_at: NOW,
        archived_at: null,
      };
      store.set(id, thread);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(thread),
      });
      return;
    }
    // /api/threads  → list (newest first)
    if (url.pathname.endsWith("/api/threads") && method === "GET") {
      const threads = [...store.values()]
        .filter((t) => t.archived_at == null)
        .reverse();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ threads, next_cursor: null }),
      });
      return;
    }
    await route.fulfill({ status: 405, body: "" });
  });

  return store;
}

function stubRun(page: Page): Promise<void> {
  return page.route("**/api/run/stream", async (route: Route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body: buildSSEBody(plainMarkdown()),
    });
  });
}

test.describe("Durable chat persistence", () => {
  test("a sent message is auto-created, persisted, and appears in Recents", async ({
    page,
  }) => {
    const store = installThreadStoreMock(page);
    await stubRun(page);
    await page.goto("/");
    if ((await composer(page).count()) === 0) {
      test.skip(true, "Skipped: chat shell not rendered (auth required).");
    }

    await sendMessage(page, "What is the moon?");
    // Wait for the run to complete (terminal state hook).
    await page
      .locator("[data-state='complete']")
      .first()
      .waitFor({ state: "visible" });

    // The client auto-created exactly one thread and persisted the turn.
    await expect.poll(() => store.size).toBe(1);
    const thread = [...store.values()][0]!;
    expect(thread.title).toBe("What is the moon?");
    // The completed turn was persisted (user + assistant message pair).
    await expect.poll(() => thread.messages.length).toBe(2);
    expect(thread.messages[0]).toMatchObject({
      role: "user",
      content: "What is the moon?",
    });
    expect(thread.messages[1]?.role).toBe("assistant");
    expect(thread.messages[1]?.content).toContain("moon");

    // The new chat appears in Recents (reload picks up the durable row).
    await page.reload();
    await expect(
      page.getByTestId(`thread-row-${thread.thread_id}`),
    ).toContainText("What is the moon?");
  });

  test("resuming a saved chat replays its transcript from the durable store", async ({
    page,
  }) => {
    const store = installThreadStoreMock(page);
    await stubRun(page);
    // Seed a saved chat directly in the store (as if persisted earlier).
    store.set("saved-1", {
      thread_id: "saved-1",
      user_id: "u",
      title: "Earlier conversation",
      messages: [
        { role: "user", content: "what units do I prefer?", turn_id: "x" },
        { role: "assistant", content: "You prefer metric units.", turn_id: "x" },
      ],
      created_at: NOW,
      updated_at: NOW,
      archived_at: null,
    });

    await page.goto("/");
    const row = page.getByTestId("thread-row-saved-1");
    if ((await row.count()) === 0) {
      test.skip(true, "Skipped: sidebar not rendered (auth required).");
    }
    await row.click();
    // The transcript replays from the durable store (no checkpointer needed).
    await expect(page.locator("[data-testid='assistant-message']")).toContainText(
      "metric units",
    );
  });
});
