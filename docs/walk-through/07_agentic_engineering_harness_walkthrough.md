---
type: validation-walkthrough
title: 'Agentic-Engineering Harness — Step-by-Step Best-Practice Walkthrough (Tracks A/B/C)'
description: 'Goal: stand up, exercise, and verify the full agent harness — sensors/hooks (A), eval-validation discipline (B), and intent-debt gates + per-folder AGENTS.md (C) — as one end-to-end procedure.'
tags: [walk-through]
---

# Agentic-Engineering Harness — Step-by-Step Best-Practice Walkthrough

> **Companion to** the [harness adoption plan](../plan/agentic_engineering_harness_adoption.plan.md).
> Where the plan is the *spec*, this is the **executable procedure** that stands the harness up,
> exercises it, and proves each piece works. Every command below is copy-pasteable from the repo
> root; every artifact it names exists on disk as of 2026-06-27.

**Goal:** Adopt and verify the three-track agentic-engineering harness on this repo, end to end:
**Track A** (sensors & hooks — write-time lint + safety backstop + CI), **Track B** (eval-validation
discipline — TPR/TNR judge validation, `pass^k` multi-trial, paired-bootstrap significance,
capability→regression graduation), **Track C** (intent-debt gates + per-folder `AGENTS.md`).

**Governing equation:** **Agent = Model + Harness**, where Harness = **guides** (AGENTS.md, ADRs)
+ **sensors** (hooks, lint, evals, judges) + **gates** (human forced-engagement) + **loop
discipline** (context hygiene). The repo was *guide-rich and sensor-thin*; this procedure closes
the sensor and intent-debt gaps without ever blocking the agent mid-reasoning.

**Audience & format:** An engineer (optionally paired with Claude Code / Cursor) installing or
auditing the harness. Each track is **independent and reversible** — do them in any order. Each step
has a **Do**, a **Why**, and a **Verify**. Stop at any green checkpoint.

**Time budget:** ~90 min full pass (A ~25, B ~40, C ~25). Smoke path: the three "Verify" checkpoints
only (~15 min) if the artifacts are already committed.

**The cardinal rules of this harness** (each traces to a real failure — the *ratchet*):
1. **Quality sensors never block; only safety does.** `PostToolUse`/pre-commit = quality (advisory);
   `PreToolUse` = the only blocker, and only for irreversible/dangerous actions.
2. **No fabricated metrics.** An undecidable rate (empty denominator, no discriminative power)
   returns `None`, never a fake `0.0` (AP-6).
3. **Failure paths first.** For every gate, write the rejection test before the acceptance test.
4. **The judge must be validated before its verdicts are trusted.** κ measures drift; TPR/TNR is the
   governance gate.

**Companion docs:**
- Plan / spec: [`agentic_engineering_harness_adoption.plan.md`](../plan/agentic_engineering_harness_adoption.plan.md)
- Testing pyramid (L1–L4, TAP-1…4): [`tdd_agentic_systems_prompt.md`](../../research/tdd_agentic_systems_prompt.md)
- ADR bundle (intent debt): [`docs/adr/`](../adr/index.md) — incl. [ADR-0002](../adr/0002-ruff-baseline-g8-audit.md) (the G8 baseline audit)
- Per-folder guide mechanics: root [`AGENTS.md`](../../AGENTS.md) + nested `trust/AGENTS.md`, `services/AGENTS.md`, …

---

## Step 0 — Preflight (shared by all three tracks)

**Do:**
```bash
cd /path/to/AgentsFramework/agent
pip install -e ".[dev]"            # one-time; installs ruff, pytest, etc. into .venv
.venv/bin/python -c "import sys; print(sys.executable)"   # must be the repo .venv
```

**Why:** The repo's **only working interpreter is `.venv/bin/python`** — a bare `python` fails test
collection. Every hook, Makefile target, and script in this guide uses `.venv/bin/...` for that
reason. (pyright is *not* a Python dep; it runs via `npx --yes pyright`, so Node must be on PATH.)

**Verify:** `sys.executable` ends in `.venv/bin/python`. If not, fix PATH before continuing.

---

## Track A — Sensors & Hooks (defense in depth, never blocks reasoning)

**What you're building:** a fast write-time lint/format loop that feeds the agent, plus a
deterministic git/CI backstop. Two layers (Claude Code hooks **and** git/CI) so a bypass at one
layer is caught at the other.

### A1 — The write-time quality hook (`PostToolUse`)

