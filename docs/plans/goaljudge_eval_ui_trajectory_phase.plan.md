# GoalJudge Eval UI — Trajectory + Admissible-Capture Phase

> **Status:** IMPLEMENTED except F10-Tier2 (2026-06-11). Pre-Stage-6 UI workstream.
> All phases landed on `feat/goaljudge-stage5-phase6-iaa-round1` — see §0 for the
> commit-by-commit execution record. Remaining: F10 Tier 2 (cheap reasoning recap)
> and the T3 `goaljudge-batch` admissibility validation.
> **One-line:** Connect the already-built (and tested) AG-UI → UI-runtime → React
> pipeline to the live chat shell, so the UI renders the **tool trajectory**, a
> **live task list + synthesized reasoning**, a **guaranteed synthesized answer**, and
> a **deterministic terminal state** — turning the app itself into admissible eval
> evidence *and* an engaging product surface.
> **Owner:** me (frontend) + scoped backend tasks (tool/step emission, guaranteed
> closing turn, cheap reasoning summary).
>
> **North star (resolved 2026-06-11):** **dual-mode.** The default UI is engaging —
> animated loading, live reasoning, progressive disclosure. A **frozen `eval` mode**
> (`?eval=…` / batch flag) disables animation, pre-settles the reasoning summary, and
> waits on a stable terminal state so every capture stays deterministic and
> admissible. One component tree, two render modes. This is the through-line that
> makes the prior IAA-admissibility goal and the new product-engagement wishlist
> coexist instead of fighting.
>
> **Waves:** **Wave A** = F1–F7 (trajectory + admissible capture, below). **Wave B**
> = F8–F12 (loading, task list, reasoning, guaranteed answer, typography) — the
> 2026-06-11 wishlist, specced in §8 with the four design decisions baked in.
>
> **Architecture:** this is an **architecture-conformance** task on a fully-built
> hexagonal ring, not a green-field UI build — see §8.5 (the placeholder
> `chat-shell.tsx` violates F-R1/F-R7/F-R8) and §8.6 (suggested architecture changes).
> **Process:** every feature ships **test-first (TDD)** per
> [`research/tdd_agentic_systems_prompt.md`](../../research/tdd_agentic_systems_prompt.md) —
> Red→Green→Refactor, failure-paths-first, tests at the correct uncertainty layer, no
> live agent in CI. The per-feature test plan + Definition-of-Done is in **§8.7**.
> **Playwright** validates the rendered UI at the right cut-point (T1 mocked / T2
> integration / T3 full-stack) per
> [`docs/skills/playwright-agentic-e2e`](../skills/playwright-agentic-e2e/SKILL.md) — the
> repo already ships the tier scripts and specs (several skip today and light up as
> F1–F3 land). Per-feature tier + assertions in **§8.8**.

---

## 0. Execution record (2026-06-11)

Implemented phase-by-phase in the Appendix B interleaved order, backend emission
first, all on `feat/goaljudge-stage5-phase6-iaa-round1` (decisions taken with the
owner at kickoff). Every slice shipped TDD-first (failure paths first) with T1
Playwright validation per §8.8.

| Commit | Phase(s) | What landed |
|---|---|---|
| `d74193d` | prep | Pin vite ^7 so vitest 4 can start (frontend test runner was dead) |
| `c123ddf` | Phase 0 | Backend emission: `StepProgressed` → `Custom step_meter`; `_translate_chain_end` emits `StateMutated` JSON-Patch `replace` for `/todos`, `/plan_ref`, `/selected_model`; telemetry-bridge skip list updated; wire artifacts regenerated |
| `230804f` | F1 | Chat shell on the runtime port: `connectFetchSSE` transport (§8.6-E Option A), `streamRun(req)` port (§8.6-F), `lib/composition_browser.ts` browser root, pure `run_view_reducer`, `useAgentRun` hook |
| `c887fcc` | F2/F3/F9 | Status slot separate from answer body; **"Using tools:" preview removed at the backend source** (GJ-012/GJ-F-008 root cause retired); tool-card testids + errored-status convention; live `TaskList` from `/todos` deltas (cancelled ≠ done) |
| `c099e6f` | F8/F10-T1 | `deriveRunPhase` → `data-run-phase` (event-driven, no timers); `narrateTrajectory` free Tier-1 narration line |
| `927c3a9` | F11 | `synthesizeFallbackAnswer` — answer slot never empty; "summary generated from tool results" marker |
| `ee17c67` | F4/F12 | react-markdown + remark-gfm (no raw HTML), `CodeBlock` with copy, dangling-fence stabilizer; Geist Sans/Mono type system per Appendix A |
| `deaf45f` | F5/F6/F7 | Model badge from `/selected_model` delta; copyable trace chip (forwarded `trace_id` only, F-R7); `?eval=GJ-…` capture surface (pinned case id, frozen animation, prod clean) |

**Verification at close:** backend 738 passed; frontend 378 unit tests passed; T1
chromium 14/14; visual tier 8/8 (baselines updated); architecture-layering tests
green with the second composition root.

**Plan corrections forced by code reality** (full detail in §8.6-F and the §8.6-C
correction): the middleware is a single `POST /run/stream` whose response body *is*
the SSE stream → the port is `streamRun(req)`, `createRun` removed; wire
`RunFinished` carries **no** `final_message`, so F11's guarantee = graph forced
synthesis + frontend fallback.

**Remaining work:**
- **F10 Tier 2** (deferred deliberately — Tier 1 ships the live information for $0):
  once-per-run cheap-model recap over a `Custom {name:"reasoning_summary"}` channel,
  Jinja prompt in `prompts/` (F-R5), lazy "Show reasoning" expander, pre-settled in
  eval mode, cost guard skips 0–1-tool runs (§8 F10 / §8.6-B).
- **T3 acceptance:** `goaljudge-batch` registry run against the full stack —
  `tool_card_count > 0` where expected, `response_text` 100% non-empty (§8.8 / §5).
- Out of band: 3 stale frontend checker-script tests (pre-existing, tracked
  separately).

---

## 1. Why this phase exists (the diagnosis)

The GoalJudge eval screenshots in
[`cache/goaljudge_eval/ui_batch_screenshots_*`](../../cache/goaljudge_eval/) show a
recurring failure that is **not** an agent failure — it's a UI failure:

* Several captures (`GJ-012`, `GJ-F-008`) show **only** the string
  `Using tools: file_io, shell…` styled identically to a real answer, frozen
  mid-stream. There is no visual difference between "agent is still working" and
  "agent answered." The capture is **inadmissible** as evidence, yet looks final.
* The long answers (`GJ-006`) render as an undifferentiated `whitespace-pre-wrap`
  wall of text — no markdown, no code blocks, no structure.
* **No tool trajectory is shown at all.** The tool calls — which the IAA protocol
  declares *primary evidence* ([goldset README](../IAA/goalJudge/goldset/README.md)
  §"Annotators and evidence discipline") — exist only in Langfuse, never in the UI.

### Root cause (verified in the code + against the architecture docs)

> The frontend is a documented hexagonal **ports-and-adapters ring** (F-R1…F-R9). The
> whole ring is already built and tested; `app/chat-shell.tsx` is an off-architecture
> placeholder that bypasses it and violates F-R1/F-R7/F-R8. The full alignment analysis
> is in **§8.5**; the architecture-doc improvements it surfaced are in **§8.6**. The
> table below is the pre-architecture-review view (still accurate, now subsumed by §8.5).

The frontend already contains a **complete, unit-tested** event pipeline:

| Layer | File | What it does |
|---|---|---|
| Wire parse | [`lib/wire/ag_ui_events.ts`](../../frontend/lib/wire/ag_ui_events.ts) | zod-validates the full AG-UI event set incl. `TOOL_CALL_START/ARGS/END`, `TOOL_RESULT`, `STEP_STARTED/FINISHED`, `step_meter` |
| Translate | [`lib/translators/ag_ui_to_ui_runtime.ts`](../../frontend/lib/translators/ag_ui_to_ui_runtime.ts) | maps every wire event → UI-runtime event (tool events → `tool_event_to_renderer_request`, steps → `step_progress`) |
| UI-runtime kernel | [`lib/wire/ui_runtime_events.ts`](../../frontend/lib/wire/ui_runtime_events.ts) | narrowed shapes the React layer consumes; every event keeps `trace_id` |
| Renderer registry | [`lib/adapters/tool_renderer/`](../../frontend/lib/adapters/tool_renderer/) | returns the component that renders a tool call |
| Tool card | [`components/tools/ToolCard.tsx`](../../frontend/components/tools/ToolCard.tsx) | collapsible `<details>` card: name · status · input · output |
| Stream surface | [`components/chat/StreamingMarkdown.tsx`](../../frontend/components/chat/StreamingMarkdown.tsx) | already accepts `modelBadge` (F7) + `step` meter (F6) props |

