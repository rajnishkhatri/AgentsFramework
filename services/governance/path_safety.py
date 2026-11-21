"""Guards for identifiers that become file-system or object-store path segments.

Workflow ids and agent ids arrive from request state and are joined onto a
storage root. An id carrying a separator or a parent reference would read or
write outside that root, so every governance store checks ids here first.
"""

from __future__ import annotations

_FORBIDDEN_CHARS = ("/", "\\", "\x00")
_FORBIDDEN_VALUES = frozenset({".", ".."})


def is_safe_path_component(value: str) -> bool:
    """Whether ``value`` stays inside its storage root when used as one segment.

    The empty string is allowed: bare invocations without a workflow id resolve
    to the storage root itself, which is still inside the root.
    """
    if not isinstance(value, str):
        return False
    if value in _FORBIDDEN_VALUES:
        return False
    return not any(ch in value for ch in _FORBIDDEN_CHARS)


def require_safe_path_component(value: str, kind: str) -> str:
    """Return ``value`` unchanged, or raise ``ValueError`` naming ``kind``."""
    if not is_safe_path_component(value):
        raise ValueError(
            f"{kind} must not contain path separators or parent references: {value!r}"
        )
    return value


__all__ = ["is_safe_path_component", "require_safe_path_component"]
