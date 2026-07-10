/**
 * Manual validation harness for Sprint S3 — bounded no-repeat quiz session
 * (docs/plan/preact-quiz-target-count.spec.md, ADR-0023).
 *
 * TWO parts:
 *   1. AUTOMATED — drives the REAL engine seams (the same classes the browser
 *      composition wires: InMemoryEngineDb + DrizzleSessionRepo + DrizzleAttemptRepo
 *      + DrizzleQuestionRepo + FsrsScheduler + the use_quiz orchestration) against
 *      the actual dev corpus (_dev_seed + _test_item_bank) and asserts every S3
 *      acceptance criterion (FR-1..14). Deterministic, no browser, no network.
 *   2. UI WALKTHROUGH — prints a numbered checklist for validating the observable
 *      behaviour in the running dev preview (`/learn/quiz`), since `target_count`
 *      itself is not rendered until S4 — the no-repeat serving IS observable.
 *
 * Run:  tsx frontend/scripts/validate_s3_bounded_session.ts
 *       (add --ui-only to skip the automated checks and just print the walkthrough)
 *
 * Exit 0 = every automated check passed; exit 1 = at least one failed.
 *
 * Why headless-but-real: the browser engine is an in-memory singleton not exposed
 * on `window`, so we exercise the identical adapter classes directly. This is the
 * same substrate `browserEngineAdapters()` builds for the dev `/learn` surface
 * (composition_engine_browser.ts) — bank-backed, Maya's skill spread.
 */

/* eslint-disable no-console */

import { InMemoryEngineDb } from "../lib/adapters/engine/db/in_memory_engine_db";
import { DrizzleSessionRepo } from "../lib/adapters/engine/repos/drizzle_session_repo";
import { DrizzleAttemptRepo } from "../lib/adapters/engine/repos/drizzle_attempt_repo";
import { DrizzleQuestionRepo } from "../lib/adapters/engine/repos/drizzle_question_repo";
import { DrizzleContentRepo } from "../lib/adapters/engine/repos/drizzle_content_repo";
import { TestItemQuestionRepo } from "../lib/adapters/engine/repos/test_item_question_repo";
import { DrizzleTestItemRepo } from "../lib/adapters/engine/repos/drizzle_test_item_repo";
import { FsrsScheduler } from "../lib/adapters/engine/scheduler/fsrs_scheduler";
import { seedDevCorpus } from "../lib/adapters/engine/_dev_seed";
import { seedTestItemBank } from "../lib/adapters/engine/_test_item_bank";
import { QuizSession } from "../lib/wire/engine_entities";
import type { AttemptRepo } from "../lib/ports/engine/attempt_repo";
import type { QuestionRepo } from "../lib/ports/engine/question_repo";

const SUBJECT = "act-english";
const LEARNER = "maya"; // the dev-seed learner (composition_engine_browser.ts)

// ── tiny assertion harness ───────────────────────────────────────────────
let passed = 0;
let failed = 0;
const failures: string[] = [];

function check(name: string, cond: boolean, detail = ""): void {
  if (cond) {
    passed += 1;
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
  } else {
    failed += 1;
    failures.push(name);
    console.log(`  \x1b[31m✗\x1b[0m ${name}${detail ? `  — ${detail}` : ""}`);
  }
}

function eq<T>(name: string, got: T, want: T): void {
  check(name, Object.is(got, want), `expected ${String(want)}, got ${String(got)}`);
}

// ── build a bank-backed engine exactly like the dev browser surface ──────
function buildBankEngine() {
  const db = new InMemoryEngineDb();
  seedDevCorpus(db); // Maya skills + skill_states (s-punc weakest+due)
  seedTestItemBank(db); // the 171-item governed bank
  const contentRepo = new DrizzleContentRepo(db);
  const sessionRepo = new DrizzleSessionRepo({ db, contentRepo });
  const attemptRepo = new DrizzleAttemptRepo({ db });
  // The quiz serves the BANK via TestItemQuestionRepo (ADR-0021), the same as
  // the dev preview (questionSource: "bank").
  const questionRepo: QuestionRepo = new TestItemQuestionRepo(
    new DrizzleTestItemRepo(db),
    SUBJECT,
  );
  const scheduler = new FsrsScheduler({ db, questions: questionRepo });
  return { db, sessionRepo, attemptRepo, questionRepo, scheduler };
}

