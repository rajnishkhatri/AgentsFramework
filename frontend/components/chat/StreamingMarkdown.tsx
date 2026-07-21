/**
 * Streaming markdown surface (S3.8.1, F2; full rendering eval-UI F4).
 *
 * RSC by default? No -- streaming display needs client state, so this is a
 * leaf "use client" boundary (B1, U2). The parent shell is RSC.
 *
 * - ARIA live region uses `aria-live="polite"` (NEVER `assertive`,
 *   FE-AP-5 AUTO-REJECT).
 * - Focus does not move on incoming tokens (U5).
 * - No `dangerouslySetInnerHTML` (FE-AP-5 family auto-reject):
 *   react-markdown renders a React element tree, never raw HTML, and raw
 *   HTML in the source text is NOT enabled (no rehype-raw).
 * - Mid-stream safety: `stabilizeStreamingMarkdown` closes dangling
 *   code fences before each parse so partial tokens never flash broken
 *   markup.
 * - Typography per Appendix A: answer = sans/base, headings = sans
 *   semibold, inline code = mono chip on a tinted background, fenced
 *   code = CodeBlock (language tag + copy button), tables = clean
 *   bordered rows.
 */

"use client";

import * as React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { CodeBlock } from "@/components/chat/CodeBlock";
import { stabilizeStreamingMarkdown } from "@/components/chat/markdown_stream";

function extractText(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (React.isValidElement(node)) {
    return extractText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

const MD_COMPONENTS: React.ComponentProps<typeof Markdown>["components"] = {
  h1: (p) => <h1 className="text-2xl font-semibold mt-4 mb-2">{p.children}</h1>,
  h2: (p) => <h2 className="text-xl font-semibold mt-4 mb-2">{p.children}</h2>,
  h3: (p) => <h3 className="text-lg font-semibold mt-3 mb-1">{p.children}</h3>,
  p: (p) => <p className="my-2 leading-relaxed">{p.children}</p>,
  ul: (p) => <ul className="my-2 pl-6 list-disc grid gap-1">{p.children}</ul>,
  ol: (p) => <ol className="my-2 pl-6 list-decimal grid gap-1">{p.children}</ol>,
  a: (p) => (
    <a href={p.href} className="text-accent underline" rel="noreferrer noopener">
      {p.children}
    </a>
  ),
  table: (p) => (
    <div className="overflow-x-auto my-2">
      <table className="border-collapse w-full text-sm">{p.children}</table>
    </div>
  ),
  th: (p) => (
    <th className="border border-border px-3 py-1.5 text-left font-semibold bg-surface">
      {p.children}
    </th>
  ),
  td: (p) => <td className="border border-border px-3 py-1.5">{p.children}</td>,
  blockquote: (p) => (
    <blockquote className="border-l-2 border-border pl-3 my-2 text-muted">
      {p.children}
    </blockquote>
  ),
  pre: (p) => {
    // react-markdown wraps fenced blocks as <pre><code class="language-x">.
    const child = React.Children.toArray(p.children)[0];
    if (React.isValidElement(child)) {
      const childProps = child.props as { className?: string; children?: React.ReactNode };
      const match = /language-(\S+)/.exec(childProps.className ?? "");
      return (
        <CodeBlock
          language={match?.[1] ?? null}
          code={extractText(childProps.children).replace(/\n$/, "")}
        />
      );
    }
    return <pre>{p.children}</pre>;
  },
  code: (p) => (
    // Inline code only -- fenced blocks are intercepted at `pre` above.
    <code className="font-mono text-sm bg-accent-light text-fg rounded-sm px-1 py-0.5">
      {p.children}
    </code>
  ),
};

export function StreamingMarkdown(props: {
  text: string;
  modelBadge?: string;
  step?: { count: number; name: string };
  /**
   * `card` (default) — chat-shell bubble with `bg-bg` padding.
   * `plain` — inherit parent surface (coach ladder / collapsible answers).
   */
  tone?: "card" | "plain";
}): React.JSX.Element {
  const tone = props.tone ?? "card";
  const showChrome = Boolean(props.modelBadge || props.step);
  return (
    <article
      className={cn(
        "text-fg",
        tone === "card" ? "grid gap-2 bg-bg p-3" : "min-w-0",
      )}
    >
      {showChrome ? (
        <header className="flex items-center gap-2 text-xs text-muted">
          {props.modelBadge ? (
            <span
              data-testid="model-badge"
              className={cn(
                "rounded-sm px-2 py-0.5 font-mono font-semibold uppercase tracking-wide",
                "bg-accent-light text-accent",
              )}
            >
              {props.modelBadge}
            </span>
          ) : null}
          {props.step ? (
            <span data-testid="step-meter" className="font-mono">
              step {props.step.count} · {props.step.name}
            </span>
          ) : null}
        </header>
      ) : null}
      <div aria-live="polite" aria-atomic="false" className="leading-relaxed">
        <Markdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
          {stabilizeStreamingMarkdown(props.text)}
        </Markdown>
      </div>
    </article>
  );
}
