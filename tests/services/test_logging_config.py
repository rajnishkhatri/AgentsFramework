"""US-0.3: Validate logging.json structure and the new handlers added in S0.

Per AGENT_UI_ADAPTER_SPRINTS.md US-0.3, [AGENTS.md](../../AGENTS.md) H4.
Failure paths first.
"""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path

import pytest

LOGGING_PATH = Path(__file__).resolve().parent.parent.parent / "logging.json"

REQUIRED_NEW_HANDLERS = [
    "trust_trace",
    "authorization",
    "long_term_memory",
    "agent_ui_adapter_server",
    "agent_ui_adapter_transport",
    "agent_ui_adapter_translators",
]

REQUIRED_NEW_LOGGERS = [
    "trust.trace",
    "services.authorization",
    "services.long_term_memory",
    "agent_ui_adapter.server",
    "agent_ui_adapter.transport",
    "agent_ui_adapter.translators",
]


@pytest.fixture(scope="module")
def config() -> dict:
    return json.loads(LOGGING_PATH.read_text())


# ── Failure paths first ───────────────────────────────────────────────


def test_logging_json_is_parseable(config: dict) -> None:
    assert isinstance(config, dict)
    assert "handlers" in config
    assert "loggers" in config


@pytest.mark.parametrize("handler", REQUIRED_NEW_HANDLERS)
def test_required_handler_exists(config: dict, handler: str) -> None:
    assert handler in config["handlers"], (
        f"S0 US-0.3 requires handler '{handler}' in logging.json"
    )


@pytest.mark.parametrize("logger_name", REQUIRED_NEW_LOGGERS)
def test_required_logger_exists(config: dict, logger_name: str) -> None:
    assert logger_name in config["loggers"], (
        f"S0 US-0.3 requires logger '{logger_name}' in logging.json"
    )


# ── Acceptance: dictConfig accepts the file ───────────────────────────


def test_logging_config_loads_without_error(tmp_path: Path, config: dict) -> None:
    """logging.dictConfig accepts the configuration. Redirects file handlers
    to a tmp_path so the test does not litter the workspace logs/ folder."""
    redirected = json.loads(json.dumps(config))  # deep copy
    for handler_cfg in redirected["handlers"].values():
        if "filename" in handler_cfg:
            handler_cfg["filename"] = str(tmp_path / Path(handler_cfg["filename"]).name)
    logging.config.dictConfig(redirected)
    for logger_name in REQUIRED_NEW_LOGGERS:
        logger = logging.getLogger(logger_name)
        assert logger is not None
