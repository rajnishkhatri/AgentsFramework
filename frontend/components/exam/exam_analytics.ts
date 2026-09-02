/**
 * Pure exam analytics read model (W2-3 / FR-30–33).
 *
 * `ExamRunItem[] + ExamSection[] + finalized attempts → ExamAnalytics`.
 * Recommendation rules are a data table (rule id → predicate → evidence) so
 * adding a rule is a row, not a branch. Does not grade — consumes persisted
 * `correct` on finalized items only (reducer leaves `correct` null until finish).
 */

import type {
  ExamAnalytics,
  ExamFacet,
  ExamFacetKind,
  ExamFacetLabel,
  ExamPacing,
  ExamQuadrants,
  ExamQuestion,
  ExamRecommendation,
  ExamRecommendationRule,
  ExamRunItem,
  ExamSection,
  ExamSectionAttempt,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";

export const LABEL_MIN_ITEMS = 5;
export const STRENGTH_ACC = 0.8;
export const WEAKNESS_ACC = 0.6;
export const PACING_TRAILING_MIN = 3;
export const CARELESS_FAST_WRONG_SHARE = 0.3;

const FINISHED: ReadonlySet<ExamSectionAttempt["status"]> = new Set([
  "submitted",
  "expired",
]);

const FACET_KINDS: readonly ExamFacetKind[] = [
  "subject",
  "category",
  "skill",
  "passage",
  "difficulty",
];

export type ExamAnalyticsInput = {
  learnerId: string;
  runId: string | null;
  items: readonly ExamRunItem[];
  sections: readonly ExamSection[];
  attempts: readonly ExamSectionAttempt[];
};

export type RuleEvidence = {
  facet_ref: string;
  evidence: string;
};

export type RuleContext = {
  facets: readonly ExamFacet[];
  pacing: readonly ExamPacing[];
  items: readonly ExamRunItem[];
};

export type ExamAnalyticsRule = {
  id: ExamRecommendationRule;
  priority: number;
  applies: (ctx: RuleContext) => readonly RuleEvidence[];
};

type BoundRow = {
  runId: string;
  sectionCode: ExamSectionCode;
  question: ExamQuestion;
  dwellMs: number;
  correct: boolean | null;
  speed: "fast" | "slow" | null;
};

type FacetAcc = {
  kind: ExamFacetKind;
  key: string;
  items: number;
  correct: number;
  unanswered: number;
  dwellSum: number;
  quadrants: ExamQuadrants;
};

export const RULES: readonly ExamAnalyticsRule[] = [
  {
    id: "pacing",
    priority: 1,
    applies: (ctx) =>
      ctx.pacing
        .filter((p) => p.trailing_unanswered >= PACING_TRAILING_MIN)
        .map((p) => ({
          facet_ref: `subject:${p.section_code}`,
          evidence: `${p.trailing_unanswered} trailing unanswered in ${p.section_code}`,
        })),
  },
  {
    id: "careless",
    priority: 2,
    applies: (ctx) =>
      ctx.facets.flatMap((f) => {
        if (f.kind !== "subject" || f.quadrants === null) return [];
        const wrong = f.quadrants.fast_wrong + f.quadrants.slow_wrong;
        if (wrong === 0) return [];
        const share = f.quadrants.fast_wrong / wrong;
        if (share < CARELESS_FAST_WRONG_SHARE) return [];
        return [
          {
            facet_ref: refOf(f),
            evidence: `fast_wrong ${f.quadrants.fast_wrong}/${wrong} of wrong`,
          },
        ];
      }),
  },
  {
    id: "knowledge_gap",
    priority: 3,
    applies: (ctx) =>
      ctx.facets.flatMap((f) => {
        if (f.label !== "weakness" || f.quadrants === null) return [];
        if (!slowWrongMajority(f.quadrants)) return [];
        return [
          {
            facet_ref: refOf(f),
            evidence: `weakness ${refOf(f)} with slow_wrong majority`,
          },
        ];
      }),
  },
  {
    id: "revise_flagged",
    priority: 4,
    applies: (ctx) => {
      const flaggedWrong = ctx.items.filter(
        (i) => i.flagged_in_section && i.correct === false,
      );
      if (flaggedWrong.length === 0) return [];
      const first = [...flaggedWrong].sort(compareItem)[0];
      if (first === undefined) {
        throw new Error("revise_flagged: non-empty flaggedWrong with no sort head");
      }
      return [
        {
          facet_ref: `subject:${first.section_code}`,
          evidence: `${flaggedWrong.length} flagged and wrong`,
        },
      ];
    },
  },
];

export function examAnalytics(input: ExamAnalyticsInput): ExamAnalytics {
  const attempts = input.attempts.filter((a) => {
    if (!FINISHED.has(a.status)) return false;
    if (input.runId !== null && a.run_id !== input.runId) return false;
    return true;
  });
  const itemByQ = new Map<string, ExamRunItem>();
  for (const item of input.items) {
    const key = `${item.run_id}:${item.section_code}:${item.question_id}`;
    itemByQ.set(key, item);
  }

  const rows: BoundRow[] = [];
  const persistedItems: ExamRunItem[] = [];
  for (const attempt of attempts) {
    const section = sectionForAttempt(attempt, input.sections, input.items);
    if (section === undefined) continue; // no form metadata — cannot facet
    for (const question of section.questions) {
      const item = itemByQ.get(
        `${attempt.run_id}:${attempt.section_code}:${question.id}`,
      );
      rows.push({
        runId: attempt.run_id,
        sectionCode: attempt.section_code,
        question,
        // Missing item row = never flushed / never answered (G9), not a
        // fabricated letter or dwell sample.
        dwellMs: item?.dwell_ms ?? 0,
        correct: item?.correct ?? null,
        speed: null,
      });
      if (item !== undefined) persistedItems.push(item);
    }
  }

  const medians = new Map<string, number | null>();
  for (const attempt of attempts) {
    const key = `${attempt.run_id}:${attempt.section_code}`;
    const dwells = rows
      .filter((r) => r.runId === attempt.run_id && r.sectionCode === attempt.section_code)
      .map((r) => r.dwellMs);
    medians.set(key, medianDwell(dwells));
  }

  for (const row of rows) {
    const median = medians.get(`${row.runId}:${row.sectionCode}`) ?? null;
    row.speed = classifySpeed(row.dwellMs, median);
  }

  const buckets = new Map<string, FacetAcc>();
  for (const row of rows) {
    for (const { kind, key } of facetKeys(row)) {
      addToFacet(buckets, kind, key, row);
    }
  }

  const facets = [...buckets.values()]
    .map(toFacet)
    .sort((a, b) => {
      const kind = FACET_KINDS.indexOf(a.kind) - FACET_KINDS.indexOf(b.kind);
      return kind !== 0 ? kind : a.key.localeCompare(b.key);
    });

  const pacing = attempts
    .filter((a) => sectionForAttempt(a, input.sections, input.items) !== undefined)
    .map((a) =>
      toPacing(
        a,
        rows.filter((r) => r.runId === a.run_id && r.sectionCode === a.section_code),
        medians.get(`${a.run_id}:${a.section_code}`) ?? null,
      ),
    );

  const ctx: RuleContext = { facets, pacing, items: persistedItems };
  const recommendations: ExamRecommendation[] = RULES.flatMap((rule) =>
    rule.applies(ctx).map((ev) => ({
      rule: rule.id,
      facet_ref: ev.facet_ref,
      evidence: ev.evidence,
      priority: rule.priority,
    })),
  ).sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.facet_ref.localeCompare(b.facet_ref);
  });

  return {
    scope: { learner_id: input.learnerId, run_id: input.runId },
    facets,
    pacing,
    recommendations,
  };
}

