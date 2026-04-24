/**
 * SelfHostedLangGraphDevClient (S3.3.1, V3 adapter).
 *
 * Talks to the self-hosted LangGraph Developer runtime via the BFF
 * (`/api/run/stream`, `/api/run/cancel`, `/api/threads/...`). The BFF
 * forwards the request bytes to the Python middleware which embeds the
 * LangGraph runtime.
 *
 * SDK isolation: this adapter intentionally does NOT import the
 * `@langchain/langgraph-sdk` package even though the package is installed.
 * The BFF + middleware are the only callers of that SDK -- the browser
 * speaks the AG-UI Agent Protocol over plain HTTP/SSE so no SDK runs in
 * user-agent code (FE-AP-7 + bundle budget).
 *
 * Layering (Rule A3): adapters depend ONLY on `ports/`, `wire/`,
 * `trust-view/`, and SDKs. The SSE transport (`transport/sse_client`) and
 * the AG-UI -> UIRuntime translator (`translators/ag_ui_to_ui_runtime`)
 * are NOT imported here -- the composition root assembles them into the
 * `openUIRuntimeStream` function that this adapter receives via
 * constructor injection.
 *
 * Error translation table (JSDoc, A5):
 *   401 -> AgentAuthError
 *   403 -> AgentAuthorizationError
 *   429 -> AgentRateLimitError
 *   5xx -> AgentServerError
 *   fetch reject / abort -> AgentNetworkError
 *
 * trace_id is forwarded from the backend via SSE; this adapter never
 * generates one (FE-AP-7 AUTO-REJECT).
 *
 * SDK pin: see `frontend/package.json` (this adapter has no direct SDK dep).
 */

import {
  RunStateViewSchema,
  type RunCreateRequest,
  type RunStateView,
} from "../../wire/agent_protocol";
import type { UIRuntimeEvent } from "../../wire/ui_runtime_events";
import type { AgentRuntimeClient } from "../../ports/agent_runtime_client";
import { createAdapterLogger, type Logger } from "../_logger";
import {
  AgentAuthError,
  AgentAuthorizationError,
  AgentNetworkError,
  AgentRateLimitError,
  AgentServerError,
} from "./errors";

const log: Logger = createAdapterLogger("runtime");

export interface SelfHostedLangGraphDevClientOptions {
  readonly baseUrl: string;
  readonly fetchImpl: typeof fetch;
  readonly getAccessToken: () => Promise<string>;
  /**
   * Composition-injected stream factory. Returns a UIRuntime event stream
   * for the given `run_id`. The composition root assembles transport (SSE)
   * + translator (AG-UI -> UIRuntime) into this single function so the
   * adapter stays free of `transport/` and `translators/` imports (A3).
   *
   * Optional only so tests that exercise `createRun` / `cancel` need not
   * provide one; calls to `streamRun()` without it throw.
   */
  readonly openUIRuntimeStream?: (
    runId: string,
  ) => AsyncIterable<UIRuntimeEvent>;
}

export class SelfHostedLangGraphDevClient implements AgentRuntimeClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly getAccessToken: () => Promise<string>;
  private readonly openUIRuntimeStream:
    | ((runId: string) => AsyncIterable<UIRuntimeEvent>)
    | undefined;

  constructor(opts: SelfHostedLangGraphDevClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl;
    this.getAccessToken = opts.getAccessToken;
    this.openUIRuntimeStream = opts.openUIRuntimeStream;
  }

  async createRun(req: RunCreateRequest): Promise<RunStateView> {
    const token = await this.getAccessToken();
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/run/stream`, {
        method: "POST",
        headers: {
          authorization: `Bearer ${token}`,
          "content-type": "application/json",
          accept: "application/json",
        },
        body: JSON.stringify(req),
      });
    } catch (e) {
      log.warn("createRun fetch rejected", {
        adapter: "self_hosted_langgraph_dev_client",
        error_type: "network_error",
      });
      throw new AgentNetworkError(
        e instanceof Error ? e.message : String(e),
        { cause: e },
      );
    }
    if (res.status === 401) {
      log.info("createRun auth rejected", {
        adapter: "self_hosted_langgraph_dev_client",
        status_code: 401,
      });
      throw new AgentAuthError(await res.text());
    }
    if (res.status === 403) {
      log.info("createRun authorization rejected", {
        adapter: "self_hosted_langgraph_dev_client",
        status_code: 403,
      });
      throw new AgentAuthorizationError(await res.text());
    }
    if (res.status === 429) {
      log.warn("createRun rate-limited", {
        adapter: "self_hosted_langgraph_dev_client",
        status_code: 429,
      });
      throw new AgentRateLimitError(await res.text());
    }
    if (res.status >= 500) {
      log.error("createRun upstream 5xx", {
        adapter: "self_hosted_langgraph_dev_client",
        status_code: res.status,
      });
      throw new AgentServerError(await res.text());
    }
    if (!res.ok) throw new AgentServerError(`unexpected status ${res.status}`);
    const json = (await res.json()) as unknown;
    return RunStateViewSchema.parse(json);
  }

  streamRun(runId: string): AsyncIterable<UIRuntimeEvent> {
    if (!this.openUIRuntimeStream) {
      throw new Error(
        "streamRun requires an openUIRuntimeStream factory; the composition " +
          "root must inject one (typically `composition.ts` wires " +
          "`connectSSE` + `agUiToUiRuntime`).",
      );
    }
    return this.openUIRuntimeStream(runId);
  }

  async cancel(runId: string): Promise<void> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/run/cancel`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ run_id: runId }),
      });
    } catch {
      // Idempotent -- network failure is observable through SSE error.
      // Swallow per A6.
      return;
    }
    if (res.status === 404) return;
    if (res.status === 401) throw new AgentAuthError("cancel requires auth");
    // Any other status: swallow (best-effort cancel).
  }
}
