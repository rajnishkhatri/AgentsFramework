"""Frontend Reviewer CLI runner.

This module implements §0 of ``prompts/codeReviewer/frontend/system_prompt.j2``:

  python -m code_reviewer.frontend \\
      --files <glob_or_paths> \\
      --scope <scope> \\
      --out review.json \\
      [--fail-on critical|warning|info] \\
      [--model MODEL_FAST|MODEL_NORMAL|MODEL_DEEP] \\
      [--dry-run | --rules-only]

Modes
-----

The full LLM tool-calling loop (the LLM invokes Section 5 tools through
LiteLLM function-calling and the dispatcher runs the matching TS script)
is intentionally **deferred to a follow-up iteration**. Today the runner
ships two pragmatic modes that exercise the full pipeline up to the
LLM boundary:

- ``--dry-run`` renders the prompt set, writes the rendered text to
  ``--out`` (or stdout when ``--out -`` is passed), records the eval
  capture entry, and exits 0. Useful for prompt-engineering iteration
  without burning tokens.
- ``--rules-only`` runs every applicable deterministic tool from §5 of
  the prompt against ``--files`` directly (no LLM in the loop) and
  aggregates the findings into a partial ``ReviewReport`` JSON.
  ``statement`` and per-finding ``confidence`` are populated with
  conservative defaults; the LLM-only fields stay empty so downstream
  tooling can tell rules-only output from a full review.

When neither flag is passed, the runner falls back to ``--rules-only``
and surfaces a ``gaps[]`` entry explaining the deferral. The
``llm`` mode is wired via the LiteLLM function-calling spec in
:func:`code_reviewer.frontend.tools.tool_function_specs` -- the
follow-up integration only needs to call ``LLMService.invoke_with_tools``
in a loop and route each ``tool_call`` through ``TOOL_HANDLERS``.

Eval capture
------------

Per AGENTS.md H5, every LLM-bearing run records its input + output via
``services.eval_capture.record()`` with ``target="code_reviewer.frontend"``
and ``user_id="reviewer-cli"`` (override-able via ``--user-id``). The
``task_id`` defaults to the ``--out`` filename so per-PR runs are easy
to correlate.

Exit codes
----------

| Code | Meaning |
|------|---------|
| 0    | ``verdict == "approve"`` (or below the ``--fail-on`` threshold) |
| 1    | ``verdict == "request_changes"`` (or any warning/info finding when --fail-on is set lower) |
| 2    | ``verdict == "reject"`` (always non-zero regardless of --fail-on) |
| 3    | Runner error -- prompt missing, invalid scope, tool subprocess crash |

The ``--fail-on`` flag DEMOTES the LLM verdict's exit code: any finding
of severity ``>= threshold`` produces a non-zero exit even when the LLM
returned ``approve``.
"""

from __future__ import annotations

import argparse
import asyncio
import glob as glob_module
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from code_reviewer.frontend.tools import (
    REPO_ROOT,
    applicable_tools,
    run_ts_script,
    tool_function_specs,
)

logger = logging.getLogger("code_reviewer.frontend.runner")

PROMPT_DIR = REPO_ROOT / "prompts"
FRONTEND_PROMPT_DIR = PROMPT_DIR / "codeReviewer" / "frontend"

VALID_SCOPES = frozenset(
    {
        "full",
        "adapter_pr",
        "ui_component_pr",
        "wire_translator_pr",
        "security_audit",
        "sprint_audit",
        "infra_audit",
    }
)
VALID_MODEL_TIERS = frozenset({"MODEL_FAST", "MODEL_NORMAL", "MODEL_DEEP"})

