---
name: code-review
type: skill
description: >-
  Run AND interpret the unified, context-routed code reviewer (v3) over the
  current branch's changed files in THIS repository (AgentsFramework `agent`
  monorepo). Use whenever the user asks to "review my changes", "run the
  reviewer", "code review this branch/PR", "check my diff before commit/push",
  "is this ready to merge", or wants a `review.json` / a CI reviewer verdict
  explained. The skill picks the right invocation for the situation
  (working-tree vs PR-vs-main vs explicit files; deterministic by default, LLM
  opt-in), then does the part that matters: it reads the `ReviewReport` and
  hands back a verdict, the criticals to fix first, an honest list of what was
  NOT checked, and a fix-vs-justify call on each finding — every finding traced
  to the owning folder's `AGENTS.md` rule. Routes each path to its `REVIEW.md`
  via `code_reviewer/routing.py`, runs the deterministic AST/TS validators
  first (D1/D4/D5 + TAP-2/TAP-4 + ADR.1 + FD2/FD3), then optionally the
  WI-8-certified v3 LLM judge (TPR=1.0 / TNR=1.0, `claude-haiku-4-5-20251001`).
  Mirrors what CI now runs (the `reviewer` job + PR comment bot), so a local run
  predicts the gate. Do NOT use for Langfuse trace audits, judge calibration, or
  Playwright E2E (separate skills).
---

# Code Review (unified, context-routed v3) — invoke **and** interpret

One reviewer, routed by changed path to each folder's thin `REVIEW.md`
enforcement map (`REVIEW.md` cites `AGENTS.md` rule IDs — it never copies
prose). Your job is two halves, and the second is the one that adds value:

1. **Invoke** the reviewer with the right command for the user's situation.
2. **Interpret** the resulting `review.json` — don't just dump it. Give a
   verdict, the criticals to fix first, an honest gaps list, and a fix-vs-justify
   recommendation, each finding traced to its rule.

A raw `review.json` paste is a non-answer. Always close the loop with the
interpretation in the report structure below.

## When to use

- "Review my changes / my diff / this branch / this PR."
- "Run the reviewer / routed reviewer / code review."
- "Check my diff before commit / before pushing." / "Is this ready to merge?"
- "Explain this review.json / the CI reviewer verdict / the PR bot comment."
- Any request to validate code against the repo's architecture invariants.

Do **not** use this for: Langfuse trace audits (→ `governance-trace-audit`),
LLM judge calibration (→ `agentsframework-eval-probe`), or Playwright E2E
(→ `agentsframework-playwright`).

## Step 1 — Pick the invocation from the situation

