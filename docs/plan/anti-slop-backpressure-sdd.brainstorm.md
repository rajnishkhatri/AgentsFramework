# Brainstorm — Folding Runbook VI (anti-slop + backpressure) into the SDD lifecycle

> **SDD Stage 1 (brainstorm).** Source research:
> `docs/research/agenticengineeringplaybook/ai-slop-backpressure` (Runbook VI).
> Micro-loop: human posed the problem → agent expanded + validated against repo
> evidence → human accepted directions at the gate (below). Advance target:
> **sdd-spec** with the accepted bundle.

## Problem (restated as a hypothesis)

*"The SDD skill family should encode Runbook VI's anti-slop and backpressure
discipline so each lifecycle stage enforces it properly."* — audited against the
tree before any direction was generated.

## Accepted decisions (human gate)

| Axis | Decision |
|---|---|
| **Lead bundle** | **D1** (AGENTS.md directives) + **D2** (skill prose: sdd-spec / sdd-implement / code-review) + **D3** (new gate + converge step) |
| **A6 sensors** | **Complexity via ruff `C901` — MEASURE-FIRST (may defer), not a switch-flip.** No new dep, but *not* free in calendar time: baseline is 109 functions at threshold 10 / 42 at 15 / 16 at 25 (see constraint #1). Needs a human threshold **+ scope policy** decision before wiring into `make check`. Duplication detector deferred separately (needs a dep + ADR). |
| **C1–C6 runtime** | **Excluded** — they govern the product runtime you ship, not the authoring loop. Separate future track. |
| **New gate name** | **G9** — the defensive-coding amplification guard. (`G2` rejected: token already load-bearing as `FR-G2.5` coach export + GoalJudge batch labels → grep collisions.) |
| **Enforcement stance** | **Reuse-first** — map to an existing gate/sensor where one exists; new machinery only at a real gap. |
| **Teeth stance** | **Prefer teeth where cheap** — mechanical sensor when cheap, convention otherwise; each mapping labeled. |

## Premise-status table

| # | Load-bearing premise | Status | Evidence |
|---|---|---|---|
| P1 | The SDD skills don't yet encode Runbook VI's anti-slop patterns | **partially refuted** | Spec-before-code (A7) is *the* SDD thesis already (`sdd-spec`: "never skip from spec to code"); **G1's rotating wordings** (`docs/adr/GATES.md:82-85`) are near-verbatim Runbook VI A1 + "abstraction earning its keep." → reuse-and-extend, not greenfield. |
| P2 | Root `AGENTS.md` has no anti-slop vocabulary | **verified** | grep `simplest thing / duplicat / defensive / circuit breaker / budget / backpressure / filler comment` in `AGENTS.md` → **0 matches**. Drop-in block genuinely absent. |
| P3 | G1/G3/G4/G7/G8 are the reuse vehicle; G2/G5/G6 free | **verified (with caveat)** | `docs/adr/GATES.md:43-49` defines exactly G1,G3,G4,G7,G8. G2/G5/G6 unused *in the gate namespace* — but `G2` collides with `FR-G2.5` + GoalJudge batch labels elsewhere → **use G9**. |
| P4 | A "slop-class arch-test" precedent already exists | **verified** | `tests/architecture/test_no_dead_config_knobs.py` + `test_no_test_weakening.py` both fail CI on a slop-class recurrence — the template A5/A6 want. |
| P5 | `make check` already runs duplication/complexity/dead-code sensors | **refuted** | `check: lint format-check typecheck cite-lint hygiene test` (`Makefile:74`); `lint = ruff check .` only. No jscpd/radon/vulture/xenon/mccabe anywhere. Dead-code (F401/F841) on for prod tree, **ignored in `scripts/docs/spikes/research`** (`pyproject.toml:131-145`). A6 = **real gap**. |
| P6 | Workflow-backpressure (B1/B3/B4) applies to a solo human+agent loop | **verified, caveat** | Kanban/Nygard team heuristics; Runbook VI itself flags them "heuristics not laws" for solo. `sdd-implement` already has latent B3 ("blocked → sdd-replan") + B4 (per-task loop). Extend, don't invent. |
| P7 | Systems-backpressure C1–C6 belong in the SDD lifecycle | **refuted for the lifecycle** | C1–C6 govern the runtime you ship (`max_turns`, bulkheads, bounded queues), not the authoring workflow. **Excluded** from this map. |

**No D0 blocking defect** — authoring tooling, nothing live is broken.

**Corrected framing:** not "add anti-slop to skills that lack it" but **"reuse the
two places the discipline already lives (spec-first spine + G1 gate), fill the
three real gaps (no repo-wide directives, no A6 complexity sensor, no A2/A3/A5
gate homes), and exclude C1–C6 as product-runtime concerns."**

## The pattern → stage design map

Legend: **🦷 teeth** (mechanical sensor exists / cheap) · **📜 conv** (convention:
skill prose / gate wording / checklist) · **♻️ reuse** (extends existing
machinery) · **🕳️ gap** (nothing today).

| Runbook VI pattern | Best-fit stage | Vehicle | Status |
|---|---|---|---|
| **A7** Spec-before-code / review the plan | sdd-spec (2–4) | *Already the spine* — two hard gates spec→plan→tasks | ♻️📜 (affirm) |
| **A1** Simplest-thing-that-works | sdd-spec (plan) + **G1** | G1 wording already asks "simpler thing you rejected" | ♻️📜 (extend to plan) |
| **"Abstraction earning its keep"** | sdd-spec + **G1** | G1 already *is* this gate | ♻️📜 (cite Runbook checklist) |
| **A2** Defensive-coding amplification guard | **sdd-implement** | **NEW gate G9** + AGENTS.md directive | 📜🕳️ (new convention gate) |
| **A5** Delete-code pass / zero-tolerance smells | **sdd-converge** (S10) + implement | Sign-off checklist item + AGENTS.md directive | 📜♻️ (+ 🦷 stretch) |
| **A6** Sensors / harness engineering | **make check** (S8) | **ruff `C901` complexity — measure-first (may defer, see constraint #1)**; duplication deferred | 🦷🕳️ (the only *candidate* mechanical tooth; gated on a baseline decision) |
| **A3** Anti-slop cleanup + "what am I missing?" | **sdd-converge** (S10) | Mandatory closing step in sign-off | 📜🕳️ (new checklist item) |
| **A4** Only-ship-code-you-understand / back-it-out | **code-review** + G-preamble | GATES.md answer-before-reveal preamble *is* A4's mechanism | ♻️📜 (cite, don't rebuild) |
| **B4** Small diffs / timeouts | sdd-implement | Per-task loop enforces; add "diff small enough to read every line" to review gate | ♻️📜 |
| **B3** Circuit-breaker on thrashing (3 strikes) | sdd-implement → sdd-replan | Latent already; make the **3-strikes** rule explicit | ♻️📜 (extend) |
| **B6** Stop-and-ask, don't expand scope | all stages + AGENTS.md | Directive block; `unrequested` drift already classified in sdd-converge | ♻️📜 |
| **B1** WIP limits (≤2–3 agent tasks) | sdd-replan | Sprint-board note; solo caveat | 📜🕳️ (light) |
| **B5** Load-shed low-value tasks | sdd-replan | Latent already ("drop" in stay/slip/split/drop) | ♻️📜 (affirm) |
| **A8** Lean agentic system design | *(product runtime)* | AGENTS.md `⚠️ Ask-first` already gates new abstractions | ♻️ (out-of-workflow) |
| **C1–C6** budgets / queues / bulkheads | *(product runtime — EXCLUDED)* | Separate future track | 🚫 out of scope |

## The 6 directions

- **D1 — Repo-wide directive block** *(high-prob; follows AGENTS.md ratchet/boundaries pattern)* — **ACCEPTED.**
  Add Runbook VI's anti-slop + backpressure blocks to root `AGENTS.md` under a new
  section, adapted to cite G1/G9, sdd-replan, and the arch-test ratchets. Each
  directive needs a one-line justification (the "Ratchet rule" — every line traces
  to a real failure). Convention; no dep; no invariant stressed.
- **D2 — Extend the three focus skills' prose** *(high-prob; follows skill-file pattern)* — **ACCEPTED.**
  Thin edits so each names its owned patterns: spec → A1/A7 + abstraction-gate
  checklist; implement → B3 (3-strikes) + B4 + A2 (→G9); code-review → A4 back-it-out
  + anti-slop review gate. Each cites Runbook VI + the existing gate; nothing new
  mechanically. Must respect the skills' "reuse, don't restate AGENTS.md" rule.
- **D3 — New gate G9 + converge step** *(high-prob; follows GATES.md template)* — **ACCEPTED.**
  Author **G9 (defensive-coding amplification)** as a gate row + rotating wordings in
  `docs/adr/GATES.md`, same answer-before-reveal format as G1. Add the **A3
  "what am I missing / what can be deleted"** step to `sdd-converge` Stage 10 sign-off.
  G9 is convention-only (no mechanical trigger, unlike G8's `test_no_test_weakening`) —
  stated honestly.
- **D4 — Wire A6 sensors into `make check`** *(exploratory; the one real teeth-gap)* — **MEASURE-FIRST; may defer.**
  ruff `C901`/mccabe needs no new dep, but is **not free in calendar time** (baseline
  109/42/16 at thresholds 10/15/25 — constraint #1). Requires a human **threshold + scope
  policy** decision (core packages vs whole tree; whether `scripts/`+mirrors get relief like
  the existing `F841`/`E402` exemptions) *before* wiring in. Split into (a) measure + decide,
  (b) wire in — and it may defer behind (a), same as duplication. Duplication detector = new
  `pyproject.toml` dep (⚠️ Ask-first + ADR + G1) → its own spec.
- **D5 — "Slop-class arch-test" template** *(exploratory; class-over-instance)* — **DEFERRED.**
  Generalize the `test_no_dead_config_knobs` / `test_no_test_weakening` precedent into
  a documented pattern: when a slop class recurs (3rd copy-paste, 4th gratuitous
  fallback), convert it into an arch-test that fails the next occurrence (Runbook VI
  §5). Speculative — build the test when the class recurs, not before (avoids A1
  over-abstraction).
- **D6 — Probe the code-review judge's dimensions** *(exploratory; under-used signal)* — **INDEPENDENT cheap probe; coupled to nothing (constraint #6).**
  Read the reviewer's REVIEW.md dimensions to see which Runbook VI patterns the
  WI-8-certified v3 judge already catches. Read-only, blocks nothing, runnable any time —
  including if duplication stays deferred forever. It *precedes* and *gates* D4-duplication
  (don't ADR-gate a dep for a sensor the judge already covers), but is not downstream of it.

## Dependency structure

- **Do-regardless (zero-risk, no-ADR):** D1, D2 — pure convention, no dep, no
  invariant. This is the "design map → apply" path.
- **Sequenced:** D3 follows D1 (directive block references G9). D6 (probe) before
  D4-duplication (don't add a sensor the judge already covers).
- **ADR-gated:** only D4-*duplication* needs a new `pyproject.toml` dep → ADR + G1
  at spec time. D4-*complexity* (ruff `C901`) needs no dep and no ADR — but is **not free
  in calendar time** (baseline decision required, constraint #1); "no dep" ≠ "switch-flip."
- **Load-bearing cost:** engineering time small (mostly prose); the real cost is
  **calendar/iteration time in both D4 sensors** — tuning a duplication baseline on existing
  code (D4-duplication) AND deciding a C901 threshold + scope policy against the 109/42/16
  pre-existing findings (D4-complexity, constraint #1). Neither is a config flip.

## Verified evidence anchors (for the spec's grounding pass)

- `docs/adr/GATES.md:41-53` — the 5-gate table (G1/G3/G4/G7/G8); G9 is the new row.
- `docs/adr/GATES.md:29-39` — the universal answer-before-reveal preamble (A4's mechanism; reuse verbatim template for G9's wordings).
- `AGENTS.md:84,95,98,102` — root file's gate mentions; the "Ratchet rule" line governs D1 additions.
- `tests/architecture/test_adr_ratchet.py:39,81-107` — ADR.1 ratchet; waiver `ADR-OK`.
- `tests/architecture/test_no_test_weakening.py:9-10,82-116` — G8 sensor; waivers `G8-OK`/`ADR-…`/`flaky-tracked:`/`live_llm`/`env-gated:` (waiver-token convention for any new sensor).
- `tests/architecture/test_no_dead_config_knobs.py` — dead-code-class arch-test precedent (D5 template).
- `Makefile:74` (`check`), `:28-29` (`lint = ruff check .`) — the A6 sensor seam.
- `pyproject.toml:131-145` — ruff per-path exemptions; `C901` is added via `[tool.ruff.lint] select`.
- `code_reviewer/cite_lint.py:1-18` — cite-lint is REVIEW.md↔AGENTS.md rule-ID resolution only, **not** general prose file:line citation (do not over-claim coverage).
- `components/answer_verifiers.py:52-80` — `verify_answer` cascade (sdd-spec's "verifier-checkable criteria" reuse point).

## Caveats carried to spec

- `.claude/settings.local.json` (hook wiring) is **untracked by git** — our chosen
  tracks don't touch hook registration, so this doesn't block, but any future
  sensor-via-hook idea inherits this fragility.
- WIP/Little's-Law numbers (B1) are team heuristics adapted to solo — encode as
  guidance, not a hard cap.
- G9 has **no mechanical trigger** — it is convention + PR-review + the ADR-ratchet
  trigger surface, exactly like G3/G7. State this honestly in the gate wording.

## Spec-binding constraints (post-gate critique — do NOT unlock these in the spec)

These constrain the accepted bundle; they are not new directions. Each traces to a
concrete risk that would otherwise let the bundle become the slop it opposes.

1. **C901 is a two-step task, not a switch-flip.** Measured baseline (2026-07-13,
   `.venv/bin/ruff check --select C901`): **109 functions at max-complexity 10; 77
   at 12; 42 at 15; 30 at 18; 16 even at 25** — worst offenders `scripts/` (12),
   `orchestration/` (5), `middleware/` + `agent_ui_adapter/` (4 each) at threshold 15.
   There is **no threshold that's free** — wiring as-is turns `make check` red on
   pre-existing code this change never touched. Spec MUST split D4-complexity into
   (a) a read-only measurement + human threshold/path-relief decision, THEN (b) the
   `make check` wire-in — the same calendar-cost honesty already applied to
   duplication. D4-complexity may itself **defer behind its measurement** — do not
   present it as a first-pass freebie.
2. **D1 is bounded by the Ratchet rule** (`AGENTS.md`: "every instruction line traces
   to a real failure … don't add a rule without a failure that justifies it").
   **Reject the wholesale Runbook VI paste** — most of its lines trace to industry
   failures (GitClear/Faros/METR), not a failure in THIS repo. D1 admits only
   directives justifiable from (a) a concrete agent failure already hit here, or
   (b) a repo mechanism they connect to (e.g. "no new abstraction without asking" →
   G1 + ADR ratchet). Softer heuristics live in skills, not AGENTS.md. Expect D1 to
   shrink from "two blocks" to a handful of justified musts.
3. **D1 vs D2 ownership is DESIGN DISCIPLINE, not a CI-enforced invariant** — thin
   ownership (AGENTS.md = short **musts**; skills = **"when this stage fires, what to
   do"**) is correct, but nothing mechanically enforces it for the AGENTS.md↔skill-prose
   boundary. *Warrant correction (verified 2026-07-13):* `test_skills_mirror_parity.py`
   only asserts `docs/skills/` ↔ `.claude/`/`.cursor/` **byte-sync** (`:31,40`) — it says
   nothing about musts-vs-procedure ownership (grep for `agents.md|must|restate|copy` →
   0 matches). `code-review`'s "never copies" is the `cite_lint.py` REVIEW.md→AGENTS.md
   **cite-resolution** seam (`:1-18`) — same *spirit*, different files, and it does NOT
   cover D1/D2. So this is author discipline + PR review — the **same convention class as
   G3/G7/G9**, not a mechanical gate. Thin edits only, or the bundle becomes prose slop
   and self-refutes — but enforce it by review, and do not cite a test that doesn't exist.
4. **G9 stays convention-only — never marketed as enforcement.** It is the G3/G7 class
   (convention + PR-review + ADR-ratchet trigger surface), NOT the G8 class
   (mechanical `test_no_test_weakening`). The ONLY new mechanical tooth this pass is
   C901 — and per (1) even that needs a baseline decision first.
5. **A3 converge step is blast-radius-scoped.** "What can we delete?" means *what did
   THIS change add that can now be deleted/simplified* — NOT a repo-wide cleanup
   drive, which would fight B6 (don't expand scope) and sdd-converge's existing
   `unrequested`-drift discipline.
6. **D6 is de-coupled, not "deferred behind duplication."** It is a standalone,
   cheap, read-only probe (read the v3 review judge's REVIEW.md dimensions) that
   *decides whether duplication is ever worth an ADR*. It blocks nothing and can run
   any time — including if duplication stays deferred forever.

**Honest headline:** after these constraints, the first pass may contain **no new
mechanical tooth at all** — if the C901 baseline decision isn't made now, the pass is
100% convention (D1-shrunk + D2-thin + D3-G9 + A3-scoped). That is a valid and correct
outcome, not a failure of the bundle.

## Next stage

Advance → **sdd-spec** with the accepted bundle **{D1-shrunk, D2-thin, D3-G9,
A3-scoped}** + **D4-complexity as a measure-first two-step** (may defer). D4-duplication,
D5 defer to their own spec/ADR; **D6 is an independent cheap probe, coupled to nothing.**
