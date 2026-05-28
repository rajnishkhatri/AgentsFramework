// @vitest-environment happy-dom
/**
 * ValidatorTable — failure-first then per-validator rendering.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ValidatorTable } from "./ValidatorTable";
import type { ValidatorStat } from "@/lib/wire/responses";

const PROMPT_INJECTION: ValidatorStat = {
  name: "prompt_injection",
  total_checks: 4,
  pass_count: 3,
  fail_count: 1,
  pass_rate: 0.75,
};
const PII: ValidatorStat = {
  name: "output_pii_scan",
  total_checks: 1,
  pass_count: 0,
  fail_count: 1,
  pass_rate: 0.0,
};

describe("ValidatorTable — failure-first", () => {
  it("renders the empty state when there are no validators", () => {
    render(<ValidatorTable validators={[]} />);
    expect(
      screen.getByRole("status", { name: /no validators/i }),
    ).toBeDefined();
  });
});

describe("ValidatorTable — acceptance", () => {
  it("renders one row per validator with formatted pass %", () => {
    render(<ValidatorTable validators={[PROMPT_INJECTION, PII]} />);
    expect(screen.getByText("prompt_injection")).toBeDefined();
    expect(screen.getByText("output_pii_scan")).toBeDefined();
    expect(screen.getByText("75.0%")).toBeDefined();
    expect(screen.getByText("0.0%")).toBeDefined();
  });
});
