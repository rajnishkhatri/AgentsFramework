/**
 * Live-testing profile loader (read once at the top of playwright.config.ts).
 *
 * Reads `e2e/testing.profiles.yml`, selects the profile named by `TEST_PROFILE`
 * (or the file's `default_profile`), and FILLS ONLY UNSET env vars from it —
 * never clobbering a value already present on the command line.
 *
 * Precedence (12-factor / CLI convention): explicit env > profile file > Playwright
 * default. So `BASE_URL=... TEST_PROFILE=stress ...` still wins for BASE_URL.
 *
 * Fail-fast (config-research point: start valid or don't start): an unknown
 * `TEST_PROFILE` throws at config build time rather than silently running against
 * the wrong target.
 *
 * Scope: non-secret, version-controlled test-orchestration knobs only. Secrets
 * (WorkOS creds) stay in .env; this file only flips the non-secret switches.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";

type Profile = {
  base_url?: string;
  env?: Record<string, string>;
  requires?: Record<string, string>;
};

type ProfilesDoc = {
  default_profile?: string;
  profiles?: Record<string, Profile>;
};

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROFILES_PATH =
  process.env.TEST_PROFILES_FILE ?? path.join(HERE, "testing.profiles.yml");

/** Set an env var only if it is currently unset/empty (explicit-wins). */
function fillIfUnset(key: string, value: string): boolean {
  const existing = process.env[key];
  if (existing !== undefined && existing !== "") {
    return false; // explicit value already present — leave it
  }
  if (value === "") {
    return false; // a blank profile value means "no default", not "clear it"
  }
  process.env[key] = value;
  return true;
}

/**
 * Apply the selected profile to process.env. No-op when no profile is requested
 * AND no default is declared (so plain `pnpm test:e2e` is unaffected). Returns
 * the resolved profile name (or null when nothing was applied).
 */
export function applyTestProfile(): string | null {
  if (!fs.existsSync(PROFILES_PATH)) {
    return null;
  }

  const doc = yaml.load(fs.readFileSync(PROFILES_PATH, "utf8")) as ProfilesDoc;
  const profiles = doc?.profiles ?? {};

  // An explicit TEST_PROFILE is required to apply a non-default; otherwise the
  // file's default_profile is used only when the var is set to "default".
  const requested = process.env.TEST_PROFILE?.trim();
  const name = requested || doc?.default_profile;
  if (!name) {
    return null;
  }

  const profile = profiles[name];
  if (!profile) {
    const available = Object.keys(profiles).join(", ") || "(none)";
    throw new Error(
      `TEST_PROFILE="${name}" not found in ${path.basename(PROFILES_PATH)}. ` +
        `Available: ${available}.`,
    );
  }

  const applied: string[] = [];
  if (profile.base_url) {
    if (fillIfUnset("BASE_URL", profile.base_url)) applied.push("BASE_URL");
  }
  for (const [k, v] of Object.entries(profile.env ?? {})) {
    if (fillIfUnset(k, v)) applied.push(k);
  }

  // Quiet during normal runs; the summary is useful when explicitly profiling.
  if (requested) {
    const set = applied.length ? applied.join(", ") : "(nothing — all overridden)";
    // eslint-disable-next-line no-console
    console.log(`[test-profile] "${name}" → BASE_URL=${process.env.BASE_URL}; set: ${set}`);
    for (const [k, v] of Object.entries(profile.requires ?? {})) {
      // eslint-disable-next-line no-console
      console.log(`[test-profile] requires ${k}: ${v}`);
    }
  }

  return name;
}
