"""middleware/composition.py -- the SINGLE wiring point for the
middleware ring.

This is the only file in ``middleware/`` that:

  * Reads ``ARCHITECTURE_PROFILE`` (rule **F1 / C1**).
  * Reads any ``WORKOS_*``, ``MEM0_*``, ``LANGFUSE_*`` env var
    (rule **C4 / C5**).
  * Names concrete adapter classes (rule **C1**).

Downstream consumers (the FastAPI app, route handlers) receive port
instances via the typed bag ``MiddlewareAdapters`` (rule **C2**) and
NEVER import a concrete adapter class themselves.

Architecture-test enforcement: ``tests/architecture/test_middleware_layer.py``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl
from middleware.adapters.auth.workos_jwt_verifier import (
    WorkOSJwtVerifier,
    default_workos_issuer,
)
from middleware.adapters.memory.mem0_cloud_client import Mem0CloudClient
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.adapters.observability.langfuse_eval_telemetry_sink import (
    LangfuseEvalTelemetrySink,
)
from middleware.ports.jwt_verifier import JwtVerifier
from middleware.ports.memory_client import MemoryClient
from middleware.ports.telemetry_exporter import TelemetryExporter
from middleware.ports.tool_acl import ToolAclProvider
from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay
from services.eval_telemetry import set_sink

_logger = logging.getLogger(__name__)


__all__ = [
    "MiddlewareAdapters",
    "AgentComponents",
    "AgentRuntimeSettings",
    "build_adapters",
    "build_components",
    "build_runtime_graph",
    "MissingEnvError",
    "UnknownProfileError",
]


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class MissingEnvError(KeyError):
    """A required env var was absent during composition."""

    def __init__(self, var_name: str) -> None:
        super().__init__(var_name)
        self.var_name = var_name

    def __str__(self) -> str:
        return f"missing required env var: {self.var_name}"


class UnknownProfileError(ValueError):
    """``ARCHITECTURE_PROFILE`` is not one of the known values."""


# ─────────────────────────────────────────────────────────────────────
# Default tool-ACL policy table
# ─────────────────────────────────────────────────────────────────────
#
# Mirror of the WorkOS dashboard role/permission seed (created via
# ``npx workos@latest role/permission ...``). Kept here as a fallback
# / canonical source so the ACL works even on first-boot before
# WorkOS roles propagate to the issued JWTs.

_DEFAULT_ROLE_TO_TOOLS: dict[str, frozenset[str]] = {
    "admin": frozenset({"shell", "file_io", "web_search"}),
    "beta": frozenset({"file_io", "web_search"}),
    "viewer": frozenset(),
    "member": frozenset(),
}

_DEFAULT_KNOWN_TOOLS: frozenset[str] = frozenset(
    {"shell", "file_io", "web_search"}
)


# ─────────────────────────────────────────────────────────────────────
# Typed adapter bag
# ─────────────────────────────────────────────────────────────────────


_RELAY_MODE_IN_PROCESS = "in_process"
_RELAY_MODE_OFF = "off"
_RELAY_MODE_EXTERNAL = "external"
_VALID_RELAY_MODES = {_RELAY_MODE_IN_PROCESS, _RELAY_MODE_OFF, _RELAY_MODE_EXTERNAL}

_DEFAULT_BB_STORAGE = Path("cache/black_box_recordings")


@dataclass(frozen=True)
class MiddlewareAdapters:
    """Bag of port-typed adapter instances (rule C2)."""

    profile: str
    jwt_verifier: JwtVerifier
    tool_acl: ToolAclProvider
    memory_client: MemoryClient
    telemetry_exporter: TelemetryExporter
    black_box_relay: BlackBoxToTelemetryRelay | None = None


# ─────────────────────────────────────────────────────────────────────
# build_adapters -- THE composition function
# ─────────────────────────────────────────────────────────────────────


def _wire_eval_telemetry(exporter: TelemetryExporter) -> None:
    """Register E1 eval.goal_judge sink for orchestration → Langfuse export."""
    set_sink(LangfuseEvalTelemetrySink(exporter))


def build_adapters(
    *,
    env: Mapping[str, str] | None = None,
) -> MiddlewareAdapters:
    """Wire all middleware adapters from the environment.

    Args:
        env: optional explicit env mapping. Tests inject this so
            composition is deterministic (no real ``os.environ`` reads).
            When ``None``, falls back to ``os.environ``.

    Returns:
        MiddlewareAdapters: typed bag of port instances.

    Raises:
        UnknownProfileError: ``ARCHITECTURE_PROFILE`` is not ``v3`` or ``v2``.
        MissingEnvError: a required env var is absent.
    """
    e = dict(env) if env is not None else dict(os.environ)

    # Profile is the ONLY place this string is read in middleware/.
    profile = e.get("ARCHITECTURE_PROFILE", "v3")
    if profile not in {"v3", "v2"}:
        raise UnknownProfileError(
            f"unknown ARCHITECTURE_PROFILE={profile!r}; "
            "must be 'v3' (dev-tier default) or 'v2' (paid graduation)"
        )

    if profile == "v3":
        return _build_v3(e)
    # profile == "v2"
    return _build_v2(e)


# ─────────────────────────────────────────────────────────────────────
# v3 (dev-tier free substrates)
# ─────────────────────────────────────────────────────────────────────


def _build_v3(e: Mapping[str, str]) -> MiddlewareAdapters:
    workos_client_id = _require(e, "WORKOS_CLIENT_ID")
    _require(e, "WORKOS_API_KEY")  # not used directly here; sanity check
    mem0_api_key = _require(e, "MEM0_API_KEY")
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get(
        "WORKOS_ISSUER", default_workos_issuer(workos_client_id)
    )
    mem0_base_url = e.get("MEM0_BASE_URL", "https://api.mem0.ai")
    langfuse_host = (
        e.get("LANGFUSE_HOST")
        or e.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    )
    jwks_url = e.get(
        "WORKOS_JWKS_URL",
        f"https://api.workos.com/sso/jwks/{workos_client_id}",
    )

    # JWT verifier -- adapter owns SDK construction (rule F-R2 / A1).
    # Real network is only hit on the first verify() call.
    verifier = WorkOSJwtVerifier(
        jwks_url=jwks_url,
        expected_issuer=workos_issuer,
        expected_client_id=workos_client_id,
        expected_token_use="access",
    )

    telemetry = LangfuseCloudExporter(
        public_key=langfuse_public,
        secret_key=langfuse_secret,
        host=langfuse_host,
    )
    _wire_eval_telemetry(telemetry)

    return MiddlewareAdapters(
        profile="v3",
        jwt_verifier=verifier,
        tool_acl=WorkOSRoleAcl(
            role_to_tools=_DEFAULT_ROLE_TO_TOOLS,
            known_tools=_DEFAULT_KNOWN_TOOLS,
        ),
        memory_client=Mem0CloudClient(
            api_key=mem0_api_key,
            base_url=mem0_base_url,
        ),
        telemetry_exporter=telemetry,
        black_box_relay=_build_relay(e, telemetry),
    )


# ─────────────────────────────────────────────────────────────────────
# v2 (paid graduation -- self-hosted variants)
# ─────────────────────────────────────────────────────────────────────


def _build_v2(e: Mapping[str, str]) -> MiddlewareAdapters:
    """v2 wiring -- self-hosted Mem0 + self-hosted Langfuse + (same)
    WorkOS verifier + WorkOS role ACL.

    Sprint 1 ships parity by reusing the v3 SDKs but pointed at
    self-hosted hosts. The dedicated self-hosted adapter classes land
    in Sprint 2 along with their conformance tests.
    """
    workos_client_id = _require(e, "WORKOS_CLIENT_ID")
    _require(e, "WORKOS_API_KEY")
    mem0_api_key = _require(e, "MEM0_API_KEY")
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get(
        "WORKOS_ISSUER", default_workos_issuer(workos_client_id)
    )
    # v2 defaults to self-hosted endpoints.
    mem0_base_url = e.get("MEM0_BASE_URL", "https://mem0.internal")
    langfuse_host = e.get("LANGFUSE_HOST", "https://langfuse.internal")
    jwks_url = e.get(
        "WORKOS_JWKS_URL",
        f"https://api.workos.com/sso/jwks/{workos_client_id}",
    )

    verifier = WorkOSJwtVerifier(
        jwks_url=jwks_url,
        expected_issuer=workos_issuer,
        expected_client_id=workos_client_id,
        expected_token_use="access",
    )

    telemetry = LangfuseCloudExporter(
        public_key=langfuse_public,
        secret_key=langfuse_secret,
        host=langfuse_host,
    )
    _wire_eval_telemetry(telemetry)

    return MiddlewareAdapters(
        profile="v2",
        jwt_verifier=verifier,
        tool_acl=WorkOSRoleAcl(
            role_to_tools=_DEFAULT_ROLE_TO_TOOLS,
            known_tools=_DEFAULT_KNOWN_TOOLS,
        ),
        memory_client=Mem0CloudClient(
            api_key=mem0_api_key,
            base_url=mem0_base_url,
        ),
        telemetry_exporter=telemetry,
        black_box_relay=_build_relay(e, telemetry),
    )


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


def _build_relay(
    e: Mapping[str, str],
    exporter: TelemetryExporter,
) -> BlackBoxToTelemetryRelay | None:
    """Build the BlackBox→Telemetry relay if BLACKBOX_RELAY_MODE requests it.

    Returns None for modes ``off``, ``external``, or any unrecognized value.
    Only ``in_process`` (the default) produces a relay instance.
    """
    mode = e.get("BLACKBOX_RELAY_MODE", _RELAY_MODE_IN_PROCESS)
    if mode not in _VALID_RELAY_MODES:
        _logger.warning(
            "Unknown BLACKBOX_RELAY_MODE=%r; treating as 'off'", mode
        )
        return None
    if mode != _RELAY_MODE_IN_PROCESS:
        return None

    storage_dir = _resolve_relay_storage_dir(e)

    from middleware.ports.compliance_publisher import CompliancePublisher

    compliance_publisher = exporter if isinstance(exporter, CompliancePublisher) else None

    return BlackBoxToTelemetryRelay(
        storage_dir=storage_dir,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
    )


def _resolve_relay_storage_dir(e: Mapping[str, str]) -> Path:
    """Resolve where the relay tails BlackBox recordings.

    Precedence:
      1. ``BLACKBOX_STORAGE_DIR`` (explicit; set by Terraform on Cloud Run).
      2. On Cloud Run (``GCP_EXECUTION_ENV=cloudrun``) with the var unset,
         derive from ``AGENT_OFFLOAD_DIR`` so the relay matches where
         ``BlackBoxRecorder`` writes (the default relative ``cache/`` path
         resolves to the wrong cwd on Cloud Run).
      3. Local default (``cache/black_box_recordings``).
    """
    storage_dir_str = e.get("BLACKBOX_STORAGE_DIR", "")
    if storage_dir_str:
        return Path(storage_dir_str)

    if e.get("GCP_EXECUTION_ENV") == "cloudrun":
        offload_dir = e.get("AGENT_OFFLOAD_DIR", "/tmp/agent_offload")
        return Path(offload_dir) / "black_box_recordings"

    return _DEFAULT_BB_STORAGE


def _require(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        raise MissingEnvError(key)
    return value


# ─────────────────────────────────────────────────────────────────────
# Agent runtime composition (local + prod profiles)
# ─────────────────────────────────────────────────────────────────────

_DEV_AGENT_ID = "dev-agent"


def _env_flag_from_mapping(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in ("1", "true", "yes")


class AgentRuntimeSettings(BaseSettings):
    """Env-driven profile for the agent object graph (Composition Root)."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    agent_env: Literal["local", "prod"] | None = None
    gcp_execution_env: str = Field(default="", validation_alias="GCP_EXECUTION_ENV")
    gcs_facts_bucket: str = Field(default="", validation_alias="GCS_FACTS_BUCKET")
    gcs_traces_bucket: str = Field(default="", validation_alias="GCS_TRACES_BUCKET")
    agent_facts_secret: str = Field(
        default="dev-secret-do-not-use-in-production",
        validation_alias="AGENT_FACTS_SECRET",
    )
    agent_offload_dir: str = Field(default="", validation_alias="AGENT_OFFLOAD_DIR")
    web_search_provider: str = Field(default="stub", validation_alias="WEB_SEARCH_PROVIDER")
    searxng_url: str = Field(default="http://localhost:8888", validation_alias="SEARXNG_URL")
    goal_judge_config_uri: str = Field(default="", validation_alias="GOAL_JUDGE_CONFIG_URI")
    goal_judge_enabled: bool = Field(default=False, validation_alias="GOAL_JUDGE_ENABLED")
    goal_judge_downgrade_enabled: bool = Field(
        default=False, validation_alias="GOAL_JUDGE_DOWNGRADE_ENABLED"
    )

    @model_validator(mode="after")
    def _resolve_agent_env(self) -> AgentRuntimeSettings:
        if self.agent_env is None:
            explicit = os.environ.get("AGENT_ENV", "").strip().lower()
            if explicit in ("local", "prod"):
                object.__setattr__(self, "agent_env", explicit)
            elif self.gcp_execution_env:
                object.__setattr__(self, "agent_env", "prod")
            else:
                object.__setattr__(self, "agent_env", "local")
        return self

    @classmethod
    def from_mapping(cls, env: Mapping[str, str]) -> AgentRuntimeSettings:
        """Build settings from an explicit env dict (tests inject this)."""
        data: dict[str, Any] = {}
        for field_name, field_info in cls.model_fields.items():
            alias = field_info.validation_alias
            if isinstance(alias, str) and alias in env:
                raw = env[alias]
                if field_name in (
                    "goal_judge_enabled",
                    "goal_judge_downgrade_enabled",
                ):
                    data[field_name] = _env_flag_from_mapping(env, alias)
                else:
                    data[field_name] = raw
            elif field_name == "agent_env" and "AGENT_ENV" in env:
                data["agent_env"] = env["AGENT_ENV"]
        settings = cls.model_validate(data)
        if settings.agent_env is None:
            if env.get("AGENT_ENV", "").strip().lower() in ("local", "prod"):
                object.__setattr__(
                    settings,
                    "agent_env",
                    env["AGENT_ENV"].strip().lower(),
                )
            elif env.get("GCP_EXECUTION_ENV"):
                object.__setattr__(settings, "agent_env", "prod")
            else:
                object.__setattr__(settings, "agent_env", "local")
        return settings


