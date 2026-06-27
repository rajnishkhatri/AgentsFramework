/**
 * Fix-probe registry — one named probe per F1–F7 tool-calling fix.
 *
 * Each probe is engineered to trigger exactly ONE fix's seam, sourced from the
 * real corpus exemplars in `cache/open_coding/tool-calling-failures/
 * STAGE5_root_cause_report.md` (§1 axial taxonomy), so every probe reproduces an
 * *observed* failure rather than a synthetic one:
 *
 *   F1  — `file_io` masked its own ValueError as a "tool_reported" string; the
 *         boundary-violating literal `/workspace/X` path must now surface
 *         `error_class == "validation"`            (report §F1, file_io.py:23→37)
 *   F1b — shell block / timeout split: a blocked program → `validation`,
 *         an over-budget command → `timeout`                       (classifier)
 *   F2  — a `validation` failure now carries the `_repair_hint` marker so the
 *         model self-repairs instead of looping on filename variants  (report §F2)
 *   F3  — a hallucinated tool name → `unknown_tool` + the `_unknown_tool_nudge`
 *         marker; the model must NOT loop the invented name (DeepSeek `read`×5,
 *         report §F3/§F4)
 *   F6  — corrupt success: a substantive trajectory with an EMPTY final answer
 *         must record `goal_met == false` / `criteria_met == 0.0` (report §F6)
 *   F7  — multi-turn: turn ≥2 must reach an answer (the dropped-user-message
 *         defect that GLM/Z.ai rejected on every case, report §F7)
 *
 * The deterministic `trace_id` mint mirrors `scripts/export_goaljudge_registry_
 * json.py` (`uuid.uuid5(NAMESPACE_DNS, id).hex`) so `verify_run.py
 * --id-namespace dns` reconciles the join key the same way it does for the
 * GoalJudge batch. `session_id` follows the same `session-{id}` convention.
 *
 * Plan: docs/plans/toolcalling_f1f7_live_validation.plan.md
 */

import { createHash } from "node:crypto";

/** The fix each probe targets (matches the analyzer's per-fix scorecard rows). */
export type FixId = "F1" | "F1b" | "F2" | "F3" | "F6" | "F7a" | "F7b";

/** One conversational turn. Single-turn probes have exactly one. */
export type ProbeTurn = {
  /** The prompt text injected into the composer for this turn. */
  prompt: string;
};

export type FixProbeCase = {
  /** Human label, e.g. "P-F1-path". Shown on the scorecard. */
  id: string;
  /**
   * Wire/join id, e.g. "GJ-FIX-01". MUST match the backend's `gj:` thread
   * regex (`GJ-[A-Z]+-\d+`, goaljudge_saturation_bridge.py:34) so the backend
   * adopts our deterministic trace_id as the BlackBox workflow_id. The
   * deterministic `trace_id` is minted from THIS id (not `id`), and the
   * analyzer/`verify_run.py --id-namespace dns` reconcile against it too.
   */
  case_id: string;
  /** The fix this probe validates. */
  fix: FixId;
  /**
   * Provider profile to pin for this probe (rides `input.pinned_model`, and is
   * seeded via `?model=` on navigation). `undefined` => default profile (no pin),
   * byte-identical to an unpinned run.
   */
  pinned_model?: string;
  /**
   * Turns sent in the SAME thread. Multi-turn probes (F7) MUST NOT click "New
   * chat" between turns so `state["messages"]` is non-empty on turn ≥2 — the
   * exact condition F7 targets.
   */
  turns: ProbeTurn[];
  /**
   * Positive carrier the analyzer asserts on the BlackBox/Langfuse trace.
   * `error_class` is the `ERROR_OCCURRED.details.error_class` string.
   */
  expected_error_class?: "validation" | "timeout" | "unknown_tool";
  /** Substring the streamed/persisted tool output must contain (F2/F3 markers). */
  expected_marker?: string;
  /** F6: assert `TASK_COMPLETED.details.goal_met` equals this. */
  expected_goal_met?: boolean;
  /**
   * Negative control — the pre-fix failure that must be ABSENT. Free-text key
   * interpreted by the analyzer:
   *   "not_tool_reported"   — no ERROR_OCCURRED with error_class=="tool_reported"
   *   "not_validation"      — the failure is NOT mislabeled validation (F1b timeout)
   *   "no_name_loop"        — the hallucinated tool name is not called ≥3×
   *   "outcome_not_success" — terminal outcome is not "success" (F6)
   *   "no_llm_rejection"    — no provider-rejection / last_llm_error on turn ≥2 (F7)
   */
  negative_control?:
    | "not_tool_reported"
    | "not_validation"
    | "no_name_loop"
    | "outcome_not_success"
    | "no_llm_rejection";
  /**
   * When true, the probe's seam depends on a *model behaving badly* (e.g. F3
   * dispatching a hallucinated tool name, F6 returning a truly empty answer) —
   * a capable pinned model often refuses to, so the seam can't be forced
   * deterministically through the live UI. The analyzer then reports SKIP
   * (live-unforcible) instead of FAIL when the trigger didn't fire; the fix
   * itself is covered by the unit suite. The probe still RUNS so a future
   * weaker model that *does* misbehave gets validated.
   */
  live_unforcible?: boolean;
  /** One-line note for the scorecard. */
  note: string;
  /** Derived (do not set): deterministic uuid5(DNS, id).hex join key. */
  trace_id: string;
  /** Derived (do not set): `session-{id-lower}`. */
  session_id: string;
};

