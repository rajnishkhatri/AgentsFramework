"""Tests for trust/enums.py -- IdentityStatus enum."""

from __future__ import annotations

import pytest

from trust.enums import IdentityStatus


class TestIdentityStatus:
    def test_has_three_members(self):
        assert len(IdentityStatus) == 3, (
            "IdentityStatus must have exactly 3 members: ACTIVE, SUSPENDED, REVOKED"
        )

    def test_member_values(self):
        assert IdentityStatus.ACTIVE.value == "active", (
            "IdentityStatus.ACTIVE.value must serialize as 'active'"
        )
        assert IdentityStatus.SUSPENDED.value == "suspended", (
            "IdentityStatus.SUSPENDED.value must serialize as 'suspended'"
        )
        assert IdentityStatus.REVOKED.value == "revoked", (
            "IdentityStatus.REVOKED.value must serialize as 'revoked'"
        )

    def test_string_compatibility(self):
        """IdentityStatus is a str enum -- comparisons with plain strings work."""
        assert IdentityStatus.ACTIVE == "active", (
            "IdentityStatus.ACTIVE must compare equal to plain 'active' (str enum)"
        )
        assert IdentityStatus.SUSPENDED == "suspended", (
            "IdentityStatus.SUSPENDED must compare equal to plain 'suspended'"
        )
        assert IdentityStatus.REVOKED == "revoked", (
            "IdentityStatus.REVOKED must compare equal to plain 'revoked'"
        )

    def test_is_str_subclass(self):
        assert isinstance(IdentityStatus.ACTIVE, str), (
            "IdentityStatus members must be str instances so JSON "
            "serialization treats them as plain strings"
        )

    def test_construct_from_value(self):
        assert IdentityStatus("active") is IdentityStatus.ACTIVE, (
            "Constructing IdentityStatus('active') must return the ACTIVE singleton"
        )
        assert IdentityStatus("suspended") is IdentityStatus.SUSPENDED, (
            "Constructing IdentityStatus('suspended') must return the SUSPENDED singleton"
        )
        assert IdentityStatus("revoked") is IdentityStatus.REVOKED, (
            "Constructing IdentityStatus('revoked') must return the REVOKED singleton"
        )

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            IdentityStatus("invalid_status")

    def test_exhaustiveness(self):
        expected = {"active", "suspended", "revoked"}
        actual = {s.value for s in IdentityStatus}
        assert actual == expected, (
            f"IdentityStatus value set drifted: expected={expected}, actual={actual}"
        )
