/**
 * B0-4 / FR-P2-5 — per-form key posture. Code switch, not env-overridable.
 * asset-served → server; client-bundled (Test-01 exemption) → client.
 */

import { describe, expect, it } from "vitest";
import {
  EXAM_KEY_POSTURE,
  examKeyPosture,
} from "./exam_key_posture";

describe("examKeyPosture (B0-4 / FR-P2-5)", () => {
  it("returns server for asset-served forms", () => {
    expect(examKeyPosture("asset-served")).toBe("server");
  });

  it("returns client for client-bundled forms (Test-01 exemption)", () => {
    expect(examKeyPosture("client-bundled")).toBe("client");
  });

  it("keeps the phase-1 global switch as client (not env-overridable)", () => {
    expect(EXAM_KEY_POSTURE).toBe("client");
  });
});

describe("S-I4 per-form posture with PT2 registered (FR-P2-5)", () => {
  it("is server for PT2 and client for Test-01", async () => {
    const { getExamFormDelivery } = await import(
      "@/lib/adapters/engine/exam_forms"
    );
    expect(examKeyPosture(getExamFormDelivery("act-practice-test-2"))).toBe(
      "server",
    );
    expect(examKeyPosture(getExamFormDelivery("test01-english"))).toBe("client");
  });
});
