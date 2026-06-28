# Transcript — OKF drift check (Routine 3), with_skill

Task: "Are our docs stale relative to the code we changed in the last few commits?
Give me a worklist of which docs reference code that just changed and might need
updating. Don't edit anything yet — just the report."

Repo (working root): `/tmp/okf-eval2-1-with`
Skill followed: `docs/skills/agentsframework-okf-curator/SKILL.md` -> **Routine 3 (Drift check)**
Python: `python3` (no `.venv` present in this repo — checked `.venv/bin/python`, absent).

## NO DOCS WERE EDITED
Confirmed before and after. `git status --porcelain | grep '\.md$'` returned nothing
tracked-modified by me (only the pre-existing untracked workspace dir + node_modules).
This was a REPORT-ONLY task. The only files I created are the two deliverables in this
`outputs/` directory (and a scratch file under `/tmp`); no file under the repo's `docs/`
content tree, no `research/`, no code, was touched.

## What I did, in order

1. Read the full SKILL.md. Confirmed Routine 3 is the drift check and that WINDOW CHOICE
   is the load-bearing decision the skill warns about ("the single most common way a
   drift check gives a false all-clear").

2. Read the bundled script `scripts/drift_report.py` to understand its mechanics:
   - It diffs `--since <ref>...HEAD` (TRIPLE-DOT = merge-base semantics).
   - It correlates changed CODE_PREFIXES files against authored docs (`docs/**`, `research/**`,
     excluding evidence dirs and index.md/log.md).
   - `--symbols` additionally flags docs that name a changed area but are MISSING a brand-new
     public symbol ([symbol-absent]).
   - It has a `_docs_only_window` guard that prints a "widen the window" NOTE only if EVERY
     changed file is under docs/ or research/.

3. Investigated the commit topology to choose the window deliberately:
   - `git log --oneline -15` and `--graph`: the 3 newest commits are the OKF docs-migration
     (`chore(docs): ...`); below them are the `feat/memory-layer-wiring` merges (#77–#80).
   - Per-commit classification: the migration commits are MIXED (mostly docs, but carry
     incidental code: scripts/okf_lint.py, meta/CodeReviewerAgentTest/*, frontend/lib/README,
     a couple of test edits) -> so the script's docs-only guard does NOT fire on HEAD~3.
   - Measured code-file counts via merge-base for several windows:
       HEAD~3...HEAD  -> 8 code files (docs-migration plumbing only)
       HEAD~6...HEAD  -> 8 code files (merges add nothing past the merge-base)
       HEAD~9...HEAD  -> 65 code files (FIRST window reaching the memory+chat feature)
   - Root cause of the "8 then suddenly 65" jump: the memory-layer code merged via MERGE
     commits, so for HEAD~3/HEAD~6 the merge-base already contains it. HEAD~9's merge-base is
     PR #76, the prior memory-layer merge, so HEAD~9...HEAD is the first window that actually
     contains services/long_term_memory.py, components/memory_context.py, the frontend
     memory_store/thread_store ports+adapters, RecalledMemories, the sidebar hooks, etc.
   - DECISION: widen to `--since HEAD~9` to reach "the code we changed in the last few
     commits" (the substantive memory-layer + chat-persistence work named in the commit
     subjects), not just the migration plumbing.

4. Ran the drift report three ways:
   a. `drift_report.py --since HEAD~3`                 (contrast — demonstrates the false all-clear)
   b. `drift_report.py --since HEAD~9 --symbols`        (PRIMARY full window: 65 files, 139 docs)
   c. `drift_report.py --since HEAD~9 --symbols --paths services/long_term_memory.py
        components/memory_context.py services/governance/memory_suppressed_carrier.py
        frontend/lib/ports frontend/lib/adapters frontend/components/memory
        frontend/components/chat`                       (SCOPED worklist: 25 files, 17 docs)

5. Analysis applied on top of the raw output:
   - The 139-hit full run is inflated by three core files referenced almost everywhere
     (orchestration/react_loop.py = 65 docs, middleware/app_prod.py = 28, black_box.py = 26).
     Counted these with a grep tally to explain the noise.
   - MATCH-TYPE caveat: all 8 new public symbols are FRONTEND types (ChromeStorage, SidebarTab,
     ThreadTurn, ThreadAppendRequest, ...), which no backend Architecture doc would name -> so
     [symbol-absent] fires on nearly every [path] hit and is LOW-PRECISION in this window.
     Documented this so a reader weights [path] over [symbol-absent] here.
   - Used the scoped pass (17 docs) as the actionable worklist, ordered into Tier A/B/C by
     number and specificity of [path] hits.
   - Noted a possible Routine-1 gap: services/governance/memory_suppressed_carrier.py is a NEW
     module with no doc referencing it by path (reported, not acted on).

6. Wrote `drift_report.txt` (the report — includes the window-choice explanation, the
   match-type labels [path]/[symbol-absent], the contrast run, and the worklist) and this
   `transcript.md`. Re-confirmed no docs edited.

## Commands run (verbatim, all from repo root /tmp/okf-eval2-1-with)
```
git log --oneline -15
git log --oneline --graph -14
git diff --stat HEAD~3 HEAD
git diff --name-only HEAD~3 HEAD | grep -vE '^docs/'
# per-commit docs-vs-code classification loop over HEAD..HEAD~5
git diff --name-only HEAD~3~1 HEAD~3 | grep -vE '^(docs/)'
git show --stat 38e6fa2
# merge-base code-file counts for windows n=3,6,9,12,15 (triple-dot)
git diff --name-only HEAD~9...HEAD | grep -E '^(services/|components/|orchestration/|...)'
git merge-base HEAD~9 HEAD ; git log -1 --format=... d127baa
python3 docs/skills/agentsframework-okf-curator/scripts/drift_report.py --since HEAD~3
python3 docs/skills/agentsframework-okf-curator/scripts/drift_report.py --since HEAD~9 --symbols
python3 docs/skills/agentsframework-okf-curator/scripts/drift_report.py --since HEAD~9 --symbols \
    --paths services/long_term_memory.py components/memory_context.py \
            services/governance/memory_suppressed_carrier.py frontend/lib/ports \
            frontend/lib/adapters frontend/components/memory frontend/components/chat
git status --porcelain | grep -E '\.md$'   # -> nothing I modified
```

## Outputs
- `drift_report.txt` — the report (window-choice rationale + match-type-labelled worklist).
- `transcript.md`     — this file.

## Compliance with the task
- Followed Routine 3. [yes]
- Used the bundled drift_report.py. [yes]
- Heeded WINDOW CHOICE guidance: recognized last-3-commits are docs-migration, widened to
  HEAD~9 to reach the real (memory-layer + chat) code; explained why HEAD~3 is a false
  all-clear and why merge topology forced HEAD~9. [yes]
- Used --symbols for deeper coverage. [yes]
- Labelled every hit by match type ([path] / [symbol-absent]) and explained the
  symbol-absent low-precision caveat for this window. [yes]
- REPORT ONLY — edited no docs. [yes]
- python3 used throughout (no .venv available). [yes]
