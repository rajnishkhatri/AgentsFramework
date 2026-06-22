"""Mem0-backed ``MemoryBackend`` for ``services.long_term_memory``.

Piece B of the memory live-infra wiring. The in-memory + sqlite backends are
dev/test only — their state evaporates on a Cloud Run restart. This backend
delegates to the Mem0 SDK so long-term memory is durable in production, while
keeping the SAME sync ``MemoryBackend`` Protocol the LangGraph nodes consume
(``put`` / ``get`` / ``search`` / ``delete``). Swapping it in is a one-line
composition-root change (plan §10 swap-radius), zero changes under
``orchestration/`` or ``agent_ui_adapter/``.

## Sync, not async (the wiring-note decision)

The react loop's recall/store happen inside *sync* LangGraph nodes, so
an async backend would need an event-loop bridge — a hazard when a loop is
already running. The Mem0 SDK (``mem0.MemoryClient``) is itself synchronous,
so this backend talks to it directly. The parallel async ``MemoryClient``
port + ``Mem0CloudClient`` adapter were deleted in replace-mem0-pgvector
Phase 3 (Branch A) — they had zero non-test consumers. This sync backend is
itself retired in Phase 4 (composition switch to ``PgVectorMemoryBackend``)
and the file deleted in Phase 5 S6 after the 24h soak.

## (user_id, key) ↔ Mem0 mapping

Mem0 auto-generates an opaque ``id`` per memory and stores free-text ``content``;
it has no caller-supplied key. We carry our ``key`` (plus the structured
``payload`` / ``metadata``) inside Mem0's per-memory ``metadata`` blob, and
resolve ``get`` / ``delete`` by scanning the user's memories for a metadata
``key`` match. ``put`` of an existing key is a delete-then-add upsert so a key
maps to exactly one row.

## Privacy invariant

Memory CONTENT is the stored text — it goes *to* Mem0 by design. But it MUST
NOT appear in a log line: this module logs only ``user_id`` / ``key`` / counts,
mirroring ``LongTermMemoryService``.

SDK pin (rule A9): ``mem0ai >= 0.1.100`` (declared in pyproject).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.long_term_memory import MemoryBackendError, MemoryRecord

logger = logging.getLogger("services.memory_backends.mem0")

# Metadata keys used to round-trip the Protocol's structured fields through
# Mem0's free-form per-memory metadata blob.
_KEY_FIELD = "__ltm_key"
_PAYLOAD_FIELD = "__ltm_payload"
_META_FIELD = "__ltm_metadata"


class Mem0MemoryBackend:
    """``MemoryBackend`` delegating to the synchronous Mem0 SDK client.

    Args:
        api_key: Mem0 Cloud API key (``MEM0_API_KEY``). Required unless a
            pre-built ``sdk_client`` is supplied (tests).
        base_url: Mem0 endpoint (``MEM0_BASE_URL``).
        sdk_client: optional pre-built/sync SDK client for tests.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.mem0.ai",
        sdk_client: Any | None = None,
    ) -> None:
        if sdk_client is None and not api_key:
            raise ValueError(
                "Mem0MemoryBackend requires a non-empty api_key (or sdk_client)"
            )
        self._api_key = api_key
        self._base_url = base_url
        self._sdk_client = sdk_client

    def _client(self) -> Any:
        if self._sdk_client is not None:
            return self._sdk_client
        # Lazy import confines the SDK to the method body; the architecture
        # test checks top-level imports only.
        from mem0 import MemoryClient as _SdkClient

        self._sdk_client = _SdkClient(
            api_key=self._api_key, host=self._base_url
        )
        return self._sdk_client

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _decode_blob(value: Any) -> dict:
        """Parse a JSON-string structured field back to a dict (or {})."""
        if isinstance(value, dict):  # tolerate SDKs that preserve nesting
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @classmethod
    def _row_to_record(cls, user_id: str, row: dict) -> MemoryRecord:
        meta = row.get("metadata") or {}
        # Our structured fields are stored as JSON STRINGS because Mem0 Cloud
        # flattens nested metadata (a nested dict comes back as "k.v" strings /
        # lists). Decode them; fall back to the verbatim memory text so
        # externally-created Mem0 rows still surface.
        payload = cls._decode_blob(meta.get(_PAYLOAD_FIELD))
        if not payload:
            payload = {"text": str(row.get("memory") or row.get("text") or "")}
        structured_meta = cls._decode_blob(meta.get(_META_FIELD))
        key = meta.get(_KEY_FIELD)
        return MemoryRecord(
            user_id=user_id,
            key=str(key) if key is not None else str(row.get("id", "")),
            payload=payload,
            metadata=structured_meta,
        )

    @staticmethod
    def _rows(result: Any) -> list[dict]:
        """Unwrap the Mem0 v2 paginated envelope to a flat row list.

        ``get_all`` / ``search`` return ``{"results": [...]}`` (v1.1+); older
        clients returned a bare list. Tolerate both so the backend works across
        SDK minor versions.
        """
        if isinstance(result, dict):
            rows = result.get("results", [])
        else:
            rows = result or []
        return [r for r in rows if isinstance(r, dict)]

    def _get_all(self, user_id: str) -> list[dict]:
        """List a user's memories. Mem0 v2 requires ``filters={user_id}`` and
        REJECTS a top-level ``user_id`` kwarg (``ENTITY_PARAMS``)."""
        return self._rows(
            self._client().get_all(filters={"user_id": user_id})
        )

    def _find_row_id(self, user_id: str, key: str) -> str | None:
        """Resolve our caller key to Mem0's opaque id (or None)."""
        for row in self._get_all(user_id):
            meta = row.get("metadata") or {}
            if meta.get(_KEY_FIELD) == key:
                rid = row.get("id")
                return str(rid) if rid is not None else None
        return None

    # ── MemoryBackend Protocol ───────────────────────────────────────

    def put(self, record: MemoryRecord) -> None:
        text = str(record.payload.get("text", "")) if record.payload else ""
        # Mem0 Cloud flattens nested metadata (a dict round-trips as "k.v"
        # strings), so encode our structured fields as JSON STRINGS — flat
        # values Mem0 stores verbatim — and decode them on read.
        metadata = {
            _KEY_FIELD: record.key,
            _PAYLOAD_FIELD: json.dumps(dict(record.payload or {})),
            _META_FIELD: json.dumps(dict(record.metadata or {})),
        }
        try:
            # Upsert: clear any existing row for this key first so a key maps
            # to exactly one Mem0 memory.
            existing = self._find_row_id(record.user_id, record.key)
            if existing is not None:
                self._client().delete(memory_id=existing)
            # ``add`` accepts ``user_id`` / ``metadata`` top-level (unlike
            # get_all/search); ``messages`` is the positional payload.
            #
            # ``infer=False`` is REQUIRED: this is a keyed (user_id, key) store,
            # so we need the text stored VERBATIM and SYNCHRONOUSLY. Mem0's
            # default ``infer=True`` runs an async LLM extraction that may
            # reword the fact, store it under a generated id with a PENDING
            # status, or drop it entirely if the LLM judges it non-memorable —
            # all of which break exact-key read-back (surfaced by the live
            # smoke test). Our own typed extraction is a separate component
            # (Phase 2 MemoryExtractor); the backend must not double-infer.
            self._client().add(
                text, user_id=record.user_id, metadata=metadata, infer=False
            )
        except Exception as exc:  # noqa: BLE001 — wrapped per Protocol contract
            raise MemoryBackendError(
                f"mem0 backend failed during put("
                f"user_id={record.user_id!r}, key={record.key!r})"
            ) from exc
        logger.info(
            "memory.backend.put user_id=%s key=%s", record.user_id, record.key
        )

    def get(self, user_id: str, key: str) -> MemoryRecord | None:
        try:
            for row in self._get_all(user_id):
                meta = row.get("metadata") or {}
                if meta.get(_KEY_FIELD) == key:
                    return self._row_to_record(user_id, row)
        except Exception as exc:  # noqa: BLE001
            raise MemoryBackendError(
                f"mem0 backend failed during get("
                f"user_id={user_id!r}, key={key!r})"
            ) from exc
        return None

    def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryRecord]:
        try:
            # Mem0 v2: user scope rides ``filters`` (top-level ``user_id`` is
            # rejected); the result count knob is ``top_k``.
            rows = self._rows(
                self._client().search(
                    query, filters={"user_id": user_id}, top_k=limit
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise MemoryBackendError(
                f"mem0 backend failed during search(user_id={user_id!r})"
            ) from exc
        records = [self._row_to_record(user_id, row) for row in rows[:limit]]
        logger.debug(
            "memory.backend.search user_id=%s count=%d", user_id, len(records)
        )
        return records

    def delete(self, user_id: str, key: str) -> bool:
        try:
            rid = self._find_row_id(user_id, key)
            if rid is None:
                return False
            self._client().delete(memory_id=rid)
        except Exception as exc:  # noqa: BLE001
            raise MemoryBackendError(
                f"mem0 backend failed during delete("
                f"user_id={user_id!r}, key={key!r})"
            ) from exc
        logger.info(
            "memory.backend.delete user_id=%s key=%s", user_id, key
        )
        return True

    def list_all(self, user_id: str) -> list[MemoryRecord]:
        """All of a user's memories (A1 optional capability).

        Uses Mem0's ``get_all`` (filtered by user_id) — the reliable list path.
        ``search`` with an empty query is unreliable for vector backends, so the
        service prefers this method for count/consolidate.
        """
        try:
            rows = self._get_all(user_id)
        except Exception as exc:  # noqa: BLE001
            raise MemoryBackendError(
                f"mem0 backend failed during list_all(user_id={user_id!r})"
            ) from exc
        return [self._row_to_record(user_id, row) for row in rows]


__all__ = ["Mem0MemoryBackend"]
