/**
 * ThreadStore -- vendor-neutral persistence port for chat threads.
 *
 * V3 implementation: NeonFreeThreadStore (Drizzle + @neondatabase/serverless).
 * V2 implementation: CloudSQLThreadStore.
 *
 * Port rules: P1, P2, P3, P4, P6.
 */

import type { ThreadCreateRequest, ThreadState } from "../wire/agent_protocol";
import type { IdentityClaim } from "../trust-view/identity";

/**
 * One page of cursor-paginated thread results.
 */
export type ThreadListPage = {
  readonly threads: ReadonlyArray<ThreadState>;
  readonly nextCursor: string | null;
};

/**
 * Vendor-neutral persistence port for chat threads.
 *
 * Behavioral contract:
 *   - `archive(threadId)` is a SOFT delete (sets `archived_at`); a hard
 *     `delete()` is intentionally absent until F1 calls for it.
 *   - `list({ userId, cursor })` is cursor-paginated (no offset). Returns
 *     `nextCursor: null` when the page is the last.
 *   - `get()` returns `null` for missing OR not-owned (404 and 403 are
 *     intentionally indistinguishable to avoid existence oracles, FD3.SEC).
 *   - `tablesFilter` in the Drizzle config MUST exclude LangGraph
 *     checkpoint tables.
 *   - All errors map to `ThreadStoreError` subclasses (P4).
 */
export interface ThreadStore {
  /**
   * Create a thread on behalf of `identity.sub`.
   *
   * @throws ThreadStoreError on persistence failure.
   */
  create(
    identity: IdentityClaim,
    req: ThreadCreateRequest,
  ): Promise<ThreadState>;

  /**
   * Read a thread by id. Returns `null` if not found or not owned by the
   * caller.
   */
  get(identity: IdentityClaim, threadId: string): Promise<ThreadState | null>;

  /**
   * List threads owned by `identity.sub`. Cursor-paginated.
   *
   * @throws ThreadStoreError on persistence failure.
   */
  list(
    identity: IdentityClaim,
    options?: { cursor?: string | null; limit?: number },
  ): Promise<ThreadListPage>;

  /**
   * Rename a thread. Returns the updated state.
   *
   * @throws ThreadStoreError if the thread does not exist or is not owned
   *   by the caller.
   */
  rename(
    identity: IdentityClaim,
    threadId: string,
    newTitle: string,
  ): Promise<ThreadState>;

  /**
   * Soft-delete a thread (sets `archived_at`).
   */
  archive(identity: IdentityClaim, threadId: string): Promise<void>;
}
