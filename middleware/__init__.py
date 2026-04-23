"""middleware/ — Sprint 1 Python ring driving ``agent_ui_adapter``.

Per ``docs/Architectures/FRONTEND_ARCHITECTURE.md`` § "Middleware sub-ring".

Process role: a Cloud Run / Fargate FastAPI app that:
  1. Verifies WorkOS JWTs on inbound requests (M3 contract).
  2. Enforces per-WorkOS-role tool ACLs (Sprint 1 §1.3).
  3. Forwards SSE streams from the embedded ``agent_ui_adapter`` runtime
     (loaded via ``langgraph.json`` config -- F4).

Dependency contract (enforced by ``tests/architecture/test_middleware_layer.py``):

  * **M1**: nothing in ``trust/``, ``services/``, ``components/``,
    ``orchestration/``, ``governance/``, ``meta/``, or
    ``agent_ui_adapter/`` imports from ``middleware/``.
  * **F4**: ``middleware/`` imports only from ``trust/``, ``services/``,
    and ``agent_ui_adapter/wire/`` (plus stdlib + Pydantic + approved
    SDKs in ``adapters/``).
  * **F1**: ``ARCHITECTURE_PROFILE`` appears only in
    ``middleware/composition.py``.
"""
