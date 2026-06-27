"""Shared test fixtures for the Trust Foundation test suite."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

try:
    from freezegun import freeze_time as _freezegun_freeze_time
except ImportError:  # pragma: no cover - dev extra only
    _freezegun_freeze_time = None

# Modules middleware tests load before freezegun runs; skipping them avoids
# pydantic schema errors when freezegun walks lazy langfuse.api attributes.
_FREEZEGUN_IGNORE = ["langfuse"]


def freeze_time(*args, **kwargs):
    """freezegun wrapper that ignores langfuse (safe after middleware test runs)."""
    if _freezegun_freeze_time is None:
        raise RuntimeError("freezegun is required for freeze_time() tests")
    ignore = list(kwargs.pop("ignore", []))
    for name in _FREEZEGUN_IGNORE:
        if name not in ignore:
            ignore.append(name)
    return _freezegun_freeze_time(*args, ignore=ignore, **kwargs)


AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


@pytest.fixture()
def future_datetime() -> datetime:
    return datetime.now(UTC) + timedelta(days=365)


@pytest.fixture()
def past_datetime() -> datetime:
    return datetime.now(UTC) - timedelta(days=1)


# ── Factory helpers (plain callables, re-used as fixtures below) ──────


def make_valid_facts(**overrides):
    """Factory for a minimal valid AgentFacts instance."""
    from trust.models import AgentFacts

    defaults = {
        "agent_id": "agent-001",
        "agent_name": "TestBot",
        "owner": "team-test",
        "version": "1.0.0",
    }
    defaults.update(overrides)
    return AgentFacts(**defaults)


def make_identity_context(**overrides):
    """Factory for a minimal valid IdentityContext instance."""
    from trust.cloud_identity import IdentityContext

    defaults = {
        "provider": "local",
        "principal_id": "test-principal",
        "display_name": "Test Principal",
        "account_id": "test-account",
    }
    defaults.update(overrides)
    return IdentityContext(**defaults)


def make_temporary_credentials(**overrides):
    """Factory for a minimal valid TemporaryCredentials instance."""
    from trust.cloud_identity import TemporaryCredentials

    defaults = {
        "provider": "local",
        "access_token": "test-token",
        "expiry": datetime.now(UTC) + timedelta(minutes=15),
        "agent_id": "agent-001",
    }
    defaults.update(overrides)
    return TemporaryCredentials(**defaults)


def make_certificate(**overrides):
    """Factory for a minimal valid Certificate instance (review_schema)."""
    from trust.review_schema import Certificate

    defaults = {
        "premises": ["[P1] tool output"],
        "conclusion": "RULE FAIL -- reason",
    }
    defaults.update(overrides)
    return Certificate(**defaults)


def make_review_finding(**overrides):
    """Factory for a minimal valid ReviewFinding instance (review_schema)."""
    from trust.review_schema import ReviewFinding, Severity

    defaults = {
        "rule_id": "D1.R1",
        "dimension": "D1",
        "severity": Severity.WARNING,
        "file": "trust/models.py",
        "description": "Test finding",
        "confidence": 0.9,
        "certificate": make_certificate(),
    }
    defaults.update(overrides)
    return ReviewFinding(**defaults)


# ── Fixture wrappers around the factories ─────────────────────────────


@pytest.fixture()
def agent_facts_factory():
    """Fixture returning the AgentFacts factory callable."""
    return make_valid_facts


@pytest.fixture()
def identity_context_factory():
    """Fixture returning the IdentityContext factory callable."""
    return make_identity_context


@pytest.fixture()
def temporary_credentials_factory():
    """Fixture returning the TemporaryCredentials factory callable."""
    return make_temporary_credentials


@pytest.fixture()
def certificate_factory():
    """Fixture returning the Certificate factory callable."""
    return make_certificate


@pytest.fixture()
def review_finding_factory():
    """Fixture returning the ReviewFinding factory callable."""
    return make_review_finding


def _reset_logging_after_dictconfig() -> None:
    """Clear global handlers left by logging.config.dictConfig (H4 setup_logging).

    Avoid ``logging.shutdown()`` — it can disturb freezegun/hypothesis time mocks.
    """
    for name in list(logging.root.manager.loggerDict.keys()):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        logger.filters.clear()
        logger.propagate = True
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()


@pytest.fixture(autouse=True)
def _isolate_logging_handlers():
    """Keep caplog-based L2 tests independent of setup_logging() side effects."""
    _reset_logging_after_dictconfig()
    yield
    _reset_logging_after_dictconfig()
