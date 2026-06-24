/**
 * use_available_models.test.ts — fetch + fail-safe contract for the model
 * picker's catalog hook.
 *
 * Failure paths first (TAP-4): a fetch error / non-OK / malformed body must
 * fall back to Auto-only (empty list) and never throw — the picker must never
 * block composing.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { useAvailableModels, type AvailableModels } from "./use_available_models";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let container: HTMLDivElement;
let root: Root;
let latest: AvailableModels;

function Probe(): null {
  latest = useAvailableModels();
  return null;
}

async function mount(): Promise<void> {
  await act(async () => {
    root.render(React.createElement(Probe));
  });
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

describe("useAvailableModels [fail-safe]", () => {
  it("falls back to Auto-only when fetch rejects (never throws)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    await mount();
    expect(latest.loading).toBe(false);
    expect(latest.models).toEqual([]);
    expect(latest.defaultModel).toBe("");
  });

  it("falls back to Auto-only on a non-OK response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 503 })),
    );
    await mount();
    expect(latest.models).toEqual([]);
    expect(latest.loading).toBe(false);
  });

  it("falls back to Auto-only on a malformed body (shape guard)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ nope: true }), { status: 200 }),
      ),
    );
    await mount();
    expect(latest.models).toEqual([]);
  });

  it("loads the registry catalog on the happy path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              default: "claude-haiku-4-5",
              models: [
                { name: "claude-haiku-4-5", tier: "fast" },
                { name: "claude-sonnet-4-6", tier: "capable" },
              ],
            }),
            { status: 200 },
          ),
      ),
    );
    await mount();
    expect(latest.loading).toBe(false);
    expect(latest.defaultModel).toBe("claude-haiku-4-5");
    expect(latest.models.map((m) => m.name)).toEqual([
      "claude-haiku-4-5",
      "claude-sonnet-4-6",
    ]);
  });
});
