---
title: 'Tier-1 misconception callout — the controlled-taxonomy → tag-bank → cluster pipeline (OQ-2): SDD Stage-1 brainstorm'
type: brainstorm
epic: E
initiative: tier-1-misconception-taxonomy
stage: 1
scope: 'Scope the OQ-2 pipeline that unblocks the /learn/skill tier-1 "Your pattern · X" aggregate callout — author a CONTROLLED misconception taxonomy, tag the bank against it, and deterministically cluster a learner''s due misses — WITHOUT manufacturing categories. A separate initiative that E1b formally deferred (not lesson-surface code).'
date: 2026-07-12
status: 'Draft — awaiting human direction gate'
parent: docs/plan/preact-parity-epic-E1b.brainstorm.md
design_source: 'Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md §3.4 (callout 3-tier honesty, DATA-CALL-1, GUARD-CALL-1), OQ-2; research/eng_coach_v2_pedagogy_spec.md §3.3 (the intended controlled 16-tag lib) / §3.6 (classify + leak-lint)'
method: 'sdd-brainstorm — premise audit (direct grep/glob + 1 explore subagent, 29 tool-uses) → every load-bearing premise checked against working tree → 6 directions over the corrected space'
---

# Tier-1 misconception callout — scoping the OQ-2 pipeline

> **The problem, re-posed.** The `/learn/skill` tier-1 callout (`"Your pattern · {theme}"`,
> design spec §3.4 tier-1 / DATA-CALL-1) renders only when a learner has **≥2 due misses that
> share the same/clustered misconception theme**. It is `gated-on-data: 0` — the live serving
> bank has **171 items / 47 tagged / all 47 tag strings DISTINCT / 0 exact clusters within any
> skill**, and the tags are free-text prose, not a controlled taxonomy. E1b formally deferred
> tier-1 behind "the reviewed OQ-2 tag-clustering pipeline" as **its own initiative**. This
> document scopes THAT initiative: how to build *taxonomy → tag → cluster* **without
> manufacturing categories** — the exact uncontrolled-mini-taxonomy risk OQ-2 exists to prevent.

## Premise audit (the problem statement is itself a hypothesis)

Every load-bearing premise was checked against the working tree (direct grep + one `explore`
subagent). **A new material finding corrects the E1b probe** (see P-7).