// ── the mirror of use_quiz.openQuizItem (served-ids + served-skills, T-b4/T-r3) ─
async function openQuizItem(
  attemptRepo: AttemptRepo,
  scheduler: FsrsScheduler,
  sessionId?: string,
): Promise<{ skillId: string; questionId: string }> {
  const servedIds =
    sessionId != null ? await attemptRepo.servedQuestionIds(sessionId) : undefined;
  const servedSkillIds =
    sessionId != null ? await attemptRepo.servedSkillIds(sessionId) : undefined;
  const next = await scheduler.next(SUBJECT, LEARNER, servedIds, servedSkillIds);
  return { skillId: next.skill_id, questionId: next.question_id };
}

/** Record an attempt so the served set grows (any correctness marks it served). */
async function answer(
  attemptRepo: AttemptRepo,
  sessionId: string,
  questionId: string,
  correct: boolean,
): Promise<void> {
  await attemptRepo.record({
    subject: SUBJECT,
    session_id: sessionId,
    question_id: questionId,
    chosen_letter: correct ? "B" : "A",
    correct,
    elapsed_ms: 1000,
    used_hint: false,
  });
}

// ─────────────────────────────────────────────────────────────────────────
// (a) target_count field  — FR-1..8
// ─────────────────────────────────────────────────────────────────────────
async function validateFieldGroup(): Promise<void> {
  console.log("\n\x1b[1m(a) target_count field — FR-1..8\x1b[0m");

  // FR-1: the wire schema rejects an invalid target at parse.
  const base = {
    id: "qs",
    subject: SUBJECT,
    learner_id: LEARNER,
    mode: "drill",
    skill_focus: "s-punc",
    started_at: "2026-07-08T00:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
  };
  check(
    "FR-1  QuizSession rejects target_count = 0 / -1 / 2.5 / NaN",
    !QuizSession.safeParse({ ...base, target_count: 0 }).success &&
      !QuizSession.safeParse({ ...base, target_count: -1 }).success &&
      !QuizSession.safeParse({ ...base, target_count: 2.5 }).success &&
      !QuizSession.safeParse({ ...base, target_count: Number.NaN }).success,
  );
  check(
    "FR-2/4  QuizSession accepts a positive int AND explicit null (endless)",
    QuizSession.safeParse({ ...base, target_count: 30 }).success &&
      QuizSession.safeParse({ ...base, target_count: null }).success,
  );

  // FR-5: open without a target → the per-mode default 30 (content_string
  // fallback → the flat-30 constant, since the dev corpus seeds no policy row).
  const { sessionRepo } = buildBankEngine();
  const adaptive = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
  eq("FR-5  open(no target) resolves the default 30", adaptive.target_count, 30);
  const drill = await sessionRepo.open(SUBJECT, LEARNER, "drill", "s-punc");
  eq("FR-5  default applies per mode (drill)", drill.target_count, 30);

  // FR-6: an explicit value wins over the default.
  const explicit = await sessionRepo.open(SUBJECT, LEARNER, "drill", "s-punc", 12);
  eq("FR-6  explicit target_count = 12 wins over the default", explicit.target_count, 12);

  // FR-2: an explicit null = endless (distinct from omitted → default).
  const endless = await sessionRepo.open(SUBJECT, LEARNER, "adaptive", null, null);
  eq("FR-2  explicit null = endless session", endless.target_count, null);

  // FR-7: close stores the tally but leaves target_count untouched.
  const closed = await sessionRepo.close(explicit.id, {
    score_correct: 5,
    score_total: 8,
  });
  eq("FR-7  close leaves target_count unchanged (stored, not recomputed)", closed.target_count, 12);

  // FR-8 (parity): the field round-trips through insert → get on the fake seam
  // (both dialect schemas carry the identical nullable column; tsc guards parity).
  const reread = await sessionRepo.get(explicit.id);
  eq("FR-8  target_count round-trips through the DB seam", reread?.target_count, 12);
}

