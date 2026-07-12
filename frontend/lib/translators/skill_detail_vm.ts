/**
 * skill_detail_vm — compose LessonContext + Tutorial → ordered BlockVM[] (E1a).
 *
 * Pure T1 translator. Holds the context recipe map (§5.1) and role→token
 * resolution (§2.4). Block order/zone/role are render-time outputs — never
 * read from a persisted blocks[] array (FR-8 / D5).
 *
 * Honest-null: a recipe tag with no backing data is skipped (FR-9), never an
 * empty container. accuracyStat self-omits when no real accuracy data (FR-16).
 *
 * Imports wire/ + select_lesson_context types only. No I/O, no React, no SDK.
 */

import type {
  AnnotatedExample,
  CompletionTry,
  Skill,
  SkillState,
  Tutorial,
  WorkedExample,
} from "../wire/engine_entities";
import type { LessonContext } from "./select_lesson_context";

export type BlockTag =
  | "ground"
  | "pitfall"
  | "question"
  | "selfExplainPrompt"
  | "rule"
  | "workedExample"
  | "completionTry"
  | "misconceptionCallout"
  | "annotatedExample"
  | "dueChecklist"
  | "accuracyStat"
  | "coachEntry";

export type BlockZone = "main" | "rail";

export type BlockRole =
  | "neutral"
  | "accent"
  | "accentDashed"
  | "accentSoft"
  | "warning"
  | "success";

export interface RoleTint {
  readonly border: string;
  readonly background: string;
  readonly ink: string;
  readonly borderStyle: "solid" | "dashed";
}

/** Role → CSS-token expressions (design §2.4). Presentational resolution. */
export const ROLE_TINT: Readonly<Record<BlockRole, RoleTint>> = {
  neutral: {
    border: "var(--color-border)",
    background: "var(--color-surface)",
    ink: "var(--color-muted)",
    borderStyle: "solid",
  },
  accent: {
    border: "color-mix(in oklab,var(--accent) 35%,var(--color-border))",
    background: "color-mix(in oklab,var(--accent) 6%,var(--color-bg))",
    ink: "color-mix(in oklab,var(--accent) 55%,var(--color-fg))",
    borderStyle: "solid",
  },
  accentDashed: {
    border: "color-mix(in oklab,var(--accent) 48%,var(--color-border))",
    background: "transparent",
    ink: "color-mix(in oklab,var(--accent) 55%,var(--color-fg))",
    borderStyle: "dashed",
  },
  accentSoft: {
    border: "color-mix(in oklab,var(--accent) 30%,var(--color-border))",
    background: "color-mix(in oklab,var(--accent) 5%,var(--color-bg))",
    ink: "color-mix(in oklab,var(--accent) 55%,var(--color-fg))",
    borderStyle: "solid",
  },
  warning: {
    border: "color-mix(in oklab,var(--color-warning) 38%,var(--color-border))",
    background: "color-mix(in oklab,var(--color-warning) 9%,var(--color-bg))",
    ink: "var(--color-warning)",
    borderStyle: "solid",
  },
  success: {
    border: "var(--color-border)",
    background: "var(--color-surface)",
    ink: "var(--color-success)",
    borderStyle: "solid",
  },
};

export type BlockVM =
  | {
      readonly tag: "ground";
      readonly zone: "main";
      readonly role: "neutral";
      readonly tint: RoleTint;
      readonly order: number;
      readonly opener: boolean;
      readonly body: string;
    }
  | {
      readonly tag: "pitfall";
      readonly zone: "main";
      readonly role: "warning";
      readonly tint: RoleTint;
      readonly order: number;
      readonly framing: "mid" | "parting";
      readonly body: string;
    }
  | {
      readonly tag: "question";
      readonly zone: "main";
      readonly role: "accent";
      readonly tint: RoleTint;
      readonly order: number;
      readonly body: string;
    }
  | {
      readonly tag: "selfExplainPrompt";
      readonly zone: "main";
      readonly role: "accentSoft";
      readonly tint: RoleTint;
      readonly order: number;
      readonly prompt: string;
    }
  | {
      readonly tag: "rule";
      readonly zone: "main";
      readonly role: "success";
      readonly tint: RoleTint;
      readonly order: number;
      readonly body: string;
      readonly examples: readonly string[];
    }
  | {
      readonly tag: "workedExample";
      readonly zone: "main";
      readonly role: "accent";
      readonly tint: RoleTint;
      readonly order: number;
      readonly example: WorkedExample;
    }
  | {
      readonly tag: "completionTry";
      readonly zone: "main";
      readonly role: "accentDashed";
      readonly tint: RoleTint;
      readonly order: number;
      readonly tryItem: CompletionTry;
      readonly skillId: string;
    }
  | {
      readonly tag: "misconceptionCallout";
      readonly zone: "main";
      readonly role: "warning";
      readonly tint: RoleTint;
      readonly order: number;
      readonly eyebrow: string;
      readonly body: string;
    }
  | {
      readonly tag: "annotatedExample";
      readonly zone: "main";
      readonly role: "accent";
      readonly tint: RoleTint;
      readonly order: number;
      readonly examples: readonly AnnotatedExample[];
    }
  | {
      readonly tag: "dueChecklist";
      readonly zone: "rail";
      readonly role: "neutral";
      readonly tint: RoleTint;
      readonly order: number;
      readonly items: ReadonlyArray<{ readonly skillId: string; readonly name: string }>;
    }
  | {
      readonly tag: "coachEntry";
      readonly zone: "rail";
      readonly role: "accent";
      readonly tint: RoleTint;
      readonly order: number;
      readonly skillId: string;
      readonly skillName: string;
    };

