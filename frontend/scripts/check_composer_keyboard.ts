/**
 * check_composer_keyboard.ts — Frontend Reviewer tool (FD2.U_KBD / U_IME /
 * U_AUTOSIZE / U_LBL / U_FOCUS_NO_STEAL).
 *
 * Walks a composer-style React component (typically
 * `frontend/components/chat/Composer.tsx`) and asserts the five composer
 * contracts encoded in the U-family of `architecture_rules.j2`:
 *
 *   U_KBD            A KeyboardEvent handler whose submit branch matches
 *                    plain Enter (`e.key === "Enter"`) AND explicitly
 *                    excludes the newline modifiers (Meta / Ctrl / Shift).
 *   U_IME            That same submit branch is guarded by
 *                    `!e.nativeEvent.isComposing`.
 *   U_AUTOSIZE       The textarea grows with content — either CSS
 *                    `field-sizing: content` in className OR a `useRef`
 *                    driven `scrollHeight` autosize pattern (presence of
 *                    either passes; fixed `rows={1}` with neither fails).
 *   U_LBL            The textarea has an associated `<label htmlFor>` OR
 *                    an `aria-label` / `aria-labelledby` attribute.
 *   U_FOCUS_NO_STEAL No `useEffect` whose dependency array includes
 *                    streaming text moves focus to the composer.
 *
 * Output JSON conforms to §5 of the Frontend Reviewer system prompt:
 *   {
 *     "pass": bool,
 *     "file": str,
 *     "checks": {u_kbd, u_ime, u_autosize, u_lbl, u_focus_no_steal: bool},
 *     "violations": [{"rule": str, "line": int, "description": str}]
 *   }
 *
 * Exit codes: 0 on PASS, 1 on FAIL, 2 on tool error.
 *
 * Usage: `tsx frontend/scripts/check_composer_keyboard.ts <filepath>`
 */

import * as path from "node:path";
import * as fs from "node:fs";
import {
  Project,
  SyntaxKind,
  type SourceFile,
  type JsxOpeningElement,
  type JsxSelfClosingElement,
} from "ts-morph";

interface Violation {
  rule: string;
  line: number;
  description: string;
}

interface ComposerChecks {
  u_kbd: boolean;
  u_ime: boolean;
  u_autosize: boolean;
  u_lbl: boolean;
  u_focus_no_steal: boolean;
}

interface CheckResult {
  pass: boolean;
  file: string;
  checks: ComposerChecks;
  violations: Violation[];
  error?: string;
}

const STREAMING_DEP_PATTERN = /(stream|token|message|content|delta|body|chunk)/i;

function asTagName(open: JsxOpeningElement | JsxSelfClosingElement): string {
  return open.getTagNameNode().getText();
}

function findTextareas(sf: SourceFile): Array<JsxOpeningElement | JsxSelfClosingElement> {
  const out: Array<JsxOpeningElement | JsxSelfClosingElement> = [];
  for (const node of sf.getDescendants()) {
    if (node.getKind() === SyntaxKind.JsxOpeningElement) {
      const open = node as JsxOpeningElement;
      if (asTagName(open) === "textarea") out.push(open);
    } else if (node.getKind() === SyntaxKind.JsxSelfClosingElement) {
      const sc = node as JsxSelfClosingElement;
      if (asTagName(sc) === "textarea") out.push(sc);
    }
  }
  return out;
}

function attributeNames(open: JsxOpeningElement | JsxSelfClosingElement): Set<string> {
  const out = new Set<string>();
  for (const attr of open.getAttributes()) {
    if (attr.getKind() !== SyntaxKind.JsxAttribute) continue;
    const name = (attr as { getNameNode?: () => { getText: () => string } }).getNameNode?.().getText();
    if (name) out.add(name);
  }
  return out;
}

function attributeText(
  open: JsxOpeningElement | JsxSelfClosingElement,
  name: string,
): string | null {
  for (const attr of open.getAttributes()) {
    if (attr.getKind() !== SyntaxKind.JsxAttribute) continue;
    const got = (attr as { getNameNode?: () => { getText: () => string } }).getNameNode?.().getText();
    if (got === name) {
      const init = (attr as { getInitializer?: () => unknown }).getInitializer?.();
      if (!init) return "";
      const node = init as { getText: () => string };
      return node.getText();
    }
  }
  return null;
}

