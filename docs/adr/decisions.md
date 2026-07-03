---
type: log
title: 'Lightweight decision log (intent debt, long tail)'
---

# Lightweight decision log

> Append-only, newest first. 2–4 lines per **small** decision: what was decided,
> the alternative rejected, and why. This is the low-friction sibling of the full
> ADRs — use a numbered ADR (`0000-template.md`) for big/structural decisions that
> need Context/Options/Rationale/Consequences; use this for the long tail of
> non-obvious-but-small choices that would otherwise go uncaptured. Lower the bar,
> capture more intent debt. (Playbook: Comprehension-Debt runbook, Part B.)

- 2026-07-02 — **`llm.call.input_text` truncation posture: raised cap + visible
  marker** (§13 audit finding F2). `input_text` alone gets 32 KB
  (`_MAX_INPUT_TEXT_BYTES`) so the persona + coach-context render region is
  auditable; every cut field now ends in `…[truncated]` inside its byte bound.
  Rejected keeping 4 KB + a pre-truncation answer-field scan in the bridge: that
  would hardcode coach domain fields into generic middleware and only answer one
  audit question, while a silent cut stays a vacuous pass everywhere else.

- 2026-07-02 — **DEP layer rules exempt test modules.** `classify_layer` matches the
  first path part in `LAYER_DIRS`, so `tests/services/...` graded as the services layer
  and the reviewer bot rejected PR #120 over a live test's legitimate `components`
  import. `check_dependency_rules` now short-circuits for tests/-tree, `test_*.py`, and
  `conftest.py` paths. Rejected relocating the test instead: the bot would re-trip on
  the next cross-layer test (instance fix); package invariants stay enforced by
  `tests/architecture/` and the unchanged package-path scan.

- 2026-07-02 — **`user_max_cost_per_task` deleted, not wired.** The per-task budget
  override (PLAN.md Story 5.1) had two reads in `orchestration/react_loop.py` and zero
  writers — one read was against a hardcoded empty dict, so it could never fire; the
  global `AgentConfig.max_cost_usd` cap is what actually enforces budget. Rejected wiring
  it through the runtime adapter: no per-user budget store or UI field exists to supply a
  value, so plumbing would be a writer-without-producer (ratchet rule: delete aspirational
  code). Reintroduction path documented in `tests/architecture/test_no_dead_config_knobs.py`.
- 2026-07-02 — **Stage-1 brainstorm premise audit runs before direction generation;
  `refuted` load-bearing premises force a re-pose.** Rejected advisory-only handling
  ("publish refutation but continue on the stated framing") — it preserves direction
  selection atop stale premises, the failure seen across the session's brainstorms.
  Blocking semantics resolved as *correct-and-continue*: the agent re-poses the
  corrected framing in the same document and generates directions over the corrected
  space; the human gate is the confirmation point. Rejected present-and-wait (a full
  round-trip before any directions) — the eval-loop runs that corrected-and-continued
  scored 100% and drew reviewer praise; a mid-brainstorm stop doubles latency for the
  common case where the correction is obvious. Spec: `docs/plan/sdd-brainstorm-hardening.spec.md`.