export interface SkillDetailInputs {
  readonly context: LessonContext;
  readonly tutorial: Tutorial | null;
  readonly skill: Skill;
  /** Verbatim newest-due-miss tag, or null (tier-3 / no due miss). */
  readonly misconceptionTag: string | null;
  /** Whole due skills for the dueChecklist rail (returning). */
  readonly dueSkills: ReadonlyArray<{ readonly skillId: string; readonly name: string }>;
  /**
   * Real per-skill answer-accuracy. E1a: always null → accuracyStat self-omits
   * (FR-16 carve-out). When a follow-up supplies data, the block activates.
   */
  readonly accuracy: { readonly valuePct: number; readonly bars: readonly number[] } | null;
  readonly nowISO: string;
  readonly skillStates?: readonly SkillState[];
}

export interface SkillDetailVM {
  readonly context: LessonContext;
  readonly skillId: string;
  readonly skillName: string;
  readonly accentVar: string;
  readonly main: readonly BlockVM[];
  readonly rail: readonly BlockVM[];
  /** Honest empty when no reviewed tutorial (FR-3 / FR-18). */
  readonly empty: boolean;
}

/** Context → main-zone recipe tags (design §5.1). Order is NOT authored content. */
const MAIN_RECIPES: Readonly<Record<LessonContext, readonly BlockTag[]>> = {
  newSkill: [
    "ground",
    "pitfall",
    "question",
    "selfExplainPrompt",
    "rule",
    "workedExample",
    "completionTry",
  ],
  returning: ["misconceptionCallout", "annotatedExample", "rule"],
  refresher: ["rule", "annotatedExample", "pitfall"],
};

const RAIL_RECIPES: Readonly<Record<LessonContext, readonly BlockTag[]>> = {
  newSkill: ["accuracyStat"],
  returning: ["dueChecklist", "accuracyStat", "coachEntry"],
  refresher: ["accuracyStat"],
};

