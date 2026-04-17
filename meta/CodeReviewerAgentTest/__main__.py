"""Allow ``python -m meta.CodeReviewerAgentTest <config.json>``."""

from __future__ import annotations

import sys

from meta.CodeReviewerAgentTest.cli import main

if __name__ == "__main__":
    sys.exit(main())
