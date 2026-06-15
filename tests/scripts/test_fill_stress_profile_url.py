"""Gate for the stress-profile URL filler (scripts/fill_stress_profile_url.py).

The script auto-fills the `stress` profile's base_url after a tagged deploy. The
risk it guards: a line-scan YAML edit that touches the WRONG block (clobbering
prod/local) or strips comments. Pure, no gcloud, no network — the `--url` path is
exercised directly via `_write_profile_url`.
"""
from __future__ import annotations

import pytest
import yaml

from scripts.fill_stress_profile_url import _write_profile_url

_SAMPLE = """\
default_profile: local

profiles:
  local:
    base_url: "http://localhost:3000"
    env:
      MOCK_MIDDLEWARE: "0"

  prod:
    base_url: "https://agent-frontend-w65nrxwkiq-uc.a.run.app"
    env:
      E2E_AUTHENTICATED: "1"

  # comment inside the stress block must survive
  stress:
    base_url: "https://stress---agent-frontend-REPLACE_HASH-uc.a.run.app"
    env:
      E2E_AUTHENTICATED: "1"
    requires:
      backend_loops: "REFLEXION_ENABLED=1"
"""

_URL = "https://stress---agent-frontend-w65nrxwkiq-uc.a.run.app"


def test_updates_only_the_stress_base_url() -> None:
    new_text, changed = _write_profile_url(_SAMPLE, _URL)
    assert changed
    d = yaml.safe_load(new_text)
    p = d["profiles"]
    assert p["stress"]["base_url"] == _URL
    # prod + local untouched (the clobber regression).
    assert p["prod"]["base_url"] == "https://agent-frontend-w65nrxwkiq-uc.a.run.app"
    assert p["local"]["base_url"] == "http://localhost:3000"
    # the stress block's other keys survive.
    assert p["stress"]["requires"]["backend_loops"] == "REFLEXION_ENABLED=1"


def test_preserves_comments() -> None:
    new_text, _ = _write_profile_url(_SAMPLE, _URL)
    assert "# comment inside the stress block must survive" in new_text


def test_idempotent_when_already_set() -> None:
    once, changed1 = _write_profile_url(_SAMPLE, _URL)
    assert changed1
    twice, changed2 = _write_profile_url(once, _URL)
    assert changed2 is False
    assert twice == once


def test_raises_when_no_stress_base_url() -> None:
    no_stress = "default_profile: local\nprofiles:\n  local:\n    base_url: \"x\"\n"
    with pytest.raises(SystemExit):
        _write_profile_url(no_stress, _URL)
