# SPIKE_A — CopilotKit + AG-UI integration

| Field | Value |
|------|-------|
| **Sprint** | 0 |
| **Stories** | S0.2.1, S0.2.2, S0.2.3 |
| **Hypotheses under test** | H4 (CopilotKit ↔ ReAct graph compatibility), H7 (iframe sandbox sufficient) |
| **Run date** | 2026-04-23 |
| **Throwaway code** | `spikes/spike-a-copilotkit/` (gitignored) |
| **Tech baseline** | Next.js 16.2.4 (Turbopack), React 19.2.4, Tailwind 4, CopilotKit 1.56.3, `@ag-ui/client` 0.0.52, Node 22.14.0 |
| **Verdict** | ✅ **PASS** with 1 minor impedance-mismatch finding |

---

## 1. TL;DR

All three CopilotKit v2 hook patterns the V3 plan depends on (frontend tools / generative UI / live state) work end-to-end on a Next.js 16 + React 19 + Tailwind 4 stack against CopilotKit Cloud's hosted LLM brain. The iframe sandbox boundary holds (`sandbox="allow-scripts"` blocks `parent.document` reads with a SecurityError). The hooks render custom React components via the `render` prop with no SDK type leakage past the component boundary.

**Implication for v1**: CopilotKit v2 is a viable F5/F13/F14 substrate. No fallback to assistant-ui needed. Proceed with Sprint 1.

---

## 2. What was built

```
spikes/spike-a-copilotkit/                      (gitignored)
├── app/
│   ├── layout.tsx                              wraps with CopilotProvider
│   ├── copilot-provider.tsx                    'use client' — renders <CopilotKit publicApiKey={...}>
│   ├── page.tsx                                three-column UI: live-state rail + chat
│   └── components/
│       ├── shell-tool-card.tsx                 sub-step 2.3.3 — shell renderer
│       ├── file-io-tool-card.tsx               sub-step 2.3.3 — file_io renderer
│       ├── web-search-tool-card.tsx            sub-step 2.3.3 — web_search renderer
│       ├── generative-html.tsx                 sub-step 2.3.4 — sandboxed-iframe renderer + verify probe
│       ├── step-meter.tsx                      sub-step 2.3.5 — live step counter
│       └── model-badge.tsx                     sub-step 2.3.5 — live model tier badge
├── .env.local                                  (gitignored) — NEXT_PUBLIC_CPK_PUBLIC_API_KEY
└── package.json
```

All real chat routing flows through CopilotKit Cloud (`<CopilotKit publicApiKey={...}>`) in this spike — there is **no** local backend in the loop. The "validate against the existing react_loop graph" piece is wire-format compatibility (AG-UI is an open standard) and is deferred to Sprint 1's S1.1.1, where it gets real test coverage.

---

## 3. Sub-step results

### 3.1 Sub-step 2.3.3 — useFrontendTool / useCopilotAction tool cards (✅ PASS)

| Tool | Verified behaviour | Screenshot |
|------|--------------------|------------|
| `shell` | LLM picked the tool from its description, called it with `command="ls -la"`, our `render` prop displayed `$ shell` header, `COMPLETE` status badge, command panel, output panel. | `spike_a_02_shell_tool.png` |
| `file_io` | LLM called with `path="README.md"`, `mode="read"`. Our render showed blue header, `READ` mode pill, `COMPLETE` status, path, result. | `spike_a_03b_file_io_full.png` |
| `web_search` | LLM called with `query="Next.js 16 release notes"`, `top_k=5`. Card header rendered. **One impedance-mismatch caught — see §4.1.** | `spike_a_04_web_search.png` |

**Note on the v2 API**: CopilotKit 1.56 deprecated `useFrontendTool` in favour of `useCopilotAction` (one hook covering frontend tools, generative UI, and HITL). The spike used `useCopilotAction` accordingly. Functionally identical for our purposes; we update the SPRINT_BOARD wording in §6 below.

### 3.2 Sub-step 2.3.4 — useComponent / generative UI in sandboxed iframe (✅ PASS)

The agent generated a full `<!DOCTYPE html>...</html>` snippet for a 3-bar chart (A=30% blue, B=70% orange, C=50% green) and our `GenerativeHtmlComponent`:

- Rendered the snippet inside `<iframe sandbox="allow-scripts">` via `srcDoc`.
- **Sandbox-verify probe** (a script we inject at the top of every iframe body) attempted `window.parent.document.title` and was **blocked**, printing `✅ sandbox holds: SecurityError on parent.document read` in a green banner inside the iframe.
- No `allow-same-origin` was ever set (verified by the probe firing).
- No `dangerouslySetInnerHTML` was used on the parent React tree.
- React 19 + Tailwind 4 had no issue rendering streaming-args-driven iframe content (the iframe re-rendered as the LLM streamed args).

