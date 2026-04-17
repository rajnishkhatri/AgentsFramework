# AGENTS.md Best Practices Research

**Date:** 2026-04-17
**Sources:** Amp manual (ampcode.com), agents.md spec (AAIF/Linux Foundation), GitHub Blog analysis of 2,500+ repos, ETH Zurich study, openai/codex, apache/airflow, vercel/next.js, Augment Code guide, real-world Amp threads

---

## 1. What Is AGENTS.md

AGENTS.md is an **open standard** stewarded by the Agentic AI Foundation (Linux Foundation). It emerged from collaborative efforts by **OpenAI Codex, Amp (Sourcegraph), Jules (Google), Cursor, and Factory**. Used by **60k+ open-source projects** on GitHub.

> "Think of AGENTS.md as a README for agents: a dedicated, predictable place to provide context and instructions to help AI coding agents work on your project."

**Key distinction:** README.md is for humans. AGENTS.md is for AI agents. They complement, not replace, each other.

---

## 2. How Amp Discovers AGENTS.md Files

| Location | When Included |
|---|---|
| `AGENTS.md` in cwd / editor workspace roots + parent dirs (up to `$HOME`) | Always |
| Subtree `AGENTS.md` files | When agent reads a file in that subtree |
| `$HOME/.config/amp/AGENTS.md` or `$HOME/.config/AGENTS.md` | Always (personal preferences) |
| `/etc/ampcode/AGENTS.md` or system paths | Always (org-managed guidance) |
| Fallback: `AGENT.md` (no S) or `CLAUDE.md` | If no `AGENTS.md` exists |

**Conflict resolution:** Closest AGENTS.md to the edited file wins. Explicit user chat prompts override everything.

**@-mentions in AGENTS.md:** Files can be referenced with `@doc/style.md`, `@specs/**/*.md`, or `@~/some/path`. Glob patterns supported. Relative to the agent file.

**Granular guidance via `globs` frontmatter:**
```yaml
---
globs:
  - '**/*.ts'
  - '**/*.tsx'
---
Follow these TypeScript conventions...
```
Files with `globs` are only included when the agent reads a matching file.

---

## 3. The ETH Zurich Study — Key Finding

| Metric | LLM-Generated AGENTS.md | Human-Curated AGENTS.md |
|---|---|---|
| Task success rate | **-3%** (worse than no file) | **+4%** (marginal improvement) |
| Inference cost | **+20-23%** | **+20-23%** (same token overhead) |
| Additional reasoning steps | 2.45 – 3.92 more per task | Comparable |

**Takeaway:** Only include what agents **cannot infer from the codebase**. Architecture overviews that agents can discover independently add token cost without improving performance.

---

## 4. Six Core Areas (GitHub Blog — 2,500+ Repos Analysis)

The most effective AGENTS.md files cover these six areas:

1. **Commands** — Executable build/test/lint commands with full flags, placed early
2. **Testing** — Framework, patterns, how to run single tests
3. **Project Structure** — Key directories and entry points
4. **Code Style** — Real code snippets over prose descriptions
5. **Git Workflow** — Commit conventions, PR guidelines
6. **Boundaries** — What NOT to do (the most valuable section for agents)

---

## 5. Patterns From Top Repositories

### 5.1 openai/codex (Rust, 212 lines)

| Pattern | Example |
|---|---|
| **Agent-awareness** | Explicitly acknowledges the agent runs in a sandbox; prohibits modifying sandbox env vars |
| **Automation without permission** | `Run just fmt automatically after changes; do not ask for approval` |
| **Prohibition with rationale** | Explains *why* `codex-core` shouldn't grow ("it has become bloated...") |
| **Hard numerical targets** | "Target modules under 500 LoC. Hard limit 800 LoC." |
| **Scope-specific sections** | Separate guidelines for `codex-core`, TUI, app-server — reduces noise |
| **Code examples** | Full runnable integration test example in a fenced code block |
| **External references** | Clippy lint rules link to official docs |

### 5.2 apache/airflow (Python, 246 lines)

