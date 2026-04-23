"""Structured Reasoning (Pyramid ReACT) Agent.

Self-contained agent driven by ``research/pyramid_react_system_prompt.md``.
Mirrors the four-layer architecture internally (trust/, services/,
components/, orchestration/) and reuses the outer agent's infrastructure
(PromptService, LLMService, governance recorders, ToolRegistry).
"""