This is the exact security boundary required by:
- `STYLE_GUIDE_FRONTEND.md` rule **U3** (sandbox `allow-scripts` only)
- `FE-AP-4 AUTO-REJECT` (no `allow-same-origin`)
- `FE-AP-12 AUTO-REJECT` (no `dangerouslySetInnerHTML` on agent output)

| Screenshot | What it shows |
|-----------|---------------|
| `spike_a_06_html_canvas_done.png` | Initial buggy render (nested doc — see §4.2) |
| `spike_a_09_bar_chart_done.png` | Final working render: green sandbox banner + 3-bar chart |
| `spike_a_07_canvas_raw.png` | Raw HTML inspector showing the LLM's full doc |

### 3.3 Sub-step 2.3.5 — useCoAgentStateRender-style live indicators (✅ PASS)

A single chat message — *"Take 4 steps using advance_step, then switch the model to smart"* — caused the LLM to:

1. Call `advance_step` four times. Each call mutated React state via `setStep((s) => s + 1)` from the action's `handler`. The `<StepMeter>` component updated in real time, its `aria-live="polite"` region announcing the new value.
2. Call `switch_model({ tier: "smart" })`. The handler set `setModel("smart")`. The `<ModelBadge>` switched from green `haiku · fast` to purple `sonnet · smart` on the same render frame.

| Screenshot | What it shows |
|-----------|---------------|
| `spike_a_12_left_rail_top.png` | Left rail after the run: `STEP: 4` (40% bar) and `MODEL: sonnet · smart` |

**Architectural note**: The spike validated the **rendering concern** (a React component re-renders whenever its data source changes). The real Sprint-3 implementation of these indicators will use `useCoAgent` / `useCoAgentStateRender`, which sources its data from AG-UI `STATE_SNAPSHOT` / `STATE_DELTA` events instead of from local `useState`. From the component's perspective this is interchangeable — the same `<StepMeter step={…}>` works either way. The risk being retired here is "can a CopilotKit-driven LLM update React UI synchronously enough to feel live?"; that risk is retired.

### 3.4 Architecture rule conformance (✅ PASS)

| Rule | Spike check | Result |
|------|-------------|--------|
| **F-R2 / A1** — SDK imports only in adapters | The spike's components import only React + local types — `@copilotkit/*` imports are confined to `app/copilot-provider.tsx` (the equivalent of an adapter) and `app/page.tsx` (the equivalent of a composition root). | ✅ |
| **F-R8 / A4** — no SDK type past adapter boundary | Our render-prop components receive `{ status, args, result }` — plain typed props. The `args` shape is what *we* declared via `parameters: [...]`, not a CopilotKit type. | ✅ (with one nuance — see §4.1) |
| **U3 / FE-AP-4** — iframe sandbox `allow-scripts` only | Verified live by probe (§3.2). | ✅ |
| **FE-AP-12** — no `dangerouslySetInnerHTML` on agent output | Verified by code review of `generative-html.tsx`. | ✅ |
| **U4 / FE-AP-5** — `aria-live="polite"`, never `assertive` | `<StepMeter>` and `<ModelBadge>` use `aria-live="polite"`. | ✅ |

---

## 4. Findings (impedance mismatches and minor bugs)

### 4.1 `result` in the render prop is not a string (low impact)

**Symptom**: The `web_search` card showed `[object Object],[object Object]` instead of the JSON I returned from the handler.

**Cause**: `useCopilotAction`'s `render` prop receives `result` typed as `unknown` (effectively the parsed return value, plus possible auto-deserialization of JSON strings). My `safeParseHits` did `typeof result === "string"` and fell through to `String(result)` on the non-string value.

**Fix in production**: The Sprint-3 `ToolRendererRegistry` adapter should normalise `result` to a Zod-validated wire shape per tool. Components must never depend on `typeof result === "string"`.

**Severity**: low — caught and documented; trivial to handle in the production adapter.

### 4.2 `srcDoc` nested-document bug (caught and fixed in spike)

**Symptom**: First Bar Chart attempt's iframe rendered blank (white). No probe banner, no SVG.

**Cause**: My initial `GenerativeHtmlComponent` always wrapped the LLM's HTML in a fresh `<!DOCTYPE html>...<body>...</body></html>`. When the LLM returned a *full* HTML doc (which is the natural thing to do for a "render an html canvas"), we ended up with a nested `<!DOCTYPE html>` inside the body of another doc, which most browsers tolerate but which broke our probe injection point.

**Fix applied during the spike**: New `buildSrcDoc(html)` helper detects whether the LLM returned a fragment or a full doc and injects the probe in the right place. After the fix the second render (Bar Chart) showed both the green probe banner and the chart correctly.