function sectionForAttempt(
  attempt: ExamSectionAttempt,
  sections: readonly ExamSection[],
  items: readonly ExamRunItem[],
): ExamSection | undefined {
  const candidates = sections.filter((s) => s.code === attempt.section_code);
  if (candidates.length === 0) return undefined;
  const ids = new Set(
    items
      .filter(
        (i) =>
          i.run_id === attempt.run_id && i.section_code === attempt.section_code,
      )
      .map((i) => i.question_id),
  );
  if (ids.size === 0) return candidates[0];
  return (
    candidates.find((s) => s.questions.some((q) => ids.has(q.id))) ??
    candidates[0]
  );
}

function facetKeys(row: BoundRow): readonly { kind: ExamFacetKind; key: string }[] {
  const keys: { kind: ExamFacetKind; key: string }[] = [
    { kind: "subject", key: row.sectionCode },
    { kind: "difficulty", key: String(row.question.difficulty) },
  ];
  if (row.question.reporting_category) {
    keys.push({ kind: "category", key: row.question.reporting_category });
  }
  if (row.question.skill_id) {
    keys.push({ kind: "skill", key: row.question.skill_id });
  }
  if (row.question.passage) {
    keys.push({ kind: "passage", key: row.question.passage });
  }
  return keys;
}

