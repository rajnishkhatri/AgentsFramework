# Pyramid Principle Review of AGENTS.md

**Analysis method:** Pyramid Principle / MECE structured evaluation
**Source:** `research/pyramid_react_system_prompt.md`
**Date:** 2026-04-17
**Subject:** `AGENTS.md` — workspace guidance file for AI agents and contributors

---

## Phase 1: Decompose

**Restated question:** "Does the AGENTS.md effectively serve its purpose — giving any AI agent (or new human contributor) the minimum viable context to work correctly in this codebase without violating architectural invariants?"

**Problem type:** Evaluation

**Issue tree:**

```
Root: Is this AGENTS.md fit for purpose?
├── Branch 1: Completeness — Does it cover everything an agent needs?
├── Branch 2: Structure — Is information ordered for fast comprehension?
├── Branch 3: Actionability — Can an agent derive correct behavior from it?
├── Branch 4: Accuracy — Does it match the actual codebase?
```

**Ordering type:** Degree (most impactful dimension first)

**Validation:**

- Completeness: Four dimensions (completeness, structure, actionability, accuracy) cover the evaluation space. Pass.
- Non-overlap: Completeness (what's missing), Structure (ordering), Actionability (can behavior be derived), Accuracy (factual correctness) are distinct. Pass.
- Item placement: "Missing `governanaceTriangle/` directory" fits Branch 1 (Completeness). Does not fit Structure, Actionability, or Accuracy. Pass.

---

## Phase 2: Hypothesize

**Initial governing thought hypothesis:** "The AGENTS.md is structurally sound and covers architecture rules well, but has actionable gaps that would cause an AI agent to make preventable errors."

**Branch hypotheses:**

| Branch | Hypothesis | Confirm if | Kill if |
|---|---|---|---|
| Completeness | Directories and rules are missing from the guide | Workspace has files/dirs not mentioned in AGENTS.md | Every workspace directory and architectural rule is covered |
| Structure | Information ordering doesn't prioritize agent needs | "How to verify" (test commands) is buried below architecture docs | High-frequency actions are near the top |
| Actionability | Anti-patterns are not surfaced, only positive rules | No "what NOT to do" section exists | Anti-patterns are explicitly listed |
| Accuracy | Content matches the actual codebase | Directory listings and rule descriptions match filesystem and source docs | Factual errors found |

---

## Phase 3: Evidence

### Branch 1: Completeness Gaps (3 findings)

| ID | Gap | Impact | Recommendation |
|---|---|---|---|
| G1 | **`governanaceTriangle/` directory** exists in workspace but is not mentioned at all | Agent will ignore or misplace files related to governance triangle | Add to Key Directories table |
| G2 | **`prompts/codeReviewer/` and `prompts/includes/`** subdirectories exist but aren't documented | Agent will create prompts in wrong location or miss include patterns | Add subdirectory naming conventions |
| G3 | **`utils/` directory** exists in workspace but has no AGENTS.md guidance | Agent may place code there vs `services/`, creating ambiguity | Clarify `utils/` role or note it as deprecated/separate |

### Branch 2: Missing Architectural Guidance (3 findings)

| ID | Gap | Impact | Recommendation |
|---|---|---|---|
| A1 | **Meta-layer dependency rules** are absent | Agent may create upward dependencies from `meta/` to `orchestration/` — Anti-Pattern 8 from STYLE_GUIDE_LAYERING | Add meta-layer row to dependency table: `Meta → Services`, `Meta → Trust Kernel`, forbidden `Meta → Orchestration` |
| A2 | **Patterns H6, H7, V3, V4, V5** from the catalog are omitted | Agent won't know about Long-term Memory, Human Feedback, RAG, Multi-Agent Deliberation, or Reflection patterns | Add at minimum a reference note that H3–H7 and V1–V6 exist |
| A3 | **Signed vs. unsigned field boundary** is mentioned but no field list | Agent modifying `AgentFacts` won't know which fields to sign | Add a brief field classification or reference to `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` §Signed vs Unsigned |

### Branch 3: Structural/Ordering Issues (2 findings)

| ID | Issue | Impact | Recommendation |
|---|---|---|---|
| S1 | **"Running the Agent" section** is near the bottom — an agent needing to test changes must scroll past architecture docs | For AI agents, "how to verify" is high-priority context | Move to top (after Project Overview) or add a one-liner test command early |
| S2 | **No explicit anti-patterns section** — STYLE_GUIDE_LAYERING has 9 anti-patterns; none surfaced here | Agent will violate rules that are only stated as "what to do" rather than "what NOT to do" | Add top 3–5 critical anti-patterns: trust types inside a service, H→H coupling, hardcoded prompts, upward governance calls |

### Branch 4: Accuracy Verified (Pass)

Cross-referencing the AGENTS.md against the actual directory listing: all listed files in `trust/`, `services/`, `components/`, `orchestration/` match the actual filesystem. The dependency rules match `STYLE_GUIDE_LAYERING.md`. The ReAct cycle description matches `PLAN_v2.md`. **No factual errors found.**

---

## Phase 4: Synthesize

### Governing Thought

**The AGENTS.md is structurally sound and covers architecture rules well, but has five actionable gaps — missing governance triangle context, absent prompt subdirectory guidance, no `meta/` layer rules, incomplete pattern catalog, and lack of an explicit "what NOT to do" section — that would cause an AI agent to make preventable errors.**

**Confidence:** 0.82. Strong evidence on completeness gaps and structural issues. Accuracy is confirmed. The actionability assessment is based on reasoning about agent behavior rather than observed failures, which introduces moderate uncertainty.

### Key Arguments

#### Arg 1: Completeness — Three workspace artifacts are invisible to agents

The `governanaceTriangle/` directory, `prompts/` subdirectories (`codeReviewer/`, `includes/`), and `utils/` directory all exist in the workspace but receive no mention in the AGENTS.md. An AI agent following the guide would not know these exist, leading to misplaced files, missed include patterns, or ambiguity about where to place utility code vs. service code.

**So-what chain:**
- Fact: Three directories exist in the workspace but are absent from AGENTS.md
- Impact: Agent has no guidance for files touching these directories
- Implication: Files get placed incorrectly, violating architectural conventions
- Connection: The AGENTS.md fails its core purpose of preventing architectural violations

#### Arg 2: Architectural Guidance — Meta-layer rules and full pattern catalog are missing

The dependency table covers four layers but omits the meta-layer entirely. The design patterns table lists 8 of 13 patterns from the full catalog. The signed/unsigned metadata convention is mentioned without the field classification needed to apply it. These omissions create blind spots where an agent must guess rather than follow rules.

**So-what chain:**
- Fact: Meta-layer dependency rules, 5 patterns, and field classifications are absent
- Impact: Agent has no guardrails for meta-layer imports or knowledge of memory/RAG/feedback patterns
- Implication: Upward dependency violations (Anti-Pattern 8) and missed pattern opportunities
- Connection: The guide covers the common case but fails on less-frequent but equally important architectural decisions

#### Arg 3: Structure — Verification commands are buried and anti-patterns are absent

The test command (`pytest tests/ -q`) appears only in the "Running the Agent" section near the bottom. No anti-patterns are surfaced despite the source documentation containing 9 detailed anti-patterns. AI agents benefit disproportionately from negative examples ("never do X") because they reduce the search space of plausible actions.

**So-what chain:**
- Fact: Test commands are at line 142; no anti-patterns section exists
- Impact: Agent may not verify changes; will lack "what NOT to do" heuristics
- Implication: Unverified changes ship; known anti-patterns get repeated
- Connection: The guide optimizes for understanding over action, when agents need both

#### Arg 4: Accuracy — Content matches the codebase (no errors found)

All directory names, file lists, dependency rules, and architectural descriptions in AGENTS.md match the actual filesystem and source documentation. This is a strength: the guide does not mislead.

---

## Validation Log

| Check | Result | Details |
|---|---|---|
| Completeness | **Partial** | 3 directories missing (`governanaceTriangle/`, `prompts/` subdirs, `utils/`), meta-layer rules absent |
| Non-Overlap | Pass | Each argument addresses a distinct dimension: completeness, guidance depth, structural ordering, factual accuracy |
| Item Placement | Pass | G1–G3 fit only Arg 1; A1–A3 fit only Arg 2; S1–S2 fit only Arg 3; accuracy findings fit only Arg 4 |
| So What? | Pass | Every finding chains to "agent makes preventable errors" |
| Vertical Logic | Pass | "Why are there gaps?" → because directories are missing (Arg 1), rules are missing (Arg 2), ordering deprioritizes action (Arg 3). Each answers the governing thought. |
| Remove One | Pass | Removing Arg 4 (accuracy) still leaves 3 arguments supporting the governing thought. Removing any single gap argument leaves 2 others. |
| Never-One | Pass | No single-child groupings in the analysis |
| Mathematical | N/A | Qualitative evaluation — no numerical claims to verify |

---

## Recommended Fixes (Priority Order)

| Priority | Fix | Effort | Impact |
|---|---|---|---|
| 1 | Add **Critical Anti-Patterns** section (top 5 from STYLE_GUIDE_LAYERING) | Low | High — prevents the most common agent errors |
| 2 | Add **meta-layer dependency rules** to the dependency table | Low | High — closes an architectural blind spot |
| 3 | Add **`governanaceTriangle/`** and **`utils/`** to Key Directories | Low | Medium — eliminates workspace ambiguity |
| 4 | Add **`prompts/` subdirectory conventions** (`codeReviewer/`, `includes/`) | Low | Medium — prevents prompt misplacement |
| 5 | Add reference note for **patterns H6–H7, V3–V5** (full catalog pointer) | Low | Medium — agents know patterns exist even if details are in the catalog |
| 6 | Move **test command** to Project Overview or add a one-liner early | Low | Low-Medium — faster verification loop |

---

## Gaps and Limitations

### Untested Hypotheses

- **Agent behavior prediction:** The impact assessments assume how an AI agent would behave when encountering missing guidance. Actual agent behavior may differ. Validating this would require running an agent on tasks that touch the gap areas and observing whether errors occur.

### Known Weaknesses

- **Severity:** Low. The review is based on structural analysis of the document against the codebase. It does not include usability testing with actual AI agents processing the AGENTS.md.

---

## Cross-Branch Interactions

- **Completeness × Actionability:** The missing `utils/` guidance (Branch 1) interacts with the missing anti-pattern for "trust types inside a service" (Branch 3). An agent that doesn't know `utils/` exists AND doesn't know the anti-pattern may place shared types inside `services/`, violating the trust kernel rules. Both gaps must be fixed together for full protection.
