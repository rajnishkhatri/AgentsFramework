"""Leak-rate over the coded_slice with the truncated-reply confound partitioned.

The one hard rule of axial coding: no count from an unpartitioned aggregate.
`truncated-reply` is environment-confound *by cause* (a sandbox/harness cutoff),
so it is a validity precondition, not a behavioral bucket. But per the straddle
rule we assign by cause and decide the CONSEQUENCE per trace: a truncated reply
is only unscorable for LEAK if the cut lands before any leak is observable. When
the leak is already in the visible text, the leak verdict is safe and the trace
stays in the denominator.

This script prints the three candidate rates and the one to trust.
"""

from __future__ import annotations

import json
from pathlib import Path

FIX = Path("docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl")
LEAK_CODES = {"leak-strong-implication", "hands-over-conclusion", "rule-naming-as-leak"}


def main() -> None:
    rows = [json.loads(l) for l in FIX.read_text().splitlines() if l.strip()]
    n = len(rows)

    leak = {r["trace_id"] for r in rows if set(r["open_codes"]) & LEAK_CODES}
    trunc = {r["trace_id"] for r in rows if "truncated-reply" in r["open_codes"]}

    # A truncated trace is unscorable for LEAK only if it shows no leak in the
    # observed text (the leak question can't be answered — the tail is lost).
    # A truncated trace that already leaked before the cut is safely scorable.
    trunc_unscorable = trunc - leak  # truncated AND no visible leak
    trunc_leaked = trunc & leak  # truncated BUT leak already visible

    print(f"N total traces:            {n}")
    print(f"leak traces:               {len(leak)}")
    print(f"truncated traces:          {len(trunc)}  {sorted(t[:8] for t in trunc)}")
    print(
        f"  truncated + leaked:      {len(trunc_leaked)}  {sorted(t[:8] for t in trunc_leaked)}"
    )
    print(
        f"  truncated, unscorable:   {len(trunc_unscorable)}  {sorted(t[:8] for t in trunc_unscorable)}"
    )
    print()

    naive = len(leak) / n
    excl_all = len(leak - trunc) / (n - len(trunc))
    trust_num = len(leak)
    trust_den = n - len(trunc_unscorable)
    trust = trust_num / trust_den

    print(
        "A. naive (poisoned aggregate):        %2d/%2d = %.3f" % (len(leak), n, naive)
    )
    print(
        "B. exclude ALL truncated (over-corr): %2d/%2d = %.3f"
        % (len(leak - trunc), n - len(trunc), excl_all)
    )
    print(
        "C. exclude only unscorable (TRUST):   %2d/%2d = %.3f"
        % (trust_num, trust_den, trust)
    )
    print()
    print(
        f"NUMBER TO TRUST: {trust:.3f}  ({trust_num}/{trust_den}, ~{trust * 100:.0f}%)"
    )


if __name__ == "__main__":
    main()
