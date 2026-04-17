# `meta/CodeReviewerAgentTest/` -- Developer Guide

A reusable, env-driven wrapper around `meta.code_reviewer.CodeReviewerAgent`. Author a new code-review agent (a phase verification, a security audit, an L2 governance audit, etc.) by writing **one JSON file** -- everything else (LLM selection, runner, markdown rendering, CLI, exit codes) is provided.

---

## 1. What this package is

| File | Role |
|------|------|
| `env_settings.py` | `EnvSettings` (pydantic-settings over `.env`) + `reviewer_profile_from_env(env_var=...)` -> `ModelProfile`. |
| `review_config.py` | `ReviewAgentConfig` schema -- the only thing a developer authors. |
| `runner.py` | `async run_review(config)` -- builds `LLMService` + `PromptService` + `CodeReviewerAgent` and returns a `ReviewReport`. |
| `report_renderer.py` | `render_markdown(report, ctx)` -- 10-section markdown matching `docs/PHASE4_CODE_REVIEW.md`. |
| `cli.py` / `__main__.py` | `python -m meta.CodeReviewerAgentTest <config.json>` with verdict-based exit codes. |
| `configs/phase1.json` | First consumer; PLAN_v2.md Phase 1 verification. |

The wrapper does **not** duplicate review logic -- it imports `CodeReviewerAgent` from `meta/code_reviewer.py` and stays compliant with the AGENTS.md rule that `meta/` may import from `trust/`, `services/`, `components/`, `utils/` (never from `orchestration/`).

---

## 2. Quick start (5 minutes)

1. Copy `configs/phase1.json` to e.g. `configs/security_audit.json`.
2. Edit:
   - `name`, `description`
   - `files`: list the repo-relative `.py` files you want reviewed
   - `output_json`, `output_md`: where to write the report
   - (optional) `model_env_var`: pick `MODEL_NAME_JUDGE` for cheaper runs
3. Run:

```bash
python -m meta.CodeReviewerAgentTest meta/CodeReviewerAgentTest/configs/security_audit.json
```

Exit codes: `0=approve`, `1=request_changes`, `2=reject`, `3=error`.

For a CI-friendly preview without API keys, add `--deterministic-only`.

---

## 3. Config schema reference

`ReviewAgentConfig` (see `review_config.py`):

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `name` | `str` (required) | -- | Slug for logs and metadata. |
| `description` | `str` | `""` | Free text for humans. |
| `model_env_var` | `str` | `"MODEL_NAME"` | Which `.env` variable selects the LLM. |
| `files` | `list[str]` (>= 1) | -- | Repo-relative `.py` files. Non-Python files are skipped by `run_deterministic_review`. |
| `diff_path` | `str \| None` | `None` | Optional unified diff to attach as submission context. |
| `prompt_template_dir` | `str` | `"prompts"` | Template root, relative to `AGENT_ROOT`. |
| `system_prompt_template` | `str` | `"codeReviewer/CodeReviewer_system_prompt"` | System prompt path (no `.j2`). |
| `submission_template` | `str` | `"codeReviewer/CodeReviewer_review_submission"` | Submission prompt path. |
| `task_id` / `user_id` | `str \| None` / `str` | -- | Forwarded to `eval_capture.record(...)` per H5. |
| `deterministic_only` | `bool` | `False` | When `True`, the LLM phase is skipped entirely. |
| `output_json` | `str` (required) | -- | Where to write the `ReviewReport` JSON. |
| `output_md` | `str \| None` | `None` | If set, also render the 10-section markdown. |
| `md_template_section_overrides` | `dict[str, str]` | `{}` | Free-form context for the renderer (`phase_label`, `plan_reference`, `decomposition_axis`, `review_id`, `model_used`, `litellm_id`, `task_id`). |

`extra="forbid"` is set, so typos in field names fail loudly.

---

## 4. Choosing the LLM

`.env` keys consumed:

