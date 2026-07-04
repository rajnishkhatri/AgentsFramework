---
name: agentsframework-axial-coding
type: skill
description: >-
  Run grounded-theory Stage 2 (axial coding) over an open-coded `coded.jsonl`:
  cluster the open codes into a small set of NAMED, TESTABLE failure categories,
  partition every code onto one of three axes (agent-behavior /
  environment-confound / judge-reliability) so frequency counts aren't poisoned
  by sandbox artifacts, surface the relational gold (minimal pairs, graded
  dimensions), and emit rubric-assertion + judge-test-case candidates. Use this
  whenever you have finished an open-coding pass and need to build the failure
  taxonomy — when the user says "axial code these", "build the taxonomy",
  "cluster the open codes", "turn coded.jsonl into categories", "what are the
  failure modes", or is prepping a judge rubric / gold set from coded traces.
  This is the OPERATIONAL companion to the strategic `llm-eval-grounded-theory`
  handbook (which covers Stage 2 conceptually); reach for it when you actually
  need to DO an axial pass. Do NOT use for the first-pass coding itself
  (→ `agentsframework-open-coding`, Stage 1), for seam instrumentation
  (→ `agentsframework-eval-probe`), or for selective coding / the core-category
  storyline (that human synthesis stays in the handbook).
disable-model-invocation: false
paths:
  - docs/skills/agentsframework-axial-coding/**
  - docs/evals/**/*_axial_coding.md
  - scripts/build_coach_open_code_inventory.py
---

# AgentsFramework Axial Coding

Turn an open-coded `coded.jsonl` (the Stage-1 artifact) into a **partitioned,
testable failure taxonomy** plus candidate rubric assertions and judge test
cases. Axial coding is grounded theory's second stage: the open codes get
grouped into named categories, the categories get placed on axes, and the
relationships between them (minimal pairs, gradients, templates) become the
"gold" that a per-turn score would miss.

> **Docs mirror.** Canonical bundle here; mirrored to `.claude/skills/` +
> `.cursor/skills/` by `make skills-sync`. The conceptual pipeline lives in
> [`llm-eval-grounded-theory`](../llm-eval-grounded-theory/SKILL.md) — Stage 2
> there is the *why*; this is the *how*. Stage 1 (the coding pass that produces
> `coded.jsonl`) is [`agentsframework-open-coding`](../agentsframework-open-coding/SKILL.md).

---

## When to use

- You have an open-coded `coded.jsonl` (≥~50 traces) and need the **taxonomy**:
  which failure categories exist, how big each is, which are testable.
- You're prepping a judge rubric or gold set and need the **assertions** that
  drive it — grounded in what the traces actually did.
- You want the **relational gold**: minimal pairs (same prompt, divergent
  behavior → failure is contingent, not forced) and graded families.

**Do not** use this to *assign* the first-pass codes — that's Stage-1 human work
(`agentsframework-open-coding`). And **do not** ask an LLM to name your
categories: the assist is for red-teaming (§5), never authorship.

---

## The one hard rule

**No assertion may be emitted from an unpartitioned aggregate.** Before any
count, top-mode pick, or rubric assertion, every code must carry an axis and
every category a testable check. The `axial_checker.py` gate enforces this — a
red checker means you are not allowed to emit yet. This exists because a count
that mixes "the agent failed" with "the sandbox blocked the agent" builds the
next rubric on poisoned numbers.

---

## The loop

```
0. Inventory     → build the code inventory CSV from coded.jsonl
1. Partition     → fill the `axis` column: agent-behavior | environment-confound | judge-reliability
2. Cluster       → fill the `category` column; write the categories CSV (check + polarity + dimension)
3. Gate          → run axial_checker.py; it must pass before you emit anything
4. Count + pairs → axial_matrix.py (confound-excluded counts) + axial_minimal_pairs.py
5. Write-up      → docs/evals/<component>/<component>_axial_coding.md
6. Emit          → rubric assertions + judge test-case candidates (prose, human judgment)
```

`<S>` = `docs/skills/agentsframework-axial-coding`.

### Step 0 — Inventory

```bash
.venv/bin/python scripts/build_coach_open_code_inventory.py \
    --coded <path>/coded.jsonl --out <work>/inventory.csv
```

One row per distinct code, with blank `axis` + `category` columns for you to
fill. (This is the coach-pipeline script; it now carries the two axial columns
every pass needs.)

