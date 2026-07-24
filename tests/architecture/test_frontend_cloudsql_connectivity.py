"""Architecture gate: T R.2 — Cloud SQL migration/runtime connectivity (FR-F1/F3).

Finding 2 from the coach-v3 end-to-end review: ``phase_frontend`` passed a
``/cloudsql/`` Unix-socket DSN to Node without Cloud SQL Proxy, and the
frontend service lacked the socket volume/mount + ``cloudsql.client`` grant.
This module tombstones the deploy-side half (proxy + node-pg URL shape);
the Terraform half lives in ``tests/infra/gcp/test_cloud_run_frontend.py``
and ``test_data.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEPLOY = _REPO_ROOT / "scripts/deploy_gcp.sh"
_FRONTEND_TF = _REPO_ROOT / "infra/gcp/cloud-run-frontend.tf"
_MIGRATE = _REPO_ROOT / "frontend/scripts/migrate_engine.mjs"
_PG_URL_HELPER = _REPO_ROOT / "frontend/lib/adapters/db/node_pg_url.ts"


def _phase_frontend_body(text: str) -> str:
    match = re.search(
        r"^phase_frontend\(\)\s*\{(.*?)^\}",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "scripts/deploy_gcp.sh must define phase_frontend()"
    return match.group(1)


class TestFrontendCloudSqlConnectivity:
    def test_phase_frontend_starts_cloud_sql_proxy_before_migrate(self) -> None:
        """T R.2 (a): migrate must not dial /cloudsql/ from the deploy host bare."""
        text = _DEPLOY.read_text()
        body = _phase_frontend_body(text)
        # Prefer the live invoke (not the header comment / dry-run string).
        proxy_invoke = re.search(
            r"^\s*cloud-sql-proxy\b",
            body,
            flags=re.MULTILINE,
        )
        migrate_invoke = re.search(
            r"node\s+scripts/migrate_engine\.mjs",
            body,
        )
        assert proxy_invoke is not None, (
            "phase_frontend must start cloud-sql-proxy (or equivalent) before "
            "migrate_engine.mjs — a /cloudsql/ socket DSN is unreachable from "
            "the deploy workstation without the proxy."
        )
        assert migrate_invoke is not None, (
            "phase_frontend must invoke node scripts/migrate_engine.mjs"
        )
        assert migrate_invoke.start() > proxy_invoke.start(), (
            "phase_frontend must start cloud-sql-proxy BEFORE invoking "
            "migrate_engine.mjs (ordering = reachability)."
        )

    def test_phase_frontend_migrate_is_pre_traffic(self) -> None:
        """T R.2 (c): migrate stays before tofu apply / traffic cutover."""
        body = _phase_frontend_body(_DEPLOY.read_text())
        migrate_pos = body.find("migrate_engine.mjs")
        # tofu_gate runs plan+apply; traffic is TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST.
        apply_markers = ("tofu_gate", "tofu apply", "TRAFFIC_TARGET")
        apply_positions = [body.find(m) for m in apply_markers if body.find(m) >= 0]
        assert migrate_pos >= 0, "phase_frontend must invoke migrate_engine.mjs"
        assert apply_positions, (
            "phase_frontend must still call tofu_gate / apply after migrate"
        )
        assert migrate_pos < min(apply_positions), (
            "migrate_engine.mjs must run BEFORE tofu_gate/apply so schema+seed "
            "are ready before the new revision takes traffic (FR-F3)."
        )

    def test_phase_frontend_normalizes_asyncpg_scheme_for_node_pg(self) -> None:
        """T R.2 (a): secret may be postgresql+asyncpg://; Node pg needs postgresql://."""
        body = _phase_frontend_body(_DEPLOY.read_text())
        asserts_normalization = (
            "to_node_pg_url" in body
            or "postgresql+asyncpg" in body
            or "+asyncpg" in body
            or "sed -E" in body
            and "postgresql" in body
        )
        assert asserts_normalization, (
            "phase_frontend must normalize postgresql+asyncpg:// → postgresql:// "
            "before handing DATABASE_URL to migrate_engine.mjs (Node pg)."
        )

    def test_frontend_tf_declares_cloudsql_volume_and_mount(self) -> None:
        """T R.2 (b): runtime half — volume + mount present in HCL source."""
        text = _FRONTEND_TF.read_text()
        assert "cloud_sql_instance" in text, (
            "cloud-run-frontend.tf must declare a cloud_sql_instance volume "
            "(built-in connector) for the engine DATABASE_URL socket."
        )
        assert 'mount_path = "/cloudsql"' in text or 'mount_path="/cloudsql"' in text, (
            "cloud-run-frontend.tf must mount the cloudsql volume at /cloudsql."
        )
        assert (
            "cloudsql.client" in text or "frontend_runtime_cloudsql_client" in text
        ), (
            "cloud-run-frontend.tf (or its depends_on) must reference the "
            "frontend_runtime cloudsql.client IAM grant."
        )

    def test_node_pg_url_helper_strips_asyncpg_dialect(self) -> None:
        """Shared helper exists so migrate + runtime Pool sites stay consistent."""
        assert _PG_URL_HELPER.exists(), (
            "frontend/lib/adapters/db/node_pg_url.ts must exist — normalize "
            "postgresql+asyncpg:// for every Node pg Pool / Client."
        )
        helper = _PG_URL_HELPER.read_text()
        assert "asyncpg" in helper.lower() or "+\\w+" in helper or "+w" in helper, (
            "node_pg_url helper must strip SQLAlchemy dialect markers (+asyncpg)."
        )
        migrate = _MIGRATE.read_text()
        assert (
            "toNodePg" in migrate
            or "to_node_pg" in migrate
            or "node_pg_url" in migrate
            or "+asyncpg" in migrate
        ), "migrate_engine.mjs must normalize the connection string for Node pg."
