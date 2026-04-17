"""AWS implementation of the CredentialProvider protocol."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from trust.cloud_identity import TemporaryCredentials
from trust.exceptions import CredentialError
from trust.models import AgentFacts

if TYPE_CHECKING:
    from utils.cloud_providers.config import TrustProviderSettings

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_PROVIDER = "aws"
_DEFAULT_DURATION_SECONDS = 900


class AWSCredentialProvider:
    def __init__(self, settings: TrustProviderSettings) -> None:
        kwargs: dict[str, Any] = {"region_name": settings.region}
        if settings.sts_endpoint:
            kwargs["endpoint_url"] = settings.sts_endpoint
        self._sts = boto3.client("sts", **kwargs)

    def issue_credentials(
        self, agent_facts: AgentFacts, scope: list[str],
    ) -> TemporaryCredentials:
        role_arn = self._resolve_role_arn(agent_facts)
        duration = int(
            agent_facts.metadata.get("credential_ttl_seconds", _DEFAULT_DURATION_SECONDS)
        )
        assume_kwargs: dict[str, Any] = {
            "RoleArn": role_arn,
            "RoleSessionName": agent_facts.agent_id,
            "DurationSeconds": duration,
        }
        if scope:
            assume_kwargs["Policy"] = self._build_session_policy(scope)
        try:
            resp = self._sts.assume_role(**assume_kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise CredentialError(
                f"Failed to assume role {role_arn!r} for agent {agent_facts.agent_id!r}: {exc}",
                provider=_PROVIDER,
                operation="issue_credentials",
                original_error=exc,
            ) from exc
        creds = resp["Credentials"]
        return TemporaryCredentials(
            provider=_PROVIDER,
            access_token=creds["AccessKeyId"],
            expiry=creds["Expiration"],
            scope=scope,
            agent_id=agent_facts.agent_id,
            raw_credentials={
                "AccessKeyId": creds["AccessKeyId"],
                "SecretAccessKey": creds["SecretAccessKey"],
                "SessionToken": creds["SessionToken"],
                "RoleArn": role_arn,
            },
        )

    def refresh_credentials(
        self, credentials: TemporaryCredentials,
    ) -> TemporaryCredentials:
        role_arn = credentials.raw_credentials.get("RoleArn", "")
        if not role_arn:
            raise CredentialError(
                "Cannot refresh: original RoleArn not found in raw_credentials.",
                provider=_PROVIDER,
                operation="refresh_credentials",
            )
        assume_kwargs: dict[str, Any] = {
            "RoleArn": role_arn,
            "RoleSessionName": credentials.agent_id,
            "DurationSeconds": _DEFAULT_DURATION_SECONDS,
        }
        if credentials.scope:
            assume_kwargs["Policy"] = self._build_session_policy(list(credentials.scope))
        try:
            resp = self._sts.assume_role(**assume_kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise CredentialError(
                f"Failed to refresh credentials for agent {credentials.agent_id!r}: {exc}",
                provider=_PROVIDER,
                operation="refresh_credentials",
                original_error=exc,
            ) from exc
        creds = resp["Credentials"]
        return TemporaryCredentials(
            provider=_PROVIDER,
            access_token=creds["AccessKeyId"],
            expiry=creds["Expiration"],
            scope=list(credentials.scope),
            agent_id=credentials.agent_id,
            raw_credentials={
                "AccessKeyId": creds["AccessKeyId"],
                "SecretAccessKey": creds["SecretAccessKey"],
                "SessionToken": creds["SessionToken"],
                "RoleArn": role_arn,
            },
        )

    def revoke_credentials(self, credentials: TemporaryCredentials) -> None:
        raise NotImplementedError(
            "revoke_credentials is not implemented in Phase 1. "
            "STS tokens cannot be directly revoked."
        )

    @staticmethod
    def _resolve_role_arn(agent_facts: AgentFacts) -> str:
        explicit = agent_facts.metadata.get("role_arn")
        if not explicit:
            raise CredentialError(
                f"AgentFacts for {agent_facts.agent_id!r} missing required "
                f"'role_arn' in metadata",
                provider=_PROVIDER,
                operation="_resolve_role_arn",
            )
        return str(explicit)

    @staticmethod
    def _build_session_policy(scope: list[str]) -> str:
        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": scope,
                "Resource": "*",
            }],
        })
