# AGENTS.md Improvement Recommendations

**Analysis method:** Pyramid Principle / MECE structured evaluation
**Source document:** `docs/AGENTS_MD_BEST_PRACTICES_RESEARCH.md`
**Subject:** Apply research findings to improve `AGENTS.md` for the ReAct Agent workspace
**Date:** 2026-04-17

---

## Phase 1: Decompose

**Restated question:** "Given the best-practices research (ETH Zurich, GitHub 2,500-repo analysis, openai/codex, apache/airflow, vercel/next.js, Amp manual), which specific changes to our AGENTS.md will maximize agent task success while minimizing token overhead?"

**Problem type:** Design (something must be built; find the best approach)

**Issue tree:**

```
Root: How should we restructure AGENTS.md?
├── Branch 1: Content — What to add, remove, or rewrite
│   ├── 1a: Content to ADD (missing from current file)
│   ├── 1b: Content to REMOVE (inferable, redundant, adds token cost)
│   └── 1c: Content to REWRITE (exists but in wrong form)
├── Branch 2: Structure — How to order and organize sections
│   ├── 2a: Section ordering (what comes first)
│   └── 2b: File splitting (root vs. subtree AGENTS.md)
├── Branch 3: Amp-Specific Features — What Amp capabilities to leverage
│   ├── 3a: @-mentions for deep context injection
│   ├── 3b: Glob-scoped guidance files
│   └── 3c: Checks and skills integration
```

**Ordering type:** Degree (highest-impact changes first)

**Validation:**
- Completeness: Content (what), Structure (how organized), Amp Features (tool leverage) cover all actionable dimensions. Pass.
- Non-overlap: Adding content ≠ reordering sections ≠ leveraging Amp features. Pass.
- Item placement: "Add a Boundaries section" fits 1a (content to ADD). "Move commands to top" fits 2a (ordering). "Use @docs/ references" fits 3a (@-mentions). Pass.

---

## Phase 2: Hypothesize

**Governing thought hypothesis:** "Seven changes — reorder sections, add boundaries/anti-patterns, trim inferable content, switch to imperative tone, add @-mentions, create subtree files, and add an architecture invariants section — will bring our AGENTS.md in line with the patterns proven by the top 3 reference repositories."

---

## Phase 3: Evidence (Research → Current File Gap Analysis)

### Branch 1a: Content to ADD

| ID | Missing Content | Evidence Source | Impact |
|---|---|---|---|
| ADD-1 | **Three-tier Boundaries section** (✅ Always / ⚠️ Ask first / 🚫 Never) | GitHub Blog: "the most valuable section for agents"; vercel/next.js, apache/airflow both have this | **Critical** — without it, agents make destructive mistakes |
| ADD-2 | **Numbered architecture invariants** | apache/airflow: 8 numbered invariants; prevents agents from violating boundaries in generated code | **High** — our dependency table is descriptive, not imperative |
| ADD-3 | **Critical anti-patterns with rationale** | openai/codex: "prohibition with rationale"; our STYLE_GUIDE_LAYERING has 9 anti-patterns, zero surfaced | **High** — agents need "what NOT to do" more than "what to do" |
| ADD-4 | **Agent identity/commit policy** | apache/airflow: "NEVER add Co-Authored-By with yourself"; vercel/next.js: "Do NOT add Generated with Claude Code footers" | **Low** — nice to have for this project stage |
| ADD-5 | **`governanaceTriangle/` and `utils/` directories** | Previous review (AGENTS_MD_REVIEW.md): 3 directories exist but are undocumented | **Medium** — prevents file misplacement |

### Branch 1b: Content to REMOVE or TRIM

| ID | Content to Trim | Evidence Source | Impact |
|---|---|---|---|
| TRIM-1 | **Key Directories table** — 13 rows listing every file in each dir | ETH Zurich: "Architecture overviews agents can discover independently add token cost without improving performance" | **High** — agents read directory listings themselves; file-level detail wastes tokens |
| TRIM-2 | **Design Patterns table** — 8 rows of pattern descriptions | ETH Zurich: same rationale; agents can read `STYLE_GUIDE_PATTERNS.md` when referenced via @-mention | **Medium** — keep pattern IDs and one-line rules, drop full descriptions |
| TRIM-3 | **Orchestration — ReAct Cycle section** — node-by-node delegation mapping | ETH Zurich: inferable from reading `react_loop.py`; Augment Code: "architectural overviews do not provide effective overviews" | **Medium** — agents will read the actual code |
| TRIM-4 | **Testing Strategy pyramid table** — repeats content from `tdd_agentic_systems_prompt.md` | ETH Zurich: "Anything already in docs = Redundant" | **Low** — keep the key rules, drop the table; reference the research doc |

