"""L1-purity tests for the count/arithmetic/value verifier shapes.

These extend the topological-sort verifier to the other checkable L2/L3 answer
shapes. Every shape RECOMPUTES the expected answer from the source data carried
in ``evidence`` (reference-free — never from an answer key), checks the final
answer asserts it, and ABSTAINS (``None``) on any parse doubt so it can never
emit a false fail.

Discipline (same as the topo fix):
  - Failure path first (TAP-6): the WRONG-value rejection and the ABSTAIN case
    precede the acceptance case for each shape.
  - Behaviour over implementation (TAP-1): assertions use known source data and
    known correct/incorrect answers; they do not reimplement the aggregation and
    compare.
  - Real-world format: acceptance vectors are copied from the ACTUAL stored arm
    answers (markdown tables, ``$`` symbols, bulleted lists) — the format that
    burned the topo verifier when only synthetic fixtures were used.
"""

from __future__ import annotations

import pytest

from components.answer_verifiers import verify_answer

# ── source data (identical bytes to the seeded fixtures) ────────────

INVOICE_EV = [
    {"tool_name": "file_io", "tool_output": "amount: 100\nstatus: paid\n"},
    {"tool_name": "file_io", "tool_output": "amount: 250\nstatus: unpaid\n"},
    {"tool_name": "file_io", "tool_output": "amount: 75\nstatus: paid\n"},
    {"tool_name": "file_io", "tool_output": "amount: 300\nstatus: paid\n"},
    {"tool_name": "file_io", "tool_output": "amount: 40\nstatus: unpaid\n"},
]
INVOICE_TASK = (
    "Sum the amounts of only the invoices whose status is 'paid', then write that "
    "subtotal to /workspace/out/paid.txt and report it."
)

REGION_EV = [
    {"tool_name": "file_io", "tool_output": "order_id,customer_id\no1,c1\no2,c2\no3,c1\no4,c3\no5,c4\no6,c2\no7,c1\n"},
    {"tool_name": "file_io", "tool_output": "customer_id,region\nc1,north\nc2,south\nc3,north\nc4,west\n"},
]
REGION_TASK = (
    "For each order, resolve its customer's region, then report how many orders "
    "fall in each region as a sorted list 'region: count'."
)

EVENTS_EV = [
    {"tool_name": "file_io", "tool_output":
        "08:01:10 INFO start\n08:15:00 ERROR disk full\n09:02:11 ERROR timeout\n"
        "09:05:42 WARN retry\n09:10:00 ERROR timeout\n09:59:59 ERROR timeout\n"
        "10:00:01 INFO ok\n10:30:00 ERROR oom\n"},
]
EVENTS_TASK = (
    "Keep only the lines containing 'ERROR', extract the timestamp at the start "
    "of each, count errors per hour, and report the single hour with the most errors."
)

REPORTS_EV = [
    {"tool_name": "file_io", "tool_output": "Quarter 1 summary.\nTOTAL: 200\n"},
    {"tool_name": "file_io", "tool_output": "Quarter 2 summary.\nTOTAL: 250\n"},
    {"tool_name": "file_io", "tool_output": "Quarter 3 summary.\nTOTAL: 300\n"},
]
REPORTS_TASK = (
    "Read all three, compute the quarter-over-quarter growth rate between "
    "consecutive quarters, and report both growth rates (q1->q2 and q2->q3) as "
    "percentages to one decimal place."
)

SCHEDULE_EV = [
    {"tool_name": "file_io", "tool_output": "09:00\n10:00\n11:00\n"},  # p1
    {"tool_name": "file_io", "tool_output": "09:00\n11:00\n"},          # p2
    {"tool_name": "file_io", "tool_output": "09:00\n10:00\n"},          # p3
    {"tool_name": "file_io", "tool_output": "09:00\n11:00\n"},          # p4
    {"tool_name": "file_io", "tool_output": "10:00\n11:00\n"},          # p5
]
SCHEDULE_TASK = (
    "Find a single 30-minute slot that works for at least four of the five "
    "people, preferring the earliest such slot, and report it."
)


# ── sum-filtered WITH a file-write side effect → abstain ────────────
# The invoice task bundles "write that subtotal to /workspace/out/paid.txt".
# A correct number with a wrong/absent write is only PARTIAL (two real arms
# computed 475 but wrote to the wrong path; the humans graded those partial).
# The verifier cannot confirm the write target from the final answer, so the
# SAFE behaviour is to abstain on the whole task and let the LLM judge weigh
# the side effect. This rule is the AWAY-from-gold regression the seed proof
# caught (31d6599c, d8dc1071) — value-only validation would over-pass them.


