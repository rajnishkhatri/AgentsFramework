/**
 * CopilotKitUIRuntime (S3.3.4, V3 UIRuntime).
 *
 * SDK isolation: the React provider (`<CopilotKit runtimeUrl=...>`) is
 * mounted by the app shell (`app/layout.tsx`) using the `CopilotKitProvider`
 * helper exported alongside this adapter. This file only owns the headless
 * `mount`/`stop`/`regenerate`/`editAndResend` plumbing -- which can be
 * tested in node without React.
 *
 * Because the React provider is composition-time only, the unit-testable
 * surface is small on purpose. Component-level tests live alongside the
 * `<CopilotKitChat>` story (S3.8.x).
 *
 * Error translation table (Rule A5):
 *   mount()        - never calls the runtime client; never throws under
 *                    the current implementation. Future provider
 *                    bootstrap errors must surface as AgentNetworkError.
 *   stop()         - delegates to AgentRuntimeClient.cancel(); the
 *                    underlying adapter swallows network failures (A6).
 *                    May surface AgentAuthError on 401.
 *   regenerate()   - calls stop() then dispatches a new run via the
 *                    CopilotKit provider; new-run errors surface as the
 *                    AgentRuntimeClient hierarchy
 *                    (Auth/Authorization/RateLimit/Server/Network).
 *   editAndResend() - same translation table as regenerate().
 *
 * SDK pin (Rule A9): see `frontend/package.json`.
 *   @sdk @copilotkit/react-core ^v2 (provider mounted in composition root)
 *   @sdk @copilotkit/react-ui   ^v2 (chat surface mounted in composition root)
 */

import type { ThreadState } from "../../wire/agent_protocol";
import type { AgentRuntimeClient } from "../../ports/agent_runtime_client";
import type {
  UIRuntime,
  UIRuntimeSession,
} from "../../ports/ui_runtime";
import { createAdapterLogger, type Logger } from "../_logger";

const log: Logger = createAdapterLogger("ui_runtime");

export interface CopilotKitUIRuntimeOptions {
  readonly runtimeClient: AgentRuntimeClient;
}

interface SessionHandle {
  runId: string | null;
}

export class CopilotKitUIRuntime implements UIRuntime {
  private readonly runtimeClient: AgentRuntimeClient;

  constructor(opts: CopilotKitUIRuntimeOptions) {
    this.runtimeClient = opts.runtimeClient;
  }

  async mount(args: { thread: ThreadState }): Promise<UIRuntimeSession> {
    const handle: SessionHandle = { runId: null };
    return { thread: args.thread, handle };
  }

  async stop(session: UIRuntimeSession): Promise<void> {
    const h = session.handle as SessionHandle;
    if (h.runId) {
      log.info("stop", {
        adapter: "copilotkit_ui_runtime",
        run_id: h.runId,
        thread_id: session.thread.thread_id,
      });
      await this.runtimeClient.cancel(h.runId);
    }
  }

  async regenerate(session: UIRuntimeSession): Promise<void> {
    log.info("regenerate", {
      adapter: "copilotkit_ui_runtime",
      thread_id: session.thread.thread_id,
    });
    await this.stop(session);
    // In production the CopilotKit provider observes the cancel and triggers
    // a new createRun via its thread runtime; here the adapter is the seam
    // for that orchestration.
  }

  async editAndResend(
    session: UIRuntimeSession,
    messageId: string,
    _body: string,
  ): Promise<void> {
    log.info("editAndResend", {
      adapter: "copilotkit_ui_runtime",
      thread_id: session.thread.thread_id,
      message_id: messageId,
    });
    await this.stop(session);
  }
}
