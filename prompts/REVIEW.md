# prompts/ — Reviewer Enforcement Map

> Thin enforcement map for the unified reviewer. Cites rule IDs from
> [`prompts/AGENTS.md`](AGENTS.md); never restates prose.

| rule_id | source | detection | severity | reviewer dimension |
|---|---|---|---|---|
| H1 (all prompts are .j2 rendered via PromptService) | prompts/AGENTS.md §The rule | LLM | warning | D2 |
| AP-3 (never hardcode a prompt string in Python) | prompts/AGENTS.md §The rule | AST (`detect_anti_patterns` AP-3) | warning | D2 |
| Naming convention (`{component}_system_prompt.j2`) | prompts/AGENTS.md §Naming + structure | LLM | note | D2 |
| Config split (no numeric thresholds in templates) | prompts/AGENTS.md §Config split | LLM | note | D2 |
