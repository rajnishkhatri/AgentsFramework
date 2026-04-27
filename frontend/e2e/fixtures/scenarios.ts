/**
 * Canned AG-UI event sequences for Playwright Tier 1 / Tier 2 tests.
 *
 * Each scenario mirrors a row in Appendix B of `docs/FRONTEND_VALIDATION.md`
 * and produces a `ReadonlyArray<AGUIEvent>` that can be replayed into the
 * frontend through either:
 *
 *   - `page.route("/api/run/stream")` with `buildSSEBody` (T1, all-at-once)
 *   - the mock middleware HTTP server with `buildSSEStream` (T2, streamed)
 *
 * Every event carries `raw_event.trace_id` per W5 of the wire kernel. The
 * default trace_id is a known constant so tests can assert trace_id
 * provenance (SS3.5).
 *
 * Imports: only `wire/`. No SDK, no React, no Playwright.
 */

import type { AGUIEvent } from "../../lib/wire/ag_ui_events";

export const DEFAULT_TRACE_ID = "test-trace-abc123";
export const DEFAULT_RUN_ID = "test-run-1";
export const DEFAULT_THREAD_ID = "test-thread-1";
export const DEFAULT_MESSAGE_ID = "test-message-1";

interface ScenarioOpts {
  readonly traceId?: string;
  readonly runId?: string;
  readonly threadId?: string;
  readonly messageId?: string;
}

function header(traceId: string): { raw_event: { trace_id: string } } {
  return { raw_event: { trace_id: traceId } };
}

/**
 * `plainMarkdown` -- a successful run that streams a short text response in
 * 5 deltas. Exercises:
 *   - SS2.4 streaming markdown (aria-live polite, incremental tokens)
 *   - SS2.14 TTFT (first delta arrives quickly)
 *   - SS3.5 trace_id provenance (every event carries the same trace_id)
 */
export function plainMarkdown(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  const deltas = [
    "The moon ",
    "is Earth's ",
    "only natural ",
    "satellite. ",
    "It orbits at ~384,400 km.",
  ];

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    ...deltas.map<AGUIEvent>((delta) => ({
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta,
      ...h,
    })),
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `toolCallSuccess` -- assistant invokes a `list_files` tool that returns
 * a string result. Exercises SS2.8 tool cards: status running -> completed,
 * input JSON pretty-printed, output rendered.
 */
export function toolCallSuccess(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const toolCallId = "tc-1";
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: "Let me list the files for you.",
      ...h,
    },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    {
      type: "TOOL_CALL_START",
      tool_call_id: toolCallId,
      tool_call_name: "list_files",
      parent_message_id: messageId,
      ...h,
    },
    {
      type: "TOOL_CALL_ARGS",
      tool_call_id: toolCallId,
      delta: '{"path": "."}',
      ...h,
    },
    { type: "TOOL_CALL_END", tool_call_id: toolCallId, ...h },
    {
      type: "TOOL_RESULT",
      tool_call_id: toolCallId,
      content: "README.md\npackage.json\nsrc/",
      role: "tool",
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `toolCallError` -- the tool returns an error string. Exercises SS2.8 tool
 * card error state (status flips to errored, card stays open).
 */
export function toolCallError(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const toolCallId = "tc-err-1";
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "TOOL_CALL_START",
      tool_call_id: toolCallId,
      tool_call_name: "shell",
      parent_message_id: null,
      ...h,
    },
    {
      type: "TOOL_CALL_ARGS",
      tool_call_id: toolCallId,
      delta: '{"command": "cat /etc/shadow"}',
      ...h,
    },
    { type: "TOOL_CALL_END", tool_call_id: toolCallId, ...h },
    {
      type: "TOOL_RESULT",
      tool_call_id: toolCallId,
      content: "Error: command 'cat /etc/shadow' rejected by allowlist",
      role: "tool",
      ...h,
    },
    {
      type: "RUN_ERROR",
      run_id: runId,
      thread_id: threadId,
      message: "tool execution failed",
      code: "tool_error",
      ...h,
    },
  ];
}

/**
 * `longStream` -- 50 deltas spaced by ~100ms (when used with `buildSSEStream`).
 * Exercises SS2.5 stop / regenerate -- the stream stays open long enough to
 * click Stop. With `buildSSEBody` (T1) the deltas all land at once; in that
 * mode the test asserts presence of the stop-button transition rather than
 * timing.
 */
export function longStream(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  const deltas: AGUIEvent[] = [];
  for (let i = 0; i < 50; i++) {
    deltas.push({
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: `Quantum paragraph ${i + 1}. `,
      ...h,
    });
  }

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    ...deltas,
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `runError` -- backend rejects the run after `RUN_STARTED`. Exercises
 * SS2.15 error resilience and the `run_error` UIRuntime event path.
 */
export function runError(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "RUN_ERROR",
      run_id: runId,
      thread_id: threadId,
      message: "internal server error",
      code: "server_error",
      ...h,
    },
  ];
}

/**
 * `generativePanel` -- emits a `state_render` event keyed for the inline
 * `PyramidPanel`. Exercises SS2.9 inline generative UI (no iframe).
 */
export function generativePanel(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "CUSTOM",
      name: "pyramid_panel",
      value: { layers: ["identity", "policy", "audit"] },
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `generativeCanvas` -- emits a `CUSTOM` event keyed for the iframe-isolated
 * `SandboxedCanvas`. Exercises SS2.9 sandboxed iframe (sandbox="allow-scripts").
 */
export function generativeCanvas(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "CUSTOM",
      name: "sandboxed_canvas",
      value: {
        srcdoc:
          "<html><body><canvas id='sine'></canvas><script>/* sine wave */</script></body></html>",
      },
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}
