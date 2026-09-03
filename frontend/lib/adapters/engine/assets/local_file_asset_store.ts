/**
 * LocalFileAssetStore — FormAssetStore over `node:fs` (ADR-0042 / FR-P2-14).
 *
 * Constructor takes `baseDir` (C4: env is read only in composition_engine.ts).
 * Missing key ⇒ null. Path traversal is refused (not treated as missing).
 */

import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import { EngineRepoError } from "../../../ports/engine/errors";
import type { FormAssetStore } from "../../../ports/engine/form_asset_store";
import type { AssetRef } from "../../../wire/exam_entities";

export class LocalFileAssetStore implements FormAssetStore {
  private readonly baseDir: string;

  constructor(baseDir: string) {
    this.baseDir = path.resolve(baseDir);
  }

  async getImage(ref: AssetRef): Promise<Uint8Array | null> {
    const filePath = this.resolveKey(ref);
    try {
      return new Uint8Array(await readFile(filePath));
    } catch (err) {
      // G9: ENOENT = unknown/absent key (FormAssetStore contract). Other I/O
      // (EACCES, EISDIR) is not "missing" — surface it.
      if (isEnoent(err)) return null;
      throw err;
    }
  }

  async has(ref: AssetRef): Promise<boolean> {
    const filePath = this.resolveKey(ref);
    try {
      const info = await stat(filePath);
      return info.isFile();
    } catch (err) {
      // G9: same missing-key contract as getImage.
      if (isEnoent(err)) return false;
      throw err;
    }
  }

  private resolveKey(ref: AssetRef): string {
    const target = path.resolve(this.baseDir, ref.form_id, ref.key);
    const relative = path.relative(this.baseDir, target);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      throw new EngineRepoError(
        `LocalFileAssetStore: refused path-traversal key '${ref.key}'`,
      );
    }
    return target;
  }
}

function isEnoent(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "code" in err &&
    (err as { code: unknown }).code === "ENOENT"
  );
}