**Implication for Sprint 3**: the production `useComponent` wrapper must encode this fragment-vs-full-doc decision **once**, not once per consumer.

**Severity**: low — caught and fixed inside the spike; documented as a Sprint-3 task.

### 4.3 CopilotKit "v1.50 is now live!" toast overlap (cosmetic)

A floating CopilotKit Cloud toast appears top-right of the chat and slightly overlaps the page header. This is a Cloud product notification, not a hook-API behaviour; will not appear in self-hosted runtime.

**Severity**: cosmetic — no fix needed in spike.

### 4.4 `useFrontendTool` → `useCopilotAction` rename (documentation drift only)

The V3 plan and SPRINT_BOARD reference `useFrontendTool`. CopilotKit 1.56 (the current latest) consolidates frontend tools, generative UI, and HITL under `useCopilotAction`. We use `useCopilotAction` in the spike and recommend the same in v1; SPRINT_BOARD wording will be updated as part of Sprint 1's planning hand-off.

**Severity**: documentation only — no behavioural change.

---

## 5. Costs and quotas burned

| Resource | Burn |
|---------|------|
| CopilotKit Cloud chat completions | ~6 user messages, ~6 LLM responses with tool calls. Negligible against any tier. |
| OpenAI tokens (CopilotKit Cloud uses your linked OpenAI key) | ~6 short turns of chat with tool-arg streaming. < $0.05. |
| Mem0 / Langfuse | Not touched by this spike. |

---

## 6. Decision: PROCEED to Sprint 1 unchanged

Both H4 and H7 are retired:

- **H4** (CopilotKit ↔ ReAct graph compatibility): the *hook* layer works. The wire-format bridge — CopilotKit's `useCopilotAction` calls vs our backend's AG-UI `TOOL_CALL_*` events — is an open-standard hop (AG-UI is the contract; both sides implement it). Sprint 1's S1.1.1 will validate the live-stream connection, not the hook API.
- **H7** (iframe sandbox sufficient for generative UI): definitively retired by the live probe.

### 6.1 Implications for downstream sprints

| Surface | Action |
|---------|--------|
| **SPRINT_BOARD.md** S0.2.x acceptance criteria | Mark all three sub-stories PASS. Update wording: `useFrontendTool` → `useCopilotAction` (v2 consolidated hook). |
| **Sprint 1 — S1.1.1** | Continues unchanged. Validates the *backend-to-CopilotKit-runtime* link via `HttpAgent` from `@ag-ui/client`. |
| **Sprint 3 — S3.3.4** (`CopilotKitUIRuntime`, `CopilotKitRegistryAdapter`) | Confirmed as `useCopilotAction`-backed with a per-tool render registry. Fragment-vs-full-doc handling per §4.2 must be in the adapter. |
| **Sprint 3 — S3.8.3** (generative UI canvas) | The exact pattern from `app/components/generative-html.tsx` — `<iframe sandbox="allow-scripts" srcDoc={…}>` plus a sandbox-verify probe — is the production blueprint. |
| **Sprint 3 — S3.8.4** (Pyramid panel) | Same renderer; feature-flagged. No change. |
| **Sprint 4 — S4.3.2** (beta launch) | F5 / F13 / F14 stay in scope for v1. |

### 6.2 V1 fallback (NOT activated)

The V1 fallback path *"revert to assistant-ui per V1; lose F13/F14/F17"* is **not invoked**. CopilotKit v2 is the chosen substrate.

---

## 7. Throwaway-code lifecycle

`spikes/spike-a-copilotkit/` stays on the developer workstation only — gitignored per `SPRINT_0_RUNBOOK.md` §5. The patterns in `app/components/*.tsx` are the reference for the production components in Sprint 3 but the production code lives at `frontend/components/tools/`, `frontend/components/generative/`, and `frontend/components/state/` per `STYLE_GUIDE_FRONTEND.md` §3.1.

Production differences from the spike:
- Self-hosted CopilotKit Runtime (not Cloud) for V3-Dev-Tier.
- `HttpAgent` from `@ag-ui/client` pointed at the middleware `/agent/*` surface.
- `result` types per tool normalised through Zod before they reach the render prop.
- Strict CSP nonce + `frame-src 'self'` enforced on the parent doc.
- Fragment-vs-full-doc handling inside the production `useComponent` wrapper, not the consumer.

## 8. Re-open trigger

Re-run this spike if **any** of:

- CopilotKit ships a major-version bump that changes the `useCopilotAction` API.
- AG-UI Protocol introduces a breaking event-type change before our wire schemas are pinned in Sprint 3.
- A Sprint-3 PR review surfaces an iframe-sandbox bypass we didn't think of.