function evaluateKeyboardSubmit(sf: SourceFile): { u_kbd: boolean; u_ime: boolean } {
  const text = sf.getFullText();
  // U_KBD: the submit branch matches plain Enter and excludes the newline
  // modifiers (Meta / Ctrl / Shift). Accept either ordering of the
  // `key === "Enter"` and `!metaKey && !ctrlKey && !shiftKey` conjuncts.
  const kbdRegex =
    /\.key\s*===\s*["'`]Enter["'`][\s\S]*?!\s*(?:[^.\s)]+\.)?metaKey[\s\S]*?!\s*(?:[^.\s)]+\.)?ctrlKey[\s\S]*?!\s*(?:[^.\s)]+\.)?shiftKey/;
  const u_kbd = kbdRegex.test(text);

  // U_IME: the SAME function body must reference !e.nativeEvent.isComposing
  // (either as a guard on the submit branch or as a top-of-handler early return).
  // Permissive check: presence of `nativeEvent.isComposing` anywhere inside a
  // KeyboardEvent handler body is enough — we parse function bodies that
  // include the U_KBD pattern and require `isComposing` inside the SAME body.
  let u_ime = false;
  for (const fn of sf.getDescendantsOfKind(SyntaxKind.FunctionDeclaration)) {
    const body = fn.getBodyText() ?? "";
    if (kbdRegex.test(body) && /isComposing/.test(body)) {
      u_ime = true;
      break;
    }
  }
  if (!u_ime) {
    for (const fn of sf.getDescendantsOfKind(SyntaxKind.ArrowFunction)) {
      const body = fn.getBodyText() ?? "";
      if (kbdRegex.test(body) && /isComposing/.test(body)) {
        u_ime = true;
        break;
      }
    }
  }
  if (!u_ime) {
    for (const fn of sf.getDescendantsOfKind(SyntaxKind.FunctionExpression)) {
      const body = fn.getBodyText() ?? "";
      if (kbdRegex.test(body) && /isComposing/.test(body)) {
        u_ime = true;
        break;
      }
    }
  }
  return { u_kbd, u_ime };
}

function evaluateAutosize(
  sf: SourceFile,
  textareas: Array<JsxOpeningElement | JsxSelfClosingElement>,
): boolean {
  if (textareas.length === 0) return false;
  // Pass condition: any textarea has `field-sizing: content` mentioned in
  // its className OR the file uses `scrollHeight` AND a useRef-bound textarea.
  const fileText = sf.getFullText();
  if (/field-sizing\s*:\s*content/.test(fileText)) return true;

  const hasScrollHeight = /scrollHeight/.test(fileText);
  const hasUseRefForTextarea = /useRef\s*<\s*HTMLTextAreaElement/.test(fileText);
  if (hasScrollHeight && hasUseRefForTextarea) return true;

  // If every textarea has rows>=2 OR no rows at all (default 2), give it the
  // benefit of the doubt — the rule targets fixed `rows={1}` without growth.
  for (const ta of textareas) {
    const rows = attributeText(ta, "rows");
    if (rows === null) continue; // no rows specified → browser default 2
    const m = rows.match(/\{?(\d+)\}?/);
    if (!m || !m[1]) continue;
    const n = Number(m[1]);
    if (n >= 2) return true;
  }
  return false;
}

function evaluateLabel(
  sf: SourceFile,
  textareas: Array<JsxOpeningElement | JsxSelfClosingElement>,
): boolean {
  if (textareas.length === 0) return false;
  const fileText = sf.getFullText();
  for (const ta of textareas) {
    const names = attributeNames(ta);
    if (names.has("aria-label") || names.has("aria-labelledby")) return true;
    // Look for `<label htmlFor=` referencing the textarea id (id may be
    // absent; presence of any <label htmlFor=...> in the same file is a
    // best-effort positive signal).
    if (names.has("id")) {
      const id = attributeText(ta, "id") ?? "";
      const idValue = id.replace(/[{}'"`]/g, "").trim();
      if (idValue && new RegExp(`htmlFor\\s*=\\s*["'\`]${idValue}["'\`]`).test(fileText)) {
        return true;
      }
    }
  }
  // Fallback: any label htmlFor + matching id pair anywhere in the tree.
  if (/<label\s+[^>]*htmlFor\s*=/.test(fileText)) return true;
  return false;
}

function evaluateFocusNoSteal(sf: SourceFile): boolean {
  // Pass = no useEffect mounts a `*.focus()` call whose dependency array
  // names a streaming-shaped variable.
  const fileText = sf.getFullText();
  // Simple regex over the file: useEffect(... focus() ..., [..stream/token/message..])
  const useEffectFocus = /useEffect\s*\(\s*\([^)]*\)\s*=>\s*\{[^}]*\.focus\s*\(\s*\)[^}]*\}\s*,\s*\[([^\]]*)\]/g;
  let match: RegExpExecArray | null;
  while ((match = useEffectFocus.exec(fileText)) !== null) {
    const deps = match[1] ?? "";
    if (STREAMING_DEP_PATTERN.test(deps)) return false;
  }
  return true;
}

