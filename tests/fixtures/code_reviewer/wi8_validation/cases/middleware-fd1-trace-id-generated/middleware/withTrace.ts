// Middleware that generates a trace_id — violates FD1 (trace_id never generated here).
//
// The trace_id must flow verbatim from the upstream caller (frontend →
// middleware → backend). Generating it here breaks distributed-trace
// continuity and means this layer owns identity it should only forward.

export function withTraceId(request: Request): Request {
  const traceId = crypto.randomUUID(); // BUG: must not be generated here.
  const headers = new Headers(request.headers);
  headers.set("x-trace-id", traceId);
  return new Request(request, { headers });
}
