---
title: 'D3 — Session-length decision (Q-1b) · Implementation trace'
type: impl
sprint: D3
epic: D
status: Implemented — 2026-07-11 (Phase 1 docs-only; keep 30)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D3-session-length.tasks.md
---

# D3 — Implementation trace

Paste-only evidence log. Branch: `feat/preact-parity-d3-session-length` (from `main` @ 80aeb5f).

## T-DES-D3 — Framing review (Q-1b options + ADR amend anatomy)

### 1. Keep 30 vs move to N

| Axis | Keep 30 (Candidate A) | Move to N (Candidate B; prototype narrative = 10) |
|------|------------------------|--------------------------------------------------|
| Adaptive-loop mastery signal | Matches ADR-0023: 30 is the adaptive mastery signal S3 shipped for. Coverage-ratchet + no-repeat validator designed against 30 × 2 (= 60-Q audit). | Shorter sessions; mastery convergence needs more sessions per skill. Product truth, not a code bug — note in `decisions.md` if chosen. |
| Session-length UX | Longer drill (~30 items). Thin skills (`s-sent = 23` reviewed) cannot fill 30 unique today — FR-11 end-early-on-exhaustion keeps runtime correct. | Prototype fidelity: `design-spec.md:143` reads "Session = 10 items, Punctuation drill". At N=10, current thin-skill bank fills a full drill without waiting on S3-pre bank growth. |
| Coverage-ratchet + no-repeat | Audit stays 2 sessions of 30. Already green. | Becomes `ceil(60/N)` sessions (e.g. 6 × 10). Validator must re-run; dedup still required. |
| Prototype fidelity | Spec author read: the `10` is a **session-supplement narrative** (demo walkthrough), not an acceptance criterion. | Closest match to the visible prototype sample session line. |
| Migration cost | Docs-only: one `decisions.md` line. Zero code, zero test rewrites. | One-const change + ADR-0023 amend + ~17 test literals (G8: value substitution, not weakening; seen-fail-first). |

**Spec recommendation (not binding):** keep 30 — ADR-0023 locked it; the prototype `10` is narrative-only; FR-11 already handles thin-skill shortfall.

### 2. ADR-0023 amend anatomy (only if flip to N)

Not used — outcome kept 30. Shape was locked pre-decision in case of flip (see tasks T-DES-D3).

## T-D0 — Draft `decisions.md` framing entry

Draft PENDING line written, then replaced at T-D2.

## T-D1 — Human answer

**Verbatim:** `keep 30` (user selected option 1).

**Rationale (from Candidate A / framing):** ADR-0023 adaptive mastery signal; design-spec `:143` "10" is narrative-only; FR-11 covers thin-skill shortfall.

## T-D2 — Final `decisions.md` entry

```
- Q-1b (2026-07-11): DEFAULT_TARGET_COUNT stays at 30. Rationale: ADR-0023 locked 30 as the adaptive-loop mastery signal; PreAct/UI-Design/design-spec.md:143's "Session = 10 items" is a sample-session narrative, not an acceptance criterion; FR-11 end-early-on-exhaustion already keeps thin-skill drills correct. Rejected alternative: move to 10 (prototype fidelity + full drills on today's thin bank without S3-pre). Docs-only — no code, no ADR-0023 amend.
```

Grep: no `DRAFT` marker remains on the Q-1b line.

## T-D3 — Sprint board

D3 header → ✅ Implemented *(decision-first, docs-only)*; Implementation evidence block added.

## T-D4 — Parity report §Q-1b

Row → ✅ **Resolved** — keep 30; cites `decisions.md` Q-1b line.

## T-D5 — Branch decision

Outcome = `keep 30` → Phase 2 **skipped**. Sprint COMPLETE (docs-only).

## T-VAL-D3a — Docs-verify runbook (Phase 1 shrink)

See `frontend/scripts/validate_d3_session_length_ui.md` (Part docs only; T-VAL-D3b/c skipped).

## T-Z — Final gate

See pasted `make check` + `pytest tests/architecture/ -q` output below after run.
