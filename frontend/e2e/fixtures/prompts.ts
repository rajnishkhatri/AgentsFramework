/**
 * Reusable prompt strings for Playwright tests.
 *
 * Mirrors Appendix B of `docs/FRONTEND_VALIDATION.md`. Each constant maps to a
 * scenario in `scenarios.ts` so tests can pair the prompt with the canned
 * AG-UI event sequence that the backend would produce in response.
 */

export const PROMPTS = {
  /** B.1 -- triggers `plainMarkdown` scenario. */
  PLAIN_MARKDOWN: "Write a short paragraph about the moon.",

  /** B.2 -- triggers `toolCallSuccess` scenario. */
  TOOL_CALL: "List the files in the current directory.",

  /** B.3 -- triggers `longStream` scenario (used for stop / regenerate). */
  LONG_STREAM: "Write a detailed analysis of quantum computing, at least eight paragraphs.",

  /** B.4a -- triggers `generativePanel` scenario. */
  GENERATIVE_PANEL: "Show me the trust-pyramid diagram for the current user.",

  /** B.4b -- triggers `generativeCanvas` scenario (sandboxed iframe). */
  GENERATIVE_CANVAS: "Render an interactive sine-wave visualizer in a sandbox.",

  /** B.5 -- triggers `toolCallError` scenario. */
  TOOL_ERROR: "Run `cat /etc/shadow` and show the output.",

  /** Generic short prompt used for TTFT measurement (SS2.14). */
  TTFT_SHORT: "What is 1 + 1?",
} as const;
