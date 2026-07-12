"""Tier-1 taxonomy-readiness probe — measure-first gate for the deferred
``/learn/skill`` "Your pattern · X" aggregate callout.

Answers: is there enough tagged, themeable misconception data for tier-1 to
ever fire meaningfully? Clusters ONLY on the pre-controlled ``standard_id``
axis (never free-text). Emits a machine-readable ``build``/``defer`` verdict
against two locked thresholds. Read-only, stdlib-only, deterministic.

Mirror of ``scripts/syllabus_coverage_report.py``. Run:

    .venv/bin/python scripts/tier1_taxonomy_readiness.py
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"
DEFAULT_SYLLABUS = _REPO / "docs" / "plan" / "act-english-syllabus.seed.json"
DEFAULT_OUT = _REPO / "docs" / "plan" / "tier1-taxonomy-readiness.verdict.json"

# Locked thresholds (human gate 2026-07-12 — do not change).
MIN_MEANINGFUL_CLUSTERS = 1  # ≥1 skill with a standard_id cluster of ≥3
MIN_CLUSTER_SIZE_FOR_GATE = 3
MIN_FIRE_RATE = 0.05  # ≥5% of simulated learners

# Simulation defaults — misses_per_learner=2 is the minimum that can fire
# (principled corpus-density probe, not a tuned target).
DEFAULT_N_LEARNERS = 2000
DEFAULT_MISSES_PER_LEARNER = 2
DEFAULT_SEED = 0
DEFAULT_DUE_MODEL = "all_due"


def load_bank(path: Path) -> list[dict[str, Any]]:
    """Load the serving bank. Absent file → [] (edge: FR-6/§6)."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return data


def load_syllabus(path: Path) -> dict[str, set[int]]:
    """Per-skill set of ``standard_id``s from the ACT-English syllabus (FR-3)."""
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, set[int]] = {}
    for row in rows:
        skill = str(row["app_skill"])
        out.setdefault(skill, set()).add(int(row["standard_id"]))
    return out


