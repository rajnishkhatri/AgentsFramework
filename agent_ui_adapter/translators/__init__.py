"""Anti-corruption layer: pure shape mapping between domain and AG-UI events.

Per AGENT_UI_ADAPTER_PLAN.md rules R5-R7:
- R5: pure data-shape mapping only
- R6: no I/O, no LLM, no policy decisions, no auth checks
- R7: imports from trust/ and agent_ui_adapter.wire/ only -- NOT from services/
"""
