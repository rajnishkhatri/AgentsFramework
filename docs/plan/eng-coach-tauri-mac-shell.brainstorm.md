---
type: brainstorm
title: "Eng Coach Mac desktop via existing Tauri shell — SDD Stage-1 brainstorm"
description: Premise audit + candidate directions for "create a Tauri Mac desktop app for the GCP-deployed Eng Coach". Central finding — scaffolding Tauri is REFUTED: Tauri 2 already lives at frontend/src-tauri/ (ADR-0001, P5), loads the live Cloud Run BFF, and already owns WorkOS system-browser + agentsframework:// deep-link auth. The honest problem is product specialization (coach-first vs dual-product), post-auth landing, packaging/notarization, and sequencing behind the sibling usable-/learn GCP slice (D7 seed). Gate OPEN — human picks direction.
status: "Stage-1 OPEN — 2026-07-15"
authored: 2026-07-15
branch: feat/eng-coach-workos-learner-identity
---

# Brainstorm — Eng Coach Mac desktop (Tauri) wrapping GCP

**Stage 1 (SDD).** Problem as posed: *"eng coach is deployed on gcp. lets create tauri shell for creating mac desktop app."*

**Tree:** `feat/eng-coach-workos-learner-identity` (same plane as the sibling
[eng-coach-gcp-deploy](eng-coach-gcp-deploy.brainstorm.md) slice).

The request reads as a greenfield native-app stand-up. The premise audit below
finds the Tauri shell, Cloud Run target, and desktop auth path **already exist**.
Continuing on "scaffold Tauri" would rebuild machinery that shipped in P5
(2026-06). The real decision is *what product the shell opens*, *where auth
lands*, and *what packaging bar* we accept — sequenced against the usable
`/learn` substrate work already in flight.

Constitution backdrop: `frontend/AGENTS.md` (Frontend Ring + Cloud Run BFF) +
root `AGENTS.md` invariants. Native shell is nested under `frontend/` by
convention (ADR-0001) — not a new root package.

---

## Premise audit

Every load-bearing premise checked against the working tree before ideation
(read-only `explore` + direct source reads).

| # | Premise (as stated / implied) | Status | Evidence |
|---|---|---|---|
| P1 | We need to **create** a Tauri shell (greenfield scaffold) | **REFUTED** | Tauri 2 app already at [`frontend/src-tauri/`](../../frontend/src-tauri/) (`Cargo.toml`, `tauri.conf.json`, `src/lib.rs`, `src/auth.rs`). npm scripts `tauri` / `tauri:dev` / `tauri:build` in [`frontend/package.json`](../../frontend/package.json). ADR-0001 accepted Tauri 2 (macOS) + Capacitor 7 (iOS) over Electron. |
| P2 | Eng Coach is **deployed on GCP** as something the shell can wrap | **VERIFIED** (with caveats) | Coach is `(coach)/learn/*` inside the same Cloud Run service `agent-frontend` — not a separate service ([`infra/gcp/cloud-run-frontend.tf`](../../infra/gcp/cloud-run-frontend.tf); sibling brainstorm). Release shell `PROD_URL` = `https://agent-frontend-w65nrxwkiq-uc.a.run.app` ([`frontend/src-tauri/src/lib.rs:26`](../../frontend/src-tauri/src/lib.rs)). **Caveat:** "usable" coach on that revision is the sibling D7 seed slice — code may be on the branch while the **live image** may still be empty-substrate until redeploy (`needs-probe`). |
| P3 | Desktop auth / deep links must be invented for the shell | **REFUTED** | System-browser + PKCE + `agentsframework://auth/callback` already implemented: Rust intercept ([`lib.rs`](../../frontend/src-tauri/src/lib.rs) + `auth.rs`), BFF desktop sign-in / [`/api/auth/desktop-callback`](../../frontend/app/api/auth/desktop-callback/route.ts), helpers in [`desktop_auth_state.ts`](../../frontend/lib/adapters/auth/desktop_auth_state.ts). Design: `docs/plans/p5_step2_auth_deeplink.design.md`. |
| P4 | The Mac app should be a **coach product** (implied by "eng coach … desktop app") | **UNVERIFIED (product)** | Existing shell product name / window title is **AgentsFramework** ([`tauri.conf.json:3-17`](../../frontend/src-tauri/tauri.conf.json)); post-auth lands **`/`** (chat), not `/learn` ([`DESKTOP_POST_AUTH_PATH = "/"`](../../frontend/lib/adapters/auth/desktop_auth_state.ts:88)). Sibling GCP-deploy **explicitly left desktop `/` untouched** (FR-8). Whether the Mac app is coach-first vs dual-product is the open product question. |
| P5 | Static-export / offline Next bundle is a viable shell mode | **REFUTED** | `output: "standalone"` ([`next.config.ts`](../../frontend/next.config.ts)); WorkOS middleware + BFF API routes require a running Node origin. ADR-0001 + P5 plan: shell **must** load live HTTP (Cloud Run in release, localhost in debug). |

