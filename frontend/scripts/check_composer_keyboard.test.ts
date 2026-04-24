/**
 * Vitest sibling for `check_composer_keyboard.ts`.
 *
 * Failure paths first (FD6.ADAPTER): each rejection fixture isolates one
 * U_* rule before we exercise a composite PASS fixture.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import * as os from "node:os";
import { checkComposerKeyboard } from "./check_composer_keyboard";

function tmpTsx(contents: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "composer-test-"));
  const file = path.join(dir, "Composer.tsx");
  fs.writeFileSync(file, contents, "utf8");
  return file;
}

const PASS_BODY = `
import * as React from "react";
export function Composer(props: { onSend: (b: string) => void }): React.JSX.Element {
  const [body, setBody] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement>(null);
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.nativeEvent.isComposing) return;
    const isSubmit = (e.metaKey || e.ctrlKey) && e.key === "Enter";
    if (isSubmit) {
      e.preventDefault();
      props.onSend(body);
    }
  }
  React.useEffect(() => {
    if (taRef.current) {
      taRef.current.style.height = "auto";
      taRef.current.style.height = taRef.current.scrollHeight + "px";
    }
  }, [body]);
  return (
    <textarea
      id="composer"
      ref={taRef}
      rows={2}
      value={body}
      onChange={(e) => setBody(e.target.value)}
      onKeyDown={onKeyDown}
      aria-label="Compose message"
    />
  );
}
`;

describe("check_composer_keyboard — rejection fixtures (failure paths first)", () => {
  it("FAILS U_KBD when submit pattern is missing", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  return <textarea aria-label="x" rows={2} />;
}
`);
    const r = checkComposerKeyboard(fp);
    expect(r.pass).toBe(false);
    expect(r.checks.u_kbd).toBe(false);
    expect(r.violations.find((v) => v.rule === "U_KBD")).toBeTruthy();
  });

  it("FAILS U_IME when handler lacks isComposing guard", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { /* submit */ }
  }
  return <textarea aria-label="x" rows={2} onKeyDown={onKeyDown} />;
}
`);
    const r = checkComposerKeyboard(fp);
    expect(r.checks.u_kbd).toBe(true);
    expect(r.checks.u_ime).toBe(false);
    expect(r.pass).toBe(false);
  });

  it("FAILS U_AUTOSIZE when textarea is fixed rows={1} with no growth", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.nativeEvent.isComposing) return;
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { /* submit */ }
  }
  return <textarea aria-label="x" rows={1} onKeyDown={onKeyDown} />;
}
`);
    const r = checkComposerKeyboard(fp);
    expect(r.checks.u_autosize).toBe(false);
    expect(r.pass).toBe(false);
  });

  it("FAILS U_LBL when no aria-label and no associated <label htmlFor>", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(): React.JSX.Element {
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.nativeEvent.isComposing) return;
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { /* submit */ }
  }
  return <textarea rows={2} onKeyDown={onKeyDown} />;
}
`);
    const r = checkComposerKeyboard(fp);
    expect(r.checks.u_lbl).toBe(false);
    expect(r.pass).toBe(false);
  });

  it("FAILS U_FOCUS_NO_STEAL when a useEffect with streaming dep refocuses the textarea", () => {
    const fp = tmpTsx(`
import * as React from "react";
export function Bad(props: { stream: string }): React.JSX.Element {
  const taRef = React.useRef<HTMLTextAreaElement>(null);
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.nativeEvent.isComposing) return;
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { /* submit */ }
  }
  React.useEffect(() => { taRef.current?.focus(); }, [props.stream]);
  return <textarea ref={taRef} aria-label="x" rows={2} onKeyDown={onKeyDown} className="field-sizing: content" />;
}
`);
    const r = checkComposerKeyboard(fp);
    expect(r.checks.u_focus_no_steal).toBe(false);
    expect(r.pass).toBe(false);
  });
});

describe("check_composer_keyboard — composite PASS fixture", () => {
  it("PASSES the all-rules-satisfied composer fixture", () => {
    const fp = tmpTsx(PASS_BODY);
    const r = checkComposerKeyboard(fp);
    if (!r.pass) {
      throw new Error(`Expected composite PASS: ${JSON.stringify(r, null, 2)}`);
    }
    expect(r.checks).toEqual({
      u_kbd: true,
      u_ime: true,
      u_autosize: true,
      u_lbl: true,
      u_focus_no_steal: true,
    });
  });
});
