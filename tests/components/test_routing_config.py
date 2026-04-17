"""L1 Deterministic: Tests for components/routing_config.py.

Pure TDD (Red-Green-Refactor). Tests defaults, validation, roundtrip.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from components.routing_config import RoutingConfig


class TestRoutingConfig:
    def test_defaults(self):
        cfg = RoutingConfig()
        assert cfg.default_model == "gpt-4o-mini"
        assert cfg.escalate_after_failures == 2
        assert cfg.max_escalations == 3
        assert cfg.budget_downgrade_threshold == 0.8

    def test_override_defaults(self):
        cfg = RoutingConfig(
            default_model="gpt-4o",
            escalate_after_failures=3,
            max_escalations=5,
            budget_downgrade_threshold=0.9,
        )
        assert cfg.default_model == "gpt-4o"
        assert cfg.escalate_after_failures == 3

    def test_roundtrip_json(self):
        cfg = RoutingConfig(default_model="claude-3-sonnet", max_escalations=10)
        restored = RoutingConfig.model_validate_json(cfg.model_dump_json())
        assert restored == cfg
