---
type: brainstorm
status: stage-1
title: Make the six SDD lifecycle skills workspace-neutral + multi-agent portable, then export as .skill archives
date: 2026-07-15
---

# SDD Stage 1 — Brainstorm: portable SDD skills + export

**Problem (human-posed):** Export the six SDD lifecycle skills. Before that,
make them usable in *any* workspace and by *any* coding agent (today: Cursor +
Claude; add Copilot + extensible). Confirmed decisions: (1) fully
workspace-neutral via a per-workspace binding config; (2) Copilot adapter now +
extensible registry; (3) export as `.skill` archives.

## Premise audit (verified against the working tree, not memory)

| # | Load-bearing premise | Status | Evidence |
|---|---|---|---|
| P1 | The six SDD skills are canonical in `docs/skills/<name>/` and byte-mirrored to `.claude/skills/` + `.cursor/skills/`. | **verified** | `docs/skills/{sdd-lifecycle,…}/SKILL.md` exist; `diff docs/skills/sdd-lifecycle/SKILL.md .claude/skills/…` = 0. |
| P2 | Sync is a hard-wired **2-target** copy that a registry refactor would generalize. | **verified** | `scripts/sync_skills.py:38` `TARGETS = (…/".claude"/"skills", …/".cursor"/"skills")` — a literal 2-tuple threaded through `check()`/`sync()`. |
| P3 | The mirror is guard-tested; SDD skills are specifically pinned. | **verified** | `tests/architecture/test_skills_mirror_parity.py` runs `sync.check()`; has `test_sdd_skills_present_in_canonical_bundle`. |
| P4 | `.cursor/rules/*.mdc` thin-pointer parity exists for **code-review only**, not SDD. | **verified** | `.cursor/rules/*-review.mdc` are all review rules; `grep sdd .cursor/rules/*.mdc` = ∅. Guard: `test_cursor_mdc_parity.py`. |
| P5 | The six skills are densely coupled to THIS repo (constitution=`AGENTS.md`, `tests/architecture/`, `docs/adr/` + `ADR-OK:`, gates G1–G9, runbook + `ai-slop-backpressure` labels, `make check`/`pytest`, CC hook lifecycle, `explore` subagent). | **verified** | explore coupling map (per-skill `file:line` table); only the 10-stage skeleton, human↔agent loop, EARS, red/green TDD are portable. |
| P6 | `.skill` archives already exist as a shipped format (so we MATCH, not invent). | **verified — CORRECTS the plan** | `docs/skills/*.skill` are **zip archives** (`unzip -l` → `<name>/SKILL.md` + `references/` + `scripts/`), git-**tracked**. Four exist (memory-compaction, governance-trace-audit, axial/open-coding). |
| P7 | There is a script that EMITS `.skill` archives. | **refuted** | No emitter in `Makefile`/`scripts` produces `*.skill`; `sync_skills.py` only does the dir mirror. The four archives were hand-zipped ad hoc. → **Export needs a NEW emitter**, and that is net-new tooling (an ⚠️ Ask-first "new abstraction" candidate). |
| P8 | A "portable methodology vs repo binding" split is novel here. | **refuted — STRONG precedent exists** | `docs/skills/README.md` already splits skills on a **"Generic, portable" vs "This repo only"** axis: `llm-eval-grounded-theory` (portable) is the sibling of `agentsframework-eval-probe` (binding); `playwright-agentic-e2e` says "pair with a workspace skill" (`SKILL.md:17,59`). The split we want is an established repo pattern — **reuse it, don't invent it.** |
| P9 | Copilot instruction format can be cited from repo prior art. | **refuted → `needs-probe`** | `grep copilot-instructions / .instructions.md / applyTo:` = ∅ repo-wide; `.github/` has only workflows + dependabot. The Copilot format (`.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` w/ `applyTo:` globs) is an **external spec** — must be verified against GitHub docs at spec time, not assumed. |
| P10 | Highest ADR = 0031, so this change's ADR would be 0032. | **verified** | `docs/adr/index.md` tail = ADR-0031; `decisions.md` is the append-only small-decision log. |

**No live open defect** surfaced in the audit → no blocking D0. The SDD skills
are live/load-bearing but not *broken*; the risk is regression during the
rewrite, not a present bug.

## Re-posed framing (after P6/P7/P8/P9 corrections)