Don't ask the user which command to run; infer it. Deterministic is the default
everywhere — it needs no API key, is reproducible, and is exactly what CI runs.
Reach for `--llm` only when the user explicitly wants the certified judge's
take on the LLM-only rules (style/design dimensions the AST checks can't see).

| The user's situation | Command (run with `.venv/bin/python`) |
|---|---|
| "before I commit" / unstaged work | `--from-git-diff --git-base HEAD` |
| "before I push" / "review this branch/PR" / "ready to merge?" | `--from-git-diff --git-base 'origin/main...HEAD'` |
| a specific set of files, no git | `--files path/a.py path/b.tsx` |
| they want the LLM judge too | add `--llm` (needs `ANTHROPIC_API_KEY` etc.) |
| they already have a `review.json` / CI verdict | **skip to Step 2** — interpret it, don't re-run |

Full form (deterministic, PR-style):

```bash
.venv/bin/python -m meta.code_reviewer --from-git-diff \
    --git-base 'origin/main...HEAD' --prompt-version v3 --output review.json
```

`make review` is the same thing (`BASE=origin/main...HEAD` default; `ARGS="--llm"`
to add the judge; `BASE=HEAD` for working-tree). Prefer it when the user is
clearly in a make-driven flow; otherwise the explicit command is clearer about
what ran.

**Exit codes:** `0` approve · `1` request_changes · `2` reject · `3` error.
These mirror the CI `reviewer` job, which **blocks merge only on `2` (reject)**
and surfaces `1` without failing — so when you report, say which way CI would go.

**Always pass `--from-git-diff` (not bare `--files`) when git is available** —
the ADR.1 new-service trigger relies on `git diff --diff-filter=A` to see added
files (confirmed at `meta/code_reviewer.py` `_git_diff_files`); a bare `--files`
list only fires the three file-presence triggers.

## Step 1.5 — Sanity-check the report before you trust it (do not skip)

The reviewer can exit `0` (`approve`) while having reviewed **nothing**. That is
the single most dangerous outcome for a pre-merge gate, and it is invisible
unless you look: the exit code and your own `git diff` will both look fine while
`review.json` quietly says it saw zero files. So before interpreting anything:

1. **Read `review.json` itself** — actually open the artifact. Do not reconstruct
   the verdict from the exit code, and do not narrate the files *you* saw in your
   own `git diff` as if the reviewer saw them. The interpretation is of the
   reviewer's output, not of your shell history.
2. **Check `files_reviewed`.** If it is empty (`[]`) — or its count disagrees
   with the `git diff --name-only <base>` you ran for situation detection — then
   **this is a vacuous result, not a pass.** An `approve` over an empty review
   set is never "clean", never "mergeable", never "confidence 1.0". Diagnose the
   cause (don't just observe the empty diff) — `git merge-base --is-ancestor HEAD
   origin/main`, `git log <base>..HEAD`, `ls <described path>` — and report it:
   - the diff genuinely is empty (branch already merged / behind remote, wrong
     base, no changes, or the change lives in a **different worktree or branch**) —
     say which, and say "the gate did not run on any of your changes."
   - the reviewer's git invocation is broken — fall back to an explicit
     `--files <paths>` run (feed it the paths from your own `git diff`) to get a
     real review, and flag the `--from-git-diff` path as defective.
3. **Only when `files_reviewed` is non-empty and consistent** with your `git diff`
   do you proceed to Step 2 and interpret the verdict as real.

Decision, stated once so it can't be softened: **`verdict == approve` AND
`files_reviewed == []` ⇒ report a vacuous pass, never a green light.** This is
the rule that turns the reviewer's own silent-failure mode into a catch instead
of a rubber stamp.

**If you run a fallback review against a *different* base** (e.g. local `main...HEAD`
because `origin/main` already contains HEAD), label its verdict a **diagnostic
surrogate, not the CI verdict.** CI will run the real (anomalous) base and get the
vacuous `approve`; your fallback `reject`/`request_changes` is "what you'd see if
the base were correct." Say both: (a) what CI will actually do now, and (b) what
the corrected-base review found. Never let the fallback verdict masquerade as CI's.
A fallback against a stale local `main` is count-sensitive — tell the user to
`git fetch` and re-confirm before trusting the numbers.

## Step 2 — Interpret the report (the part that matters)

`review.json` is a `ReviewReport`: `verdict`, `dimensions[]` (each finding has
`rule_id`, `dimension`, `severity`, `file`, `line`, `description`,
`fix_suggestion`, `confidence`, `certificate`), `gaps[]` (what was NOT
evaluated), `validation_log[]` (which tools ran on which files).

Read it, then produce the report below. Rules that keep you honest:

- **Deterministic findings take precedence over LLM judgment** and are
  trustworthy now. LLM findings carry calibrated confidence — surface it.
- **`gaps[]` is not noise — it's the honesty ledger.** Deterministic-only runs
  always leave the LLM-only dimensions (style, design intent) in `gaps[]`. Say
  what was *not* checked plainly; an "approve" from a deterministic run means
  "no deterministic violation found," not "this is good code."
- **Quote fields, don't invent numbers.** Every number you state — a `confidence`,
  a file count, a test count, a rule_id, the `statement` — must be a value you read
  from a named `review.json` field (`files_reviewed`, `findings[].confidence`,
  `statement`, …). Do not assert confidence/TPR/TNR/coverage figures that aren't in
  the artifact or a named benchmark file; a fabricated metric violates `meta/`'s
  AP-6 (a number is a claim about a quadrant with data). If you quote `confidence:
  1.0` on an empty review, say it's confidence in *nothing*, not assurance.
- **Then fill the template below.** The recurring regressions (three-way CI gate,
  routed rule per finding, two blocking paths, provenance) are *fields* in it — not
  advice to remember. Filling the template correctly is the bar.

### Report structure — fill every field; an empty field is a visible omission

This is a **checklist, not a suggestion**. The skill's best behaviors regress when
they live in prose the agent has to remember — so they are template fields here.
If you can't fill a field, say why; never silently drop it. Copy this shape:

```
**Verdict:** <approve | request_changes | reject>
**CI gate** (state ALL THREE every time — the user reasons about re-run verdicts):
  - approve (exit 0) → reviewer job PASSES.
  - request_changes (exit 1) → informational PR comment, NON-BLOCKING (gate stays green).
  - reject (exit 2) → BLOCKS merge.
  → This run: <which line applies>.
Reviewed N files (from `files_reviewed`) vs <base>. <one-line headline>.

**Critical — fix before merge** (if any)
- [<rule_id>] file:line — <what's wrong>. Fix: <fix_suggestion, condensed>.
  Rule: <folder>/AGENTS.md <invariant/rule name> (routed via <folder>/REVIEW.md).
  Blocks via: <CI reviewer gate (reject only) | make check + tests/architecture/ (independent)>.
  Provenance: <branch-introduced (you must fix) | pre-existing on <base> (inherited, not your regression)>.

**Warnings — fix or justify**
- [<rule_id>] file:line — <what>. Recommendation: <fix | justify-in-PR, and why>.
  Rule: <folder>/AGENTS.md <rule> (routed via <folder>/REVIEW.md).

**Clean** (REQUIRED when files_reviewed lists files with no findings)
- "No findings on <file>." — name each, so the user knows nothing was dropped.

**Not checked (gaps)**
- <gap>, … — be explicit these need the --llm pass / tsx / etc. If a vacuous/empty
  run reports "no ADR.1 trigger", say that's because the diff was empty, NOT a clean
  ADR bill of health.

**Next action** (authoritative gate first)
- <make check / tests/architecture/ is the authoritative blocker for D1/D4 — lead
  with it; the reviewer re-run is consequent, not the gate. Then: file ADR(s) if
  triggered (see below), re-run reviewer to clear the comment.>

**Optional — design/style pass** (offer on every run; the LLM judge is gate-grade):
- `.venv/bin/python -m meta.code_reviewer --from-git-diff --git-base 'origin/main...HEAD'
  --prompt-version v3 --llm --output review_llm.json`  (needs ANTHROPIC_API_KEY etc.)
  The WI-8 judge is certified TPR=1.0/TNR=1.0 — quote that from
  `tests/fixtures/code_reviewer/wi8_validation/`, don't assert it bare.
```

**Hard rules the template encodes** (these are the recurring regressions — they are
not optional):

- **Never write "blocks merge" next to a `request_changes` verdict.** The CI
  reviewer gate fails *only* on `reject`. A `request_changes` is a non-blocking
  comment. State the three-way gate first, *then* a finding's blocking status.
  This is a **trust** rule, not a wording nit: tell a user `request_changes`
  "blocks merge" and you either send them chasing a block that isn't there, or you
  teach them the reviewer's verdicts can't be trusted — the gate model is only
  useful if its blocking claims are exact every time.
- **Every finding names its routed rule** — `<folder>/AGENTS.md` *and* the
  `<folder>/REVIEW.md` seam — not just the root `AGENTS.md`. Criticals, warnings,
  and named passing dimensions alike.
- **Two blocking paths, never collapsed.** (a) the CI reviewer gate (reject only)
  vs (b) `make check` / `tests/architecture/`, which fails D1/D4 criticals
  *regardless* of the reviewer verdict. A `request_changes` with a D1 critical is
  non-blocking *in the reviewer gate* but still blocked *by the architecture suite*.
- **Write the LLM pass to `review_llm.json`**, not over the `review.json` you're
  interpreting. `make review ARGS="--llm"` is a verified shorthand but writes
  `review.json`. Use bare `python` **never** — only `.venv/bin/python`.

If the verdict is `approve` with non-empty `files_reviewed` and zero findings,
collapse to: verdict line + the three-way gate + what was checked + clean files +
gaps caveat + the LLM-pass offer. (Empty `files_reviewed` ⇒ Step 1.5 territory —
do **not** collapse to "ready".)

### Mapping a finding to its rule (cite, don't invent)

Every `rule_id` traces to a folder's `AGENTS.md`; the reviewer reached it via
that folder's `REVIEW.md`. Name the owning folder when you report a finding —
e.g. a `D1` upward-import in `services/` cites `services/AGENTS.md` (routed via
`services/REVIEW.md`). The known folders each have their own `REVIEW.md`:
`trust/`, `services/`, `components/`, `orchestration/`, `meta/`, `prompts/`,
`frontend/`, `middleware/`; everything else falls back to the root `REVIEW.md`.
Never invent a rule; if a `REVIEW.md` row couldn't be evaluated, it belongs in
`gaps[]`, not in findings.

### Provenance pass on criticals (whose regression is this?)

When the diff range is wide (a fallback review, a long-lived branch), some
criticals may be **pre-existing on the base**, not introduced by this branch —
the user shouldn't be sent to fix code that isn't theirs. For each critical (and
a sample of warnings when there are many), check whether the offending line
predates the branch:

```bash
git cat-file -e <base>:<file> 2>/dev/null && echo "exists on <base>"   # file is old
git log --oneline -1 <base> -- <file>                                   # last base touch
git blame -L <line>,<line> <base> -- <file>                             # who/when on base
```

Report criticals in two buckets: **branch-introduced** (the user must fix) vs
**pre-existing/inherited** (the run flags them, but they aren't this branch's
regression). This changes the call — and note that `confidence` is the reviewer's
confidence in the *rule match*, not in "this is yours to fix"; say so when
provenance lowers the actionable confidence.

### New-service / "wired it in" — a required ADR-trigger enumeration

Parsing rule: **"wired in" / "hooked up" / "integrated" / "plumbed in" almost
always means TWO `⚠️ Ask first` triggers, not one.** A new service rarely arrives
alone. When the user describes adding *and* integrating a change, you MUST run the
full trigger checklist and surface **every** one that applies — each is its own
ADR.1 obligation. Stopping at the service is the recurring miss:

- **new horizontal service** (`services/<x>/`) — the service itself,
- **new graph node** in `orchestration/react_loop.py` — the "wiring"; AND it must
  stay a thin ≤10–15-line wrapper (Invariant #6),
- **new abstraction** (G1),
- **new `pyproject.toml` dependency** — e.g. a notifications service likely adds an
  SMTP / HTTP-client dep,
- **trust-kernel type change** in `trust/models.py` (triggers re-signing),
- **templated messages** — if the service renders any message/prompt text, it goes
  through `PromptService.render_prompt()` as a `.j2` file, never a hardcoded
  f-string (D5/AP-3 — the classic place this slips).

**Re-run gotcha:** the deterministic ADR.1 trigger only fires under
`--from-git-diff` (it uses `git diff --diff-filter=A` to see *added* files like the
new `__init__.py`). The new files must be **committed/added** before re-running, or
the trigger stays silent. When you advise an ADR + re-run, say this.

ADR mechanics (so it's structurally valid first time): copy
`docs/adr/0000-template.md`, add frontmatter `type:`, an `index.md` entry, and a
newest-first `log.md` line. (Or an `ADR-OK:` waiver in the commit for a range.)

## What the deterministic phase checks (trustworthy now)

| Dimension | Check | Tool |
|---|---|---|
| D1 Architectural Compliance | dependency table, no upward imports | `check_dependency_rules` |
| D4 Trust Framework Integrity | trust purity (no I/O in `trust/`) | `check_trust_purity` |
| D5 Code Quality | anti-patterns (AP-2/3/5/6) | `detect_anti_patterns` |
| D2 ADR Ratchet | `⚠️ Ask first` diff with no new `docs/adr/` | `detect_adr1_missing` (file-list) |
| D3 Test Quality | TAP-2 mock addiction (>3 mocks/test) | `detect_mock_abuse` |
| D3 Test Quality | TAP-4 failure-path ratio | `detect_failure_path_ratio` |
| FD2/FD3 Frontend | CSP, iframe sandbox, secrets, JWT, composer | TS predicates (`code_reviewer/frontend/tools.py`) |

## Honest limits — say these out loud in the report

- **LLM verdicts ARE gate-grade — the WI-8 judge is certified.** The certification
  numbers are not folklore: quote them from their source —
  `tests/fixtures/code_reviewer/wi8_validation/` (the committed `verdicts.json` +
  its `README.md`). A recorded 20-case run (`claude-haiku-4-5-20251001`) scored
  **TPR=1.0 / TNR=1.0** there, certifying the v3 LLM judge at the ≥ 0.90 gate. Cite
  that path when you state the numbers; don't assert them bare. The WI-8
  harness replays that recording in CI (`tests/code_reviewer/test_wi8_validation.py`)
  — **no live LLM in CI**. Re-record when the judge model changes
  (`scripts/record_code_reviewer_validation.py`); commit a new `verdicts.json`
  only if TPR/TNR ≥ 0.90.
- **A deterministic-only `approve` is not "good code."** It means no AST/TS
  violation fired. The design/style dimensions are in `gaps[]` until `--llm` runs.
- **TAP-4 is file-level**, not per-decision-point coverage. It catches
  overwhelmingly-happy-path suites, not every missing branch test.
- **Frontend TS tools require `tsx`** (`cd frontend && npm install`). Missing
  `tsx` surfaces as a `gaps[]` entry, not a hard failure.
- **ADR.1 new-service trigger** needs `--from-git-diff`; with bare `--files`
  only the three file-presence triggers fire.

## How this fits the automated gates (PR #107)

The same deterministic reviewer now runs in three automated places — so an
on-demand run here *predicts* what the team's gates will say:

- **CI `reviewer` job** (`.github/workflows/python-tests.yml`, PR-only) runs
  `--deterministic-only` vs `origin/<base>...HEAD` and **blocks merge on `reject`
  only**; `request_changes` is surfaced, non-blocking.
- **PR comment bot** (`.github/workflows/reviewer-comment.yml`) posts/updates one
  informational comment summarizing `review.json` — never changes the gate.
- **Advise-only harness hooks** (`scripts/hooks/stop_adr_reminder.py`,
  `subagent_stop_review.py`) remind mid-session; they never block (hooks can't
  capture a typed ADR answer — the `GATES.md` honest limit). The merge-time
  `tests/architecture/test_adr_ratchet.py` is the hard ADR gate.

When you interpret a verdict, translate it into "CI would pass / surface /
block" so the user knows the merge consequence, not just the label.

## After the run

The template's **Next action** field already orders this: fix criticals first,
recommend fix-vs-justify per warning, file any triggered ADR(s) (mechanics in the
new-service section), then `make check`. The one thing to internalize: **`make
check` / `tests/architecture/` is the authoritative gate** for D1/D4 — the reviewer
is the top rung of the ladder, not a replacement for the rungs below it. Re-running
the reviewer only clears the PR comment; it doesn't make a D1 critical mergeable.

## Source

Plan: `docs/plan/unified_context_routed_reviewer.plan.md` (WI-6, WI-7).
ADR: `docs/adr/0004-automated-code-review-integration.md` (the CI/hook wiring).
Router: `code_reviewer/routing.py`. Runner: `meta/code_reviewer.py`.
Review maps: `*/REVIEW.md` + root `REVIEW.md`. Cite-lint:
`code_reviewer/cite_lint.py` (enforces `REVIEW.md`→`AGENTS.md` cites; in `make check`).

## Cursor parity (WI-7)

The same content chain resolves in Cursor as in Claude Code — only the
path-attachment mechanism differs:

- **`.cursor/rules/<folder>-review.mdc`** (one per known folder) are
  **Auto-Attached** via `globs: <folder>/**`: when a file in that subtree is in
  context, Cursor loads the rule, which points the agent at that folder's
  `REVIEW.md`. The router does the actual path→`REVIEW.md` resolution at CLI
  time, so the `.mdc` body stays a thin pointer — it never restates rule prose.
- **`.cursor/rules/code-review-dispatch.mdc`** is **Agent-Requested**: it fires
  on "review my changes" and covers root-level files + the root `REVIEW.md`
  fallback.
- **No per-edit reviewer hook.** The reviewer is dispatched on demand —
  deterministic-first; even a certified LLM judge should not gate every keystroke.

Parity is guard-tested in `tests/code_reviewer/test_cursor_mdc_parity.py`.
