"""Capability-gating: make ``AgentFacts.capabilities`` load-bearingly gate tools.

ADR-0007 (Option A2). The governanceTriangle Identity pillar
(``governanaceTriangle/03_agentfacts_governance.md`` §1.1 "capability-based
access … prevent unauthorized operations"; §7.3 "apply least privilege") claims
an agent's declared contract *governs* it. Today that claim is theatre: the full
process-wide ``ToolRegistry`` is bound to every LLM regardless of what the agent
declared. This component closes the gap — it derives the tool set an agent may be
bound *from its declared capabilities*, so the LLM never even sees a tool outside
its contract. This is preventive (bind-time) filtering; it complements — does not
replace — the run-time ``authorization_service`` PEP.

Framework-agnostic domain logic (Invariant #3): imports only stdlib + Pydantic +
``trust``. No langgraph/langchain. The capability↔tool mapping is a *decision*, so
it lives here (a component), not in an orchestration node (AP-5 thin nodes).

Reuses the existing ``trust.models.Capability.name`` field only — no ``trust/``
type change, so no kernel re-sign (ADR-0007 §Consequences).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CapabilityToolMissingError(ValueError):
    """A declared capability names a tool absent from the registry (FR-5).

    Declared-but-unavailable is a *configuration bug* — a contract naming a tool
    the registry cannot provide — not a silent no-op that degrades to an empty
    tool set the operator never notices. Raised at graph-build so the failure is
    loud and immediate (fail-fast).
    """


class CapabilityGateResult(BaseModel):
    """The ``declared = bound`` evidence object (FR-6).

    ``capabilities`` is what the agent declared; ``bound_tool_names`` is what the
    filter will actually bind to the LLM. When gating is correct the two sets are
    equal — the arch test and the identity trace carrier assert on exactly this.
    """

    capabilities: list[str]
    bound_tool_names: list[str]


def derive_bound_tools(
    *,
    capability_names: list[str],
    available_tool_names: list[str],
) -> CapabilityGateResult:
    """Derive the tools to bind from declared capabilities (FR-3/FR-4/FR-5).

    Returns the intersection of declared capabilities and the registry's tools,
    preserving the declared order for a stable evidence object. A capability that
    names a tool absent from ``available_tool_names`` raises
    :class:`CapabilityToolMissingError` (FR-5) — the intersection would otherwise
    silently drop it.
    """
    available = set(available_tool_names)
    missing = [name for name in capability_names if name not in available]
    if missing:
        raise CapabilityToolMissingError(
            "AgentFacts capability names tool(s) absent from the ToolRegistry: "
            f"{missing}. Available tools: {sorted(available)}. "
            "A declared-but-unavailable tool is a configuration bug — fix the "
            "capability contract or register the tool."
        )
    bound = [name for name in capability_names if name in available]
    return CapabilityGateResult(
        capabilities=list(capability_names),
        bound_tool_names=bound,
    )


def filter_registry_schemas(
    schemas: list[dict[str, Any]],
    bound_tool_names: list[str],
) -> list[dict[str, Any]]:
    """Reduce ``ToolRegistry.get_schemas()`` output to the bound subset.

    ``get_schemas()`` returns ``list[dict]`` each carrying a ``"name"`` key
    (``services/tools/registry.py``). Selection only — the schema dicts are not
    mutated — so exactly the declared tools' schemas reach the LLM binding.
    """
    allowed = set(bound_tool_names)
    return [schema for schema in schemas if schema.get("name") in allowed]
