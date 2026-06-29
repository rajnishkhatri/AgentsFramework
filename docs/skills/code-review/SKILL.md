---
name: code-review
type: skill
description: >-
  Run the unified, context-routed code reviewer (v3) over the current branch's
  changed files in THIS repository (AgentsFramework `agent` monorepo). Use
  whenever the user asks to "review my changes", "run the reviewer", "code
  review this branch/PR", "check my diff before commit", or "run the routed
  reviewer". Routes each changed path to its owning folder's `REVIEW.md`
  enforcement map via `code_reviewer/routing.py`, runs the deterministic AST/TS
  validators first (D1/D4/D5 + TAP-2/TAP-4 + ADR.1 + FD2/FD3), then optionally
  the v3 LLM reviewer with the routed `REVIEW.md` injected. Deterministic
  findings are trustworthy now; the v3 LLM judge is **certified** by a recorded
  WI-8 run (TPR=1.0 / TNR=1.0, `claude-haiku-4-5-20251001`) — LLM verdicts are
  gate-grade for the routed LLM-only rules covered by the fixture. The WI-8
  harness (`scripts/record_code_reviewer_validation.py` +
  `meta/code_reviewer_validation.py`) replays the committed `verdicts.json` in CI
  (see `tests/fixtures/code_reviewer/wi8_validation/README.md`); re-record when
  the judge model changes.
---

# Code Review (unified, context-routed v3)

Run the unified reviewer over the current branch's changed files. One reviewer,
routed by changed path to each folder's thin `REVIEW.md` enforcement map
(`REVIEW.md` cites `AGENTS.md` rule IDs — it never copies prose).

## When to use

- "Review my changes / my diff / this branch / this PR."
- "Run the reviewer / routed reviewer / code review."
- "Check my diff before commit / before pushing."
- Any request to validate code against the repo's architecture invariants.

Do **not** use this for: Langfuse trace audits (→ `governance-trace-audit`),
LLM judge calibration (→ `agentsframework-eval-probe`), or Playwright E2E
(→ `agentsframework-playwright`).

## The contract (what gets enforced, from where)

```
changed paths (git diff --name-only)
        │
   path router (deterministic, code_reviewer/routing.py)
        │  per file: (folder, language, rules_file = nearest REVIEW.md)
        ▼
 ONE reviewer (v3) + loads each group's REVIEW.md (cites AGENTS.md)
        + runs the deterministic checks first (precedence)
        ▼
   ReviewReport JSON (verdict / dimensions / findings / gaps)
```

- `AGENTS.md` = rule **content** (coding agent loads it).
- `REVIEW.md` = thin **enforcement map** (reviewer loads it; cites rule IDs).
- Deterministic findings (AST/TS) take precedence over LLM judgment.

## How to run it

### 1. Deterministic-only (default — no API key needed, CI-safe)

```bash
python -m meta.code_reviewer --from-git-diff --git-base HEAD \
    --prompt-version v3 --output review.json
```

For a PR-style review of branch commits vs main:

```bash
python -m meta.code_reviewer --from-git-diff --git-base 'origin/main...HEAD' \
    --prompt-version v3 --output review.json
```

Exit codes: `0` approve · `1` request_changes · `2` reject · `3` error.

### 2. With LLM (requires ANTHROPIC_API_KEY / OPENAI_API_KEY / LITELLM_API_KEY)

```bash
python -m meta.code_reviewer --from-git-diff --git-base HEAD \
    --prompt-version v3 --llm --output review.json
```

### 3. Explicit file list (no git)

```bash
python -m meta.code_reviewer --files trust/foo.py services/bar.py \
    --prompt-version v3 --output review.json
```

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

