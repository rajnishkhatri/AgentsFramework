"""Cite-resolves lint for the per-folder ``REVIEW.md`` enforcement maps (WI-2).

A ``REVIEW.md`` is a *thin enforcement map* that **cites** rule IDs whose content
lives in an ``AGENTS.md`` — it must never restate the rule prose. This module
checks the cite-don't-copy invariant deterministically (L1-pure, stdlib only):

1. Every ``rule_id`` row in a ``REVIEW.md`` table names a ``source`` file.
2. That source ``AGENTS.md`` exists, and the rule's identifying token resolves to
   text inside it (a heading, a table cell, or inline prose).
3. The cite is **local** — it names the REVIEW.md's own folder's ``AGENTS.md``
   or the root ``AGENTS.md`` (P2-11 cross-folder guard).
4. The REVIEW.md and every cited ``AGENTS.md`` are free of mojibake — the
   encoding corruption that silently turns ``§`` into ``Â§``, ``ยง``, ``?``,
   or U+FFFD (P3 mojibake guard).

A cite that does not resolve (or a file that fails encoding lint) is a lint
failure — the plan §6 gotcha ("a ``REVIEW.md`` citing a rule ID absent from
``AGENTS.md`` is a lint failure").

The matcher is intentionally lenient on *where* the token appears (heading vs.
table vs. prose) but strict on *whether* it appears: the goal is to catch
dangling pointers, not to police `AGENTS.md` formatting.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# A markdown table row: leading "|", cells split on "|".
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")

# The identifying token in a rule_id — the first rule-shaped code we can anchor
# a cite on. Matches the families used across the nested AGENTS.md files.
_RULE_TOKEN = re.compile(
    r"\b("
    r"Invariant\s+#\d+"
    r"|AP-?\d+"
    r"|FE-AP-\d+"
    r"|H\d+"
    r"|V\d+"
    r"|FD\d+"
    r"|F-R\d+"
    r"|TAP-?\d+"
    r"|G\d+"
    r"|HOOK-\d+"
    r"|ADR\.\d+"
    r"|TRUST_PURITY\.\w+"
    r")\b"
)

# Header cells that mark the columns we read. The table must have at least
# a rule_id column and a source column.
_RULE_COL = "rule_id"
_SOURCE_COL = "source"


@dataclass(frozen=True)
class Cite:
    """One cited rule from a REVIEW.md table row."""

    review_file: str
    rule_id: str
    token: str | None
    source: str


@dataclass(frozen=True)
class CiteViolation:
    """A cite that failed to resolve."""

    review_file: str
    rule_id: str
    source: str
    reason: str


def _source_folder(source: str, review_path: Path, *, repo_root: Path) -> str | None:
    """Return the repo-relative folder whose AGENTS.md the cite names.

    ``"meta/AGENTS.md §..."`` -> ``"meta"``; ``"root AGENTS.md"`` -> ``""``
    (the repo root); a bare ``"AGENTS.md"`` -> the REVIEW.md's own folder.
    Returns ``None`` when no AGENTS.md token is present.
    """
    m = re.search(r"([\w./-]*AGENTS\.md)", source)
    if not m:
        return None
    rel = m.group(1)
    if "root" in source.lower() and rel == "AGENTS.md":
        return ""
    if "/" in rel:
        return rel.rsplit("/", 1)[0]
    # Bare "AGENTS.md" — sibling of the REVIEW.md. For the root REVIEW.md
    # this resolves to "." (the repo root), normalized to "".
    try:
        folder = str(review_path.parent.relative_to(repo_root))
    except ValueError:
        return None
    return "" if folder == "." else folder


def parse_cites(review_path: Path, *, repo_root: Path) -> list[Cite]:
    """Extract ``(rule_id, source)`` cites from every REVIEW.md table.

    A REVIEW.md may hold several tables under different section headings
    (e.g. the root map has an "Always-on" table and an "ADR ratchet" table).
    We parse *every* table that has both a ``rule_id`` and a ``source`` header
    column; rows of each table are parsed until a non-table line ends it, then
    we reset and look for the next qualifying header rather than stopping.
    """
    text = review_path.read_text()
    lines = text.splitlines()
    rel_review = _rel(review_path, repo_root)

    header_cols: list[str] | None = None
    rule_idx = source_idx = -1
    cites: list[Cite] = []

    for line in lines:
        m = _TABLE_ROW.match(line)
        if not m:
            # End the current table — reset header state so a later table
            # under a new heading is re-detected from its own header row.
            header_cols = None
            rule_idx = source_idx = -1
            continue
        cells = [c.strip() for c in m.group(1).split("|")]

        if header_cols is None:
            lowered = [c.lower() for c in cells]
            if _RULE_COL in lowered and _SOURCE_COL in lowered:
                header_cols = cells
                rule_idx = lowered.index(_RULE_COL)
                source_idx = lowered.index(_SOURCE_COL)
            continue

        # Skip the markdown separator row (|---|---|).
        if all(set(c) <= {"-", ":"} for c in cells if c):
            continue
        if max(rule_idx, source_idx) >= len(cells):
            continue

        rule_id = cells[rule_idx]
        source = cells[source_idx]
        token_match = _RULE_TOKEN.search(rule_id)
        cites.append(
            Cite(
                review_file=rel_review,
                rule_id=rule_id,
                token=token_match.group(1) if token_match else None,
                source=source,
            )
        )
    return cites


def resolve_source(cite: Cite, review_path: Path, *, repo_root: Path) -> Path | None:
    """Resolve a cite's ``source`` column to an AGENTS.md path on disk.

    The source column reads like ``frontend/AGENTS.md §Key invariants`` or
    ``root AGENTS.md`` or ``trust/AGENTS.md §...``. We extract the ``*AGENTS.md``
    token and resolve it: an explicit ``<folder>/AGENTS.md`` is repo-relative;
    a bare ``AGENTS.md`` (often "root AGENTS.md") resolves against the repo root.
    """
    text = cite.source
    m = re.search(r"([\w./-]*AGENTS\.md)", text)
    if not m:
        return None
    rel = m.group(1)
    if "root" in text.lower() and rel == "AGENTS.md":
        candidate = repo_root / "AGENTS.md"
    elif "/" in rel:
        candidate = repo_root / rel
    else:
        # Bare "AGENTS.md" with no "root" qualifier -> sibling of the REVIEW.md.
        candidate = review_path.parent / rel
    return candidate if candidate.is_file() else None


def lint_review_file(review_path: Path, *, repo_root: Path) -> list[CiteViolation]:
    """Lint one REVIEW.md: every cite resolves to its source AGENTS.md token.

    Two checks run:

    1. **Resolves** — the named ``AGENTS.md`` exists and the rule's token
       appears inside it (the original WI-2 cite-don't-copy invariant).
    2. **Local** — the cite names the REVIEW.md's *own* folder's ``AGENTS.md``
       or the root ``AGENTS.md``. A per-folder map citing another folder's
       ``AGENTS.md`` (e.g. ``meta/REVIEW.md`` citing ``trust/AGENTS.md``)
       breaks locality: the folder's enforcement map should depend only on
       its own rules plus the inter-layer invariants owned by root. Root is
       always citable; every other folder is citable only from itself.
    """
    violations: list[CiteViolation] = []
    rel_review = _rel(review_path, repo_root)
    # Encoding lint on the REVIEW.md itself — mojibake in the map corrupts
    # every downstream check (P3). Reported with a synthetic rule_id so the
    # violation is visible and counted.
    for defect in lint_encoding(review_path):
        violations.append(CiteViolation(rel_review, "<encoding>", "<file>", defect))
    review_text = review_path.read_text()
    for defect in _lost_section_marker_defects(review_text):
        violations.append(CiteViolation(rel_review, "<encoding>", "<file>", defect))
    cites = parse_cites(review_path, repo_root=repo_root)
    try:
        own_folder = str(review_path.parent.relative_to(repo_root))
    except ValueError:
        own_folder = ""
    # The root REVIEW.md lives at the repo root; treat its own folder as "".
    if own_folder == ".":
        own_folder = ""

    for cite in cites:
        source_file = resolve_source(cite, review_path, repo_root=repo_root)
        if source_file is None:
            violations.append(
                CiteViolation(
                    cite.review_file,
                    cite.rule_id,
                    cite.source,
                    "source AGENTS.md not found",
                )
            )
            continue
        # Locality: the cite's source folder must be the REVIEW.md's own
        # folder or the repo root (root owns the inter-layer invariants).
        src_folder = _source_folder(cite.source, review_path, repo_root=repo_root)
        if src_folder is not None and src_folder != own_folder and src_folder != "":
            violations.append(
                CiteViolation(
                    cite.review_file,
                    cite.rule_id,
                    cite.source,
                    f"cross-folder cite: {own_folder or 'root'}/REVIEW.md cites "
                    f"{src_folder}/AGENTS.md — cite {own_folder or 'root'}/AGENTS.md "
                    f"or root AGENTS.md instead",
                )
            )
            continue
        if cite.token is None:
            # No rule-shaped token to anchor on (e.g. a prose-only invariant
            # cite). Require the source file to at least exist, which it does.
            continue
        haystack = source_file.read_text()
        if not _token_resolves(cite.token, haystack):
            violations.append(
                CiteViolation(
                    cite.review_file,
                    cite.rule_id,
                    cite.source,
                    f"token '{cite.token}' not found in {_rel(source_file, repo_root)}",
                )
            )
    return violations


# Matches an "Architecture Invariants" heading (any heading level).
_INVARIANTS_HEADING = re.compile(r"^#+\s*Architecture Invariants", re.MULTILINE)


def _token_resolves(token: str, haystack: str) -> bool:
    """Return True when ``token`` resolves to content in ``haystack``.

    Most tokens resolve by literal substring match. The ``Invariant #N`` family
    is special: the root ``AGENTS.md`` numbers its invariants as a plain ``N.``
    markdown list under an "Architecture Invariants" heading rather than spelling
    out ``Invariant #N``. For that family we resolve by confirming the heading
    exists and an ``N.``-numbered list item is present.
    """
    # Literal match wins first: nested AGENTS.md files often restate an
    # invariant inline as "(Invariant #4)".
    if token in haystack:
        return True
    # Fallback for the root AGENTS.md, which numbers invariants as a plain
    # "N." markdown list under an "Architecture Invariants" heading rather
    # than spelling out "Invariant #N".
    m = re.fullmatch(r"Invariant\s+#(\d+)", token)
    if m and _INVARIANTS_HEADING.search(haystack):
        n = m.group(1)
        return re.search(rf"^\s*{n}\.\s+\*\*", haystack, re.MULTILINE) is not None
    return False


# ── Mojibake / encoding guard (P3) ─────────────────────────────────────
#
# A REVIEW.md or AGENTS.md that has been round-tripped through the wrong
# codec silently corrupts the section markers the cite-lint depends on:
# ``§`` (U+00A7) becomes ``Â§`` (Latin-1 of UTF-8), ``ยง`` (Thai misdecode),
# ``?`` (lossy ASCII placeholder), or U+FFFD (replacement char). The cite
# resolver then can't find the section, the rule_id column reads ``?AP-4``
# instead of ``§AP-4``, and the map drifts from reality.
#
# This detector catches the high-confidence signals:
#   1. bytes that don't decode as UTF-8 (raw bad bytes),
#   2. U+FFFD replacement chars in the decoded text,
#   3. Latin-1-of-UTF-8 bigrams (``Â``/``Ã``/``â€`` followed by non-ASCII),
#   4. a ``?`` immediately after ``AGENTS.md `` in a table source cell —
#      the lossy-ASCII placeholder for ``§`` (narrow, low false-positive).

# Latin-1-of-UTF-8 mojibake: a C0/C1-area lead byte mis-decoded as a letter.
# ``Â`` (U+00C2) and ``Ã`` (U+00C3) are the two most common leads; either
# followed by a non-ASCII char is almost always mojibake. The ``â€`` prefix
# covers the em-dash/smart-quote family (``â€"`` for ``—``, ``â€"`` for ``"``).
_MOJIBAKE_LEAD = re.compile(r"[\xc2\xc3]|â€|ï¿|ï½")

# Replacement char U+FFFD — always a defect.
_REPLACEMENT_CHAR = "\ufffd"


def detect_mojibake(text: str) -> list[str]:
    """Return a list of mojibake defect descriptions found in ``text``.

    Pure: operates on already-decoded text. Catches U+FFFD and the
    Latin-1-of-UTF-8 bigram family. Use :func:`lint_encoding` to also catch
    raw invalid-UTF-8 bytes (which never reach this function).
    """
    defects: list[str] = []
    if _REPLACEMENT_CHAR in text:
        n = text.count(_REPLACEMENT_CHAR)
        defects.append(f"U+FFFD replacement char x{n}")
    # Scan for the lead-char + non-ASCII bigrams. We walk the regex matches
    # and confirm the following char is non-ASCII to avoid flagging a lone
    # legit ``Â`` (rare in English prose but possible in names).
    for m in _MOJIBAKE_LEAD.finditer(text):
        end = m.end()
        lead = m.group(0)
        # For the single-char leads (Â/Ã), require a following non-ASCII char.
        if lead in ("\xc2", "\xc3"):
            if end < len(text) and ord(text[end]) > 0x7F:
                defects.append(
                    f"mojibake bigram '{lead}{text[end]}' "
                    f"(Latin-1 of UTF-8) at offset {m.start()}"
                )
        else:
            defects.append(f"mojibake fragment '{lead}' at offset {m.start()}")
    return defects


def lint_encoding(path: Path) -> list[str]:
    """Encoding lint for one file: invalid UTF-8 + mojibake in decoded text.

    Returns a list of human-readable defect strings (empty = clean).
    """
    raw = path.read_bytes()
    defects: list[str] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        defects.append(f"invalid UTF-8 byte(s) at offset {exc.start} ({exc.reason})")
        # Decode with replacement so we can still scan the rest for U+FFFD/bigrams.
        text = raw.decode("utf-8", errors="replace")
    defects.extend(detect_mojibake(text))
    return defects


# A table source cell like ``services/AGENTS.md ?Anti-patterns`` — the ``?``
# is the lossy-ASCII placeholder for ``§``. Narrow: only flags ``?`` that
# immediately follows an ``AGENTS.md `` token inside a markdown table row.
_LOST_SECTION_MARKER = re.compile(r"AGENTS\.md\s+\?(\w)")


def _lost_section_marker_defects(text: str) -> list[str]:
    """Flag ``AGENTS.md ?<word>`` in table rows — a lost ``§`` placeholder."""
    defects: list[str] = []
    for line in text.splitlines():
        if not _TABLE_ROW.match(line):
            continue
        for m in _LOST_SECTION_MARKER.finditer(line):
            defects.append(
                f"lost section marker: 'AGENTS.md ?{m.group(1)}' "
                f"— '?' is a placeholder for '§' (re-encode as UTF-8)"
            )
    return defects


def find_review_files(repo_root: Path) -> list[Path]:
    """Find every REVIEW.md under the repo (excluding vendored / hidden trees).

    Hidden dirs are tool state, not repo docs — ``.claude/worktrees/`` in
    particular holds duplicate agent-session checkouts of this repo.
    """
    out: list[Path] = []
    for path in repo_root.rglob("REVIEW.md"):
        rel_parts = path.relative_to(repo_root).parts
        if set(rel_parts) & {"node_modules", ".venv", "__pycache__"} or any(
            p.startswith(".") for p in rel_parts[:-1]
        ):
            continue
        out.append(path)
    return sorted(out)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


# ── CLI ──────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m code_reviewer.cite_lint",
        description=(
            "Lint REVIEW.md enforcement maps: every rule_id cited in a REVIEW.md "
            "table must resolve to a real token in the AGENTS.md named by its "
            "source column. Exits 0 when clean, 1 on any dangling cite."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=(
            "Repo root used to resolve AGENTS.md sources and to discover "
            "REVIEW.md files when --files is omitted (default: cwd)."
        ),
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        metavar="REVIEW.md",
        help=(
            "Explicit REVIEW.md paths to lint (repo-relative to --root, or "
            "absolute). When omitted, every REVIEW.md under --root is linted."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code (0 clean, 1 violations)."""
    args = _parse_args(argv)
    repo_root: Path = args.root.resolve()

    if args.files:
        review_paths: list[Path] = []
        for f in args.files:
            p = Path(f)
            review_paths.append(p if p.is_absolute() else repo_root / f)
    else:
        review_paths = find_review_files(repo_root)

    if not review_paths:
        print(f"no REVIEW.md files found under {repo_root}")
        return 0

    total_violations = 0
    for review_path in review_paths:
        if not review_path.is_file():
            rel = _rel(review_path, repo_root)
            print(f"{rel}: file not found")
            total_violations += 1
            continue
        for v in lint_review_file(review_path, repo_root=repo_root):
            print(f"{v.review_file}: {v.rule_id} -> {v.source} ({v.reason})")
            total_violations += 1

    # Encoding lint on every AGENTS.md under root (the cite source of truth).
    # Mojibake in an AGENTS.md is worse than in a REVIEW.md: it corrupts the
    # rule definitions every REVIEW.md depends on. Scanned in the same CLI
    # pass so `make check` catches both in one shot (P3).
    agents_violations = _lint_all_agents_encoding(repo_root)
    for rel, defect in agents_violations:
        print(f"{rel}: <encoding> -> <file> ({defect})")
        total_violations += 1

    reviewed = len(review_paths)
    if total_violations:
        print(
            f"\n{total_violations} cite violation(s) across {reviewed} "
            f"REVIEW.md file(s)."
        )
        return 1
    print(f"clean: {reviewed} REVIEW.md file(s), 0 cite violations.")
    return 0


def _lint_all_agents_encoding(repo_root: Path) -> list[tuple[str, str]]:
    """Scan every AGENTS.md under root for mojibake. Returns ``(rel, defect)``."""
    out: list[tuple[str, str]] = []
    for path in repo_root.rglob("AGENTS.md"):
        rel_parts = path.relative_to(repo_root).parts
        if set(rel_parts) & {"node_modules", ".venv", "__pycache__"} or any(
            p.startswith(".") for p in rel_parts[:-1]
        ):
            continue
        for defect in lint_encoding(path):
            out.append((_rel(path, repo_root), defect))
    return sorted(out)


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "Cite",
    "CiteViolation",
    "parse_cites",
    "resolve_source",
    "lint_review_file",
    "find_review_files",
    "detect_mojibake",
    "lint_encoding",
    "main",
]
