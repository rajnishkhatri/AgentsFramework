"""Pluggable backends for `services.long_term_memory`.

External backends (Mem0, SQLite, pgvector, ...) live as siblings of
`in_memory.py` and are wired by the composition root. The service core
imports neither this package nor any specific backend.
"""

from __future__ import annotations

from services.memory_backends.in_memory import InMemoryMemoryBackend

__all__ = ["InMemoryMemoryBackend"]
