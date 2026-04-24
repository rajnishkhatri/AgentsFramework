/**
 * MemoryClient -- vendor-neutral long-term memory port (Mem0 in V3).
 *
 * The Mem0 calls themselves happen in `middleware/adapters/memory/`; the BFF
 * never calls Mem0 directly because doing so would force the BFF to hold
 * cloud credentials (F-R9 / FE-AP-18). The frontend port exists to type the
 * search/recall results that flow back to the UI via the run state.
 *
 * Port rules: P1, P2, P3, P4, P6.
 */

/**
 * One scored memory hit returned by `MemoryClient.search()`.
 */
export type MemorySearchHit = {
  readonly memory_id: string;
  readonly score: number;
  readonly content: string;
  readonly metadata: Readonly<Record<string, unknown>>;
};

/**
 * Vendor-neutral long-term memory port.
 *
 * Behavioral contract:
 *   - `search(query, opts)` returns at most `limit` memories ranked by
 *     relevance. Empty result is normal; throwing is reserved for transport
 *     failures.
 *   - `recall(memoryId)` returns the full memory or `null`.
 *   - All errors map to `MemoryClientError` (P4).
 */
export interface MemoryClient {
  /**
   * Semantic search across the user's memories.
   *
   * @throws MemoryClientError on transport / quota failure.
   */
  search(
    query: string,
    opts?: { limit?: number },
  ): Promise<ReadonlyArray<MemorySearchHit>>;

  /**
   * Read a single memory by id. Returns `null` if the id is unknown.
   *
   * @throws MemoryClientError on transport failure.
   */
  recall(memoryId: string): Promise<MemorySearchHit | null>;
}