### Re-posed framing

The honest problem is **not** "scaffold Tauri for the first time." It is:

> **Specialize (or prove) the existing Tauri 2 macOS shell as a Mac client for
> the GCP-deployed Eng Coach** — deciding (a) coach-first vs dual-product
> front door, (b) desktop post-auth landing (`/` vs `/learn`), (c) packaging
> bar (unsigned local vs notarized DMG), and (d) sequencing against the
> sibling usable-`/learn` substrate (D7 seed + redeploy) so the shell does
> not wrap an empty product.

(a)/(b) are product; (c) is calendar/ops (Apple Developer); (d) is a
**sequenced dependency**, not parallel with "create shell."

---

## D0 — Blocking risks found during the audit

Present risks outrank every future capability.

### D0-a — Empty or unseeded prod `/learn` on the URL the shell points at

Sibling Stage-1/2 already named this **D0-b**: under production,
`composition_engine_browser` built an empty `InMemoryEngineDb` until the D7
`fresh`-pack path lands ([ADR-0033](../adr/0033-coach-prod-web-seed-fresh-mode.md);
[`engine_seed_plan.ts`](../../frontend/lib/engine_seed_plan.ts) on this branch).
The shell's release constant is the **live** Cloud Run URL
([`lib.rs:26`](../../frontend/src-tauri/src/lib.rs)). Wrapping that URL before
D7 is redeployed yields a Mac app with working auth and **zero coach content**.

**Status:** `needs-probe` — confirm the live revision digest includes D7 before
calling desktop "usable." Branch code ≠ live image.

### D0-b — Live Tauri deep-link auth smoke was deferred

Eng-coach WorkOS auth tasks marked live Tauri/iOS deep-link smoke as **tech
debt / DROP from DoD** (structural `/api/auth/*` check accepted instead) —
[`eng-coach-workos-auth.tasks.md`](eng-coach-workos-auth.tasks.md). Unit/BFF
paths exist; end-to-end from a bundled `.app` is still the P5 Step-4 gate
([`p5_tauri_macos_shell.plan.md`](../plans/p5_tauri_macos_shell.plan.md)).

A "ship coach desktop" claim without re-opening that smoke is a known gap.

### D0-c — `PROD_URL` / desktop-revision drift (historical)

RCA (`docs/plans/p5_desktop_auth_root_cause_analysis.md`) documented a failure
mode where the main Cloud Run URL lacked desktop-auth wiring and traffic had
to use a `desktop---` tagged revision. **Current** `lib.rs:26` points at the
main hash URL again; Capacitor uses yet another hostname form
([`capacitor.config.ts`](../../frontend/capacitor.config.ts)). Tag
`needs-probe`: verify desktop sign-in + cookie seal against the URL the release
shell actually loads.

### D0-d — Marker non-durability (accepted cost, not shell-specific)