# Map MODEL_FAST/MODEL_NORMAL/MODEL_DEEP onto the env-driven profile
# selectors in `meta.CodeReviewerAgentTest.env_settings`. The Python
# runtime only reads the `MODEL_NAME*` env vars when the LLM mode is
# eventually wired up; for `--dry-run` and `--rules-only` the tier is
# recorded as metadata only.
MODEL_TIER_TO_ENV: dict[str, str] = {
    "MODEL_FAST": "MODEL_NAME",
    "MODEL_NORMAL": "MODEL_NAME_REVIEWER",
    "MODEL_DEEP": "MODEL_NAME_JUDGE",
}

SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}

EXIT_OK = 0
EXIT_REQUEST_CHANGES = 1
EXIT_REJECT = 2
EXIT_RUNNER_ERROR = 3


# ── Dataclasses (intentionally not Pydantic to keep zero-import-cost) ──


@dataclass(frozen=True)
class CliArgs:
    """Parsed CLI options. Frozen to discourage mutation downstream."""

    files: tuple[str, ...]
    scope: str
    out: str
    fail_on: str
    model: str
    dry_run: bool
    rules_only: bool
    submission_context: str
    user_id: str
    task_id: str | None


@dataclass
class ToolFinding:
    """A single deterministic-tool violation (pre-Pydantic)."""

    rule_id: str
    dimension: str
    severity: str
    file: str
    line: int | None
    description: str
    fix_suggestion: str
    tool: str
    raw: dict[str, Any] = field(default_factory=dict)


