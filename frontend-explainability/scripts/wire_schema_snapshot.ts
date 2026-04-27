/**
 * wire_schema_snapshot.ts
 *
 * Regenerates lib/wire/__python_schema_baseline__.json from the live Python
 * Pydantic models in explainability_app.wire.responses.  The baseline is a
 * JSON object keyed by Python class name, each value a JSON-Schema export.
 *
 * Usage: npm run wire-schema-snapshot
 *   — run from the frontend-explainability/ directory.
 *   — requires Python 3.10+ and the agent package installed (pip install -e ".[dev]").
 *
 * CI: .github/workflows/explainability-wire-baseline.yml runs this then checks
 *     git diff --quiet to fail if the baseline drifted.
 */
import { execFileSync } from "child_process";
import { mkdtempSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join, resolve } from "path";

const REPO_ROOT = resolve(__dirname, "../..");
const OUTPUT_PATH = resolve(__dirname, "../lib/wire/__python_schema_baseline__.json");

const SHAPES = [
  "WorkflowSummaryResponse",
  "BlackBoxEventResponse",
  "WorkflowEventsResponse",
  "DecisionRecordResponse",
  "TimeSeriesPointResponse",
  "DashboardMetricsResponse",
  "HealthResponse",
  "ErrorResponse",
];

const pythonSrc = `import json
from explainability_app.wire import responses as r

shapes = {name: getattr(r, name).model_json_schema() for name in ${JSON.stringify(SHAPES)}}
print(json.dumps(shapes, indent=2, sort_keys=False))
`;

const tmp = mkdtempSync(join(tmpdir(), "wire-snapshot-"));
const scriptPath = join(tmp, "dump.py");
writeFileSync(scriptPath, pythonSrc, "utf-8");

let raw: string;
try {
  raw = execFileSync("python3", [scriptPath], {
    cwd: REPO_ROOT,
    env: { ...process.env, PYTHONPATH: REPO_ROOT },
  })
    .toString()
    .trim();
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

writeFileSync(OUTPUT_PATH, raw + "\n", "utf-8");
console.log(`[wire-schema-snapshot] Wrote ${OUTPUT_PATH}`);
