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
import { ArrowUp, Check, ChevronDown, Plus } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { AUTO_MODEL } from "@/lib/translators/ui_input_to_agent_request";
import type { components } from "@/lib/wire-types";
import { cn } from "@/lib/utils";

type ModelInfo = components["schemas"]["ModelInfo"];

export function Composer(props: {
  /** `selectedModel` is the picker choice ("Auto" or a registry model name). */
  onSend: (body: string, selectedModel?: string) => void | Promise<void>;
  busy?: boolean;
  placeholder?: string;
  /**
   * Model-picker catalog (from useAvailableModels). When empty, the picker
   * offers Auto only — the fail-safe path, so composing is never blocked.
   */
  models?: ReadonlyArray<ModelInfo>;
  /** Controlled selection ("Auto" or a model name). Defaults to "Auto". */
  selectedModel?: string;
  /** Lifts the selection to the owner (ChatShell), so `send` can pass it. */
  onSelectModel?: (model: string) => void;
}): React.JSX.Element {
  const [body, setBody] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement>(null);

  const models = props.models ?? [];
  const selectedModel = props.selectedModel ?? AUTO_MODEL;

  function submit(): void {
    const trimmed = body.trim();
    if (!trimmed || props.busy) return;
    void props.onSend(trimmed, selectedModel);
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
  // The chip shows the active choice: a pinned model name, or "Auto".
  const chipLabel = selectedModel === AUTO_MODEL ? "Auto" : selectedModel;

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
        rows={2}
        value={body}
        placeholder={props.placeholder ?? "Send a message… (⌘↩ for newline)"}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={onKeyDown}
        aria-label="Compose message"
        // Floor at two visible lines (2 × 18px/1.6lh ≈ 3.6rem) so the second
        // line of entered text is never clipped at rest; `field-sizing: content`
        // still grows it from there up to the primitive's ~6-line max.
        className={cn(
          "border-0 bg-transparent px-1 py-0 min-h-[3.6rem]",
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
        {/* Model picker (Task #4): real dropdown — Auto (default) + the fetched
           registry models. Selecting one pins it for the run; the choice rides
           input.pinned_model and is honored by the backend router's pin branch.
           §4c/HIG: min-h-11 floors a 44pt-tall tap target. */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              data-testid="model-picker-trigger"
              aria-label="Choose model"
              title={`Model: ${chipLabel}`}
              className={cn(
                "inline-flex min-h-11 items-center gap-1 rounded-sm px-2 py-1",
                "text-sm text-muted transition-colors min-w-0",
                "cursor-pointer hover:bg-selected",
                "data-[state=open]:bg-selected data-[state=open]:text-fg",
              )}
            >
              {/* In a narrow slot the label is hidden (chevron stays as the
                 affordance); it returns once the composer slot is wide enough. */}
              <span className="truncate hidden @[20rem]/composer:inline">
                {chipLabel}
              </span>
              <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-[12rem]">
            <ModelMenuItem
              label="Auto"
              hint="Let the agent route per step"
              testid="model-option-Auto"
              checked={selectedModel === AUTO_MODEL}
              onSelect={() => props.onSelectModel?.(AUTO_MODEL)}
            />
            {models.length > 0 ? (
              <DropdownMenuSeparator />
            ) : null}
            {models.map((m) => (
              <ModelMenuItem
                key={m.name}
                label={m.name}
                hint={m.tier}
                testid={`model-option-${m.name}`}
                checked={selectedModel === m.name}
                onSelect={() => props.onSelectModel?.(m.name)}
              />
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
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

/** One model row in the picker: name + tier hint, with a check on the active one. */
function ModelMenuItem(props: {
  label: string;
  hint: string;
  checked: boolean;
  onSelect: () => void;
  testid?: string;
}): React.JSX.Element {
  return (
    <DropdownMenuItem
      onSelect={props.onSelect}
      className="justify-between gap-3"
      aria-checked={props.checked}
      role="menuitemradio"
      {...(props.testid ? { "data-testid": props.testid } : {})}
    >
      <span className="flex min-w-0 items-center gap-2">
        <Check
          className={cn(
            "size-3.5 shrink-0",
            props.checked ? "opacity-100" : "opacity-0",
          )}
          aria-hidden="true"
        />
        <span className="truncate">{props.label}</span>
      </span>
      <span className="shrink-0 text-xs text-muted">{props.hint}</span>
    </DropdownMenuItem>
  );
}
