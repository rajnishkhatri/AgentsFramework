/**
 * Composition root (S3.6.1) -- the ONLY file that names concrete adapter
 * classes and the ONLY file allowed to read `ARCHITECTURE_PROFILE`. Both
 * rules are statically enforced by `tests/architecture/test_frontend_layering.test.ts`.
 *
 * `buildAdapters({ profile, ... })` returns the typed port bag the React
 * tree consumes via `<AdapterProvider>` (a sibling React file -- keeping
 * pure construction here so unit tests run in node).
 *
 * Substrate swaps (V3 -> V2-Frontier) are composition-root-only changes
 * per F3 -- no `ports/`, `wire/`, `translators/`, or `transport/` files
 * change when graduating.
 *
 * Composition is also the ONLY place that wires `transport/` and
 * `translators/` into adapters. The `SelfHostedLangGraphDevClient`
 * adapter receives an injected `openUIRuntimeStream` factory so it stays
 * free of `transport/` and `translators/` imports (Rule A3).
 */

import { SelfHostedLangGraphDevClient } from "./adapters/runtime/self_hosted_langgraph_dev_client";
import {
  WorkOSAuthKitAdapter,
  type WorkOSSDK,
} from "./adapters/auth/workos_authkit_adapter";
import {
  InMemoryThreadRepo,
  NeonFreeThreadStore,
  type ThreadRepo,
} from "./adapters/thread_store/neon_free_thread_store";
import { EnvVarFlagsAdapter } from "./adapters/feature_flags/env_var_flags_adapter";
import { CopilotKitRegistryAdapter } from "./adapters/tool_renderer/copilotkit_registry_adapter";
import { CopilotKitUIRuntime } from "./adapters/ui_runtime/copilotkit_ui_runtime";
import {
  connectSSE,
  isSSEHeartbeatTimeout,
  isSSEParseError,
  type EventSourceFactory,
} from "./transport/sse_client";
import { agUiToUiRuntime } from "./translators/ag_ui_to_ui_runtime";
import type { UIRuntimeEvent } from "./wire/ui_runtime_events";
import type {
  AgentRuntimeClient,
  AuthProvider,
  FeatureFlagProvider,
  MemoryClient,
  TelemetrySink,
  ThreadStore,
  ToolRendererRegistry,
  UIRuntime,
} from "./ports";

export type ArchitectureProfile = "v3" | "v2";

export interface BuildAdaptersOptions {
  readonly profile: ArchitectureProfile;
  readonly fetchImpl: typeof fetch;
  readonly workosSDK: WorkOSSDK;
  readonly threadRepo?: ThreadRepo; // composition wires Neon repo; tests inject in-memory
  readonly env: Readonly<Record<string, string | undefined>>;
  readonly baseUrl: string;
  /**
   * Browser-side EventSource constructor. Server-side (BFF) builds proxy
   * SSE streams via `proxySSE`, so this can be omitted in node tests and
   * route handlers; only browser code paths invoke `streamRun()`.
   */
  readonly eventSourceFactory?: EventSourceFactory;
}

export interface PortBag {
  readonly agentRuntimeClient: AgentRuntimeClient;
  readonly authProvider: AuthProvider;
  readonly threadStore: ThreadStore;
  readonly memoryClient: MemoryClient;
  readonly telemetrySink: TelemetrySink;
  readonly featureFlagProvider: FeatureFlagProvider;
  readonly toolRendererRegistry: ToolRendererRegistry;
  readonly uiRuntime: UIRuntime;
}

// V3 placeholders for ports we have not yet built dedicated adapters for.
// These are intentionally minimal -- they satisfy the port contract so the
// composition root can return a PortBag today; concrete impls land in v1.5.

class NullMemoryClient implements MemoryClient {
  async search() {
    return [];
  }
  async recall() {
    return null;
  }
}

class NullTelemetrySink implements TelemetrySink {
  async log() {
    // O1: swallow.
  }
}

