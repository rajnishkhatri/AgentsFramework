/**
 * Vitest sibling for `check_iframe_sandbox.ts`.
 *
 * Failure paths first (FD6.ADAPTER): missing-sandbox, dangerous-token, and
 * non-literal-value rejections come BEFORE the canonical SandboxedCanvas
 * PASS fixture.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import { checkIframeSandbox } from "./check_iframe_sandbox";

const TEST_DIR = (import.meta as { dirname?: string }).dirname ?? __dirname;
const FRONTEND_ROOT = path.resolve(TEST_DIR, "..");

function tmpTsx(contents: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "iframe-test-"));
  const file = path.join(dir, "Component.tsx");
  fs.writeFileSync(file, contents, "utf8");
  return file;
}

describe("check_iframe_sandbox — rejection fixtures (failure paths first)", () => {
  it("FAILS when <iframe> is missing the sandbox attribute (SBX1 / FE-AP-4)", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  return <iframe srcDoc={"<p>hi</p>"} title="bad" />;
}
`);
    const result = checkIframeSandbox(fp);
    expect(result.pass).toBe(false);
    expect(result.iframes[0]?.violations.some((v) => v.startsWith("SBX1"))).toBe(true);
  });

  it("FAILS when sandbox includes allow-same-origin (SBX2)", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  return <iframe sandbox="allow-scripts allow-same-origin" srcDoc="x" title="x" />;
}
`);
    const result = checkIframeSandbox(fp);
    expect(result.pass).toBe(false);
    const sbx2 = result.iframes[0]?.violations.find((v) => v.includes("allow-same-origin"));
    expect(sbx2).toBeTruthy();
  });

  it("FAILS when sandbox is a non-literal expression (cannot verify)", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(props: { sb: string }): React.JSX.Element {
  return <iframe sandbox={props.sb} srcDoc="x" title="x" />;
}
`);
    const result = checkIframeSandbox(fp);
    expect(result.pass).toBe(false);
    expect(result.iframes[0]?.violations.some((v) => v.includes("non-literal"))).toBe(true);
  });

  it("FAILS when sandbox is missing the required allow-scripts token", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  return <iframe sandbox="" srcDoc="x" title="x" />;
}
`);
    const result = checkIframeSandbox(fp);
    expect(result.pass).toBe(false);
  });
});

describe("check_iframe_sandbox — pass fixture against the canonical SandboxedCanvas", () => {
  it("PASSES on frontend/components/generative/SandboxedCanvas.tsx", () => {
    const fp = path.join(FRONTEND_ROOT, "components", "generative", "SandboxedCanvas.tsx");
    const result = checkIframeSandbox(fp);
    if (!result.pass) {
      throw new Error(`Expected canonical SandboxedCanvas to pass: ${JSON.stringify(result, null, 2)}`);
    }
    expect(result.pass).toBe(true);
    expect(result.iframes).toHaveLength(1);
    expect(result.iframes[0]?.sandbox).toBe("allow-scripts");
  });

  it("PASSES on a minimal sandbox=\"allow-scripts\" fixture", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Good(): React.JSX.Element {
  return <iframe sandbox="allow-scripts" srcDoc="x" title="x" />;
}
`);
    const result = checkIframeSandbox(fp);
    expect(result.pass).toBe(true);
  });
});