ADR-0034: in-memory coach markers until threads BFF Cloud SQL bind. Shell
inherits the same flapping. Fails closed. Not a reason to block shell work;
name it as accepted UX cost.

---

## Candidate directions (~6)

Three high-probability (follow existing repo patterns) + three exploratory.
Plus an explicit **demand-side** option that makes native packaging *not happen*.

### D1 — Coach-first thin wrap (high-probability)

**Idea:** Keep one Tauri binary and one `PROD_URL`. Change launch navigation
(and optionally `DESKTOP_POST_AUTH_PATH`) so release opens `{origin}/learn`.

- **Follows:** `target_url()` / `shell_origin()` in [`lib.rs:76-101`](../../frontend/src-tauri/src/lib.rs); post-auth constant in [`desktop_auth_state.ts:88`](../../frontend/lib/adapters/auth/desktop_auth_state.ts); scheme already registered.
- **Tradeoffs:** Tiny code delta; makes the Mac app read as coach. Contradicts sibling FR-8 ("desktop `/` untouched") if post-auth flips — that was a *web-slice scope guard*, not a forever product law, but amending it needs an explicit decision + decisions.md/ADR note.
- **What breaks:** Dual-product users who use the Mac app for chat/eval lose the chat landing; WorkOS dashboard redirect URI / deep-link path unchanged (same scheme). Chat remains reachable via in-app nav only if we add a link the other way.
- **Invariants / Ask-first:** No new dep/service/node. Product flip of `DESKTOP_POST_AUTH_PATH` is a deliberate scope change vs eng-coach-gcp-deploy FR-8 → record in `decisions.md` (or ADR if we treat desktop coach as a new front door).
- **Gated on:** D0-a (seeded live `/learn`), D0-b/c (auth works against that URL).

### D2 — Dual-product status quo + prove the path (high-probability)

**Idea:** Do **not** change shell landing. Ship/prove: release shell → GCP `/` →
WorkOS desktop auth → ChatShell **"Open Coach"** → `/learn`.

- **Follows:** [`chat-shell.tsx` Open Coach CTA](../../frontend/app/chat-shell.tsx) (sibling D2); existing P5 shell; eng-coach-gcp-deploy FR-8 left alone.
- **Tradeoffs:** Zero (or near-zero) shell code; honest dual-product. Coach is one click after auth, not the front door. Matches "AgentsFramework" branding in `tauri.conf.json`.
- **What breaks:** User expectation of "Eng Coach desktop app" — the Dock icon still says AgentsFramework and opens chat first.
- **Invariants:** None stressed. Ask-first: none for code; product naming may still want a separate Dock label later (→ D4).
- **Demand-side adjacent:** minimizes native work; the expensive packaging (D3) becomes optional.

### D3 — Finish P5 packaging bar (unsigned → notarized DMG) (high-probability)

**Idea:** Treat "create Mac app" as **distribution**: Step 4–5 of
[`p5_tauri_macos_shell.plan.md`](../plans/p5_tauri_macos_shell.plan.md)
(codesign, notarize, DMG; Sparkle optional). Shell code stays as-is (or D1/D2).

- **Follows:** P5 plan Steps 4–5; ADR-0001 distribution posture.
- **Tradeoffs:** Real installable artifact. **Calendar cost** dominates: Apple Developer Program enrollment was required; plan recorded **0 signing identities** (2026-06). Engineering time ≠ wait time.
- **What breaks:** Nothing in the web stack. Without D0-a/b, you notarize an empty or auth-broken coach experience.
- **Ask-first:** CI secrets for notarization; possibly Sparkle feed hosting — ops, not trust-kernel.

### D4 — Coach-branded second Tauri product (exploratory)

**Idea:** Second app id (`com.agentsframework.coach` / productName "Eng Coach"),
optional second scheme, same Rust auth pattern, launch URL forced to `/learn`.