**Do:** Confirm the hook is wired and points at the script:
```bash
grep -n '"hooks"' .claude/settings.local.json
ls scripts/hooks/post_edit_ruff.py
```
The `PostToolUse` matcher is the exact alternation `Edit|Write`; the script runs
`.venv/bin/ruff format` + `.venv/bin/ruff check --fix` on the edited path **only if it ends in
`.py`**, then exits **2 with residual lint on stderr** so the agent self-corrects.

**Why:** `PostToolUse` runs *after* the file is written, so it **cannot block** — which is exactly
what you want for quality. Exit-2-returns-stderr-to-the-agent gives the agent a tight "you left an
F-code, fix it" loop without ever interrupting mid-edit. Putting a quality gate in `PreToolUse`
(which *does* block) is the playbook anti-pattern: it stalls the agent's reasoning mid-write.

**Verify (the real test):** make a deliberate lint error through an editor tool and watch the hook
fix it:
```bash
printf 'import os\nx=1\n' > /tmp/hook_probe.py    # unused import + missing spaces
# Edit /tmp/hook_probe.py via your agent's Edit/Write tool (not shell), then:
cat /tmp/hook_probe.py   # 'import os' removed, 'x = 1' formatted; residual lint (if any) was surfaced
```
> **Gotcha — the import-then-use race.** If you add an import in one edit and its first *use* in a
> later edit, the hook's `--fix` will delete the "unused" import *between* the two edits (F401). When
> authoring code that imports-then-uses across edits, add the import **in the same edit** as a use, or
> re-add it after. This bit the review-fix work twice; it's a property of the loop, not a bug.

### A2 — The safety backstop (`PreToolUse`)

**Do:**
```bash
ls scripts/hooks/pre_bash_guard.py
```
The `PreToolUse` matcher is `Bash`; the script blocks (exit 2) a **tiny, documented** regex set:
`git push … origin main`, broad `rm -rf`, and reads/writes of `.env*`.

**Why:** `PreToolUse` is the **only** hook that can block (exit 2 → call denied, stderr = reason to
the agent). It is reserved for **irreversible/dangerous** actions only. It is **intentionally
separate** from the `d5d68d9` shell-approval HITL classifier — keep the guard's regex set tiny so the
two don't drift. Hooks run without a controlling terminal, so a hook can never *prompt* — it can only
allow or block.

**Verify:** attempt a blocked command through the agent's Bash tool:
```bash
# Ask the agent to run:  git push origin main
# Expect: the call is blocked and the agent sees the reason on stderr. Nothing is pushed.
```

### A3 — The git/CI backstop (`pre-commit` + GitHub Actions)

**Do:**
```bash
ls .pre-commit-config.yaml .github/workflows/pre-commit.yml
.venv/bin/python -m pre_commit run --all-files   # or: pre-commit run --all-files
```
`.pre-commit-config.yaml` pins `astral-sh/ruff-pre-commit` (`ruff-check --fix` + `ruff-format`) and
`gitleaks` (offline, staged-only — satisfies "no network/no live LLM in CI"). The CI workflow
re-runs `pre-commit run --all-files`.

**Why:** Local hooks are bypassable (`git commit --no-verify`), so **CI must re-run the same checks**
— the backstop's backstop. `gitleaks` staged-only keeps secrets out without calling anything external.

**Verify:** `pre-commit run --all-files` is green; pushing a branch triggers `pre-commit.yml` in CI.

### A4 — The canonical sensor triad (`make check`)

**Do:**
```bash
make check        # lint + format-check + typecheck + test  — the canonical pre-commit gate
```
Targets: `make lint` (`.venv/bin/ruff check .`), `make format` (`.venv/bin/ruff format .`),
`make typecheck` (`npx --yes pyright`), `make check` = `lint format-check typecheck test`.

**Why:** One memorable command means `AGENTS.md` can simply say "run `make check` after changes."
`check` is **read-only** (`format-check`, not `format`) so the gate never mutates your tree out from
under you.

**Verify (Track A done):** `make check` → **green** (expect ~4136 passed at time of writing).
Optionally confirm `.cursor/hooks.json` exists for Cursor parity — note Cursor hooks **fail open by
default**, so that file sets `"failClosed": true`.

> **Track A checkpoint:** write-time auto-fix works; `git push origin main` is blocked;
> `pre-commit run --all-files` and `make check` are both green.

---

## Track B — Eval-Validation Discipline

**What you're building:** the discipline that makes the existing judges *trustworthy* — validate
them (TPR/TNR, not just κ), measure A/B reliability honestly (`pass^k` + significance), and graduate
proven capability evals into a frozen regression suite. Bolts onto `meta/` and
`scripts/model_ab_eval.py`; adds nothing to the live path.

### B1 — Validate the judge: TPR/TNR + Rogan–Gladen

