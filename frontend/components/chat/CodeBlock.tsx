/**
 * Fenced code block with language tag + copy button (eval-UI F4).
 *
 * Leaf "use client" boundary: the copy interaction needs
 * `navigator.clipboard`. No syntax-highlighting dependency -- mono
 * rendering per the Appendix A type system; highlighting can layer on
 * later without changing this surface.
 */

"use client";

import * as React from "react";

export function CodeBlock(props: {
  language: string | null;
  code: string;
}): React.JSX.Element {
  const [copied, setCopied] = React.useState(false);

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(props.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1_500);
    } catch {
      // Clipboard unavailable (permissions / insecure context) -- the
      // button simply stays in its idle state.
    }
  }

  return (
    <div
      data-testid="code-block"
      className="border border-border rounded-md my-2 bg-surface overflow-hidden"
    >
      <div className="flex items-center justify-between px-3 py-1 border-b border-border-light">
        <span className="font-mono text-xs text-muted uppercase tracking-wide">
          {props.language ?? "text"}
        </span>
        <button
          type="button"
          data-testid="copy-code"
          onClick={copy}
          aria-label="Copy code"
          className="font-mono text-xs text-muted hover:text-fg bg-transparent border-0 cursor-pointer"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-auto m-0 px-3 py-2 font-mono text-sm leading-normal">
        <code>{props.code}</code>
      </pre>
    </div>
  );
}
