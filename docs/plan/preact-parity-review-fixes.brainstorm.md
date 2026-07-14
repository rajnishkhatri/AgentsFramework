# SDD Stage 1 — Brainstorm: addressing the Epic A–F parity-review findings

**Status:** Stage 1 (brainstorm). Direction-level acceptance only — no spec yet.
**Runbook:** `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` §3.
**Input problem:** close the 8 findings from the A–F parity review (P-4, D-8, SD-6,
S-2b, C-3, SD-1/3/5, markSubmitted 500, coach-back resume).

---

## 1. Premise audit (findings re-verified against the live tree)

The review findings are themselves hypotheses. Each was re-checked against the
current working tree (branch `feat/preact-parity-epic-F`) by direct file read +
a parallel `explore` sweep. Two premises changed materially.

| # | Finding (as posed) | Status | Evidence (verified `file:line`) |
|---|---|---|---|
| P-4 | Progress renders a fabricated **0%** mastery bar; violates Epic F FR-4 | **verified** | `bucket_card_vm.ts:34,42` (`?? 0` → `masteryPct:0`); `progress_screen_vm.ts:68` passes buckets through; `ProgressView.tsx:47-67` renders `role="progressbar" aria-valuenow={0}` + filled bar **with no no-data branch**. Guard test `bucket_missing_mastery_is_honest_not_zero` promised at spec `:206` **does not exist**; `bucket_card_vm.test.ts:49,67` instead *assert* `toBe(0)` and call it a "placeholder path". FR-4 (`spec:77-78`) is **self-contradictory**: "never a fabricated 0%" *and* "per `bucket_card_vm` today". |
| D-8 | iPhone nav drops Coach / adds Skill on a fabricated **§8.1** citation | **verified + refined** | `nav_model.ts:106` `iphone:["dashboard","quiz","skill","progress"]` (4 tabs, Coach dropped). §8.1 citation (`nav_model.ts:19,100`; `AppNav.tsx:7`) is **fabricated** — the only real §8.1 in-repo is `research/eng_coach_v2_pedagogy_spec.md:359` (LLM-vs-deterministic split, unrelated). **Refinement:** `AppNav.tsx:6-7` comment says a **3-tab** "Home/Practice/Progress" bar while the array ships **4** tabs incl Skill — the *comment* is stale, not just the citation. `nav_model.test.ts:143-144` asserts `not.toContain("Coach")` — the test **codifies** the divergence. |
| SD-6 | Bucket card still drills instead of opening the now-live `/learn/skill` | **verified** | `BucketCard.tsx:26` `focusHref = ${screen("quiz").route}?focus=${vm.skillId}` (a drill). Header `:7-11` still calls `/learn/skill` "the dead route… Re-points when S9 lands" — **stale**: `nav_model.ts:75` has skill `comingSoon:false` (live since E1a/ADR-0028) and `SkillDetailView.tsx` is fully built. `e2e/learn/skill-detail.spec.ts` **does not exist**. |
| S-2b | "0 min" for sub-30s sessions | **verified** | `session_summary_vm.ts:60-65`: `Math.round(ms/60000)` → `0` for <30s; only `ended_at==null`/negative falls back to `"—"`. No `<1 min` branch. |
| C-3 | Raw `s-gram` id can show in coach history instead of a friendly name | **verified** | `coach/page.tsx:75` hardcodes `skillLabel: null` into `toCoachSurfaceVM`; `pin.skillId` is available (used `:57-60`) but never name-resolved. |
| SD-1/3/5 | Skill-detail thinner than design | **verified, SD-5 softened** | SD-1: `SkillDetailView.tsx` renders **no** share-of-test-% header / bucket dot (only `accentVar` tint). SD-3: `skill_detail_vm.ts:157` a **single** `misconceptionCallout`, not a cluster. **SD-5 softer than posed:** `dueChecklist` (`skill_detail_vm.ts:174`, `SkillDetailView.tsx:345-371`) **does** render a cross-skill "also due" list with drill links — closer to design than "just a count". |
| mark-500 | `markSubmitted` DB outage → 500 (not graceful) | **verified — subagent's "FIXED" overturned** | `marker_repo.ts:84-89` `markSubmitted` is a bare `await` (no try/catch); sibling `isSubmitted:91-106` **has** one. Repo docstring `:20-25` claims "fire-and-forget — the caller logs and continues". **But the caller does not:** `app/api/coach/session-marker/route.ts:59` is a bare `await …markSubmitted(...)` with no catch → an outage throw becomes an **unhandled 500**. The documented contract is **not implemented**. |
| coach-back | coach-back resume inconsistent by entry path | **verified — it's a design choice, not a plain bug** | `coach/page.tsx:93-100` `onBack`: `window.history.length>1 ? router.back() : push(quiz)`. `router.back()` returns to the *previous history entry* (Feedback, if you came from Feedback), so "resume the pinned quiz item" is **not** encoded — the heuristic is intentional but doesn't honor the resume intent from the Feedback origin. |

