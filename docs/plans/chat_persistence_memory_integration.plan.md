# Chat Persistence + Memory Integration

> **Status:** Phase A IMPLEMENTED (2026-06-19, uncommitted); Phase B PROPOSED.
> Research-backed. Builds on the shipped UI refresh
> ([`ui_left_panel_refresh.plan.md`](ui_left_panel_refresh.plan.md),
> commit `01863ec` — SidebarPanel / Recents).
>
> **Phase A delivered:** `ThreadStore.appendTurn` port + `NeonFreeThreadStore`
> impl (idempotent, append-only); optional client `thread_id` + provisional
> title (via `metadata.first_message`) through the wire (Python source-of-truth
> + TS mirror + regenerated drift baseline / openapi.yaml / wire-types.ts);
> `makeThreadAppendHandler` + `POST /api/threads/[id]/messages` route;
> `useChatSidebars.createThread`/`persistTurn` (+ pure `createThreadRequest`/
> `appendTurnRequest`); `useAgentRun(runtime, persist)` fires auto-create on
> first send + per-turn persist on completion (fire-and-forget, never breaks the
> live run). Verified: 777 vitest, 86 architecture, 63 drift, 393 Python adapter
> + 109 middleware, 2 stateful persistence e2e (save→Recents→resume), tsc clean.
> **Companion:** [`chat_persistence_memory_integration.design.md`](chat_persistence_memory_integration.design.md)
> (data model, sequences, the hybrid trade-off table, testid contract).
> **One-line:** Save **all** user chats durably and make Recents resume from
> that durable record; then surface, per chat, which memories were recalled —
> with a reject (soft-suppress) action — for dev/user evaluation.
> **Owner:** frontend BFF + a thin middleware read-back; no trust-kernel changes.
> **Constraint:** Reuse existing seams. The `threads` table already HAS a
> `messages` JSONB column ("the resume path replays this" — schema.ts) and a
> reserved `thread_messages` table; this is **finishing the wiring**, not new
> infra. SDK imports stay in `lib/adapters/**` (F-R2); BFF holds no cloud creds
> (F-R9); panels stay dumb (F-R1).

---

## 1. The gap (verified in code)

- The BFF thread store persists thread **metadata only**: `messages: []` is
  hard-coded in every adapter (`neon_free_thread_store.ts:157`,
  `pg_thread_repo.ts`, `neon_thread_repo.ts`). The real transcript lives only in
  the **LangGraph checkpointer** (keyed by `thread_id`).
- A thread **row is created only by an explicit `POST /api/threads`**
  (`handlers.ts:70`). The lazy "New chat" path never POSTs — `useAgentRun`
  mints a `thread_id` on first `send` (`use_agent_run.ts:181`) and streams. So
  **most real conversations never get a Recents row.**
- The `ThreadStore` port has `create / get / list / rename / archive` but **no
  method to append/save messages** — that seam doesn't exist yet.
- The DB schema is ready: `threads.messages` JSONB exists and is documented as
  the resume-replay source; `thread_messages` is reserved for a future
  normalized migration (`db/schema.ts`). `ThreadCreateRequestSchema` already
  accepts a caller-supplied `thread_id`.

## 2. Decision (research-backed, locked)

External consensus (LangChain persistence docs + 2025/26 production guides):
**hybrid** — checkpointer = short-term thread state for *resume/time-travel*;
a separate query-optimized table = the durable, listable history for the UI.
Reading full history from the checkpointer for *display* is a perf concern, and
**checkpoints get pruned for volume** → checkpointer-only history is not durable.

→ **BFF thread store is the durable transcript of record.** Checkpointer stays
authoritative for **resume only**. See the design doc §2 for the full trade-off
table and sourced findings. Locked sub-decisions:

| # | Decision |
|---|----------|
| D1 | **Auto-create the thread row on first send** (client POSTs with the SAME `thread_id` the agent uses, then streams). Empty "New chat" clicks create nothing. |
| D2 | **Persist each completed turn** (`{user, assistant}`) into `threads.messages` (JSONB, v1). The reserved `thread_messages` table stays for a later per-row migration. |
| D3 | **Resume replays from the durable BFF store** (already the code path: `GET /api/threads/[id]` → `messages` → `threadMessagesToTurns`). No checkpointer read needed for display. |
| D4 | **Recents ↔ memory stay separate stores.** Surface **recalled-memories-per-chat** (link recalled memory keys ↔ `thread_id`) for eval. |
| D5 | **Reject = soft-suppress globally**: a rejected memory is no longer recalled/injected and leaves the recall list, but the row is retained/auditable (reuse the memory disable seam). Reversible. |
| D6 | **Deleting a chat keeps derived memories** (independent stores). |
| D7 | **Rollout: persistence first** (Phase A), then the recalled-memory eval/reject UI (Phase B). |

## 3. Phase A — Durable chat persistence (the "save all chats" core)

