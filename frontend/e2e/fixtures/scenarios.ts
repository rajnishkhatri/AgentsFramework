/**
 * Canned AG-UI event sequences for Playwright Tier 1 / Tier 2 tests.
 *
 * Each scenario mirrors a row in Appendix B of `docs/guides/FRONTEND_VALIDATION.md`
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
 * `todoListRun` -- the agent maintains a `state_todo` checklist while
 * working (eval-UI F9). Two STATE_DELTA frames carry JSON-Patch
 * `replace /todos` ops exactly as `langgraph_runtime._translate_chain_end`
 * emits them; one item finishes, one is cancelled (must stay visibly
 * not-done), one stays pending.
 */
export function todoListRun(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  const todosV1 = [
    { id: "t1", content: "read notes.md", status: "in_progress" },
    { id: "t2", content: "strip TODO lines", status: "pending" },
    { id: "t3", content: "publish summary", status: "pending" },
  ];
  const todosV2 = [
    { id: "t1", content: "read notes.md", status: "completed" },
    { id: "t2", content: "strip TODO lines", status: "completed" },
    { id: "t3", content: "publish summary", status: "cancelled" },
  ];

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "STATE_DELTA",
      delta: [{ op: "replace", path: "/todos", value: todosV1 }],
      ...h,
    },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: "Working through the checklist.",
      ...h,
    },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    {
      type: "STATE_DELTA",
      delta: [{ op: "replace", path: "/todos", value: todosV2 }],
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `toolOnlyRun` -- the run ends on a tool result with NO prose at all
 * (eval-UI F11): the GJ-F-008/GJ-012 root-cause shape. The UI must
 * synthesize a fallback recap so the answer slot is never empty.
 */
export function toolOnlyRun(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const toolCallId = "tc-only-1";
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "TOOL_CALL_START",
      tool_call_id: toolCallId,
      tool_call_name: "file_io",
      parent_message_id: null,
      ...h,
    },
    {
      type: "TOOL_CALL_ARGS",
      tool_call_id: toolCallId,
      delta: '{"operation": "write", "path": "/workspace/f3.txt"}',
      ...h,
    },
    { type: "TOOL_CALL_END", tool_call_id: toolCallId, ...h },
    {
      type: "TOOL_RESULT",
      tool_call_id: toolCallId,
      content: "wrote 42 bytes",
      role: "tool",
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
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

/**
 * `reasoningRecapRun` -- a two-tool run whose backend emitted the F10
 * Tier-2 cheap recap (`CUSTOM reasoning_summary`) before RUN_FINISHED.
 * Exercises the "Show reasoning" expander.
 */
export function reasoningRecapRun(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  const tool = (id: string, name: string): ReadonlyArray<AGUIEvent> => [
    {
      type: "TOOL_CALL_START",
      tool_call_id: id,
      tool_call_name: name,
      parent_message_id: null,
      ...h,
    },
    { type: "TOOL_CALL_ARGS", tool_call_id: id, delta: '{"path": "/workspace/x.txt"}', ...h },
    { type: "TOOL_CALL_END", tool_call_id: id, ...h },
    { type: "TOOL_RESULT", tool_call_id: id, content: "ok", role: "tool", ...h },
  ];

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    ...tool("tc-recap-1", "file_io"),
    ...tool("tc-recap-2", "file_io"),
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: "The file now contains status=active.",
      ...h,
    },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    {
      type: "CUSTOM",
      name: "reasoning_summary",
      value: { text: "I wrote the file first, then read it back to verify the status value." },
      ...h,
    },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `taskUnderstandingRun` -- a run whose backend emitted the plan-time
 * TaskUnderstanding artifact (`CUSTOM task_understanding`, Phase 3 soft
 * gate) before the answer streamed. Exercises the understanding card.
 */
export function taskUnderstandingRun(opts: ScenarioOpts = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "CUSTOM",
      name: "task_understanding",
      value: {
        restated_intent: "Create /workspace/f3.txt and verify its contents.",
        success_conditions: [
          "The file /workspace/f3.txt exists with 'hello'.",
          "The file contents were listed via a shell command.",
        ],
        confidence: 0.85,
        source: "generated",
      },
      ...h,
    },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: "Created the file and verified its contents.",
      ...h,
    },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/**
 * `recalledMemoriesRun` -- a run whose backend recalled memories for the turn,
 * emitting `CUSTOM memory_recalled` with the injected records' KEYS (Phase B).
 * Keys are identifiers (never content); the eval view joins them against the
 * owner's memory panel. Exercises the recalled-memories eval/reject disclosure.
 */
export function recalledMemoriesRun(
  keys: ReadonlyArray<string>,
  opts: ScenarioOpts = {},
): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? DEFAULT_TRACE_ID;
  const runId = opts.runId ?? DEFAULT_RUN_ID;
  const threadId = opts.threadId ?? DEFAULT_THREAD_ID;
  const messageId = opts.messageId ?? DEFAULT_MESSAGE_ID;
  const h = header(traceId);

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    {
      type: "CUSTOM",
      name: "memory_recalled",
      value: { count: keys.length, keys: [...keys] },
      ...h,
    },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: messageId,
      delta: "You prefer metric units.",
      ...h,
    },
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}
