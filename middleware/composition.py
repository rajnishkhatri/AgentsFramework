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
from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)
from middleware.adapters.observability.langfuse_eval_telemetry_sink import (
    LangfuseEvalTelemetrySink,
)
from middleware.ports.embedding_client import EmbeddingClient
from middleware.ports.jwt_verifier import JwtVerifier
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
    "build_coach_components",
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

_DEFAULT_KNOWN_TOOLS: frozenset[str] = frozenset({"shell", "file_io", "web_search"})


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
    """Bag of port-typed adapter instances (rule C2).

    NOTE (replace-mem0-pgvector Phase 3, Branch A): the async
    ``memory_client`` field is GONE. The ``Mem0CloudClient`` adapter and
    its ``MemoryClient`` Protocol port were deleted outright — Phase 0
    C2 proved zero non-test consumers (the sync ``LongTermMemoryService``
    handles ``/agent/memory`` routes via the graph-side
    ``MemoryBackend`` Protocol).
    """

    profile: str
    jwt_verifier: JwtVerifier
    tool_acl: ToolAclProvider
    telemetry_exporter: TelemetryExporter
    black_box_relay: BlackBoxToTelemetryRelay | None = None
    # Phase 1 (replace-mem0-pgvector): the EmbeddingClient that Phase 2's
    # PgVectorMemoryBackend will consume. Optional during transition — wired
    # only when OPENAI_API_KEY is present; absent in dev/CI runs that don't
    # touch the real provider (the FakeEmbeddingClient stays test-local).
    embedding_client: EmbeddingClient | None = None


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
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get("WORKOS_ISSUER", default_workos_issuer(workos_client_id))
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
        telemetry_exporter=telemetry,
        black_box_relay=_build_relay(e, telemetry),
        embedding_client=_build_embedding_client(e),
    )


# ─────────────────────────────────────────────────────────────────────
# v2 (paid graduation -- self-hosted variants)
# ─────────────────────────────────────────────────────────────────────


def _build_v2(e: Mapping[str, str]) -> MiddlewareAdapters:
    """v2 wiring -- self-hosted Langfuse + (same) WorkOS verifier + WorkOS
    role ACL.

    Sprint 1 ships parity by reusing the v3 SDKs but pointed at
    self-hosted hosts. The dedicated self-hosted adapter classes land
    in Sprint 2 along with their conformance tests.

    NOTE (Phase 0.5 R1): ``MEM0_API_KEY`` is no longer read — see _build_v3.
    """
    workos_client_id = _require(e, "WORKOS_CLIENT_ID")
    _require(e, "WORKOS_API_KEY")
    langfuse_public = _require(e, "LANGFUSE_PUBLIC_KEY")
    langfuse_secret = _require(e, "LANGFUSE_SECRET_KEY")

    workos_issuer = e.get("WORKOS_ISSUER", default_workos_issuer(workos_client_id))
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
        telemetry_exporter=telemetry,
        black_box_relay=_build_relay(e, telemetry),
        embedding_client=_build_embedding_client(e),
    )


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────


