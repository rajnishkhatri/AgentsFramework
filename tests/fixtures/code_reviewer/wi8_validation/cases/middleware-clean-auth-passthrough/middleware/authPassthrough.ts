// Clean middleware auth passthrough.
//
// FD1/F-R2 clean: SDK imports confined to middleware/adapters/ (none here).
// No cloud credentials are held in this layer. trace_id flows verbatim — it
// is read from the incoming request and forwarded, never generated.

export function authPassthrough(request: Request): Request {
  const headers = new Headers(request.headers);
  // Forward the incoming trace_id verbatim; do not generate one here.
  const traceId = headers.get("x-trace-id");
  if (!traceId) {
    // Fail-safe: refuse to synthesize an id; surface the gap upstream.
    return new Response("missing trace_id", { status: 400 }) as unknown as Request;
  }
  // No credentials are read or stored in this layer.
  headers.set("x-forwarded-auth", "passthrough");
  return new Request(request, { headers });
}