- 2026-07-02 — **PostCompact hooks CANNOT return `additionalContext` (CC 2.1.185).** A
  live `/compact` rejected `postcompact_reinject.py`'s output with `Hook JSON output
  validation failed — (root): Invalid input`: the harness hook-output schema has no
  PostCompact case, only `UserPromptSubmit` / `PostToolUse` / `PostToolBatch` / `Stop` /
  `SubagentStop` accept `additionalContext`. The S3 design (and this plan's "verified facts")
  had assumed PostCompact would accept it — wrong. Decision: the AGENTS.md re-inject must
  re-home on a schema-accepted event. **RESOLVED same day: re-homed to `SessionStart`
  gated on `source == "compact"`** (`postcompact_reinject.py` → `sessionstart_reinject.py`).
  Official CC docs confirm `SessionStart` accepts `additionalContext` and exposes a
  `compact` source that fires after auto/manual compaction, so the gate reproduces the
  post-compaction timing without injecting on startup/resume/clear. Rejected leaving it on
  PostCompact (non-functional) and `UserPromptSubmit` (fires every turn, needs a
  just-compacted guard). Pure detection/budget helpers + tests transferred unchanged (10
  tests, incl. a new non-compact-source silent-no-op). See
  `docs/research/agenticengineeringplaybook/sdd_lifecycle_harness_integration.plan.md` "S3
  defect".
- 2026-07-02 — **Coach trace-audit binding: coach-shape rules, no new carriers** (agent
  design doc §13). Two rulings: (1) `eval.goal_judge` absent on a completed coach run is
  the EXPECTED shape (ADR-0009 — judgment is post-hoc in the `coach_judges` stream), a
  shape rule mirroring the audit skill's resumed-run Identity precedent, not a weakening;
  (2) the derived `mode`/`question_id` audit evidence rides `task.started`'s recorded
  input — rejected a new observation name/sidecar (curate volume, never truth; the §13.2
  context-contract check reads existing carriers). Amendment lands as a versioned
  `governance_carrier_spec` bump at build step 3, red-first via two coach fixtures.
- 2026-07-02 — **Subject-Coach judge calibration runs the full `llm-eval-grounded-theory`
  lifecycle** (agent design doc §12) instead of a bare three-source bootstrap. ADR-0008
  cond#1's floor (TNR ≥ 0.95 / TPR ≥ 0.90 / κ ≥ 0.75) stays binding; the §12.6
  enable-policy only adds stricter gates (precision, false-action, flip, α, frozen split)
  — augmentation, not amendment, so no ADR change. Judge rubrics ship PROVISIONAL at
  build step 3 (research-prior seeds, telemetry-only); human open/axial coding on shadow
  traces revises them before any gold-set labeling or cert. Rejected: a new ADR (no
  accepted decision changes) and a separate eval design doc (§12 keeps the Stage-4
  sibling-doc structure).
- 2026-07-02 — **Post-compaction re-inject hook is advisory `additionalContext`, bounded
  ≤10 KB** (`scripts/hooks/sessionstart_reinject.py`, SessionStart matcher `compact`,
  HOOK-4; originally wired on PostCompact — see the S3-defect entry above for why it moved).
  Re-injects only the *nested* `AGENTS.md` guides of subtrees with uncommitted changes (root
  is auto-reloaded by the harness — duplicating it wastes the compaction). Rejected
  transcript parsing for "active subtree" (brittle, version-dependent) in favor of
  `git diff` + untracked files; rejected unbounded injection (defeats compaction —
  over budget degrades to a re-read path list). First hook to emit the
  `hookSpecificOutput` JSON shape; contract added as HOOK-4 in `scripts/hooks/AGENTS.md`.
- 2026-07-02 — **Skills mirrors become tracked + mechanically synced.** `.claude/skills/`
  un-gitignored; `scripts/sync_skills.py` (+ `make skills-sync`) copies canonical
  `docs/skills/` → `.claude/skills/` + `.cursor/skills/`; parity arch-test fails CI on
  drift. Why: auto-trigger requires skills in a discovery path — the old "mirror by hand"
  convention had already drifted (`deploy-gcp` mirror-only; `agentsframework-eval-probe`
  copies diverged). Rejected user-level `~/.claude/skills` install (not versioned with the
  repo; invisible to teammates/CI) and docs/skills-only (zero auto-detection).
- 2026-07-01 — **ADR-0005 number collision kept, disambiguated by suffix.** Two records
  share number 0005: `0005-subject-coach-engine-home-and-substrate.md` and
  `0005-reflections-task-id-guard-cross-turn-leak.md` (created on parallel workstreams).
  Decision: keep both, cite the latter as "ADR-0005-reflections"; suffix-disambiguation is
  the accepted convention for a collision discovered post-merge. Rejected renumbering —
  both are linked from `index.md`/`log.md`/design docs and commit messages; breaking those
  references costs more than the numbering wart. New ADRs must still take the next free
  number (0012 is next).
- 2026-07-01 — **Coach surface is routed under `/learn`, not `/`** (Phase 1.1). The
  design/plan placed the Dashboard at `app/(coach)/page.tsx`, which resolves to `/` —
  but `app/page.tsx` (the chat landing) already owns `/`, and Next.js route groups add
  nothing to the URL, so both pages would resolve to `/` → a build-time parallel-page
  collision. Decision: anchor the whole coach surface under a base segment `COACH_BASE`
  (`/learn`): Dashboard=`/learn`, Quiz=`/learn/quiz`, etc.; `/` stays the chat landing.
  Rejected: (a) coach at `/coach` — would double as `/coach/coach` for the Coach screen;
  (b) coach replaces `/` and chat moves to `/chat` — larger blast radius (touches the
  existing chat app's routing + every link to `/`). `COACH_BASE` is the single source of
  truth in `nav_model.ts`; a regression test forbids any screen routing to `/`.
- 2026-07-01 — **`CoachAgentClient` is not an engine port** (reconciliation). ADR-0006's
  port table + `SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md` §3 + the agent brainstorm §4
  list `CoachAgentClient` as an 8th "engine port over the AG-UI SSE transport." The built
  code ships **no** such port: the coach rides the existing **chat `AgentRuntimeClient`** —
  `use_coach` wraps `use_agent_run` (see `frontend/lib/translators/coach_message_vm.ts`
  header). Decision: the coach is a **consumer of the chat runtime port**, not an engine
  port; the engine bounded context stays **7 ports** (→ 8 with ADR-0011's `LearnerReadRepo`,
  still not the coach). Rejected materializing a `coach_agent_client.ts` engine port — it
  would duplicate the AG-UI transport already confined to the chat adapters (ADR-0006 itself
  rejects a new coach transport). Captured so the doc-vs-code divergence doesn't read as a
  missing port. See [SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §5.1/§7.
- 2026-06-30 — ADR-0007 capability-gating derives the coach's bound tool set from
  a **build-time capability list** (`build_graph(bound_capabilities=…)`), not per-run
  from the `agent_capabilities` resolved into state. Rejected per-run binding: it
  would force the `call_llm` node to recompute tool schemas each turn (build-once is
  the current contract) for a benefit — one graph serving many identities — the
  coach doesn't need. Matches the ADR's "graph-build boundary" wording. Flag OFF by
  default (`capability_gating_enabled`); the run-time `authorization_service` PEP is
  unaffected and complementary (bind-time filter + run-time authz).
- 2026-06-28 — ADR.1 ratchet mechanism = a git-diff **arch-test**
  (`tests/architecture/test_adr_ratchet.py`), not a Stop hook. Rejected the
  Stop-hook trigger (harness v2 item 2.1's first option): a hook can't capture the
  typed human answer the gate wants (honest limit), is version-dependent, and
  doesn't run in CI. The arch-test wires the already-shipped pure detector
  (`detect_adr1_missing`) against the merge-base diff and is version-independent.
  Waiver: an `ADR-OK: <reason>` token in a commit message of the range.
- 2026-06-28 — `.cursor/hooks.json` `afterFileEdit` kept `failClosed:false`.
  Rejected flipping it to `true` (the harness plan's blanket contract). Why: the
  post-edit ruff hook is advisory formatting (HOOK-1 never-block-on-edit); a
  formatter hiccup must not block an edit. Scoped deviation, documented inline in
  the file. The safety gate `beforeShellExecution` stays `failClosed:true`.
