# Frontend UI Manual Validation Script

A QA-facing checklist for certifying a frontend release by hand. Every item
is framed as a binary YES/NO outcome, mirroring [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts)
so a manual failure is reproducible by an engineer via the linked automated
test.

Pairs with [docs/STYLE_GUIDE_FRONTEND.md](STYLE_GUIDE_FRONTEND.md) §11
(F-R1–F-R9), §13, §15, §19, §20 (test pyramid), §22 (anti-patterns
FE-AP-1…FE-AP-20), and the "Frontend Conventions" block in
[AGENTS.md](../AGENTS.md). Binary outcome framing comes from
[research/tdd_agentic_systems_prompt.md](../research/tdd_agentic_systems_prompt.md).

---

## §0. Pre-flight

### 0.1 Install and run

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
```

A backend runtime must be reachable for the chat-flow sections (§2.3–§2.15).
Without it, §2.1 (auth) and §2.2 (shell layout) are still meaningful.

### 0.2 Test users

WorkOS AuthKit. Provision one beta user and store credentials in your
password manager. Export them when running the e2e smoke for cross-checking:

```bash
export E2E_USER_EMAIL=beta@example.com
export E2E_AUTHENTICATED=1     # only if you have a stored session
```

See [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) lines 24
and 80 for how the spec gates on these.

### 0.3 Browser / device matrix


| Channel          | Device / viewport   | Notes                                    |
| ---------------- | ------------------- | ---------------------------------------- |
| Chrome (latest)  | Desktop 1440×900    | Primary                                  |
| Safari (latest)  | Desktop 1440×900    | Required for WebKit IME + iframe sandbox |
| Firefox (latest) | Desktop 1440×900    | Required for CSP nonce coverage          |
| Chrome           | iPhone 14 — 390×844 | Mirrors `e2e/smoke.spec.ts` line 272     |
| Chrome           | iPad — 768×1024     | Mirrors `e2e/smoke.spec.ts` line 290     |


Use Chrome DevTools "Toggle device toolbar" for the mobile/tablet rows.

### 0.4 Defect logging

File against the project's GitHub Issues. One ticket per failed binary check.
Title format: `[QA][<section>] <feature> — <observed>`. Attach the
"Evidence" artifact from the §2 template.

Severity rubric:


| Sev | Definition                                         | Examples                                              |
| --- | -------------------------------------------------- | ----------------------------------------------------- |
| S0  | Release blocker — security, data loss, full outage | CSP missing, JWT in localStorage, sign-in broken      |
| S1  | Major — core feature unusable                      | Streaming never starts, Send button never enables     |
| S2  | Minor — workaround exists                          | Tool card collapse glitch, sidebar misaligned on iPad |
| S3  | Polish — visual or copy nit                        | Wrong color shade, typo in placeholder                |


### 0.5 Conventions

- `[ ] YES  [ ] NO` — tick the result for each binary check.
- "Evidence" — capture a screenshot, HAR file, or console snippet before
marking PASS so an engineer can reproduce later.
- "Linked test" — the automated equivalent. When you fail a manual check,
open that test first; it likely needs to be tightened.

---

## §1. Smoke run order (15–20 min happy path)

Run this once at the start of every test session. If any step fails, stop
and file an S0/S1 before continuing to §2.

1. Open [http://localhost:3000](http://localhost:3000) in a fresh incognito window.
2. Click **Sign in with WorkOS**, complete sign-in.
3. Land on chat shell — verify your email shows in the header
  ([frontend/app/page.tsx](../frontend/app/page.tsx) lines 17–22).
4. Type "What is 2 + 2?", press ⌘↩ (mac) or Ctrl↩ (other).
5. Watch tokens stream into an assistant bubble.
6. Send "List the files in the current directory" — observe a tool card
  render with input/output ([frontend/components/tools/ToolCard.tsx](../frontend/components/tools/ToolCard.tsx)).
7. Send a prompt that triggers the generative canvas (see Appendix B.4).
  Confirm an iframe appears.
8. Click the theme toggle in the header — UI flips light/dark.
9. Click **Sign out** — return to the unauthenticated CTA.

Pass: [ ] YES  [ ] NO

---

## §2. Feature-by-feature deep checks

Each subsection uses this template:

```
Goal:           <one binary outcome question>
Pre-conditions: <state needed>
Steps:          <numbered actions>
Expected:       <observable outcomes>
Pass:           [ ] YES   [ ] NO
Evidence:       <screenshot | HAR | console snippet>
Linked test:    <path::name>
```

### 2.1 Auth flow (S3.7.1 · [frontend/app/page.tsx](../frontend/app/page.tsx), [frontend/middleware.ts](../frontend/middleware.ts))

**Goal:** Can an unauthenticated user sign in via WorkOS and land on the chat shell?

**Pre-conditions:** Fresh incognito window. Backend not required.

**Steps:**

1. Navigate to `/`.
2. Confirm the "Sign in with WorkOS" CTA renders.
3. Click the CTA — verify the URL transitions to a `*.authkit.`* or
  `*.workos.*` host.
4. Complete WorkOS sign-in.
5. Verify redirect back to `/` and the `<ChatShell userEmail={…}>` renders
  with your email in the header.
6. Click **Sign out** — verify you return to the CTA and the WorkOS
  session cookie is cleared (DevTools → Application → Cookies).

**Expected:** Six steps complete with no console errors and no failed
network requests other than the documented WorkOS redirect chain.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `Auth flow > unauthenticated user is redirected to sign-in`

### 2.2 Chat shell layout ([frontend/app/chat-shell.tsx](../frontend/app/chat-shell.tsx))

**Goal:** Does the chat shell render the three-row grid (header / messages / composer) and autoscroll on new messages?

**Pre-conditions:** Authenticated session.

**Steps:**

1. Land on the shell.
2. Confirm the empty state shows "What can I help you with?" ([chat-shell.tsx](../frontend/app/chat-shell.tsx) line 109).
3. Send 6 short messages in succession.
4. Watch the bottom of the message list stay in view as each lands.

**Expected:** The header is sticky, the composer is sticky, and the
messages region scrolls; `bottomRef.current?.scrollIntoView` keeps the
latest message visible.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/app/chat-shell.test.tsx](../frontend/app/chat-shell.test.tsx)

### 2.3 Composer (S3.8.5, F4 · [frontend/components/chat/Composer.tsx](../frontend/components/chat/Composer.tsx))

**Goal:** Does the composer correctly handle keyboard, IME, autosize, and accessibility?

**Pre-conditions:** Authenticated session.

**Steps:**

1. Click into the composer. Type a single character.
2. Verify the **Send** button enables (was disabled when empty).
3. Press ⌘↩ on macOS or Ctrl↩ elsewhere — the message submits and the
  textarea clears.
4. Type a multi-line draft using **Shift+Enter** to insert newlines —
  confirm no submit fires.
5. Switch your input source to a Japanese / Pinyin / Hangul IME (macOS
  System Settings → Keyboard, or the Chrome IME extension). Begin typing
   a candidate, then press Enter to confirm — verify the candidate is
   accepted and the message does NOT submit.
6. Paste 8 lines of text — verify the textarea grows to ~6 lines, then
  begins to scroll inside (autosize via `field-sizing: content`,
   [Composer.tsx](../frontend/components/chat/Composer.tsx) line 79).
7. Tab into the composer with the keyboard. Run VoiceOver / NVDA — the
  textarea should announce as "Compose message".
8. While `busy === true` (during a stream), the Send button shows a
  visually disabled state.

**Expected:** All eight steps pass. The Cmd+Enter / Ctrl+Enter / Shift+Enter
matrix matches the contract documented at [Composer.tsx](../frontend/components/chat/Composer.tsx) lines 1–18.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked tests:

- Unit: [frontend/components/chat/Composer.test.tsx](../frontend/components/chat/Composer.test.tsx)
- Static: [frontend/scripts/check_composer_keyboard.ts](../frontend/scripts/check_composer_keyboard.ts) (`pnpm check:composer`)

### 2.4 Streaming markdown (S3.8.1, F2 · [frontend/components/chat/StreamingMarkdown.tsx](../frontend/components/chat/StreamingMarkdown.tsx))

**Goal:** Do tokens stream incrementally into a polite ARIA live region without focus theft?

**Pre-conditions:** Authenticated; backend connected.

**Steps:**

1. Send "Write a short paragraph about the moon."
2. Watch tokens arrive incrementally (not all at once).
3. Verify the response renders in an `<article>` whose body has
  `aria-live="polite"` and `aria-atomic="false"` (DevTools → Elements,
   [StreamingMarkdown.tsx](../frontend/components/chat/StreamingMarkdown.tsx) lines 44–50).
4. While streaming, click into the composer and start typing — focus
  must NOT jump to the response bubble.
5. Confirm the model badge (when provided) carries `data-testid="model-badge"`
  and the step meter carries `data-testid="step-meter"`.
6. View page source — confirm there is no `dangerouslySetInnerHTML` on
  the streamed content.

**Expected:** All six steps pass. `aria-live` MUST be `polite`, never
`assertive` (FE-AP-5 auto-reject in [STYLE_GUIDE_FRONTEND.md §22](STYLE_GUIDE_FRONTEND.md)).

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/components/chat/StreamingMarkdown.test.tsx](../frontend/components/chat/StreamingMarkdown.test.tsx)

### 2.5 Run controls (S3.8.7, F3 · [frontend/components/chat/RunControls.tsx](../frontend/components/chat/RunControls.tsx))

**Goal:** Can the user stop a running agent and regenerate a response?

**Pre-conditions:** Authenticated; backend connected.

**Steps:**

1. Send "Write a long detailed analysis of quantum computing."
2. While streaming, locate the **Stop** button in the run controls
  toolbar (`role="toolbar"`, `aria-label="Run controls"`).
3. Click **Stop** — verify the stream halts and the composer re-enables
  within ~1 s.
4. After a complete assistant response, click **Regenerate** — confirm a
  new run starts using the same prior user message.
5. Click **Edit & resend** — verify the prior user message becomes
  editable in the composer.

**Expected:** Stop is disabled when `isRunning === false`. Regenerate and
Edit & resend always enabled. All three buttons keyboard-focusable.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `Run controls > stop button cancels a running agent`

### 2.6 Thread sidebar (S3.8.6, F1 · [frontend/components/chat/ThreadSidebar.tsx](../frontend/components/chat/ThreadSidebar.tsx))

**Goal:** Does the sidebar list threads, allow creating and selecting one, and collapse on mobile?

**Pre-conditions:** Authenticated. At least one prior thread persisted.

**Steps:**

1. Confirm the sidebar `<nav aria-label="Threads">` lists existing
  threads.
2. Click **New chat** — a fresh thread is created and becomes active
  (`aria-current="page"`).
3. Click another thread — confirm its messages load.
4. Resize the viewport to 390×844 (iPhone 14 / DevTools device toolbar)
  — verify the sidebar is hidden or collapsed (≤100 px wide).

**Expected:** Active thread visually distinct (uses `bg-accent-light`).
Threads list is keyboard-navigable via Tab.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `Mobile responsive > thread sidebar is hidden or collapsed on mobile`

### 2.7 Theme toggle (S3.8.8, F9 · [frontend/components/chat/ThemeToggle.tsx](../frontend/components/chat/ThemeToggle.tsx))

**Goal:** Does dark/light toggle work, persist, and avoid FOUC?

**Steps:**

1. With a fresh window, observe the initial theme (system default).
2. Click the toggle in the header.
3. Verify `<html>` gains/loses the `dark` class or `data-theme="dark"`.
4. Reload — the chosen theme persists (next-themes localStorage key).
5. Hard reload with the browser cache cleared — confirm there is no
  flash of the wrong theme on first paint (FOUC).
6. Tab to the toggle — verify the focus ring is visible and the
  `aria-label` switches between "Switch to light theme" and
   "Switch to dark theme".

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `Theme toggle > theme toggle switches between light and dark`

### 2.8 Tool cards (S3.8.2, F5 · [frontend/components/tools/ToolCard.tsx](../frontend/components/tools/ToolCard.tsx))

**Goal:** Do tool calls render as collapsible cards with input/output?

**Pre-conditions:** Authenticated; backend with tools enabled.

**Steps:**

1. Send a prompt that triggers a tool call (Appendix B.2: "List files in
  the current directory").
2. Observe the `<details>` card with the tool name and status
  ("running" → "completed").
3. Click the `<summary>` to collapse and re-expand.
4. Verify input JSON renders pretty-printed in a `<pre>`.
5. Verify output renders as a string when string-typed, otherwise as
  pretty JSON.
6. Trigger a tool error path (Appendix B.5) — confirm status shows
  "errored" and the card stays open by default.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked story: [frontend/components/tools/ToolCard.stories.tsx](../frontend/components/tools/ToolCard.stories.tsx)

### 2.9 Generative UI (S3.8.3, F13 · [frontend/components/generative/SandboxedCanvas.tsx](../frontend/components/generative/SandboxedCanvas.tsx), [frontend/components/generative/PyramidPanel.tsx](../frontend/components/generative/PyramidPanel.tsx))

**Goal:** Are static generative panels rendered inline and open-ended canvases isolated in a sandboxed iframe?

**Pre-conditions:** Authenticated; backend emits an `analysis_output`
that targets `useComponent`.

**Steps:**

1. Trigger a `PyramidPanel` (Appendix B.4a) — verify it renders inline
  (no iframe).
2. Trigger a `SandboxedCanvas` (Appendix B.4b) — verify an `<iframe>`
  appears.
3. Inspect the iframe in DevTools → Elements:
  - `sandbox="allow-scripts"` — exact value, no other tokens
   (FE-AP-4 auto-reject).
  - `srcdoc` is set; there is no `src` attribute pointing at an external
  origin.
  - There is no `dangerouslySetInnerHTML` anywhere on the parent
  (FE-AP-12).
4. Run `pnpm check:iframe` from `frontend/` — verify exit code 0.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked tests:

- Unit: [frontend/components/generative/SandboxedCanvas.test.tsx](../frontend/components/generative/SandboxedCanvas.test.tsx)
- Static: [frontend/scripts/check_iframe_sandbox.ts](../frontend/scripts/check_iframe_sandbox.ts)

### 2.10 Trust badge (F-R7 · [frontend/lib/trust-view/identity.ts](../frontend/lib/trust-view/identity.ts))

**Goal:** Does the trust view display signed `AgentFacts` and reject tampered envelopes?

**Steps:**

1. Send any prompt and let it complete.
2. Locate the agent identity badge (model, version, capability).
3. In DevTools → Sources, set a breakpoint inside the trust verifier and
  mutate the envelope payload before verification (or use the network
   override feature to swap the response body).
4. Reload — the badge must now show an "untrusted" / "unverified" state
  or refuse to render.

**Expected:** Tamper produces a clearly degraded UI; signed envelopes
remain `Readonly` (FE-AP-6).

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/lib/trust-view/identity.test.ts](../frontend/lib/trust-view/identity.test.ts)

### 2.11 Observability — `trace_id` provenance and console silence

**Goal:** Does every server request carry a `trace_id` minted by the Python runtime, and is the production console silent?

**Steps:**

1. Open DevTools → Network. Send a chat message.
2. Inspect the `/api/run/stream` response headers — confirm `trace_id`
  (or equivalent) is present.
3. Confirm the same `trace_id` does NOT appear in any **request** body
  sent from the browser (FE-AP-7).
4. Switch to a production build (`pnpm build && pnpm start`).
5. Open Console and exercise §1 happy path — there must be zero
  `console.log` / `console.warn` / `console.error` from app code.
   `console.`* is forbidden outside `frontend/lib/adapters/`
   (STYLE_GUIDE_FRONTEND.md §17, Rule O3).

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/lib/adapters/_logger.test.ts](../frontend/lib/adapters/_logger.test.ts)

### 2.12 Mobile responsiveness

**Goal:** Is the layout usable on iPhone 14 (390×844) and iPad (768×1024)?

**Steps:**

1. iPhone 14 viewport — composer visible, not horizontally clipped, the
  send button reachable without horizontal scroll.
2. iPhone 14 viewport — sidebar hidden or collapsed (≤100 px wide).
3. iPad viewport — sidebar visible OR a clear hamburger toggle exposes
  it.
4. All touch targets (Send, theme toggle, sidebar items, run controls)
  ≥ 44×44 px (DevTools measure tool).

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `Mobile responsive`

### 2.13 Accessibility (WCAG 2.2 AA · STYLE_GUIDE_FRONTEND.md §13)

**Goal:** Can a keyboard- and screen-reader-only user complete a full chat round-trip?

**Steps:**

1. Disconnect the mouse. Tab from the page top — verify the order is
  header → sidebar → messages → composer → Send.
2. Focus rings are visible on every interactive element.
3. Activate VoiceOver (macOS: ⌘F5) or NVDA (Windows). Send a message
  using the keyboard.
4. Confirm the response is announced after streaming pauses, NOT
  interrupted on every token (polite live region).
5. Run `pnpm check:axe-a11y` from `frontend/` — exit code 0, zero
  violations.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked tests:

- Static: [frontend/scripts/check_axe_a11y.ts](../frontend/scripts/check_axe_a11y.ts)
- ESLint: `eslint-plugin-jsx-a11y` in [frontend/package.json](../frontend/package.json)

### 2.14 Performance

**Goal:** Is TTFT (time to first token) under 500 ms p50 and Lighthouse healthy?

**Steps:**

1. With backend warm, open DevTools → Performance. Send a short prompt
  ("What is 1+1?").
2. Measure TTFT — start when ⌘↩ fires, stop when the first response
  token paints. Repeat 5×, take the median.
3. Median TTFT ≤ 500 ms.
4. Run Lighthouse (DevTools → Lighthouse → Performance + Accessibility
  - Best Practices) on the chat page:
  - Performance ≥ 90
  - Accessibility ≥ 95
  - Best Practices ≥ 95
5. Run `pnpm check:bundle-budget` from `frontend/` — exit code 0.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked tests:

- E2E: [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) `TTFT performance > first token arrives within 500ms`
- Static: [frontend/scripts/check_bundle_budget.ts](../frontend/scripts/check_bundle_budget.ts)

### 2.15 Error and resilience

**Goal:** Do network failures and server errors surface gracefully with `trace_id` preserved?

**Steps:**

1. Send a message; while streaming, throttle to "Offline" in DevTools
  → Network. Confirm an inline error appears and the composer re-enables.
2. Restore network. Use DevTools "Block request URL" on `/api/run/stream`
  to simulate 401 — confirm the user is routed to the auth flow.
3. Use a dev override to return 429 from `/api/run/stream` — confirm a
  rate-limit message appears with a retry hint.
4. Use a dev override to return 500 — confirm a generic error appears
  and the response body includes the original `trace_id` so support can
   correlate.

Pass: [ ] YES  [ ] NO
Evidence: ___
Linked test: [frontend/lib/transport/sse_client.test.ts](../frontend/lib/transport/sse_client.test.ts)

---

## §3. Trust and security visual checks

DevTools-driven checks that map directly to the auto-reject anti-patterns
in [docs/STYLE_GUIDE_FRONTEND.md §22](STYLE_GUIDE_FRONTEND.md). Each item
cites the FE-AP number and the closest F-R rule from §11.

### 3.1 Strict CSP, no inline (FE-AP-19 · F-R6)

**Steps:**

1. DevTools → Network → main document → Headers.
2. Confirm `content-security-policy` is present.
3. Confirm it contains NEITHER `'unsafe-inline'` NOR `'unsafe-eval'` in
  the production build (built with `pnpm build && pnpm start`).
4. Confirm `script-src` and `style-src` carry `'nonce-…'`.
5. Confirm `frame-ancestors 'none'` and `object-src 'none'`.
6. Run `pnpm check:csp` — exit code 0.

Pass: [ ] YES  [ ] NO
Source: [frontend/middleware.ts](../frontend/middleware.ts) lines 39–53; [frontend/scripts/check_csp_strict.ts](../frontend/scripts/check_csp_strict.ts).

### 3.2 Iframe sandbox is `allow-scripts` only (FE-AP-4 · F-R6)

**Steps:**

1. Trigger a generative canvas (Appendix B.4b).
2. DevTools → Elements → select the `<iframe>`.
3. Confirm `sandbox="allow-scripts"` exact (no `allow-same-origin`,
  no `allow-top-navigation`, no `allow-forms`).
4. Confirm content arrived via `srcdoc`, not `src` to a third party.
5. Run `pnpm check:iframe` — exit code 0.

Pass: [ ] YES  [ ] NO
Source: [frontend/components/generative/SandboxedCanvas.tsx](../frontend/components/generative/SandboxedCanvas.tsx) line 24.

### 3.3 No JWT in browser storage (F-R5)

**Steps:**

1. After sign-in, DevTools → Application → Local Storage and Session
  Storage.
2. Search for substrings `eyJ`, `jwt`, `token`, `bearer`. Expect zero
  matches in app-owned keys.
3. Confirm the WorkOS session lives in an HttpOnly cookie (Application
  → Cookies; "HttpOnly" column = checkmark).
4. Run `pnpm check:jwt-storage` — exit code 0.

Pass: [ ] YES  [ ] NO
Source: [frontend/scripts/check_jwt_storage.ts](../frontend/scripts/check_jwt_storage.ts).

### 3.4 No `dangerouslySetInnerHTML` on agent output (FE-AP-12 · F-R6)

**Steps:**

1. View page source on a chat with a tool card and a generative panel.
2. Search for `dangerouslySetInnerHTML` — expect zero matches.

Pass: [ ] YES  [ ] NO
Source: [frontend/components/chat/StreamingMarkdown.tsx](../frontend/components/chat/StreamingMarkdown.tsx) lines 10–12 (documented contract).

### 3.5 `trace_id` originates server-side (FE-AP-7 · F-R7)

**Steps:**

1. DevTools → Network. Send a message.
2. Inspect every outbound request body to `/api/`**. Confirm none
  contains a client-generated `trace_id`.
3. Inspect the corresponding response — confirm `trace_id` is present.

Pass: [ ] YES  [ ] NO
Source: [docs/STYLE_GUIDE_FRONTEND.md §22 FE-AP-7](STYLE_GUIDE_FRONTEND.md).

### 3.6 No secrets in `NEXT_PUBLIC_*` (FE-AP-18 · F-R8)

**Steps:**

1. Inspect the runtime bundle (View Page Source on the production build,
  search for `NEXT_PUBLIC`_).
2. Confirm only non-sensitive values (e.g., the WorkOS public client ID,
  public app URL).
3. Run `pnpm check:secrets-env` — exit code 0.

Pass: [ ] YES  [ ] NO
Source: [frontend/scripts/check_secrets_in_public_env.ts](../frontend/scripts/check_secrets_in_public_env.ts).

### 3.7 No SDK leak outside `adapters/` (FE-AP-13 · F-R2)

**Steps:**

1. Run `pnpm test:arch` from `frontend/` — exit code 0.
2. Spot-check: `rg "@copilotkit|@workos-inc|@langchain"` in
  `frontend/components/`, `frontend/lib/wire/`, `frontend/lib/ports/` —
   expect zero hits (only `frontend/lib/adapters/` is allowed).

Pass: [ ] YES  [ ] NO

### 3.8 Sealed envelopes are read-only (FE-AP-6 · F-R7)

**Steps:**

1. In DevTools console, attempt to mutate a verified envelope:
  `Object.assign(window.__lastAgentFacts ?? {}, { status: "active" })`
   (only available with the trust-view debug shim).
2. Confirm a TypeError or no-op (frozen object), and that the badge
  refuses to honor the mutation.

Pass: [ ] YES  [ ] NO
Source: [frontend/lib/trust-view/identity.ts](../frontend/lib/trust-view/identity.ts).

### 3.9 Other security headers

**Steps:**

1. Confirm `strict-transport-security: max-age=63072000; includeSubDomains; preload`.
2. Confirm `x-content-type-options: nosniff`.
3. Confirm `x-frame-options: DENY`.
4. Confirm `referrer-policy: strict-origin-when-cross-origin`.
5. Confirm `permissions-policy` denies camera, microphone, geolocation,
  payment.

Pass: [ ] YES  [ ] NO
Source: [frontend/middleware.ts](../frontend/middleware.ts) lines 86–93.

---

## §4. Cross-browser / cross-device matrix

Run §1 (smoke) plus §2.3 (composer), §2.4 (streaming), §2.7 (theme),
§2.8 (tool cards), §2.9 (generative UI), and §2.13 (a11y) on each cell.


| Feature            | Chrome desktop | Safari desktop | Firefox desktop | iPhone 14 (390×844) | iPad (768×1024) |
| ------------------ | -------------- | -------------- | --------------- | ------------------- | --------------- |
| 1 Smoke happy path | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.1 Auth           | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.3 Composer       | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.4 Streaming      | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.5 Run controls   | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.6 Sidebar        | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.7 Theme          | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.8 Tool cards     | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.9 Generative UI  | [ ]            | [ ]            | [ ]             | [ ]                 | [ ]             |
| 2.13 A11y          | [ ]            | [ ]            | n/a             | n/a                 | n/a             |


Tick = PASS. Empty = NOT RUN. Strike = FAIL (file ticket, link in
comments).

---

## §5. Sign-off

Ship only when all five gates are green. Tick each on the release ticket.

- **Gate 1 — Automation precondition.** Appendix A one-liner exits 0
on the release branch.
- **Gate 2 — Manual feature checks.** Every box in §2.1 through
§2.15 is YES on at least Chrome desktop.
- **Gate 3 — Trust and security.** §3.1 through §3.9 are YES.
- **Gate 4 — Cross-browser matrix.** §4 has at least one row per
browser/device cell ticked or explicitly marked n/a.
- **Gate 5 — Staging e2e.** `pnpm test:e2e` passes against staging
with `E2E_AUTHENTICATED=1`.

QA sign-off: ____________________  Date: __________
Eng on-call:  ____________________  Date: __________

---

## Appendix A — Automated precondition gate

These are the engineer-side gates QA assumes are green before manual
work starts. Run from `frontend/`.


| #   | Command                     | What it proves                                    |
| --- | --------------------------- | ------------------------------------------------- |
| 1   | `pnpm typecheck`            | No TypeScript errors                              |
| 2   | `pnpm lint`                 | ESLint + jsx-a11y clean                           |
| 3   | `pnpm test`                 | Vitest unit + component + adapter tests pass      |
| 4   | `pnpm test:arch`            | Layering rules F-R1…F-R9 intact                   |
| 5   | `pnpm check:wire-types`     | TS wire types match `openapi.yaml`                |
| 6   | `pnpm wire-schema-snapshot` | Zod kernels match Python baseline                 |
| 7   | `pnpm check:csp`            | Strict CSP, no `unsafe-inline` / `unsafe-eval`    |
| 8   | `pnpm check:iframe`         | Generative iframe sandbox is `allow-scripts` only |
| 9   | `pnpm check:composer`       | Composer keyboard contract (⌘↩, Shift+Enter, IME) |
| 10  | `pnpm check:secrets-env`    | No secrets in `NEXT_PUBLIC`_*                     |
| 11  | `pnpm check:jwt-storage`    | JWT not in `localStorage` / `sessionStorage`      |
| 12  | `pnpm check:bundle-budget`  | First-load JS within budget                       |
| 13  | `pnpm check:axe-a11y`       | Static a11y ruleset pass                          |
| 14  | `pnpm check:sprint-story`   | Sprint story acceptance criteria met              |


One-liner that mirrors CI:

```bash
pnpm typecheck && pnpm lint && pnpm test && pnpm test:arch \
  && pnpm check:wire-types && pnpm check:csp && pnpm check:iframe \
  && pnpm check:composer && pnpm check:secrets-env && pnpm check:jwt-storage \
  && pnpm check:bundle-budget && pnpm check:axe-a11y
