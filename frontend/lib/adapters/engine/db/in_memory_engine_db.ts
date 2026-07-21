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
  SkillAccuracyRow,
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

function hintKey(h: Pick<Hint, "question_id" | "choice_letter" | "rung">): string {
  return `${h.question_id}\0${h.choice_letter ?? ""}\0${h.rung}`;
}

export class InMemoryEngineDb implements EngineDb {
  private skills: Skill[] = [];
  private questions = new Map<string, Question>();
  private hints = new Map<string, Hint>(); // key: `${question_id}\0${letter??''}\0${rung}`
  private testItems = new Map<string, TestItem>();
  private testBlueprints = new Map<string, TestBlueprint>();
  private sessions = new Map<string, QuizSession>();
  private attempts: Attempt[] = [];
  /**
   * Monotonic insertion sequence per stored attempt copy. Used only to
   * tie-break `listMisses` when two rows share a `created_at` (directly-injected
   * fixtures can still tie; `DrizzleAttemptRepo.record` keeps live writes
   * strictly increasing). Newest-inserted wins — the deterministic stand-in for
   * a Postgres heap's physical order, so this fake never disagrees with the pg
   * adapter's `orderBy(desc(created_at))`. WeakMap keeps it off the wire shape.
   */
  private attemptSeq = new WeakMap<Attempt, number>();
  private nextAttemptSeq = 0;
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
    for (const h of hints) this.hints.set(hintKey(h), { ...h, choice_letter: h.choice_letter ?? null });
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

  // --- hint (ADR-0014/ADR-0035) ---
  async listReviewedHints(
    subject: string,
    questionId: string,
    choiceLetter?: string | null,
  ): Promise<Hint[]> {
    // Default to item-level ladder (null letter) so Gen1 quiz/coach callers
    // stay correct when choice-conditional rows are also seeded.
    const letter = choiceLetter ?? null;
    return [...this.hints.values()]
      .filter(
        (h) =>
          h.subject === subject &&
          h.question_id === questionId &&
          (h.choice_letter ?? null) === letter &&
          h.reviewed === true, // HARD GATE (FR-12)
      )
      .sort((a, b) => a.rung - b.rung)
      .map((h) => ({ ...h, choice_letter: h.choice_letter ?? null }));
  }
  async insertHint(h: Hint): Promise<void> {
    const row = { ...h, choice_letter: h.choice_letter ?? null };
    const key = hintKey(row);
    if (this.hints.has(key)) {
      throw new Error(
        `duplicate hint rung: (${row.question_id}, ${row.choice_letter}, ${row.rung}) already exists`,
      );
    }
    this.hints.set(key, row);
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

  async listClosedSessionsByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]> {
    const sinceISO = options?.sinceISO;
    const rows = [...this.sessions.values()].filter(
      (s) =>
        s.subject === subject &&
        s.learner_id === learnerId &&
        s.ended_at != null &&
        (sinceISO == null || s.ended_at >= sinceISO),
    );
    rows.sort((a, b) => {
      const endCmp = (b.ended_at ?? "").localeCompare(a.ended_at ?? "");
      if (endCmp !== 0) return endCmp;
      return a.id.localeCompare(b.id);
    });
    return rows.map((s) => ({ ...s }));
  }

  // --- attempt ---
  async insertAttempt(a: Attempt): Promise<void> {
    const stored = { ...a };
    this.attemptSeq.set(stored, this.nextAttemptSeq++);
    this.attempts.push(stored);
  }
  async listMisses(subject: string, learnerId: string): Promise<Attempt[]> {
    // Outstanding misses only (FR-D4 / FR-C5): latest attempt per question_id
    // for this learner+subject — include iff that latest row is incorrect. A
    // later correct answer clears the item from the review pool (append-only
    // history is preserved; this read is a projection).
    const learnerSessionIds = new Set(
      [...this.sessions.values()]
        .filter((s) => s.subject === subject && s.learner_id === learnerId)
        .map((s) => s.id),
    );
    const byNewest = (a: Attempt, b: Attempt): number => {
      if (a.created_at !== b.created_at) {
        return a.created_at < b.created_at ? 1 : -1;
      }
      // Same-ms tie: fall back to insertion order (newest-inserted first).
      // The `id` is a random UUID here, so sorting on it would surface an
      // arbitrary row — the summary recap must show the LAST miss recorded.
      const seqA = this.attemptSeq.get(a) ?? -1;
      const seqB = this.attemptSeq.get(b) ?? -1;
      return seqB - seqA;
    };
    const learnerAttempts = this.attempts
      .filter(
        (a) => a.subject === subject && learnerSessionIds.has(a.session_id),
      )
      .sort(byNewest);
    const latestByQuestion = new Map<string, Attempt>();
    for (const a of learnerAttempts) {
      if (!latestByQuestion.has(a.question_id)) {
        latestByQuestion.set(a.question_id, a);
      }
    }
    return [...latestByQuestion.values()]
      .filter((a) => a.correct === false)
      .sort(byNewest)
      .map((a) => ({ ...a }));
  }
  async listSessionQuestionIds(sessionId: string): Promise<string[]> {
    // Every question answered in this session (any correctness) — the served
    // set (FR-13). Filter by session_id → project question_id.
    return this.attempts
      .filter((a) => a.session_id === sessionId)
      .map((a) => a.question_id);
  }
  async listSessionAttempts(sessionId: string): Promise<Attempt[]> {
    return this.attempts
      .filter((a) => a.session_id === sessionId)
      .slice()
      .sort((a, b) => {
        if (a.created_at !== b.created_at) {
          return a.created_at < b.created_at ? -1 : 1;
        }
        return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
      })
      .map((a) => ({ ...a }));
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

  async accuracyRowsBySkill(
    subject: string,
    learnerId: string,
    skillId: string,
    sessions: number,
  ): Promise<SkillAccuracyRow[]> {
    // Per-session on-skill tallies newest-first (E1b-D1). Same COALESCE join as
    // listSessionSkillIds: attempt.question_id may be a `question` id OR a
    // `test_item` id (ADR-0021). Scope by learner via session.learner_id.
    // Derived from `attempt` only — never skill_state (FR-7).
    const learnerSessionIds = new Set(
      [...this.sessions.values()]
        .filter((s) => s.subject === subject && s.learner_id === learnerId)
        .map((s) => s.id),
    );
    const bySession = new Map<
      string,
      { correct: number; total: number; newestAt: string }
    >();
    for (const a of this.attempts) {
      if (a.subject !== subject || !learnerSessionIds.has(a.session_id)) continue;
      const resolvedSkill =
        this.questions.get(a.question_id)?.skill_id ??
        this.testItems.get(a.question_id)?.skill_id;
      if (resolvedSkill !== skillId) continue;
      const cur = bySession.get(a.session_id) ?? {
        correct: 0,
        total: 0,
        newestAt: a.created_at,
      };
      cur.total += 1;
      if (a.correct) cur.correct += 1;
      if (a.created_at > cur.newestAt) cur.newestAt = a.created_at;
      bySession.set(a.session_id, cur);
    }
    return [...bySession.entries()]
      .sort(([, x], [, y]) => (x.newestAt < y.newestAt ? 1 : -1))
      .slice(0, sessions)
      .map(([sessionId, v]) => ({
        sessionId,
        correct: v.correct,
        total: v.total,
      }));
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
