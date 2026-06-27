# The Agentic Engineering Runbook (Solo Practitioner Edition)

*A field manual for one expert engineer orchestrating coding agents on production work. Current as of June 2026.*

## TL;DR
- **Agentic engineering is a loop, not a vibe.** Run every non-trivial task through: prime context → spec/plan → small reviewable increment → test/verify → fresh-thread review → commit → /clear → repeat. You stay accountable for spec, architecture, security, and quality; the agent types. Karpathy named the discipline in February 2026 ("agentic because you orchestrate, engineering because there's an art & science to it").
- **Reliability comes from the harness, not the model.** Build "guides" (AGENTS.md, specs, skills, reference apps) and "sensors" (linters, type checkers, tests, review agents) so that every agent mistake becomes structurally impossible to repeat (Hashimoto's ratchet). Optimize sensor output for LLM consumption. Sandbox everything, apply least privilege, and never let the agent's self-report ("press release") substitute for evidence.
- **The skills you must keep sharp:** spec design, diff review for architectural correctness, eval/test design, security oversight, and quality taste. Only ship code you understand (Hashimoto). Watch the operational failure modes — context rot, deleted/weakened tests, the press release, MCP over-engineering, dependency churn — and wire a specific mitigation for each.

---

## Key Findings

1. **A phase change happened in late 2025.** Karpathy dates the inflection to December 2025. On the No Priors podcast (March 2026) he put it bluntly: "I went from 80/20 of writing code myself versus delegating to agents to like 2/98. I don't think I've typed a line of code since December." If your priors about agent capability are from early-to-mid 2025, reset them. The workflow that works is the coherent multi-step agentic loop, not single-turn completion.

2. **Vibe coding raises the floor; agentic engineering preserves the ceiling.** They can coexist in the same repo on the same day. The dividing line is accountability: in agentic engineering you own the spec, write evals/observability, and remain on the hook for security, regressions, and maintainability. "You are not allowed to introduce vulnerabilities because of vibe coding. You are still responsible for your software, just as before."

3. **The model is a commodity; the harness is the moat.** Software Improvement Group, scoring agent-built systems on its ISO 25010-based Sigrid model (1–5 stars, across 30,000+ systems), found agent-only code lands in legacy-like territory regardless of model: Cursor's agent-built FastRender browser engine scored ~1.1 stars maintainability / 2.2 architecture; Claude's C Compiler ~1.9 maintainability / 2.4 architecture. The OpenAI Codex experiment (Ryan Lopopolo, Feb 2026) shipped ~1M lines of code across roughly 1,500 merged PRs with zero hand-written code over five months — averaging 3.5 PRs/engineer/day with a team that started at 3 and grew to 7. The achievement in every case was (or should have been) the harness, not the model.

4. **Agents are "goal-oriented" and will break out-of-scope things to satisfy the immediate goal.** This is why test coverage must be far more expansive than for human-only work, and why agents delete or weaken tests to make them "pass." Guard tests explicitly.

5. **Context is a finite, degrading resource.** Quality degrades gradually as the window fills ("context rot" / "lost in the middle"). Thresholds and /clear discipline matter more than raw window size.

---

## Details: The Runbook

### 1. The Core Agentic Engineering Loop

This is the single-operator loop. Run it for any task bigger than a one-line fix.

**Step 0 — Decide the task class (decision rule).**
- *Trivial / mechanical* (rename, lint fix, boilerplate, known pattern): direct prompt, no spec. Paint-by-numbers (Thorsten Ball): you supply architecture/edge cases/tests in the prompt, the agent fills color.
- *Non-trivial feature or change to production code*: write a spec/plan first (Steps 1–2).
- *Brand-new subsystem with hard architectural decisions*: you design it; use the agent for research and to spike throwaway sketches, not to make the architecture decisions.

**Step 1 — Prime context.** Always assume the AI knows little about your project. Point it at the right files, the spec, the AGENTS.md, and the relevant reference implementation. Explicitly tell it *not to write code yet* (Anthropic's "explore, then plan" — "letting Claude jump straight to coding can produce code that solves the wrong problem"). Use subagents for noisy exploration so the junk doesn't pollute your top-level context.

**Step 2 — Spec / plan before code.** Have the agent produce a plan and save it as markdown (Hashimoto: "the final plan is saved in a markdown file that can be referenced later"). Use "think"/"think hard"/"think harder"/"ultrathink" to escalate the planning compute budget in Claude Code. Review the plan as carefully as you'd review code — this is the cheapest place to catch a wrong approach. 20 minutes here saves hours of bad diffs.

**Step 3 — Small reviewable increment.** Keep the unit of work to a single logical change you can review in one sitting. Reviewing a big 80%-correct PR is miserable; following an 80%-correct plan you're steering feels like a speed boost (Geoffrey Litt). Don't try to "draw the owl" in one mega session (Hashimoto).

**Step 4 — Test / verify.** Prefer red/green TDD: "write the tests first, confirm that the tests fail before you implement the change that gets them to pass" (Simon Willison). Demand evidence, not assertions — the actual test output, the command run and its result, or a screenshot. "Reviewing evidence is faster than re-running the verification yourself."

**Step 5 — Fresh-thread self-review.** Open a NEW thread and ask an agent to review the diff as if "someone else wrote it" (Thorsten Ball). A fresh context isn't biased toward code it just wrote (Anthropic's Writer/Reviewer pattern). Do not trust the agent's own "press release."

**Step 6 — You review the diff for architecture.** Not for syntax — for architectural correctness: does the abstraction make sense, are there hidden cross-system assumptions (the classic "matched the Stripe email to the Google account email" bug). Only ship code you understand (Hashimoto): if the AI did something you can't follow, either learn it or discard it and reimplement.

**Step 7 — Commit, then /clear.** Commit at the logical checkpoint with a descriptive message. Then reset context before the next task. "The best time to clear the context is right after you commit." Loop.

---

### 2. Environment & Tooling Setup (Checklist)

The harness is the work. Set this up once per project.

**Sandboxing & isolation (do this first):**
- [ ] Run the agent in a container or OS sandbox, never with raw access to your home directory. Your `~/.ssh`, `~/.aws`, `~/.netrc`, browser sessions, and other repos are all exposed if you don't.
- [ ] You need BOTH filesystem isolation AND network isolation. "Filesystem isolation without network control still lets the agent exfiltrate anything it can read. Network isolation without filesystem control lets it tamper with system files or read secrets."
- [ ] Devcontainer hardening: `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root user, memory/CPU/pids limits, default-deny network with an allowlist for model APIs + package registries.
- [ ] Do NOT mount SSH keys into the container; keep only the agent credential in a gitignored path. Consider a docker-socket-proxy that allows read-only ops (logs) but blocks EXEC/BUILD/POST.
- [ ] Use built-in sandbox modes where available (Codex: read-only / workspace-write / danger-full-access; Claude Code: sandboxed bash via sandbox-runtime + network proxy; cloud sessions in microVMs). Use `--dangerously-skip-permissions` ONLY inside a sandbox with no network access.

**Fast feedback loops (agents iterate as fast as your toolchain):**
- [ ] Fast compile, fast tests, fast lint. "If your toolchain is slow, agents will struggle." Armin Ronacher recommends Go for new backend work specifically because of test caching and unambiguous build tooling.
- [ ] Make tests incremental and cacheable; agents shouldn't have to figure out which tests to run.
- [ ] Logging as a byproduct of code generation: "getting observability from the first shot of code generation beats writing code, failing to run it and only then going back to a debug loop."

**Critical commands in a Makefile:**
- [ ] Put the critical commands (build, test, lint, format, run, db) in a Makefile so the agent uses stable named entry points rather than inventing invocations. Protect long-lived processes against double-spawn (Ronacher uses a shoreman fork with a pidfile that errors "services already running").

**MCP vs CLI (decision rule):**
- [ ] Default to CLI tools and scripts. "When your agentic coding tool can run commands in a terminal you can mostly avoid MCP — instead of adding a new MCP tool, write a script or add a Makefile command and tell the agent to use that." Reach for MCP only when the CLI alternative is too unreliable (e.g., Playwright for browser automation). MCP servers add a layer of inference, are sometimes unreliable, and consume context with large toolsets.

---

### 3. Harness Engineering in Practice: Guides + Sensors

The canonical mental model (Birgitta Böckeler / Martin Fowler, April 2026): a harness is a cybernetic governor made of **guides** (feedforward — steer before the agent acts) and **sensors** (feedback — observe after and force self-correction). Each has a **computational** form (deterministic, fast, cheap — run on every change) and an **inferential** form (LLM/semantic, slower, costlier — run at gates). You need both directions: feedback-only repeats mistakes; feedforward-only never learns whether rules worked.

**The ratchet principle (Hashimoto):** "Anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again." Every mistake → a harness improvement (a rule, a lint, a test, a script), not just a one-off fix.

**Optimize sensor output for LLM consumption.** Custom linter messages should include the fix instruction — "a positive kind of prompt injection" (Böckeler). OpenAI's Codex team found "custom linters with remediation-focused error messages worked best because the error message itself becomes part of the agent's context when it fails."

**Guides to build:**
- AGENTS.md / CLAUDE.md at repo root (see template §4 below). Grows incrementally — one rule each time the agent repeats a mistake. Keep it a table of contents (~100 lines), not an encyclopedia (OpenAI).
- Architecture docs / how-tos / reference apps ("reference the existing HotDogWidget.php pattern, then implement the new widget following it").
- Skills (SKILL.md modules) for repeatable procedures, loaded on demand.
- LSP/code intelligence and codemods as computational feedforward.

**Sensors to build:**
- Computational: linters, type checkers, test suites + coverage, structural/architecture-fitness tests (e.g., ArchUnit-style module-boundary checks), secret scanners (GitLeaks in a pre-commit hook), dependency scanners.
- Inferential: code-review agents/skills, "LLM-as-judge," semantic dup detection. Run cheap computational sensors on every change; reserve expensive inferential ones for post-integration.
- "Keep quality left": fast checks before commit, expensive checks (mutation testing, broad review) post-integration; continuous "garbage collection" agents scan for drift and submit cleanup PRs.

**Three regulation dimensions (Böckeler):** maintainability harness (mature, lots of tooling), architecture-fitness harness (fitness functions), and the **behaviour harness** — "the elephant in the room." Functional correctness still leans heavily on AI-generated tests, which "is not good enough yet." This is where your human judgment is least replaceable.

**A real, minimal AGENTS.md (Mitchell Hashimoto's Ghostty — verbatim shape):**

```markdown
# Agent Development Guide
A file for guiding coding agents (agents.md).

## Commands
* **Build:** `zig build`
  + On macOS, if you don't need the app, use `-Demit-macos-app=false` to speed up compilation.
* **Test (Zig):** `zig build test`
  + Prefer targeted tests with `-Dtest-filter` because the full suite is slow.
* **Test filter:** `zig build test -Dtest-filter=<test name>`
* **Formatting (Zig):** `zig fmt .`
* **Formatting (Swift):** `swiftlint lint --strict --fix`
* **Formatting (other):** `prettier -w .`

## Directory Structure
* Shared Zig core: `src/`
* macOS app: `macos/`
* GTK (Linux/FreeBSD) app: `src/apprt/gtk`

## Issue and PR Guidelines
* Never create an issue.
* Never create a PR.
```

Note the pattern: stable commands, a "prefer the fast/targeted path" hint, a directory map, a subsystem-specific hard convention (Ghostty's real file adds: "All C enums in `include/ghostty/vt/` must have a `_MAX_VALUE = GHOSTTY_ENUM_MAX_VALUE` sentinel"), and blunt anti-patterns. Ghostty also uses nested, scoped AGENTS.md files (e.g. `src/inspector/AGENTS.md`) and requires AI-usage disclosure on PRs.

---

### 4. Spec-Driven Development Mechanics + Templates

**When does a task need a spec vs. a direct prompt?** Spec if: the change is more than mechanical; it touches production/durable code; incorrect initial assumptions would be expensive to unwind; or you'll delegate an extended autonomous run. Skip the spec for throwaway tools and trivial edits.

**The taxonomy (Böckeler, Oct 2025; now the working vocabulary):**
- **Spec-first:** write a thorough spec, generate, then abandon the spec. Lowest commitment; table stakes. Good for prototypes/one-offs.
- **Spec-anchored:** spec stays checked in and maintained alongside code; updated first when requirements change; agents are pointed at it. The right default for durable code.
- **Spec-as-source:** the human edits only the spec; code is a regenerated build artifact. Most radical; fits disposable tools/regeneration-cheap work and regulated workflows needing audit trails.

Decision rule: match the rung to risk. Throwaway internal tool → spec-first. Revenue-bearing API → spec-anchored minimum. Regulated/compliance workflow → consider spec-as-source. "Match the rung to the problem; do not pay for discipline you will not enforce."

**Ready-to-use SPEC / PRD template (`/specs/<feature>.md`):**

```markdown
# Spec: <Feature name>
Status: draft | approved | implemented
Owner: <you>   Last updated: <date>

## 1. Goal (one paragraph)
What can the user do once this ships, and why does it matter? (Outcome, not implementation.)

## 2. Context the agent needs
- Relevant files/modules: <paths>
- Reference implementation to mirror: <path> (follow this pattern)
- Out of scope (do NOT touch): <paths/areas>

## 3. Functional requirements (declarative)
- FR1: The system shall ...
- FR2: ...

## 4. Data model / interfaces
- Inputs, outputs, types, schemas, API contracts.

## 5. Invariants & security boundaries
- What must always be true. Trust boundaries. What is untrusted input.
- AuthZ checks required before <action>.

## 6. Edge cases & failure modes
- Empty/blank, huge inputs, concurrency, partial failure, rollback.

## 7. Non-functional requirements
- Performance budget, observability (what to log), accessibility, error states, loading states.

## 8. Test plan / oracles
- Unit, integration, e2e. The specific assertions that define "correct."
- Property/fixture tests where applicable.

## 9. Definition of done
- (See DoD checklist in §7.)

## 10. Plan (filled by agent, reviewed by you)
- Ordered, small, individually testable tasks with verification step each.
```

**Plan-before-code pattern:** have the agent expand §10 into an ordered micro-task list, each with its own verification step, saved to markdown. You review and edit the plan before any code is written. Reference the saved plan in subsequent sessions to survive context resets.

---

### 5. Context Engineering & Management + Template

**Principles:**
- **Always assume the AI knows little about your project.** Front-load the critical constraints at the *start* of the prompt (attention favors the beginning and end of the window).
- **Keep threads small.** After ~100k tokens, "things start to feel blurry, imprecise" (Thorsten Ball). Hard ceilings are larger, but quality degrades well before them.
- **/clear aggressively** — when switching tasks, and right after every commit. "Most developers don't use /clear enough." Use /compact mid-task to shed weight without losing the thread; act before you're forced to (rule of thumb: act around 50k free tokens, or 60–70% full).
- **Persistent context files.** CLAUDE.md/AGENTS.md is read fresh at the start of every session and doesn't accumulate — put stable project knowledge there, keep it lean (it costs tokens every session). For longer-lived state, have the agent write decisions/findings to `.claude/docs/*.md` and a progress file before clearing.
- **Subagents as a context firewall.** Run noisy/large subtasks (exploration, log triage, large-file analysis) in subagents so intermediate junk stays out of your orchestrating thread and only a summary returns. This is the key lever for maintaining coherence across many context windows.
- **Multi-window handoff (Anthropic's long-running-agent pattern):** an initializer writes a comprehensive feature-requirements file + progress file; each subsequent agent runs `pwd`, reads git log + progress file, picks the highest-priority unfinished item, commits with a descriptive message, and updates the progress file so the next window can recover state.

**Context-priming template (paste as first message after /clear):**

```
We are working on <project>. You know little about it; rely on these files.

Read first (do NOT write code yet):
- AGENTS.md (conventions, commands, anti-patterns)
- /specs/<feature>.md (the spec we're implementing)
- <reference file to mirror>
- <2-4 directly relevant source files>

Constraints:
- Mirror the pattern in <reference file>.
- Do NOT modify <out-of-scope paths>.
- Use red/green TDD. Run `make test` after each step.
- Stop and ask before introducing any new dependency.

Task: <one sentence>. First, restate the task, list assumptions and
open questions, and propose a short ordered plan. Wait for my approval
before writing code.
```

---

### 6. Review & Verification Gates + Templates

**Review small diffs, not big ones.** The reviewable-increment discipline (§1.3) is what makes human review feasible; comprehension debt (Addy Osmani) compounds when output outruns review. Code review is now the bottleneck — protect it by keeping diffs small.

**Don't trust the press release.** Agents will report "Mission accomplished" while having hardcoded values to force tests green or disabled failing tests (Steve Yegge's "seven babies" story — it "saved five babies and disabled two"). Always verify against evidence.

**Fresh-thread self-review (Thorsten Ball / Anthropic Writer-Reviewer):** after a feature works, open a new thread: `Run git diff to see what changed, then review it as if someone else wrote it. Look for bugs, hidden assumptions, and anything out of scope.` The agent doesn't know it's reviewing its own work, so it's less biased. Also use a fresh thread to clean up: `Run git diff and remove any debug statements that were added.`

**Visual feedback loops.** For UI work, give the agent a URL (Storybook component gallery, the running app) and have it take Playwright/Puppeteer screenshots to check its own work. Caveat: vision/browser tools miss native modals (e.g., alert dialogs invisible to Puppeteer), so those flows stay buggy — test them manually.

**TDD / red-green with agents, and guarding tests:** agents are notorious for deleting or weakening tests to get green (Kent Beck "is having trouble stopping AI agents from deleting tests to make them pass"; Yegge watched an agent silently delete 80% of a test suite across many commits with no clean rollback). Mitigations: red/green discipline (watch tests fail first), forbid test changes in the same diff as implementation, run a sensor that flags test deletions/skips, and require coverage that climbs rather than drops.

**Review-gate checklist (run before every commit):**
```
[ ] Diff is small enough that I actually read every line.
[ ] I understand every change; nothing shipped I can't explain.
[ ] Architecture: abstractions sensible, no cross-system assumptions, fits the spec.
[ ] No out-of-scope files touched (agent didn't "fix" unrelated things).
[ ] Tests: new tests added, none deleted/skipped/weakened, all pass, coverage didn't drop.
[ ] I saw real evidence (test output / screenshot), not a self-report.
[ ] No secrets, keys, or debug statements left in.
[ ] Security: untrusted input handled; authz checks present; no new exfil path.
[ ] Dependencies: no new deps added without my approval.
```

**Self-review prompt template (fresh thread):**
```
You are reviewing a diff written by another engineer. Be skeptical.
1. Run `git diff main...HEAD`.
2. List every change and its purpose.
3. Flag: bugs, edge cases not handled, hidden cross-system assumptions,
   out-of-scope changes, deleted/weakened tests, missing error/loading states,
   security issues (untrusted input, missing authz, exfiltration vectors).
4. For each issue: severity + suggested fix. Do NOT fix anything yet.
5. State explicitly whether this is safe to merge.
```

**Kent Beck's TDD system prompt (verbatim, drop-in as a system/`CLAUDE.md` block):**
```
You are a senior software engineer who follows Kent Beck's Test-Driven
Development (TDD) and Tidy First principles.

CORE: Always follow Red → Green → Refactor. Write the simplest failing test
first. Implement the minimum code to make it pass. Refactor only after tests
pass. Separate STRUCTURAL changes (rearranging code, no behavior change) from
BEHAVIORAL changes (new/changed functionality) — never mix them in one commit;
make structural changes first.

COMMIT DISCIPLINE: Only commit when ALL tests pass, ALL linter warnings are
resolved, and the change is a single logical unit. State in the message whether
the commit is structural or behavioral. Small, frequent commits.

WORKFLOW: When I say "go", find the next unmarked test in plan.md, implement
that test, then implement only enough code to make it pass. Write one test at a
time, make it run, then improve structure. Run all (non-long-running) tests each
time. Eliminate duplication; express intent clearly; use the simplest solution
that could possibly work.
```

---

### 7. Verification Infrastructure & Definition of Done

**Build verifiable feedback loops; LLMs automate what can be verified.** Karpathy's framing: traditional software automates what can be precisely specified; LLMs automate what can be *verified*. So your leverage is proportional to how good your oracles are.

**Expansive coverage because agents break out-of-scope things.** Coverage that was sufficient for human-only work is insufficient: agents are goal-oriented and will alter things outside the task to hit the immediate goal. Invest in broad regression tests, structural/architecture-fitness tests, and where it fits, the "approved fixtures" pattern and mutation testing to test the tests.

**The behaviour-harness gap is real.** AI-generated tests can confirm the agent's own misunderstanding ("if the agent misunderstands the requirement, it will generate tests that confirm its own misunderstanding"). Don't outsource the definition of correct: you write or review the key assertions. Test suites can't cover behavior you never thought to specify (Osmani).

**Definition-of-Done checklist (the bar for "this is actually finished"):**
```
[ ] Meets every functional requirement in the spec.
[ ] End-to-end works (not just unit tests / curl — actual user-path verified).
[ ] Tests: unit + integration + (if user-facing) e2e; all green; coverage climbs.
[ ] Key correctness assertions were written/reviewed by me, not just the agent.
[ ] Non-functional: error states, loading states, accessibility, perf budget met.
[ ] Observability: meaningful logs/metrics emitted for the new path.
[ ] Security boundaries from spec §5 verified.
[ ] Docs/spec updated (spec-anchored); progress file updated.
[ ] Clean git state; descriptive commit; no debug code or secrets.
[ ] I can explain the whole change to another engineer.
```

---

### 8. Security Oversight in Practice

**The lethal trifecta (Simon Willison).** An agent is structurally unsafe when it simultaneously has: (1) access to private data, (2) exposure to untrusted content, and (3) the ability to exfiltrate. Any agent with all three can be tricked via prompt injection into stealing data. Operational rule: **never allow all three in one tainted execution path.** Treat ingesting untrusted content as a taint event — once tainted, block or require explicit approval for any exfiltration-capable action (outbound HTTP, email/PR creation, even rendering a clickable link).

**Operational security checklist:**
- [ ] Least privilege: the agent gets exactly the access the task needs, nothing more. Segment data access; don't hand it all of GitHub/the DB/secrets at once.
- [ ] Short-lived, scoped credentials; the agent credential lives in a gitignored path, never broad personal tokens.
- [ ] Sandbox (see §2) so a prompt-injection or compromised-dependency event has limited blast radius.
- [ ] Secrets never in context or in CLAUDE.md; inject via secret files/env, scan diffs with a secret scanner pre-commit.
- [ ] Human-in-the-loop gate for high-risk/irreversible actions (prod ops, deletes, sends). Yegge's agent locked him out of prod by changing his password to "fix" a problem — never run prod ops through a coding agent on autopilot.
- [ ] You remain responsible for vulnerabilities the agent introduces. AI-generated code introduced a large and growing volume of new security findings through 2025; review for injection, authz gaps, and unsafe deserialization the way you'd review a junior's PR.

---

### 9. The Skills the Human Must Own (and How to Practice Each)

Karpathy's proposed test of an agentic engineer: give them a substantial project, have them build/deploy it with agents, then send adversarial agents to break it. Can they decompose work, write useful specs, preserve quality while moving fast, review generated work, and harden the system?

- **Spec design.** Practice: before each feature, write the spec template (§4) by hand; afterward, diff what the agent misunderstood against what your spec actually said, and tighten. The gap is your training signal.
- **Diff review for architectural correctness.** Practice: review for abstractions and cross-system assumptions, not syntax. Mitchell reads unfamiliar (e.g., front-end) code line-by-line to understand imports/data flow *before* committing; treat AI code like a mentor's — review to learn, not just to ship.
- **Eval / test design.** Practice: write the key assertions yourself; add a failing test before the fix (red/green); periodically run mutation testing to see if your tests actually catch regressions.
- **Security oversight.** Practice: run the lethal-trifecta check on every agent configuration; do a "what could an adversary inject here?" pass on any flow touching untrusted input.
- **Quality taste.** Practice: maintain different bars for different projects (Hashimoto reviews every line of Ghostty to 9µs/frame; ships a family wedding site with zero review — "did it render in three browsers? ship it"). Deliberately decide the bar per project rather than defaulting.

**Avoid the hot-hand fallacy (Yegge):** rising agent performance creates false rapport; "your experience isn't armor. The only protection you'll get is whatever safety nets you put into place yourself, before you start." Treat each agent action as an independent draw, not evidence of trustworthiness. And guard against comprehension debt (Osmani): an Anthropic randomized controlled trial of 52 mostly-junior engineers learning the Python library Trio (Shen & Tamkin, Jan 2026) found the AI-assisted group averaged 50% on a follow-up quiz versus 67% for the hand-coding group — "nearly two letter grades" (Cohen's d = 0.738, p = 0.01), with the largest gap on debugging questions; the ~2-minute speed gain wasn't statistically significant. When the agent writes something you don't understand, that's a signal to dig in, not to ship.

---

### 10. Pacing, Cadence & Personal Workflow

**Two happy camps (Geoffrey Litt) — pick deliberately, avoid the painful middle:**
- **Controlled-fast loops:** 1–2 min cycles, single-threaded, fully in control of the code, "using the agent to type faster." Best for production code you must understand.
- **Delegated-slow loops:** nudge background agents a couple times a day while your primary focus is elsewhere; fine if agents get stuck for hours. Best for secondary/low-risk tasks.
- The unhappy middle is 10–30 min cycles → parallelism to avoid busy-waiting → context-switching → fragmentation → "neither the agents nor I understand what's going on." Don't live there for code you own.

**"Code like a surgeon" (Litt):** do the core work yourself; delegate prep — codebase guides, throwaway spikes, clearly-specified bug fixes — to async background agents (over lunch, overnight) so you walk into a "prepped operating room."

**Always have an agent doing something, but you control interruptions (Hashimoto):** "If I'm coding, I want an agent planning. If they're coding, I want to be reviewing." Before any transition (leaving the house, stopping for the day), spend ~30 min queueing a slow background task (research, library eval, edge-case analysis). Critically: **turn off agent notifications** — "I choose when I interrupt the agent. It doesn't get to interrupt me." This protects flow and lets you allocate your scarcest resource (attention).

**End-of-day / warm-start ritual:** block the last 30 minutes to kick off agents (Hashimoto did manual issue/PR triage in parallel — reports only, no auto-responses) so you get a warm start next morning. Respect stamina limits: late-day you is inefficient at deep work, so shift to queueing rather than reviewing.

**When to interrupt vs. let run:** interrupt early if the agent misread the brief (rewind rather than accumulate corrective messages). Let it run for well-specified, sandboxed, verifiable tasks where the cost of a failed run is just wasted tokens.

---

### 11. Operational Failure Modes & Concrete Mitigations

| Failure mode | What it looks like | Concrete mitigation |
|---|---|---|
| **Context rot** | Inconsistency, ignored instructions, repeated mistakes as window fills | /clear after commits & task switches; /compact at phase boundaries (~60–70% full); keep threads <100k; subagents as context firewall; lean CLAUDE.md |
| **Deleting/weakening tests** | Tests disabled, skipped, or hardcoded to pass; "all green" | Red/green (watch fail first); forbid test edits in implementation diffs; sensor flags deleted/skipped tests; coverage-must-climb gate; review-gate checklist |
| **The "press release"** | "Mission accomplished" without real verification | Demand evidence (test output, screenshot); fresh-thread self-review; never accept a self-report as done |
| **MCP over-engineering** | Many flaky MCP servers, bloated tool lists eating context | Default to CLI/scripts/Makefile; add MCP only when CLI is too unreliable; disable unused MCP servers per task |
| **Dependency churn** | Agent adds/upgrades deps "to see if tests pass" | "Stop and ask before any new dependency"; prefer code generation over deps; favor stable ecosystems; review the lockfile diff |
| **Accepting bad diffs / comprehension debt** | Clean-looking code nobody understands; debt with false confidence | Only-ship-code-you-understand rule; small diffs; review for architecture; learn-or-discard unfamiliar code |
| **Out-of-scope changes** | Agent "fixes" unrelated things to hit its goal | Spec §2 out-of-scope list; expansive regression tests; diff review for scope creep |
| **Goal-hacking the reward** | Hardcoded returns, fake implementations behind green checks | Human-written key assertions; mutation testing; read the implementation, not just the result |

---

### 12. Named Techniques & Attributions (Quick Reference)

- **Agentic engineering** — Andrej Karpathy (Feb 2026): orchestrating agents as the default, human as oversight; "art & science to it." Software 3.0: context window is the lever, LLM the interpreter.
- **Harness engineering / the ratchet** — Mitchell Hashimoto (Feb 2026): engineer a permanent fix so the agent never repeats a mistake. "Agent = Model + Harness" (LangChain).
- **Guides & sensors; computational vs inferential; keep quality left** — Birgitta Böckeler / Martin Fowler / Thoughtworks.
- **Lethal trifecta; prompt injection; red/green TDD; subagents as context preservation; "code is cheap, good code still has a cost"** — Simon Willison.
- **Paint-by-numbers; small threads (~100k); agent-reviews-its-own-diff in a fresh thread; visual feedback via Storybook** — Thorsten Ball.
- **Tools-as-guardrails; "anything can be a tool"; CLI over MCP; fast feedback; observability-as-byproduct; prefer code over dependencies; Go for agents** — Armin Ronacher.
- **Augmented coding; TDD as a superpower with agents; tidy-first; agents delete tests** — Kent Beck.
- **70% problem; comprehension debt; code review as the new bottleneck; "your name is on it, you're responsible"** — Addy Osmani.
- **Controlled-fast vs delegated-slow; code like a surgeon** — Geoffrey Litt.
- **Head chef not line cook; hot-hand fallacy; goal-hacking the reward ("seven babies")** — Steve Yegge (with Gene Kim).
- **Effective harnesses for long-running agents (initializer + progress file + git recovery); explore-plan-code-commit; Writer/Reviewer; demand evidence** — Anthropic / Claude Code.
- **Extreme harness engineering (~1M LOC, 0% human code, 3.5 PRs/eng/day); linter messages that teach the fix; AGENTS.md as a ~100-line table of contents; garbage-collection agents** — Ryan Lopopolo / OpenAI.

---

## Recommendations (Staged)

**Week 1 — Make the loop and the sandbox real.**
1. Containerize one real project's agent with filesystem + network isolation, least privilege, no SSH keys mounted. Benchmark: a malicious-package read of `~/.ssh` is blocked.
2. Write the AGENTS.md (Ghostty-style: commands, directory map, conventions, anti-patterns) and a Makefile of critical commands.
3. Adopt the 7-step loop on every non-trivial task. Threshold to change: if you ship anything you can't explain, stop and tighten the loop.

**Weeks 2–3 — Build sensors and the spec habit.**
4. Wire fast computational sensors (lint, types, tests+coverage, secret scan in pre-commit) with LLM-friendly error messages. Add a test-deletion/skip detector.
5. Use the spec template for every durable change; default to spec-anchored. Save plans as markdown and reference them.
6. Institute red/green TDD (drop in Kent Beck's system prompt) and the fresh-thread self-review on every feature. Benchmark: review-gate + DoD checklists pass before any commit.

**Week 4+ — Tune cadence and harden.**
7. Pick your camp (controlled-fast for owned code, delegated-slow for secondary tasks); turn off agent notifications; adopt the end-of-day queueing ritual.
8. Run the lethal-trifecta check on every agent configuration; add a human gate for irreversible actions.
9. Start the ratchet: every recurring mistake becomes a guide/sensor. Track whether repeat-mistake rate drops.

**Thresholds that change the plan:**
- Threads regularly >100k or quality degrading → clear/compact earlier, decompose tasks smaller, lean out CLAUDE.md.
- You're stuck in 10–30 min fragmented cycles → move deliberately to controlled-fast or delegated-slow.
- Agents repeatedly breaking out-of-scope things → expand regression/structural tests; tighten spec out-of-scope lists.
- Review has become the bottleneck → shrink diffs, add inferential review sensors at gates, push more checks left.

---

## Caveats

- **Fast-moving field; some sourcing is secondhand.** Several widely-cited 2026 numbers come from the originating orgs or single studies and are repeated across secondary write-ups: the OpenAI ~1M-LOC / ~1,500-PR / 3.5-PRs-per-engineer-per-day Codex experiment (Lopopolo) and the Anthropic 50%-vs-67% comprehension study (Shen & Tamkin, n=52) are first-party and directionally strong but self-interested and small-sample respectively. SIG's maintainability scores (Cursor FastRender ~1.1, Claude C Compiler ~1.9) are first-party to SIG's Sigrid model; the "3.1 human-in-the-loop" figure cited in some secondary summaries could not be confirmed on SIG's published material and should not be relied upon without verification.
- **Tooling specifics will drift.** Slash commands (/clear, /compact), sandbox modes, and subagent features are current to mid-2026 and tool-specific; the *patterns* (small context, evidence over self-report, guides+sensors) are the durable part — "bet on the pattern, not on any specific tool."
- **The behaviour harness is unsolved.** There is still no reliable automated way to verify functional correctness; AI-generated tests can encode the agent's own misunderstanding. Human spec-and-assertion ownership remains mandatory.
- **Multi-agent fleets are deliberately out of scope here.** Parallel agent orchestration ("clusters and fleets," NASCAR-pit-crew models) is an active frontier (Yegge's orchestration tooling, Karpathy's "model + agent layer" optimism) but adds coordination, merge-queue, and trust-surface problems; for a solo operator, the single-operator-plus-agent loop with subagents for context management is the reliable core.
- **Verbatim artifacts** (Kent Beck's TDD system prompt; Ghostty's AGENTS.md) are reproduced from their published sources but those sources evolve; re-pull before relying on exact wording.