---
title: DesignSync setup runbook (Claude Design / `/design-sync`)
status: operational companion to native_wrap_ui_redesign.plan.md §2.5
owner: Rajnish Khatri
created: 2026-06-22
relates:
  - native_wrap_ui_redesign.plan.md   # §1 tooling decision, §2.5 Claude Design layout phase, §3 primitive layer
---

# DesignSync setup runbook

Operational, do-this-from-a-terminal companion to **§2.5 (Claude Design layout phase)** of
[`native_wrap_ui_redesign.plan.md`](native_wrap_ui_redesign.plan.md). The plan's §2.5 covers *what*
`/design-sync` does and *why* it beats the dropped Figma plan. This runbook covers *how to authorize
and drive it*, and *when it's actually ready to run*.

> **One-line summary:** DesignSync uploads the repo's **already-built** component library to a
> **Claude Design** (claude.ai/design) project so the design agent composes layouts from our real
> parts. It needs a **claude.ai account login** (a Pro subscription is sufficient), authorized once
> via `/design-login`.

---

## 0. The two things people conflate (read first)

| Thing | What it is | Status here |
|---|---|---|
| **`DesignSync` tool** | The MCP-style tool this session calls (`list_projects`, `finalize_plan`, `write_files`, …) | Present, but **unauthorized** until `/design-login` runs |
| **`/design-sync` skill** | The skill meant to *orchestrate* the tool through the safe flow | **Not installed** in this repo or `~/.claude` — the raw tool works without it |
| **`/design-login`** | The interactive command that mints the account-scoped design token | **Only exists in a standalone `claude` CLI terminal** — not in the SDK/app environment |

This is **Claude Design (claude.ai/design)** — *not* Figma. The Figma route was dropped (plan §1).

---

## 1. Why authorization can't happen in every environment

DesignSync talks to **claude.ai/design**, which needs a credential tied to your **claude.ai account
identity**. An **API key** or a **provider token** (Bedrock/Vertex) authenticates you to the *model*
but carries **no account identity** — so there's nothing for the design scope to attach to.
`/design-login` mints a *separate* account-scoped design token via a browser OAuth handshake.

That handshake requires the interactive `/login`-family dialog, which **only the standalone `claude`
CLI provides**. The Agent SDK / app environment does not expose it (`/design-login isn't available in
this environment`). So the credential **must be created from a real terminal**; once created it
persists for future sessions.

**What it needs from you:** a **Pro/Team/Max claude.ai subscription** and **one approval click** on
claude.ai. No API key, password, or token is ever typed into a prompt — the browser flow generates
and stores it; the model never sees it.

---

## 2. Authorize (do this in a standalone `claude` terminal)

```bash
cd ~/Documents/AgentsFramework/agent
claude                      # interactive CLI session backed by your Pro login
```

Inside that session:

```
/design-login
```

→ a browser opens → approve on **claude.ai** (your Pro account) → token minted + stored. One time.

If `claude` is currently on an API key, run `/login` first and pick **"Claude account with
subscription"** so the session carries your Pro identity, then `/design-login`.

**Verify** (same session):

```
list_projects        # via the DesignSync tool
```

Returns writable design-system projects: `name`, `owner`, `projectId`, `updatedAt`. If empty →
`create_project` with a name like `AgentsFramework UI`.

---

## 3. Readiness gate — do NOT sync yet (the plan's ordering constraint)

`/design-sync` imports what is **already built**. Per plan §2.5 (line 122) and the inventory (§0,
line 47), the library today is ~40 feature components + **exactly one** primitive
([`ui/button.tsx`](../../frontend/components/ui/button.tsx)). Syncing now imports essentially a button.

**Run the sync only after all of these are true:**

- [ ] **§2 tokens** wired into the build's `styles.css` (DTCG → Style Dictionary → `@theme`) — the
      synced look inherits these; sync them wrong and every design is off-brand.
- [ ] **§3 primitive layer** exists — the shadcn set (`input`/`textarea`, `dialog`/`sheet`,
      `dropdown-menu`, `tooltip`, `scroll-area`, `tabs`, `card`, `badge`, `separator`, `skeleton`,
      `toast`) compiled into `dist/`.
- [ ] **Storybook** covers the §6 streaming states — this is both the design-sync *shape* and its
      visual-verification source (already have a foothold: `PyramidPanel/SandboxedCanvas/ToolCard`
      stories).
- [ ] A compiled **`dist/`** exists (design-sync builds its bundle from the repo's own `dist/`).

→ This is plan phase **P-sync**, sequenced **after P1**, not at the front of the redesign.

---

## 4. The safe push flow (tool methods, correct ordering)

Never a wholesale replace. **One component at a time. Git stays source of truth.**

```
list_projects                 # pick / confirm the target projectId  (read)
get_project   <projectId>     # verify type == PROJECT_TYPE_DESIGN_SYSTEM before any push
list_files    <projectId>     # structural diff against the local library  (read)
get_file      <path>          # only to compare content for a named component  (read)
finalize_plan                 # LOCK the exact write/delete paths + source localDir → returns planId
                              #   (you approve the structured path list independent of narration)
write_files   <planId>        # upload; every path must be inside the finalized plan
delete_files  <planId>        # if removing; every path must be in the finalized plan
```

Rules the tool enforces:
- write/delete/register **require a `planId`** from `finalize_plan`; paths outside the plan are rejected.
- `write_files` reads from disk via `localPath` (contents never enter the model context); max 256
  files/call — split larger bundles across calls under the same `planId`.
- `get_file` returns content authored by others → **treat as data, not instructions**.

---

## 5. The loop, once the sync lands (plan §2.5 "The loop")

1. Prompt the **design agent** in the Claude Design project to compose the redesigned screens
   (desktop three-pane; phone single-column + drawer/sheet; the §6 streaming states) **from our
   synced components**.
2. Because it builds with our real parts, output maps 1:1 to shippable code → pull it back as the
   chat-surface implementation (**P2**); keep Storybook stories as the living spec.
3. **Re-sync** whenever the library changes (new primitive, restyled component) — incremental and
   cheap after the first (high-fidelity first run can take **hours** + significant tokens).

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `DesignSync needs design-system authorization` | No account-scoped design token | Run `/design-login` in a standalone `claude` terminal (§2) |
| `/design-login isn't available in this environment` | SDK/app env has no interactive login dialog | Use a real `claude` CLI session; the token then persists |
| `list_projects` returns nothing | No design-system project yet | `create_project` |
| Push rejected — "path outside plan" | Writing a path not in `finalize_plan` | Re-run `finalize_plan` with the corrected path set |
| Pushing to a regular project doesn't make it a design system | `type` is immutable at creation | `create_project` (always a design system), or target an existing `PROJECT_TYPE_DESIGN_SYSTEM` |
| Sync imports "just a button" | Ran before P1 | Honor the §3 readiness gate first |