class TestSideEffectTaskAbstains:
    def test_paid_subtotal_with_write_abstains_even_when_correct(self):
        answer = "FINAL ANSWER: The subtotal of all paid invoices is **$475**."
        assert verify_answer(INVOICE_TASK, answer, INVOICE_EV) is None

    def test_paid_subtotal_with_write_abstains_when_wrong(self):
        # Even a wrong number defers — the LLM judge owns side-effect tasks wholesale.
        assert verify_answer(INVOICE_TASK, "The subtotal is 425.", INVOICE_EV) is None


# ── count-by-group (region counts → north 4 / south 2 / west 1) ─────


class TestCountByGroup:
    def test_wrong_count_rejected(self):
        answer = "north: 3\nsouth: 2\nwest: 1"  # north is wrong (should be 4)
        assert verify_answer(REGION_TASK, answer, REGION_EV) is False

    def test_missing_group_abstains(self):
        answer = "north: 4\nsouth: 2"  # west not reported → can't confirm full answer
        assert verify_answer(REGION_TASK, answer, REGION_EV) is None

    def test_correct_table_real_format(self):
        # opus real format: a markdown table.
        answer = (
            "**Order counts by region:**\n\n| Region | Orders |\n|--------|--------|\n"
            "| north  | 4 |\n| south  | 2 |\n| west   | 1 |\n"
        )
        assert verify_answer(REGION_TASK, answer, REGION_EV) is True

    def test_correct_colon_list(self):
        assert verify_answer(REGION_TASK, "north: 4, south: 2, west: 1", REGION_EV) is True


# ── peak-bucket: the events task also bundles a file write ──────────
# "Write the full per-hour table to /workspace/out/errors_by_hour.txt as well."
# Same side-effect rule → abstain wholesale.


class TestPeakBucketSideEffectAbstains:
    EVENTS_TASK_FULL = EVENTS_TASK + (
        " Write the full per-hour table to /workspace/out/errors_by_hour.txt as well."
    )

    def test_peak_hour_with_write_abstains(self):
        assert verify_answer(self.EVENTS_TASK_FULL, "The hour with the most errors is 09.", EVENTS_EV) is None

    def test_peak_hour_no_write_requirement_validates(self):
        # Without the write clause the pure value check applies.
        assert verify_answer(EVENTS_TASK, "The hour with the most errors is 09.", EVENTS_EV) is True
        assert verify_answer(EVENTS_TASK, "The peak error hour is 10.", EVENTS_EV) is False


# ── growth-rate (q-o-q → 25.0%, 20.0%) ──────────────────────────────


class TestGrowthRate:
    def test_wrong_rate_rejected(self):
        # 30.0% is wrong for q1->q2.
        answer = "Q1->Q2: 30.0%\nQ2->Q3: 20.0%"
        assert verify_answer(REPORTS_TASK, answer, REPORTS_EV) is False

    def test_only_one_rate_abstains(self):
        assert verify_answer(REPORTS_TASK, "Growth was 25.0%.", REPORTS_EV) is None

    def test_correct_rates_real_format(self):
        answer = "- **Q1 -> Q2:** 25.0%\n- **Q2 -> Q3:** 20.0%"
        assert verify_answer(REPORTS_TASK, answer, REPORTS_EV) is True


# ── earliest-covering-slot (→ 09:00) ────────────────────────────────


class TestEarliestSlot:
    def test_wrong_slot_rejected(self):
        # 11:00 also covers 4 but is NOT the earliest — wrong answer.
        assert verify_answer(SCHEDULE_TASK, "The best slot is 11:00.", SCHEDULE_EV) is False

    def test_no_slot_abstains(self):
        assert verify_answer(SCHEDULE_TASK, "I found a good slot.", SCHEDULE_EV) is None

    def test_correct_slot_0900(self):
        answer = "09:00 works for 4 of 5 (p1, p2, p3, p4); p5 cannot attend."
        assert verify_answer(SCHEDULE_TASK, answer, SCHEDULE_EV) is True


# ── non-checkable shapes still abstain ──────────────────────────────


class TestStillAbstains:
    def test_budget_offset_abstains(self):
        # multi-part (overrun + cuts total + no cut below actual) — too compound
        # to validate from messy prose; left to the LLM judge.
        task = (
            "Identify every category over budget, compute the total overrun, then "
            "propose a set of cuts that fully offsets it, and verify the offset "
            "balances to zero."
        )
        ev = [{"tool_name": "file_io", "tool_output":
               "category,planned,actual\nfood,100,130\ntravel,200,150\noffice,80,60\nrent,500,500\n"}]
        assert verify_answer(task, "Food is over by 30; cut travel by 30.", ev) is None
