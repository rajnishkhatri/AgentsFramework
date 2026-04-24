/**
 * L2 tests for CopilotKitRegistryAdapter (S3.3.4 partial).
 *
 * The registry is a sync map keyed on tool name with `*` as the wildcard
 * fallback. Tests verify the resolver contract.
 */

import { describe, expect, it } from "vitest";
import { CopilotKitRegistryAdapter } from "./copilotkit_registry_adapter";

const fixtureReq = {
  trace_id: "trace-001",
  tool_call_id: "tc1",
  tool_name: "shell",
  input: {},
  status: "running" as const,
  output: null,
};

describe("CopilotKitRegistryAdapter", () => {
  it("resolves the wildcard fallback when no specific renderer is registered", () => {
    const reg = new CopilotKitRegistryAdapter();
    reg.register("*", () => "fallback");
    expect(reg.resolve("unknown")(fixtureReq)).toBe("fallback");
  });

  it("specific renderer wins over wildcard", () => {
    const reg = new CopilotKitRegistryAdapter();
    reg.register("*", () => "fallback");
    reg.register("shell", () => "shell-card");
    expect(reg.resolve("shell")(fixtureReq)).toBe("shell-card");
  });

  it("re-registering the same name overwrites (idempotent)", () => {
    const reg = new CopilotKitRegistryAdapter();
    reg.register("shell", () => "v1");
    reg.register("shell", () => "v2");
    expect(reg.resolve("shell")(fixtureReq)).toBe("v2");
  });

  it("never throws on resolve when no renderers are registered", () => {
    const reg = new CopilotKitRegistryAdapter();
    const r = reg.resolve("anything");
    expect(typeof r).toBe("function");
    expect(r(fixtureReq)).toBeUndefined();
  });
});