def _build_embedding_client(e: Mapping[str, str]) -> EmbeddingClient | None:
    """Construct the EmbeddingClient (Phase 1, replace-mem0-pgvector).

    Returns ``None`` when ``OPENAI_API_KEY`` is unset — Phase 1 ships the
    port + adapter but does NOT yet require a live provider in any
    runtime path. Phase 2's ``PgVectorMemoryBackend`` will receive this
    via constructor injection. Phase 4 promotes the requirement gate
    (``MEMORY_BACKEND=pgvector`` without an embedding client = composition
    error) — until then the field stays Optional.

    The adapter import is local so the SDK isolation invariant (the
    architecture test's M-no-cross rule) stays clean: ``litellm`` enters
    Python's import graph only when we actually need it.
    """
    api_key = e.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    model = e.get("EMBEDDING_MODEL", "text-embedding-3-small")
    dim_str = e.get("EMBEDDING_DIMENSION", "1536")
    try:
        dimension = int(dim_str)
    except ValueError as exc:
        raise MissingEnvError("EMBEDDING_DIMENSION") from exc

    from middleware.adapters.embedding.litellm_embedding_client import (
        LiteLLMEmbeddingClient,
    )

    return LiteLLMEmbeddingClient(
        model=model,
        dimension=dimension,
        api_key=api_key,
    )


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
        _logger.warning("Unknown BLACKBOX_RELAY_MODE=%r; treating as 'off'", mode)
        return None
    if mode != _RELAY_MODE_IN_PROCESS:
        return None

    storage_dir = _resolve_relay_storage_dir(e)

    from middleware.ports.compliance_publisher import CompliancePublisher

    compliance_publisher = (
        exporter if isinstance(exporter, CompliancePublisher) else None
    )

    # Phase 4: curated view on by default; LANGFUSE_RELAY_CURATED=false restores
    # the audit-complete dual view (Option B) without a redeploy of logic.
    curated_view = e.get("LANGFUSE_RELAY_CURATED", "true").strip().lower() != "false"

    return BlackBoxToTelemetryRelay(
        storage_dir=storage_dir,
        exporter=exporter,
        compliance_publisher=compliance_publisher,
        curated_view=curated_view,
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
    web_search_provider: str = Field(
        default="stub", validation_alias="WEB_SEARCH_PROVIDER"
    )
    searxng_url: str = Field(
        default="http://localhost:8888", validation_alias="SEARXNG_URL"
    )
    goal_judge_config_uri: str = Field(
        default="", validation_alias="GOAL_JUDGE_CONFIG_URI"
    )
    goal_judge_enabled: bool = Field(
        default=False, validation_alias="GOAL_JUDGE_ENABLED"
    )
    goal_judge_downgrade_enabled: bool = Field(
        default=False, validation_alias="GOAL_JUDGE_DOWNGRADE_ENABLED"
    )
    # Tiered-loops runtime flags (Step 0). Default OFF — prod parity with the
    # shadow-first defaults in services/base_config.py. A dedicated stress
    # revision flips REFLEXION_ENABLED / PLANNING_PLAN_SOURCE to gather evidence.
    planning_plan_source: Literal["deterministic", "shadow", "generated"] = Field(
        default="deterministic", validation_alias="PLANNING_PLAN_SOURCE"
    )
    reflexion_enabled: bool = Field(default=False, validation_alias="REFLEXION_ENABLED")
    max_reflexion_attempts: int = Field(
        default=2, validation_alias="MAX_REFLEXION_ATTEMPTS"
    )
    # Phase 4 (T3 fan-out). Default OFF — prod parity. The stress revision flips
    # T3_FANOUT_ENABLED (and, only on stress, FANOUT_FAULT_INJECT) to exercise
    # the parallel fork; fault-inject must NEVER be set on the prod revision.
    t3_fanout_enabled: bool = Field(default=False, validation_alias="T3_FANOUT_ENABLED")
    fanout_fault_inject: bool = Field(
        default=False, validation_alias="FANOUT_FAULT_INJECT"
    )
    # Governance carrier-gate enforcement (Phase 2). Default OFF — shadow-first
    # prod parity. When enabled, the dev/prod split (raise vs degrade) is derived
    # from agent_env (see _carrier_gate_enforce_mode). Promote only on Phase-1
    # calibration evidence + explicit approval.
    carrier_gate_enforce_enabled: bool = Field(
        default=False, validation_alias="CARRIER_GATE_ENFORCE_ENABLED"
    )
    # Carrier-gate fault-injection (the live gap-catch proof). Default OFF — MUST
    # stay OFF in prod (same posture as FANOUT_FAULT_INJECT). Only the dedicated
    # tagged validation revision flips it; the magic token is inert without it.
    carrier_gate_fault_inject: bool = Field(
        default=False, validation_alias="CARRIER_GATE_FAULT_INJECT"
    )
    # Phase 1 memory wiring. Default OFF — prod parity, shadow-first (same
    # discipline as reflexion/t3_fanout). The dev/stress revision flips
    # MEMORY_ENABLED to recall+store per user; prod stays byte-identical until
    # promotion. The LongTermMemoryService is constructed regardless of the flag
    # so the graph shape is stable; the flag only gates the recall/store calls.
    memory_enabled: bool = Field(default=False, validation_alias="MEMORY_ENABLED")
    # Phase 2 typed background auto-capture. Default OFF — shadow-first: the
    # extractor proposes and the trace carries the proposal, but write-back to
    # the store is gated on this flag (which flips only after the grounded-theory
    # enable-policy clears). Independent of MEMORY_ENABLED's recall path.
    memory_autocapture_enabled: bool = Field(
        default=False, validation_alias="MEMORY_AUTOCAPTURE_ENABLED"
    )
    # The enable-policy GUARD (services.governance.memory_enable_policy): the
    # flag above is the operator's INTENT, but write-back only actually turns on
    # when a passing, frozen-test-split calibration certificate is also present.
    # This is the path to that certificate (emitted by
    # scripts/eval/memory_extractor_calibrate.py --emit-certificate). Unset or
    # invalid → write-back stays SHADOW even with the flag on (fail-safe; the
    # composition logs a loud governance warning naming why). 03_enable_policy.md.
    memory_autocapture_cert: str = Field(
        default="", validation_alias="MEMORY_AUTOCAPTURE_CERT"
    )
    # Hermes / memory-os adoption A2: relevance floor on recall injection.
    # Default 0.0 = no floor (byte-identical to today); a scoring backend (Mem0)
    # on a tagged revision sets it to drop weakly-related recalls. Calibrate
    # before flipping on (docs/research/memory/hermes_adoptions_design.md).
    memory_recall_min_relevance: float = Field(
        default=0.0, validation_alias="MEMORY_RECALL_MIN_RELEVANCE"
    )
    # Hermes / memory-os adoption A3: salience threshold for the [confirmed]/
    # [inferred] recall-block tiers. Render-only; meaningful once write-back live.
    memory_authoritative_at: float = Field(
        default=0.8, validation_alias="MEMORY_AUTHORITATIVE_AT"
    )
    # Hermes / memory-os adoption A1: per-type item budgets. On write-back, a
    # type over its budget is consolidated (dedup + evict lowest-salience). 0 =
    # no cap (the consolidation step is skipped). Defaults match the design doc;
    # a stress revision sets a small budget so consolidation fires within a test
    # batch.
    memory_budget_semantic: int = Field(
        default=50, validation_alias="MEMORY_BUDGET_SEMANTIC"
    )
    memory_budget_episodic: int = Field(
        default=30, validation_alias="MEMORY_BUDGET_EPISODIC"
    )
    memory_budget_procedural: int = Field(
        default=10, validation_alias="MEMORY_BUDGET_PROCEDURAL"
    )
    # P2 #8: an un-evictable safety floor. A memory whose salience is >= this is
    # never evicted to satisfy a budget (a medical/safety fact must not be crowded
    # out). Default 0.0 → disabled (no pinning; the original consolidation
    # behavior). Set e.g. 0.95 once memory holds safety-critical facts.
    memory_safety_floor: float = Field(
        default=0.0, validation_alias="MEMORY_SAFETY_FLOOR"
    )
    # Live-infra (Piece B): when present, the agent ring selects the durable
    # Mem0MemoryBackend instead of the ephemeral InMemoryMemoryBackend so
    # long-term memory survives a Cloud Run restart. Absent (dev/tests/CI) →
    # in-memory. Phase 4 (replace-mem0-pgvector) replaces this selector with a
    # MEMORY_BACKEND=pgvector branch; the field itself stays in settings until
    # Phase 5 S6 (24h soak completes + mem0 keys revoked).
    mem0_api_key: str = Field(default="", validation_alias="MEM0_API_KEY")
    mem0_base_url: str = Field(
        default="https://api.mem0.ai", validation_alias="MEM0_BASE_URL"
    )
    # Phase 1 (replace-mem0-pgvector). The embedding port + LiteLLM adapter
    # ship now; the PgVectorMemoryBackend that consumes them lands in Phase 2.
    # Defaults match text-embedding-3-small. EMBEDDING_DIMENSION must match
    # the pgvector column type — changing it requires re-embedding every row.
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(
        default=1536, validation_alias="EMBEDDING_DIMENSION"
    )
    # Phase 4 (replace-mem0-pgvector). MEMORY_BACKEND replaces the legacy
    # ``mem0_api_key`` selector — the composition root builds the durable
    # PgVectorMemoryBackend only when this is set to ``"pgvector"`` AND a
    # ``DATABASE_URL`` is present AND an ``OPENAI_API_KEY`` is available for
    # the embedding client. Any missing piece raises ``MissingEnvError`` at
    # composition time — never silently fall back to InMemory in prod.
    # Default ``"inmemory"`` keeps dev/test/CI behaviour byte-identical.
    memory_backend: Literal["inmemory", "pgvector"] = Field(
        default="inmemory", validation_alias="MEMORY_BACKEND"
    )
    # Postgres connection string. Already consumed by the BFF thread store
    # (see [[bff-threads-cloudsql-driver-gap]]); Phase 4 reuses the same DSN
    # for the agent_memories table on the same Cloud SQL instance.
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    # OpenAI key. Already read directly inside ``_build_embedding_client`` via
    # the env mapping; lifted into settings here so ``build_components`` (which
    # only receives ``settings``) can detect its absence and fail loud when
    # ``MEMORY_BACKEND=pgvector`` is requested without an embedding provider.
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    # Anthropic chat key. litellm reads provider keys from the process env, so the
    # runtime needs ANTHROPIC_API_KEY in the environment before the first
    # ``ChatLiteLLM(model="anthropic/...")`` call under the "anthropic" profile
    # set. Lifted here (mirroring openai_api_key) so build_components can detect
    # its absence and fail loud rather than letting every Anthropic Auto run 401.
    # Chat-only — the pgvector embedding path still requires OPENAI_API_KEY.
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    # DeepSeek chat key. Same dispatch-by-prefix as anthropic: litellm reads
    # DEEPSEEK_API_KEY from the process env before the first
    # ``ChatLiteLLM(model="deepseek/...")`` call under the "deepseek" profile set.
    # Lifted here so the generalized provider-key guard below can fail loud.
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    # Which model registry the composition root wires (services/llm_config.py
    # build_model_registry). "openai" → the byte-identical-to-today OpenAI stack
    # (gpt-4o-mini fast / gpt-4o capable). "anthropic" → the 3-tier all-Anthropic
    # Auto stack (Haiku 4.5 fast / Sonnet 4.6 capable / Opus 4.8 reasoning).
    # "deepseek" → the DeepSeek V4 stack (Flash fast+capable / Pro reasoning).
    # Default "openai" so prod Auto is unchanged until a tagged revision promotes
    # the flag after the regression suites pass + the provider key is confirmed.
    model_profile_set: str = Field(
        default="openai", validation_alias="MODEL_PROFILE_SET"
    )
    # ─── C1 message-history compaction (design §9 / impl §6) ─────────────
    # Seven shadow-first knobs; the master flag (CONTEXT_COMPACT_MESSAGES)
    # gates BOTH seams (call_llm_node READ, evaluate_node WRITE), so with it
    # OFF the entire stack early-returns and the run is byte-identical to
    # today. Numeric defaults match services/base_config.py — promote on a
    # tagged revision, not silently in prod.
    context_compact_messages_enabled: bool = Field(
        default=False, validation_alias="CONTEXT_COMPACT_MESSAGES"
    )
    context_compact_trigger_fraction: float = Field(
        default=0.6, validation_alias="CONTEXT_COMPACT_TRIGGER_FRACTION"
    )
    context_observation_clear_fraction: float = Field(
        default=0.3, validation_alias="CONTEXT_OBSERVATION_CLEAR_FRACTION"
    )
    context_keep_last_k: int = Field(default=10, validation_alias="CONTEXT_KEEP_LAST_K")
    context_mask_after_steps: int = Field(
        default=10, validation_alias="CONTEXT_MASK_AFTER_STEPS"
    )
    context_compact_cooldown_steps: int = Field(
        default=5, validation_alias="CONTEXT_COMPACT_COOLDOWN_STEPS"
    )
    context_constraint_reinject_turns: int = Field(
        default=0, validation_alias="CONTEXT_CONSTRAINT_REINJECT_TURNS"
    )
    # C2 Phase 8 (design §8.3) — caller-side sampling gate for the L2 shadow
    # fidelity judge. 0.0 default keeps the L2 wire OFF in prod until
    # calibration earns the cost (AP-7).
    context_compaction_fidelity_sample_rate: float = Field(
        default=0.0, validation_alias="CONTEXT_COMPACTION_FIDELITY_SAMPLE_RATE"
    )
    # Fix 1 — harvest operator pins from human views into the §B2-R floor.
    # Default OFF keeps both fold sites passing user_constraints=[] (byte-
    # identical with the prior behaviour); flip ON to close the empty-floor gap.
    context_extract_user_constraints: bool = Field(
        default=False, validation_alias="CONTEXT_EXTRACT_USER_CONSTRAINTS"
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
                    "reflexion_enabled",
                    "t3_fanout_enabled",
                    "fanout_fault_inject",
                    "carrier_gate_enforce_enabled",
                    "carrier_gate_fault_inject",
                    "memory_enabled",
                    "memory_autocapture_enabled",
                    # C1 master flag (design §9) — the gate for BOTH seams.
                    "context_compact_messages_enabled",
                    # Fix 1 — user-pin harvest gate (default OFF).
                    "context_extract_user_constraints",
                ):
                    data[field_name] = _env_flag_from_mapping(env, alias)
                elif field_name == "max_reflexion_attempts":
                    data[field_name] = int(raw)
                elif field_name in (
                    # C1 numeric knobs (design §9). Ints stay ints, floats stay
                    # floats — the type the WRITE/READ seams arithmetic on.
                    "context_keep_last_k",
                    "context_mask_after_steps",
                    "context_compact_cooldown_steps",
                    "context_constraint_reinject_turns",
                ):
                    data[field_name] = int(raw)
                elif field_name in (
                    "context_compact_trigger_fraction",
                    "context_observation_clear_fraction",
                    # C2 Phase 8 — the sampling gate is a fraction (0.0–1.0).
                    "context_compaction_fidelity_sample_rate",
                ):
                    data[field_name] = float(raw)
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
    memory_service: Any = None
    memory_autocapture: Any = None


def _model_profiles(profile_set: str = "openai") -> tuple[list[Any], str]:
    """Return ``(models, default_model)`` for the wired profile set.

    Thin wiring over the H2-canonical registry in services/llm_config.py — the
    composition root only *selects* a set (from MODEL_PROFILE_SET), it does not
    own the catalog. See build_model_registry for the order-is-a-safety-contract
    invariant the router's first-match-per-tier depends on.
    """
    from services.llm_config import build_model_registry

    return build_model_registry(profile_set)


def _resolve_search_provider(settings: AgentRuntimeSettings) -> Any:
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
    models, default_model = _model_profiles(settings.model_profile_set)

    # Fail loud if a profile set is wired without the provider key its models
    # need: litellm reads provider keys from the process env at the first
    # ChatLiteLLM call, so an unset key would otherwise 401 on EVERY turn that
    # reaches that provider (a silent runtime failure, not a composition error).
    # Generalized provider→(litellm_id prefix, settings key, env var) map: guard
    # fires only for a provider that actually appears in the selected set's
    # models — so the keyless "openai" default set boots untouched, and adding a
    # new provider (deepseek) is one row here, not a new branch.
    _PROVIDER_KEY_GUARDS: tuple[tuple[str, str, str], ...] = (
        ("anthropic/", settings.anthropic_api_key, "ANTHROPIC_API_KEY"),
        ("deepseek/", settings.deepseek_api_key, "DEEPSEEK_API_KEY"),
    )
    for prefix, key_value, env_var in _PROVIDER_KEY_GUARDS:
        if any(m.litellm_id.startswith(prefix) for m in models) and not key_value:
            raise MissingEnvError(env_var)

    goal_judge_enabled = settings.goal_judge_enabled
    goal_judge_downgrade = settings.goal_judge_downgrade_enabled

    # Carrier-gate enforcement mode (Phase 2): flag OFF → "off" (shadow only).
    # Flag ON → dev raises (fail loud at the source), prod degrades (loud trace,
    # run continues). The mode collapses the flag + env split into one explicit
    # field consumed by the graph (services/base_config.carrier_gate_enforce_mode).
    if not settings.carrier_gate_enforce_enabled:
        carrier_gate_enforce_mode = "off"
    elif settings.agent_env == "prod":
        carrier_gate_enforce_mode = "degrade"
    else:
        carrier_gate_enforce_mode = "raise"

    agent_config = AgentConfig(
        default_model=default_model,
        models=models,
        max_steps=20,
        max_cost_usd=1.0,
        goal_judge_enabled=goal_judge_enabled,
        goal_judge_downgrade_enabled=goal_judge_downgrade,
        # Tiered-loops flags (Step 0): reach the live path. Default OFF in prod;
        # a dedicated stress revision flips these to exercise Phases 1-3.
        plan_source=settings.planning_plan_source,
        reflexion_enabled=settings.reflexion_enabled,
        max_reflexion_attempts=settings.max_reflexion_attempts,
        t3_fanout_enabled=settings.t3_fanout_enabled,
        fanout_fault_inject=settings.fanout_fault_inject,
        carrier_gate_enforce_mode=carrier_gate_enforce_mode,
        carrier_gate_fault_inject=settings.carrier_gate_fault_inject,
        memory_enabled=settings.memory_enabled,
        # Hermes / memory-os recall refinements (A2/A3). Default-identity values
        # (0.0 floor / 0.8 tier) keep recall byte-identical until a tagged
        # revision tunes them.
        memory_recall_min_relevance=settings.memory_recall_min_relevance,
        memory_authoritative_at=settings.memory_authoritative_at,
        # C1 message-history compaction (design §9). Direct copy — the
        # carrier_gate_enforce_mode derivation pattern doesn't apply here;
        # every C1 knob is the operator's literal intent. Default-off across
        # the board, so an empty env yields the byte-identical-when-off path.
        context_compact_messages_enabled=settings.context_compact_messages_enabled,
        context_compact_trigger_fraction=settings.context_compact_trigger_fraction,
        context_observation_clear_fraction=settings.context_observation_clear_fraction,
        context_keep_last_k=settings.context_keep_last_k,
        context_mask_after_steps=settings.context_mask_after_steps,
        context_compact_cooldown_steps=settings.context_compact_cooldown_steps,
        context_constraint_reinject_turns=settings.context_constraint_reinject_turns,
        context_compaction_fidelity_sample_rate=settings.context_compaction_fidelity_sample_rate,
        context_extract_user_constraints=settings.context_extract_user_constraints,
    )

    delegation_dispatcher = LocalLLMDelegationDispatcher(agent_config)
    tool_registry = ToolRegistry(
        {
            "shell": ToolDefinition(
                # Not cacheable: same hazard as file_io below — shell reads mutable
                # filesystem state (cat/ls/grep/...), so a cached result is silently
                # stale after the file changes later in the thread.
                executor=execute_shell,
                schema=ShellToolInput,
                cacheable=False,
            ),
            "file_io": ToolDefinition(
                # Not cacheable: the thread-level tool_cache keys on exact args and
                # never invalidates, so a cached read returns stale content after
                # the same path is overwritten later in the thread.
                executor=execute_file_io,
                schema=FileIOInput,
                cacheable=False,
            ),
            "state_file": ToolDefinition(
                executor=execute_state_file_tool,
                schema=StateFileToolInput,
                cacheable=False,
            ),
            "state_todo": ToolDefinition(
                executor=execute_state_todo_tool,
                schema=StateTodoToolInput,
                cacheable=False,
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
        }
    )

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

    # Phase 1 memory wiring: construct the injected LongTermMemoryService once at
    # the composition root (H7 — no node imports a backend). The graph reads only
    # the sync MemoryBackend port via this service. The service is built
    # regardless of memory_enabled so the graph shape is stable; the flag gates
    # the calls.
    #
    # Backend selection (Phase 4, replace-mem0-pgvector):
    #   ``MEMORY_BACKEND=pgvector``  → durable PgVectorMemoryBackend on Cloud SQL
    #                                  (requires DATABASE_URL + OPENAI_API_KEY;
    #                                  any missing piece raises MissingEnvError
    #                                  — never silently degrade in prod).
    #   ``MEMORY_BACKEND=inmemory``  → ephemeral InMemoryMemoryBackend (default;
    #                                  dev/test/CI).
    # The legacy ``mem0_api_key`` selector was retired here — the mem0 backend
    # file stays on disk until Phase 5 S6 (after 24h soak) so a redeploy of the
    # prior revision is still a valid rollback; this composition root never
    # wires it. (The async Mem0CloudClient + MemoryClient port were deleted in
    # Phase 3.)
    from services.long_term_memory import (
        InMemoryMemoryBackend,
        LongTermMemoryService,
    )

    memory_backend: Any
    if settings.memory_backend == "pgvector":
        if not settings.database_url:
            raise MissingEnvError("DATABASE_URL")
        if not settings.openai_api_key:
            raise MissingEnvError("OPENAI_API_KEY")
        from middleware.adapters.embedding.litellm_embedding_client import (
            LiteLLMEmbeddingClient,
        )
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        embedding_client = LiteLLMEmbeddingClient(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            api_key=settings.openai_api_key,
        )
        memory_backend = PgVectorMemoryBackend(
            embedding_client=embedding_client,
            dsn=settings.database_url,
        )
        _logger.info("memory backend: pgvector (durable)")
    else:
        memory_backend = InMemoryMemoryBackend()
        _logger.info("memory backend: in-memory (ephemeral)")
    # A1 per-type item budgets (Hermes adoption), injected at the root so EVERY
    # writer (autocapture, the /agent/memory CRUD route, the panel) consolidates
    # on overflow — no writer can grow the store unbounded.
    memory_budgets = {
        "semantic": settings.memory_budget_semantic,
        "episodic": settings.memory_budget_episodic,
        "procedural": settings.memory_budget_procedural,
    }
    # P2 #8 safety floor: 0.0 (default) → disabled (no pinning); a positive value
    # pins facts at/above it so consolidation never evicts a safety-critical fact.
    safety_floor = settings.memory_safety_floor or None
    memory_service = LongTermMemoryService(
        memory_backend, budgets=memory_budgets, safety_floor=safety_floor
    )

    # Phase 2 typed background auto-capture: construct the post-run autocapture
    # seam at the root too. It runs OUTSIDE the graph hot path (the runtime
    # adapter calls it after a run finishes), so it does not enter build_graph.
    # write_back is gated on MEMORY_AUTOCAPTURE_ENABLED — default OFF means
    # shadow (propose-only); the extractor still runs and the trace carries the
    # proposal, but nothing is stored until the eval enable-policy clears.
    import importlib

    from services.base_config import default_fast_profile
    from services.governance.black_box import BlackBoxRecorder
    from services.llm_config import LLMService
    from services.memory_autocapture import MemoryAutoCaptureService
    from services.prompt_service import PromptService

    # Load the extractor component by string reference (importlib), not a static
    # Python import — same layering contract as the graph factory
    # (_load_graph_factory): middleware/ must not statically import components/
    # (F4). The autocapture service depends only on the structural extractor
    # port, so this stays clean.
    _MemoryExtractor = getattr(
        importlib.import_module("components.memory_extractor"), "MemoryExtractor"
    )
    memory_extractor = _MemoryExtractor(
        llm_service=LLMService(config=agent_config),
        prompt_service=PromptService(),
        profile=default_fast_profile(),
    )
    # Enable-policy guard: the flag is the operator's intent, but write-back only
    # actually turns on when a passing frozen-test-split calibration certificate
    # is also present (machine-checked, not honour-system). Flag-on-but-no-cert
    # fails SAFE to shadow and is logged loudly — write-back must never store
    # ungated. Rollback is unchanged (flag off → shadow instantly).
    from services.governance.memory_enable_policy import (
        load_certificate,
        resolve_write_back,
    )

    _wb = resolve_write_back(
        flag_requested=settings.memory_autocapture_enabled,
        certificate=load_certificate(settings.memory_autocapture_cert or None),
    )
    if _wb.blocked:
        _logger.warning("memory autocapture: %s", _wb.reason)
    else:
        _logger.info("memory autocapture: %s", _wb.reason)
    memory_autocapture = MemoryAutoCaptureService(
        extractor=memory_extractor,
        memory_service=memory_service,
        write_back_enabled=_wb.write_back_enabled,
        # Same recordings dir the graph writes to (cache_dir / black_box_recordings)
        # so proposal carriers land in the run's own workflow trace.
        black_box=BlackBoxRecorder(cache_dir / "black_box_recordings"),
        # A1 budgets are enforced in memory_service.store (injected above), so
        # autocapture needs no budget map — it emits the carrier from store()'s
        # returned ConsolidationOutcome.
    )

    return AgentComponents(
        agent_config=agent_config,
        tool_registry=tool_registry,
        agent_facts_registry=agent_facts_registry,
        cache_dir=cache_dir,
        goal_judge_config_reader=goal_judge_config_reader,
        settings=settings,
        memory_service=memory_service,
        memory_autocapture=memory_autocapture,
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
    bound_capabilities: list[str] | None = None,
) -> Any:
    """Single call site for ``build_graph`` with reader injection.

    ``bound_capabilities`` (ADR-0007): the declared capability list an
    identity-bound instance passes so ``build_graph`` binds ONLY those tools'
    schemas to the LLM. ``None`` (the default) keeps every existing caller
    byte-identical (full registry bound, as today).
    """
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
        memory_service=components.memory_service,
        bound_capabilities=bound_capabilities,
    )


# Coach identity-contract fields (ADR-0007/ADR-0012): these come from the
# ratified card in services/governance/subject_coach_identity.py — a base
# deployment config must never override them (gating OFF, default capture
# tag, or an empty guardrail would silently un-govern the instance).
_COACH_IDENTITY_FIELDS: frozenset[str] = frozenset(
    {
        "agent_name",
        "agent_version",
        "capability_gating_enabled",
        "input_guardrail_accept_condition",
        "eval_capture_target",
        "additional_instructions",
    }
)


def build_coach_components(components: AgentComponents) -> AgentComponents:
    """Derive the subject-coach components bag from the deployment bag.

    Identity-contract fields come from ``subject_coach_agent_config`` (the
    ratified least-privilege contract, FR-1..11); every other knob carries
    the deployment's runtime posture (models, budgets, compaction flags) so
    the coach shadows the same stack chat runs on. The persona is the
    rendered ``.j2`` (H1 — never a hardcoded string), injected via
    ``additional_instructions``. Callers pass
    ``bound_capabilities=SUBJECT_COACH_CAPABILITIES`` to
    ``build_runtime_graph`` alongside this bag.
    """
    from dataclasses import replace

    from services.governance.subject_coach_identity import (
        subject_coach_agent_config,
    )
    from services.prompt_service import PromptService

    persona = PromptService().render_prompt(
        "subject_coach_system_prompt", subject="English"
    )
    base = components.agent_config
    carried = {
        name: getattr(base, name)
        for name in type(base).model_fields
        if name not in _COACH_IDENTITY_FIELDS
    }
    coach_config = subject_coach_agent_config(
        additional_instructions=persona, **carried
    )
    return replace(components, agent_config=coach_config)
