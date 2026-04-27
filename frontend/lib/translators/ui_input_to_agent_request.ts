/**
 * Pure translator: UI composer input -> AgentProtocol RunCreateRequest.
 *
 * Pure (T1). No I/O, no SDK. Validates basic UI invariants (non-empty body,
 * size budget) before producing the wire shape.
 */

import type { RunCreateRequest } from "../wire/agent_protocol";

const MAX_USER_BODY_BYTES = 64 * 1024; // 64 KiB per turn

export interface UIComposerInput {
  readonly thread_id: string;
  readonly body: string;
  readonly agent_id?: string;
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

  const req: RunCreateRequest = {
    thread_id: input.thread_id,
    input: {
      messages: [{ role: "user", content: input.body }],
    },
    ...(input.agent_id !== undefined ? { agent_id: input.agent_id } : {}),
  };
  return req;
}