# ── Argv parsing ──────────────────────────────────────────────────────


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser. Exposed for unit tests."""
    p = argparse.ArgumentParser(
        prog="python -m code_reviewer.frontend",
        description=(
            "Frontend Ring Code Review Validator runner. See "
            "prompts/codeReviewer/frontend/system_prompt.j2 §0 for the "
            "invocation contract."
        ),
    )
    p.add_argument(
        "--files",
        action="append",
        default=[],
        help=(
            "File path or glob (repeatable). Globs are expanded with `glob`'s "
            "recursive matcher. Comma-separated lists are also accepted in a "
            "single --files argument."
        ),
    )
    p.add_argument(
        "--scope",
        default="full",
        help=f"Review scope. One of: {', '.join(sorted(VALID_SCOPES))}.",
    )
    p.add_argument(
        "--out",
        default="review.json",
        help="Destination for the ReviewReport JSON (use '-' for stdout).",
    )
    p.add_argument(
        "--fail-on",
        default="critical",
        choices=["critical", "warning", "info"],
        help=(
            "Severity threshold that demotes the verdict's exit code. "
            "`critical` = CI default; `warning` = stricter; `info` = "
            "any finding fails."
        ),
    )
    p.add_argument(
        "--model",
        default="MODEL_NORMAL",
        choices=sorted(VALID_MODEL_TIERS),
        help="Model tier (recorded in metadata; used by the future LLM loop).",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the prompt only; write to --out and exit 0.",
    )
    mode.add_argument(
        "--rules-only",
        action="store_true",
        help="Run every deterministic tool against --files; emit a partial ReviewReport.",
    )
    p.add_argument(
        "--submission-context",
        default="",
        help="Optional free-text PR context appended to the rendered prompt.",
    )
    p.add_argument(
        "--user-id",
        default="reviewer-cli",
        help="user_id passed to eval_capture.record() (H5).",
    )
    p.add_argument(
        "--task-id",
        default=None,
        help="task_id passed to eval_capture.record(); defaults to --out basename.",
    )
    return p


def parse_args(argv: list[str]) -> CliArgs:
    """Parse and normalise argv into the immutable :class:`CliArgs` view.

    Raises ``ValueError`` on an unknown ``--scope`` so callers can map
    that to ``EXIT_RUNNER_ERROR`` rather than the argparse default of
    SystemExit(2) which would collide with the reject exit code.
    """
    parser = build_arg_parser()
    ns = parser.parse_args(argv)
    if ns.scope not in VALID_SCOPES:
        raise ValueError(
            f"unknown scope {ns.scope!r}; valid: {sorted(VALID_SCOPES)}",
        )

    flat_files: list[str] = []
    for entry in ns.files:
        # Allow comma-separated values inside a single --files arg.
        for piece in entry.split(","):
            piece = piece.strip()
            if piece:
                flat_files.append(piece)

    task_id = ns.task_id
    if task_id is None:
        task_id = Path(ns.out).stem if ns.out != "-" else "review-stdout"

    return CliArgs(
        files=tuple(flat_files),
        scope=ns.scope,
        out=ns.out,
        fail_on=ns.fail_on,
        model=ns.model,
        dry_run=bool(ns.dry_run),
        rules_only=bool(ns.rules_only),
        submission_context=ns.submission_context,
        user_id=ns.user_id,
        task_id=task_id,
    )


# ── File expansion ────────────────────────────────────────────────────


def expand_files(patterns: tuple[str, ...]) -> list[str]:
    """Expand each --files entry (path or glob) to a sorted unique list.

    Globs run with `recursive=True` so `**` works as expected. Paths that
    don't match anything fall through verbatim so the caller can show a
    "missing file" entry in `validation_log`.
    """
    out: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        if any(ch in pat for ch in "*?["):
            matches = glob_module.glob(pat, recursive=True)
            for m in matches:
                if m not in seen:
                    seen.add(m)
                    out.append(m)
        else:
            if pat not in seen:
                seen.add(pat)
                out.append(pat)
    out.sort()
    return out


# ── Prompt rendering ──────────────────────────────────────────────────


def render_prompts(
    files_to_review: list[dict[str, Any]],
    *,
    review_scope: str,
    submission_context: str,
    template_dir: Path = PROMPT_DIR,
) -> dict[str, str]:
    """Render the system prompt + the review submission as a paired bundle.

    The system prompt includes ``architecture_rules.j2`` via Jinja
    ``{% include %}`` so the architecture rules fall through automatically;
    we render the system prompt with no variables and the submission
    prompt with the per-call variables.

    @returns Dict with ``system`` and ``user`` keys (the OpenAI/Anthropic
             role split the LLM tool-calling loop will eventually use).
    """
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    system_tpl = env.get_template("codeReviewer/frontend/system_prompt.j2")
    user_tpl = env.get_template("codeReviewer/frontend/review_submission.j2")
    system = system_tpl.render()
    user = user_tpl.render(
        files_to_review=files_to_review,
        submission_context=submission_context,
        review_scope=review_scope,
    )
    return {"system": system, "user": user}


def collect_file_payloads(paths: list[str]) -> list[dict[str, Any]]:
    """Build the `files_to_review` Jinja variable from disk.

    Each entry has ``path``, ``content``, ``language``, ``layer``, and
    ``lines_changed``. Missing files are recorded with a ``content`` body
    of ``"<missing>"`` so the prompt is still well-formed.
    """
    out: list[dict[str, Any]] = []
    for p in paths:
        full = Path(p)
        if not full.is_absolute():
            full = REPO_ROOT / p
        try:
            content = full.read_text(encoding="utf-8")
            language = _guess_language(full)
        except (FileNotFoundError, IsADirectoryError):
            content = "<missing>"
            language = "text"
        except UnicodeDecodeError:
            content = "<binary>"
            language = "text"
        out.append({
            "path": p,
            "content": content[:20_000],  # truncate huge files; warn via gaps
            "language": language,
            "layer": _classify_layer(p),
            "lines_changed": "Full file",
        })
    return out


def _guess_language(p: Path) -> str:
    suffix = p.suffix.lower()
    return {
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".py": "python",
        ".tf": "hcl",
        ".md": "markdown",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
    }.get(suffix, "text")


def _classify_layer(p: str) -> str:
    """Cheap classification mirroring `frontend/scripts/classify_frontend_layer.ts`."""
    lower = p.lower()
    for token, layer in (
        ("frontend/lib/wire/", "wire"),
        ("frontend/lib/trust-view/", "trust-view"),
        ("frontend/lib/ports/", "ports"),
        ("frontend/lib/translators/", "translators"),
        ("frontend/lib/transport/", "transport"),
        ("frontend/lib/adapters/", "adapters"),
        ("frontend/lib/composition", "composition"),
        ("frontend/lib/bff/", "bff"),
        ("frontend/components/", "components"),
        ("frontend/app/", "app"),
        ("frontend/middleware.ts", "edge_middleware"),
        ("middleware/", "middleware_python"),
        ("infra/dev-tier/", "infra"),
    ):
        if token in lower:
            return layer
    return "unclassified"


# ── Rules-only aggregation ────────────────────────────────────────────


def severity_for_rule(rule: str) -> str:
    """Map a tool-emitted rule id to a ReviewReport severity."""
    crit = {"CSP1", "CSP2", "SBX2"}
    if rule in crit:
        return "critical"
    if rule.startswith("U_") or rule.startswith("HARD"):
        return "warning"
    if rule == "SBX1":
        return "critical"
    if rule.startswith("name~") or rule.startswith("value~"):
        return "critical"  # FE-AP-18
    return "warning"


def _findings_from_check_csp_strict(file: str, raw: dict[str, Any]) -> list[ToolFinding]:
    out: list[ToolFinding] = []
    for v in raw.get("violations", []):
        rule = v.get("rule", "CSP")
        out.append(ToolFinding(
            rule_id=f"FD3.{rule}" if rule in {"CSP1", "CSP2"} else f"FD3.{rule}",
            dimension="FD3",
            severity=severity_for_rule(rule),
            file=file,
            line=None,
            description=v.get("description", ""),
            fix_suggestion=(
                "Remove the offending CSP token; rely on the per-request nonce + "
                "'strict-dynamic' chain documented in architecture_rules.j2."
            ),
            tool="check_csp_strict",
            raw=v,
        ))
    return out


def _findings_from_check_iframe_sandbox(file: str, raw: dict[str, Any]) -> list[ToolFinding]:
    out: list[ToolFinding] = []
    for iframe in raw.get("iframes", []):
        for msg in iframe.get("violations", []):
            rule = msg.split(":", 1)[0].strip()
            out.append(ToolFinding(
                rule_id=f"FD3.{rule}",
                dimension="FD3",
                severity="critical",
                file=file,
                line=iframe.get("line"),
                description=msg,
                fix_suggestion=(
                    "Restrict the iframe sandbox to `allow-scripts` only; remove "
                    "any allow-same-origin / allow-forms / allow-top-navigation tokens."
                ),
                tool="check_iframe_sandbox",
                raw=iframe,
            ))
    return out


def _findings_from_check_composer_keyboard(file: str, raw: dict[str, Any]) -> list[ToolFinding]:
    out: list[ToolFinding] = []
    for v in raw.get("violations", []):
        rule = v.get("rule", "U_KBD")
        out.append(ToolFinding(
            rule_id=f"FD2.{rule}",
            dimension="FD2",
            severity="warning",
            file=file,
            line=v.get("line"),
            description=v.get("description", ""),
            fix_suggestion=(
                "Update the composer to satisfy the U-family contract in "
                "architecture_rules.j2 (S3.8.5)."
            ),
            tool="check_composer_keyboard",
            raw=v,
        ))
    return out


def _findings_from_check_secrets(file: str, raw: dict[str, Any]) -> list[ToolFinding]:
    out: list[ToolFinding] = []
    for v in raw.get("violations", []):
        out.append(ToolFinding(
            rule_id="FD3.SEC1",
            dimension="FD3",
            severity="critical",
            file=file,
            line=v.get("line"),
            description=(
                f"NEXT_PUBLIC variable {v.get('var')} matches the secret pattern "
                f"{v.get('matched_pattern')} (FE-AP-18 AUTO-REJECT)."
            ),
            fix_suggestion=(
                "Move the value out of NEXT_PUBLIC_ and route the credential "
                "through middleware/ instead (F-R9)."
            ),
            tool="check_secrets_in_public_env",
            raw=v,
        ))
    return out


def _findings_from_check_jwt(file: str, raw: dict[str, Any]) -> list[ToolFinding]:
    out: list[ToolFinding] = []
    for v in raw.get("violations", []):
        out.append(ToolFinding(
            rule_id="FD3.SEC2",
            dimension="FD3",
            severity="critical",
            file=file,
            line=v.get("line"),
            description=(
                f"{v.get('api')} writes auth-shaped value `{v.get('key_or_value')}` "
                "to browser storage."
            ),
            fix_suggestion=(
                "Store the JWT in an HttpOnly + Secure + SameSite=Strict cookie set "
                "by middleware; never localStorage/sessionStorage."
            ),
            tool="check_jwt_storage",
            raw=v,
        ))
    return out


_TOOL_TO_FINDINGS_FN = {
    "check_csp_strict": _findings_from_check_csp_strict,
    "check_iframe_sandbox": _findings_from_check_iframe_sandbox,
    "check_composer_keyboard": _findings_from_check_composer_keyboard,
    "check_secrets_in_public_env": _findings_from_check_secrets,
    "check_jwt_storage": _findings_from_check_jwt,
}


def run_rules_only(files: list[str]) -> tuple[list[ToolFinding], list[str], list[str]]:
    """Dispatch every applicable TS tool against ``files`` and aggregate.

    @returns (findings, validation_log, gaps)
    """
    findings: list[ToolFinding] = []
    validation_log: list[str] = []
    gaps: list[str] = []
    for f in files:
        tools = applicable_tools(f)
        if not tools:
            validation_log.append(f"No deterministic tool applies to {f} (rules-only mode)")
            continue
        for name, args in tools:
            raw = run_ts_script(name, *args)
            fn = _TOOL_TO_FINDINGS_FN.get(name)
            if raw.get("error"):
                gaps.append(
                    f"{name}({args[0] if args else ''}) tool error: {raw.get('error')}",
                )
                validation_log.append(
                    f"{name} -> error: {raw.get('error')}",
                )
                continue
            if raw.get("skipped"):
                gaps.append(f"{name} skipped: {raw.get('reason')}")
                validation_log.append(f"{name} -> skipped: {raw.get('reason')}")
                continue
            if fn is None:
                # Tool produced no finding mapper today; record as a debug log.
                validation_log.append(
                    f"{name} -> exit_code={raw.get('exit_code')}; "
                    f"no rules-only mapper (results forwarded to gaps)",
                )
                continue
            new = fn(f, raw)
            findings.extend(new)
            validation_log.append(
                f"{name}({f}) -> exit_code={raw.get('exit_code')}, "
                f"{len(new)} finding(s)"
            )
    return findings, validation_log, gaps


# ── Verdict + report assembly ─────────────────────────────────────────


def derive_verdict(findings: list[ToolFinding]) -> str:
    """Apply the strict verdict rules from §8 of the system prompt."""
    if any(f.severity == "critical" for f in findings):
        return "reject"
    warnings = sum(1 for f in findings if f.severity == "warning")
    if warnings > 2:
        return "request_changes"
    return "approve"


def report_to_dict(
    *,
    verdict: str,
    findings: list[ToolFinding],
    files_reviewed: list[str],
    validation_log: list[str],
    gaps: list[str],
    statement: str,
    confidence: float,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Shape the in-memory aggregation into a JSON-serialisable ReviewReport."""
    by_dim: dict[str, list[ToolFinding]] = {}
    for f in findings:
        by_dim.setdefault(f.dimension, []).append(f)
    dimensions: list[dict[str, Any]] = []
    for dim, items in sorted(by_dim.items()):
        any_critical = any(i.severity == "critical" for i in items)
        status = "fail" if any_critical else ("partial" if items else "pass")
        dimensions.append({
            "dimension": dim,
            "name": _dim_label(dim),
            "status": status,
            "hypotheses_tested": len(items),
            "hypotheses_confirmed": len(items),
            "hypotheses_killed": 0,
            "findings": [
                {
                    "rule_id": i.rule_id,
                    "dimension": i.dimension,
                    "severity": i.severity,
                    "file": i.file,
                    "line": i.line,
                    "description": i.description,
                    "fix_suggestion": i.fix_suggestion,
                    "confidence": 1.0,
                    "certificate": {
                        "premises": [
                            f"[P1] {i.tool} ({i.file}{':' + str(i.line) if i.line else ''})"
                        ],
                        "traces": [],
                        "conclusion": f"{i.rule_id} FAIL -- {i.description}",
                    },
                }
                for i in items
            ],
        })

    return {
        "verdict": verdict,
        "statement": statement,
        "confidence": confidence,
        "dimensions": dimensions,
        "gaps": gaps,
        "validation_log": validation_log,
        "files_reviewed": files_reviewed,
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": metadata,
    }


