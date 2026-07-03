"""Runtime-readable Subject-Coach judge switches (GCS or local file).

Small L2 horizontal service mirroring ``goal_judge_runtime_config.py``
(Subject-Coach design §7.2 / ADR-0008): versioned JSON config with TTL cache,
bounded reads, stale-on-error degradation, and env fallback. No langgraph
imports — wiring lives in the ``meta/`` sampler job and (later) middleware.

Posture contract: **every flag defaults OFF** and malformed config fails DARK
(off), never open — the CI path must never see a live judge LLM, and
``coach_leakage_gate_enabled`` may flip only after the §7.4 calibration floor
(TNR ≥ 0.95, TPR ≥ 0.90, κ ≥ 0.75) is certified. ``coach_judge_sample_rate``
defaults to the design's 0.10 sampling band.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from google.cloud.storage import Client as StorageClient

logger = logging.getLogger("services.subject_coach_judge_runtime_config")

DEFAULT_SAMPLE_RATE = 0.10
_DEFAULT_TTL_S = 30.0
_DEFAULT_TIMEOUT_S = 2.0
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="coach-judge-config")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _env_sample_rate() -> float:
    raw = os.environ.get("COACH_JUDGE_SAMPLE_RATE", "").strip()
    if not raw:
        return DEFAULT_SAMPLE_RATE
    try:
        rate = float(raw)
    except ValueError:
        return DEFAULT_SAMPLE_RATE
    return max(0.0, min(1.0, rate))


class SubjectCoachJudgeRuntimeConfig(BaseModel):
    """Versioned on-disk / GCS posture document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    coach_grader_judge_enabled: bool = False
    coach_pedagogy_judge_enabled: bool = False
    coach_judge_sample_rate: float = Field(default=DEFAULT_SAMPLE_RATE, ge=0.0, le=1.0)
    coach_leakage_gate_enabled: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by: str = "unknown"


@dataclass(frozen=True)
class ResolvedSubjectCoachJudgeConfig:
    """Effective posture after precedence resolution (uri > env > defaults)."""

    coach_grader_judge_enabled: bool
    coach_pedagogy_judge_enabled: bool
    coach_judge_sample_rate: float
    coach_leakage_gate_enabled: bool
    source: str
    schema_version: int | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


def _posture_dict(resolved: ResolvedSubjectCoachJudgeConfig) -> dict[str, Any]:
    return {
        "grader_judge_enabled": resolved.coach_grader_judge_enabled,
        "pedagogy_judge_enabled": resolved.coach_pedagogy_judge_enabled,
        "sample_rate": resolved.coach_judge_sample_rate,
        "leakage_gate_enabled": resolved.coach_leakage_gate_enabled,
        "source": resolved.source,
        "schema_version": resolved.schema_version,
        "updated_at": resolved.updated_at.isoformat() if resolved.updated_at else None,
        "updated_by": resolved.updated_by,
    }


class InMemorySubjectCoachJudgeConfigReader:
    """Deterministic reader for L2/L4 tests — zero I/O, defaults OFF."""

    def __init__(
        self,
        *,
        coach_grader_judge_enabled: bool = False,
        coach_pedagogy_judge_enabled: bool = False,
        coach_judge_sample_rate: float = DEFAULT_SAMPLE_RATE,
        coach_leakage_gate_enabled: bool = False,
        source: str = "test",
    ) -> None:
        self._resolved = ResolvedSubjectCoachJudgeConfig(
            coach_grader_judge_enabled=coach_grader_judge_enabled,
            coach_pedagogy_judge_enabled=coach_pedagogy_judge_enabled,
            coach_judge_sample_rate=coach_judge_sample_rate,
            coach_leakage_gate_enabled=coach_leakage_gate_enabled,
            source=source,
            schema_version=1,
            updated_by="test",
        )

    def get(self) -> ResolvedSubjectCoachJudgeConfig:
        return self._resolved

    def health_posture(self) -> dict[str, Any]:
        return _posture_dict(self._resolved)


