"""Scaffolding + drift helper for the per-folder ``REVIEW.md`` enforcement maps.

The plan (WI-2) locks a two-tier rule model: ``AGENTS.md`` holds the rule
*content* and a thin ``REVIEW.md`` is the *enforcement map* that **cites** rule
IDs — it never restates prose. Hand-authoring the first REVIEW.md for a new
folder is error-prone (forgotten rules) and the cite-don't-copy invariant gives
no mechanical help for the *reverse* direction: an ``AGENTS.md`` that grows a new
rule nobody curates into ``REVIEW.md`` drifts silently. ``cite_lint`` catches
``REVIEW.md`` → ``AGENTS.md`` dangling cites; this module closes the other half.

L1-pure (stdlib only), reuses ``cite_lint._RULE_TOKEN`` so the two tools agree
on what counts as a rule token.

Two operations:

1. **Scaffold** (``scaffold_review_md`` / ``--folder``): for a folder with no
   ``REVIEW.md``, scan its sibling ``AGENTS.md`` (and root ``AGENTS.md``) for
   rule tokens and emit a thin skeleton — one table row per discovered token,
   with ``detection``/``severity``/``dimension`` left as author-curated
   placeholders. Refuses to overwrite an existing map (curation is human
   judgment; we only bootstrap the missing case).
2. **Drift** (``review_md_drift`` / ``--check``): for an existing ``REVIEW.md``,
   report rule tokens present in the sibling ``AGENTS.md`` but not yet cited.
   Informational by default (not every AGENTS.md rule must be enforced — the
   author curates); ``--strict`` opts into a non-zero exit for CI gating.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from code_reviewer.cite_lint import _RULE_TOKEN, parse_cites

# A markdown ATX heading: "# Foo", "## Foo", etc. Used to attach a best-effort
# nearest-heading context to each discovered token.
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# Placeholder values for the author-curated columns of a scaffolded row. The
# skeleton is explicitly a starting point, not a finished map — the footer
# instructs the author to replace these.
_PLACEHOLDER_DETECTION = "LLM"
_PLACEHOLDER_SEVERITY = "warning"
_PLACEHOLDER_DIMENSION = "—"


@dataclass(frozen=True)
class RuleToken:
    """A rule token discovered in an ``AGENTS.md``.

    ``source`` is the repo-relative path of the AGENTS.md it came from (or
    ``"root AGENTS.md"`` for the root file). ``context`` is the nearest preceding
    markdown heading at the point the token appeared — best-effort provenance to
    help the author fill in the ``source`` column of the scaffolded row.
    """

    token: str
    source: str
    context: str


def discover_rule_tokens(
    agents_path: Path,
    *,
    repo_root: Path,
) -> list[RuleToken]:
    """Scan one ``AGENTS.md`` for rule tokens; dedup by token, first-appearance order.

    Uses ``cite_lint._RULE_TOKEN`` so a token counts as a token here iff it
    counts as a token for the lint — the two tools cannot disagree on the
    token set. The root ``AGENTS.md`` numbers invariants as a plain ``N.``
    list rather than spelling out ``Invariant #N``; those are surfaced
    separately by :func:`discover_root_invariants` so callers can decide
    whether to seed them into a scaffold.
    """
    if not agents_path.is_file():
        return []
    text = agents_path.read_text()
    source = _source_label(agents_path, repo_root)

    out: list[RuleToken] = []
    seen: set[str] = set()
    current_heading = ""
    for line in text.splitlines():
        h = _HEADING.match(line)
        if h:
            current_heading = h.group(2).strip()
            continue
        for m in _RULE_TOKEN.finditer(line):
            token = m.group(1)
            if token in seen:
                continue
            seen.add(token)
            out.append(RuleToken(token=token, source=source, context=current_heading))
    return out


def discover_root_invariants(repo_root: Path) -> list[RuleToken]:
    """Surface ``Invariant #N`` tokens from the root ``AGENTS.md`` numbered list.

    The root file numbers invariants as a plain ``N.`` markdown list under an
    "Architecture Invariants" heading instead of spelling out ``Invariant #N``.
    ``_RULE_TOKEN`` therefore does not match them in :func:`discover_rule_tokens`;
    cite_lint special-cases the same pattern for resolution. We mirror that here
    so a scaffolded map can seed the always-on invariants.
    """
    root_agents = repo_root / "AGENTS.md"
    if not root_agents.is_file():
        return []
    text = root_agents.read_text()
    if not re.search(r"^#+\s*Architecture Invariants", text, re.MULTILINE):
        return []
    out: list[RuleToken] = []
    seen: set[str] = set()
    invariants_heading = "Architecture Invariants"
    for m in re.finditer(r"^\s*(\d+)\.\s+\*\*", text, re.MULTILINE):
        n = m.group(1)
        token = f"Invariant #{n}"
        if token in seen:
            continue
        seen.add(token)
        out.append(
            RuleToken(
                token=token,
                source="root AGENTS.md",
                context=invariants_heading,
            )
        )
    return out


def scaffold_review_md(folder: Path, *, repo_root: Path) -> str:
    """Render a thin ``REVIEW.md`` skeleton for ``folder``.

    Seeds the cite table with every rule token found in the folder's own
    ``AGENTS.md`` (if any) plus the root ``AGENTS.md`` invariants. The
    ``detection``/``severity``/``dimension`` columns are placeholders — the
    footer tells the author to curate them. The output is deliberately not
    a finished enforcement map; it is a complete starting set of cites so
    no known rule is forgotten at bootstrap.
    """
    folder_agents = folder / "AGENTS.md"
    folder_name = folder.name or "root"
    rel_agents = _rel(folder_agents, repo_root)
    root_rel = _rel(repo_root / "AGENTS.md", repo_root) or "AGENTS.md"

    tokens = discover_rule_tokens(folder_agents, repo_root=repo_root)
    # Always fold in root invariants — they are the always-on inter-layer
    # rules every folder's map should at least consider.
    root_invariants = discover_root_invariants(repo_root)
    seen = {t.token for t in tokens}
    for t in root_invariants:
        if t.token not in seen:
            tokens.append(t)
            seen.add(t.token)

    agents_link = rel_agents if rel_agents != "AGENTS.md" else root_rel
    header = (
        f"# {folder_name}/ — Reviewer Enforcement Map\n\n"
        f"> **Thin enforcement map, not a rule book.** This file tells the unified\n"
        f"> reviewer (`prompts/codeReviewer/v3/`) *what to flag here and how*. It\n"
        f"> **cites** rule IDs whose content lives in [`{agents_link}`]({agents_link})\n"
        f"> and the root [`AGENTS.md`](../AGENTS.md) — it never restates the rule\n"
        f"> prose. If a cite below does not resolve to a heading/ID in the sibling\n"
        f"> `AGENTS.md`, that is a lint failure (see\n"
        f"> `tests/code_reviewer/test_review_md_cites.py`).\n"
        f">\n"
        f"> Detection column: **AST** = a deterministic validator runs first and\n"
        f"> its finding takes precedence; **LLM** = the reviewer judges it (not\n"
        f"> gate-grade until the judge is validated, WI-8).\n"
        f">\n"
        f"> **Scaffolded by `code_reviewer.review_scaffold`.** Curate the rows:\n"
        f"> drop rules you do not want enforced here, set ``detection`` to\n"
        f"> ``AST (<fn>)`` only when a real deterministic predicate exists, and\n"
        f"> assign ``severity`` / ``reviewer dimension`` per the v3 protocol.\n"
    )

    rows: list[str] = [
        "| rule_id | source | detection | severity | reviewer dimension |",
        "|---|---|---|---|---|",
    ]
    for t in tokens:
        source_col = t.source
        if t.context:
            source_col = f"{t.source} §{t.context}"
        rows.append(
            f"| {t.token} | {source_col} | {_PLACEHOLDER_DETECTION} | "
            f"{_PLACEHOLDER_SEVERITY} | {_PLACEHOLDER_DIMENSION} |"
        )

    return header + "\n" + "\n".join(rows) + "\n"


def review_md_drift(
    review_path: Path,
    *,
    repo_root: Path,
) -> list[RuleToken]:
    """Return rule tokens in the sibling ``AGENTS.md`` not cited in ``REVIEW.md``.

    Drift is informational: the plan's model is that the author *curates* which
    AGENTS.md rules to enforce, so an uncited rule is not a violation — it is a
    prompt to consider whether it should be enforced here. The reverse direction
    (a REVIEW.md cite absent from AGENTS.md) is a hard lint failure and belongs
    to ``cite_lint``, not here.
    """
    folder = review_path.parent
    agents_path = folder / "AGENTS.md"
    if not agents_path.is_file():
        return []
    available = discover_rule_tokens(agents_path, repo_root=repo_root)
    if not available:
        return []

    cited_tokens: set[str] = set()
    for cite in parse_cites(review_path, repo_root=repo_root):
        if cite.token is not None:
            cited_tokens.add(cite.token)
    # Also count root invariants as cited-by-default so they don't appear as
    # drift for every folder — they live in root AGENTS.md, not the sibling.
    for t in discover_root_invariants(repo_root):
        cited_tokens.add(t.token)

    return [t for t in available if t.token not in cited_tokens]


# ── CLI ──────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m code_reviewer.review_scaffold",
        description=(
            "Scaffold a thin REVIEW.md enforcement map for a folder with none, "
            "or report drift (AGENTS.md rule tokens not yet cited) for existing "
            "maps. Cites rule IDs from the folder's AGENTS.md — never restates "
            "prose. Reuses cite_lint's token set so the two tools agree."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repo root (default: cwd). Used to resolve AGENTS.md sources and "
        "to discover REVIEW.md files in --check mode.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Scaffold a REVIEW.md for this folder (repo-relative to --root, or "
        "absolute). Writes only if no REVIEW.md exists there; refuses to overwrite.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Drift mode: for every REVIEW.md under --root, report rule tokens in "
        "the sibling AGENTS.md that are not cited. Informational (exit 0) unless "
        "--strict is given.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="With --check: exit 1 if any drift is reported. Off by default, since "
        "an uncited rule is a curation choice, not a violation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    args = _parse_args(argv)
    repo_root: Path = args.root.resolve()

    if args.folder is not None:
        folder = args.folder
        if not folder.is_absolute():
            folder = repo_root / folder
        folder = folder.resolve()
        review_path = folder / "REVIEW.md"
        if review_path.is_file():
            print(
                f"{_rel(review_path, repo_root)}: already exists — refusing to "
                "overwrite (curation is human judgment; edit it in place)."
            )
            return 1
        if not folder.is_dir():
            print(f"{_rel(folder, repo_root)}: folder not found")
            return 1
        text = scaffold_review_md(folder, repo_root=repo_root)
        review_path.write_text(text)
        print(
            f"scaffolded {_rel(review_path, repo_root)} ({text.count(chr(10))} lines)"
        )
        return 0

    # --check mode
    from code_reviewer.cite_lint import find_review_files

    review_paths = find_review_files(repo_root)
    if not review_paths:
        print(f"no REVIEW.md files found under {repo_root}")
        return 0

    total_drift = 0
    for review_path in review_paths:
        drift = review_md_drift(review_path, repo_root=repo_root)
        rel = _rel(review_path, repo_root)
        if not drift:
            print(f"{rel}: no drift (sibling AGENTS.md rules all cited)")
            continue
        total_drift += len(drift)
        print(f"{rel}: {len(drift)} uncited rule token(s) in sibling AGENTS.md:")
        for t in drift:
            ctx = f" §{t.context}" if t.context else ""
            print(f"  {t.token}  ({t.source}{ctx})")

    if total_drift:
        print(
            f"\n{total_drift} drift token(s) across {len(review_paths)} REVIEW.md file(s)."
        )
        if args.strict:
            return 1
        return 0
    print(f"clean: {len(review_paths)} REVIEW.md file(s), 0 drift.")
    return 0


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _source_label(agents_path: Path, repo_root: Path) -> str:
    """The ``source`` column value for tokens from this AGENTS.md.

    A bare ``AGENTS.md`` at the repo root is labeled ``"root AGENTS.md"`` to
    match the convention the existing REVIEW.md files use (and that
    ``cite_lint.resolve_source`` special-cases).
    """
    try:
        rel = agents_path.relative_to(repo_root)
    except ValueError:
        return str(agents_path)
    s = str(rel)
    if s == "AGENTS.md":
        return "root AGENTS.md"
    return s


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "RuleToken",
    "discover_rule_tokens",
    "discover_root_invariants",
    "scaffold_review_md",
    "review_md_drift",
    "main",
]
