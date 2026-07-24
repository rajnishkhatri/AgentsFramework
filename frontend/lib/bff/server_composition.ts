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
import {
  makeWorkOSServerSDK,
  makeBypassServerSDK,
} from "../adapters/auth/workos_server_sdk";
import { selectThreadRepo } from "../adapters/thread_store/neon_thread_repo";
import { selectCoachMarkerRepo } from "../adapters/coach_marker/marker_repo";
import type { CoachSessionMarkerRepo } from "../ports/coach_session_marker_repo";
import type { EngineDb } from "../adapters/engine/db/engine_db";
import {
  buildEngineAdapters,
  selectEngineDb,
  type EnginePortBag,
} from "../composition_engine";

let _bag: PortBag | null = null;
let _middlewareUrl: string | null = null;
let _markerRepo: CoachSessionMarkerRepo | null = null;
let _engineDb: EngineDb | null = null;
let _enginePorts: EnginePortBag | null = null;

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
  // Dev/test escape hatch: when E2E_BYPASS_AUTH=1 the BFF data routes use a stub
  // identity (mirrors app/page.tsx's page-level bypass) so /api/models etc. don't
  // 401 locally. Never set in prod.
  const bypassAuth = process.env.E2E_BYPASS_AUTH === "1";
  _bag = buildAdapters({
    profile,
    fetchImpl: globalThis.fetch.bind(globalThis),
    workosSDK: bypassAuth ? makeBypassServerSDK() : makeWorkOSServerSDK(),
    env: process.env as Record<string, string | undefined>,
    baseUrl: middlewareUrl(),
    // Live-infra (Piece C): durable Neon ThreadStore when DATABASE_URL is set,
    // ephemeral in-memory otherwise. This is the one place a concrete thread
    // repo is named — the composition seam (C1) is allowed to read env here.
    threadRepo: selectThreadRepo(
      process.env as Record<string, string | undefined>,
    ),
  });
  return _bag;
}

/**
 * Coach-session marker store (ADR-0012 Amendment). Owned by the composition
 * seam (C1): the one place the concrete marker repo is named and env is
 * read. Durable pg table when DATABASE_URL is set; globalThis-backed
 * in-memory store otherwise (dev/shadow).
 */
export function coachMarkerRepo(): CoachSessionMarkerRepo {
  if (_markerRepo) return _markerRepo;
  _markerRepo = selectCoachMarkerRepo(
    process.env as Record<string, string | undefined>,
  );
  return _markerRepo;
}

/**
 * Durable engine DB (coach-v3 FR-A3 / T A.6 / ADR-0038). Mirrors
 * `coachMarkerRepo()`: memoized, env-reading, called directly by
 * `/api/engine/*` handlers — NOT a param on `serverPortBag()`/`buildAdapters`.
 * Unset `DATABASE_URL` → typed `EngineRepoError` via `selectEngineDb` (no
 * silent in-memory fallback).
 */
export function engineDb(): EngineDb {
  if (_engineDb) return _engineDb;
  _engineDb = selectEngineDb(
    process.env as Record<string, string | undefined>,
  );
  return _engineDb;
}

/**
 * Engine port bag over the durable `engineDb()` seam. Used by coarse handlers
 * that need Scheduler / repos (`next`, dashboard assembly) without naming
 * adapters in the route file.
 */
export function enginePorts(): EnginePortBag {
  if (_enginePorts) return _enginePorts;
  _enginePorts = buildEngineAdapters({
    env: process.env as Record<string, string | undefined>,
    engineDb: engineDb(),
    questionSource: "bank",
  });
  return _enginePorts;
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
  _markerRepo = null;
  _engineDb = null;
  _enginePorts = null;
}
