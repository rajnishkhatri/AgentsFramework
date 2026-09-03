/**
 * FormAssetStore port (ADR-0042) — authenticated form-image bytes.
 *
 * One interface (P1). Adapters: LocalFileAssetStore (WT-B / FR-P2-14) and
 * the design-only GcsAssetStore follow-on (FR-P2-16, not built here).
 */

import type { AssetRef } from "../../wire/exam_entities";

/**
 * FormAssetStore — serve official-form images by opaque `AssetRef`.
 *
 * Behavioral contract:
 *  1. MISSING ⇒ NULL. `getImage` returns `null` when the key is unknown or
 *     the bytes are absent. It never throws for an unknown key (AP-6; the
 *     renderer shows a "content unavailable" placeholder — FR-P2-13).
 *  2. `has(ref)` is true only when `getImage` would return bytes.
 *  3. AUTHENTICATION is the call site's job (the asset route), not this
 *     port's. Adapters read bytes; they do not check the learner claim.
 *  4. NO BUNDLE. Image bytes never appear in the client JS graph; the
 *     browser root must not construct a store (C4/C5).
 *
 * @throws never for an unknown key — only for adapter-internal I/O that
 *   is not "missing" (e.g. a refused path-traversal). Those land in WT-B.
 */
export interface FormAssetStore {
  getImage(ref: AssetRef): Promise<Uint8Array | null>;
  has(ref: AssetRef): Promise<boolean>;
}
