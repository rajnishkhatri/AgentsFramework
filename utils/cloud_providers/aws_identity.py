"""AWS implementation of the IdentityProvider protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from trust.cloud_identity import IdentityContext, VerificationResult
from trust.exceptions import AuthenticationError

if TYPE_CHECKING:
    from utils.cloud_providers.config import TrustProviderSettings

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_PROVIDER = "aws"


def _parse_arn(arn: str) -> dict[str, str]:
    parts = arn.split(":")
    return {
        "partition": parts[1] if len(parts) > 1 else "",
        "service": parts[2] if len(parts) > 2 else "",
        "region": parts[3] if len(parts) > 3 else "",
        "account_id": parts[4] if len(parts) > 4 else "",
        "resource": parts[5] if len(parts) > 5 else "",
    }


class AWSIdentityProvider:
    def __init__(self, settings: TrustProviderSettings) -> None:
        sts_kwargs: dict[str, Any] = {"region_name": settings.region}
        iam_kwargs: dict[str, Any] = {"region_name": settings.region}
        if settings.sts_endpoint:
            sts_kwargs["endpoint_url"] = settings.sts_endpoint
        if settings.iam_endpoint:
            iam_kwargs["endpoint_url"] = settings.iam_endpoint
        self._sts = boto3.client("sts", **sts_kwargs)
        self._iam = boto3.client("iam", **iam_kwargs)
        self._iam_kwargs = iam_kwargs

    def get_caller_identity(self) -> IdentityContext:
        try:
            resp = self._sts.get_caller_identity()
        except (ClientError, BotoCoreError) as exc:
            raise AuthenticationError(
                f"Failed to get caller identity: {exc}",
                provider=_PROVIDER,
                operation="get_caller_identity",
                original_error=exc,
            ) from exc
        parsed = _parse_arn(resp["Arn"])
        return IdentityContext(
            provider=_PROVIDER,
            principal_id=resp["UserId"],
            display_name=parsed["resource"],
            account_id=resp["Account"],
            raw_attributes=dict(resp),
        )

    def resolve_identity(self, identifier: str) -> IdentityContext:
        try:
            assume_resp = self._sts.assume_role(
                RoleArn=identifier,
                RoleSessionName="trust-resolve-identity",
            )
            assumed_creds = assume_resp["Credentials"]
            iam = boto3.client(
                "iam",
                aws_access_key_id=assumed_creds["AccessKeyId"],
                aws_secret_access_key=assumed_creds["SecretAccessKey"],
                aws_session_token=assumed_creds["SessionToken"],
                **{k: v for k, v in self._iam_kwargs.items() if k != "region_name"},
                region_name=self._iam_kwargs.get("region_name", "us-east-1"),
            )
            role_name = self._role_name_from_arn(identifier)
            role_resp = iam.get_role(RoleName=role_name)
            role = role_resp["Role"]
            tags_resp = iam.list_role_tags(RoleName=role_name)
            tags = {t["Key"]: t["Value"] for t in tags_resp.get("Tags", [])}
        except (ClientError, BotoCoreError) as exc:
            raise AuthenticationError(
                f"Failed to resolve identity for {identifier!r}: {exc}",
                provider=_PROVIDER,
                operation="resolve_identity",
                original_error=exc,
            ) from exc
        parsed = _parse_arn(role["Arn"])
        return IdentityContext(
            provider=_PROVIDER,
            principal_id=role.get("RoleId", ""),
            display_name=role["RoleName"],
            account_id=parsed["account_id"],
            roles=[role["RoleName"]],
            tags=tags,
            raw_attributes={"role": role},
        )

    def verify_identity(self, identity: IdentityContext) -> VerificationResult:
        if identity.session_expiry and identity.session_expiry < datetime.now(UTC):
            return VerificationResult(
                verified=False,
                reason="Session expired",
                provider=_PROVIDER,
                checked_at=datetime.now(UTC),
            )
        try:
            sts = self._build_subject_sts(identity)
            sts.get_caller_identity()
        except (ClientError, BotoCoreError) as exc:
            return VerificationResult(
                verified=False,
                reason=f"STS validation failed: {exc}",
                provider=_PROVIDER,
                checked_at=datetime.now(UTC),
            )
        return VerificationResult(
            verified=True,
            reason="Credentials valid",
            provider=_PROVIDER,
            checked_at=datetime.now(UTC),
        )

    def _build_subject_sts(self, identity: IdentityContext) -> Any:
        """Build an STS client scoped to the subject's credentials if available."""
        raw = identity.raw_attributes
        if all(k in raw for k in ("AccessKeyId", "SecretAccessKey")):
            return boto3.client(
                "sts",
                aws_access_key_id=raw["AccessKeyId"],
                aws_secret_access_key=raw["SecretAccessKey"],
                aws_session_token=raw.get("SessionToken"),
            )
        return self._sts

    @staticmethod
    def _role_name_from_arn(arn: str) -> str:
        resource = arn.rsplit(":", 1)[-1]
        if "/" in resource:
            return resource.split("/", 1)[-1]
        return resource
