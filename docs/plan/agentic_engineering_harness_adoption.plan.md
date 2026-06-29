# Agentic-Engineering Harness Adoption — Phased Plan

> **Status:** COMPLETE — all three tracks merged to `origin/main` (2026-06-28).
> Authored 2026-06-27.
> **Source research:** `docs/research/agenticengineeringplaybook/` (4 runbooks) + external
> web research on Claude Code hooks, Cursor, eval-validation discipline, comprehension/intent
> debt, and nested `AGENTS.md` mechanics. Full subagent research dumps preserved at
> `~/.claude/plans/docs-research-agenticengineeringplayboo-virtual-haven-agent-*.md`.
> **Companion:** step-by-step adoption guide at
> `docs/walk-through/07_agentic_engineering_harness_walkthrough.md`.

## Outcome (verified 2026-06-28)

All work items shipped and live-verified. Two residual items (neither a blocker):

| Track | Result |
|---|---|
| **A — Sensors & Hooks** | DONE. `scripts/hooks/{post_edit_ruff,pre_bash_guard,cursor_*}.py`, `.pre-commit-config.yaml`, `.github/workflows/pre-commit.yml`, `.cursor/hooks.json`, `make check` (lint+format-check+typecheck+test). PreToolUse guard confirmed live-blocking `git push origin main`. |
| **B — Eval Validation** | DONE (machinery). `meta/judge_validation.py` (TPR/TNR + Rogan–Gladen, floors 0.90), `model_ab_eval.py` (`pass_hat_k`, `paired_bootstrap_ci`, `decide_passk_verdict`), `services/governance/eval_graduation.py` (capability→regression + Langfuse bridge). **Residual ①:** GoalJudge fails its own gate — TNR 0.8235 < 0.90 (3 false positives on the 53-row human-adjudicated seed); the validator working as designed caught an untrustworthy judge. Fix the 3 FPs or justify an asymmetric-cost floor before trusting the judge. **Residual ②:** the Langfuse→goldset harvest is wired but not yet *run* on a schedule (cold feedback loop). |
| **C — Intent-Debt Gates** | DONE. `docs/adr/` OKF bundle (template + 0001 + 0002), G1/G4/G8 + ratchet in AGENTS.md, per-folder nested `AGENTS.md`+`CLAUDE.md` in 8 folders. Root AGENTS.md trimmed 227→132 (target was 90–110; stopped to preserve load-bearing inter-layer invariants). |

The three "Open items to confirm" below were resolved: pyright adopted (in `make check`);
Cursor parity built; Track C kept prose (the optional `Stop`-hook ADR trigger was *not* built,
per the honest-enforcement-limit note).

## Context — why this change

Four agentic-engineering runbooks were added to `docs/research/`. They collapse to one
equation: **Agent = Model + Harness**, where Harness = **guides** (AGENTS.md, specs) +
**sensors** (hooks, lint, evals, judges) + **gates** (human forced-engagement) +
**loop discipline** (context hygiene). A gap analysis of *this* repo shows it is
**guide-rich and sensor-thin**: the AGENTS.md, 4-layer architecture invariants, L1–L4 test
pyramid, defense-in-depth security, governance triangle, and `meta/` eval infra are strong;
but the *automatic* sensor layer (hooks, pre-commit, `make check`) and the *intent-debt*
layer (ADRs, comprehension gates) are missing, and existing judges are un-validated
(κ only, no TPR/TNR; single-run A/B, no significance).

This plan closes those gaps in **three independent, parallel tracks** (no cross-track
dependency — pick up in any order). Each track is self-contained and reversible.

**Locked decisions (from the brainstorm):**
- Sensors live at **both** layers (Claude Code hooks + git/CI) — defense in depth.
- Dangerous-Bash backstop = **thin independent PreToolUse hook** (NOT folded into the
  existing shell-approval HITL classifier from `d5d68d9`).
