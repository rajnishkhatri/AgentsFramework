"""Serve the open-coding HTML, its cases, and accept its 'Save to disk' POST.

A plain http.server only serves files. This handler adds three routes the coder
needs:

    GET  /cases  -> the cases array (what to code), read from CASES_PATH
    GET  /load   -> the previously-saved coded JSONL, so reopening restores codes
    POST /save   -> writes the coded JSONL to SAVE_PATH (with validation + backup)

Usage:

    python serve_open_coder.py                       # serves on :3117
    python serve_open_coder.py --port 3118
    python serve_open_coder.py --dir path/to/workdir  # where coder.html/cases.json live

The work directory must contain `coder.html` and `cases.json`. Coded output and
timestamped backups are written next to them.

This is the skill's portable copy. The repo's planning-depth session used the
equivalent at scripts/serve_open_coder.py with paths hardcoded to
cache/goaljudge_eval/open_coding/.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# A save smaller than this fraction of the existing file is rejected as a likely
# truncation clobber, unless ?force=1 is passed. This guard exists because a
# stray `curl /save` once overwrote a fully-coded file with the string "probe".
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


def make_handler(workdir: Path, save_path: Path, cases_path: Path):
    class Handler(SimpleHTTPRequestHandler):
        def _send(self, code: int, body: str, ctype: str = "text/plain") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/cases":
                if not cases_path.exists():
                    self._send(404, "[]", "application/json")
                    return
                self._send(200, cases_path.read_text(), "application/json")
                return
            if self.path == "/load":
                body = save_path.read_text() if save_path.exists() else ""
                self._send(200, body, "application/x-ndjson")
                return
            super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path != "/save":
                self.send_error(404)
                return
            force = parse_qs(parsed.query).get("force", ["0"])[0] not in (
                "0",
                "",
                "false",
            )
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")

            # (1) reject anything that isn't valid JSONL with a 'trace_id' per row
            n, err = _validate_jsonl(body)
            if err is not None:
                self._send(400, f"invalid JSONL, not saved: {err}")
                self.log_message("rejected save: %s", err)
                return

            # (2) reject a save that would dramatically shrink the file
            if save_path.exists() and not force:
                existing = sum(
                    1 for line in save_path.read_text().splitlines() if line.strip()
                )
                if existing and n < existing * TRUNCATION_FLOOR:
                    msg = (
                        f"refusing to shrink {existing} rows -> {n} "
                        f"(< {int(TRUNCATION_FLOOR * 100)}%); pass ?force=1 to override"
                    )
                    self._send(400, msg)
                    self.log_message("rejected save: %s", msg)
                    return

            save_path.write_text(body if body.endswith("\n") else body + "\n")
            # (3) timestamped backup so an accidental overwrite is recoverable
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            (workdir / f"{save_path.stem}.{ts}.jsonl").write_text(save_path.read_text())
            msg = f"{n} rows -> {save_path.name}"
            self._send(200, msg)
            self.log_message("saved %s", msg)

    return partial(Handler, directory=str(workdir))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3117)
    ap.add_argument(
        "--dir", default=".", help="work dir holding coder.html + cases.json"
    )
    ap.add_argument(
        "--coded",
        default="coded.jsonl",
        help="coded JSONL filename (relative to --dir)",
    )
    ap.add_argument(
        "--cases", default="cases.json", help="cases filename (relative to --dir)"
    )
    args = ap.parse_args()

    workdir = Path(args.dir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    save_path = workdir / args.coded
    cases_path = workdir / args.cases

    handler = make_handler(workdir, save_path, cases_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"open coder: http://localhost:{args.port}/coder.html")
    print(f"GET  /cases -> {cases_path}")
    print(f"POST /save  -> {save_path}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
