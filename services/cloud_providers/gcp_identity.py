"""GCP Workload Identity → AgentFacts mapping.

Maps a GCP service account (from Workload Identity Federation or
metadata server) to a registered AgentFacts identity card. Used in the
Cloud Run composition root to resolve the running service's identity
without hardcoding agent IDs.

The mapping is driven by the ``GCP_SERVICE_ACCOUNT`` env var (set
automatically by Cloud Run) or by querying the metadata server.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from trust.models import AgentFacts

logger = logging.getLogger("services.cloud_providers.gcp_identity")


class AgentFactsProvider(Protocol):
    """Minimal interface for looking up AgentFacts by agent_id."""

    def get(self, agent_id: str) -> AgentFacts: ...


class GcpIdentityResolver:
    """Resolves the current GCP service account to an AgentFacts identity.

    Strategy:
    1. Check ``GCP_AGENT_ID`` env var (explicit override for testing).
    2. Check ``GCP_SERVICE_ACCOUNT`` env var (set by Cloud Run).
    3. Query the GCE metadata server for the default service account.

    The resolved service account email is mapped to an agent_id via a
    configurable mapping dict or a naming convention (SA email prefix).
    """

    def __init__(
        self,
        registry: AgentFactsProvider,
        *,
        sa_to_agent_id: dict[str, str] | None = None,
    ) -> None:
        self._registry = registry
        self._sa_to_agent_id = sa_to_agent_id or {}

    def resolve(self) -> AgentFacts:
        """Resolve the current runtime identity to AgentFacts.

        Raises:
            RuntimeError: If no identity can be resolved.
            KeyError: If the resolved agent_id is not in the registry.
        """
        agent_id = os.environ.get("GCP_AGENT_ID")
        if agent_id:
            logger.info("Resolved identity via GCP_AGENT_ID=%s", agent_id)
            return self._registry.get(agent_id)

        sa_email = os.environ.get("GCP_SERVICE_ACCOUNT")
        if not sa_email:
            sa_email = self._query_metadata_server()

        if not sa_email:
            raise RuntimeError(
                "Cannot resolve GCP identity: neither GCP_AGENT_ID nor "
                "GCP_SERVICE_ACCOUNT is set, and metadata server is unreachable"
            )

        agent_id = self._map_sa_to_agent_id(sa_email)
        logger.info("Resolved identity: SA=%s → agent_id=%s", sa_email, agent_id)
        return self._registry.get(agent_id)

    def _map_sa_to_agent_id(self, sa_email: str) -> str:
        if sa_email in self._sa_to_agent_id:
            return self._sa_to_agent_id[sa_email]
        # Convention: use the SA local part (before @) as agent_id
        local_part = sa_email.split("@")[0]
        return local_part

    @staticmethod
    def _query_metadata_server() -> str | None:
        """Query GCE metadata server for the default SA email.

        Returns None if not running on GCP or metadata server is unreachable.
        """
        try:
            import urllib.request

            url = (
                "http://metadata.google.internal/computeMetadata/v1/"
                "instance/service-accounts/default/email"
            )
            req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            return None


__all__ = ["GcpIdentityResolver"]
