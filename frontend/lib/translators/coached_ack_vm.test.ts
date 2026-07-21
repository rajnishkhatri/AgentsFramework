/**
 * T20 / MOM-3 / V2 — wrong-pick acknowledgment composer v2 (L1).
 *
 * Shape: verdict → specific diagnosis → "So —" hand-off into the pump.
 * The old re-read hand-off competed with rung-1 and is retired (V2).
 * VOICE-3 forbids engine vocabulary; LEAK-1 forbids naming the answer.
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

describe("composeCoachedAck — T20 verdict → diagnosis → So —", () => {
  it("orders verdict → diagnosis → So — handoff, and keys diagnosis to the picked letter", () => {
    const q = question({ id: "q1" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    const v = ack.body.indexOf(ack.verdict);
    const d = ack.body.indexOf(ack.diagnosis);
    const h = ack.body.indexOf(ack.handoff);
    expect(v).toBeLessThan(d);
    expect(d).toBeLessThan(h);
    expect(ack.verdict).toMatch(/not quite/i);
    expect(ack.handoff).toBe("So —");
    expect(ack.diagnosis).toContain("libraries");
    // V2: no competing re-read hand-off
    expect(ack.body).not.toMatch(/re-read the sentence/i);
  });

  it("produces a different diagnosis for a different picked letter", () => {
    const q = question({ id: "q1" });
    const b = composeCoachedAck({ question: q, pickedLetter: "B" });
    const c = composeCoachedAck({ question: q, pickedLetter: "C" });
    expect(b.diagnosis).not.toBe(c.diagnosis);
    expect(c.diagnosis).toContain("are");
  });

  it("prefers the author-captured misconception when present", () => {
    const q = question({
      id: "q2",
      misconception:
        "Learners match the verb to the nearest noun, not the true subject.",
    });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.diagnosis).toContain("nearest noun");
  });

  it("falls back to a generic diagnosis when both misconception and the letter rationale are absent", () => {
    const q = question({
      id: "q3",
      misconception: null,
      per_choice_rationale: { A: "Correct.", B: "", C: "", D: "" },
    });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.diagnosis.length).toBeGreaterThan(0);
    expect(ack.diagnosis).not.toContain("libraries");
    expect(ack.handoff).toBe("So —");
  });

  it("never uses engine vocabulary (ladder, rung, moment, wrong-pick, assertion rung) in learner-facing copy", () => {
    const q = question({ id: "q4" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    const banned = /\b(ladder|rung|moment|wrong-pick|assertion rung)\b/i;
    expect(banned.test(ack.verdict)).toBe(false);
    expect(banned.test(ack.diagnosis)).toBe(false);
    expect(banned.test(ack.handoff)).toBe(false);
    expect(banned.test(ack.body)).toBe(false);
  });

  it("LEAK-1: substitutes a neutral diagnosis when the rationale names the correct letter", () => {
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
    expect(ack.diagnosis).not.toMatch(/\bA\b/);
  });

  it("LEAK-1: does not flag a false leak when the rationale merely discusses the trap", () => {
    const q = question({ id: "q6" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.leaked).toBe(false);
  });

  it("handoff is only the lead-in to the pump — never a second question", () => {
    const q = question({ id: "q7" });
    const ack = composeCoachedAck({ question: q, pickedLetter: "B" });
    expect(ack.handoff).toBe("So —");
    expect(ack.handoff).not.toMatch(/\?/);
    expect(ack.body.endsWith("So —")).toBe(true);
  });
});
