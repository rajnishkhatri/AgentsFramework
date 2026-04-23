"""middleware/adapters/ — concrete implementations of port Protocols.

Each subdirectory is one adapter family:

  * ``auth/`` — JWT verifiers (WorkOS, Auth0, ...)
  * ``acl/``  — tool ACL providers (WorkOS roles, static config, ...)
  * ``memory/`` — long-term memory clients (Mem0 Cloud, self-hosted, ...)
  * ``observability/`` — telemetry exporters (Langfuse, Cloud Trace, ...)

**SDK isolation** (rule F-R2 / A1): third-party SDK imports
(``jwt``, ``mem0ai``, ``langfuse``, ``workos``) MUST appear only in this
sub-tree. ``tests/architecture/test_middleware_layer.py`` enforces this
on every commit.
"""
