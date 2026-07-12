/**
 * toAccuracyVM — re-export from wire/ (E1b-D1).
 *
 * The reduce lives next to SkillAccuracyRow / AccuracyBySkill so adapters can
 * import it without violating Rule A3 (no translators/ imports). Kept here as
 * the L1 translator entrypoint used by unit tests and skill_detail comments.
 */

export { toAccuracyVM } from "../wire/engine_entities";
