"""In-memory MemoryBackend for tests and local dev.

Re-exports the `InMemoryMemoryBackend` defined in `services.long_term_memory`.
External backends (Mem0, SQLite, pgvector, ...) provide their own modules
in this package and depend on `MemoryRecord` from the service module.
"""

from __future__ import annotations

from services.long_term_memory import InMemoryMemoryBackend

__all__ = ["InMemoryMemoryBackend"]
