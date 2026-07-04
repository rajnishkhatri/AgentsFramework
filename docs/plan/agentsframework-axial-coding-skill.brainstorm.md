# Brainstorm outcome — `agentsframework-axial-coding` skill

**Stage:** SDD Stage 1 (brainstorm) — COMPLETE. This file records the *chosen
direction + validated hypotheses* the human accepted at the gate. It is the
hand-off to **sdd-spec**, not itself a spec.

## Context

Axial coding (grounded-theory Stage 2) has been done by hand **twice** in this
repo — `docs/research/goaljudge_phase3_axial_coding.md` (460 ln, 3-axis) and
`docs/evals/eng-coach/coach_axial_coding.md` (325 ln, 9 pedagogy categories +
dimensions + minimal-pairs + template-economy). A recurring hand-effort with no
skill = the "class over instance" trigger. The handbook
(`llm-eval-grounded-theory`) only *names* Stage 2 in ~22 lines of conceptual
*why*; the operational *how* gets re-derived every pass. This skill becomes the
**operational companion** to the handbook's Stage 2, exactly as
`agentsframework-open-coding` is to Stage 1.

**Key brainstorm finding (premise P5 refuted):** the two hand passes do NOT
share a doc template. What recurs is a **discipline**, not a fill-in template —
so the skill carries the moves + scripts, and the doc shape stays emergent.

## Chosen direction (human-gated)

Compose **D1 (operational companion) + D2 (bundled scripts) + D3 (confound
spine)** into one references-only skill, with these human modifications:

1. **The 3-axis confound partition is the single mandatory gate**, as a
   class-level rule: **no assertion may be emitted from an unpartitioned
   aggregate.** Agent-behavior vs environment-confound vs judge-reliability must
   be separated before any frequency count feeds downstream. The relational
   layer (dimensions, minimal pairs, template-economy) is **optional** on top,
   per domain.
2. **D2 ships as `references/` scripts with a documented input contract**
   (consume any `coded.jsonl`, not coach-specific columns): code×category
   matrix, minimal-pair detection (group by normalized prompt → divergent
   `open_codes`), template-similarity (near-dup replies). The **Cohen's κ / IAA
   script is conditional, not a gate** — mark it "only when ≥2 coders"; demote
   IAA from a hard gate to a conditional check.
3. **The emit step targets rubric assertions + judge test-case candidates** —
   the proven downstream consumer (the eng-coach pass fed
   `judge_test_cases.jsonl`; §7 assertions → suite map).
4. **D6 folded in ONLY as an adversarial-review prompt** — red-team the proposed
   categories for untestable buckets ("capability limitations"). **Never** a
   draft generator (avoids R3/R12 violation: human owns final names).
5. **D4 rejected as sole path** (breaks the generic-vs-binding split).
   **D5 (interactive UI) deferred** with an explicit trigger: ~75+ codes or a
   multi-coder pass — revisit only then.

## Spine decision (human-gated)

Mandatory backbone = the 3-axis partition; relational layer optional. Settled;
does not defer to spec.

## Validated hypotheses (carry to sdd-spec)

- **Works because** the 6-move discipline is stable across both hand passes even
  though the doc shape isn't. (verified: P1, P5-reposed)
- **Safe because** references + `scripts/` only — no runtime, no layer crossing;
  authored canonically in `docs/skills/` + mirror-gated. (verified: P4, P7)
- **Earns its place (G1) because** handbook Stage 2 is 22 lines of *why*; the
  operational *how* has nowhere to live. (verified: P3)

## Premise-status table (audited before ideation)

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | Axial coding done by hand ≥2× → recurring class | **verified** | `goaljudge_phase3_axial_coding.md` + `coach_axial_coding.md` |
| P2 | No axial-coding skill exists yet | **verified** | `.claude/skills/` has open-coding, eval-probe, handbook — no `*-axial-*` |
| P3 | Handbook already "covers" axial | **verified but THIN** | `llm-eval-grounded-theory/SKILL.md` Stage 2 ≈ L122–144 (7-step checklist + gate + R23) |
| P4 | Two-layer split: generic methodology + workspace-bound companion | **verified** | open-coding SKILL.md L28–41 explicit |
| P5 | Two hand passes share ONE templatable structure | **REFUTED → re-posed** | GoalJudge 3-axis + first-failure vs Coach 9-cat + dimensions/minimal-pairs/templates; only the *discipline* is shared |
| P6 | Output has established home + conventions | **verified** | `docs/evals/<comp>/<comp>_axial_coding.md`, no OKF frontmatter (excluded dir) |
| P7 | Skills authored canonically then mirrored | **verified** | `docs/skills/<name>/`, `make skills-sync`, `tests/architecture/test_skills_mirror_parity.py` |
| P8 | Open-coding scripts produce axial's inputs | **verified** | `scripts/build_coach_open_code_inventory.py` rolls coded.jsonl → inventory CSV |

## Directions considered (for the record)

- **D1** Operational companion mirroring open-coding — *chosen (shape)*
- **D2** Bundle mechanical scripts (matrix, minimal-pair, template-sim, κ) — *chosen (teeth)*
- **D3** 3-axis confound partition as spine — *chosen (spine, elevated to hard gate)*
- **D4** No new skill; deepen handbook + eval-probe — *rejected as sole path*
- **D5** Interactive HTML clustering UI — *deferred (trigger: ~75+ codes / multi-coder)*
- **D6** LLM axial-draft generator — *folded in as adversarial red-team prompt only*

## Constraints inherited by the spec

- No Architecture Invariant stressed (docs + `scripts/` only). No ⚠️ Ask-first
  trigger. **G1 new-abstraction gate** applies to the skill — the "what it buys
  over the handbook" answer is P3.
- Author canonically at `docs/skills/agentsframework-axial-coding/`; run
  `make skills-sync`; parity-gated by
  `tests/architecture/test_skills_mirror_parity.py`. Needs `docs/skills/index.md`
  + `log.md` entry (curator skill).
- Reuse, don't reinvent: `scripts/build_coach_open_code_inventory.py` already
  rolls coded.jsonl → inventory CSV ("human fills definitions during axial
  coding") — the new generic scripts sit beside it.
- Output docs land in `docs/evals/<component>/` (no OKF frontmatter, excluded
  dir).

## Do-regardless (orthogonal)

Coach axial/selective numbers still include the 34 truncated traces the
selective doc says to exclude — independent eval-data cleanup, not part of this
skill.

## Next stage

→ **sdd-spec** with this direction. Write the EARS acceptance criteria for: the
mandatory-partition emit gate, the script input contract, the conditional-κ rule,
the rubric/judge-case emit target, and the adversarial-review prompt. Then plan +
tasks, cross-checked against the constitution before any code.
