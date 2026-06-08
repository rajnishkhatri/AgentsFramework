/**
 * Shared Playwright browser-context defaults for E2E runs.
 *
 * WorkOS AuthKit localizes from Accept-Language; without an explicit
 * locale, headless Chromium may pick af-ZA and render Afrikaans while
 * a normal Chrome profile stays English.
 */
export const E2E_BROWSER_CONTEXT = {
  locale: "en-US" as const,
  extraHTTPHeaders: {
    "Accept-Language": "en-US,en;q=0.9",
  },
};
