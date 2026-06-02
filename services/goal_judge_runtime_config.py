"""Runtime-readable GoalJudge feature switch (GCS or local file).

Small L2 horizontal service: versioned JSON config with TTL cache,
bounded reads, stale-on-error degradation, and env/AgentConfig fallback.
No langgraph imports — wiring lives in middleware/composition.py.
"""

from __future__ import annotations

import json
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

logger = logging.getLogger("services.goal_judge_runtime_config")

_DEFAULT_TTL_S = 30.0
_DEFAULT_TIMEOUT_S = 2.0
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gj-config")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class GoalJudgeRuntimeConfig(BaseModel):
    """Versioned on-disk / GCS posture document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    goal_judge_enabled: bool
    goal_judge_downgrade_enabled: bool
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by: str = "unknown"


@dataclass(frozen=True)
class ResolvedGoalJudgeConfig:
    """Effective posture after precedence resolution."""

    goal_judge_enabled: bool
    goal_judge_downgrade_enabled: bool
    source: str
    schema_version: int | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class InMemoryGoalJudgeConfigReader:
    """Deterministic reader for L4 gate tests — zero I/O."""

    def __init__(
        self,
        *,
        goal_judge_enabled: bool = False,
        goal_judge_downgrade_enabled: bool = False,
        source: str = "test",
        schema_version: int | None = 1,
        updated_at: datetime | None = None,
        updated_by: str | None = "test",
    ) -> None:
        self._resolved = ResolvedGoalJudgeConfig(
            goal_judge_enabled=goal_judge_enabled,
            goal_judge_downgrade_enabled=goal_judge_downgrade_enabled,
            source=source,
            schema_version=schema_version,
            updated_at=updated_at,
            updated_by=updated_by,
        )

    def get(self) -> ResolvedGoalJudgeConfig:
        return self._resolved

    def health_posture(self) -> dict[str, Any]:
        r = self._resolved
        return {
            "enabled": r.goal_judge_enabled,
            "downgrade_enabled": r.goal_judge_downgrade_enabled,
            "source": r.source,
            "schema_version": r.schema_version,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "updated_by": r.updated_by,
        }


class GoalJudgeRuntimeConfigReader:
    """TTL-cached reader for ``gs://`` or ``file://`` GoalJudge config."""

    def __init__(
        self,
        *,
        uri: str | None = None,
        ttl_s: float | None = None,
        timeout_s: float | None = None,
        gcs_client: StorageClient | None = None,
        env_enabled: bool | None = None,
        env_downgrade: bool | None = None,
        defaults_enabled: bool = False,
        defaults_downgrade: bool = False,
    ) -> None:
        resolved_uri = uri if uri is not None else os.environ.get("GOAL_JUDGE_CONFIG_URI", "")
        self._uri = resolved_uri.strip() or None
        self._ttl_s = float(
            ttl_s
            if ttl_s is not None
            else os.environ.get("GOAL_JUDGE_CONFIG_TTL_S", _DEFAULT_TTL_S)
        )
        self._timeout_s = float(
            timeout_s
            if timeout_s is not None
            else os.environ.get("GOAL_JUDGE_CONFIG_TIMEOUT_S", _DEFAULT_TIMEOUT_S)
        )
        self._gcs_client = gcs_client
        self._env_enabled = (
            _env_flag("GOAL_JUDGE_ENABLED") if env_enabled is None else env_enabled
        )
        self._env_downgrade = (
            _env_flag("GOAL_JUDGE_DOWNGRADE_ENABLED")
            if env_downgrade is None
            else env_downgrade
        )
        self._env_enabled_explicit = (
            env_enabled is not None or "GOAL_JUDGE_ENABLED" in os.environ
        )
        self._env_downgrade_explicit = (
            env_downgrade is not None or "GOAL_JUDGE_DOWNGRADE_ENABLED" in os.environ
        )
        self._defaults_enabled = defaults_enabled
        self._defaults_downgrade = defaults_downgrade

        self._lock = threading.Lock()
        self._cache_expires_at: float | None = None
        self._cached: ResolvedGoalJudgeConfig | None = None
        self._last_good: ResolvedGoalJudgeConfig | None = None
        self._last_posture: tuple[bool, bool] | None = None

    @classmethod
    def from_env(
        cls,
        *,
        defaults_enabled: bool = False,
        defaults_downgrade: bool = False,
    ) -> GoalJudgeRuntimeConfigReader:
        """Construct a reader from process env (zero I/O when URI unset)."""
        return cls(
            defaults_enabled=defaults_enabled,
            defaults_downgrade=defaults_downgrade,
        )

    def get(self) -> ResolvedGoalJudgeConfig:
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
        return {
            "enabled": resolved.goal_judge_enabled,
            "downgrade_enabled": resolved.goal_judge_downgrade_enabled,
            "source": resolved.source,
            "schema_version": resolved.schema_version,
            "updated_at": resolved.updated_at.isoformat() if resolved.updated_at else None,
            "updated_by": resolved.updated_by,
        }

    def _resolve_fresh(self) -> ResolvedGoalJudgeConfig:
        if not self._uri:
            return self._fallback_without_uri()

        try:
            raw = self._read_with_timeout()
            parsed = GoalJudgeRuntimeConfig.model_validate_json(raw)
            source = self._source_tag()
            resolved = ResolvedGoalJudgeConfig(
                goal_judge_enabled=parsed.goal_judge_enabled,
                goal_judge_downgrade_enabled=parsed.goal_judge_downgrade_enabled,
                source=source,
                schema_version=parsed.schema_version,
                updated_at=parsed.updated_at,
                updated_by=parsed.updated_by,
            )
            with self._lock:
                self._last_good = resolved
            return resolved
        except Exception as exc:
            logger.warning(
                "GoalJudge config read/parse failed (%s); degrading",
                exc,
            )
            with self._lock:
                if self._last_good is not None:
                    return ResolvedGoalJudgeConfig(
                        goal_judge_enabled=self._last_good.goal_judge_enabled,
                        goal_judge_downgrade_enabled=self._last_good.goal_judge_downgrade_enabled,
                        source="stale",
                        schema_version=self._last_good.schema_version,
                        updated_at=self._last_good.updated_at,
                        updated_by=self._last_good.updated_by,
                    )
            return self._fallback_without_uri(source="default")

    def _fallback_without_uri(self, *, source: str | None = None) -> ResolvedGoalJudgeConfig:
        if self._env_enabled_explicit or self._env_downgrade_explicit:
            return ResolvedGoalJudgeConfig(
                goal_judge_enabled=self._env_enabled,
                goal_judge_downgrade_enabled=self._env_downgrade,
                source=source or "env",
            )
        return ResolvedGoalJudgeConfig(
            goal_judge_enabled=self._defaults_enabled,
            goal_judge_downgrade_enabled=self._defaults_downgrade,
            source=source or "default",
        )

    def _read_with_timeout(self) -> str:
        future = _executor.submit(self._read_raw)
        try:
            return future.result(timeout=self._timeout_s)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"GoalJudge config read timed out after {self._timeout_s}s"
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
            bucket_name = parsed.netloc
            blob_path = parsed.path.lstrip("/")
            return self._read_gcs_text(bucket_name, blob_path)
        raise ValueError(f"unsupported GoalJudge config URI scheme: {parsed.scheme!r}")

    def _read_file_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _read_gcs_text(self, bucket_name: str, blob_path: str) -> str:
        client = self._get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.download_as_text()

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

    def _maybe_log_posture_change(self, resolved: ResolvedGoalJudgeConfig) -> None:
        posture = (resolved.goal_judge_enabled, resolved.goal_judge_downgrade_enabled)
        if self._last_posture is not None and posture != self._last_posture:
            logger.warning(
                "GoalJudge posture changed: %s -> %s (source=%s updated_by=%s)",
                self._last_posture,
                posture,
                resolved.source,
                resolved.updated_by,
            )
        self._last_posture = posture