**Net:** all 8 stand as real gaps. Two corrections vs the original review:
(a) **markSubmitted 500 is real** and lives in the *route*, not the repo — the fix
target moves; (b) **SD-5 is largely already built** — drop it from the thin-skill
work, leaving SD-1 (share header/dot) + SD-3 (misconception cluster) as the only
skill-detail thinness worth speccing.

### Cross-cutting observations the audit surfaced (not in the original 8)

- **A recurring class, not 8 instances:** P-4, S-2b, C-3, and the D-8/SD-6 stale
  comments are all the **same defect class** — *a VM/translator emits a value that
  reads as real data when the underlying datum is absent or unresolved*, and a
  **stale comment or a test that asserts the wrong thing** locks it in. This is the
  "honesty of surfaces" rule failing at the translator seam. The class-over-instance
  lens (below, D-B) matters here.
- **Tests encode the bug, twice:** `bucket_card_vm.test.ts:49,67` and
  `nav_model.test.ts:143` both *assert the forbidden behavior*. Any fix must **flip
  the test** (G8 test-weakening gate applies in reverse — we're *strengthening*).
- **FR-4 is self-refuting** — closing P-4 requires **editing the spec**, not just
  the code, or the spec ratifies the bug. That's an ADR-adjacent doc change.

---

## 2. What each fix costs, structurally (feasibility, de-adjectived)

Before generating directions: none of these is "trivial". The honest costs:

- **P-4** is *not* a one-line view tweak. `BucketCardVM` carries **no** `masteryKnown`
  signal, so the view has nothing to branch on. The fix is a **wire/VM shape change**
  (`bucket_card_vm.ts` adds a field) + **two** consumers (`BucketCard.tsx`,
  `ProgressView.tsx`) + **flip two tests** + **write the missing guard test** +
  **edit FR-4**. Touches a shared kernel-adjacent translator → the change ripples.
- **D-8** is a **decision**, not code: restore Coach on iPhone (revert to prototype)
  **or** ratify Skill-on-iPhone. Either way delete the phantom §8.1 and fix the
  `AppNav.tsx:7` comment. Ratifying needs a **real ADR** (nav divergence from the
  prototype is exactly an ADR trigger). ~10 lines of code; the cost is the decision +
  ADR, and flipping `nav_model.test.ts` if we restore Coach.
- **SD-6** is genuinely small: repoint `BucketCard.tsx:26` to
  `${screen("skill").route}?skillId=${vm.skillId}`, delete the stale header, add the
  missing `skill-detail.spec.ts`. **But** it interacts with D-8 (if iPhone keeps
  Skill, the bucket→skill path is the *only* skill entry on phone — raising its
  priority) and with the drill-vs-teach product question (is the dashboard bucket
  meant to drill or teach? the prototype says teach).
- **S-2b / C-3** are the cheapest: S-2b adds a `<1 min` branch in one VM +
  test rows; C-3 resolves `skillId → name` (the skill catalog is already imported
  on the page) and passes it instead of `null`, + a test.
- **SD-1/SD-3** is real design build (new VM fields: `shareOfTestPct` already exists
  on the bucket, misconception-*cluster* needs an aggregation the current single-miss
  read doesn't do — this is **E-class**, gated on whether the miss corpus supports a
  cluster). SD-5 drops out (already built).
- **markSubmitted 500** is a **one-line route fix** (wrap `:59` in try/catch + log)
  — the repo already documents the intended posture; the route just never honored it.
- **coach-back** is a **design choice to revisit**, not a bug to patch: to honor
  "resume the pinned item" from the Feedback origin, `onBack` must route to the
  pinned quiz item explicitly rather than `router.back()`. That changes intended
  behavior → needs a product call (is back = "previous screen" or "resume practice"?).

---

## 3. Directions (~6)

Findings split on two axes the human should keep separate:
**(i) present-risk hygiene vs future capability**, and **(ii) instance-patch vs
class-fix**. I pose them as independent tracks, not a single ranked list.

### D0 (blocking, present risk) — **markSubmitted route resilience**
*A live 500 outranks every cosmetic/honesty gap.* One-line fix at
`session-marker/route.ts:59`: wrap the `markSubmitted` await in try/catch, log, and
still return 204 (honor the fire-and-forget contract the repo docstring already
declares). Follows the exact pattern `isSubmitted` already uses (`marker_repo.ts:101`).
- **Pattern followed:** the fail-closed try/catch in `marker_repo.ts:92-106`.
- **Tradeoff:** none material — it *implements* the documented contract.
- **What breaks if chosen:** nothing; strictly more resilient. Needs one integration
  test (outage → 204, marker absent) — a **failure-path-first** test (§20 rule).
- **Invariant stressed:** F-R4 (route stays thin — try/catch is not "business logic").
- **Dependency:** independent. **Do first, do regardless.**

### D-A (high-prob, honesty) — **P-4 honest-absent mastery, done as the class fix**
Add `masteryKnown: boolean` (or `masteryPct: number | null`) to `BucketCardVM`;
`ProgressView`/`BucketCard` branch to a "—/no data yet" form when unknown; **flip**
`bucket_card_vm.test.ts:49,67`; **write** the promised guard test; **edit FR-4** to
drop the self-contradiction.
- **Pattern followed:** the honest-null discipline already in `session_summary_vm.ts`
  (`"—"` on null `ended_at`) and `progress_screen_vm.ts` (empty-trend state). This is
  the *same* pattern applied to a place that missed it.
- **Tradeoff:** a nullable VM field ripples to every `BucketCardVM` consumer (grep
  first — dashboard grid + progress). `exactOptionalPropertyTypes` is on, so the
  shape change is compiler-checked.
- **What breaks if chosen:** the two tests that assert `toBe(0)` (intended — G8 in
  reverse: we justify strengthening). Demo seed populates all 6 buckets, so no visible
  demo change — the fix is latent-correctness, which is exactly why it slipped.
- **Invariant stressed:** W-family (wire/VM shape) + T4 (table tests). ADR-adjacent:
  editing FR-4 is a spec change (record in `decisions.md`, not a full ADR).
- **Dependency:** independent of D0/D-8; **is** the anchor of the class-fix (D-B).

### D-B (exploratory, class-over-instance) — **an "honest-null at the translator seam" sweep + a guard test**
Rather than patch P-4/S-2b/C-3 one at a time, treat them as one class: *a translator
that substitutes a plausible value for an absent datum*. Deliverable = (1) fix all
three, (2) a small shared convention (a documented "absent → `null`/`"—"`, never a
zero/placeholder" rule for `lib/translators/`), and (3) **one architecture-ish test**
that scans the VMs for the smell (or, more cheaply, a checklist entry + the per-VM
guard tests). This is the "shared seam + a test that fails the next occurrence" move.
- **Pattern followed:** the guardrail cascade's `decision_stage` audit-field idea —
  make the honest-null path *observable/testable*, not just present.
- **Tradeoff:** a repo-wide "smell scanner" for VMs is likely over-engineering (there
  are ~8 VMs — a checklist + per-VM tests may beat a bespoke arch test). The honest
  scope is: fix 3 + document the rule + 3 guard tests; the arch-test is optional.
- **What breaks if chosen:** more surface than the human may want *now* — but it stops
  the 4th instance. **G1 new-abstraction gate applies** to the "convention": state
  what it buys before adding it.
- **Invariant stressed:** none hard; it's a discipline, not a layer change.
- **Dependency:** supersets D-A + S-2b + C-3. Pick D-B **instead of** patching them
  singly, or pick the singles if the human wants minimal blast radius.

### D-C (high-prob, decision-gated) — **D-8 nav: decide, then de-fabricate**
This is a **product decision** wearing a code finding. Two sub-options:
- **D-C1 (parity-restoring):** iPhone bottom bar = Home/Practice/**Coach**/Progress
  per the prototype; drop Skill from the phone tab bar (reachable via bucket→skill
  once SD-6 lands). Revert `nav_model.ts:106`, flip `nav_model.test.ts:143`, fix the
  `AppNav.tsx:7` comment, delete §8.1.
- **D-C2 (ratifying):** keep Skill on iPhone; write a **real ADR** for the divergence
  ("phone favors the teach-plane over contextual Coach"), replace every §8.1 citation
  with the ADR id, fix the AppNav comment to say 4 tabs.
- **Tradeoff:** D-C1 is "match the spec"; D-C2 is "the divergence was intentional and
  we own it". **The human must pick** — automation can't judge which the product wants.
- **What breaks:** whichever tab set changes, its `nav_model.test.ts` row flips.
- **Invariant stressed:** ADR ratchet (D-C2 **requires** an ADR; D-C1 does not).
- **Dependency:** interacts with SD-6 (D-D) — if D-C1 drops Skill from the phone bar,
  the bucket→skill link becomes the *only* phone skill entry, raising SD-6's priority.

### D-D (high-prob) — **SD-6 bucket card → skill detail (+ the missing e2e)**
Repoint `BucketCard.tsx:26` to the live skill route, delete the stale "dead route"
header, add `e2e/learn/skill-detail.spec.ts` (the spec the finding says is owed).
- **Pattern followed:** the 2/3 SD-6 entry points E already wired (SummaryView "See
  full lesson" → `/learn/skill`); this finishes the 3rd.
- **Tradeoff:** raises the drill-vs-teach product question — does the dashboard bucket
  *teach* (open skill detail) or *drill* (quiz)? Prototype = teach. If the answer is
  "both", that's a bigger surface (a split control), not a repoint. **Confirm intent.**
- **What breaks:** any test asserting the bucket routes to `?focus=` drill.
- **Invariant stressed:** none; it's a wiring + test add.
- **Dependency:** coupled to D-C (see above). Otherwise independent.

### D-E (exploratory, capability, gated-on-data) — **SD-1/SD-3 skill-detail depth**
Add the share-of-test-% header + bucket dot (SD-1 — data already on the bucket) and a
misconception **cluster** (SD-3 — needs an aggregation over the miss corpus the
current single-newest-miss read doesn't do). SD-5 **drops** (already built).
- **Pattern followed:** SD-1 mirrors `bucket_card_vm`'s `shareOfTestPct` (already
  computed — just unrendered on skill detail). SD-3's cluster is **E-class**: a new
  aggregation like the accuracy read.
- **`gated-on-data`:** SD-3's cluster is only meaningful if a learner accrues *multiple
  distinct* misses per skill — **needs-probe** on the miss corpus density (the same
  "corpus density, not code" caution as the tier-1 taxonomy brainstorm). SD-1 is not
  gated (static data).
- **Tradeoff:** SD-1 is cheap and honest; SD-3 risks manufacturing a "cluster" from
  one miss (a fabrication of a different kind). Split them.
- **Invariant stressed:** a new read/aggregation for SD-3 → an ⚠️ Ask-first service
  seam → ADR at spec time.
- **Dependency:** independent; lowest present value (thin-but-honest today).

### D-F (design decision) — **coach-back resume semantics**
Decide what "Back" means from the coach screen: **(a)** previous screen
(`router.back()` — today's behavior, lands on Feedback from that origin), or **(b)**
resume the pinned practice item (route explicitly to the pinned quiz question). Then
encode the chosen semantics.
- **Tradeoff:** (b) honors the "resume where you left" intent the review flagged but
  overrides browser-history expectation; (a) is predictable but doesn't resume. This
  is genuinely a **product call**, not a bug.
- **What breaks:** the two e2e specs (`validate_epic_ab.spec.ts:383,458`) that assert
  quiz-context visibility after coach-back — they encode expectation (b) but the code
  does (a); that mismatch **is** the 2 e2e failures. So D-F **also closes the 2 red
  e2e tests** — pairing it with D0 clears the live-red signal entirely.
- **Invariant stressed:** none; behavior choice.
- **Dependency:** independent, but **note:** D0 + D-F together are what turn the e2e
  suite green (25/27 → 27/27).

---

## 4. Dependency structure & the real decision

```
DO-REGARDLESS (present risk, no ADR, no product call):
  D0  markSubmitted 500 → try/catch route fix        [1 line + 1 test]
  S-2b  "<1 min" branch                               [cheapest honesty]
  C-3  resolve skillId→name                           [cheapest honesty]

PICK-THE-PRIORITY (independent, each self-contained):
  D-A  P-4 honest-absent mastery (+ flip tests, +guard test, +edit FR-4)   [honesty, spec edit]
  D-D  SD-6 bucket→skill (+ e2e)                                           [wiring]  ── couples to ──┐
                                                                                                     │
DECISION-GATED (human must choose before spec):                                                     │
  D-C  D-8 nav: D-C1 restore Coach (no ADR)  |  D-C2 ratify Skill (ADR)    ───────────────────────┘
  D-F  coach-back: (a) back  |  (b) resume    [also closes the 2 red e2e]

CLASS-FIX ALTERNATIVE (supersedes D-A + S-2b + C-3 if chosen):
  D-B  honest-null translator sweep + convention + guard tests            [G1 gate on the "convention"]

DEFERRED-BEHIND-DATA (lowest present value):
  D-E  SD-1 (cheap, do) + SD-3 (needs-probe: miss-corpus density) ; SD-5 DROPPED
```

**The three real decisions for the human (not "which bug first"):**

1. **Instance vs class** — patch P-4/S-2b/C-3 individually (D-A + singles), or do the
   honest-null **class fix** (D-B) with a shared convention? (G1 applies to D-B.)
2. **D-8 nav** — **restore Coach** on iPhone (D-C1, matches prototype, no ADR) or
   **ratify Skill** (D-C2, needs a real ADR)? This gates SD-6's priority.
3. **coach-back** — is Back "**previous screen**" (a) or "**resume practice**" (b)?
   The answer decides whether the 2 red e2e tests get fixed or **rewritten**.

**Zero-risk, start-now regardless of all three:** D0, S-2b, C-3. **SD-5 is done** —
remove it from scope. **SD-3 is `needs-probe`** — don't spec a misconception cluster
until the miss-corpus density is measured (else it fabricates a cluster from one miss —
a new honesty violation to replace the one we're closing).

**Recommended lead if you want one pick:** **D0 + D-F together** — they clear the only
*live-red* signal (the 500 and the 2 failing e2e), are the highest-severity present
risks, and D-F forces the one product decision (back-semantics) that's blocking the
e2e from going green. Everything else is honest-but-latent and can follow.

---

## 5. Human gate — DECISIONS LOCKED (2026-07-13)

The three gating decisions are made:

1. **Instance vs class → CLASS-FIX (D-B).** Fix P-4 + S-2b + C-3 under one
   "honest-null at the translator seam" convention for `lib/translators/`, with
   per-VM guard tests that fail the next occurrence. *(G1 new-abstraction gate
   applies to the convention — spec must state what it buys.)*
2. **D-8 nav → RESTORE COACH (D-C1).** iPhone bottom bar =
   Home / Practice / **Coach** / Progress per the prototype; **drop Skill** from the
   phone tab bar (Skill reachable via the bucket→skill link once SD-6 lands). Revert
   `nav_model.ts:106`, flip `nav_model.test.ts:143-144`, fix the stale
   `AppNav.tsx:6-7` comment, **delete every fabricated §8.1 citation**
   (`nav_model.ts:19,100`; `AppNav.tsx:7`). **No ADR** (matches the prototype).
3. **coach-back → RESUME PRACTICE (D-F b).** `onBack` routes explicitly to the
   pinned quiz item, not `router.back()`. This turns the 2 red e2e tests
   (`validate_epic_ab.spec.ts:383,458`) green (they already assert quiz-context
   after coach-back).

**Do-regardless (confirmed in scope):** D0 (markSubmitted route try/catch),
plus S-2b + C-3 (now folded into the D-B class-fix). **SD-6 (D-D)** in scope and its
priority is **raised** — under D-C1, once Skill leaves the phone tab bar, the
bucket→skill link is a primary phone entry to skill detail.
**SD-5 → DROPPED** (already built). **SD-3 → PARKED `needs-probe`** (miss-corpus
density); **SD-1** may proceed (static data) but is lowest present value.

### Selected scope → sdd-implement

| Track | What ships | ADR? | Tests |
|---|---|---|---|
| **D0** | try/catch at `session-marker/route.ts:59`; return 204 on outage | no | outage→204, marker absent (failure-first) |
| **D-B** | honest-null convention + P-4 (`masteryKnown`/nullable + view no-data branch) + S-2b (`<1 min`) + C-3 (`skillId→name`) | decisions.md (FR-4 edit) | flip `bucket_card_vm.test.ts:49,67`; **write** `bucket_missing_mastery_is_honest_not_zero`; S-2b + C-3 guard rows |
| **D-C1** | iPhone nav restore Coach / drop Skill; delete §8.1; fix AppNav comment | no | flip `nav_model.test.ts:143-144` (restore Coach, drop Skill) |
| **D-D** | `BucketCard.tsx:26` → skill route; delete stale header; add e2e | no | new `e2e/learn/skill-detail.spec.ts` |
| **D-F b** | `coach/page.tsx:93-100` `onBack` → pinned quiz item | no | the 2 existing red e2e go green |

**Deferred (not this pass):** SD-5 (done), SD-3 (`needs-probe`), SD-1 (optional).
FR-4's self-contradiction is edited as part of D-B (drop "per `bucket_card_vm` today").

**Next stage:** `sdd-implement` on the five tracks above (D0, D-B, D-C1, D-D, D-F b).
Sequencing note: D-C1 and D-D interact (both touch the phone→skill path) — implement
D-C1's nav change and D-D's bucket link in the same change so the phone skill-entry
story is coherent at every commit (FR-B5 no-dead-control discipline).
