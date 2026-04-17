# Pyramid Principle Review: TDD Coverage in AGENTS.md

**Analysis method:** Pyramid Principle / MECE structured evaluation
**Source:** `research/pyramid_react_system_prompt.md`
**Date:** 2026-04-17
**Subject:** Gap analysis between `research/tdd_agentic_systems_prompt.md` (1,544-line TDD reference) and TDD guidance surfaced in `AGENTS.md` (9 lines)

---

## Phase 1: Decompose

**Restated question:** "What critical TDD guidance from the 1,544-line TDD reference document is not surfaced in AGENTS.md, and which gaps would cause an AI agent to write incorrect, misaligned, or anti-pattern-laden tests?"

**Problem type:** Evaluation

**Issue tree:**

```
Root: Is TDD guidance in AGENTS.md sufficient?
├── Branch 1: Coverage — Which TDD concepts are present vs. absent?
├── Branch 2: Actionability — Can an agent derive correct test-writing behavior from what's there?
├── Branch 3: Alignment — Does the AGENTS.md terminology match the TDD doc's framework?
```

**Ordering type:** Degree (most impactful gap first)

**Validation:**
- Completeness: Coverage (what's missing), Actionability (can behavior be derived), Alignment (terminology consistency) are distinct and collectively exhaustive for evaluating TDD guidance quality. Pass.
- Non-overlap: Coverage = content presence. Actionability = behavioral derivability. Alignment = vocabulary consistency. No overlap. Pass.

---

## Phase 2: Hypothesize

**Initial governing thought hypothesis:** "The AGENTS.md surfaces 5 of the TDD doc's 40+ actionable rules, omitting the testing anti-patterns, pytest marker conventions, test layer dependency rules, and the pattern catalog — causing agents to write structurally correct but strategically misaligned tests."

**Branch hypotheses:**

| Branch | Hypothesis | Confirm if | Kill if |
|---|---|---|---|
| Coverage | >70% of TDD doc's actionable rules are absent from AGENTS.md | Counting rules present vs. absent confirms >70% gap | All major categories are represented |
| Actionability | An agent reading only AGENTS.md would not know which assertion type to use per layer | No assertion-type guidance exists in AGENTS.md | Assertion types are documented per layer |
| Alignment | AGENTS.md uses different terms than the TDD doc for the same concepts | Dir names in AGENTS.md don't match TDD doc's architecture mapping | Terminology is consistent |

---

## Phase 3: Evidence

### Branch 1: Coverage Gaps (8 findings)

The TDD doc contains **7 major sections** with distinct actionable content. Cross-referencing against AGENTS.md:

| TDD Doc Section | Lines | Key Content | In AGENTS.md? | Gap ID |
|---|---|---|---|---|
| **Four Operating Principles** (lines 9-14) | 6 | Test at uncertainty boundary, layer-aware design, behavior over implementation, failure paths first | **Partial** — only "failure paths first" is surfaced | G1 |
| **Pyramid Rules** (lines 64-70) | 7 | Volume, speed, CI, flake, diagnostic rules | **Partial** — CI rule and flake rule present; volume/speed/diagnostic absent | G2 |
| **Protocols A-D** (lines 84-569) | 485 | Per-layer TDD workflows with entry/exit criteria, test categories (A1-A5, B1-B5, C1-C3, D1-D3) | **Absent** — no protocol reference at all | G3 |
| **Test Pattern Catalog** (lines 573-810) | 237 | 11 reusable patterns with layer, when-to-use, anti-pattern-prevented | **Absent** — no patterns referenced | G4 |
| **Testing Anti-Patterns** (lines 814-976) | 162 | 7 anti-patterns: tautological, mock addiction, determinism theater, eval overfitting, live LLM in CI, gap blindness, cross-layer dependency leak | **Absent** — zero testing anti-patterns surfaced (AGENTS.md has 5 architecture anti-patterns but no testing ones) | G5 |
| **Self-Validation Suite** (lines 980-1063) | 83 | 8 quality checks: coverage completeness, layer alignment, dependency compliance, failure path coverage, anti-pattern scan, contract coverage, determinism audit, CI/CD compliance | **Absent** | G6 |
| **pytest Configuration** (lines 1422-1509) | 87 | Marker definitions, test dir structure, CI pipeline config | **Partially implemented** — `pyproject.toml` has markers, but AGENTS.md doesn't reference them | G7 |
| **Architecture-to-Pyramid Mapping** (lines 72-80) | 9 | Which modules belong to which test layer | **Absent** — AGENTS.md says "L1 (trust/)" and "L2 (services/)" but doesn't map components or orchestration | G8 |

### Branch 2: Actionability Gaps (4 findings)

| ID | Scenario | Agent Behavior with Current AGENTS.md | Correct Behavior per TDD Doc |
|---|---|---|---|
| A1 | Agent writes test for `trust/signature.py` | Knows "Pure TDD, property-based, exact assertions" — correct strategy, but no guidance on *what* to test (schema validation? roundtrip? tampering?) | Use Protocol A: test categories A1 (schema), A2 (pure function), A3 (enum), A4 (state machine), A5 (backward compat) |
| A2 | Agent writes test for `services/guardrails.py` | Knows "Contract-driven TDD, mock I/O" — correct strategy, but doesn't know to use `freezegun` for time-dependent tests or `tmp_path` for filesystem | Use Protocol B: time-mocking (B3), record/replay (B5), contract tests (B4) |
| A3 | Agent writes test for `components/router.py` | No L3 guidance at all in AGENTS.md | Use Protocol C: mocked LLM (C1), trajectory evals (C2), rubric-based evals (C3) |
| A4 | Agent writes test with 5 mocks | No guidance on mock limits or anti-patterns | Anti-Pattern 2 (Mock Addiction): >3 mocks signals over-mocking; prefer in-memory implementations |

### Branch 3: Alignment Gaps (2 findings)

| ID | AGENTS.md Term | TDD Doc Term | Mismatch Impact |
|---|---|---|---|
| AL1 | `services/` (architecture) | `utils/` (TDD doc L2 mapping, line 77) | TDD doc maps L2 to `utils/` but the actual codebase uses `services/`. Agent following TDD doc literally would look for wrong directory. **Note:** The TDD doc uses the composable_app reference naming (`utils/`), not the actual project naming (`services/`). |
| AL2 | `components/` (architecture) | `agents/` (TDD doc L3 mapping, line 78) | Same issue — TDD doc says `agents/`, actual project uses `components/`. |

---

## Phase 4: Synthesize

### Governing Thought

**The AGENTS.md Testing Rules section covers 2 of 7 major TDD categories (pyramid rules and CI policy), but omits the 5 highest-impact categories — testing anti-patterns, test pattern catalog, per-layer protocols with test categories, the self-validation suite, and the architecture-to-pyramid module mapping — leaving agents without the "what to test" and "what NOT to do" guidance needed to write strategically correct tests.**

**Confidence:** 0.85. Strong evidence from direct line-by-line comparison. Minor gap: we have not observed actual agent test-writing failures caused by these omissions.

### Key Arguments

#### Arg 1: Testing Anti-Patterns Are Completely Missing (Highest Impact)

The TDD doc defines 7 testing anti-patterns (lines 814-976). The AGENTS.md has 5 architecture anti-patterns (AP-1 through AP-5) but **zero testing anti-patterns**. An AI agent generating tests is highly susceptible to:

- **Tautological tests** (AP-1): reimplementing `compute_signature()` with SHA256 in the test
- **Mock addiction** (AP-2): using 5+ mocks instead of in-memory implementations
- **Determinism theater** (AP-3): asserting exact LLM output strings with `temperature=0`
- **Gap blindness** (AP-6): writing only happy-path tests for trust gates

**So-what chain:**
- Fact: 7 testing anti-patterns documented; 0 surfaced in AGENTS.md
- Impact: Agent writes tests that pass but verify nothing (tautological) or break on model change (determinism theater)
- Implication: Test suite provides false confidence; architectural violations go undetected
- Connection: The "failure paths first" rule in AGENTS.md is the only defense — insufficient alone

#### Arg 2: Per-Layer Test Categories Are Missing (Medium-High Impact)

The TDD doc defines 16 test categories across 4 protocols (A1-A5, B1-B5, C1-C3, D1-D3). AGENTS.md gives the *strategy name* per layer but not the *test categories*. An agent knows to use "Pure TDD" for `trust/` but doesn't know the 5 specific categories: schema validation, pure function correctness, enum completeness, state machine invariants, backward compatibility.

**So-what chain:**
- Fact: 16 test categories exist; 0 are referenced in AGENTS.md
- Impact: Agent writes ad-hoc tests instead of systematically covering each category
- Implication: Coverage gaps in critical areas (state machine invariants, backward compatibility)

#### Arg 3: The Test Pattern Catalog Is Not Referenced (Medium Impact)

11 reusable test patterns exist (Pattern 1-11) with explicit layer targeting and anti-pattern prevention mappings. None are referenced in AGENTS.md. Agents cannot use patterns they don't know exist.

**So-what chain:**
- Fact: 11 patterns exist; 0 referenced
- Impact: Agent reinvents patterns (e.g., writes its own record/replay instead of using Pattern 5)
- Implication: Inconsistent test infrastructure; harder to maintain

#### Arg 4: Directory Name Mismatch Creates Confusion (Low-Medium Impact)

The TDD doc uses `utils/` and `agents/` (from the composable_app reference); the actual project uses `services/` and `components/`. An agent reading the TDD doc's architecture mapping would look for `utils/identity_service.py` instead of `services/governance/agent_facts_registry.py`.

---

## Recommended Fixes (Priority Order)

### Priority 1 — CRITICAL

#### R1: Add Testing Anti-Patterns to AGENTS.md

Surface the top 4 testing anti-patterns with detection rules. These are the highest-frequency agent errors.

**Proposed content to add after the existing "Testing Rules" section:**

```markdown
## Testing Anti-Patterns

### 🚫 TAP-1: Tautological Tests
Reimplementing the production algorithm in the test (e.g., computing SHA256 in the test to compare against `compute_signature()`).
**Detect:** Test contains the same logic as the implementation.
**Fix:** Test behavioral properties ("sign then verify is True") or use known test vectors, never the algorithm itself.

### 🚫 TAP-2: Mock Addiction
Using 4+ mocks in a single test. The test verifies mock configuration, not real behavior.
**Detect:** Count mocks per test. >3 is a warning.
**Fix:** Use real in-memory implementations (e.g., `InMemoryIdentityService`). Reserve mocks for truly external systems.

### 🚫 TAP-3: Determinism Theater
Asserting exact LLM output strings with `temperature=0`. Breaks on model updates.
**Detect:** `assertEqual(output, "exact string")` in tests involving LLM calls.
**Fix:** Assert structural properties at L2 (with mock providers). Use rubric-based evals at L3.

### 🚫 TAP-4: Gap Blindness in Tests
Writing only success-path tests for trust gates. A gate that accepts everything is more dangerous than one that rejects everything.
**Detect:** Success tests outnumber failure tests 2:1 for any decision point.
**Fix:** Write the rejection test before the acceptance test. Use failure mode matrices for gates.
```

---

### Priority 2 — HIGH

#### R2: Add Test Category Quick Reference per Layer

Agents need to know *what* to test, not just *how*. Add a compact mapping.

**Proposed content to add to the existing "Testing Rules" section:**

```markdown
### Test Categories by Layer

- **L1 (trust/)**: Schema validation (valid + invalid), pure function correctness, enum completeness, state machine invariants, backward compatibility
- **L2 (services/)**: Registry CRUD + lifecycle, authorization decision matrix, credential TTL (use `freezegun`), policy backend contracts, record/replay fixtures
- **L3 (components/)**: Deterministic behavior (mocked LLM), trajectory evals, rubric-based quality evals
- **L4 (orchestration/, meta/)**: Trust gate failure mode matrix, governance feedback loop simulations, binary outcome scenarios
```

---

### Priority 3 — MEDIUM

#### R3: Add pytest Marker Convention

The `pyproject.toml` already defines markers, but AGENTS.md doesn't tell agents when to use them.

**Proposed content:**

```markdown
### pytest Markers

Tag tests by execution context. CI runs only L1+L2 by default.

- `@pytest.mark.slow` — L3 tests (nightly/weekly)
- `@pytest.mark.simulation` — L4 tests (on-demand)
- `@pytest.mark.live_llm` — tests requiring real LLM API calls (never in CI)
- `@pytest.mark.property` — Hypothesis property-based tests
```

---

#### R4: Add Test Dependency Rule

Tests must follow the same layer import rules as production code.

**Proposed one-liner to add to Testing Rules:**

```markdown
- **Test imports follow layer rules** — `tests/trust/` may only import from `trust/`. `tests/services/` may import from `trust/` and `services/`. Never import from a layer above the code under test.
```

---

### Priority 4 — LOW

#### R5: Note the Directory Name Mapping

The TDD doc uses composable_app naming. Add a translation note.

**Proposed one-liner to add to References:**

```markdown
- @research/tdd_agentic_systems_prompt.md — testing pyramid for agentic systems. **Note:** Doc uses `utils/` → maps to `services/`; `agents/` → maps to `components/` in this project.
```

---

#### R6: Reference the Test Pattern Catalog

Rather than reproducing all 11 patterns, add a pointer.

**Proposed one-liner:**

```markdown
See @research/tdd_agentic_systems_prompt.md §Test Pattern Catalog for 11 reusable patterns (property-based schema, state machine invariant, signature roundtrip, consumer-driven contract, record/replay, mock provider, dependency enforcement, trajectory eval, rubric eval, governance loop simulation, failure mode matrix).
```

---

## Estimated Impact on AGENTS.md

| Addition | Lines | Token Impact |
|---|---|---|
| R1: Testing Anti-Patterns (4 items) | +16 | Non-inferable — agents cannot discover these from code |
| R2: Test Category Quick Reference | +6 | Non-inferable — categories are buried in 485 lines of protocol text |
| R3: pytest Marker Convention | +6 | Semi-inferable from `pyproject.toml` — but agents benefit from explicit guidance |
| R4: Test Dependency Rule | +1 | Non-inferable — not obvious that test files follow production layer rules |
| R5: Directory Name Mapping | +1 | Low impact but prevents confusion |
| R6: Pattern Catalog Reference | +1 | Pointer only — no token overhead |
| **Total** | **+31 lines** | File grows from 158 → ~189 lines (under 200-line threshold) |

---

## Validation Log

| Check | Result | Details |
|---|---|---|
| Completeness | Pass | All 7 major TDD doc sections evaluated against AGENTS.md |
| Non-Overlap | Pass | Coverage (what's present), Actionability (can derive behavior), Alignment (terminology) are distinct |
| Item Placement | Pass | G1-G8 fit only Arg 1-3; AL1-AL2 fit only Arg 4 |
| So What? | Pass | Every finding chains to "agent writes misaligned tests" |
| Vertical Logic | Pass | Why gaps exist → because specific categories are absent (each arg answers the governing thought) |
| Remove One | Pass | Removing any single argument still leaves 3 others supporting the governing thought |
| Never-One | Pass | No single-child groupings |
| Mathematical | N/A | Qualitative evaluation |

---

## Gaps and Limitations

### Untested Hypotheses
- **Agent behavior prediction:** Impact assessments assume how an agent would write tests when encountering missing guidance. Actual behavior may differ. Validation requires running an agent on test-writing tasks with and without the proposed additions.

### Known Weaknesses
- **Severity: Low.** The TDD doc itself is a reference/system prompt for a TDD Analysis Agent, not a developer guide. Some content (output schema, worked examples) is specific to that agent's output format and does not need surfacing in AGENTS.md.

---

## Cross-Branch Interactions

- **Coverage × Actionability:** The absent test categories (Branch 1, G3) directly cause the actionability gap where agents don't know *what* to test (Branch 2, A1-A3). Fixing G3 with a compact reference (R2) addresses both.
- **Coverage × Alignment:** The directory name mismatch (Branch 3, AL1-AL2) would cause agents to misapply the TDD doc's L2/L3 protocols to the wrong directories. R5 resolves this by providing an explicit mapping.