@dataclass(frozen=True)
class AgentComponents:
    """Typed bag of agent-runtime wiring (rule C2 analogue for the graph)."""

    agent_config: Any
    tool_registry: Any
    agent_facts_registry: Any
    cache_dir: Path
    goal_judge_config_reader: Any
    settings: AgentRuntimeSettings


def _model_profiles() -> tuple[Any, Any]:
    from services.base_config import ModelProfile

    fast = ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )
    capable = ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )
    return fast, capable


def _resolve_search_provider(settings: AgentRuntimeSettings) -> Any:
    from services.tools.search.port import WebSearchProvider
    from services.tools.search.stub import StubProvider

    provider_name = settings.web_search_provider.lower()
    if provider_name == "searxng":
        from services.tools.search.searxng import SearxngProvider

        return SearxngProvider(base_url=settings.searxng_url)
    return StubProvider()


def build_components(
    settings: AgentRuntimeSettings,
    *,
    agent_root: Path,
) -> AgentComponents:
    """Wire the agent object graph once for local or prod profile."""
    from services.base_config import AgentConfig
    from services.goal_judge_runtime_config import GoalJudgeRuntimeConfigReader
    from services.governance.agent_facts_registry import AgentFactsRegistry
    from services.observability import setup_logging
    from services.tools.delegation_dispatcher import LocalLLMDelegationDispatcher
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.file_tools import StateFileToolInput, execute_state_file_tool
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.shell import ShellToolInput, execute_shell
    from services.tools.task_tool import TaskToolInput, build_task_tool_executor
    from services.tools.think_tool import ThinkToolInput, execute_think_tool
    from services.tools.todo_tools import StateTodoToolInput, execute_state_todo_tool
    from services.tools.web_search import WebSearchInput, build_web_search_executor
    from trust.enums import IdentityStatus
    from trust.models import AgentFacts, Capability

    setup_logging()
    fast, capable = _model_profiles()

    goal_judge_enabled = settings.goal_judge_enabled
    goal_judge_downgrade = settings.goal_judge_downgrade_enabled

    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[fast, capable],
        max_steps=20,
        max_cost_usd=1.0,
        goal_judge_enabled=goal_judge_enabled,
        goal_judge_downgrade_enabled=goal_judge_downgrade,
    )

    delegation_dispatcher = LocalLLMDelegationDispatcher(agent_config)
    tool_registry = ToolRegistry({
        "shell": ToolDefinition(
            # Not cacheable: same hazard as file_io below — shell reads mutable
            # filesystem state (cat/ls/grep/...), so a cached result is silently
            # stale after the file changes later in the thread.
            executor=execute_shell, schema=ShellToolInput, cacheable=False
        ),
        "file_io": ToolDefinition(
            # Not cacheable: the thread-level tool_cache keys on exact args and
            # never invalidates, so a cached read returns stale content after
            # the same path is overwritten later in the thread.
            executor=execute_file_io, schema=FileIOInput, cacheable=False
        ),
        "state_file": ToolDefinition(
            executor=execute_state_file_tool, schema=StateFileToolInput, cacheable=False
        ),
        "state_todo": ToolDefinition(
            executor=execute_state_todo_tool, schema=StateTodoToolInput, cacheable=False
        ),
        "task": ToolDefinition(
            executor=build_task_tool_executor(delegation_dispatcher.dispatch),
            schema=TaskToolInput,
            cacheable=False,
        ),
        "think": ToolDefinition(
            executor=execute_think_tool, schema=ThinkToolInput, cacheable=False
        ),
        "web_search": ToolDefinition(
            executor=build_web_search_executor(_resolve_search_provider(settings)),
            schema=WebSearchInput,
            cacheable=True,
        ),
    })

    if settings.agent_env == "prod":
        cache_dir = Path(settings.agent_offload_dir or "/tmp/agent_offload")
        if not settings.gcs_facts_bucket:
            raise RuntimeError("GCS_FACTS_BUCKET is required in production")
        from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry

        agent_facts_registry = AgentFactsGcsRegistry(
            bucket_name=settings.gcs_facts_bucket,
            secret=settings.agent_facts_secret,
        )
    else:
        cache_dir = agent_root / "cache"
        if settings.agent_offload_dir:
            cache_dir = Path(settings.agent_offload_dir)
        agent_facts_dir = cache_dir / "agent_facts"
        agent_facts_registry = AgentFactsRegistry(
            storage_dir=agent_facts_dir,
            secret=settings.agent_facts_secret,
        )
        try:
            agent_facts_registry.get(_DEV_AGENT_ID)
        except KeyError:
            agent_facts_registry.register(
                AgentFacts(
                    agent_id=_DEV_AGENT_ID,
                    agent_name="Dev Agent",
                    owner="dev-user",
                    version="1.0.0",
                    description="Local development agent",
                    capabilities=[Capability(name="delegate.subagent.*")],
                    status=IdentityStatus.ACTIVE,
                ),
                registered_by="dev-bootstrap",
            )

    cache_dir.mkdir(parents=True, exist_ok=True)

    config_uri = settings.goal_judge_config_uri.strip() or None
    if settings.agent_env == "prod" and not config_uri and settings.gcs_facts_bucket:
        config_uri = f"gs://{settings.gcs_facts_bucket}/ops/goal_judge_config.json"

    goal_judge_config_reader = GoalJudgeRuntimeConfigReader(
        uri=config_uri,
        env_enabled=goal_judge_enabled,
        env_downgrade=goal_judge_downgrade,
        defaults_enabled=agent_config.goal_judge_enabled,
        defaults_downgrade=agent_config.goal_judge_downgrade_enabled,
    )

    return AgentComponents(
        agent_config=agent_config,
        tool_registry=tool_registry,
        agent_facts_registry=agent_facts_registry,
        cache_dir=cache_dir,
        goal_judge_config_reader=goal_judge_config_reader,
        settings=settings,
    )


def build_runtime_graph(
    components: AgentComponents,
    build_graph: Any,
    *,
    checkpointer: Any = None,
    telemetry: Any = None,
    authorization_service: Any = None,
    trace_service: Any = None,
    interrupt_before_execute_tool: bool = True,
) -> Any:
    """Single call site for ``build_graph`` with reader injection."""
    return build_graph(
        agent_config=components.agent_config,
        tool_registry=components.tool_registry,
        cache_dir=components.cache_dir,
        checkpointer=checkpointer,
        agent_facts_registry=components.agent_facts_registry,
        telemetry=telemetry,
        authorization_service=authorization_service,
        trace_service=trace_service,
        interrupt_before_execute_tool=interrupt_before_execute_tool,
        goal_judge_config_reader=components.goal_judge_config_reader,
    )