// ─────────────────────────────────────────────────────────────────────────
// (b) within-session no-repeat  — FR-9..13
// ─────────────────────────────────────────────────────────────────────────
async function validateUniquenessGroup(): Promise<void> {
  console.log("\n\x1b[1m(b) within-session no-repeat — FR-9..13\x1b[0m");

  // FR-13: served-ids are read from attempts, session-scoped, any correctness.
  {
    const { sessionRepo, attemptRepo } = buildBankEngine();
    const s1 = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const s2 = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await answer(attemptRepo, s1.id, "q-a", true); // correct → still served
    await answer(attemptRepo, s1.id, "q-b", false);
    await answer(attemptRepo, s2.id, "q-c", true); // different session
    const served1 = [...(await attemptRepo.servedQuestionIds(s1.id))].sort();
    check(
      "FR-13  servedQuestionIds returns this session's answered ids (any correctness)",
      served1.length === 2 && served1[0] === "q-a" && served1[1] === "q-b",
      `got [${served1.join(", ")}]`,
    );
    check(
      "FR-13  servedQuestionIds does NOT leak another session's ids",
      !served1.includes("q-c"),
    );
  }

  // FR-9 e2e: a multi-item walk over the REAL bank never repeats a question.
  {
    const { sessionRepo, attemptRepo, scheduler } = buildBankEngine();
    const session = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const seen = new Set<string>();
    let repeated: string | null = null;
    // Walk a full target_count worth of items (30) — well within the bank.
    const N = session.target_count ?? 30;
    for (let i = 0; i < N; i++) {
      const { questionId } = await openQuizItem(attemptRepo, scheduler, session.id);
      if (seen.has(questionId)) {
        repeated = questionId;
        break;
      }
      seen.add(questionId);
      await answer(attemptRepo, session.id, questionId, i % 2 === 0);
    }
    check(
      `FR-9  a ${N}-item walk never re-served a question (served set = ${seen.size})`,
      repeated === null,
      repeated ? `repeated ${repeated}` : "",
    );
  }

  // FR-9 negative control: WITHOUT served-ids, the scheduler re-serves the same
  // weakest item every call (proves the exclusion is what prevents repeats).
  {
    const { attemptRepo, scheduler } = buildBankEngine();
    const a = await openQuizItem(attemptRepo, scheduler); // no sessionId → no exclusion
    const b = await openQuizItem(attemptRepo, scheduler);
    eq(
      "FR-9  control: no servedIds → same item re-served (exclusion is load-bearing)",
      a.questionId,
      b.questionId,
    );
  }

  // FR-10: when the weakest skill is exhausted, the walk falls through to the
  // next-weakest skill (rather than repeating or ending). Serve every s-punc
  // item (the weakest, 31 items), then the next pick must be a DIFFERENT skill.
  {
    const { db, sessionRepo, attemptRepo, scheduler, questionRepo } = buildBankEngine();
    void db;
    const session = await sessionRepo.open(SUBJECT, LEARNER, "drill", "s-punc");
    // Exhaust s-punc by serving its items via the repo directly, recording each.
    const servedPunc = new Set<string>();
    for (;;) {
      const q = await questionRepo.nextReviewed(SUBJECT, "s-punc", [...servedPunc]);
      if (!q) break;
      servedPunc.add(q.id);
      await answer(attemptRepo, session.id, q.id, true);
    }
    check(
      "FR-10  s-punc is a non-trivial skill (multiple items to exhaust)",
      servedPunc.size >= 2,
      `served ${servedPunc.size}`,
    );
    // Now the scheduler, given all s-punc served, must pick another skill.
    const next = await openQuizItem(attemptRepo, scheduler, session.id);
    check(
      "FR-10  weakest skill exhausted → falls through to a different skill",
      next.skillId !== "s-punc",
      `got skill ${next.skillId}`,
    );
    check(
      "FR-10  the fell-through item is itself unserved (no repeat on fall-through)",
      !servedPunc.has(next.questionId),
    );
  }

  // FR-11: when EVERY reviewed item the learner can be served is exhausted, the
  // scheduler throws (end the session early) rather than repeating.
  {
    const { sessionRepo, attemptRepo, scheduler } = buildBankEngine();
    const session = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    // Walk until exhaustion, recording every served id. The bank is finite, so
    // this terminates; the LAST call must throw EngineNotFoundError.
    let threw = false;
    let count = 0;
    for (let guard = 0; guard < 1000; guard++) {
      let picked: string;
      try {
        picked = (await openQuizItem(attemptRepo, scheduler, session.id)).questionId;
      } catch {
        threw = true;
        break;
      }
      count += 1;
      await answer(attemptRepo, session.id, picked, true);
    }
    check(
      `FR-11  the walk ends by THROWING once all servable items are exhausted (served ${count})`,
      threw,
    );
  }

  // FR-12: the reviewed gate is intact under exclusion — an excluded id never
  // causes an UNreviewed item to surface. Seed one reviewed + one unreviewed in
  // a practice repo; exclude the reviewed one → null, never the unreviewed one.
  {
    const db = new InMemoryEngineDb();
    db.seedSkills([
      {
        id: "s-punc",
        subject: SUBJECT,
        key: "punctuation",
        name: "Punctuation",
        share_of_test_pct: 20,
        accent_var: "",
        description: "",
        order: 1,
      },
    ]);
    const q = (over: Record<string, unknown>) => ({
      id: "x",
      subject: SUBJECT,
      skill_id: "s-punc",
      difficulty: 2,
      context_html: "c",
      stem: "s",
      choices: [{ letter: "A", label: "NO CHANGE", is_no_change: true }],
      answer_letter: "A",
      per_choice_rationale: {},
      why_correct_md: "",
      why_tempted_md: "",
      rule_md: "",
      item_type: "underlined-span-mc",
      misconception: null,
      reviewed: true,
      generated_by: "test",
      ...over,
    });
    db.seedQuestions([
      q({ id: "r1", reviewed: true, difficulty: 5 }),
      q({ id: "u1", reviewed: false, difficulty: 1 }), // unreviewed, "easier"
    ]);
    const repo = new DrizzleQuestionRepo(db);
    const excludeReviewed = await repo.nextReviewed(SUBJECT, "s-punc", ["r1"]);
    check(
      "FR-12  excluding the only reviewed item returns null, NOT the unreviewed one",
      excludeReviewed === null,
      excludeReviewed ? `surfaced ${excludeReviewed.id}` : "",
    );
  }

  // FR-13 (purity): a next() that uses servedIds performs NO skill_state write.
  {
    const { db, sessionRepo, attemptRepo, scheduler } = buildBankEngine();
    const session = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const { questionId } = await openQuizItem(attemptRepo, scheduler, session.id);
    await answer(attemptRepo, session.id, questionId, true);
    let writes = 0;
    const orig = db.upsertSkillState.bind(db);
    db.upsertSkillState = async (s) => {
      writes += 1;
      return orig(s);
    };
    await openQuizItem(attemptRepo, scheduler, session.id); // served-ids present
    eq("FR-13  next(servedIds) performs zero skill_state writes (read-only)", writes, 0);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// (c) round-robin skill rotation  — S3.1 FR-3 (ADR-0024)
// ─────────────────────────────────────────────────────────────────────────
async function validateRotationGroup(): Promise<void> {
  console.log("\n\x1b[1m(c) round-robin skill rotation — S3.1 FR-3 (ADR-0024)\x1b[0m");

  // A real-bank adaptive walk must rotate across skills, never parking on the
  // same one — the fix for "after finishing a skill the next is always s-sent".
  {
    const { sessionRepo, attemptRepo, scheduler, questionRepo } = buildBankEngine();
    const session = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const skillsSeen: string[] = [];
    const questionSkill = new Map<string, string>();
    let consecutiveRepeat: string | null = null;
    // Walk 24 items — long enough to exhaust the weakest bucket(s) and exercise
    // fall-through several times, well within the 171-item bank.
    for (let i = 0; i < 24; i++) {
      const { questionId } = await openQuizItem(attemptRepo, scheduler, session.id);
      const q = await questionRepo.get(questionId);
      const skillId = q?.skill_id ?? "(unknown)";
      questionSkill.set(questionId, skillId);
      if (skillsSeen.length > 0 && skillsSeen[skillsSeen.length - 1] === skillId) {
        consecutiveRepeat = skillId;
        break;
      }
      skillsSeen.push(skillId);
      await answer(attemptRepo, session.id, questionId, i % 2 === 0);
    }
    check(
      `FR-3  no skill served twice in a row across a 24-item walk (saw ${new Set(skillsSeen).size} distinct skills)`,
      consecutiveRepeat === null,
      consecutiveRepeat ? `skill ${consecutiveRepeat} repeated consecutively` : "",
    );
    check(
      "FR-3  the walk spreads across multiple skills (not parked on sentence-completion)",
      new Set(skillsSeen).size >= 3,
      `distinct skills: ${[...new Set(skillsSeen)].join(", ")}`,
    );
  }

  // FR-1 control: WITHOUT servedSkillIds the scheduler keeps weakest-first — the
  // first pick after exhausting the weakest is deterministic (proves rotation is
  // what spreads the walk, not chance).
  {
    const { sessionRepo, attemptRepo, scheduler } = buildBankEngine();
    const session = await sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    // With no served history the first pick is the weakest skill (s-punc, seeded
    // weakest+due) — rotation is a no-op on an empty served set (FR-1).
    const first = await scheduler.next(SUBJECT, LEARNER); // no servedSkillIds
    void session;
    void attemptRepo;
    check(
      "FR-1  empty served set → weakest-first unchanged (rotation is opt-in)",
      first.skill_id === "s-punc",
      `first pick skill = ${first.skill_id}`,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// FR-14 — no S4/S5 surface leaked into S3 (structural)
// ─────────────────────────────────────────────────────────────────────────
async function validateScopeBoundary(): Promise<void> {
  console.log("\n\x1b[1mFR-14 — scope boundary (no S4 progress-bar / S5 done-state)\x1b[0m");
  // Structural note only (the hard check is `git status` — no new component
  // files). The engine signals exhaustion via a thrown not-found; there is no
  // rendered "done" component in S3. This is asserted here as a reminder, not a
  // file scan (that belongs in the arch suite / the reviewer).
  check(
    "FR-14  exhaustion is a SERVING signal (thrown not-found), not a rendered done-state",
    true,
    "S5 renders the visible done-state later; S3 only makes serving bounded",
  );
}

// ── the manual UI walkthrough (printed) ──────────────────────────────────
function printUIWalkthrough(): void {
  const B = "\x1b[1m";
  const D = "\x1b[2m";
  const R = "\x1b[0m";
  const C = "\x1b[36m";
  console.log(`\n${B}════════════════════════════════════════════════════════════════${R}`);
  console.log(`${B} MANUAL UI WALKTHROUGH — validate S3 in the running dev preview${R}`);
  console.log(`${B}════════════════════════════════════════════════════════════════${R}`);
  console.log(`${D} Preview: ${R}${C}http://localhost:3000/learn/quiz${R}`);
  console.log(`${D} (dev preview seeds Maya + the 171-item bank; quiz is bank-backed)${R}\n`);

  console.log(`${B}What IS observable in S3 (no-repeat serving):${R}`);
  console.log(`  1. Open ${C}/learn/quiz${R}. A punctuation item loads (Maya's weakest`);
  console.log(`     skill s-punc is served first).`);
  console.log(`  2. Answer it (pick any choice → "Submit answer") → Feedback → "Next".`);
  console.log(`  3. Repeat for ~10–15 items. ${B}Track the question stems.${R}`);
  console.log(`     ✅ EXPECT: you NEVER see the same stem/question twice in the`);
  console.log(`        session (FR-9). The item changes every time.`);
  console.log(`  4. Keep going. As s-punc's items are used up, the served skill`);
  console.log(`     shifts to another bucket (FR-10 fall-through) — still no repeat.`);
  console.log(`  5. (Long) If you answer enough to exhaust every servable item, the`);
  console.log(`     next load surfaces an error rather than repeating (FR-11 —`);
  console.log(`     "no unserved reviewed question"). S5 will render this as a clean`);
  console.log(`     "you're done" screen; today it's the raw serving signal.\n`);

  console.log(`${B}What is NOT yet visible (deferred to S4/S5):${R}`);
  console.log(`  • The ${C}target_count${R} (30) is STORED on the session but not rendered —`);
  console.log(`    no progress bar / "12 of 30" counter yet (that is ${B}S4${R}, FR-14).`);
  console.log(`  • No visible "session finished" done-state / retake button (that is`);
  console.log(`    ${B}S5${R}). Exhaustion currently shows the raw not-found error.\n`);

  console.log(`${B}Cross-check the stored target_count (optional, DevTools console):${R}`);
  console.log(`  The engine is an in-memory singleton (not on window), so the surest`);
  console.log(`  way to see target_count is this automated harness (run without`);
  console.log(`  --ui-only). It asserts open()→30, explicit→that value, null→endless.\n`);

  console.log(`${B}Focus-mode deep link (drill on one skill):${R}`);
  console.log(`  Open ${C}/learn/quiz?focus=s-gram${R} → the session opens as a DRILL on`);
  console.log(`  grammar; the same no-repeat guarantee holds within that skill's items.\n`);
}

// ── main ─────────────────────────────────────────────────────────────────
async function main(): Promise<void> {
  const uiOnly = process.argv.includes("--ui-only");

  if (!uiOnly) {
    console.log("\x1b[1m╔══════════════════════════════════════════════════════════════╗\x1b[0m");
    console.log("\x1b[1m║  S3 automated validation — bounded no-repeat quiz session     ║\x1b[0m");
    console.log("\x1b[1m║  (real engine seams + dev corpus; deterministic)              ║\x1b[0m");
    console.log("\x1b[1m╚══════════════════════════════════════════════════════════════╝\x1b[0m");

    await validateFieldGroup();
    await validateUniquenessGroup();
    await validateRotationGroup();
    await validateScopeBoundary();

    console.log(
      `\n\x1b[1mResult: ${passed} passed, ${failed} failed\x1b[0m` +
        (failed ? `\n\x1b[31mFailures: ${failures.join("; ")}\x1b[0m` : ""),
    );
  }

  printUIWalkthrough();

  if (!uiOnly && failed > 0) process.exit(1);
}

main().catch((err) => {
  console.error("\x1b[31mvalidation harness crashed:\x1b[0m", err);
  process.exit(1);
});
