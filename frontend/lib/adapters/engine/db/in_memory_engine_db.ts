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
import type {
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../../wire/exam_entities";
import { mergeExamDwell } from "../../../../components/exam/exam_dwell_merge";
import { EngineNotFoundError, EngineRepoError } from "../../../ports/engine/errors";
import type {
  EngineDb,
  ExamRunDetail,
  ExamRunListEntry,
  ExamSectionFinishStatus,
  ExamSectionGrades,
  InsertAttemptResult,
  SessionClosePatch,
} from "./engine_db";

function skillStateKey(subject: string, skillId: string, learnerId: string): string {
  return `${subject}\0${skillId}\0${learnerId}`;
}

function contentKey(subject: string, key: string, locale: string): string {
  return `${subject}\0${key}\0${locale}`;
}

function hintKey(h: Pick<Hint, "question_id" | "choice_letter" | "rung">): string {
  return `${h.question_id}\0${h.choice_letter ?? ""}\0${h.rung}`;
}

function examAttemptKey(runId: string, section: ExamSectionCode): string {
  return `${runId}\0${section}`;
}

function examItemKey(
  runId: string,
  section: ExamSectionCode,
  questionId: string,
): string {
  return `${runId}\0${section}\0${questionId}`;
}

export class InMemoryEngineDb implements EngineDb {
  private skills: Skill[] = [];
  private questions = new Map<string, Question>();
  private hints = new Map<string, Hint>(); // key: `${question_id}\0${letter??''}\0${rung}`
  private testItems = new Map<string, TestItem>();
  private testBlueprints = new Map<string, TestBlueprint>();
  private sessions = new Map<string, QuizSession>();
  private attempts: Attempt[] = [];
  private skillState = new Map<string, SkillState>();
  private content = new Map<string, string>();
  private tutorials = new Map<string, Tutorial>(); // key: subject\0skillId
  private progress: ProgressPoint[] = [];
  // Exam store (W1-4). learner_id on the run is the positional claim.
  private examRuns = new Map<string, ExamRun>();
  private examAttempts = new Map<string, ExamSectionAttempt>();
  private examItems = new Map<string, ExamRunItem>();

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
    this.sessions.set(s.id, {
      ...s,
      current_question_id: s.current_question_id ?? null,
    });
  }
  async getSession(id: string): Promise<QuizSession | null> {
    const s = this.sessions.get(id);
    return s ? { ...s, current_question_id: s.current_question_id ?? null } : null;
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
      // T R.12 / FR-B3c: clear the served pointer on close (mirrors the live
      // seam's atomic single-UPDATE clear).
      current_question_id: null,
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

  async setSessionCurrentQuestion(
    sessionId: string,
    questionId: string | null,
  ): Promise<void> {
    const s = this.sessions.get(sessionId);
    if (!s) return;
    this.sessions.set(sessionId, { ...s, current_question_id: questionId });
  }

  async getNewestOpenSession(
    subject: string,
    learnerId: string,
  ): Promise<QuizSession | null> {
    const rows = [...this.sessions.values()].filter(
      (s) =>
        s.subject === subject &&
        s.learner_id === learnerId &&
        s.ended_at == null,
    );
    rows.sort((a, b) => {
      const startCmp = (b.started_at ?? "").localeCompare(a.started_at ?? "");
      if (startCmp !== 0) return startCmp;
      return b.id.localeCompare(a.id);
    });
    const first = rows[0];
    return first
      ? { ...first, current_question_id: first.current_question_id ?? null }
      : null;
  }

  // --- attempt ---
  async insertAttempt(a: Attempt): Promise<InsertAttemptResult> {
    const key = a.idempotency_key ?? null;
    if (key != null) {
      const existing = this.attempts.find(
        (row) =>
          row.session_id === a.session_id &&
          row.question_id === a.question_id &&
          row.idempotency_key === key,
      );
      if (existing) {
        return { status: "already-existed", attempt: { ...existing } };
      }
    }
    const stored = { ...a, idempotency_key: key };
    this.attempts.push(stored);
    return { status: "inserted", attempt: { ...stored } };
  }
  async listMisses(subject: string, learnerId: string): Promise<Attempt[]> {
    // Outstanding misses only (FR-D4 / FR-C5): latest attempt per question_id
    // for this learner+subject — include iff that latest row is incorrect. A
    // later correct answer clears the item from the review pool (append-only
    // history is preserved; this read is a projection).
    const latestByQuestion = this.latestAttemptsByQuestion(subject, learnerId);
    return [...latestByQuestion.values()]
      .filter((a) => a.correct === false)
      .sort((a, b) => this.compareAttemptsNewestFirst(a, b))
      .map((a) => ({ ...a }));
  }
  async listAlreadyCorrectQuestionIds(
    subject: string,
    learnerId: string,
  ): Promise<string[]> {
    // FR-E4 — inverse of listMisses: latest attempt correct===true.
    const latestByQuestion = this.latestAttemptsByQuestion(subject, learnerId);
    const ids: string[] = [];
    for (const a of latestByQuestion.values()) {
      if (a.correct === true) ids.push(a.question_id);
    }
    return ids;
  }
  private compareAttemptsNewestFirst(a: Attempt, b: Attempt): number {
    if (a.created_at !== b.created_at) {
      return a.created_at < b.created_at ? 1 : -1;
    }
    // §6 same-ms tie: greatest `id` wins. `id` is the server-assigned primary
    // key, stable across devices — the same order the drizzle adapter's
    // `NOT EXISTS (later.created_at > … OR (later.created_at = … AND
    // later.id > …))` predicate enforces, so this fake agrees with pg on the
    // concurrent-device same-ms case §6 was added for.
    return a.id < b.id ? 1 : a.id > b.id ? -1 : 0;
  }
  private latestAttemptsByQuestion(
    subject: string,
    learnerId: string,
  ): Map<string, Attempt> {
    const learnerSessionIds = new Set(
      [...this.sessions.values()]
        .filter((s) => s.subject === subject && s.learner_id === learnerId)
        .map((s) => s.id),
    );
    const learnerAttempts = this.attempts
      .filter(
        (a) => a.subject === subject && learnerSessionIds.has(a.session_id),
      )
      .sort((a, b) => this.compareAttemptsNewestFirst(a, b));
    const latestByQuestion = new Map<string, Attempt>();
    for (const a of learnerAttempts) {
      if (!latestByQuestion.has(a.question_id)) {
        latestByQuestion.set(a.question_id, a);
      }
    }
    return latestByQuestion;
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

  // --- exam (W1-4). Ownership is the stored positional learner_id (FR-3). ---
  private ownedExamRun(learnerId: string, runId: string): ExamRun | null {
    const run = this.examRuns.get(runId);
    if (run == null || run.learner_id !== learnerId) return null;
    return run;
  }

  private requireOwnedExamRun(learnerId: string, runId: string): ExamRun {
    const run = this.ownedExamRun(learnerId, runId);
    // Missing and foreign-learner both look like "not owned" — the BFF
    // maps this to 403/404 in W1-6. Failure: run id is absent or stored
    // learner_id ≠ positional claim (FR-3 join).
    if (run == null) {
      throw new EngineNotFoundError(`exam run not found: ${runId}`);
    }
    return run;
  }

  private attemptsForRun(runId: string): ExamSectionAttempt[] {
    return [...this.examAttempts.values()]
      .filter((a) => a.run_id === runId)
      .sort((a, b) => a.section_code.localeCompare(b.section_code))
      .map((a) => ({ ...a }));
  }

  private itemsForRun(runId: string): ExamRunItem[] {
    return [...this.examItems.values()]
      .filter((i) => i.run_id === runId)
      .sort((a, b) => a.ordinal - b.ordinal || a.question_id.localeCompare(b.question_id))
      .map((i) => ({ ...i }));
  }

  async insertExamRun(learnerId: string, run: ExamRun): Promise<void> {
    // Persist the positional claim, not run.learner_id (W1-3 / FR-38).
    const stored: ExamRun = { ...run, learner_id: learnerId };
    if (this.examRuns.has(stored.id)) {
      throw new EngineRepoError(`duplicate exam run: ${stored.id}`);
    }
    this.examRuns.set(stored.id, stored);
  }

  async listExamRunsByLearner(
    learnerId: string,
    formId?: string,
  ): Promise<ExamRunListEntry[]> {
    const rows = [...this.examRuns.values()].filter(
      (r) => r.learner_id === learnerId && (formId == null || r.form_id === formId),
    );
    rows.sort((a, b) => {
      const created = b.created_at.localeCompare(a.created_at);
      return created !== 0 ? created : a.id.localeCompare(b.id);
    });
    return rows.map((r) => ({
      run: { ...r },
      attempts: this.attemptsForRun(r.id),
    }));
  }

  async getExamRun(
    learnerId: string,
    runId: string,
  ): Promise<ExamRunDetail | null> {
    const run = this.ownedExamRun(learnerId, runId);
    if (run == null) return null;
    return {
      run: { ...run },
      attempts: this.attemptsForRun(runId),
      items: this.itemsForRun(runId),
    };
  }

  async beginExamSection(
    learnerId: string,
    runId: string,
    section: ExamSectionCode,
    startedAt: string,
    deadlineAt: string,
  ): Promise<ExamSectionAttempt> {
    this.requireOwnedExamRun(learnerId, runId);
    const key = examAttemptKey(runId, section);
    const existing = this.examAttempts.get(key);
    // FR-37 keep-first: retry of the same in_progress section returns the
    // stored started_at / deadline_at (no free time).
    if (existing?.status === "in_progress") {
      return { ...existing };
    }
    if (existing?.status === "submitted" || existing?.status === "expired") {
      throw new EngineRepoError(
        `beginExamSection: attempt already ${existing.status}`,
      );
    }
    for (const a of this.examAttempts.values()) {
      if (a.run_id === runId && a.status === "in_progress") {
        throw new EngineRepoError(
          "beginExamSection: another section is in progress",
        );
      }
    }
    // Missing row = not yet begun (insertExamRun does not know form sections).
    const attempt: ExamSectionAttempt = {
      run_id: runId,
      section_code: section,
      status: "in_progress",
      started_at: startedAt,
      finished_at: null,
      deadline_at: deadlineAt,
      raw_correct: null,
      raw_scored_total: null,
      scale_score: null,
      time_remaining_ms_at_submit: null,
    };
    this.examAttempts.set(key, attempt);
    return { ...attempt };
  }

  async upsertExamRunItems(
    learnerId: string,
    runId: string,
    section: ExamSectionCode,
    items: readonly ExamRunItem[],
  ): Promise<void> {
    this.requireOwnedExamRun(learnerId, runId);
    const attempt = this.examAttempts.get(examAttemptKey(runId, section));
    if (attempt?.status !== "in_progress") {
      throw new EngineRepoError("upsertExamRunItems: attempt not in_progress");
    }
    for (const incoming of items) {
      const stamped: ExamRunItem = {
        ...incoming,
        run_id: runId,
        section_code: section,
      };
      const key = examItemKey(runId, section, stamped.question_id);
      const stored = this.examItems.get(key);
      this.examItems.set(
        key,
        stored == null ? stamped : mergeExamDwell(stored, stamped),
      );
    }
  }

  async finishExamSection(
    learnerId: string,
    runId: string,
    section: ExamSectionCode,
    status: ExamSectionFinishStatus,
    grades: ExamSectionGrades,
    remainingMs: number | null,
  ): Promise<ExamSectionAttempt> {
    this.requireOwnedExamRun(learnerId, runId);
    const key = examAttemptKey(runId, section);
    const existing = this.examAttempts.get(key);
    if (existing == null) {
      throw new EngineNotFoundError(
        `exam section attempt not found: ${runId}/${section}`,
      );
    }
    // FR-27 / §7 finish-once: already finished → stored result, ignore args.
    if (existing.status === "submitted" || existing.status === "expired") {
      return { ...existing };
    }
    if (existing.status !== "in_progress") {
      throw new EngineRepoError("finishExamSection: attempt not in_progress");
    }
    const finished: ExamSectionAttempt = {
      ...existing,
      status,
      finished_at: new Date().toISOString(),
      raw_correct: grades.raw_correct,
      raw_scored_total: grades.raw_scored_total,
      scale_score: grades.scale_score,
      time_remaining_ms_at_submit: remainingMs,
    };
    this.examAttempts.set(key, finished);
    return { ...finished };
  }

  async setExamRunComposite(
    learnerId: string,
    runId: string,
    composite: number | null,
  ): Promise<void> {
    const run = this.requireOwnedExamRun(learnerId, runId);
    this.examRuns.set(run.id, { ...run, composite });
  }

  async setExamBookmark(
    learnerId: string,
    runId: string,
    section: ExamSectionCode,
    questionId: string,
    bookmarked: boolean,
  ): Promise<void> {
    this.requireOwnedExamRun(learnerId, runId);
    const attempt = this.examAttempts.get(examAttemptKey(runId, section));
    if (attempt?.status !== "submitted" && attempt?.status !== "expired") {
      throw new EngineRepoError("setExamBookmark: attempt not finished");
    }
    const key = examItemKey(runId, section, questionId);
    const stored = this.examItems.get(key);
    if (stored == null) {
      throw new EngineNotFoundError(
        `exam run item not found: ${runId}/${section}/${questionId}`,
      );
    }
    this.examItems.set(key, { ...stored, bookmarked });
  }

  async listExamRunItemsByLearner(learnerId: string): Promise<ExamRunItem[]> {
    const ownedIds = new Set(
      [...this.examRuns.values()]
        .filter((r) => r.learner_id === learnerId)
        .map((r) => r.id),
    );
    return [...this.examItems.values()]
      .filter((i) => ownedIds.has(i.run_id))
      .sort(
        (a, b) =>
          a.run_id.localeCompare(b.run_id) ||
          a.section_code.localeCompare(b.section_code) ||
          a.ordinal - b.ordinal ||
          a.question_id.localeCompare(b.question_id),
      )
      .map((i) => ({ ...i }));
  }
}
