/**
 * B-1 — LocalFileAssetStore (FR-P2-14).
 *
 * Reads constructor `baseDir` only (no env). Missing key ⇒ null.
 * Path traversal is refused (not treated as missing).
 */

import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { EngineRepoError } from "../../../ports/engine/errors";
import type { AssetRef } from "../../../wire/exam_entities";
import { LocalFileAssetStore } from "./local_file_asset_store";

const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function ref(over: Partial<AssetRef> = {}): AssetRef {
  return {
    store: "form-image",
    form_id: "fake-official-form",
    key: "math/q-2.png",
    ...over,
  };
}

describe("LocalFileAssetStore (B-1 / FR-P2-14)", () => {
  let baseDir = "";

  afterEach(async () => {
    if (baseDir) await rm(baseDir, { recursive: true, force: true });
    baseDir = "";
  });

  async function seeded(): Promise<LocalFileAssetStore> {
    baseDir = await mkdtemp(path.join(tmpdir(), "exam-assets-"));
    const dest = path.join(baseDir, "fake-official-form", "math");
    await mkdir(dest, { recursive: true });
    await writeFile(path.join(dest, "q-2.png"), PNG);
    return new LocalFileAssetStore(baseDir);
  }

  it("reads bytes from a file under the constructor baseDir", async () => {
    const store = await seeded();
    const image = ref();
    expect(await store.has(image)).toBe(true);
    expect(await store.getImage(image)).toEqual(PNG);
  });

  it("returns null for a missing key (never throws)", async () => {
    const store = await seeded();
    const missing = ref({ key: "missing.png" });
    expect(await store.has(missing)).toBe(false);
    expect(await store.getImage(missing)).toBeNull();
  });

  it("refuses a path-traversal key", async () => {
    const store = await seeded();
    const escape = ref({ key: "../../etc/passwd" });
    await expect(store.getImage(escape)).rejects.toBeInstanceOf(EngineRepoError);
    await expect(store.has(escape)).rejects.toBeInstanceOf(EngineRepoError);
  });
});