def tagged_rows(bank: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Rows whose ``misconception`` is non-null and non-empty after strip (FR-1)."""
    return [
        dict(row)
        for row in bank
        if isinstance(row.get("misconception"), str) and row["misconception"].strip()
    ]


def untagged_ids(bank: Iterable[Mapping[str, Any]]) -> list[str]:
    """Ids of rows that fail the tagged predicate — flagged at foot, NEVER counted."""
    tagged_id_set = {r["id"] for r in tagged_rows(bank) if "id" in r}
    return [
        str(row.get("id", "?"))
        for row in bank
        if str(row.get("id", "?")) not in tagged_id_set
    ]


def integrity_warnings(
    tagged: Iterable[Mapping[str, Any]],
    syllabus: Mapping[str, set[int]],
) -> list[str]:
    """Tagged items whose ``standard_id`` is absent from the syllabus registry."""
    registered: set[int] = set()
    for stds in syllabus.values():
        registered.update(stds)
    warnings: list[str] = []
    for row in tagged:
        sid = row.get("standard_id")
        if sid is None:
            warnings.append(f"item {row.get('id', '?')}: missing standard_id")
            continue
        sid_int = int(sid)
        if sid_int not in registered:
            warnings.append(
                f"item {row.get('id', '?')}: standard_id {sid_int} not in syllabus registry"
            )
    return warnings


def meaningful_clusters(
    tagged: Iterable[Mapping[str, Any]],
    syllabus: Mapping[str, set[int]],
) -> dict[str, Any]:
    """Cluster tagged items by ``(skill_id, standard_id)`` (FR-2).

    Returns ``{clusters, not_meaningful, label}`` where:
    - ``clusters`` — multi-standard skills only, count ≥2 (candidate themes)
    - ``not_meaningful`` — single-standard skills' buckets (FR-3, excluded)
    - ``label`` — always ``\"candidate\"`` (FR-4); never a confirmed theme
    """
    registered = {sid for stds in syllabus.values() for sid in stds}
    counts: Counter[tuple[str, int]] = Counter()
    for row in tagged:
        skill = str(row.get("skill_id", ""))
        sid = row.get("standard_id")
        if sid is None:
            continue
        sid_int = int(sid)
        if sid_int not in registered:
            continue  # integrity_warnings surfaces these; never count
        counts[(skill, sid_int)] += 1

    clusters: dict[tuple[str, int], int] = {}
    not_meaningful: dict[tuple[str, int], int] = {}
    for key, n in counts.items():
        if n < 2:
            continue
        skill, _sid = key
        stds = syllabus.get(skill, set())
        if len(stds) <= 1:
            not_meaningful[key] = n
        else:
            clusters[key] = n
    return {
        "clusters": clusters,
        "not_meaningful": not_meaningful,
        "label": "candidate",
    }


def fires_for_misses(
    miss_rows: Iterable[Mapping[str, Any]],
    meaningful_keys: set[tuple[str, int]],
    *,
    due_skills: set[str] | None,
) -> bool:
    """True iff ≥2 due misses land in one meaningful ``(skill, standard_id)`` cluster.

    ``due_skills=None`` means all skills are due (the ``all_due`` upper bound).
    """
    counts: Counter[tuple[str, int]] = Counter()
    for row in miss_rows:
        skill = str(row.get("skill_id", ""))
        if due_skills is not None and skill not in due_skills:
            continue
        sid = row.get("standard_id")
        if sid is None:
            continue
        key = (skill, int(sid))
        if key in meaningful_keys:
            counts[key] += 1
            if counts[key] >= 2:
                return True
    return False


def simulate_fire_rate(
    tagged: Iterable[Mapping[str, Any]],
    syllabus: Mapping[str, set[int]],
    *,
    n_learners: int = DEFAULT_N_LEARNERS,
    misses_per_learner: int = DEFAULT_MISSES_PER_LEARNER,
    due_model: str = DEFAULT_DUE_MODEL,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Simulate the fraction of learners who fire tier-1 (FR-6 / FR-7).

    Draws misses over tagged items. Fires when ≥2 land in one meaningful
    cluster. ``due_model`` is an EXPLICIT param (never a silent FSRS port):
    - ``all_due`` — every missed skill is due (upper bound)
    - ``none_due`` — no skills due → fire-rate 0 (structural contrast)

    When no meaningful clusters exist, ``overall`` is 0.0 with
    ``structural_zero=True`` (AP-6: labeled, not a fabricated measured low).
    """

    tagged_list = [dict(r) for r in tagged]
    cluster_info = meaningful_clusters(tagged_list, syllabus)
    meaningful_keys = set(cluster_info["clusters"].keys())

    base: dict[str, Any] = {
        "due_model": due_model,
        "n_learners": n_learners,
        "misses_per_learner": misses_per_learner,
        "seed": seed,
        "per_skill": {},
        "overall": 0.0,
        "structural_zero": False,
    }

    if not meaningful_keys:
        base["structural_zero"] = True
        base["overall"] = 0.0
        # AP-6: per-skill absent, not a fake measured 0.0.
        base["per_skill"] = {}
        return base

    if not tagged_list or misses_per_learner <= 0 or n_learners <= 0:
        return base

    rng = random.Random(seed)
    skills = sorted(
        {str(r.get("skill_id", "")) for r in tagged_list if r.get("skill_id")}
    )

    if due_model == "all_due":
        due_skills: set[str] | None = None
    elif due_model == "none_due":
        due_skills = set()
    else:
        raise ValueError(
            f"unknown due_model: {due_model!r} (use 'all_due' or 'none_due')"
        )

    fire_count = 0
    per_skill_fire: Counter[str] = Counter()
    per_skill_n: Counter[str] = Counter()

    for _ in range(n_learners):
        k = min(misses_per_learner, len(tagged_list))
        misses = rng.sample(tagged_list, k) if k else []
        # Attribute learner to skills they touched (for per-skill rates).
        touched = {str(m.get("skill_id", "")) for m in misses}
        for skill in touched:
            per_skill_n[skill] += 1
        if fires_for_misses(misses, meaningful_keys, due_skills=due_skills):
            fire_count += 1
            for skill in touched:
                per_skill_fire[skill] += 1

    base["overall"] = fire_count / n_learners
    base["per_skill"] = {
        skill: (
            per_skill_fire[skill] / per_skill_n[skill] if per_skill_n[skill] else None
        )
        for skill in skills
    }
    return base


def verdict(
    clusters: Mapping[tuple[str, int], int],
    fire_rate: Mapping[str, Any],
    *,
    min_meaningful_clusters: int = MIN_MEANINGFUL_CLUSTERS,
    min_cluster_size: int = MIN_CLUSTER_SIZE_FOR_GATE,
    min_fire_rate: float = MIN_FIRE_RATE,
) -> dict[str, Any]:
    """Emit ``build``/``defer`` against the two locked thresholds (FR-8).

    ``build`` iff ≥1 multi-standard skill has a cluster of ≥``min_cluster_size``
    AND simulated fire-rate ≥ ``min_fire_rate``; else ``defer`` + reasons.
    """
    n_ge = sum(1 for n in clusters.values() if n >= min_cluster_size)
    rate = fire_rate.get("overall")
    if rate is None:
        rate_f = 0.0
    else:
        rate_f = float(rate)

    reasons: list[str] = []
    if n_ge < min_meaningful_clusters:
        reasons.append(
            f"cluster gate: {n_ge} cluster(s) of size ≥{min_cluster_size} "
            f"(need ≥{min_meaningful_clusters})"
        )
    if fire_rate.get("structural_zero"):
        reasons.append(
            "fire-rate gate: structural zero — no meaningful clusters exist "
            f"(need ≥{min_fire_rate:.0%})"
        )
    elif rate_f < min_fire_rate:
        reasons.append(
            f"fire-rate gate: measured {rate_f:.4f} under due_model="
            f"{fire_rate.get('due_model', '?')!r} (need ≥{min_fire_rate:.0%})"
        )

    return {
        "verdict": "build" if not reasons else "defer",
        "thresholds": {
            "min_meaningful_clusters": min_meaningful_clusters,
            "min_cluster_size": min_cluster_size,
            "min_fire_rate": min_fire_rate,
        },
        "measured": {
            "n_clusters_ge_3": n_ge,
            "n_meaningful_clusters_ge_2": len(clusters),
            "fire_rate": rate_f,
            "due_model": fire_rate.get("due_model"),
            "structural_zero": bool(fire_rate.get("structural_zero")),
            "n_learners": fire_rate.get("n_learners"),
            "misses_per_learner": fire_rate.get("misses_per_learner"),
            "seed": fire_rate.get("seed"),
        },
        "reasons": reasons,
    }


def per_skill_coverage(
    bank: Iterable[Mapping[str, Any]],
    tagged: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Per-skill totals for the coverage table (FR-5)."""
    bank_list = list(bank)
    tagged_list = list(tagged)
    skills = sorted(
        {str(r.get("skill_id", "")) for r in bank_list if r.get("skill_id")}
        | {str(r.get("skill_id", "")) for r in tagged_list if r.get("skill_id")}
    )
    out: dict[str, dict[str, Any]] = {}
    for skill in skills:
        items = [r for r in bank_list if str(r.get("skill_id", "")) == skill]
        skill_tagged = [r for r in tagged_list if str(r.get("skill_id", "")) == skill]
        stds = {
            int(r["standard_id"])
            for r in skill_tagged
            if r.get("standard_id") is not None
        }
        out[skill] = {
            "total": len(items),
            "tagged": len(skill_tagged),
            "tagged_pct": (len(skill_tagged) / len(items) if items else 0.0),
            "distinct_standards": len(stds),
        }
    return out


def render_report(
    bank: list[Mapping[str, Any]],
    syllabus: Mapping[str, set[int]],
    cluster_info: Mapping[str, Any],
    fire: Mapping[str, Any],
    decision: Mapping[str, Any],
    untagged: list[str],
    warnings: list[str],
) -> str:
    """Fixed-width human report (mirrors syllabus_coverage_report.render_report)."""
    tagged = tagged_rows(bank)
    coverage = per_skill_coverage(bank, tagged)
    lines: list[str] = []
    lines.append("Tier-1 taxonomy-readiness probe")
    lines.append("=" * 72)
    lines.append(
        f"bank items: {len(bank)}  tagged: {len(tagged)}  "
        f"untagged: {len(untagged)}  (untagged NEVER counted, FR-1)"
    )
    lines.append("")
    header = f"{'skill':<10} {'total':>5} {'tagged':>6} {'pct':>6} {'stds':>5}"
    lines.append(header)
    lines.append("-" * len(header))
    for skill, row in sorted(coverage.items()):
        pct = f"{row['tagged_pct'] * 100:5.1f}%" if row["total"] else "   —"
        lines.append(
            f"{skill:<10} {row['total']:5d} {row['tagged']:6d} {pct:>6} "
            f"{row['distinct_standards']:5d}"
        )
    lines.append("")
    lines.append(
        f"candidate clusters (label={cluster_info.get('label', 'candidate')!r}; "
        "human-review required, FR-4)"
    )
    lines.append(f"{'skill':<10} {'std':>4} {'n':>4}  status")
    lines.append("-" * 36)
    for (skill, sid), n in sorted(cluster_info.get("clusters", {}).items()):
        status = "candidate"
        lines.append(f"{skill:<10} {sid:4d} {n:4d}  {status}")
    for (skill, sid), n in sorted(cluster_info.get("not_meaningful", {}).items()):
        lines.append(f"{skill:<10} {sid:4d} {n:4d}  not-meaningful (FR-3)")
    if not cluster_info.get("clusters") and not cluster_info.get("not_meaningful"):
        lines.append("  (none)")
    lines.append("")
    due = fire.get("due_model", "?")
    rate = fire.get("overall")
    if fire.get("structural_zero"):
        rate_s = "— (structural zero: no meaningful clusters)"
    elif rate is None:
        rate_s = "—"
    else:
        rate_s = f"{float(rate):.4f}"
    lines.append(
        f"simulated fire-rate (due_model={due!r}, "
        f"n_learners={fire.get('n_learners')}, "
        f"misses_per_learner={fire.get('misses_per_learner')}, "
        f"seed={fire.get('seed')}): {rate_s}"
    )
    lines.append(
        "NOTE: due_model is an explicit approximation (FR-7); "
        "FSRS is TypeScript-only and is NOT re-implemented here."
    )
    lines.append("")
    lines.append(f"VERDICT: {decision.get('verdict', '?').upper()}")
    for reason in decision.get("reasons", []):
        lines.append(f"  - {reason}")
    if untagged:
        lines.append("")
        lines.append(f"UNTAGGED rows (never counted, FR-1): {len(untagged)}")
    if warnings:
        lines.append("")
        lines.append(f"INTEGRITY warnings: {len(warnings)}")
        lines.extend(f"  - {w}" for w in warnings)
    return "\n".join(lines)


def build_result(
    bank: list[Mapping[str, Any]],
    syllabus: Mapping[str, set[int]],
    *,
    n_learners: int = DEFAULT_N_LEARNERS,
    misses_per_learner: int = DEFAULT_MISSES_PER_LEARNER,
    due_model: str = DEFAULT_DUE_MODEL,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Run the full probe and return report text + verdict payload."""
    tagged = tagged_rows(bank)
    untagged = untagged_ids(bank)
    cluster_info = meaningful_clusters(tagged, syllabus)
    warnings = integrity_warnings(tagged, syllabus)
    fire = simulate_fire_rate(
        tagged,
        syllabus,
        n_learners=n_learners,
        misses_per_learner=misses_per_learner,
        due_model=due_model,
        seed=seed,
    )
    decision = verdict(cluster_info["clusters"], fire)
    # JSON-safe cluster keys.
    clusters_json = {
        f"{skill}:{sid}": n
        for (skill, sid), n in sorted(cluster_info["clusters"].items())
    }
    not_meaningful_json = {
        f"{skill}:{sid}": n
        for (skill, sid), n in sorted(cluster_info["not_meaningful"].items())
    }
    report = render_report(
        bank, syllabus, cluster_info, fire, decision, untagged, warnings
    )
    payload = {
        **decision,
        "clusters": clusters_json,
        "not_meaningful": not_meaningful_json,
        "label": cluster_info["label"],
        "coverage": per_skill_coverage(bank, tagged),
        "untagged_count": len(untagged),
        "integrity_warnings": warnings,
        "bank_items": len(bank),
        "tagged_items": len(tagged),
    }
    return {"report": report, "verdict": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--syllabus", type=Path, default=DEFAULT_SYLLABUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--n-learners", type=int, default=DEFAULT_N_LEARNERS)
    parser.add_argument(
        "--misses-per-learner", type=int, default=DEFAULT_MISSES_PER_LEARNER
    )
    parser.add_argument("--due-model", default=DEFAULT_DUE_MODEL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    bank = load_bank(args.corpus)
    syllabus = load_syllabus(args.syllabus)
    result = build_result(
        bank,
        syllabus,
        n_learners=args.n_learners,
        misses_per_learner=args.misses_per_learner,
        due_model=args.due_model,
        seed=args.seed,
    )
    print(result["report"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result["verdict"], indent=2) + "\n")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
