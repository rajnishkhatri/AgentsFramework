"""Cloud-agnostic protocol definitions (hexagonal ports).

Each protocol uses ``typing.Protocol`` (PEP 544, structural subtyping)
so that cloud adapter classes satisfy the interface without inheriting
from an ABC. All protocols are ``@runtime_checkable``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
    TemporaryCredentials,
    VerificationResult,
)
from trust.models import AgentFacts


@runtime_checkable
class IdentityProvider(Protocol):
    """Resolve and verify cloud-native identities."""

    def get_caller_identity(self) -> IdentityContext: ...

    def resolve_identity(self, identifier: str) -> IdentityContext: ...

    def verify_identity(self, identity: IdentityContext) -> VerificationResult: ...


@runtime_checkable
class PolicyProvider(Protocol):
    """Query cloud IAM policies."""

    def list_policies(self, identity: IdentityContext) -> list[PolicyBinding]: ...

    def evaluate_access(
        self, identity: IdentityContext, action: str, resource: str
    ) -> AccessDecision: ...

    def get_permission_boundary(
        self, identity: IdentityContext
    ) -> PermissionBoundary | None: ...


@dataclass
class LLMCompletion:
    """Framework-agnostic, LiteLLM-shaped result of a single chat completion.

    The portable return type for a direct-call provider (an "extension" of
    LiteLLM for models LiteLLM cannot serve — first case: GLM-5.2 over Z.ai).
    A plain dataclass (not Pydantic, no langchain) keeps the Trust Foundation
    pure and dependency-free, matching the value objects in ``cloud_identity``.

    Field shapes mirror what the react loop reads off a chat response so the
    horizontal boundary shim can map this onto an ``AIMessage`` 1:1:
      * ``content``      — the answer text (thinking blocks already collapsed out).
      * ``tool_calls``   — LangChain tool-call dict shape ``{"name","args","id"}``.
      * ``usage``        — ``{"input_tokens": int, "output_tokens": int}``.
      * ``raw``          — the unparsed provider JSON (audit / debugging).
    """

    content: str
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Direct-call chat-completion port (the LiteLLM extension contract).

    A hexagonal port: any client that calls a provider's REST API directly
    (bypassing LiteLLM) satisfies this by exposing ``acompletion`` — no ABC
    inheritance, structural subtyping only (matches the other ports here).
    The horizontal ``LLMService`` selects an implementation by
    ``ModelProfile.provider`` and adapts the result to the call sites.
    """

    async def acompletion(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMCompletion: ...


@runtime_checkable
class CredentialProvider(Protocol):
    """Issue, refresh, and revoke short-lived credentials."""

    def issue_credentials(
        self, agent_facts: AgentFacts, scope: list[str]
    ) -> TemporaryCredentials: ...

    def refresh_credentials(
        self, credentials: TemporaryCredentials
    ) -> TemporaryCredentials: ...

    def revoke_credentials(self, credentials: TemporaryCredentials) -> None: ...
