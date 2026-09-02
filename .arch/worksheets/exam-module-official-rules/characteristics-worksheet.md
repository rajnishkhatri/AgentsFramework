# Characteristics Worksheet — Exam module (official-rules durable test suite)

> Stage 1 of the arch-* sweep · **review mode** · target = `exam-module-official-rules`
> Sources: [spec](../../../docs/plan/exam-module-official-rules.spec.md) · [plan](../../../docs/plan/exam-module-official-rules.plan.md) · [ADR-0040](../../../docs/adr/0040-exam-module-durable-runs-analytics.md)
> Repo claims verified by evidence sweep (2026-09-02) — citations inline.

## Domain in one line

A **measurement instrument**: a full-length practice exam that behaves like the
official ACT/PreACT sitting (timed sections one-at-a-time, official nav/timing,
per-question dwell + mark-for-review), whose results **persist across sittings and
devices** and drive a **computed strength/weakness analysis**. It is *not* a teaching
loop (that's the FSRS practice quiz, kept hard-separate).

The domain fact that dominates: **a practice test that reports the wrong score, leaks
another learner's data, or fabricates a scale band is worse than no test.** So the
driving characteristics are integrity/correctness-flavored, not throughput-flavored.

## Candidate extraction (source-tagged)

| Candidate | Source | From |
|---|---|---|
| Data integrity (idempotent, isolated, honest-null) | explicit | FR-3, FR-4, FR-7, FR-8, FR-27, §7 |
| Correctness / official-rules fidelity + reproducible scoring | explicit | §2 "official rules", FR-1/2/11–16/27/28 |
| Durability / cross-device continuity | explicit | §1, FR-14, plan §3 (device read-back) |
| Recoverability / fault-tolerance (offline, reload) | explicit | FR-5, FR-21, §6 |
| Modularity / evolvability (section-agnostic + registry + isolation) | explicit+implicit | §2.1, §4, FR-6/9/26 |
| Confidentiality / privacy (learner-scoped behavioral data) | implicit+explicit | §5, FR-3 |
| Determinism / analyzability of the read model | explicit | §7, FR-30–33 |
| Performance / latency | explicit | §7 (debounce, single round-trip, O(n)) |
| Scalability / elasticity | implicit | — |
| Reversibility / deployability | explicit | §7, plan §3 |
| Availability (BFF reachable during a section) | implicit | FR-5 (deliberately relaxed) |

## 3-part test applied (nondomain · needs structure · critical)

Kept as **driving** (all three true, and the *new* design — not just the inherited
seam — is responsible):

| # | Driving characteristic | Why it needs *structure* (not just design) |
|---|---|---|
| 1 | **Data Integrity** | Exactly-once write effect + owner isolation + honest-null require the upsert/monotonic-max semantics, the dispatcher `LEARNER_ARG` override, and the finish-once path — all structural. |
| 2 | **Correctness / Auditability** | Official rules are enforced by a *server-anchored deadline state machine* + reproducible pure scoring/analytics, not by UI politeness. |
| 3 | **Durability / Continuity** | Survive-reload-and-device-switch needs durable `exam_*` tables + server-recorded `started_at`; can't be done in a `useReducer` (that's exactly what Test Mode is, and why it can't be extended — [test_runner_reducer.ts:30](../../../frontend/components/test/test_runner_reducer.ts#L30)). |
| 4 | **Recoverability / Fault-tolerance** | Offline-buffer + flush + "not saved" surfacing is a structural resilience path (FR-5), not a try/catch. |
| 5 | **Modularity / Evolvability** | Section-agnostic model + form registry + **hard isolation** from practice are structural seams; isolation in particular has *no enforcement today* ([test_frontend_layering.test.ts:33-105](../../../frontend/tests/architecture/test_frontend_layering.test.ts#L33) covers `lib/` rings only). |
| 6 | **Confidentiality / Privacy** | Learner-scoping = dispatcher override + ownership joins ([route.ts:28-100](../../../frontend/app/api/engine/db/[method]/route.ts#L28)). *Largely inherited* from ADR-0038 — the new duty is "don't weaken it." |

**Demoted to "handle via design" (fails needs-structure or critical at driving level):**

- **Performance / latency** → design, not structure. Data is hundreds of rows/learner, analytics is O(n), writes are debounced single round-trips. No structural pressure. (§7)
- **Reversibility / deployability** → satisfied *by construction*: additive tables + own route + Test Mode untouched; rollback = remove the nav entry (plan §3). Real, but not a structural driver.

**Others Considered (fails critical):**

- **Scalability / elasticity** — learner-scoped, no burst, no fan-out. Not critical.
- **Availability of the BFF during a section** — **deliberately de-prioritized.** FR-5 tolerates unreachability (local clock keeps running). Recorded as a *rejected* driver so the trade is explicit, not accidental.
- **Interoperability** — no external consumers in phase 1.

## Composite decomposition & contested terms

- **"Integrity" ≠ "Correctness."** Integrity = writes have exactly-once effect, are
  well-formed, owner-isolated (data isn't *corrupted*). Correctness = the computed
  outputs (raw/scale/composite/analytics) are the *right values* per official rules.
  Both driving, kept distinct.
- **"Durability" ≠ "Availability."** Durability = committed state survives failure /
  restart / device. Availability = the service answers *now*. The design maximizes
  durability and **explicitly relaxes availability** (FR-5).
- **"Recoverability" ≠ "Reliability."** We assume faults happen (offline, reload) and
  target graceful restore + honest failure — not a low failure rate.
- **Determinism/analyzability** folded into **Correctness/Auditability**: the pure
  read-model (`ExamRunItem[]+ExamSection[] → ExamAnalytics`, no storage) is *how*
  reproducible correctness is achieved (ADR-0040 rejected storing analytics, option C).

## Objective definitions + measures (fitness-function seeds → stage 6)

1. **Data Integrity** — *fitness:* L2 `duplicate upsert applied once; dwell monotonic-max` (FR-4); L2 `foreign learner ⇒ 403/404` (FR-3); L2 finish-once returns stored result (FR-27); L1 honest-null (FR-7/8). **Caveat:** idempotency tests must assert the *stored value/effect count*, not just "no throw" — a silent no-op also "passes twice."
2. **Correctness / Auditability** — *fitness:* L1 `exam_scoring` (raw over scored-only; scale from table; composite `round(mean)`, .5 up — FR-27/28); L1 reducer deadline→expired+writes-refused (FR-1); L1 golden-fixture analytics (FR-30–33). **Caveat:** measure rule-by-rule in L1, not via one e2e smoke — a smoke pass hides a single broken rule.
3. **Durability / Continuity** — *fitness:* L4 reload-resume (countdown from `started_at`, answers/flags restored, ≤ one debounce-window dwell lost — FR-14/21); `schema.parity.test` (pg+sqlite); plan §3 second-device read-back. **Caveat:** durability is of *committed* writes; the un-flushed loss is bounded and stated, not zero.
4. **Recoverability / Fault-tolerance** — *fitness:* L1 `use_exam_section` offline-buffer flushes; failed flush ⇒ visible "not saved", never silent success (FR-5). **Caveat:** this is the characteristic that *trades against* #2 — see tension table.
5. **Modularity / Evolvability** — *fitness:* L1 `exam_entities` zod round-trip + registry load assertions (FR-6/9); L1 rules-as-data fire/don't-fire (§4.4); **arch:** `test_exam_isolation.test.ts` — no import edge `components/exam|exam_run_repo ↔ quiz/scheduler/skill_state` + no `skill_state` write (FR-26). **Caveat:** isolation is on *data/scheduler edges*, NOT on pure-util reuse — `format_clock`/`use_countdown`/`Grader` are deliberately reused ([use_countdown.ts:13](../../../frontend/components/test/use_countdown.ts#L13)).
6. **Confidentiality / Privacy** — *fitness:* shares #1's foreign-learner test; grep for no-new-answer-logging (§5). **Caveat:** inherited from ADR-0038; obligation is non-regression.

## Divergent clusters (→ arch-style quantum input)

The candidates split into two intra-module clusters plus one cross-subsystem seam.
Do **not** average them into one set (the "fatal flaw").

- **Cluster A — live timed-run (in-section):** drivers = Correctness/fidelity +
  Recoverability + Integrity. *Stateful, failure-sensitive, latency-sensitive,
  eventually-consistent* (buffer/flush, monotonic-max).
- **Cluster B — post-hoc analytics/review:** drivers = Determinism + honesty +
  analyzability. *Read-only, pure, wants a settled snapshot.* Reconciled by ADR-0040's
  choice to **compute, not store** analytics — it always reflects settled items.
- **Cross-subsystem hard seam: exam ⟂ practice/FSRS** (Modularity/isolation). These
  must **not** share a quantum or data (test exclusivity, FR-26). This is the sharpest
  architectural line and it is currently **unenforced** — the top governance item.

## Tension pairs (note the cursor the human must place)

| Pair | The trade | How the design resolves it |
|---|---|---|
| **Correctness/fidelity ↔ Recoverability** ★ | Official rule "clock never pauses" vs "don't lose the learner's work offline" | Local clock keeps running (fidelity) + buffer/flush (work) + "not saved" surfacing (honesty). **THE signature trade-off — FR-5.** |
| Durability ↔ Availability | Require BFF up vs tolerate offline | Availability *relaxed*; durability + local resilience chosen. |
| Integrity ↔ Latency | Persist every nav vs debounce | Persist on nav-away + submit, debounced; bounded ≤ current-question un-flushed dwell. |
| Modularity/isolation ↔ Reuse | No practice edges vs reuse timers | Isolate *data/scheduler* edges; reuse *pure utils*. |

## Proposed top 3 (confirm in any order — not a full ranking)

1. **Data Integrity**
2. **Correctness / Auditability**
3. **Durability / Continuity**

Reasoning: these three *are* the module's reason to exist over the already-shipped
Test Mode — durable, honest, reproducible measurement. #4–#6 are load-bearing but
either inherited (Confidentiality) or a resilience refinement (Recoverability) or a
roadmap enabler (Modularity).

**Elimination probe — "drop one, which?":** two honest candidates —
(a) **Confidentiality** (least *new* work — already delivered structurally by the
inherited ADR-0038 dispatcher), or (b) **Recoverability** (a v1 could require
connectivity and drop the offline buffer). The human owns this call; I lean (a),
because relaxing (b) removes a *named* failure path (FR-5) while (a) only removes
*new* responsibility for an already-enforced property.

---

## GATE: ✅ ACCEPTED — 2026-09-02 (Rajnish Khatri)

- **Driving list (6): ACCEPTED as-is.**
- **Top-3: ACCEPTED** — Integrity · Correctness · Durability.
- **Demotions: ACCEPTED** — Performance, Reversibility → design; Availability → deliberately rejected driver.
- **★ Cursor: ACCEPTED** — FR-5 fidelity-over-availability-with-honest-failure is the ratified resolution (availability stays a rejected driver). Carries the Stage-5 **R2** obligation: the offline buffer needs a real durability path for this to be safe.