class SubjectCoachJudgeConfigReader:
    """TTL-cached reader for ``gs://`` or ``file://`` coach-judge config."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        ttl_s: float | None = None,
        timeout_s: float | None = None,
        gcs_client: StorageClient | None = None,
    ) -> None:
        resolved_uri = (
            uri if uri is not None else os.environ.get("COACH_JUDGE_CONFIG_URI", "")
        )
        self._uri = resolved_uri.strip() or None
        self._ttl_s = float(
            ttl_s
            if ttl_s is not None
            else os.environ.get("COACH_JUDGE_CONFIG_TTL_S", _DEFAULT_TTL_S)
        )
        self._timeout_s = float(
            timeout_s
            if timeout_s is not None
            else os.environ.get("COACH_JUDGE_CONFIG_TIMEOUT_S", _DEFAULT_TIMEOUT_S)
        )
        self._gcs_client = gcs_client

        self._lock = threading.Lock()
        self._cache_expires_at: float | None = None
        self._cached: ResolvedSubjectCoachJudgeConfig | None = None
        self._last_good: ResolvedSubjectCoachJudgeConfig | None = None
        self._last_posture: tuple[bool, bool, bool] | None = None

    def get(self) -> ResolvedSubjectCoachJudgeConfig:
        now = datetime.now(UTC).timestamp()
        with self._lock:
            if (
                self._cached is not None
                and self._cache_expires_at is not None
                and now < self._cache_expires_at
            ):
                return self._cached

        resolved = self._resolve_fresh()
        with self._lock:
            self._cached = resolved
            self._cache_expires_at = now + self._ttl_s
        self._maybe_log_posture_change(resolved)
        return resolved

    def health_posture(self) -> dict[str, Any]:
        """Non-blocking posture echo for /healthz — serves cache only."""
        with self._lock:
            resolved = self._cached or self._last_good
        if resolved is None:
            resolved = self._fallback_without_uri()
        return _posture_dict(resolved)

    def _resolve_fresh(self) -> ResolvedSubjectCoachJudgeConfig:
        if not self._uri:
            return self._fallback_without_uri()

        try:
            raw = self._read_with_timeout()
            parsed = SubjectCoachJudgeRuntimeConfig.model_validate_json(raw)
            resolved = ResolvedSubjectCoachJudgeConfig(
                coach_grader_judge_enabled=parsed.coach_grader_judge_enabled,
                coach_pedagogy_judge_enabled=parsed.coach_pedagogy_judge_enabled,
                coach_judge_sample_rate=parsed.coach_judge_sample_rate,
                coach_leakage_gate_enabled=parsed.coach_leakage_gate_enabled,
                source=self._source_tag(),
                schema_version=parsed.schema_version,
                updated_at=parsed.updated_at,
                updated_by=parsed.updated_by,
            )
            with self._lock:
                self._last_good = resolved
            return resolved
        except Exception as exc:
            logger.warning(
                "SubjectCoach judge config read/parse failed (%s); degrading", exc
            )
            with self._lock:
                if self._last_good is not None:
                    # Stale-on-error: a transient config outage must not
                    # silently flip the judges; serve the last-good posture.
                    return ResolvedSubjectCoachJudgeConfig(
                        coach_grader_judge_enabled=self._last_good.coach_grader_judge_enabled,
                        coach_pedagogy_judge_enabled=self._last_good.coach_pedagogy_judge_enabled,
                        coach_judge_sample_rate=self._last_good.coach_judge_sample_rate,
                        coach_leakage_gate_enabled=self._last_good.coach_leakage_gate_enabled,
                        source="stale",
                        schema_version=self._last_good.schema_version,
                        updated_at=self._last_good.updated_at,
                        updated_by=self._last_good.updated_by,
                    )
            # Never-read failure: fail DARK (all OFF), never open.
            return self._fallback_without_uri(source="default")

    def _fallback_without_uri(
        self, *, source: str | None = None
    ) -> ResolvedSubjectCoachJudgeConfig:
        env_names = (
            "COACH_GRADER_JUDGE_ENABLED",
            "COACH_PEDAGOGY_JUDGE_ENABLED",
            "COACH_JUDGE_SAMPLE_RATE",
            "COACH_LEAKAGE_GATE_ENABLED",
        )
        env_explicit = any(name in os.environ for name in env_names)
        return ResolvedSubjectCoachJudgeConfig(
            coach_grader_judge_enabled=_env_flag("COACH_GRADER_JUDGE_ENABLED"),
            coach_pedagogy_judge_enabled=_env_flag("COACH_PEDAGOGY_JUDGE_ENABLED"),
            coach_judge_sample_rate=_env_sample_rate(),
            coach_leakage_gate_enabled=_env_flag("COACH_LEAKAGE_GATE_ENABLED"),
            source=source or ("env" if env_explicit else "default"),
        )

    def _read_with_timeout(self) -> str:
        future = _executor.submit(self._read_raw)
        try:
            return future.result(timeout=self._timeout_s)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"SubjectCoach judge config read timed out after {self._timeout_s}s"
            ) from exc

    def _read_raw(self) -> str:
        if not self._uri:
            raise ValueError("config URI is unset")
        parsed = urlparse(self._uri)
        if parsed.scheme == "file":
            path = Path(parsed.path)
            if parsed.netloc:
                path = Path(f"/{parsed.netloc}{parsed.path}")
            return self._read_file_text(path)
        if parsed.scheme == "gs":
            return self._read_gcs_text(parsed.netloc, parsed.path.lstrip("/"))
        raise ValueError(
            f"unsupported SubjectCoach judge config URI scheme: {parsed.scheme!r}"
        )

    def _read_file_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _read_gcs_text(self, bucket_name: str, blob_path: str) -> str:
        client = self._get_gcs_client()
        return client.bucket(bucket_name).blob(blob_path).download_as_text()

    def _get_gcs_client(self) -> StorageClient:
        if self._gcs_client is None:
            from google.cloud.storage import Client

            self._gcs_client = Client()
        return self._gcs_client

    def _source_tag(self) -> str:
        assert self._uri is not None
        parsed = urlparse(self._uri)
        if parsed.scheme == "file":
            return f"file:{Path(parsed.path)}"
        if parsed.scheme == "gs":
            return f"gcs:{parsed.path.lstrip('/')}"
        return self._uri

    def _maybe_log_posture_change(
        self, resolved: ResolvedSubjectCoachJudgeConfig
    ) -> None:
        posture = (
            resolved.coach_grader_judge_enabled,
            resolved.coach_pedagogy_judge_enabled,
            resolved.coach_leakage_gate_enabled,
        )
        if self._last_posture is not None and posture != self._last_posture:
            logger.warning(
                "SubjectCoach judge posture changed: %s -> %s (source=%s updated_by=%s)",
                self._last_posture,
                posture,
                resolved.source,
                resolved.updated_by,
            )
        self._last_posture = posture
