"""Outer adapter ring exposing the four-layer backend to AG-UI clients.

Per docs/plan/adapter/AGENT_UI_ADAPTER_PLAN.md and AGENT_UI_ADAPTER_SPRINTS.md.
This package introduces exactly ONE new abstraction (AgentRuntime in ports/).
All other concerns are consumed from horizontal services in services/.
"""
