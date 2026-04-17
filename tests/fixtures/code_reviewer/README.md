# CodeReviewer L3 fixtures

The `TestCodeReviewerL3` class in `tests/meta/test_code_reviewer.py`
replays a recorded LLM response (`review_response.json`) so the L3 path
exists in CI without making a live API call. The recording is stored in
this directory and committed to the repo.

## Recording procedure (one-off, requires API key)

1. Set `OPENAI_API_KEY` (or `LITELLM_API_KEY`) in your environment.
2. From the repo root, run the helper:

   ```bash
   python scripts/record_code_reviewer_fixture.py
   ```

   This invokes the real `meta.code_reviewer` CLI in `--llm` mode against
   `trust/enums.py` and writes the structured `ReviewReport` JSON to
   `tests/fixtures/code_reviewer/review_response.json`.

3. Inspect the JSON, redact anything sensitive, then commit the file.

CI must NOT regenerate this file (no live LLM calls in CI). When the
fixture is absent, `TestCodeReviewerL3.test_review_with_recorded_fixture`
skips with a pointer to this README.
