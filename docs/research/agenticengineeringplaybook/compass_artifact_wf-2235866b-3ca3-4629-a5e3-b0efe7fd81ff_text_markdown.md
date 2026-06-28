# RUNBOOK #4 — Agentic Engineering Patterns (Solo Operator Edition)

*A standalone, rules-first runbook for a senior practitioner working in a single-operator-plus-agent loop. Anchored on Simon Willison's "Agentic Engineering Patterns" guide and triangulated across the 2025–2026 practitioner field. Current as of June 25, 2026.*

## TL;DR

- **The durable discipline is "vibe engineering" / agentic engineering: stay proudly accountable for code you have *proven* to work.** The single highest-leverage rule across every source (Willison, Anthropic, Böckeler, Hashimoto, Karpathy, Osmani) is *design for verifiability* — give the agent a fast, deterministic way to check its own work (tests, linters, screenshots, oracles), and never confuse "the tests passed" with "I understand what this does."
- **Context is the scarce resource; the harness is your moat.** Manage the context window deliberately (subagents as firewalls, compaction, scratchpad notes, /clear discipline), and treat every agent mistake as a permanent harness fix (Hashimoto's ratchet) encoded in AGENTS.md/CLAUDE.md plus deterministic sensors.
- **Calibrate autonomy to stakes and reversibility.** Use a controlled fast loop for code you care about, a delegated slow loop for low-stakes refactors, and a hard human gate for irreversible actions and the lethal trifecta. Plan before code on anything you can't describe in one sentence.

## Key Findings

1. **Willison's guide is built on a small set of four-word, high-density prompts** ("Use red/green TDD", "First run the tests") that pack large amounts of engineering discipline already baked into frontier models. These are reliable, tool-agnostic levers.
2. **"Designing for verifiability" is the meta-pattern.** Anthropic's Claude Code best practices call giving the agent a way to verify its own work "the highest-leverage practice." Böckeler/Fowler formalize this as *sensors* (feedback controls). The 12-factor project frames it as owning your control flow and context. All roads lead to fast, deterministic feedback loops.
3. **Context engineering has crystallized into named techniques** — compaction, structured note-taking/scratchpads, tool-result clearing, and sub-agents as context firewalls (Anthropic). "Context rot" / the "dumb zone" past heavy context fill is real; more tokens makes agents worse.
4. **Harness engineering is the 2026 super-concept.** Mitchell Hashimoto introduced it in his February 5, 2026 blog post "My AI Adoption Journey" (Step 5, "Engineer the Harness"); OpenAI engineer Ryan Lopopolo's field report "Harness Engineering: Leveraging Codex in an Agent-First World" followed roughly February 11, 2026, and Thoughtworks/Böckeler formalized it on martinfowler.com. Agent = Model + Harness. The harness is guides (feed-forward) + sensors (feedback), computational (deterministic) and inferential (LLM-judged). The ratchet principle: the harness only tightens.
5. **Security reduces to the lethal trifecta** (Willison, June 16, 2025): private data + untrusted content + exfiltration. Cut at least one leg structurally; per Willison, filters "reach roughly 97% accuracy on known attack patterns… [which] means three percent of attacks succeed," and "you can't have security mitigations that work on statistics."
6. **Review is the new bottleneck.** Osmani's "70% problem": "AI can rapidly produce maybe 70% of the code for an app… But the remaining 30% — edge cases… integration with production systems… security, your API keys — that can be just as time consuming as it ever was." He pegs real developer productivity at roughly "1X, 2X. Maybe they can complete 20% more tasks than they could before," while "code review is becoming the new bottleneck." GitClear's "AI Copilot Code Quality 2025" report (211M changed lines across 2020–2024, including Google/Microsoft/Meta repos) found copy/pasted lines rose from 8.3% to 12.3% while refactored ("moved") lines fell from 24.1% to 9.5%, with code blocks containing 5+ duplicated lines increasing roughly 8× — "copy/paste exceeds moved code for the first time in history." Google's 2024 DORA report estimated "a 7.2% decrease in delivery stability for every 25% increase in AI adoption." For a solo operator the rules differ from enterprise — lean on tests and review what matters, but never ship code you don't understand.

## Details — The Attributed Pattern Catalog

Each pattern: **NAME (attribution)** — PROBLEM → RULE(s) → WHEN / WHEN NOT.

### A. Principles & Mindset

**A1. Vibe engineering / agentic engineering (Willison).** *Problem:* the gap between fast-loose "vibe coding" and accountable professional work. *Rule:* "Iterate with coding agents to produce production-quality code that you're confident you can maintain." Stay "proudly and confidently accountable for the software you produce." AI amplifies existing expertise — operate at the top of your game. *When:* all production work. *When not:* genuinely throwaway prototypes (then plain vibe coding is fine). *(Note: Willison proposed "vibe engineering" in Oct 2025 but as of Feb 2026 acknowledges "Agentic Engineering" is winning out as the term.)*

**A2. Your job is to deliver code you have proven to work (Willison, Dec 2025).** *Problem:* agents (and humans) hand off plausible-but-unverified code. *Rule:* never assume LLM code works until executed; ship proof (tests, manual-test notes, screenshots) alongside the change. *When:* always before any merge/PR.

**A3. Writing code is cheap now; understanding stayed expensive (Willison; echoed by Osmani).** *Problem:* near-zero cost to generate code distorts old intuitions. *Rule:* adopt a "zero tolerance attitude to minor code smells" because fixing them is now cheap; but budget real time for comprehension. *When:* refactors, debt paydown.

**A4. Hoard things you know how to do (Willison).** *Problem:* re-deriving known solutions wastes the agent's and your time. *Rule:* maintain a personal corpus of working examples (TIL blog, tools collection, research repos); prompt agents to *recombine* two known-good examples into something new; point agents at local paths/repos to clone as input. *When:* greenfield prototypes, "is this possible" questions.

**A5. Embrace the compound engineering loop (Shipper/Klaassen at Every, via Willison).** *Problem:* lessons learned in one session evaporate. *Rule:* end projects with a retrospective "compound step" — document what worked into instructions for future agent runs; small improvements compound. *When:* recurring task types.

### B. Context Engineering

**B1. Subagents as context firewall (Willison; Anthropic; HumanLayer).** *Problem:* exploration and token-heavy operations pollute the root context (models degrade well below their ~1M limit; benchmarks favor <200K). *Rule:* dispatch a subagent with a fresh context window to explore/search/run-tests and return only a condensed summary; keep the orchestrator context clean for coherence. Use a cheaper model (e.g. Haiku) for parallel subagents. *When:* large-repo exploration, big test suites, multi-file independent edits. *When not:* don't over-fragment into dozens of specialists — the root agent can debug/review its own output if it has the tokens.

**B2. Compaction (Anthropic).** *Problem:* conversations approach the context limit. *Rule:* summarize the conversation into a high-fidelity summary and reinitiate a fresh window; maximize recall first, then trim precision; clear old tool-call results (lightest-touch compaction). *When:* long-running sessions after major milestones. *When not:* over-aggressive compaction loses subtle context.

**B3. Structured note-taking / scratchpad (Anthropic; LangChain).** *Problem:* context truncation loses the plan. *Rule:* have the agent persist a plan/progress to an external file (NOTES.md, progress file) and re-read after compaction; combine with Git commits as checkpoints so the agent can reconstruct state via git log/diff. Durable memory should hold only what constrains future reasoning (decisions, failed approaches, preferences). *When:* iterative multi-session projects.

**B4. /clear discipline & the dumb zone (Anthropic; 12-factor).** *Problem:* cluttered context degrades retrieval. *Rule:* run /clear between unrelated tasks; if you've corrected the agent more than twice on the same issue, the context is cluttered — /clear and restart. Keep working context under heavy-fill thresholds; check what's loaded (/context). *When:* task switches, repeated correction loops.

**B5. Context priming / precise reference (Anthropic; 12-factor "own your context window").** *Problem:* the agent greps the whole tree or guesses conventions. *Rule:* reference files precisely (@-mentions, tab-completion); pre-fetch relevant context up front rather than mid-execution; keep CLAUDE.md/AGENTS.md focused — bloated instruction files cause the agent to ignore real instructions. *When:* every session start.

### C. Planning & Spec

**C1. Explore → Plan → Code → Commit (Anthropic Claude Code best practices).** *Problem:* jumping straight to code builds the wrong thing confidently. *Rule:* (1) read relevant files read-only in plan mode; (2) ask for a written plan; (3) implement against the plan, running tests; (4) commit with a descriptive message and open a PR. *When:* non-trivial multi-file work. *When not:* "Skip planning only if you could describe the diff in one sentence."

**C2. Spec-driven development (GitHub Spec Kit; Böckeler).** *Problem:* agents drift from intent; code is a binding artifact. *Rule:* write a structured, living spec first (Spec → Plan → Tasks → Implement); the spec is the source of truth, regenerated when requirements change; use EARS-style testable acceptance criteria ("WHEN [condition] THE SYSTEM SHALL [behavior]"). *When:* features in complex/existing systems, legacy modernization. *When not:* 3–5 minute one-sentence changes (over-planning wastes time).

**C3. Plan-as-markdown / editable plan (Anthropic).** *Problem:* steering a plan through chat is lossy. *Rule:* open the plan in your editor and edit it directly before execution; save the plan to a file the implementation phase refers back to. *When:* complex tasks.

### D. Verification & Feedback Loops

**D1. Design for verifiability (Anthropic — "highest-leverage practice").** *Problem:* without a success oracle the agent produces code that looks right and isn't, and all the feedback burden falls on you. *Rule:* give the agent a runnable way to check itself — tests, lint/typecheck returning OK/FAIL, screenshots to compare. Make verification easy and fast (Karpathy: "make this EASY, FAST to win"). *When:* always — this is the meta-rule.

**D2. Red/green TDD (Willison; Beck lineage).** *Problem:* agents write code that doesn't work or is never used. *Rule:* prompt "Use red/green TDD" — write tests first, confirm they fail (red), then implement until they pass (green). Confirming failure first proves the test exercises the new code. *When:* anything verifiable. *Guard:* commit tests before implementation so if the agent alters tests to pass, the diff shows it (DataCamp/Anthropic). Never let the agent weaken tests to go green.

**D3. First run the tests (Willison).** *Problem:* agent doesn't know a suite exists and won't run it. *Rule:* open each session against an existing repo with "First run the tests" (or "Run 'uv run pytest'"). This forces test-running habit, signals project size, and primes a testing mindset. *When:* every session start on an existing project.

**D4. Agentic manual testing (Willison).** *Problem:* passing tests ≠ works as intended (server crashes on startup, missing UI element). *Rule:* have the agent exercise code itself — `python -c "..."` for libraries, `curl` to "explore" a JSON API, write throwaway demos in `/tmp`. When manual testing finds a bug, fix it with red/green TDD so it becomes a permanent test. *When:* before landing any feature.

**D5. Visual feedback loop (Willison "Rodney"; Anthropic Puppeteer/Playwright variant).** *Problem:* UI correctness is invisible to text tests. *Rule:* give the agent a browser-automation CLI (Playwright, Vercel agent-browser, Willison's Rodney) and a mock/screenshot target; tell it to "test that with Playwright" and "look at screenshots" so it uses its own vision to compare against the target and iterate. Anthropic reports a 2–3× quality improvement when the agent can check output against a visual target. *When:* interactive web UIs, design-mock matching.

**D6. Sensors: feedback controls (Böckeler/Fowler).** *Problem:* agents repeat mistakes and can't self-correct. *Rule:* install sensors that observe output and feed back — computational (linters, type checkers, ESLint/Semgrep, Dependency Cruiser, coverage, mutation testing, GitLeaks pre-commit) and inferential (LLM semantic review). Optimize sensor messages for LLM consumption (custom linter messages that include self-correction instructions — "a positive kind of prompt injection"). Gate expensive inferential sensors behind cheap computational ones. *When:* any codebase you maintain over time.

**D7. Demand evidence, not assertions / Showboat (Willison).** *Problem:* agents write what they *hoped* happened. *Rule:* require the agent to "show its work" by capturing real command output (Willison's Showboat `exec` records the command and its actual output, discouraging fabrication). Don't trust the "press release" — review the PR description the agent wrote too. *When:* handoffs, documentation of testing.

### E. Harness Engineering

**E1. Agent = Model + Harness (Böckeler/Fowler; Hashimoto).** *Problem:* model quality is not the bottleneck — the environment is. *Rule:* invest in the harness (guides + sensors + tools + memory + permissions), not in waiting for a smarter model. Guides (feed-forward) steer before acting; sensors (feedback) catch after. *When:* always; this is the organizing frame.

**E2. The ratchet (Hashimoto; Osmani).** *Problem:* agents repeat the same class of mistake. *Rule (verbatim, Hashimoto, "My AI Adoption Journey," Feb 2026):* "Anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again." Encode each fix as a permanent harness improvement (an AGENTS.md line, a lint rule, a hook). *Hashimoto's corollary:* zero aspirational rules — every line in your instructions file should trace to a real failure; if you can't point to the mistake, delete the line. The harness only tightens. *When:* continuously.

**E3. Tools-as-guardrails / CLI-over-MCP (Ronacher).** *Problem:* MCP servers are unreliable and consume context; agents misuse tools. *Rule:* prefer plain scripts/CLIs/Makefile commands over MCP where possible — Claude Code runs regular tools well; reach for MCP only when the alternative is too unreliable (e.g., Playwright browser automation). Tools must be fast (crashes tolerable, hangs problematic), give clear error messages, and be "protected against an LLM chaos monkey using them completely wrong — there is no such thing as user error." Place critical commands in a Makefile. Produce useful log output as a byproduct of code generation. *When:* designing the agent's tool surface.

**E4. Harness-friendly codebase & ambient affordances (Ronacher; Böckeler).** *Problem:* some codebases are hard for agents to navigate. *Rule:* favor stable ecosystems with low churn and good build tooling (Ronacher recommends Go for new backend projects — explicit context, fast incremental test caching); make code findable via basic tools (grep); prefer local reasoning, simple descriptive names, plain SQL over complex ORMs, keep permission checks locally visible; prefer more code generation over more dependencies. Encode conventions as ambient affordances (file naming, directory structure, type annotations). *When:* tech-stack and architecture choices for agent-heavy work.

**E5. Garbage-collection / janitor agent (OpenAI Codex case study; Fowler).** *Problem:* documentation and architecture drift; context rot in instruction files. *Rule:* run a scheduled agent that doesn't build features but scans for stale docs, obsolete AGENTS.md instructions, and architecture-boundary violations, and opens cleanup PRs. *Context:* in the OpenAI/Lopopolo field report, three engineers used Codex over five months — starting from an empty repo in late August 2025 — to build a roughly one-million-line codebase with zero manually written code, using exactly this kind of mechanically-enforced architecture plus background cleanup agents. *When:* mature long-lived repos. *When not:* early-stage solo prototypes (overhead).

### F. Security

**F1. Avoid the lethal trifecta (Willison, June 16, 2025).** *Problem:* an agent with (1) access to private data + (2) exposure to untrusted content + (3) an exfiltration vector is structurally exploitable via prompt injection. Per Willison, filters "reach roughly 97% accuracy on known attack patterns… [which] means three percent of attacks succeed," and "you can't have security mitigations that work on statistics." *Rule:* structurally cut at least one leg — run the agent without private data, OR only process trusted content, OR make exfiltration structurally impossible. For most production agents, cutting exfiltration is the most practical defense. Treat MCP tool-mixing as a trifecta risk. *When:* any agent touching email, browsing, private repos/DBs plus outbound network.

**F2. Least privilege + sandboxing (Ronacher; Anthropic).** *Problem:* an agent with full permissions can damage the host or leak data. *Rule:* run agents inside Docker/devcontainers/ephemeral VMs (Anthropic's own engineers only use `--dangerously-skip-permissions` inside containers); read-only DB access by default; no exposed API keys; egress firewall; timeouts on long-running commands. Use a permissions allowlist for common safe commands; a PreToolUse hook is the deterministic backstop the allowlist alone doesn't give you. *When:* any autonomous/YOLO-mode running.

**F3. Human gate for irreversible actions (12-factor "contact humans as a tool"; Karpathy leash).** *Problem:* agents take destructive/irreversible actions on wrong assumptions. *Rule:* require explicit human approval before irreversible operations (push to main, prod deploy, payments, data deletion, external sends). The agent should never push directly to main — it opens PRs a human reviews. *When:* always for irreversible/high-blast-radius actions.

### G. Review & Comprehension

**G1. Never inflict unreviewed code on collaborators (Willison anti-pattern).** *Problem:* dumping large unreviewed agent PRs shifts the real work onto reviewers. *Rule:* the initial review pass is *your* responsibility; a good agentic PR (a) works and you're confident it works, (b) is small enough to review efficiently (several small PRs beat one big one), (c) includes context/links to issues/specs, (d) has a PR description you've actually read and validated. Include evidence of manual testing (notes, screenshots, video). *When:* every PR.

**G2. Only ship code you understand / comprehension preservation (Willison; Ronacher; Karpathy).** *Problem:* merging code you can't explain accumulates "comprehension debt"; skills atrophy via the "paradox of supervision." *Rule:* read what matters; use linear walkthroughs to rebuild understanding. Karpathy: "I'm still the bottleneck." *When:* always for code you'll maintain.

**G3. Linear walkthroughs (Willison).** *Problem:* you (or a new maintainer) don't understand existing or vibe-coded code. *Rule:* point a fresh agent at the repo: "Read the source and then plan a linear walkthrough of the code that explains how it all works in detail," using a tool (Showboat) that includes real code snippets via grep/sed/cat (not hand-copied, to avoid hallucination). *When:* onboarding to a codebase, post-vibe-coding comprehension.

**G4. Fresh-context review (Willison subagents; community).** *Problem:* the agent that wrote the code shares its own blind spots. *Rule:* review the diff in a fresh thread / specialist code-reviewer subagent with isolated context, so the review isn't anchored to the implementation reasoning. *When:* before merging non-trivial diffs.

### H. Workflow & Cadence

**H1. Controlled fast vs. delegated slow loops (Litt).** *Problem:* partial-delegation (10–30 min cycles) fragments context and produces weaker results for both human and agent. *Rule:* pick a camp deliberately — (a) **controlled fast loop:** 1–2 min cycles, single-threaded, you stay in control of the code, using the agent "to type faster"; or (b) **delegated slow loop:** nudge background agents a couple times a day while you focus elsewhere, paying ~no attention to code, fine if the agent gets stuck for hours. Avoid the unhappy middle. *When:* (a) code you care about; (b) low-stakes refactors/chores.

**H2. Keep agents on a leash (Karpathy).** *Problem:* unsupervised agents make "subtle conceptual errors a slightly sloppy junior dev would make," act on wrong assumptions, don't seek clarification. *Rule:* describe the single next concrete incremental change; ask for approaches before code; pick one, draft, review/learn, test, git commit, repeat. Keep changes small and supervised. *When:* anything non-trivial or unfamiliar.

**H3. Karpathy pre-coding checklist (Karpathy Guidelines).** *Problem:* agents over-engineer and silently act on inferred assumptions. *Rule:* before writing code, have the agent list every assumption; if an assumption is inferred and consequential, state it and ask for confirmation; if inferred and obvious, note it and continue. Counters over-abstraction and premature frameworks. *When:* any consequential task.

**H4. Background/async agents for chores (Willison).** *Problem:* time-consuming-but-simple refactors interrupt flow. *Rule:* fire async agents (Jules, Codex web, Claude Code on web) on a branch/worktree for refactors; evaluate the PR — land it, re-prompt it, or throw it away. *When:* mechanical refactors, debt paydown. *When not:* architecturally subtle work.

**H5. Autonomy slider / "land the plane" (Karpathy; Yegge).** *Problem:* fixed autonomy doesn't fit all tasks. *Rule:* tune autonomy to stakes; for session wrap-up use a "land the plane" prompt that drives the agent to finish and check off all outstanding tasks before declaring done. *When:* end of session, varying task stakes.

### I. Orchestration (covered lightly — solo focus)

**I1. Single-threaded by default; parallel subagents when independent (Willison; Anthropic).** *Rule:* prefer single-threaded control; parallelize only when sub-tasks are genuinely independent (use git worktrees for isolation). *When not:* don't jump to multi-agent fleets as a solo operator — Yegge's levels 6–8 (10+ agents, custom orchestrators like Gas Town/Beads) add coordination cost most solos don't need; "simple, composable patterns beat complex frameworks" (Anthropic).

**I2. Anthropic's five workflow patterns (Anthropic "Building Effective Agents").** *Reference catalog:* prompt chaining, routing, parallelization, orchestrator-worker, evaluator-optimizer. *Rule:* match control-flow shape to task; workflows beat agents when task structure is stable enough to encode in code; "only add agentic patterns when simpler approaches demonstrably underperform." *When:* designing repeatable automation, not one-off coding.

**I3. Andrew Ng's four design patterns (Ng).** *Reference catalog:* Reflection (self-critique loop), Tool Use, Planning, Multi-agent collaboration. *Rule:* reflection is the cheapest, highest-value to add (have the agent critique and run its own output); planning is "less mature, less predictable." *When:* building agentic features, not just coding.

**I4. 12-factor agents (Humanlayer/Horthy).** *Reference principles for solo-built agentic features:* own your prompts; own your context window; tools as structured outputs; own your control flow; small focused agents; contact humans as first-class tool calls; stateless reducer design. Core insight: "most successful 'AI agents' are mostly well-engineered software with LLM calls at key points." *When:* building your own agent harness/tooling.

## Drop-in Directives (AGENTS.md / CLAUDE.md)

Copy-paste and prune to fit. Keep it short — every line should trace to a real failure (Hashimoto). Bloated files get ignored.

```markdown
# AGENTS.md

## Workflow
- For any change you can't describe in one sentence: explore (read-only) → write a plan → get my approval → implement → commit.
- Start every session by running the tests. Build: `make build`. Test: `make test`. Lint/typecheck: `make check`.
- Use red/green TDD for anything verifiable: write the test first, run it, confirm it FAILS, then implement until green.
- Never modify or weaken a test to make it pass. If a test is wrong, stop and tell me.
- After implementing, manually exercise the code (python -c / curl / Playwright) and show the real output.

## Evidence
- Never claim something works until you have executed it. Paste the actual command output, not a summary.
- PR descriptions must reflect what you actually did and tested. I will read them.

## Context
- Keep changes small. Prefer several small commits/PRs over one large one.
- Use a subagent to explore the repo or run the full test suite; return only a summary.
- Reference files precisely; don't grep the whole tree when I've named the file.

## Guardrails
- Never push to main. Open a PR.
- Never run destructive/irreversible commands (deploys, deletes, external sends, payments) without explicit approval.
- No new dependencies without asking. Prefer generating code over adding a dependency.
- Prefer plain scripts and Makefile commands over MCP servers.

## Assumptions (Karpathy)
- Before coding, list every assumption. If an assumption is inferred and consequential, state it and ask before proceeding.
- Do not over-engineer. Build exactly what was asked — no speculative frameworks, plugins, or abstractions.
```

## Checklists & Gates

**Session-start checklist:** `/clear` if switching tasks → confirm AGENTS.md loaded → "First run the tests" → state the goal in one sentence → decide plan-mode vs. direct.

**Pre-merge gate (all must be true):**
- [ ] Tests written first, observed failing, now passing; tests not weakened.
- [ ] I manually exercised the feature and saw it work (notes/screenshots attached).
- [ ] Computational sensors green (lint, typecheck, coverage, secret-scan).
- [ ] Diff is small enough that I read and understand every change.
- [ ] PR description is accurate and I wrote/validated it.
- [ ] No lethal-trifecta exposure introduced; no irreversible action taken without approval.

**Ratchet gate (post-incident):** Did the agent make a mistake? → Add the smallest permanent harness fix (AGENTS.md line / lint rule / hook / test) that makes it structurally impossible to repeat. Never just re-prompt and move on.

## Decision Rules & Thresholds

- **Plan or not?** One-sentence diff → skip plan, direct/auto-accept. Multi-file, unfamiliar code, or uncertain approach → plan mode first.
- **Subagent or root?** Token-heavy exploration / large test output / independent multi-file edits → subagent. Reasoning the root needs to retain → keep in root.
- **/clear trigger:** corrected the agent twice on the same issue → /clear and restart fresh. Context past heavy fill → compact or clear.
- **Autonomy by stakes:** code you'll maintain → controlled fast loop, supervised, small steps. Low-stakes chore → delegated slow/background loop. Irreversible action → hard human gate regardless.
- **Loop budget:** if a bug fix fails after ~2 autonomous attempts, stop, /clear, change approach (Anthropic).
- **Security gate fires** whenever a planned tool combination would create all three trifecta legs simultaneously — block and redesign.
- **Don't scale to multi-agent fleets** until single-agent throughput is genuinely your bottleneck and you have verification you trust (Yegge levels 6–8 are a structural shift, not a free upgrade).

## Anti-Patterns & Counters

| Anti-pattern | Counter |
|---|---|
| Filing unreviewed agent PRs on others (Willison) | You do the first review pass; ship proof of testing. |
| "Tests passed, ship it" on code nobody understood (Osmani) | Comprehension gate — read what matters; tiered review by stakes. |
| Trusting code that was never executed (Willison) | Demand evidence: run it, show real output. |
| Agent weakens/rewrites tests to go green | Commit tests first; forbid test edits; diff review. |
| Over-engineering / speculative abstractions (Karpathy) | Pre-coding assumption list; "build exactly what was asked." |
| Context bloat / "dumb zone" (Anthropic) | /clear, compaction, subagent firewalls, lean CLAUDE.md. |
| Aspirational rule-stuffing in AGENTS.md (Hashimoto) | Every line traces to a real failure or gets deleted. |
| MCP sprawl / slow, flaky tools (Ronacher) | CLI/scripts/Makefile over MCP; fast tools with clear errors. |
| Lethal trifecta by accident via MCP mixing (Willison) | Structurally cut one leg; least privilege; sandbox. |
| Blocking Edit/Write mid-plan with hooks | Validate via PostToolUse/pre-commit, never block writes mid-reasoning. |
| Defensive-coding amplification in loops (Ronacher) | Make malformed states unrepresentable; don't let each loop add another speculative guard. |
| Skill atrophy / paradox of supervision (Willison/Anthropic) | Linear walkthroughs; keep reading and reasoning about code. |

## Recommendations — Staged Adoption

**Stage 0 (today, ~30 min):** Create AGENTS.md/CLAUDE.md at repo root with the drop-in directives above. Wire three Makefile commands: `make build`, `make test`, `make check`. Adopt the two four-word prompts: "First run the tests" and "Use red/green TDD."

**Stage 1 (week 1):** Add the pre-merge gate as a literal checklist. Turn on the explore→plan→code→commit workflow for anything you can't describe in one sentence. Start committing tests before implementation. Begin the ratchet: every agent mistake → one permanent harness line.

**Stage 2 (weeks 2–4):** Build the sensor suite — pre-commit hooks for lint/typecheck/secret-scan, coverage in CI, a PreToolUse safety hook. Add a code-reviewer subagent for fresh-context review. Set up sandboxed execution (devcontainer/Docker) and a permissions allowlist. Audit every agent for lethal-trifecta exposure and cut a leg.

**Stage 3 (ongoing):** Introduce structured note-taking + compaction discipline for long sessions. Adopt spec-driven development for complex features. Add a scheduled janitor agent for doc/architecture drift if the repo is long-lived. Periodically prune AGENTS.md (delete any line not traceable to a failure).

**Benchmarks that change the plan:**
- If you're correcting the agent >2×/issue routinely → your harness/guides are too thin; invest in sensors before more prompting.
- If review is your bottleneck and PRs are growing → enforce smaller diffs and stronger automated sensors, not more generation.
- If you can't explain a merged change → stop; you've crossed from engineering into gambling. Re-introduce walkthroughs/review.
- If single-agent throughput is genuinely capped and verification is trustworthy → only then experiment with parallel/background agents.

## Caveats

- **Source reliability & recency.** This domain moves weekly. Willison's guide is explicitly a living document (chapters updated post-publication; several chapters were last modified within weeks of this writing). His own terminology shifted from "vibe engineering" (Oct 2025) to "agentic engineering" (Feb 2026). Treat tool-specific details (Claude Code slash commands, plan-mode keybindings, model names) as illustrations, not durable truths — the *patterns* are durable; the *tooling* drifts.
- **Vendor incentives.** Anthropic, OpenAI, GitHub, and harness-tool vendors have a commercial interest in agentic-coding optimism; the OpenAI "1M LOC, zero human-written code" case study (three engineers, five months, empty repo from late August 2025) and Yegge's productivity claims are self-reported and should be read skeptically. Fowler's own commentary notes the OpenAI write-up omits functional/behavioral verification.
- **Contested productivity data.** GitClear ("AI Copilot Code Quality 2025," 211M changed lines, 2020–2024), Faros, and Google's 2024 DORA report (≈7.2% delivery-stability decrease per 25% AI-adoption increase) come from instrumentation studies with their own methodological limits; directionally consistent but not settled. Osmani's "20% more tasks" and "70% problem" figures are practitioner observations, not controlled measurements.
- **Solo scope.** This runbook deliberately treats multi-agent fleets/clusters lightly. Enterprise patterns (locked-down multi-agent, evidence-required pipelines, org-level LSP rollouts) are deliberately out of scope and would add friction for a solo operator.
- **Harness engineering is young.** The term is ~4 months old as of this writing (Hashimoto, Feb 5, 2026; OpenAI/Lopopolo ~Feb 11, 2026); its boundaries are still fluid and some catalogs over-claim. Start simple (good AGENTS.md + pre-commit hooks) and add complexity only when simple controls demonstrably fail.