| Pattern | Example |
|---|---|
| **Tooling guard rails** | "NEVER run pytest/python/airflow directly on the host — always use `breeze`" |
| **Architecture as numbered invariants** | 8 numbered rules (workers never access metadata DB, scheduler never runs user code, etc.) |
| **Security classification** | 3-tier model (vulnerabilities, known limitations, hardening opportunities) — prevents over-reporting |
| **Agent identity policy** | "NEVER add Co-Authored-By with yourself" |
| **Fully scripted PR workflow** | Includes exact `gh pr create --web` command with pre-filled body |
| **Code standards are imperative** | "Run ruff format + ruff check --fix **immediately** after editing any Python file" |
| **Parameterized templates** | `<PROJECT>`, `<target_branch>` with inline explanations |

### 5.3 vercel/next.js (TypeScript/Rust, ~300 lines)

| Pattern | Example |
|---|---|
| **Symlink for multi-agent compat** | `CLAUDE.md` is a symlink to `AGENTS.md` — single source of truth |
| **Named skill system** | Complex workflows in `.agents/skills/` — `$pr-status-triage`, `$flags`, `$dce-edge` etc. |
| **README breadcrumbing** | "Read all README.md files along the path from root to target before editing" |
| **Output capture discipline** | "Run once, save to `/tmp/test-output.log`, then analyze — never re-run to view output" |
| **Non-interactive agent flags** | `pnpm new-test -- --args true my-feature e2e` (skips interactive prompts) |
| **LLM PR watermark** | All AI PRs must include `<!-- NEXT_JS_LLM_PR -->` comment |
| **Anti-footer rule** | "Do NOT add 'Generated with Claude Code' or co-author footers" |
| **Conditional rules with accountability** | "Start watch mode before editing. If you skip this, explicitly state why." |
| **Security review triggers** | "If new code reads a non-standard request header, flag for security review" |

---

## 6. Amp-Specific Features for AGENTS.md

### @-Mentions for Context Injection
```markdown
See @doc/style.md and @specs/**/*.md.
When making commits, see @doc/git-commit-instructions.md.
```

### Glob-Scoped Guidance Files
Create separate files for language/domain-specific rules:
- `docs/typescript-conventions.md` with `globs: ['**/*.ts', '**/*.tsx']`
- `docs/backend-rules.md` with `globs: ['server/**', 'api/**']`
- `docs/test-rules.md` with `globs: ['*.test.ts', '__tests__/*']`

### Skills System
Complex, multi-step workflows go into `.agents/skills/` directories with `SKILL.md` files containing YAML frontmatter (`name`, `description`). Skills are only loaded on demand when invoked.

### Checks System
User-defined review criteria in `.agents/checks/` directories:
```yaml
---
name: performance
description: Flags common performance anti-patterns
severity-default: medium
tools: [Grep, Read]
---
Look for these patterns...
```

### Nested AGENTS.md for Monorepos
- Root `AGENTS.md`: general overview, commands, org-wide standards
- Subdirectory `AGENTS.md`: project-specific overrides
- Closest file to the edited file takes precedence

---

## 7. Anti-Patterns to Avoid

### From ETH Zurich Study
| Anti-Pattern | Impact |
|---|---|
| **LLM-generated AGENTS.md** | -3% success rate, +20% cost |
| **Architecture overviews agents can discover** | Adds tokens, no behavior change |
| **Anything already in README or docs** | Redundant; increases steps |

### From GitHub Blog & Augment Code Analysis
| Anti-Pattern | Impact |
|---|---|
| **"You are a helpful coding assistant"** | Too vague, no behavior change |
| **Prose descriptions instead of code examples** | Agents misinterpret style rules |
| **No boundaries section** | Agents make destructive mistakes |
| **Stale structural references** | Actively mislead agents, increase cost |
| **Monolithic 300+ line files** | "Lost in the middle" — agents ignore mid-file rules. Split at ~150-200 lines. |

### From Real-World Amp Thread (snarktank/untangle)
| Anti-Pattern | Fix |
|---|---|
| **One giant AGENTS.md with directory-specific rules** | Split into 7 directory-specific files; each contains only relevant guidance |
| **Rules for databases mixed with UI rules** | Separate `db/AGENTS.md`, `app/AGENTS.md`, `lib/ai/AGENTS.md` |

