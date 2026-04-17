"""L2 Reproducible: Tests for services/eval_capture.py.

Contract-driven TDD. Tests EvalRecord construction and logging.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from services.eval_capture import record


class TestEvalCapture:
    @pytest.mark.asyncio
    async def test_record_emits_log(self, caplog):
        config = {"configurable": {"task_id": "t1", "user_id": "u1"}}
        with caplog.at_level(logging.INFO, logger="services.eval_capture"):
            await record(
                target="call_llm",
                ai_input={"prompt": "hello"},
                ai_response={"content": "hi"},
                config=config,
                step=1,
                model="gpt-4o-mini",
            )
        assert len(caplog.records) >= 1

    @pytest.mark.asyncio
    async def test_record_includes_user_id(self, caplog):
        config = {"configurable": {"task_id": "t1", "user_id": "user-42"}}
        with caplog.at_level(logging.INFO, logger="services.eval_capture"):
            await record(
                target="guardrail",
                ai_input={},
                ai_response="accept",
                config=config,
                step=0,
            )
        assert any("user-42" in str(r.__dict__) or "user-42" in r.getMessage() for r in caplog.records)
