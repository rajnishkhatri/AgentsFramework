/**
 * NeonFreeThreadStore (S3.3.3, V3 ThreadStore).
 *
 * SDK isolation: production wiring of `drizzle-orm` + `@neondatabase/serverless`
 * happens in the composition root, which constructs a `NeonThreadRepo` and
 * passes it as the `repo` dependency. The store itself depends only on the
 * narrow `ThreadRepo` interface defined here, which keeps unit tests fast
 * (in-memory `InMemoryThreadRepo`) and prevents Drizzle types from leaking
 * past the adapter boundary (A4 / F-R8).
 *
 * Drizzle config note: `tablesFilter` MUST exclude LangGraph checkpoint
 * tables (the schema constant `THREAD_TABLE_NAME` is the inclusion list).
 *
 * Soft-delete policy: archive() flips the `archived_at` column; list() and
 * get() filter on `archived_at IS NULL`.
 *
 * Error translation table (Rule A5):
 *   repo.findOne() returns null OR row.user_id mismatch
 *                          -> get(): returns null (no existence oracle)
 *   repo.findOne() returns null OR ownership mismatch on rename
 *                          -> ThreadStoreError("thread {id} not found")
 *   repo.update() returns null after successful findOne
 *                          -> ThreadStoreError (race / concurrent delete)
 *   repo.findOne()/list()/insert()/update() rejection
 *                          -> propagated verbatim from the underlying repo
 *                             (the production NeonThreadRepo is responsible
 *                             for translating Drizzle/Neon errors to
 *                             `ThreadStoreError`; this layer never sees
 *                             vendor types per A4)
 *   archive() on missing-or-non-owner -> resolves silently (idempotent A6)
 *
 * SDK pin (Rule A9): see `frontend/package.json`.
 *   @sdk drizzle-orm ^0.x  (production wiring only; not used in tests)
 *   @sdk @neondatabase/serverless ^0.x
 */

import type { ThreadCreateRequest, ThreadState } from "../../wire/agent_protocol";
import type {
  ThreadListPage,
  ThreadStore,
} from "../../ports/thread_store";
import type { IdentityClaim } from "../../trust-view/identity";
import { createAdapterLogger, type Logger } from "../_logger";

const log: Logger = createAdapterLogger("thread_store");

export class ThreadStoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ThreadStoreError";
  }
}

/**
 * The narrow data-access shim that the production NeonThreadRepo and the
 * test InMemoryThreadRepo both implement. This keeps Drizzle / Neon types
 * out of the adapter's public surface.
 */
export interface ThreadRepo {
  insert(thread: ThreadRow): Promise<void>;
  findOne(threadId: string): Promise<ThreadRow | null>;
  list(opts: {
    ownerSub: string;
    cursor: string | null;
    limit: number;
  }): Promise<{ rows: ThreadRow[]; nextCursor: string | null }>;
  update(threadId: string, patch: Partial<ThreadRow>): Promise<ThreadRow | null>;
}

interface ThreadRow {
  thread_id: string;
  user_id: string;
  title: string;
  messages: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

function rowToState(row: ThreadRow): ThreadState {
  return {
    thread_id: row.thread_id,
    user_id: row.user_id,
    messages: row.messages,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

let _idSeq = 0;
function newId(): string {
  _idSeq += 1;
  return `t_${Date.now().toString(36)}_${_idSeq}`;
}

export class InMemoryThreadRepo implements ThreadRepo {
  private rows = new Map<string, ThreadRow>();
  // Insertion order tracks pagination.
  private order: string[] = [];

  async insert(thread: ThreadRow): Promise<void> {
    this.rows.set(thread.thread_id, thread);
    this.order.push(thread.thread_id);
  }
  async findOne(threadId: string): Promise<ThreadRow | null> {
    return this.rows.get(threadId) ?? null;
  }
  async list(opts: {
    ownerSub: string;
    cursor: string | null;
    limit: number;
  }): Promise<{ rows: ThreadRow[]; nextCursor: string | null }> {
    const visible = this.order
      .map((id) => this.rows.get(id)!)
      .filter((r) => r.user_id === opts.ownerSub && r.archived_at == null);
    let start = 0;
    if (opts.cursor) {
      const idx = visible.findIndex((r) => r.thread_id === opts.cursor);
      start = idx === -1 ? visible.length : idx + 1;
    }
    const page = visible.slice(start, start + opts.limit);
    const nextCursor =
      start + opts.limit < visible.length ? page[page.length - 1]!.thread_id : null;
    return { rows: page, nextCursor };
  }
  async update(threadId: string, patch: Partial<ThreadRow>): Promise<ThreadRow | null> {
    const row = this.rows.get(threadId);
    if (!row) return null;
    const merged = { ...row, ...patch, updated_at: new Date().toISOString() };
    this.rows.set(threadId, merged);
    return merged;
  }
}

export interface NeonFreeThreadStoreOptions {
  readonly repo: ThreadRepo;
}

export class NeonFreeThreadStore implements ThreadStore {
  private readonly repo: ThreadRepo;
  constructor(opts: NeonFreeThreadStoreOptions) {
    this.repo = opts.repo;
  }

  async create(
    identity: IdentityClaim,
    req: ThreadCreateRequest,
  ): Promise<ThreadState> {
    const now = new Date().toISOString();
    const row: ThreadRow = {
      thread_id: newId(),
      user_id: identity.sub,
      title: "New chat",
      messages: [],
      metadata: { ...req.metadata },
      created_at: now,
      updated_at: now,
      archived_at: null,
    };
    await this.repo.insert(row);
    return rowToState(row);
  }

  async get(
    identity: IdentityClaim,
    threadId: string,
  ): Promise<ThreadState | null> {
    const row = await this.repo.findOne(threadId);
    if (!row || row.user_id !== identity.sub || row.archived_at != null) {
      return null;
    }
    return rowToState(row);
  }

  async list(
    identity: IdentityClaim,
    options?: { cursor?: string | null; limit?: number },
  ): Promise<ThreadListPage> {
    const { rows, nextCursor } = await this.repo.list({
      ownerSub: identity.sub,
      cursor: options?.cursor ?? null,
      limit: options?.limit ?? 20,
    });
    return { threads: rows.map(rowToState), nextCursor };
  }

  async rename(
    identity: IdentityClaim,
    threadId: string,
    newTitle: string,
  ): Promise<ThreadState> {
    const existing = await this.repo.findOne(threadId);
    if (!existing || existing.user_id !== identity.sub) {
      log.info("rename rejected", {
        adapter: "neon_free_thread_store",
        thread_id: threadId,
        error_type: "not_found_or_not_owner",
      });
      throw new ThreadStoreError(`thread ${threadId} not found`);
    }
    const row = await this.repo.update(threadId, { title: newTitle });
    if (!row) throw new ThreadStoreError(`thread ${threadId} not found`);
    return rowToState(row);
  }

  async archive(identity: IdentityClaim, threadId: string): Promise<void> {
    const existing = await this.repo.findOne(threadId);
    if (!existing || existing.user_id !== identity.sub) {
      log.debug("archive idempotent no-op", {
        adapter: "neon_free_thread_store",
        thread_id: threadId,
      });
      // Idempotent: silently succeed.
      return;
    }
    await this.repo.update(threadId, { archived_at: new Date().toISOString() });
  }
}
