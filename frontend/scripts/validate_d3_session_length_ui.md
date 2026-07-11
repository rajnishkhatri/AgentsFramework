# D3 — Session-length decision (Q-1b): validation guide

Phase 1 outcome was **keep 30** (docs-only). Runtime behaviour is unchanged —
`DEFAULT_TARGET_COUNT` stays 30; ADR-0023 is not amended. This runbook shrinks to
docs verification only (tasks: skip T-VAL-D3b / T-VAL-D3c).

| Artifact | Path |
|---|---|
| Spec | [`docs/plan/preact-parity-D3-session-length.spec.md`](../../docs/plan/preact-parity-D3-session-length.spec.md) |
| Plan | [`docs/plan/preact-parity-D3-session-length.plan.md`](../../docs/plan/preact-parity-D3-session-length.plan.md) |
| Tasks | [`docs/plan/preact-parity-D3-session-length.tasks.md`](../../docs/plan/preact-parity-D3-session-length.tasks.md) |
| Impl | [`docs/plan/preact-parity-D3-session-length.impl.md`](../../docs/plan/preact-parity-D3-session-length.impl.md) |
| Board | [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md) §D3 |
| Decisions | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) (Q-1b 2026-07-11) |
| Parity | [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](../../docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md) §Q-1b |
| ADR-0023 | [`docs/adr/0023-quiz-bounded-session-target-count.md`](../../docs/adr/0023-quiz-bounded-session-target-count.md) — **not amended** |

**What you are proving:** FR-1 only (product answer recorded). Phase 2 FRs do not fire.

---

## Part docs — verify the decision record

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent

# Final Q-1b line present; no DRAFT marker
rg -n 'Q-1b \(2026-07-11\)' docs/adr/decisions.md
rg -n 'DRAFT.*Q-1b|Q-1b.*DRAFT' docs/adr/decisions.md && echo "FAIL: DRAFT still present" || echo "PASS: no DRAFT"

# Outcome = keep 30
rg -n 'DEFAULT_TARGET_COUNT stays at 30' docs/adr/decisions.md

# Rejected alternative + source citation
rg -n 'Rejected alternative: move to 10|design-spec.md:143' docs/adr/decisions.md

# Board flipped
rg -n 'Sprint D3.*Implemented' docs/plan/preact-parity-sprint-board-D.md

# Parity §Q-1b resolved
rg -n 'Q-1b.*Resolved.*keep 30' docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md

# Const unchanged (sanity)
rg -n 'DEFAULT_TARGET_COUNT = 30' frontend/lib/adapters/engine/repos/drizzle_session_repo.ts

# ADR-0023 has no Q-1b Amendment section (Phase 2 skipped)
rg -n 'Amendment.*Q-1b' docs/adr/0023-quiz-bounded-session-target-count.md && echo "FAIL: unexpected amend" || echo "PASS: no Q-1b amend"
```

### Pass/fail

| Check | Pass looks like |
|---|---|
| FR-1 decisions.md | Newest-first Q-1b line: stays at 30 + rejected move-to-10 + design-spec:143 cite |
| Board | D3 header ✅ Implemented; evidence block cites keep 30 |
| Parity | §Q-1b ✅ Resolved — keep 30 |
| No Phase 2 | `DEFAULT_TARGET_COUNT = 30` still; no ADR-0023 `## Amendment — … (Q-1b` |

---

## §A — automated gate (T-Z)

```bash
make check
pytest tests/architecture/ -q
```

Paste actual output into `docs/plan/preact-parity-D3-session-length.impl.md` §T-Z.
