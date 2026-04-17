"""Trust Foundation enums for lifecycle states and status values.

These string enums ensure type-safe status fields while remaining
compatible with plain string comparisons (e.g. ``status == "active"``).
"""

from __future__ import annotations

from enum import Enum


class IdentityStatus(str, Enum):
    """Lifecycle status for an agent identity.

    Maps to IAM role states:
      - ACTIVE:    role exists and is assumable
      - SUSPENDED: deny-all inline policy attached
      - REVOKED:   role deleted
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
