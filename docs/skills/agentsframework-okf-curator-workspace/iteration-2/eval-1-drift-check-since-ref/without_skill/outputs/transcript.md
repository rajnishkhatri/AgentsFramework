# Transcript — doc-drift check since recent code changes (no skill)

Task: "Are our docs stale relative to the code we changed in the last few
commits? Give me a worklist of which docs reference code that just changed and
might need updating. Don't edit anything yet — just the report."

Worktree: `/tmp/okf-eval-1-without` (sandbox). REPORT ONLY — no docs created/edited.

## Steps

1. **Surveyed recent history.** `git log --oneline` showed the 3 most-recent
   commits (cf79094, 3f33db5, 38e6fa2) are docs-only "OKF bundle migration".
   `git log -- '*.py' '*.ts' ...` revealed the last real CODE commits are the
   memory-layer / chat-persistence feature line (4efd155, f4cd671, e80068f,
   1b18ee4, ...). Decided the meaningful drift WINDOW = `4efd155~1..HEAD`.

2. **Listed changed source files** with `git diff --name-only 4efd155~1 HEAD`,
   filtering out tests/fixtures/e2e/docs → 51 source files (backend wire/server/
   react_loop/memory + frontend ports/adapters/components).

3. **Extracted distinctive symbols** from the CURRENT text of each changed file
   via a python3 script (`/tmp/drift_scan.py`, then a tightened
   `/tmp/drift_scan2.py`): CamelCase classes/types, `useX` hooks, `makeX`
   factories, long snake_case fns, `*_node`/`*_carrier`. Filtered generic tokens
   (messages, count, start, phase, ...) and Test*/_Fake* helpers.

4. **Grepped the doc corpus** — all 454 tracked `*.md` (excluding eval-workspace
   outputs) — for those symbols AND for literal changed file paths. Ranked docs
   by (symbols + 3×path-refs). Got 20 candidate docs.

5. **Triaged by real age.** Key correction: `git log -1 -- <doc>` reported almost
   every doc as "edited today (cf79094)", but inspecting the cf79094 diff
   (`git show cf79094 -- <doc>`) proved those edits were frontmatter + link-path
   only — NOT content. So I computed each doc's last SUBSTANTIVE commit by
   skipping the 3 OKF migration commits. This split the 20 into stale reference
   docs (Apr–May) vs plan docs edited within the window (Jun).

6. **Confirmed drift concretely** for the stalest reference docs by grepping for
   the NEW capabilities and getting count 0:
   - AGENT_UI_ADAPTER_ARCHITECTURE.md, FRONTEND_WIRE_..._DEEP_DIVE.md,
     BACKEND_SOLUTION_ARCHITECTURE.md, END_TO_END_TRACING_GUIDE.md all mention
     `suppress`=0, `MemoryRecalled`=0, `ThreadStore`=0.
   - Verified the adapter arch doc's DomainEvent catalog is MISSING the 4 events
     now in `domain_events.py` (MemoryRecalled, ReasoningSummarized,
     StepProgressed, TaskUnderstood) and the new suppress/thread routes.
   - Verified the new PATCH /agent/memory/{key} suppress route, MEMORY_SUPPRESSED
     carrier, and memory_store/thread_store ports via `git diff` of the window.

7. **Wrote `drift_report.txt`** — tiered worklist (A=stale reference docs to fix
   first, B=stale plan/sprint docs to verify, C=docs co-edited in the window /
   low risk, D=incidental matches) with per-doc reason, last-substantive date,
   and a concrete DO.

## Tooling produced (in /tmp, not committed)
- `/tmp/drift_scan.py`, `/tmp/drift_scan2.py` — symbol→doc mappers
- `/tmp/lastsub.sh` — last-non-OKF-commit-per-doc helper

## Verification of constraints
- Created/edited NO files under the docs corpus. The only files written are the
  two required outputs under
  `docs/skills/agentsframework-okf-curator-workspace/iteration-1/eval-1-drift-check-since-ref/without_skill/outputs/`
  (eval workspace, not documentation).
