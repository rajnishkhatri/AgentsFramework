/**
 * DrizzleContentRepo — the `ContentRepo` adapter (ADR-0006 #7).
 *
 * The objective plane: UI strings keyed by (subject, key, locale). No business
 * logic. `text()` returns the key itself on a miss (a visible, debuggable
 * fallback — a missing label must never crash a screen, FR-F3) and only throws
 * on a backing-store failure. `bundle()` returns the full (subject, locale) map
 * for one-shot screen hydration. Locale defaults to "en".
 */

import type { ContentRepo } from "../../../ports/engine/content_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { EngineDb } from "../db/engine_db";

const DEFAULT_LOCALE = "en";

export class DrizzleContentRepo implements ContentRepo {
  constructor(private readonly db: EngineDb) {}

  async text(subject: string, key: string, locale = DEFAULT_LOCALE): Promise<string> {
    let value: string | null;
    try {
      value = await this.db.getContentString(subject, key, locale);
    } catch (err) {
      throw translate("text", err);
    }
    // Missing key → return the key itself (debuggable, never throws).
    return value ?? key;
  }

  async bundle(
    subject: string,
    locale = DEFAULT_LOCALE,
  ): Promise<Record<string, string>> {
    let rows: Array<{ key: string; value: string }>;
    try {
      rows = await this.db.listContentStrings(subject, locale);
    } catch (err) {
      throw translate("bundle", err);
    }
    const out: Record<string, string> = {};
    for (const { key, value } of rows) out[key] = value;
    return out;
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`content repo ${op} failed: ${detail}`);
}