- Gates = **minimal**: `docs/adr/` + 3 prose gates (G1/G4/G8) + one mechanical trigger;
  no attempt to force typed human answers (hooks can't capture that — see Track C).
- AGENTS.md = **per-folder nested files** with `CLAUDE.md`→`@AGENTS.md` bridges, lean root.

---

## Track A — Sensors & Hooks (computational, defense-in-depth)

**Goal:** fast write-time lint/format feedback to the agent + a deterministic git/CI backstop,
without ever blocking the agent's reasoning mid-edit.

### Key mechanics (verified)
- **`PostToolUse` cannot block** (file already written) but **exit code 2 returns stderr to
  the agent** — perfect for "format the file, then surface residual lint" without blocking.
- **`PreToolUse` is the only blocker** (exit 2 → call blocked, stderr = reason to agent) —
  the right place for the safety backstop.
- Matcher: `"Edit|Write"` is exact alternation; any regex char flips to JS regex.
  Hook receives JSON on stdin (`tool_input.file_path`, `tool_input.command`).
- pre-commit ids renamed: `ruff-check` (was `ruff`) + `ruff-format`, rev pinned.
- `gitleaks` runs offline/staged-only → satisfies "no live LLM / no network in CI".

### Work items
1. **`.claude/settings.local.json` — add a `hooks` block** (currently permissions-only):
   - `PostToolUse` matcher `Edit|Write` → script that runs `.venv/bin/ruff format` +
     `.venv/bin/ruff check --fix` on the edited path **only if it's `*.py`**; exit 2 with
     residual lint on stderr so the agent self-corrects.
   - `PreToolUse` matcher `Bash` → **thin** script blocking `git push * origin main` /
     `git push origin main`, `rm -rf` on broad paths, and reads/writes of `.env*`.
     Independent of the HITL classifier; keep its regex set tiny and documented.
2. **Two hook scripts** under `scripts/hooks/` (use `.venv/bin/ruff` per repo interpreter
   convention — see Makefile header): `post_edit_ruff.py`, `pre_bash_guard.py`. Read stdin
   JSON, fast, clear errors, fail-safe.
3. **`.pre-commit-config.yaml`** (new): `astral-sh/ruff-pre-commit` (`ruff-check --fix` +
   `ruff-format`) + `gitleaks`. Pin revs. Exclude generated/`node_modules`/`.venv`.
4. **CI workflow** `.github/workflows/pre-commit.yml`: run `pre-commit run --all-files`
   (CI must re-run because `git commit --no-verify` bypasses local hooks).
5. **Makefile** — add canonical sensor triad so AGENTS.md can say "run `make check`":
   - `make lint` → `.venv/bin/ruff check .`
   - `make format` → `.venv/bin/ruff format .`
   - `make check` → lint + format-check + (optional) typecheck + `make test`
   - `make typecheck` → if a type checker is adopted (confirm ruff-only vs +mypy/pyright).
6. **(Optional) Cursor parity** `.cursor/hooks.json`: `afterFileEdit` formatter +
   `beforeShellExecution` guard. **Must set `"failClosed": true`** (Cursor hooks fail OPEN
   by default). Skip if Cursor isn't in active use.

### Critical files
- `.claude/settings.local.json` (edit), `scripts/hooks/*.py` (new),
  `.pre-commit-config.yaml` (new), `.github/workflows/pre-commit.yml` (new),
  `Makefile` (edit), optionally `.cursor/hooks.json` (new).

### Gotchas
- Never put a quality gate in `PreToolUse` (it would block writes mid-reasoning — the
  playbook anti-pattern). Quality = `PostToolUse`/pre-commit; `PreToolUse` = safety only.
- Hooks run without a controlling terminal — no interactive prompts inside a hook.
- Keep the thin Bash guard's regex set documented and minimal to avoid drift with the
  `d5d68d9` HITL classifier (the two are intentionally separate; note the overlap).

---

## Track B — Eval Validation Discipline (bolt onto existing `meta/`)

**Goal:** make the existing judges *trustworthy* — validate them, measure reliability
honestly, and stop reporting A/B deltas that are inside the noise band.

### Repo facts confirmed
- `meta/drift.py` computes Cohen's **κ** over 5-category ordinal ratings, gates at κ ≥ 0.75.
  **No TPR/TNR.** GoalJudge reports κ + FN counts.
- `scripts/model_ab_eval.py` is **single-run**, emits raw `delta` floats — **no trials,
  no significance test, no CI**. Has `_precision` but no recall/TNR.

### Why this matters
- κ is a fine **drift** signal (chance-corrected, "harder to fake" than accuracy) but a
  single scalar that **hides directionality** — it won't tell you the judge's recall on
  real failures (TPR) vs its false-alarm rate (TNR), which is exactly what a *governance*
  judge needs (a missed failure costs more than a false alarm). Raw agreement is a trap
  metric (a 90%-"pass" judge scores 90% accuracy at 10% prevalence and catches nothing).
- Single-run A/B hides reliability: 75% per-trial over 3 trials = ~42% all-pass (`pass^k`).
- At n=100, p=.5: SE≈5pts, 95% CI≈±10pts → a **sub-4-point delta is noise**.

### Work items
1. **TPR/TNR alongside κ.** Add a held-out **human-labeled** fixture (binary pass/fail +
   written critique — Critique Shadowing, ~30 for discovery / 100+ for validation) and a
   script computing TPR + TNR per judge. Keep κ as the drift signal; add TPR/TNR as the
   *validation* gate (target >90% each, set by asymmetric cost). Add **Rogan–Gladen**
   correction `θ_true = (θ_obs − FPR)/(TPR − FPR)` to recover true failure rate.
   - Bolt-on: extend `meta/drift.py` (or a sibling `meta/judge_validation.py`).
2. **`pass^k` multi-trial** in the A/B harness. Add `--trials N` to `scripts/model_ab_eval.py`;
   run the frozen corpus N× per arm with **fresh graph state** (not the checkpointer);
   compute `pass^k` (`E_task[C(c,k)/C(n,k)]`); diff **pass^k**, not pass^1, in PROMOTE/HOLD.
   Recommend n≥8 trials to read pass^8 (≥5 floor).
3. **Statistical honesty in `diff_summaries`.** Add SE + **paired bootstrap** CI on
   per-item deltas (same frozen corpus both arms → paired is far more powerful);
   downgrade HOLD→"NOISE" note when the delta CI includes 0.
4. **Capability→regression graduation.** Tag corpus rows `capability` vs `regression`;
   freeze stable high-pass capability evals into a continuously-run regression suite
   (~100% target). Wire a Langfuse-trace → golden-set feedback loop via `eval_capture`.

### Critical files
- `meta/drift.py` (edit), new `meta/judge_validation.py` + human-labeled fixture,
  `scripts/model_ab_eval.py` (edit), corpus fixtures (tag rows).
- Consider the `agentsframework-eval-probe` skill for the per-seam probe scaffolding.

---

## Track C — Comprehension / Intent-Debt Gates (minimal) + per-folder AGENTS.md

**Goal:** capture decision rationale (intent debt) and add *only* the human gates that
automation structurally cannot cover — without over-friction on a governance-automated repo.

### Honest enforcement limit
Claude Code hooks **can** mechanically `ask`/`deny`/`block` (PreToolUse `permissionDecision`,
or a `Stop` hook `decision: "block"`) — e.g. "no ADR appended for this architectural change →
don't end the turn." But hooks **cannot capture a free-form typed human answer** (no
controlling terminal as of v2.1.x). So the *generation-effect* core of a comprehension gate
("human produces an explanation before the agent reveals its account") is **convention/prose**,
not tool-enforced. The plan is honest about this split.

