"use client";

import { useEffect, useState } from "react";
import { authAdapter } from "../adapters/authAdapter";

/**
 * useSession — a clean frontend hook.
 *
 * FD1 clean: the SDK is imported only via an adapter (adapters/), not directly
 * into the component/hook. No trace_id generation here, no JWT in browser
 * storage.
 */
export function useSession(token: string | null) {
  const [session, setSession] = useState<{ user: string } | null>(null);

  useEffect(() => {
    if (!token) {
      setSession(null);
      return;
    }
    authAdapter.getSession(token).then(setSession);
  }, [token]);

  return session;
}
