"""AgentFactsRegistry: identity card management.

JSON-file-backed registry with HMAC signature integrity.
Uses trust.signature for compute/verify operations.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trust.enums import IdentityStatus
from trust.models import AgentFacts, AuditEntry
from trust.signature import compute_signature, verify_signature

logger = logging.getLogger("services.governance.agent_facts")


class AgentFactsRegistry:
    def __init__(self, storage_dir: Path | str, secret: str | None = None) -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        resolved = secret or os.environ.get("AGENT_FACTS_SECRET")
        if not resolved:
            raise ValueError(
                "AgentFactsRegistry requires a secret: pass it explicitly "
                "or set the AGENT_FACTS_SECRET environment variable"
            )
        self._secret = resolved

    def _facts_path(self, agent_id: str) -> Path:
        return self._storage_dir / f"{agent_id}.json"

    def _audit_path(self, agent_id: str) -> Path:
        return self._storage_dir / f"{agent_id}_audit.jsonl"

    def _signable_dict(self, facts_dict: dict) -> dict:
        """Return the dict with signature_hash removed for signing."""
        d = dict(facts_dict)
        d.pop("signature_hash", None)
        return d

    def register(self, facts: AgentFacts, registered_by: str) -> AgentFacts:
        path = self._facts_path(facts.agent_id)
        if path.exists():
            raise ValueError(f"Agent '{facts.agent_id}' already registered")

        facts_dict = facts.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(facts_dict), self._secret)
        facts_dict["signature_hash"] = sig
        registered = AgentFacts.model_validate(facts_dict)

        path.write_text(registered.model_dump_json(indent=2))
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

    def verify(self, agent_id: str) -> bool:
        path = self._facts_path(agent_id)
        if not path.exists():
            return False

        facts = AgentFacts.model_validate_json(path.read_text())
        if facts.status != IdentityStatus.ACTIVE:
            return False

        facts_dict = facts.model_dump(mode="json")
        expected_hash = facts_dict.get("signature_hash", None)
        if not expected_hash:
            return False
        return verify_signature(self._signable_dict(facts_dict), self._secret, expected_hash)

    def get(self, agent_id: str) -> AgentFacts:
        path = self._facts_path(agent_id)
        if not path.exists():
            raise KeyError(f"Agent '{agent_id}' not found")
        return AgentFacts.model_validate_json(path.read_text())

    def suspend(self, agent_id: str, reason: str, suspended_by: str) -> None:
        facts = self.get(agent_id)
        updated = facts.model_copy(update={"status": IdentityStatus.SUSPENDED})
        updated_dict = updated.model_dump(mode="json")
        sig = compute_signature(self._signable_dict(updated_dict), self._secret)
        updated_dict["signature_hash"] = sig
        final = AgentFacts.model_validate(updated_dict)

        self._facts_path(agent_id).write_text(final.model_dump_json(indent=2))
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

        self._facts_path(agent_id).write_text(final.model_dump_json(indent=2))
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

    def audit_trail(self, agent_id: str) -> list[AuditEntry]:
        path = self._audit_path(agent_id)
        if not path.exists():
            return []
        entries = []
        for line in path.read_text().strip().split("\n"):
            if line:
                entries.append(AuditEntry.model_validate_json(line))
        return entries

    def _append_audit(self, agent_id: str, entry: AuditEntry) -> None:
        path = self._audit_path(agent_id)
        with open(path, "a") as f:
            f.write(entry.model_dump_json() + "\n")
