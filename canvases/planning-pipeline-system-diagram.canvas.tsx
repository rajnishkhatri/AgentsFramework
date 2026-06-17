import {
  Callout,
  CollapsibleSection,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Swatch,
  Table,
  Text,
} from "cursor/canvas";

const SPINE_ROWS = [
  ["1", "START", "ingress", ""],
  ["2", "guard_input", "ingress", "InputGuardrail"],
  ["3", "route", "plan", "depth + T1 plan + task understanding"],
  ["4", "supervisor | call_llm", "execute", "_route_to_supervisor"],
  ["5", "worker -> join", "execute", "T3 fan-out only"],
  ["6", "call_llm <-> execute_tool", "execute", "ReAct loop"],
  ["7", "evaluate", "eval", "synthesis + keyword + GoalJudge"],
  ["8", "reflect | reasoning_recap", "exit", "_should_continue_or_escalate"],
  ["9", "END", "exit", ""],
];

const DEPTH_ROWS = [
  ["L0", "1", "simple-initial-task; post-tool-synthesis forced", "never (_route_to_supervisor -> direct)", "no", "no"],
  ["L1", "3", "complexity_score >= 2 or L1 floors", "yes if 2+ plan steps + flag", "yes", "yes (open todos, short answer)"],
  ["L2", "5", "complexity_score >= 3 or incident-narrative", "yes if 2+ plan steps + flag", "yes", "yes + branch coverage >= 60%"],
];

const SUPERVISOR_TEMPLATES = [
  ["independent-branches: LLM proposed parallelizable branches", "fan_out", "Structure check passed"],
  ["not-independent: structure check overrides model optimism", "decline", "LLM wanted fan-out; deterministic veto"],
  ["sequential-dependent: T1 plan steps reference prior outputs", "decline", "GAIA guard - explicit dependencies"],
];

const LLM_INVENTORY = [
  ["1", "guard_input", "InputGuardrail", "input_guardrail.j2", "fast", "guardrail", "always step 0"],
  ["2", "route step-0", "PlanGenerator", "plan_builder_prompt.j2", "fast", "(plan gen)", "plan_source shadow/generated"],
  ["3", "route step-0", "TaskUnderstandingGenerator", "task_understanding_prompt.j2", "fast", "task_understanding", "success_conditions_source"],
  ["4", "supervisor", "plan_delegations", "supervisor_decompose.j2", "default", "-", "T3 + L1/L2 + plan_source=generated"],
  ["5", "call_llm", "ReAct loop", "system + planning_instructions", "routed", "call_llm", "each turn"],
  ["6", "worker", "DelegationDispatcher", "delegation_worker_system_prompt.j2", "worker", "-", "T3 fan_out per branch"],
  ["7", "join", "join synthesizer", "fanout_join.j2", "fast/main", "-", "T3 after workers"],
  ["8", "evaluate", "GoalJudge", "goal_judge_system_prompt.j2", "fast", "goal_judge", "goal_judge_enabled"],
  ["9", "reflect", "generate_reflection", "inline critique prompt", "fast", "-", "T2 failed/partial + budget"],
  ["10", "reasoning_recap", "_reasoning_recap_impl", "reasoning_recap.j2", "fast", "-", "done; skip if < 2 tools"],
];

const EVAL_FLOW = [
  "final_answer from messages",
  "validate_synthesis (L1/L2 depth-aware checks)",
  "evaluate_task_outcome (keyword heuristic)",
  "GoalJudge.evaluate when goal_judge_enabled (best-effort overlay)",
  "optional success->partial downgrade when goal_judge_downgrade_enabled",
  "persist last_task_outcome + last_unmet_conditions",
  "_should_continue_or_escalate -> continue | reflect | done",
];

const REFLEXION_TRIGGERS = [
  "base _should_continue returns done (terminal turn)",
  "reflexion_enabled == true",
  "decide_escalation -> escalate because failed/partial verdict OR D3 prose_repeat",
  "len(reflections) < max_reflexion_attempts",
  "NOT depth-gated: L0 tasks can reflex",
];

