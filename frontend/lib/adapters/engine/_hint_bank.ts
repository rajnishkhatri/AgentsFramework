/**
 * The governed hint-ladder bank (coach-bank-hints spec FR-B1) —
 * GENERATED FILE — do not edit by hand. Every row was EARNED through the
 * hint verifier cascade (components/hint_generation.py: schema ->
 * deterministic per-rung leakage -> duplicate) driven by
 * scripts/generate_hints.py; `generated_by` carries the promoting run's
 * "<model>@<workflow_id>" stamp. Regenerate (reads
 * docs/plan/coach-bank-hints.seed.json, emits this file AND
 * components/subject_coach_bank_hints.py):
 *
 *   .venv/bin/python scripts/emit_hint_bank.py
 *
 * SERVING. Loaded by the browser composition root's dev-default branch via
 * `seedHintBank(db)` (next to `seedTestItemBank`); served ONLY through the
 * read-only `HintRepo` reviewed gate (ADR-0014, FR-12). JSON-quoted keys are
 * deliberate: the provenance detector matches the quoted form.
 */

import type { Hint } from "../../wire/engine_entities";
import type { InMemoryEngineDb } from "./db/in_memory_engine_db";

export const HINT_BANK: readonly Hint[] = [
  {
      "id": "h-gen-4c074a1e7b686f66",
      "subject": "act-english",
      "question_id": "ti-gen-00d5603f1e869633",
      "rung": 1,
      "body_md": "What do you think is the main purpose of the underlined phrase in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5d5425290c741a58cab05c905d86b26"
  },
  {
      "id": "h-gen-d9c087972bd4c490",
      "subject": "act-english",
      "question_id": "ti-gen-00d5603f1e869633",
      "rung": 2,
      "body_md": "Consider the difference between restrictive and non-restrictive clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5d5425290c741a58cab05c905d86b26"
  },
  {
      "id": "h-gen-b9cb6984628d19bc",
      "subject": "act-english",
      "question_id": "ti-gen-00d5603f1e869633",
      "rung": 3,
      "body_md": "Look closely at how the presence or absence of commas affects the meaning of the clause.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5d5425290c741a58cab05c905d86b26"
  },
  {
      "id": "h-gen-f052ae307bbf8860",
      "subject": "act-english",
      "question_id": "ti-gen-0104d697f908031f",
      "rung": 1,
      "body_md": "What do you think about the phrase that indicates the action of getting out of bed?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4bf4d88d696a414585fae4a509576c60"
  },
  {
      "id": "h-gen-a3250929b394a40b",
      "subject": "act-english",
      "question_id": "ti-gen-0104d697f908031f",
      "rung": 2,
      "body_md": "Consider the concept of redundancy in language; what does it mean for a word to be unnecessary?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4bf4d88d696a414585fae4a509576c60"
  },
  {
      "id": "h-gen-4efbdbecb75860c3",
      "subject": "act-english",
      "question_id": "ti-gen-0104d697f908031f",
      "rung": 3,
      "body_md": "Look closely at the action described in the underlined phrase and think about whether both words are needed to convey the same meaning.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4bf4d88d696a414585fae4a509576c60"
  },
  {
      "id": "h-gen-1b61a210a7dcd885",
      "subject": "act-english",
      "question_id": "ti-gen-010cbb92a190e0e6",
      "rung": 1,
      "body_md": "What do you think about the placement of the description in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4fc96bbd1f7548a4aec613028c1c82d7"
  },
  {
      "id": "h-gen-d6d079bf1381c1e4",
      "subject": "act-english",
      "question_id": "ti-gen-010cbb92a190e0e6",
      "rung": 2,
      "body_md": "Consider the rule that a modifier should be placed next to the noun it describes.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4fc96bbd1f7548a4aec613028c1c82d7"
  },
  {
      "id": "h-gen-1302d87e002e8800",
      "subject": "act-english",
      "question_id": "ti-gen-010cbb92a190e0e6",
      "rung": 3,
      "body_md": "Look closely at how the description is connected to the noun in each option. Where does the clause end in each choice?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4fc96bbd1f7548a4aec613028c1c82d7"
  },
  {
      "id": "h-gen-cbd9e021afc8b634",
      "subject": "act-english",
      "question_id": "ti-gen-01bcf552622af4e7",
      "rung": 1,
      "body_md": "What do you think about the use of 'more' in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51a2b5934ea4438d83d581f1920fc81d"
  },
  {
      "id": "h-gen-f2cc7d5a4a9f94af",
      "subject": "act-english",
      "question_id": "ti-gen-01bcf552622af4e7",
      "rung": 2,
      "body_md": "In English, when making comparisons, we typically use either a comparative form or the word 'more', but not both together.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51a2b5934ea4438d83d581f1920fc81d"
  },
  {
      "id": "h-gen-6ecfc57f3978711d",
      "subject": "act-english",
      "question_id": "ti-gen-01bcf552622af4e7",
      "rung": 3,
      "body_md": "Consider how the underlined phrase could be rephrased to avoid using both a comparative marker and 'more'.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51a2b5934ea4438d83d581f1920fc81d"
  },
  {
      "id": "h-gen-7aaa2cd0db1b4192",
      "subject": "act-english",
      "question_id": "ti-gen-029593c1fe5291ac",
      "rung": 1,
      "body_md": "What do you think about the pronoun used in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1a2ac03cdb9a4782956b1e5ca5f27b84"
  },
  {
      "id": "h-gen-65fff8958acc9c11",
      "subject": "act-english",
      "question_id": "ti-gen-029593c1fe5291ac",
      "rung": 2,
      "body_md": "Consider the rule that pronouns must agree in number with the nouns they refer to.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1a2ac03cdb9a4782956b1e5ca5f27b84"
  },
  {
      "id": "h-gen-17b2115c3ad33c1e",
      "subject": "act-english",
      "question_id": "ti-gen-029593c1fe5291ac",
      "rung": 3,
      "body_md": "Look closely at the subject of the sentence and think about how it relates to the pronoun in question.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1a2ac03cdb9a4782956b1e5ca5f27b84"
  },
  {
      "id": "h-gen-2237589bee29f26c",
      "subject": "act-english",
      "question_id": "ti-gen-03e8dc4d409295fc",
      "rung": 1,
      "body_md": "What do you think about the subject of the sentence? Is it singular or plural?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@86fdc00a454b443398ebcee1875a2ac0"
  },
  {
      "id": "h-gen-1ee6870cd2ca7d97",
      "subject": "act-english",
      "question_id": "ti-gen-03e8dc4d409295fc",
      "rung": 2,
      "body_md": "Remember that the subject of a sentence determines the form of the verb. What do you know about subjects that are singular versus plural?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@86fdc00a454b443398ebcee1875a2ac0"
  },
  {
      "id": "h-gen-ba4cd44d5f2b884e",
      "subject": "act-english",
      "question_id": "ti-gen-03e8dc4d409295fc",
      "rung": 3,
      "body_md": "Look closely at the word 'each' in the sentence. How does it affect the verb that should be used?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@86fdc00a454b443398ebcee1875a2ac0"
  },
  {
      "id": "h-gen-946aeaf2511e8710",
      "subject": "act-english",
      "question_id": "ti-gen-04b3df88a3e00997",
      "rung": 1,
      "body_md": "What do you think makes figurative language more effective than plain language in writing?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7dd8ded06e94de49ab130a58993a300"
  },
  {
      "id": "h-gen-1f3bc88ace7ec69b",
      "subject": "act-english",
      "question_id": "ti-gen-04b3df88a3e00997",
      "rung": 2,
      "body_md": "Consider how figurative language can create vivid imagery or evoke emotions in the reader.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7dd8ded06e94de49ab130a58993a300"
  },
  {
      "id": "h-gen-b9d43120af488230",
      "subject": "act-english",
      "question_id": "ti-gen-04b3df88a3e00997",
      "rung": 3,
      "body_md": "Look closely at the options and think about how each choice conveys a sense of activity or liveliness compared to the original phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7dd8ded06e94de49ab130a58993a300"
  },
  {
      "id": "h-gen-15574b7a397f06e8",
      "subject": "act-english",
      "question_id": "ti-gen-0547a2126a9a3834",
      "rung": 1,
      "body_md": "What do you think is the main point the essay is trying to make about libraries in today's world?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c7025a3588e8460380360c544d8f8a86"
  },
  {
      "id": "h-gen-41cf8058372c3b0b",
      "subject": "act-english",
      "question_id": "ti-gen-0547a2126a9a3834",
      "rung": 2,
      "body_md": "Consider how a strong body paragraph should support the main claim of an essay. What kind of information would be most relevant?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c7025a3588e8460380360c544d8f8a86"
  },
  {
      "id": "h-gen-0864b63c03e9eb82",
      "subject": "act-english",
      "question_id": "ti-gen-0547a2126a9a3834",
      "rung": 3,
      "body_md": "Look for details that illustrate how libraries contribute to society today. What modern services might be important to mention?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c7025a3588e8460380360c544d8f8a86"
  },
  {
      "id": "h-gen-da511964baa498cf",
      "subject": "act-english",
      "question_id": "ti-gen-0871498e14f92745",
      "rung": 1,
      "body_md": "What do you think is the best way to connect the two parts of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@89ddb379f7f841d59223f1fbe401166d"
  },
  {
      "id": "h-gen-593b4fa0260b5bac",
      "subject": "act-english",
      "question_id": "ti-gen-0871498e14f92745",
      "rung": 2,
      "body_md": "Consider how independent clauses can be joined in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@89ddb379f7f841d59223f1fbe401166d"
  },
  {
      "id": "h-gen-3eb1d1f146b097b4",
      "subject": "act-english",
      "question_id": "ti-gen-0871498e14f92745",
      "rung": 3,
      "body_md": "Look closely at the punctuation options and think about how they affect the relationship between the two clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@89ddb379f7f841d59223f1fbe401166d"
  },
  {
      "id": "h-gen-31e0f09ca5ec40ec",
      "subject": "act-english",
      "question_id": "ti-gen-08dfeed4155da2ed",
      "rung": 1,
      "body_md": "What do you think the relationship is between the two parts of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8872c6f0efca4a30a7d6605eb78af66b"
  },
  {
      "id": "h-gen-86f451e671ff523f",
      "subject": "act-english",
      "question_id": "ti-gen-08dfeed4155da2ed",
      "rung": 2,
      "body_md": "Consider how transitions can indicate the order of actions or ideas.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8872c6f0efca4a30a7d6605eb78af66b"
  },
  {
      "id": "h-gen-86d539f3f27c37f7",
      "subject": "act-english",
      "question_id": "ti-gen-08dfeed4155da2ed",
      "rung": 3,
      "body_md": "Look closely at how the transition connects the soaking of the beans to the next action described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8872c6f0efca4a30a7d6605eb78af66b"
  },
  {
      "id": "h-gen-c54db9149864537e",
      "subject": "act-english",
      "question_id": "ti-gen-0965ed6ac4c30558",
      "rung": 1,
      "body_md": "What are your thoughts on the tone of the phrase used in the press release?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@920ab3049e0d479389b1df5986268a0c"
  },
  {
      "id": "h-gen-467a81ecb6929fc0",
      "subject": "act-english",
      "question_id": "ti-gen-0965ed6ac4c30558",
      "rung": 2,
      "body_md": "Consider the importance of maintaining a professional tone in formal communications.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@920ab3049e0d479389b1df5986268a0c"
  },
  {
      "id": "h-gen-d8abb37410c30075",
      "subject": "act-english",
      "question_id": "ti-gen-0965ed6ac4c30558",
      "rung": 3,
      "body_md": "Look closely at the options and think about which phrases convey a more formal and respectful tone.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@920ab3049e0d479389b1df5986268a0c"
  },
  {
      "id": "h-gen-cd9eff457503a6f1",
      "subject": "act-english",
      "question_id": "ti-gen-0a9808afaaedc6d9",
      "rung": 1,
      "body_md": "What do you think the phrase 'day in the sun' is trying to convey about the sketches?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ce153e2fbb2441589e6c49a52a753cd6"
  },
  {
      "id": "h-gen-26c6169fa91d3ba8",
      "subject": "act-english",
      "question_id": "ti-gen-0a9808afaaedc6d9",
      "rung": 2,
      "body_md": "Consider the meaning of idioms and how they can sometimes be misused in context.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ce153e2fbb2441589e6c49a52a753cd6"
  },
  {
      "id": "h-gen-35813acae3a2af71",
      "subject": "act-english",
      "question_id": "ti-gen-0a9808afaaedc6d9",
      "rung": 3,
      "body_md": "Look closely at the meaning of the underlined phrase and think about what type of sketches are being described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ce153e2fbb2441589e6c49a52a753cd6"
  },
  {
      "id": "h-gen-99476d80e7c2b517",
      "subject": "act-english",
      "question_id": "ti-gen-0c1789eb6711c6f2",
      "rung": 1,
      "body_md": "What do you think about the verb used in the underlined phrase? Does it match the other verbs in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92657b039ee9429bb9989d7b6d8a3d02"
  },
  {
      "id": "h-gen-daa74c71383ad540",
      "subject": "act-english",
      "question_id": "ti-gen-0c1789eb6711c6f2",
      "rung": 2,
      "body_md": "Consider the rule of maintaining consistent verb tense within a narrative. Why is this important?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92657b039ee9429bb9989d7b6d8a3d02"
  },
  {
      "id": "h-gen-019a8382210635e8",
      "subject": "act-english",
      "question_id": "ti-gen-0c1789eb6711c6f2",
      "rung": 3,
      "body_md": "Look closely at the verbs in the sentence. How do they relate to each other in terms of tense? Pay attention to the sequence of actions described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92657b039ee9429bb9989d7b6d8a3d02"
  },
  {
      "id": "h-gen-c73e5b6bc25d6c73",
      "subject": "act-english",
      "question_id": "ti-gen-0dcd672f1f8d3b8a",
      "rung": 1,
      "body_md": "What do you think about the verb choice in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e0a987d62ba4b61bbda10a79e41226e"
  },
  {
      "id": "h-gen-91b2057c8cbb49c1",
      "subject": "act-english",
      "question_id": "ti-gen-0dcd672f1f8d3b8a",
      "rung": 2,
      "body_md": "Consider how subjects connected by 'and' typically affect verb agreement.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e0a987d62ba4b61bbda10a79e41226e"
  },
  {
      "id": "h-gen-592adafcf5b30ea0",
      "subject": "act-english",
      "question_id": "ti-gen-0dcd672f1f8d3b8a",
      "rung": 3,
      "body_md": "Look closely at the subject of the sentence and think about how it influences the verb form.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e0a987d62ba4b61bbda10a79e41226e"
  },
  {
      "id": "h-gen-f9125599ec9fa621",
      "subject": "act-english",
      "question_id": "ti-gen-0ec8f45b9028b6c6",
      "rung": 1,
      "body_md": "What do you think the relationship is between the late frost and the cider festival?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ef031d7acef54d3b90665cd4329efdc0"
  },
  {
      "id": "h-gen-85594e694c95c70d",
      "subject": "act-english",
      "question_id": "ti-gen-0ec8f45b9028b6c6",
      "rung": 2,
      "body_md": "Consider how different transitions can indicate relationships between events, such as cause and effect or contrast.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ef031d7acef54d3b90665cd4329efdc0"
  },
  {
      "id": "h-gen-bcc0141483a7b493",
      "subject": "act-english",
      "question_id": "ti-gen-0ec8f45b9028b6c6",
      "rung": 3,
      "body_md": "Look closely at how the outcome of the festival relates to the setback of the frost; think about whether the festival's occurrence is a direct result of the frost or if it contrasts with it.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ef031d7acef54d3b90665cd4329efdc0"
  },
  {
      "id": "h-gen-2cf86152c1d7daac",
      "subject": "act-english",
      "question_id": "ti-gen-0ef8644e50886b15",
      "rung": 1,
      "body_md": "What do you think is the correct form of the verb in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1c9e3091171b446ba68897c1ee1fe3a4"
  },
  {
      "id": "h-gen-d3ecb4f9787a0ea8",
      "subject": "act-english",
      "question_id": "ti-gen-0ef8644e50886b15",
      "rung": 2,
      "body_md": "Consider the rule that irregular verbs have specific forms for their past participles.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1c9e3091171b446ba68897c1ee1fe3a4"
  },
  {
      "id": "h-gen-3463eab154474a49",
      "subject": "act-english",
      "question_id": "ti-gen-0ef8644e50886b15",
      "rung": 3,
      "body_md": "Look closely at the verb forms that follow 'had' and compare them to the standard forms of irregular verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1c9e3091171b446ba68897c1ee1fe3a4"
  },
  {
      "id": "h-gen-0a2395568504ea75",
      "subject": "act-english",
      "question_id": "ti-gen-10f0b02354ecfdf4",
      "rung": 1,
      "body_md": "What do you think the chef's description of her menu suggests about its quality or completeness?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a619cde3d6f9478695a2bf92c1e08bb0"
  },
  {
      "id": "h-gen-101fec47097f430e",
      "subject": "act-english",
      "question_id": "ti-gen-10f0b02354ecfdf4",
      "rung": 2,
      "body_md": "Consider the concept of a work in progress versus a finished product.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a619cde3d6f9478695a2bf92c1e08bb0"
  },
  {
      "id": "h-gen-83e2471690bfccd2",
      "subject": "act-english",
      "question_id": "ti-gen-10f0b02354ecfdf4",
      "rung": 3,
      "body_md": "Look closely at the implications of the chef's admission about her menu; think about how it relates to the idea of experimentation or initial attempts.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a619cde3d6f9478695a2bf92c1e08bb0"
  },
  {
      "id": "h-gen-ddc2084c628e1173",
      "subject": "act-english",
      "question_id": "ti-gen-115a1f54729c0934",
      "rung": 1,
      "body_md": "What do you think is the correct past form of the verb in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9ef488a24ab04ab790c289db82fb8ce5"
  },
  {
      "id": "h-gen-aad6c5a52c6cd815",
      "subject": "act-english",
      "question_id": "ti-gen-115a1f54729c0934",
      "rung": 2,
      "body_md": "Consider the general rule for forming the past tense of irregular verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9ef488a24ab04ab790c289db82fb8ce5"
  },
  {
      "id": "h-gen-49e80fa90e29f826",
      "subject": "act-english",
      "question_id": "ti-gen-115a1f54729c0934",
      "rung": 3,
      "body_md": "Look closely at the verb in the underlined phrase and compare it to the options provided, especially focusing on how past forms are typically constructed.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9ef488a24ab04ab790c289db82fb8ce5"
  },
  {
      "id": "h-gen-8367fa750de22da7",
      "subject": "act-english",
      "question_id": "ti-gen-12bb79b0de650b29",
      "rung": 1,
      "body_md": "What do you think is the role of the word in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3a7fa7d168d4de19f2ff9184212393d"
  },
  {
      "id": "h-gen-fd2be3967be815d7",
      "subject": "act-english",
      "question_id": "ti-gen-12bb79b0de650b29",
      "rung": 2,
      "body_md": "Consider the difference between words that refer to people and those that refer to things.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3a7fa7d168d4de19f2ff9184212393d"
  },
  {
      "id": "h-gen-b9a54441b8a4cefd",
      "subject": "act-english",
      "question_id": "ti-gen-12bb79b0de650b29",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence and think about how the word connects to the noun it describes.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3a7fa7d168d4de19f2ff9184212393d"
  },
  {
      "id": "h-gen-f6d1dd1a41c3f482",
      "subject": "act-english",
      "question_id": "ti-gen-130d46cb6e004cef",
      "rung": 1,
      "body_md": "What do you think makes a strong thesis statement for an essay?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@013ce2e8c70343fa9b4482a25f2b3ebb"
  },
  {
      "id": "h-gen-a4bc40269b1701ac",
      "subject": "act-english",
      "question_id": "ti-gen-130d46cb6e004cef",
      "rung": 2,
      "body_md": "A strong thesis statement should present an arguable claim and outline the main points that will be discussed.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@013ce2e8c70343fa9b4482a25f2b3ebb"
  },
  {
      "id": "h-gen-3306d35c191a4f05",
      "subject": "act-english",
      "question_id": "ti-gen-130d46cb6e004cef",
      "rung": 3,
      "body_md": "Consider how each option presents its argument and whether it provides specific reasons that support the claim.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@013ce2e8c70343fa9b4482a25f2b3ebb"
  },
  {
      "id": "h-gen-f438e14b1c183f9c",
      "subject": "act-english",
      "question_id": "ti-gen-17fdb4a4ee295f8d",
      "rung": 1,
      "body_md": "What do you think about the phrase that indicates membership in the robotics club?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@38aa4d7b0a064610bd89f8f86fc82f02"
  },
  {
      "id": "h-gen-cce09f2f6d637612",
      "subject": "act-english",
      "question_id": "ti-gen-17fdb4a4ee295f8d",
      "rung": 2,
      "body_md": "Consider the principle of conciseness in writing — how can you express the same idea using fewer words?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@38aa4d7b0a064610bd89f8f86fc82f02"
  },
  {
      "id": "h-gen-099100e61ad2a8e6",
      "subject": "act-english",
      "question_id": "ti-gen-17fdb4a4ee295f8d",
      "rung": 3,
      "body_md": "Look closely at the options and compare how each one conveys the idea of belonging to the club.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@38aa4d7b0a064610bd89f8f86fc82f02"
  },
  {
      "id": "h-gen-42a04e79ee6e580d",
      "subject": "act-english",
      "question_id": "ti-gen-18702ebe60cf2373",
      "rung": 1,
      "body_md": "What do you think is missing in the underlined phrase to make it a complete sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5351c1d7ffc04de68c8f155397f5cdde"
  },
  {
      "id": "h-gen-5bc9577e64b99b39",
      "subject": "act-english",
      "question_id": "ti-gen-18702ebe60cf2373",
      "rung": 2,
      "body_md": "Remember that a complete sentence requires both a subject and a finite verb.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5351c1d7ffc04de68c8f155397f5cdde"
  },
  {
      "id": "h-gen-ffb13b13ce1cc33e",
      "subject": "act-english",
      "question_id": "ti-gen-18702ebe60cf2373",
      "rung": 3,
      "body_md": "Look closely at the structure of the underlined phrase and consider how it could be connected to a subject and verb.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5351c1d7ffc04de68c8f155397f5cdde"
  },
  {
      "id": "h-gen-8342e82c5bac8e00",
      "subject": "act-english",
      "question_id": "ti-gen-1d1287067e8530e5",
      "rung": 1,
      "body_md": "What do you think makes a statement persuasive in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8bae54114904c88abcc582e8f96a2cc"
  },
  {
      "id": "h-gen-c366d519c0c9e506",
      "subject": "act-english",
      "question_id": "ti-gen-1d1287067e8530e5",
      "rung": 2,
      "body_md": "Consider how specific evidence can enhance an argument's effectiveness.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8bae54114904c88abcc582e8f96a2cc"
  },
  {
      "id": "h-gen-1eea07ce998ea053",
      "subject": "act-english",
      "question_id": "ti-gen-1d1287067e8530e5",
      "rung": 3,
      "body_md": "Look closely at the options and think about which one provides concrete support for the claim.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8bae54114904c88abcc582e8f96a2cc"
  },
  {
      "id": "h-gen-c5e56942cd2596b6",
      "subject": "act-english",
      "question_id": "ti-gen-1e22163f8445836f",
      "rung": 1,
      "body_md": "What do you think the second body paragraph should focus on based on the introduction's promise?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@af5d5409f0be4c3790da43e41b0448ef"
  },
  {
      "id": "h-gen-5bc801110facdf65",
      "subject": "act-english",
      "question_id": "ti-gen-1e22163f8445836f",
      "rung": 2,
      "body_md": "Consider the importance of addressing both topics mentioned in the introduction.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@af5d5409f0be4c3790da43e41b0448ef"
  },
  {
      "id": "h-gen-494796515d27b454",
      "subject": "act-english",
      "question_id": "ti-gen-1e22163f8445836f",
      "rung": 3,
      "body_md": "Look for a choice that discusses actions taken to rebuild trust in the community.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@af5d5409f0be4c3790da43e41b0448ef"
  },
  {
      "id": "h-gen-3205345f677e73be",
      "subject": "act-english",
      "question_id": "ti-gen-225a988bdbe48711",
      "rung": 1,
      "body_md": "What do you think the main idea of the passage is regarding sourdough?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4cf3f8650b3245768cb2a8552ce40918"
  },
  {
      "id": "h-gen-298ca6db302d8444",
      "subject": "act-english",
      "question_id": "ti-gen-225a988bdbe48711",
      "rung": 2,
      "body_md": "Consider how the passage describes the complexity of sourdough compared to other types of bread.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4cf3f8650b3245768cb2a8552ce40918"
  },
  {
      "id": "h-gen-d3858593d82daee9",
      "subject": "act-english",
      "question_id": "ti-gen-225a988bdbe48711",
      "rung": 3,
      "body_md": "Look for a conclusion that reflects back on the initial idea about the nature of sourdough.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4cf3f8650b3245768cb2a8552ce40918"
  },
  {
      "id": "h-gen-269642aa5a9b1b1f",
      "subject": "act-english",
      "question_id": "ti-gen-2347e23051258ddd",
      "rung": 1,
      "body_md": "What do you think about the verb form used in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8b4827e2e86f4bdf84d61fcb8086283f"
  },
  {
      "id": "h-gen-227bcd9a4d2aa48c",
      "subject": "act-english",
      "question_id": "ti-gen-2347e23051258ddd",
      "rung": 2,
      "body_md": "Consider the rule for expressing actions that were ongoing before a specific past event.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8b4827e2e86f4bdf84d61fcb8086283f"
  },
  {
      "id": "h-gen-848a2e3eaecc6fb0",
      "subject": "act-english",
      "question_id": "ti-gen-2347e23051258ddd",
      "rung": 3,
      "body_md": "Look closely at the timing of the action in the underlined phrase and compare it to the other options to see which best fits the context.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8b4827e2e86f4bdf84d61fcb8086283f"
  },
  {
      "id": "h-gen-0cd38b9d114079b5",
      "subject": "act-english",
      "question_id": "ti-gen-24344ba26513cfcf",
      "rung": 1,
      "body_md": "What do you think about the placement of 'however' in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@867b76686c304c759dd37e4e12c1949c"
  },
  {
      "id": "h-gen-160b942e72891ddd",
      "subject": "act-english",
      "question_id": "ti-gen-24344ba26513cfcf",
      "rung": 2,
      "body_md": "Consider the punctuation rules for connecting two independent clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@867b76686c304c759dd37e4e12c1949c"
  },
  {
      "id": "h-gen-43f528dba74fffe9",
      "subject": "act-english",
      "question_id": "ti-gen-24344ba26513cfcf",
      "rung": 3,
      "body_md": "Look at the punctuation used before and after 'however' in similar contexts.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@867b76686c304c759dd37e4e12c1949c"
  },
  {
      "id": "h-gen-d1ad4a3daf2bc947",
      "subject": "act-english",
      "question_id": "ti-gen-25b1576fd5f783b9",
      "rung": 1,
      "body_md": "What do you think about the relationship between the two statements in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4089fb4f59a94c88a88ab32cef608b28"
  },
  {
      "id": "h-gen-6ebf6aec1a4676e5",
      "subject": "act-english",
      "question_id": "ti-gen-25b1576fd5f783b9",
      "rung": 2,
      "body_md": "Consider the rule regarding how to connect two independent clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4089fb4f59a94c88a88ab32cef608b28"
  },
  {
      "id": "h-gen-3864622321bdb55a",
      "subject": "act-english",
      "question_id": "ti-gen-25b1576fd5f783b9",
      "rung": 3,
      "body_md": "Look closely at the punctuation used before the conjunction in similar sentences.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4089fb4f59a94c88a88ab32cef608b28"
  },
  {
      "id": "h-gen-5d8a0d189ce3ec6c",
      "subject": "act-english",
      "question_id": "ti-gen-26b65ee2ba3d6de6",
      "rung": 1,
      "body_md": "What do you think the main focus of the report is regarding the drought and its effects?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3497b7727b6641b2b20dd1d6141a0f0d"
  },
  {
      "id": "h-gen-6c2dc8fe0d0feed4",
      "subject": "act-english",
      "question_id": "ti-gen-26b65ee2ba3d6de6",
      "rung": 2,
      "body_md": "Consider how a conclusion should relate to the main ideas presented in the report.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3497b7727b6641b2b20dd1d6141a0f0d"
  },
  {
      "id": "h-gen-ffb7a369976ff06d",
      "subject": "act-english",
      "question_id": "ti-gen-26b65ee2ba3d6de6",
      "rung": 3,
      "body_md": "Look for a choice that emphasizes the town's strategy for dealing with future droughts.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3497b7727b6641b2b20dd1d6141a0f0d"
  },
  {
      "id": "h-gen-efab525cb390cf0e",
      "subject": "act-english",
      "question_id": "ti-gen-293a6839500a18f6",
      "rung": 1,
      "body_md": "What do you think is the main issue with the way the cities and states are presented in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@05ab50b1bd40451f886973e6146db9f5"
  },
  {
      "id": "h-gen-70c0626cfa2c9b8b",
      "subject": "act-english",
      "question_id": "ti-gen-293a6839500a18f6",
      "rung": 2,
      "body_md": "Consider how items in a list can be separated to avoid confusion, especially when some items contain commas.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@05ab50b1bd40451f886973e6146db9f5"
  },
  {
      "id": "h-gen-3283ee9a32d5d675",
      "subject": "act-english",
      "question_id": "ti-gen-293a6839500a18f6",
      "rung": 3,
      "body_md": "Look closely at how the items in the list are punctuated, particularly focusing on the separation between the city-state pairs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@05ab50b1bd40451f886973e6146db9f5"
  },
  {
      "id": "h-gen-03e023036df5b4b7",
      "subject": "act-english",
      "question_id": "ti-gen-293cc0b3217916e9",
      "rung": 1,
      "body_md": "What do you think about the pronoun that should be used for 'the library'?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@cf33b508e21e4ed588b7d44aa50b053f"
  },
  {
      "id": "h-gen-95b076166640ff09",
      "subject": "act-english",
      "question_id": "ti-gen-293cc0b3217916e9",
      "rung": 2,
      "body_md": "Consider the rule that a singular noun typically takes a singular pronoun.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@cf33b508e21e4ed588b7d44aa50b053f"
  },
  {
      "id": "h-gen-55dc3b9c97649f44",
      "subject": "act-english",
      "question_id": "ti-gen-293cc0b3217916e9",
      "rung": 3,
      "body_md": "Look closely at the pronouns provided and compare them to the noun in the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@cf33b508e21e4ed588b7d44aa50b053f"
  },
  {
      "id": "h-gen-9ed7c9c4da1aa523",
      "subject": "act-english",
      "question_id": "ti-gen-2b9ae16d270c28ea",
      "rung": 1,
      "body_md": "What do you think about the verb form used in the sentence? Does it seem correct to you?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e64bbbcf6b57418187bf9dfc859d90b5"
  },
  {
      "id": "h-gen-42bcf14ac3f7e61e",
      "subject": "act-english",
      "question_id": "ti-gen-2b9ae16d270c28ea",
      "rung": 2,
      "body_md": "Remember that subjects and verbs must agree in number. What does this mean for singular and plural forms?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e64bbbcf6b57418187bf9dfc859d90b5"
  },
  {
      "id": "h-gen-0feaa9c80ad1a04f",
      "subject": "act-english",
      "question_id": "ti-gen-2b9ae16d270c28ea",
      "rung": 3,
      "body_md": "Look closely at the subject of the sentence. Consider how it relates to the verb and whether they match in number.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e64bbbcf6b57418187bf9dfc859d90b5"
  },
  {
      "id": "h-gen-b2adf1a3d8ae715c",
      "subject": "act-english",
      "question_id": "ti-gen-2e0a772869e0c812",
      "rung": 1,
      "body_md": "What do you think is the main issue with the bridge design mentioned in the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b7d384069be2499f8e5448f1fa53820b"
  },
  {
      "id": "h-gen-9e54cf5938738cbb",
      "subject": "act-english",
      "question_id": "ti-gen-2e0a772869e0c812",
      "rung": 2,
      "body_md": "Consider how different words can describe the severity of a design flaw. What terms might indicate a more serious problem?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b7d384069be2499f8e5448f1fa53820b"
  },
  {
      "id": "h-gen-1de9a130afd05040",
      "subject": "act-english",
      "question_id": "ti-gen-2e0a772869e0c812",
      "rung": 3,
      "body_md": "Look closely at the options and think about how each choice conveys the design's ability to handle sudden gusts. Which option suggests a more definitive failure?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b7d384069be2499f8e5448f1fa53820b"
  },
  {
      "id": "h-gen-38286853fa7759b8",
      "subject": "act-english",
      "question_id": "ti-gen-2e3eda6d9075d574",
      "rung": 1,
      "body_md": "What do you think is the most important aspect of the surgeon's report regarding the incision?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c075aef3b6ab478d844fa0182ef4716a"
  },
  {
      "id": "h-gen-7c3e009749286122",
      "subject": "act-english",
      "question_id": "ti-gen-2e3eda6d9075d574",
      "rung": 2,
      "body_md": "Consider the concept of accuracy in surgical procedures; what term describes a high level of exactness?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c075aef3b6ab478d844fa0182ef4716a"
  },
  {
      "id": "h-gen-4077a5b666a99cf3",
      "subject": "act-english",
      "question_id": "ti-gen-2e3eda6d9075d574",
      "rung": 3,
      "body_md": "Look closely at the options provided and think about which word best conveys the idea of needing to be very careful and exact in a surgical context.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c075aef3b6ab478d844fa0182ef4716a"
  },
  {
      "id": "h-gen-9e8d4f5cbe6ea792",
      "subject": "act-english",
      "question_id": "ti-gen-2ec3664d2b4e817b",
      "rung": 1,
      "body_md": "What do you think the phrase 'tie your hands' implies about the client's options in a legal context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@742982a02c194b42aa23b392315eab12"
  },
  {
      "id": "h-gen-6a6e85a43e7b766c",
      "subject": "act-english",
      "question_id": "ti-gen-2ec3664d2b4e817b",
      "rung": 2,
      "body_md": "Consider the importance of using formal language in legal documents and how it affects clarity.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@742982a02c194b42aa23b392315eab12"
  },
  {
      "id": "h-gen-d6acb2962f5f1ed5",
      "subject": "act-english",
      "question_id": "ti-gen-2ec3664d2b4e817b",
      "rung": 3,
      "body_md": "Look closely at the implications of the underlined phrase and think about how it relates to the client's future choices.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@742982a02c194b42aa23b392315eab12"
  },
  {
      "id": "h-gen-98b799a9834f3ea7",
      "subject": "act-english",
      "question_id": "ti-gen-2fddf2bbbfb1b061",
      "rung": 1,
      "body_md": "What do you think the phrase 'consistent to' means in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bfea31359cb34f868096a878216c3ae1"
  },
  {
      "id": "h-gen-98e33c877dc34415",
      "subject": "act-english",
      "question_id": "ti-gen-2fddf2bbbfb1b061",
      "rung": 2,
      "body_md": "Consider how idiomatic expressions often have specific prepositions that are used with them.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bfea31359cb34f868096a878216c3ae1"
  },
  {
      "id": "h-gen-6d5876550f08c27e",
      "subject": "act-english",
      "question_id": "ti-gen-2fddf2bbbfb1b061",
      "rung": 3,
      "body_md": "Look at the relationship between the results and the hypothesis; think about common phrases that describe this relationship.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bfea31359cb34f868096a878216c3ae1"
  },
  {
      "id": "h-gen-5f2312c8a941a41d",
      "subject": "act-english",
      "question_id": "ti-gen-31665b0a1bd7961d",
      "rung": 1,
      "body_md": "What do you think about the way the information about the spring is presented in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@80ad5f7b8d2a4a7e847e3b2a2f07a197"
  },
  {
      "id": "h-gen-8fda66d9bdc5b895",
      "subject": "act-english",
      "question_id": "ti-gen-31665b0a1bd7961d",
      "rung": 2,
      "body_md": "Consider the rules regarding the use of parentheses in writing. What do you know about how they should be used?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@80ad5f7b8d2a4a7e847e3b2a2f07a197"
  },
  {
      "id": "h-gen-443a6ff850b5b239",
      "subject": "act-english",
      "question_id": "ti-gen-31665b0a1bd7961d",
      "rung": 3,
      "body_md": "Look closely at the punctuation around the additional information about the spring. How does it relate to the main sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@80ad5f7b8d2a4a7e847e3b2a2f07a197"
  },
  {
      "id": "h-gen-6caae0f301eb2eab",
      "subject": "act-english",
      "question_id": "ti-gen-31e0a62ecc0b5a4f",
      "rung": 1,
      "body_md": "What do you think makes a good tour guide?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d2ad3310747f4ab5ac53ac7ba1fc4e85"
  },
  {
      "id": "h-gen-bea7cc25fe273938",
      "subject": "act-english",
      "question_id": "ti-gen-31e0a62ecc0b5a4f",
      "rung": 2,
      "body_md": "Consider how items in a list should be structured to maintain consistency.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d2ad3310747f4ab5ac53ac7ba1fc4e85"
  },
  {
      "id": "h-gen-9c3b79b17f65ebcd",
      "subject": "act-english",
      "question_id": "ti-gen-31e0a62ecc0b5a4f",
      "rung": 3,
      "body_md": "Look closely at the qualities listed and check if they all share the same grammatical form.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d2ad3310747f4ab5ac53ac7ba1fc4e85"
  },
  {
      "id": "h-gen-5a0606cfdecc91bf",
      "subject": "act-english",
      "question_id": "ti-gen-34265d79953a3867",
      "rung": 1,
      "body_md": "What do you think is the best way to separate items in a list?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a6254663c8db4f8793c50a2653434fbf"
  },
  {
      "id": "h-gen-fdf566a1280a658f",
      "subject": "act-english",
      "question_id": "ti-gen-34265d79953a3867",
      "rung": 2,
      "body_md": "In general, how do we punctuate items in a series?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a6254663c8db4f8793c50a2653434fbf"
  },
  {
      "id": "h-gen-07b7c416b1b1894b",
      "subject": "act-english",
      "question_id": "ti-gen-34265d79953a3867",
      "rung": 3,
      "body_md": "Look closely at the items in the series and consider how they are connected. Pay attention to the punctuation that separates them.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a6254663c8db4f8793c50a2653434fbf"
  },
  {
      "id": "h-gen-a9d3750225552b56",
      "subject": "act-english",
      "question_id": "ti-gen-36eb52579d0ef14b",
      "rung": 1,
      "body_md": "What do you think is the main issue with the current sentence structure?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7e21dac4e41448d790c9dc0aa5d3bad2"
  },
  {
      "id": "h-gen-c9b633e4f6b31e41",
      "subject": "act-english",
      "question_id": "ti-gen-36eb52579d0ef14b",
      "rung": 2,
      "body_md": "Consider how modifiers should relate to the nouns they describe.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7e21dac4e41448d790c9dc0aa5d3bad2"
  },
  {
      "id": "h-gen-71749f95d049a50d",
      "subject": "act-english",
      "question_id": "ti-gen-36eb52579d0ef14b",
      "rung": 3,
      "body_md": "Look closely at the subject of the action in the underlined phrase and see if it matches the noun performing the action.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7e21dac4e41448d790c9dc0aa5d3bad2"
  },
  {
      "id": "h-gen-e2661d72ca03c583",
      "subject": "act-english",
      "question_id": "ti-gen-36ee7811583ee9f3",
      "rung": 1,
      "body_md": "What do you think is the most important aspect of maintaining a consistent daily routine in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ca754c50c224f9d98b28aec313012e8"
  },
  {
      "id": "h-gen-098f8f17dca08690",
      "subject": "act-english",
      "question_id": "ti-gen-36ee7811583ee9f3",
      "rung": 2,
      "body_md": "Consider how verb tense can affect the perception of routine and consistency in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ca754c50c224f9d98b28aec313012e8"
  },
  {
      "id": "h-gen-8e63b05a2c820f17",
      "subject": "act-english",
      "question_id": "ti-gen-36ee7811583ee9f3",
      "rung": 3,
      "body_md": "Look closely at the verb in the underlined phrase and think about how it relates to the other verbs in the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ca754c50c224f9d98b28aec313012e8"
  },
  {
      "id": "h-gen-02b2c9da9596a7f0",
      "subject": "act-english",
      "question_id": "ti-gen-38b5fe785ba95a5a",
      "rung": 1,
      "body_md": "What do you think about the way the two parts of the sentence are connected?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@56b6a21a24304cfdab362c67445157d6"
  },
  {
      "id": "h-gen-de5c68a7a060eb99",
      "subject": "act-english",
      "question_id": "ti-gen-38b5fe785ba95a5a",
      "rung": 2,
      "body_md": "Consider the rule about how to properly separate independent clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@56b6a21a24304cfdab362c67445157d6"
  },
  {
      "id": "h-gen-e100442c46df463f",
      "subject": "act-english",
      "question_id": "ti-gen-38b5fe785ba95a5a",
      "rung": 3,
      "body_md": "Look closely at where the first part of the sentence ends and think about how to properly punctuate the connection to the second part.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@56b6a21a24304cfdab362c67445157d6"
  },
  {
      "id": "h-gen-32cc4a8c740f2286",
      "subject": "act-english",
      "question_id": "ti-gen-3a1b53fce3a96f39",
      "rung": 1,
      "body_md": "What do you think about the punctuation used at the beginning of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9be810f7705243e6b8a8ed2156d5b4fd"
  },
  {
      "id": "h-gen-e4dd7ed7277aecda",
      "subject": "act-english",
      "question_id": "ti-gen-3a1b53fce3a96f39",
      "rung": 2,
      "body_md": "Consider the rule regarding punctuation after long introductory phrases.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9be810f7705243e6b8a8ed2156d5b4fd"
  },
  {
      "id": "h-gen-5dad510c7e26b67b",
      "subject": "act-english",
      "question_id": "ti-gen-3a1b53fce3a96f39",
      "rung": 3,
      "body_md": "Look closely at the punctuation options and think about how they relate to the structure of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9be810f7705243e6b8a8ed2156d5b4fd"
  },
  {
      "id": "h-gen-d52415a431ce67f2",
      "subject": "act-english",
      "question_id": "ti-gen-3b087ff10d6b4c60",
      "rung": 1,
      "body_md": "What do you think the mood of the passage is, and how does it make you feel about the pier?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ba05126624d4463e8668f3f612067d44"
  },
  {
      "id": "h-gen-213aa527324178a7",
      "subject": "act-english",
      "question_id": "ti-gen-3b087ff10d6b4c60",
      "rung": 2,
      "body_md": "Consider how word choice can influence the mood of a description, especially in relation to age and weathering.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ba05126624d4463e8668f3f612067d44"
  },
  {
      "id": "h-gen-c314ab47e95bc791",
      "subject": "act-english",
      "question_id": "ti-gen-3b087ff10d6b4c60",
      "rung": 3,
      "body_md": "Look closely at the words used to describe the pier and think about which options convey a sense of wear and exposure to the elements.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ba05126624d4463e8668f3f612067d44"
  },
  {
      "id": "h-gen-86b2f046a0311d67",
      "subject": "act-english",
      "question_id": "ti-gen-3d16a3afd16b2422",
      "rung": 1,
      "body_md": "What do you think about the phrase used to describe the mayor's change in position?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@25a21865b8554fcabf60c2fdda06ba1f"
  },
  {
      "id": "h-gen-fa87216a61018b01",
      "subject": "act-english",
      "question_id": "ti-gen-3d16a3afd16b2422",
      "rung": 2,
      "body_md": "Consider the concept of redundancy in language. What does it mean for a phrase to be redundant?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@25a21865b8554fcabf60c2fdda06ba1f"
  },
  {
      "id": "h-gen-eb17e8721fbb5511",
      "subject": "act-english",
      "question_id": "ti-gen-3d16a3afd16b2422",
      "rung": 3,
      "body_md": "Look closely at the expression used to describe the reversal. Are there any words that might be unnecessary or repetitive?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@25a21865b8554fcabf60c2fdda06ba1f"
  },
  {
      "id": "h-gen-a0ec4f5b7ac176fd",
      "subject": "act-english",
      "question_id": "ti-gen-3d7b1786e115d2ae",
      "rung": 1,
      "body_md": "What do you think about the verb phrase in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d32f977e223342ac9cbf716499f34e7e"
  },
  {
      "id": "h-gen-2db2d746db5d9385",
      "subject": "act-english",
      "question_id": "ti-gen-3d7b1786e115d2ae",
      "rung": 2,
      "body_md": "Consider the rule regarding the correct form of modal verbs followed by 'have'.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d32f977e223342ac9cbf716499f34e7e"
  },
  {
      "id": "h-gen-383c0c276c89ae40",
      "subject": "act-english",
      "question_id": "ti-gen-3d7b1786e115d2ae",
      "rung": 3,
      "body_md": "Look closely at the structure of the verb phrase and compare it to standard forms of modal verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d32f977e223342ac9cbf716499f34e7e"
  },
  {
      "id": "h-gen-31bffdc26bd904cc",
      "subject": "act-english",
      "question_id": "ti-gen-3f067badd58987d9",
      "rung": 1,
      "body_md": "What do you think is the relationship between the two statements in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@63c3260d92444437bed990bda1f48a13"
  },
  {
      "id": "h-gen-8f10d01574283d71",
      "subject": "act-english",
      "question_id": "ti-gen-3f067badd58987d9",
      "rung": 2,
      "body_md": "Consider how independent clauses are connected in English. What punctuation or conjunctions are typically used?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@63c3260d92444437bed990bda1f48a13"
  },
  {
      "id": "h-gen-513779c1128b2f94",
      "subject": "act-english",
      "question_id": "ti-gen-3f067badd58987d9",
      "rung": 3,
      "body_md": "Look closely at how the two statements are structured. Check where the first statement ends and think about how to properly connect it to the second.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@63c3260d92444437bed990bda1f48a13"
  },
  {
      "id": "h-gen-fcba7fa3d5e364dc",
      "subject": "act-english",
      "question_id": "ti-gen-4026afc5e8d79eba",
      "rung": 1,
      "body_md": "What do you think is the main focus of the article regarding the falcon's recovery?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fd2b035e753a44c2b3fafc9b87727e68"
  },
  {
      "id": "h-gen-83225b9ee19ed5ae",
      "subject": "act-english",
      "question_id": "ti-gen-4026afc5e8d79eba",
      "rung": 2,
      "body_md": "Consider how each option relates to the causes of the falcon's comeback.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fd2b035e753a44c2b3fafc9b87727e68"
  },
  {
      "id": "h-gen-8f8622c4d88dca80",
      "subject": "act-english",
      "question_id": "ti-gen-4026afc5e8d79eba",
      "rung": 3,
      "body_md": "Look for the choice that continues the discussion of actions taken to support the falcon's recovery.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fd2b035e753a44c2b3fafc9b87727e68"
  },
  {
      "id": "h-gen-d4ae604753fa05dc",
      "subject": "act-english",
      "question_id": "ti-gen-42a0f73fda4c2917",
      "rung": 1,
      "body_md": "What do you think the phrase in question is trying to convey in the context of the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@401c45cdfb724af189d2b1ba44b85360"
  },
  {
      "id": "h-gen-ffec402f97dbd26a",
      "subject": "act-english",
      "question_id": "ti-gen-42a0f73fda4c2917",
      "rung": 2,
      "body_md": "Consider how connectives function in sentences. What role does a connective play in linking ideas?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@401c45cdfb724af189d2b1ba44b85360"
  },
  {
      "id": "h-gen-3f357db22df18179",
      "subject": "act-english",
      "question_id": "ti-gen-42a0f73fda4c2917",
      "rung": 3,
      "body_md": "Look closely at the structure of the phrase. How does the presence of a noun or clause affect the choice of connective?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@401c45cdfb724af189d2b1ba44b85360"
  },
  {
      "id": "h-gen-0668960133c2d47b",
      "subject": "act-english",
      "question_id": "ti-gen-45cb88c727550efa",
      "rung": 1,
      "body_md": "What do you think is the main focus of the comparison between the two routes?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@baaef435c68141bda7a25c9a6502852d"
  },
  {
      "id": "h-gen-7443b5bbe93c7d96",
      "subject": "act-english",
      "question_id": "ti-gen-45cb88c727550efa",
      "rung": 2,
      "body_md": "Consider the difference between comparative and superlative forms in English.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@baaef435c68141bda7a25c9a6502852d"
  },
  {
      "id": "h-gen-e91b5d345742d036",
      "subject": "act-english",
      "question_id": "ti-gen-45cb88c727550efa",
      "rung": 3,
      "body_md": "Look closely at how the two routes are being compared and think about the grammatical structure used to express that comparison.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@baaef435c68141bda7a25c9a6502852d"
  },
  {
      "id": "h-gen-91b076ec8ef04dda",
      "subject": "act-english",
      "question_id": "ti-gen-473761e950feceac",
      "rung": 1,
      "body_md": "What do you think the detective's feelings are towards the gray sedan?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@402e8e6eed4e48eeb8bc32718355ea6b"
  },
  {
      "id": "h-gen-64b5b70e07713ae6",
      "subject": "act-english",
      "question_id": "ti-gen-473761e950feceac",
      "rung": 2,
      "body_md": "Consider the concept of how curiosity can lead to a sense of caution or wariness.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@402e8e6eed4e48eeb8bc32718355ea6b"
  },
  {
      "id": "h-gen-79a0b4cb91b156ea",
      "subject": "act-english",
      "question_id": "ti-gen-473761e950feceac",
      "rung": 3,
      "body_md": "Look closely at the context of the situation and think about how the detective's repeated observations might influence their feelings.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@402e8e6eed4e48eeb8bc32718355ea6b"
  },
  {
      "id": "h-gen-8162b3e7a97536f3",
      "subject": "act-english",
      "question_id": "ti-gen-48ea13424888c8b4",
      "rung": 1,
      "body_md": "What do you think about the punctuation used in the phrase regarding the location and date?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3c5f4a90bbb49a88423cdb8dfb5e003"
  },
  {
      "id": "h-gen-5e14ec820cd9a75e",
      "subject": "act-english",
      "question_id": "ti-gen-48ea13424888c8b4",
      "rung": 2,
      "body_md": "Consider the general rule about using commas with state names and dates.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3c5f4a90bbb49a88423cdb8dfb5e003"
  },
  {
      "id": "h-gen-a485059d8f8c24e6",
      "subject": "act-english",
      "question_id": "ti-gen-48ea13424888c8b4",
      "rung": 3,
      "body_md": "Look closely at how the punctuation is applied around the state name and the date in the underlined phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3c5f4a90bbb49a88423cdb8dfb5e003"
  },
  {
      "id": "h-gen-e36745ea20c0b6b9",
      "subject": "act-english",
      "question_id": "ti-gen-48ebd8c087d04821",
      "rung": 1,
      "body_md": "What do you think about how to show ownership in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2b2204f2502c4dc8bac5398d6ae273a8"
  },
  {
      "id": "h-gen-1afade817e655a10",
      "subject": "act-english",
      "question_id": "ti-gen-48ebd8c087d04821",
      "rung": 2,
      "body_md": "Remember that possessive forms indicate ownership and typically involve an apostrophe.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2b2204f2502c4dc8bac5398d6ae273a8"
  },
  {
      "id": "h-gen-7e3337b34c43b53f",
      "subject": "act-english",
      "question_id": "ti-gen-48ebd8c087d04821",
      "rung": 3,
      "body_md": "Consider how many owners are involved in this situation and check the placement of the apostrophe.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2b2204f2502c4dc8bac5398d6ae273a8"
  },
  {
      "id": "h-gen-b515db47a4278ec4",
      "subject": "act-english",
      "question_id": "ti-gen-48ed4ba18f05609d",
      "rung": 1,
      "body_md": "What do you think the writer is trying to convey about the neighbors' actions after the flood?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ffb20706215f45ee9ffba6a14c9ebaaf"
  },
  {
      "id": "h-gen-7ba4ebdc2266d512",
      "subject": "act-english",
      "question_id": "ti-gen-48ed4ba18f05609d",
      "rung": 2,
      "body_md": "Consider how different verbs can imply varying levels of effort and involvement.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ffb20706215f45ee9ffba6a14c9ebaaf"
  },
  {
      "id": "h-gen-53ceab25235f004e",
      "subject": "act-english",
      "question_id": "ti-gen-48ed4ba18f05609d",
      "rung": 3,
      "body_md": "Look closely at the verbs in the answer choices and think about which one suggests the most intense or sustained effort.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ffb20706215f45ee9ffba6a14c9ebaaf"
  },
  {
      "id": "h-gen-b51b40da9d1fbf1a",
      "subject": "act-english",
      "question_id": "ti-gen-49679201bbbf2fb9",
      "rung": 1,
      "body_md": "What do you think about how the phrase regarding the lighthouse's construction fits into the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b0ddd1b153a24110a176132536d8d634"
  },
  {
      "id": "h-gen-3bc66210a2ea5912",
      "subject": "act-english",
      "question_id": "ti-gen-49679201bbbf2fb9",
      "rung": 2,
      "body_md": "Consider how additional information about a noun is typically set off in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b0ddd1b153a24110a176132536d8d634"
  },
  {
      "id": "h-gen-99526e9e58fb7719",
      "subject": "act-english",
      "question_id": "ti-gen-49679201bbbf2fb9",
      "rung": 3,
      "body_md": "Look closely at how the phrase is integrated into the sentence and check if it needs any punctuation to clarify its relationship to the main clause.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b0ddd1b153a24110a176132536d8d634"
  },
  {
      "id": "h-gen-9102a01b6b8a2ab1",
      "subject": "act-english",
      "question_id": "ti-gen-49ef4a599004b6c4",
      "rung": 1,
      "body_md": "What do you think about the tone of the word used to describe the laughter in the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3ea37d332a84ddfae2629b94e72671f"
  },
  {
      "id": "h-gen-1b053ff73c23adb3",
      "subject": "act-english",
      "question_id": "ti-gen-49ef4a599004b6c4",
      "rung": 2,
      "body_md": "Consider how different words can convey affection or criticism in descriptions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3ea37d332a84ddfae2629b94e72671f"
  },
  {
      "id": "h-gen-af9c4ad4e08f2d7c",
      "subject": "act-english",
      "question_id": "ti-gen-49ef4a599004b6c4",
      "rung": 3,
      "body_md": "Look closely at the connotations of the words in the answer choices and think about which one best reflects a positive sentiment.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c3ea37d332a84ddfae2629b94e72671f"
  },
  {
      "id": "h-gen-3ef7bc17d2c21b85",
      "subject": "act-english",
      "question_id": "ti-gen-49ef91abd4738e50",
      "rung": 1,
      "body_md": "Who do you think is being referred to by the pronoun in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9276156804f54ce68e9fd44fa8efe14a"
  },
  {
      "id": "h-gen-d891f996431d61a5",
      "subject": "act-english",
      "question_id": "ti-gen-49ef91abd4738e50",
      "rung": 2,
      "body_md": "Consider the rule that when a pronoun could refer to more than one person, it's often clearer to use a specific name.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9276156804f54ce68e9fd44fa8efe14a"
  },
  {
      "id": "h-gen-148279919f4bfda5",
      "subject": "act-english",
      "question_id": "ti-gen-49ef91abd4738e50",
      "rung": 3,
      "body_md": "Look closely at the context of the sentence and think about how the pronoun relates to the other names mentioned.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9276156804f54ce68e9fd44fa8efe14a"
  },
  {
      "id": "h-gen-868290b309c643d8",
      "subject": "act-english",
      "question_id": "ti-gen-4ae6a4ffb48ec23d",
      "rung": 1,
      "body_md": "What do you think about the verb tense used in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@470711b8a3da4748a285fb67fb757d9d"
  },
  {
      "id": "h-gen-9cc76408bf07d339",
      "subject": "act-english",
      "question_id": "ti-gen-4ae6a4ffb48ec23d",
      "rung": 2,
      "body_md": "Consider how verbs change form to indicate different times, especially irregular verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@470711b8a3da4748a285fb67fb757d9d"
  },
  {
      "id": "h-gen-2ee14a376387bf80",
      "subject": "act-english",
      "question_id": "ti-gen-4ae6a4ffb48ec23d",
      "rung": 3,
      "body_md": "Look closely at the verb in the underlined phrase and think about how it relates to the time described in the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@470711b8a3da4748a285fb67fb757d9d"
  },
  {
      "id": "h-gen-70d01089696d8c45",
      "subject": "act-english",
      "question_id": "ti-gen-4b220c8ea4c43178",
      "rung": 1,
      "body_md": "What do you think is the main idea conveyed by the underlined phrase in the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e43d0ce69f6465c886bcc9e839f1311"
  },
  {
      "id": "h-gen-e707c34cae66ebe7",
      "subject": "act-english",
      "question_id": "ti-gen-4b220c8ea4c43178",
      "rung": 2,
      "body_md": "Consider how definitions can vary in clarity and conciseness.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e43d0ce69f6465c886bcc9e839f1311"
  },
  {
      "id": "h-gen-47c223d94e4aea2e",
      "subject": "act-english",
      "question_id": "ti-gen-4b220c8ea4c43178",
      "rung": 3,
      "body_md": "Look closely at how each option describes the mixture; pay attention to unnecessary words or phrases that might make a definition less clear.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1e43d0ce69f6465c886bcc9e839f1311"
  },
  {
      "id": "h-gen-f5d8237372926186",
      "subject": "act-english",
      "question_id": "ti-gen-4b2651a209bf761f",
      "rung": 1,
      "body_md": "What do you think the writer is trying to convey about the vendors' display?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a73a2c1b8564466584f2abe41d4df438"
  },
  {
      "id": "h-gen-f463a9a57f68e9d4",
      "subject": "act-english",
      "question_id": "ti-gen-4b2651a209bf761f",
      "rung": 2,
      "body_md": "Consider the concept of deliberate action in writing. What verbs suggest intentionality?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a73a2c1b8564466584f2abe41d4df438"
  },
  {
      "id": "h-gen-a8359e2d23ca958c",
      "subject": "act-english",
      "question_id": "ti-gen-4b2651a209bf761f",
      "rung": 3,
      "body_md": "Look closely at the verbs in the answer choices. How do they each reflect the idea of careful arrangement or display?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a73a2c1b8564466584f2abe41d4df438"
  },
  {
      "id": "h-gen-b1bf439ab3339c24",
      "subject": "act-english",
      "question_id": "ti-gen-50b4dfc045bf65f3",
      "rung": 1,
      "body_md": "What do you think about the timing of the drying in relation to the judges' arrival?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@437fd75470214b3e94762a692082270d"
  },
  {
      "id": "h-gen-21174a2f87d680ff",
      "subject": "act-english",
      "question_id": "ti-gen-50b4dfc045bf65f3",
      "rung": 2,
      "body_md": "Consider how different verb tenses can indicate the sequence of events in the past.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@437fd75470214b3e94762a692082270d"
  },
  {
      "id": "h-gen-87a097d80bd2ab98",
      "subject": "act-english",
      "question_id": "ti-gen-50b4dfc045bf65f3",
      "rung": 3,
      "body_md": "Look closely at the verbs used in the options and think about which one suggests that the drying was completed before another past event.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@437fd75470214b3e94762a692082270d"
  },
  {
      "id": "h-gen-ef9b5263eb934267",
      "subject": "act-english",
      "question_id": "ti-gen-518721c8b8fb1534",
      "rung": 1,
      "body_md": "What do you think about the way the sentence introduces the new information about the museum?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@811e43659aed46b692a320566869f27a"
  },
  {
      "id": "h-gen-14e556abdf14c967",
      "subject": "act-english",
      "question_id": "ti-gen-518721c8b8fb1534",
      "rung": 2,
      "body_md": "Consider how different transition words can signal the relationship between ideas in a list.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@811e43659aed46b692a320566869f27a"
  },
  {
      "id": "h-gen-f649011c69befcb8",
      "subject": "act-english",
      "question_id": "ti-gen-518721c8b8fb1534",
      "rung": 3,
      "body_md": "Look closely at the beginning of the sentence and think about how it connects to the previous items in the list.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@811e43659aed46b692a320566869f27a"
  },
  {
      "id": "h-gen-3c4b5f1a3b270339",
      "subject": "act-english",
      "question_id": "ti-gen-545e646d68ef68ad",
      "rung": 1,
      "body_md": "What do you think is the main idea of the paragraph?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e18b513c2c35429dabc0f7c1c4048f9a"
  },
  {
      "id": "h-gen-02b2236b250eb25b",
      "subject": "act-english",
      "question_id": "ti-gen-545e646d68ef68ad",
      "rung": 2,
      "body_md": "A topic sentence should summarize the main point that all the supporting details in the paragraph relate to.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e18b513c2c35429dabc0f7c1c4048f9a"
  },
  {
      "id": "h-gen-c97ccc70eca0ec9d",
      "subject": "act-english",
      "question_id": "ti-gen-545e646d68ef68ad",
      "rung": 3,
      "body_md": "Consider how each option relates to the overall importance of bees in agriculture as discussed in the paragraph.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e18b513c2c35429dabc0f7c1c4048f9a"
  },
  {
      "id": "h-gen-b7e3fd2f43ba9d3f",
      "subject": "act-english",
      "question_id": "ti-gen-581a7c98b2ac9090",
      "rung": 1,
      "body_md": "What do you think is the best way to introduce a list in a sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7e8a64fb08a4191a503ed800f42c3d1"
  },
  {
      "id": "h-gen-9a532ac60d0f9734",
      "subject": "act-english",
      "question_id": "ti-gen-581a7c98b2ac9090",
      "rung": 2,
      "body_md": "Consider the rule that a punctuation mark can be used to introduce a list after a complete statement.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7e8a64fb08a4191a503ed800f42c3d1"
  },
  {
      "id": "h-gen-ba8d7080334e095c",
      "subject": "act-english",
      "question_id": "ti-gen-581a7c98b2ac9090",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence before the list to determine how it should be punctuated.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f7e8a64fb08a4191a503ed800f42c3d1"
  },
  {
      "id": "h-gen-a973ef0a560a6c55",
      "subject": "act-english",
      "question_id": "ti-gen-587deb3bbea41fa8",
      "rung": 1,
      "body_md": "What do you think is the main contrast being made in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@082c62c7f53348819bed5d7312347c29"
  },
  {
      "id": "h-gen-f4777c0c3779f966",
      "subject": "act-english",
      "question_id": "ti-gen-587deb3bbea41fa8",
      "rung": 2,
      "body_md": "Consider how contrasting ideas are typically punctuated in English.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@082c62c7f53348819bed5d7312347c29"
  },
  {
      "id": "h-gen-abae158d2005ed7f",
      "subject": "act-english",
      "question_id": "ti-gen-587deb3bbea41fa8",
      "rung": 3,
      "body_md": "Look closely at how the phrase that indicates the contrast is set off from the rest of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@082c62c7f53348819bed5d7312347c29"
  },
  {
      "id": "h-gen-f5f4e3a4333f9321",
      "subject": "act-english",
      "question_id": "ti-gen-5b62aae3d773b227",
      "rung": 1,
      "body_md": "What do you think is the best way to indicate the last step in a sequence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d07357874cdd493aac9d9aa88aac46e1"
  },
  {
      "id": "h-gen-ecd5eb6e7fae6bf0",
      "subject": "act-english",
      "question_id": "ti-gen-5b62aae3d773b227",
      "rung": 2,
      "body_md": "Consider how transitions can signal the order of events in a sequence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d07357874cdd493aac9d9aa88aac46e1"
  },
  {
      "id": "h-gen-4b991e54385a935e",
      "subject": "act-english",
      "question_id": "ti-gen-5b62aae3d773b227",
      "rung": 3,
      "body_md": "Look closely at the options and think about which transition would best indicate the conclusion of a series.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d07357874cdd493aac9d9aa88aac46e1"
  },
  {
      "id": "h-gen-79f6d078dc0c9d15",
      "subject": "act-english",
      "question_id": "ti-gen-5c506f2cebb6e381",
      "rung": 1,
      "body_md": "What do you think the correct word might be based on the context of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c848759af6f44471a5e9c46716ec733b"
  },
  {
      "id": "h-gen-5fd4b1c4d011c637",
      "subject": "act-english",
      "question_id": "ti-gen-5c506f2cebb6e381",
      "rung": 2,
      "body_md": "Consider the difference between 'there', 'their', and 'they're'. What does each word indicate in terms of meaning and usage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c848759af6f44471a5e9c46716ec733b"
  },
  {
      "id": "h-gen-8883ffc92602781a",
      "subject": "act-english",
      "question_id": "ti-gen-5c506f2cebb6e381",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence. What is the role of the underlined phrase in the context of the sentence? How does it relate to the tasks mentioned?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c848759af6f44471a5e9c46716ec733b"
  },
  {
      "id": "h-gen-0cbd69ba8f30dbf0",
      "subject": "act-english",
      "question_id": "ti-gen-60d11553962fd438",
      "rung": 1,
      "body_md": "What do you think the opening description is trying to convey about the situation?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f9d60637cf1a437280fe11ca1bae555f"
  },
  {
      "id": "h-gen-13fe5be6761d97bb",
      "subject": "act-english",
      "question_id": "ti-gen-60d11553962fd438",
      "rung": 2,
      "body_md": "Consider how modifiers relate to the nouns they describe in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f9d60637cf1a437280fe11ca1bae555f"
  },
  {
      "id": "h-gen-b67f41191e39a890",
      "subject": "act-english",
      "question_id": "ti-gen-60d11553962fd438",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence and identify which noun the opening description is intended to modify.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f9d60637cf1a437280fe11ca1bae555f"
  },
  {
      "id": "h-gen-0173879a155eaa43",
      "subject": "act-english",
      "question_id": "ti-gen-60df6286c7916681",
      "rung": 1,
      "body_md": "What do you think the mentors' comments reveal about their attitude towards her work?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9d6530b4c694b828e0f0b8ee88c2e9a"
  },
  {
      "id": "h-gen-709fb756f5f3a3f8",
      "subject": "act-english",
      "question_id": "ti-gen-60df6286c7916681",
      "rung": 2,
      "body_md": "Consider how different words can convey varying levels of support or endorsement.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9d6530b4c694b828e0f0b8ee88c2e9a"
  },
  {
      "id": "h-gen-e8c11031af1564df",
      "subject": "act-english",
      "question_id": "ti-gen-60df6286c7916681",
      "rung": 3,
      "body_md": "Look closely at the options and think about which word best captures a strong sense of advocacy.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9d6530b4c694b828e0f0b8ee88c2e9a"
  },
  {
      "id": "h-gen-ae9b284f078bd2fb",
      "subject": "act-english",
      "question_id": "ti-gen-61a600f134c0969a",
      "rung": 1,
      "body_md": "What do you think the sentence is trying to convey regarding the decision about Main Street?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a1a2719e5cb3469b8f7cbb279378348b"
  },
  {
      "id": "h-gen-1d787712b30f572e",
      "subject": "act-english",
      "question_id": "ti-gen-61a600f134c0969a",
      "rung": 2,
      "body_md": "Consider the function of the word that introduces alternatives in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a1a2719e5cb3469b8f7cbb279378348b"
  },
  {
      "id": "h-gen-3faa65c5c303a250",
      "subject": "act-english",
      "question_id": "ti-gen-61a600f134c0969a",
      "rung": 3,
      "body_md": "Look closely at the context of the underlined phrase and think about how it relates to making a choice.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a1a2719e5cb3469b8f7cbb279378348b"
  },
  {
      "id": "h-gen-8306d47bc3b81ef4",
      "subject": "act-english",
      "question_id": "ti-gen-630536b6545d348a",
      "rung": 1,
      "body_md": "What do you think about the tone of the phrase used in the report?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f13a3ea974242e2af745fd98cdb6dfb"
  },
  {
      "id": "h-gen-b18d8d92da89d7cc",
      "subject": "act-english",
      "question_id": "ti-gen-630536b6545d348a",
      "rung": 2,
      "body_md": "Consider how formal language differs from informal language in writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f13a3ea974242e2af745fd98cdb6dfb"
  },
  {
      "id": "h-gen-598bcb401adbce97",
      "subject": "act-english",
      "question_id": "ti-gen-630536b6545d348a",
      "rung": 3,
      "body_md": "Look closely at the end of the mayor's speech and think about how the wording fits with the overall tone of the article.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f13a3ea974242e2af745fd98cdb6dfb"
  },
  {
      "id": "h-gen-306d8d4954e89aef",
      "subject": "act-english",
      "question_id": "ti-gen-6320e41e5627b12e",
      "rung": 1,
      "body_md": "What do you think the writer is trying to convey about the eagle's dive?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5bbbe3975ce4deda0f438cc4c9f2e15"
  },
  {
      "id": "h-gen-fadfe1c329ea42f6",
      "subject": "act-english",
      "question_id": "ti-gen-6320e41e5627b12e",
      "rung": 2,
      "body_md": "Consider the concept of word choice and how it can convey different levels of intensity or emotion.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5bbbe3975ce4deda0f438cc4c9f2e15"
  },
  {
      "id": "h-gen-73f6ab78219970fc",
      "subject": "act-english",
      "question_id": "ti-gen-6320e41e5627b12e",
      "rung": 3,
      "body_md": "Look closely at the options and think about which words might evoke a sense of wonder or amazement in relation to speed.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c5bbbe3975ce4deda0f438cc4c9f2e15"
  },
  {
      "id": "h-gen-5e6efb60aa10b994",
      "subject": "act-english",
      "question_id": "ti-gen-64359f35eb3a32c2",
      "rung": 1,
      "body_md": "What do you think the phrase 'done stuff' conveys about the firefighter's contributions?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5db63f9b1e824802815acce3f8e7eb05"
  },
  {
      "id": "h-gen-8deb4ca25c45d4a6",
      "subject": "act-english",
      "question_id": "ti-gen-64359f35eb3a32c2",
      "rung": 2,
      "body_md": "Consider the tone typically used in formal tributes or obituaries.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5db63f9b1e824802815acce3f8e7eb05"
  },
  {
      "id": "h-gen-9e68f49b602192bb",
      "subject": "act-english",
      "question_id": "ti-gen-64359f35eb3a32c2",
      "rung": 3,
      "body_md": "Look closely at the options and think about which phrases might reflect a more respectful and dignified tone.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5db63f9b1e824802815acce3f8e7eb05"
  },
  {
      "id": "h-gen-8e933ded176fc29d",
      "subject": "act-english",
      "question_id": "ti-gen-65e9643edd0781d7",
      "rung": 1,
      "body_md": "What do you think is the main action that needs to be taken by the gymnasts in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9c24259bb3164da591d820cee237f9d4"
  },
  {
      "id": "h-gen-d86a7c3ae6f1c595",
      "subject": "act-english",
      "question_id": "ti-gen-65e9643edd0781d7",
      "rung": 2,
      "body_md": "Consider how infinitive phrases function in a sentence. What do they typically indicate or modify?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9c24259bb3164da591d820cee237f9d4"
  },
  {
      "id": "h-gen-89b4e1a3ee7ab028",
      "subject": "act-english",
      "question_id": "ti-gen-65e9643edd0781d7",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentences provided. Pay attention to who or what is being described as needing to perform the action.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9c24259bb3164da591d820cee237f9d4"
  },
  {
      "id": "h-gen-409a1c5720bda322",
      "subject": "act-english",
      "question_id": "ti-gen-66ffedcdd57fec1a",
      "rung": 1,
      "body_md": "What do you think the uncle is trying to convey with his warning about sudden gusts?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@841ea45323f54eec861776abfb67cec4"
  },
  {
      "id": "h-gen-f71a916966bf3e3a",
      "subject": "act-english",
      "question_id": "ti-gen-66ffedcdd57fec1a",
      "rung": 2,
      "body_md": "Consider the importance of being prepared for unexpected changes in sailing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@841ea45323f54eec861776abfb67cec4"
  },
  {
      "id": "h-gen-54757d96b74f7aef",
      "subject": "act-english",
      "question_id": "ti-gen-66ffedcdd57fec1a",
      "rung": 3,
      "body_md": "Look closely at the context of the warning and think about how it relates to the overall message about sailing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@841ea45323f54eec861776abfb67cec4"
  },
  {
      "id": "h-gen-5b75d6d4f09f6039",
      "subject": "act-english",
      "question_id": "ti-gen-670a5cc4945b3eb0",
      "rung": 1,
      "body_md": "What do you think about the phrase that starts the sentence? Do you find it clear or too wordy?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02531f01ea354e929a0934bb8bb30a49"
  },
  {
      "id": "h-gen-ff39bdf9882fcf1c",
      "subject": "act-english",
      "question_id": "ti-gen-670a5cc4945b3eb0",
      "rung": 2,
      "body_md": "Consider the concept of conciseness in writing. How can we express ideas more directly?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02531f01ea354e929a0934bb8bb30a49"
  },
  {
      "id": "h-gen-09a938986145af45",
      "subject": "act-english",
      "question_id": "ti-gen-670a5cc4945b3eb0",
      "rung": 3,
      "body_md": "Look closely at the beginning of the sentence. Which options might simplify the expression without losing meaning?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02531f01ea354e929a0934bb8bb30a49"
  },
  {
      "id": "h-gen-cbedb4cc71de0fa8",
      "subject": "act-english",
      "question_id": "ti-gen-689be41bb9faba70",
      "rung": 1,
      "body_md": "What do you think is the best way to compare the two weeks of practice?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8647b7a0d2404664b80320787e488444"
  },
  {
      "id": "h-gen-2fe588a754fd8c9c",
      "subject": "act-english",
      "question_id": "ti-gen-689be41bb9faba70",
      "rung": 2,
      "body_md": "When comparing actions or states, consider whether you need to use an adverb or an adjective.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8647b7a0d2404664b80320787e488444"
  },
  {
      "id": "h-gen-562c38f08b1784c5",
      "subject": "act-english",
      "question_id": "ti-gen-689be41bb9faba70",
      "rung": 3,
      "body_md": "Look closely at how the two weeks are being compared in terms of the manner of practice.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8647b7a0d2404664b80320787e488444"
  },
  {
      "id": "h-gen-f69a27194f6c50af",
      "subject": "act-english",
      "question_id": "ti-gen-6cb24370d8242f1b",
      "rung": 1,
      "body_md": "What do you think is important for maintaining consistency in a list of actions?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1838a19054964d03b988986226b12e63"
  },
  {
      "id": "h-gen-716f9084258751f5",
      "subject": "act-english",
      "question_id": "ti-gen-6cb24370d8242f1b",
      "rung": 2,
      "body_md": "Consider the rule of parallel structure in lists. What does it mean for items in a series to be parallel?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1838a19054964d03b988986226b12e63"
  },
  {
      "id": "h-gen-f6d4a3e9ec2af7c1",
      "subject": "act-english",
      "question_id": "ti-gen-6cb24370d8242f1b",
      "rung": 3,
      "body_md": "Look closely at the grammatical forms of the items in the series. How do they relate to each other, and where does the underlined phrase fit in?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1838a19054964d03b988986226b12e63"
  },
  {
      "id": "h-gen-582d59c0608626c5",
      "subject": "act-english",
      "question_id": "ti-gen-6d1b683baf09e036",
      "rung": 1,
      "body_md": "How do you think the performance of the understudy is being described in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@caba289dec1c49b3bb4a1987de846312"
  },
  {
      "id": "h-gen-67ff9ed0c55d05d4",
      "subject": "act-english",
      "question_id": "ti-gen-6d1b683baf09e036",
      "rung": 2,
      "body_md": "Consider the difference between adjectives and adverbs in describing actions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@caba289dec1c49b3bb4a1987de846312"
  },
  {
      "id": "h-gen-e91a1cfb608e786f",
      "subject": "act-english",
      "question_id": "ti-gen-6d1b683baf09e036",
      "rung": 3,
      "body_md": "Look closely at the word that modifies how the understudy performed; think about what type of word is needed to describe an action.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@caba289dec1c49b3bb4a1987de846312"
  },
  {
      "id": "h-gen-c309fb93373b5117",
      "subject": "act-english",
      "question_id": "ti-gen-6f0cd0d7341e719c",
      "rung": 1,
      "body_md": "What do you think the hikers are feeling after their long climb?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@59da9801c47c41ce9def82dd75ad56f3"
  },
  {
      "id": "h-gen-d2456fdcb924e37a",
      "subject": "act-english",
      "question_id": "ti-gen-6f0cd0d7341e719c",
      "rung": 2,
      "body_md": "Consider the concept of exhaustion and how it relates to physical states.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@59da9801c47c41ce9def82dd75ad56f3"
  },
  {
      "id": "h-gen-d1e79497f5e4f6ba",
      "subject": "act-english",
      "question_id": "ti-gen-6f0cd0d7341e719c",
      "rung": 3,
      "body_md": "Look closely at the context of the sentence and think about how the hikers' condition might be described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@59da9801c47c41ce9def82dd75ad56f3"
  },
  {
      "id": "h-gen-fd9faaf49bc1b82a",
      "subject": "act-english",
      "question_id": "ti-gen-6f9c0becf3f197f0",
      "rung": 1,
      "body_md": "What are your thoughts on how the underlined phrase fits into the overall sentence structure?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2e77bec300a4be394b204bfd2854413"
  },
  {
      "id": "h-gen-6ddfddb297b7c425",
      "subject": "act-english",
      "question_id": "ti-gen-6f9c0becf3f197f0",
      "rung": 2,
      "body_md": "Consider the role of conjunctive adverbs in a sentence. What punctuation is typically used around them when they interrupt a clause?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2e77bec300a4be394b204bfd2854413"
  },
  {
      "id": "h-gen-4a2c1788477c89ff",
      "subject": "act-english",
      "question_id": "ti-gen-6f9c0becf3f197f0",
      "rung": 3,
      "body_md": "Look closely at the placement of the underlined phrase within the sentence. How does it affect the flow and meaning of the surrounding text?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2e77bec300a4be394b204bfd2854413"
  },
  {
      "id": "h-gen-58e07e734e7e36e4",
      "subject": "act-english",
      "question_id": "ti-gen-6fee13e7f68d08ea",
      "rung": 1,
      "body_md": "What do you think the phrase 'meant a ton' conveys about Dana's feelings towards the scholarship committee?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbf41ef08b1d4ae387dc2d9b4dfd81bc"
  },
  {
      "id": "h-gen-f3f0ade0d7d5c337",
      "subject": "act-english",
      "question_id": "ti-gen-6fee13e7f68d08ea",
      "rung": 2,
      "body_md": "Consider the tone that is appropriate for a thank-you note. What qualities should the language reflect?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbf41ef08b1d4ae387dc2d9b4dfd81bc"
  },
  {
      "id": "h-gen-2450108c1ec77b7e",
      "subject": "act-english",
      "question_id": "ti-gen-6fee13e7f68d08ea",
      "rung": 3,
      "body_md": "Look closely at the options and think about which phrases express a sense of gratitude and respect. How do they compare in terms of warmth and formality?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbf41ef08b1d4ae387dc2d9b4dfd81bc"
  },
  {
      "id": "h-gen-e6be4d35f0172ec5",
      "subject": "act-english",
      "question_id": "ti-gen-6ff15380f6fcd522",
      "rung": 1,
      "body_md": "What do you think is the main focus of the comparison in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6505c21d76024537b681246232dbda7e"
  },
  {
      "id": "h-gen-ec82f7189cbee16d",
      "subject": "act-english",
      "question_id": "ti-gen-6ff15380f6fcd522",
      "rung": 2,
      "body_md": "Consider the importance of maintaining parallel structure in comparisons.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6505c21d76024537b681246232dbda7e"
  },
  {
      "id": "h-gen-3b1e05f4be1880c6",
      "subject": "act-english",
      "question_id": "ti-gen-6ff15380f6fcd522",
      "rung": 3,
      "body_md": "Look closely at how the verbs in the comparison relate to each other.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6505c21d76024537b681246232dbda7e"
  },
  {
      "id": "h-gen-10c58d0d51796d3d",
      "subject": "act-english",
      "question_id": "ti-gen-71d01781ee685ec2",
      "rung": 1,
      "body_md": "What do you think is the relationship between the calm morning and the stiff breeze that follows?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51ba2831bfa4482aa56f684cb236ca3b"
  },
  {
      "id": "h-gen-cb449467635b2667",
      "subject": "act-english",
      "question_id": "ti-gen-71d01781ee685ec2",
      "rung": 2,
      "body_md": "Consider how transitions can indicate a change in circumstances or conditions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51ba2831bfa4482aa56f684cb236ca3b"
  },
  {
      "id": "h-gen-ae0bf2a6d401ad5c",
      "subject": "act-english",
      "question_id": "ti-gen-71d01781ee685ec2",
      "rung": 3,
      "body_md": "Look closely at the context surrounding the underlined phrase to identify how the shift in weather is presented.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@51ba2831bfa4482aa56f684cb236ca3b"
  },
  {
      "id": "h-gen-2b1545b9a9239ce7",
      "subject": "act-english",
      "question_id": "ti-gen-725c2513c059a420",
      "rung": 1,
      "body_md": "What do you think the players were trying to communicate based on the coach's silence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1fb87a19e22d45d988ebc15d63d593c4"
  },
  {
      "id": "h-gen-5879c1be438a134b",
      "subject": "act-english",
      "question_id": "ti-gen-725c2513c059a420",
      "rung": 2,
      "body_md": "Consider the difference between how a sender communicates a message and how a receiver interprets it.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1fb87a19e22d45d988ebc15d63d593c4"
  },
  {
      "id": "h-gen-c6371524f22b30e2",
      "subject": "act-english",
      "question_id": "ti-gen-725c2513c059a420",
      "rung": 3,
      "body_md": "Look closely at the relationship between the players' understanding and the coach's actions; think about what the players might have concluded from the situation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1fb87a19e22d45d988ebc15d63d593c4"
  },
  {
      "id": "h-gen-97c7b9af4904bb6d",
      "subject": "act-english",
      "question_id": "ti-gen-74185039391e8c26",
      "rung": 1,
      "body_md": "What do you think about the phrase that mentions the time of the meeting?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2229904369f4498975e709d112cd056"
  },
  {
      "id": "h-gen-bef42f86a496a1ac",
      "subject": "act-english",
      "question_id": "ti-gen-74185039391e8c26",
      "rung": 2,
      "body_md": "Consider the concept of redundancy in language; how can we avoid repeating the same information?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2229904369f4498975e709d112cd056"
  },
  {
      "id": "h-gen-00f1d6b84626c143",
      "subject": "act-english",
      "question_id": "ti-gen-74185039391e8c26",
      "rung": 3,
      "body_md": "Look closely at the structure of the time reference; are there any parts that convey the same meaning?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f2229904369f4498975e709d112cd056"
  },
  {
      "id": "h-gen-fcf0b2b9c5ee39f3",
      "subject": "act-english",
      "question_id": "ti-gen-742799c550a58e1a",
      "rung": 1,
      "body_md": "What do you think the main action of the bridge is in relation to the gorge?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@16be3d27796d4246af4b5fea4039e80c"
  },
  {
      "id": "h-gen-bba2f8b3ade889c8",
      "subject": "act-english",
      "question_id": "ti-gen-742799c550a58e1a",
      "rung": 2,
      "body_md": "Consider what it means for a structure to connect two points in a way that emphasizes its function.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@16be3d27796d4246af4b5fea4039e80c"
  },
  {
      "id": "h-gen-e312cba4545b8f9c",
      "subject": "act-english",
      "question_id": "ti-gen-742799c550a58e1a",
      "rung": 3,
      "body_md": "Look closely at the verbs used in the choices and think about which one best describes the relationship between the bridge and the gorge.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@16be3d27796d4246af4b5fea4039e80c"
  },
  {
      "id": "h-gen-5cba48627f423c7c",
      "subject": "act-english",
      "question_id": "ti-gen-75ffdc935d7018d9",
      "rung": 1,
      "body_md": "What do you think about the way the two words in the underlined phrase are connected?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bed0d7d2f7054103a7166e77c0fd07c2"
  },
  {
      "id": "h-gen-8ecacfb4763e22ef",
      "subject": "act-english",
      "question_id": "ti-gen-75ffdc935d7018d9",
      "rung": 2,
      "body_md": "Consider the rules for hyphenating compound modifiers that appear before a noun.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bed0d7d2f7054103a7166e77c0fd07c2"
  },
  {
      "id": "h-gen-1380717223e32ffd",
      "subject": "act-english",
      "question_id": "ti-gen-75ffdc935d7018d9",
      "rung": 3,
      "body_md": "Look closely at the relationship between the two words in the underlined phrase and check if they need a hyphen when used together.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bed0d7d2f7054103a7166e77c0fd07c2"
  },
  {
      "id": "h-gen-9fac26036e6e6795",
      "subject": "act-english",
      "question_id": "ti-gen-760a68005523b0ff",
      "rung": 1,
      "body_md": "What are your initial thoughts about the mentor's role in the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6456e790c3604c2a9b91830b23d413e5"
  },
  {
      "id": "h-gen-75538a4513050a85",
      "subject": "act-english",
      "question_id": "ti-gen-760a68005523b0ff",
      "rung": 2,
      "body_md": "Consider how details about a mentor can influence the perception of a situation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6456e790c3604c2a9b91830b23d413e5"
  },
  {
      "id": "h-gen-3474effd56a65d54",
      "subject": "act-english",
      "question_id": "ti-gen-760a68005523b0ff",
      "rung": 3,
      "body_md": "Look closely at the context surrounding the mentor's actions and how they relate to the narrator's expectations.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6456e790c3604c2a9b91830b23d413e5"
  },
  {
      "id": "h-gen-9c21ee1d12662964",
      "subject": "act-english",
      "question_id": "ti-gen-7ac43692a538ced7",
      "rung": 1,
      "body_md": "What do you think about the word used to refer to the person Amara credits?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@014c88e5dc8d465399ed0afc1fcd55a7"
  },
  {
      "id": "h-gen-bf424f9baec7e489",
      "subject": "act-english",
      "question_id": "ti-gen-7ac43692a538ced7",
      "rung": 2,
      "body_md": "Consider the difference between using 'who', 'whom', 'whose', and 'which' when referring to people.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@014c88e5dc8d465399ed0afc1fcd55a7"
  },
  {
      "id": "h-gen-c058e69e2f2b675e",
      "subject": "act-english",
      "question_id": "ti-gen-7ac43692a538ced7",
      "rung": 3,
      "body_md": "Look closely at the relationship between Amara and the person she credits. How does that relationship influence the choice of word?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@014c88e5dc8d465399ed0afc1fcd55a7"
  },
  {
      "id": "h-gen-406a2ec75b9a1714",
      "subject": "act-english",
      "question_id": "ti-gen-7e0b194c1e8733c7",
      "rung": 1,
      "body_md": "What do you think about how the detail about the trainer is currently presented in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5b69fabc22074128b1242567364076e6"
  },
  {
      "id": "h-gen-4a3ae8983b866713",
      "subject": "act-english",
      "question_id": "ti-gen-7e0b194c1e8733c7",
      "rung": 2,
      "body_md": "Consider the concept of appositives, which are used to provide additional information about a noun.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5b69fabc22074128b1242567364076e6"
  },
  {
      "id": "h-gen-02ae7fffc474ee9f",
      "subject": "act-english",
      "question_id": "ti-gen-7e0b194c1e8733c7",
      "rung": 3,
      "body_md": "Look closely at how the detail about the trainer is integrated into the sentence. Check if it is presented as a full clause or a more concise phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5b69fabc22074128b1242567364076e6"
  },
  {
      "id": "h-gen-191984b508732f8e",
      "subject": "act-english",
      "question_id": "ti-gen-81857f7ae5f6aa04",
      "rung": 1,
      "body_md": "What do you think the phrase 'by watching' means in the context of reading the wind?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@68384388631b477e9ab09e784d8f9e38"
  },
  {
      "id": "h-gen-f4e3c2cd0d5d5cc0",
      "subject": "act-english",
      "question_id": "ti-gen-81857f7ae5f6aa04",
      "rung": 2,
      "body_md": "Consider how verb-plus-preposition combinations function in English. What role does the preposition play in these phrases?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@68384388631b477e9ab09e784d8f9e38"
  },
  {
      "id": "h-gen-5da89f8a2c72691b",
      "subject": "act-english",
      "question_id": "ti-gen-81857f7ae5f6aa04",
      "rung": 3,
      "body_md": "Look closely at the structure of the phrase in question. How does the preposition relate to the action of the verb in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@68384388631b477e9ab09e784d8f9e38"
  },
  {
      "id": "h-gen-05327f8333b0ec63",
      "subject": "act-english",
      "question_id": "ti-gen-84bd26e843217d93",
      "rung": 1,
      "body_md": "What do you think is the main difference between the farmers' market's past and present situation?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@468bb10934514d869f9b94c03a61948a"
  },
  {
      "id": "h-gen-71b7132a07866988",
      "subject": "act-english",
      "question_id": "ti-gen-84bd26e843217d93",
      "rung": 2,
      "body_md": "Consider how transitions can indicate a change in time or circumstances.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@468bb10934514d869f9b94c03a61948a"
  },
  {
      "id": "h-gen-e2ec2b65e7471f8a",
      "subject": "act-english",
      "question_id": "ti-gen-84bd26e843217d93",
      "rung": 3,
      "body_md": "Look closely at the relationship between the two parts of the sentence and think about how you might express a shift from one time period to another.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@468bb10934514d869f9b94c03a61948a"
  },
  {
      "id": "h-gen-1849fd68efe4c4f3",
      "subject": "act-english",
      "question_id": "ti-gen-85e2987f63fb5449",
      "rung": 1,
      "body_md": "What are your thoughts on how the introductory word affects the flow of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f23cf512d3004e9ebb07194dc6924303"
  },
  {
      "id": "h-gen-7fa39dc9332b3223",
      "subject": "act-english",
      "question_id": "ti-gen-85e2987f63fb5449",
      "rung": 2,
      "body_md": "Consider the general rule for punctuating introductory words in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f23cf512d3004e9ebb07194dc6924303"
  },
  {
      "id": "h-gen-6242fe08eed56437",
      "subject": "act-english",
      "question_id": "ti-gen-85e2987f63fb5449",
      "rung": 3,
      "body_md": "Look closely at how the introductory word connects to the rest of the sentence and check if a pause is needed.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f23cf512d3004e9ebb07194dc6924303"
  },
  {
      "id": "h-gen-759c5e3d4d60cf61",
      "subject": "act-english",
      "question_id": "ti-gen-87320507356d0f55",
      "rung": 1,
      "body_md": "What do you think about the nature of the decision described in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@14f92c9ca65b41ed9643d7ba4c5e6130"
  },
  {
      "id": "h-gen-ccc3258bc2c84fd2",
      "subject": "act-english",
      "question_id": "ti-gen-87320507356d0f55",
      "rung": 2,
      "body_md": "Consider the concept of a decision that is unwavering or unchangeable.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@14f92c9ca65b41ed9643d7ba4c5e6130"
  },
  {
      "id": "h-gen-19df0af09127321c",
      "subject": "act-english",
      "question_id": "ti-gen-87320507356d0f55",
      "rung": 3,
      "body_md": "Look closely at the qualities of the decision mentioned in the sentence and think about words that convey strength or certainty.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@14f92c9ca65b41ed9643d7ba4c5e6130"
  },
  {
      "id": "h-gen-9b058f955d0c05b1",
      "subject": "act-english",
      "question_id": "ti-gen-882e189eb5d38d67",
      "rung": 1,
      "body_md": "What do you think the word 'notorious' suggests about Dr. Okafor's reputation?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@034230c4aa024aa5af01de91b5543db7"
  },
  {
      "id": "h-gen-622895ac6805ca75",
      "subject": "act-english",
      "question_id": "ti-gen-882e189eb5d38d67",
      "rung": 2,
      "body_md": "Consider the difference between words that have a positive connotation and those that have a negative connotation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@034230c4aa024aa5af01de91b5543db7"
  },
  {
      "id": "h-gen-a0ef8fa1eae1d035",
      "subject": "act-english",
      "question_id": "ti-gen-882e189eb5d38d67",
      "rung": 3,
      "body_md": "Look closely at the context of the sentence and think about how the meaning of the underlined phrase relates to the overall impression of Dr. Okafor.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@034230c4aa024aa5af01de91b5543db7"
  },
  {
      "id": "h-gen-b1e506d32687fdcd",
      "subject": "act-english",
      "question_id": "ti-gen-888139978be5073c",
      "rung": 1,
      "body_md": "What do you think is being compared in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@653e61a36d1648de92c6c0c82db7677f"
  },
  {
      "id": "h-gen-703bc48a64dc58b9",
      "subject": "act-english",
      "question_id": "ti-gen-888139978be5073c",
      "rung": 2,
      "body_md": "When making comparisons, it's important to ensure that the items being compared are of the same type.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@653e61a36d1648de92c6c0c82db7677f"
  },
  {
      "id": "h-gen-fc1d4d1068c1f690",
      "subject": "act-english",
      "question_id": "ti-gen-888139978be5073c",
      "rung": 3,
      "body_md": "Consider what the underlined phrase is referring to and how it relates to the other finalists.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@653e61a36d1648de92c6c0c82db7677f"
  },
  {
      "id": "h-gen-f37b282269c3c5ed",
      "subject": "act-english",
      "question_id": "ti-gen-88873e730bb625d7",
      "rung": 1,
      "body_md": "What do you think is the main issue with the way the two printer problems are presented in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f34597aedd2c432d8ad82359ddd6080b"
  },
  {
      "id": "h-gen-90a1b5561fa335ee",
      "subject": "act-english",
      "question_id": "ti-gen-88873e730bb625d7",
      "rung": 2,
      "body_md": "Consider how different punctuation marks can connect related independent clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f34597aedd2c432d8ad82359ddd6080b"
  },
  {
      "id": "h-gen-c326fae51b8dd7b0",
      "subject": "act-english",
      "question_id": "ti-gen-88873e730bb625d7",
      "rung": 3,
      "body_md": "Look closely at how the two printer problems are structured and think about the punctuation that can effectively link them.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f34597aedd2c432d8ad82359ddd6080b"
  },
  {
      "id": "h-gen-07cf1f64edcb395e",
      "subject": "act-english",
      "question_id": "ti-gen-89c7ff6378446caf",
      "rung": 1,
      "body_md": "What do you think is the most appropriate action for a composer when creating music?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5cfcdfa1e14a4e60a401112b55def5f7"
  },
  {
      "id": "h-gen-05d823871ac4ab23",
      "subject": "act-english",
      "question_id": "ti-gen-89c7ff6378446caf",
      "rung": 2,
      "body_md": "Consider the specific terminology used in the context of music creation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5cfcdfa1e14a4e60a401112b55def5f7"
  },
  {
      "id": "h-gen-5d91007cf46641a4",
      "subject": "act-english",
      "question_id": "ti-gen-89c7ff6378446caf",
      "rung": 3,
      "body_md": "Look closely at the verb used in the underlined phrase and think about how it relates to the act of creating music.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5cfcdfa1e14a4e60a401112b55def5f7"
  },
  {
      "id": "h-gen-b8ba752515a5ac1b",
      "subject": "act-english",
      "question_id": "ti-gen-8af409b05a85324e",
      "rung": 1,
      "body_md": "What do you think is being compared in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e4f4847e32e642dab2074d588e100653"
  },
  {
      "id": "h-gen-37d9b79c6b1b6e32",
      "subject": "act-english",
      "question_id": "ti-gen-8af409b05a85324e",
      "rung": 2,
      "body_md": "Consider how comparisons are typically structured in English.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e4f4847e32e642dab2074d588e100653"
  },
  {
      "id": "h-gen-4aec2eedfa729452",
      "subject": "act-english",
      "question_id": "ti-gen-8af409b05a85324e",
      "rung": 3,
      "body_md": "Look closely at the phrase that follows the comparison to see what is being referenced.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@e4f4847e32e642dab2074d588e100653"
  },
  {
      "id": "h-gen-a4e592ea48474041",
      "subject": "act-english",
      "question_id": "ti-gen-8b41ed68ca64cc04",
      "rung": 1,
      "body_md": "What do you think about the phrase used to describe the treatment group's performance?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0a8ddf004e8d4488847089b5be335cf6"
  },
  {
      "id": "h-gen-091c3c103f90e73d",
      "subject": "act-english",
      "question_id": "ti-gen-8b41ed68ca64cc04",
      "rung": 2,
      "body_md": "Consider the importance of using objective and precise language in scientific writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0a8ddf004e8d4488847089b5be335cf6"
  },
  {
      "id": "h-gen-1a9e5f7e5c6408e6",
      "subject": "act-english",
      "question_id": "ti-gen-8b41ed68ca64cc04",
      "rung": 3,
      "body_md": "Look closely at the wording used to describe the comparison between the two groups and think about which term conveys the result in a more formal and scientific manner.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0a8ddf004e8d4488847089b5be335cf6"
  },
  {
      "id": "h-gen-5ac44c9c9f85e99d",
      "subject": "act-english",
      "question_id": "ti-gen-8f419a733dbba475",
      "rung": 1,
      "body_md": "What do you think about the sentence that mentions the difference between starters in San Francisco and Paris?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0930d4a7daa4441aa3c74709c89f19ae"
  },
  {
      "id": "h-gen-c7cd0eaaef979759",
      "subject": "act-english",
      "question_id": "ti-gen-8f419a733dbba475",
      "rung": 2,
      "body_md": "Consider how examples can support or illustrate a claim made in a text.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0930d4a7daa4441aa3c74709c89f19ae"
  },
  {
      "id": "h-gen-6401dbff9b1e16b9",
      "subject": "act-english",
      "question_id": "ti-gen-8f419a733dbba475",
      "rung": 3,
      "body_md": "Look at how the example relates to the main idea of the paragraph and whether it adds clarity or context.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0930d4a7daa4441aa3c74709c89f19ae"
  },
  {
      "id": "h-gen-b5677b5b2978821d",
      "subject": "act-english",
      "question_id": "ti-gen-8f7f2bbc3fc8fffc",
      "rung": 1,
      "body_md": "What do you think is the main idea behind how plants grow, especially for someone who is new to gardening?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4e2709c92cee4b7db2dd9ad53243a665"
  },
  {
      "id": "h-gen-1149c62870ce39b6",
      "subject": "act-english",
      "question_id": "ti-gen-8f7f2bbc3fc8fffc",
      "rung": 2,
      "body_md": "Consider how different phrases might explain the process of plants using sunlight to grow.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4e2709c92cee4b7db2dd9ad53243a665"
  },
  {
      "id": "h-gen-1f18038895d26907",
      "subject": "act-english",
      "question_id": "ti-gen-8f7f2bbc3fc8fffc",
      "rung": 3,
      "body_md": "Look closely at the options and think about which one uses simpler language that a beginner gardener would easily understand.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@4e2709c92cee4b7db2dd9ad53243a665"
  },
  {
      "id": "h-gen-849829563cf9ee27",
      "subject": "act-english",
      "question_id": "ti-gen-926e040affb783e5",
      "rung": 1,
      "body_md": "What do you think about the way ownership is expressed in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3c45a77b7161471daef86c3c4a977896"
  },
  {
      "id": "h-gen-36bda690669fb96f",
      "subject": "act-english",
      "question_id": "ti-gen-926e040affb783e5",
      "rung": 2,
      "body_md": "Consider the rule for showing joint ownership in English.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3c45a77b7161471daef86c3c4a977896"
  },
  {
      "id": "h-gen-ad04c15fe215a850",
      "subject": "act-english",
      "question_id": "ti-gen-926e040affb783e5",
      "rung": 3,
      "body_md": "Look closely at how the names are connected in the underlined phrase and think about how to indicate that they both own the podcast.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3c45a77b7161471daef86c3c4a977896"
  },
  {
      "id": "h-gen-151e81d19dea3c3d",
      "subject": "act-english",
      "question_id": "ti-gen-93dab2fe84ba3929",
      "rung": 1,
      "body_md": "What do you think the relationship is between the two sentences?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@777e47aafba34442bdf5b562eb374ca5"
  },
  {
      "id": "h-gen-7bbbe09838903379",
      "subject": "act-english",
      "question_id": "ti-gen-93dab2fe84ba3929",
      "rung": 2,
      "body_md": "Consider how transitions can indicate relationships such as agreement, contrast, or continuation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@777e47aafba34442bdf5b562eb374ca5"
  },
  {
      "id": "h-gen-e68d0a3635ad0d96",
      "subject": "act-english",
      "question_id": "ti-gen-93dab2fe84ba3929",
      "rung": 3,
      "body_md": "Look closely at how the second sentence relates to the first; think about whether it supports or contradicts the idea presented.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@777e47aafba34442bdf5b562eb374ca5"
  },
  {
      "id": "h-gen-5ec3d0b53f0a2910",
      "subject": "act-english",
      "question_id": "ti-gen-949378b918123353",
      "rung": 1,
      "body_md": "What do you think about the phrase 'super weird' in the context of a lab report?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159"
  },
  {
      "id": "h-gen-00dd4d40c30baab3",
      "subject": "act-english",
      "question_id": "ti-gen-949378b918123353",
      "rung": 2,
      "body_md": "Consider how word choice can affect the tone of a passage, especially in formal writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159"
  },
  {
      "id": "h-gen-21a015af09ac7d33",
      "subject": "act-english",
      "question_id": "ti-gen-949378b918123353",
      "rung": 3,
      "body_md": "Look closely at the tone of the entire sentence and think about how each option aligns with that tone.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b84a0e653d4545fab68539e5b35f7159"
  },
  {
      "id": "h-gen-588c2c0fcd00249d",
      "subject": "act-english",
      "question_id": "ti-gen-94e1f8044bd59460",
      "rung": 1,
      "body_md": "What do you think about how the opening clause connects to the main part of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0acf3e59979a4533b144c250d65112c4"
  },
  {
      "id": "h-gen-66d37529d9ad1b25",
      "subject": "act-english",
      "question_id": "ti-gen-94e1f8044bd59460",
      "rung": 2,
      "body_md": "Consider the rule regarding punctuation after introductory clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0acf3e59979a4533b144c250d65112c4"
  },
  {
      "id": "h-gen-c1968f1b2e0e9b7f",
      "subject": "act-english",
      "question_id": "ti-gen-94e1f8044bd59460",
      "rung": 3,
      "body_md": "Look closely at the end of the introductory clause and think about how it relates to the main clause that follows.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0acf3e59979a4533b144c250d65112c4"
  },
  {
      "id": "h-gen-96594f26f3b716cc",
      "subject": "act-english",
      "question_id": "ti-gen-97cf1d12c90d64ab",
      "rung": 1,
      "body_md": "What do you think the word in the underlined phrase conveys about the relationship between the design and the traditions?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6652f166a2274d8893795230923674ec"
  },
  {
      "id": "h-gen-360e0558ab496590",
      "subject": "act-english",
      "question_id": "ti-gen-97cf1d12c90d64ab",
      "rung": 2,
      "body_md": "Consider the concept of showing respect or tribute in design. What words might capture that idea?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6652f166a2274d8893795230923674ec"
  },
  {
      "id": "h-gen-e56de97fd9436be8",
      "subject": "act-english",
      "question_id": "ti-gen-97cf1d12c90d64ab",
      "rung": 3,
      "body_md": "Look closely at the meanings of the options provided. Which one suggests a deeper acknowledgment of traditions rather than just a passive recognition?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@6652f166a2274d8893795230923674ec"
  },
  {
      "id": "h-gen-61858663f1829fc0",
      "subject": "act-english",
      "question_id": "ti-gen-9879e8c22aac3eca",
      "rung": 1,
      "body_md": "What do you think the editorial is trying to convey about the levee's condition?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@36b66237fc6345d29f383d9b0e2f822c"
  },
  {
      "id": "h-gen-f03e814eacd1304d",
      "subject": "act-english",
      "question_id": "ti-gen-9879e8c22aac3eca",
      "rung": 2,
      "body_md": "Consider the concept of caution in decision-making and how it relates to potential risks.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@36b66237fc6345d29f383d9b0e2f822c"
  },
  {
      "id": "h-gen-4daa6829de4d073a",
      "subject": "act-english",
      "question_id": "ti-gen-9879e8c22aac3eca",
      "rung": 3,
      "body_md": "Look closely at the tone of the editorial and think about how it describes the consequences of ignoring the levee's issues.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@36b66237fc6345d29f383d9b0e2f822c"
  },
  {
      "id": "h-gen-709c8b3ba144d38b",
      "subject": "act-english",
      "question_id": "ti-gen-993e51faa7a5ba14",
      "rung": 1,
      "body_md": "What do you think the conclusion should reflect about the lighthouse's state at the beginning of the essay?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@65cccab0e7d949a1bec57d8d81c97907"
  },
  {
      "id": "h-gen-4033f242005e4a84",
      "subject": "act-english",
      "question_id": "ti-gen-993e51faa7a5ba14",
      "rung": 2,
      "body_md": "Consider how a conclusion can effectively tie back to the initial imagery presented in the essay.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@65cccab0e7d949a1bec57d8d81c97907"
  },
  {
      "id": "h-gen-f504a1d9e43b953a",
      "subject": "act-english",
      "question_id": "ti-gen-993e51faa7a5ba14",
      "rung": 3,
      "body_md": "Look for a choice that emphasizes a transformation or change related to the lighthouse, especially in terms of its light.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@65cccab0e7d949a1bec57d8d81c97907"
  },
  {
      "id": "h-gen-a403b78db1e577de",
      "subject": "act-english",
      "question_id": "ti-gen-9a237b9f8b5ba000",
      "rung": 1,
      "body_md": "What do you think about the way the two clauses are connected in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@682fc2ab7c8f40d8bb75194d848f1b30"
  },
  {
      "id": "h-gen-cc3cf3b50439beff",
      "subject": "act-english",
      "question_id": "ti-gen-9a237b9f8b5ba000",
      "rung": 2,
      "body_md": "Consider the rules for joining independent clauses. What types of conjunctions can be used to connect them?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@682fc2ab7c8f40d8bb75194d848f1b30"
  },
  {
      "id": "h-gen-46e5f3b6416e26e9",
      "subject": "act-english",
      "question_id": "ti-gen-9a237b9f8b5ba000",
      "rung": 3,
      "body_md": "Look closely at the relationship between the two clauses. How might you indicate a contrast or a result between them?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@682fc2ab7c8f40d8bb75194d848f1b30"
  },
  {
      "id": "h-gen-62afb3c0d60be85f",
      "subject": "act-english",
      "question_id": "ti-gen-9b3b4144fc30cdf2",
      "rung": 1,
      "body_md": "What do you think about the placement of the conjunction in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92edb86f88a346038571fc1755b4a121"
  },
  {
      "id": "h-gen-6b110dc5e4077483",
      "subject": "act-english",
      "question_id": "ti-gen-9b3b4144fc30cdf2",
      "rung": 2,
      "body_md": "Consider the rule of parallel structure in sentences with paired conjunctions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92edb86f88a346038571fc1755b4a121"
  },
  {
      "id": "h-gen-67d8636e222df90d",
      "subject": "act-english",
      "question_id": "ti-gen-9b3b4144fc30cdf2",
      "rung": 3,
      "body_md": "Look closely at how the options are structured and compare the phrases that follow the conjunction.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@92edb86f88a346038571fc1755b4a121"
  },
  {
      "id": "h-gen-e5c2ec338f0ebe79",
      "subject": "act-english",
      "question_id": "ti-gen-9b824ee4a3f416d0",
      "rung": 1,
      "body_md": "What do you think the word 'almost' is modifying in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a0cef3f32e374492ad358440211ffbf5"
  },
  {
      "id": "h-gen-d667a7fa19e8bc92",
      "subject": "act-english",
      "question_id": "ti-gen-9b824ee4a3f416d0",
      "rung": 2,
      "body_md": "Modifiers like 'almost' should be placed directly before the word they limit.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a0cef3f32e374492ad358440211ffbf5"
  },
  {
      "id": "h-gen-92b9dc88399fd0ef",
      "subject": "act-english",
      "question_id": "ti-gen-9b824ee4a3f416d0",
      "rung": 3,
      "body_md": "Consider where the limiting word appears in each option and how it affects the meaning of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a0cef3f32e374492ad358440211ffbf5"
  },
  {
      "id": "h-gen-ef9d564962a0fbdd",
      "subject": "act-english",
      "question_id": "ti-gen-9e8e72b34bcb715d",
      "rung": 1,
      "body_md": "What do you think the author is trying to convey about the sense of wonder mentioned in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@326840823149477ea6c9d04c8e76a966"
  },
  {
      "id": "h-gen-2a11e8f73644fda1",
      "subject": "act-english",
      "question_id": "ti-gen-9e8e72b34bcb715d",
      "rung": 2,
      "body_md": "Consider the connotations of words that describe a sense of wonder; think about how they can be perceived positively or negatively.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@326840823149477ea6c9d04c8e76a966"
  },
  {
      "id": "h-gen-0cd79e76c928d28f",
      "subject": "act-english",
      "question_id": "ti-gen-9e8e72b34bcb715d",
      "rung": 3,
      "body_md": "Look closely at the meaning of the underlined word and think about synonyms that might fit the context of admiration.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@326840823149477ea6c9d04c8e76a966"
  },
  {
      "id": "h-gen-e4113d938be7cada",
      "subject": "act-english",
      "question_id": "ti-gen-9ecce8513dec92cc",
      "rung": 1,
      "body_md": "What do you think is important about the author's relationship with her mother as it relates to the central image?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9442655ad5bb4379b0c7f7462a2f6f3a"
  },
  {
      "id": "h-gen-83df6b447f02c0a2",
      "subject": "act-english",
      "question_id": "ti-gen-9ecce8513dec92cc",
      "rung": 2,
      "body_md": "Consider how a conclusion can effectively tie back to the main themes or images presented throughout a narrative.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9442655ad5bb4379b0c7f7462a2f6f3a"
  },
  {
      "id": "h-gen-7590a0c156aee836",
      "subject": "act-english",
      "question_id": "ti-gen-9ecce8513dec92cc",
      "rung": 3,
      "body_md": "Look closely at how each option connects to the imagery of hands and dough, and think about which choice reinforces that connection.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9442655ad5bb4379b0c7f7462a2f6f3a"
  },
  {
      "id": "h-gen-3ee99a884e0c26bc",
      "subject": "act-english",
      "question_id": "ti-gen-9f104eddac2ff7ae",
      "rung": 1,
      "body_md": "What do you think about the relevance of the stadium's new scoreboard to the argument for after-school funding?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d28bd8f716bd4cefa23faea97ed16a06"
  },
  {
      "id": "h-gen-f04badc200674d51",
      "subject": "act-english",
      "question_id": "ti-gen-9f104eddac2ff7ae",
      "rung": 2,
      "body_md": "Consider how evidence should relate to the main argument being made in a piece of writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d28bd8f716bd4cefa23faea97ed16a06"
  },
  {
      "id": "h-gen-7d3ff18c7c392876",
      "subject": "act-english",
      "question_id": "ti-gen-9f104eddac2ff7ae",
      "rung": 3,
      "body_md": "Look closely at how the underlined phrase connects to the overall claim about after-school programs and whether it directly supports that claim.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d28bd8f716bd4cefa23faea97ed16a06"
  },
  {
      "id": "h-gen-c2bdf8c40408b73e",
      "subject": "act-english",
      "question_id": "ti-gen-9fb6fd5eaae7fdf9",
      "rung": 1,
      "body_md": "What do you think about the phrase that is underlined? How does it convey the committee's agreement?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3b4837bd5e3d4ec199afa6eae923701a"
  },
  {
      "id": "h-gen-1f4cb110b4e40f91",
      "subject": "act-english",
      "question_id": "ti-gen-9fb6fd5eaae7fdf9",
      "rung": 2,
      "body_md": "Consider the concept of conciseness in writing. How can we express an idea using fewer words without losing its meaning?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ffa220c7af7e43bc9fc60293cfcee6f1"
  },
  {
      "id": "h-gen-5543d107b9211662",
      "subject": "act-english",
      "question_id": "ti-gen-9fb6fd5eaae7fdf9",
      "rung": 3,
      "body_md": "Look closely at the options and compare how each one expresses the idea of agreement. Which options seem to use more words than necessary?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3b4837bd5e3d4ec199afa6eae923701a"
  },
  {
      "id": "h-gen-22a1c922cd4c5141",
      "subject": "act-english",
      "question_id": "ti-gen-a37fbfd95df2caef",
      "rung": 1,
      "body_md": "What do you think about the punctuation used in the teacher's name?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2082feb0f2ca4fab9b0cb0f1dae9e07c"
  },
  {
      "id": "h-gen-22e8e62a03b865d2",
      "subject": "act-english",
      "question_id": "ti-gen-a37fbfd95df2caef",
      "rung": 2,
      "body_md": "Consider the rule for punctuating renaming appositives in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2082feb0f2ca4fab9b0cb0f1dae9e07c"
  },
  {
      "id": "h-gen-6852f902b7e4a4c2",
      "subject": "act-english",
      "question_id": "ti-gen-a37fbfd95df2caef",
      "rung": 3,
      "body_md": "Look closely at the punctuation around the teacher's name and think about how it relates to the surrounding sentence structure.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2082feb0f2ca4fab9b0cb0f1dae9e07c"
  },
  {
      "id": "h-gen-6b39484037cd14bc",
      "subject": "act-english",
      "question_id": "ti-gen-a519014ae187ac76",
      "rung": 1,
      "body_md": "What do you think about the way the underlined phrase is structured?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c86a596cb95a4354a643a6ecae3736d1"
  },
  {
      "id": "h-gen-4d95144815370d61",
      "subject": "act-english",
      "question_id": "ti-gen-a519014ae187ac76",
      "rung": 2,
      "body_md": "Consider the difference between restrictive and nonrestrictive clauses in sentences.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c86a596cb95a4354a643a6ecae3736d1"
  },
  {
      "id": "h-gen-8a23aac350442397",
      "subject": "act-english",
      "question_id": "ti-gen-a519014ae187ac76",
      "rung": 3,
      "body_md": "Look closely at how the underlined phrase is set off in the sentence. Pay attention to the punctuation used around it.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c86a596cb95a4354a643a6ecae3736d1"
  },
  {
      "id": "h-gen-ac151cf135fee7b0",
      "subject": "act-english",
      "question_id": "ti-gen-a5c4bc79eb059ac0",
      "rung": 1,
      "body_md": "What do you think about the use of 'myself' in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0109dd41525e4f6c883f087468e6473d"
  },
  {
      "id": "h-gen-ce861846a1ff2949",
      "subject": "act-english",
      "question_id": "ti-gen-a5c4bc79eb059ac0",
      "rung": 2,
      "body_md": "Consider the difference between subject and object pronouns.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0109dd41525e4f6c883f087468e6473d"
  },
  {
      "id": "h-gen-3f1acf849e11e651",
      "subject": "act-english",
      "question_id": "ti-gen-a5c4bc79eb059ac0",
      "rung": 3,
      "body_md": "Look closely at the role of the underlined phrase in the sentence and think about how it relates to the other parts.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0109dd41525e4f6c883f087468e6473d"
  },
  {
      "id": "h-gen-bfe1d059d17a436f",
      "subject": "act-english",
      "question_id": "ti-gen-a8faee19068a0769",
      "rung": 1,
      "body_md": "What do you think about how ownership is shown in the phrase being tested?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@008067cba31c497b90c0b52393368dc0"
  },
  {
      "id": "h-gen-56a97358b1eb0ba7",
      "subject": "act-english",
      "question_id": "ti-gen-a8faee19068a0769",
      "rung": 2,
      "body_md": "When indicating possession for multiple owners, what is the general rule for forming possessives?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@008067cba31c497b90c0b52393368dc0"
  },
  {
      "id": "h-gen-1d0fbecd6ee59717",
      "subject": "act-english",
      "question_id": "ti-gen-a8faee19068a0769",
      "rung": 3,
      "body_md": "Consider how the ownership is expressed for both individuals in the tested wording. Are there specific forms you should compare to ensure each owner is correctly represented?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@008067cba31c497b90c0b52393368dc0"
  },
  {
      "id": "h-gen-7f6dcb93889ee08a",
      "subject": "act-english",
      "question_id": "ti-gen-a9fe78e59aae3959",
      "rung": 1,
      "body_md": "What do you think the change in the theater was after the blackout?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@08527defdf4649c8989ab22f11842489"
  },
  {
      "id": "h-gen-293542f679318501",
      "subject": "act-english",
      "question_id": "ti-gen-a9fe78e59aae3959",
      "rung": 2,
      "body_md": "Consider how a colon is used to introduce a list or explanation in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@08527defdf4649c8989ab22f11842489"
  },
  {
      "id": "h-gen-b0b66a5de34ad78e",
      "subject": "act-english",
      "question_id": "ti-gen-a9fe78e59aae3959",
      "rung": 3,
      "body_md": "Look closely at the end of the clause to determine how the change is presented.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@08527defdf4649c8989ab22f11842489"
  },
  {
      "id": "h-gen-c3c33f96fc97db58",
      "subject": "act-english",
      "question_id": "ti-gen-ab12f0a5a507e9ac",
      "rung": 1,
      "body_md": "What do you think the main point of the paragraph is regarding the club's activities and their impact on hikers?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8d54b1f844f45728dd97b1833043c83"
  },
  {
      "id": "h-gen-0c5b919ab28e6557",
      "subject": "act-english",
      "question_id": "ti-gen-ab12f0a5a507e9ac",
      "rung": 2,
      "body_md": "Consider how a conclusion should summarize or reflect on the information presented in the paragraph.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8d54b1f844f45728dd97b1833043c83"
  },
  {
      "id": "h-gen-ecbc4d515d56b198",
      "subject": "act-english",
      "question_id": "ti-gen-ab12f0a5a507e9ac",
      "rung": 3,
      "body_md": "Look for a statement that connects the club's efforts to the positive outcomes for hikers, focusing on the overall effectiveness of their work.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a8d54b1f844f45728dd97b1833043c83"
  },
  {
      "id": "h-gen-cfdea4e436a71880",
      "subject": "act-english",
      "question_id": "ti-gen-af530f347820d781",
      "rung": 1,
      "body_md": "What do you think happens after the tide pools form and before the animals are mentioned?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5c7bde44f6e14f978f7cbdc1a9622d37"
  },
  {
      "id": "h-gen-015d490555d59ed3",
      "subject": "act-english",
      "question_id": "ti-gen-af530f347820d781",
      "rung": 2,
      "body_md": "Consider how a sentence can connect the formation of the tide pools to the creatures that inhabit them.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5c7bde44f6e14f978f7cbdc1a9622d37"
  },
  {
      "id": "h-gen-5aa6072cad3c7640",
      "subject": "act-english",
      "question_id": "ti-gen-af530f347820d781",
      "rung": 3,
      "body_md": "Look for a choice that describes what occurs in the tide pools after the water recedes, as this will help bridge the two paragraphs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5c7bde44f6e14f978f7cbdc1a9622d37"
  },
  {
      "id": "h-gen-7a3de31a391bd5df",
      "subject": "act-english",
      "question_id": "ti-gen-af86c1bda07ec259",
      "rung": 1,
      "body_md": "What do you think about the way the aside is introduced in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02dd098187294479bb9344aa94d8509e"
  },
  {
      "id": "h-gen-29f7f15c73da6aa3",
      "subject": "act-english",
      "question_id": "ti-gen-af86c1bda07ec259",
      "rung": 2,
      "body_md": "Consider the punctuation rules for asides in sentences. What do you know about how to properly set off an aside?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02dd098187294479bb9344aa94d8509e"
  },
  {
      "id": "h-gen-e349e17bc1af03fb",
      "subject": "act-english",
      "question_id": "ti-gen-af86c1bda07ec259",
      "rung": 3,
      "body_md": "Look closely at the punctuation marks used around the aside. How do they compare to each other, and what does that suggest about their usage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@02dd098187294479bb9344aa94d8509e"
  },
  {
      "id": "h-gen-4ddef691167c6c75",
      "subject": "act-english",
      "question_id": "ti-gen-b149168609a7069d",
      "rung": 1,
      "body_md": "What do you think about the relevance of the sentence regarding downtown rents to the overall argument about parks and health?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@95b71f5c6ae1454bb994a83cf7752d80"
  },
  {
      "id": "h-gen-20420064e6619783",
      "subject": "act-english",
      "question_id": "ti-gen-b149168609a7069d",
      "rung": 2,
      "body_md": "Consider the importance of staying on topic in a paragraph. What does it mean for a sentence to support the main point?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@95b71f5c6ae1454bb994a83cf7752d80"
  },
  {
      "id": "h-gen-93a1d06388d3bf35",
      "subject": "act-english",
      "question_id": "ti-gen-b149168609a7069d",
      "rung": 3,
      "body_md": "Look closely at how the sentence about rents relates to the surrounding sentences. Does it contribute to the discussion about health benefits from parks?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@95b71f5c6ae1454bb994a83cf7752d80"
  },
  {
      "id": "h-gen-6918198a1cdc75e2",
      "subject": "act-english",
      "question_id": "ti-gen-b21513cab961e3f7",
      "rung": 1,
      "body_md": "What do you think the relationship is between Ella's training and her marathon performance?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9e9a5193bac49a4b3626b59aba4e8af"
  },
  {
      "id": "h-gen-4ec6d5dfa627330c",
      "subject": "act-english",
      "question_id": "ti-gen-b21513cab961e3f7",
      "rung": 2,
      "body_md": "Consider how transitions can indicate cause and effect versus contrast.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9e9a5193bac49a4b3626b59aba4e8af"
  },
  {
      "id": "h-gen-df4faf81dc9fc077",
      "subject": "act-english",
      "question_id": "ti-gen-b21513cab961e3f7",
      "rung": 3,
      "body_md": "Look closely at how the second sentence relates to the first; think about whether it suggests a consequence or a different perspective.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b9e9a5193bac49a4b3626b59aba4e8af"
  },
  {
      "id": "h-gen-affbb4764cdce799",
      "subject": "act-english",
      "question_id": "ti-gen-b21cca2fbc4a3c98",
      "rung": 1,
      "body_md": "What do you think is the correct past tense form of the verb in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8c8e25936ce443fe90e99abc88a21e30"
  },
  {
      "id": "h-gen-901bda200d0920a1",
      "subject": "act-english",
      "question_id": "ti-gen-b21cca2fbc4a3c98",
      "rung": 2,
      "body_md": "Consider the general rule for forming the past tense of irregular verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8c8e25936ce443fe90e99abc88a21e30"
  },
  {
      "id": "h-gen-ab0ee20748486507",
      "subject": "act-english",
      "question_id": "ti-gen-b21cca2fbc4a3c98",
      "rung": 3,
      "body_md": "Look closely at the verb in the underlined phrase and compare it to the common past tense forms of similar verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8c8e25936ce443fe90e99abc88a21e30"
  },
  {
      "id": "h-gen-0ec316a237f6a714",
      "subject": "act-english",
      "question_id": "ti-gen-b71faa75b88c9e90",
      "rung": 1,
      "body_md": "What do you think the problem with the strap is based on the context of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@87f0279e34834793b43060734f9d0703"
  },
  {
      "id": "h-gen-9d9a0f901fe6049f",
      "subject": "act-english",
      "question_id": "ti-gen-b71faa75b88c9e90",
      "rung": 2,
      "body_md": "Consider the difference between words that describe something not being tight versus words that indicate misplacing something.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@87f0279e34834793b43060734f9d0703"
  },
  {
      "id": "h-gen-3cd7279eba9231ce",
      "subject": "act-english",
      "question_id": "ti-gen-b71faa75b88c9e90",
      "rung": 3,
      "body_md": "Look closely at the word that describes the condition of the strap in relation to the helmet's fit.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@87f0279e34834793b43060734f9d0703"
  },
  {
      "id": "h-gen-0f61367a405636e5",
      "subject": "act-english",
      "question_id": "ti-gen-b848acac3943750d",
      "rung": 1,
      "body_md": "What do you think about the way possession is shown in this sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@137a5c7faeb345e890242b262041eb55"
  },
  {
      "id": "h-gen-b4c3005bc2937186",
      "subject": "act-english",
      "question_id": "ti-gen-b848acac3943750d",
      "rung": 2,
      "body_md": "Consider how possessive forms are created for irregular plural nouns.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@137a5c7faeb345e890242b262041eb55"
  },
  {
      "id": "h-gen-0bd6c1e411c2ad5e",
      "subject": "act-english",
      "question_id": "ti-gen-b848acac3943750d",
      "rung": 3,
      "body_md": "Look closely at the words that indicate ownership and think about how they relate to the plural form.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@137a5c7faeb345e890242b262041eb55"
  },
  {
      "id": "h-gen-ba38875425ffe9f0",
      "subject": "act-english",
      "question_id": "ti-gen-ba5da13ef71e6085",
      "rung": 1,
      "body_md": "What do you think about the verb form used in the underlined phrase? Does it match the tense of the other verbs in the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a8df6191c0545c8b601a6951eac34eb"
  },
  {
      "id": "h-gen-0e009e3a927ca0d8",
      "subject": "act-english",
      "question_id": "ti-gen-ba5da13ef71e6085",
      "rung": 2,
      "body_md": "Consider the rules of verb tense consistency. How should verbs relate to one another in terms of time when describing actions in a narrative?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a8df6191c0545c8b601a6951eac34eb"
  },
  {
      "id": "h-gen-9389641b785fd1e1",
      "subject": "act-english",
      "question_id": "ti-gen-ba5da13ef71e6085",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence. Pay attention to the verb forms used in the surrounding context and see how they relate to the underlined phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a8df6191c0545c8b601a6951eac34eb"
  },
  {
      "id": "h-gen-1b1ef1b27f87e8b7",
      "subject": "act-english",
      "question_id": "ti-gen-bd8de98582eeb065",
      "rung": 1,
      "body_md": "What do you think about the relationship between the difficulty of the trail and the reward of the view from the summit?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@eb0a32f8872a4bd792f4435543211b31"
  },
  {
      "id": "h-gen-cb98223d447309c1",
      "subject": "act-english",
      "question_id": "ti-gen-bd8de98582eeb065",
      "rung": 2,
      "body_md": "Consider the concept of concession in writing, where a difficulty or hardship is acknowledged but followed by a positive outcome.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@eb0a32f8872a4bd792f4435543211b31"
  },
  {
      "id": "h-gen-1034d0bfdd717555",
      "subject": "act-english",
      "question_id": "ti-gen-bd8de98582eeb065",
      "rung": 3,
      "body_md": "Look closely at the transition options and think about which one indicates that despite the challenges mentioned, there is still a positive result.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@eb0a32f8872a4bd792f4435543211b31"
  },
  {
      "id": "h-gen-0acab1de9e699a31",
      "subject": "act-english",
      "question_id": "ti-gen-bdbcbe226d86801b",
      "rung": 1,
      "body_md": "What do you think about the necessity of the clause in the sentence? Does it add important information or seem repetitive?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5571db3fc2d1476ab89b019e31944af3"
  },
  {
      "id": "h-gen-9022d42e49883a63",
      "subject": "act-english",
      "question_id": "ti-gen-bdbcbe226d86801b",
      "rung": 2,
      "body_md": "Consider the concept of redundancy in writing. When a phrase repeats information that is already clear, it may be unnecessary.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5571db3fc2d1476ab89b019e31944af3"
  },
  {
      "id": "h-gen-d7b36e3610ccea32",
      "subject": "act-english",
      "question_id": "ti-gen-bdbcbe226d86801b",
      "rung": 3,
      "body_md": "Look closely at the clause in question and think about whether it provides new information or simply restates what is already implied.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5571db3fc2d1476ab89b019e31944af3"
  },
  {
      "id": "h-gen-525281823d2df95d",
      "subject": "act-english",
      "question_id": "ti-gen-bf29386cecb39137",
      "rung": 1,
      "body_md": "What do you think the coach means by saying that a missed free throw can be viewed differently depending on how the players respond to it?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@316aed7aa9244bfbb82e0acbd914c8b7"
  },
  {
      "id": "h-gen-74c160833495a73a",
      "subject": "act-english",
      "question_id": "ti-gen-bf29386cecb39137",
      "rung": 2,
      "body_md": "Consider how different words can convey varying levels of severity or impact when describing a situation.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@316aed7aa9244bfbb82e0acbd914c8b7"
  },
  {
      "id": "h-gen-9e13f11c3d74d3dc",
      "subject": "act-english",
      "question_id": "ti-gen-bf29386cecb39137",
      "rung": 3,
      "body_md": "Look closely at the tone of the options provided and think about which word suggests that the situation can be improved or learned from.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@316aed7aa9244bfbb82e0acbd914c8b7"
  },
  {
      "id": "h-gen-2f7311259e6fd319",
      "subject": "act-english",
      "question_id": "ti-gen-c42986d0102d9d7d",
      "rung": 1,
      "body_md": "What do you think the writer is trying to convey about the moon in the poem?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5bacc47d19b9424bb3f3d8719b4132e9"
  },
  {
      "id": "h-gen-63f9f2ceec720b02",
      "subject": "act-english",
      "question_id": "ti-gen-c42986d0102d9d7d",
      "rung": 2,
      "body_md": "Consider how figurative language can enhance imagery in writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5bacc47d19b9424bb3f3d8719b4132e9"
  },
  {
      "id": "h-gen-8459ba247023cacb",
      "subject": "act-english",
      "question_id": "ti-gen-c42986d0102d9d7d",
      "rung": 3,
      "body_md": "Look closely at the descriptions of the moon and think about how they relate to the choices provided.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5bacc47d19b9424bb3f3d8719b4132e9"
  },
  {
      "id": "h-gen-292fbcf64b9ea230",
      "subject": "act-english",
      "question_id": "ti-gen-c460b9d55b0b2362",
      "rung": 1,
      "body_md": "What do you think is the main issue with the current sentence structure?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@724eec4200964970b0231b8043d13ebc"
  },
  {
      "id": "h-gen-7f5cd8d46b63b0da",
      "subject": "act-english",
      "question_id": "ti-gen-c460b9d55b0b2362",
      "rung": 2,
      "body_md": "Consider how modifiers should relate to the subjects they describe.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@724eec4200964970b0231b8043d13ebc"
  },
  {
      "id": "h-gen-eef0d6b5b50a1c84",
      "subject": "act-english",
      "question_id": "ti-gen-c460b9d55b0b2362",
      "rung": 3,
      "body_md": "Look closely at the subject of the opening phrase and see if it matches the main subject of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@724eec4200964970b0231b8043d13ebc"
  },
  {
      "id": "h-gen-32b40bb0e3e2925b",
      "subject": "act-english",
      "question_id": "ti-gen-c53704861efec902",
      "rung": 1,
      "body_md": "What do you think the tone of the sentence is regarding the summer being discussed?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1dba085c6faa4edebe41d3a0c374ac97"
  },
  {
      "id": "h-gen-c67eaa07e999deff",
      "subject": "act-english",
      "question_id": "ti-gen-c53704861efec902",
      "rung": 2,
      "body_md": "Consider how the tone of a phrase can influence the overall meaning of a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1dba085c6faa4edebe41d3a0c374ac97"
  },
  {
      "id": "h-gen-a6c3d126fb3d1c13",
      "subject": "act-english",
      "question_id": "ti-gen-c53704861efec902",
      "rung": 3,
      "body_md": "Look closely at the implications of the underlined phrase and think about how it relates to the overall sentiment expressed in the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@1dba085c6faa4edebe41d3a0c374ac97"
  },
  {
      "id": "h-gen-23a53c7f9a3222f4",
      "subject": "act-english",
      "question_id": "ti-gen-c86b66726f6339df",
      "rung": 1,
      "body_md": "What do you think about the use of the apostrophe in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f201378d6cc34707a2f35f030bf0e905"
  },
  {
      "id": "h-gen-005d79fc5bcacba9",
      "subject": "act-english",
      "question_id": "ti-gen-c86b66726f6339df",
      "rung": 2,
      "body_md": "Consider the general rule for forming possessives with singular nouns.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f201378d6cc34707a2f35f030bf0e905"
  },
  {
      "id": "h-gen-707d4e73d49c6561",
      "subject": "act-english",
      "question_id": "ti-gen-c86b66726f6339df",
      "rung": 3,
      "body_md": "Look closely at the relationship between the owner and the item being owned in the underlined phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f201378d6cc34707a2f35f030bf0e905"
  },
  {
      "id": "h-gen-a443ce22cf42845f",
      "subject": "act-english",
      "question_id": "ti-gen-ca301b7240c9a794",
      "rung": 1,
      "body_md": "What do you think about the relationship between the two parts of the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@646759e8a79d4bc2948df4f62a328f6f"
  },
  {
      "id": "h-gen-f966611332c49604",
      "subject": "act-english",
      "question_id": "ti-gen-ca301b7240c9a794",
      "rung": 2,
      "body_md": "Consider how coordinating conjunctions function in connecting clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@646759e8a79d4bc2948df4f62a328f6f"
  },
  {
      "id": "h-gen-a163d11ddbe69ddd",
      "subject": "act-english",
      "question_id": "ti-gen-ca301b7240c9a794",
      "rung": 3,
      "body_md": "Look closely at the end of the first clause and think about how it relates to the second clause.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@646759e8a79d4bc2948df4f62a328f6f"
  },
  {
      "id": "h-gen-0c3cbdaadf382d38",
      "subject": "act-english",
      "question_id": "ti-gen-cbd3325cb0fd4832",
      "rung": 1,
      "body_md": "What do you think the new sentence adds to the overall context of the passage?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@de1f1d9db468408d989515e996dab1cb"
  },
  {
      "id": "h-gen-c157fb7cf23b2af1",
      "subject": "act-english",
      "question_id": "ti-gen-cbd3325cb0fd4832",
      "rung": 2,
      "body_md": "Consider how supporting details are typically placed in relation to the main ideas they elaborate on.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@de1f1d9db468408d989515e996dab1cb"
  },
  {
      "id": "h-gen-127f69f18e8f7588",
      "subject": "act-english",
      "question_id": "ti-gen-cbd3325cb0fd4832",
      "rung": 3,
      "body_md": "Look closely at the relationship between the sentences discussing the ceiling and the new sentence about the medallions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@de1f1d9db468408d989515e996dab1cb"
  },
  {
      "id": "h-gen-2e1037ac764f5dc9",
      "subject": "act-english",
      "question_id": "ti-gen-cc4452d8304c2c1b",
      "rung": 1,
      "body_md": "What are your thoughts on how to connect the two clauses in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@773cb9afcba9414fa436f3ac9318d096"
  },
  {
      "id": "h-gen-dbb3b9d656b5db20",
      "subject": "act-english",
      "question_id": "ti-gen-cc4452d8304c2c1b",
      "rung": 2,
      "body_md": "Consider the rule for punctuating a conjunctive adverb that links two independent clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@773cb9afcba9414fa436f3ac9318d096"
  },
  {
      "id": "h-gen-6e77072eb19369d7",
      "subject": "act-english",
      "question_id": "ti-gen-cc4452d8304c2c1b",
      "rung": 3,
      "body_md": "Look closely at the punctuation used before and after the transition between the two clauses.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@773cb9afcba9414fa436f3ac9318d096"
  },
  {
      "id": "h-gen-de482486a1e61e3a",
      "subject": "act-english",
      "question_id": "ti-gen-ccb0cbb911db934d",
      "rung": 1,
      "body_md": "What do you think about the phrase that indicates a restriction on actions?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@548cfd767287452194fc3b6aa56209d9"
  },
  {
      "id": "h-gen-44aca90f2f4270f7",
      "subject": "act-english",
      "question_id": "ti-gen-ccb0cbb911db934d",
      "rung": 2,
      "body_md": "Consider the general rule for expressing prohibition in English.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@548cfd767287452194fc3b6aa56209d9"
  },
  {
      "id": "h-gen-753ec1e7008a6736",
      "subject": "act-english",
      "question_id": "ti-gen-ccb0cbb911db934d",
      "rung": 3,
      "body_md": "Look closely at how the phrase connects to the action being restricted and think about common prepositions used in similar contexts.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@548cfd767287452194fc3b6aa56209d9"
  },
  {
      "id": "h-gen-26501ed146d4492b",
      "subject": "act-english",
      "question_id": "ti-gen-d177ac4c09a673d3",
      "rung": 1,
      "body_md": "What do you think about the use of both words in the underlined phrase? Do they convey the same idea?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5355a17a6a094f92a56c5fa708561827"
  },
  {
      "id": "h-gen-948974a89bfbdd5e",
      "subject": "act-english",
      "question_id": "ti-gen-d177ac4c09a673d3",
      "rung": 2,
      "body_md": "Consider the concept of redundancy in language. What does it mean for two words to have the same meaning?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5355a17a6a094f92a56c5fa708561827"
  },
  {
      "id": "h-gen-298c4086e44ffe8c",
      "subject": "act-english",
      "question_id": "ti-gen-d177ac4c09a673d3",
      "rung": 3,
      "body_md": "Look closely at the underlined phrase and think about how you might simplify it. Are there any words that could be removed without losing the overall meaning?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@5355a17a6a094f92a56c5fa708561827"
  },
  {
      "id": "h-gen-2ad8cf815b5a0e76",
      "subject": "act-english",
      "question_id": "ti-gen-d5cf1d16bc41eae4",
      "rung": 1,
      "body_md": "What do you think is the main idea of the paragraph based on the details provided?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9a890786b50040749cbfd5c210ed2de3"
  },
  {
      "id": "h-gen-55c0efdd9dacb33c",
      "subject": "act-english",
      "question_id": "ti-gen-d5cf1d16bc41eae4",
      "rung": 2,
      "body_md": "A strong topic sentence should summarize the main idea and connect to all the details in the paragraph.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9a890786b50040749cbfd5c210ed2de3"
  },
  {
      "id": "h-gen-b0c624f55c989d5e",
      "subject": "act-english",
      "question_id": "ti-gen-d5cf1d16bc41eae4",
      "rung": 3,
      "body_md": "Consider how the details about the soil and crops relate to the overall fertility of the island.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@9a890786b50040749cbfd5c210ed2de3"
  },
  {
      "id": "h-gen-9d6e169d987ce827",
      "subject": "act-english",
      "question_id": "ti-gen-d695906ab0114f7f",
      "rung": 1,
      "body_md": "What do you think about the subject of the opening phrase? Can it perform the action described?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f6637d3d33cc44549d9a5ceecdd6fb33"
  },
  {
      "id": "h-gen-34f2e759eb834858",
      "subject": "act-english",
      "question_id": "ti-gen-d695906ab0114f7f",
      "rung": 2,
      "body_md": "Consider the concept of a dangling modifier. What does it require in terms of a subject?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f6637d3d33cc44549d9a5ceecdd6fb33"
  },
  {
      "id": "h-gen-a094f52cd365184c",
      "subject": "act-english",
      "question_id": "ti-gen-d695906ab0114f7f",
      "rung": 3,
      "body_md": "Look closely at the beginning of the sentence. Where does the clause that describes the action end, and who or what is performing that action?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f6637d3d33cc44549d9a5ceecdd6fb33"
  },
  {
      "id": "h-gen-bc130853f5d5fa1b",
      "subject": "act-english",
      "question_id": "ti-gen-d895b6e62645c3d6",
      "rung": 1,
      "body_md": "What do you think about the complexity of sourdough compared to other types of bread?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d9e2b998af4c4498b009f87242e0bdf8"
  },
  {
      "id": "h-gen-c8ed22c286ace96f",
      "subject": "act-english",
      "question_id": "ti-gen-d895b6e62645c3d6",
      "rung": 2,
      "body_md": "Consider how contrasts are often used to highlight differences in characteristics or qualities.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d9e2b998af4c4498b009f87242e0bdf8"
  },
  {
      "id": "h-gen-09bc593bbf267d4b",
      "subject": "act-english",
      "question_id": "ti-gen-d895b6e62645c3d6",
      "rung": 3,
      "body_md": "Look closely at the relationship between the complexity mentioned and the implications of the underlined phrase.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@d9e2b998af4c4498b009f87242e0bdf8"
  },
  {
      "id": "h-gen-51165feaa9cc45e2",
      "subject": "act-english",
      "question_id": "ti-gen-dcfcdb4223eef909",
      "rung": 1,
      "body_md": "What do you think about the use of 'you' in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c6a5cc351bbb4a86b6d7fe3af6e35362"
  },
  {
      "id": "h-gen-c55a547141583dbc",
      "subject": "act-english",
      "question_id": "ti-gen-dcfcdb4223eef909",
      "rung": 2,
      "body_md": "Consider the importance of maintaining a consistent point of view in writing.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c6a5cc351bbb4a86b6d7fe3af6e35362"
  },
  {
      "id": "h-gen-6a0af2ce7fc49fab",
      "subject": "act-english",
      "question_id": "ti-gen-dcfcdb4223eef909",
      "rung": 3,
      "body_md": "Look closely at how the subject of the sentence is expressed and think about whether it aligns with the rest of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@c6a5cc351bbb4a86b6d7fe3af6e35362"
  },
  {
      "id": "h-gen-97bccd923bbfe77f",
      "subject": "act-english",
      "question_id": "ti-gen-dd0e929d10c612be",
      "rung": 1,
      "body_md": "What do you think about the tone of the phrase in the context of a textbook?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0daff9a0859747bb98095c838739b8a9"
  },
  {
      "id": "h-gen-d01d0e1987c3a6a5",
      "subject": "act-english",
      "question_id": "ti-gen-dd0e929d10c612be",
      "rung": 2,
      "body_md": "Consider how a neutral tone differs from more emotional or idiomatic expressions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0daff9a0859747bb98095c838739b8a9"
  },
  {
      "id": "h-gen-2c59e44fe35a30f7",
      "subject": "act-english",
      "question_id": "ti-gen-dd0e929d10c612be",
      "rung": 3,
      "body_md": "Look closely at the implications of the underlined phrase and think about how it might be rephrased to maintain a neutral tone.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@0daff9a0859747bb98095c838739b8a9"
  },
  {
      "id": "h-gen-6107d68e266bedfc",
      "subject": "act-english",
      "question_id": "ti-gen-df0fe0c126bbe20c",
      "rung": 1,
      "body_md": "What do you think about the relationship between the starter and the fermentation process?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7d377a40deed429f9595ddaa7577fe96"
  },
  {
      "id": "h-gen-67d93a09fc41bfa3",
      "subject": "act-english",
      "question_id": "ti-gen-df0fe0c126bbe20c",
      "rung": 2,
      "body_md": "Consider the rules of punctuation regarding clauses and how they can affect sentence clarity.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7d377a40deed429f9595ddaa7577fe96"
  },
  {
      "id": "h-gen-b18683c65cd67b33",
      "subject": "act-english",
      "question_id": "ti-gen-df0fe0c126bbe20c",
      "rung": 3,
      "body_md": "Look closely at the structure of the underlined phrase and think about how it connects to the surrounding sentences.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7d377a40deed429f9595ddaa7577fe96"
  },
  {
      "id": "h-gen-7300cd0b8e9e0611",
      "subject": "act-english",
      "question_id": "ti-gen-dfd75410d01e1797",
      "rung": 1,
      "body_md": "What do you think the writer is trying to convey about the lifeguard's actions in this sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b8350078cf724149923c216a0beccdf7"
  },
  {
      "id": "h-gen-5517d5e647131760",
      "subject": "act-english",
      "question_id": "ti-gen-dfd75410d01e1797",
      "rung": 2,
      "body_md": "Consider how different verbs can change the perception of speed and urgency in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b8350078cf724149923c216a0beccdf7"
  },
  {
      "id": "h-gen-95f66582d4faf3bd",
      "subject": "act-english",
      "question_id": "ti-gen-dfd75410d01e1797",
      "rung": 3,
      "body_md": "Look closely at the verbs in each choice and think about which one suggests the fastest action.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b8350078cf724149923c216a0beccdf7"
  },
  {
      "id": "h-gen-7db8a6b58f7a53f7",
      "subject": "act-english",
      "question_id": "ti-gen-e68996d993ddbf5a",
      "rung": 1,
      "body_md": "What do you think about the phrase that follows 'the reason'? Does it clearly explain the cause of the trail closure?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c9a8d7da147434f9cbd09e576d78491"
  },
  {
      "id": "h-gen-7428e3e4c194e4d9",
      "subject": "act-english",
      "question_id": "ti-gen-e68996d993ddbf5a",
      "rung": 2,
      "body_md": "Consider the grammatical structure that follows 'the reason'. What is the typical way to introduce an explanation or cause in English?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c9a8d7da147434f9cbd09e576d78491"
  },
  {
      "id": "h-gen-ef72510aecb277eb",
      "subject": "act-english",
      "question_id": "ti-gen-e68996d993ddbf5a",
      "rung": 3,
      "body_md": "Look closely at how the phrase after 'the reason' connects to the explanation. Does it maintain clarity without introducing redundancy?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c9a8d7da147434f9cbd09e576d78491"
  },
  {
      "id": "h-gen-27b89cd950d3247c",
      "subject": "act-english",
      "question_id": "ti-gen-e837d1c29c445707",
      "rung": 1,
      "body_md": "What do you think about the structure of the two parts in the phrase? Do they seem to match?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@edca01f752b04569b5402a08f47f5b82"
  },
  {
      "id": "h-gen-1fa06dcc82a4ba5c",
      "subject": "act-english",
      "question_id": "ti-gen-e837d1c29c445707",
      "rung": 2,
      "body_md": "In a 'not only ... but also' construction, what must be true about the two parts that follow?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@edca01f752b04569b5402a08f47f5b82"
  },
  {
      "id": "h-gen-701c14f2c84b006e",
      "subject": "act-english",
      "question_id": "ti-gen-e837d1c29c445707",
      "rung": 3,
      "body_md": "Look closely at how each option structures the second part of the phrase. Are they both using similar grammatical forms?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@edca01f752b04569b5402a08f47f5b82"
  },
  {
      "id": "h-gen-8b50cb612ea10ddd",
      "subject": "act-english",
      "question_id": "ti-gen-e8caf2efaea6d18c",
      "rung": 1,
      "body_md": "What do you think about the verb tense used in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ad53321e79904629b3436e5ce955be96"
  },
  {
      "id": "h-gen-1d13ccd2c250360c",
      "subject": "act-english",
      "question_id": "ti-gen-e8caf2efaea6d18c",
      "rung": 2,
      "body_md": "Consider the importance of maintaining consistent verb tense throughout a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ad53321e79904629b3436e5ce955be96"
  },
  {
      "id": "h-gen-c5bf98cfe7dd7a4f",
      "subject": "act-english",
      "question_id": "ti-gen-e8caf2efaea6d18c",
      "rung": 3,
      "body_md": "Look closely at the verb in the underlined phrase and think about how it relates to the rest of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@ad53321e79904629b3436e5ce955be96"
  },
  {
      "id": "h-gen-20b7367159f135e0",
      "subject": "act-english",
      "question_id": "ti-gen-ea7b624cd42ec31e",
      "rung": 1,
      "body_md": "What do you think the relationship is between the two ideas in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a5f7a74a2a341c6a5613187f5501f0e"
  },
  {
      "id": "h-gen-eaf62beced14e0c3",
      "subject": "act-english",
      "question_id": "ti-gen-ea7b624cd42ec31e",
      "rung": 2,
      "body_md": "Consider how correlative conjunctions function in pairs to connect related ideas.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a5f7a74a2a341c6a5613187f5501f0e"
  },
  {
      "id": "h-gen-14c7747ddb1b5995",
      "subject": "act-english",
      "question_id": "ti-gen-ea7b624cd42ec31e",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence and identify how the conjunction connects the two qualities being described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8a5f7a74a2a341c6a5613187f5501f0e"
  },
  {
      "id": "h-gen-ba132dcca5313ed2",
      "subject": "act-english",
      "question_id": "ti-gen-ea7d2862984dd53c",
      "rung": 1,
      "body_md": "What do you think the phrase 'enters a state of dormancy' means in the context of the little bear?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@31c75977c6194c49bfef76e149aab987"
  },
  {
      "id": "h-gen-5d695573453f020a",
      "subject": "act-english",
      "question_id": "ti-gen-ea7d2862984dd53c",
      "rung": 2,
      "body_md": "Consider how language can be tailored for young audiences, focusing on simplicity and clarity.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@31c75977c6194c49bfef76e149aab987"
  },
  {
      "id": "h-gen-703ca93fafb9882f",
      "subject": "act-english",
      "question_id": "ti-gen-ea7d2862984dd53c",
      "rung": 3,
      "body_md": "Look closely at the options and think about which one uses language that is easy for children to understand.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@31c75977c6194c49bfef76e149aab987"
  },
  {
      "id": "h-gen-1b9093f22a9628dd",
      "subject": "act-english",
      "question_id": "ti-gen-ec2124e42f09a80c",
      "rung": 1,
      "body_md": "What punctuation do you think is needed before the list of essentials mentioned in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7710b657c6954944a7dc39ac654b7c9c"
  },
  {
      "id": "h-gen-849bbda55a6eb778",
      "subject": "act-english",
      "question_id": "ti-gen-ec2124e42f09a80c",
      "rung": 2,
      "body_md": "Consider the general rule for introducing a list in a sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7710b657c6954944a7dc39ac654b7c9c"
  },
  {
      "id": "h-gen-b9b7557f0083ad0a",
      "subject": "act-english",
      "question_id": "ti-gen-ec2124e42f09a80c",
      "rung": 3,
      "body_md": "Look closely at the structure of the sentence and identify where the main clause ends before the list begins.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7710b657c6954944a7dc39ac654b7c9c"
  },
  {
      "id": "h-gen-49ef9d537b54d6f8",
      "subject": "act-english",
      "question_id": "ti-gen-edd247e2ef9ff76d",
      "rung": 1,
      "body_md": "What do you think is important to consider when maintaining a consistent structure in a list?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@545e70e1b30e44de8563f10a1290df0a"
  },
  {
      "id": "h-gen-5676818f03c5fd53",
      "subject": "act-english",
      "question_id": "ti-gen-edd247e2ef9ff76d",
      "rung": 2,
      "body_md": "Consider the rule of parallel structure, which requires that items in a list share the same grammatical form.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@545e70e1b30e44de8563f10a1290df0a"
  },
  {
      "id": "h-gen-3d28b31db60220e9",
      "subject": "act-english",
      "question_id": "ti-gen-edd247e2ef9ff76d",
      "rung": 3,
      "body_md": "Look closely at the last item in the list and compare it to the previous items to see if they match in form.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@545e70e1b30e44de8563f10a1290df0a"
  },
  {
      "id": "h-gen-2e0d8c4bb4017eff",
      "subject": "act-english",
      "question_id": "ti-gen-eeb2b7c4a9e39f80",
      "rung": 1,
      "body_md": "What do you think the correct form should be before 'entry'?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c3649e3c2c84ce0b1e11dd125a0b5be"
  },
  {
      "id": "h-gen-9331a667b4e7337b",
      "subject": "act-english",
      "question_id": "ti-gen-eeb2b7c4a9e39f80",
      "rung": 2,
      "body_md": "Consider the difference between possessive forms and contractions.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c3649e3c2c84ce0b1e11dd125a0b5be"
  },
  {
      "id": "h-gen-8b72a6a33c042eb2",
      "subject": "act-english",
      "question_id": "ti-gen-eeb2b7c4a9e39f80",
      "rung": 3,
      "body_md": "Look closely at the context of the underlined phrase and think about whether it indicates possession or a contraction.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@7c3649e3c2c84ce0b1e11dd125a0b5be"
  },
  {
      "id": "h-gen-ed44982254e5d92c",
      "subject": "act-english",
      "question_id": "ti-gen-eeedf6557d108a36",
      "rung": 1,
      "body_md": "What do you think the word in the underlined phrase means in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@921eb3609cfb462395eca1cdd48b07b8"
  },
  {
      "id": "h-gen-9915486544f07dff",
      "subject": "act-english",
      "question_id": "ti-gen-eeedf6557d108a36",
      "rung": 2,
      "body_md": "Consider the difference between 'affect' and 'effect' in terms of their grammatical roles.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@921eb3609cfb462395eca1cdd48b07b8"
  },
  {
      "id": "h-gen-6702b003ddd64e41",
      "subject": "act-english",
      "question_id": "ti-gen-eeedf6557d108a36",
      "rung": 3,
      "body_md": "Look closely at the verb form used in the underlined phrase and think about how it relates to the action described in the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@921eb3609cfb462395eca1cdd48b07b8"
  },
  {
      "id": "h-gen-a020ea88b624d316",
      "subject": "act-english",
      "question_id": "ti-gen-ef7c83c59dea8738",
      "rung": 1,
      "body_md": "What do you think about the way the adjectives are used before the noun in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a047866ebe694d179d75192c8afe164c"
  },
  {
      "id": "h-gen-da40a9afe99cb6f3",
      "subject": "act-english",
      "question_id": "ti-gen-ef7c83c59dea8738",
      "rung": 2,
      "body_md": "Consider how adjectives can modify nouns and the rules for using commas with multiple adjectives.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a047866ebe694d179d75192c8afe164c"
  },
  {
      "id": "h-gen-8c1921d9804a973e",
      "subject": "act-english",
      "question_id": "ti-gen-ef7c83c59dea8738",
      "rung": 3,
      "body_md": "Look closely at how the adjectives relate to the noun they describe. Are they coordinating or cumulative?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@a047866ebe694d179d75192c8afe164c"
  },
  {
      "id": "h-gen-be2e631f03eb8a0f",
      "subject": "act-english",
      "question_id": "ti-gen-f19724b908798592",
      "rung": 1,
      "body_md": "What do you think the phrase 'enfants terribles' suggests about the founders' behavior and attitude?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bd1f69d4f4834d43bc14f411b6bfa74d"
  },
  {
      "id": "h-gen-3249860ab904aecd",
      "subject": "act-english",
      "question_id": "ti-gen-f19724b908798592",
      "rung": 2,
      "body_md": "Consider the concept of how certain terms describe individuals who either conform to or challenge societal norms.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bd1f69d4f4834d43bc14f411b6bfa74d"
  },
  {
      "id": "h-gen-8f405c64866e7e7c",
      "subject": "act-english",
      "question_id": "ti-gen-f19724b908798592",
      "rung": 3,
      "body_md": "Look closely at the characteristics of the founders as described in the passage and think about how they relate to the idea of following industry standards.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@bd1f69d4f4834d43bc14f411b6bfa74d"
  },
  {
      "id": "h-gen-65c686d6cac94a19",
      "subject": "act-english",
      "question_id": "ti-gen-f1a9bd02d9424a66",
      "rung": 1,
      "body_md": "What do you think about the relationship between the studying and the exam in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@238edf15c2eb41ec8de2bda15352ef6c"
  },
  {
      "id": "h-gen-41cb5d67a1271e96",
      "subject": "act-english",
      "question_id": "ti-gen-f1a9bd02d9424a66",
      "rung": 2,
      "body_md": "Consider the rule about modifiers: they should clearly relate to the subject they describe.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@238edf15c2eb41ec8de2bda15352ef6c"
  },
  {
      "id": "h-gen-3f795621d8d7be2f",
      "subject": "act-english",
      "question_id": "ti-gen-f1a9bd02d9424a66",
      "rung": 3,
      "body_md": "Look closely at the beginning of the sentence and identify who is performing the action of studying.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@238edf15c2eb41ec8de2bda15352ef6c"
  },
  {
      "id": "h-gen-f9e01c22999add9d",
      "subject": "act-english",
      "question_id": "ti-gen-f1be4f7a34c291a1",
      "rung": 1,
      "body_md": "What are your thoughts on the use of pronouns in this sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f36a8f09f8347a1a78f6695a2c467f7"
  },
  {
      "id": "h-gen-0e840b0b176fda2a",
      "subject": "act-english",
      "question_id": "ti-gen-f1be4f7a34c291a1",
      "rung": 2,
      "body_md": "Consider the difference between pronouns that refer to subjects versus those that refer to objects.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f36a8f09f8347a1a78f6695a2c467f7"
  },
  {
      "id": "h-gen-6e9e23e74e4c3bc3",
      "subject": "act-english",
      "question_id": "ti-gen-f1be4f7a34c291a1",
      "rung": 3,
      "body_md": "Look closely at the role of the pronoun in the sentence. Check how it relates to the action being described.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2f36a8f09f8347a1a78f6695a2c467f7"
  },
  {
      "id": "h-gen-03cc573cf2a4f670",
      "subject": "act-english",
      "question_id": "ti-gen-f353d63071548ccf",
      "rung": 1,
      "body_md": "What do you think about the ownership of the costumes mentioned in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b892e8a9a7e642fbaa76e10426a5187f"
  },
  {
      "id": "h-gen-8e6d8140c3ef8c23",
      "subject": "act-english",
      "question_id": "ti-gen-f353d63071548ccf",
      "rung": 2,
      "body_md": "Consider how to indicate possession when the owner is plural and already ends with an 's'.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b892e8a9a7e642fbaa76e10426a5187f"
  },
  {
      "id": "h-gen-da3261b3246cc478",
      "subject": "act-english",
      "question_id": "ti-gen-f353d63071548ccf",
      "rung": 3,
      "body_md": "Look closely at the word that indicates who the costumes belong to and think about how to properly show that relationship.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@b892e8a9a7e642fbaa76e10426a5187f"
  },
  {
      "id": "h-gen-c7c28ca9d3d5b351",
      "subject": "act-english",
      "question_id": "ti-gen-f42903f54fb3d4b9",
      "rung": 1,
      "body_md": "What do you think about the way the memoir describes the rivals? Do you see any negative implications in the wording used?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3e926d69b3a145308600c39fcbd7c3ff"
  },
  {
      "id": "h-gen-8c9f64c2d7d7963e",
      "subject": "act-english",
      "question_id": "ti-gen-f42903f54fb3d4b9",
      "rung": 2,
      "body_md": "Consider how words can carry different connotations. What does it mean for a word to have a negative connotation?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3e926d69b3a145308600c39fcbd7c3ff"
  },
  {
      "id": "h-gen-1413532918df7ae1",
      "subject": "act-english",
      "question_id": "ti-gen-f42903f54fb3d4b9",
      "rung": 3,
      "body_md": "Look closely at the context in which the rivals are described. How do the characteristics mentioned influence your perception of them?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@3e926d69b3a145308600c39fcbd7c3ff"
  },
  {
      "id": "h-gen-759e78ed4b88b3b9",
      "subject": "act-english",
      "question_id": "ti-gen-f5935917bf02bf12",
      "rung": 1,
      "body_md": "What do you think about the phrase used to describe the waiting room? How does it make you feel about the space?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ef4643006a040ddb497d643d133c2d6"
  },
  {
      "id": "h-gen-2a7409998dac0a06",
      "subject": "act-english",
      "question_id": "ti-gen-f5935917bf02bf12",
      "rung": 2,
      "body_md": "Consider the importance of using formal language in professional documents. What characteristics define formal diction?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ef4643006a040ddb497d643d133c2d6"
  },
  {
      "id": "h-gen-7999e0119a629297",
      "subject": "act-english",
      "question_id": "ti-gen-f5935917bf02bf12",
      "rung": 3,
      "body_md": "Look closely at the options provided and think about which words convey a sense of professionalism and neutrality. How do the choices differ in tone?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@8ef4643006a040ddb497d643d133c2d6"
  },
  {
      "id": "h-gen-5604140732b7c561",
      "subject": "act-english",
      "question_id": "ti-gen-f93b402b9faaa78b",
      "rung": 1,
      "body_md": "What do you think about the way the sentence is currently structured?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2eef28369a6a4b75967567c0fc93488e"
  },
  {
      "id": "h-gen-ef4766930f99f06c",
      "subject": "act-english",
      "question_id": "ti-gen-f93b402b9faaa78b",
      "rung": 2,
      "body_md": "Consider the rule regarding independent clauses and how they can be connected.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2eef28369a6a4b75967567c0fc93488e"
  },
  {
      "id": "h-gen-bae6c15384ed9ce1",
      "subject": "act-english",
      "question_id": "ti-gen-f93b402b9faaa78b",
      "rung": 3,
      "body_md": "Look closely at the punctuation options and think about how they affect the relationship between the two parts of the sentence.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@2eef28369a6a4b75967567c0fc93488e"
  },
  {
      "id": "h-gen-b286a9b3e0bb953b",
      "subject": "act-english",
      "question_id": "ti-gen-fb64033d78c6ae8e",
      "rung": 1,
      "body_md": "What do you think about the way the engine's performance is described in the sentence?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f3e3e3f0a7da4539b5f07d5e7ab19f20"
  },
  {
      "id": "h-gen-22f6aaa58c326053",
      "subject": "act-english",
      "question_id": "ti-gen-fb64033d78c6ae8e",
      "rung": 2,
      "body_md": "Consider the difference between adjectives and adverbs in modifying verbs.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f3e3e3f0a7da4539b5f07d5e7ab19f20"
  },
  {
      "id": "h-gen-5274104eea306846",
      "subject": "act-english",
      "question_id": "ti-gen-fb64033d78c6ae8e",
      "rung": 3,
      "body_md": "Look closely at how the underlined phrase describes the action of the engine and think about what type of word is needed to modify that action.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@f3e3e3f0a7da4539b5f07d5e7ab19f20"
  },
  {
      "id": "h-gen-286aab7e03eb447a",
      "subject": "act-english",
      "question_id": "ti-gen-fbd84e33e8d1095c",
      "rung": 1,
      "body_md": "What do you think the writer is trying to express about the influence of the grandmother's lessons?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbc4449eb3b84fb0a390a1eb7906c44c"
  },
  {
      "id": "h-gen-52cdeb6b1aa05569",
      "subject": "act-english",
      "question_id": "ti-gen-fbd84e33e8d1095c",
      "rung": 2,
      "body_md": "Consider what it means for something to have a lasting impact on someone's development.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbc4449eb3b84fb0a390a1eb7906c44c"
  },
  {
      "id": "h-gen-f429c98c8bc4de27",
      "subject": "act-english",
      "question_id": "ti-gen-fbd84e33e8d1095c",
      "rung": 3,
      "body_md": "Look closely at the meaning of the underlined phrase and think about how it relates to the overall message of the essay.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@fbc4449eb3b84fb0a390a1eb7906c44c"
  },
  {
      "id": "h-gen-e153ce2b2429cfd0",
      "subject": "act-english",
      "question_id": "ti-gen-fef10b2484a7f035",
      "rung": 1,
      "body_md": "What do you think about the timing of the action described in the underlined phrase?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@99f02e0a3bbb4a84b62aa944cb8bce98"
  },
  {
      "id": "h-gen-6f7be161647afe2a",
      "subject": "act-english",
      "question_id": "ti-gen-fef10b2484a7f035",
      "rung": 2,
      "body_md": "Consider the concept of verb tenses, particularly how they indicate the timing of actions in relation to each other.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@99f02e0a3bbb4a84b62aa944cb8bce98"
  },
  {
      "id": "h-gen-32cce852d1040ca4",
      "subject": "act-english",
      "question_id": "ti-gen-fef10b2484a7f035",
      "rung": 3,
      "body_md": "Look closely at the context of the entire sentence and think about how the timing of the action in the underlined phrase relates to the other events mentioned.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@99f02e0a3bbb4a84b62aa944cb8bce98"
  },
  {
      "id": "h-gen-3085934e722cb497",
      "subject": "act-english",
      "question_id": "ti-gen-ffcac62995b325e2",
      "rung": 1,
      "body_md": "What do you think the phrase in question means in this context?",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@167b814458e740c88d18cb6f94397b33"
  },
  {
      "id": "h-gen-8083fb4bb47c450f",
      "subject": "act-english",
      "question_id": "ti-gen-ffcac62995b325e2",
      "rung": 2,
      "body_md": "Consider the concept of expressions that describe works made from existing elements or styles.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@167b814458e740c88d18cb6f94397b33"
  },
  {
      "id": "h-gen-788e93bbb7b5bf5c",
      "subject": "act-english",
      "question_id": "ti-gen-ffcac62995b325e2",
      "rung": 3,
      "body_md": "Look closely at the meanings of the options provided and compare them to the idea of a work that combines familiar elements.",
      "reviewed": true,
      "generated_by": "gpt-4o-mini@167b814458e740c88d18cb6f94397b33"
  },
];

/**
 * Explicit FR-A3 waivers — (question_id, rung) ladder gaps the coverage
 * ratchet (`_hint_bank.test.ts`) accepts. An empty table means every
 * reviewed bank item carries a full 3-rung ladder.
 */
export const HINT_BANK_WAIVERS: ReadonlyArray<{
  readonly question_id: string;
  readonly rung: 1 | 2 | 3;
  readonly reason: string;
}> = [];

/** Load the reviewed hint ladders into the dev in-memory engine DB. */
export function seedHintBank(db: InMemoryEngineDb): void {
  db.seedHints([...HINT_BANK]);
}
