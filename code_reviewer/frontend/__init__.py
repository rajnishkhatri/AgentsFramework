"""Frontend Ring Code Review Validator runner.

The package exposes the CLI invokable as
``python -m code_reviewer.frontend`` (or, from the ``AgentsFramework/``
parent, ``python -m agent.code_reviewer.frontend``). The runner loads the
Jinja prompt set under ``prompts/codeReviewer/frontend/`` and dispatches
the review per the contract in §0 of ``system_prompt.j2``.

See :mod:`code_reviewer.frontend.runner` for the public API and
:mod:`code_reviewer.frontend.tools` for the deterministic tool dispatch
table (used by ``--rules-only`` and the future LLM tool-calling loop).
"""
