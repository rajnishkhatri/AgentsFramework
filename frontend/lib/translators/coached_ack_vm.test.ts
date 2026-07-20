/**
 * T13 / MOM-3 / VOICE-1 — wrong-pick acknowledgment composer (L1).
 *
 * The acknowledgment is the distinct coach statement that precedes ladder rung 1
 * after a wrong commit. VOICE-1 orders it: shared ground → specific complication
 * → hand off to the question. VOICE-3 forbids engine vocabulary (ladder, rung,
 * moment, wrong-pick, assertion rung) in learner-facing copy. LEAK-1 forbids
 * naming the correct letter or restating the key.
 */

import { describe, expect, it } from "vitest";
import { composeCoachedAck } from "./coached_ack_vm";
import type { Question } from "../wire/engine_entities";

function question(over: Partial<Question> & { id: string }): Question {
  return {
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 2,
    context_html: "Each of the branch libraries <u>keeps</u> a binder.",
    stem: "Which choice is correct for the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "keep", is_no_change: false },
      { letter: "C", label: "are keeping", is_no_change: false },
      { letter: "D", label: "have kept", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {
      A: "Correct: the subject is the singular pronoun 'Each,' so the singular verb agrees.",
      B: "Matches the verb to 'libraries,' the nearest noun, but that noun is the object of 'of,' not the subject.",
      C: "Doubles the error: the plural helper 'are' clashes with singular 'Each,' and progressive aspect misfits a routine habit.",
      D: "Uses the plural helper 'have' with the singular subject and shifts a present routine into the perfect tense.",
    },
    why_correct_md: "The true subject is **Each**, which is always singular.",
    why_tempted_md: "The plural noun 'libraries' sits right next to the verb.",
    rule_md: "Find the verb, ask who or what does it, match the verb to the head word.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("composeCoachedAck — VOICE-1 order + VOICE-3 vocabulary", () => {
  it("orders shared ground → complication → handoff, and keys the complication to the picked letter", () => {
    const q = question({ id: "q1" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    // VOICE-1 order: shared ground comes first, handoff comes last.
    const sg = ack.body.indexOf(ack.sharedGround);
    const cp = ack.body.indexOf(ack.complication);
    const hf = ack.body.indexOf(ack.handoff);
    expect(sg).toBeLessThan(cp);
    expect(cp).toBeLessThan(hf);
    // The complication is the B rationale (the trap for picking B), not A's.
    expect(ack.complication).toContain("libraries");
  });

  it("produces a different complication for a different picked letter", () => {
    const q = question({ id: "q1" });
    const b = composeCoachedAck({ question: q, pickedLetter: "B" });
    const c = composeCoachedAck({ question: q, pickedLetter: "C" });
    expect(b.complication).not.toBe(c.complication);
    expect(c.complication).toContain("are");
  });

  it("prefers the author-captured misconception when present", () => {
    const q = question({
      id: "q2",
      misconception: "Learners match the verb to the nearest noun, not the true subject.",
    });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.complication).toContain("nearest noun");
  });

  it("falls back to a generic complication when both misconception and the letter rationale are absent", () => {
    const q = question({
      id: "q3",
      misconception: null,
      per_choice_rationale: { A: "Correct.", B: "", C: "", D: "" },
    });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.complication.length).toBeGreaterThan(0);
    // Generic line must not pretend to know the specific trap.
    expect(ack.complication).not.toContain("libraries");
  });

  it("never uses engine vocabulary (ladder, rung, moment, wrong-pick, assertion rung) in learner-facing copy", () => {
    const q = question({ id: "q4" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    const banned = /\b(ladder|rung|moment|wrong-pick|assertion rung)\b/i;
    expect(banned.test(ack.sharedGround)).toBe(false);
    expect(banned.test(ack.complication)).toBe(false);
    expect(banned.test(ack.handoff)).toBe(false);
    expect(banned.test(ack.body)).toBe(false);
  });

  it("LEAK-1: substitutes a neutral complication when the rationale names the correct letter", () => {
    // Force a rationale for B that names the answer letter "A".
    const q = question({
      id: "q5",
      per_choice_rationale: {
        A: "Correct.",
        B: "The right choice is A because Each is singular.",
        C: "",
        D: "",
      },
    });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.leaked).toBe(true);
    // The substituted complication must not contain the answer letter "A".
    expect(ack.complication).not.toMatch(/\bA\b/);
  });

  it("LEAK-1: does not flag a false leak when the rationale merely discusses the trap", () => {
    const q = question({ id: "q6" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    // The B rationale discusses 'libraries' but never names the answer letter.
    expect(ack.leaked).toBe(false);
  });

  it("handoff points back to the sentence without naming the answer", () => {
    const q = question({ id: "q7" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.handoff).toMatch(/re-read|sentence|asking/i);
    expect(ack.handoff).not.toMatch(/\bA\b/);
  });
});
