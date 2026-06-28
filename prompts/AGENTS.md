# prompts/ — Jinja2 Templates

> Nested guide. Loads when Claude reads a file under `prompts/`. Root `AGENTS.md`
> is authoritative for inter-layer rules; this file is local guidance.

## The rule (H1 / AP-3)

All prompts are `.j2` files **here**, rendered via
`PromptService.render_prompt()`. **Never** hardcode a prompt string in Python
(AP-3) — it bypasses logging, blocks non-engineers from editing, and makes A/B
testing impossible.

## Naming + structure

- Naming: `{component_name}_system_prompt.j2` or `{ClassName}_{method}.j2`.
- `includes/` — reusable partials. Compose, don't copy-paste prompt fragments.
- `codeReviewer/` — backend review prompts.

## Config split (restated — it bites here)

`.j2` templates hold **human intent** (prose policy). Numeric thresholds live in
`components/routing_config.py`, not in templates. The meta-optimizer tunes
numbers; humans write the policy prose in these templates.

## Code-reviewer prompt versions

- `prompts/codeReviewer/` — stable **v1** baseline.
- `prompts/codeReviewer/v2/` — deep-agent hardening family (Sprint 4).
- Rollout: default to v1; select v2 explicitly for staged adoption or A/B
  (`prompt_version` config field or CLI `--prompt-version v2`).
- `prompts/codeReviewer/frontend/` — the frontend reviewer (FD1–FD7 dimensions).