export default function PlanningPipelineSystemDiagramCanvas() {
  return (
    <Stack gap={24}>
      <Stack gap={8}>
        <H1>Planning Pipeline System Diagram</H1>
        <Text tone="secondary">
          Backend runtime reference for orchestration/react_loop.py. Planning depth L0/L1/L2 is
          orthogonal to pipeline tiers T1/T2/T3.
        </Text>
        <Row gap={8}>
          <Pill>Architecture reference</Pill>
          <Pill>Backend only</Pill>
          <Pill>Source: react_loop.py</Pill>
        </Row>
      </Stack>

      <Callout tone="info" title="Two orthogonal axes">
        <Text>
          L0/L1/L2 (select_planning_depth) controls plan granularity and synthesis strictness.
          T1/T2/T3 (plan_source, reflexion_enabled, t3_fanout_enabled) are additive mechanisms on
          the same StateGraph spine.
        </Text>
      </Callout>

      <CollapsibleSection title="Overview - StateGraph spine" defaultOpen leading={<Swatch color="blue" />}>
        <Table
          headers={["#", "Node", "Phase", "Notes"]}
          rows={SPINE_ROWS}
          striped
        />
      </CollapsibleSection>

      <CollapsibleSection title="Route deep-dive - L0/L1/L2 + T1" count={3} leading={<Swatch color="green" />}>
        <Stack gap={12}>
          <Text size="small" tone="secondary">
            Planning is folded into route_node (no separate planner_node). Step-0 artifacts memoized per task_id.
          </Text>
          <Table
            headers={["Depth", "Max steps", "Selection", "T3 eligible", "Reflexion", "Synthesis checks"]}
            rows={DEPTH_ROWS}
            striped
          />
          <H2>T1 plan flow in route_node</H2>
          <Text>
            build_plan_artifact (floor) then PlanGenerator when plan_source is shadow or generated.
            Replan when plan_is_stale(last_tool_result) increments replan_count.
          </Text>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="T3 fan-out - supervisor, worker, join" count={3} leading={<Swatch color="purple" />}>
        <Stack gap={12}>
          <Text size="small" tone="secondary">
            Gate: t3_fanout_enabled AND planning_depth != L0 AND len(ordered_steps) {"\u003e="} 2. Real decline
            decision in plan_delegations + validate_independence.
          </Text>
          <Table
            headers={["Supervisor rationale template", "Decision", "Meaning"]}
            rows={SUPERVISOR_TEMPLATES}
            striped
          />
          <Row gap={16}>
            <Stack gap={4}>
              <Text weight="semibold">worker</Text>
              <Text size="small">Receives branch objective only (not full task_input)</Text>
              <Text size="small" tone="tertiary">delegation_worker_system_prompt.j2</Text>
            </Stack>
            <Stack gap={4}>
              <Text weight="semibold">join</Text>
              <Text size="small">Receives task_input + all worker_results</Text>
              <Text size="small" tone="tertiary">fanout_join.j2 - then evaluate (GoalJudge on joined answer)</Text>
            </Stack>
          </Row>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="Evaluation + GoalJudge + T2 reflexion" count={2} leading={<Swatch color="orange" />}>
        <Stack gap={12}>
          <H2>Terminal evaluate path</H2>
          <Stack gap={6}>
            {EVAL_FLOW.map((line, i) => (
              <Row gap={8}>
                <Pill size="sm">{i + 1}</Pill>
                <Text size="small">{line}</Text>
              </Row>
            ))}
          </Stack>
          <H2>Success conditions priority</H2>
          <Text size="small">
            1. task_understanding.success_conditions (generated or user_edited) then 2. plan_artifact
            floor.
          </Text>
          <H2>T2 reflexion triggers (_should_continue_or_escalate)</H2>
          <Stack gap={4}>
            {REFLEXION_TRIGGERS.map((line) => (
              <Text size="small">- {line}</Text>
            ))}
          </Stack>
        </Stack>
      </CollapsibleSection>

      <CollapsibleSection title="LLM call inventory" count={10} leading={<Swatch color="yellow" />} defaultOpen>
        <Table
          headers={["#", "Node", "Component", "Prompt", "Tier", "eval_capture", "Gate"]}
          rows={LLM_INVENTORY}
          striped
          stickyHeader
        />
      </CollapsibleSection>

      <Text size="small" tone="tertiary">
        Full Mermaid + SVG: docs/Architectures/PLANNING_PIPELINE_SYSTEM_DIAGRAM.md
      </Text>
    </Stack>
  );
}
