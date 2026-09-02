# Risk Assessment & Risk-Storm — Exam module (official-rules durable test suite)

> Stage 5 of the arch-* sweep · **review mode** · first assessment (all markers 🆕)
> Input diagram: [logical-components.md](../../components/exam-module-official-rules/logical-components.md)
> Criteria = the 6 driving characteristics ([worksheet](../../worksheets/exam-module-official-rules/characteristics-worksheet.md)).
> Contexts: **CX1** live timed-run · **CX2** persistence seam · **CX3** analytics/review · **CX4** form registry · **CX5** exam⟂practice boundary.
> **Honesty on method:** three blind lenses (Operations, Security/Data-integrity, Implementation/Evolvability) were **same-model coverage lenses, not independent voters** — convergence signals salience, not statistical confidence. Scores are `impact(1–3) × likelihood(1–3)`; bands **1–2 low · 3–4 med · 6–9 high**. Merges use the **median**; the human arbitrates.

## Consensus register (ranked; merged from 29 raw → 16)

| ID | Context | Criterion | Lenses | Merged I×L | Band | Risk (merged) |
|---|---|---|---|---|---|---|
| **R1** | CX5 | Modularity/Isolation | SEC-4, IMPL-3 | 3×3=**9** | 🔴 high | **FR-26 isolation guard is UNBUILT and the existing layering test doesn't reach `components/`** — an exam↔quiz/scheduler/`skill_state` edge (or a `skill_state` write from exam code) can merge silently; the module's entire raison d'être is unenforced. |
| **R2** | CX1 | Recoverability | OPS-3, OPS-7, IMPL-10 | 3×3=**9** | 🔴 high | **Un-flushed buffer loss.** The write buffer is in-memory with no stated persist/retry path; a mobile tab-kill / bfcache eviction / crash in the debounce window silently loses the last answers on a *scored* exam. FR-5's "not saved" is honest but reactive. |
| **R3** | CX1/CX4 | Confidentiality | SEC-1 *(single-lens)* | 3×3=**9** | 🔴 high | **Client-side answer-key exposure on a timed surface.** Phase-1 reuses the Test-01 slice and (like today's Test Mode, ADR-0013) may grade client-side with the key in the bundle → the "official-rules" exam and *all* its analytics are trivially cheatable. **The durable, scored, analysed exam plausibly trips ADR-0013's own "stake" tripwire** that says flip keys server-side. |
| **R4** | CX2 | Confidentiality/Isolation | SEC-2, SEC-5, IMPL-1, IMPL-9 | 3×2=**6** | 🔴 high | **Dispatcher learner-scoping (4-lens convergence).** Positional `LEARNER_ARG` (learnerId must stay arg 0); completeness not proven to be enforced (a method with no entry → dispatcher default: does it deny or trust-client?); every one of the 9 methods must JOIN `learner_id=claim`. Any one slip = cross-learner read/write. |
| **R5** | CX1/CX2 | Durability/Correctness | OPS-1, OPS-2, OPS-9 | 3×2=**6** | 🔴 high | **`begin` sync point.** (a) Cloud Run scale-to-zero / Cloud SQL warm-up times out `begin` → learner can't start (OPS-1, likelihood ↑). (b) A `begin` retry that isn't keep-first resets `started_at` → **free extra time** (fidelity break). (c) A classroom's synchronized begins exhaust the connection pool. |
| **R6** | CX1/CX2 | Data Integrity | OPS-5, SEC-6, IMPL-2 | 3×2=**6** | 🔴 high | **Late-flush clobber + dwell connascence.** Last-write-wins by `updated_at` lets a stale offline buffer clobber a newer answer; and `dwell` monotonic-max is a **connascence-of-algorithm across the client/server boundary** — if one side sums and the other maxes, replays silently corrupt dwell. |
| **R7** | CX1 | Correctness/Auditability | OPS-4 | 2×3=**6** | 🔴 high | **Lazy-only finalization.** Auto-submit fires only on load/interaction; a learner who never returns leaves the run `in_progress` forever, and analytics either omit it or (R12) skew on it. |
| **R8** | CX2/CX5 | Correctness | OPS-10 | 2×3=**6** | 🔴 high | **sqlite can't exercise concurrent-writer ordering**, so a Postgres-only upsert/`updated_at` concurrency bug (R6) passes every parity test and only bites in prod. |
| **R9** | CX1 | Correctness/Continuity | IMPL-7 | 3×2=**6** | 🔴 high | **Countdown re-anchor / shared-util drift.** `use_countdown` anchors on `Date.now()` at mount; *partially mitigated* by plan §0 (`durationMs = deadline_at − now` each mount), but the reused Test-Mode timer utils are shared — a third consumer's change silently alters exam timing. |
| R10 | CX2 | Data Integrity | SEC-7 | 2×2=4 | 🟠 med | Late buffered flush writes items into an already-**finished** section → items no longer reconcile with the frozen grade. |
| R11 | CX1 | Correctness | OPS-6 | 2×2=4 | 🟠 med | Answer entered in the client's believed window, flushed just after the true server deadline, refused, silently dropped. |
| R12 | CX3 | Correctness/Auditability | SEC-8, OPS-8 | 2×2=4 | 🟠 med | Analytics honesty regressions: null→0/default (facet <5 items shown as a real %), or derivation over in-progress/abandoned runs → fabricated strength/weakness into **both** results and `/learn/progress`. |
| R13 | CX3 | Maintainability | IMPL-8 | 2×2=4 | 🟠 med | Computed-never-stored recompute cost grows; a RULES-table edit silently shifts `/learn/progress` output for a surface not under test. |
| R14 | CX4 | Evolvability | IMPL-5 *(single-lens)* | 2×2=4 | 🟠 med | Section-agnostic model validated by **N=1** (one A–D 24-item form); 5-choice / different-scale official forms may not fit the "landing zone." |
| R15 | CX2 | Durability | IMPL-6, SEC-9 | 2×2=4 | 🟠 med | Parity test compares column *shapes* not constraints/defaults; and pg `GREATEST` vs sqlite `MAX/CASE` dwell-merge can diverge → parity green, prod wrong. |
| R16 | CX5 | Isolation | IMPL-4 | 2×2=4 | 🟠 med | Even once written, an import-edge scan can miss type-only / dynamic `import()` / barrel / transitive edges → the R1 guard passes **vacuously**. |

## Matrix — context × criterion (hotspots)

Column sums rank **contexts**; row sums rank **criteria** (highest-product per cell shown):

| Criterion \ Context | CX1 live | CX2 seam | CX3 analytics | CX4 registry | CX5 boundary | **row Σ** |
|---|---|---|---|---|---|---|
| Data Integrity | 6 (R6) | 4 (R10) | — | — | — | **10** |
| Correctness/Auditability | 6 (R7,R9,R11) | 6 (R5) | 4 (R12) | — | 6 (R8) | **22** |
| Durability/Continuity | 9 (R2) | 6 (R5) | — | — | — | **15** |
| Recoverability | 9 (R2) | — | — | — | — | **9** |
| Modularity/Isolation | — | 6 (R4) | — | 4 (R14) | 9 (R1,R16) | **19** |
| Confidentiality | 9 (R3) | 6 (R3,R4) | — | 9 (R3) | — | **24** |
| **col Σ (hotness)** | **🔥 48** | **🔥 28** | 4 | 13 | **24** | |

**Reading:** the hottest **context** is **CX1 (live timed-run)**, then **CX2 (persistence seam)** and **CX5 (isolation boundary)**. The hottest **criteria** are **Confidentiality** and **Correctness/Auditability**, with **Modularity/Isolation** third. This **confirms the stage-1 ranking** (Integrity/Correctness/Durability) and adds the emphasis stage 1 flagged: the *unenforced isolation boundary* and *client confidentiality* are where the new design carries the most exposure.

## Consensus log (convergence & single-lens)

- **Multi-lens convergence (salience signal):** R1 (isolation) ×2, R2 (buffer loss) ×3, R4 (dispatcher scoping) ×4, R6 (clobber/dwell) ×3, R12/R15 ×2. These independently-recurring risks are the spine of the report.
- **Single-lens identifications — deliberated (Phase-2 rule):** **R3** (client-key, Security-only) and **R14** (registry N=1, Impl-only). R3 is exactly the *lone-identifier-with-experience* case risk-storming exists for — I am **not** discounting it for lacking a second vote; it is elevated to blocking. R14 is acknowledged by the spec (phase-1 registry = the deliverable) → held at medium.
- **Anchoring/deliberation on R1:** initial positions SEC-4 `6` vs IMPL-3 `9`; driven to **9** — impact is unarguably 3 (corrupts FSRS state / voids the separation), likelihood 3 because the guard is *absent* today and can lag the code it polices. No conformity collapse; the merge is reasoned, not averaged.

## Phase 3 — mitigations (priced; **human accepts/rejects each**)

**Blocking (unmitigated high in a design about to be built — surface before ship):**

- **R1 → write `test_exam_isolation.test.ts` FIRST, red-before-green** (plan task T-E, but *reorder it to the front*). Cost: **S** (the plan already scopes it). Also add a deliberate **red fixture** (a forbidden edge that must fail) so it can't pass vacuously (closes R16); assert on the resolved module graph incl. type-only + dynamic imports.
- **R3 → decide the answer-key posture *before* build** — does the durable, scored, analysed exam trip **ADR-0013's "stake" tripwire**? Two options: (a) **grade server-side** and ship in-progress questions *without* answer-bearing fields (the ADR-0013 Option-B mode, cost **M**); (b) explicitly **re-affirm client-grading as accepted-risk** for phase-1 practice with the `COACH_TEST_KEYS_CLIENT_SERVED` tripwire documented (cost **S**, but records the exposure). **This is a significant decision → route to arch-decide** (new ADR or an ADR-0040/0013 amendment).
- **R2 → buffer durability ladder** (layer incrementally): flush on `visibilitychange=hidden`/`pagehide` via `navigator.sendBeacon` (**S**) → mirror the buffer to `localStorage` with a backoff retry queue (**S–M**) → block *scored finalization* while a buffer is unflushed (**S**) → shrink debounce near the deadline (**S**). This is the stage-2 **C4→Write-Buffer split** paying off — do the split so this logic is one tested unit.

**High — recommend mitigating:**

- **R4 → make learner-scoping mechanical, not positional.** Prefer a **named `{learnerId}` field** (connascence of name > position) *or* a test asserting `arg0-name == learnerId` for every `LEARNER_ARG` entry **and** that every exam method appears in the map (completeness) **and** dispatcher default = **deny**. Add the FR-3 foreign-`run_id`→empty test to **each** of the 9 methods, not one. Cost **S–M**. *(Also audit the inherited seam: is the 41-method dispatcher deny-by-default? — a systemic question beyond exam.)*
- **R5 → `begin` = keep-first upsert** keyed `(run_id, section_code)` returning the existing `started_at` on retry (kills the deadline-reset, **S**); set Cloud Run **min-instances ≥ 1** for the exam route + Cloud SQL keep-warm (**S**, ops cost); jittered backoff + pool cap for the classroom burst (**M**).
- **R6 → one shared dwell-merge spec.** Extract the monotonic-max merge to a single pure function (or a shared fixture replayed through *both* client reducer and server merge asserting identical output); stamp answer-time at *selection* not flush and reject writes older than stored `updated_at`; server-clamp dwell to the section budget. Cost **M**.
- **R7 → finalization is not lazy-only:** lazy-finalize on any *read* of an overdue run (**S**) and/or a server deadline sweeper (**M**).
- **R8 / R15 → run the concurrency + monotonic-max + constraint-level assertions against real Postgres in CI**, not only sqlite; make `schema.parity.test` assert constraints/defaults/PK-FK, not just column names. Cost **M**.
- **R9 → freeze the reused timer utils behind an exam-owned wrapper + a contract test**, so a third consumer can't silently change exam timing; keep the plan-§0 deadline re-derivation. Cost **S**.

**Medium — accept or defer (cheaper partials noted):** R10 reject item upserts to a finished section (**S**); R11 client hard-stop safety-margin + surface refused writes (**S**); R12 golden tests pinning every null trigger + filter analytics to finalized runs (**S**); R13 memo/cache keyed on run-version + a `/learn/progress` golden (**S**); R14 prove the registry against one synthetic 5-choice form now *or* explicitly scope phase-1 as concrete (**S**).

## GATE: ✅ ACCEPTED — 2026-09-02 (Rajnish Khatri)

- **Arbiter: ACCEPTED** — the 16 consensus risks, the **R1→9** merge, and the **R3**
  single-lens elevation all confirmed.
- **Business stakeholder: ACCEPTED** — the recommended mitigations for R4–R16 become the
  implementation **must-do/should-do list**.
- **Blocking items resolved:**
  - **R1 → build the isolation guard FIRST**, red-before-green, resolved-graph, with a red fixture (plan T-E reordered to the front).
  - **R2 → adopt the buffer durability ladder** (`pagehide`/`sendBeacon` → `localStorage` + retry → block scored finalize while unflushed), in the C4→Write-Buffer unit.
  - **R3 → routed to arch-decide** — an ADR/amendment will lay out server-side-grading vs client-grade-as-accepted-risk for a deliberate choice (not decided in-line).
- **Also to decisions.md:** R4 (named-vs-positional learner arg), R6 (shared dwell-merge fn).

*Assessment ratified. Re-run this storm after the isolation guard lands and after the first multi-device prod smoke.*
