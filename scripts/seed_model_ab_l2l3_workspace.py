"""Deterministic workspace fixtures for the model-A/B GEN-L2/L3 answer corpus.

The L2/L3 prompts (frontend/e2e/fixtures/model_ab_corpus.json, difficulty L2/L3)
reference files under ``/workspace/…`` that were NEVER seeded — so every L2/L3 run
graded *file-absence handling*, not reasoning (confirmed by the opus-4-8 drive
2026-06-25: "no budget.csv exists in the workspace"). This is the L2/L3 analogue of
the GEN-L1 gap that seed_model_ab_workspace.py fixed.

This module seeds each referenced file with KNOWN content whose correct answer is
fully determined by the fixture. Unlike L1 (single deterministic value), L2/L3
answers are COMPOUND prose — so this module ALSO exports ``GROUND_TRUTH`` (a per-case
fact list) that the blind-adjudication rubric keys are authored from
(docs/plans/model_ab_l2l3_blind_adjudication.plan.md, Phase 1). The fixture and the
ground-truth facts are kept side by side here as the single source of truth.

Paths: prompts say ``/workspace/X`` but the file-IO tool sandboxes to ``WORKSPACE_DIR``
(= ``<repo>/workspace``); the agent resolves ``/workspace/X`` against that boundary.
We therefore seed at the SAME RELATIVE structure under ``<repo>/workspace``.

Idempotent: every call overwrites. Machine-independent: writes under the passed
``workspace`` dir, not the literal ``/workspace`` OS root.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = AGENT_ROOT / "workspace"


def _fresh_dir(path: Path) -> Path:
    """mkdir(parents, exist_ok) but tolerate a stray non-directory at the path.

    A prior contaminated run (e.g. an agent writing 'directory does not exist' as a
    FILE at workspace/invoices) leaves a non-dir where a fixture dir must go, which
    breaks plain mkdir. Remove the conflicting file/symlink first so the seeder is
    idempotent even after such a run.
    """
    if path.exists() and not path.is_dir():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class GroundTruth:
    """The compound correct answer the seeded fixtures imply for one L2/L3 case.

    ``facts`` is the must-have fact list (what a correct answer MUST contain);
    ``notes`` records acceptable variation (units/ordering/rounding/format). The
    Phase-1 rubric keys are authored verbatim from these, so the fixture and the
    grading rubric can never drift.
    """

    case: str
    facts: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


# ── Fixtures + the ground truth they imply (ONE source of truth) ─────────────


def _seed(ws: Path) -> None:
    # 07 multi-file-reconcile: sum 'paid' invoice amounts -> write to out/paid.txt
    #    inv-1 100 paid, inv-2 250 unpaid, inv-3 75 paid, inv-4 300 paid,
    #    inv-5 40 unpaid  => paid subtotal = 100+75+300 = 475
    inv = _fresh_dir(ws / "invoices")
    (inv / "inv-1.txt").write_text("amount: 100\nstatus: paid\n")
    (inv / "inv-2.txt").write_text("amount: 250\nstatus: unpaid\n")
    (inv / "inv-3.txt").write_text("amount: 75\nstatus: paid\n")
    (inv / "inv-4.txt").write_text("amount: 300\nstatus: paid\n")
    (inv / "inv-5.txt").write_text("amount: 40\nstatus: unpaid\n")

    # 08 cross-ref-lookup: orders -> customer -> region; count per region.
    #    customers: c1=north, c2=south, c3=north, c4=west
    #    orders: o1->c1, o2->c2, o3->c1, o4->c3, o5->c4, o6->c2, o7->c1
    #    regions: north = c1(o1,o3,o7)+c3(o4) = 4 ; south = c2(o2,o6) = 2 ; west = c4(o5) = 1
    (ws / "orders.csv").write_text(
        "order_id,customer_id\no1,c1\no2,c2\no3,c1\no4,c3\no5,c4\no6,c2\no7,c1\n"
    )
    (ws / "customers.csv").write_text(
        "customer_id,region\nc1,north\nc2,south\nc3,north\nc4,west\n"
    )

    # 09 pipeline-transform: ERROR lines per hour; peak hour. Timestamps HH:MM:SS.
    #    08:xx -> 1 ERROR ; 09:xx -> 3 ERROR ; 10:xx -> 1 ERROR  => peak hour 09
    (ws / "events.log").write_text(
        "08:01:10 INFO start\n"
        "08:15:00 ERROR disk full\n"
        "09:02:11 ERROR timeout\n"
        "09:05:42 WARN retry\n"
        "09:10:00 ERROR timeout\n"
        "09:59:59 ERROR timeout\n"
        "10:00:01 INFO ok\n"
        "10:30:00 ERROR oom\n"
    )

    # 10 multi-source-synthesis: q1=200, q2=250, q3=300.
    #    q1->q2 = (250-200)/200 = 25% ; q2->q3 = (300-250)/250 = 20%
    rep = _fresh_dir(ws / "reports")
    (rep / "q1.txt").write_text("Quarter 1 summary.\nTOTAL: 200\n")
    (rep / "q2.txt").write_text("Quarter 2 summary.\nTOTAL: 250\n")
    (rep / "q3.txt").write_text("Quarter 3 summary.\nTOTAL: 300\n")

    # 11 verify-and-fix: config has host but port is 70000 (out of 1..65535) =>
    #    INVALID; corrected port must be the fallback the prompt names. We seed an
    #    invalid port and a missing-nothing-else config so the single defect is
    #    unambiguous: port out of range.
    (ws / "config.json").write_text(
        json.dumps({"host": "db.internal", "port": 70000}) + "\n"
    )

    # 12 dependency-resolve: a DAG with a unique-enough topo order.
    #    A->B, A->C, B->D, C->D  (A depends on B,C; B,C depend on D)
    #    install order (deps first): D, then B and C, then A.
    (ws / "deps.txt").write_text("A -> B\nA -> C\nB -> D\nC -> D\n")

    # 13 constraint-solve: 30-min Monday slots; find one for >=4 of 5, earliest.
    #    Slots present: p1{09:00,10:00,11:00} p2{09:00,11:00} p3{09:00,10:00}
    #    p4{09:00,11:00} p5{10:00,11:00}
    #    09:00 -> p1,p2,p3,p4 = 4 ; 10:00 -> p1,p3,p5 = 3 ; 11:00 -> p1,p2,p4,p5 = 4
    #    earliest covering >=4 = 09:00 (attendees p1,p2,p3,p4; absent p5)
    sch = _fresh_dir(ws / "schedule")
    (sch / "p1.txt").write_text("09:00\n10:00\n11:00\n")
    (sch / "p2.txt").write_text("09:00\n11:00\n")
    (sch / "p3.txt").write_text("09:00\n10:00\n")
    (sch / "p4.txt").write_text("09:00\n11:00\n")
    (sch / "p5.txt").write_text("10:00\n11:00\n")

    # 14 multi-hop-synthesis: citation graph; most-cited paper + its claim.
    #    cites: p1->p3 ; p2->p3 ; p4->p3 ; p3->(none)  => p3 cited by 3 (the most)
    #    p3's claim is stated in its body; its dependents are p1,p2,p4.
    pap = _fresh_dir(ws / "papers")
    (pap / "paper-1.txt").write_text(
        "Title: Caching strategies.\nClaim: LRU beats FIFO under skew.\ncites: 3\n"
    )
    (pap / "paper-2.txt").write_text(
        "Title: Index tuning.\nClaim: Covering indexes cut IO.\ncites: 3\n"
    )
    (pap / "paper-3.txt").write_text(
        "Title: Foundations of locality.\n"
        "Claim: Temporal locality dominates real workloads.\ncites: \n"
    )
    (pap / "paper-4.txt").write_text(
        "Title: Prefetching.\nClaim: Prefetch depth 2 is optimal.\ncites: 3\n"
    )

    # 15 iterative-refine: budget over/under; offsetting cuts that balance to 0.
    #    category,planned,actual
    #    food   100  130  (over by 30)   travel 200 150 (under, slack 50)
    #    office 80   60   (under, slack 20)  rent 500 500 (exact)
    #    total overrun = 30 ; cuts must come from under-budget planned WITHOUT
    #    cutting planned below actual: travel slack=50, office slack=20.
    #    a valid offset: cut travel by 30 (200->170, still >=150). offset balances.
    (ws / "budget.csv").write_text(
        "category,planned,actual\n"
        "food,100,130\n"
        "travel,200,150\n"
        "office,80,60\n"
        "rent,500,500\n"
    )


GROUND_TRUTH: tuple[GroundTruth, ...] = (
    GroundTruth(
        "GEN-L2-multi-file-reconcile-07",
        facts=(
            "paid invoices are inv-1 (100), inv-3 (75), inv-4 (300)",
            "paid subtotal = 475",
            "475 is written to out/paid.txt",
        ),
        notes=("currency symbol optional; the file write must actually happen",),
    ),
    GroundTruth(
        "GEN-L2-cross-ref-lookup-08",
        facts=("north: 4", "south: 2", "west: 1"),
        notes=("sorted by region name; counts are the load-bearing facts",),
    ),
    GroundTruth(
        "GEN-L2-pipeline-transform-09",
        facts=(
            "peak error hour = 09 (three ERRORs)",
            "per-hour table: 08=1, 09=3, 10=1, written to out/errors_by_hour.txt",
        ),
        notes=("hour may be '09' or '09:00'; table file write must happen",),
    ),
    GroundTruth(
        "GEN-L2-multi-source-synthesis-10",
        facts=("q1->q2 growth = 25%", "q2->q3 growth = 20%"),
        notes=("percent vs fraction (0.25) both acceptable if labeled",),
    ),
    GroundTruth(
        "GEN-L2-verify-and-fix-11",
        facts=(
            "config is INVALID: port 70000 is out of range 1..65535",
            "corrected config written to out/config.fixed.json with a valid port",
        ),
        notes=("the corrected port value depends on the prompt's named fallback",),
    ),
    GroundTruth(
        "GEN-L2-dependency-resolve-12",
        facts=(
            "valid topological install order with D before B and C, and B,C before A",
            "e.g. D, B, C, A (or D, C, B, A)",
            "no cycle exists",
        ),
        notes=(
            "any order respecting deps-first is correct; B/C order interchangeable",
        ),
    ),
    GroundTruth(
        "GEN-L3-constraint-solve-13",
        facts=(
            "earliest slot covering >=4 people = 09:00",
            "attendees at 09:00 = p1, p2, p3, p4 (p5 absent)",
        ),
        notes=("11:00 also covers 4 but 09:00 is earlier and thus required",),
    ),
    GroundTruth(
        "GEN-L3-multi-hop-synthesis-14",
        facts=(
            "most-cited paper = paper-3 (cited by 3)",
            "paper-3's claim: temporal locality dominates real workloads",
            "its dependents (citers) are paper-1, paper-2, paper-4",
        ),
        notes=("claim wording may paraphrase; the paper id + citers are load-bearing",),
    ),
    GroundTruth(
        "GEN-L3-iterative-refine-15",
        facts=(
            "only food is over budget, by 30 (total overrun = 30)",
            "cuts come from under-budget categories without going below actual "
            "(travel slack 50, office slack 20)",
            "the proposed cuts sum to 30 and the offset balances to zero",
        ),
        notes=(
            "many valid cut sets (e.g. travel -30, or travel -20 + office -10); "
            "correctness = overrun identified AND cuts total 30 AND no category "
            "cut below its actual",
        ),
    ),
)

GROUND_TRUTH_BY_CASE: dict[str, GroundTruth] = {g.case: g for g in GROUND_TRUTH}


def seed_l2l3_workspace(workspace: Path | None = None) -> Path:
    """Write all GEN-L2/L3 fixtures under ``workspace`` (default <repo>/workspace).

    Returns the workspace path. Idempotent (overwrites)."""
    ws = workspace or DEFAULT_WORKSPACE
    ws.mkdir(parents=True, exist_ok=True)
    _seed(ws)
    return ws


if __name__ == "__main__":
    import sys

    ws = seed_l2l3_workspace(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"seeded {len(GROUND_TRUTH)} GEN-L2/L3 fixtures under {ws}")
    for g in GROUND_TRUTH:
        print(f"  {g.case}")
        for fact in g.facts:
            print(f"     - {fact}")