function addToFacet(
  buckets: Map<string, FacetAcc>,
  kind: ExamFacetKind,
  key: string,
  row: BoundRow,
): void {
  const id = `${kind}:${key}`;
  let acc = buckets.get(id);
  if (acc === undefined) {
    acc = {
      kind,
      key,
      items: 0,
      correct: 0,
      unanswered: 0,
      dwellSum: 0,
      quadrants: {
        fast_right: 0,
        fast_wrong: 0,
        slow_right: 0,
        slow_wrong: 0,
      },
    };
    buckets.set(id, acc);
  }
  acc.items += 1;
  acc.dwellSum += row.dwellMs;
  if (row.correct === null) acc.unanswered += 1;
  if (row.correct === true) acc.correct += 1;
  if (row.correct !== null && row.speed !== null) {
    const quad =
      row.speed === "fast"
        ? row.correct
          ? "fast_right"
          : "fast_wrong"
        : row.correct
          ? "slow_right"
          : "slow_wrong";
    acc.quadrants[quad] += 1;
  }
}

function toFacet(acc: FacetAcc): ExamFacet {
  const accuracy = acc.items === 0 ? null : acc.correct / acc.items;
  const mean = acc.items === 0 ? null : acc.dwellSum / acc.items;
  const qTotal =
    acc.quadrants.fast_right +
    acc.quadrants.fast_wrong +
    acc.quadrants.slow_right +
    acc.quadrants.slow_wrong;
  return {
    kind: acc.kind,
    key: acc.key,
    items: acc.items,
    correct: acc.correct,
    unanswered: acc.unanswered,
    accuracy,
    mean_dwell_ms: mean,
    // No quadrant-classified items ⇒ median was undefined for every source row.
    quadrants: qTotal === 0 ? null : acc.quadrants,
    label: labelOf(acc.items, acc.unanswered, accuracy),
  };
}

function labelOf(
  items: number,
  unanswered: number,
  accuracy: number | null,
): ExamFacetLabel {
  // All-blank is a pacing story, not a knowledge label (spec §6).
  if (items < LABEL_MIN_ITEMS || unanswered === items || accuracy === null) {
    return "insufficient_data";
  }
  if (accuracy >= STRENGTH_ACC) return "strength";
  if (accuracy <= WEAKNESS_ACC) return "weakness";
  return "insufficient_data";
}

function toPacing(
  attempt: ExamSectionAttempt,
  rows: readonly BoundRow[],
  median: number | null,
): ExamPacing {
  let unanswered = 0;
  let trailing = 0;
  let stillTrailing = true;
  let over2x = 0;
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    if (row === undefined) continue;
    if (row.correct === null) unanswered += 1;
    if (stillTrailing && row.correct === null) trailing += 1;
    else stillTrailing = false;
  }
  if (median !== null) {
    const cap = 2 * median;
    for (const row of rows) {
      if (row.dwellMs > cap) over2x += 1;
    }
  }
  return {
    section_code: attempt.section_code,
    unanswered,
    trailing_unanswered: trailing,
    time_remaining_ms_at_submit: attempt.time_remaining_ms_at_submit,
    pct_over_2x_median_dwell:
      median === null || rows.length === 0 ? null : over2x / rows.length,
  };
}

function medianDwell(dwells: readonly number[]): number | null {
  if (dwells.length < 2) return null; // spec §6: one item → undefined
  if (dwells.every((d) => d === 0)) return null; // spec §6: all dwell 0
  const sorted = [...dwells].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[mid] ?? null;
  }
  const lo = sorted[mid - 1];
  const hi = sorted[mid];
  if (lo === undefined || hi === undefined) return null;
  return (lo + hi) / 2;
}

function classifySpeed(
  dwellMs: number,
  median: number | null,
): "fast" | "slow" | null {
  if (median === null) return null;
  return dwellMs < median ? "fast" : "slow";
}

function slowWrongMajority(q: ExamQuadrants): boolean {
  const total = q.fast_right + q.fast_wrong + q.slow_right + q.slow_wrong;
  if (total === 0) return false;
  return q.slow_wrong > total / 2;
}

function refOf(f: Pick<ExamFacet, "kind" | "key">): string {
  return `${f.kind}:${f.key}`;
}

function compareItem(a: ExamRunItem, b: ExamRunItem): number {
  return (
    a.run_id.localeCompare(b.run_id) ||
    a.section_code.localeCompare(b.section_code) ||
    a.ordinal - b.ordinal
  );
}
