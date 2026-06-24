"use client";

/**
 * iOS shell bootstrap (P6 Step 2) — mounts in the root layout, renders nothing.
 *
 * On mount it calls `setupIosShellAuth()` (P6 Step 2) and `setupIosNativeFeel()`
 * (P6 Step 3 — status bar, keyboard lift, safe area). Both are NO-OPs unless the
 * code is running inside the Capacitor native shell (`Capacitor.isNativePlatform()`),
 * so on the plain web + macOS-Tauri builds this is inert and safe to mount
 * unconditionally in the shared layout (F-R1: no domain logic here — it only
 * delegates to the iOS composition root).
 */

import { useEffect } from "react";
import { setupIosShellAuth, setupIosNativeFeel } from "@/lib/composition_ios";

export function IosShellBootstrap(): null {
  useEffect(() => {
    const cleanups: Array<() => void> = [];
    void setupIosShellAuth().then((teardown) => cleanups.push(teardown));
    void setupIosNativeFeel().then((teardown) => cleanups.push(teardown));
    return () => {
      for (const teardown of cleanups) teardown();
    };
  }, []);
  return null;
}
