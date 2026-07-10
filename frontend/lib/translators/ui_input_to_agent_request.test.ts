/**
 * L1 tests for the UI input -> AgentProtocol RunCreateRequest translator.
 *
 * Failure paths first.
 */

import { describe, expect, it } from "vitest";
import { AUTO_MODEL, uiInputToAgentRequest } from "./ui_input_to_agent_request";

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

  // ── Model pin (Task #3) ──────────────────────────────────────────────
  it("omits pinned_model when no model is selected (Auto is the default)", () => {
    const req = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    expect(req.input).not.toHaveProperty("pinned_model");
  });

  it("omits pinned_model when the choice is the Auto sentinel", () => {
    const req = uiInputToAgentRequest({
      thread_id: "t1",
      body: "hi",
      selectedModel: AUTO_MODEL,
    });
    expect(req.input).not.toHaveProperty("pinned_model");
  });

  it("rides a concrete pin inside input.pinned_model (not a top-level field)", () => {
    const req = uiInputToAgentRequest({
      thread_id: "t1",
      body: "hi",
      selectedModel: "claude-sonnet-4-6",
    });
    expect(req.input).toMatchObject({
      messages: [{ role: "user", content: "hi" }],
      pinned_model: "claude-sonnet-4-6",
    });
    // strict top-level: the pin must NOT leak to the root request object
    expect(req).not.toHaveProperty("pinned_model");
    expect(req).not.toHaveProperty("selected_model");
  });

  it("Auto choice is byte-identical to the no-pin path", () => {
    const auto = uiInputToAgentRequest({
      thread_id: "t1",
      body: "hi",
      selectedModel: AUTO_MODEL,
    });
    const none = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    expect(auto).toEqual(none);
  });

  // ── Coach context (BP-3a / FR-9, FR-10) ───────────────────────────────
  it("omits coach_context when not provided (messages-only)", () => {
    const req = uiInputToAgentRequest({ thread_id: "t1", body: "hi" });
    expect(req.input).not.toHaveProperty("coach_context");
  });

  it("omits coach_context when explicitly null", () => {
    const req = uiInputToAgentRequest({
      thread_id: "t1",
      body: "hi",
      coach_context: null,
    });
    expect(req.input).not.toHaveProperty("coach_context");
  });

  it("rides coach_context inside input when assembled", () => {
    const coach_context = {
      mode: "post_feedback" as const,
      question_id: "q1",
      skill_id: "s-punc",
      question: { id: "q1" } as never,
      misses_aggregate: { skill_id: "s-punc", missed: 2 },
    };
    const req = uiInputToAgentRequest({
      thread_id: "t1",
      body: "why B?",
      coach_context,
    });
    expect(req.input).toMatchObject({
      messages: [{ role: "user", content: "why B?" }],
      coach_context,
    });
    expect(
      (req.input as { coach_context: { misses_aggregate: object } })
        .coach_context.misses_aggregate,
    ).not.toHaveProperty("window");
  });
});
