import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Capacitor 7 config — AgentsFramework iOS shell (P6).
 *
 * The web app is **server-dependent** (`next.config.ts` → `output: "standalone"`
 * + WorkOS AuthKit middleware + BFF API routes incl. SSE `run/stream`), so this
 * shell does NOT bundle a static export. It loads the running web app over the
 * network via `server.url` — the iOS analogue of the Tauri macOS shell's
 * remote-URL decision. See docs/plans/p6_capacitor_ios_shell.plan.md.
 *
 * URL modes (override with CAP_SERVER_URL, e.g. point a dev build at the
 * deployed URL for an auth spike, or at a teammate's LAN dev server):
 *   - release  → the deployed Cloud Run BFF (PROD_URL below)
 *   - dev      → CAP_SERVER_URL (a Mac LAN IP:3000) with cleartext allowed; a
 *                device/simulator cannot reach `localhost`, and iOS ATS blocks
 *                plain HTTP unless `cleartext: true`.
 *
 * `webDir` points at a tiny placeholder (capacitor-shell/) only to satisfy the
 * CLI — it is NEVER the loaded surface while `server.url` is set.
 */

// The deployed Cloud Run BFF the release build points at (same origin the web
// app and the Tauri macOS shell use — keep in sync with src-tauri PROD_URL).
const PROD_URL = "https://agent-frontend-590652793393.us-central1.run.app";

const serverUrl = process.env.CAP_SERVER_URL?.trim() || PROD_URL;
// Allow plain-HTTP only for a LAN dev URL; never for the pinned HTTPS prod URL.
const cleartext = serverUrl.startsWith("http://");

const config: CapacitorConfig = {
  appId: "com.agentsframework.app",
  appName: "AgentsFramework",
  // Placeholder only — unused when `server.url` is set (see file header).
  webDir: "capacitor-shell",
  server: {
    url: serverUrl,
    cleartext,
  },
  ios: {
    // Allow text/inputs to resize for the software keyboard; pairs with
    // @capacitor/keyboard's resize handling (P6 Step 3).
    contentInset: "always",
  },
  plugins: {
    Keyboard: {
      // Resize the WebView (not just the body) so the pinned composer rides the
      // keyboard; avoids the known Capacitor WebView keyboard-resize bug.
      resize: "native" as never,
    },
  },
};

export default config;
