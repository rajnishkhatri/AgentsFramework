"""Gate for ``scripts/fetch_memory_trace.py`` (memory governance audit helper).

Pure, deterministic, no network — ``urllib.request.urlopen`` is mocked away.
Failure-first: no carrier → exit 2; persistent 429 during fallback → skip and
continue, not crash.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

from scripts import fetch_memory_trace as fmt


def _resp(payload: dict) -> MagicMock:
    body = json.dumps(payload).encode()
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://langfuse.test/api",
        code,
        "err",
        {},
        io.BytesIO(body.encode()),
    )


def test_has_memory_carrier_matches_dotted_and_legacy_names() -> None:
    assert fmt._has_memory_carrier([{"name": "memory.recalled"}])
    assert fmt._has_memory_carrier([{"name": "span/MEMORY_STORED"}])
    assert not fmt._has_memory_carrier([{"name": "run.started"}, {"name": "llm.call"}])


def test_find_by_name_picks_latest_trace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "memory.recalled": {
            "data": [
                {"traceId": "trace-old", "startTime": "2026-06-18T10:00:00Z"},
            ]
        },
        "memory.stored": {
            "data": [
                {"traceId": "trace-new", "timestamp": "2026-06-18T11:00:00Z"},
            ]
        },
    }

    def fake_get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
        assert path == "/api/public/observations"
        assert params is not None
        return pages[params["name"]]

    monkeypatch.setattr(fmt, "_get", fake_get)
    assert fmt._find_by_name("https://langfuse.test", None) == "trace-new"


def test_find_by_name_passes_since_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def fake_get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
        seen.append(params or {})
        return {"data": []}

    monkeypatch.setattr(fmt, "_get", fake_get)
    fmt._find_by_name("https://langfuse.test", "2026-06-18T09:55:00Z")
    assert len(seen) == 2
    assert all(p.get("fromStartTime") == "2026-06-18T09:55:00Z" for p in seen)


def test_get_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    calls = {"n": 0}

    def fake_open(req, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(429)
        return _resp({"ok": True})

    with patch.object(fmt.urllib.request, "urlopen", side_effect=fake_open):
        with patch.object(fmt.time, "sleep"):
            out = fmt._get("https://langfuse.test", "/api/public/traces")
    assert out == {"ok": True}
    assert calls["n"] == 3


def test_main_exit_2_when_no_carriers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(sys, "argv", ["fetch_memory_trace.py"])

    def fake_get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
        if path == "/api/public/observations":
            return {"data": []}
        if path == "/api/public/traces":
            return {"data": [{"id": "t1"}, {"id": "t2"}]}
        return {"observations": [{"name": "run.started"}]}

    monkeypatch.setattr(fmt, "_get", fake_get)
    assert fmt.main() == 2


def test_main_fallback_skips_429_trace_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    out = tmp_path / "trace.json"
    monkeypatch.setattr(sys, "argv", ["fetch_memory_trace.py", "--out", str(out)])

    def fake_get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
        if path == "/api/public/observations":
            return {"data": []}
        if path == "/api/public/traces":
            return {"data": [{"id": "blocked"}, {"id": "good"}]}
        if path.endswith("/blocked"):
            raise _http_error(429)
        return {
            "observations": [
                {"name": "run.started"},
                {"name": "memory.stored", "metadata": {"key": "units"}},
            ]
        }

    monkeypatch.setattr(fmt, "_get", fake_get)
    monkeypatch.setattr(fmt.time, "sleep", lambda _: None)
    assert fmt.main() == 0
    payload = json.loads(out.read_text())
    assert any(o.get("name") == "memory.stored" for o in payload)


def test_main_trace_id_skips_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    out = tmp_path / "out.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_memory_trace.py", "--trace-id", "explicit-id", "--out", str(out)],
    )

    def fake_get(host: str, path: str, params: dict | None = None, *, retries: int = 5) -> dict:
        assert path == "/api/public/traces/explicit-id"
        return {"observations": [{"name": "memory.recalled", "metadata": {"count": 1}}]}

    monkeypatch.setattr(fmt, "_get", fake_get)
    assert fmt.main() == 0
    payload = json.loads(out.read_text())
    assert payload[0]["name"] == "memory.recalled"
