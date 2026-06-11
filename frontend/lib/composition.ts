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

export function buildAdapters(opts: BuildAdaptersOptions): PortBag {
  if (opts.profile !== "v3" && opts.profile !== "v2") {
    throw new Error(`unknown profile: ${String(opts.profile)}`);
  }

  const auth = new WorkOSAuthKitAdapter({ sdk: opts.workosSDK });
  const flags = new EnvVarFlagsAdapter({ env: opts.env });
  const registry = new CopilotKitRegistryAdapter();
  registry.register("*", () => undefined);

  const baseUrl = opts.baseUrl.replace(/\/$/, "");

  // Server-side bag: streaming is a browser concern -- the BFF proxies SSE
  // bytes via `proxySSE` and never consumes `streamRun()`. The browser
  // composition root (`composition_browser.ts`) injects the fetch-SSE
  // stream factory (§8.6-E); here `streamRun` throws if ever invoked.
  const runtime = new SelfHostedLangGraphDevClient({
    baseUrl,
    fetchImpl: opts.fetchImpl,
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
