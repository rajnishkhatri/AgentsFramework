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

from services.governance.agent_facts_registry import is_expired
from services.governance.path_safety import (
    is_safe_path_component,
    require_safe_path_component,
)
from trust.enums import IdentityStatus
from trust.models import AgentFacts, AuditEntry
from trust.signature import compute_signature, verify_signature

if TYPE_CHECKING:
    from google.cloud.storage import Client as StorageClient

logger = logging.getLogger("services.governance.agent_facts_gcs")

# Bounded retries for the conditional audit append (see ``_append_audit``).
_AUDIT_APPEND_ATTEMPTS = 5


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
        if not is_safe_path_component(agent_id):
            raise KeyError(f"Agent '{agent_id}' not found in gs://{self._bucket_name}")
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
        except ValueError as exc:
            # Malformed JSON or a schema violation: an unreadable card is unverified.
            logger.warning(
                "Agent %s failed verification: corrupt card (%s)", agent_id, exc
            )
            return False

        if facts.status != IdentityStatus.ACTIVE:
            return False
        if is_expired(facts):
            logger.warning("Agent %s failed verification: card expired", agent_id)
            return False

        facts_dict = facts.model_dump(mode="json")
        expected_hash = facts_dict.get("signature_hash", None)
        if not expected_hash:
            return False
        return verify_signature(
            self._signable_dict(facts_dict), self._secret, expected_hash
        )

    def register(self, facts: AgentFacts, registered_by: str) -> AgentFacts:
        require_safe_path_component(facts.agent_id, "agent_id")
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path(facts.agent_id))

        if blob.exists():
            raise ValueError(f"Agent '{facts.agent_id}' already registered")

        facts_dict = facts.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(facts_dict), self._secret)
        facts_dict["signature_hash"] = sig
        registered = AgentFacts.model_validate(facts_dict)

        from google.api_core.exceptions import PreconditionFailed

        try:
            # ``if_generation_match=0`` makes the create atomic: if another
            # writer registered this id after the existence check above, GCS
            # rejects the upload instead of overwriting their card.
            blob.upload_from_string(
                registered.model_dump_json(indent=2),
                content_type="application/json",
                if_generation_match=0,
            )
        except PreconditionFailed as exc:
            raise ValueError(f"Agent '{facts.agent_id}' already registered") from exc

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
        """Append one audit line, retrying when another writer got in first.

        GCS has no append, so this is read-modify-write. The upload is
        conditional on the generation that was read; a conflicting write
        fails the precondition and the append is retried on fresh content
        instead of overwriting the other writer's entry.
        """
        from google.api_core.exceptions import PreconditionFailed

        client = self._get_client()
        bucket = client.bucket(self._bucket_name)
        line = entry.model_dump_json() + "\n"

        for _attempt in range(_AUDIT_APPEND_ATTEMPTS):
            blob = bucket.blob(self._audit_blob_path(agent_id))
            if blob.exists():
                blob.reload()
                generation = blob.generation
                existing = blob.download_as_text()
            else:
                generation = 0
                existing = ""
            try:
                blob.upload_from_string(
                    existing + line,
                    content_type="application/x-ndjson",
                    if_generation_match=generation,
                )
                return
            except PreconditionFailed:
                continue

        raise RuntimeError(
            f"Could not append audit entry for agent '{agent_id}' after "
            f"{_AUDIT_APPEND_ATTEMPTS} conflicting writes"
        )


__all__ = ["AgentFactsGcsRegistry"]
