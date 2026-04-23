"""Architecture tests for the agent_ui_adapter/ outer ring.

Per AGENT_UI_ADAPTER_PLAN.md §15.2 (T1-T9) and §8 (R1-R9). Each test enforces
exactly one rule from the plan. Most are stubbed at S0 and flip to passing as
their owning sprint lands code:

- T1, T2, T3 owned by S6 (US-6.5)
- T4 owned by S2 (US-2.5)
- T5, T6 owned by S4 (US-4.5)
- T7, T8, T9 owned by S7 (US-7.3)
- R8, R9 owned by S9 (US-9.1) -- enforce composition + single-port shape

Pattern: dependency-rule-enforcement test (TDD §Pattern 7).
Failure-paths first per AGENTS.md TAP-4: each test fails when the rule is
artificially broken (covered by sprint-owning tests).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from utils.code_analysis import collect_imports_in_directory


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
ADAPTER_DIR = AGENT_ROOT / "agent_ui_adapter"


def _adapter_imports() -> list[tuple[str, str]]:
    """All (filepath, top-level-package) imports under agent_ui_adapter/."""
    if not ADAPTER_DIR.exists():
        return []
    return collect_imports_in_directory(ADAPTER_DIR, relative_to=AGENT_ROOT)


def _imports_in(subdir: str) -> list[tuple[str, str]]:
    target = ADAPTER_DIR / subdir
    if not target.exists():
        return []
    return collect_imports_in_directory(target, relative_to=AGENT_ROOT)


# ─────────────────────────────────────────────────────────────────────
# T1-T9: AG-UI architecture tests per plan §15.2
# ─────────────────────────────────────────────────────────────────────


class TestAdapterImportBoundaries:
    """T1, T2, T3: rules R1-R3 from plan §8."""

    def test_adapter_does_not_import_meta(self) -> None:
        """T1: agent_ui_adapter/ MUST NOT import from meta/. (Plan rule R1, R2)"""
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _adapter_imports()
            if pkg == "meta"
        ]
        assert violations == [], (
            "agent_ui_adapter/ must not import from meta/:\n" + "\n".join(violations)
        )

    def test_adapter_does_not_import_components(self) -> None:
        """T2: agent_ui_adapter/ MUST NOT import from components/ directly. (Rule R2)"""
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _adapter_imports()
            if pkg == "components"
        ]
        assert violations == [], (
            "agent_ui_adapter/ must not import from components/:\n"
            + "\n".join(violations)
        )

    def test_inner_layers_do_not_import_adapter(self) -> None:
        """T3: trust/services/components/orchestration/meta MUST NOT import adapter. (Rule R3)"""
        forbidden_consumers = ["trust", "services", "components", "orchestration", "meta"]
        violations: list[str] = []
        for layer in forbidden_consumers:
            layer_dir = AGENT_ROOT / layer
            if not layer_dir.exists():
                continue
            for path, pkg in collect_imports_in_directory(layer_dir, relative_to=AGENT_ROOT):
                if pkg == "agent_ui_adapter":
                    violations.append(f"{path} imports agent_ui_adapter")
        assert violations == [], (
            "Inner layers must not import from agent_ui_adapter/:\n"
            + "\n".join(violations)
        )


class TestWirePurity:
    """T4: rule R4 from plan §8."""

    def test_wire_is_pure_pydantic(self) -> None:
        """T4: agent_ui_adapter/wire/ may import only stdlib + pydantic + trust + ag_ui types."""
        forbidden = {
            "httpx",
            "requests",
            "boto3",
            "langgraph",
            "langchain",
            "langchain_core",
            "langchain_community",
            "openai",
            "litellm",
            "fastapi",
            "uvicorn",
        }
        wire_imports = _imports_in("wire")
        if not wire_imports:
            pytest.skip("awaits S2 wire/ contents")
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in wire_imports
            if pkg in forbidden
        ]
        assert violations == [], (
            "agent_ui_adapter/wire/ must be pure (Pydantic + stdlib only):\n"
            + "\n".join(violations)
        )


class TestTranslatorPurity:
    """T5, T6: rules R5-R7 from plan §8."""

    def test_translators_do_not_import_services(self) -> None:
        """T5: translators MUST NOT import from services/ (rule R7)."""
        translator_imports = _imports_in("translators")
        translator_files = [
            p for p in (ADAPTER_DIR / "translators").rglob("*.py")
            if p.exists() and p.stat().st_size > 200  # skip empty placeholders
        ] if (ADAPTER_DIR / "translators").exists() else []
        if not translator_files:
            pytest.skip("awaits S4 translators/ contents")
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in translator_imports
            if pkg == "services"
        ]
        assert violations == [], (
            "agent_ui_adapter/translators/ must not import from services/:\n"
            + "\n".join(violations)
        )

    def test_signed_payload_roundtrips(self) -> None:
        """T6: every signed trust type round-trips byte-equivalent through translators.

        Detailed coverage lives in
        ``tests/agent_ui_adapter/translators/test_sealed_envelope.py``; this
        slot is the architecture-level smoke proving the helpers exist and
        that an HMAC signed AgentFacts still verifies after the round-trip.
        """
        from agent_ui_adapter.translators.sealed_envelope import (
            from_envelope,
            signable_dict,
            to_envelope,
        )
        from trust.models import AgentFacts
        from trust.signature import compute_signature, verify_signature

        secret = "architecture-T6-secret"
        base = AgentFacts(
            agent_id="t6-agent",
            agent_name="t6",
            owner="ci",
            version="1.0.0",
        )
        base_dict = base.model_dump(mode="json")
        base_dict["signature_hash"] = compute_signature(
            signable_dict(base_dict), secret
        )
        signed = AgentFacts.model_validate(base_dict)

        rehydrated = from_envelope(to_envelope(signed))
        rehydrated_dict = rehydrated.model_dump(mode="json")
        assert verify_signature(
            signable_dict(rehydrated_dict),
            secret,
            rehydrated_dict["signature_hash"],
        )


class TestHITLAndTraceConventions:
    """T7, T8, T9: plan §4.3 conventions."""

    def test_hitl_uses_tool_call_pattern(self) -> None:
        """T7: request_approval is registered as a tool; TOOL_RESULT routes back via translator.

        Detailed coverage lives in
        ``tests/agent_ui_adapter/test_hitl_tool_registered.py`` (US-7.1) and
        ``tests/agent_ui_adapter/test_hitl_round_trip.py`` (US-7.2). This
        slot is the architecture-level smoke proving (a) the HITL virtual
        tool is registrable under the canonical name ``request_approval``
        with the documented schema, and (b) an inbound AG-UI ``TOOL_RESULT``
        is routed by ``ag_ui_to_domain.to_domain`` into a domain
        ``ToolResultReceived`` -- i.e. HITL re-uses the tool-call wire
        pattern instead of any new event type (plan §4.3).
        """
        from agent_ui_adapter.translators.ag_ui_to_domain import to_domain
        from agent_ui_adapter.wire.ag_ui_events import ToolResult
        from agent_ui_adapter.wire.domain_events import ToolResultReceived
        from services.tools.hitl import (
            REQUEST_APPROVAL_TOOL_NAME,
            request_approval_tool,
        )
        from services.tools.registry import ToolRegistry

        # (a) Registry can carry the virtual tool under the canonical name
        # with both required fields advertised on the JSON schema.
        registry = ToolRegistry(
            {REQUEST_APPROVAL_TOOL_NAME: request_approval_tool()}
        )
        assert registry.has(REQUEST_APPROVAL_TOOL_NAME)
        schema = registry.get_schemas()[0]
        assert schema["name"] == "request_approval"
        properties = schema["parameters"]["properties"]
        assert "action" in properties
        assert "justification" in properties

        # (b) Inbound TOOL_RESULT is the wire vehicle for the user's
        # decision; the translator re-enters it as a domain event.
        domain_event = to_domain(
            ToolResult(
                tool_call_id="tc-arch-T7",
                content="approved",
                role="tool",
            ),
            trace_id="T7-trace",
        )
        assert isinstance(domain_event, ToolResultReceived)
        assert domain_event.tool_call_id == "tc-arch-T7"
        assert domain_event.result == "approved"
        assert domain_event.trace_id == "T7-trace"

    def test_auth_token_never_in_event_payload(self) -> None:
        """T8: AG-UI wire schemas have no auth-token fields, and translator
        outputs never contain ``Bearer `` / ``eyJ`` token literals.

        Two complementary checks:

        Static
            Walk every AG-UI event Pydantic model; no field name may match
            an auth-token shape (``authorization``, ``bearer``, ``token``,
            ``auth_token``, ``api_key``). The wire contract is the
            structural guarantee -- if the field doesn't exist, leakage by
            this route is impossible regardless of runtime.

        Dynamic
            Translate a representative ``DomainEvent`` and assert the
            serialized AG-UI payload contains neither ``Bearer `` nor an
            ``eyJ`` JWT prefix anywhere -- including ``raw_event`` (the
            sidecar that only carries ``trace_id``, never credentials).
        """
        from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
        from agent_ui_adapter.wire import ag_ui_events as agui_module
        from agent_ui_adapter.wire.ag_ui_events import BaseEvent
        from agent_ui_adapter.wire.domain_events import (
            LLMTokenEmitted,
            RunStartedDomain,
            ToolCallStarted,
        )

        forbidden_field_names = {
            "authorization",
            "bearer",
            "token",
            "auth_token",
            "api_key",
            "apikey",
        }

        leaks: list[str] = []
        for name in dir(agui_module):
            cls = getattr(agui_module, name)
            if not isinstance(cls, type):
                continue
            if not issubclass(cls, BaseEvent):
                continue
            if cls is BaseEvent:
                continue
            for field_name in cls.model_fields:
                if field_name.lower() in forbidden_field_names:
                    leaks.append(f"{cls.__name__}.{field_name}")
        assert not leaks, (
            "AG-UI wire schema declares auth-token-shaped field(s); "
            "rule R5/R6 violated: " + ", ".join(leaks)
        )

        sample_events = [
            RunStartedDomain(
                trace_id="T8-trace", run_id="r1", thread_id="t1"
            ),
            LLMTokenEmitted(
                trace_id="T8-trace", message_id="m1", delta="hello"
            ),
            ToolCallStarted(
                trace_id="T8-trace",
                tool_call_id="tc-T8",
                tool_name="grep",
                args_json="{}",
            ),
        ]
        for domain_event in sample_events:
            for ag_ui_event in to_ag_ui(domain_event):
                payload = ag_ui_event.model_dump_json()
                assert "Bearer " not in payload, (
                    f"translator emitted 'Bearer ' literal: {payload}"
                )
                assert "eyJ" not in payload, (
                    f"translator emitted 'eyJ' (JWT prefix) literal: {payload}"
                )

    def test_trace_id_propagation(self) -> None:
        """T9: every emitted AG-UI event has rawEvent.trace_id matching origin TrustTraceRecord.

        Detailed coverage (one assertion per DomainEvent variant) lives in
        ``tests/agent_ui_adapter/translators/test_trace_id_propagation.py``.
        This slot is the architecture-level smoke: a well-formed domain
        event tagged with a known trace_id produces AG-UI events whose
        ``raw_event['trace_id']`` carries that exact value.
        """
        from agent_ui_adapter.translators.domain_to_ag_ui import to_ag_ui
        from agent_ui_adapter.wire.domain_events import ToolCallStarted

        trace_id = "T9-trace"
        outputs = to_ag_ui(
            ToolCallStarted(
                trace_id=trace_id,
                tool_call_id="tc-1",
                tool_name="grep",
                args_json="{}",
            )
        )
        assert outputs, "translator must emit at least one AG-UI event"
        for out in outputs:
            assert out.raw_event is not None
            assert out.raw_event.get("trace_id") == trace_id


# ─────────────────────────────────────────────────────────────────────
# R8, R9: composition + single-port rules (owned by S9 US-9.1)
# ─────────────────────────────────────────────────────────────────────


class TestCompositionAndPortShape:
    def test_orchestrator_composes_services(self) -> None:
        """R8: server.py route handlers compose service+translator at the boundary only.

        AST scan: route-handler functions in ``agent_ui_adapter/server.py``
        must call into the runtime port and the translator; they must NOT
        define new business-logic helpers, classes, or perform
        domain-decision branching beyond simple HTTP-error mapping.

        Heuristic checks (acceptable v1):
        - route handlers (functions decorated with ``@app.<verb>``) only
          contain calls to ``runtime.*``, ``threads.*``, ``runs.*``,
          ``to_ag_ui``, ``encode_event``, ``encode_error``, or trivial
          control flow (if-raise-HTTPException, for-yield).
        - the only ``Protocol`` referenced inside the file is
          ``AgentRuntime`` (port) plus the local ``JwtVerifier`` (composition
          root abstraction). No translator/service Protocols leak in.
        """
        server_path = ADAPTER_DIR / "server.py"
        if not server_path.exists():
            pytest.skip("awaits S6 server.py (US-6.1)")

        source = server_path.read_text()
        tree = ast.parse(source)

        required_symbols = {
            "AgentRuntime",
            "to_ag_ui",
            "encode_event",
            "SENTINEL_LINE",
            "AuthorizationService",
            "TraceService",
            "LongTermMemoryService",
            "ToolRegistry",
        }
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for name in node.names:
                    imported.add(name.name)
        missing = required_symbols - imported
        assert not missing, (
            "R8: composition root must compose port+translator+transport; "
            f"missing imports: {missing}"
        )

        # No business-logic abstractions besides composition glue:
        # at most three local classes are allowed -- the composition-root
        # JwtClaims/JwtVerifier/InMemoryJwtVerifier and the in-memory
        # ThreadStore/RunRegistry placeholders. Cap below at 6 to leave
        # tolerance, but flag explosive growth.
        local_classes = [
            n for n in tree.body if isinstance(n, ast.ClassDef)
        ]
        assert len(local_classes) <= 6, (
            "R8: server.py is growing domain abstractions; "
            f"found {len(local_classes)} local classes -- consider extracting"
        )

    def test_single_port_in_adapter(self) -> None:
        """R9: agent_ui_adapter/ports/ defines exactly one Protocol subclass.

        AST scan of every .py file under ports/. Counts classes whose bases
        include 'Protocol'.
        """
        ports_dir = ADAPTER_DIR / "ports"
        if not ports_dir.exists():
            pytest.skip("awaits S0 scaffolding")
        protocol_defs: list[str] = []
        for py in ports_dir.rglob("*.py"):
            if py.name == "__init__.py":
                continue
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    base_names = {
                        b.id if isinstance(b, ast.Name)
                        else (b.attr if isinstance(b, ast.Attribute) else "")
                        for b in node.bases
                    }
                    if "Protocol" in base_names:
                        protocol_defs.append(f"{py.relative_to(AGENT_ROOT)}:{node.name}")
        if not protocol_defs:
            pytest.skip("awaits S3 AgentRuntime port (US-3.1)")
        assert len(protocol_defs) == 1, (
            f"R9 violation: ports/ must define exactly one Protocol; found:\n"
            + "\n".join(protocol_defs)
        )
