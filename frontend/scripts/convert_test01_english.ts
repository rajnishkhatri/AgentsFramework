/**
 * convert_test01_english — offline converter: Test-01.md → engine English corpus.
 *
 * WHAT. Parses the ENGLISH section (questions 1–48) of
 * `PreAct/practice-tests/Test-01.md` into the vendor-neutral `Question` shape
 * (`lib/wire/engine_entities.ts`) plus a `{ questionId: answer_letter }` official
 * answer-key map, and writes them to `e2e/fixtures/test01_english_corpus.ts`.
 *
 * WHY OFFLINE. This is NOT app runtime — it's a build-time generator (the twin of
 * `snapshot_wire_schemas.ts`): the emitted `.ts` fixture is CHECKED IN, and the
 * script is re-run only when the source markdown changes. That keeps the Test-Mode
 * runner importing plain typed data, never re-parsing markdown in the browser.
 *
 * PARSE CONTRACT (pinned by convert_test01_english.test.ts against the real file):
 *   - Only the `# SECTION 1 — ENGLISH` block is read (up to the next `# SECTION`).
 *   - Questions are `**N.** …` items whose choices are `**LETTER.** text`, either
 *     inline on the same line or on the following lines. ACT alternates lettering
 *     (odd A–D, even F–J); we normalize to internal A–D positionally.
 *   - The answer key block (`1. B  2. F …`) gives `answer_letter` (also normalized).
 *   - The explanation block (`N. **X** ★ — *Category (sub).* text`) gives the
 *     reporting category → engine skill bucket, the ★ ceiling flag → difficulty,
 *     and the explanation prose → `why_correct_md`.
 *
 * PURE CORE. `parseTest01English(md)` is a pure string→data function (node-testable,
 * no I/O). `main()` is the thin file-writing wrapper.
 *
 * LAYERING. A script under `scripts/`, imports only the `wire/` shapes + stdlib.
 * No React, no adapter, no composition import.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { type Choice, DEFAULT_SUBJECT, type Question } from "../lib/wire/engine_entities";

// ── lettering ──────────────────────────────────────────────────────────────
// ACT alternates: odd items use A–D, even items use F–J. The engine renderer is
// A–D only, so we map each raw choice letter to its A–D POSITION.
const AD = ["A", "B", "C", "D"] as const;
const RAW_ODD = ["A", "B", "C", "D"];
const RAW_EVEN = ["F", "G", "H", "J"];

function normalizeLetter(raw: string, evenItem: boolean): string | null {
  const table = evenItem ? RAW_EVEN : RAW_ODD;
  const idx = table.indexOf(raw);
  return idx >= 0 ? AD[idx]! : null;
}

// ── skill mapping ────────────────────────────────────────────────────────────
// The explanation tag's reporting category (+ sub-tag keyword) → one of the six
// engine skill buckets. Order matters: first keyword hit wins.
const SKILL_RULES: ReadonlyArray<readonly [RegExp, string]> = [
  [/punctuat|comma|semicolon|colon|apostrophe|quotation/i, "s-punc"],
  [/agree|pronoun|verb|tense|idiom|modal|homophone|relative/i, "s-gram"],
  [/parallel|modifier|splice|fragment|run-on|participl|clause|coordinate adjective/i, "s-sent"],
  [/conc|redundan|word choice|tone|style|register|wordiness/i, "s-rhet"],
  [/transition|organization|placement|order/i, "s-org"],
];
const DEFAULT_SKILL = "s-style";

function skillForCategory(tag: string): string {
  for (const [re, skill] of SKILL_RULES) {
    if (re.test(tag)) return skill;
  }
  return DEFAULT_SKILL;
}

// ── raw structures ───────────────────────────────────────────────────────────
interface RawQuestion {
  readonly num: number;
  readonly stem: string;
  readonly choices: ReadonlyArray<{ readonly rawLetter: string; readonly text: string }>;
  readonly passageContext: string;
}

interface Explanation {
  readonly category: string;
  readonly ceiling: boolean;
  readonly prose: string;
}

/** Split the doc into just the English section body (between headers). */
function englishSection(md: string): string {
  const lines = md.split("\n");
  const start = lines.findIndex((l) => /^# SECTION 1 — ENGLISH/.test(l));
  if (start < 0) throw new Error("English section header not found");
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((l) => /^# SECTION /.test(l));
  return (end < 0 ? rest : rest.slice(0, end)).join("\n");
}

const CHOICE_RE = /\*\*([A-DF-K])\.\*\*\s*([^*]*?)(?=\s*\*\*[A-DF-K]\.\*\*|$)/g;

function parseChoicesInline(s: string): Array<{ rawLetter: string; text: string }> {
  const out: Array<{ rawLetter: string; text: string }> = [];
  for (const m of s.matchAll(CHOICE_RE)) {
    out.push({ rawLetter: m[1]!, text: m[2]!.trim() });
  }
  return out;
}

/**
 * Parse the English question blocks. A block starts at `**N.**`. Its choices are
 * either inline (`**A.** … **B.** …` on the same line) or on the following lines
 * (`**A.** …` each). The `passageContext` is the nearest preceding passage's
 * `## Passage …` title + body (so the runner shows the item in context).
 */
function parseQuestions(section: string): RawQuestion[] {
  const lines = section.split("\n");
  const questions: RawQuestion[] = [];
  let passageTitle = "";
  let passageBody: string[] = [];

  const flushBody = (): string => passageBody.join(" ").replace(/\s+/g, " ").trim();

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;

    const passageMatch = /^##\s+Passage\s+.+/.exec(line);
    if (passageMatch) {
      passageTitle = line.replace(/^##\s+/, "").trim();
      passageBody = [];
      continue;
    }

    const qMatch = /^\*\*(\d+)\.\*\*\s*(.*)$/.exec(line);
    if (!qMatch) {
      // Passage body line (prose between the title and the questions).
      if (passageTitle && line.trim() && !line.startsWith("**")) {
        passageBody.push(line.trim());
      }
      continue;
    }

    const num = Number(qMatch[1]);
    const remainder = qMatch[2]!;
    let choices = parseChoicesInline(remainder);
    let stem: string;

    if (choices.length > 0) {
      // Inline: everything before the first `**A.**` is the (possibly empty) stem.
      const firstChoiceIdx = remainder.search(/\*\*[A-DF-K]\.\*\*/);
      stem = remainder.slice(0, firstChoiceIdx).trim();
    } else {
      // Multiline: the remainder is the stem; choices are on the next lines.
      // A following line may hold ONE choice (`**F.** text`) or ALL of them inline
      // (`**F.** … **G.** … **H.** … **J.** …`), so parse each line with the inline
      // splitter and accumulate until a blank line or a non-choice line.
      stem = remainder.trim();
      const collected: Array<{ rawLetter: string; text: string }> = [];
      let j = i + 1;
      for (; j < lines.length; j++) {
        const cl = lines[j]!.trim();
        if (cl === "") break;
        if (!/^\*\*[A-DF-K]\.\*\*/.test(cl)) break;
        collected.push(...parseChoicesInline(cl));
      }
      choices = collected;
      i = j - 1;
    }

    questions.push({
      num,
      stem: stem || "Which choice best fixes the underlined portion?",
      choices,
      passageContext: passageTitle ? `${passageTitle} — ${flushBody()}` : flushBody(),
    });
  }
  return questions;
}

/** Parse the English answer-key block (`1. B  2. F …`) → { num: rawLetter }. */
function parseAnswerKey(md: string): Map<number, string> {
  const lines = md.split("\n");
  const engIdx = lines.findIndex((l) => /^##\s+English\s*$/.test(l));
  if (engIdx < 0) throw new Error("English answer-key header not found");
  const key = new Map<number, string>();
  for (let i = engIdx + 1; i < lines.length; i++) {
    const l = lines[i]!;
    if (/^##\s+/.test(l)) break; // next section (Math)
    for (const m of l.matchAll(/(\d+)\.\s*([A-DF-K])\b/g)) {
      key.set(Number(m[1]), m[2]!);
    }
  }
  return key;
}

/** Parse the English explanations (`N. **X** ★ — *Category.* prose`). */
function parseExplanations(md: string): Map<number, Explanation> {
  const lines = md.split("\n");
  // The explanations live under `# EXPLANATIONS …` then `## English`.
  const explIdx = lines.findIndex((l) => /^#\s+EXPLANATIONS/.test(l));
  const scope = explIdx < 0 ? lines : lines.slice(explIdx);
  const engIdx = scope.findIndex((l) => /^##\s+English\s*$/.test(l));
  const out = new Map<number, Explanation>();
  if (engIdx < 0) return out;
  for (let i = engIdx + 1; i < scope.length; i++) {
    const l = scope[i]!;
    if (/^##\s+/.test(l)) break;
    const m = /^(\d+)\.\s+\*\*[A-DF-K]\*\*\s*(★)?\s*—\s*\*([^*]+)\*\s*(.*)$/.exec(l);
    if (!m) continue;
    out.set(Number(m[1]), {
      category: m[3]!.trim(),
      ceiling: m[2] === "★",
      prose: m[4]!.trim(),
    });
  }
  return out;
}

// ── assembly ─────────────────────────────────────────────────────────────────

export interface Test01EnglishCorpus {
  readonly questions: readonly Question[];
  readonly answerKey: Readonly<Record<string, string>>;
}

/**
 * Pure converter: markdown string → { questions, answerKey }. Node-testable, no
 * I/O. Every emitted question is schema-valid, A–D-normalized, skill-tagged,
 * reviewed, and carries an `answer_letter` that equals its official-key entry.
 */
export function parseTest01English(md: string): Test01EnglishCorpus {
  const section = englishSection(md);
  const raw = parseQuestions(section);
  const rawKey = parseAnswerKey(md);
  const explanations = parseExplanations(md);

  const questions: Question[] = [];
  const answerKey: Record<string, string> = {};

  for (const rq of raw) {
    const even = rq.num % 2 === 0;
    const id = `t01-eng-${rq.num}`;

    // Normalize the four choices to A–D.
    const choices: Choice[] = rq.choices.map((c, idx) => {
      const letter = normalizeLetter(c.rawLetter, even) ?? AD[idx]!;
      return {
        letter,
        label: c.text.replace(/^NO CHANGE$/i, "NO CHANGE"),
        is_no_change: /^NO CHANGE$/i.test(c.text),
      };
    });

    const rawAns = rawKey.get(rq.num);
    if (rawAns == null) throw new Error(`no answer key for English Q${rq.num}`);
    const answer = normalizeLetter(rawAns, even);
    if (answer == null) throw new Error(`bad answer letter ${rawAns} for Q${rq.num}`);

    const expl = explanations.get(rq.num);
    const skill = expl ? skillForCategory(expl.category) : DEFAULT_SKILL;
    // Difficulty: base 2, +1 for a ★ ceiling item, clamped 2..5.
    const difficulty = expl?.ceiling ? 4 : 2;

    // Per-choice rationale is sparse in the source; surface the correct-answer
    // explanation on the answer letter, an honest placeholder elsewhere.
    const perChoice: Record<string, string> = {};
    for (const c of choices) {
      perChoice[c.letter] =
        c.letter === answer
          ? expl?.prose || "The corrected option follows the rule for this item."
          : "This option leaves or introduces an error under the tested rule.";
    }

    const context =
      rq.passageContext ||
      "Read the sentence and choose the option that conforms to standard written English.";

    const q: Question = {
      id,
      subject: DEFAULT_SUBJECT,
      skill_id: skill,
      difficulty,
      context_html: passageToHtml(context),
      stem: rq.stem,
      choices,
      answer_letter: answer,
      per_choice_rationale: perChoice,
      why_correct_md: expl?.prose || "The corrected option follows the tested rule.",
      why_tempted_md: "The original can read smoothly until you apply the rule.",
      rule_md: expl ? `Rule focus: ${expl.category}.` : "Apply the tested rule, not what merely sounds right.",
      item_type: "underlined-span-mc",
      reviewed: true,
      generated_by: "test01-convert",
    };
    questions.push(q);
    answerKey[id] = answer;
  }

  return { questions, answerKey };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Render a passage's markdown into the reviewed `context_html` an
 * `underlined-span-mc` item expects: `**phrase** [n]` → `<u>phrase</u>`, `*word*`
 * → `<em>word</em>`, and the bare `[n]` sentence/reference markers dropped. Text
 * is escaped FIRST, then the (trusted, engine-authored) markup is re-introduced,
 * so no raw markdown leaks and no user/agent HTML is injected (FR-A6 delivery).
 */
function passageToHtml(passage: string): string {
  let html = escapeHtml(passage);
  // `**bold phrase** [n]` (an underlined span + its number) → underline, drop [n].
  html = html.replace(/\*\*([^*]+)\*\*\s*\[\d+\]/g, "<u>$1</u>");
  // Any remaining `**bold**` (no trailing number) → underline too.
  html = html.replace(/\*\*([^*]+)\*\*/g, "<u>$1</u>");
  // `*italic*` → emphasis (titles like *Osprey*).
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  // Drop the remaining bare sentence/reference markers `[1] [2] …`.
  html = html.replace(/\[\d+\]/g, "");
  // Collapse any doubled spaces left by the removals.
  return html.replace(/\s{2,}/g, " ").trim();
}

// ── file emit (thin wrapper) ─────────────────────────────────────────────────

function renderModule(corpus: Test01EnglishCorpus): string {
  const header = `/**
 * GENERATED by scripts/convert_test01_english.ts — DO NOT EDIT BY HAND.
 *
 * The English section of PreAct/practice-tests/Test-01.md, converted to the
 * engine \`Question\` shape for the timed Test-Mode runner. Re-generate with
 * \`pnpm convert:test01\` when the source markdown changes.
 *
 * \`TEST01_ENGLISH_ANSWER_KEY\` is the official answer key (also normalized to
 * internal A–D); the converter test asserts every \`answer_letter\` matches it, so
 * it doubles as a grading correctness oracle.
 */

import type { Question } from "../../wire/engine_entities";

export const TEST01_ENGLISH_QUESTIONS: readonly Question[] = ${JSON.stringify(
    corpus.questions,
    null,
    2,
  )};

export const TEST01_ENGLISH_ANSWER_KEY: Readonly<Record<string, string>> = ${JSON.stringify(
    corpus.answerKey,
    null,
    2,
  )};

/** English section length (minutes) per Test-01 instructions. */
export const TEST01_ENGLISH_MINUTES = 35;
`;
  return header;
}

function main(): void {
  const here = dirname(fileURLToPath(import.meta.url));
  const source = resolve(here, "../../PreAct/practice-tests/Test-01.md");
  const out = resolve(here, "../lib/adapters/engine/_test01_english_corpus.ts");
  const md = readFileSync(source, "utf8");
  const corpus = parseTest01English(md);
  writeFileSync(out, renderModule(corpus), "utf8");
  // eslint-disable-next-line no-console
  console.log(`convert:test01 → ${corpus.questions.length} English questions → ${out}`);
}

// Run only when executed directly (not when imported by the test).
const invokedDirectly =
  process.argv[1] != null && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) main();