- **LLM verdicts ARE gate-grade — the WI-8 judge is certified.** A recorded
  20-case run (`claude-haiku-4-5-20251001`, committed `verdicts.json`) scored
  **TPR=1.0 / TNR=1.0** (all 10 violations detected, all 10 clean cases cleared),
  certifying the v3 LLM judge at the ≥ 0.90 gate. The deterministic findings
  remain fully trusted; LLM findings carry calibrated confidence. The WI-8
  harness (`scripts/record_code_reviewer_validation.py` +
  `meta/code_reviewer_validation.py` + the 20-case fixture) replays the committed
  recording in CI (`tests/code_reviewer/test_wi8_validation.py`). **Re-record
  when the judge model changes** — run the recording script with an API key and,
  if TPR/TNR ≥ 0.90, commit the new `verdicts.json`. A failing recording must
  not be committed to flip the gate — iterate the v3 prompt and re-record.
- **TAP-4 is file-level**, not true per-decision-point coverage (impl→test
  mapping is deferred). It catches overwhelmingly-happy-path suites.
- **Frontend TS tools require `tsx`** (`cd frontend && npm install`). Missing
  `tsx` surfaces as a `gaps[]` entry, not a hard failure.
- **ADR.1 new-service trigger** needs `--from-git-diff` (it uses
  `git diff --diff-filter=A`); with a bare `--files` list only the three
  file-presence triggers fire.

## Reading the output

`review.json` is a `ReviewReport`:

- `verdict` — `approve` / `request_changes` / `reject`.
- `dimensions[]` — per-dimension status + findings (each finding has
  `rule_id`, `dimension`, `severity`, `file`, `line`, `description`,
  `fix_suggestion`, `confidence`, `certificate`).
- `gaps[]` — what was NOT evaluated deterministically (be honest about these).
- `validation_log[]` — which tools ran against which files.

Every finding cites a `rule_id` whose content lives in the folder's
`AGENTS.md`. Do not invent rules; if a `REVIEW.md` row cannot be evaluated,
record it in `gaps[]`.

## After the run

1. Read `verdict` + `dimensions[]`. Fix all `critical` findings first.
2. For each `warning`, decide fix vs. justify-in-PR.
3. If `gaps[]` lists an ADR.1 trigger you intentionally skipped, file the ADR
   under `docs/adr/` (copy `docs/adr/0000-template.md`) and re-run.
4. Re-run `make check` — the reviewer is the top rung of the verification
   ladder, not a replacement for the rungs below it.

## Source

Plan: `docs/plan/unified_context_routed_reviewer.plan.md` (WI-6, WI-7).
Router: `code_reviewer/routing.py`. Runner: `meta/code_reviewer.py`.
Review maps: `*/REVIEW.md` + root `REVIEW.md`. Cite-lint:
`code_reviewer/cite_lint.py` (enforces `REVIEW.md`→`AGENTS.md` cites,
locality, and mojibake; wired into `make check`).

## Cursor parity (WI-7)

The same content chain resolves in Cursor as in Claude Code — only the
path-attachment mechanism differs:

- **`.cursor/rules/<folder>-review.mdc`** (9 files, one per known folder) are
  **Auto-Attached** via `globs: <folder>/**`: when a file in that subtree is in
  context, Cursor loads the rule, which points the agent at that folder's
  `REVIEW.md`. The router (`code_reviewer/routing.py`) does the actual
  path→`REVIEW.md` resolution at CLI invocation time, so the `.mdc` body stays a
  thin pointer — it never restates rule prose.
- **`.cursor/rules/code-review-dispatch.mdc`** is **Agent-Requested** (rich
  `description`, no `globs`, `alwaysApply: false`): it fires when the user asks
  to "review my changes" and covers root-level files + the universal fallback to
  root `REVIEW.md`.
- **No per-edit reviewer hook.** `.cursor/hooks.json` keeps only the
  `afterFileEdit` formatter + `beforeShellExecution` safety guard (the lower
  rungs). The reviewer is dispatched on demand via the CLI above —
  deterministic-first; even a certified LLM judge (WI-8) should not gate every
  keystroke (cost + latency); it certifies the on-demand verdict, not a per-edit
  hook.

Parity is guard-tested in `tests/code_reviewer/test_cursor_mdc_parity.py`:
every known folder has a `.mdc`, its `globs` matches the subtree, its body
points at the folder's `REVIEW.md`, and it carries the canonical dispatch
command without restating rule prose.
