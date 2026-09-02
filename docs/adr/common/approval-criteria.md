---
type: convention
title: 'ADR approval-criteria thresholds (higher-authority routing)'
status: pending-human
created: 2026-09-02
updated: 2026-09-02
owner: Rajnish Khatri
related: 0040-exam-module-durable-runs-analytics.md, exam-module-official-rules.tasks.md
tags: [convention]
---

# ADR approval-criteria thresholds (higher-authority routing)

**Status:** ⏳ **PENDING HUMAN (D2)** — 2026-09-02 implement-time capture.
**Audience:** anyone authoring a future ADR who needs to know whether the call
routes to a higher authority than the usual Stage-2 / tasks→implement gate.

---

## Decision path (do not invent values)

The arch-lifecycle stage-4 audit queued **D2** as a first-use conversation:
agree the **cost / cross-team / security** thresholds that route future ADRs
to a higher authority, then record them here
([decide-audit](../../../.arch/worksheets/exam-module-official-rules/decide-audit.md),
[RATIFICATION](../../../.arch/worksheets/exam-module-official-rules/RATIFICATION.md) §B).

sdd-implement (2026-09-02) searched the exam-module spec, plan, ADR-0040,
ADR-0041, and `decisions.md` for those three **approval-routing** numbers.
**None are present.** The numeric floors that *do* exist in the spec
(FR-32 ≥5 items / accuracy 0.80 / 0.60; FR-33 pacing ≥3 trailing unanswered /
careless ≥30 % of wrong) are **analytics read-model rules**, not ADR-routing
thresholds. They must not be reused here.

Until a human fills the table, **no mechanical higher-authority route exists**.
Default remains the existing ADR ratchet (`⚠️ Ask first` → numbered ADR +
index/log). Filling a cell is a human act; an agent must not guess a number.

| Axis | Question the conversation must answer | Value |
|---|---|---|
| **Cost** | Above what spend / infra / calendar-cost does an ADR escalate? | **UNSET** — not in spec/plan/ADR |
| **Cross-team** | Above what blast radius (teams / surfaces / owned seams) does an ADR escalate? | **UNSET** — not in spec/plan/ADR |
| **Security** | Which trust-boundary / integrity / privacy classes always escalate? | **UNSET** — not in spec/plan/ADR |

**How to close D2:** human supplies the three values → this file's Status
flips to Accepted → `docs/adr/index.md` + `log.md` get a newest-first line
→ RATIFICATION §B D2 is checked.

---

## Related (not this file)

- **D1** (ADR-0040 Proposed → Accepted) closed **2026-09-02** (human). See
  [ADR-0040](../0040-exam-module-durable-runs-analytics.md). D2 is independent and still UNSET.
- Analytics label / quadrant floors live in the spec (FR-32/FR-33) and will
  be restated in `decisions.md` when `exam_analytics` lands (DoD §9) — not here.
