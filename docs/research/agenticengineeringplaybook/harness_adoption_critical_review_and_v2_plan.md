# Critical Review — Agentic-Engineering Harness Adoption + v2 Improvement Plan

> **Scope:** Critical review of `docs/plan/agentic_engineering_harness_adoption.plan.md`
> against the four playbooks in this folder, verified against the actual codebase,
> sharpened with 2026 external research, and a phased improvement plan.
>
> **Date:** 2026-06-28
> **Sources:** the four `compass_artifact_wf-*.md` playbooks in this directory + the
> 2026 external-research sources listed in §3.

---

## 1. What the plan actually delivered (verified)

I confirmed the artifacts exist and are well-built, not just present:

| Track | Claim | Verified reality |
|---|---|---|
| **A** | DONE | `scripts/hooks/{post_edit_ruff,pre_bash_guard,cursor_*}.py`, `.pre-commit-config.yaml` (ruff v0.15.16 + gitleaks v8.30.1 + hygiene hooks), `.github/workflows/pre-commit.yml`, `.cursor/hooks.json`, `make check` (lint + format-check + **pyright** + test). The `make check` target is real and read-only. |
| **B** | DONE (machinery) | `meta/judge_validation.py` is genuinely high quality: pure functions, AP-6 `None`-when-undecidable, Rogan–Gladen with unclamped reporting, fail-closed, single-source-of-truth mapping reuse from `measure_l2l3_goaljudge`. `model_ab_eval.py` has `pass_hat_k`, `paired_bootstrap_ci`, `decide_passk_verdict` (extracted as a pure function — directly tested). `eval_graduation.py` ships `graduate()` + `regression_floor_violations()` + the Langfuse bridge. |
| **C** | DONE | `docs/adr/` OKF bundle (template + 0001 + **0002**), G1/G4/G8 + ratchet in `AGENTS.md`, 10 per-folder nested `AGENTS.md`+`CLAUDE.md` bridges. **ADR-0002 is exemplary** — three independent lines of evidence (normalized assert-line diff + ruff safe-fix contract + suite parity), re-runnable audit commands, explicit `--unsafe-fixes` carve-out. |

The plan's intellectual honesty is a real strength — the "honest enforcement limit" note (hooks can't capture typed answers) and the two named residuals are rare and correct.

## 2. Gaps, weaknesses, issues

Grouped by severity. Each is tied to a playbook recommendation and/or a 2026 best-practice source.

### 🔴 Critical — the named residuals are real and one is a playbook-named failure mode

