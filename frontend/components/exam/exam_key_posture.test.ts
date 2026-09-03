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
