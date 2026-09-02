# Style & Quanta Decision — Exam module (official-rules durable test suite)

> Stage 3 of the arch-* sweep · **review mode** · the join of
> [characteristics](characteristics-worksheet.md) + [components](../../components/exam-module-official-rules/logical-components.md)
> **Ratings note:** the methodology's star-rating figures are images and are not in this
> bundle — every rating below is **prose-reconstructed qualitative**, never invented stars.

## 0. Decision-readiness

| Input | Status |
|---|---|
| Domain understood | ✔ measurement instrument (worksheet §domain) |
| Characteristics worksheet on file | ✔ stage 1 |
| Data-architecture constraint | ✔ **must ride the existing durable engine seam** (single relational store, pg prod / sqlite parity), migration `0005` |
| Cloud/on-prem | ✔ GCP Cloud Run frontend + Cloud SQL (existing topology) |
| Organizational | ✔ solo/small team, frontend-only diff, high process maturity (SDD + arch tests) |
| AWS AI/ML capability | ✔ **n/a** — no LLM anywhere (§7); `aws-ai-assess` not invoked |

No material `needs-input` tags — the constraints are all known and inherited.

## 1. Determination 1 — one quantum or many? → **ONE**

Coupling test ("shared DB ⇒ same quantum"): the `exam_*` tables live in the **same Cloud
SQL**, are reached through the **same `EngineDb` seam**, and deploy in the **same Cloud Run
frontend**. → the exam module is the **same quantum as the host app**.

- The two intra-module clusters (A live-run, B analytics) **do not** counteract enough to
  split — they share `exam_run_item` and the deployable; B is a *pure read* over A's data
  (analytics computed-not-stored), so it cannot form its own quantum.
- ★ **Key nuance:** the **exam ⟂ practice** isolation (FR-26) is a **logical boundary
  inside one quantum**, *not* a quantum split. Exam and practice share the DB and the
  EngineDb seam → same quantum by the coupling test. Isolation is bought by **import-edge
  arch-tests**, not by deployment separation. This is the correct **modular-monolith** move
  — a quantum split for test-exclusivity would be gross over-engineering.

**Quantum map:** one quantum (the app); exam = a new *module* with two internal clusters
and a hard *logical* seam to practice (dotted red `x` in the stage-2 diagram).

## 2. Determination 2 — where does data live? → **existing single relational store, new `exam_*` tables**

- Default-to-challenge ("one relational DB"): challenged and **kept** — data is
  learner-scoped, a few hundred rows/learner, no independent scaling need.