### Step 1 — Partition (fill `axis`)

Assign each code exactly one axis:

- **agent-behavior** — a real reasoning/pedagogy failure or strength (feeds the
  taxonomy + rubric).
- **environment-confound** — a sandbox/harness/truncation artifact that
  *masquerades* as agent behavior (a **validity precondition**: these cases are
  excluded from agent denominators, not counted).
- **judge-reliability** — a verdict defect (drift, mislabeled key) — feeds judge
  calibration, not the agent taxonomy.

**Straddling code** (touches two axes — e.g. `truncated-reply` is
environment-confound *by cause* but unscorable *by consequence*): assign by
**cause**, record the consequence in the memo/notes. One column, no silent call.

### Step 2 — Cluster (fill `category` + write the categories CSV)

Group agent-behavior codes into a small set of **named, testable** categories.
Target ~5–6, but this is **not a gate** — the eng-coach pass honestly ran to 9;
forced lumping is worse than an extra honest category.

Write `<component>_categories.csv` with columns
`category,axis,polarity,binary_check,dimension`:

- **binary_check** — a pass/fail question answerable from observable evidence
  ("Did the reply leave the last inference to the learner?"), not a vibe ("bad
  scaffolding"). A category with no writable check is **rejected as un-testable**
  — the "capability limitations" reject.
- **dimension** — set this only where the member codes form an *ordered
  gradient* (e.g. `right-sizes-the-hint` → `leak-strong-implication` →
  `hands-over-conclusion`). Then `binary_check` records a check at **each
  boundary** (`|`-separated), because a gradient doesn't reduce to one coarse
  pass/fail.

### Step 3 — Gate (the checker)

```bash
.venv/bin/python <S>/scripts/axial_checker.py \
    --inventory <work>/inventory.csv --categories <work>/categories.csv
```

Exit 0 = partition complete, every category testable → you may emit. Exit 1 = it
names what's missing (a code with no axis, a category with no check, an axis
mismatch). Fix and re-run. **This is the emit gate; nothing downstream is valid
until it's green.**

### Step 4 — Count + minimal pairs

```bash
.venv/bin/python <S>/scripts/axial_matrix.py --coded <path>/coded.jsonl --inventory <work>/inventory.csv
.venv/bin/python <S>/scripts/axial_minimal_pairs.py --coded <path>/coded.jsonl
```

`axial_matrix` reports per-category counts with the **agent denominator that
excludes confound-only traces** (FR-3). `axial_minimal_pairs` groups by
normalized-exact prompt and surfaces divergent code sets. It is **axis-blind in
v1** — its output note reminds you that a pair diverging only on
environment/judge codes is noise, not gold; confirm divergence on
agent-behavior before quoting a pair.

### Step 5–6 — Write-up + emit

Write `docs/evals/<component>/<component>_axial_coding.md`: the category map
(category → axis → member codes → polarity), per-category dimensions, the
minimal pairs and graded families, and a template-economy note if canned
behavior recurs. Then **emit** the downstream candidates — rubric assertions and
judge test-case candidates (the proven consumer: see eng-coach `§7` →
`judge_test_cases.jsonl`).

**Emit is prose, not a script.** Selecting exemplars and writing
`must_catch`/`failure_if` is judgment-heavy and gains nothing from automation —
each candidate just has to trace to a partitioned, testable category.

---

## Adversarial assist (the only place an LLM helps)

You may use an LLM to **red-team** your categories — hunt un-testable or
over-broad buckets, propose a boundary case that breaks a `binary_check`. You may
**not** use it to draft categories or name them: the human owns the taxonomy
(R3/R12 in the handbook). A category you can't defend against a red-team probe is
not ready.

---

## Worked exemplars

Two real axial passes, different shapes, same discipline:

- `docs/evals/eng-coach/coach_axial_coding.md` — 9 categories, dimensions,
  minimal pairs, the template-economy cross-cut.
- `docs/research/goaljudge_phase3_axial_coding.md` — the three-axis
  Agent/Confound/Judge partition, externally grounded (MAST, arXiv 2603.06847).

Read these for *how a good write-up reads*; the doc shape is emergent per
domain, but the discipline above is constant.

## Scope

Stage 2 only. Selective coding — naming the single **core category** and writing
the storyline (e.g. `coach_selective_coding.md`) — is human synthesis on top;
the handbook covers it. This skill stops at the testable taxonomy + emitted
candidates.