function resolveBlock(
  tag: BlockTag,
  order: number,
  inputs: SkillDetailInputs,
): BlockVM | null {
  const t = inputs.tutorial;
  switch (tag) {
    case "ground": {
      if (t?.ground_md == null || t.ground_md.trim() === "") return null;
      return {
        tag: "ground",
        zone: "main",
        role: "neutral",
        tint: ROLE_TINT.neutral,
        order,
        opener: true,
        body: t.ground_md,
      };
    }
    case "pitfall": {
      if (t?.pitfall_md == null || t.pitfall_md.trim() === "") return null;
      return {
        tag: "pitfall",
        zone: "main",
        role: "warning",
        tint: ROLE_TINT.warning,
        order,
        framing: inputs.context === "refresher" ? "parting" : "mid",
        body: t.pitfall_md,
      };
    }
    case "question": {
      if (t?.question_md == null || t.question_md.trim() === "") return null;
      return {
        tag: "question",
        zone: "main",
        role: "accent",
        tint: ROLE_TINT.accent,
        order,
        body: t.question_md,
      };
    }
    case "selfExplainPrompt": {
      if (t?.self_explain_prompt == null || t.self_explain_prompt.trim() === "")
        return null;
      return {
        tag: "selfExplainPrompt",
        zone: "main",
        role: "accentSoft",
        tint: ROLE_TINT.accentSoft,
        order,
        prompt: t.self_explain_prompt,
      };
    }
    case "rule": {
      if (t == null || t.body_md.trim() === "") return null;
      return {
        tag: "rule",
        zone: "main",
        role: "success",
        tint: ROLE_TINT.success,
        order,
        body: t.body_md,
        examples: t.examples,
      };
    }
    case "workedExample": {
      if (t?.worked_example == null) return null;
      return {
        tag: "workedExample",
        zone: "main",
        role: "accent",
        tint: ROLE_TINT.accent,
        order,
        example: t.worked_example,
      };
    }
    case "completionTry": {
      if (t?.completion_try == null) return null;
      return {
        tag: "completionTry",
        zone: "main",
        role: "accentDashed",
        tint: ROLE_TINT.accentDashed,
        order,
        tryItem: t.completion_try,
        skillId: inputs.skill.id,
      };
    }
    case "misconceptionCallout": {
      // FR-6c / FR-16b: untagged or no due miss → hide (no miss-count substitute).
      if (inputs.misconceptionTag == null || inputs.misconceptionTag.trim() === "")
        return null;
      return {
        tag: "misconceptionCallout",
        zone: "main",
        role: "warning",
        tint: ROLE_TINT.warning,
        order,
        eyebrow: `On your last miss · ${inputs.skill.name}`,
        body: inputs.misconceptionTag,
      };
    }
    case "annotatedExample": {
      if (t?.annotated_examples == null || t.annotated_examples.length === 0)
        return null;
      return {
        tag: "annotatedExample",
        zone: "main",
        role: "accent",
        tint: ROLE_TINT.accent,
        order,
        examples: t.annotated_examples,
      };
    }
    case "dueChecklist": {
      if (inputs.dueSkills.length === 0) return null;
      return {
        tag: "dueChecklist",
        zone: "rail",
        role: "neutral",
        tint: ROLE_TINT.neutral,
        order,
        items: inputs.dueSkills,
      };
    }
    case "accuracyStat": {
      // FR-16: self-omit when no real accuracy data (E1a carve-out).
      if (inputs.accuracy == null) return null;
      // Render path reserved for the follow-up; today always null.
      return null;
    }
    case "coachEntry": {
      return {
        tag: "coachEntry",
        zone: "rail",
        role: "accent",
        tint: ROLE_TINT.accent,
        order,
        skillId: inputs.skill.id,
        skillName: inputs.skill.name,
      };
    }
    default: {
      const _exhaustive: never = tag;
      return _exhaustive;
    }
  }
}

const TENSION_TAGS: ReadonlySet<BlockTag> = new Set([
  "pitfall",
  "misconceptionCallout",
]);

/**
 * GUARD-END-1 (AL-13 block layer): a self-contained lesson main zone must end
 * on a resolution, never on an unresolved tension block. Mutates `main` in
 * place: while the last block is a tension block AND no `rule` appears anywhere
 * before it, drop it. A parting tension block that FOLLOWS a `rule` (the
 * refresher exception) is retained, because the rule already resolved the beat.
 */
function enforceEndOnResolution(main: BlockVM[]): void {
  while (main.length > 0) {
    const last = main[main.length - 1]!;
    if (!TENSION_TAGS.has(last.tag)) return;
    const ruleAbove = main
      .slice(0, main.length - 1)
      .some((b) => b.tag === "rule");
    if (ruleAbove) return; // parting caution after the rule — permitted (FR-6d)
    main.pop();
  }
}

/**
 * Compose the skill-detail surface VM from selector output + recipe map.
 * Returns empty:true when tutorial is null (honest degrade, FR-3/FR-18).
 */
export function toSkillDetailVM(inputs: SkillDetailInputs): SkillDetailVM {
  const base = {
    context: inputs.context,
    skillId: inputs.skill.id,
    skillName: inputs.skill.name,
    accentVar: inputs.skill.accent_var,
  };

  if (inputs.tutorial == null) {
    return { ...base, main: [], rail: [], empty: true };
  }

  const mainTags = MAIN_RECIPES[inputs.context];
  const railTags = RAIL_RECIPES[inputs.context];

  const main: BlockVM[] = [];
  let order = 0;
  for (const tag of mainTags) {
    const block = resolveBlock(tag, order, inputs);
    if (block != null) {
      main.push(block);
      order += 1;
    }
  }

  // GUARD-END-1 (AL-13 block layer): the main zone must end on a resolution,
  // never on an unresolved tension block. A partial seed could otherwise leave
  // a `pitfall`/`misconceptionCallout` trailing with no `rule` above it — the
  // learner staring at a trap with no fix below. Drop such trailing tension
  // blocks. A parting `pitfall` AFTER `rule` (refresher, FR-6d) is retained.
  enforceEndOnResolution(main);

  const rail: BlockVM[] = [];
  let railOrder = 0;
  for (const tag of railTags) {
    const block = resolveBlock(tag, railOrder, inputs);
    if (block != null) {
      rail.push(block);
      railOrder += 1;
    }
  }

  return { ...base, main, rail, empty: false };
}

/** Recipe map exported for FR-8b type/order assertions (order from recipe, not data). */
export const __MAIN_RECIPES_FOR_TEST = MAIN_RECIPES;
