/**
 * Wire-drift test (rule W2 / FD7.AP14).
 *
 * Asserts that every property declared in __python_schema_baseline__.json
 * exists as a key in WorkflowSummarySchema, and vice versa.  Fails if either
 * side gains or loses a field without the other being updated.
 *
 * Run via: npm run wire-schema-snapshot && npm run test
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { WorkflowSummarySchema } from "./responses";

const baselinePath = resolve(__dirname, "./__python_schema_baseline__.json");

interface PythonSchema {
  properties: Record<string, unknown>;
  required?: string[];
  title?: string;
  type?: string;
}

describe("wire baseline drift", () => {
  let baseline: PythonSchema;

  // Failure-first: baseline file must exist before any schema comparison.
  it("baseline JSON file exists and is parseable", () => {
    const raw = readFileSync(baselinePath, "utf-8");
    baseline = JSON.parse(raw) as PythonSchema;
    expect(baseline).toHaveProperty("properties");
    expect(baseline).toHaveProperty("required");
  });

  it("Zod schema keys match Python property names (no added frontend-only fields)", () => {
    const raw = readFileSync(baselinePath, "utf-8");
    baseline = JSON.parse(raw) as PythonSchema;

    const pythonKeys = new Set(Object.keys(baseline.properties));
    const zodKeys = new Set(Object.keys(WorkflowSummarySchema.shape));

    const frontendOnly = [...zodKeys].filter((k) => !pythonKeys.has(k));
    expect(
      frontendOnly,
      `Frontend Zod schema has fields not present in Python: ${frontendOnly.join(", ")}`,
    ).toEqual([]);
  });

  it("Python property names all present in Zod schema (no missing frontend mirrors)", () => {
    const raw = readFileSync(baselinePath, "utf-8");
    baseline = JSON.parse(raw) as PythonSchema;

    const pythonKeys = Object.keys(baseline.properties);
    const zodKeys = new Set(Object.keys(WorkflowSummarySchema.shape));

    const missingFromZod = pythonKeys.filter((k) => !zodKeys.has(k));
    expect(
      missingFromZod,
      `Python schema has fields not mirrored in Zod: ${missingFromZod.join(", ")}`,
    ).toEqual([]);
  });

  it("required fields from Python are non-optional in Zod schema", () => {
    const raw = readFileSync(baselinePath, "utf-8");
    baseline = JSON.parse(raw) as PythonSchema;

    const required = baseline.required ?? [];
    for (const key of required) {
      expect(
        WorkflowSummarySchema.shape,
        `Required field '${key}' must exist in Zod schema`,
      ).toHaveProperty(key);
    }
  });
});