### Gate triage (governance-heavy repo → adopt only 3)
| Gate | Verdict | Reason |
|---|---|---|
| G2 dependency, G3 security, G5 large-diff, G6 unfamiliar-API, G7 architecture | **Drop** | Redundant with `⚠️ Ask first`, 3-layer defense-in-depth, `tests/architecture/`. |
| **G1 new-abstraction** | **Keep** (as ADR trigger) | Automation can't judge whether an abstraction earns its place — intent debt. |
| **G4 complex-algorithm** | **Keep, scoped to `trust/` only** | Crypto/signing path is where a passing-but-not-understood diff is dangerous. |
| **G8 test-mass-rewrite** | **Keep** | Maps to TAP-1/3/4 — silent test weakening that passing tests hide. |

### Work items
1. **`docs/adr/` (Nygard ADRs).** `NNNN-title.md` with Status / Context / Decision /
   Consequences / **Alternatives rejected** (the intent-debt payload). One decision per file
   (beats a single growing `DECISIONS.md` for grep/supersede). Triggers = existing
   `⚠️ Ask first` list: new horizontal service, new graph node, trust-kernel type change,
   new abstraction (G1), any deviation from an architecture invariant. Link each ADR from
   the code seam it governs.
2. **AGENTS.md directives** for the ratchet + 3 gates (prose):
   - "When a change matches an ADR trigger, append a numbered ADR to `docs/adr/` and link it."
   - G1/G4/G8 forced-engagement wording (answer-before-reveal), G4 scoped to `trust/`.
   - Ratchet rule: every instruction line traces to a real failure; delete aspirational lines.
3. **(Optional) mechanical trigger.** A `Stop` hook that checks: did this turn touch
   `trust/` types / add a new graph node / create a new abstraction, with no new file under
   `docs/adr/`? → `decision: block` with a `systemMessage` asking for the ADR. Pure
   stop-and-require; no typed-answer capture.

### Per-folder nested AGENTS.md (the AGENTS.md restructure)
**Verified mechanics:** Claude Code reads **`CLAUDE.md`, not `AGENTS.md`** (2026). Ancestor
files load **in full at launch**; **subdirectory files load on demand** when Claude reads a
file in that subtree (lazy → keeps root context lean). Files **concatenate** (root + nested
both present; closer = read last = recency weight) — NOT override. `@import` does **not** save
tokens (loads at launch); only genuinely *nested* files are lazy.

