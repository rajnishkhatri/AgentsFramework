/**
 * Mint a UUID v4 string that works outside secure contexts.
 *
 * `crypto.randomUUID()` is secure-context-only (HTTPS / localhost). Device
 * passes over LAN HTTP (`http://192.168.x.x:3000` on iPad Safari) throw
 * TypeError otherwise — W9 height-chain spike hits this path.
 *
 * Fallback uses `crypto.getRandomValues`, which is available on insecure
 * origins. Named failure: missing `randomUUID` on non-secure HTTP.
 */
export function newUuid(): string {
  const c = globalThis.crypto;
  if (c != null && typeof c.randomUUID === "function") {
    return c.randomUUID();
  }
  if (c == null || typeof c.getRandomValues !== "function") {
    throw new Error("crypto.getRandomValues unavailable; cannot mint UUID");
  }
  const bytes = new Uint8Array(16);
  c.getRandomValues(bytes);
  // RFC 4122 §4.4 — version 4 + variant 10xx
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join(
    "",
  );
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