### Branch 1c: Content to REWRITE

| ID | Rewrite Needed | Evidence Source | Current Form → Target Form |
|---|---|---|---|
| RW-1 | **Tone: suggestive → imperative** | apache/airflow: "Run ruff format **immediately** after editing" | "Run tests: `cd agent && pytest tests/ -q`" → "Run `pytest tests/ -q` immediately after making changes. Fix all failures before proceeding." |
| RW-2 | **Dependency rules: table → numbered invariants** | apache/airflow: numbered rules; openai/codex: hard targets | Allowed/Forbidden table → "1. Components MUST NOT import from orchestration. 2. Trust kernel MUST NOT import from any layer above. ..." |
| RW-3 | **Trust Kernel rules: criteria list → gate checklist** | openai/codex: "Target modules under 500 LoC. Hard limit 800 LoC." | Abstract criteria → actionable checklist with concrete examples |

### Branch 2a: Section Ordering

| ID | Change | Evidence Source | Rationale |
|---|---|---|---|
| ORD-1 | **Commands immediately after Project Overview** | GitHub Blog: "Put commands early; the agent references them repeatedly"; all 3 reference repos do this | Currently at line 129 (bottom); should be line 7 |
| ORD-2 | **Boundaries section in upper half** | GitHub Blog: "the most valuable section for agents" | Currently absent; should be before Key Directories |
| ORD-3 | **Key Documents at the bottom** | All reference repos: reference links are last | Already at bottom; correct. No change. |

### Branch 2b: File Splitting

| ID | Change | Evidence Source | Rationale |
|---|---|---|---|
| SPLIT-1 | **Current file is 161 lines** — within the 150-200 line threshold | Augment Code: "Start with a single file; split when it exceeds 150-200 lines" | **No split needed yet.** After adding boundaries + anti-patterns, re-evaluate. |
| SPLIT-2 | **Plan for future subtree AGENTS.md** | vercel/next.js: skills system; Amp manual: nested AGENTS.md; snarktank/untangle: 7 directory-specific files | Document as a future action when layer-specific rules grow. E.g., `trust/AGENTS.md` for trust kernel development rules. |

### Branch 3a–3c: Amp-Specific Features

| ID | Feature | Evidence Source | Recommendation |
|---|---|---|---|
| AMP-1 | **@-mentions for deep context** | Amp manual: `@docs/style.md`; keeps AGENTS.md lean while providing deep context on demand | Replace Key Documents table with @-mentions: `@docs/STYLE_GUIDE_LAYERING.md`, `@docs/STYLE_GUIDE_PATTERNS.md` |
| AMP-2 | **Glob-scoped guidance** | Amp manual: separate files with `globs` frontmatter | **Defer.** Useful when layer-specific rules are extensive enough to warrant separate files. |
| AMP-3 | **Checks for code review** | Amp manual: `.agents/checks/` with YAML frontmatter | Create `architecture-boundary` check that verifies layer dependency rules during `amp review`. **Defer to separate task.** |

---

## Phase 4: Synthesize

### Governing Thought

**Apply 7 changes in priority order: (1) move commands to top, (2) add three-tier boundaries, (3) add numbered architecture invariants, (4) add critical anti-patterns with rationale, (5) switch to imperative tone, (6) replace Key Documents with @-mentions, (7) trim inferable content — to produce an AGENTS.md aligned with the patterns proven by openai/codex, apache/airflow, and vercel/next.js while respecting the ETH Zurich finding that only non-inferable content improves agent performance.**

**Confidence:** 0.88. Strong evidence from 5 independent sources (ETH Zurich study, GitHub 2,500-repo analysis, 3 reference repos). Minor gap: we have not A/B tested the changes on our specific codebase to measure actual agent performance improvement.

---

### Prioritized Recommendations

