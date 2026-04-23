"""Pyramid services -- horizontal infrastructure for the Structured Reasoning agent.

Imports allowed: outer ``trust/``, outer ``services/`` (notably
``PromptService``, ``LLMService``, ``eval_capture``, governance recorders),
sibling ``StructuredReasoning/trust/``, plus stdlib + ``pydantic``.
No ``langgraph`` / ``langchain`` (mirroring the outer rule).
"""
