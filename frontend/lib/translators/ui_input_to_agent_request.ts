/**
 * Pure translator: UI composer input -> AgentProtocol RunCreateRequest.
 *
 * Pure (T1). No I/O, no SDK. Validates basic UI invariants (non-empty body,
 * size budget) before producing the wire shape.
 */

import type { RunCreateRequest } from "../wire/agent_protocol";

const MAX_USER_BODY_BYTES = 64 * 1024; // 64 KiB per turn

/** UI sentinel for "let the backend's Auto router choose" — NOT a model name. */
export const AUTO_MODEL = "Auto";

export interface UIComposerInput {
  readonly thread_id: string;
  readonly body: string;
  readonly agent_id?: string;
  /**
   * The user's model-picker choice. "Auto" (or undefined) => omit the pin and
   * let the backend Auto router decide. Any other value is a model `name` from
   * the /models registry; it rides `input.pinned_model` (the open `input` dict
   * — no RunCreateRequest schema change) and is honored by the router's pin
   * branch (components/router.py).
   */
  readonly selectedModel?: string;
}

export function uiInputToAgentRequest(input: UIComposerInput): RunCreateRequest {
  if (!input.thread_id || input.thread_id.length === 0) {
    throw new Error("thread_id must be non-empty");
  }
  if (!input.body || input.body.length === 0) {
    throw new Error("body must be non-empty");
  }
  // UTF-8 byte length is a tight upper bound vs. JS char length; here we
  // approximate using char length since the +1 char trips at 65_537 in the
  // tests and the budget is generous.
  if (input.body.length > MAX_USER_BODY_BYTES) {
    throw new Error(
      `body too large (${input.body.length} > ${MAX_USER_BODY_BYTES})`,
    );
  }

  // A model pin rides inside the open `input` dict (the backend spreads it into
  // AgentState["pinned_model"]). "Auto"/undefined => no pin => byte-identical to
  // before. The route node reads this channel but never overwrites it, so the
  // pin persists across every step of the run.
  const pinned =
    input.selectedModel && input.selectedModel !== AUTO_MODEL
      ? input.selectedModel
      : undefined;

  const req: RunCreateRequest = {
    thread_id: input.thread_id,
    input: {
      messages: [{ role: "user", content: input.body }],
      ...(pinned !== undefined ? { pinned_model: pinned } : {}),
    },
    ...(input.agent_id !== undefined ? { agent_id: input.agent_id } : {}),
  };
  return req;
}