#### Priority 1 — CRITICAL (Do First)

##### R1: Move Commands to Top (ORD-1)

**What:** Move "Running the Agent" section to immediately after "Project Overview". Rename to "Key Commands".

**Why (evidence):** GitHub Blog analysis of 2,500 repos: "Put commands early; the agent references them repeatedly throughout a task." All three reference repos (openai/codex, apache/airflow, vercel/next.js) place commands in the first or second section.

**Current state:** Commands are at line 129 — bottom 20% of the file.

**Imperative rewrite:**
```markdown
## Key Commands

Run these after making changes. Fix all failures before proceeding.

- **Install:** `pip install -e ".[dev]"`
- **Test:** `pytest tests/ -q` — run immediately after changes
- **Run:** `python -m agent.cli "What is the capital of France?"`
- **Docker:** `docker build -t react-agent . && docker run -e OPENAI_API_KEY=$OPENAI_API_KEY react-agent "What is 2+2?"`
```

---

##### R2: Add Three-Tier Boundaries Section (ADD-1)

**What:** Add a Boundaries section with ✅ Always / ⚠️ Ask first / 🚫 Never tiers.

**Why (evidence):** GitHub Blog: "the most valuable section for agents." vercel/next.js and apache/airflow both structure boundaries this way. Without it, agents make destructive mistakes that are costly to undo.

**Proposed content:**
```markdown
## Boundaries

### ✅ Always
- Run `pytest tests/ -q` after making changes
- Use `PromptService.render_prompt()` for all prompts — no hardcoded strings
- Record every LLM call via `eval_capture.record()` with `user_id` and `task_id`
- Create `.j2` files in `prompts/` for new prompts

### ⚠️ Ask first
- Adding new dependencies to `pyproject.toml`
- Modifying trust kernel types in `trust/models.py` (triggers re-signing)
- Adding new graph nodes to `orchestration/react_loop.py`
- Creating new horizontal services

### 🚫 Never
- Import from `orchestration/` in `components/` or `services/`
- Import from `langgraph` or `langchain` in `components/` or `trust/`
- Place shared trust types inside a service module — they belong in `trust/`
- Hardcode model names — reference tiers from `services/llm_config.py`
- Commit secrets, API keys, or `.env` files
- Run live LLM calls in CI test suites
- Create peer imports between components (e.g., `router` importing `evaluator`)
```

---

##### R3: Add Numbered Architecture Invariants (ADD-2, RW-2)

**What:** Replace the Allowed/Forbidden dependency table with numbered invariants in imperative form.

**Why (evidence):** apache/airflow uses 8 numbered invariants ("workers never access metadata DB directly"). Numbered rules are harder to ignore than table rows. openai/codex uses hard numerical targets. The imperative form ("MUST NOT") outperforms the descriptive form ("Forbidden") per the apache/airflow pattern.

**Proposed content:**
```markdown
## Architecture Invariants — STRICTLY ENFORCED

Tests in `tests/architecture/` verify these. Never break them.

1. **Dependencies flow downward only.** Orchestration → Components → Services → Trust Kernel. Never upward.
2. **Trust kernel has ZERO outward dependencies.** `trust/` imports only stdlib + Pydantic. No I/O, no logging, no network.
3. **Components are framework-agnostic.** `components/` MUST NOT import `langgraph` or `langchain`.
4. **Services are framework-agnostic.** `services/` MUST NOT import `langgraph` or `langchain` (exception: `llm_config.py` wraps `ChatLiteLLM`).
5. **No peer imports between components.** `router.py` MUST NOT import from `evaluator.py` or vice versa.
6. **Orchestration nodes are thin wrappers.** All logic delegates to `components/` and `services/`. No domain logic in `orchestration/`.
7. **Services MUST NOT import from components.** Horizontal services have no knowledge of domain logic.
8. **Meta-layer (`meta/`) MUST NOT import from orchestration.** It reads logs and config, never calls the graph directly.
```

---

#### Priority 2 — HIGH (Do Next)

##### R4: Add Critical Anti-Patterns with Rationale (ADD-3)

**What:** Surface the top 5 anti-patterns from `STYLE_GUIDE_LAYERING.md` with *why* they fail.

