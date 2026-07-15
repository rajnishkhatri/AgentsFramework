# Portable SDD lifecycle skills — install into any workspace

Six spec-driven-development (SDD) skills that run a production-grade change
through a **10-stage lifecycle** — brainstorm → spec → plan → tasks → analyze →
implement → review → test → converge → sign-off — with a human gate at each
stage. They are **workspace-neutral and coding-agent-neutral**: their bodies use
`{{placeholder}}` tokens instead of any one repo's paths or commands, and they
adapt to whatever ecosystem you drop them into.

| Skill | Owns |
|---|---|
| `sdd-lifecycle` | The router — names which sibling owns each stage. Start here. |
| `sdd-brainstorm` | Stage 1 — expand a problem into ~6 validated directions. |
| `sdd-spec` | Stages 2–4 — EARS spec → clarify → plan → tasks → analyze. |
| `sdd-replan` | Stage 5 — mid-flight loop-back when scope/priority changes. |
| `sdd-implement` | Stage 6 — execute the task list with red/green TDD. |
| `sdd-converge` | Stages 9–10 — classify gaps vs spec, run the sign-off gate. |

(Stage 7 review and Stage 8 test use *your* existing review + gate commands —
the skills route to them, they don't replace them.)

---

## What's in this bundle

```
sdd-skills-bundle/
├── INSTALL.md                     ← this file
├── _sdd/                          ← the shared workspace-binding contract
│   ├── binding.schema.md          ← the 13-key vocabulary + fill-prompts
│   ├── binding.template.toml      ← copy to .sdd/binding.toml and fill
│   └── FIRST_RUN.md               ← the inspect→propose→confirm→persist flow
├── sdd-lifecycle/  SKILL.md + the three _sdd files (self-contained)
├── sdd-brainstorm/ SKILL.md + …
├── sdd-spec/       SKILL.md + …
├── sdd-replan/     SKILL.md + …
├── sdd-implement/  SKILL.md + …
└── sdd-converge/   SKILL.md + …
```

Each skill dir is **self-contained** — it carries its own copy of the binding
template, schema, and first-run doc — so a single `sdd-<name>/` directory works
on its own if you only want one stage. The top-level `_sdd/` is the shared
master copy of the contract.

---

## Install (pick your coding agent)

Unzip the bundle, then copy the six `sdd-*/` skill directories into your agent's
skills discovery path. **Do not copy `_sdd/` or `INSTALL.md`** into the skills
path — they are documentation, and each skill already carries the binding files
it needs.

### Claude Code
```bash
# project-scoped (checked into the repo) …
cp -r sdd-lifecycle sdd-brainstorm sdd-spec sdd-replan sdd-implement sdd-converge \
    <your-repo>/.claude/skills/
# … or user-scoped (all your projects)
cp -r sdd-* ~/.claude/skills/
```
Claude Code auto-discovers `SKILL.md` files under those paths. Invoke with
`/sdd-lifecycle` (or any sibling), or just describe the task — the descriptions
trigger them.

### Cursor
```bash
cp -r sdd-lifecycle sdd-brainstorm sdd-spec sdd-replan sdd-implement sdd-converge \
    <your-repo>/.cursor/skills/
```

### GitHub Copilot
Copilot reads path-scoped instructions from `.github/instructions/*.instructions.md`.
Add a thin pointer per skill so Copilot loads it in context, and keep the skill
bodies under a docs path it can resolve:
```bash
mkdir -p <your-repo>/docs/skills <your-repo>/.github/instructions
cp -r sdd-* <your-repo>/docs/skills/
for s in sdd-lifecycle sdd-brainstorm sdd-spec sdd-replan sdd-implement sdd-converge; do
  printf -- '---\napplyTo: "**"\n---\n\nSee `docs/skills/%s/SKILL.md` for the %s skill.\n' "$s" "$s" \
    > "<your-repo>/.github/instructions/$s.instructions.md"
done
```

### Any other agent (Windsurf, Codex, Aider, a bare LLM, …)
The skills are plain Markdown. Put the six `sdd-*/SKILL.md` files wherever your
agent reads instructions from, or paste one into the conversation when you want
that stage. Nothing in them is agent-specific except where the **binding** makes
it so (see below) — and that adapts to you.

---

## First run — bind the skills to your workspace (one time)

The skill bodies contain `{{placeholder}}` tokens (`{{constitution}}`,
`{{check_gate}}`, `{{adr_home}}`, …). Before a skill runs, those resolve to
**your** workspace's real values. Resolution order:

1. **`.sdd/binding.toml`** at your repo root — if present and filled, used directly.
2. Otherwise, **first-run auto-adapt** kicks in.

### Auto-adapt: inspect → propose → confirm → persist
On the first invocation in a workspace with no `.sdd/binding.toml`, the skill:

1. **Inspects** your ecosystem for each binding — a constitution doc
   (`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md` / `.cursorrules`), a gate
   command (a `Makefile` target / `package.json` script / `justfile` / `tox.ini`),
   a test runner, ADR/decision homes, etc.
2. **Proposes** a filled `binding.toml` with every detected value.
3. **Requires your confirmation** — it never runs a *guessed* `check_gate` or
   `test_gate`. A wrong gate command is worse than asking. (Undecidable → ask,
   never fabricate.)
4. **Persists** the confirmed binding to `.sdd/binding.toml`. Later runs skip
   straight to step 1.

### Or fill it yourself ahead of time
```bash
mkdir -p <your-repo>/.sdd
cp _sdd/binding.template.toml <your-repo>/.sdd/binding.toml
# then edit .sdd/binding.toml — replace every <fill> with your value,
# or <none> for anything your workspace doesn't have.
```

The **13 keys** and a fill-prompt for each are in `_sdd/binding.schema.md`.
Minimal viable binding — the two that matter most:

```toml
[binding]
constitution = "CONTRIBUTING.md"          # your rules-of-record doc
check_gate   = "npm run verify"           # your full lint+typecheck+test command
test_gate    = "npm test"                 # your must-pass invariant/arch tests
# … set the rest, or <none> for what you don't have. Any <none> key = the skill
#   skips that step (e.g. no adr_home → the decision-record stage is a no-op).
```

**Graceful degradation:** a `<none>` key means that step has no analog in your
workspace, so the skill skips it rather than emitting a broken command or a
fabricated path.

---

## How the pieces fit

- **The skill body is the *methodology*** (the 10 stages, EARS acceptance
  criteria, the human↔agent micro-loop, red/green TDD) — identical in every
  workspace.
- **The binding is the *coupling*** (which file is the constitution, what the
  gate command is, where ADRs live) — different in every workspace, resolved at
  runtime, never hard-coded into the skill.

That split is what makes one set of skills portable across repos *and* across
coding agents. You install the skills once; the binding tunes them to the repo
they land in.

---

## Verify it took

Ask your agent to run `sdd-lifecycle` (or `/sdd-lifecycle`) and describe a small
change. On a fresh workspace it should propose a binding and ask you to confirm
it before doing anything gate-related. Once `.sdd/binding.toml` exists, it should
route you straight into Stage 1 (brainstorm) with your real file paths and
commands filled in.
