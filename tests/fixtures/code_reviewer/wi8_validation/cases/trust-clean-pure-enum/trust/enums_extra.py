"""Clean trust-kernel enum — pure data, no I/O, no logging, no upward imports."""

from enum import Enum


class RetryPolicy(str, Enum):
    """Retry strategy for an operation.

    NONE        — do not retry.
    LINEAR      — fixed-delay retries.
    EXPONENTIAL — backoff retries.
    """

    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
