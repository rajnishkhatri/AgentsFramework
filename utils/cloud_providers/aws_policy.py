"""AWS implementation of the PolicyProvider protocol."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from trust.cloud_identity import (
    AccessDecision,
    IdentityContext,
    PermissionBoundary,
    PolicyBinding,
)
from trust.exceptions import AuthorizationError

if TYPE_CHECKING:
    from utils.cloud_providers.config import TrustProviderSettings

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_PROVIDER = "aws"


class AWSPolicyProvider:
    def __init__(self, settings: TrustProviderSettings) -> None:
        kwargs: dict[str, Any] = {"region_name": settings.region}
        if settings.iam_endpoint:
            kwargs["endpoint_url"] = settings.iam_endpoint
        self._iam = boto3.client("iam", **kwargs)

    def list_policies(self, identity: IdentityContext) -> list[PolicyBinding]:
        role_name = self._role_name(identity)
        try:
            bindings = self._list_attached(role_name) + self._list_inline(role_name)
        except (ClientError, BotoCoreError) as exc:
            raise AuthorizationError(
                f"Failed to list policies for role {role_name!r}: {exc}",
                provider=_PROVIDER,
                operation="list_policies",
                original_error=exc,
            ) from exc
        return bindings

    def evaluate_access(
        self, identity: IdentityContext, action: str, resource: str,
    ) -> AccessDecision:
        role_name = self._role_name(identity)
        source_arn = self._role_arn(identity, role_name)
        try:
            resp = self._iam.simulate_principal_policy(
                PolicySourceArn=source_arn,
                ActionNames=[action],
                ResourceArns=[resource],
            )
        except (ClientError, BotoCoreError) as exc:
            raise AuthorizationError(
                f"Failed to evaluate access for {role_name!r}: {exc}",
                provider=_PROVIDER,
                operation="evaluate_access",
                original_error=exc,
            ) from exc
        results = resp.get("EvaluationResults", [])
        if not results:
            return AccessDecision(
                allowed=False,
                reason="No evaluation results returned",
                evaluated_policies=[],
                provider=_PROVIDER,
            )
        first = results[0]
        decision = first.get("EvalDecision", "implicitDeny")
        allowed = decision == "allowed"
        return AccessDecision(
            allowed=allowed,
            reason=decision,
            evaluated_policies=[str(r.get("EvalDecisionDetails", {})) for r in results],
            provider=_PROVIDER,
        )

    def get_permission_boundary(
        self, identity: IdentityContext,
    ) -> PermissionBoundary | None:
        role_name = self._role_name(identity)
        try:
            resp = self._iam.get_role(RoleName=role_name)
        except (ClientError, BotoCoreError) as exc:
            raise AuthorizationError(
                f"Failed to get permission boundary for {role_name!r}: {exc}",
                provider=_PROVIDER,
                operation="get_permission_boundary",
                original_error=exc,
            ) from exc
        role = resp.get("Role", {})
        boundary = role.get("PermissionsBoundary")
        if boundary is None:
            return None
        boundary_arn = boundary.get("PermissionsBoundaryArn", "")
        max_permissions = self._extract_boundary_actions(boundary_arn)
        return PermissionBoundary(
            boundary_id=boundary_arn,
            max_permissions=max_permissions,
            provider=_PROVIDER,
        )

    def _extract_boundary_actions(self, policy_arn: str) -> list[str]:
        """Retrieve the Action list from a managed policy's default version."""
        try:
            policy_resp = self._iam.get_policy(PolicyArn=policy_arn)
            version_id = policy_resp["Policy"]["DefaultVersionId"]
            version_resp = self._iam.get_policy_version(
                PolicyArn=policy_arn, VersionId=version_id,
            )
            doc = version_resp["PolicyVersion"]["Document"]
            if isinstance(doc, str):
                doc = json.loads(doc)
            actions: list[str] = []
            for stmt in doc.get("Statement", []):
                act = stmt.get("Action", [])
                if isinstance(act, list):
                    actions.extend(act)
                else:
                    actions.append(act)
            return actions
        except (ClientError, BotoCoreError):
            return []

    def _list_attached(self, role_name: str) -> list[PolicyBinding]:
        paginator = self._iam.get_paginator("list_attached_role_policies")
        bindings: list[PolicyBinding] = []
        for page in paginator.paginate(RoleName=role_name):
            for p in page.get("AttachedPolicies", []):
                bindings.append(PolicyBinding(
                    policy_id=p.get("PolicyArn", ""),
                    policy_name=p.get("PolicyName", ""),
                    policy_type="managed",
                    provider=_PROVIDER,
                    attached_to=role_name,
                ))
        return bindings

    def _list_inline(self, role_name: str) -> list[PolicyBinding]:
        paginator = self._iam.get_paginator("list_role_policies")
        bindings: list[PolicyBinding] = []
        for page in paginator.paginate(RoleName=role_name):
            for name in page.get("PolicyNames", []):
                bindings.append(PolicyBinding(
                    policy_id=f"inline:{role_name}/{name}",
                    policy_name=name,
                    policy_type="inline",
                    provider=_PROVIDER,
                    attached_to=role_name,
                ))
        return bindings

    @staticmethod
    def _role_name(identity: IdentityContext) -> str:
        if identity.roles:
            return identity.roles[0]
        return identity.display_name

    @staticmethod
    def _role_arn(identity: IdentityContext, role_name: str) -> str:
        return f"arn:aws:iam::{identity.account_id}:role/{role_name}"
