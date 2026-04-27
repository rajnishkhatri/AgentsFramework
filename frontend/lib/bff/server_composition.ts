/**
 * Server-side composition for BFF Route Handlers (S3.9.1).
 *
 * This file is a server-side composition seam (counterpart to the React
 * composition seam in `lib/composition_react.tsx`). Per F1/C1 it is one of
 * the two files allowed to read `process.env` and to name a concrete
 * adapter factory; the architecture test in
 * `tests/architecture/test_frontend_layering.test.ts` recognises it as
 * part of the "composition" ring.
 *
 * Route Handlers MUST NOT read `process.env` (B6 / FE-AP-3) -- they go
 * through `serverPortBag()` for ports and `forwardToMiddleware()` for raw
 * SSE/HTTP proxying. Both helpers are owned here.
 */

import "server-only";
import {
  buildAdapters,
  type ArchitectureProfile,
  type PortBag,
} from "../composition";
import { makeWorkOSServerSDK } from "../adapters/auth/workos_server_sdk";

let _bag: PortBag | null = null;
let _middlewareUrl: string | null = null;

function middlewareUrl(): string {
  if (_middlewareUrl) return _middlewareUrl;
  _middlewareUrl = (
    process.env.MIDDLEWARE_URL ?? "http://localhost:8000"
  ).replace(/\/$/, "");
  return _middlewareUrl;
}

export function serverPortBag(): PortBag {
  if (_bag) return _bag;
  const profile = (process.env.ARCHITECTURE_PROFILE as ArchitectureProfile) ?? "v3";
  _bag = buildAdapters({
    profile,
    fetchImpl: globalThis.fetch.bind(globalThis),
    workosSDK: makeWorkOSServerSDK(),
    env: process.env as Record<string, string | undefined>,
    baseUrl: middlewareUrl(),
  });
  return _bag;
}

/**
 * Forward a request to the middleware service. Owned by the composition
 * seam so route handlers never reach into `process.env` themselves
 * (Rule C4/C5, FE-AP-3 / B6). Returns the raw upstream `Response` so the
 * caller can pipe SSE byte-for-byte through `proxySSE`.
 */
export async function forwardToMiddleware(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return globalThis.fetch(`${middlewareUrl()}${normalized}`, init);
}

/** Test-only seam. */
export function _resetServerComposition(): void {
  _bag = null;
  _middlewareUrl = null;
}
