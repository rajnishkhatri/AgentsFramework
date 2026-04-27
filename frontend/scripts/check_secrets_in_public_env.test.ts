/**
 * Vitest sibling for `check_secrets_in_public_env.ts`.
 *
 * Failure paths first (FD6.ADAPTER): every secret-shaped name AND every
 * secret-shaped value is exercised before the PASS fixtures (the
 * benign-only `.env`, the documented public-by-design CopilotKit key,
 * and the per-project allowlist).
 */

import { afterEach, describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import {
  checkSecretsInPublicEnv,
  evaluateEnvLine,
  loadAllowlist,
  parseCliArgs,
} from "./check_secrets_in_public_env";

const tmpFiles: string[] = [];

afterEach(() => {
  for (const f of tmpFiles.splice(0)) {
    try {
      fs.rmSync(path.dirname(f), { recursive: true, force: true });
    } catch {
      // best-effort cleanup
    }
  }
});

function tmpEnv(contents: string, name = ".env"): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "env-test-"));
  const file = path.join(dir, name);
  fs.writeFileSync(file, contents, "utf8");
  tmpFiles.push(file);
  return file;
}

function tmpJson(contents: string, name = "allow.json"): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "allow-test-"));
  const file = path.join(dir, name);
  fs.writeFileSync(file, contents, "utf8");
  tmpFiles.push(file);
  return file;
}

describe("evaluateEnvLine — pattern coverage", () => {
  it("flags NEXT_PUBLIC_*KEY* names", () => {
    expect(evaluateEnvLine("NEXT_PUBLIC_API_KEY=foo", 1)?.matched_pattern).toMatch(/KEY/);
  });
  it("flags NEXT_PUBLIC_*SECRET* names", () => {
    expect(evaluateEnvLine("NEXT_PUBLIC_DB_SECRET=foo", 1)?.matched_pattern).toMatch(/SECRET/);
  });
  it("flags NEXT_PUBLIC_*PRIVATE* names", () => {
    expect(evaluateEnvLine("NEXT_PUBLIC_PRIVATE_DSN=foo", 1)?.matched_pattern).toMatch(/PRIVATE/);
  });
  it("flags NEXT_PUBLIC_ values shaped like sk_*", () => {
    // Construct the value at runtime so the literal "sk_live_" prefix never
    // appears intact in source — keeps GitHub push-protection scanners happy
    // while still exercising the regex.
    const fakeSecret = ["sk", "live", "abcdefghijklmnopqrstuvwx"].join("_");
    const v = evaluateEnvLine(`NEXT_PUBLIC_FOO=${fakeSecret}`, 1);
    expect(v?.matched_pattern).toMatch(/sk_\*/);
  });
  it("flags NEXT_PUBLIC_ values shaped like JWT", () => {
    const seg = "abcdefghijklmnopqrstuvwxyz0123456789";
    const v = evaluateEnvLine(`NEXT_PUBLIC_X=${seg}.${seg}.${seg}`, 1);
    expect(v?.matched_pattern).toMatch(/JWT/);
  });
  it("ignores non-NEXT_PUBLIC names", () => {
    expect(evaluateEnvLine("API_KEY=foo", 1)).toBeNull();
  });
  it("ignores comments", () => {
    expect(evaluateEnvLine("# NEXT_PUBLIC_API_KEY=foo", 1)).toBeNull();
  });
  it("PASSES NEXT_PUBLIC names that look benign (URL, FLAG)", () => {
    expect(evaluateEnvLine("NEXT_PUBLIC_BASE_URL=https://example.com", 1)).toBeNull();
    expect(evaluateEnvLine("NEXT_PUBLIC_FEATURE_FLAG_NEW_UI=true", 1)).toBeNull();
  });
});

describe("evaluateEnvLine — hybrid PUBLIC + allowlist suppression", () => {
  it("PASSES NEXT_PUBLIC_*PUBLIC* names via the suffix-PUBLIC rule (default allowlist)", () => {
    // `CPK_PUBLIC_API_KEY` (the suffix after NEXT_PUBLIC_) contains
    // `PUBLIC` → name regex skipped. The value `cpk_pub_xxxx…` matches
    // the default allowlist pattern → value-shape skipped. PASS.
    const allowlist = loadAllowlist(
      path.resolve(__dirname, "secrets_allowlist.json"),
    );
    const v = evaluateEnvLine(
      "NEXT_PUBLIC_CPK_PUBLIC_API_KEY=cpk_pub_xxxxxxxxxxxxxxxxxxxxxxxx",
      1,
      allowlist,
    );
    expect(v).toBeNull();
  });

  it("STILL FAILS NEXT_PUBLIC_*API*KEY* without the PUBLIC affirmation", () => {
    // `OPENAI_API_KEY` suffix has no PUBLIC substring → name check
    // applies and matches *API* / *KEY*. The value shape isn't even
    // reached.
    const allowlist = loadAllowlist(
      path.resolve(__dirname, "secrets_allowlist.json"),
    );
    const v = evaluateEnvLine(
      "NEXT_PUBLIC_OPENAI_API_KEY=sk-abc1234567890123456789",
      1,
      allowlist,
    );
    expect(v).not.toBeNull();
    expect(v?.matched_pattern).toMatch(/name~/);
  });

  it("PASSES via custom --allowlist names[] (exact-match skips both name AND value checks)", () => {
    const allowJson = tmpJson(
      JSON.stringify({ names: ["NEXT_PUBLIC_CUSTOM_API_KEY"], patterns: [] }),
    );
    const allowlist = loadAllowlist(allowJson);
    // Even though the value LOOKS like a JWT, the exact-name allowlist
    // wins and skips every check for this variable.
    const seg = "abcdefghijklmnopqrstuvwxyz0123456789";
    const v = evaluateEnvLine(
      `NEXT_PUBLIC_CUSTOM_API_KEY=${seg}.${seg}.${seg}`,
      1,
      allowlist,
    );
    expect(v).toBeNull();
  });

  it("STILL FAILS when only the value matches a pattern but the NAME has no PUBLIC affirmation", () => {
    // Allowlist patterns suppress only the VALUE check. A leaked-name
    // (`NEXT_PUBLIC_..._KEY`) without a PUBLIC suffix-affirmation must
    // still trip the name-pattern detector.
    const allowJson = tmpJson(
      JSON.stringify({ names: [], patterns: ["^cpk_pub_[A-Za-z0-9]{16,}$"] }),
    );
    const allowlist = loadAllowlist(allowJson);
    const v = evaluateEnvLine(
      "NEXT_PUBLIC_OPENAI_API_KEY=cpk_pub_xxxxxxxxxxxxxxxxxxxxxxxx",
      1,
      allowlist,
    );
    expect(v).not.toBeNull();
    expect(v?.matched_pattern).toMatch(/name~/);
  });

  it("PUBLIC affirmation + value matches an allowlist pattern → PASS", () => {
    const allowJson = tmpJson(
      JSON.stringify({ names: [], patterns: ["^cpk_pub_[A-Za-z0-9]{16,}$"] }),
    );
    const allowlist = loadAllowlist(allowJson);
    const v = evaluateEnvLine(
      "NEXT_PUBLIC_VENDOR_PUBLIC_KEY=cpk_pub_xxxxxxxxxxxxxxxxxxxxxxxx",
      1,
      allowlist,
    );
    expect(v).toBeNull();
  });
});