- Tables already split along the aggregate: `exam_run → exam_section_attempt →
  exam_run_item` ([schema.pg.ts:205](../../../frontend/lib/adapters/engine/db/schema.pg.ts#L205) is the `quiz_session` precedent). Namespaced `exam_*` to avoid the
  `test_item` content-table collision (ADR-0040 option F).
- **Analytics has no table — computed read model** (ADR-0040 option C rejected storage):
  nothing to invalidate; single source of truth for tunable thresholds. A genuine
  data-topology decision → already recorded in ADR-0040.

## 3. Determination 3 — sync or async? → **sync boundaries + async-buffered writes**

- **Sync:** `beginExamSection` and `finishExamSection` are single round-trips (plan §7).
- **Async/decoupled:** in-section item writes are **buffered + debounced + offline-tolerant**
  (FR-5), flushed on nav/submit/reconnect.
- ★ **Dynamic Quantum Entanglement check (the important one):** if the live-run
  synchronously blocked on the BFF for every dwell/answer write, it would **inherit the
  store's availability** (entanglement collapse) — the section would freeze when the network
  hiccups. The async buffer is precisely what **prevents** that collapse: it keeps the
  latency/availability-sensitive live-run independent of store availability. Correct use of
  async — *to protect a boundary*, not for fashion.
- **One honest hard sync point:** `begin` must record server `started_at` before the clock
  is trustworthy (durability anchor, FR-13/14). If the BFF is down *at begin*, the section
  can't start durably — acceptable (no work lost yet), but name it (stage-5 risk: "can't
  begin offline").

## 4. Candidate styles — trade-off matrix (driving chars as rows)

Shortlist consistent with {one quantum, one DB, sync+async-buffer}:

- **A. New module in the modular-monolith / Frontend-Ring app** *(chosen; incumbent)*
- **B. Extend Test Mode in place** *(ADR-0040 option A — the "reuse, no new module" pole)*
- **C. Separate exam quantum/service** *(the distributed pole)*

| Driving characteristic | A · new module | B · extend Test Mode | C · separate quantum |
|---|---|---|---|
| Data Integrity | **strong** (own tables + upsert semantics) | weak (Test Mode has no persistence to be idempotent over) | strong but redundant |
| Correctness/Auditability | strong (dedicated state machine) | weak (single-section reducer, no deadline/composite model) | strong |
| Durability/Continuity | **strong** (durable seam) | **fails** (ephemeral by consent gate) | strong |
| Recoverability | strong (buffer/flush in the hook) | n/a | strong |
| Modularity/Evolvability | **strong** (registry plug-ins; logical isolation) | weak (retrofit rewrites it, breaks pinned e2e) | strong but heavy |
| Confidentiality | strong (inherited dispatcher scoping) | n/a | strong |
| Simplicity / cost | **strong** (plugs into existing patterns) | *appears* cheap, but retrofit ≈ rewrite | **poor** (new deploy unit, 11 fallacies) |
| Testability | strong (pure modules + in-memory port fake) | mixed | strong |

**Isomorphism read:** the module is **customization-shaped along the *forms* axis** (Test-01
English now; Math/Reading/Science, 5-choice, real official forms, differing scale tables
later). That shape is **microkernel** — a *core* (Section Run Machine + Score Computer +
persistence) plus **form plug-ins via the registry**. So the least-worst pick is a
**hybridization**: the module sits in the app's modular monolith (macro) and internally
adopts a **microkernel/registry pattern** for form extensibility. This binds directly to the
roadmap (phase 1 is deliberately one plug-in).

**Fashion check:** option C (separate service) would be *fashion over fit* — no independent
scaling, no discrete-processor shape, no event backbone. The 11 distributed fallacies are
the argument against it: the design already treats its **one** network hop (client→BFF) as
unreliable (FR-5); C would multiply such hops for zero benefit. The design correctly resists
the fashion.

## 5. Least-worst pick + edge/access topology (component stage excluded this)

**Pick:** **A — new module in the modular monolith, microkernel-flavored internally for
forms.** Losing alternatives: B (ephemeral by contract; retrofit = rewrite + breaks pinned
Test-Mode e2e), C (distributed cost for no distributed benefit).

**Edge / access / UI topology** (surfaced here so a later stage doesn't have to):

- **Routes (3, under the existing `(coach)` group + WorkOS auth):** `/learn/exam` (home),
  `/learn/exam/[runId]` (results+analytics), `/learn/exam/[runId]/[section]`
  (directions→runner→review).
- **Edge = the *existing* dispatcher** `POST /api/engine/db/[method]` — **no new route
  family** (ADR-0040 option E). Access control lives here: `LEARNER_ARG` overrides the
  learner arg from the server claim ([route.ts:28](../../../frontend/app/api/engine/db/[method]/route.ts#L28)) → FR-3 isolation is an *edge* property.
- **Actor classes = one** (authenticated Learner). **No proctor/admin surface** in phase 1
  — stated explicitly so no later stage assumes one.
- **Reachability gate:** the nav entry (`nav_model` exam screen + `SCREEN_TITLES`) is the
  last commit of T-D — the feature is unreachable until then (rollback = remove it).

## 6. Decisions requiring ADRs (follow-on list → stage 4)

| Decision | Status |
|---|---|
| Style: new module vs extend Test Mode vs reuse `quiz_session` | ✔ **ADR-0040** (options A/B) |
| Data topology: compute-not-store analytics; `exam_*` namespace; same DB | ✔ **ADR-0040** (options C/F) |
| Edge: reuse generic dispatcher vs dedicated handlers | ✔ **ADR-0040** (option E) |
| ★ **Sync/async communication boundary** — async-buffered writes to decouple live-run from store availability; sync `begin`/`finish`; `begin` as a hard durability point | ⚠ **NOT separately recorded** — the *resilience* (FR-5) is specced, but the *architectural communication decision* is implicit. → **stage-4 candidate** (new ADR or `decisions.md` line). |
| Microkernel/registry framing for forms | observation only → at most a `decisions.md` line |

**Self-check vs sealed worked-answers:** intentionally **not opened** — the seal holds the
book's *own kata* answers, and this is a real-system review with no matching kata, so a diff
would only risk anchoring on unrelated content. Seal left intact.

---

## GATE: ✅ ACCEPTED (per determination) — 2026-09-02 (Rajnish Khatri)

1. **Quantum count = 1: CONFIRMED** (module in the existing quantum; isolation logical, not physical).
2. **Data = existing single store + `exam_*` + computed-not-stored analytics: CONFIRMED.**
3. **Comm = sync begin/finish + async-buffered item writes: CONFIRMED** — `begin` accepted as a hard sync/durability point (can't begin offline; Stage-5 **R5** owns cold-start).
4. **Style = new module (modular monolith) + internal microkernel/registry: CONFIRMED.**
5. **New ADR-candidate (sync/async boundary): carried to Stage 4 as duty D3** (not yet recorded).
