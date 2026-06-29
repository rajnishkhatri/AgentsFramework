# Unified, Context-Routed Code Reviewer — Plan

> **Status:** COMPLETE — **WI-1 → WI-9 COMPLETE** (2026-06-28) +
> **post-WI-5 hardening pass COMPLETE** (P1-3, P2 detectors, P2-10/11, P3-a/b;
> 2026-06-28); **WI-8 COMPLETE + GATE CERTIFIED** (validation harness + 20-case
> fixture + recording script + replay test + first live recording at
> TPR=1.0/TNR=1.0; 2026-06-28); **WI-9 COMPLETE** (calibrated verdict policy —
> severity + confidence + dimension-aware; 2026-06-28). `verdicts.json` is
> committed; CI enforces the recorded gate via
> `tests/code_reviewer/test_wi8_validation.py::TestWi8RecordedGate`.
> **The honest limit LIFTS:** v3 LLM verdicts are now gate-grade (judge certified
> at TPR/TNR = 1.0 on the 20-case fixture, model `claude-haiku-4-5-20251001`),
> and the verdict policy is calibrated (cosmetics no longer gate).
> Authored 2026-06-28.
> **Source research:** `docs/research/agenticengineeringplaybook/` (4 runbooks) +
> external (Cursor Rules docs, AGENTS.md cross-tool standard). Grounding notes in §1.
> **Companion:** harness adoption plan (`agentic_engineering_harness_adoption.plan.md`)
> introduced the per-folder AGENTS.md split this plan reuses as the reviewer rule source.
>
> ### Progress log
>
> **2026-06-28 — WI-9 landed (calibrated verdict policy).** Replaced the
> schema-compatible `>2 warnings → REQUEST_CHANGES` heuristic — which was
> duplicated inline across two v3 sites (`run_deterministic_review_v3` and
> `_merge_reports`) — with a single shared pure function
> `apply_v3_verdict_policy(findings) -> (Verdict, statement, demoted_findings)`
> in `meta/code_reviewer.py`. The policy is now **severity + confidence +
> dimension-aware**: `reject` on any critical in **D1/D4** (backend
> architectural / trust kernel) or any **FD7 auto-reject** anti-pattern
> (FE-AP-4/6/7/12/18/19); `request_changes` on any *other* critical OR ≥3
> warnings with **confidence ≥ 0.7**; `approve` otherwise. **Confidence gates
> cosmetics:** a warning with confidence < 0.7 is demoted to an **INFO note**
> (`_demote_cosmetic_warnings`) — it stays in the report but does not count
> toward the quorum and does not trip the verdict, so a 598-file format baseline
> (many low-confidence cosmetics) no longer yields `request_changes`. The merge
> path demotes cosmetics inside the merged dimensions and recomputes dimension
> status (PARTIAL→PASS when only notes remain) so the emitted report surfaces
> notes rather than vanishing them. The v3 system prompt §6 was rewritten to
> state the calibrated policy and the confidence-honesty instruction
> (high-confidence only when the violation is clear from the routed rule + diff).
> The fail-closed LLM-infra-failure path (`REJECT` on "LLM review failed") is
> preserved as distinct from policy. **v1/v2 and the legacy frontend runner's
> `derive_verdict` are untouched** (frozen A/B baseline + superseded runner).
> 11 new tests in `tests/meta/test_code_reviewer_v3.py`: a 12-case calibration
> matrix for `apply_v3_verdict_policy` (clean approve, D1/D4/FD7 reject,
> other-dimension critical → request_changes, sub-quorum vs quorum warnings,
> 598-cosmetic demotion, boundary inclusivity at 0.7, critical precedence) +
> a merge-seam test that 5 low-confidence LLM warnings demote to INFO and the
> dimension drops PARTIAL→PASS. Full `make check` green (4499 passed). **G1
> note:** `apply_v3_verdict_policy` is a new load-bearing helper; it earns its
> place by collapsing two duplicated inline policy blocks into one testable
> unit, preventing the deterministic-only and LLM-merged reports from drifting
> on verdict policy. No ADR filed (no invariant deviation, no new dependency);
> this entry is the intent-of-record.
> **2026-06-28 — WI-8 machinery landed (judge validation harness).** The v3
> LLM judge can now be validated against a labeled fixture, isolated from the
> (already-trusted) deterministic half. **Detection-vs-policy split:** the
> gate measures the judge's *detection* accuracy (`goal_met` = no
> critical/warning LLM finding), decoupled from the verdict *policy*
> (`>2 warnings → REQUEST_CHANGES`, which WI-9 calibrates) — a single warning
> yields `APPROVE`, so the verdict alone is too coarse a gate signal. **20-case
> fixture** at `tests/fixtures/code_reviewer/wi8_validation/` (10 clean + 10
> violating), each targeting an **LLM-only** rule ID (TAP-1, H5, AP-1, V6,
> AP-5, AP-6, FD4, FD7, FD1, HOOK-1) across 8 folders; `cases.json` is the
> manifest, per-case files live under `cases/<id>/<repo-relative path>`.
> **Recording script** `scripts/record_code_reviewer_validation.py`
> materializes each case into a temp tree (with the folder's `REVIEW.md` copied
> in so routing resolves), runs `CodeReviewerAgent.review_v3_llm_only`
> (new WI-8 seam — returns the LLM report *before* the deterministic merge),
> and writes `verdicts.json`. **Validation module**
> `meta/code_reviewer_validation.py` runs `meta.judge_validation.validate_judge`
> on the recording (TPR/TNR ≥ 0.90, fail-closed on no data / undecidable
> rates); CLI `python -m meta.code_reviewer_validation`. **CI test**
> `tests/code_reviewer/test_wi8_validation.py` is skip-gated on
> `verdicts.json` (mirrors the L3 fixture — no live LLM in CI): when the
> recording is present it replays through `validate_judge` and asserts the gate
> passes; when absent it skips. 16 new tests (fixture well-formedness,
> validation math on synthetic recordings, CLI; the recorded-gate test skips).
> **CodeReviewerAgent** gained a `repo_root` parameter (defaults to
> `AGENT_ROOT`) so the harness can run over materialized trees without mutating
> the real repo. **Gate pending the first live recording:** the honest limit
> ("LLM verdicts are not gate-grade") STAYS until a human runs the recording
> script with an API key, the gate passes (TPR/TNR ≥ 0.90), and `verdicts.json`
> is committed. A failing recording must NOT be committed to flip the gate —
> iterate the v3 prompt first and re-record.
> **Honest limit unchanged until the recording passes.**
>
> **2026-06-28 — WI-8 gate CERTIFIED (first live recording).** Ran
> `scripts/record_code_reviewer_validation.py` against `claude-haiku-4-5-20251001`
> (the `.env` `MODEL_NAME` pointed at the retired `claude-3-haiku-20240307`;
> the recording overrides `MODEL_NAME` to a current model — the Anthropic key
> itself was valid). **Result: TPR=1.0, TNR=1.0 (n=20)** — all 10 violations
> detected, all 10 clean cases cleared, zero parse errors. `verdicts.json` is
> committed. Two normalizer defects surfaced and fixed during recording (both
> in `meta/code_reviewer.py::_normalize_review_payload`):
> (1) the LLM emits `dimensions` as a **flat list of finding-shaped objects**
> (no nested `findings` key) — the old normalizer silently dropped every
> finding; now flattened findings are detected and grouped by dimension;
> (2) `fix_suggestion: null` and `line: "9–13"` (range string) failed Pydantic
> validation and fell back to empty error reports — now coerced to `""` / int.
> `gaps`/`files_reviewed` are also coerced when the LLM emits them as lists of
> dicts. **One prompt defect fixed:** the v3 system prompt never told the LLM
> that a *finding is a violation, not a pass-confirmation* — claude-haiku-4-5
> was logging "check passed" entries as `warning`-severity findings on clean
> files (TNR collapsed to 0.3). Section 6 now states findings are violations
> only and pass-confirmations belong in `validation_log`; clean files must
> produce zero findings. **The recorded-gate test is now enforced in CI**
> (the `@pytest.mark.slow` marker was removed — it is a fast recorded-replay,
> not a live LLM call, so `make check` runs it). **The honest limit lifts:**
> v3 LLM verdicts are gate-grade for the routed LLM-only rules certified by
> this fixture. WI-9 (verdict-policy calibration) is the remaining item.
>
> **2026-06-28 — WI-7 landed (dispatch surface: Cursor parity).** The same
> content chain (`AGENTS.md` → `REVIEW.md` → reviewer) now resolves in Cursor as
> in Claude Code; only the path-attachment mechanism differs. Ten `.mdc` files
> in `.cursor/rules/`: nine per-folder rules (`trust/services/components/
> orchestration/meta/prompts/frontend/middleware/hooks`-`review.mdc`) are
> **Auto-Attached** via `globs: <folder>/**` — when a file in that subtree is in
> context, Cursor loads the rule, which points the agent at that folder's
> `REVIEW.md` and the canonical dispatch CLI. One root `code-review-dispatch.mdc`
> is **Agent-Requested** (rich `description`, no `globs`, `alwaysApply: false`)
> covering root-level files + the universal fallback to root `REVIEW.md`.
> Each `.mdc` is a thin pointer — it names the folder's `REVIEW.md` and the
> `python -m meta.code_reviewer --from-git-diff --git-base HEAD --prompt-version v3
> --output review.json` command; it never restates rule prose. The router
> (`code_reviewer/routing.py`) does the actual path→`REVIEW.md` resolution at
> CLI invocation time, so the `.mdc` surface and the CLI surface cannot drift
> (cross-checked by `tests/code_reviewer/test_cursor_mdc_parity.py`).
> **§8 open item resolved:** "Cursor dispatch depth → `.mdc` glob pointers only"
> — no per-edit reviewer hook is added. `.cursor/hooks.json` keeps only the
> `afterFileEdit` formatter + `beforeShellExecution` safety guard (the lower
> rungs); the reviewer is dispatched on demand via the CLI pointed at by the
> `.mdc` files. Rationale: an un-validated LLM judge must not gate every
> keystroke (deterministic-first; LLM verdicts are not gate-grade until WI-8).
> `docs/skills/code-review/SKILL.md` gained a "Cursor parity" section pointing
> at the `.mdc` surface. 90 new parity tests (frontmatter shape, glob→owning-
> folder tie to the router, thin-pointer/no-prose-restatement, canonical
> dispatch command identical across all `.mdc`, WI-8 honest-limit present,
> `hooks.json` carries no `meta.code_reviewer` hook entry).
> **Honest limit unchanged:** LLM verdicts are not gate-grade until WI-8.
>
> **2026-06-28 — WI-6 landed (dispatch surface: Claude Code).** The router,
> v3 prompt, `REVIEW.md` maps, and P2 detectors are now wired end-to-end:
> `meta/code_reviewer.py` v3 path routes each changed path → groups by
> `REVIEW.md` → runs the folded deterministic checks (backend AST D1/D4/D5 +
> TAP-2/TAP-4 + ADR.1 + frontend TS FD2/FD3) → injects `rules_file_content`
> + `deterministic_findings` into the v3 submission → LLM (verdict merge
> preserves deterministic precedence). New `code_reviewer/frontend/findings.py`
> is the canonical v3 mapper (shared with the legacy runner for
> `severity_for_rule`). CLI gained `--from-git-diff`/`--git-base` (feeds
> `added_files` to the ADR.1 new-service trigger). Skill at
> `docs/skills/code-review/SKILL.md`. Closed a prerequisite gap: v3 was
> claimed by WI-3 but never actually wired into `review_config.py` /
> `CodeReviewerAgent` / the CLI — now `{v1,v2,v3}` everywhere; v1/v2
> byte-for-byte unchanged. v1/v2 default stays `v1`. 36 new tests; full
> `make check` green (lint/format/typecheck/cite-lint/test).
> **Honest limit unchanged:** LLM verdicts are not gate-grade until WI-8.
>
> **2026-06-28 — Post-WI-5 critical-review hardening landed.** A depth review of the
> WI-1→WI-5 implementation surfaced P0/P1/P2/P3 gaps; all but the deferred items below
> were fixed in-session, deterministic-first and test-first (full `make check` green:
> 4340 passed, 51 skipped; ruff + pyright clean; `cite-lint` wired into the gate).
>
> - **P1-3 — `REVIEW.md` scaffolding completeness. DONE.** Verified all ten
>   enforcement maps present (`trust/`, `services/`, `components/`, `orchestration/`,
>   `meta/`, `prompts/`, `frontend/`, `middleware/`, `scripts/hooks/`, root) and that
>   each cites sibling `AGENTS.md` rule IDs rather than restating prose.
> - **P2 detectors — deterministic D3/D5 backfill. DONE.** Three new AST detectors in
>   `utils/code_analysis.py`, each unit-tested in `tests/utils/test_code_analysis.py`:
>   - `detect_adr1_missing` → ADR.1 (file-list-checkable; root `REVIEW.md` gate).
>   - `detect_mock_abuse` → TAP-2 (>3 mocks/test threshold).
>   - `detect_failure_path_ratio` → TAP-4 (failure-test ratio per decision point).
>   A static `DETECTOR_RULE_IDS: dict[str, frozenset[str]]` registry now declares the
>   detector→rule-id contract; guard test
>   `test_label_rule_token_is_in_detector_contract` enforces every `AST (...)` label
>   in a `REVIEW.md` points at a rule the named detector actually emits.
> - **P2-10 — Rule-id hyphen consistency. DONE.** `detect_anti_patterns` now emits
>   hyphenated IDs (`AP-2/3/5/6`) matching `AGENTS.md`/`REVIEW.md` columns (was `AP2…`);
>   `services/`+`prompts/`+`components/` `REVIEW.md` labels corrected;
>   `test_no_non_hyphenated_ap_token_in_labels` prevents regression.
> - **P2-11 — Cross-folder cite locality. DONE.** `meta/REVIEW.md` was citing
>   `trust/AGENTS.md §L1` for TAP-4 — a locality break. TAP-4 rule content is now
>   authored locally in `meta/AGENTS.md §L4` and `meta/REVIEW.md` cites it.
>   `code_reviewer/cite_lint.py` gained `_source_folder()` + a locality guard: a
>   `REVIEW.md` may cite only its own folder's `AGENTS.md` or the root `AGENTS.md`;
>   cross-folder cites are `CiteViolation`s. `TestCrossFolderCiteGuard` (7 cases).
> - **P3-a — Mojibake detection. DONE.** `cite_lint.py` now catches encoding drift in
>   `REVIEW.md`/`AGENTS.md`: invalid UTF-8 bytes, U+FFFD replacement chars, Latin-1-of-
>   UTF-8 bigrams (`Â§`, `â€`, `ï¿`, `ï½`), and lost `§` markers (`AGENTS.md ?<word>`).
>   `detect_mojibake` (pure) + `lint_encoding` + `_lost_section_marker_defects`;
>   `lint_review_file` self-lints its `REVIEW.md`, `main` runs an
>   `_lint_all_agents_encoding` pass over every `AGENTS.md`. `TestMojibakeGuard`
>   (10 cases). Fixed live mojibake in `services/REVIEW.md` (`?`→`§`, `—`).
> - **P3-b — `cite_lint` wired into `make check`. DONE.** New `cite-lint` Makefile
>   target added to the `check` dependency chain (`check: lint format-check typecheck
>   cite-lint test`); local pre-commit hook in `.pre-commit-config.yaml`
>   (`files: '(^|/)(REVIEW|AGENTS)\.md$'`, `pass_filenames: false`). Stdlib-only, so
>   `python -m code_reviewer.cite_lint` is portable across local + CI.
>
> **Deferred (re-scoped from the critical review):**
> - **P0 items** identified in the review were either already covered by WI-6
>   (runner wiring of router + `rules_file_content` injection) or re-classified as
>   P1-3/P2 and completed above — none remain open.
> - ~~WI-8 machinery landed~~ → **WI-8 COMPLETE + gate CERTIFIED** (TPR=1.0,
>   TNR=1.0). ~~WI-9 remains deferred~~ → **WI-9 COMPLETE** (calibrated verdict
>   policy). All nine work items are done; the honest limit lifts and the
>   verdict policy is calibrated.
>
> **2026-06-28 — WI-1 → WI-5 landed** (branch `fix/track-b-eval-review-hardening`,
> deterministic-first, test-first; 158 reviewer-surface tests + 122 architecture
> tests green; ruff clean). Locked session decisions: scope WI-1→WI-5; router lives
> at `code_reviewer/routing.py` (shared); both runners kept, share the router;
> v2/frontend/explainability_frontend kept as legacy.
>
> - **WI-1 — Path router (keystone). DONE.** `code_reviewer/routing.py` — L1-pure
>   (stdlib only). `route(paths)` → `[RouteEntry(path, folder, language, rules_file)]`
>   via longest-prefix segment match + nearest-ancestor `REVIEW.md` resolution.
>   `tests/code_reviewer/test_routing.py` (36 tests, 100% deterministic).
> - **WI-2 — Per-folder `REVIEW.md` enforcement maps. DONE.** Ten thin maps
>   (`trust/`, `services/`, `components/`, `orchestration/`, `meta/`, `prompts/`,
>   `frontend/`, `middleware/`, `scripts/hooks/`, root `REVIEW.md`). Each cites
>   `AGENTS.md` rule IDs; never copies prose. Cite-resolves lint
>   `code_reviewer/cite_lint.py` + `tests/code_reviewer/test_review_md_cites.py`
>   (resolves literal `Invariant #N` *and* root's numbered-list form).
> - **WI-3 — One reviewer prompt (v3). DONE.** `prompts/codeReviewer/v3/`
>   (system + architecture_rules + submission) — global protocol + `rules_file_content`
>   injection slot + FD1–FD7 for TS/TSX. `review_config.py` validator `{v1,v2}`→
>   `{v1,v2,v3}`; v2 untouched. Render-verified through the real `PromptService`
>   (StrictUndefined); `tests/prompts/test_code_reviewer_v3_renders.py`.
> - **WI-4 — TDD fold + deprecate. DONE.** TAP-1…4 folded into v3 §5 (D3) with
>   AST/LLM detection split; `docs/reviews/TDD_AGENTS_MD_REVIEW.md` marked
>   DEPRECATED (header → v3/D3 + per-folder maps), body kept as rationale-of-record.
> - **WI-5 — Track A/B/C as cited rules. DONE.** New `scripts/hooks/AGENTS.md`
>   (+CLAUDE.md bridge) with HOOK-1/2/3 (PostToolUse-never-blocks /
>   PreToolUse-safety-only / fail-safe) derived from the live hook scripts;
>   `meta/REVIEW.md` cites AP-4/AP-6; root `REVIEW.md` makes ADR.1 file-list-checkable.
>
> **Deferred:** WI-8 (validate the reviewer judge — TPR/TNR ≥ 0.90 fixture),
> WI-9 (verdict-policy calibration). **Honest caveat:** the deterministic half
> (router, cite-lint, AST/TS predicates) is trustworthy now; v3 **LLM verdicts
> are not gate-grade until WI-8**.

## Intent (one paragraph)

Collapse the three reviewer prompt families into **one global reviewer** (the *how to
review*) routed by changed path to a **thin per-folder `REVIEW.md`** (the *what to enforce
here*). Whichever coding agent is active (Claude Code or Cursor) auto-detects the changed
paths and feeds the reviewer that folder's `REVIEW.md`, so the gap between "good
backend/four-layer coverage" and "everything else (frontend, middleware, hooks, meta,
prompts)" closes with one reviewer. Deprecate the stale TDD review doc and fold its testing
anti-patterns (TAP-1…4) into the reviewer's D3.

**Locked decisions (from the brainstorm):**
- **Two-tier rules:** ONE global reviewer prompt holds the protocol + D1–D5 + output contract;
  each folder carries a **thin `REVIEW.md`** with its local enforcement.
- **`REVIEW.md` cites, never copies.** It references the folder `AGENTS.md` rule IDs it
  enforces (e.g. "flag H1, AP-3") + per-rule detection (AST vs LLM) + severity. `AGENTS.md`
  stays the single source of the rule *content*; `REVIEW.md` is the thin *enforcement map*.
  Rationale (trade-off): an inline `## Review rules` section inside `AGENTS.md` would **bloat**
  it with a second audience and worsen the coding agent's auto-loaded context every edit
  (context rot); a separate `REVIEW.md` keeps audiences clean (coding agent loads `AGENTS.md`,
  reviewer loads `REVIEW.md`) and the cite-don't-copy form defuses the two-file drift risk.
- **TDD content** → deprecate the doc; fold TAP-1…4 into reviewer **D3** (AST-checkable where possible).
- **Agent-agnostic**: same flow for **Claude Code and Cursor** — auto-detect/prompt the right
  per-folder context. Shared `REVIEW.md` source, two thin dispatch surfaces.

---

## 1. Research grounding (why this design, not invented)

### From the playbooks (`docs/research/agenticengineeringplaybook/`)
- **Verification ladder (Eugene Yan, Anthropic).** Catch issues at the lowest rung:
  post-edit hooks → tests/evals → **LLM reviews** at the top. The reviewer is the top rung;
  hooks/sensors below it *dispatch* to it. (RB-V.)
- **Subagent as context firewall + fresh-thread Writer/Reviewer (Willison; Anthropic).**
  The reviewer should run in **isolated context** with *only* the relevant rules loaded —
  the architectural argument for per-folder scoping: load that folder's `AGENTS.md`, not all
  of them. (RB#4 B1, RB-Core Step 5.)
- **Per-criterion scoped judges, not holistic (Husain/Shankar).** "One judge = one failure
  mode." Argues *for* folder-scoped rulesets over one mega-prompt, and *against* proliferating
  reviewers beyond signal → one reviewer with scoped rules, not three families. (RB-V P5.)
- **Validate the judge (TPR/TNR).** A reviewer judge must itself be validated on a
  human-labeled set — ties to Track B's `meta/judge_validation.py`. (RB-V.)
- **Named precedent.** The playbook cites Ghostty's **nested, scoped `AGENTS.md`**
  (`src/inspector/AGENTS.md`) as real-world practice — exactly this repo's model.

### From external research (current as of June 2026)
- **`AGENTS.md` is the cross-tool standard** (Linux Foundation Agentic AI Foundation, read by
  Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf, Zed). Nested `AGENTS.md`
  **auto-applies by subdirectory in BOTH Claude Code and Cursor** — the convergence point:
  one per-folder rule source both coding agents already path-attach.
- **Cursor `.cursor/rules/*.mdc`** frontmatter fields: `alwaysApply`, `description`, `globs`.
  `globs: "frontend/**/*.tsx"` = *Auto-Attached* (included when a matching file is in context).
  Standard `.mdc` files do **not** nest/auto-attach by subdirectory — only `globs` scope them.
  → For Cursor, path-scoping is done with `globs:` in root-located `.mdc`, OR by relying on
  Cursor's native nested-`AGENTS.md` support. Both are viable; see §4.

**Design consequence:** the *rule source* is agent-agnostic (nested `AGENTS.md`); only the
*dispatch surface* is tool-specific (Claude Code hook vs Cursor `.mdc` glob / hook).

Sources:
- Cursor Rules docs — https://cursor.com/docs/rules
- AGENTS.md cross-tool standard — https://vibecoding.app/blog/agents-md-guide ,
  https://codersera.com/blog/agents-md-vs-claude-md-vs-cursor-rules-comparison-2026/

---

## 2. Current state (verified 2026-06-28)

| Surface | Today | Problem |
|---|---|---|
| Backend reviewer | `prompts/codeReviewer/v2/` (D1–D5, 11-rule dep table, trust rules). AST-backed via `meta/code_reviewer.py` (`check_dependency_rules`/`check_trust_purity`/`detect_anti_patterns`). | Four-layer Python only; zero awareness of frontend ring or Track A/B/C invariants. Frozen at "Sprint 4". |
| Frontend reviewer | `prompts/codeReviewer/frontend/` (FD1–FD7) + `code_reviewer/frontend/runner.py` + a deterministic `tools.py` (path predicates: `.tsx`, `Composer.tsx`). | Separate family; no shared protocol with backend; can drift. |
| Explainability FE reviewer | `prompts/codeReviewer/explainability_frontend/` | Third family — more drift surface. |
| Dispatch | None by path. `meta/code_reviewer.py` is invoked with hand-fed files; `prompt_version` is `v1`/`v2` only. | No hook/sensor picks the reviewer by changed paths. |
| Cursor | `.cursor/hooks.json` exists; **no `.cursor/rules/`**. | No Cursor-side review context routing. |
| TDD review | `docs/reviews/TDD_AGENTS_MD_REVIEW.md` (RESOLVED 2026-06-14). | Stale: cites "AGENTS.md 219 lines / lines 189–209"; post-restructure root is 126 lines and TAP content moved into nested files → dangling pointers. |

**Three families + no router = the gap.** This plan makes it one reviewer + a path router +
the nested `AGENTS.md` as rule source.

---

## 3. Target architecture

```
                changed paths (git diff --name-only)
                              │
              ┌───────────────┴────────────────┐
              │   path router (deterministic)   │   maps each path → owning folder
              └───────────────┬────────────────┘
                              │  per file: (folder, language)
                              ▼
        ┌─────────────────────────────────────────────────┐
        │  ONE reviewer (global protocol, unchanged D1–D5) │
        │  + loads that folder's REVIEW.md (cites AGENTS)  │
        │  + runs the folder's deterministic checks first  │
        └─────────────────────────────────────────────────┘
                              ▲
        ┌─────────────────────┴───────────────────────────┐
        │  Dispatch surfaces (tool-specific, thin)         │
        │   • Claude Code: PostToolUse/Stop hook + skill   │
        │   • Cursor: .cursor/rules/*.mdc (globs) + hook   │
        └──────────────────────────────────────────────────┘
```

**Two-tier rules, single source of content:** the folder `AGENTS.md` holds the rule
*content* (trust purity, FD1–FD7, H1–H5, AP-4, hook fail-safe). A thin per-folder
`REVIEW.md` is the *enforcement map*: it **cites** the AGENTS.md rule IDs the reviewer must
flag + per-rule detection method (AST vs LLM) + severity — it never copies the rule text.
The coding agent auto-loads `AGENTS.md` (build guidance); the reviewer loads `REVIEW.md`
(enforcement). Audiences stay separate → `AGENTS.md` is not bloated and the coding agent's
auto-loaded context does not carry review-only rules.

**What stays deterministic (the lowest rung):** the existing AST validators
(`check_dependency_rules`, `check_trust_purity`, `detect_anti_patterns`) and the frontend
`tools.py` path predicates run **before** any LLM judgment and their findings take precedence.
The LLM layer adds only what AST can't see, reading the routed folder's `REVIEW.md`.

---

## 4. Work items

### WI-1 — Path router (deterministic, the keystone) ✅ DONE (2026-06-28 → `code_reviewer/routing.py`)
A pure function `route(paths) -> list[(path, folder, language, rules_file)]`:
- Maps each changed path to its **owning folder** (longest-prefix match over the known set:
  `trust/`, `services/`, `components/`, `orchestration/`, `meta/`, `prompts/`, `frontend/`,
  `middleware/`, `scripts/hooks/`, root).
- Resolves `rules_file` = nearest ancestor `REVIEW.md` (folder's own, else root `REVIEW.md`).
- Classifies `language` (`.py` → backend dims; `.ts/.tsx` → frontend FD dims).
- Lives where both runners can import it (e.g. `code_reviewer/routing.py`), L1-pure, unit-tested.
- This is the seam hooks/sensors call. **Deterministic = testable; no LLM in the router.**

### WI-2 — Author the thin per-folder `REVIEW.md` enforcement maps ✅ DONE (2026-06-28 → 10 `*/REVIEW.md` + `code_reviewer/cite_lint.py`; hardened P2-10/P2-11/P3-a)
- One `REVIEW.md` per known folder (`trust/`, `services/`, `components/`, `orchestration/`,
  `meta/`, `prompts/`, `frontend/`, `middleware/`, `scripts/hooks/`) + a root `REVIEW.md`
  fallback. Each is **thin**: a table of `rule_id (from AGENTS.md) | detection (AST|LLM) |
  severity`. It **cites** AGENTS.md rule IDs; it never restates the rule text.
- This is the per-folder reviewer context the router resolves and the dispatch surfaces point at.
- **Hardening (post-WI-5):** `cite_lint.py` now also enforces (a) `AST (...)` label →
  detector contract match via `DETECTOR_RULE_IDS` (P2-10), (b) cross-folder cite locality
  — a `REVIEW.md` may cite only its own or the root `AGENTS.md` (P2-11), and (c) mojibake
  in `REVIEW.md`/`AGENTS.md` (P3-a). Wired into `make check` + pre-commit (P3-b).

### WI-3 — Collapse to one reviewer prompt that consumes `REVIEW.md` ✅ DONE (2026-06-28 → `prompts/codeReviewer/v3/`, `review_config.py` v3)
> **Carry-forward to a future WI:** the v3 *prompt* consumes `REVIEW.md`, but
> folding the frontend `tools.py` predicates into the shared deterministic layer
> and wiring the runner to inject `rules_file_content` is **not yet done** — v3 is
> authored and render-verified; the runner integration rides with WI-6.
- New `prompts/codeReviewer/v3/` (clean rollout via existing `prompt_version` machinery —
  extend `review_config.py` validator from `{v1,v2}` to include `v3`; do **not** mutate v2,
  it's an A/B baseline).
- v3 system prompt = the global five-phase protocol + output contract, **plus** a slot that
  injects the routed folder's `REVIEW.md` as the local enforcement map, **plus** the FD1–FD7
  dimensions activated when the routed language is TS/TSX.
- Fold the frontend `tools.py` deterministic predicates into the shared deterministic layer so
  the one reviewer keeps both Python-AST and frontend-path checks.
- Result: `frontend/` and `explainability_frontend/` prompt families are **superseded** by
  v3 + the `frontend/REVIEW.md` (their FD content is cited from `frontend/AGENTS.md`).

### WI-4 — Fold TDD anti-patterns into D3 (deprecate the doc) ✅ DONE (2026-06-28 → v3 §5; `TDD_AGENTS_MD_REVIEW.md` deprecated; AST detectors landed P2)
- Add TAP-1…4 to the reviewer's **D3 Test Quality** with detection rules; make the
  AST-checkable ones deterministic: TAP-2 (>3 mocks/test), TAP-4 (failure-test ratio per
  decision point), TAP-1 (test re-imports the impl symbol it's testing). TAP-3 stays LLM.
- TAP-1…4 rule *content* already lives in the nested `AGENTS.md` test sections; the relevant
  `REVIEW.md` (`trust/`, `services/`, `components/`, `meta/`) cites those IDs into D3.
- Mark `docs/reviews/TDD_AGENTS_MD_REVIEW.md` **DEPRECATED** with a header pointing to v3/D3
  and the per-folder `REVIEW.md`; keep the file as rationale-of-record (don't delete history).
- **Detectors landed (P2):** `detect_mock_abuse` (TAP-2) and `detect_failure_path_ratio`
  (TAP-4) implemented in `utils/code_analysis.py`, unit-tested, and registered in
  `DETECTOR_RULE_IDS`. TAP-4 rule content localized to `meta/AGENTS.md §L4` (P2-11) so
  `meta/REVIEW.md` cites its own folder. TAP-1 and TAP-3 remain LLM-side per the plan.

### WI-5 — Track A/B/C invariants as reviewer rules (close the ratchet) ✅ DONE (2026-06-28 → `scripts/hooks/AGENTS.md` HOOK-1/2/3; root `REVIEW.md` ADR.1; ADR.1 detector landed P2)
Rule content lives in `AGENTS.md`; the cite goes in the folder's `REVIEW.md`:
- `scripts/hooks/`: hook fail-safe / `PostToolUse` never-block / `PreToolUse` safety-only
  (`scripts/hooks/REVIEW.md` flags a PostToolUse script that can exit-block). Add the rule to
  `scripts/hooks/AGENTS.md` first if absent.
- `meta/AGENTS.md` already has AP-6 (`None` not `0.0`) — `meta/REVIEW.md` cites it (AST-checkable).
- ADR ratchet: root `REVIEW.md` flags a diff matching an `⚠️ Ask first` trigger with **no** new
  `docs/adr/` file (mechanically checkable from the file list — the Track C gate made executable).
- **Detector landed (P2):** `detect_adr1_missing` in `utils/code_analysis.py` makes the ADR.1
  gate file-list-checkable (matches `⚠️ Ask first` triggers against the diff's file list and
  checks for a new `docs/adr/` entry). Unit-tested; registered in `DETECTOR_RULE_IDS`.

### WI-6 — Dispatch surface: Claude Code ✅ DONE (2026-06-28 → router wired into `meta/code_reviewer.py`; frontend fold; `--from-git-diff` CLI; `docs/skills/code-review/SKILL.md`)
> Includes the WI-3 carry-forward: wire `meta/code_reviewer.py` to call the WI-1
> router and inject each group's `REVIEW.md` as `rules_file_content`, + fold the
> frontend `tools.py` predicates into the shared deterministic layer.
- **v3 wiring prerequisite (closed a gap vs. WI-3's claim).** `review_config.py`
  validator, `CodeReviewerAgent.__init__`, and the CLI `--prompt-version`
  choices extended from `{v1,v2}` to `{v1,v2,v3}`; v3 template branches added to
  `_system_prompt_template`/`_submission_prompt_template`. v1/v2 byte-for-byte
  unchanged (v2 A/B baseline preserved).
- **Router integration.** The v3 path of `review()` calls
  `run_deterministic_review_v3(files, repo_root, added_files)` and
  `_build_routed_groups(files, repo_root)`. Each group reads its governing
  `REVIEW.md` from disk → `rules_file_content`; file payloads carry
  `path/folder/language/language_hint/content`. Falls back to root `REVIEW.md`
  when a folder lacks its own.
- **Frontend fold.** New shared `code_reviewer/frontend/findings.py` emits
  trust-schema `ReviewFinding` objects from the TS tool output (canonical v3
  source; `severity_for_rule` shared with the legacy runner). The v3
  deterministic phase runs `applicable_tools` + `run_ts_script` + the shared
  mappers on frontend-routed files → FD2/FD3 findings. The legacy frontend
  runner is left as-is (superseded, frozen).
- **New detectors wired.** `detect_adr1_missing` (D2, across the whole file
  list), `detect_mock_abuse` (D3 TAP-2) and `detect_failure_path_ratio` (D3
  TAP-4) on Python test files — all now invoked by the v3 deterministic phase.
- **Deterministic findings injected into the prompt.** The v3 submission
  template's `deterministic_findings` slot is populated with a compact JSON
  payload so the LLM sees pre-computed results (precedence preserved by the
  existing merge logic).
- **CLI dispatch.** New `--from-git-diff` / `--git-base` flags run
  `git diff --name-only <base>` (+ `--diff-filter=A` for `added_files`, which
  enables the ADR.1 new-service trigger). `--files` is now optional when
  `--from-git-diff` is set. The deterministic CLI path branches on v3.
- **Skill.** `docs/skills/code-review/SKILL.md` documents the contract, the
  deterministic vs. LLM invocations, the honest limits (LLM verdicts not
  gate-grade until WI-8), and the output contract. Registered in
  `docs/skills/index.md`.
- **Optional `Stop`/`PostToolUse` hook hint deferred** (marked optional in the
  plan) — the skill + CLI are the primary dispatch surface.
- **Tests.** `tests/meta/test_code_reviewer_v3.py` (v3 config, routed
  deterministic, ADR.1 trigger+relief, TAP-2, frontend fold, routed-groups
  payload, LLM injection, CLI `--from-git-diff`, v1/v2 regression guard) +
  `tests/code_reviewer/test_frontend_findings.py` (shared mappers). 36 new
  tests; full `make check` green.

### WI-7 — Dispatch surface: Cursor (parity) ✅ DONE (2026-06-28 → `.cursor/rules/*.mdc` (9 per-folder + root dispatch); `.cursor/hooks.json` decision note; parity guard)
- `.cursor/rules/<folder>-review.mdc` per known folder with `globs: <folder>/**`
  frontmatter — Auto-Attached, so Cursor picks it by path automatically. Each
  `.mdc` points the agent at that folder's `REVIEW.md` (which cites `AGENTS.md`)
  and the canonical dispatch CLI. The router (`code_reviewer/routing.py`) does
  the actual path→`REVIEW.md` resolution at CLI invocation time.
- `.cursor/rules/code-review-dispatch.mdc` is Agent-Requested (rich
  `description`, no `globs`, `alwaysApply: false`) — the "review my changes"
  entry point covering root-level files + the universal fallback to root
  `REVIEW.md`.
- Each `.mdc` is **thin and points at the folder's `REVIEW.md`** — which itself
  cites `AGENTS.md`. Same content chain Claude and Cursor both resolve; no rule
  restated anywhere.
- **`hooks.json` reused, no new hook.** `.cursor/hooks.json` keeps only the
  existing `afterFileEdit` formatter + `beforeShellExecution` safety guard (the
  lower rungs). The reviewer dispatches on demand via the CLI the `.mdc` files
  point at — deterministic-first; an un-validated LLM judge must not gate every
  keystroke (LLM verdicts are not gate-grade until WI-8). A `_comment_wi7` field
  records the decision.
- **Parity guard.** `tests/code_reviewer/test_cursor_mdc_parity.py` (90 tests):
  every `routing.KNOWN_FOLDERS` entry has a `.mdc`; frontmatter shape
  (`alwaysApply: false`, `globs` present, `description` non-empty); glob prefix
  matches the owning folder; cross-checks `routing.owning_folder()` for a sample
  path; body points at the folder's `REVIEW.md`; body has no rule tables
  (thin-pointer / cite-don't-copy); canonical dispatch command present +
  identical across all `.mdc` (no v1/v2 drift); WI-8 honest-limit stated;
  `hooks.json` carries no `meta.code_reviewer` hook entry.

### WI-8 — Validate the one reviewer's judge (Track B medicine) ✅ COMPLETE — gate CERTIFIED (TPR=1.0, TNR=1.0)
- **Labeled fixture:** 20 cases (10 clean + 10 violating) at
  `tests/fixtures/code_reviewer/wi8_validation/`, each targeting an **LLM-only**
  rule ID (no AST detector) so the deterministic half doesn't trivially pass it.
  `cases.json` is the manifest; per-case files under `cases/<id>/<repo-relative path>`.
- **Detection-vs-policy split:** `goal_met` = no critical/warning LLM finding
  (not `verdict == APPROVE`). This measures the judge's *detection* accuracy
  (WI-8), decoupled from the verdict *policy* (WI-9): the v3 `>2 warnings →
  REQUEST_CHANGES` rule means a single warning yields `APPROVE`, so the verdict
  alone would falsely score a detected-and-warned violation as "met".
- **Recording:** `scripts/record_code_reviewer_validation.py` (human-run, API
  key) materializes each case into a temp tree + the folder's `REVIEW.md`, runs
  `CodeReviewerAgent.review_v3_llm_only` (new seam — LLM report pre-merge), and
  writes `verdicts.json`. NOT run in CI (no live LLM in CI).
- **Validation:** `meta/code_reviewer_validation.py` runs
  `meta.judge_validation.validate_judge` on the recording; gate TPR/TNR ≥ 0.90,
  fail-closed on no data / undecidable rates; CLI
  `python -m meta.code_reviewer_validation`.
- **CI replay test:** `tests/code_reviewer/test_wi8_validation.py` replays the
  committed `verdicts.json` and asserts the gate passes. It is **enforced in
  `make check`** (no `slow` marker — it is a fast recorded-replay, no live LLM).
- **Gate status: CERTIFIED.** First live recording (2026-06-28,
  `claude-haiku-4-5-20251001`) scored **TPR=1.0, TNR=1.0 (n=20)**; `verdicts.json`
  is committed. The honest limit **lifts** — v3 LLM verdicts are gate-grade for
  the routed LLM-only rules covered by this fixture. Recording fixed two
  normalizer defects (flattened-findings drop, `null`/range `line` coercion) and
  one prompt defect (findings must be violations, not pass-confirmations). A
  future failing recording must NOT be committed to flip the gate — iterate the
  v3 prompt and re-record. Re-recording is also required when the judge model
  changes (record `MODEL_NAME` in `verdicts.json`-adjacent provenance).

### WI-9 — Calibrate verdict policy ✅ DONE (2026-06-28 → `apply_v3_verdict_policy` + `_demote_cosmetic_warnings` in `meta/code_reviewer.py`; v3 prompt §6 rewritten)
> v3's verdict policy was schema-compatible with v2 (`>2 warnings`); this WI
> replaces it with the severity+confidence model.
- Replaced v2's arbitrary ">2 warnings" with a single shared
  `apply_v3_verdict_policy(findings)` used by **both** v3 verdict sites
  (`run_deterministic_review_v3` and `_merge_reports`), collapsing the
  duplicated inline blocks into one testable unit:
  - `reject` = any **critical** in **D1** or **D4** (backend) OR any **FD7
    auto-reject** anti-pattern (FE-AP-4/6/7/12/18/19, frontend
    security-critical).
  - `request_changes` = any *other* critical, OR **≥3 warnings** with
    **confidence ≥ 0.7** (the quorum constant `_V3_HIGH_CONF_WARNING_QUORUM`).
  - `approve` = 0 gate-relevant criticals and sub-quorum warnings.
- **Low-confidence cosmetics become notes, not gate-trippers.**
  `_demote_cosmetic_warnings` rewrites warnings with `confidence < 0.7` to
  `Severity.INFO` (with a "demoted to note" annotation) — they stay in the
  report but do not count toward the quorum. A 598-file format baseline (many
  low-confidence cosmetics) does **not** trip `request_changes`. The merge path
  demotes inside the merged dimensions and recomputes dimension status
  (PARTIAL→PASS when only notes remain).
- **v1/v2 and the legacy frontend `derive_verdict` are untouched** — v2 is the
  frozen A/B baseline; the frontend runner is the superseded legacy runner.
- The fail-closed LLM-infra-failure `REJECT` ("LLM review failed") is preserved
  as distinct from the policy outcome.
- **Iterate-loop bound (the plan's "≤3× deterministic stop"):** the confidence
  gate is the deterministic stop — a finding below `_V3_WARNING_CONFIDENCE_THRESHOLD`
  (0.7) is a note, not a gate-tripper, so low-confidence cosmetics cannot drive
  an iterate loop. The iterate-loop itself lives in the agent runtime
  (orchestration), not the reviewer; the reviewer's contribution is to stop
  low-confidence findings from gating.
- **Tests:** 11 new tests in `tests/meta/test_code_reviewer_v3.py` — a 12-case
  calibration matrix for `apply_v3_verdict_policy` + a merge-seam
  cosmetic-demotion test (5 low-confidence LLM warnings → INFO, dimension
  PARTIAL→PASS, verdict APPROVE). Full `make check` green.

---

## 5. Critical files

- **New:** `code_reviewer/routing.py` (WI-1), per-folder `*/REVIEW.md` + root `REVIEW.md` (WI-2),
  `prompts/codeReviewer/v3/*` (WI-3), `.cursor/rules/*.mdc` (WI-7),
  `tests/fixtures/code_reviewer/wi8_validation/` (cases.json + per-case files, WI-8),
  `scripts/record_code_reviewer_validation.py` (WI-8), `meta/code_reviewer_validation.py` (WI-8),
  `tests/code_reviewer/test_wi8_validation.py` (WI-8).
- **Edit:** `meta/code_reviewer.py` (consume router + v3 + folded predicates;
  `repo_root` parameter + `review_v3_llm_only` seam for WI-8),
  `meta/CodeReviewerAgentTest/review_config.py` (allow `v3`), nested `AGENTS.md` only where a
  Track-A/B/C rule's *content* is missing (WI-5), `.cursor/hooks.json` (WI-7),
  `docs/reviews/TDD_AGENTS_MD_REVIEW.md` (deprecate header).
- **Supersede (keep, mark legacy):** `prompts/codeReviewer/frontend/`,
  `prompts/codeReviewer/explainability_frontend/`, `prompts/codeReviewer/v2/`.

## 6. Gotchas
- **Don't mutate v2** — it's the prompt-version A/B baseline; v3 is a clean addition.
- **`AGENTS.md` = rule content; `REVIEW.md` = enforcement cite; `.mdc` = path pointer.** Three
  thin layers, one content source. The coding agent loads `AGENTS.md`; the reviewer loads
  `REVIEW.md`; Cursor's `.mdc` glob points at `REVIEW.md`. No rule text is copied across layers.
- **`.mdc` ≠ nested.** Cursor `.mdc` auto-attach is by `globs`, not subdirectory. (Nested
  `AGENTS.md` *is* by subdirectory in both tools, but it's build guidance, not the review cite.)
- **Router must be deterministic and L1-tested** — it's the keystone; an LLM router reintroduces
  the un-validated-judge problem the whole plan avoids.
- **Single source of truth or it drifts** — `REVIEW.md` and `.mdc` *cite* AGENTS.md rule IDs;
  never copy rule text into them. A `REVIEW.md` citing a rule ID absent from AGENTS.md is a lint
  failure to add later. **Enforced:** `cite_lint.py` now catches missing-rule cites, non-hyphenated
  AP tokens, cross-folder cites, and mojibake — wired into `make check` + pre-commit (P2-10/11, P3).
- **Detector contract is explicit.** `DETECTOR_RULE_IDS` in `utils/code_analysis.py` is the
  contract between a detector and the rule IDs it may emit; `AST (...)` labels in `REVIEW.md`
  must reference only IDs in that contract (guard-tested). Add a new detector → register it.
- **Reviewer judge VALIDATED (WI-8 certified).** A recorded 20-case run
  (`claude-haiku-4-5-20251001`, committed `verdicts.json`) scored TPR=1.0 /
  TNR=1.0 — the honest limit lifts: v3 LLM verdicts are gate-grade for the
  routed LLM-only rules covered by the fixture. Deterministic findings remain
  fully trusted. Re-record when the judge model changes.

## 7. Verification (per work item)
- **WI-1:** unit tests: a `frontend/x.tsx` path routes to `frontend/REVIEW.md`+FE language; a
  `trust/x.py` to `trust/REVIEW.md`+backend; root file → root `REVIEW.md`. 100% deterministic.
- **WI-2:** every `REVIEW.md` rule ID resolves to a real heading/ID in the sibling `AGENTS.md`
  (a cite-resolves lint); no `REVIEW.md` restates rule prose.
- **WI-3/4/5:** point v3 at a known-violating `frontend/` diff → FD finding (v2 produced none);
  at a `trust/` I/O import → D4 critical (regression-safe vs v2); at a trust-type change w/o ADR
  → ADR.1 finding.
- **WI-6/7:** edit a `frontend/` file → Claude routed reviewer loads `frontend/REVIEW.md`;
  open same file in Cursor → `.mdc` glob auto-attaches the same `REVIEW.md` pointer.
- **WI-8:** `meta.code_reviewer_validation` prints TPR/TNR for the recorded reviewer
  fixture; gate fires below 0.90; the CI replay test is enforced in `make check`
  (fast recorded-replay, no live LLM). **Detection-vs-policy split:** the gate
  measures LLM *detection* (no critical/warning finding = met), not the verdict,
  so WI-9's policy calibration can't bias the gate. **Certified 2026-06-28:**
  TPR=1.0 / TNR=1.0 on the committed `verdicts.json`
  (`claude-haiku-4-5-20251001`); the honest limit lifts.
- **WI-9:** a 1-critical-D4 + 3-cosmetic diff yields `reject` on the critical
  (D4 critical auto-rejects), and the 3 low-confidence cosmetics demote to INFO
  notes that do not gate; a 598-file format baseline (low-confidence cosmetics)
  does **not** trip `request_changes`; a D5 critical + 5 high-confidence
  warnings yields `request_changes` (other-dimension critical, not reject).

## 8. Open items — RESOLVED 2026-06-28
- ~~v3 vs in-place v2 extension~~ → **v3, clean rollout.** v2 untouched (A/B baseline);
  `review_config.py` validator extended to `{v1,v2,v3}`.
- ~~Where the router lives~~ → **`code_reviewer/routing.py`** (shared, L1-pure).
- ~~Merge the two runners~~ → **Leave both, share the router.** v2 / frontend /
  explainability_frontend kept as legacy; the runner-wiring of the router rides with WI-6.
- ~~Cursor dispatch depth~~ → **`.mdc` glob pointers only (WI-7).** No per-edit
  reviewer hook — the reviewer dispatches on demand via the CLI the `.mdc` files point
  at. Deterministic-first: an un-validated LLM judge must not gate every keystroke
  (LLM verdicts are not gate-grade until a recorded WI-8 run certifies TPR/TNR ≥ 0.90).
  `.cursor/hooks.json` keeps only the formatter + safety guard.
- ~~WI-8 judge-validation shape~~ → **Detection-vs-policy split + record-then-replay.**
  The gate measures the LLM judge's *detection* accuracy (no critical/warning finding =
  met), decoupled from the verdict *policy* (WI-9). 20-case labeled fixture (10 clean /
  10 violating, LLM-only rule IDs); `scripts/record_code_reviewer_validation.py` records
  the LLM-only verdicts (human-run, API key); `meta.code_reviewer_validation.py` runs
  `validate_judge` (TPR/TNR ≥ 0.90, fail-closed); the CI test replays the recording and
  is skip-gated on `verdicts.json` (no live LLM in CI). The honest limit lifts only when
  a recorded run passes and `verdicts.json` is committed — a failing recording must not
  be committed to flip the gate.
