"""Generic configuration consumed by any layer.

NO langgraph or langchain imports allowed.

ModelProfile describes an LLM model's capabilities and costs.
AgentConfig holds global agent-level configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ModelProfile(BaseModel):
    name: str
    litellm_id: str
    tier: str
    context_window: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    median_latency_ms: float = 1000


class AgentConfig(BaseModel):
    # Identity (E9): surfaced on TASK_STARTED so the trace answers "who did it?"
    # from the first event without a registry round-trip. The registry, when
    # present and verified, refines agent_facts_id to the resolved agent id.
    agent_name: str = "governance-agent"
    agent_version: str = "0.0.0"
    max_steps: int = 20
    max_cost_usd: float = 1.0
    default_model: str = "gpt-4o-mini"
    models: list[ModelProfile] = []
    tool_output_offload_threshold_chars: int = 4000
    tool_output_preview_chars: int = 400
    tool_result_history_limit: int = 100
    trajectory_compaction_token_threshold: int = 3000
    delegation_max_cost_usd: float = 0.5
    delegation_max_calls_per_task: int = 4
    no_progress_repeat_threshold: int = 3
    no_progress_hard_limit: int = 5
    # I2: enable the task-adaptive LLM-as-judge to overlay goal_met/criteria_met
    # onto TaskOutcome. Off by default so CI stays L2-pure (no live LLM); the
    # deterministic keyword heuristic is the fallback when disabled.
    goal_judge_enabled: bool = False
    # Stage 2 rollout: when True, a goal_met=False verdict may downgrade a
    # clean ``success`` outcome to ``partial`` (strictly success->partial).
    # Decoupled from goal_judge_enabled so the judge can run in shadow mode
    # (gather verdicts, change nothing) before the gate is enabled. Default
    # off — stays off until the gold-set production-enable gate is met.
    goal_judge_downgrade_enabled: bool = False
    # Phase 1 (T1 plan-and-execute): source of the route_node plan artifact.
    #   "deterministic" — regex ``build_plan_artifact`` (steady-state, default).
    #   "shadow"        — LLM plan is generated + captured for eval, but the
    #                     deterministic artifact is what the run consumes.
    #   "generated"     — LLM plan is consumed, with ``build_plan_artifact`` as
    #                     the floor on any parse/validation failure.
    # Default stays deterministic so CI is L2-pure (no live LLM) and steady
    # state is unchanged; promote on evidence (GoalJudge shadow->consume idiom).
    plan_source: Literal["deterministic", "shadow", "generated"] = "deterministic"
    # Phase 2 (T2 reflexion): enable the evaluate->reflect->route re-entry loop.
    # When True, a GoalJudge failed/partial verdict (or a D3 prose-thrash) below
    # the budget ceiling writes a verbal critique and re-enters the loop. Off by
    # default — the reflect edge exists in the graph but decide_reentry returns
    # "stop" until flipped, so CI/prod behavior is unchanged (shadow-first, same
    # discipline as plan_source). Promote on evidence.
    reflexion_enabled: bool = False
    # D1: reflexion budget ceiling. decide_reentry returns "stop" once
    # len(reflections) >= this, even on a failed verdict — bounds the loop so
    # it can never thrash (Reflexion, arxiv 2303.11366; thrash-bound sim guard).
    max_reflexion_attempts: int = 2
    # Phase 4 (T3 supervisor fan-out): enable the route->supervisor->worker->join
    # parallel-fan-out fork. When False, _route_to_supervisor always returns
    # "direct" → today's graph EXACTLY (the route->call_llm path is byte-identical).
    # Off by default — same shadow-first discipline as plan_source/reflexion;
    # promote only on parallel-workload evidence (plan §3.5a / §5: don't grow T3
    # without it). The decline decision still bounds fan-out even when enabled.
    t3_fanout_enabled: bool = False
    # T3 fault-injection hook for the stress corpus timing-fault rows. When True,
    # the worker node honors the magic objective tokens __FAULT_TIMEOUT__ /
    # __FAULT_SLOW__ (corpus §4.3a) to exercise the superstep-cancellation /
    # straggler paths. MUST stay OFF in prod — set only on the --tag stress
    # revision (plan §5 Risks: "fault-injection hook leaks to prod").
    fanout_fault_inject: bool = False
    # T3 per-branch wall-clock ceiling (seconds). asyncio.wait_for bounds each
    # worker so one slow/hung branch cannot stall the whole superstep; on timeout
    # the worker records a sentinel and survivors still synthesize.
    fanout_branch_timeout_s: float = 60.0
    # Governance carrier-gate enforcement (enforcement gate Phase 2). The inline
    # gate ALWAYS records a shadow carrier (Phase 1); this field decides whether a
    # missing-pillar gap also ACTS:
    #   "off"     — shadow only; the gap is recorded, nothing blocks (prod parity,
    #               the Phase-1 default; stays here until calibration justifies it).
    #   "raise"   — a gap raises CarrierGateViolation (dev / CI — fail loud so a
    #               seam defect is caught at the source).
    #   "degrade" — a gap is annotated loudly on the trace + run, never silent, but
    #               the run still completes (prod — degrade-not-block).
    # composition.py sets it from CARRIER_GATE_ENFORCE_ENABLED + AGENT_ENV
    # (dev→raise, prod→degrade); default OFF preserves shadow-first discipline —
    # promote only on Phase-1 calibration evidence + explicit approval.
    carrier_gate_enforce_mode: Literal["off", "raise", "degrade"] = "off"
    # Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md): wire the
    # orphaned LongTermMemoryService into the loop. When True, route_node recalls
    # the user's relevant memories once per run and injects them into the system
    # prompt, and the run-end path stores a salient memory. Off by default —
    # shadow-first, same discipline as reflexion_enabled/t3_fanout_enabled: with
    # the flag OFF the loop is byte-identical to today (should_recall returns
    # False, no search/store, no carriers). Promote on a dev/stress revision; the
    # injected memory_service is still constructed at the composition root so the
    # graph shape is stable regardless of the flag.
    memory_enabled: bool = False
    # Phase 2 typed background auto-capture. When True (and memory_enabled), the
    # post-run autocapture seam runs the typed extractor and WRITES BACK the
    # proposed memories. Off by default — shadow-first: with the flag OFF the
    # extractor still proposes and the trace carries the proposal (so the eval
    # workstream has shadow traces), but NOTHING is stored. It flips to write-back
    # ONLY after the grounded-theory enable-policy clears on the frozen test split
    # (mirrors goal_judge: shadow -> dev-enable -> prod-enable; never iterate the
    # prompt on the test split). Independent of memory_enabled's recall path so
    # recall can ship before write-back.
    #
    # ENFORCEMENT: this flag is the operator's INTENT only. The composition root
    # (middleware/composition.py) routes it through the enable-policy GUARD
    # (services/governance/memory_enable_policy.py): write-back actually turns on
    # only when a passing, frozen-test-split calibration certificate
    # (MEMORY_AUTOCAPTURE_CERT) is also present. Flag-on-but-no-cert fails SAFE to
    # shadow. So flipping this alone in prod does NOT start storing — the gate is
    # machine-checked, not honour-system.
    memory_autocapture_enabled: bool = False
    # Hermes / memory-os adoption A2 (docs/research/memory/hermes_adoptions_design.md):
    # relevance floor on recall injection. render_recall_block drops a recalled
    # record whose backend relevance ``score`` is below this floor (cuts prompt
    # noise from weakly-related matches). 0.0 (default) = no floor, byte-identical
    # to today; a backend that attaches no score (InMemory) is unaffected. Only
    # bites against a scoring backend (Mem0) in prod. Calibrate (not guess) before
    # flipping on — shadow-measure via the memory_recall eval_capture, same
    # discipline as the goal-judge enable-policy.
    memory_recall_min_relevance: float = 0.0
    # Hermes / memory-os adoption A3: salience-tier provenance in the recall
    # block. A recalled record at/above this salience renders ``[confirmed]``,
    # below it ``[inferred]``; a record with no salience renders unmarked (the v1
    # deterministic store writes none → backward-compatible). Render-only; no
    # store change. Meaningful once typed-autocapture write-back is live.
    memory_authoritative_at: float = 0.8
    # Carrier-gate fault-injection hook (the LIVE gap-catch proof). When True, a
    # task whose input carries the magic token ``__DROP_CARRIER:<phase>__`` has the
    # required carrier for that phase SUPPRESSED before the gate checks it —
    # simulating the exact seam defect the gate exists to catch, so the enforce
    # path (alert carrier + raise/degrade) can be proven end-to-end on a live run.
    # MUST stay OFF in prod (same posture as fanout_fault_inject — a dedicated
    # tagged revision flips it; the magic token is inert without the flag).
    carrier_gate_fault_inject: bool = False
    # ─── C1 message-history compaction + B2 pinned-floor (design §9) ─────
    # All seven knobs default to "off / no-op" so prod is byte-identical when
    # the master flag is False: both seams (call_llm_node READ, evaluate_node
    # WRITE) early-return before any mask/fold/tail logic. Promote on evidence
    # via a tagged revision (same shadow-first discipline as plan_source,
    # reflexion_enabled, t3_fanout_enabled, memory_enabled).
    #
    # Master switch — when False the §5.1 fold and §5.2 mask are both inert.
    context_compact_messages_enabled: bool = False
    # Token-pressure trigger fraction. The WRITE seam folds when current tokens
    # cross ``compaction_trigger_tokens(profile.context_window, fraction)``.
    # Pin at/below the model's empirical Safe Turn Depth (§B2-R S1/S6) — an
    # eval task, not a guess. 0.6 is the §9 default.
    context_compact_trigger_fraction: float = 0.6
    # Mask fraction (§5.2): the READ seam clears tool-observation content
    # once the working set crosses this fraction of context_window. Pure
    # transient mask — never persisted into the checkpointer messages channel
    # at this default. 0.3 is the §9 default.
    context_observation_clear_fraction: float = 0.3
    # plan_fold_cutoff(keep_last_k=...). The number of step-blocks preserved
    # verbatim at the suffix; the prefix gets folded into the summary. 10 is
    # the §9 default — block-aware so an Interaction Block is never split.
    context_keep_last_k: int = 10
    # plan_observation_mask(mask_after_steps=...). Tool observations older than
    # the last M step-blocks have their ``content`` masked. M=10 is the §B1-R
    # R1 ablated optimum; do not flip without ablation evidence.
    context_mask_after_steps: int = 10
    # Cooldown between successive folds. The WRITE seam gates on
    # ``step_count - state.get("last_compaction_step", 0) >= cooldown_steps``
    # so two folds cannot stack inside a re-entry burst (Reflexion lap, T3
    # join). 5 is the §9 default.
    context_compact_cooldown_steps: int = 5
    # Tail-floor cadence (§5.2 / §B2-R S2/S5): when N > 0 and step_count % N == 0,
    # the READ seam appends ``build_constraint_floor(pinned)`` after existing
    # messages AND persists it append-only into the checkpointer messages
    # channel. The §7.3 checkpoint-privilege caveat applies — the persisted
    # tail puts constraint TEXT on a privileged store, so the ship default
    # (N=0) keeps the tail OFF and the checkpoint content-free. Promote only
    # on calibrated cache-hit-rate evidence (§B1-R R6 cost-negation tension).
    context_constraint_reinject_turns: int = 0
    # C2 Phase 8 (design §8.3) — caller-side sampling gate for the L2 shadow
    # fidelity judge. ``random() < context_compaction_fidelity_sample_rate``
    # wraps the ``await eval_capture.record(target="compaction_fidelity",
    # ...)`` call on COMMITTED folds. 0.0 = the gate fully suppresses L2
    # (prod-default until calibration earns the cost). NEW infra — no
    # sampler existed in-repo before this (Fix D); ``eval_capture.record()``
    # is a bare ``logger.info`` (``services/eval_capture.py:49``).
    context_compaction_fidelity_sample_rate: float = 0.0
    # Fix 1 (Phase-9 manual-probe root cause): when True, the fold floor and the
    # §5.2 tail reinjection harvest the operator's conversational pins from the
    # human views (``services.summarizer.extract_user_constraints``) and pass
    # them as the ``user_constraints`` arg to ``derive_pinned_floor`` — so a
    # free-text pin ("avoid destructive file tools") reaches the §B2-R must-not
    # floor. Default OFF: with this flag False both fold sites pass ``[]`` exactly
    # as before, keeping flag-OFF behaviour byte-identical.
    context_extract_user_constraints: bool = False


def compaction_trigger_tokens(context_window: int, fraction: float) -> int:
    """Token threshold above which the WRITE seam folds the message history.

    Pure helper (design §9). ``window * fraction`` truncated to int, floored
    at 1: a 0 trigger would compact on every step (``tokens >= 0`` is
    trivially true), so this floor keeps the trigger meaningful even when
    a degenerate ModelProfile.context_window or fraction lands on the call.
    """
    return max(1, int(context_window * fraction))


def default_fast_profile() -> ModelProfile:
    """Canonical fast-model profile used as fallback across the system."""
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )
