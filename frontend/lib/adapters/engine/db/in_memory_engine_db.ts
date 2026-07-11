/**
 * InMemoryEngineDb — the behavioral fake of `EngineDb`.
 *
 * A records-and-answers fake (not a mock of internal calls): it stores rows in
 * arrays/maps and answers queries the same way the live Drizzle seam does. It is
 * the L1/dev implementation — the conformance suite runs the repos against THIS
 * and (where a DB is available) the live seam, proving the repos depend only on
 * the narrow `EngineDb` contract.
 *
 * Seeding helpers (`seedSkills`, `seedQuestions`, `seedSkillStates`,
 * `seedContent`, `seedTutorial`, `seedProgress`) let tests stand up a
 * deterministic corpus without the live DB.
 */

import type {
  Attempt,
  Hint,
  ProgressPoint,
  Question,
  QuizSession,
  Skill,
  SkillState,
  TestBlueprint,
  TestItem,
  Tutorial,
} from "../../../wire/engine_entities";
import type { EngineDb, SessionClosePatch } from "./engine_db";

function skillStateKey(subject: string, skillId: string, learnerId: string): string {
  return `${subject}\0${skillId}\0${learnerId}`;
}

function contentKey(subject: string, key: string, locale: string): string {
  return `${subject}\0${key}\0${locale}`;
}

export class InMemoryEngineDb implements EngineDb {
  private skills: Skill[] = [];
  private questions = new Map<string, Question>();
  private hints = new Map<string, Hint>(); // key: `${question_id} ${rung}`
  private testItems = new Map<string, TestItem>();
  private testBlueprints = new Map<string, TestBlueprint>();
  private sessions = new Map<string, QuizSession>();
  private attempts: Attempt[] = [];
  private skillState = new Map<string, SkillState>();
  private content = new Map<string, string>();
  private tutorials = new Map<string, Tutorial>(); // key: subject\0skillId
  private progress: ProgressPoint[] = [];

  // --- seeding helpers (test/dev only) ---
  seedSkills(skills: Skill[]): void {
    this.skills.push(...skills.map((s) => ({ ...s })));
  }
  seedQuestions(questions: Question[]): void {
    for (const q of questions) this.questions.set(q.id, { ...q });
  }
  seedHints(hints: Hint[]): void {
    for (const h of hints) this.hints.set(`${h.question_id}\0${h.rung}`, { ...h });
  }
  seedTestItems(items: TestItem[]): void {
    for (const i of items) this.testItems.set(i.id, { ...i });
  }
  seedTestBlueprints(blueprints: TestBlueprint[]): void {
    for (const b of blueprints) this.testBlueprints.set(b.id, { ...b });
  }
  seedSkillStates(states: SkillState[]): void {
    // Test/dev only: stand up read fixtures for the read-only ports (ADR-0011
    // LearnerReadRepo) without going through the Scheduler write path.
    for (const s of states) {
      this.skillState.set(
        skillStateKey(s.subject, s.skill_id, s.learner_id),
        { ...s },
      );
    }
  }
  seedContent(subject: string, locale: string, map: Record<string, string>): void {
    for (const [k, v] of Object.entries(map)) {
      this.content.set(contentKey(subject, k, locale), v);
    }
  }
  seedTutorial(t: Tutorial): void {
    this.tutorials.set(`${t.subject}\0${t.skill_id}`, { ...t });
  }
  seedProgress(points: ProgressPoint[]): void {
    this.progress.push(...points.map((p) => ({ ...p })));
  }

