#!/usr/bin/env python
"""Write the live tagged stress-frontend URL into the `stress` test profile.

After deploying the `--tag stress` frontend revision (deploy-gcp skill §Tiered-Loops
Stress Revision), the tagged URL is assigned by Cloud Run — don't hand-guess the
hash. This reads the real URL off the service's traffic map (the entry tagged
``stress``) and writes it into ``frontend/e2e/testing.profiles.yml`` so
``TEST_PROFILE=stress`` points at the right host.

Idempotent: re-running with the same URL is a no-op. Refuses to write a
placeholder/empty URL (so a missing tag fails loudly instead of stamping garbage).

    python scripts/fill_stress_profile_url.py
    python scripts/fill_stress_profile_url.py --service agent-frontend --region us-central1
    python scripts/fill_stress_profile_url.py --url https://stress---...run.app  # skip gcloud
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = AGENT_ROOT / "frontend" / "e2e" / "testing.profiles.yml"


def _tagged_url_from_gcloud(service: str, region: str, tag: str) -> str:
    """Return the URL of the traffic entry carrying ``tag`` (raises if absent)."""
    out = subprocess.run(
        [
            "gcloud", "run", "services", "describe", service,
            "--region", region, "--format", "json(status.traffic)",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    traffic = (json.loads(out).get("status") or {}).get("traffic") or []
    for entry in traffic:
        if entry.get("tag") == tag:
            url = (entry.get("url") or "").strip()
            if not url:
                raise SystemExit(
                    f"traffic tag {tag!r} on {service} has no URL yet — "
                    "wait for the tagged revision to be Ready, then retry."
                )
            return url
    tags = [e.get("tag") for e in traffic if e.get("tag")]
    raise SystemExit(
        f"no traffic entry tagged {tag!r} on {service} (found tags: {tags or 'none'}). "
        "Deploy the tagged revision first (deploy-gcp skill §Tiered-Loops Stress Revision)."
    )


def _write_profile_url(profiles_text: str, url: str) -> tuple[str, bool]:
    """Replace the stress profile's base_url line. Returns (new_text, changed).

    Edits the single ``base_url:`` line inside the ``stress:`` block by line scan
    (no YAML round-trip — preserves comments/formatting exactly).
    """
    lines = profiles_text.splitlines(keepends=True)
    in_stress = False
    stress_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Enter the stress block: a top-level "stress:" key under "profiles:".
        if stripped == "stress:" and (len(line) - len(line.lstrip())) >= 2:
            in_stress = True
            stress_indent = len(line) - len(line.lstrip())
            continue
        if in_stress:
            indent = len(line) - len(line.lstrip())
            # A sibling/parent key at <= the stress indent ends the block.
            if stripped and not stripped.startswith("#") and indent <= stress_indent:
                break
            if stripped.startswith("base_url:"):
                prefix = line[: len(line) - len(line.lstrip())]
                new_line = f'{prefix}base_url: "{url}"\n'
                if new_line == line:
                    return profiles_text, False
                lines[i] = new_line
                return "".join(lines), True
    raise SystemExit("could not find the stress profile's base_url line to update")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="agent-frontend")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--tag", default="stress")
    parser.add_argument(
        "--url",
        default=None,
        help="set this URL directly instead of querying gcloud",
    )
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH)
    args = parser.parse_args()

    url = args.url or _tagged_url_from_gcloud(args.service, args.region, args.tag)
    if not url.startswith("https://") or "REPLACE_HASH" in url:
        raise SystemExit(f"refusing to write non-live URL: {url!r}")

    text = args.profiles.read_text(encoding="utf-8")
    new_text, changed = _write_profile_url(text, url)
    if not changed:
        print(f"stress profile already points at {url} — no change")
        return 0
    args.profiles.write_text(new_text, encoding="utf-8")
    print(f"wrote stress base_url = {url}")
    print(f"  in {args.profiles}")
    print("now run: TEST_PROFILE=stress STRESS_SMOKE=1 pnpm test:e2e:stress")
    return 0


if __name__ == "__main__":
    sys.exit(main())
