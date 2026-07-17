import { afterEach, describe, expect, it, vi } from "vitest";
import { newUuid } from "./new_uuid";

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("newUuid", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prefers crypto.randomUUID when present", () => {
    const randomUUID = vi.fn(() => "11111111-2222-4333-8444-555555555555");
    vi.stubGlobal("crypto", { randomUUID, getRandomValues: vi.fn() });
    expect(newUuid()).toBe("11111111-2222-4333-8444-555555555555");
    expect(randomUUID).toHaveBeenCalledOnce();
  });

  it("falls back to getRandomValues when randomUUID is missing (LAN HTTP / Safari)", () => {
    const getRandomValues = vi.fn((buf: Uint8Array) => {
      for (let i = 0; i < buf.length; i++) buf[i] = i;
      return buf;
    });
    vi.stubGlobal("crypto", { getRandomValues });
    const id = newUuid();
    expect(id).toMatch(UUID_V4);
    expect(getRandomValues).toHaveBeenCalledOnce();
  });

  it("returns a UUID v4 shape on the real crypto", () => {
    expect(newUuid()).toMatch(UUID_V4);
  });
});
