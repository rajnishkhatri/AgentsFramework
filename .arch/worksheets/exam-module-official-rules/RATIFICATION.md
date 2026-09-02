# Ratification Checklist — Exam module arch-* sweep (1→6)

> **Batch / provisional-gate run.** Every stage was traversed *provisionally* — nothing is
> Accepted, no ADR was authored or flipped, no OKF/`docs/adr/` file was written. All outputs
> stay provisional until you ratify below. Target = `exam-module-official-rules`.
> Sources: [spec](../../../docs/plan/exam-module-official-rules.spec.md) · [plan](../../../docs/plan/exam-module-official-rules.plan.md) · [ADR-0040](../../../docs/adr/0040-exam-module-durable-runs-analytics.md).
> Evidence sweep (2026-09-02): **all** load-bearing repo claims verified.

## A. Per-stage gates (confirm or amend)

- [x] **Stage 1 · Characteristics** — ✅ **ACCEPTED 2026-09-02.** Driving 6; top-3 = Integrity · Correctness · Durability; demotions confirmed; ★ FR-5 cursor = fidelity + honest-failure (availability rejected as driver). Carries the R2 obligation. → [worksheet](characteristics-worksheet.md)
- [x] **Stage 2 · Components** — ✅ **ACCEPTED 2026-09-02.** 10-component set accepted; **C4→Write-Buffer split ADOPTED**; Dwell-Tracker split DECLINED (dwell stays in reducer). → [components](../../components/exam-module-official-rules/logical-components.md)
- [x] **Stage 3 · Style** — ✅ **ACCEPTED 2026-09-02** (all 4 determinations): 1 quantum · existing store + `exam_*` + computed analytics · sync begin/finish + async-buffered writes (`begin` = hard sync point) · new module + internal microkernel/registry. Determination 5 (record sync/async) → duty D3. → [style](style-decision.md)
- [x] **Stage 4 · Decide** — ✅ **AUDIT ACCEPTED 2026-09-02.** ADR-0040 sound; **D3 (sync/async) + D4 (business line) written into ADR-0040** (OKF lint 0 failures, status still `proposed`). ADR acceptance (D1) + D2/D5 pending. → [audit](decide-audit.md)
- [x] **Stage 5 · Risk** — ✅ **ACCEPTED 2026-09-02.** 16 risks + R1→9 merge + R3 elevation confirmed; R4–R16 mitigations = the build must-do/should-do list; blocking R1/R2 committed, R3 → arch-decide. → [risk](../../risk/exam-module-official-rules/risk-report.md)
- [x] **Stage 6 · Validate** — ✅ **SIGNED OFF 2026-09-02** (all 9 intersections; amber axes #2/#3/#6/#8 covered by ratified R5/R8/R15/R1/D4). Governance table + release checklist accepted. → [validation](validation-report.md)

## B. Queued gate-resident duties (surfaced, NOT performed)

- [ ] **D1 · Accept ADR-0040** (Proposed→Accepted + index/log per DoD §9) — a human act; **not flipped at sdd-implement 2026-09-02** (LLM-humility). Status remains `proposed`.
- [ ] **D2 · Approval-criteria first-use conversation** — cost/cross-team/security thresholds that route future ADRs to a higher authority. **Path captured 2026-09-02** in [`docs/adr/common/approval-criteria.md`](../../../docs/adr/common/approval-criteria.md); all three values **UNSET** (none exist in spec/plan/ADR — do not invent). Human fills the table to close.
- [x] **D3 · Record the sync/async communication boundary** — ✅ DONE: *Communication posture* paragraph added to ADR-0040 §Decision (2026-09-02, OKF lint clean).
- [x] **D4 · Add the explicit business-value line** — ✅ DONE: *Business value* bullet added to ADR-0040 §Rationale (2026-09-02, OKF lint clean).
- [x] **D5 · (optional)** — ✅ DONE: recorded in `docs/adr/decisions.md` (2026-09-02 sweep entry, item 4).

## C. Blocking items (resolve BEFORE writing component code)

- [x] **R1 · Build `test_exam_isolation.test.ts` FIRST** — ✅ **COMMITTED 2026-09-02** (red-before-green, resolved-graph, + red fixture; plan T-E reordered to the front).
- [x] **R2 · Buffer durability ladder** — ✅ **COMMITTED 2026-09-02** (`pagehide`/`sendBeacon` + `localStorage` mirror + retry + block scored finalize while unflushed, in the C4→Write-Buffer unit).
- [x] **R3 · Answer-key posture** — ✅ **ADR-0041 ACCEPTED (Option A) 2026-09-02** — [0041-exam-answer-key-posture.md](../../../docs/adr/0041-exam-answer-key-posture.md), status `accepted`, index+log updated, OKF lint clean. Client-grade phase-1 behind the ADR-0013 tripwire; commits to the `test_exam_no_client_served_keys` guard; server-grade (Option B) is the committed evolution at the delivery/stake trigger.

## D. Decisions routed back to arch-decide

- [x] **R3** answer-key posture → ✅ **ADR-0041 ACCEPTED (Option A)** 2026-09-02.
- [x] **R4** named-vs-positional learner arg → ✅ recorded in `decisions.md` (2026-09-02 sweep entry, item 1).
- [x] **R6** one shared dwell-merge function/fixture → ✅ recorded in `decisions.md` (2026-09-02 sweep entry, item 2).

## E. Re-entry triggers (this is iterative, not one-shot)

- Re-run the **risk storm** after the isolation guard lands and after the first multi-device prod smoke.
- Re-open **intersection #9 (GenAI)** when the deferred LLM improvement-narrative arrives.
- Re-enter **arch-components** if the C4 split or a second form changes the component set.

---

**Nothing above is ratified.** When you sign items off, the corresponding stage output flips
from provisional to accepted; unresolved misalignments route back to their owning stage.