The plan is **smaller in one place and larger in another** than first stated:
- **Smaller:** the portable/binding *split* is not a new idea to design — it's
  `llm-eval-grounded-theory` ↔ `agentsframework-eval-probe` applied to SDD. And
  `.skill` is a known zip format to match.
- **Larger:** there is **no `.skill` emitter** (P7) and **no Copilot prior art**
  (P9). Export tooling + the Copilot format are the genuinely net-new work.

## Directions

### High-probability (follow an existing repo pattern)

**D1 — Binding-config file the skills read (follows the ADR-0006 `EnginePortBag`
/ config-object pattern + the eval two-layer split P8).**
One declarative `docs/skills/_workspace.sdd.toml` (or `.json`) that names this
workspace's: constitution path, check-gate cmd, test cmd, spec/plan/ADR/decision
homes, ADR-trigger list, waiver tokens, breadth-read mechanism. The six SKILL.md
bodies swap `AGENTS.md`/`make check`/`docs/adr/` for *"the workspace's
constitution / check gate / ADR home."* This repo's real values ship as the
reference instance.
- *Stresses:* nothing in the 8 invariants (skills aren't a package layer).
- *What breaks if chosen:* every SKILL.md is rewritten once; the mirror
  byte-parity test still passes (canonical → mirrors unchanged mechanism).
- *ADR trigger:* new abstraction (the binding contract) → **needs ADR-0032**.

**D2 — Adapter registry in `sync_skills.py` (follows P2/P4 directly).**
Replace the hard-coded `TARGETS` 2-tuple (`:38`) with an adapter list — each
adapter = `{discovery_path, projection_fn}`. Claude/Cursor adapters re-derive
today's byte-copy exactly (regression-safe); Copilot is one new entry. Extend
`test_skills_mirror_parity.py` per target. Windsurf/Codex later = one dict entry.
- *Stresses:* none (script layer).
- *What breaks:* the parity test must be generalized from 2 fixed paths to the
  registry; keep the existing 2 green first (red/green).

**D3 — `.skill` emitter as a `make skills-pack` target (follows the tracked-zip
format P6, fills the P7 gap).**
A `scripts/pack_skills.py` that zips `docs/skills/<name>/` → `<name>.skill`
(matching the existing archive layout), plus a `--check` to guard the tracked
archives don't drift from their source dir — mirroring how `sync_skills.py
--check` guards the dir mirrors. Emit the six SDD `.skill` archives, each
bundling the portable SKILL.md **+ the binding-config template** so a consumer
fills in their workspace.
- *Stresses:* none.
- *ADR trigger:* new tooling/abstraction → folds into ADR-0032 or a
  `decisions.md` line (small).

### Exploratory (different abstraction / integration / shift)

**D4 — Copilot adapter as a THIN pointer (mirror the `.mdc` P4 pattern), not a
prose copy.** Project into `.github/copilot-instructions.md` (repo-wide entry) +
`.github/instructions/sdd-*.instructions.md` with `applyTo:` globs, each a thin
pointer to the canonical `docs/skills/<name>/SKILL.md` — never restating skill
prose (exactly how `.cursor/rules/*.mdc` stay pointers). Keeps one source of
truth; Copilot resolves the chain like Cursor does.
- *Risk:* `needs-probe` — the Copilot instruction-file spec (filename,
  `applyTo:` semantics, whether Copilot auto-loads `.github/instructions/`)
  must be verified against current GitHub docs at spec time (P9).

**D5 — "SDD-in-a-box" self-describing bundle (bigger abstraction).** Instead of
a workspace config the *repo* owns, each `.skill` archive carries a
`binding.template.toml` + a short "first-run: fill these 7 fields" preamble the
skill reads on invocation in a foreign repo. Makes the archive truly
drop-in-anywhere without the host repo pre-authoring a config.
- *Trade-off:* more moving parts per archive; the skill must degrade gracefully
  when the config is absent (a G9 defensive-path question — name the failure).

**D6 — Demand-side / do-less: extract ONLY the portable core as a single new
`sdd-lifecycle-portable` skill, leave the six repo-bound skills untouched.**
Rather than rewrite six live skills (regression risk), author one portable
methodology skill (the 10 stages + EARS + TDD + micro-loop, zero repo paths) and
have the existing six remain the *reference binding instance* — exactly the
`llm-eval-grounded-theory` (portable) ↔ `agentsframework-eval-probe` (binding)
shape (P8). Export = pack the one portable skill + the binding contract.
- *Trade-off:* the six skills stay Claude/Cursor-only; portability lives in the
  new skill. Cheapest, lowest-regression, but doesn't make the *existing six*
  multi-agent — which may or may not be what's wanted.

## Dependency structure

- **D1 → D2 → {D3, D4}** is the spine: can't multi-target or archive skills with
  `AGENTS.md`/`make check` welded in until D1 decouples them.
- **D3 (emitter)** and **D4 (Copilot)** are independent-parallel once D1+D2 land.
- **D2 (registry)** is do-regardless hygiene even if Copilot slips — it retires
  the hard-coded tuple and generalizes the parity guard.
- **D6 is an ALTERNATIVE spine** to D1 (do-less: new skill vs rewrite six).
- **Cost axis:** engineering time dominates (no calendar-wait); the load-bearing
  risk is *regression in six live skills* (D1) — which D6 sidesteps.

## Leading recommendation (for the gate)

**D1 + D2 + D3 + D4** as the confirmed full scope — *unless* the regression risk
of rewriting six live skills argues for the **D6 do-less** spine (author one
portable skill, keep the six as the binding reference). The real decision at the
gate: **rewrite the six in place (D1) vs extract a new portable skill (D6).**

## Hypotheses for the leading direction (D1 spine)

- **Works because** the binding contract has a proven shape here — `EnginePortBag`
  (ADR-0006) is a config object threaded through consumers; the eval skills already
  split portable-vs-binding (P8). We're applying two established patterns, not
  inventing.
- **Safe because** canonical→mirror byte-parity (P3) is unchanged: rewriting
  SKILL.md bodies still flows through `make skills-sync`; the guard test proves no
  drift. Regression is bounded to *skill prose semantics*, caught at Stage-7 review
  + a new "no repo path leaks in portable core" guard.
- **Needs ADR-0032** (new abstraction: the workspace-binding contract) — declared
  up front per the ⚠️ Ask-first list.

## Open questions the gate must resolve

1. **Rewrite-in-place (D1) vs extract-new-portable-skill (D6)?** — the spine choice.
2. **Copilot format** is `needs-probe` — accept that Stage-2 verifies it against
   GitHub docs before the adapter is specced.
3. **Binding config: repo-owned (D1) vs archive-carried (D5)?** — where the
   workspace values live.

## GATE RESOLVED (2026-07-15) → advance to sdd-spec

**Chosen scope: D1 + D2 + D3 + D4 + D5.**

- **D1 (spine)** — rewrite the six SDD SKILL.md bodies in place so they *become*
  portable (read the workspace binding instead of hard-coding `AGENTS.md` /
  `make check` / `docs/adr/`). Single source of truth. Regression risk in six
  live skills is accepted, guarded at Stage-7 review **+ a new "no repo-path
  leak in portable core" arch guard**.
- **D5 (binding home)** — each `.skill` archive **carries** a
  `binding.template.toml` + a "first-run: fill these fields" preamble; the skill
  reads it on first run in a foreign repo (drop-in-anywhere). This repo ships its
  real values as the reference instance too.
- **D2 (required by D4)** — generalize `sync_skills.py:38` `TARGETS` 2-tuple into
  an **adapter registry**; Claude/Cursor adapters re-derive today's byte-copy
  exactly (regression-safe); Copilot is one new entry; parity guard generalized
  per target. Windsurf/Codex later = one entry.
- **D3 (required by D5/export)** — new `scripts/pack_skills.py` +
  `make skills-pack` + a `--check` drift guard (mirrors `sync_skills.py --check`),
  matching the existing tracked `.skill` zip layout. This is the export mechanism.
- **D4 (Copilot adapter)** — thin-pointer projection into
  `.github/copilot-instructions.md` + `.github/instructions/sdd-*.instructions.md`
  with `applyTo:` globs, never restating prose (mirrors the `.mdc` pattern).
  **Carries a `needs-probe`:** Stage-2 must verify the Copilot instruction-file
  spec (filename, `applyTo:` semantics, auto-load of `.github/instructions/`)
  against current GitHub docs before this adapter is specced.

**Rejected at gate:** D6 (extract one new portable skill, leave the six
untouched) — chose the in-place rewrite for a single source of truth over the
lower-regression duplicate-skill path.

**ADR-0032 required** (new abstraction: the workspace-binding contract).

