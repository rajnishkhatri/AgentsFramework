"""Mem0 live smoke test (NOT a CI test — needs a real MEM0_API_KEY).

Validates that the real Mem0 SDK surface matches what the _FakeMem0Sdk in
tests/services/memory_backends/test_mem0_backend.py models — the TDD-review
LOW #2 gap (CI never exercises _client()'s real `from mem0 import` branch).

Runs put -> get -> search -> delete against Mem0 Cloud under a UNIQUE throwaway
user_id, then verifies the row is gone. Self-cleaning. Loads MEM0_API_KEY /
MEM0_BASE_URL from .env. Prints PASS/FAIL per step; exits non-zero on any failure.

Usage:  .venv/bin/python scripts/mem0_smoke.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    """Minimal .env loader (no python-dotenv dependency assumed)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def main() -> int:
    _load_env()
    api_key = os.environ.get("MEM0_API_KEY", "")
    base_url = os.environ.get("MEM0_BASE_URL", "https://api.mem0.ai")
    if not api_key:
        print("FAIL: MEM0_API_KEY not found in environment/.env")
        return 2

    from services.long_term_memory import MemoryRecord
    from services.memory_backends.mem0 import Mem0MemoryBackend

    backend = Mem0MemoryBackend(api_key=api_key, base_url=base_url)

    # Unique throwaway subject so we never touch a real user's memories.
    user_id = f"smoke-{uuid.uuid4().hex[:12]}"
    key = "smoke-key-1"
    secret = f"SMOKE-CONTENT-{uuid.uuid4().hex[:8]}"
    print(f"user_id={user_id} base_url={base_url} sdk-key-len={len(api_key)}")

    # Capture logs to assert the privacy invariant (content never logged).
    buf = logging.handlers.MemoryHandler(capacity=10_000)
    root = logging.getLogger()
    root.addHandler(buf)
    root.setLevel(logging.DEBUG)

    failures: list[str] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    try:
        # 1. put
        backend.put(
            MemoryRecord(
                user_id=user_id,
                key=key,
                payload={"text": secret},
                metadata={"type": "semantic", "source": "smoke"},
            )
        )
        step("put", True)

        # Mem0 Cloud indexes asynchronously; give it a moment before read-back.
        time.sleep(2.0)

        # 2. get by (user_id, key)
        got = backend.get(user_id=user_id, key=key)
        step(
            "get round-trips payload+metadata",
            got is not None
            and got.payload.get("text") == secret
            and got.metadata.get("type") == "semantic",
            f"got={'<none>' if got is None else got.payload.get('text')!r}",
        )

        # 3. search returns the row, user-scoped
        hits = backend.search(user_id=user_id, query="SMOKE", limit=10)
        step(
            "search returns the stored row",
            any(h.payload.get("text") == secret for h in hits),
            f"{len(hits)} hit(s)",
        )

        # 4. delete by key, then confirm gone
        deleted = backend.delete(user_id=user_id, key=key)
        step("delete returns True", deleted is True)
        time.sleep(2.0)
        gone = backend.get(user_id=user_id, key=key)
        step("get after delete returns None", gone is None)

        # 5. delete of a missing key returns False (failure-path parity)
        step(
            "delete missing key returns False",
            backend.delete(user_id=user_id, key="never") is False,
        )

    finally:
        root.removeHandler(buf)

    # Privacy invariant: the stored content must NOT appear in any log line.
    logged = "\n".join(r.getMessage() for r in buf.buffer)
    step("privacy: content absent from logs", secret not in logged)

    # Best-effort cleanup in case an assertion left the row.
    try:
        backend.delete(user_id=user_id, key=key)
    except Exception:
        pass

    print()
    if failures:
        print(f"SMOKE FAILED: {', '.join(failures)}")
        return 1
    print("SMOKE PASSED — real Mem0 SDK surface matches the adapter contract.")
    return 0


if __name__ == "__main__":
    import logging.handlers  # noqa: E402 — needed for MemoryHandler

    raise SystemExit(main())
