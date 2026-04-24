/**
 * L1 tests for the UI input -> AgentProtocol RunCreateRequest translator.
 *
 * Failure paths first.
 */

import { describe, expect, it } from "vitest";
import { uiInputToAgentRequest } from "./ui_input_to_agent_request";

describe("uiInputToAgentRequest [T1 pure / T3 zero-or-many]", () => {
  it("rejects empty thread_id", () => {
    expect(() =>
      uiInputToAgentRequest({ thread_id: "", body: "hi" }),
    ).toThrowError(/thread_id/);
  });

  it("rejects empty body (no zero-length user messages)", () => {
    expect(() =>
      uiInputToAgentRequest({ thread_id: "t1", body: "" }),
    ).toThrowError(/body/);
  });

  it("rejects body > 64 KiB (FE budget for a single user turn)", () => {
    const big = "x".repeat(65_537);
    expect(() =>
      uiInputToAgentRequest({ thread_id: "t1", body: big }),
    ).toThrowError(/too large/);
  });

  it("produces a valid RunCreateRequest", () => {
    const req = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    expect(req.thread_id).toBe("t1");
    expect(req.input).toMatchObject({
      messages: [{ role: "user", content: "hi" }],
    });
    expect(req.agent_id).toBeUndefined();
  });

  it("forwards an explicit agent_id when provided", () => {
    const req = uiInputToAgentRequest({
      thread_id: "t1",
      body: "hi",
      agent_id: "agent-001",
    });
    expect(req.agent_id).toBe("agent-001");
  });

  it("is pure: same input always produces deeply-equal output", () => {
    const a = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    const b = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    expect(a).toEqual(b);
  });
});
