// @vitest-environment happy-dom
/**
 * ComplianceExportButtons — failure-first disabled state, then JSON / CSV
 * download triggers (S3.2.1 AC).
 *
 * `URL.createObjectURL` is stubbed because happy-dom does not implement it
 * by default; the test asserts that:
 *   - the empty list disables both buttons (failure-first);
 *   - JSON click produces a blob with the wrapping bundle keys;
 *   - CSV click produces a blob with the documented header row.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import {
  ComplianceExportButtons,
  type ComplianceExportRow,
} from "./ComplianceExportButtons";
import type { IntegrityReport, WorkflowSummary } from "@/lib/wire/responses";

function makeWorkflow(id: string): WorkflowSummary {
  return {
    workflow_id: id,
    started_at: "2026-04-26T08:00:00.000Z",
    event_count: 5,
    status: "completed",
    primary_agent_id: "cli-agent",
  };
}

function valid(id: string): IntegrityReport {
  return {
    workflow_id: id,
    chain_valid: true,
    broken_at_event_id: null,
    expected_hash: null,
    actual_hash: null,
  };
}

let captured: { content: string; mime: string }[] = [];

beforeEach(() => {
  captured = [];
  vi.stubGlobal(
    "Blob",
    function StubBlob(parts: BlobPart[], options?: BlobPropertyBag) {
      const text = parts.map((p) => String(p)).join("");
      captured.push({ content: text, mime: options?.type ?? "" });
      return { size: text.length, type: options?.type ?? "" };
    } as unknown as typeof Blob,
  );
  // We MUST keep URL constructable so happy-dom's anchor click handler can
  // still parse the href.  We only need to stub createObjectURL.
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:stub");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
});

const STUB_API_URL = "http://localhost:8001";

describe("ComplianceExportButtons — failure-first", () => {
  it("disables every button when there is nothing to export", () => {
    render(
      <ComplianceExportButtons
        rows={[]}
        generatedAt="2026-04-26T08:00:00.000Z"
        apiUrl={STUB_API_URL}
      />,
    );
    const summary = screen.getByRole("button", { name: /export summary json/i });
    const fullBundle = screen.getByRole("button", {
      name: /export full bundle json/i,
    });
    const csv = screen.getByRole("button", { name: /export csv/i });
    expect(summary.hasAttribute("disabled")).toBe(true);
    expect(fullBundle.hasAttribute("disabled")).toBe(true);
    expect(csv.hasAttribute("disabled")).toBe(true);
  });
});

describe("ComplianceExportButtons — summary acceptance", () => {
  const rows: ComplianceExportRow[] = [
    { workflow: makeWorkflow("wf-a"), report: valid("wf-a") },
  ];

  it("emits a JSON blob with bundle_type='compliance_summary' on Summary click", () => {
    render(
      <ComplianceExportButtons
        rows={rows}
        generatedAt="2026-04-26T08:00:00.000Z"
        apiUrl={STUB_API_URL}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /export summary json/i }),
    );
    expect(captured).toHaveLength(1);
    expect(captured[0]?.mime).toBe("application/json");
    const parsed = JSON.parse(captured[0]!.content);
    expect(parsed.bundle_type).toBe("compliance_summary");
    expect(parsed.workflow_count).toBe(1);
    expect(parsed.workflows[0].workflow_summary.workflow_id).toBe("wf-a");
    expect(parsed.workflows[0].integrity.chain_valid).toBe(true);
  });

  it("emits a CSV blob with the documented header row when clicked", () => {
    render(
      <ComplianceExportButtons
        rows={rows}
        generatedAt="2026-04-26T08:00:00.000Z"
        apiUrl={STUB_API_URL}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));
    expect(captured).toHaveLength(1);
    expect(captured[0]?.mime).toBe("text/csv");
    const csv = captured[0]!.content;
    expect(csv).toContain(
      "workflow_id,started_at,status,event_count,primary_agent_id," +
        "chain_valid,broken_at_event_id,expected_hash,actual_hash",
    );
    expect(csv).toContain("wf-a");
    expect(csv).toContain("cli-agent");
  });
});

describe("ComplianceExportButtons — full bundle export (Sprint 3 review F1)", () => {
  it("fetches every workflow's ComplianceBundle and emits the full payload", async () => {
    const rows: ComplianceExportRow[] = [
      { workflow: makeWorkflow("wf-a"), report: valid("wf-a") },
      { workflow: makeWorkflow("wf-b"), report: valid("wf-b") },
    ];
    const fetchMock = vi.fn(async (input: string | URL) => {
      const url = String(input);
      const wfId = url.includes("wf-a") ? "wf-a" : "wf-b";
      const body = {
        workflow_id: wfId,
        event_count: 1,
        hash_chain_valid: true,
        bundle_type: "compliance_audit",
        exported_at: "2026-04-26T08:00:01.000Z",
        events: [
          {
            event_id: "e1",
            workflow_id: wfId,
            event_type: "task_started",
            timestamp: "2026-04-26T08:00:00.000Z",
            step: null,
            details: { agent_id: "cli-agent" },
            integrity_hash: "h",
          },
        ],
        identity_cards: {},
        audit_trails: {},
        phase_decisions: [],
        correlation_health: {
          has_trace_id: true,
          has_user_id: true,
          has_task_id: true,
          has_agent_id: true,
          missing_keys: [],
        },
        integrity: {
          workflow_id: wfId,
          chain_valid: true,
          broken_at_event_id: null,
          expected_hash: null,
          actual_hash: null,
        },
      };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ComplianceExportButtons
        rows={rows}
        generatedAt="2026-04-26T08:00:00.000Z"
        apiUrl={STUB_API_URL}
      />,
    );
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /export full bundle json/i }),
      );
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    expect(captured).toHaveLength(1);
    const parsed = JSON.parse(captured[0]!.content);
    expect(parsed.bundle_type).toBe("compliance_audit_bundle");
    expect(parsed.workflow_count).toBe(2);
    expect(parsed.bundle_failures).toEqual([]);
    // Sprint 3 review F1 contract: the full bundle MUST include the
    // governance evidence keys, not only summary metadata.
    expect(parsed.workflows[0]).toHaveProperty("correlation_health");
    expect(parsed.workflows[0]).toHaveProperty("events");
    expect(parsed.workflows[0]).toHaveProperty("identity_cards");
    expect(parsed.workflows[0]).toHaveProperty("phase_decisions");
    expect(parsed.workflows[0]).toHaveProperty("integrity");
  });
});
