"""Allow ``python -m code_reviewer.frontend ...`` invocation.

Forwards directly to :func:`code_reviewer.frontend.runner.run`. See that
module's docstring for the full CLI contract.
"""

from __future__ import annotations

import sys

from code_reviewer.frontend.runner import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
