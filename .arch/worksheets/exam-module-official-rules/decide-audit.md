# ADR Audit (Stage 4) — Exam module

> Stage 4 of the arch-* sweep · **review / existing-decision mode** (work backwards from
> the in-place ADR). **No file written to `docs/adr/`** — that is the governed OKF bundle;
> in provisional mode this stage *audits* [ADR-0040](../../../docs/adr/0040-exam-module-durable-runs-analytics.md)
> and **queues** duties, it does not author or accept ADRs.

## Verdict on ADR-0040: **sound and well-formed — accept after two small additions**

| Check | Result |
|---|---|
| **Significant?** (Nygard + Third-Law) | ✔ Yes. Structure + non-functional + interfaces + dependencies; options A–F each carry real trade-offs. A legitimate ADR, not a non-decision. |
| **Timing** (last responsible moment) | ✔ Correct. Stage-2 plan gate, before code, with the seam verified. Not premature, not CYA. |
| **Template** (Context/Decision/Options/Rationale/Consequences) | ✔ All present. Options-rejected table (A–F) is strong — the intent-debt payload is there. |
| **Status flow** | ✔ Proposed (not Accepted). DoD §9 requires acceptance + index/log. **I do not flip it** (LLM-humility clause). |
| **Recency fit** | ✔ Rides [ADR-0038](../../../docs/adr/log.md) (accepted 2026-07-22), "does not supersede it" — correct. Consistent with the 0015/0021/0023 test-exclusivity lineage. No contradiction with 0037–0039. |
| **Both justifications** (technical **and** business) | ⚠ **Technical strong; business implicit.** → finding B1. |
| **Compliance/governance section** | ⚠ Present but *scattered* in Consequences (the `test_exam_isolation` guard + honesty invariants), not a dedicated section. → stage 6 formalizes. |

## Handed-over decisions (stage 3) — every item accounted for

| Decision | Disposition |
|---|---|
| Style: new module vs extend Test Mode vs reuse `quiz_session` | **Merged** — ADR-0040 options A/B |
| Data topology: compute-not-store analytics; `exam_*` namespace; same DB | **Merged** — ADR-0040 options C/F |
| Edge: generic dispatcher vs dedicated handlers | **Merged** — ADR-0040 option E |
| ★ **Sync/async communication boundary** (async-buffered writes decouple the live-run from store availability; sync `begin`/`finish`; `begin` = hard durability point, can't-begin-offline) | ⚠ **NOT recorded** → **duty D3** below. Recommend **merging into ADR-0040 while it is still Proposed** (a Proposed ADR may be amended): add it as a Consequences paragraph or an option row, so the availability-relaxation trade is on the record, not just implied by FR-5. Lighter alternative: a `decisions.md` line. |
| Microkernel/registry framing for forms | Observation only → at most a `decisions.md` line (D5, optional) |

## Findings

- **B1 — business justification is implicit.** The Rationale is entirely technical
  (simplest-thing / what-the-abstractions-buy / honesty / deterministic-first). The
  litmus test (`no business value ⇒ reconsider`) *passes on substance* but not *on the
  page*: the real business value is **user satisfaction** (a durable, honest, cross-device
  practice exam that guides study) + **strategic positioning** (the section-agnostic form
  registry is the *landing zone for the privately-ingested official forms* — the product's
  differentiator) + **time-to-market** (reuses the paved ADR-0038 seam; no new infra).
  → **Add one explicit business-value line before acceptance.**
- **B2 — the isolation guard is the load-bearing new invariant, and it does not exist
  yet.** ADR-0040 Consequences already says `test_exam_isolation.test.ts` is a *new*
  enforced boundary. The evidence sweep **confirms** nothing enforces frontend
  component-to-component isolation today ([test_frontend_layering.test.ts:33-105](../../../frontend/tests/architecture/test_frontend_layering.test.ts#L33) covers `lib/` rings only). This is correctly recorded — carried to stage 5 (risk) and stage 6 (governance) as the #1 item.

## GATE: ✅ VERDICT ACCEPTED — 2026-09-02 (Rajnish Khatri)

**Verdict accepted:** ADR-0040 is architecturally sound and accept-ready. The audit itself
is ratified; the ADR's own `Proposed → Accepted` flip stays with the human (D1).

**Queued duties — status:**

- **D3 · Record the sync/async boundary — ✅ DONE.** Added as a *Communication posture*
  paragraph in ADR-0040 §Decision (2026-09-02). OKF lint: 0 failures.
- **D4 · Business-value line — ✅ DONE.** Added a *Business value* bullet to ADR-0040
  §Rationale (2026-09-02). OKF lint: 0 failures.
- **D1 · Acceptance — ⏳ PENDING (human).** ADR-0040 Proposed → Accepted + index/log per
  DoD §9. `updated:` bumped to 2026-09-02; status left `proposed`.
- **D2 · Approval-criteria first-use conversation — ⏳ PENDING (needs your thresholds).**
  The cost / cross-team / security thresholds routing future ADRs to a higher authority,
  to be recorded in `docs/adr/common/approval-criteria.md` (does not exist; not created).
- **D5 · (optional) — ⏳ PENDING.** A `decisions.md` line for the microkernel/registry-for-forms framing.

*Audit ratified. ADR-0040 body strengthened (D3/D4); its acceptance (D1) + D2/D5 remain on the checklist.*