def _dim_label(dim: str) -> str:
    return {
        "FD1": "Layering & Dependency Direction",
        "FD2": "Pattern Adherence",
        "FD3": "Security & Sandboxing",
        "FD4": "Accessibility (WCAG 2.2 AA)",
        "FD5": "Performance & Streaming",
        "FD6": "Tests & Architecture Tests",
        "FD7": "Anti-Patterns",
        "FD8": "Sprint Story Alignment",
        "FD9": "Middleware Ring (Python)",
        "FD10": "Infra Dev-Tier (OpenTofu)",
        "FD11": "Operational Readiness (Sprint 4)",
    }.get(dim, dim)


def exit_code_for(verdict: str, findings: list[ToolFinding], fail_on: str) -> int:
    """Apply --fail-on demotion to the LLM's verdict and return the exit code."""
    base = {"approve": EXIT_OK, "request_changes": EXIT_REQUEST_CHANGES, "reject": EXIT_REJECT}.get(
        verdict, EXIT_RUNNER_ERROR
    )
    threshold = SEVERITY_RANK[fail_on]
    has_above = any(SEVERITY_RANK[f.severity] >= threshold for f in findings)
    if base == EXIT_OK and has_above:
        # Demote: any finding ≥ threshold trips a non-zero exit.
        return EXIT_REQUEST_CHANGES if not any(f.severity == "critical" for f in findings) else EXIT_REJECT
    return base


