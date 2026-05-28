/**
 * Composition root (rule C1, C2, C5).
 *
 * The ONLY file allowed to read NEXT_PUBLIC_EXPLAINABILITY_API_URL.
 * Exports buildAdapters() returning a typed bag of port implementations.
 * No domain logic here — just wiring.
 */
import { HttpExplainabilityClient } from "@/lib/adapters/http_explainability_client";
import type { ExplainabilityClient } from "@/lib/ports/explainability_client";

/** Typed adapter bag returned by buildAdapters() (rule C2). */
export interface Adapters {
  explainabilityClient: ExplainabilityClient;
  /**
   * The resolved API base URL.  Exposed so client components that need to
   * open browser-side connections (e.g. EventSource for log tail) can reuse
   * the same value the adapters were constructed with.  Rule C5 (only
   * reader of NEXT_PUBLIC_EXPLAINABILITY_API_URL) is preserved.
   */
  apiUrl: string;
}

/**
 * Reads env, constructs adapters, returns typed bag.
 * Call once per request in Server Components or once at app startup in client pages.
 */
export function buildAdapters(): Adapters {
  const apiUrl =
    process.env["NEXT_PUBLIC_EXPLAINABILITY_API_URL"] ?? "http://localhost:8001";
  return {
    explainabilityClient: new HttpExplainabilityClient(apiUrl),
    apiUrl,
  };
}
