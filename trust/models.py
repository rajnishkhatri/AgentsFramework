"""Identity and governance data models for the Trust Foundation.

Pure data -- no I/O, no storage, no network. These are the shared kernel
types consumed by every layer above.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from trust.enums import IdentityStatus


class Capability(BaseModel):
    """What an agent can do."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class Policy(BaseModel):
    """Behavioral constraint on an agent."""

    name: str
    description: str = ""
    rules: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class AgentFacts(BaseModel):
    """The agent identity card -- central model of Layer 1."""

    agent_id: str
    agent_name: str
    owner: str
    version: str
    description: str = ""
    capabilities: list[Capability] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    signed_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: IdentityStatus = IdentityStatus.ACTIVE
    valid_until: datetime | None = None
    parent_agent_id: str | None = None
    signature_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


class AuditEntry(BaseModel):
    """Change record appended to per-agent audit trails."""

    agent_id: str
    action: str
    performed_by: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class VerificationReport(BaseModel):
    """Bulk verification results."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    expired: int = 0
    failures: list[dict[str, Any]] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


class CloudBinding(BaseModel):
    """Maps an AgentFacts identity to cloud IAM primitives."""

    agent_id: str
    provider: Literal["aws", "gcp", "azure", "local"]
    principal_mapping: dict[str, Any] = Field(default_factory=dict)
    capability_mappings: list[dict[str, Any]] = Field(default_factory=list)
    status_mapping: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)
