/**
 * Streaming-markdown stabilizer (eval-UI F4).
 *
 * Mid-stream, a fenced code block may not be closed yet; parsing it
 * as-is flashes raw backticks and swallows following text. Closing the
 * dangling fence keeps every in-flight render well-formed -- the next
 * delta re-parses the full text so no state is carried between renders.
 *
 * Pure string helper: no React, no I/O.
 */

const FENCE_LINE = /^\s{0,3}(```|~~~)/;

export function stabilizeStreamingMarkdown(text: string): string {
  if (text.length === 0) return text;
  let open = false;
  for (const line of text.split("\n")) {
    if (FENCE_LINE.test(line)) open = !open;
  }
  if (!open) return text;
  return text.endsWith("\n") ? `${text}\`\`\`` : `${text}\n\`\`\``;
}