### A1. ThreadStore gains a message-save seam
- Add to the `ThreadStore` port (`lib/ports/thread_store.ts`):
  `appendTurn(identity, threadId, turn: { user: ChatMessage; assistant: ChatMessage })`
  **or** the simpler `saveMessages(identity, threadId, messages)` (full replace).
  Decision in design §3: **`appendTurn`** (append-only, mirrors the checkpointer
  reducer; avoids clobbering on concurrent turns).
- Implement in `NeonThreadRepo` / `pg_thread_repo` / `InMemoryThreadRepo` as a
  read-modify-write of the JSONB `messages` (v1) — or a JSONB array append. The
  in-memory repo makes it node-testable.
- Contract: append to a missing/not-owned thread throws `ThreadStoreError`
  (collapsed to 404 by the handler — no existence oracle, FD3.SEC).

### A2. BFF route to persist a turn
- `POST /api/threads/[id]/messages` → `makeThreadAppendHandler` (sibling of the
  existing thread handlers): auth → Zod-validate `{user, assistant}` → call
  `threadStore.appendTurn`. Idempotency: include a per-turn id so a retried
  POST is a no-op (dedupe by turn id in the repo).

### A3. Client: auto-create + persist
- `useAgentRun`:
  - On the **first** `send` of a new chat, before streaming, `POST /api/threads`
    with the just-minted `thread_id` (+ a provisional title = the first user
    line, trimmed). Reuse `ThreadCreateRequest` (already takes `thread_id`).
  - On each **completed** turn (run reaches `complete`), `POST
    /api/threads/[id]/messages` with `{user, assistant-text}`.
  - Both are **fire-and-forget with error capture** (persistence failure must
    never break the live chat — surfaced via a non-blocking error, mirrors
    `useChatSidebars.guard`).
- `ChatShell` / `useChatSidebars`: after auto-create, refresh the Recents list
  (the new thread appears immediately) and set it active.
- Title: provisional from first message; the existing rename affordance and/or
  a later autotitle can refine it (out of scope here).

### A4. Tests (TDD, failure-first — FD6/TAP-4)
- `thread_store` repos: `appendTurn` happy path + append-to-missing throws +
  ordering preserved + idempotent re-append (InMemory + a pg contract test).
- `handlers.test.ts`: `makeThreadAppendHandler` — 401 unauth, 400 bad body, 404
  missing/not-owned, 200 appends.
- `use_agent_run`: first-send creates (spy POST /threads with the minted id);
  completed turn POSTs messages; a failing persist does NOT throw into the run.
- E2E (`e2e/full-stack` mocked): send a message → thread appears in Recents →
  reload/resume → transcript replays from the store.

## 4. Phase B — Recalled-memories-per-chat + reject

### B1. Capture which memories were recalled, per thread
- The run already emits a `memory_recalled` domain event (count is folded onto
  the run view; `RecallIndicator`). Extend the wire event / reducer to carry the
  recalled memory **keys** (not just the count) for the turn — content already
  flows server-side; we surface keys for the eval view.
- Persist the recalled keys with the thread (a `recalled_memory_keys` entry in
  `threads.metadata` JSONB, or alongside the turn) so the eval view is durable.

### B2. Eval view in the chat
- Under each assistant turn (or a per-chat panel), a **"memories recalled here"**
  disclosure listing the recalled items (key + type + content), gated to a dev/
  eval surface (reuse the `evalMode`/`?eval=` gate or a settings flag) so prod
  chat stays clean.
- Each item has a **Reject** button.

### B3. Reject = soft-suppress globally
- `POST`/`PATCH` to the memory store marking the item suppressed (reuse the
  existing memory disable/delete seam in `/api/memory`; add a `suppressed` flag
  rather than hard delete). Suppressed items are excluded from recall/injection
  server-side and disappear from the recall list. Reversible (un-suppress).
- Backend: the recall gate filters out suppressed keys for the user.

### B4. Tests
- Wire/reducer: `memory_recalled` carries keys; reducer exposes them per turn.
- Memory store: suppress sets the flag; recall excludes suppressed; un-suppress
  restores. Failure-first (suppress a missing key → typed error).
- Component: the eval disclosure renders recalled items; Reject calls the
  suppress callback; the item leaves the list.
- E2E: recalled list shows after a run; Reject removes it and a re-run does not
  recall it.

## 5. Out of scope / follow-ups
- Normalized `thread_messages` migration (v1 stays inline JSONB).
- Auto-titling chats from content (provisional title + manual rename for now).
- Cascade-delete of memories on chat delete (D6 keeps them).
- Full-text server-side search over transcripts (Recents search stays the
  client-side title filter shipped in the UI refresh).

## 6. Validation
Backend `pytest tests/ -q` + `tests/architecture/` (layer boundaries) for any
middleware read-back; frontend `vitest run` + `tsc --noEmit` + `pnpm test:e2e`
(chromium smoke locally per the T1-too-slow rule, full matrix in CI). The
`agentsframework-playwright` skill supplies commands/selectors.
