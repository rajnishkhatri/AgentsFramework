"""L1 Deterministic: AG-UI version-pin sanity check.

Per AGENT_UI_ADAPTER_SPRINTS.md US-2.6 -- closes plan §13 risk R1
("AG-UI 0.x spec breaks before v1 ships").
"""

from __future__ import annotations

import re

from agent_ui_adapter.wire import ag_ui_events
from agent_ui_adapter.wire.ag_ui_events import AGUI_PINNED_VERSION


_PIN_RE = re.compile(r"^0\.\d+\.\d+$")


def test_pinned_version_is_a_0_x_string():
    assert isinstance(AGUI_PINNED_VERSION, str)
    assert _PIN_RE.match(AGUI_PINNED_VERSION), (
        f"AGUI_PINNED_VERSION={AGUI_PINNED_VERSION!r} must match 0.x.y "
        "(AG-UI 0.x line per plan §13 R1)"
    )


def test_pinned_version_documented_in_docstring():
    docstring = ag_ui_events.__doc__ or ""
    assert AGUI_PINNED_VERSION in docstring, (
        "Module docstring must reference the pinned version so reviewers "
        "see the pin without reading code."
    )