```

Optional, requires a running app:

```bash
pnpm test:e2e
```

---

## Appendix B — Test data and fixtures

Reusable prompts that reliably exercise each branch. Copy verbatim into
the composer.

### B.1 Plain markdown response

> Write a short paragraph about the moon.

Triggers: §2.4 streaming markdown.

### B.2 Tool call (file listing)

> List the files in the current directory.

Triggers: §2.8 tool cards. Produces a `ToolCallRendererRequest` with
status `running` → `completed`.

### B.3 Long stream (for stop / regenerate)

> Write a detailed analysis of quantum computing, at least eight paragraphs.

Triggers: §2.5 run controls (Stop, Regenerate). Stream stays open long
enough to click Stop.

### B.4 Generative UI

**a. Static panel (`PyramidPanel`):**

> Show me the trust-pyramid diagram for the current user.

Triggers: §2.9 inline generative panel.

**b. Sandboxed canvas (`SandboxedCanvas`):**

> Render an interactive sine-wave visualizer in a sandbox.

Triggers: §2.9 iframe sandbox check.

### B.5 Tool error path

> Run `cat /etc/shadow` and show the output.

Triggers: §2.8 errored tool card. The shell tool validator should reject
the command (defense in depth, see `AGENTS.md` §"Security Model").

### B.6 Auth / rate-limit / 5xx simulation

DevTools → Network:

- **401**: right-click `/api/run/stream` → Block request URL → resend.
- **429**: use a Chrome extension like "Requestly" or `mitmproxy` to
rewrite the response status.
- **500**: same as 429 with a 500 body. Confirm `trace_id` is preserved
in the rendered error.

Triggers: §2.15 error and resilience.

---

## Appendix C — Glossary and references

- **Binary outcome** — every check answers a single YES/NO question.
See [research/tdd_agentic_systems_prompt.md](../research/tdd_agentic_systems_prompt.md).
- **F-R1…F-R9** — frontend invariants in
[docs/STYLE_GUIDE_FRONTEND.md §11](STYLE_GUIDE_FRONTEND.md).
- **FE-AP-1…FE-AP-20** — frontend anti-patterns in
[docs/STYLE_GUIDE_FRONTEND.md §22](STYLE_GUIDE_FRONTEND.md).
Auto-reject set used by the frontend code reviewer: FE-AP-4, FE-AP-6,
FE-AP-7, FE-AP-12, FE-AP-18, FE-AP-19.
- **Test pyramid** — five tiers in
[docs/STYLE_GUIDE_FRONTEND.md §20](STYLE_GUIDE_FRONTEND.md).
- **TTFT** — time to first token. Target < 500 ms p50, threshold check
in [frontend/e2e/smoke.spec.ts](../frontend/e2e/smoke.spec.ts) line 314.
- **Sprint refs (S3.7.x / S3.8.x / S4.3.2)** — referenced in component
doc-comments; see the sprint planning docs for the full text.

Related canonical docs:

- [docs/STYLE_GUIDE_FRONTEND.md](STYLE_GUIDE_FRONTEND.md) — canonical
rules and anti-patterns this checklist enforces.
- [docs/Architectures/FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md)
— four-ring architecture context.
- [docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md)
— adapter / port boundary referenced in §3.7.
- [docs/Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md)
— wire/trust-view kernel context for §2.10 and §3.5.
- [AGENTS.md](../AGENTS.md) — "Frontend Conventions" block.

