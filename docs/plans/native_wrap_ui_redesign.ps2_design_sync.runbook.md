---
title: PS2 — /design-sync first run (step-by-step walkthrough)
status: complete
created: 2026-06-22
owner: Rajnish Khatri
companion: native_wrap_ui_redesign.plan.md
phase: PS2
todos:
  - sync-library-to-claude-design
---

# PS2 walkthrough — `/design-sync` first run

Sync the **built primitive library** (P1 + PS1) into a **Claude Design project** so the design
agent can compose the redesigned screens from our real components (plan §2.5). This runbook is the
exact sequence for the **first** (high-fidelity) sync.

> **Read first — the two hard truths about this phase**
> 1. **It costs real time + tokens.** A first-time high-fidelity sync visually verifies *every*
>    component and can run **hours of wall-clock + significant tokens** (plan §11). This is a
>    deliberate spend, not a quick command. Re-syncs after this are incremental and cheap.
> 2. **It needs a human-gated login I can't supply.** `/design-sync` writes through your
>    **claude.ai login with design-system access**. If the session has no design scope it prompts
>    `/design-login`. I cannot authenticate for you — you run the login step.

---

## 0. Preconditions (verify before spending the hours)

All of these are **already true** as of end of PS1 — this is the checklist, not new work:

| Prereq | How to verify | State |
|---|---|---|
| Built library `dist/` | `pnpm --dir frontend build:lib` → `frontend/dist/index.js` + `dist/types/*` | ✅ PS1 |
| Storybook builds | `pnpm --dir frontend build-storybook` → `storybook-static/` | ✅ PS1 |
| Tokens wired | `frontend/app/generated-theme.css` exists; `globals.css` imports it | ✅ P0 |
| 14 primitives + stories | `frontend/components/ui/*.tsx` + `*.stories.tsx` | ✅ P1/PS1 |
| `components.json` | shadcn config present at `frontend/components.json` | ✅ P1 |
| **The `/design-sync` skill** | listed in available skills / `~/.claude/skills` | ⚠️ **NOT installed here** — see §1 |
| **claude.ai design login** | `/design-login` succeeds (or design scope already granted) | ⏳ you do this |

Run the one-shot precheck:

```bash
cd frontend
pnpm build:lib && pnpm build-storybook \
  && test -f dist/index.js && test -d storybook-static \
  && echo "PS2 preconditions: library + storybook build OK"
```

---

## 1. Install / locate the `/design-sync` skill  ⚠️ blocker in this environment

The **`DesignSync` tool** (the low-level API) is available, but the **`/design-sync` skill** that
orchestrates it — builds the deterministic bundle, runs the render-check verification loop, writes
`.design-sync/config.json` — is **not installed in this environment**.

You need the skill before the first sync. Options:

- **If you have it elsewhere:** ensure it appears in `/help` or the available-skills list (e.g.
  installed under `~/.claude/skills/design-sync/`). Then invoke `/design-sync` and skip to §2.
- **If you don't:** the sync can still be driven through the raw `DesignSync` tool (the manual path
  in §5), but that means *I* hand-build the bundle + run the verification, which is exactly the
  hours-long, token-heavy work the skill automates. Prefer the skill.

> **Decision gate:** confirm the skill is available, OR explicitly choose the manual path (§5),
> before going further. Don't start the spend without deciding which path.

---

## 2. Authenticate (you, once)

1. In the session, run `/design-login` (or the first `DesignSync` read call will prompt to add
   design-system access to your claude.ai login).
2. Approve the design-system scope when prompted.
3. Sanity check — list writable design-system projects:
   - skill path: `/design-sync` handles this.
   - manual: `DesignSync { method: "list_projects" }` → should return without an auth error.

If `list_projects` returns an auth error, the login didn't take — redo step 1.

---

## 3. Pick or create the target project

- **First time → create one.** Name it for the app, e.g. `agentsframework-ui` (or
  `native-wrap-redesign`). The project **type is immutable at creation** — it MUST be created as a
  design-system project; you cannot convert a regular project later.
  - skill: it offers create-vs-pick; choose **create new**.
  - manual: `DesignSync { method: "create_project", name: "agentsframework-ui" }` → capture the
    returned `projectId`.
