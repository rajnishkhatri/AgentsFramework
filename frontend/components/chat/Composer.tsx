/**
 * Mobile-first responsive composer (S3.8.5, F4).
 *
 * Keyboard shortcuts: ⌘↩ / Ctrl↩ submits. Shift+Enter inserts a newline.
 *
 * IME guard (FD2.U_IME): the submit branch is suppressed while an IME
 * composition session is in flight (`e.nativeEvent.isComposing === true`).
 * Without the guard, the Enter key that confirms a kana/hangul/pinyin
 * candidate selection would also trip Meta+Enter and double-fire onSend.
 *
 * Autosize (FD2.U_AUTOSIZE): the textarea uses CSS `field-sizing: content`
 * (Tailwind v4 arbitrary property) to grow with content up to a documented
 * max of 6 lines, then scrolls. `min-h-[2.5rem]` and `max-h-[12rem]`
 * (~6 × 2rem line-height) bracket the autosize range. `resize-y` is kept
 * as a secondary manual-drag override so the user can still nudge the
 * height when desired; CSS field-sizing is the primary growth signal so
 * mobile keyboards never see a fixed-height textarea (F4).
 */

// B1: 'use client' required — useState for body text, useRef for textarea,
// onKeyDown / onChange / onSubmit event handlers are browser-only APIs.
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function Composer(props: {
  onSend: (body: string) => void | Promise<void>;
  busy?: boolean;
  placeholder?: string;
}): React.JSX.Element {
  const [body, setBody] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement>(null);

  function submit(): void {
    const trimmed = body.trim();
    if (!trimmed || props.busy) return;
    void props.onSend(trimmed);
    setBody("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    const isSubmit =
      (e.metaKey || e.ctrlKey) &&
      e.key === "Enter" &&
      !e.nativeEvent.isComposing;
    if (isSubmit) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex gap-2 p-3 border-t border-border-light bg-bg"
    >
      {/*
        Autosize contract (FD2.U_AUTOSIZE): `field-sizing: content` is the
        primary growth driver. The min-h floor keeps a single visible
        line; the max-h ceiling caps growth at ~6 lines (matches the rule
        default in `architecture_rules.j2`) before the textarea begins to
        scroll. `resize-y` is the manual-override fallback.
      */}
      <textarea
        ref={taRef}
        rows={1}
        value={body}
        placeholder={props.placeholder ?? "Send a message…"}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Compose message"
        className={cn(
          "flex-1 bg-transparent text-fg border border-border",
          "rounded-md px-3 py-2 text-[0.95rem] font-[inherit]",
          "[field-sizing:content] min-h-[2.5rem] max-h-[12rem]",
          "resize-y",
        )}
      />
      <button
        type="submit"
        disabled={props.busy || body.trim().length === 0}
        aria-label="Send"
        className={cn(
          "bg-accent text-white border-0 rounded-md px-4",
          "font-semibold cursor-pointer",
          "disabled:cursor-not-allowed disabled:opacity-60",
        )}
      >
        Send
      </button>
    </form>
  );
}
