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
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            "--region",
            region,
            "--format",
            "json(status.traffic)",
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


def _write_profile_url(profiles_text: str, profile: str, url: str) -> tuple[str, bool]:
    """Replace a profile's base_url line. Returns (new_text, changed)."""
    lines = profiles_text.splitlines(keepends=True)
    in_profile = False
    profile_indent = None
    profile_key = f"{profile}:"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == profile_key and (len(line) - len(line.lstrip())) >= 2:
            in_profile = True
            profile_indent = len(line) - len(line.lstrip())
            continue
        if in_profile:
            indent = len(line) - len(line.lstrip())
            if stripped and not stripped.startswith("#") and indent <= profile_indent:
                break
            if stripped.startswith("base_url:"):
                prefix = line[: len(line) - len(line.lstrip())]
                new_line = f'{prefix}base_url: "{url}"\n'
                if new_line == line:
                    return profiles_text, False
                lines[i] = new_line
                return "".join(lines), True
    raise SystemExit(
        f"could not find the {profile!r} profile's base_url line to update"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="agent-frontend")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--tag", default="stress")
    parser.add_argument(
        "--profile",
        default=None,
        help="profile key in testing.profiles.yml (defaults to --tag)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="set this URL directly instead of querying gcloud",
    )
    parser.add_argument("--profiles", type=Path, default=PROFILES_PATH)
    args = parser.parse_args()

    profile = args.profile or args.tag
    url = args.url or _tagged_url_from_gcloud(args.service, args.region, args.tag)
    if not url.startswith("https://") or "REPLACE_HASH" in url:
        raise SystemExit(f"refusing to write non-live URL: {url!r}")

    text = args.profiles.read_text(encoding="utf-8")
    new_text, changed = _write_profile_url(text, profile, url)
    if not changed:
        print(f"{profile} profile already points at {url} — no change")
        return 0
    args.profiles.write_text(new_text, encoding="utf-8")
    print(f"wrote {profile} base_url = {url}")
    print(f"  in {args.profiles}")
    if profile == "stress":
        print("now run: TEST_PROFILE=stress STRESS_SMOKE=1 pnpm test:e2e:stress")
    elif profile == "phaseb":
        print("now run: TEST_PROFILE=phaseb PHASEB_SMOKE=1 pnpm test:e2e:phaseb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