**The live chat bypasses all of it.**
[`app/chat-shell.tsx`](../../frontend/app/chat-shell.tsx) is a self-described
*placeholder* ("full AG-UI / CopilotKit integration lands in later sprints"). It
hand-rolls an SSE reader that:

1. handles only `TEXT_MESSAGE_CONTENT` and `RUN_ERROR` — **drops** `TOOL_CALL_*`,
   `STEP_*`, `RUN_FINISHED`;
2. concatenates every delta into one `assistantText` blob (so the agent's
   `Using tools: …` narration lands inside the answer body);
3. renders `whitespace-pre-wrap` (no markdown);
4. passes neither `modelBadge` nor `step` to `StreamingMarkdown`;
5. has no per-message terminal marker — global `busy` flips, the text just stops
   growing.

So this phase is mostly **wiring an existing, tested stack into one placeholder
component** — not greenfield. That is what makes it cheap and high-leverage.

### Evidence this is the right target

The batch harness JSONL schema already declares a `tool_card_count` field
([`goaljudge-batch.spec.ts`](../../frontend/e2e/full-stack/goaljudge-batch.spec.ts)
header) — it was designed expecting tool cards in the DOM, and gets `0` today.
The Playwright skill's gotchas (`article div[aria-live='polite']`, "wait by
text-settle not `finished()`", "strip status-feed prefix") are all workarounds
for defects F2/F3 below remove at the source.

---

## 2. Feature list (ranked by leverage)

| # | Feature | Leverage | Effort | Depends on |
|---|---|---|---|---|
| **F1** | Wire AG-UI runtime into the live chat shell | keystone — unlocks F2/F3/F5/F6 | M | backend confirm |
| **F2** | Distinct run-status + terminal-state affordance | retires the inadmissible-capture class | S | F1 |
| **F3** | Tool-trajectory rendering (wire `ToolCard`) | **the new feature** — UI becomes primary evidence | S–M | F1 |
| **F4** | Real markdown + code blocks + copy button | readability; independent | M | — |
| **F5** | Model badge + step meter (surface D6 telemetry) | seeds deferred D6 backfill; props already exist | S | F1 |
| **F6** | Per-message `trace_id` / case-id chip | one-click UI↔Langfuse correlation for annotators | S | F1 |
| **F7** | "Eval mode" capture surface (`?eval=GJ-…`) | identical admissible captures for harness + humans | M | F2,F3 |

S ≈ ½–1 day · M ≈ 1–2 days, given the stack is already built and tested.

---

## 3. Specs

### F1 — Put the chat shell on the existing runtime port *(keystone)*

> **Reframed by §8.5.** This is not "build a reducer" — the ring already has one path.
> It's "stop bypassing it." See §8.5 for the F-R1/F-R7/F-R8 violations being fixed.

**Change:** Delete the raw `fetch("/api/run/stream")` + hand-rolled `flushEvent` SSE
parser from [`app/chat-shell.tsx`](../../frontend/app/chat-shell.tsx). Drive the run
through the **`AgentRuntimeClient` port** obtained from `composition.ts`:
`createRun(req)` → `streamRun(runId)` yields **`UIRuntimeEvent`s** (already translated
by `ag_ui_to_ui_runtime` inside the adapter — components never see raw `AGUIEvent`, per
deviation D-V3-P1 + F-R8). The per-message reducer over `UIRuntimeEvent` lives behind
the **`UIRuntime`** port / a hook — **not in the component** (F-R1).

**Transport (decided — §8.6 gap E, Option A):** the chat-shell `fetch`-SSE reader is not
deleted outright — its frame-parse loop (`chat-shell.tsx:90-144`) is **promoted into a
`connectFetchSSE` transport adapter** (`lib/transport/`) that yields `AGUIEvent`s over
`fetch`+`ReadableStream`. `makeOpenUIRuntimeStream` wires `connectFetchSSE` (not the
`EventSource`-based `connectSSE`) so the browser reads the BFF stream over `fetch` —
**this is what keeps the existing T1 `page.route` mocks alive.** Heartbeat + Last-Event-ID
resumption are intentionally dropped on this path. `connectSSE` stays for server-side use.

**Per-assistant-message view state** (derived in the UIRuntime layer, passed as props):
```
{ id, status: "streaming"|"complete"|"error",
  segments: Array<{kind:"text", text} | {kind:"tool", request: ToolRendererRequest}>,
  step?: {count, name, costUsd}, modelBadge?: string, traceId }   // traceId forwarded, never generated (F-R7)
```
Segments append in **trajectory order** so the render mirrors the real ReAct loop.

**`UIRuntimeEvent`s consumed** (post-translation shapes from the deep-dive contract):
`run_started`, `token`, `tool_renderer_request`/`tool_renderer_update`, `step`,
`model_switch`, `run_completed` (→ `status:"complete"`, carries `final_message`),
`run_error` (→ `status:"error"`). Runtime Contract §1 guarantees the stream ends on
`run_completed`/`run_error` — F2 hangs off that.

**Backend link to verify (§8.5):** confirm
[`agent_ui_adapter/translators/domain_to_ag_ui.py`](../../agent_ui_adapter/translators/domain_to_ag_ui.py)
emits `ToolCallStart/ToolResult` + `StepStarted/Finished` + `StateDelta` (grep was
empty — may emit only text + lifecycle today). If missing, add the emission there (the
wire shapes already exist; this is translator work, not agent logic).

**Acceptance:** a multi-tool prompt (`GJ-F-008`, `GJ-F-020`) renders interleaved text +
≥1 tool card via the port; `run_completed` flips the message to `complete`; the
architecture test `test_frontend_layering.ts` passes (no raw-fetch / no adapter import
in the component); existing `chat-shell.test.tsx` + wire/translator suites stay green.

---

### F2 — Distinct run-status + terminal-state affordance

**Problem solved:** the `Using tools: …`-as-answer inadmissible capture.

**Spec:**
* The in-progress status feed renders in a **separate, visually-distinct slot**
  (a status line / spinner with its own `aria-live="polite"` region), **never**
  concatenated into the answer body. The answer region contains only the answer.
