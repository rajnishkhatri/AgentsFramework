/**
 * ContentRepo — the objective plane: UI strings keyed by (subject, key, locale)
 * (ADR-0006 #7).
 *
 * Behavioral contract:
 *   1. NO BUSINESS LOGIC. This port returns labels; it makes no decisions. An
 *      in-repo bundle now, a CMS later — the seam is the same (engine spec
 *      FR-F3). `subject` is a dimension alongside `locale`.
 *   2. `text()` returns the string for a (subject, key, locale). On a missing
 *      key it returns the `key` itself (a visible, debuggable fallback), never
 *      throws — a missing label must not crash a screen.
 *   3. `bundle()` returns the full (subject, locale) map for one-shot hydration
 *      (the UI loads a screen's strings once, not per-label).
 *   4. Locale defaults to `"en"`.
 *
 * @throws EngineRepoError only on a backing-store failure (not on a missing key).
 */

export interface ContentRepo {
  /** One label; returns the key itself if absent (no throw). */
  text(subject: string, key: string, locale?: string): Promise<string>;

  /** The full (subject, locale) label map for one-shot hydration. */
  bundle(subject: string, locale?: string): Promise<Record<string, string>>;
}