describe("loadAllowlist — file IO + parsing", () => {
  it("returns an empty allowlist when the path is null", () => {
    const al = loadAllowlist(null);
    expect(al.names.size).toBe(0);
    expect(al.patterns).toEqual([]);
  });
  it("returns an empty allowlist when the file is missing", () => {
    const al = loadAllowlist("/tmp/definitely-not-a-real-file-xyz.json");
    expect(al.names.size).toBe(0);
  });
  it("throws on malformed JSON", () => {
    const f = tmpJson("{not json", "broken.json");
    expect(() => loadAllowlist(f)).toThrow(/parse allowlist/);
  });
  it("throws on invalid regex pattern", () => {
    const f = tmpJson(JSON.stringify({ names: [], patterns: ["[unterminated"] }));
    expect(() => loadAllowlist(f)).toThrow(/invalid regex/);
  });
  it("loads the bundled default allowlist (CopilotKit pre-allow)", () => {
    const al = loadAllowlist(
      path.resolve(__dirname, "secrets_allowlist.json"),
    );
    expect(al.names.has("NEXT_PUBLIC_CPK_PUBLIC_API_KEY")).toBe(true);
    expect(al.patterns.length).toBeGreaterThanOrEqual(1);
  });
});

describe("parseCliArgs — CLI surface", () => {
  it("accepts a bare filepath", () => {
    expect(parseCliArgs([".env"])).toEqual({
      filepath: ".env",
      allowlistPath: null,
      usageError: null,
    });
  });
  it("accepts --allowlist <path>", () => {
    expect(parseCliArgs([".env", "--allowlist", "/tmp/a.json"])).toEqual({
      filepath: ".env",
      allowlistPath: "/tmp/a.json",
      usageError: null,
    });
  });
  it("accepts --allowlist=<path>", () => {
    expect(parseCliArgs([".env", "--allowlist=/tmp/a.json"])).toEqual({
      filepath: ".env",
      allowlistPath: "/tmp/a.json",
      usageError: null,
    });
  });
  it("rejects --allowlist with no argument", () => {
    const r = parseCliArgs([".env", "--allowlist"]);
    expect(r.usageError).toMatch(/--allowlist requires/);
  });
  it("rejects unknown flags", () => {
    const r = parseCliArgs([".env", "--bogus"]);
    expect(r.usageError).toMatch(/unknown flag/);
  });
});

describe("check_secrets_in_public_env — file-level rejection + pass", () => {
  it("FAILS on a .env containing NEXT_PUBLIC_API_KEY", () => {
    const fp = tmpEnv("NEXT_PUBLIC_BASE_URL=https://x\nNEXT_PUBLIC_API_KEY=abc\n");
    const r = checkSecretsInPublicEnv(fp);
    expect(r.pass).toBe(false);
    expect(r.violations.find((v) => v.var === "NEXT_PUBLIC_API_KEY")).toBeTruthy();
  });

  it("PASSES on a .env with only benign NEXT_PUBLIC variables", () => {
    const fp = tmpEnv(
      "NEXT_PUBLIC_BASE_URL=https://x\nNEXT_PUBLIC_FEATURE_FLAG=true\n# comment line\n",
    );
    const r = checkSecretsInPublicEnv(fp);
    expect(r.pass).toBe(true);
    expect(r.violations).toEqual([]);
  });

  it("PASSES on the repo's `.env.example` when the bundled allowlist is supplied", () => {
    const repoEnv = path.resolve(__dirname, "..", "..", ".env.example");
    if (!fs.existsSync(repoEnv)) {
      // Repo layout sanity check; skip if .env.example is removed.
      return;
    }
    const allowlist = loadAllowlist(
      path.resolve(__dirname, "secrets_allowlist.json"),
    );
    const r = checkSecretsInPublicEnv(repoEnv, allowlist);
    expect(r.violations).toEqual([]);
    expect(r.pass).toBe(true);
  });
});