**Therefore:**
- Keep authoring in `AGENTS.md` (tool-neutral); add a one-line `CLAUDE.md` containing
  `@AGENTS.md` (or a committed symlink; prefer `@import` for Windows safety) in each folder.
- **Architecture Invariants table MUST stay in ROOT** (always loaded) — a nested file loads
  too late to prevent an upward import authored in a *new* file. `tests/architecture/`
  remains the hard enforcement layer; nested files are guidance only.

**Lean root `AGENTS.md` keeps:** Project Overview, Key Commands, the 8-rule Architecture
Invariants table + `tests/architecture/` pointer, Key Directories map, cross-cutting
Boundaries, References, and a pointer listing the per-folder files. Target ~90–110 lines
(from 227).

**Per-folder mapping (start with the 3 highest-distinct-rule folders, grow later):**
| Folder | Moves down from root |
|---|---|
| **`trust/`** | Trust Kernel Rules (4 criteria, key types, signed/unsigned), AP-1, L1 testing (zero-flake, pure TDD, `tests/trust/` import rule), TAP-1, TAP-4, **G4 gate**. |
| **`frontend/`+`middleware/`** | Entire Frontend Conventions block (F/W/P/A/T/X/C/B/U/S/O, adapter-only SDK imports, pure Zod kernels, trace_id flow, BFF-no-creds, CSP/nonce, FD1–FD7, FE-AP auto-rejects) + style-guide pointers. |
| **`services/`** | H1–H5, "Adding a horizontal service", AP-2, AP-3, Security Model (3-layer), L2 testing, eval-capture `user_id`/`task_id`. |
| `components/` | V1/V2/V6, "Adding a component", error classification, L3 testing, TAP-2, TAP-3. |
| `orchestration/` | AP-5 (thin wrappers ≤10–15 lines), L4 testing, config rule (`.j2`=intent / `routing_config.py`=numbers). |
| `meta/` | "must not import orchestration", AP-4, `@pytest.mark.simulation`, drift/judge conventions. |
| `prompts/` | Prompt naming, `includes/`, `codeReviewer/` v1 vs v2 rollout, restate H1/AP-3. |

### Critical files
- `docs/adr/` (new dir + `0001-record-architecture-decisions.md`), root `AGENTS.md` (trim),
  per-folder `AGENTS.md` + `CLAUDE.md` bridges, optionally `scripts/hooks/stop_adr_check.py`.

### Gotchas
- **Nested files don't load until Claude touches the subtree** → keep inter-folder rules in
  root; nested = additive local detail only, never re-litigate a root rule (concatenation can
  produce arbitrary conflict resolution).
- **Drift:** review AGENTS.md/CLAUDE.md edits in PRs like docs; root = single source of truth
  for inter-folder invariants.
- **Compaction:** root CLAUDE.md survives `/compact`; nested files do not auto-reinject.
- **Stale content to fix while refactoring root:** line ~99 still says "Vercel/Cloudflare
  Pages" for the BFF (BFF now on Cloud Run per 2026-06-18); `governanaceTriangle/` dir name is
  misspelled on disk too — decide whether to fix or leave.
- Cognitive-forcing gates have real UX cost and uneven payoff (Buçinca) — the 3-gate minimum
  is deliberate; don't expand without a real failure justifying it (ratchet).

---

## Verification (per track)

- **Track A:** Make a deliberate lint error in a `.py` file via Edit → confirm the
  `PostToolUse` hook auto-fixes and surfaces residual issues to the agent. Attempt
  `git push origin main` via Bash → confirm `PreToolUse` blocks with a clear reason.
  Run `pre-commit run --all-files` and `make check` → both green. Push a branch → CI
  `pre-commit.yml` runs.
- **Track B:** Run the new TPR/TNR script against the human-labeled fixture → both rates
  printed, gate fires below threshold. Run `model_ab_eval.py --trials 8` → pass^k + paired
  CI in the verdict; a sub-4-pt delta is reported as NOISE.
- **Track C:** Create a `trust/` type change with no ADR → (if mechanical trigger built)
  the `Stop` hook blocks asking for an ADR. Launch Claude in `trust/` → confirm
  `trust/AGENTS.md` (via `CLAUDE.md`) loads (`/memory`). Confirm root stays ~90–110 lines
  and architecture invariants still present at launch.

## Open items to confirm before executing
- Type checker: ruff-only, or add mypy/pyright to `make check` / pre-commit?
- Is Cursor in active use (build `.cursor/hooks.json` parity or skip)?
- Build the optional `Stop`-hook ADR trigger, or keep Track C fully prose?
