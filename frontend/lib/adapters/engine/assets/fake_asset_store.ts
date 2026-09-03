/**
 * In-memory FormAssetStore for CI / lane tests (B0-6). Never holds ©ACT bytes.
 */

import type { FormAssetStore } from "../../../ports/engine/form_asset_store";
import type { AssetRef } from "../../../wire/exam_entities";

function refKey(ref: AssetRef): string {
  return `${ref.form_id}:${ref.key}`;
}

export class FakeAssetStore implements FormAssetStore {
  private readonly blobs: Map<string, Uint8Array>;

  constructor(entries: Iterable<[AssetRef, Uint8Array]> = []) {
    this.blobs = new Map(
      [...entries].map(([ref, bytes]) => [refKey(ref), bytes]),
    );
  }

  async getImage(ref: AssetRef): Promise<Uint8Array | null> {
    // null = unknown key (FormAssetStore contract; never throw).
    return this.blobs.get(refKey(ref)) ?? null;
  }

  async has(ref: AssetRef): Promise<boolean> {
    return this.blobs.has(refKey(ref));
  }
}
