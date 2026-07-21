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
    const isSubmit = e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey;
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
    if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey) { /* submit */ }
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
    if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey) { /* submit */ }
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
    if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey) { /* submit */ }
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
    if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey) { /* submit */ }
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

// The real Composer renders its textarea through the shadcn `<Textarea>`
// primitive (frontend/AGENTS.md U7 — wrap shadcn primitives; never a raw
// element). The U-family attributes (aria-label, rows, onKeyDown) sit on that
// `<Textarea>` element exactly as they would on a lowercase `<textarea>`. The
// checker MUST see through the capitalized primitive tag, or it fires a spurious
// "No <textarea> element found" COMPOSER violation on the one composer the repo
// actually ships — a false positive against the mandated pattern.
const PASS_BODY_PRIMITIVE = `
import * as React from "react";
import { Textarea } from "@/components/ui/textarea";
export function Composer(props: { onSend: (b: string) => void }): React.JSX.Element {
  const [body, setBody] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement>(null);
  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.nativeEvent.isComposing) return;
    const isSubmit = e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey;
    if (isSubmit) {
      e.preventDefault();
      props.onSend(body);
    }
  }
  return (
    <Textarea
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

describe("check_composer_keyboard — shadcn <Textarea> primitive (U7 wrapper)", () => {
  it("recognizes the <Textarea> primitive — no spurious COMPOSER violation", () => {
    const fp = tmpTsx(PASS_BODY_PRIMITIVE);
    const r = checkComposerKeyboard(fp);
    expect(
      r.violations.find((v) => v.rule === "COMPOSER"),
      "the <Textarea> primitive must be treated as a composer element",
    ).toBeFalsy();
  });

  it("evaluates the U-family contracts ON the <Textarea> primitive element", () => {
    const fp = tmpTsx(PASS_BODY_PRIMITIVE);
    const r = checkComposerKeyboard(fp);
    if (!r.pass) {
      throw new Error(
        `Expected primitive composer PASS: ${JSON.stringify(r, null, 2)}`,
      );
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
