"""Cloud-agnostic value objects for identity, policy, and credential data.

Every cloud adapter converts its native SDK responses into these
provider-neutral Pydantic models. All models are frozen (immutable).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IdentityContext(BaseModel):
    """Cloud-agnostic representation of a resolved identity."""

    provider: str
    principal_id: str
    display_name: str
    account_id: str
    roles: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    session_expiry: datetime | None = None
    raw_attributes: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class VerificationResult(BaseModel):
    """Outcome of identity verification."""

    verified: bool
    reason: str
    provider: str
    checked_at: datetime

    model_config = ConfigDict(frozen=True)


class AccessDecision(BaseModel):
    """Allow/deny result from cloud IAM policy evaluation."""

    allowed: bool
    reason: str
    evaluated_policies: list[str] = Field(default_factory=list)
    provider: str

    model_config = ConfigDict(frozen=True)


class TemporaryCredentials(BaseModel):
    """Scoped, time-bounded credentials issued by a cloud provider."""

    provider: str
    access_token: str
    expiry: datetime
    scope: list[str] = Field(default_factory=list)
    agent_id: str
    raw_credentials: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class PolicyBinding(BaseModel):
    """A single policy attached to a cloud identity."""

    policy_id: str
    policy_name: str
    policy_type: str
    provider: str
    attached_to: str = ""

    model_config = ConfigDict(frozen=True)


class PermissionBoundary(BaseModel):
    """Maximum permission set for a cloud identity."""

    boundary_id: str
    max_permissions: list[str] = Field(default_factory=list)
    provider: str

    model_config = ConfigDict(frozen=True)
