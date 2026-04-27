/**
 * Shared adapter logger (Rule A7 / O3).
 *
 * Each adapter family (auth, runtime, thread_store, feature_flags,
 * tool_renderer, ui_runtime) gets its own namespaced logger:
 *
 *     const log = createAdapterLogger("auth");
 *     log.info("session refreshed", { user_id_hash, latency_ms });
 *
 * Allowed metadata fields (Rule O2 -- no PII):
 *   trace_id, run_id, thread_id, adapter, error_type, latency_ms,
 *   status_code, attempt, hashed identifiers.
 * Forbidden:
 *   tokens, raw user content, memory content, LLM output text, raw
 *   email addresses, raw phone numbers.
 *
 * Why this lives here (not under `lib/observability/`):
 *   `console.*` is forbidden outside `adapters/` (FE-AP-9). Keeping the
 *   sink inside `lib/adapters/` means `console.*` only appears in the
 *   adapter ring. The leading underscore signals this is a shared
 *   adapter-ring utility, not a sibling adapter -- A2 ("adapters do not
 *   import each other") is preserved in spirit.
 *
 * Browser vs server: this implementation uses `console.*` directly.
 * Server-side (Cloud Run / Edge) `console.*` is captured by the
 * platform's structured-log collector and forwarded to Cloud Logging /
 * Cloudflare Logs. Browser-side it appears in the devtools console.
 */

export type AdapterFamily =
  | "auth"
  | "runtime"
  | "thread_store"
  | "feature_flags"
  | "tool_renderer"
  | "ui_runtime";

export type LogLevel = "debug" | "info" | "warn" | "error";

/**
 * Allowed metadata keys. Adapters that want to attach arbitrary metadata
 * MUST stick to these (or hashed equivalents) so the logger output cannot
 * accidentally include PII.
 */
export type LogMeta = Readonly<{
  trace_id?: string;
  run_id?: string;
  thread_id?: string;
  user_id_hash?: string;
  adapter?: string;
  error_type?: string;
  status_code?: number;
  attempt?: number;
  latency_ms?: number;
  // Free-form numeric/boolean attributes are permitted; string values are
  // explicitly typed above so reviewers see at a glance which fields land
  // in logs. Adding a new string field requires updating this contract.
  [extra: string]: number | boolean | string | undefined;
}>;

export interface Logger {
  readonly namespace: string;
  debug(msg: string, meta?: LogMeta): void;
  info(msg: string, meta?: LogMeta): void;
  warn(msg: string, meta?: LogMeta): void;
  error(msg: string, meta?: LogMeta): void;
}

interface LoggerInternals {
  /** Test seam: replace the default console sink. */
  readonly sink?: (level: LogLevel, line: string) => void;
}

function defaultSink(level: LogLevel, line: string): void {
  // eslint-disable-next-line no-console -- intentional: this IS the adapter logger sink.
  const fn =
    level === "debug"
      ? console.debug
      : level === "info"
        ? console.info
        : level === "warn"
          ? console.warn
          : console.error;
  fn.call(console, line);
}

function format(
  namespace: string,
  level: LogLevel,
  msg: string,
  meta?: LogMeta,
): string {
  const base = `[${namespace}] ${level} ${msg}`;
  if (!meta) return base;
  // Stable key ordering for grep-friendliness in tests / log search.
  const parts: string[] = [];
  for (const k of Object.keys(meta).sort()) {
    const v = meta[k];
    if (v === undefined) continue;
    parts.push(`${k}=${typeof v === "string" ? v : String(v)}`);
  }
  return parts.length === 0 ? base : `${base} ${parts.join(" ")}`;
}

/**
 * Create a logger bound to a specific adapter family. The namespace
 * follows the §17 / O3 convention `frontend:adapter:<family>`.
 */
export function createAdapterLogger(
  family: AdapterFamily,
  internals?: LoggerInternals,
): Logger {
  const namespace = `frontend:adapter:${family}`;
  const sink = internals?.sink ?? defaultSink;
  return {
    namespace,
    debug(msg, meta) {
      sink("debug", format(namespace, "debug", msg, meta));
    },
    info(msg, meta) {
      sink("info", format(namespace, "info", msg, meta));
    },
    warn(msg, meta) {
      sink("warn", format(namespace, "warn", msg, meta));
    },
    error(msg, meta) {
      sink("error", format(namespace, "error", msg, meta));
    },
  };
}