| Env var | Purpose |
|---------|---------|
| `MODEL_NAME` | Default reviewer model (typically the cheapest reasonable). |
| `MODEL_NAME_JUDGE` | Alternative slot, used by `meta/judge.py`. |
| `MODEL_NAME_REVIEWER` | Reserved for a dedicated reviewer pool. |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `TOGETHER_API_KEY` | Provider credentials. The CLI auto-detects which key the selected model needs based on its LiteLLM id prefix. |

Built-in registry in `env_settings._MODEL_REGISTRY`:

| LiteLLM id | Tier | Context | $/1k in | $/1k out |
|------------|------|---------|---------|----------|
| `anthropic/claude-3-haiku-20240307` | fast | 200k | 0.00025 | 0.00125 |
| `anthropic/claude-3-sonnet-20240229` | balanced | 200k | 0.003 | 0.015 |
| `openai/gpt-4o-mini` | fast | 128k | 0.00015 | 0.0006 |
| `openai/gpt-4.1-nano` | fast | 128k | 0.00010 | 0.00040 |
| `openai/gpt-4o` | balanced | 128k | 0.0025 | 0.01 |
| `together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1` | balanced | 32k | 0.0006 | 0.0006 |

To add a new model id, append a row to `_MODEL_REGISTRY`. Unknown ids still work via a defensive fallback (zero-cost, 8k context) and emit a single warning log.

---

## 5. Authoring custom prompts

The runner reuses `prompts/codeReviewer/CodeReviewer_system_prompt.j2` and `prompts/codeReviewer/CodeReviewer_review_submission.j2` by default. To swap in your own:

1. Drop a new `.j2` under `prompts/<your_agent>/`.
2. Set `system_prompt_template` and/or `submission_template` in your config to the new path (without the `.j2` suffix).

The submission template must accept the variables `files_to_review`, `submission_context` (see the existing `CodeReviewer_review_submission.j2` for shape).

---

## 6. Output format

- **JSON:** `trust.review_schema.ReviewReport` -- frozen Pydantic model (verdict, statement, confidence, dimensions, gaps, validation_log, files_reviewed, metadata).
- **Markdown:** 10 sections matching `docs/PHASE4_CODE_REVIEW.md`:
  1. Governing Thought  2. Pyramid Self-Validation  3. Files Reviewed  4. Dimension Results  5. Cross-Dimension Interactions  6. Gaps  7. Judge Filter Log  8. Verdict Decision Trace  9. Recommended Action List  10. Metadata

`md_template_section_overrides` lets you push contextual labels into the renderer (`phase_label`, `plan_reference`, etc.) without code changes.

---

## 7. CI integration

```yaml
- name: Code review (deterministic, no API key required)
  run: |
    python -m meta.CodeReviewerAgentTest \
      meta/CodeReviewerAgentTest/configs/phase1.json \
      --deterministic-only
```

For nightly LLM-augmented runs, set `ANTHROPIC_API_KEY` (or whichever provider matches `MODEL_NAME`) in the runner's secrets, and remove `--deterministic-only`. Exit codes map straight to job conclusions: `0` -> green, `1`/`2` -> red, `3` -> retry.

---

## 8. Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `LLM review requires ANTHROPIC_API_KEY ...` (exit 3) | `MODEL_NAME` selects an Anthropic model but no `ANTHROPIC_API_KEY` is exported / present in `.env`. |
| `Unknown LiteLLM id 'foo/bar' -- falling back to a defensive profile.` | The id is missing from `_MODEL_REGISTRY`; runs still succeed but cost reporting will be zero. |
| `jinja2.exceptions.TemplateNotFound` | `system_prompt_template` / `submission_template` does not match a file under `prompt_template_dir`. |
| `pydantic.ValidationError: files [...] min_length` | The config has `"files": []`. The schema requires at least one entry. |
| Output JSON written but markdown is missing | `output_md` is `null`/absent in the config. Set it to a path. |