/**
 * Composition-time helper that assembles the SSE transport and the
 * AG-UI -> UIRuntime translator into a single `(runId) => stream` factory.
 *
 * Lives here (not in the adapter) so the runtime adapter remains free of
 * `transport/` and `translators/` imports -- Rule A3.
 *
 * On transport-level failures (parse error, heartbeat timeout) we
 * synthesize a `RunErrorEvent` with `trace_id: "no-trace"` -- this is a
 * documented sentinel, NOT browser-generated trace_id (FE-AP-7): there is
 * no real `trace_id` to forward when the SSE frame itself failed to
 * deserialize.
 */
function makeOpenUIRuntimeStream(
  baseUrl: string,
  eventSourceFactory: EventSourceFactory | undefined,
): (runId: string) => AsyncIterable<UIRuntimeEvent> {
  return async function* openUIRuntimeStream(
    runId: string,
  ): AsyncGenerator<UIRuntimeEvent, void, void> {
    if (!eventSourceFactory) {
      throw new Error(
        "openUIRuntimeStream requires an eventSourceFactory; the composition " +
          "caller (browser-side) must pass one (typically " +
          "`(url, init) => new EventSource(url, init)`).",
      );
    }
    const stream = connectSSE({
      url: `${baseUrl}/run/stream?run_id=${encodeURIComponent(runId)}`,
      runId,
      eventSourceFactory,
    });
    for await (const yielded of stream) {
      if (isSSEParseError(yielded)) {
        yield {
          type: "run_error",
          trace_id: "no-trace",
          run_id: runId,
          error_type: "wire_parse_error",
          message: yielded.message,
        };
        return;
      }
      if (isSSEHeartbeatTimeout(yielded)) {
        yield {
          type: "run_error",
          trace_id: "no-trace",
          run_id: runId,
          error_type: "network_error",
          message: yielded.message,
        };
        return;
      }
      try {
        for (const ui of agUiToUiRuntime(yielded)) {
          yield ui;
        }
      } catch (e) {
        yield {
          type: "run_error",
          trace_id: "no-trace",
          run_id: runId,
          error_type: "wire_parse_error",
          message: e instanceof Error ? e.message : String(e),
        };
        return;
      }
    }
  };
}

export function buildAdapters(opts: BuildAdaptersOptions): PortBag {
  if (opts.profile !== "v3" && opts.profile !== "v2") {
    throw new Error(`unknown profile: ${String(opts.profile)}`);
  }

  const auth = new WorkOSAuthKitAdapter({ sdk: opts.workosSDK });
  const flags = new EnvVarFlagsAdapter({ env: opts.env });
  const registry = new CopilotKitRegistryAdapter();
  registry.register("*", () => undefined);

  const baseUrl = opts.baseUrl.replace(/\/$/, "");
  const openUIRuntimeStream = makeOpenUIRuntimeStream(
    baseUrl,
    opts.eventSourceFactory,
  );

  const runtime = new SelfHostedLangGraphDevClient({
    baseUrl,
    fetchImpl: opts.fetchImpl,
    getAccessToken: () => auth.getAccessToken(),
    openUIRuntimeStream,
  });

  const threadStore = new NeonFreeThreadStore({
    repo: opts.threadRepo ?? new InMemoryThreadRepo(),
  });

  const ui = new CopilotKitUIRuntime({ runtimeClient: runtime });

  // V3 vs V2 currently differ only in substrate (Neon vs CloudSQL, Mem0 vs
  // Self-hosted Mem0, etc.) -- the swap is a one-line change here when the
  // V2 adapters land. Profile is preserved so the composition test can
  // verify both paths.
  if (opts.profile === "v2") {
    // Same bag shape, future V2 substitutions go here.
  }

  return {
    agentRuntimeClient: runtime,
    authProvider: auth,
    threadStore,
    memoryClient: new NullMemoryClient(),
    telemetrySink: new NullTelemetrySink(),
    featureFlagProvider: flags,
    toolRendererRegistry: registry,
    uiRuntime: ui,
  };
}
