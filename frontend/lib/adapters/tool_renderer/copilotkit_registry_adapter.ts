/**
 * CopilotKitRegistryAdapter (S3.3.4, V3 ToolRendererRegistry).
 *
 * Implements the synchronous registry the React tree consults at render
 * time. The CopilotKit `<CopilotKit>` provider (mounted by the app shell)
 * subscribes to this registry to inject `useFrontendTool(...)` hooks for
 * each registered renderer.
 *
 * SDK isolation: this adapter does not import CopilotKit directly -- the
 * actual `useFrontendTool` calls happen inside `CopilotKitUIRuntime`. The
 * registry itself is SDK-free so it can be unit-tested in node.
 */

import type {
  ToolRenderer,
  ToolRendererRegistry,
} from "../../ports/tool_renderer_registry";
import { createAdapterLogger, type Logger } from "../_logger";

const log: Logger = createAdapterLogger("tool_renderer");

const NOOP: ToolRenderer = () => undefined;

export class CopilotKitRegistryAdapter implements ToolRendererRegistry {
  private readonly map = new Map<string, ToolRenderer>();

  register(toolName: string, renderer: ToolRenderer): void {
    if (this.map.has(toolName)) {
      log.debug("tool renderer overwritten", {
        adapter: "copilotkit_registry",
        tool_name: toolName,
      });
    }
    this.map.set(toolName, renderer);
  }

  resolve(toolName: string): ToolRenderer {
    return this.map.get(toolName) ?? this.map.get("*") ?? NOOP;
  }

  /**
   * Iterate all registered tool names. Used by `CopilotKitUIRuntime` to
   * mount one `useFrontendTool(name)` per registration at provider
   * construction time.
   */
  *entries(): IterableIterator<[string, ToolRenderer]> {
    for (const e of this.map.entries()) yield e;
  }
}