/** RFC-4122 v5 (SHA-1) UUID over NAMESPACE_DNS — matches Python `uuid.uuid5`. */
function uuid5Dns(name: string): string {
  // NAMESPACE_DNS = 6ba7b810-9dad-11d1-80b4-00c04fd430c8
  const ns = Buffer.from("6ba7b8109dad11d180b400c04fd430c8", "hex");
  const hash = createHash("sha1")
    .update(Buffer.concat([ns, Buffer.from(name, "utf8")]))
    .digest();
  const bytes = hash.subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50; // version 5
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC variant
  return bytes.toString("hex");
}

/** Probe definitions BEFORE the derived join keys are filled in. */
type RawProbe = Omit<FixProbeCase, "trace_id" | "session_id">;

const RAW_PROBES: RawProbe[] = [
  {
    id: "P-F1-path",
    case_id: "GJ-FIX-01",
    fix: "F1",
    pinned_model: "claude-haiku-4-5",
    // F1 runs on the default provider — every backend masks this the same way
    // pre-fix; the carrier (not the prose) is what we assert.
    turns: [
      {
        prompt:
          "Read the file at the absolute path /etc/passwd and report its first " +
          "line. Use the file reading tool.",
      },
    ],
    expected_error_class: "validation",
    negative_control: "not_tool_reported",
    note:
      "Boundary-violating path must surface error_class=validation, not the " +
      "masked tool_reported string (file_io.py self-catch, report §F1).",
  },
  {
    id: "P-F1b-shell",
    case_id: "GJ-FIX-02",
    fix: "F1b",
    pinned_model: "claude-haiku-4-5",
    turns: [
      {
        // `date` is NOT in the shell allowlist {ls,cat,head,tail,grep,find,
        // python,wc} → the validator rejects it as a malformed call (validation),
        // which the model will actually attempt (unlike `rm -rf /`, which it
        // refuses conversationally and never calls the tool).
        prompt:
          "Use the shell tool to run the command `date` and report the current " +
          "system date and time it prints.",
      },
    ],
    expected_error_class: "validation",
    negative_control: "not_tool_reported",
    note:
      "A non-allowlisted shell program classifies as validation (shell.py " +
      "allowlist branch), not a generic runtime crash (report §F1b).",
  },
  {
    id: "P-F1b-timeout",
    case_id: "GJ-FIX-03",
    fix: "F1b",
    pinned_model: "claude-haiku-4-5",
    turns: [
      {
        // `find` IS allowlisted and has no metacharacters; scanning the whole
        // filesystem with a 1-second budget exceeds it → TimeoutExpired →
        // error_class=timeout. (`sleep` is not allowlisted, so it would have
        // mis-fired as validation — that was the prior probe's bug.)
        prompt:
          "Use the shell tool to run `find / -name needle.txt` with the tool's " +
          "timeout set to 1 second, then report what it found.",
      },
    ],
    expected_error_class: "timeout",
    // No "not_validation" neg control: a live model often makes several shell
    // calls in one run (e.g. an earlier `sleep` rejected as validation, then the
    // `find` that times out), so BOTH carriers legitimately appear. The positive
    // `timeout` carrier IS the discriminating signal the fix added.
    note:
      "An allowlisted command that exceeds its time budget classifies as " +
      "timeout, distinct from validation (classifier split, report §F1b).",
  },
  {
    id: "P-F2-repair",
    case_id: "GJ-FIX-04",
    fix: "F2",
    pinned_model: "claude-haiku-4-5",
    turns: [
      {
        // Writing OUTSIDE the workspace boundary (/workspace, set via
        // WORKSPACE_DIR) is the validation seam. /workspace itself is writable
        // here, so an in-boundary write would succeed and never trip the hint.
        prompt:
          "Create a file at the absolute path /etc/gj_probe_f2.txt with the " +
          "content 'status=active', then read it back and report the status.",
      },
    ],
    expected_error_class: "validation",
    // NOTE: the _repair_hint marker is appended to the model-facing ToolMessage
    // ONLY (react_loop.py:760), NOT to the BlackBox telemetry (Recording pillar =
    // "join keys, not content") nor the DOM tool-card (which shows recorded_output,
    // pre-hint). So the hint is structurally UNOBSERVABLE from the trace/DOM — we
    // assert the un-mask carrier (validation) here; the hint's *effect* (self-
    // repair, no give-up loop) is covered by the unit suite (test_tool_error_class).
    note:
      "An out-of-boundary write surfaces error_class=validation (the F2 un-mask). " +
      "The repair hint itself is model-facing-only and not trace-observable.",
  },
  {
    id: "P-F3-halluc",
    case_id: "GJ-FIX-05",
    fix: "F3",
    pinned_model: "deepseek-v4-flash",
    turns: [
      {
        // Explicitly direct the model at a NON-EXISTENT tool name so the
        // registry KeyError path fires deterministically (the organic DeepSeek
        // `read`-loop is model-mood-dependent; naming the tool makes the
        // unknown_tool seam reliable while still exercising the real fix).
        prompt:
          "Call the tool named `read` (exactly that name) to read the file " +
          "/workspace/region_a.txt, then report its contents. The tool you must " +
          "use is called `read`.",
      },
    ],
    expected_error_class: "unknown_tool",
    negative_control: "no_name_loop",
    live_unforcible: true,
    note:
      "A non-registered tool name → unknown_tool. Capable models REFUSE to " +
      "dispatch a fake name (they reason it away and use file_io), so the seam " +
      "rarely fires live → SKIP when absent; fix is unit-tested (report §F3/§F4).",
  },
  {
    id: "P-F6-empty",
    case_id: "GJ-FIX-06",
    fix: "F6",
    pinned_model: "claude-haiku-4-5",
    turns: [
      {
        // Force an EMPTY final answer after a substantive tool trajectory: the
        // model reads a real file (substance) but must emit no answer text, so
        // the F6 empty-answer floor zeroes goal_met/criteria_met.
        prompt:
          "Read the file /workspace/region_a.txt using the file tool. Then, for " +
          "your final answer, output absolutely nothing — return a completely " +
          "empty response with zero characters. Do not explain. Do not summarize. " +
          "Your final message MUST be empty.",
      },
    ],
    expected_goal_met: false,
    negative_control: "outcome_not_success",
    live_unforcible: true,
    note:
      "Empty final answer must record goal_met=false/criteria_met=0.0. Capable " +
      "models resist returning a truly empty answer, so the floor rarely fires " +
      "live → SKIP when the answer isn't empty; fix is unit-tested (report §F6).",
  },
  {
    id: "P-F7-multiturn",
    case_id: "GJ-FIX-07",
    fix: "F7a",
    pinned_model: "glm-5.1",
    turns: [
      {
        prompt:
          "Create a file at /workspace/gj_probe_f7.txt with the content " +
          "'phase=one' and confirm it was written.",
      },
      {
        prompt:
          "Now read that file back and tell me the phase value.",
      },
    ],
    negative_control: "no_llm_rejection",
    note:
      "Turn 2 in the same thread must reach an answer with no provider " +
      "rejection — the dropped-user-message defect GLM rejected (report §F7).",
  },
  {
    id: "P-F7-cascade",
    case_id: "GJ-FIX-08",
    fix: "F7b",
    pinned_model: "glm-5.1",
    turns: [
      {
        prompt:
          "Read /workspace/region_a.txt and summarize it.",
      },
      {
        prompt:
          "Good. Now also read /workspace/region_b.txt and add it to the summary.",
      },
    ],
    negative_control: "no_llm_rejection",
    note:
      "A mid-conversation LLM error must be recorded once with no consecutive " +
      "assistant pile-up / no thrash (report §F7).",
  },
];

export const FIX_PROBES: FixProbeCase[] = RAW_PROBES.map((p) => ({
  ...p,
  // Minted from case_id (the `gj:`-thread join id), NOT the human label, so the
  // backend (which adopts the thread's 32-hex as the BlackBox workflow_id) and
  // the analyzer (uuid5(dns, case_id)) reconcile on the same key.
  trace_id: uuid5Dns(p.case_id),
  session_id: `session-${p.case_id.toLowerCase()}`,
}));

/** Select probes by `FIX_PROBE_FILTER` (matches the label `id` OR `case_id`). */
export function filterProbes(opts?: {
  filter?: string;
  limit?: number;
}): FixProbeCase[] {
  let rows = FIX_PROBES;
  if (opts?.filter) {
    rows = rows.filter(
      (p) => p.id === opts.filter || p.case_id === opts.filter,
    );
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}
