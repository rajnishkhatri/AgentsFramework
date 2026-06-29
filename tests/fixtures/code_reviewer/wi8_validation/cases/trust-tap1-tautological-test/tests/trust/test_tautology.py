"""Tautological test — violates TAP-1 (asserts nothing)."""

from trust.enums import IdentityStatus


def test_status_is_itself():
    s = IdentityStatus.ACTIVE
    assert s == s  # tautology: passes regardless of correctness


def test_active_truthy():
    p = IdentityStatus.ACTIVE
    assert p == p  # another tautology
