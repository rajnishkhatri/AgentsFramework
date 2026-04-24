/**
 * BFF SSE edge proxy (S3.5.2).
 *
 * Pure helper -- given an upstream `Response`, returns a Web `Response` whose
 * body is forwarded byte-for-byte and whose headers are set per the X6
 * streaming-headers contract. Intended use is in a Next.js Route Handler:
 *
 *     const upstream = await fetch(MIDDLEWARE_SSE_URL, { ... });
 *     return proxySSE(upstream);
 *
 * The function is intentionally synchronous (no awaits): we hand back the
 * `ReadableStream` from upstream so Next.js / Cloudflare flushes it lazily.
 *
 * Per B7: this lives server-side only. Per X6: strips `Content-Encoding` so
 * upstream gzip never collides with the SSE byte stream. Other upstream
 * headers (e.g. `X-Trace-ID`) are forwarded verbatim.
 *
 * Imports: stdlib (Web standard) only.
 */

const STREAMING_HEADERS: ReadonlyArray<readonly [string, string]> = [
  ["Content-Type", "text/event-stream"],
  ["Cache-Control", "no-cache, no-transform"],
  ["X-Accel-Buffering", "no"],
  ["Connection", "keep-alive"],
];

const STRIPPED_HEADERS = new Set(["content-encoding", "content-length"]);

export function proxySSE(upstream: Response): Response {
  if (upstream.status >= 300 || upstream.status < 200) {
    // Non-success: pass straight through (preserve status + Content-Type).
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  }

  if (!upstream.body) {
    throw new Error(
      "proxySSE: upstream 2xx response has no body -- would wedge the SSE stream",
    );
  }

  const headers = new Headers();
  for (const [k, v] of upstream.headers.entries()) {
    if (!STRIPPED_HEADERS.has(k.toLowerCase())) {
      headers.set(k, v);
    }
  }
  for (const [k, v] of STREAMING_HEADERS) {
    headers.set(k, v);
  }

  return new Response(upstream.body, {
    status: 200,
    statusText: "OK",
    headers,
  });
}
