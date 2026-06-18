/**
 * HttpMemoryStore -- V3 `MemoryStore` adapter that forwards to the middleware
 * over HTTP (F-R9: the BFF never holds Mem0 credentials; the middleware owns
 * them). Mirrors the `SelfHostedLangGraphDevClient` forwarding shape:
 * injected `baseUrl` + `fetchImpl`, bearer token supplied per call by the BFF
 * composition (never read from env here).
 *
 * Layer rules: A1 (no SDK), A3 (no transport/translator import), A4 (only
 * `wire/` shapes cross the boundary). Validates every response with the Zod
 * wire schema so a malformed upstream payload is a typed error, not silent
 * corruption.
 */

import {
  MemoryCreateRequestSchema,
  MemoryItemSchema,
  MemoryListResponseSchema,
  type MemoryItem,
  type MemoryType,
} from "../../wire/agent_protocol";
import { MemoryStoreError, type MemoryStore } from "../../ports/memory_store";

export interface HttpMemoryStoreOptions {
  readonly baseUrl: string;
  readonly fetchImpl: typeof fetch;
  /** Supplies the caller's bearer token (F-R9: BFF injects, no env here). */
  readonly getToken: () => Promise<string>;
}

export class HttpMemoryStore implements MemoryStore {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly getToken: () => Promise<string>;

  constructor(opts: HttpMemoryStoreOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.fetchImpl = opts.fetchImpl;
    this.getToken = opts.getToken;
  }

  private async authHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken();
    return {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    };
  }

  async list(): Promise<ReadonlyArray<MemoryItem>> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/agent/memory`, {
        method: "GET",
        headers: await this.authHeaders(),
      });
    } catch (e) {
      throw new MemoryStoreError(e instanceof Error ? e.message : String(e), {
        cause: e,
      });
    }
    if (!res.ok) {
      throw new MemoryStoreError(`memory list failed (${res.status})`);
    }
    const parsed = MemoryListResponseSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new MemoryStoreError("malformed memory list response");
    }
    return parsed.data.items;
  }

  async add(content: string, type: MemoryType): Promise<MemoryItem> {
    const body = MemoryCreateRequestSchema.parse({ content, type, key: null });
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/agent/memory`, {
        method: "POST",
        headers: await this.authHeaders(),
        body: JSON.stringify(body),
      });
    } catch (e) {
      throw new MemoryStoreError(e instanceof Error ? e.message : String(e), {
        cause: e,
      });
    }
    if (!res.ok) {
      throw new MemoryStoreError(`memory add failed (${res.status})`);
    }
    const parsed = MemoryItemSchema.safeParse(await res.json());
    if (!parsed.success) {
      throw new MemoryStoreError("malformed memory add response");
    }
    return parsed.data;
  }

  async remove(key: string): Promise<void> {
    let res: Response;
    try {
      res = await this.fetchImpl(
        `${this.baseUrl}/agent/memory/${encodeURIComponent(key)}`,
        { method: "DELETE", headers: await this.authHeaders() },
      );
    } catch (e) {
      throw new MemoryStoreError(e instanceof Error ? e.message : String(e), {
        cause: e,
      });
    }
    // 404 is idempotent-OK from the caller's view (already gone).
    if (res.ok || res.status === 404) return;
    throw new MemoryStoreError(`memory remove failed (${res.status})`);
  }
}
