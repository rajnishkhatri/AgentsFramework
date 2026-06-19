/**
 * MemoryStore -- vendor-neutral CRUD port for the user's own long-term
 * memory, backing the editable memory panel (Phase 3, F1).
 *
 * Distinct from `MemoryClient` (P1: one interface per module): `MemoryClient`
 * is the agent's read-only *recall* surface; `MemoryStore` is the panel's
 * *management* surface (list / add / remove of the caller's own items).
 *
 * Like `MemoryClient`, the Mem0 calls themselves live in
 * `middleware/adapters/memory/` — the BFF never holds cloud credentials
 * (F-R9). The V3 adapter therefore FORWARDS to the middleware over HTTP with
 * the caller's bearer token; it does not touch a DB or an SDK directly.
 *
 * Every method is scoped to the caller's own subject server-side (the
 * cross-user-leak guard lives in the backend endpoint, keyed on
 * identity.owner). The port carries no user_id for that reason.
 *
 * Port rules: P1, P2, P3, P4, P6.
 */

import type { MemoryItem, MemoryType } from "../wire/agent_protocol";

/**
 * Vendor-neutral CRUD port for the caller's own memory.
 *
 * Behavioral contract:
 *   - `list()` returns the caller's own items (empty array is normal).
 *   - `add(content, type)` creates a user-authored memory and returns it.
 *   - `remove(key)` deletes one of the caller's items; resolves whether or
 *     not the key existed (idempotent from the caller's view).
 *   - All errors map to a `MemoryStoreError` (P4).
 */
export interface MemoryStore {
  /**
   * List the caller's own stored memories.
   *
   * @throws MemoryStoreError on transport failure.
   */
  list(): Promise<ReadonlyArray<MemoryItem>>;

  /**
   * Add a user-authored memory. `salience` (A3 provenance tiers) is optional —
   * omitted → stored unmarked.
   *
   * @throws MemoryStoreError on transport failure.
   */
  add(
    content: string,
    type: MemoryType,
    salience?: number | null,
  ): Promise<MemoryItem>;

  /**
   * Remove one of the caller's memories by key.
   *
   * @throws MemoryStoreError on transport failure.
   */
  remove(key: string): Promise<void>;
}

export class MemoryStoreError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "MemoryStoreError";
  }
}