* Each assistant message exposes `data-state="streaming"|"complete"|"error"` on its
  root and a visible terminal marker when `complete` (subtle "done" affordance; the
  composer's per-turn enable ties to `run_completed`, not a global flag).
* The status slot disappears (or collapses into the trajectory) on `complete`.

**Why it matters:** the batch harness waits on `[data-state="complete"]`
deterministically instead of text-settle heuristics. Directly retires three
Playwright gotchas and the whole "is this capture admissible?" question — every
captured `complete` message *is* admissible by construction.

**Acceptance:** capturing at `data-state="complete"` never yields a status-feed-only
screenshot across the full registry batch; `tool_card_count` in the JSONL is
non-zero for tool-using cases.

---

### F3 — Tool-trajectory rendering *(the new feature)*

**Spec:** Render each message's tool segments via the existing tool-renderer
registry → `ToolCard`. Each card: `tool_name`, status (`running`/`completed`/
`errored`), `input` (pretty JSON), `output` (string or pretty JSON), collapsible
`<details>` (default-open while `running`, collapsed when done). Cards interleave
with text in trajectory order (from F1's `segments`). Add deterministic hooks:
`data-testid="tool-card-{i}"` per card and `data-tool-count` on the message root so
the harness can read `tool_card_count` from the DOM.

**Why it's the headline feature:** today the tool trajectory — the IAA program's
*primary evidence* — lives only in Langfuse, so a UI screenshot can never be
primary evidence and the protocol must route annotators to Langfuse for six
specific cases. With the trajectory in the DOM, **the screenshot becomes admissible
primary evidence**, annotators stop round-tripping to Langfuse, and `goal_met`
labeling can be done from the capture alone for most cells.

**Acceptance:** `GJ-F-008` shows a `file_io` card (read → transform → write);
`GJ-F-020` shows the multi-tool audit trajectory; `GJ-F-022` (compose) shows
file_io + shell + web cards in order. The card `output` matches the Langfuse tool
result for the same trace.

---

### F4 — Real markdown rendering + code blocks + copy

**Problem solved:** the `GJ-006` wall of text. `StreamingMarkdown`'s own header
comment promises this ("Full markdown rendering (code highlighting + copy button)
lands in S3.8.x +1") — this phase delivers it.

**Spec:** streaming-safe incremental markdown (headings, lists, tables, emphasis,
links, inline + fenced code). Fenced code blocks get a language tag + copy button.
**No `dangerouslySetInnerHTML`** without sanitization (the component contract
forbids it; FE-AP-5 auto-reject). Preserve the `aria-live="polite"` region and the
no-focus-steal rule (U5). Independent of F1 — can land in parallel.

**Acceptance:** `GJ-006`-class answers render with visible structure; a fenced code
block copies to clipboard; the streaming-markdown test suite covers partial-token
safety (no broken-fence flash mid-stream).

---

### F5 — Model badge + step meter (surface D6 telemetry)

**Spec:** Feed `StreamingMarkdown`'s existing `modelBadge` + `step` props from F1's
per-message state. Model badge = the run's model tier (from run metadata /
model-tier event); step meter = `step_progress` (`step {count} · {name}`). Both
render in the message header (test IDs `model-badge`, `step-meter` already exist).

**Why:** the goldset manifest's D6 fields (`model_tier_distribution_observed`,
`routing_reason_distribution_observed`) are `{}` and
[deferred](goaljudge_stage5_phase6c_v09_and_wave2.plan.md#8-out-of-scope-for-this-plan).
Surfacing tier/step in the UI gives annotators routing context and is a natural
seam to start capturing the D6 distributions the gold-set plan punts on. Near-zero
cost — the props and test IDs already exist.

**Acceptance:** a routed prompt shows its model tier badge; a multi-step prompt
shows the step meter incrementing.

---

### F6 — Per-message `trace_id` / case-id chip

**Spec:** Every UI-runtime event carries `trace_id` (W5 contract). Surface it as a
small **copyable** chip in the assistant message footer, gated to dev/eval mode (a
flag or `?eval` query param so prod chat stays clean). In batch/eval mode also pin
the case id. The batch spec writes `trace_id` into the JSONL next to
`tool_card_count`.

**Why:** closes the screenshot ↔ Langfuse loop. An annotator looking at an
admissible capture can jump straight to the trace by `trace_id` instead of
reconstructing the `thread=session-gj-XXX` query by hand (a documented pain in the
Playwright gotchas).

**Acceptance:** the chip copies the trace_id; the JSONL row's `trace_id` matches the
Langfuse trace for that case.

---

### F7 — "Eval mode" capture surface *(stretch)*

**Spec:** With `?eval=GJ-F-008` (or a batch flag), the app: pins the case id, shows
the prompt + (optionally) expected axes, collapses the sidebar, fixes content width,
forces `en-US` locale, and renders the F2/F3 layout. The **same** app then serves
both the Playwright batch and human annotators — identical, deterministic,
admissible captures, eliminating the "UI capture vs Langfuse" evidence split for
good.

**Acceptance:** a batch run in eval mode and a human opening the same `?eval` URL see
pixel-equivalent trajectories; captures pass the admissibility check 100%.

---

## 4. Dependency graph & sequencing

```
F1 (keystone, needs backend confirm)
 ├─ F2 (terminal state)  ─┐
 ├─ F3 (tool trajectory) ─┼─ F7 (eval mode, stretch)
 ├─ F5 (badge/step)       │
 └─ F6 (trace chip)       │
F4 (markdown) — parallel, no dep ┘
```

**Recommended order:** F1 → F2 → F3 (this trio is the whole value: admissible,
trajectory-bearing captures) → F4 (readability) → F5/F6 (telemetry + correlation)
→ F7 (stretch). F4 can be done by a second person in parallel from day one.

---

## 5. What this unblocks for the IAA / Stage 5–6 program

* **Wave-2 labeling gets cheaper and more reliable.** The combined sheet is already
  101 admissibility-constrained rows; wave 2 adds ~150 in the *adversarial* cells
  (wrong-tool, blocked-tool, request_approval) where `goal_met` is hardest to read
  from a final answer alone. A visible tool trajectory is exactly what those cells
  need to label confidently — see the wave-2 plan's
  [§5.1 cell mix](goaljudge_stage5_phase6c_v09_and_wave2.plan.md#51-phase-4-wave-2-authoring).
* **The protocol's six "inadmissible UI" carve-outs can be deleted** once captures
  carry the trajectory + a `complete` marker.
* **D6 telemetry** (F5) starts flowing toward the manifest fields the gold-set plan
  defers.

This phase does **not** touch the rubric, the gold-set freeze, the firewall, or
Stage 6 calibration logic — it is purely the evidence-rendering surface.

---

## 6. Out of scope

* Full CopilotKit adoption (this phase wires the *runtime translation*, not the SDK
  hooks; the existing adapters already avoid importing CopilotKit per F-R2).
* Backend agent changes beyond confirming/forwarding AG-UI tool/step events.
* Any change to gold-set artifacts, manifest schema, or `gate_goldset_v1_floors`.

---

## 7. Resolved design decisions (2026-06-11)

Four forks were settled with the user; they drive Wave B (§8).

| # | Decision | Chosen | Consequence |
|---|---|---|---|
| D-A | Audience / determinism vs. engagement | **Engaging UX + frozen `eval` mode** | Dual-mode (see north star). Animation/streaming on by default; `eval` mode freezes + pre-settles for admissible capture. |
| D-B | Reasoning provenance + "synthesized" | **Hybrid (option 2 + 3), cost-minimized** | Free frontend narration *live*; one **cheap small-model** end-of-run summary behind progressive disclosure. See §8 F10 + research §9. |
| D-C | Always-show synthesized answer | **Backend guarantee + frontend fallback** | Agent graph always emits a closing summary turn; UI synthesizes from the trajectory if text is still absent. See §8 F11. |
| D-D | Typography | **Cursor-aesthetic via free substitutes + deck alignment** | Mimic the Cursor Agents look (screenshot ref) with licensable grotesque-sans + mono; align palette to the pitch deck. See §8 F12 + Appendix A. |

**F1 backend dependency (now narrowed by §8.5):** the frontend ring is fully built —
`AgentRuntimeClient.createRun/streamRun`, `sse_client`, `ag_ui_to_ui_runtime`,
`composition.ts` all exist and are tested; the backend wire *defines* every event we
need. The one unverified link is whether
[`agent_ui_adapter/translators/domain_to_ag_ui.py`](../../agent_ui_adapter/translators/domain_to_ag_ui.py)
actually **emits** `ToolCallStart/ToolResult` + `StepStarted/Finished` +
`StateDelta` at runtime (the grep for these in that translator came back empty — it may
only emit text + run lifecycle today). **First task:** confirm/repair that emission. If
the events flow, F1–F3 + F8 are "swap `chat-shell` onto the existing port" and ship this
week. F9 additionally needs §8.6-A (promote `StateDelta` from Phase 2).

---

## 8. Wave B — wishlist features (F8–F12)

> Grounded in two backend facts found this session: (1) a real **`state_todo`** tool
> ([`services/tools/todo_tools.py`](../../services/tools/todo_tools.py)) already
> maintains `TodoItem{id, content, status∈pending|in_progress|completed|cancelled}`
> and returns `state_delta={"todos":[…]}`; (2) a MECE-validated **`PlanArtifact`**
> ([`components/plan_builder.py`](../../components/plan_builder.py)) with
> `ordered_steps`, `constraints`, `success_conditions`. The task list is a *render*
> of existing data, not a build.

### F8 — Loading / liveness indicator (dual-mode)

**Spec:** A single source-of-truth run-phase indicator driven by F1's per-message
`status` + the latest `step`/activity: phases `connecting → thinking → using {tool} →
writing → done`. **Default mode:** animated (shimmer on the active phase, subtle
pulse), `aria-live="polite"` text so it's also announced. **`eval` mode:** the *same*
phase text rendered **static** (no animation) and the harness waits on
`data-state="complete"` (F2) — so liveness never destabilizes a capture.

* Place the indicator in the message's status slot (F2), never inside the answer body.
* `data-run-phase="thinking|tool|writing|done"` for deterministic assertions.
* Keep it honest: phase is derived from real events (`STEP_*`, `TOOL_CALL_*`,
  `TEXT_MESSAGE_*`, `RUN_FINISHED`), never a fake timer.

**Acceptance:** during a multi-tool run the phase advances through `using file_io →
writing → done`; in `eval` mode the captured frame shows a stable `done` with no
animation artifact.

### F9 — Live task / todo list (render `state_todo`)

**Spec:** Subscribe to `STATE_DELTA`/`STATE_SNAPSHOT` (already translated to
`state_render`); project the `todos` array into a **checklist** above/beside the
trajectory. Render each `TodoItem` user-friendly: a checkbox/icon by status
(`pending` ○, `in_progress` ◐ + active emphasis, `completed` ✓ struck/dimmed,
`cancelled` ⊘), `content` as the label. Items update in place as deltas arrive →
visible "marking complete" behavior. Show a compact progress count (`3/5 done`).

* If a `PlanArtifact` is present (planning-depth ≥ L1), seed the list from
  `ordered_steps` (title + goal) and reconcile with live `todos` by id.
* **Synthesized, not raw:** collapse internal ids; show `content`/`title` only;
  group by status if the list is long; cap visible items with a "show all" expander
  (progressive disclosure).
* Determinism: `data-todo-count`, `data-todo-done`, `data-testid="todo-{id}"`.

**Why it's high-value:** for the wave-2 *adversarial* gold-set cells (wrong-tool,
blocked-tool, request_approval) a visible task list with completion state is often
the clearest `goal_met` evidence — the annotator sees which subtasks the agent
actually closed. Directly serves the
[wave-2 cell mix](goaljudge_stage5_phase6c_v09_and_wave2.plan.md#51-phase-4-wave-2-authoring).

**Acceptance:** `GJ-F-022` (compose triple) renders a 3-item list that ticks to
`3/3`; a `subtask-dropped` case visibly leaves one item `pending`.

### F10 — Synthesized reasoning (hybrid, cost-minimized) — decision D-B

The user asked to **minimize cost + latency without compromising interactivity or
information.** Research (§9) converges on a two-tier, progressive-disclosure design:

**Tier 1 — live narration (free, deterministic, zero added latency/cost).**
Derive a friendly present-tense line from the event stream as it arrives:
`Reading notes.md → removing TODO lines → saving notes_clean.md`. Pure
frontend reduction over `STEP_*` + `TOOL_CALL_*` (name + args) + any `state_todo`
transitions. This is what the user *sees while waiting* — it carries the information
and the interactivity with **no model call**. If the agent emits its own ReAct
thought text, show it here verbatim (collapsed).

**Tier 2 — polished reasoning recap (one cheap call, lazy).**
After `RUN_FINISHED`, optionally produce a short synthesized "why/how" paragraph via
a **small/fast model tier** (Haiku-class), **once per run, not per token**, summarizing
the trajectory. Gate it by progressive disclosure: rendered only when the user
expands **"Show reasoning,"** or pre-computed in `eval` mode so the capture is stable.
Reuse the existing model-tier routing (D6) — the cheap tier already exists.

**Cost/latency math:** Tier 1 = $0, 0 ms. Tier 2 = one short Haiku-class completion
over a trajectory (hundreds of tokens), amortized once per run and **off the
critical path** (lazy/post-stream) — TTFT and inter-token latency of the *answer* are
untouched. This is the documented progressive-disclosure + model-routing pattern
(§9) for "minimum cost without compromising information."

* **Default mode:** Tier 1 streams live; Tier 2 lazy behind the expander.
* **`eval` mode:** Tier 1 frozen to its final line; Tier 2 pre-rendered + settled
  before capture (so reasoning is admissible evidence, not a moving target).
* Reasoning renders in its **own typographic layer** (Appendix A) — visually distinct
  from the answer so no one mistakes thinking for the final answer.

**Acceptance:** Tier 1 line is present for every multi-step run with no extra latency;
expanding "Show reasoning" yields a ≤3-sentence recap; in `eval` mode the recap is
present and static at capture time. A cost guard caps Tier 2 to the cheap tier and
skips it for trivial (0–1 tool) runs.

### F11 — Guaranteed synthesized answer (two layers) — decision D-C

**Backend (primary):** the agent graph always ends a run with a **closing synthesized
answer turn** — even when the last useful action was a tool call. This fixes the
`GJ-F-008`/`GJ-012` root cause (runs that end on a tool call with no prose) at the
source and *also* improves gold-set labeling (every row has a final answer to judge).

**Frontend (fallback):** if `RUN_FINISHED` arrives with empty answer text, synthesize
a deterministic recap from the trajectory — `"Completed 3 steps: created
/workspace/f3.txt, listed its contents, fetched Austin weather."` — rendered in the
answer slot with a subtle "summary generated from tool results" marker. Never leave
the answer slot empty; never let a status line stand in for the answer.

**Acceptance:** no run in the full registry batch ends with an empty answer slot;
`GJ-F-008` shows a real closing answer (backend) or the fallback recap (frontend); the
batch JSONL `response_text` is non-empty for 100% of cases.

### F12 — Typography theme for layered information — decision D-D

Goal: a **font + type-scale system that visually separates the information layers** —
answer · reasoning · tool I/O · task list · metadata — in the **Cursor Agents
aesthetic** the user referenced (screenshot), aligned to the pitch-deck styling.

The referenced screenshot is **Cursor's** house style — **Cursor Gothic** (a bespoke
grotesque/"gothic" sans built on Kimera's *Waldenburg*) for UI/body + **Cursor Mono**
for code; both *proprietary and not licensable*. So we **mimic the feel with free,
screen-optimized grotesque-sans + mono substitutes**. Note the Cursor look is
**all sans + mono — no serif** — so we separate layers *within* that system (family
sans↔mono, plus weight/size/color), not by adding a serif. Full spec in **Appendix
A**; summary:

| Layer | Role | Family (substitute) | Style |
|---|---|---|---|
| Answer | primary reading | **Geist Sans** *(or Inter)* — Cursor-Gothic/Waldenburg grotesque feel | base size, regular, line-height ~1.6 |
| Answer headings | section titles | Geist Sans | semibold, larger (matches screenshot's bold headers) |
| Reasoning | synthesized "thinking" | Geist Sans, **muted + italic** (no serif) | sm, `--color-muted`; distinct from answer by color/style |
| Tool I/O / code | technical | **Geist Mono** *(or JetBrains Mono)* — Cursor-Mono feel | mono, sm, muted; inline code as a tinted chip (screenshot cue) |
| Task list | structured | Geist Sans | sm, status-colored icons |
| Metadata | badges/trace/step | Geist Mono | xs, muted, uppercase tracking |

* Implement as `--font-sans` (grotesque) / `--font-mono` + a **type scale**
  (`--text-xs…2xl`, paired line-heights) in `app/globals.css`'s `@theme`, extending
  the existing tokens (palette is already dark/warm-neutral and close to the
  screenshot's near-black surface).
* Load via `next/font` (self-hosted, no layout shift). **No serif** — stay faithful
  to the Cursor sans+mono look.
* Reproduce three screenshot cues: **bold inline emphasis** for key terms,
  **inline-code chips** (mono on a faint tinted background), and a **clean bordered
  table** (header row, generous row padding) — these are markdown-render styles (F4).
* Keep dark + light parity (globals.css already defines both); the screenshot is dark.
* **Pitch-deck alignment:** pull exact brand colors (and any embedded font) from the
  deck when it's available and reconcile the accent/surface tokens. *(The `.pptx`
  files present at session start were not on disk at extraction time — grounded on
  the screenshot + existing tokens for now; will reconcile to the deck on request.)*

**Acceptance:** the four layers are visually distinguishable at a glance; no web-font
layout shift (CLS ≈ 0); `eval`-mode captures render identical fonts headless.

---

## 8.5 Architecture alignment (FRONTEND_ARCHITECTURE + deep dives)

> Added 2026-06-11 after reconciling against
> [`FRONTEND_ARCHITECTURE.md`](../Architectures/FRONTEND_ARCHITECTURE.md),
> [`FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md`](../Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md),
> and [`FRONTEND_PORT_DEVIATIONS_V3.md`](../Architectures/FRONTEND_PORT_DEVIATIONS_V3.md).
> **This reframes the whole plan: it is an architecture-conformance task, not a
> green-field UI build.**

### The core realization

The documented frontend is a strict **hexagonal ports-and-adapters ring** with hard
invariants **F-R1…F-R9**. The entire ring is **already built and tested** in
`frontend/lib/`: 8 ports, every adapter family (`runtime/`, `ui_runtime/`,
`tool_renderer/`, `auth/`, `thread_store/`, `feature_flags/`), 4 translators,
`transport/sse_client.ts`, `transport/edge_proxy.ts`, both wire kernels, `trust-view/`,
and `composition.ts`. The backend wire
([`agent_ui_adapter/wire/ag_ui_events.py`](../../agent_ui_adapter/wire/ag_ui_events.py))
defines `ToolCallStart/Args/End`, `ToolResult`, `StepStarted/Finished`,
`StateSnapshot/Delta`, `Custom`. The runtime adapter
[`self_hosted_langgraph_dev_client.ts`](../../frontend/lib/adapters/runtime/self_hosted_langgraph_dev_client.ts)
already exposes `createRun()` + `streamRun()` and is wired to `sse_client` +
`ag_ui_to_ui_runtime`.

**The only thing off-architecture is `app/chat-shell.tsx`** — a self-described
placeholder that does a **raw `fetch("/api/run/stream")`** and parses SSE by hand. That
single file **violates the documented invariants**:

| Invariant | How `chat-shell.tsx` violates it | Fix |
|---|---|---|
| **F-R1** (no domain logic / run-lifecycle in components) | Owns SSE parsing, run lifecycle, error mapping, message reduction inline | Move all of it behind `AgentRuntimeClient` (`createRun`/`streamRun`) + the UIRuntime port |
| **F-R8 / A4** (no raw wire past adapter; ports yield `UIRuntimeEvent`) | Reads raw SSE frames + ad-hoc JSON in the component | Consume translated `UIRuntimeEvent`s from `streamRun()` only |
| **Runtime Contract §1** (stream ends `run_completed`/`run_error`) | No terminal-state handling — message just stops growing | Drive F2 terminal state off `run_completed`/`run_error` |
| **F-R7** (forward `trace_id`, never generate) | Generates `assistantId` via `crypto.randomUUID()`; ignores backend `trace_id` | Use the backend `trace_id` from `streamRun()` events (powers F6) |

### Consequence for the feature plan — every feature maps to an existing seam

Re-grounding F1–F12 on the real ring (so we **wire**, not invent):

| Feature | Architecture seam it uses (already exists) |
|---|---|
| **F1** (wire the runtime in) | Replace `chat-shell` fetch with `AgentRuntimeClient.createRun/streamRun` from `composition.ts`; consume `UIRuntimeEvent`. **This is the keystone and it's now "use the port that exists."** |
| **F2** terminal state | `RunCompletedEvent` / `RunErrorEvent` (Runtime Contract §1 guarantees the terminal event) |
| **F3** tool trajectory | `ToolCallStart→ToolResult` → `tool_event_to_renderer_request` → `ToolRendererRegistry` → `ToolCard` (the orphaned component) |
| **F5** model badge / step meter | `ModelSwitchEvent` + `StepEvent` (wire defines `step_count`, `total_cost_usd`, `tokens_in/out`) → existing `StreamingMarkdown` props |
| **F6** trace chip | `trace_id` on every `UIRuntimeEvent` + `trust-view/RunIdentity` |
| **F8** loading indicator | `run_started` → `RunCompletedEvent`; phase from `StepEvent`/`ToolStart` |
| **F9** task list | `StateSnapshot`/`StateDelta` (the `state_todo` `state_delta` rides this). **Caveat:** `StateMutated`/`StateDelta` is marked *"Phase 2"* in the wire deep dive — see §8.6 doc-gap A. |
| **F10** reasoning | No reasoning event in the wire today → `Custom` event (deep dive shows `Custom{name,value}`; translator already special-cases `CUSTOM name==="step_meter"`). See §8.6 doc-gap B. |
| **F11** guaranteed answer | `RunCompletedEvent.final_message` (wire already carries it!) is the backend guarantee surface; frontend fallback if it's empty |
| **F4 / F12** markdown + type theme | Pure component/CSS layer — `StreamingMarkdown` + `globals.css`; no port impact, fully architecture-neutral |

**Net:** F1–F8, F11 require **zero new ports and zero new wire shapes** — they consume
events the architecture already defines. The work is (a) delete the placeholder SSE
code from `chat-shell.tsx`, (b) consume `streamRun()` via `composition.ts`, (c) render
the translated events. That is *less* code than the placeholder, and it makes the
component F-R1-compliant.

### Architecture rules this plan must honor

* **C1 / F-R1:** no run-lifecycle logic in `chat-shell.tsx` or any component. The
  reducer over `UIRuntimeEvent` belongs in the `UIRuntime` adapter / a hook fed by the
  port — not in the component.
* **F-R2 / F-R8:** `ToolCard`, `StreamingMarkdown`, task-list, reasoning components
  take **`wire/` or `ui_runtime_events/` props only** — never CopilotKit/SDK types. The
  F10 cheap-summary call (if backend) lives behind the runtime, not in a component.
* **F-R5:** the F10 reasoning-summary **prompt** is a Jinja template in `prompts/`, not
  a TS string. (This pushes F10 Tier 2 to the backend regardless — see §8.6.)
* **F-R7:** F6's trace chip reads the forwarded `trace_id`; the browser never makes one.
* **Substrate-swap:** everything stays in `ports`/`translators`/`wire`, so V2↔V3 is
  unaffected; new behavior must not leak into a composition root as logic.
* **Eval-mode (D-A):** implement as a `FeatureFlagProvider` flag (the port exists),
  not an ad-hoc `?eval` read scattered in components.

---

## 8.6 Suggested architecture changes / improvements

Reconciling the plan surfaced **four genuine gaps** where the architecture (or its
docs) needs a small, deliberate extension. None are violations of the design — they
are the "introduce the abstraction when the second case arrives" moments.

**A. `StateDelta` is "Phase 2" but F9 needs it now.**
The wire deep dive marks `StateMutated`/`StateDelta` as *Phase 2* (`delta: z.unknown()`,
"populated in Phase 2"). The `state_todo` tool already emits `state_delta={"todos":…}`
**today**, so the task list (F9) needs Phase-2 state to land now. *Suggestion:* promote
`StateDelta` to Phase 1 with a typed `todos` projection in `ui_runtime_events.ts` (a new
`TaskListUpdate` UI-runtime shape), and add the `StateSnapshot/Delta → TaskListUpdate`
row to the `ag_ui_to_ui_runtime` contract table. Keep the generic JSON-Patch `delta`
for everything else.

**B. No reasoning event in the wire — decide `Custom` vs. a first-class event.**
There is no `ReasoningStart/Content` in the local wire (AG-UI defines them upstream).
F10 Tier 1 (live narration) needs none — it's a pure frontend reduction over existing
events. F10 Tier 2 (cheap summary) needs a channel. *Suggestion:* ship Tier 2 over the
existing `Custom{name:"reasoning_summary", value}` event (zero wire change, matches the
`step_meter` precedent), and only promote a first-class `ReasoningEvent` if a second
consumer appears (abstraction-introduction principle). Document the `Custom` event-name
registry (`step_meter`, `reasoning_summary`, …) in the wire deep dive so they're not
ad-hoc.

**C. `RunCompletedEvent.final_message` should be the F11 guarantee — make it
load-bearing.** The wire already carries `final_message` on `run.completed`. *Suggestion:*
make it a **documented contract** that `final_message` is always non-empty (the backend
"always emit a closing answer" guarantee, D-C) — add it to the Runtime Contract as a 5th
rule, and have the frontend fallback trigger only when it's empty. This turns F11's
backend half into an architecture invariant instead of a prompt-only convention, and it
directly fixes the inadmissible-capture root cause at the wire level.

**D. `ToolCard` / generative components live in `frontend/components/`, outside the
`lib/` ring — clarify where presentational components sit.** The architecture docs spec
`lib/ports|adapters|wire|translators|transport` exhaustively but are mostly silent on
`frontend/components/` and `app/` (the React tree). `ToolCard`, `StreamingMarkdown`,
the task-list, and reasoning components are presentational and must obey F-R1/F-R8 but
aren't "adapters." *Suggestion:* add a short "Presentation layer" section to
`FRONTEND_ARCHITECTURE.md` stating that `components/` + `app/` consume **only**
`wire/`/`ui_runtime_events/`/`trust-view/` types via the `UIRuntime` port, never
`adapters/` or SDKs — i.e. make the implicit F-R1 boundary for the view layer explicit,
and note that `app/chat-shell.tsx` is the current exception to fix (tech-debt callout).

**E. Browser-facing stream transport stays `fetch`-readable — RESOLVED (Option A).**
The runtime adapter's `streamRun()` is currently wired through
`transport/sse_client.ts`, whose `connectSSE` uses **`EventSource`**, and the
composition root (`makeOpenUIRuntimeStream`, `lib/composition.ts:112-130`) requires a
browser-side `eventSourceFactory`. `page.route` cannot intercept `EventSource`
([Playwright #15353](https://github.com/microsoft/playwright/issues/15353)), so the
repo's existing T1 stream mocks (which `page.route("**/api/run/stream")`) would silently
stop intercepting the moment F1 routes the browser through `streamRun()` as currently
composed.

**Decision (taken 2026-06-11):** the **browser consumes the BFF SSE stream over
`fetch`+`ReadableStream`, never `EventSource`.** This is now a binding architecture rule,
not an open question. Concretely:

- **Add a `connectFetchSSE` transport adapter** in `lib/transport/` that does
  `fetch()` → `res.body.getReader()` → SSE frame-parse → `AGUIEventSchema.parse` →
  `yield AGUIEvent`. It is a drop-in alternative to `connectSSE` behind the same
  `(opts) => AsyncGenerator<SSEYield>` shape, so `makeOpenUIRuntimeStream` swaps the
  transport **behind the `AgentRuntimeClient.streamRun()` port** — the browser still
  consumes the port (F-R1/F-R7/F-R8 satisfied), only the wire mechanism changes.
- **Source it from the working code we already have.** `chat-shell.tsx:90-144` is a
  functioning fetch-SSE reader today; F1 *promotes* that loop into `connectFetchSSE`
  rather than deleting it. The translator (`agUiToUiRuntime`), the wire schema
  (`AGUIEventSchema`), and the parse-error sentinel pattern are reused verbatim.
- **`connectSSE`/`EventSource` stays in the tree, unused by the browser.** It remains
  available for any *server-side* consumer that wants `EventSource` semantics; it is no
  longer on the browser composition path.
- **Drop `connectSSE`'s heartbeat-timeout + Last-Event-ID resumption** (decided
  2026-06-11). `connectFetchSSE` reads to EOF with no resumption — matching today's
  `chat-shell.tsx`, which already has neither. Rationale: eval runs are short (~30 s
  traces) and reload-to-retry is acceptable; resumption is a long-agent concern, not an
  eval-trace one. If a long-run consumer ever needs it, `connectSSE` is the place for it,
  server-side. *(This trade is recorded so it isn't silently lost: the fetch path is
  intentionally thinner than the EventSource path.)*

Why Option A over the alternatives (full trade-off table in §8.8): mocking at **T2**
(mock backend) instead would push a server process into the per-commit gate and rewrite
3 specs (friction the Playwright skill warns against); an **env-selected dual transport**
(fetch in test, EventSource in prod) is **Determinism Theater** (TDD Anti-Pattern #3) —
it green-lights a browser path the user never runs. Option A is the only choice that
keeps the per-commit T1 net **and** tests the real browser path **and** lands the shell
on the architecture's port. Document the rule next to the `transport/` import rules in
`FRONTEND_ARCHITECTURE.md`. Full analysis in §8.8.

**Also worth a doc note (not a change):** `FRONTEND_PORT_DEVIATIONS_V3.md` already
records that `streamRun()` yields **`UIRuntimeEvent`** (post-translation), not raw
`AGUIEvent` — so any plan text implying components see `AGUIEvent` is wrong. Wave A/B
components consume `UIRuntimeEvent` only. (This plan's §3/§8 specs are updated to say so.)

**F. Port surface follows the single-POST protocol — RESOLVED during F1 (2026-06-11).**
Implementation surfaced a fact the §3-F1 text missed: the middleware exposes exactly
`POST /run/stream` (response body IS the SSE stream) + `POST /run/cancel`. There is no
create-then-stream-by-id pair, so `createRun(req) → RunStateView` could never work
against the real BFF (it expected JSON from an SSE endpoint) and `streamRun(runId)` had
nothing to stream from. **Decision:** the port models the consumer's need directly —
`AgentRuntimeClient.streamRun(req: RunCreateRequest)` starts the run and yields its
`UIRuntimeEvent`s; `createRun` is removed (a future create/stream substrate, e.g.
LangGraph Platform SaaS, composes both calls behind the same method). HTTP-status →
`run_error{error_type}` mapping (401/403/429/5xx) moved from thrown adapter errors into
the composition stream, using the closed `RunErrorType` enum. A second composition entry,
`lib/composition_browser.ts`, owns the browser slice (fetch-SSE + translators + tool
aggregator + Runtime-Contract-§1 terminal-event enforcement) so the WorkOS server SDK
never enters the client bundle; the layering test blesses it as composition-ring.
`tool_render` joined the `UIRuntimeEvent` union (typed projection of
`ToolCallRendererRequest`) so trajectory segments ride the same channel as text.

**Correction to §8.6-C (found during F11, 2026-06-11):** the wire `RunFinished` does
**not** carry `final_message` — that premise was wrong. The implemented F11 contract:
(a) the graph's continuation logic (`react_loop._should_continue`) already forces a
synthesis pass after tool results on the normal path (the backend half, pre-existing);
(b) the frontend `synthesizeFallbackAnswer` translator guarantees a non-empty answer
slot for abnormal terminations (budget / max-steps / no-progress runs that complete
without prose), rendered with a visible "summary generated from tool results" marker.
Promoting `final_message` onto `RunFinished` remains open as a wire enhancement if the
T3 batch shows the two layers above leave gaps.

---

## 8.7 TDD discipline (mandatory) — per `research/tdd_agentic_systems_prompt.md`

> **Every feature in this plan ships test-first.** Implementation follows the
> [TDD Analysis Agent for Agentic Systems](../../research/tdd_agentic_systems_prompt.md):
> Red → Green → Refactor, **failure paths first**, behavior over implementation, and
> tests written *at the correct uncertainty layer*. No feature is "done" until its
> tests are green *and* the 8-check self-validation suite passes for the change.

### Mapping the Agentic Testing Pyramid onto the frontend ring

The frontend ring mirrors the four-layer backend, so the pyramid maps directly. This
tells us **which test strategy each feature uses** — applying the wrong one is the
"Layer Alignment" failure (Check 2).

| Pyramid layer | Frontend modules | Determinism | Strategy | CI |
|---|---|---|---|---|
| **L1 Deterministic** | `wire/` (Zod schemas), `trust-view/`, pure reducers, type-scale/markdown render helpers | ZERO — exact + property | Pure Red-Green-Refactor; property tests on parse/translate | every commit, <10s, zero flake |
| **L2 Reproducible** | `translators/`, `transport/sse_client` + `edge_proxy`, `ports/` conformance, adapters w/ mocked SSE/fetch | LOW — contract + record/replay | Contract-driven TDD; **mock the SSE stream**, never a live agent | every commit, <30s |
| **L3 Probabilistic** | the live `streamRun()` against a real agent (trajectory: does a tool card appear? is the task list ticked?) | MEDIUM — aggregate | Eval-driven; the **Playwright `goaljudge-batch`** run, trajectory assertions | scheduled / on-demand, **never per-commit** |
| **L4 Behavioral** | end-to-end "admissible capture" across the registry; eval-mode determinism | HIGH | Simulation/binary-outcome (the GoalJudge eval itself) | on-demand only |

**The determinism boundary for this plan:** everything that makes the UI *render
correctly given an event stream* is L1/L2 and must be **fully deterministic and in CI**
(mock the stream — Pattern 5/6). Everything that depends on *what the real agent does*
is L3/L4 and lives in the Playwright batch, **never gating a commit** (Anti-Pattern 5:
no live agent/LLM in CI).

### Per-feature TDD plan (write these tests first)

| Feature | Layer | Red-first tests (failure path leads) | Anti-patterns to avoid |
|---|---|---|---|
| **F1** runtime port wiring | L2 | `streamRun()` consumed via a **mock SSE** adapter: assert reducer builds correct `segments` from a recorded event sequence; **failure-first:** `run_error` → `status:"error"`; mid-stream disconnect → terminal error; missing `trace_id` → synthetic `RunErrorEvent` (transport contract) | Mock Addiction (use the real translator + a recorded stream, not a hand-stubbed reducer); Determinism Theater (assert structure, not agent text) |
| **F2** terminal state | L1/L2 | reducer maps `run_completed`→`complete`, `run_error`→`error`; **failure-first:** stream that ends *without* a terminal event surfaces an error state (Runtime Contract §1) | Gap Blindness (test the no-terminal and error cases before the happy path) |
| **F3** tool trajectory | L1/L2 | `tool_event_to_renderer_request` already tested — add: interleave ordering of text+tool segments; `ToolCard` renders `running/completed/errored`; **failure-first:** `ToolEnd` with `error` → errored card | Tautological (don't re-derive the translator in the test; feed events, assert rendered output) |
| **F8** loading indicator | L1 | pure phase-derivation fn: `(events)→phase`; **failure-first:** `run_error` → no spurious `done`; eval-mode flag → static (no animation class) | Determinism Theater (phase from events, not timers) |
| **F9** task list | L1/L2 | `StateDelta{todos}` projection → `TaskListUpdate` (new shape, §8.6-A); status icon mapping; **failure-first:** `cancelled`/`subtask-dropped` leaves item not-done; malformed delta → ignored, not crash | Mock Addiction (drive with real `state_todo` output fixtures) |
| **F10 Tier1** live narration | L1 | pure `(events)→narration line` reduction; deterministic given a fixed event list; **failure-first:** unknown tool name → graceful generic phrasing | Determinism Theater |
| **F10 Tier2** cheap summary | **L3** (backend) | reasoning summary is an LLM call → **mocked provider** for the deterministic scaffolding (input assembly, empty-trajectory skip, cost-cap guard) at L2; quality only via **rubric eval** at L3, never exact-match; prompt is a Jinja template (F-R5) tested for render | Live LLM in CI (mock it); Determinism Theater (rubric, not string match) |
| **F11** guaranteed answer | L1/L2 (FE) + L3 (BE) | FE fallback: `run_completed` with empty `final_message` → synthesized recap from trajectory (deterministic); **failure-first:** empty answer slot is the bug under test — assert it's *never* empty; BE: `final_message` non-empty contract (§8.6-C) tested in the adapter | Gap Blindness |
| **F4** markdown | L1 | render helper: fenced code, tables, inline-code chips, bold; **failure-first:** partial/broken fence mid-stream doesn't throw; no `dangerouslySetInnerHTML` of unsanitized input | Tautological |
| **F12** typography | L1 | token presence + role→class mapping assertions; no web-font CLS (computed-style test); light/dark parity | — |
| **all** | L1 | **architecture conformance** (`test_frontend_layering.ts`, Pattern 7): the new `chat-shell` imports the **port**, not raw `fetch`; no component imports `adapters/` or an SDK (F-R1/F-R2/F-R8) | Cross-Layer Dependency Leak |

### Definition of Done (per feature)

A feature is done only when **all** hold (the doc's exit criteria + self-validation):

1. **Red first:** the failure-path test was written and observed failing before code.
2. **Green:** all L1/L2 tests pass; suite stays <30s; zero flake over 10 runs (Check 7).
3. **Layer-correct:** assertions match the pyramid layer (Check 2) — no live agent in CI
   (Check 8); L3 trajectory checks live in the Playwright batch, tagged, not per-commit.
4. **Failure paths covered:** every new decision point has a rejection test before its
   acceptance test (Check 4) — for this plan that means error/empty/cancelled/malformed
   stream cases for F1/F2/F9/F11.
5. **No anti-patterns:** Check 5 scan clean — in particular no Determinism Theater
   (never assert exact agent output) and no Mock Addiction (use real translators + a
   recorded stream over hand-stubbed reducers).
6. **Architecture conformance test green:** `test_frontend_layering.ts` + port
   conformance pass — the F-R1/F-R7/F-R8 fixes from §8.5 are *proven by test*, not just
   asserted in prose.

### TDD reference for backend tasks

The two backend tasks this plan creates — emitting tool/step/state events in
[`domain_to_ag_ui.py`](../../agent_ui_adapter/translators/domain_to_ag_ui.py) (§8.5) and
the guaranteed `final_message` (§8.6-C) — are **L2 contract-driven** (Protocol B):
write the consumer-driven contract test (Pattern 4) that asserts the emitted
`AGUIEvent` sequence for a recorded `DomainEvent` input, **failure paths first**
(tool-error → `ToolEnd.error`; empty model output → still a non-empty `final_message`),
using record/replay (Pattern 5), no live LLM.

---

## 8.8 Playwright E2E validation (per `docs/skills/playwright-agentic-e2e`)

> TDD (§8.7) covers L1/L2 with mocked streams. **Playwright is how we validate the
> rendered UI** — at the right *cut-point* (the skill's organizing idea). The repo
> **already has the tier taxonomy and the specs**; this plan mostly *unblocks specs
> that are written but skip today*, then adds new ones per feature.

### The cut-point ↔ pyramid mapping (reuse, don't reinvent)

The skill's mock cut-points map onto §8.7's pyramid 1:1. The repo's `package.json`
already encodes the tiers — **adopt them** (skill rule: "adopt the repo's taxonomy"):

| Skill tier | Cut | Repo script | Pyramid | When |
|---|---|---|---|---|
| **T1 mocked** | `page.route("**/api/run/stream")` returns canned SSE | `test:e2e:t1` (grep-invert `@t2/@t3/@visual`) | L1/L2 | **per-commit CI** |
| **T2 integration** | mock middleware HTTP server | `test:e2e:t2` (`MOCK_MIDDLEWARE=1`) | L2 | nightly |
| **T3 full-stack** | nothing — live agent + model | `test:e2e:t3` (`e2e/full-stack/`, the `goaljudge-batch`) | L3/L4 | on-demand / release gate |
| **Visual** | snapshot (mocked) | `test:e2e:visual` (`E2E_BYPASS_AUTH=1`) | L1 | per-commit (for F12/markdown) |

**Golden rule (skill + §8.7 agree):** only **T1 + visual** gate a commit. T3 (live
model) is on-demand — it costs money and a live model is inherently a bit flaky.

### The specs already exist and *describe the target UI* — they skip today

The repo ships T1 specs written against the UI this plan builds, and they
**`test.skip()` when the component isn't rendered** — so they're green-by-skip on the
placeholder and will *light up* as F1–F3 land. These are our executable acceptance
criteria, already in-tree:

| Spec | Asserts (skill-aligned: structure, not prose) | Unblocked by |
|---|---|---|
| [`e2e/tool-cards.spec.ts`](../../frontend/e2e/tool-cards.spec.ts) | `data-testid='tool-card'` renders; `<details>` collapse; **errored tool → error state** (failure-first) | **F3** |
| [`e2e/streaming.spec.ts`](../../frontend/e2e/streaming.spec.ts) | streamed content in `article div[aria-live='polite']` (FE-AP-5: polite never assertive) | **F1/F2/F4** |
| [`e2e/chat-shell.spec.ts`](../../frontend/e2e/chat-shell.spec.ts), `run-controls`, `observability` | shell wiring, run lifecycle, trace propagation | **F1/F2/F6** |
| [`e2e/full-stack/goaljudge-batch.spec.ts`](../../frontend/e2e/full-stack/goaljudge-batch.spec.ts) | the registry batch; `tool_card_count`, `response_text`, screenshots | **F3/F11** (T3) |

### ✅ Transport decision that makes-or-breaks T1 mocking — DECIDED (Option A, 2026-06-11)

The single most consequential field (skill §"the one decision"): **`stream_transport`.**
There was a split in the repo, now resolved by an explicit rule (§8.6 gap E). The facts
that forced the decision:

* `app/chat-shell.tsx` streams via **`fetch()` + `getReader()`** → `page.route` **can**
  intercept it. Today's T1 specs mock `**/api/run/stream` and work *because* of this.
* `lib/transport/sse_client.ts`'s `connectSSE` uses **`EventSource`**, and the
  composition root (`makeOpenUIRuntimeStream`, `lib/composition.ts:112`) requires a
  browser-side `eventSourceFactory` to feed `streamRun()`. **`page.route` does NOT
  intercept `EventSource`** ([Playwright #15353](https://github.com/microsoft/playwright/issues/15353)).
* **Nothing in the browser calls `streamRun()` today** — the `EventSource` path is
  unit-tested but never exercised by a real composition root, so choosing the fetch path
  costs us no shipped behavior.

**Decision: the browser reads the BFF SSE stream over `fetch`+`ReadableStream`, never
`EventSource`.** F1 adds a `connectFetchSSE` transport adapter (promoted from
`chat-shell.tsx:90-144`) and wires it into `makeOpenUIRuntimeStream` **behind the
`streamRun()` port** — the browser still consumes the port, only the wire mechanism
changes. `connectSSE`/`EventSource` stays in the tree for any future server-side
consumer. Heartbeat-timeout + Last-Event-ID resumption are **intentionally dropped** on
the fetch path (eval runs are short; reload-to-retry is fine). Full rule + rationale in
§8.6 gap E.

This **preserves the per-commit T1 safety net** (`page.route` keeps intercepting), tests
the **real browser path** (no Determinism Theater), and lands the shell on the
architecture's port. The two alternatives were rejected: **(b) move streaming to T2**
(mock-middleware HTTP) pushes a server process into the fast gate and rewrites 3 specs;
**(c) env-selected dual transport** tests a path the user never runs (TDD Anti-Pattern #3).

| Option | T1 net | Tests real path | New code | Verdict |
|---|---|---|---|---|
| **A — fetch reader behind `streamRun()`** | ✅ preserved | ✅ yes | `connectFetchSSE` (~80 LOC, promoted from chat-shell) | **CHOSEN** |
| B — keep EventSource, mock at T2 | ❌ T1 streaming goes dark | ✅ yes | rewrite 3 specs + CI mock backend per-commit | rejected (slow gate) |
| C — env-selected dual transport | ✅ in test | ❌ prod path untested | dual wiring | rejected (Determinism Theater) |

### Per-feature Playwright validation (tier + what to assert)

Following the skill's non-negotiables — **assert structure/provenance, not LLM prose;
wait by text-settle (`waitForResponse`), never `finished()`; scope to
`article div[aria-live='polite']` or a `data-testid`, never bare `[aria-live]`** (Next's
router announcer is `aria-live="assertive"`):

| Feature | Tier | Assertion (stable across runs) | New `data-testid` to add |
|---|---|---|---|
| **F1** runtime wiring | T1 | message renders from a canned SSE sequence; `run_error` event → error UI; **transport: `page.route` still intercepts** (proves decision (a)) | `message-content` |
| **F2** terminal state | T1 | `data-state` transitions `streaming→complete`; capture at `[data-state='complete']` is never a status-feed-only frame; no-terminal stream → error | `data-state` attr |
| **F3** tool trajectory | T1 | un-skip `tool-cards.spec.ts`; card count = canned tool events; errored tool → error card; interleave order text/tool | `tool-card`, `data-tool-count` |
| **F8** loading | T1 | `data-run-phase` advances on canned `step`/`tool` events; **eval-mode flag → no animation class** (snapshot-stable) | `data-run-phase`, `run-status` |
| **F9** task list | T1 | canned `StateDelta{todos}` → checklist; status icons; `3/5` count; **cancelled item stays not-done** | `todo-item`, `data-todo-count/done` |
| **F10** reasoning | T1 (Tier1) / T3 (Tier2 quality) | Tier1 narration line from canned events; "Show reasoning" expander toggles; **Tier2 prose only judged at T3 via LLM-judge, never exact-match** | `reasoning-narration`, `reasoning-summary` |
| **F11** guaranteed answer | T1 + T3 | T1: canned `run_completed` w/ empty `final_message` → fallback recap renders (answer slot never empty); T3: `goaljudge-batch` `response_text` non-empty for 100% of cases | `answer-content` |
| **F4** markdown | Visual | snapshot of fenced code + table + inline-code chip; broken-fence mid-stream doesn't throw | — |
| **F12** typography | Visual | per-layer font/role snapshot (sans answer, mono tool I/O); light+dark; **no web-font CLS** | layer classes |
| **eval-mode** (D-A) | Visual + T3 | frozen mode produces deterministic, animation-free captures across the registry → admissibility 100% | — |

### Server-side verification (T3 only) — `scripts/verify_run.py`

A green DOM assertion proves the *frontend* rendered; for the agentic path also prove
the *backend* did the right thing (skill §5). The repo already has
[`scripts/verify_run.py`](../../scripts/verify_run.py) and the workspace playwright
skill's Cloud-Logging gotchas (bridge line in `jsonPayload.message`; thread form
`session-gj-XXX`; strip the status-feed prefix before the answer-presence check). For
F3/F11 the T3 check is: **every case's tool calls + final answer that render in the DOM
also appear in the Langfuse trace** (DOM ↔ trace reconciliation) — and the `trace_id`
in the F6 chip matches the trace. Encode the join key via a structured `thread_id`
(skill §"injecting a join key") — **never** a client-generated `trace_id` (F-R7).

### CI wiring (what changes)

* **Per-commit:** `test:e2e:t1` + `test:e2e:visual` must stay green — un-skipping
  `tool-cards`/`streaming` means they now actually execute, so F1–F3 must satisfy them.
* **Nightly:** `test:e2e:t2` (transport/proxy survival for the F1 stream).
* **On-demand / release gate:** `test:e2e:t3` (`goaljudge-batch`) for F3/F11/eval-mode
  + `verify_run.py` DOM↔trace reconciliation. **No live model in per-commit CI**
  (skill golden rule = §8.7 Anti-Pattern 5).
* New testids above are added **in the same commit as the feature** (TDD: the
  un-skipped/new spec is the failing-red test written first).

---

## 9. External research — best practices (2026)

Folded into the decisions above:

* **Observability/transparency builds trust** — surfacing tool calls, reasoning, and
  multi-step progress beats a black box; the best agent UIs visualize tool calls and
  decision trees automatically. → F3, F8, F9, F10.
* **To-do lists are a first-class agent UI pattern** — Claude Code / Codex / Cline
  break work into a live, updating checklist with dependencies; visible progress is
  expected for multi-tool/long-running work. → F9 (and we already have `state_todo`).
* **Streaming is expected; protect TTFT/inter-token latency** (>400–800 ms frustrates).
  Keep the *answer* on the fast path; do summary work off-critical-path. → F8, F10.
* **Progressive disclosure** — reveal complexity gradually (name → detail → on
  demand); the cost/latency-minimizing way to surface reasoning. → F10 Tier 2 behind
  an expander; F9 "show all".
* **Model routing / small-model summarization** — reserve premium models for hard
  reasoning; use cheap/fast tiers for routine summarization; routing cuts cost 70%+.
  → F10 Tier 2 uses the existing cheap D6 tier, once per run.
* **AG-UI has purpose-built events** — `ActivitySnapshot/Delta (activityType:"PLAN")`
  for task lists and `ReasoningStart/ReasoningMessageContent` for reasoning. Our local
  `lib/wire/ag_ui_events.ts` models a subset (no Activity/Reasoning yet); F9/F10 ride
  on `STATE_DELTA` + `CUSTOM` today, with a clean upgrade path to native events later.
* **Typography (Cursor reference)** — Cursor ships a bespoke type system via the
  Kimera foundry: **Cursor Gothic** (a grotesque/"gothic" sans built on *Waldenburg*)
  for UI/body and **Cursor Mono** for code — proprietary, so we mimic with free
  grotesque-sans + mono substitutes. The Cursor look is **sans + mono only (no
  serif)**; we separate information layers within that system by family/weight/size/
  color, plus the inline-code-chip + bold-emphasis + table cues from the screenshot.

Sources:
[Fuselab — Agent UX 2026](https://fuselabcreative.com/ui-design-for-ai-agents/) ·
[Fastio — UI frameworks for agents](https://fast.io/resources/best-ui-frameworks-ai-agents/) ·
[Towards Data Science — agents & to-do lists](https://towardsdatascience.com/how-agents-plan-tasks-with-to-do-lists/) ·
[Prompting Guide — LLM agents (ReAct/plan-execute)](https://www.promptingguide.ai/research/llm-agents) ·
[Latitude — real-time LLM latency](https://latitude.so/blog/real-time-llms-optimizing-latency-streaming) ·
[Agentic Design — progressive disclosure UI](https://agentic-design.ai/patterns/ui-ux-patterns/progressive-disclosure-patterns) ·
[MindStudio — model router / 3-tier stacks](https://www.mindstudio.ai/blog/set-up-ai-model-router-llm-stack-c2610) ·
[The Brand Identity — Cursor's Kimera typeface system (Cursor Gothic / Cursor Mono / Waldenburg)](https://the-brandidentity.com/project/how-kimera-built-cursors-identity-around-a-custom-typeface-system) ·
[Cursor Docs — themes & appearance](https://cursor.com/help/customization/themes) ·
[AG-UI events](https://docs.ag-ui.com/concepts/events).

---

## Appendix A — Typography spec (token-level)

Extend `app/globals.css` `@theme` (Tailwind v4). Names mirror the existing scheme.

```css
@theme {
  /* families — self-hosted via next/font; free substitutes for Cursor's faces.
     --font-sans  ≈ Cursor Gothic / Waldenburg (grotesque "gothic" sans)
     --font-mono  ≈ Cursor Mono.  No serif — Cursor's look is sans + mono only. */
  --font-sans: "Geist Sans", "Inter", ui-sans-serif, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;

  /* type scale — 1.2 ratio, paired line-heights */
  --text-xs:   0.75rem;  --leading-xs:   1.4;   /* metadata, trace, step */
  --text-sm:   0.875rem; --leading-sm:   1.5;   /* tool I/O, task list, reasoning */
  --text-base: 1rem;     --leading-base: 1.6;   /* the answer */
  --text-lg:   1.125rem; --leading-lg:   1.5;
  --text-xl:   1.375rem; --leading-xl:   1.3;   /* section headers in answers */
  --text-2xl:  1.625rem; --leading-2xl:  1.2;   /* empty-state hero */
}
```

**Role → style map (the "layered information" system — sans + mono only):**

| Layer | Font | Size / leading | Color | Weight |
|---|---|---|---|---|
| Answer body | sans | base / 1.6 | `--color-fg` | 400 |
| Answer headings | sans | xl / 1.3 | `--color-fg` | 600 |
| Reasoning (synthesized) | sans, **italic** | sm / 1.5 | `--color-muted` | 400 |
| Tool name (card summary) | mono | sm | `--color-fg` | 700 |
| Tool input/output | mono | sm / 1.5 | `--color-muted` | 400 |
| Inline code (in answers) | mono | sm | `--color-fg` | 400, tinted-bg chip |
| Task-list item | sans | sm | by status | 400/500 |
| Metadata (model/step/trace) | mono | xs | `--color-muted` | 500, tracked |

Rationale: with no serif (faithful to Cursor), three signals still separate every
layer — **family** (sans ↔ mono), **size**, and **color/weight/italic**. Answer =
sans regular; reasoning = sans *italic muted* (reads as a quieter "thinking" voice
without leaving the grotesque system); tool I/O + metadata = mono muted; inline code =
mono on a tinted chip, exactly like the screenshot. Substitutes are interchangeable
(Geist Sans ↔ Inter ↔ Hanken Grotesk / Space Grotesk for more Waldenburg character;
Geist Mono ↔ JetBrains Mono ↔ Commit Mono) — lock the pair once the pitch-deck font is
confirmed.

---

## Appendix B — Updated sequencing

```
Wave A:  F1 ──► F2 ──► F3            (admissible, trajectory-bearing captures)
              └─► F5, F6
         F4 (markdown, parallel)
Wave B:  F1 ──► F8 (loading)
              ├─► F9 (task list — render state_todo)
              ├─► F10 Tier 1 (live narration, free)  ──► Tier 2 (cheap summary, lazy)
              └─► F11 frontend fallback
         F11 backend (closing turn)  — agent/graph change, parallelizable
         F12 typography              — independent, parallelizable from day 1
```

Recommended: confirm F1 emission → F2/F3/F9 (the eval-evidence core) → F8/F10-Tier1
(free engagement) → F11 → F4/F12 in parallel → F10-Tier2 → F7 (stretch).

**Execution status (2026-06-11):** done in exactly this order — Phase 0 ✅ →
F1 ✅ → F2/F3/F9 ✅ → F8/F10-Tier1 ✅ → F11 ✅ → F4/F12 ✅ → F5/F6/F7 ✅.
Only **F10-Tier2** remains. Commit map in §0.