| # | Premise | Status | Evidence (verified `file:line`) |
|---|---------|--------|----------------------------------|
| **P-1** | A **controlled** misconception taxonomy (kebab-id `MisconceptionTag` → `MiscLibrary{pump,hint,prompt,assertion}`) is the *intended* design | ✅ **verified — design-only** | `research/eng_coach_v2_pedagogy_spec.md:136-146` (§3.3 "the linchpin"): `type MisconceptionTag = string // kebab id, e.g. "drops-commas-brevity"`, `MiscLibrary = Record<MisconceptionTag, MiscEntry>` w/ 4-rung ladder. |
| **P-2** | That structured taxonomy exists **in code** (any concrete instance / seed / enum) | ❌ **refuted — ABSENT** | Zero hits for `MisconceptionTag`/`MiscLibrary`/`MiscEntry` under `components/`, `services/`, `prompts/`, `frontend/lib/`. Only the markdown spec defines them. No seed JSON carries kebab-id tags. |
| **P-3** | The live `misconception` column is **free-text**, hand-authored, no tag/id structure | ✅ **verified** | `frontend/lib/wire/engine_entities.ts:76-77,151-152` = `z.string().nullable().default(null)` "Author-captured one-line … (C2/ADR-0027)". Values are literal prose in `_test_item_bank.ts` (e.g. `:111` `"using casual 'seen' for the past participle"`). `prompts/test_item_generator.j2:17` never *asks* for a `misconception` field — it's a nullable authored one-liner threaded verbatim by `scripts/emit_test_item_bank.py:58,191-198`. |
| **P-4** | A non-LLM `classify()` (wrong answer → tag), the §3.6 outer-loop signal | ❌ **refuted — ABSENT** | No misconception `classify()` in `components/`/`services/` (only unrelated `injection_classifier.py` etc.). ADR-0027 (`docs/adr/0027-question-misconception-field.md`) **explicitly rejected** both an LLM-synthesize path and an FK-to-taxonomy-table path — the controlled path was never built by design. |
| **P-5** | Tier-1 aggregate branch + `GUARD-CALL-1` self-hide **exist in shipped code** | ❌ **refuted — NOT shipped** | `frontend/lib/translators/skill_detail_vm.ts:344-357` renders **tier-2 ONLY** (`"On your last miss · ${skill.name}"`, single verbatim tag; hides on null/blank). NO tier-1 branch, NO cluster input, NO `GUARD-CALL` symbol anywhere. `newest_due_miss.ts:32-55` returns the *single* newest due miss verbatim; `use_coach_surface.ts:29-48` returns a plain **count**. GUARD-CALL-1 is a *design requirement*, not code. |
| **P-6** | Provenance-confinement discipline + a leak-lint exist to mirror | ✅ **verified (with a convention nuance)** | `tests/architecture/test_hint_provenance_confinement.py:22-23` accepts `<model>@<runid>` **or** bare `"authored"`; `test_test_item_provenance_confinement.py` + `test_tutorial_provenance_confinement.py` exist. **Nuance:** the tutorial gate uses a *stricter* `^(?:hand|llm):[^@\s]+@[^@\s]+$` prefix (NOT bare `"authored"`) — the newer convention to mirror. Cascade stamps `reviewed=True`+`generated_by` at `components/test_item_generation.py:212-238`. `components/hint_leakage.py` is **answer-leakage-specific to hint rungs** (4 literal classes) — **NOT reusable** for skill-level misconception copy. |
| **P-7** | Normalization yields only stop-word noise (E1b probe's conclusion) | ⚠️ **REFINED — density-dependent, and the "clusters" are false positives** | Content-word pass (this session): `s-gram` (19 tagged) surfaces candidate shared words `where`×3, `who`×2, `plural`×2, `adverb`×2. **BUT inspection shows they are FALSE POSITIVES:** `"using 'good' where an adverb is required"` and `"'Whom'…where 'who' belongs"` share "where" while being *entirely different misconceptions* (adj/adv confusion vs who/whom). The only genuine 2-item theme is who/whom. Sparse skills (`s-punc` 2 tagged, `s-org` 5) can't cluster at any density. **⟹ naive normalization MANUFACTURES categories — exactly the OQ-2 risk.** |

**Corpus caveat resolved (naming collision).** `docs/plan/coach-item-bank-live.promoted.json` is
confusingly named — its ids are `ti-gen-*` and it is emitted by `scripts/emit_test_item_bank.py`
into `_test_item_bank.ts`, documented (`_test_item_bank.ts:2`) as "**The governed practice item
bank (ADR-0021)**" that `_dev_seed.ts` loads into the browser engine DB for `/learn`. So the
47/171 measurement **IS the right serving corpus** — the file name says "coach" but it is the
practice bank `/learn` serves. (The `Eng-coach-ui-design/` sibling copy carries **0** tags.)

### What the audit changes vs the naive framing

The problem statement is essentially correct, but the audit sharpens three things:
1. **P-2/P-4**: the controlled taxonomy AND its classifier are **100% design-only** — this is a
   *build-from-zero* initiative on the taxonomy side, not a "normalize what exists" refactor.
2. **P-5**: there is **no tier-1 render code to un-stub** — the render seam (`themeCluster` input +
   tier-1 branch + GUARD-CALL-1) is net-new too. The pipeline's *output* has no consumer yet.
3. **P-7**: the deepest finding — even a reviewed human couldn't cluster *today's* bank into
   tier-1-firing themes at meaningful coverage, because (a) coverage is 27% and skill-uneven, and
   (b) tier-1 fires per-LEARNER (needs one learner to miss ≥2 *due* items sharing a *real* theme),
   and the densest skill caps at ~2 genuinely-themed items. **The load-bearing cost is a corpus
   that must first accumulate tagged, themeable items — calendar/authoring time, not engineering
   time.** This is the single most important thing the human gate must weigh.

## Directions (6) — over the corrected space

Three high-probability (follow a named repo pattern) + three exploratory. The **demand-side**
lens dominates here: the cheapest "pipeline" may be the one that makes the expensive
taxonomy-authoring *not happen yet*.

| id | kind | direction | follows pattern | ADR / gate |
|----|------|-----------|-----------------|-----------|
| **D0** | do-regardless hygiene | **Rename the mislabeled corpus file** `docs/plan/coach-item-bank-live.promoted.json` → `test-item-bank-live.promoted.json` (+ update `emit_test_item_bank.py` refs) so the ADR-0021 *coach* bank and the *test-item* bank stop colliding by name (cost the audit paid twice) | file rename + ref-rewrite (okf-curator) | none — mechanical, its own tiny PR |
| **D1** | high-probability | **Author a controlled taxonomy as a governed content artifact** — a versioned kebab-id `misconception_taxonomy.json` (mirror the item-bank ADR-0021 cascade + provenance-confinement), then **re-tag** the 47 free-text one-liners to `taxonomy_tag` via a human-reviewed mapping; add a `taxonomy_tag` field alongside the verbatim `misconception` | ADR-0021 item-bank cascade + `test_tutorial_provenance_confinement.py` (`hand:`/`llm:@` stamp) | ⚠️ new content artifact + new taxonomy field → ADR (G1 new-abstraction) |
| **D2** | high-probability | **Deterministic cluster translator over `taxonomy_tag`** (pure T1): a learner's due misses → group-by `taxonomy_tag` → self-hide below ≥2 (GUARD-CALL-1) → tier-1 VM branch; renders NOTHING until D1 tags exist (honest-invisible) | `newest_due_miss.ts:32-55` + `skill_detail_vm.ts:344-357` tier-2 case | decisions.md line (pure translator, no port); depends on D1 |
| **D3** | high-probability / **demand-side** | **Defer-with-a-tripwire** — build NOTHING now; add a read-only **coverage probe** (`scripts/taxonomy_readiness.py`) that reports, per skill, tagged-count + genuine-theme-count + *simulated tier-1 fire rate* against the multi-session corpus, and a threshold ("author the taxonomy when ≥1 skill clears N themeable items"). Ships the *decision rule*, not the feature | `scripts/syllabus_coverage_report.py` read-only report pattern | none — pure measurement; the honest default |
| **D4** | exploratory | **LLM-assisted taxonomy induction + human ratify** — a B2-style generator (`prompts/misconception_taxonomy_inducer.j2` + cascade) proposes a candidate kebab-id taxonomy FROM the 47 tags, a `PedagogyJudge`-style pass scores leak-safety + distinctness, a human **ratifies** (never auto-accept) | `components/hint_generation.py` + `prompts/hint_generator.j2` + judge cascade (ADR-0021/0015) | ⚠️ new prompt + generator + judge = 3 Ask-first triggers → ADR; **manufacture-risk lives here** |
| **D5** | exploratory | **Capture the tag at authoring-time, structurally** — extend `test_item_generator.j2` + the cascade to emit a `taxonomy_tag` from a *fixed enum* at generation, so every NEW item is born clustered; backfill old items via D1's mapping. Moves the taxonomy upstream to the source of truth (class-over-instance: one tagged field feeds tier-1 AND the §3.6 classifier AND feed-back) | `test_item_generation.py:212-238` reviewed-row stamp + `emit_test_item_bank.py:58` field passthrough | ⚠️ prompt/schema change + enum on the wire → ADR; largest blast radius |
| **D6** | exploratory / **reframe** | **Reject tier-1 as specified; ship tier-2+ only, permanently** — accept that a per-learner recurring-pattern claim needs corpus density the product may never reach at 27% coverage, and that the honest UX is already delivered by the shipped tier-2 verbatim callout. Close OQ-2 as WON'T-DO with evidence | design-spec I1 rejects the neutral miss-count line already (§3.4 tier-3) | none — a decision record; deletes future work |

**Manufacture-risk map (the OQ-2 tripwire).** The risk lives in **D4** (LLM induction can invent a
plausible-but-fake taxonomy) and in any *automatic* normalization (P-7 proved naive word-overlap
produces false themes). **D1/D5 defuse it by making the taxonomy human-ratified + versioned +
leak-linted** before any tag maps to it; **D3 defuses it by not authoring until data justifies a
real one**; **D2 is inert** (renders nothing on an empty taxonomy). No direction should auto-derive
tier-1 themes from free-text without a human in the loop — that IS the failure OQ-2 names.

## Dependency structure

```
D0 (rename)            — independent, do-regardless, ~15 min
D3 (readiness probe)   — independent; INFORMS whether D1/D4/D5 are worth doing YET
D1 (author taxonomy)   — the spine; D2 and the tier-1 render both need it
   └─ D2 (cluster translator + tier-1 VM)  — needs D1's taxonomy_tag
D4 (LLM induction)     — an ACCELERATOR for D1's authoring, not a replacement (human ratifies)
D5 (author-time tag)   — SUPERSET of D1 for NEW items; still needs D1's mapping for the 47 old ones
D6 (won't-do)          — mutually exclusive with D1/D2/D4/D5; a decision, not a build
```

**The real decision is not "which pipeline" — it is "build now vs. gate on corpus density."**
D3 is the honest first move regardless of the eventual pick: it converts "is the corpus ready?"
from an assumption into a measured number. The load-bearing cost of D1/D4/D5 is **authoring +
data-accumulation calendar time**, not engineering time — the pipeline code (D2) is a day; a
*themeable* corpus is weeks of content work.

## Leading direction + hypotheses

**Lead: D3 (readiness probe) → D1 (author taxonomy) → D2 (cluster + render), gated by D3's number.**
Reject D4-as-primary (manufacture risk); keep D4 as an optional accelerator for D1's authoring.

- **D3 works** *because* the read-only report pattern already exists (`scripts/syllabus_coverage_report.py`)
  and the multi-session corpus exists (`scripts/build_memory_multisession_corpus.py`) to simulate
  tier-1 fire rate against real due-miss distributions.
- **D1 is safe** *because* it reuses the ratified provenance-confinement discipline
  (`test_tutorial_provenance_confinement.py` `hand:`/`llm:@` stamp) — a `taxonomy_tag` only maps to
  a **reviewed** taxonomy entry, never a bare/forged one (honors [[preact-s3-bounded-session-spec]]
  "don't forge the stamp" + [[coach-item-bank-live-adr0021]] cascade).
- **D2 is safe** *because* it is a pure T1 translator that self-hides below ≥2 (GUARD-CALL-1) — on
  an empty/partial taxonomy it renders **nothing**, exactly like the shipped tier-2 case; it cannot
  fabricate a "pattern."
- **The whole chain honors OQ-2** *because* no free-text → theme mapping is ever automatic: D3
  measures, D1 authors with a human, D2 only clusters an *already-controlled* tag.

## Human direction gate (awaiting pick)

Orthogonal tracks — these are separate decisions, not one:

- **HG-1 (do-regardless):** ship **D0** (rename the mislabeled corpus file) now? *(recommend YES —
  the name collision cost this audit real time twice.)*
- **HG-2 (the real fork — build vs. gate):** pick the posture —
  **(A)** D3 first (measure readiness, then decide) *[recommended]* ·
  **(B)** commit to D1→D2 now (author the taxonomy regardless of current density) ·
  **(C)** D6 — close tier-1 as WON'T-DO, ship tier-2 permanently.
- **HG-3 (if building — authoring method):** D1 hand-authored only, or D1 **+ D4** LLM-induction as
  a human-ratified accelerator?
- **HG-4 (if building — where the tag lives):** D1 (add `taxonomy_tag`, backfill 47) only, or **D5**
  (also capture at generation-time so new items are born clustered)?

**Advance → `sdd-spec`** with the chosen posture. If HG-2=A, the "spec" is D3's probe + a threshold
decision record (light spec, runbook §6 carve-out). If HG-2=B/C, full EARS spec + the ADR the
chosen direction triggers.

See [[preact-epic-e1b-brainstorm]], [[preact-epic-e-readiness]], [[coach-item-bank-live-adr0021]],
[[preact-s3-bounded-session-spec]], [[demand-side-reduction-default-lens]].
