/**
 * Architecture test: HttpExplainabilityClient satisfies ExplainabilityClient.
 *
 * This is a compile-time structural check (AC5 of S0.3.2).
 * If HttpExplainabilityClient ever drifts from the port interface, tsc will
 * reject this file and the test will fail.
 */
import { describe, it, expect } from "vitest";
import type { ExplainabilityClient } from "@/lib/ports/explainability_client";
import { HttpExplainabilityClient } from "@/lib/adapters/http_explainability_client";

describe("port conformance", () => {
  it("HttpExplainabilityClient is assignable to ExplainabilityClient", () => {
    // Structural type check — if the adapter drifts from the interface,
    // this assignment fails at compile time (tsc --noEmit catches it).
    const client: ExplainabilityClient = new HttpExplainabilityClient(
      "http://localhost:8001",
    );
    expect(client).toBeDefined();
    expect(typeof client.listWorkflows).toBe("function");
  });
});