  // --- skill ---
  async listSkills(subject: string): Promise<Skill[]> {
    return this.skills
      .filter((s) => s.subject === subject)
      .sort((a, b) => a.order - b.order)
      .map((s) => ({ ...s }));
  }
  async getSkillByKey(subject: string, key: string): Promise<Skill | null> {
    const s = this.skills.find((x) => x.subject === subject && x.key === key);
    return s ? { ...s } : null;
  }
  async listSkillIds(subject: string): Promise<string[]> {
    // Ordered by (order, id) to match the live seam's ORDER BY — a deterministic
    // seed order, so the seeded weakest-due pick is stable across both impls.
    return this.skills
      .filter((s) => s.subject === subject)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id))
      .map((s) => s.id);
  }

  // --- question (reviewed gate enforced here too — the fake must match the seam) ---
  async nextReviewedQuestion(
    subject: string,
    skillId: string,
    excludeIds?: readonly string[],
  ): Promise<Question | null> {
    // The served set (FR-9): skip these ids. A Set for O(1) membership; the
    // filter is a PRE-FILTER on top of the reviewed gate — an excluded id and
    // an unreviewed row are both simply not candidates (FR-12 gate untouched).
    const excluded = new Set(excludeIds ?? []);
    const candidates = [...this.questions.values()].filter(
      (q) =>
        q.subject === subject &&
        q.skill_id === skillId &&
        q.reviewed === true && // HARD GATE
        !excluded.has(q.id),
    );
    // Deterministic: lowest difficulty first, then id.
    candidates.sort((a, b) => a.difficulty - b.difficulty || a.id.localeCompare(b.id));
    const first = candidates[0];
    return first ? { ...first } : null;
  }
  async getQuestion(id: string): Promise<Question | null> {
    const q = this.questions.get(id);
    return q ? { ...q } : null;
  }
  async insertQuestion(q: Question): Promise<void> {
    this.questions.set(q.id, { ...q });
  }

  // --- hint (ADR-0014) ---
  async listReviewedHints(subject: string, questionId: string): Promise<Hint[]> {
    return [...this.hints.values()]
      .filter(
        (h) =>
          h.subject === subject &&
          h.question_id === questionId &&
          h.reviewed === true, // HARD GATE (FR-12)
      )
      .sort((a, b) => a.rung - b.rung)
      .map((h) => ({ ...h }));
  }
  async insertHint(h: Hint): Promise<void> {
    const key = `${h.question_id} ${h.rung}`;
    if (this.hints.has(key)) {
      throw new Error(
        `duplicate hint rung: (${h.question_id}, ${h.rung}) already exists`,
      );
    }
    this.hints.set(key, { ...h });
  }

  // --- test_item (ADR-0015; same pushed-down reviewed gate as question) ---
  async listReviewedTestItems(subject: string): Promise<TestItem[]> {
    return [...this.testItems.values()]
      .filter((i) => i.subject === subject && i.reviewed === true) // HARD GATE (FR-27.1)
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((i) => ({ ...i }));
  }
  async insertTestItem(item: TestItem): Promise<void> {
    this.testItems.set(item.id, { ...item });
  }

  // --- test_blueprint (ADR-0015) ---
  async getTestBlueprint(id: string): Promise<TestBlueprint | null> {
    const b = this.testBlueprints.get(id);
    return b ? { ...b } : null;
  }
  async insertTestBlueprint(bp: TestBlueprint): Promise<void> {
    this.testBlueprints.set(bp.id, { ...bp });
  }

  // --- quiz_session ---
  async insertSession(s: QuizSession): Promise<void> {
    this.sessions.set(s.id, { ...s });
  }
  async getSession(id: string): Promise<QuizSession | null> {
    const s = this.sessions.get(id);
    return s ? { ...s } : null;
  }
  async patchSessionClose(
    id: string,
    patch: SessionClosePatch,
  ): Promise<QuizSession | null> {
    const s = this.sessions.get(id);
    if (!s) return null;
    const updated: QuizSession = {
      ...s,
      // Idempotent close: preserve the first close timestamp on re-close (the
      // live seam does the same via COALESCE) so re-closing never moves ended_at.
      ended_at: s.ended_at ?? patch.ended_at,
      score_correct: patch.score_correct,
      score_total: patch.score_total,
    };
    this.sessions.set(id, updated);
    return { ...updated };
  }

  // --- attempt ---
  async insertAttempt(a: Attempt): Promise<void> {
    this.attempts.push({ ...a });
  }
  async listMisses(subject: string, learnerId: string): Promise<Attempt[]> {
    // The fake joins attempt → session for learner scoping (live seam does too).
    const learnerSessionIds = new Set(
      [...this.sessions.values()]
        .filter((s) => s.subject === subject && s.learner_id === learnerId)
        .map((s) => s.id),
    );
    return this.attempts
      .filter(
        (a) =>
          a.subject === subject &&
          a.correct === false &&
          learnerSessionIds.has(a.session_id),
      )
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1)) // newest-first
      .map((a) => ({ ...a }));
  }
  async listSessionQuestionIds(sessionId: string): Promise<string[]> {
    // Every question answered in this session (any correctness) — the served
    // set (FR-13). Filter by session_id → order by created_at ASC → project
    // question_id. Oldest-first is the port contract (attempt_repo.ts §5) so the
    // C2 FR-14 self-correction half-split in use_summary.ts reads a stable
    // attempt sequence regardless of adapter.
    return this.attempts
      .filter((a) => a.session_id === sessionId)
      .slice()
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
      .map((a) => a.question_id);
  }
  async listSessionSkillIds(sessionId: string): Promise<string[]> {
    // The session's served skills newest-first, distinct (S3.1 FR-5). Resolve
    // each attempt's question_id → skill_id, order by created_at desc, de-dup
    // keeping the newest occurrence. An attempt's question_id may be a `question`
    // id (dev/practice path) OR a `test_item` id (the ADR-0021 bank path), so we
    // resolve against BOTH id-spaces — resolving only `question` would make
    // rotation silently no-op on the live bank-backed quiz. Derived from
    // `attempt` only (FR-13); an id in neither table is skipped.
    const seen = new Set<string>();
    const skills: string[] = [];
    for (const a of [...this.attempts]
      .filter((a) => a.session_id === sessionId)
      .sort((x, y) => (x.created_at < y.created_at ? 1 : -1))) {
      const skillId =
        this.questions.get(a.question_id)?.skill_id ??
        this.testItems.get(a.question_id)?.skill_id;
      if (skillId == null || seen.has(skillId)) continue;
      seen.add(skillId);
      skills.push(skillId);
    }
    return skills;
  }

  // --- skill_state ---
  async listSkillState(subject: string, learnerId: string): Promise<SkillState[]> {
    return [...this.skillState.values()]
      .filter((s) => s.subject === subject && s.learner_id === learnerId)
      .map((s) => ({ ...s }));
  }
  async getSkillState(
    subject: string,
    skillId: string,
    learnerId: string,
  ): Promise<SkillState | null> {
    const s = this.skillState.get(skillStateKey(subject, skillId, learnerId));
    return s ? { ...s } : null;
  }
  async upsertSkillState(state: SkillState): Promise<void> {
    this.skillState.set(
      skillStateKey(state.subject, state.skill_id, state.learner_id),
      { ...state },
    );
  }

  // --- content_string ---
  async getContentString(
    subject: string,
    key: string,
    locale: string,
  ): Promise<string | null> {
    return this.content.get(contentKey(subject, key, locale)) ?? null;
  }
  async listContentStrings(
    subject: string,
    locale: string,
  ): Promise<Array<{ key: string; value: string }>> {
    const prefix = `${subject}\0`;
    const suffix = `\0${locale}`;
    const out: Array<{ key: string; value: string }> = [];
    for (const [k, value] of this.content.entries()) {
      if (k.startsWith(prefix) && k.endsWith(suffix)) {
        const key = k.slice(prefix.length, k.length - suffix.length);
        out.push({ key, value });
      }
    }
    return out;
  }

  // --- tutorial / progress_point ---
  async getTutorial(subject: string, skillId: string): Promise<Tutorial | null> {
    const t = this.tutorials.get(`${subject}\0${skillId}`);
    return t ? { ...t } : null;
  }
  async listProgressPoints(
    subject: string,
    learnerId: string,
  ): Promise<ProgressPoint[]> {
    return this.progress
      .filter((p) => p.subject === subject && p.learner_id === learnerId)
      .sort((a, b) => (a.at < b.at ? -1 : 1)) // chronological
      .map((p) => ({ ...p }));
  }
}
