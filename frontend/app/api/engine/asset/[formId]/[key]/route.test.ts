/**
 * B-6 — GET /api/engine/asset/<formId>/<key> (FR-P2-15 / FR-P2-13).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);

const { getAuthSession, getImage } = vi.hoisted(() => ({
  getAuthSession: vi.fn(),
  getImage: vi.fn(),
}));

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession: getAuthSession },
  }),
  enginePorts: () => ({
    formAssetStore: { getImage, has: vi.fn() },
  }),
}));

import { assetRefToUrl } from "@/components/exam/exam_item_vm";
import { GET } from "./route";

function req(formId: string, key: string): NextRequest {
  return new NextRequest(
    `http://localhost/api/engine/asset/${formId}/${key}`,
    { method: "GET" },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GET /api/engine/asset/[formId]/[key] (B-6 / FR-P2-15)", () => {
  it("401 when unauthenticated", async () => {
    getAuthSession.mockResolvedValue(null);
    const res = await GET(req("fake-official-form", "q-2.png"), {
      params: Promise.resolve({ formId: "fake-official-form", key: "q-2.png" }),
    });
    expect(res.status).toBe(401);
    expect(getImage).not.toHaveBeenCalled();
  });

  it("404 when the asset is missing", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    getImage.mockResolvedValue(null);
    const res = await GET(req("fake-official-form", "missing.png"), {
      params: Promise.resolve({
        formId: "fake-official-form",
        key: "missing.png",
      }),
    });
    expect(res.status).toBe(404);
    expect(getImage).toHaveBeenCalledWith({
      store: "form-image",
      form_id: "fake-official-form",
      key: "missing.png",
    });
  });

  it("streams bytes with private cache headers", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    getImage.mockResolvedValue(PNG);
    const res = await GET(req("fake-official-form", "q-2.png"), {
      params: Promise.resolve({ formId: "fake-official-form", key: "q-2.png" }),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/png");
    expect(res.headers.get("cache-control")).toBe("private");
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(PNG);
  });

  it("VM-built slashy key decodes to the store key and 200s (CV4-2 / FR-P2-15)", async () => {
    getAuthSession.mockResolvedValue({ sub: "learner-A" });
    getImage.mockResolvedValue(PNG);
    const storeKey = "questions/math-q02.png";
    const url = assetRefToUrl({
      store: "form-image",
      form_id: "act-practice-test-2",
      key: storeKey,
    });
    const keySegment = url.split("/").pop()!;
    expect(keySegment).toBe(encodeURIComponent(storeKey));
    expect(keySegment).not.toContain("/");
    const res = await GET(req("act-practice-test-2", keySegment), {
      params: Promise.resolve({
        formId: "act-practice-test-2",
        key: keySegment,
      }),
    });
    expect(res.status).toBe(200);
    expect(getImage).toHaveBeenCalledWith({
      store: "form-image",
      form_id: "act-practice-test-2",
      key: storeKey,
    });
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(PNG);
  });
});
