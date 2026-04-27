# `adapters/feature_flags/` — FeatureFlagProvider family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger.

## Port

[`FeatureFlagProvider`](../../ports/feature_flag_provider.ts) —
vendor-neutral, **synchronous** flag lookup. The sync return is a
deliberate **P5 exception** (documented both in the port JSDoc and in
the conformance test) so React components can call `isEnabled()` at
render time without a Suspense round trip.

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`EnvVarFlagsAdapter`](./env_var_flags_adapter.ts) | none — reads `NEXT_PUBLIC_FF_*` env vars |

Snapshot is taken at construction time (composition root) and frozen.
Post-construction env mutation does **not** affect lookups (tested).

## Recognized flags

| Flag name | Env var | V3 default |
|-----------|---------|------------|
| `pyramid_panel` | `NEXT_PUBLIC_FF_PYRAMID_PANEL` | `false` |
| `voice_mode` | `NEXT_PUBLIC_FF_VOICE_MODE` | `false` |
| `per_tool_authorization` | `NEXT_PUBLIC_FF_PER_TOOL_AUTHORIZATION` | `false` |
| `json_run_export` | `NEXT_PUBLIC_FF_JSON_RUN_EXPORT` | `false` |

Adding a new flag requires updating both `FeatureFlagName` (the port
helper type) and the `FLAG_TO_ENV` table — both live in this family.

## Truthy values

The set is intentionally narrow: `1`, `true`, `on`, `yes` (case
insensitive). Anything else — including `enabled`, `y`, the empty
string, or numeric `2` — evaluates to `false`. This matches the
backend's environment-flag parser.

## Logger

`frontend:adapter:feature_flags` (Rule **A7 / O3**). Emits a single
boot-time line:

| Event | Meta | When |
|-------|------|------|
| `flag snapshot loaded` | one boolean per flag | constructor (composition root) |

This makes the V3-Dev-Tier flag matrix observable in Cloud Logging /
Cloudflare Logs without leaking env values themselves. No PII.

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| A/B testing or per-user targeting needed | LaunchDarkly / Statsig adapter (requires ADR — moves the port to async + Suspense) | new adapter file; **port signature change** would be required (P5 exception removed) — substantive ADR scope |

## Tests

- [`env_var_flags_adapter.test.ts`](./env_var_flags_adapter.test.ts) —
  defaults (all `false`), exhaustive truthy parsing, snapshot semantics
  (post-construction mutation ignored).