**Why (evidence):** openai/codex: "prohibition with rationale" — explains why `codex-core` shouldn't grow. Agents obey rules better when they understand the consequence of violation. Our style guide has 9 anti-patterns; zero are surfaced in AGENTS.md.

**Proposed content:**
```markdown
## Critical Anti-Patterns

### 🚫 AP-1: Trust Types Inside a Service
Placing `AgentFacts` or `Policy` inside `services/identity_service.py` instead of `trust/models.py`.
**Why it fails:** Other services must import from a peer, creating hidden coupling. Every new consumer adds another cross-service dependency.
**Fix:** Shared trust types always live in `trust/`. Services import from the foundation.

### 🚫 AP-2: Horizontal-to-Horizontal Coupling
`authorization_service` calling `identity_service.get()` directly.
**Why it fails:** Two services become coupled; testing one requires mocking the other; changes to identity API break authorization.
**Fix:** The orchestrator fetches data and passes it as a parameter. Services receive data, not service dependencies.

### 🚫 AP-3: Hardcoded Prompts
Writing `prompt = f"You are a math educator..."` in Python code.
**Why it fails:** Bypasses logging, prevents non-engineers from editing prompts, makes A/B testing impossible.
**Fix:** Create a `.j2` file in `prompts/` and call `PromptService.render_prompt()`.

### 🚫 AP-4: Upward Governance Calls
`meta/lifecycle_manager.py` importing from `orchestration/`.
**Why it fails:** Creates circular dependency. Governance depends on orchestration which depends on services which governance also uses.
**Fix:** Governance emits `TrustTraceRecord` events. A separate consumer handles orchestration actions.

### 🚫 AP-5: Domain Logic in Orchestration Nodes
Putting routing heuristics directly in `orchestration/react_loop.py`.
**Why it fails:** Logic becomes coupled to LangGraph. Breaks the framework-swap fallback (PLAN_v2.md Phase 4).
**Fix:** All logic lives in `components/` or `services/`. Orchestration nodes are thin wrappers — max 10-15 lines each.
```

---

##### R5: Switch to Imperative Tone (RW-1)

**What:** Rewrite passive/descriptive statements as direct commands.

**Why (evidence):** apache/airflow: "Run ruff format + ruff check --fix **immediately** after editing any Python file." Imperative form ("Run X") outperforms suggestive form ("Tests can be run with...") because agents treat imperative statements as actionable instructions rather than informational context.

**Examples:**

| Current (Descriptive) | Proposed (Imperative) |
|---|---|
| "Run tests: `cd agent && pytest tests/ -q`" | "Run `pytest tests/ -q` immediately after making changes. Fix all failures before proceeding." |
| "Architecture tests in `tests/architecture/` enforce these rules." | "Run `pytest tests/architecture/ -q` to verify layer boundaries. These tests MUST pass." |
| "All prompts in `prompts/*.j2`, rendered via `PromptService.render_prompt()`" | "Create all prompts as `.j2` files in `prompts/`. Render via `PromptService.render_prompt()`. Never hardcode prompt strings in Python." |

---

#### Priority 3 — MEDIUM (Do After)

##### R6: Replace Key Documents with @-Mentions (AMP-1)

**What:** Replace the Key Documents table with Amp @-mention references. This keeps AGENTS.md lean while allowing the agent to pull in deep context when needed.

**Why (evidence):** Amp manual: "@-mentions in AGENTS.md let you reference other files as context." ETH Zurich: inferable content adds cost without improving performance. @-mentions are loaded on demand, not always.

**Proposed content:**
```markdown
## References

For deep context on architecture and patterns, see:

- @docs/STYLE_GUIDE_LAYERING.md — four-layer architecture rules and anti-patterns
- @docs/STYLE_GUIDE_PATTERNS.md — design patterns catalog (H1-H7, V1-V6)
- @docs/Architectures/FOUR_LAYER_ARCHITECTURE.md — trust foundation, hexagonal ports, policy engines
- @docs/TRUST_FRAMEWORK_ARCHITECTURE.md — seven-layer trust framework
- @research/tdd_agentic_systems_prompt.md — testing pyramid for agentic systems
```

---

##### R7: Trim Inferable Content (TRIM-1 through TRIM-4)