- **Re-run later → pick the existing one** from `list_projects` (don't create duplicates).

Record the `projectId` — every subsequent call needs it, and it gets written into
`.design-sync/config.json`.

---

## 4. Detect the source "shape" (Storybook vs package)

`/design-sync` auto-detects how to build previews:

- **Storybook shape (preferred, what we have):** previews are rendered from real stories and
  verified against the Storybook render. We have `.storybook/` + 25 stories → this path. Highest
  fidelity.
- **Package shape (fallback):** previews authored from usage examples, graded on an absolute rubric.
  Only relevant if Storybook weren't present.

No action needed beyond confirming the skill reports **Storybook shape**. If it reports package
shape, something's wrong with the Storybook build — re-run §0's `build-storybook` and check.

---

## 5. Build the bundle + push (the long part)

This is where the hours go. With the **skill**, it's one orchestrated flow; the underlying tool
ordering is always **list/read → finalize_plan → write/delete**.

**5a. Build the deterministic bundle.** The skill compiles, from `dist/` + stories, a per-component
set: `_ds_bundle.js`, `styles.css` (our tokens ride along here — this is why the synced look matches
production), and for each component an `.html` preview + `.jsx` + `.d.ts` + `.prompt.md`. Each
preview's first line carries a `<!-- @dsCard group="…" -->` marker so the Design System pane indexes
it automatically.

**5b. Render-check loop (the expensive verification).** Each component preview is rendered and
visually verified; thin/blank/identical-variant previews are regenerated until they pass. This is
the per-component pass that takes time and tokens. Suggested grouping for our 14 primitives:

- **Actions:** Button, Badge
- **Forms:** Input, Textarea
- **Surfaces:** Card, Separator, Skeleton, ScrollArea
- **Navigation:** Tabs
- **Overlays:** Dialog, Sheet, DropdownMenu, Tooltip
- **Feedback:** Toast

**5c. Finalize the plan, then write.** The skill calls `finalize_plan` with the exact write paths
(e.g. `ui_kits/agentsframework/**`) and `localDir` = the bundle dir, then `write_files` (≤256 files
per call) under that `planId`. You will see the structured path list + source dir in the permission
prompt — **review it before approving**; nothing writes until you do.

> **Manual path (no skill):** I would do 5a–5c by hand via the `DesignSync` tool — build previews,
> self-verify, `finalize_plan`, `write_files`. Doable, but it's the work the skill exists to
> automate. Only take this path if §1's decision gate chose it.

---

## 6. Verify the sync landed

1. **In the tool:** `DesignSync { method: "list_files", projectId }` → confirms the uploaded paths.
2. **In the UI:** open the project at **claude.ai/design** → the Design System pane should show a
   card per primitive, grouped (Actions / Forms / Surfaces / …), each rendering in the
   §2.6 warm-neutral look (tokens came along via `styles.css`).
3. **Spot-check fidelity:** Button shows default/outline/ghost + sizes; Dialog/Sheet render their
   overlay; dark variants look right (our `[data-theme="dark"]` tokens).

If a card is blank or off-brand: the render-check didn't converge for that component — re-run the
sync for just that one (incremental) rather than the whole library.

---

## 7. Write the local sync state (so re-syncs are cheap)

The skill writes these into `frontend/.design-sync/` — commit them:

- **`config.json`** — the project pin (`projectId`) + detected shape (Storybook). This is what makes
  later runs target the same project automatically.
- **`conventions.md`** — the header the **design agent** reads: our wrapping/provider/token
  vocabulary **and the §2.6 Cursor warm-neutral aesthetic** (so every layout it composes stays
  on-brand — plan §2.5/§2.6).
- **`_ds_sync.json`** — the incremental anchor; later syncs diff against it and only re-push changed
  components (this is why re-syncs are cheap).

> **Author `conventions.md` deliberately.** State: token source is `design/tokens/*` → `@theme`;
> primitives live in `components/ui`; the look is **Cursor warm-neutral** (warm off-white canvas,
> one rationed accent, hairline borders, radius-lg soft chrome, recessed sidebar, pill composer);
> components are client-side React + Radix. The agent designs *toward* this.

---

## 8. Exit gate (PS2 done-when)

- [x] `/design-sync` (or manual path) completed without errors. *(manual path via mcp__claude_design__* tools, 2026-06-22)*
- [x] Every one of the 14 primitives is a verified card in the Claude Design project (grouped). *(15 files confirmed in project listing)*
- [ ] Cards render in the §2.6 warm-neutral look, light + dark. *(spot-check in UI — your step)*
- [x] `frontend/.design-sync/{config.json,conventions.md,_ds_sync.json}` exist and are committed.
- [x] `conventions.md` states the Cursor warm-neutral aesthetic as the design target.

When all checked → **PS3**: prompt the design agent in the project to compose the desktop three-pane
+ phone single-column/drawer/sheet + the §6 streaming states **from these synced components**, then
pull its output back as the P2 chat-surface implementation.

---

## Rollback / cost control

- **Stop anytime.** The render-check loop is resumable; a partial sync just means fewer cards. No
  destructive change to the local repo (the bundle is built into a temp/`dist`-adjacent dir).
- **Scope the spend.** Keep the synced surface to the 14 primitives (don't import the whole shadcn
  catalog — plan §3/§9). Fewer components = shorter first sync.
- **Re-sync, don't re-create.** After the first run, never `create_project` again — re-running
  `/design-sync` diffs via `_ds_sync.json` and only re-pushes what changed.

## Where I can / can't help

- **I can:** run the precheck (§0), build `dist/`/Storybook, drive the raw `DesignSync` tool calls
  (manual path §5), and author `conventions.md`.
- **I cannot:** perform `/design-login` (your claude.ai auth), or decide to spend the hours/tokens
  for you. Those are your gates — §1, §2, and the §5c approval.
