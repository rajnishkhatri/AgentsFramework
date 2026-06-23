---
title: P4 — scroll-to-bottom + message actions (hover desktop / long-press touch)
status: in-progress
created: 2026-06-23
owner: Rajnish Khatri
parent: native_wrap_ui_redesign.plan.md
phase: P4 (native-feel, §4a/§4c/§6 remainder)
---

# P4 — Scroll-to-bottom button + per-message actions

## Context

P4 (native-feel) is the last web-actionable phase of the native-wrap redesign; the
parent plan (`native_wrap_ui_redesign.plan.md` §7:303) names its remaining items as
**scroll-to-bottom button**, **long-press message actions**, and keyboard-pinned composer.
Per the 2026-06-23 scope decision we tackle the **scroll-to-bottom button** and **message
actions** now (copy/regenerate, hover on desktop + long-press on touch, per §6 "hover
toolbar on desktop, long-press on mobile"); the keyboard-pinned composer is **deferred** —
the parent flags it P6-coupled (needs the Capacitor safe-area plugin to do for real).

**Intended outcome:** during/after streaming the user can (a) jump back to the latest
message when scrolled up, and (b) copy an assistant answer or regenerate it — via a hover
toolbar on pointer-fine devices and a long-press menu on touch — all pre-wrap-safe (works
in a plain browser, inherits into Tauri/Capacitor for free).

## Ground truth (verified on disk)

- **Scroll container:** `app/chat-shell.tsx:556` `<main className="overflow-y-auto p-3 sm:p-4">`.
  Auto-scroll today is unconditional: `useEffect(() => bottomRef.scrollIntoView({behavior:"smooth"}), [turns])`
  (`:407`). There is **no scroll-position tracking** anywhere (`grep scrollTop/IntersectionObserver` = none).
- **Messages:** turns map to a user bubble + `<AssistantMessage>` (defined inline at
  `chat-shell.tsx:183`); the assistant root is `data-testid="assistant-message"` (`:207`),
  a `grid gap-2`. Answer text lives in `assistant.segments` (kind `"text"`).
- **Copy pattern to reuse:** `components/chat/CodeBlock.tsx:20-47` — `navigator.clipboard.writeText`
  + a `copied` flag + `data-testid="copy-code"` + `aria-label`. Mirror this for message copy.
- **Primitives available:** `DropdownMenu*` (`components/ui/dropdown-menu.tsx`) for the
  long-press menu; `Button` for the toolbar; `Toast` (sonner) for feedback if wanted.
- **Regenerate seam:** `send(body)` exists (`Composer onSend={send}`). Regenerate = re-send the
  turn's `user` text. A `run/cancel` route exists for the stop control already.
- **Touch targets:** §4c shipped 44pt across chrome — new controls must keep `size-11`/`min-h-11`.
- **e2e to keep green:** `e2e/chat-shell.spec.ts`, `streaming.spec.ts`, `smoke.spec.ts`,
  `run-controls.spec.ts` assert on `assistant-message` / streaming. New affordances must not
  move those selectors; add new `data-testid`s rather than restructure.

## Scope of changes

### A. Scroll-to-bottom button
1. **`useStickToBottom` hook** (new, `lib/hooks/use_stick_to_bottom.ts`): track whether the
   scroll container is within ~80px of the bottom. Return `{ ref, isAtBottom, scrollToBottom }`.
   Attach an onScroll listener (passive) computing `scrollHeight - scrollTop - clientHeight`.
2. **Gate auto-scroll on stickiness:** change the `[turns]` effect (`chat-shell.tsx:407`) so it
   only auto-scrolls when `isAtBottom` — otherwise a user reading history isn't yanked down
   mid-stream. (This is the correct behavior the current unconditional scroll lacks.)
3. **The button:** a floating circular `size-11` control, bottom-center above the composer,
   shown only when `!isAtBottom && turns.length > 0`. Lucide `ArrowDown`, `aria-label="Scroll to
   latest"`, `data-testid="scroll-to-bottom"`. Token-styled (`bg-surface` + border + shadow),
   `motion-reduce` safe. Click → `scrollToBottom({behavior:"smooth"})`.

### B. Message actions (copy + regenerate)
1. **`MessageActions` component** (new, `components/chat/MessageActions.tsx`): given the answer
   text + an `onRegenerate`, render:
   - **Desktop (hover):** a small inline toolbar of `Button` (ghost, `size-11` hit area) —
     Copy + Regenerate — revealed on `group-hover` of the message, **gated `@media (hover:hover)`**
     (a `hover-only` utility / `[@media(hover:hover)]:` so it never sticks on touch).
   - **Touch (long-press):** a `DropdownMenu` opened by a long-press (pointerdown + ~500ms timer,
     cancel on move/up) anywhere on the assistant message, gated to coarse pointers. Items: Copy,
     Regenerate. `data-testid="message-actions-menu"`.
   - Copy mirrors CodeBlock: `navigator.clipboard.writeText(answerText)` + transient "Copied".
2. **Wire into `AssistantMessage`:** add `group` to the assistant root; render `<MessageActions>`
   at the end of the grid. Extract the answer text from `assistant.segments` (text kinds joined)
   — reuse/extend the `synthesizeFallbackAnswer` logic if it already concatenates text, else a
   tiny local `answerText(assistant)` helper. Only render when there's settled text (not while
   the very first tokens are mid-stream and status==="streaming" with empty text).
3. **Regenerate:** lift an `onRegenerate(turnId)` from `chat-shell` into `AssistantMessage` →
   `MessageActions`. Implementation: re-`send(turn.user)` (and, if a run is live, it's disabled).
   Keep it minimal — no branch/edit in this pass (those are bigger §6 items).

### C. Tests
- Component test for `useStickToBottom` (jsdom: simulate scroll metrics) and `MessageActions`
  (copy writes clipboard, regenerate fires callback, long-press opens menu).
- Keep existing e2e green; add `data-testid` assertions only if a spec needs them.

## Files
- `frontend/lib/hooks/use_stick_to_bottom.ts` (new)
- `frontend/components/chat/MessageActions.tsx` (new)
- `frontend/app/chat-shell.tsx` (scroll gating + button + wire actions/regenerate)
- `frontend/lib/hooks/use_stick_to_bottom.test.ts`, `frontend/components/chat/MessageActions.test.tsx` (new)

## Verification
1. `pnpm typecheck` clean; `pnpm vitest run` — new tests pass, no regressions.
2. Preview (`/mockchat`): scroll up mid-conversation → button appears; click → returns to
   bottom; stream while scrolled up → NOT yanked down; at bottom → button hidden.
3. Hover a message on desktop → Copy/Regenerate toolbar; click Copy → clipboard has the answer.
4. Resize to `mobile` / coarse pointer → toolbar hidden, long-press opens the menu.
5. `prefers-reduced-motion` respected; 44pt hit areas confirmed via inspect.

## Out of scope (this pass)
- Keyboard-pinned composer (P6-coupled — needs Capacitor plugin).
- Edit / branch message actions (larger §6 work; copy + regenerate only here).
- Desktop right-detail panel (P-future).