**Do:** Run judge validation against the binary goldset (mined from the GoalJudge v0.9 goldset):
```bash
.venv/bin/python -m meta.judge_validation --help     # --seed/--judge/--mapping/--clean/--tpr-min/--tnr-min
.venv/bin/python -m meta.judge_validation            # uses the pinned defaults; prints TPR/TNR/FPR/FNR + Rogan–Gladen
```
The module ([`meta/judge_validation.py`](../../meta/judge_validation.py)) **composes**, never
re-implements, the `services.governance.goaljudge_calibration` confusion math: `judge_rates()`,
`rogan_gladen()`, `validate_judge()`. Floors default to `DEFAULT_TPR_MIN = DEFAULT_TNR_MIN = 0.90`.

**Why:**
- **κ (Cohen's kappa, `meta/drift.py`)** is a fine *drift* signal but a single scalar that **hides
  directionality** — it can't separate recall on real failures (TPR) from the false-alarm rate on
  clean runs (TNR). For a **governance** judge the asymmetry is the whole point: a missed failure
  costs more than a false alarm. So κ stays as the drift signal; **TPR/TNR is the validation gate.**
- **Positive class = "judge says not-met" (failure detection)** — inherited from
  `goaljudge_calibration`; **do not flip it.** `TPR = tp/(tp+fn)`, `TNR = tn/(tn+fp)`,
  `FPR = fp/(fp+tn)` (= false-downgrade rate).
- **Rogan–Gladen** corrects observed prevalence back to the truth given the judge's error rates:
  `θ_true = (θ_obs − FPR)/(TPR − FPR)`. It is **undefined when `TPR == FPR`** (no discriminative
  power) — the CLI prints `— (undecidable)`, *never* a fabricated number, and reports the unclamped
  value so out-of-range estimates are visible.
- **Fail-closed:** an undecidable rate (empty denominator) **fails** the gate, it does not pass by
  omission.

**Verify:** the run prints `TPR`, `TNR`, `FPR`, `FNR`, the confusion counts, and the Rogan–Gladen
line; the exit code is non-zero when either rate is below its floor. (Worked example from the audit
artifact: `TP=34/FP=3/FN=2/TN=14` → `TPR=0.944` but `TNR=0.82` **fails** the 0.90 TNR floor — the
gate fires, correctly.)

### B2 — `pass^k`: multi-trial reliability, not single-run luck

**Do:**
```bash
# N>=8 recommended to read pass^8. Requires --answer-score and the GEN-L1 answer corpus.
.venv/bin/python scripts/model_ab_eval.py \
    --baseline-set <arm> --candidate-set <arm> \
    --answer-score --trials 8
```
Each arm is driven **N times into `trial_<i>/` with fresh graph state** (not the checkpointer — a
reused checkpointer would leak trial *i*'s context into *i+1* and collapse the variance `pass^k`
measures). The verdict diffs **`pass^k`**, not `pass^1`.

**Why:** Single-run A/B hides reliability — a 75%-per-trial arm over 3 trials is only ~42% all-pass
(`pass^3`). `pass_hat_k` uses the **unbiased Chen et al. estimator** `mean_task[ C(c,k)/C(n,k) ]`,
and is **`None` (undecidable)** when `k > trials` or the corpus is empty (AP-6).

**Verify:** the verdict line reads `pass^k over N trials` with per-arm `pass^k` and the delta; a
`model_ab_passk_report.json` is written.

### B3 — Statistical honesty: paired bootstrap + the NOISE band

**Do:** (same command as B2 — significance is computed automatically when `--trials > 1`.)

**Why:** At n=100, p=.5 the SE is ~5 pts and the 95% CI is ~±10 pts, so a **sub-4-point delta is
noise.** Because both arms run the **same frozen corpus**, the per-task deltas are *paired* — a
**paired bootstrap** (resample tasks, average per-task deltas; deterministic for a fixed seed) is far
more powerful than two independent CIs. The verdict rule lives in one pure, directly-tested function,
`decide_passk_verdict(...)`:
- integrity failure **or** provider/transport contamination **or** an undecidable `pass^k` →
  **`CONTAMINATED`** (instrumentation failure *dominates* — never scored as a behavior regression);
- candidate below baseline past tolerance → **`HOLD`**, **downgraded to `NOISE`** when the paired
  delta CI straddles 0;
- otherwise **`PROMOTE`**.

> **Two integrity guards that make the verdict honest** (both hardened after review):
> - **No silent empty trial:** a trial that produced *no* recordings is an explicit integrity
>   mismatch, not a pass masked by a good sibling (counts are summed, not `max`'d).
> - **Contamination is swept across *all* cases**, not just the L1-graded subset — a transport error
>   on an L2/L3 case contaminates the verdict too (`log_has_provider_error`).
> `--gate` exits non-zero on `HOLD`/`CONTAMINATED`; **`NOISE`/`PROMOTE` exit 0** (NOISE = not
> decision-grade, so it does not block a swap).

**Verify:** the verdict prints `paired bootstrap mean Δ`, the 95% CI, and `(includes 0: …)`; a
within-noise regression is reported as **`NOISE`**, not `HOLD`.

### B4 — Capability → regression graduation + the Langfuse feedback loop

**Do:** Use [`services/governance/eval_graduation.py`](../../services/governance/eval_graduation.py):
`classify_tier(row)`, `graduate(rows, pass_rates, …)`, `regression_floor_violations(rows, pass_rates, …)`,
`eval_record_to_goldset_row(record, …)`.

**Why:** **Capability** evals are *probing* — they may fail (that's their job). **Regression** evals
are *frozen* and run continuously at the floor (`DEFAULT_REGRESSION_FLOOR = 1.0`). A stable,
high-pass capability eval **graduates** into the regression suite once it clears
`DEFAULT_MIN_PASS_RATE = 0.95` over `DEFAULT_MIN_RUNS = 5`. Fail-safe defaults: an **untagged** row
or a **harvested** Langfuse row lands in **CAPABILITY** (a fresh real failure has not earned
regression status); a frozen regression eval that **did not run** is itself a violation (`runs == 0`).
Harvested rows preserve a real `trace_id` so they can join back to the source Langfuse trace.

**Verify:** `regression_floor_violations` flags any frozen eval below `1.0` (including no-run);
`eval_record_to_goldset_row(...)["tier"] == "capability"` for harvested rows.

> **Track B checkpoint:** `meta.judge_validation` prints TPR/TNR and fails below floor;
> `model_ab_eval.py --trials 8` reports `pass^k` + paired CI and downgrades a within-noise delta to
> NOISE; graduation/floor functions behave fail-safe.

---

## Track C — Intent-Debt Gates + Per-Folder AGENTS.md

**What you're building:** capture *why* behind structural changes (intent debt), add **only** the
human gates automation structurally cannot cover, and restructure the monorepo guide into lean,
lazily-loaded per-folder files.

### C1 — Per-folder `AGENTS.md` with `CLAUDE.md` bridges

**Do:**
```bash
ls AGENTS.md CLAUDE.md
ls trust/AGENTS.md services/AGENTS.md components/AGENTS.md orchestration/AGENTS.md \
   meta/AGENTS.md prompts/AGENTS.md frontend/AGENTS.md middleware/AGENTS.md
cat CLAUDE.md   # single line: @AGENTS.md
```

**Why (verified mechanics):** Claude Code reads **`CLAUDE.md`, not `AGENTS.md`** — hence the
one-line `@AGENTS.md` bridge in each folder (authoring stays tool-neutral in `AGENTS.md`). The
**root** loads in full at launch and **survives `/compact`**; **nested** files load **lazily** when
Claude reads that subtree (keeps root context lean) and do **not** auto-reinject after compaction.
Files **concatenate** (closer = read last = recency weight), they do not override — so nested files
add *local detail* and must never re-litigate a root rule.

> **The `@import` gotcha that bit this work:** nested `@import` paths resolve **relative to the
> importing file's directory, not the repo root.** A nested `frontend/AGENTS.md` must use
> `@../docs/...` — `@docs/...` would wrongly resolve to `frontend/docs/`. Verify every nested doc
> import is `@../...`.

**Verify:**
```bash
# In a Claude Code session opened inside trust/, run /memory and confirm trust/AGENTS.md is loaded.
grep -rn '@docs/' trust/AGENTS.md services/AGENTS.md frontend/AGENTS.md middleware/AGENTS.md  # expect NO matches
grep -rn '@../docs/' frontend/AGENTS.md middleware/AGENTS.md trust/AGENTS.md                  # expect the nested imports
```

### C2 — Lean root, invariants stay in root

**Do:** Confirm the root keeps the inter-layer essentials and is trimmed (~137 lines, from 227):
```bash
wc -l AGENTS.md
grep -n "Architecture Invariants" AGENTS.md
```

**Why:** The **8-rule Architecture Invariants table MUST stay in ROOT** — a nested file loads *too
late* to stop an upward import authored in a *new* file in that folder. `tests/architecture/` is the
**hard** enforcement; the prose is guidance. The root keeps: Project Overview, Key Commands, the
Invariants table + `tests/architecture/` pointer, the Boundaries (✅/⚠️/🚫), the Decision-records +
gates section, the Key Directories map, and References.

**Verify:** `make check` includes the architecture suite — `pytest tests/architecture/ -q` →
**green** (the invariants are still enforced regardless of where the prose lives).

### C3 — The ADR ratchet + 3 comprehension gates (G1/G4/G8)

**Do:** Read the root `AGENTS.md` §"Decision records (intent debt) + comprehension gates" and the
ADR bundle:
```bash
ls docs/adr/                       # 0000-template.md, index.md, log.md, ADR-0001, ADR-0002
sed -n '/Decision records/,/Key Directories/p' AGENTS.md
```

**Why:** On a governance-heavy repo most cognitive-forcing gates are redundant with `⚠️ Ask first` +
3-layer defense-in-depth + `tests/architecture/`, and gates have real UX cost (Buçinca). So adopt
**only three**, each tracing to a real failure class:
- **G1 new-abstraction** — automation can't judge whether an abstraction earns its place (intent
  debt). State what it buys and what you rejected → an ADR for anything load-bearing.
- **G4 complex-algorithm, scoped to `trust/`** — on the crypto/signing path, write down what the
  algorithm does and why the change is correct *before* pasting the implementation back. A green test
  you can't explain is not done.
- **G8 test-mass-rewrite** — a large `--fix`/test rewrite can silently weaken the suite (TAP-1/3/4);
  justify *why each weakened assertion is still sound* before trusting green.

**The ADR ratchet:** when a change matches an `⚠️ Ask first` trigger (new dependency, trust-kernel
type change, new graph node, new horizontal service, new abstraction, invariant deviation), append a
numbered ADR (copy `docs/adr/0000-template.md`: Context / Decision / Options-rejected / Rationale /
Consequences) and wire it into the OKF bundle (`index.md` entry + newest-first `log.md` line).

> **Honest enforcement limit:** Claude Code hooks **can** mechanically `ask`/`deny`/`block`
> (PreToolUse `permissionDecision`, or a `Stop` hook `decision: "block"`), but they **cannot capture
> a free-form typed human answer** (no controlling terminal). So the *generation-effect* core of a
> comprehension gate — *human writes the explanation before the agent reveals its account* — is
> **convention/PR-review, not tool-enforced.** Be honest about this split; don't pretend prose is a
> hard gate.

**Worked G8 example (this is what "doing the gate" looks like):** the Track-A ruff baseline rewrote
598 files (202 tests). [ADR-0002](../adr/0002-ruff-baseline-g8-audit.md) records the audit that
proves it was format-and-safe-fix only — normalized assert-diff + comparison spot-check + ruff's
safe-fix contract + suite parity — with the re-runnable commands. That ADR *is* the gate, discharged.

**Verify:**
```bash
.venv/bin/python scripts/okf_lint.py 2>&1 | tail -1   # docs/adr/ bundle: 0 failures
```

> **Track C checkpoint:** each folder has `AGENTS.md` + a `@AGENTS.md` `CLAUDE.md`; nested doc
> imports are `@../...`; root is lean with the Invariants table intact; the ADR bundle lints clean;
> the 3 gates + ratchet are documented in root `AGENTS.md`.

---

## Full-harness verification (the one command)

```bash
make check                                   # A: lint+format-check+typecheck+test — green
.venv/bin/python -m pytest tests/architecture/ -q   # C: layer boundaries enforced
.venv/bin/python scripts/okf_lint.py 2>&1 | tail -1 # C: ADR + walk-through bundles — 0 failures
.venv/bin/python -m meta.judge_validation           # B: TPR/TNR gate prints + exits on floor breach
```

If all four are green, the harness is stood up and honest: sensors give the agent fast feedback
without blocking it, the safety backstop is double-layered, the judge is validated, A/B verdicts are
significance-gated, and structural decisions leave an intent-debt trail.

---

## The ratchet (read before extending this harness)

Every line of every gate, hook, and AGENTS.md rule **traces to a real failure**. Do not add a rule,
a gate, or a hook speculatively — and **delete** aspirational lines that never caught anything. The
3-gate minimum, the tiny `PreToolUse` regex set, and the lean root are all deliberate. Expand only
when a concrete failure justifies the new friction.

## Companion / supersedes

- Recipe ↔ spec: this walkthrough executes the
  [harness adoption plan](../plan/agentic_engineering_harness_adoption.plan.md).
- Intent debt produced by Track C: [`docs/adr/`](../adr/index.md).
- Sibling validation walkthroughs (judge-specific): [01–06 in this bundle](index.md).