- **Tradeoffs:** Clear Dock branding; doubles packaging, WorkOS redirect entries, scheme registration, update feeds. Violates "simplest thing" unless product split is the goal.
- **What breaks:** Two binaries to ship against one BFF; deep-link collision risk if schemes diverge carelessly.
- **Ask-first:** New packaging surface / product abstraction → **G1 + ADR** at spec time (amend or sibling to ADR-0001).
- **Class over instance:** Prefer D1 branding tweaks (name/icon only) before a second binary.

### D5 — On-device SQLite coach substrate inside Tauri (exploratory)

**Idea:** Build the ADR-0005/0010 on-device engine DB path for **Tauri** (today
called out as Capacitor-oriented / unbuilt), so the Mac app is not purely a
thin client of Cloud Run's in-memory bag.

- **Tradeoffs:** Real offline/local progress story; large vertical slice (Rust FS + JS bridge + engine ports). Does **not** remove need for BFF auth/SSE.
- **What breaks:** Dual-write / sync story vs web Cloud Run learners; identity (`learnerId`) must stay WorkOS-aligned.
- **Ask-first:** New native data plane + likely ADR amendment to 0005/0010/0033 (web vs native split). High invariant surface on Frontend Ring adapters.
- **Gated on:** D0-a web seed may still be required for content packs unless packs ship in-app.

### D6 — Bundle a local Next BFF inside the `.app` (exploratory — reject-leaning)

**Idea:** Ship Node + standalone Next inside the Mac app instead of loading
Cloud Run.

- **Tradeoffs:** Offline-ish; huge binary; secret/env handling on device; contradicts ADR-0001's decisive "thin webview → live origin" insight.
- **What breaks:** Update story (every web change = app reship); WorkOS redirect URIs; FE-AP-18 credential posture on a user machine.
- **Ask-first:** Re-opens ADR-0001. Treat as **rejected unless** a hard offline requirement appears.

### D7 — Demand-side: no Mac packaging yet (high-value lens)

**Idea:** Make the expensive operation (native packaging + notarization) *not
happen*. Use browser → GCP `/learn` until sibling eng-coach-gcp-deploy converges
and live desktop auth is re-proven (D0-a/b/c). Optionally keep `pnpm tauri:dev`
as a local spike only.

- **Follows:** Sibling slice already chose web-only post-auth; P5 live smoke deferred; repo anti-slop "stop before expanding scope."
- **Tradeoffs:** Fastest path to a usable coach; no Dock app. Fails the literal "Mac desktop app" ask until a later phase.
- **What breaks:** Only the expectation that "create Tauri" was greenfield work — it wasn't.

---

## Under-used signal

The highest-quality under-used signal already in-repo is the **deferred live
Tauri/iOS deep-link smoke** (structural DoD substituted). Any direction that
claims "Mac app works" should **re-consume that signal** as DoD — not add a
third parallel auth design. Pair with Cloud Logging / WorkOS dashboard checks
already used in the desktop-auth RCA.

---

## Hypotheses for the leading direction

Leading candidate if the human wants a **coach Mac app soon without a second
product:** **D1 (coach-first thin wrap) sequenced after D0-a**, with **D2 as
the interim prove path**, and **D3 as a separate packaging track**.

| ID | Hypothesis | Validation |
|---|---|---|
| H1 | Works *because* the release shell already loads the live Cloud Run origin and coach routes are same-origin `/learn/*`. | **SUPPORTED** — [`lib.rs:3-11,26`](../../frontend/src-tauri/src/lib.rs); [`COACH_BASE = "/learn"`](../../frontend/components/shell/nav_model.ts). |
| H2 | Safe *because* desktop auth already seals the same `wos-session` cookie the `(coach)` layout's `withAuth` expects. | **SUPPORTED in code** — desktop-callback `saveSession` + `(coach)/layout` guard. **Live E2E** still D0-b deferred → tag `needs-probe` before ship. |
| H3 | Changing only launch URL to `/learn` is "trivial / zero product risk." | **REJECTED as stated** — post-auth still lands `/` unless `DESKTOP_POST_AUTH_PATH` changes; sibling FR-8 explicitly preserved desktop `/`. Launch-only change leaves a bounce: auth → `/` → user must navigate. |
| H4 | D1 and eng-coach-gcp-deploy are independent-parallel. | **REJECTED** — sequenced: shell usability **depends on** D7-seeded live revision (D0-a). Packaging (D3) is independent of seed code but not of "usable demo." |
| H5 | Scaffolding a new `src-tauri` tree is required. | **REJECTED** — P1 refuted. |

