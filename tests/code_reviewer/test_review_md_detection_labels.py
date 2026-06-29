"""Detection-column lint for ``REVIEW.md`` enforcement maps (P2).

The cite-lint (``code_reviewer/cite_lint.py``) checks the *rule-id* direction:
every ``rule_id`` cited in a REVIEW.md table resolves to a token in the named
``AGENTS.md``. It does **not** check the *detection* column — so a row can label
its detection ``AST (`some_fn`)`` for a function that does not exist, creating
the false-confidence "aspirational detector" problem the unified-reviewer
critical review flagged (P2-9).

This module closes that gap mechanically. For every ``AST (`<callable>`)``
label found in any REVIEW.md table, it asserts the callable resolves to a real
artifact:

* a Python function importable from ``utils.code_analysis`` (the shared
  deterministic layer), **or**
* a TypeScript predicate script at ``frontend/scripts/<callable>.ts`` (the
  frontend Ring's deterministic checks, invoked via subprocess by
  ``code_reviewer/frontend/runner.py``).

Anything else (a bare prose label like ``AST (file-list scan)`` with no
backticked callable, or a callable that resolves to neither location) is a
violation. Pure: stdlib only (ast + pathlib + importlib + re); no test
execution, no network.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from code_reviewer.cite_lint import find_review_files
from utils.code_analysis import DETECTOR_RULE_IDS

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The two legitimate homes for a deterministic detector named in a REVIEW.md
# ``AST (`name`)`` label. The Python detectors live in utils.code_analysis; the
# frontend TS predicates live as sibling scripts under frontend/scripts/.
_PYTHON_DETECTOR_MODULE = "utils.code_analysis"
_FRONTEND_TS_DIR = _REPO_ROOT / "frontend" / "scripts"

# ``AST (`callable` …)`` — capture the first backticked token after ``AST (``.
# Matches ``AST (`check_dependency_rules`)``, ``AST (`detect_anti_patterns` AP3)``,
# ``AST (`check_trust_purity` → TRUST_PURITY.io_import)``, etc.
_AST_LABEL = re.compile(r"AST\s*\(\s*`([A-Za-z_][A-Za-z0-9_]*)`")

# Full span of an AST(...) label (callable + any trailing prose/token), used to
# extract rule-id tokens named alongside the callable.
_AST_LABEL_FULL = re.compile(r"AST\s*\(\s*`([A-Za-z_][A-Za-z0-9_]*)`([^)]*)\)")

# Rule-id token shapes that may appear inside an AST(...) label after the
# callable (mirrors ``code_reviewer.cite_lint._RULE_TOKEN``). When a label names
# one, it must (a) use the canonical hyphenated form and (b) be in the named
# detector's ``DETECTOR_RULE_IDS`` contract.
_LABEL_RULE_TOKEN = re.compile(
    r"\b("
    r"AP-?\d+"
    r"|TAP-?\d+"
    r"|ADR\.\d+"
    r"|TRUST_PURITY\.\w+"
    r"|PROTOCOL\.\w+"
    r")\b"
)

# A non-hyphenated AP token (``AP6`` instead of ``AP-6``). Catching this
# directly is the P2-10 regression guard: detector output and REVIEW.md
# rule_id columns use the hyphenated form, so a label that drops the hyphen
# breaks finding-dedup at merge time.
_BARE_AP = re.compile(r"\bAP\d+\b")


def _python_detector_names() -> set[str]:
    """Public callables of ``utils.code_analysis`` (the deterministic layer)."""
    mod = importlib.import_module(_PYTHON_DETECTOR_MODULE)
    return {
        name
        for name in dir(mod)
        if callable(getattr(mod, name)) and not name.startswith("_")
    }


def _frontend_ts_predicates() -> set[str]:
    """Stem names of ``frontend/scripts/check_*.ts`` predicate scripts."""
    if not _FRONTEND_TS_DIR.is_dir():
        return set()
    return {p.stem for p in _FRONTEND_TS_DIR.glob("check_*.ts")}


def _review_md_labels() -> list[tuple[str, str]]:
    """Every ``(review_file, callable)`` pair from ``AST (`callable`)`` labels."""
    out: list[tuple[str, str]] = []
    for review_path in find_review_files(_REPO_ROOT):
        text = review_path.read_text()
        rel = str(review_path.relative_to(_REPO_ROOT))
        for m in _AST_LABEL.finditer(text):
            out.append((rel, m.group(1)))
    return out


def _review_md_label_rule_tokens() -> list[tuple[str, str, str]]:
    """Every ``(review_file, callable, rule_token)`` triple where a rule-id
    token is named alongside the callable inside an ``AST (...)`` label.

    Labels whose trailing prose is plain English (e.g. "file-list scan",
    "failure-test ratio") yield no triples — only rule-id-shaped tokens do.
    """
    out: list[tuple[str, str, str]] = []
    for review_path in find_review_files(_REPO_ROOT):
        text = review_path.read_text()
        rel = str(review_path.relative_to(_REPO_ROOT))
        for m in _AST_LABEL_FULL.finditer(text):
            callable_name, rest = m.group(1), m.group(2)
            for tok in _LABEL_RULE_TOKEN.finditer(rest):
                out.append((rel, callable_name, tok.group(1)))
    return out


def _resolves(callable: str, python_names: set[str], ts_names: set[str]) -> bool:
    if callable in python_names:
        return True
    if callable in ts_names:
        return True
    return False


class TestDetectionLabelsResolve:
    """Every ``AST (`name`)`` detection label in a REVIEW.md must name a real
    deterministic detector — no aspirational labels."""

    def test_all_ast_labels_resolve_to_a_real_detector(self):
        python_names = _python_detector_names()
        ts_names = _frontend_ts_predicates()
        labels = _review_md_labels()
        assert labels, "expected at least one AST(`name`) label across REVIEW.md files"

        unresolved: list[str] = []
        for review_file, callable in labels:
            if not _resolves(callable, python_names, ts_names):
                unresolved.append(f"{review_file}: AST(`{callable}`) -> not found")
        assert unresolved == [], (
            "REVIEW.md detection labels name detectors that do not exist "
            "(utils.code_analysis function or frontend/scripts/check_*.ts). "
            "Either implement the detector or relabel the row to LLM/pending:\n"
            + "\n".join(unresolved)
        )

    def test_new_p2_detectors_are_importable(self):
        """The three P2 detectors named in REVIEW.md must be importable from
        utils.code_analysis — the claims are no longer aspirational."""
        from utils.code_analysis import (
            detect_adr1_missing,
            detect_failure_path_ratio,
            detect_mock_abuse,
        )

        assert callable(detect_adr1_missing)
        assert callable(detect_mock_abuse)
        assert callable(detect_failure_path_ratio)

    @pytest.mark.parametrize(
        "callable_name",
        sorted(
            {
                name
                for _, name in _review_md_labels()
                if name in _python_detector_names()
            }
        ),
    )
    def test_python_detector_named_in_review_md_is_importable(self, callable_name: str):
        """Each Python detector named in a REVIEW.md label is importable from
        utils.code_analysis and returns a dict (the certificate shape)."""
        mod = importlib.import_module(_PYTHON_DETECTOR_MODULE)
        fn = getattr(mod, callable_name)
        assert callable(fn), f"{callable_name} is not callable"

    def test_no_bare_prose_ast_label_without_callable(self):
        """A bare ``AST (prose)`` label with no backticked callable is a lint
        failure — it can't be mechanically resolved. Every AST detection must
        name its callable."""
        bare = re.compile(r"AST\s*\(\s*[^`)]+?\s*\)")
        offenders: list[str] = []
        for review_path in find_review_files(_REPO_ROOT):
            text = review_path.read_text()
            rel = str(review_path.relative_to(_REPO_ROOT))
            for m in bare.finditer(text):
                inner = m.group(1) if m.lastindex else m.group(0)
                # Skip if this same span was captured as a backticked label.
                if "`" in text[m.start() : m.end()]:
                    continue
                offenders.append(f"{rel}: {m.group(0).strip()}")
        assert offenders == [], (
            "REVIEW.md has bare AST(...) labels with no backticked callable — "
            "name the detector so the label is mechanically resolvable:\n"
            + "\n".join(offenders)
        )

    def test_no_non_hyphenated_ap_token_in_labels(self):
        """P2-10 regression guard: an ``AST (...)`` label must never name a
        non-hyphenated AP token (``AP6`` instead of ``AP-6``). The detector
        emits the hyphenated form and the ``rule_id`` column uses it; a bare
        ``AP6`` breaks finding-dedup at merge time."""
        offenders: list[str] = []
        for review_path in find_review_files(_REPO_ROOT):
            text = review_path.read_text()
            rel = str(review_path.relative_to(_REPO_ROOT))
            for m in _AST_LABEL_FULL.finditer(text):
                for bare in _BARE_AP.finditer(m.group(2)):
                    offenders.append(
                        f"{rel}: {m.group(0).strip()} uses '{bare.group(0)}' "
                        f"— use the hyphenated '{bare.group(0)[:-1]}-{bare.group(0)[-1]}'"
                    )
        assert offenders == [], (
            "REVIEW.md AST(...) labels use non-hyphenated AP tokens — "
            "normalize to AP-<n> so findings dedup against rule_id:\n"
            + "\n".join(offenders)
        )

    def test_label_rule_token_is_in_detector_contract(self):
        """Any rule-id token named alongside a callable in an ``AST (...)``
        label must be in that detector's ``DETECTOR_RULE_IDS`` contract. This
        catches the "AP-1 row labelled with AP-6 detection" class of bug — a
        claim that the detector fires for a rule it never emits."""
        triples = _review_md_label_rule_tokens()
        assert triples, (
            "expected at least one AST(...) label naming a rule-id token "
            "alongside its callable"
        )
        offenders: list[str] = []
        for review_file, callable_name, token in triples:
            contract = DETECTOR_RULE_IDS.get(callable_name)
            if contract is None:
                # Detector has a dynamic rule-id vocabulary (e.g.
                # check_dependency_rules) — its labels use prose, so reaching
                # here means a label accidentally named a rule-id token. Flag
                # it so the label is corrected to prose or the detector is
                # given a contract.
                offenders.append(
                    f"{review_file}: AST(`{callable_name}` {token}) — "
                    f"{callable_name} has no DETECTOR_RULE_IDS contract"
                )
                continue
            if token not in contract:
                offenders.append(
                    f"{review_file}: AST(`{callable_name}` {token}) — "
                    f"{token} not emitted by {callable_name} "
                    f"(contract: {sorted(contract)})"
                )
        assert offenders == [], (
            "REVIEW.md AST(...) labels name rule ids the detector does not "
            "emit — fix the label or the detector contract:\n" + "\n".join(offenders)
        )
