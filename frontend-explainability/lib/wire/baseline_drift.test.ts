/**
 * Wire-drift test (rule W2 / FD7.AP14).
 *
 * Asserts that every property declared in __python_schema_baseline__.json
 * exists as a key in the corresponding Zod schema, and vice versa.  Fails if
 * either side gains or loses a field without the other being updated.
 *
 * The baseline is now a JSON object keyed by Python class name; each value is
 * a JSON-Schema export.  This file maps each Python shape name to its Zod
 * mirror in ./responses.ts.
 *
 * Run via: npm run wire-schema-snapshot && npm run test
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import {
  WorkflowSummarySchema,
  BlackBoxEventSchema,
  WorkflowEventsSchema,
  DecisionRecordSchema,
  TimeSeriesPointSchema,
  DashboardMetricsSchema,
  HealthResponseSchema,
  ErrorResponseSchema,
} from "./responses";
import type { ZodObject, ZodRawShape } from "zod";

const baselinePath = resolve(__dirname, "./__python_schema_baseline__.json");

interface PythonSchema {
  properties: Record<string, unknown>;
  required?: string[];
  title?: string;
  type?: string;
}

type Baseline = Record<string, PythonSchema>;

const ZOD_MIRRORS: Record<string, ZodObject<ZodRawShape>> = {
  WorkflowSummaryResponse: WorkflowSummarySchema,
  BlackBoxEventResponse: BlackBoxEventSchema,
  WorkflowEventsResponse: WorkflowEventsSchema,
  DecisionRecordResponse: DecisionRecordSchema,
  TimeSeriesPointResponse: TimeSeriesPointSchema,
  DashboardMetricsResponse: DashboardMetricsSchema,
  HealthResponse: HealthResponseSchema,
  ErrorResponse: ErrorResponseSchema,
};

function loadBaseline(): Baseline {
  const raw = readFileSync(baselinePath, "utf-8");
  return JSON.parse(raw) as Baseline;
}

describe("wire baseline drift", () => {
  // Failure-first: baseline file must exist and parse before any comparison.
  it("baseline JSON file exists and is parseable as a multi-shape map", () => {
    const baseline = loadBaseline();
    expect(typeof baseline).toBe("object");
    for (const [name, schema] of Object.entries(baseline)) {
      expect(schema, `baseline[${name}] must declare 'properties'`).toHaveProperty(
        "properties",
      );
    }
  });

  it("every Python shape has a matching Zod mirror in responses.ts", () => {
    const baseline = loadBaseline();
    const missingMirrors = Object.keys(baseline).filter(
      (name) => !(name in ZOD_MIRRORS),
    );
    expect(
      missingMirrors,
      `Python shapes without Zod mirror: ${missingMirrors.join(", ")}`,
    ).toEqual([]);
  });

  it("every Zod mirror has a matching Python shape in the baseline", () => {
    const baseline = loadBaseline();
    const orphaned = Object.keys(ZOD_MIRRORS).filter(
      (name) => !(name in baseline),
    );
    expect(
      orphaned,
      `Zod mirrors without Python shape: ${orphaned.join(", ")}`,
    ).toEqual([]);
  });

  it.each(Object.keys(ZOD_MIRRORS))(
    "Zod schema keys for %s match Python property names",
    (shapeName) => {
      const baseline = loadBaseline();
      const pyShape = baseline[shapeName];
      expect(pyShape, `${shapeName} must exist in baseline`).toBeDefined();
      const zodShape = ZOD_MIRRORS[shapeName]!;

      const pythonKeys = new Set(Object.keys(pyShape!.properties));
      const zodKeys = new Set(Object.keys(zodShape.shape));

      const frontendOnly = [...zodKeys].filter((k) => !pythonKeys.has(k));
      const missingFromZod = [...pythonKeys].filter((k) => !zodKeys.has(k));

      expect(
        frontendOnly,
        `${shapeName}: Zod has fields not present in Python: ${frontendOnly.join(", ")}`,
      ).toEqual([]);
      expect(
        missingFromZod,
        `${shapeName}: Python has fields not mirrored in Zod: ${missingFromZod.join(", ")}`,
      ).toEqual([]);
    },
  );

  it.each(Object.keys(ZOD_MIRRORS))(
    "Python required fields for %s exist in Zod schema",
    (shapeName) => {
      const baseline = loadBaseline();
      const pyShape = baseline[shapeName]!;
      const zodShape = ZOD_MIRRORS[shapeName]!;
      const required = pyShape.required ?? [];
      for (const key of required) {
        expect(
          zodShape.shape,
          `${shapeName}: required Python field '${key}' missing from Zod`,
        ).toHaveProperty(key);
      }
    },
  );
});