**C1. GoalJudge TNR = 0.8235 < 0.90 — UNRESOLVED, and the data says it is a rubric bug, not noise.**
The plan marks Track B "DONE (machinery)" with this residual. But `cache/goaljudge_eval/residual_fp_revalidation.json` shows the 3 false-positives are **consistent across 5 re-runs** (e.g. `70ff3369` / `GEN-L3-iterative-refine-15`: `met_count: 0/5`, all 5 rationales complain the answer doesn't say "zero-balance" verbatim even though it says "fully offset"). This is exactly the playbook's P14 case: **a false-positive on an inline guardrail is a production bug, not a tolerance to tune.** The 2026 calibration-loop guidance (aievals.co; GL SDK) is unambiguous: when TPR/TNR falls below 90%, iterate the **rubric**, not the model, and don't ship the judge. The validator working-as-designed caught an untrustworthy judge; the judge was then not fixed. This is the single highest-priority gap.

**C2. L2/L3 prose answers are still UNGRADED — `model_ab_l2l3_blind_adjudication.plan.md` is "PLAN (not started)."**
The A/B verdict is L1-deterministic only. The plan acknowledges this, but it means the model-swap gate that Track B exists to harden is blind on the harder stratum — precisely where regressions hide. The blind-adjudication plan exists and is well-framed (it correctly refuses to make the agent a steady-state judge) but has not been executed.

**C3. No `tier: regression` rows, no continuously-run regression gate, no scheduled pass^k.**
`eval_graduation.py` ships `graduate()` and `regression_floor_violations()`, but no corpus row is tagged `tier: regression` and nothing runs `--trials 8` on a cadence. `make model-ab` is explicitly "NEVER in CI." So Track B is machinery-without-practice: the reliability measurement the playbooks demand (pass^k, P10) and the regression graduation (P9) exist as code but not as a running loop. The plan's Residual ② is exactly this — and it is a bigger deal than "cold feedback loop" framing suggests, because the *whole point* of the eval harness is a continuously-run regression tier.

### 🟠 High — Track C kept the gate *names* but dropped the gate *mechanism* (the novel core)

**H1. G1/G4/G8 are prose triggers with no forced-engagement *wording*.**
The comprehension-debt playbook's novel core (Part C) is the **universal gate preamble**: "Answer in your own words BEFORE I show my explanation… name the load-bearing line… name the one assumption most likely to be wrong." The repo's `AGENTS.md` names G1/G4/G8 as triggers ("state in the PR/commit what it buys," "write down what the algorithm does") but does NOT encode the **answer-before-reveal, generative-not-recognitional** wording that the playbook's evidence base (Slamecka & Graf; Rozenblit & Keil; Buçinca et al.) shows is the actual mechanism. As written, "state what it buys in the PR" can be satisfied by a one-line summary the agent wrote — which is recognition, not generation. The gate is named but the cognitive-forcing prompt is missing.

**H2. No mechanical trigger — and 2026 made it feasible.**
The plan deferred the `Stop`-hook ADR trigger and was honest about why (hooks can't capture typed answers). But the 2026 hooks upgrade changed what's feasible: `Stop` and `SubagentStop` now accept `hookSpecificOutput.additionalContext` for **non-error feedback that continues the turn**, and the payload includes `background_tasks`/`session_crons`. So a `Stop` hook that detects "this turn touched `trust/models.py` or added a graph node or added a new abstraction, and no new file appeared under `docs/adr/`" → `{"decision": "block", "reason": "ADR required for this change; append one to docs/adr/ and re-run"}` is now a working pattern. The plan's "convention + PR-review, not tool-enforced" framing is no longer the honest limit for the *trigger* (only for the *typed answer capture*). This is the single biggest Track C uplift.

**H3. Dropped G2/G3/G5/G6/G7 entirely.**
The plan drops them as "redundant with ⚠️ Ask first / defense-in-depth / `tests/architecture/`." That's defensible for G2 (deps) and G6 (unfamiliar API), but **G3 (security boundary)** and **G7 (architecture)** are the highest-stakes comprehension gates in the playbook — they map to the lethal-trifecta and the architecture-invariants the repo cares most about. Dropping them to "redundant with ⚠️ Ask first" conflates *permission* with *comprehension*: Ask-first makes you *approve*; a gate makes you *explain*. The repo already has a `security-review` skill and a `governance-trace-audit` skill — wiring G3/G7 as forced-engagement prompts at the seam would close this.

### 🟠 High — Track A sensors miss two playbook-named sensors

**H4. No test-deletion/skip detector.**
Playbook Runbook #2 §6 and Runbook #4 D6 both name this explicitly: "run a sensor that flags test deletions/skips," "coverage-must-climb gate." The repo's G8 gate is prose; the ratchet move is a mechanical sensor. A pre-commit hook (or a `tests/architecture/` test) that diffs `git diff --stat` against `tests/**` and flags any deleted `def test_*` / added `pytest.skip` / `@pytest.mark.skip` / `xfail` flips would be the structural fix. This is the exact failure mode Kent Beck and Yegge watch agents commit (silent test deletion to go green).

**H5. `.cursor/hooks.json` `afterFileEdit` is `failClosed: false` — contradicts the plan's own stated requirement.**
The plan says: "**Must set `\"failClosed\": true\"`** (Cursor hooks fail OPEN by default)." The file has `beforeShellExecution: true` (correct) but `afterFileEdit: false`. A formatter failing open is arguably benign, but it contradicts the plan's stated contract and means a Cursor-side ruff failure silently disappears. Either fix the value or update the plan to record the deliberate exception.

**H6. No behaviour-harness sensor (mutation testing).**
Both playbooks (Runbook #2 §7, Runbook #4 D6) name mutation testing as the way to "test the tests" — and the METR finding (~half of test-passing SWE-bench PRs aren't mergeable) is the empirical case. The repo has expansive unit tests but no `mutmut`/`cosmic-ray`/`pytest-mut` run. The playbook calls this the "elephant in the room" — the behaviour harness is unsolved, and mutation testing is the partial fix.

### 🟡 Medium — judge validation is below the 2026 bar

**M1. No position-bias / test-retest / cross-model validation (2026 MVVP).**
The 2026 "Minimum Viable Validation Protocol" (arXiv 2606.19544) extends TPR/TNR with: (2) position-swap AB+BA, (3) test-retest over ≥3 runs at temp 0 with caching disabled, (4) cross-validate on ≥2 benchmarks, (5) audit the paradox (test-retest >0.95 *with* position bias >0.10 is a failure mode, not a strength). `judge_validation.py` does TPR/TNR/RG/κ only. The repo already has the 5-trial revalidation data (`residual_fp_revalidation.json`) that *could* feed a test-retest check — the data exists, the metric doesn't. Also: the judge is `claude-haiku-4-5` and the systems-under-test may also be Claude → self-enhancement bias risk the playbooks hand-waved ("usually fine for scoped binary tasks") but 2026 research is more cautious.

**M2. Validation seed is 53 rows — below the playbook's own 100-example minimum.**
The plan states "~30 for discovery / 100+ for validation" and shipped 53. At n=53, p=0.5, SE ≈ 0.069 → 95% CI ≈ ±13.5 points. The TNR=0.8235 vs floor 0.90 gap (−0.0765) is *inside* that CI on TNR alone. The gate fired correctly because it's a hard floor, but the *estimate* is underpowered. The playbook and 2026 guidance agree: ≥100 for validation.

**M3. Guardrails-vs-evaluators conflation (playbook P14).**
The GoalJudge is both an *evaluator* (drift, A/B cross-check) and an *inline guardrail* (the downgrade gate). The playbook says guardrails must be versioned, logged, conservative, and false-positives treated as production bugs. C1's 3 FPs are exactly false-positives on an inline guardrail — so per P14 they should be filed as bugs and the guardrail versioned/bumped, not left as a "residual."

### 🟡 Medium — context engineering & workflow discipline is thin

**M4. No context-engineering conventions for the dev harness itself.**
The playbooks dedicate large sections to this (Runbook #4 B1–B5; Runbook #2 §5): subagents-as-context-firewall for noisy exploration, `/clear` discipline, scratchpad/progress-file for long sessions, context priming template. The repo is a LangGraph agent *about* agents, with strong governance telemetry, but its **own** development harness has none of these encoded. There's no convention "use an `explore` subagent for repo grep; only the summary returns," no "scratchpad file before `/compact`," no `/clear` cadence. The per-folder nested `AGENTS.md` refactor (good) is undercut by the fact M5 below.

**M5. Nested `AGENTS.md` don't auto-reinject after `/compact` — noted, not mitigated.**
The plan's own Gotchas flag this. 2026 mitigation: a `PostCompact` hook (now a supported event) that re-injects the current subtree's `AGENTS.md`, or a `sessionStart`/`UserPromptSubmit` reminder. The plan noted the risk and stopped.

**M6. Root `AGENTS.md` is 126 lines — above the plan's 90–110 target and ~2.5× the ~50 Anthropic now suggests.**
The Architecture Invariants table is load-bearing and must stay (correct call). But the Boundaries / Decision-records / Key-Directories / Cross-cutting-References sections could trim further (e.g., the Key Directories table duplicates what nested files say; the References block is 6 `@`-imports that all load at launch).

### 🟡 Medium — missing playbook patterns the repo is well-positioned to adopt

**M7. No spec-anchored template with EARS acceptance criteria.**
Runbook #2 §4 names spec-anchored the "right default for durable code." 2026 made this mainstream (GitHub Spec Kit; EARS). The repo's `docs/plan/` is rich but ad hoc — no required template, no EARS-style testable acceptance criteria ("WHEN [condition] THE SYSTEM SHALL [behavior]"). The repo already has ADRs for the *why*; it's missing the spec for the *what*.

**M8. No janitor / garbage-collection agent (OpenAI's "third pillar").**
Runbook #4 E5 and Runbook #2 §3 name the scheduled janitor agent that scans for doc/AGENTS.md/architecture drift and opens small PRs. The repo just created 10 nested `AGENTS.md` + an OKF ADR bundle + style guides — all of which will drift. `tests/architecture/` catches *code* drift but not *instruction/doc* drift. The repo already has a `cursor-guide` subagent and GitHub Actions cron patterns; a weekly janitor is cheap.

**M9. No "fresh-thread self-review" wired as a gate (Runbook #2 §6; Runbook #4 G4).**
The repo has `meta/code_reviewer.py`, a `codeReviewer` prompt, a `review-bugbot` skill, and a `security-review` subagent. But the playbook's "open a NEW thread, review the diff as if someone else wrote it" is not a deterministic gate on every non-trivial PR. A `SubagentStop`-gated code-reviewer subagent (2026 pattern) would close this with the machinery that already exists.

**M10. No "demand evidence, not assertions" / red-green-TDD mandate in `AGENTS.md`.**
Runbook #4 D2/D3/D7 and Runbook #2 §6 are explicit: "First run the tests," "Use red/green TDD," "Paste the actual command output, not a summary." The repo's `AGENTS.md` says "make check after changes" but doesn't require observing-tests-fail-first or pasting real output. The repo's strong L1–L4 test culture is a *code* asset; the *agent-instruction* asset is missing these two cheap, high-leverage lines.

**M11. No lightweight DECISIONS.md alongside ADRs.**
The comprehension playbook's Part B directive says "append 2–4 lines to DECISIONS.md" for any non-obvious decision. The repo chose Nygard ADRs (one file per decision) — reasonable for big decisions, but **higher friction → fewer decisions captured**. The playbook's 2–4-line DECISIONS.md is specifically designed to lower the bar so small intent-debt gets captured too. ADRs-for-big + a lightweight `docs/adr/log.md`-style append-only DECISIONS.md for small would be more complete.

## 3. External research — 2026 best practices that sharpen the gaps

Key sources (all 2026):

1. **Claude Code hooks reference + Steering blog (Anthropic, 2026)** — `Stop`/`SubagentStop` now support `hookSpecificOutput.additionalContext` for non-error feedback that continues the turn; payload includes `background_tasks`/`session_crons`. Subagents run in isolated context and only the summary returns. → Makes H2 (mechanical ADR trigger) and M9 (gated review subagent) feasible.
2. **"Reliability without Validity" — Minimum Viable Validation Protocol (arXiv 2606.19544, 2026)** — chance-correct (κ), position-swap (AB+BA), test-retest ≥3 runs at temp 0 with caching disabled, cross-validate ≥2 benchmarks, audit the test-retest>0.95-with-bias>0.10 paradox. → Extends M1 beyond TPR/TNR.
3. **Calibrating your judge against humans (aievals.co, 2026) + GL SDK Calibrate-the-Evals** — iterate the *rubric* not the model; train/dev/test splits; the 100-example minimum; Priority 1–4 sampling (all FAILs, near-threshold, structurally novel, sample of clear PASSes); stopping criterion TPR≥0.9 AND TNR≥0.9. → Directly prescribes the fix for C1.
4. **Spec-Driven Development in 2026 + GitHub Spec Kit (v0.11.9, 2026-06-26)** — Spec→Plan→Tasks→Implement; EARS (Ubiquitous/Event-driven/State-driven/Unwanted/Optional) as the de facto testable-acceptance-criteria standard; spec-anchored as the recommended default. Spec Kit v0.11.9 ships a slash-command agent workflow (`/speckit.constitution` → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`, plus `/speckit.clarify`, `/speckit.analyze`, `/speckit.converge`) with versioned artifacts: `.specify/memory/constitution.md` (non-negotiable principles), per-feature `spec.md` / `plan.md` / `research.md` / `data-model.md` / `contracts/` / `tasks.md`. The `constitution` is the load-bearing idea — `/speckit.plan` checks the plan against it, so principles become mechanically enforced, not aspirational. → Prescribes M7 and the toolchain decision in Phase 6.1b.
5. **Garbage-Collection / Entropy-Reduction agents (aipatternbook; AgentPatterns.ai; OpenAI/Lopopolo, 2026)** — scheduled background sweeps, one-violation-per-PR, `tech-debt-tracker.md` as a living audit log, drift signals dashboard (trend over time, not just a snapshot). → Prescribes M8 and the dashboard in 6.2.1.
6. **Ratchet (arXiv 2605.22148, 2026)** — formalizes the ratchet loop with bounded active-cap + retirement threshold; non-divergence proposition. LLM-authored skills deliver +0.0 pp vs +16.2 pp for human-curated → the bottleneck is *lifecycle management*, not authoring. → Validates the repo's "ratchet rule" and suggests retiring stale AGENTS.md lines, not just adding.
7. **SubagentStop quality gates (Totalum; claudelab; shuji-bonji, 2026)** — `code-reviewer`/`security-auditor`/`test-coverage-gate` subagents with MUST-level delegation rules; `SubagentStop` grades output and sends it back with `decision: block` + `reason`. → Prescribes M9 and the enforcement half of H2.

---

# Improvement / Implementation Plan

A phased, reversible plan that closes the gaps above. Each item traces to a playbook recommendation + a 2026 source. Ordered by ROI. Recommended to land as `docs/plan/agentic_engineering_harness_adoption_v2.plan.md` (the repo convention).

## Phase 1 — Close the named residuals (week 1, ~1–2 days) 🔴

**1.1 Fix the GoalJudge rubric (C1).** The 3 FPs are a single rubric defect: the "explicit zero-balance verification" sub-criterion rejects answers that say "fully offset" instead. Action: edit the GoalJudge rubric (`meta/judge_prompt.j2` or the rubric config) to accept "fully offset / exactly offsets / balances the overrun" phrasings as meeting the verification criterion. Re-run `python -m meta.judge_validation` → target TNR ≥ 0.90. Per 2026 calibration guidance, **iterate the rubric, not the model, and don't ship the judge until both rates clear 0.90.** If a tighter fix is wanted, add the 3 cases as few-shot "this is a PASS" examples.

**1.2 File the 3 FPs as guardrail bugs and version the GoalJudge (M3).** Per playbook P14, an inline-guardrail false-positive is a production bug. Bump the GoalJudge manifest version and record the fix in an ADR (it's a trust-kernel-adjacent change → ADR trigger). Link from `services/governance/goaljudge_calibration.py`.

**1.3 Grow the validation seed to ≥100 rows (M2).** The 53-row seed is underpowered. Add the next ~50 rows from the blind-adjudication corpus (priorities: all FAILs, near-threshold 0.5s, structurally novel, ~10 clear PASSes — the GL SDK Priority 1–4 sampling). Re-validate.

**1.4 Run the L2/L3 blind adjudication (C2).** Execute `docs/plans/model_ab_l2l3_blind_adjudication.plan.md`. The plan is already written and correctly scoped (9 L2/L3 rows × arms; blind labels → seed gold set → Stage 5/6 calibration). This unblocks the L2/L3 verdict the A/B harness currently reports as "UNGRADED."

**Phase 1 done = the validator's verdict is decision-grade and the A/B gate covers L2/L3.**

## Phase 2 — Make Track C mechanically enforced (week 2) 🟠

**2.1 Build the `Stop`-hook ADR trigger (H2).** `scripts/hooks/stop_adr_check.py`: on `Stop`, inspect the turn's file changes (the hook payload now carries what was touched); if any match an ADR trigger (`trust/models.py`, new file in `orchestration/react_loop.py` adding a node, new horizontal service, new abstraction) AND no new file under `docs/adr/` was created → emit `{"decision": "block", "reason": "ADR required: this turn touched <seam>. Append docs/adr/NNNN-*.md and re-run."}`. This is the *trigger* enforcement the plan deferred; the *typed-answer* part stays prose (the honest limit). Wire in `.claude/settings.local.json` under `hooks.Stop`. Add an ADR for this hook (it's itself a new gate).

**2.2 Encode the forced-engagement *wording* (H1).** Add to `AGENTS.md` (and the relevant nested files) the universal gate preamble from the comprehension-debt playbook Part C, scoped to G1/G4/G8 + re-added **G3 (security)** and **G7 (architecture)**:

> Before committing a GATED change, answer in your own words BEFORE the agent reveals its account: (1) what does this change do and why; (2) name the load-bearing line/function — what breaks if it changes; (3) what is the one assumption most likely to be wrong. The agent asks, you answer, THEN the agent reveals and corrects.

This is the cognitive-forcing prompt the evidence base (Slamecka & Graf; Rozenblit & Keil; Buçinca) shows is the actual mechanism. Store the gate library in a new `docs/adr/GATES.md` so the wording can be rotated (Part F anti-habituation).

**2.3 Rotate gate wording (Part F).** Maintain 2–3 phrasings per gate in `GATES.md` and cycle them. Static prose → habituation → rubber-stamping is the named failure mode.

## Phase 3 — Add the missing sensors (week 2–3) 🟠

**3.1 Test-deletion/skip detector (H4).** `scripts/hooks/pre_commit_test_guard.py` (or a `tests/architecture/test_no_test_weakening.py`): diff `tests/**` — flag any deleted `def test_*`, added `pytest.skip`/`@pytest.mark.skip`/`@pytest.mark.xfail` flips, or coverage drop. Block the commit. This is the ratchet move for G8 — the structural fix the playbook names.

**3.2 Fix `.cursor/hooks.json` `afterFileEdit` → `failClosed: true` (H5).** Or record the deliberate exception in the plan and the file comment. One-line change.

**3.3 Mutation testing, scoped to `trust/` (H6).** Add `mutmut` (or `cosmic-ray`) to dev deps, scoped to `trust/` first (the G4 surface — a passing-but-not-understood test there is most dangerous). Run weekly via a Makefile target `make mutate-trust`. Don't gate CI initially — run it on a cadence and report the mutation score trend. This is the behaviour-harness partial fix the playbooks name as "the elephant in the room."

## Phase 4 — Judge validation to 2026 MVVP bar (week 3) 🟡

**4.1 Add test-retest + position-bias to `judge_validation.py` (M1).** `judge_test_rest(judge, items, runs=3)` — run the judge ≥3× at temp 0 with caching disabled, report agreement across runs. `judge_position_bias(judge, pairs, ab_and_ba=True)` — for any pairwise use, report `|P(A wins) − 0.5|`. The 5-trial data in `residual_fp_revalidation.json` can bootstrap the test-retest check. Add the "test-retest >0.95 with position bias >0.10 is a failure mode" audit. Re-baseline the GoalJudge.

**4.2 Consider a cross-family judge for Claude arms (M1).** When the system-under-test is a Claude model, run a second judge from a different family (e.g., GPT-4o-mini) on a sample and report agreement. 2026 research is more cautious than the playbook about same-family judging.

**4.3 Graduate the first regression tier (C3).** Tag the now-stable high-pass L1 cases as `tier: regression` in the corpus. Wire `regression_floor_violations()` into a CI job (or a pre-merge gate) so a drop below 1.0 on a frozen eval blocks the merge. This converts Track B from machinery to practice.

**4.4 Schedule pass^k.** A weekly GitHub Action (or a `make model-ab-passk` target run before any model swap) that runs `--trials 8 --answer-score` on the regression tier and writes the pass^k report to `cache/model_ab/`. Not in the hot CI path (real LLM calls), but on a cadence.

## Phase 5 — Context engineering & workflow discipline (week 3–4) 🟡

**5.1 Encode subagent-as-context-firewall (M4).** Add to root `AGENTS.md`: "For repo-wide exploration, large test-output triage, or multi-file independent edits, dispatch an `explore` subagent; only the summary returns to the root context." Define an `explore` subagent in `.claude/agents/` (read-only tools: Read, Grep, Glob) and a `reviewer` subagent (read-only, fresh context) per the 2026 production playbook.

**5.2 `PostCompact` re-injection (M5).** `scripts/hooks/postcompact_reinject.py`: on `PostCompact`, re-inject the current subtree's `AGENTS.md` (detect from the most recently read file) into `additionalContext`. Mitigates the "nested files don't auto-reinject" gotcha the plan flagged.

**5.3 Add the two cheap, high-leverage `AGENTS.md` lines (M10).** "Use red/green TDD for anything verifiable — write the test, watch it FAIL, then implement." "Demand evidence, not assertions — paste the actual command output." Both trace to playbook failures; both are zero-cost.

**5.4 Trim root `AGENTS.md` toward 90–110 (M6).** Move the Key Directories table's per-folder detail into the nested files (it's already duplicated there); keep only the inter-layer rows. Keep the Architecture Invariants table in root (load-bearing). Target 90–110; do not sacrifice invariants.

## Phase 6 — Spec-anchored + janitor (week 4+, ongoing) 🟡

**6.1 Adopt spec-anchored development with EARS (M7).** Two layered decisions — the methodology first, the toolchain second.

**6.1a — Repo-native spec template (the methodology, land first).** Add `docs/plan/_spec_template.md` (adapt Runbook #2 §4): Goal / Context / FRs in EARS ("WHEN… THE SYSTEM SHALL…") / Data model / Invariants & security boundaries / Edge cases / NFRs / Test plan / DoD. Mandate it (in `AGENTS.md`) for any non-trivial durable change, alongside the existing ADR requirement. The repo already has the ADR for *why*; this adds the spec for *what*. This is zero-dependency and works with the existing `docs/plan/` convention and review flow. Land this regardless of 6.1b.

**6.1b — GitHub Spec Kit CLI: scoped trial, then decide (the toolchain).** The 2026 Spec Kit (v0.11.9) is more than a template — it's a slash-command agent workflow (`/speckit.constitution` → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`, plus `/speckit.converge` for drift-back-to-spec) that produces versioned artifacts (`.specify/memory/constitution.md`, per-feature `spec.md` / `plan.md` / `research.md` / `data-model.md` / `contracts/` / `tasks.md`) and mechanically checks `/speckit.plan` output against the `constitution`. The load-bearing idea is the **constitution**: non-negotiable principles that the planner is checked against, so principles become enforced rather than aspirational.

This repo already has a strong, hand-curated equivalent of a constitution — the `AGENTS.md` Architecture Invariants + the `⚠️ Ask first` triggers + the `tests/architecture/` enforcement. So the decision is *not* "do we need a constitution" (we have one); it is "does the Spec Kit CLI earn its place over the repo-native template in 6.1a." Run a scoped trial to answer it:

- **Trial scope:** one medium non-trivial change (e.g., a new horizontal service or a `trust/` type change — both are ADR triggers and would exercise the constitution-check). Run it through Spec Kit end-to-end (`/speckit.constitution` seeded from the existing `AGENTS.md` invariants → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`), and run the same change through the 6.1a template. Compare on: spec quality, EARS coverage, constitution-violation catch rate, friction, and whether the generated `tasks.md` respects the repo's layering/import rules.
- **Seed the constitution from existing assets.** `.specify/memory/constitution.md` should be generated *from* `AGENTS.md`'s Architecture Invariants + Boundaries, not rewritten from scratch — otherwise the trial tests a weaker constitution than the repo already has. The constitution is a *projection* of the invariants into Spec Kit's format, not a new source of truth.
- **Decision rule.** Adopt Spec Kit CLI repo-wide only if the trial shows (i) the constitution-check catches at least one invariant violation the 6.1a template missed, AND (ii) friction is acceptable (no double-maintenance of `docs/plan/` + `specs/`). Otherwise keep 6.1a as the canonical template and record the trial as an ADR (it's a toolchain decision → ADR trigger) so the next evaluation isn't a blank slate. Either outcome, the constitution concept is retained: in 6.1a it lives in `AGENTS.md` + `tests/architecture/`; under Spec Kit it lives in `.specify/memory/constitution.md` + the `/speckit.plan` check.
- **Do NOT adopt `/speckit.taskstoissues` or auto-issue creation in the trial.** The repo's work tracking is plan-doc + ADR based; auto-creating GitHub issues is a process change that should follow, not be bundled with, the toolchain decision.
- **CI integration is gated behind adoption.** If adopted, add a `make spec-check` target that runs Spec Kit's constitution/spec/plan/tasks consistency check (`/speckit.analyze` equivalent) on PRs touching `specs/**`, mirroring how `make check` guards code. Do not add this before the adoption decision — it would cement the tool before the trial verdict.

**6.2 Janitor agent (M8).** A weekly GitHub Action (cron) running a `cursor-guide`/general-purpose subagent that scans for: (a) `AGENTS.md` lines not traceable to a real failure (Hashimoto ratchet rule — the *deletion* direction); (b) stale `docs/plan/` items marked "PLAN (not started)" past N days; (c) `governanaceTriangle/` misspelling drift; (d) ADR seams in code with no `# ADR-NNNN` comment. Opens one small PR per category. Encode golden principles as a `tech-debt-tracker.md` the agent reads and updates — this file is the **source of truth**, kept reviewable in the normal PR flow.

**6.2.1 Drift-signals dashboard (closes the "deliberately weaker than the research" gap).** The 2026 research names a "drift signals dashboard" as a characteristic of the pattern; the v1 of this plan downgraded it to the tracker file alone. Add a thin rendered view *over* `tech-debt-tracker.md` so the operator gets the entropy-reduction dashboard the research prescribes, without making the tracker file subordinate to it:

- **Source of truth stays markdown.** `docs/adr/tech-debt-tracker.md` remains the append-only, PR-reviewed ledger — every janitor run appends to it and every fix strikes a line. The dashboard is a *view*, not a second store; it must never be hand-edited.
- **Dashboard = a generated Markdown page.** A small script (`scripts/janitor/render_drift_dashboard.py`, run by the same weekly Action after the sweep) reads `tech-debt-tracker.md` and emits `docs/adr/drift-dashboard.md` with: open-vs-resolved counts per category (a–d), age of the oldest open item per category, a trend sparkline of open-item count over the last N runs, and the "red categories" (any category whose open count is rising run-over-run). Commit the dashboard page in the same janitor PR as the tracker updates so review stays unified.
- **Trend, not just snapshot.** The dashboard's value over the raw tracker is *trend* — the operator can see whether entropy is being reduced or accumulating, which is the actual signal the research cares about (entropy-reduction is a *direction*, not a *state*). Keep at least the last 12 weekly snapshots in git history so the trend is reconstructable.
- **Optional Canvas view (deferred).** If the operator wants a live visual, the same script can emit a `.canvas.tsx` rendering the dashboard. Do NOT build this in Phase 6 — the markdown dashboard is the reversible baseline; the Canvas view is a later enhancement gated on the operator actually using the markdown dashboard for ≥4 weeks (avoid building a UI no one reads).
- **Retirement threshold.** The dashboard doubles as the retirement signal for the Ratchet research (§3 #6): if a category's open count stays at 0 for ≥8 consecutive runs, retire the corresponding `AGENTS.md` rule or check that produced it — the entropy source is gone. This closes the ratchet loop in both directions (add on failure, retire on sustained cleanliness).

**6.3 Lightweight DECISIONS.md (M11).** `docs/adr/decisions.md` — append-only, 2–4 lines per small decision (decision / rejected alternative / reason). ADRs for big structural decisions; this for the long tail. Lower friction → more intent-debt captured.

## Verification per phase

- **P1:** `python -m meta.judge_validation` prints `VALIDATION: PASS` with TPR ≥ 0.90 AND TNR ≥ 0.90 on a ≥100-row seed; L2/L3 blind adjudication complete and labels ingested into Stage 5.
- **P2:** A `trust/models.py` edit with no ADR → `Stop` hook blocks with the ADR-required reason; `GATES.md` exists with rotated wordings; G3/G7 re-added.
- **P3:** A commit that deletes `def test_*` → pre-commit blocks; `make mutate-trust` reports a mutation score; `.cursor/hooks.json` afterFileEdit is `failClosed: true`.
- **P4:** `judge_validation.py` reports test-retest + position bias; ≥1 corpus row tagged `tier: regression`; a scheduled pass^k run exists.
- **P5:** `explore`/`reviewer` subagents defined in `.claude/agents/`; `PostCompact` hook re-injects nested `AGENTS.md`; root `AGENTS.md` ≤ 110 lines.
- **P6:** `_spec_template.md` exists and is referenced from `AGENTS.md`; the Spec Kit scoped trial (6.1b) is complete and its outcome recorded as an ADR (adopted: `make spec-check` runs on `specs/**` PRs, OR not adopted: ADR records why and 6.1a remains canonical); janitor action has run at least once and opened a PR; `drift-dashboard.md` is generated from `tech-debt-tracker.md` and committed in the same PR, with ≥1 trend snapshot; `decisions.md` has ≥1 entry.

## What I deliberately did NOT recommend (and why)

- **Multi-agent fleets / orchestration tooling** — both playbooks scope this out for a solo operator; the repo is single-operator-plus-agent; no failure justifies it yet (ratchet rule).
- **Spec-as-source (code-as-generated-artifact)** — the playbook reserves this for disposable/regulated work; the repo is durable and human-curated. Spec-anchored is the right rung. (Distinct from the Spec Kit CLI decision in 6.1b, which is spec-anchored and in-scope for a trial.)
- **A typed-answer-capturing gate** — the plan's honest limit stands; hooks still can't capture free-form human text. Phase 2 enforces the *trigger*, not the *answer*.
- **Lowering the TNR floor to "justify an asymmetric-cost floor"** — the plan offered this as an escape hatch for C1. The 2026 guidance and the residual data (consistent 0/5 wrong verdicts) say the judge is *wrong*, not *asymmetric*. Fix the rubric; don't move the goalpost.

---

## Bottom line

The plan is a strong, honest implementation of ~70% of the playbooks. The gaps cluster in three places:

1. **The named residuals are real** and one (GoalJudge TNR) is a playbook-named failure mode that the data says is a rubric bug — fix it, don't tolerate it.
2. **Track C kept the gate *names* but dropped the gate *mechanism*** (forced-engagement wording) and the mechanical trigger — and 2026 hooks now make the trigger feasible.
3. **Track B is machinery-without-practice** — the regression tier isn't graduated, pass^k isn't scheduled, L2/L3 is ungraded.

The improvement plan above is ordered to close those first.

---

## Appendix — Playbook sources (this directory)

- `compass_artifact_wf-2235866b-3ca3-4629-a5e3-b0efe7fd81ff_text_markdown.md` — Runbook #4, Agentic Engineering Patterns (Solo Operator Edition)
- `compass_artifact_wf-223f46fe-239a-459a-b642-2834f5f34368_text_markdown.md` — The Agentic Engineering Runbook (Solo Practitioner Edition)
- `compass_artifact_wf-23923f35-f1ad-4a0f-aa3e-27239a1bb9e5_text_markdown.md` — The Comprehension-Debt Runbook (G1–G8 gates)
- `compass_artifact_wf-2801c381-df1d-4819-a3d4-372a0e685dd2_text_markdown.md` — The Evals Handbook for Solo Agentic Engineering
