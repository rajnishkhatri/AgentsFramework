"""AgentFactsGcsRegistry: GCS-backed agent identity card registry.

Read-only in the runtime path — signed JSON blobs are pre-deployed to
``gs://{bucket}/{prefix}/{agent_id}.json``. The registry reads and verifies
signatures using the same trust.signature primitives as the local
``AgentFactsRegistry``.

Write operations (register, suspend, restore) are supported for
bootstrapping and CI but are expected to be infrequent in production.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from trust.enums import IdentityStatus
from trust.models import AgentFacts, AuditEntry
from trust.signature import compute_signature, verify_signature

if TYPE_CHECKING:
    from google.cloud.storage import Client as StorageClient

logger = logging.getLogger("services.governance.agent_facts_gcs")


class AgentFactsGcsRegistry:
    """GCS-backed registry for signed AgentFacts identity cards."""

    def __init__(
        self,
        bucket_name: str,
        *,
        secret: str | None = None,
        client: StorageClient | None = None,
        prefix: str = "agent_facts",
    ) -> None:
        self._bucket_name = bucket_name
        self._prefix = prefix.rstrip("/")
        self._client = client
        resolved = secret or os.environ.get("AGENT_FACTS_SECRET")
        if not resolved:
            raise ValueError(
                "AgentFactsGcsRegistry requires a secret: pass it explicitly "
                "or set the AGENT_FACTS_SECRET environment variable"
            )
        self._secret = resolved

    def _get_client(self) -> StorageClient:
        if self._client is None:
            from google.cloud.storage import Client

            self._client = Client()
        return self._client

    def _blob_path(self, agent_id: str) -> str:
        return f"{self._prefix}/{agent_id}.json"

    def _audit_blob_path(self, agent_id: str) -> str:
        return f"{self._prefix}/{agent_id}_audit.jsonl"

    def _signable_dict(self, facts_dict: dict) -> dict:
        d = dict(facts_dict)
        d.pop("signature_hash", None)
        return d

    def get(self, agent_id: str) -> AgentFacts:
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path(agent_id))

        if not blob.exists():
            raise KeyError(f"Agent '{agent_id}' not found in gs://{self._bucket_name}")

        data = blob.download_as_text()
        return AgentFacts.model_validate_json(data)

    def verify(self, agent_id: str) -> bool:
        try:
            facts = self.get(agent_id)
        except KeyError:
            return False

        if facts.status != IdentityStatus.ACTIVE:
            return False

        facts_dict = facts.model_dump(mode="json")
        expected_hash = facts_dict.get("signature_hash", None)
        if not expected_hash:
            return False
        return verify_signature(
            self._signable_dict(facts_dict), self._secret, expected_hash
        )

    def register(self, facts: AgentFacts, registered_by: str) -> AgentFacts:
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path(facts.agent_id))

        if blob.exists():
            raise ValueError(f"Agent '{facts.agent_id}' already registered")

        facts_dict = facts.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(facts_dict), self._secret)
        facts_dict["signature_hash"] = sig
        registered = AgentFacts.model_validate(facts_dict)

        blob.upload_from_string(
            registered.model_dump_json(indent=2),
            content_type="application/json",
        )

        self._append_audit(
            facts.agent_id,
            AuditEntry(
                agent_id=facts.agent_id,
                action="register",
                performed_by=registered_by,
                timestamp=datetime.now(UTC),
                details={"status": registered.status.value},
            ),
        )
        logger.info("Registered agent %s by %s", facts.agent_id, registered_by)
        return registered

    def suspend(self, agent_id: str, reason: str, suspended_by: str) -> None:
        facts = self.get(agent_id)
        updated = facts.model_copy(update={"status": IdentityStatus.SUSPENDED})
        updated_dict = updated.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(updated_dict), self._secret)
        updated_dict["signature_hash"] = sig
        final = AgentFacts.model_validate(updated_dict)

        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path(agent_id))
        blob.upload_from_string(
            final.model_dump_json(indent=2),
            content_type="application/json",
        )

        self._append_audit(
            agent_id,
            AuditEntry(
                agent_id=agent_id,
                action="suspend",
                performed_by=suspended_by,
                timestamp=datetime.now(UTC),
                details={"reason": reason},
            ),
        )
        logger.info("Suspended agent %s: %s", agent_id, reason)

    def restore(self, agent_id: str, reason: str, restored_by: str) -> None:
        facts = self.get(agent_id)
        updated = facts.model_copy(update={"status": IdentityStatus.ACTIVE})
        updated_dict = updated.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(updated_dict), self._secret)
        updated_dict["signature_hash"] = sig
        final = AgentFacts.model_validate(updated_dict)

        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path(agent_id))
        blob.upload_from_string(
            final.model_dump_json(indent=2),
            content_type="application/json",
        )

        self._append_audit(
            agent_id,
            AuditEntry(
                agent_id=agent_id,
                action="restore",
                performed_by=restored_by,
                timestamp=datetime.now(UTC),
                details={"reason": reason},
            ),
        )
        logger.info("Restored agent %s: %s", agent_id, reason)

    def list_agent_ids(self) -> list[str]:
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        prefix = f"{self._prefix}/"
        blobs = bucket.list_blobs(prefix=prefix)

        ids: list[str] = []
        for blob in blobs:
            name = blob.name.removeprefix(prefix)
            if name.endswith(".json") and not name.endswith("_audit.jsonl"):
                ids.append(name.removesuffix(".json"))
        ids.sort()
        return ids

    def _append_audit(self, agent_id: str, entry: AuditEntry) -> None:
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._audit_blob_path(agent_id))

        existing = ""
        if blob.exists():
            existing = blob.download_as_text()

        updated = existing + entry.model_dump_json() + "\n"
        blob.upload_from_string(updated, content_type="application/x-ndjson")


__all__ = ["AgentFactsGcsRegistry"]