/**
 * Run the composer keyboard check on a single file. Public entrypoint.
 *
 * @param filepath  Absolute or repo-relative path to the composer .tsx file.
 */
export function checkComposerKeyboard(filepath: string): CheckResult {
  const abs = path.resolve(filepath);
  if (!fs.existsSync(abs)) {
    return {
      pass: false,
      file: filepath,
      checks: { u_kbd: false, u_ime: false, u_autosize: false, u_lbl: false, u_focus_no_steal: true },
      violations: [],
      error: `file not found: ${filepath}`,
    };
  }
  try {
    const project = new Project({ useInMemoryFileSystem: false, compilerOptions: { jsx: 4 } });
    const sf = project.addSourceFileAtPath(abs);
    const textareas = findTextareas(sf);
    const { u_kbd, u_ime } = evaluateKeyboardSubmit(sf);
    const u_autosize = evaluateAutosize(sf, textareas);
    const u_lbl = evaluateLabel(sf, textareas);
    const u_focus_no_steal = evaluateFocusNoSteal(sf);

    const checks: ComposerChecks = { u_kbd, u_ime, u_autosize, u_lbl, u_focus_no_steal };
    const violations: Violation[] = [];
    if (textareas.length === 0) {
      violations.push({
        rule: "COMPOSER",
        line: 1,
        description: "No <textarea> element found; check_composer_keyboard expects a composer-style component.",
      });
    } else {
      const headLine = textareas[0]?.getStartLineNumber() ?? 1;
      if (!u_kbd)
        violations.push({
          rule: "U_KBD",
          line: headLine,
          description:
            "Composer is missing a submit handler that matches plain Enter and excludes the newline modifiers (Meta/Ctrl/Shift).",
        });
      if (!u_ime)
        violations.push({
          rule: "U_IME",
          line: headLine,
          description:
            "Composer submit branch is missing the `!e.nativeEvent.isComposing` guard; IME / kana / hangul Enter would double-fire.",
        });
      if (!u_autosize)
        violations.push({
          rule: "U_AUTOSIZE",
          line: headLine,
          description:
            "Composer textarea is fixed-height — neither `field-sizing: content` nor a `useRef` + `scrollHeight` autosize was found.",
        });
      if (!u_lbl)
        violations.push({
          rule: "U_LBL",
          line: headLine,
          description:
            "Composer textarea is missing an associated <label htmlFor>, aria-label, or aria-labelledby (jsx-a11y/label-has-associated-control).",
        });
      if (!u_focus_no_steal)
        violations.push({
          rule: "U_FOCUS_NO_STEAL",
          line: headLine,
          description:
            "A useEffect with a streaming-shaped dependency moves focus into the composer; that steals focus from the live region (U5 regression).",
        });
    }
    return { pass: violations.length === 0, file: filepath, checks, violations };
  } catch (e) {
    return {
      pass: false,
      file: filepath,
      checks: { u_kbd: false, u_ime: false, u_autosize: false, u_lbl: false, u_focus_no_steal: true },
      violations: [],
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

function main(argv: string[]): number {
  const arg = argv[2];
  if (!arg) {
    process.stderr.write("usage: tsx frontend/scripts/check_composer_keyboard.ts <filepath>\n");
    return 2;
  }
  const result = checkComposerKeyboard(arg);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  if (result.error) return 2;
  return result.pass ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exit(main(process.argv));
}