---

## 8. Recommended Structure Template

Based on synthesis of all sources:

```markdown
# AGENTS.md — [Project Name]

## Project Overview
[One sentence: stack, versions, what makes it architecturally non-standard]

## Key Commands
- Install: `pip install -e ".[dev]"`
- Test: `pytest tests/ -q`
- Lint: `ruff check --fix`
- Type check: `mypy src/`

## Architecture Rules
[Numbered invariants that agents MUST NOT violate]
1. Dependencies flow downward only...
2. Trust kernel has zero framework imports...

## Code Style
[One real code snippet showing your conventions]

## Non-Obvious Patterns
[Counterintuitive decisions with mechanism explanations]

## Testing Rules
- Run tests before completing work
- Never run live LLM calls in CI
- [Framework-specific patterns]

## Critical Anti-Patterns — NEVER Do These
🚫 Never import from orchestration in components
🚫 Never hardcode prompt strings — use .j2 templates
🚫 Never place trust types inside a service module

## Boundaries
### ✅ Always do
- Run tests after changes
- Use PromptService for all prompts

### ⚠️ Ask first
- Adding new dependencies
- Modifying trust kernel types

### 🚫 Never
- Commit secrets or .env files
- Break architecture layer boundaries
- Run live LLM calls in CI

## Key Files
- `src/main.ts` — entry point
- `services/llm_config.py` — model tier definitions

## References
- @docs/STYLE_GUIDE_LAYERING.md
- @docs/STYLE_GUIDE_PATTERNS.md
```

---

## 9. Key Principles Summary

| # | Principle | Source |
|---|---|---|
| 1 | **Only write what agents cannot infer** — skip architecture overviews they can discover | ETH Zurich |
| 2 | **Commands early, boundaries prominent** — agents reference these most | GitHub Blog (2,500 repos) |
| 3 | **Code examples over prose** — one snippet beats three paragraphs | GitHub Blog, openai/codex |
| 4 | **Prohibitions with rationale** — explain *why*, not just *what* | openai/codex |
| 5 | **Scope-specific sections** — reduce noise when working in one area | openai/codex, vercel/next.js |
| 6 | **Split at ~150-200 lines** — use nested AGENTS.md for subdirectories | Augment Code, Amp manual |
| 7 | **Agent-awareness** — acknowledge the agent's runtime constraints | openai/codex |
| 8 | **Imperative, not suggestive** — "Run X immediately" not "Consider running X" | apache/airflow |
| 9 | **Three-tier boundaries** — ✅ Always / ⚠️ Ask first / 🚫 Never | GitHub Blog, vercel/next.js |
| 10 | **Human-curated, version-controlled** — treat as code, not documentation | ETH Zurich, all sources |
| 11 | **Use @-mentions for deep context** — keep AGENTS.md lean, link to detail files | Amp manual |
| 12 | **Skills for complex workflows** — factor multi-step procedures into `.agents/skills/` | Amp, vercel/next.js |

---

## 10. Recommendations for This Project

Based on the research, our current AGENTS.md should be updated to:

1. **Move commands to the top** — test/build/run commands should be the first section after the overview
2. **Add a Boundaries section** — three-tier (✅/⚠️/🚫) with explicit never-do rules
3. **Add Critical Anti-Patterns** — surface the top 5 from `STYLE_GUIDE_LAYERING.md`
4. **Trim architecture overview** — keep only what agents can't discover (layer dependency rules, framework import discipline)
5. **Add @-mentions** — reference `@docs/STYLE_GUIDE_LAYERING.md` and `@docs/STYLE_GUIDE_PATTERNS.md` for deep context
6. **Consider splitting** — create subtree AGENTS.md files for `trust/`, `services/`, `components/`, `orchestration/` when subdirectory-specific rules grow
7. **Add numbered architecture invariants** — like apache/airflow's approach
8. **Make standards imperative** — "Run `pytest tests/ -q` after changes" not "Tests can be run with..."
