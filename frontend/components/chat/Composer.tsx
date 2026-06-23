/**
 * Mobile-first responsive composer (S3.8.5, F4) — Cursor warm-neutral pill (§2.6).
 *
 * Shape (P2 redesign): a single soft `radius-lg` pill with a hairline border
 * that lifts to the accent on focus-within; the autosizing Textarea primitive
 * sits flush inside it and the send button is a round accent puck with an
 * up-arrow glyph. One rationed accent, no chrome — the look in the screenshot.
 *
 * Keyboard shortcuts: Enter submits. ⌘↩ / Ctrl↩ / Shift↩ insert a newline.
 *
 * IME guard (FD2.U_IME): the submit branch is suppressed while an IME
 * composition session is in flight (`e.nativeEvent.isComposing === true`).
 * Without the guard, the Enter key that confirms a kana/hangul/pinyin
 * candidate selection would also fire Enter and double-fire onSend.
 *
 * Autosize (FD2.U_AUTOSIZE): the Textarea primitive uses CSS
 * `field-sizing: content` (Tailwind v4 arbitrary property) to grow with
 * content up to a documented max of ~6 lines, then scrolls. `min-h-[2.5rem]`
 * and `max-h-[12rem]` (~6 × 2rem line-height) bracket the autosize range.
 */

// B1: 'use client' required — useState for body text, useRef for textarea,
// onKeyDown / onChange / onSubmit event handlers are browser-only APIs.
"use client";

import * as React from "react";
import { ArrowUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
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
      e.key === "Enter" &&
      !e.metaKey &&
      !e.ctrlKey &&
      !e.shiftKey &&
      !e.altKey &&
      !e.nativeEvent.isComposing;
    if (isSubmit) {
      e.preventDefault();
      submit();
    }
  }

  const disabled = props.busy || body.trim().length === 0;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      // The pill: soft radius-lg chrome, hairline border that warms to the
      // accent on focus-within. surface-sunken keeps it a half-step recessed
      // from the canvas so it reads as an input well, not a card.
      className={cn(
        "flex items-end gap-2 p-2 pl-4",
        "rounded-lg border border-border bg-surface-sunken",
        "transition-colors focus-within:border-accent",
      )}
    >
      {/*
        Autosize contract (FD2.U_AUTOSIZE): the Textarea primitive owns
        `field-sizing: content`. Inside the pill it drops its own border /
        background / padding so it reads as one continuous well; the pill
        provides the chrome. The min-h floor keeps a single visible line;
        the max-h ceiling caps growth at ~6 lines before it scrolls.
      */}
      <Textarea
        ref={taRef}
        rows={1}
        value={body}
        placeholder={props.placeholder ?? "Send a message… (⌘↩ for newline)"}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Compose message"
        className={cn(
          "flex-1 border-0 bg-transparent px-0 py-2",
          "focus:border-0 focus:outline-none",
        )}
      />
      <button
        type="submit"
        disabled={disabled}
        aria-label="Send"
        // Round accent puck — the one rationed accent in the composer.
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-full",
          "bg-accent text-white transition-opacity",
          "cursor-pointer disabled:cursor-not-allowed disabled:opacity-40",
        )}
      >
        <ArrowUp className="size-5" aria-hidden="true" />
      </button>
    </form>
  );
}
