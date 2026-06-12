/**
 * SelfHostedLangGraphDevClient (S3.3.1, V3 adapter).
 *
 * Talks to the self-hosted LangGraph Developer runtime via the BFF
 * (`/api/run/stream`, `/api/run/cancel`, `/api/threads/...`). The BFF
 * forwards the request bytes to the Python middleware which embeds the
 * LangGraph runtime.
 *
 * Protocol (eval-UI F1): the middleware exposes a single
 * `POST /run/stream` whose response body IS the SSE stream, so
 * `streamRun(req)` both starts the run and yields its events. There is no
 * separate create call. The BFF authenticates via session cookie
 * (`credentials: "include"` on the transport); no bearer token is needed
 * browser-side.
 *
 * SDK isolation: this adapter intentionally does NOT import the
 * `@langchain/langgraph-sdk` package even though the package is installed.
 * The BFF + middleware are the only callers of that SDK -- the browser
 * speaks the AG-UI Agent Protocol over plain HTTP/SSE so no SDK runs in
 * user-agent code (FE-AP-7 + bundle budget).
 *
 * Layering (Rule A3): adapters depend ONLY on `ports/`, `wire/`,
 * `trust-view/`, and SDKs. The fetch-SSE transport
 * (`transport/fetch_sse_client`) and the AG-UI -> UIRuntime translator
 * (`translators/ag_ui_to_ui_runtime`) are NOT imported here -- the browser
 * composition root (`composition_browser.ts`) assembles them into the
 * `openUIRuntimeStream` function this adapter receives via constructor
 * injection.
 *
 * Error surface (A5): stream-path failures arrive as `run_error`
 * UIRuntimeEvents with the closed `error_type` enum (401 -> auth_error,
 * 403 -> authorization_error, 429 -> rate_limit_error, 5xx -> server_error,
 * transport -> network_error), mapped in the composition stream.
 * `cancel()` keeps the typed-error contract: 401 -> AgentAuthError.
 *
 * trace_id is forwarded from the backend via SSE; this adapter never
 * generates one (FE-AP-7 AUTO-REJECT).
 *
 * SDK pin: see `frontend/package.json` (this adapter has no direct SDK dep).
 */

import type {
  RunCreateRequest,
  TaskUnderstandingEditRequest,
} from "../../wire/agent_protocol";
import type { UIRuntimeEvent } from "../../wire/ui_runtime_events";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "../../ports/agent_runtime_client";
import { createAdapterLogger, type Logger } from "../_logger";
import {
  AgentAuthError,
  AgentNetworkError,
  AgentRuntimeError,
} from "./errors";

const log: Logger = createAdapterLogger("runtime");

export interface SelfHostedLangGraphDevClientOptions {
  readonly baseUrl: string;
  readonly fetchImpl: typeof fetch;
  /**
   * Composition-injected stream factory. Starts the run described by the
   * request and returns its UIRuntime event stream. The composition root
   * assembles transport (fetch-SSE) + translators into this single
   * function so the adapter stays free of `transport/` and `translators/`
   * imports (A3).
   *
   * Optional only so tests that exercise `cancel` need not provide one;
   * calls to `streamRun()` without it throw.
   */
  readonly openUIRuntimeStream?: (
    req: RunCreateRequest,
    opts?: StreamRunOptions,
  ) => AsyncIterable<UIRuntimeEvent>;
}

export class SelfHostedLangGraphDevClient implements AgentRuntimeClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly openUIRuntimeStream:
    | ((
        req: RunCreateRequest,
        opts?: StreamRunOptions,
      ) => AsyncIterable<UIRuntimeEvent>)
    | undefined;

  constructor(opts: SelfHostedLangGraphDevClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl;
    this.openUIRuntimeStream = opts.openUIRuntimeStream;
  }

  streamRun(
    req: RunCreateRequest,
    opts?: StreamRunOptions,
  ): AsyncIterable<UIRuntimeEvent> {
    if (!this.openUIRuntimeStream) {
      throw new Error(
        "streamRun requires an openUIRuntimeStream factory; the browser " +
          "composition root must inject one (composition_browser.ts wires " +
          "`connectFetchSSE` + `agUiToUiRuntime`).",
      );
    }
    log.info("streamRun", {
      adapter: "self_hosted_langgraph_dev_client",
      thread_id: req.thread_id,
    });
    return this.openUIRuntimeStream(req, opts);
  }

  async updateUnderstanding(
    threadId: string,
    req: TaskUnderstandingEditRequest,
  ): Promise<void> {
    let res: Response;
    try {
      res = await this.fetchImpl(
        `${this.baseUrl}/run/understanding/${encodeURIComponent(threadId)}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(req),
        },
      );
    } catch (e) {
      throw new AgentNetworkError(
        e instanceof Error ? e.message : String(e),
        { cause: e },
      );
    }
    if (res.ok) return;
    if (res.status === 401) {
      throw new AgentAuthError("understanding edit requires auth");
    }
    let detail = res.statusText;
    try {
      const payload = (await res.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* keep statusText */
    }
    throw new AgentRuntimeError(
      `understanding edit rejected (${res.status}): ${detail}`,
    );
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