---

## Dependency map (before naming a lead)

```
do-regardless (hygiene)
  ├─ D0-c probe: desktop auth against current PROD_URL
  ├─ D0-a probe: live /learn seeded (sibling D7 redeploy)
  └─ Keep ADR-0001 thin-client model (reject D6 unless offline req)

pick-the-priority (orthogonal axes — answer separately)
  ├─ Product front door: coach-first (D1) vs dual-product (D2) vs branded split (D4)
  ├─ Desktop post-auth: keep "/" (FR-8) vs flip to "/learn" (amend FR-8)
  └─ Packaging bar: prove unsigned local (dev) vs notarized DMG (D3)

deferred-behind
  ├─ D5 (on-device SQLite) behind a real offline/local-progress requirement
  └─ D3 Sparkle behind notarization + Apple enrollment

demand-side
  └─ D7: no packaging until probes green
```

**Capability vs operational:** "coach opens in a Mac window" is capability (D1/D2);
"notarized DMG in Downloads" is operational (D3). Conflating them is the usual
schedule blow-up — Apple enrollment is calendar time.

---

## Human gate (direction-level only)

Stage-1 is **OPEN**. Pick with explicit ids (a bare "yes" is not consent).

### Q1 — Product front door for the Mac app

| Id | Option |
|---|---|
| **Q1-A** | **D1 coach-first** — release shell opens `/learn` (thin wrap). |
| **Q1-B** | **D2 dual-product** — keep `/` landing; coach via Open Coach CTA; prove path. |
| **Q1-C** | **D4 second branded app** — Eng Coach binary (ADR at spec). |
| **Q1-D** | **D7 defer native** — browser-only until GCP usable-`/learn` + auth probes green. |

### Q2 — Desktop post-auth landing (only if Q1-A or Q1-C)

| Id | Option |
|---|---|
| **Q2-A** | Keep `DESKTOP_POST_AUTH_PATH="/"` (honor eng-coach-gcp-deploy FR-8); coach-first = launch URL only / in-app redirect after cookie seal. |
| **Q2-B** | Flip `DESKTOP_POST_AUTH_PATH="/learn"` (amend FR-8; record in decisions.md). |

### Q3 — Packaging bar for this slice

| Id | Option |
|---|---|
| **Q3-A** | Unsigned local / `tauri:dev` + release build pointed at GCP — prove coach path; notarization later. |
| **Q3-B** | Include **D3** notarized DMG in this slice (gated on Apple Developer enrollment — calendar). |

### Q4 — Sequencing vs sibling GCP deploy

| Id | Option |
|---|---|
| **Q4-A** | **Hard sequence:** finish eng-coach-gcp-deploy D7+redeploy (+ probes) before any desktop product flip. |
| **Q4-B** | Spec desktop in parallel; DoD blocked on live probes (risk: spec drift). |

### Suggested default (not consent)

If the goal is "Eng Coach on my Mac against GCP" with least invention:
**Q1-A + Q2-B + Q3-A + Q4-A** — coach-first thin wrap, post-auth `/learn`,
unsigned prove-first, after seeded live `/learn`. Reject D4/D5/D6 for this
slice.

---

## Advance rule

On gate close → **sdd-spec** with chosen Q-answers + validated hypotheses
(H1/H2; H3/H4/H5 rejected). Spec must name live prod surface
`agent-frontend` / current `PROD_URL`, not a new Cloud Run service, and must
list Ask-first items (FR-8 amendment and/or second-app ADR) up front.