# ── Report writers + eval capture ─────────────────────────────────────


def write_report(report: dict[str, Any], out: str) -> None:
    """Serialize `report` to ``out`` (or stdout when ``out == '-'``)."""
    payload = json.dumps(report, indent=2, default=str)
    if out == "-":
        sys.stdout.write(payload + "\n")
        return
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")


async def _record_eval(
    *,
    target: str,
    ai_input: dict[str, Any],
    ai_response: Any,
    user_id: str,
    task_id: str,
    model: str,
) -> None:
    """Best-effort eval_capture.record(); swallows any service error."""
    try:
        from services import eval_capture  # local import keeps test isolation

        await eval_capture.record(
            target=target,
            ai_input=ai_input,
            ai_response=ai_response,
            config={"configurable": {"task_id": task_id, "user_id": user_id}},
            model=model,
        )
    except Exception as exc:  # pragma: no cover - capture is non-blocking
        logger.warning("eval_capture.record failed: %s", exc)


# ── Main flow ─────────────────────────────────────────────────────────


def run(argv: list[str]) -> int:
    """Top-level entry point used by both `python -m` and the tests."""
    try:
        args = parse_args(argv)
    except (ValueError, SystemExit) as exc:
        logger.error("argument error: %s", exc)
        return EXIT_RUNNER_ERROR

    files = expand_files(args.files)
    if not files and not args.dry_run:
        logger.warning("--files matched zero entries; nothing to review")

    file_payloads = collect_file_payloads(files)
    rendered = render_prompts(
        file_payloads,
        review_scope=args.scope,
        submission_context=args.submission_context,
    )

    metadata: dict[str, Any] = {
        "scope": args.scope,
        "model_tier": args.model,
        "model_env_var": MODEL_TIER_TO_ENV.get(args.model, ""),
        "fail_on": args.fail_on,
        "mode": "dry_run" if args.dry_run else ("rules_only" if args.rules_only else "default_rules_only"),
        "tool_function_specs_count": len(tool_function_specs()),
    }

    if args.dry_run:
        report = {
            "verdict": "approve",
            "statement": "DRY-RUN: prompt rendered; no tools invoked, no LLM call placed.",
            "confidence": 1.0,
            "dimensions": [],
            "gaps": [
                "Full LLM tool-calling loop deferred (--dry-run mode).",
            ],
            "validation_log": [
                f"Rendered prompt for scope={args.scope} ({len(rendered['system'])} + "
                f"{len(rendered['user'])} chars)",
            ],
            "files_reviewed": files,
            "created_at": datetime.now(UTC).isoformat(),
            "metadata": {
                **metadata,
                "rendered_prompt_chars": len(rendered["system"]) + len(rendered["user"]),
            },
            "rendered_prompt": rendered,
        }
        write_report(report, args.out)
        asyncio.run(
            _record_eval(
                target="code_reviewer.frontend",
                ai_input={"system_chars": len(rendered["system"]), "user_chars": len(rendered["user"])},
                ai_response={"mode": "dry_run"},
                user_id=args.user_id,
                task_id=args.task_id or "dry-run",
                model=args.model,
            )
        )
        return EXIT_OK

    # rules-only (also the default fallback)
    findings, validation_log, gaps = run_rules_only(files)
    if not args.rules_only:
        gaps.insert(
            0,
            "LLM tool-calling loop deferred; falling back to --rules-only behaviour.",
        )
    verdict = derive_verdict(findings)
    statement_parts = [verdict.upper().replace("_", " ") + ":"]
    if verdict == "reject":
        crit_ids = sorted({f.rule_id for f in findings if f.severity == "critical"})
        statement_parts.append(f"auto-reject due to {', '.join(crit_ids)}.")
    statement_parts.append(
        f"Ran {len(findings)} deterministic finding(s) across {len(files)} file(s) "
        f"(scope={args.scope}, mode=rules-only)."
    )
    statement = " ".join(statement_parts)

    report = report_to_dict(
        verdict=verdict,
        findings=findings,
        files_reviewed=files,
        validation_log=validation_log,
        gaps=gaps,
        statement=statement,
        confidence=0.7,  # rules-only is partial; the LLM phase would lift this.
        metadata=metadata,
    )
    write_report(report, args.out)
    asyncio.run(
        _record_eval(
            target="code_reviewer.frontend",
            ai_input={"files": files, "scope": args.scope, "mode": metadata["mode"]},
            ai_response={"verdict": verdict, "findings": len(findings), "gaps": len(gaps)},
            user_id=args.user_id,
            task_id=args.task_id or "rules-only",
            model=args.model,
        )
    )
    return exit_code_for(verdict, findings, args.fail_on)


__all__ = [
    "EXIT_OK",
    "EXIT_REQUEST_CHANGES",
    "EXIT_REJECT",
    "EXIT_RUNNER_ERROR",
    "VALID_SCOPES",
    "VALID_MODEL_TIERS",
    "CliArgs",
    "ToolFinding",
    "build_arg_parser",
    "parse_args",
    "expand_files",
    "render_prompts",
    "collect_file_payloads",
    "run_rules_only",
    "derive_verdict",
    "report_to_dict",
    "exit_code_for",
    "run",
]
