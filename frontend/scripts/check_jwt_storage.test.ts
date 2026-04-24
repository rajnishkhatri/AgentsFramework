/**
 * Vitest sibling for `check_jwt_storage.ts`.
 *
 * Failure paths first (FD6.ADAPTER): each storage API + each auth-shaped
 * identifier is exercised before the PASS fixture.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import { checkJwtStorage } from "./check_jwt_storage";

function tmpTs(contents: string, ext = ".ts"): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "jwt-test-"));
  const file = path.join(dir, `mod${ext}`);
  fs.writeFileSync(file, contents, "utf8");
  return file;
}

describe("check_jwt_storage — rejection fixtures (failure paths first)", () => {
  it("FAILS on localStorage.setItem('jwt', tok)", () => {
    const fp = tmpTs(`export function save(tok: string): void { localStorage.setItem("jwt", tok); }`);
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(false);
    expect(r.violations[0]?.api).toBe("localStorage.setItem");
  });

  it("FAILS on sessionStorage.setItem('access_token', t)", () => {
    const fp = tmpTs(
      `export function s(t: string): void { sessionStorage.setItem("access_token", t); }`,
    );
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(false);
    expect(r.violations[0]?.api).toBe("sessionStorage.setItem");
  });

  it("FAILS on window.localStorage.setItem('bearer', x)", () => {
    const fp = tmpTs(
      `export function s(x: string): void { window.localStorage.setItem("bearer", x); }`,
    );
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(false);
  });

  it("FAILS when only the value identifier is auth-shaped", () => {
    const fp = tmpTs(
      `const sessionId = "x"; export function s(): void { localStorage.setItem("foo", sessionId); }`,
    );
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(false);
  });
});

describe("check_jwt_storage — pass fixtures", () => {
  it("PASSES on a benign localStorage write (theme preference)", () => {
    const fp = tmpTs(`export function save(): void { localStorage.setItem("theme", "dark"); }`);
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(true);
  });

  it("PASSES when there are no storage writes at all", () => {
    const fp = tmpTs(`export const x = 1;`);
    const r = checkJwtStorage(fp);
    expect(r.pass).toBe(true);
  });
});