**What:** Reduce the Key Directories table from 13 rows to ~6 (only directories with non-obvious purpose). Remove the Orchestration — ReAct Cycle section (inferable from code). Shorten the Design Patterns table to IDs and one-line rules only.

**Why (evidence):** ETH Zurich: "architectural overviews do not provide effective overviews." Agents read directory listings and source code directly. Redundant content increases inference cost by 20-23% with no performance improvement.

**Specific trims:**
- **Key Directories:** Keep `trust/`, `services/`, `components/`, `orchestration/`, `prompts/`. Drop `tests/`, `docs/`, `research/`, `cache/`, `logs/` (agents discover these).
- **Orchestration section:** Remove entirely. The node delegation mapping is inferable from `react_loop.py`.
- **Testing Strategy table:** Keep the 4 key rules. Drop the pyramid table (reference `@research/tdd_agentic_systems_prompt.md` instead).

---

#### Priority 4 — DEFERRED (Future Tasks)

| ID | Task | Trigger |
|---|---|---|
| D1 | Create subtree `trust/AGENTS.md` | When trust kernel development rules exceed 20 lines |
| D2 | Create `.agents/checks/architecture-boundary.md` | When using `amp review` regularly |
| D3 | Create glob-scoped guidance files (e.g., `docs/prompt-authoring-rules.md` with `globs: ['prompts/**/*.j2']`) | When prompt-specific rules grow |
| D4 | Add agent identity/commit policy | When multiple agents/contributors work concurrently |

---

### Validation Log

| Check | Result | Details |
|---|---|---|
| Completeness | Pass | Content (add/remove/rewrite), Structure (ordering/splitting), Amp features (3 categories) cover all actionable dimensions |
| Non-Overlap | Pass | R1 (ordering) ≠ R2 (new section) ≠ R3 (rewrite existing) ≠ R4 (new section) ≠ R5 (tone) ≠ R6 (tool feature) ≠ R7 (trim). Each is independently actionable. |
| Item Placement | Pass | "Move commands" fits only R1. "Add boundaries" fits only R2. "@-mentions" fits only R6. |
| So What? | Pass | Every recommendation chains to "agent produces fewer errors with less token overhead" |
| Vertical Logic | Pass | Why these 7 changes? Because they address the 7 gaps between current state and proven best practices (ETH Zurich, GitHub analysis, reference repos). |
| Remove One | Pass | Removing any single recommendation still leaves 6 improvements. R2 (Boundaries) is highest-individual-impact but the others independently add value. |
| Never-One | Pass | No single-child groupings |
| Mathematical | N/A | Qualitative design problem |

---

### Gaps and Known Weaknesses

| Gap | Severity | Impact on Confidence |
|---|---|---|
| No A/B testing on our codebase | Medium | We rely on external evidence (ETH Zurich, GitHub analysis) rather than measured improvement on our specific project |
| ETH Zurich study focused on SWE-bench tasks | Low | Our project (agentic framework) differs from typical SWE-bench repos, but the token overhead findings are generalizable |
| "Lost in the middle" threshold is approximate | Low | 150-200 line split threshold is a heuristic; our file may work fine at 180 lines post-changes |

---

### Cross-Branch Interactions

- **R7 (trim) enables R1 (reorder):** Removing inferable content makes room for commands at the top without increasing file length past the 200-line threshold.
- **R6 (@-mentions) enables R7 (trim):** @-mentions let us remove the Key Documents table and reference docs without losing access to that information.
- **R2 (boundaries) + R4 (anti-patterns):** Boundaries say "never do X." Anti-patterns explain "why X fails." Together they provide both the rule and the rationale. Separated, either is weaker.

---

### Estimated Final File Length

| Section | Lines (est.) |
|---|---|
| Project Overview | 3 |
| Key Commands | 8 |
| Architecture Invariants | 15 |
| Framework Import Discipline | 6 |
| Key Directories (trimmed) | 10 |
| Design Patterns (IDs + one-liners) | 12 |
| Trust Kernel Rules | 8 |
| Testing Rules (key rules only) | 8 |
| Security Model | 6 |
| Development Conventions | 10 |
| Critical Anti-Patterns | 30 |
| Boundaries (three-tier) | 20 |
| References (@-mentions) | 8 |
| **Total** | **~144 lines** |

This is under the 150-line threshold, leaving headroom for future additions before a split is needed.
