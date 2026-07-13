# Spec — Fold Runbook VI (anti-slop + backpressure) into the SDD lifecycle

> **Status:** Draft — 2026-07-13
> **Owner:** Rajnish Khatri
> **Related:** brainstorm `docs/plan/anti-slop-backpressure-sdd.brainstorm.md` (SDD Stage 1);
> source research `docs/research/agenticengineeringplaybook/ai-slop-backpressure` (Runbook VI);
> reuse vehicles `docs/adr/GATES.md`, root `AGENTS.md`, the `sdd-*` skills.

---

## 1. Goal

Make the SDD stages this change actually touches — **sdd-spec, sdd-implement, sdd-converge,
and code-review** (not brainstorm/replan/lifecycle) — carry Runbook VI's anti-slop discipline
where it is *not already present*, by **reusing the two seams it already lives in** (the
spec-first spine + the G1 comprehension gate) and filling the real gaps with the **cheapest
teeth available** — a new convention gate (**G9**), a scoped converge step, thin skill prose,
and a bounded set of `AGENTS.md` directives. For the repo author + agent loop, not the product
runtime. (B1/B5 → sdd-replan and A5's standalone form are named deferrals, §PI-11, not edits here.)

This is an **authoring-workflow / documentation** change (skills, `AGENTS.md`, GATES.md).
It ships **no product code path** and, in its accepted first pass, **no new mechanical
sensor** unless the C901 baseline decision (§PI-6) is taken now.

## 2. Context

The brainstorm audited the premise "the SDD skills don't encode Runbook VI" and found it
**partially refuted**: spec-before-code (A7) is already the SDD thesis, and G1's rotating
wordings (`docs/adr/GATES.md:82-85`) are near-verbatim Runbook VI A1. So the corrected
framing is *reuse-and-extend*, not greenfield. Three real gaps remain:

1. Root `AGENTS.md` has **zero** anti-slop vocabulary (grep: 0 matches) — no repo-wide directive.
2. No home for A2 (defensive-coding amplification) / A3 (anti-slop cleanup) in the gate + converge surfaces.
3. `make check` runs **no** complexity/duplication/dead-code sensor beyond ruff's default F401/F841 (`Makefile:74`).

The accepted bundle (human gate, brainstorm §"Accepted decisions") is
**{D1-shrunk, D2-thin, D3-G9, A3-scoped}** convention work + **D4-complexity as a
measure-first two-step (may defer)**. C1–C6 systems-backpressure is **excluded** (product
runtime, not authoring). D4-duplication and D5 defer to their own specs; D6 is an
independent read-only probe.

**Six spec-binding constraints** carried from the brainstorm critique (§"Spec-binding
constraints") are treated as hard scope walls below — they *constrain*, never *unlock*.

## 3. Functional requirements (EARS)

Failure paths first (cf. TAP-4). "THE SYSTEM" here = the SDD authoring artifacts
(`AGENTS.md`, `docs/adr/GATES.md`, the `sdd-*` + `code-review` skill files) and the
`make check` gate.

**Failure-path / anti-slop guards (write these first):**

- **FR-1 (bounds D1).** IF a proposed `AGENTS.md` directive traces only to an industry
  study (GitClear/Faros/METR) and not to a failure hit in THIS repo or a repo mechanism
  it connects to, THEN it SHALL NOT be added to `AGENTS.md` (it belongs in skill prose or
  nowhere) — the Ratchet rule (`AGENTS.md:112`). *(constraint #2)*
- **FR-2 (bounds G9).** THE new G9 gate SHALL be documented as **convention-only**
  (convention + PR-review + ADR-ratchet trigger surface, the G3/G7 class) and SHALL NOT
  be described as mechanically enforced. *(constraint #4)*
- **FR-3 (bounds A3 converge step).** THE A3 "what can be deleted / what am I missing"
  converge step SHALL be scoped to *what THIS change added* (blast-radius), NOT a
  repo-wide cleanup drive, so it does not fight B6 or the existing `unrequested`-drift
  class. *(constraint #5)*
- **FR-4 (bounds D1/D2 split).** THE `AGENTS.md` additions SHALL be short **musts** and
  the skill additions SHALL be stage-scoped **"when this fires, do this"** procedure;
  neither SHALL restate the other. This is enforced by author discipline + PR review, NOT
  by a test (no CI gate covers this seam — verified: `test_skills_mirror_parity.py` only
  byte-syncs mirrors). *(constraint #3)*
- **FR-5 (bounds C901 wire-in).** IF the C901 sensor is wired into `make check` in this
  pass, THEN it SHALL be preceded by a recorded human threshold + path-relief decision
  against the measured baseline; it SHALL NOT be wired at a threshold that turns
  `make check` red on pre-existing untouched code. *(constraint #1)*

**Capability requirements** (target artifact = canonical `docs/skills/` per §10 write-surface rule):

- **FR-7 (D1).** THE root `AGENTS.md` SHALL gain a bounded anti-slop directive block — the
  **≤5-must shortlist in §3a**, each must tracing to (a) a concrete repo failure or (b) a repo
  mechanism — citing G1/G9, sdd-replan, and the arch-test ratchets.
- **FR-8 (D3-gate).** `docs/adr/GATES.md` SHALL gain a **G9** row in the gate table **with a
  concrete Trigger + Scope** (the §3a-G9 draft), a G9 rotating-wordings block in the same
  answer-before-reveal format as G1/G3, and an updated frontmatter `title:` that lists G9; and
  `AGENTS.md` SHALL gain a one-line G9 name-declaration alongside G1/G4/G8.
- **FR-9 (D3-converge).** `docs/skills/sdd-converge/SKILL.md` Stage-10 sign-off SHALL gain the A3
  blast-radius cleanup step, its gate-list (`G1/G3/G4/G7/G8`) SHALL be updated to include G9, and
  A5's disposition SHALL be stated (A5 is **folded into the A3 step** as "delete what THIS change
  added" — NOT shipped as a separate repo-wide delete-code pass, which would fight FR-3/B6).
- **FR-10 (D2).** THE `docs/skills/{sdd-spec,sdd-implement,code-review}/SKILL.md` files SHALL each
  name the Runbook VI patterns they own (spec → A1/A7 + abstraction gate; implement → B3
  3-strikes + B4 + A2→G9; code-review → A4 back-it-out + the §3b anti-slop review gate), each
  citing Runbook VI + the existing gate, adding nothing mechanically new. *(respects FR-4)*
  THE `code-review` edit SHALL touch **`docs/skills/code-review/SKILL.md` prose only** — the
  certified v3 judge rubric (`prompts/codeReviewer/v3/*.j2`) SHALL NOT be modified
  (re-certification is out of scope; D6 decides whether it is ever worth it). *(Grounding note:
  the reviewer's judgment lives in `prompts/codeReviewer/v3/*.j2` (the certified rubric) and in
  per-folder `REVIEW.md` cite-maps lint-checked by `code_reviewer/cite_lint.py` — the latter are
  enforcement maps, not scoring dimensions; neither is in scope.)* After T4–T7 land, **`make
  skills-sync`** regenerates the `.claude/`/`.cursor/` mirrors and the parity test must be green.

**Plan-invariants** (these are requirements on THIS planning artifact, not EARS-system behaviors —
kept because they carry real acceptance meaning, but honestly a different class from FR-7..10):

- **PI-6 (D4-complexity, measure-first).** The task list SHALL split D4-complexity into two
  ordered tasks: **(a)** a read-only re-measurement of the ruff `C901` baseline + a human
  threshold/scope decision, THEN **(b)** the `make check` wire-in — and (b) MAY defer behind (a).
  It SHALL NOT be presented as a first-pass freebie. *(constraint #1)*
- **PI-11 (traceability, primary-owner).** Every **in-scope** Runbook VI pattern (the set fixed in
  TASK-8: **A1, A2, A3, A4, A7, B3, B4, B6, abstraction-earning-keep**) SHALL have a named
  **primary owner** and SHALL NOT be silently dropped. **Multi-cite is expected and allowed** where
  the roles differ — a *must* in AGENTS.md vs a *when-to-fire* in a skill vs a *gate* in GATES.md
  (this is the D1/D2/D3 layering, not a contradiction; A2's primary = sdd-implement prose, with a
  G9 gate role + an AGENTS.md must role). Every **out-of-scope** pattern (A5→folded into A3,
  A6-complexity→PI-6, A6-duplication→own spec, A8, B1/B5, C1–C6, D5, D6) SHALL carry a one-line
  disposition. *(supersedes the earlier
  "exactly one artifact" wording, which contradicted the multi-vehicle brainstorm map.)*

## 3a. Draft content for the load-bearing edits (D1 shortlist + G9 gate)

These are **candidate drafts** so the implementer isn't inventing the highest-risk content under
FR-1. The human picks / trims at the Stage-3 gate; the spec does not force all five.

**D1 — candidate AGENTS.md musts (pick ≤5; each already traces to a repo mechanism or failure):**

1. *"No new abstraction, dep, service, or graph node without asking first — state what it buys and
   the simpler thing you rejected (→ G1, ADR ratchet)."* — traces to the existing `⚠️ Ask first`
   list + G1; A1/A8/"abstraction earning its keep."
2. *"Ship only code you can explain; if a diff can't be understood line-by-line, back it out rather
   than merge it (→ the G-preamble)."* — traces to GATES.md answer-before-reveal (A4).
3. *"Defensive fallbacks are not free — a silent `except/return None/or default` that masks a real
   error is slop; justify each or delete it (→ G9)."* — traces to new G9 + AP-6 (`return None`, not
   a fabricated `0.0`) already in the spec template; A2.
4. *"Stop and ask before expanding scope — build what the spec asked, not what you noticed nearby
   (→ sdd-converge `unrequested` drift, sdd-replan)."* — traces to the existing drift class; B6.
5. *"Three failed attempts at the same task = stop and re-plan, don't thrash (→ sdd-replan)."* —
   traces to sdd-implement's latent "blocked → sdd-replan"; B3 circuit-breaker.

> Each line is a **must** (imperative + repo mechanism), not a heuristic essay. Softer Runbook VI
> guidance (WIP caps, small-diff sizing) stays in skill prose per FR-4, not here.

**G9 — Trigger + Scope draft (for the GATES.md row, FR-8):**

- **Gate:** **G9** — defensive-coding amplification guard.
- **Trigger:** a diff **adds or broadens** a defensive path — a new `try/except`, a `… or <default>`,
  an `if x is None: return`, a swallowed error, or a fallback branch — **on a path the change did not
  previously need**.
- **Scope:** name the specific failure the fallback catches, why that failure can actually occur
  here, and why silently degrading (vs. raising / returning an honest `None`) is correct. A fallback
  that can't name its failure is slop — delete it. *(Convention-only: PR-review + the ADR-ratchet
  trigger surface, the G3/G7 class — no mechanical sensor. Cf. AP-6: undecidable → `None`, never a
  fabricated value.)*
- **Rotating wordings (draft, ≥2 per GATES.md §2.3 convention):**
  - *"Point at the line that fails if this fallback is removed. If you can't, the fallback is masking,
    not handling."*
  - *"What real input reaches this `except`/default, and would raising instead have surfaced a bug
    you'd want to see?"*

## 3b. Definition — the "anti-slop review gate" (FR-10, code-review)

Not new machinery: a **named checklist item** added to `docs/skills/code-review/SKILL.md` prose that
the reviewer applies while reading a diff. It cites the existing G-preamble + Runbook VI; it does
**not** modify the certified v3 rubric. Concretely, the review gate asks the reviewer to flag:

- **A4** — any hunk the author couldn't explain (back-it-out candidate).
- **A2 / G9** — a defensive fallback with no named failure it catches.
- **A1** — an abstraction/indirection with a single call site (no duplication removed).
- **B4** — a diff too large to read every line (request a split, don't rubber-stamp).

Pass condition for TASK-7 is that these four bullets (or equivalent) exist as a named gate — a grep
for "A4"/"back-it-out" that lands on empty prose is a **fail**.

## 4. Data model / contracts

No types, schemas, or wire shapes change. Artifacts touched are Markdown:
`AGENTS.md`, `docs/adr/GATES.md`, the canonical
`docs/skills/{sdd-spec,sdd-implement,sdd-converge,code-review}/SKILL.md` bundles (mirrors
regenerated by `make skills-sync`, never hand-edited), and (if PI-6b lands) `pyproject.toml`
`[tool.ruff.lint] select` + `Makefile`. **No trust-kernel type changes → no re-signing.**

The one *contract-like* artifact is the **G9 gate row** — it must match the GATES.md schema:
a `| Gate | Trigger | Scope |` table row (format at `docs/adr/GATES.md:43-49`) plus a
`**G9 — …**` rotating-wordings block (format at `:55-96`).

## 5. Invariants & security boundaries

- **No Architecture Invariant (#1–#8) is touched.** This is documentation + skill prose +
  (optionally) a lint-config line. There is no import, no layer boundary, no dependency
  arrow. → **G7 does not fire.**
- **No security boundary (guardrail / validator / auth / sandbox / trifecta path) is
  touched.** → **G3 does not fire.**
- **ADR triggers (root `AGENTS.md` ⚠️ Ask first):** the accepted first-pass bundle adds
  **no new dependency, no trust-kernel type, no graph node, no service, and no new
  abstraction** — so **no ADR is required for {D1, D2, D3, A3}**. The one *potential*
  trigger is **PI-6b** *if* wiring C901 counts as a `pyproject.toml` change of consequence;
  it adds no dependency (ruff is already present), so it is a config-select edit, not a new
  dep — a `decisions.md` entry, not an ADR. (D4-**duplication**, which *does* need a new
  dep, is explicitly out of this spec.)
- **G9 itself is convention-only** (FR-2) — it does not add enforcement, it adds a *prompt*.

## 6. Edge cases

- **C901 baseline decision deferred** → first pass ships 100% convention, no new tooth.
  That is a **valid** outcome (brainstorm "Honest headline"), not a gap — do not fabricate a
  tooth to fill it.
- **G9 token collision** — `G2` was rejected (collides with `FR-G2.5` + GoalJudge batch
  labels); confirm `G9` is grep-clean in the gate namespace before authoring.
- **AGENTS.md directive over-reach** — a directive that reads as a soft heuristic (not a
  must) is an FR-1 failure; it belongs in a skill, not AGENTS.md.
- **Skill prose that restates AGENTS.md** — an FR-4 failure; the skill must say *when/what*,
  not re-list the musts.
- **`sdd-converge` gate-list drift** — if FR-9 updates the sign-off but misses the
  `G1/G3/G4/G7/G8` list at `SKILL.md:48`, G9 is orphaned. Both edits are one task.
- **A3 step interpreted repo-wide** — an FR-3 failure; must read as "what did *this change*
  add that can now be deleted."

## 7. Non-functional requirements

- **Determinism:** all acceptance is L1 (grep/file-presence assertions on Markdown) — no LLM,
  no live call, no flake. The one-shot greps stay **off** the CI hot path. **Exception:** if
  PI-6b lands, the C901 `select` runs inside `make check` (that is the point of wiring it) —
  so "nothing on CI" holds for the *convention* pass only; C901 is the deliberate exception.
- **Reversibility:** every edit is prose/config and trivially revertible; no migration, no
  data change. (Runbook VI A4 "back-it-out" applies to the change itself.)
- **Cost:** engineering time small (mostly prose). The only real cost axis is **calendar/
  iteration time in PI-6a** — deciding a C901 threshold + scope policy against the measured
  109/42/16 baseline. That is not a config flip.

## 8. Test plan

The deliverable is documentation, so acceptance is **content assertions**, not unit tests of
product code. Two tiers: **one-shot L1 greps** (run once at ship, output pasted into the DoD;
**NOT** on the `make check`/CI hot path — see Stage-3 lock) and **review-gated checks** (the
constraints no test covers — stated honestly per FR-4).

**No permanent `tests/architecture/test_sdd_slop_discipline.py` is created in this pass.** The
FR-2/7/8/9/10 greps are presence checks, not failure-class ratchets; putting them on `make check`
would overstate enforcement while FR-1/3/4 stay human (D5-class arch-test stays deferred until a
specific absence *recurs* — and if one ever lands, prefer a **narrow G9 cross-cite (FR-8 shape)**,
not kitchen-sink prose-police).

| FR | Test / check | Layer | On `make check`? |
|----|------|-------|------------------|
| FR-2 | one-shot grep: GATES.md G9 block contains "convention" AND lacks "mechanically enforced"/"test_" | L1 | no (one-shot, DoD) |
| FR-7 | one-shot grep: `AGENTS.md` new anti-slop section heading + ≥1 G9 cite | L1 | no (one-shot, DoD) |
| FR-8 | one-shot grep: GATES.md `\| **G9**` table row AND `**G9 —` wordings block; AGENTS.md G9 name line | L1 | no (one-shot, DoD) |
| FR-9 | one-shot grep: `docs/skills/sdd-converge/SKILL.md` A3 step + `G9` in gate list + A5-disposition note | L1 | no (one-shot, DoD) |
| FR-10 | one-shot grep: docs/skills/{sdd-spec,sdd-implement,code-review} each for its owned pattern ids (A1/A7; B3/B4/A2/G9; A4) + parity test green post-sync | L1 | no (one-shot, DoD) |
| PI-11 | one-shot cross-check: every **in-scope** pattern has a named primary owner; every deferred pattern has a disposition (multi-cite OK) | L1 (grep) | no (one-shot, DoD) |
| FR-1 | **review-gated** — each AGENTS.md directive has a traceable justification | — (PR review) | no |
| FR-3 | **review-gated** — A3 step reads blast-radius-scoped | — (PR review) | no |
| FR-4 | **review-gated** — no AGENTS.md↔skill restatement (no test covers this seam) | — (PR review) | no |
| FR-5 | conditional on PI-6b — `make check` stays green after any C901 wire-in | L1 | yes (only if PI-6b lands) |
| PI-6 | task-ordering check: measurement task (9) precedes wire-in task (10) in the task list | — (plan review) | no |

> **Stage-3 lock (human, 2026-07-13):** the greps above are **one-shot** — required by DoD, run
> at ship, output pasted; they do **not** join `make check`. FR-1/3/4 stay review-gated (no
> automatable substitute). The only thing that ever touches `make check` is a C901 wire-in
> (FR-5), and only if PI-6a's decision says so.

## 9. Definition of Done

Two exit gates (per §11 ship order):

**Convention-complete** (a PR may land here):
- [ ] FR-7 through FR-10 + PI-11 implemented; each **one-shot L1 grep** run at ship and its output
      pasted here (no permanent arch-test created; greps do not join `make check`).
- [ ] FR-1..FR-5 (the bounding constraints) hold — verified by review, stated as review-gated.
- [ ] All skill edits landed in **canonical `docs/skills/`**, then `make skills-sync` run and
      `test_skills_mirror_parity.py` green (never hand-edited `.claude/`).
- [ ] `code-review` edit touched **`docs/skills/code-review/SKILL.md` prose only** — the certified
      v3 rubric (`prompts/codeReviewer/v3/*.j2`) was **not** modified (`git diff` shows nothing
      under `prompts/codeReviewer/`; separate re-certification — **D6 is NOT required for this DoD**,
      it is the optional independent probe that would *decide* any future re-cert).
- [ ] `make check` green AND `pytest tests/architecture/ -q` green — actual output pasted.
- [ ] Invariants §5 unbroken: **no ADR required** for {D1,D2,D3,A3} (confirmed: no dep/type/
      node/service/abstraction added).
- [ ] G9 is documented convention-only everywhere it appears (FR-2) — no "enforced" language;
      G9 has a concrete Trigger + Scope (not a bare label).
- [ ] Every **in-scope** Runbook VI pattern has a named primary owner; every deferred pattern (A5,
      A6-complexity→PI-6, A6-duplication, A8, B1/B5, C1–C6, D5, D6) has a one-line disposition
      (PI-11); C1–C6 remain excluded.

**Spec-complete** (Status → Implemented only here):
- [ ] PI-6a (C901 re-measure + decision) recorded in `docs/adr/decisions.md`; PI-6b wired **only if**
      the decision says so, else explicitly deferred with the deferral noted. Convention work did
      **not** block on this. `decisions.md` entry filed for the C901 call.

---

## 10. Plan (Stage 2 — architecture + touchpoints)

No architecture. Every change is a Markdown edit to an existing file (or a config-select line
in the C901 branch). Derived from the clarified spec + the constitution (`AGENTS.md` invariants,
all untouched per §5).

> **Write-surface rule (grounding, verified 2026-07-13):** canonical skills live in
> **`docs/skills/<name>/SKILL.md`** (the OKF bundle); `.claude/skills/` and `.cursor/skills/`
> are **mechanical mirrors** synced by `scripts/sync_skills.py` and gated by
> `tests/architecture/test_skills_mirror_parity.py`. **All skill edits target `docs/skills/`,
> then `make skills-sync` regenerates the mirrors.** Editing `.claude/` directly turns parity
> red or is clobbered by the next sync.

Touchpoints, in dependency order:

| # | Artifact | Edit | FR |
|---|----------|------|-----|
| T1 | `docs/adr/GATES.md` | Add **G9** table row (after `:49`) + G9 rotating-wordings block (after `:96`), answer-before-reveal format; convention-only language; **include a Trigger + Scope line** (FR-8a) | FR-8, FR-2 |
| T1b | `docs/adr/GATES.md` | Update the frontmatter `title:` from `(G1/G3/G4/G7/G8)` to include G9 — else OKF/cite drift | FR-8 |
| T2 | `AGENTS.md` | Add G9 name-declaration line beside G1/G4/G8 (near `:95-102`) | FR-8 |
| T3 | `AGENTS.md` | Add bounded anti-slop directive block — the ≤5-must shortlist in §3a, each tracing to a repo failure or mechanism, citing G1/G9/sdd-replan/ratchets; respects Ratchet rule (`:112`) | FR-7, FR-1, FR-4 |
| T4 | `docs/skills/sdd-converge/SKILL.md` | Add A3 blast-radius cleanup step to Stage-10 sign-off + add `G9` to the `G1/G3/G4/G7/G8` gate list (`:48`); note A5's disposition (FR-9a) | FR-9, FR-3 |
| T5 | `docs/skills/sdd-spec/SKILL.md` | Name A1 (simplest-thing) + A7 (spec-first) + abstraction-gate ownership; cite Runbook VI + G1 | FR-10, FR-4 |
| T6 | `docs/skills/sdd-implement/SKILL.md` | Name B3 (3-strikes→replan) + B4 (small diffs) + A2 (defensive-coding→G9); cite Runbook VI + G9 | FR-10, FR-4 |
| T7 | `docs/skills/code-review/SKILL.md` | Name A4 (back-it-out) + the anti-slop review gate defined in §3b; **SKILL.md prose only, v3 rubric untouched** | FR-10, FR-4 |
| T7b | *(mirror sync)* | `make skills-sync` after T4–T7 land; parity test green | FR-10 |
| T8 | `docs/adr/decisions.md` | Record the PI-6a C901 threshold/scope decision (after T9 measurement) | PI-6a |
| T9 | *(read-only)* | Re-measure the ruff `C901` baseline; produce the threshold + path-relief options for the human | PI-6a |
| T10 | `pyproject.toml` + `Makefile` | **CONDITIONAL** — wire C901 into `make check` **only if** T8's decision says so; else record explicit deferral | PI-6b, FR-5 |

**ADR check:** T1–T9 add no dep/type/node/service/abstraction → **no ADR** (§5). T10 adds a ruff
`select` entry (ruff already present) → **`decisions.md`, not an ADR**; if it turns `make check`
red on untouched code it violates FR-5 and must not land.

## 11. Tasks (Stage 3 — atomic, with pass/fail from EARS)

Dependency markers: `→` = depends on. Parallelizable tasks share no arrow.

- **TASK-1 — G9 gate authoring** (`docs/adr/GATES.md`). *Independent.*
  Pass: `| **G9**` row present in the gate table **with a concrete Trigger + Scope** (§3a-G9); a
  `**G9 —` rotating-wordings block present in the same format as G1/G3; the block contains
  "convention" and contains **neither** "mechanically enforced" **nor** a `test_` reference
  (FR-2, FR-8). Fail: any of those, or a G9 row with no trigger (a label, not a gate).
- **TASK-1b — GATES.md frontmatter title** (`docs/adr/GATES.md`). → TASK-1.
  Pass: the `title:` frontmatter lists G9 (no longer `(G1/G3/G4/G7/G8)` only) (FR-8). Fail: stale title.
- **TASK-2 — G9 name line in AGENTS.md** (`AGENTS.md`). → TASK-1 (name must match the row).
  Pass: a one-line `G9 — …` declaration sits alongside the G1/G4/G8 lines (`:95-102`) (FR-8).
- **TASK-3 — anti-slop directive block** (`AGENTS.md`). → TASK-2 (cites G9). *review-gated.*
  Pass: a new section heading + the §3a shortlist musts (≤5), each with a one-line justification
  tracing to a repo failure or mechanism; ≥1 cites G9; none is a bare industry-study heuristic
  (FR-7, FR-1); no line restates a skill procedure (FR-4). Fail: any unjustified/industry-only directive.
- **TASK-4 — converge A3 step + G9 in gate list + A5 note** (`docs/skills/sdd-converge/SKILL.md`).
  → TASK-1. *One task.*
  Pass: Stage-10 sign-off has a step reading "what did THIS change add that can be deleted /
  what am I missing", scoped to the change (FR-3, blast-radius) — **not** repo-wide; the
  `G1/G3/G4/G7/G8` list now includes `G9` (FR-9); AND A5's disposition is stated (folded into the
  A3 step as "delete-what-this-change-added", not a separate repo-wide delete-code pass — FR-9a).
  Fail: repo-wide wording, G9 missing from list, or A5 silently dropped.
- **TASK-5 — sdd-spec prose** (`docs/skills/sdd-spec/SKILL.md`). *Independent.*
  Pass: names A1 + A7 + abstraction-gate as owned; cites Runbook VI + G1; adds nothing
  mechanical; does not restate an AGENTS.md must (FR-10, FR-4).
- **TASK-6 — sdd-implement prose** (`docs/skills/sdd-implement/SKILL.md`). → TASK-1 (cites G9).
  *Independent of T5/T7.*
  Pass: names B3 (3-strikes → sdd-replan) + B4 + A2→G9; cites Runbook VI + G9; no restatement (FR-10, FR-4).
- **TASK-7 — code-review prose** (`docs/skills/code-review/SKILL.md`). *Independent.*
  Pass: names A4 back-it-out + the §3b anti-slop review gate (a named review-checklist item, not
  empty prose); cites Runbook VI + the G-preamble; **certified v3 rubric untouched** — `git diff`
  shows no change under `prompts/codeReviewer/` and no `REVIEW.md` diff (FR-10, FR-4).
- **TASK-7b — sync mirrors** (`make skills-sync`). → TASK-4..7. *One task.*
  Pass: `make skills-sync` run; `pytest tests/architecture/test_skills_mirror_parity.py -q` green
  (docs/skills ↔ .claude/.cursor byte-identical) (FR-10). Fail: parity red.
- **TASK-8 — pattern-coverage cross-check.** → TASK-3..7b. *One-shot grep, review-gated.*
  **In-scope pattern set (this pass):** A1, A2, A3, A4, A7, B3, B4, B6, "abstraction-earning-keep".
  **Explicitly deferred / out (named, not dropped):** A5 (folded into A3 per TASK-4),
  A6-complexity (→ PI-6, the C901 measure-first two-step; may defer), A6-duplication (own spec),
  A8 (product runtime), B1/B5 (sdd-replan, latent — not edited this pass), C1–C6 (excluded),
  D5 (arch-test template), D6 (independent probe).
  Pass: every **in-scope** pattern has a named **primary owner** and is not silently dropped;
  **multi-cite is allowed** where roles differ (a *must* in AGENTS.md vs a *when-to-fire* in a skill
  vs a *gate* in GATES.md — e.g. A2 = implement-prose primary + G9 gate + AGENTS must); C1–C6 absent
  from all authoring artifacts; every deferred pattern has a one-line disposition (PI-11).
  Fail: an in-scope pattern with no owner, or a deferred pattern with no stated disposition.
- **TASK-9 — C901 re-measure + decision** (read-only → `docs/adr/decisions.md`). *Independent; may run last.*
  Pass: fresh `.venv/bin/ruff check --select C901` counts recorded; a human threshold + path-relief
  decision written to `decisions.md`; a clear "wire" or "defer" verdict (PI-6a).
- **TASK-10 — C901 wire-in** (`pyproject.toml`+`Makefile`). → TASK-9, **CONDITIONAL on its verdict.**
  Pass (if wire): `make check` **stays green** on the untouched tree after adding the C901 `select`
  at the decided threshold (FR-5); Fail: any red on pre-existing code. If defer: task closed with a
  one-line deferral note, no edit.

**Ship order:** TASK-1 → TASK-1b → {2,3,4} and {5,6,7} in parallel → **TASK-7b (`make skills-sync`)**
→ TASK-8 (coverage) → run all one-shot greps → `make check` + arch-tests → sign-off.
TASK-9/10 run on their own track.

**Two exit states (resolves the DoD ↔ ship-order question):**
- **Convention-complete** — TASK-1..8 done, greps pasted, `make check` + arch-tests green. A PR may
  land here. TASK-9/10 do **not** block this PR.
- **Spec-complete** — convention-complete **AND** TASK-9's C901 decision is recorded in
  `decisions.md` (wire or explicit defer). The **spec** (this doc) is only signed off — Status →
  Implemented — at spec-complete. So: convention ships early; the spec closes when 6a is decided.
