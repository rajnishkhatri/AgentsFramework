/**
 * Vitest sibling for `check_sprint_story.ts`.
 *
 * Failure paths first (FD6.ADAPTER): unknown story id and synthesised
 * markdown rows are exercised before the real PASS lookup.
 */

import { describe, expect, it } from "vitest";
import {
  checkSprintStory,
  composeShellCommand,
  parseSprintStoryMap,
} from "./check_sprint_story";

const SAMPLE_TABLE = `
## Sprint Story Acceptance Map

| story_id | key_files | acceptance_signal | known_status |
|----------|-----------|-------------------|--------------|
| **S0.1.1** | \`docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md\` | \`test -f docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md\` | PASS |
| **S2.1.2** | \`infra/dev-tier/neon.tf\`, \`frontend/drizzle.config.ts\` | \`true\` | PARTIAL |

## Some Other Section
`;

describe("parseSprintStoryMap — table parsing", () => {
  it("extracts every data row and explodes brace-expanded key_files", () => {
    const rows = parseSprintStoryMap(
      SAMPLE_TABLE +
        "\n## Sprint Story Acceptance Map\n" +
        "| **S3.3.2** | `frontend/lib/adapters/auth/workos_authkit_adapter.{ts,test.ts}` | `true` | re-derive |\n",
    );
    expect(rows.find((r) => r.story_id === "S0.1.1")).toBeTruthy();
    expect(rows.find((r) => r.story_id === "S2.1.2")?.key_files).toEqual([
      "infra/dev-tier/neon.tf",
      "frontend/drizzle.config.ts",
    ]);
    const expanded = rows.find((r) => r.story_id === "S3.3.2");
    expect(expanded?.key_files).toEqual([
      "frontend/lib/adapters/auth/workos_authkit_adapter.ts",
      "frontend/lib/adapters/auth/workos_authkit_adapter.test.ts",
    ]);
  });
});

describe("composeShellCommand — Sprint Map signal translation", () => {
  it("AND-chains a multi-component signal split on ' + '", () => {
    const out = composeShellCommand("test -f a.md + test -f b.md");
    expect(out).toBe("test -f a.md && test -f b.md");
  });
  it("defends pytest tests/infra/* commands with --override-ini", () => {
    const out = composeShellCommand("pytest tests/infra/test_neon.py -q");
    expect(out).toContain('pytest --override-ini="addopts="');
  });
  it("does NOT mutate non-infra pytest commands", () => {
    const out = composeShellCommand(
      "pytest tests/architecture/test_middleware_layer.py -q",
    );
    expect(out).toBe("pytest tests/architecture/test_middleware_layer.py -q");
  });
  it("passes through a single command unchanged", () => {
    const out = composeShellCommand('test -f docs/X.md');
    expect(out).toBe("test -f docs/X.md");
  });
});

describe("check_sprint_story — rejection + pass", () => {
  it("FAILS with row_found=false for an unknown story_id", () => {
    const r = checkSprintStory("S9.9.9");
    expect(r.pass).toBe(false);
    expect(r.row_found).toBe(false);
    expect(r.error).toMatch(/not found/i);
  });

  it("PASSES on S0.1.1 (canonical existing-file row)", () => {
    const r = checkSprintStory("S0.1.1");
    if (!r.pass) {
      throw new Error(`Expected S0.1.1 to pass: ${JSON.stringify(r, null, 2)}`);
    }
    expect(r.row_found).toBe(true);
    expect(r.key_files_missing).toEqual([]);
  });
});
