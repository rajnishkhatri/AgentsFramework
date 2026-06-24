/**
 * useAvailableModels — load the model picker's catalog from the BFF.
 *
 * Fetches `GET /api/models` (auth-scoped proxy to the backend's H2 registry)
 * once on mount. Exposes the fetched `{name, tier}[]` plus the registry default.
 * On ANY failure (network, 401, malformed body) it falls back to an empty list:
 * the picker then shows Auto only and never blocks composing (the plan's
 * fail-safe). "Auto" itself is a UI sentinel the component prepends — it is
 * never a member of this list.
 */

"use client";

import * as React from "react";
import type { components } from "@/lib/wire-types";

type ModelInfo = components["schemas"]["ModelInfo"];

export interface AvailableModels {
  /** Registry models in first-match order (Auto is NOT included here). */
  readonly models: ReadonlyArray<ModelInfo>;
  /** The backend's steady-state default model name (for display only). */
  readonly defaultModel: string;
  /** True until the first fetch settles (success or fallback). */
  readonly loading: boolean;
}

const AUTO_ONLY: Omit<AvailableModels, "loading"> = {
  models: [],
  defaultModel: "",
};

function isModelsResponse(
  v: unknown,
): v is { default: string; models: ModelInfo[] } {
  if (typeof v !== "object" || v === null) return false;
  const o = v as Record<string, unknown>;
  if (typeof o.default !== "string" || !Array.isArray(o.models)) return false;
  return o.models.every(
    (m) =>
      typeof m === "object" &&
      m !== null &&
      typeof (m as Record<string, unknown>).name === "string" &&
      typeof (m as Record<string, unknown>).tier === "string",
  );
}

export function useAvailableModels(): AvailableModels {
  const [state, setState] = React.useState<AvailableModels>({
    ...AUTO_ONLY,
    loading: true,
  });

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/models", { cache: "no-store" });
        if (!res.ok) throw new Error(`models fetch ${res.status}`);
        const body: unknown = await res.json();
        if (!isModelsResponse(body)) throw new Error("malformed models body");
        if (cancelled) return;
        setState({
          models: body.models,
          defaultModel: body.default,
          loading: false,
        });
      } catch {
        // Fail-safe: Auto-only. Never block composing on a catalog fetch.
        if (!cancelled) setState({ ...AUTO_ONLY, loading: false });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
