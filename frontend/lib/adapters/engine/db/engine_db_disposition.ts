/**
 * Exhaustive per-method disposition for `EngineDb` (coach-v3 FR-A4 / §2).
 *
 * Every interface method resolves to exactly one of:
 *   - `fine` — thin `/api/engine/db/<method>` route (callable from HttpEngineDb)
 *   - `server-only` — no route; HttpEngineDb throws `EngineRepoError("server-only method")`
 *
 * Coarse carriers (dashboard/summary/…) aggregate reads for chattiness; they do
 * not remove the fine-grained disposition for repo call sites that still need
 * a single-method fetch after the atomic swap.
 */

export type EngineDbMethodDisposition = "fine" | "server-only";

/** The 32 EngineDb methods + disposition. Order matches plan §2 (+ FR-E4). */
export const ENGINE_DB_DISPOSITION = {
  listSkillState: "fine",
  listSkills: "fine",
  getSkillByKey: "fine",
  listSkillIds: "fine",
  nextReviewedQuestion: "fine",
  getQuestion: "fine",
  insertQuestion: "server-only",
  listReviewedHints: "fine",
  insertHint: "server-only",
  listReviewedTestItems: "fine",
  insertTestItem: "server-only",
  getTestBlueprint: "fine",
  insertTestBlueprint: "server-only",
  insertSession: "fine",
  getSession: "fine",
  patchSessionClose: "fine",
  listClosedSessionsByLearner: "fine",
  setSessionCurrentQuestion: "fine",
  getNewestOpenSession: "fine",
  insertAttempt: "fine",
  listMisses: "fine",
  // FR-E4: only `GET /api/engine/next` needs this cross-session projection.
  listAlreadyCorrectQuestionIds: "server-only",
  listSessionQuestionIds: "fine",
  listSessionAttempts: "fine",
  listSessionSkillIds: "fine",
  accuracyRowsBySkill: "fine",
  getSkillState: "fine",
  upsertSkillState: "fine",
  getContentString: "fine",
  listContentStrings: "fine",
  getTutorial: "fine",
  listProgressPoints: "fine",
} as const satisfies Record<string, EngineDbMethodDisposition>;

export type EngineDbMethodName = keyof typeof ENGINE_DB_DISPOSITION;

export const SERVER_ONLY_ENGINE_DB_METHODS = (
  Object.entries(ENGINE_DB_DISPOSITION) as Array<
    [EngineDbMethodName, EngineDbMethodDisposition]
  >
)
  .filter(([, d]) => d === "server-only")
  .map(([m]) => m);

export const FINE_ENGINE_DB_METHODS = (
  Object.entries(ENGINE_DB_DISPOSITION) as Array<
    [EngineDbMethodName, EngineDbMethodDisposition]
  >
)
  .filter(([, d]) => d === "fine")
  .map(([m]) => m);
