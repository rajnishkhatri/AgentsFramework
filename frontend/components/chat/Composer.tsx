/**
 * Mobile-first responsive composer (S3.8.5, F4) — Cursor warm-neutral (§2.6).
 *
 * Shape (P2 + design-showcase polish): a soft `radius-lg` box — the autosizing
 * Textarea on top, a toolbar row beneath it (left: add + model picker; right:
 * the round accent send puck). Hairline border warms to the accent on
 * focus-within. One rationed accent (the send puck + the gradient it carries).
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
import { ArrowUp, ChevronDown, Plus } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export function Composer(props: {
  onSend: (body: string) => void | Promise<void>;
  busy?: boolean;
  placeholder?: string;
  /** Display-only model label shown in the picker chip (design parity). */
  modelLabel?: string;
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
  const model = props.modelLabel ?? "Composer 2.5 Fast";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      // The box: soft radius-lg chrome, hairline border that warms to the
      // accent on focus-within. surface-sunken keeps it a half-step recessed
      // from the canvas so it reads as an input well, not a card.
      // `@container/composer` (P3 §5): the toolbar adapts to the composer's own
      // slot width, not the viewport — so it reads right in a wide Mac window
      // and a narrow phone/drawer slot alike.
      className={cn(
        "@container/composer grid gap-2 p-3",
        "rounded-lg border border-border bg-surface-sunken",
        "transition-colors focus-within:border-accent",
      )}
    >
      {/*
        Autosize contract (FD2.U_AUTOSIZE): the Textarea primitive owns
        `field-sizing: content`. Inside the box it drops its own border /
        background / padding so it reads as one continuous well; the box
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
          "border-0 bg-transparent px-1 py-0",
          "focus:border-0 focus:outline-none",
        )}
      />
      {/* Toolbar row: add + model picker (left) · send (right). The add and
         model-picker are display affordances (design parity); they carry no
         run-lifecycle logic (F-R1). */}
      <div className="flex items-center gap-2">
        {/* §4c/HIG: size-11 (44×44pt) hit area; the glyph stays size-4. */}
        <button
          type="button"
          aria-label="Add attachment"
          className={cn(
            "flex size-11 shrink-0 items-center justify-center rounded-full",
            "bg-surface text-muted transition-colors",
            "cursor-pointer hover:bg-selected hover:text-fg",
          )}
        >
          <Plus className="size-4" aria-hidden="true" />
        </button>
        {/* §4c/HIG: min-h-11 floors the model picker to a 44pt-tall tap target;
           text + chevron sizing unchanged. */}
        <button
          type="button"
          aria-label="Choose model"
          title={model}
          className={cn(
            "inline-flex min-h-11 items-center gap-1 rounded-sm px-2 py-1",
            "text-sm text-muted transition-colors min-w-0",
            "cursor-pointer hover:bg-selected",
          )}
        >
          {/* In a narrow slot the long model label is hidden (chevron stays as
             the affordance); it returns once the composer slot is wide enough. */}
          <span className="truncate hidden @[20rem]/composer:inline">{model}</span>
          <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
        </button>
        <button
          type="submit"
          disabled={disabled}
          aria-label="Send"
          // Round accent puck — the one rationed accent in the composer.
          // btn-shine gives it the terracotta bezel + background shine (frozen).
          // §4c/HIG: size-11 (44×44pt) hit area; the arrow glyph stays size-5.
          className={cn(
            "btn-shine ml-auto flex size-11 shrink-0 items-center justify-center rounded-full",
            "text-white transition-opacity",
            "cursor-pointer disabled:cursor-not-allowed disabled:opacity-40",
          )}
        >
          <ArrowUp className="size-5" aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
