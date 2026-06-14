"""Serve the open-coding HTML and accept its 'Save to disk' POST.

A plain http.server only serves files; the coder's Save button POSTs the coded
JSONL to /save, which this handler writes to disk so the Langfuse pusher can read it.

    python scripts/serve_open_coder.py            # serves on :3117
    python scripts/serve_open_coder.py --port 3118

Saves to: cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl
A timestamped backup is also written on every save so a bad overwrite is recoverable.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent / "cache" / "goaljudge_eval" / "open_coding"
SAVE_PATH = ROOT / "depth_strata_coded.jsonl"

# A save smaller than this fraction of the existing file is rejected as a likely
# truncation clobber, unless ?force=1 is passed.
TRUNCATION_FLOOR = 0.5


def _validate_jsonl(body: str) -> tuple[int, str | None]:
    """Return (row_count, error). error is None when every non-blank line is a
    JSON object carrying a 'trace_id' key."""
    rows = [line for line in body.splitlines() if line.strip()]
    if not rows:
        return 0, "empty body"
    for i, line in enumerate(rows, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            return len(rows), f"line {i} is not valid JSON: {e}"
        if not isinstance(obj, dict) or "trace_id" not in obj:
            return len(rows), f"line {i} is missing a 'trace_id' key"
    return len(rows), None


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/load":
            body = SAVE_PATH.read_text() if SAVE_PATH.exists() else ""
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self.wfile.write(body.encode())
            return
        super().do_GET()

    def _reject(self, msg: str) -> None:
        self.send_response(400)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())
        self.log_message("rejected save: %s", msg)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlsplit(self.path)
        if parsed.path != "/save":
            self.send_error(404)
            return
        force = parse_qs(parsed.query).get("force", ["0"])[0] not in ("0", "", "false")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")

        # (1) reject anything that isn't valid JSONL with a 'trace_id' per row
        n, err = _validate_jsonl(body)
        if err is not None:
            self._reject(f"invalid JSONL, not saved: {err}")
            return

        # (2) reject a save that would dramatically shrink the file (truncation
        # clobber) unless explicitly forced
        if SAVE_PATH.exists() and not force:
            existing = sum(1 for line in SAVE_PATH.read_text().splitlines() if line.strip())
            if existing and n < existing * TRUNCATION_FLOOR:
                self._reject(
                    f"refusing to shrink {existing} rows -> {n} "
                    f"(< {int(TRUNCATION_FLOOR * 100)}%); pass ?force=1 to override"
                )
                return

        SAVE_PATH.write_text(body if body.endswith("\n") else body + "\n")
        # (3) timestamped backup so an accidental overwrite is recoverable
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (ROOT / f"depth_strata_coded.{ts}.jsonl").write_text(SAVE_PATH.read_text())
        msg = f"{n} rows -> {SAVE_PATH.name}"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())
        self.log_message("saved %s", msg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3117)
    args = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    handler = partial(Handler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"open coder: http://localhost:{args.port}/coder.html")
    print(f"POST /save -> {SAVE_PATH}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
