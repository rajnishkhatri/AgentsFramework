---
type: research
title: Teaching-Strategy Framework for the Subject-Coach Tutoring System
description: Runtime coaching pedagogy and item-bank design framework for the subject coach — how tutoring strategy and item structure connect (grounding for Epic E lesson generation).
tags: [research, eng-coach, pedagogy]
---

# A Teaching-Strategy Framework for the Subject-Coach Tutoring System: Runtime Coaching Pedagogy and Item-Bank Design

## TL;DR
- **Build the coach as a two-loop decision engine (VanLehn): an outer loop that selects and spaces items by skill/difficulty, and an inner loop that responds turn-by-turn with the least assistance sufficient to get the student unstuck — escalating pump → hint → prompt → assertion, and always diagnosing the specific misconception behind a wrong answer before saying anything.** The single most leveraged design decision is to make each item's distractors carry machine-readable misconception tags so the inner loop can deliver misconception-targeted feedback and a targeted Socratic prompt instead of a generic rule restatement.
- **The item bank (Axis B) is the fuel for the coaching pedagogy (Axis A).** Every distractor should encode one documented, diagnosable error; each item should carry skill-tag, standard, and difficulty metadata; and each should ship with a distractor-level rationale and a worked heuristic. This is what lets the autograder distinguish "pedagogically correct scaffolding" from "answer leakage" and lets the outer loop sequence adaptively.
- **The strongest evidence base is well-established (worked-example effect, faded worked examples, the assistance dilemma, formative-feedback taxonomies, ICAP, retrieval/spacing/interleaving, Haladyna item-writing rules); the emerging and contested frontier is LLM-specific — Socratic guardrails, answer-leakage detection, and LLM-as-judge reliability, where 2023–2026 work shows real gains but also that generic LLM judges correlate poorly with human pedagogy labels.**

## Key Findings

**1. Two-loop architecture is the organizing backbone (VanLehn, 2006/2011).** Tutoring systems have an *outer loop* (executes once per task: selects the next problem) and an *inner loop* (executes once per step: gives feedback and hints within a problem). VanLehn's criterion is that having an inner loop is what makes a system an ITS rather than mere CAI. In VanLehn's 2011 review ("The Relative Effectiveness of Human Tutoring, Intelligent Tutoring Systems, and Other Tutoring Systems," *Educational Psychologist* 46(4):197–221), **step-based ITS reached an effect size of d=0.76 versus no tutoring, essentially matching human tutoring at d=0.79** — overturning the long-assumed 1.0 and 2.0 figures — while weaker "substep-based" systems reached only d=0.40. Map your LangGraph agents directly onto this: an outer-loop "sequencer" node and an inner-loop "coach" node.

**2. The assistance dilemma is the central runtime tension (Koedinger & Aleven, 2007/2008).** Withholding help too long causes frustration and wasted time; giving too much causes shallow learning and disengagement. There is no fixed answer — the optimal amount of assistance depends on learner expertise, which is why *contingent scaffolding* and *fading* are the resolution mechanisms, not a fixed hint policy.

**3. Worked examples, faded to problems, beat unsupported problem-solving for novices (Sweller; Renkl & Atkinson; Salden/Schwonke).** The worked-example effect is robust even against well-supported tutored problem-solving. The practical instantiation is *backward fading* (remove the last solution step first, then progressively earlier steps) turning a worked example into a series of completion problems. Critically, this reverses with expertise — the *expertise reversal effect*: examples that help novices become redundant and even harmful for more advanced learners, so fading should be adaptive to demonstrated competence.

**4. Formative-feedback structure (Hattie & Timperley, 2007; Shute, 2008).** Hattie & Timperley's model: effective feedback answers "Where am I going?" (feed-up), "How am I going?" (feed-back), "Where to next?" (feed-forward), operating at four levels (task, process, self-regulation, self — avoid the "self/praise" level). Shute's taxonomy distinguishes verification (knowledge of results, KR), knowledge of correct response (KCR), and *elaborated feedback* (addresses topic, response, specific errors, worked examples, or gentle guidance). Elaborated, response-specific feedback outperforms bare verification. Timing: immediate feedback helps low-achievers and on difficult tasks; delayed feedback can favor high-achievers and transfer. Shute's guideline set: focus on the task not the learner, keep it specific and manageable, be nonevaluative and supportive.

**5. Dialogue-move taxonomy from AutoTutor and human-tutoring research (Graesser & Person).** The core escalation ladder, from most student-generated to most tutor-supplied: **pump** ("What else? Tell me more" — elicits without giving), **hint** (a question or nudge that leads toward the target information), **prompt** (a fill-in-the-blank leaving out a specific keyword), **assertion/elaboration** (tutor states the information), **correction**, and **summary**. AutoTutor's Expectation-Misconception Tailored (EMT) dialogue matches student utterances against a list of *expectations* (good answers) and *misconceptions* (anticipated errors) and tailors moves accordingly. The **5-step tutoring frame** (Graesser & Person, 1994): (1) tutor asks question; (2) student answers; (3) tutor gives short immediate feedback; (4) tutor and student collaboratively improve the answer (5–10 turns); (5) tutor gauges understanding.

**6. Misconception-targeted remediation is the differentiator.** The whole point of encoding misconceptions in distractors is so the coach responds to *the specific error* rather than restating the rule. This is validated by the LLM-tutor evaluation literature: Maurya, Srivatsa, Petukhova & Kochmar's (2025, "Unifying AI Tutor Evaluation," arXiv:2412.09416) eight-dimension taxonomy for AI tutors treats *mistake identification* and *mistake location* as distinct dimensions from *providing guidance*.

**7. Retrieval, spacing, interleaving, desirable difficulties (Bjork).** "Desirable difficulties" — conditions that slow acquisition but improve long-term retention and transfer: spacing, interleaving, retrieval practice, generation, variation. Interleaving forces discrimination between problem types (learning *when*, not just *how*). Key caveat: these become *undesirable* if the learner lacks the background to respond successfully — so the coach must gate difficulty on demonstrated mastery.

**8. Self-explanation effect (Chi et al., 1989/1994).** Prompting students to explain *why* — their reasoning, why an answer is right/wrong — produces reliable learning gains. Bisra, Liu, Nesbit, Salimi & Winne (2018, "Inducing Self-Explanation: a Meta-Analysis," *Educational Psychology Review* 30(3):703–725) report **"The overall weighted mean effect size using a random effects model was g = 0.55"** across 69 effect sizes from 64 reports. Prompted self-explanation converts external feedback into usable internal understanding. This is a high-ICAP move.

**9. Cognitive Load Theory as the constraint (Sweller).** Three loads: intrinsic (inherent complexity × prior knowledge), extraneous (poor presentation — minimize), germane (schema-building — support). Working memory holds only ~4 chunks. Every coaching turn must avoid overloading: one idea per turn, segment multi-step reasoning, don't dump the whole rule when a targeted nudge suffices.

**10. ICAP as a ranking of engagement (Chi & Wylie, 2014).** Interactive > Constructive > Active > Passive. This gives the autograder a principled way to score coaching moves: a move that elicits student generation (constructive/interactive) outranks one that has the student passively receive an explanation. The biggest jump is Active→Constructive.

**11. Bloom's 2-sigma and mastery learning — aspirational, not literal.** Bloom (1984) reported one-to-one tutoring + mastery learning put the average student ~2 SD above classroom peers. Modern reanalyses find this figure inflated: Nickow, Oreopoulos & Quan (2020, NBER Working Paper 27476) report **"an overall pooled effect size estimate of 0.37 SD"** across 96 screened studies (~14 percentile points), with none reaching 2 sigma; the peer-reviewed 2024 *AERJ* version reports an even lower pooled effect of **0.288 SD** (SE=0.029, p<.001). VanLehn's review put tutoring nearer d≈0.79, and mastery learning alone is roughly 0.5–1.0 sigma. Takeaway: mastery-gating (don't advance until the skill is demonstrated) is well-supported; the "2 sigma" number should be treated as motivational framing, not a target.

**12. Productive confusion / impasse-driven learning (VanLehn; D'Mello & Graesser; Kapur).** Confusion is the only emotion that consistently *predicts* learning — but only when *resolved*. Per D'Mello & Graesser (2012), citing VanLehn et al. (2003, "Why Do Only Some Events Cause Learning During Human Tutoring?"), **"learners acquired a physics principle in only 33 of the 62 impasse occurrences … because their impasses were not resolved for the remaining 29 cases."** The coach should tolerate and even engineer brief productive struggle, but detect and rescue *persistent* confusion before it decays into frustration/boredom.

**13. LLM-tutor guardrails and answer-leakage (2023–2026, emerging).** Khanmigo's design thesis is that "the guardrails are the product" — the hard engineering is making it *not* give answers; it requires students to attempt first and guides via questions. Empirically, per Maurya et al. (2025) reporting on Macina et al. (2023, MathDial, EMNLP Findings, 2,861 dialogues), **"ChatGPT as a tutor reveals the solution 66% of the time and provides incorrect feedback 59% of the time"** — leakage measured as a "telling@k" score. Specialized/fine-tuned tutors (SocraticLM, MathDial-SFT) reduce leakage but often lower raw solve rates — the same assistance-dilemma tradeoff, now measurable. Caution: Maurya et al. found the Prometheus2 LLM-judge's pedagogical annotations correlate poorly (sometimes negatively) with human labels — so an LLM-as-judge autograder needs careful rubric design and human calibration, not blind trust.

## Details

### AXIS A — Runtime Coaching Pedagogy (weighted more heavily)

**A.1 The inner-loop decision procedure (turn-by-turn).**
On each student turn, the coach should execute this decision cascade:

1. **Classify the response** against the item's expectation set and misconception set (EMT-style). For an MCQ, the chosen distractor *is* the classification signal — read its misconception tag.
2. **Short verification feedback first** (KR/KCR-lite): brief positive/neutral/negative acknowledgment. Keep it non-evaluative of the person.
3. **Select the least-assistance move** that can move the student forward, escalating only on repeated failure:
   - **Pump** ("What made you pick that? What's the next thing you notice?") — highest ICAP, zero leakage.
   - **Hint** — a question or cue pointing at the relevant feature ("Look at the verb — what's its subject?"), still no answer.
   - **Prompt** — fill-in-the-blank for a specific keyword ("So the subject is singular, which means the verb must be ___").
   - **Assertion/elaboration** — state the rule/step, used only after prompts fail (cap at ~2–3 prompts before asserting, per the MWPTutor guardrail pattern in "AutoTutor meets Large Language Models," 2024).
4. **Misconception-targeted elaboration, not rule restatement.** If the distractor tag is, e.g., "treats intervening prepositional phrase as the subject," the feedback targets *that* ("The phrase 'of the students' sits between subject and verb — is 'students' really the subject?"), not "subjects and verbs must agree."
5. **Self-explanation prompt** to consolidate ("Why does the singular verb work here?").
6. **Gauge understanding** (step 5 of the frame) before advancing.

**A.2 Feedback decision rules (implementable).**
- Default to **elaborated, response-specific** feedback over bare KR/KCR.
- **Never include the correct option letter/value** in any hint or prompt (this is the leakage line). Assertions may reveal it, and should only fire after the escalation ladder is exhausted or the student explicitly disengages.
- Structure longer feedback on Hattie & Timperley: confirm the goal (feed-up), locate the gap (feed-back), give the next move (feed-forward).
- **Timing:** immediate feedback for struggling students and hard items; consider slightly delayed / withheld verification to preserve productive struggle for stronger students.
- Keep each turn to one chunk (CLT): no multi-rule dumps.

**A.3 Scaffolding and fading.**
Use *contingent* scaffolding — calibrate support to the current response, and *fade* it as competence grows (backward fading of worked steps; example → completion problem → independent problem). Make fading adaptive to demonstrated mastery to avoid the expertise-reversal effect. Watch for "click-through"/help-abuse and "learned helplessness" from over-scaffolding.

**A.4 The Socratic layer — best practices and failure modes.**
- **Ask before telling; guide discovery.** The Socratic ideal is that the student articulates the rule. Operationalize via the pump→hint→prompt ladder.
- **Balance Socratic method against efficiency.** Pure questioning that loops without progress is a known failure mode — it frustrates and wastes time (this is the assistance dilemma from the "withhold" side). Rule: bound the number of Socratic turns on a single sub-step; if the student is at a genuine impasse after N nudges, provide a more direct hint or a worked step. Detect persistent (unproductive) confusion and rescue it.
- **Guardrail implementation** (from Khanmigo and MWPTutor patterns): (a) require a student attempt before any guidance; (b) constrain the generator so hints/prompts must not contain the answer token; (c) ground the tutor in verified item content/rationale rather than free generation; (d) log every turn for review. Khanmigo uses model routing (e.g., GPT-4 for tutoring) and content grounding in Khan Academy's library; its known weakness is arithmetic reliability, an argument for offloading deterministic checks (grammar-rule verification) to non-LLM logic.

**A.5 Motivation and affect.**
Handle frustration and confusion as first-class states. Use encouragement tied to process/effort and specific progress, not empty praise ("Great job!" with no referent is the low-value "self" level of Hattie & Timperley). Engineer brief productive confusion at impasses but monitor the confusion→frustration→boredom transition (D'Mello & Graesser) and intervene before disengagement.

**A.6 Sequencing, retrieval, spacing, interleaving (outer loop).**
- **Mastery-gate** advancement (don't move on until the skill is demonstrated).
- **Space** re-tests of a skill across sessions rather than massing.
- **Interleave** skill types once basics are in place, to build discrimination (when to apply which rule) — highly relevant for ACT-English where the challenge is often identifying *which* rule a sentence tests.
- Treat these as desirable difficulties gated on mastery: don't interleave/space a skill the student hasn't yet minimally acquired.

### AXIS B — Item and Question-Bank Design

**B.1 Distractor design grounded in misconceptions.** Per Haladyna, Downing & Rodriguez (2002, *Applied Measurement in Education* 15(3):309–333) and Haladyna & Rodriguez (2013, *Developing and Validating Test Items*): make all distractors plausible, and *base distractors on common student errors* (their Rule 30). The most effective way to generate plausible distractors is to identify the common errors elicited by the stem. Each distractor should map to one specific, diagnosable misconception — no throwaway/implausible options. Gierl, Bulut, Guo & Zhang (2017, *Review of Educational Research* 87(6):1082–1116): distractor analysis "can reveal students' misconceptions, which can then guide the type of instruction and remedial lessons required," and the chosen distractor gives "hidden information about student learning."

**B.2 Distractor rationales.** Ship a written rationale per distractor stating the misconception it encodes and the feedback line the coach should surface. This is the artifact that connects Axis B to Axis A.

**B.3 Non-functioning distractors.** A distractor chosen by <5% of examinees is "non-functioning" (Haladyna & Downing, 1993). Empirically most items have only 1–2 functioning distractors (Tarrant, Ware & Mohammed, 2009, *BMC Medical Education* 9:40, found only 52.2% of distractors functioning, averaging 1.54 per item). Guidance: "an item with two plausible distractors is preferable to an item with three or four implausible distractors."

**B.4 Number of options.** Rodriguez (2005, "Three Options Are Optimal for Multiple-Choice Items: A Meta-Analysis of 80 Years of Research," *Educational Measurement: Issues and Practice* 24(2):3–13) concludes: **"More 3-option items can be administered than 4- or 5-option items per testing time while improving content coverage, without detrimental effects on psychometric quality of test scores."** Since ACT English uses 4 options, the fourth option must be justified by a genuine documented misconception, not filler; expect many items to function effectively as 3-option items. Removing options *randomly* harms reliability — keep options functional, don't just cut them.

**B.5 Difficulty and discrimination calibration.** Use classical-test-theory bands (Ebel & Frisbie, 1991, *Essentials of Educational Measurement*): discrimination D ≥ 0.40 "very good," 0.30–0.39 "reasonably good but possibly subject to improvement," 0.20–0.29 "marginal … need some revision," <0.20 "poor … major revision or should be eliminated"; negative discrimination flags a miskeyed/flawed item. Point-biserial >0.20 desirable, <0 flags a flaw. Difficulty (p-value) desirable range ~0.30–0.70; discrimination is maximized near p≈0.50, so high-stakes forms cluster there while practice banks can run easier. Difficulty should map onto the skill/standard progression (easier items → easier standards).

**B.6 Stem quality.** Single-skill targeting; avoid double-barreled items (testing two skills at once); clear whether the item is a "grammar/usage" item (one defensible correct answer per standard written English) vs. a "rhetorical/goal" item (all options may be grammatical; correct = best serves purpose — roughly half of ACT English). This distinction matters for the coach: goal-framed items need feedback about purpose/relevance, grammar items need rule-based feedback.

**B.7 Misconception-targeted authoring and diagnostic distractors.** Consider Ordered Multiple-Choice (Briggs, Alonzo, Schwab & Wilson, 2006, "Diagnostic Assessment With Ordered Multiple-Choice Items," *Educational Assessment* 11(1):33–63; building on Sadler, 1998, *JRST* 35): options map to levels of a learning progression, so the distractor chosen locates the student developmentally. Caveat (Briggs et al.): single-item misconception inferences "can lack reliability" — use multiple items per misconception.

**B.8 The pedagogical rule/explanation attached to each item.** A good explanation is a *worked heuristic* (a procedure the student can reapply: "Cross out the phrase between subject and verb, then check agreement") rather than a bare fact ("The subject is 'list'"). Keep rule *type* consistent and tagged — procedure vs. fact vs. meta-strategy — so the coach knows what kind of move to scaffold and the autograder can check type consistency.

**B.9 Coverage, redundancy, bank balance.** Map items to a skill taxonomy; ensure coverage across standards and difficulty within each skill; avoid near-duplicate items (they inflate apparent coverage and enable memorization over transfer). Multiple non-duplicate items per skill support reliable diagnosis and spacing/interleaving.

**B.10 Metadata for adaptive sequencing.** Tag every item with skill, standard, difficulty (p and/or IRT b), and discrimination (a). Adaptive item selection (Han, 2018, *J. Educ. Eval. Health Prof.* 15:7) rests on three components — content balancing (uses skill tags), an item-selection criterion (uses difficulty/discrimination, e.g., maximized Fisher information), and exposure control. a-stratified CAT (Chang & Ying, 1999) administers low-discrimination items early and reserves high-discrimination items for later once ability is better estimated; cognitive-diagnostic CAT (Cheng, 2010) balances coverage across skills/attributes.

### Integration: how Axis B feeds Axis A
The pipeline is: **student picks distractor D → item metadata resolves D to misconception tag M and its rationale R → coach's inner loop selects a misconception-targeted move (a Socratic hint aimed at M, drawn from R) instead of a generic rule restatement → self-explanation prompt → mastery update in the outer loop → spacing/interleaving schedule adjusts.** Concretely: a subject-verb-agreement item whose distractor encodes "agrees verb with nearest noun, not the true subject" lets the coach ask "What's the actual subject here — is it the word right before the verb?" That targeted prompt is only possible because the item author pre-encoded the misconception. Without the tag, the coach can only restate the rule (low ICAP, often experienced as unhelpful). The distractor rationale also gives the LLM-as-judge autograder the ground truth to check two things at once: (1) did the coach target the *right* misconception (pedagogical quality), and (2) did the coach avoid stating the correct option (answer-leakage).

### Autograder / LLM-as-judge design implications
- Score coaching turns on a multi-dimension rubric aligned to Maurya et al.'s eight dimensions — verbatim: **"(1) mistake identification, (2) mistake location, (3) revealing of the answer, (4) providing guidance, (5) actionability, (6) coherence, (7) tutor tone, and (8) human-likeness"** (released with the MRBench benchmark, built from the MathDial and Bridge datasets). Use ICAP level and the pump/hint/prompt/assertion label as additional structured features.
- Answer-leakage detection: because the item knows its correct option, the judge can do a deterministic string/semantic check for the answer token *plus* an LLM check for indirect give-aways ("it must be the singular one"). Note the baseline scale of the problem — unguarded ChatGPT reveals the solution 66% of the time (MathDial).
- Calibrate the judge against human pedagogy labels — the literature shows generic LLM judges (Prometheus2) can correlate poorly or negatively with humans on fine-grained pedagogy, so hold out a human-annotated set.
- Benchmarks to borrow rubric structure from: MRBench, MathDial, TutorBench, MathTutorBench, and SafeTutors (adversarial student attacks / leakage robustness).

## Recommendations

**Stage 1 — Instrument the item bank first (highest leverage).** Add to every item: skill tag, standard, difficulty (start with p-value from usage logs), and — most important — a per-distractor misconception tag and rationale, plus a rule-type tag (procedure/fact/meta-strategy). Benchmark to change plan: if >5%-selection analysis shows a large share of distractors are non-functioning once you have data, rewrite them from documented errors (target: ≥2 functioning distractors per item).

**Stage 2 — Build the inner-loop coach as an explicit move-selector.** Implement the pump→hint→prompt→assertion ladder as discrete, labeled actions with a hard rule: hints/prompts may never contain the correct option; require a student attempt before guidance; cap prompts (~2–3) before an assertion. Wire the misconception tag into move selection so remediation targets the specific error.

**Stage 3 — Build the outer-loop sequencer with mastery-gating + spacing + interleaving.** Gate advancement on demonstrated mastery; space skill re-tests across sessions; interleave skills once acquired. Use difficulty/discrimination metadata for selection; start with simple difficulty-matching, graduate to a-stratified-style logic.

**Stage 4 — Harden the autograder.** Implement the eight-dimension rubric + ICAP + move-label + deterministic leakage check. Hold out a human-labeled calibration set; track judge-vs-human correlation and do not ship dimensions where correlation is weak. Threshold to change plan: if leakage-detection precision/recall on adversarial student prompts is poor, add a multi-agent refine step or constrained decoding.

**Stage 5 — Affect and productive struggle.** Add impasse detection: allow brief struggle, bound Socratic looping, rescue persistent confusion, and replace generic praise with process-specific encouragement.

**Benchmarks that would change these recommendations:** if learning-gain A/Bs show pure-Socratic looping depresses completion or gains vs. faster hinting, shorten the ladder; if expertise-reversal shows up (advanced students slowed by scaffolds), fade faster; if interleaving hurts early acquisition, delay it until mastery thresholds are higher.

## Caveats
- **Well-established vs. emerging.** Worked-example/faded-example effects, the assistance dilemma, CLT, Hattie & Timperley / Shute feedback taxonomies, ICAP, Bjork's desirable difficulties, self-explanation, and Haladyna item-writing rules are all robust, peer-reviewed, and decades-deep. LLM-specific tutoring guardrails, answer-leakage metrics, and LLM-as-judge pedagogy scoring are 2023–2026 and *emerging* — directionally supported but not yet settled.
- **Bloom's 2 sigma is contested and likely inflated;** treat mastery-gating as the supported practice and 2 sigma as motivational, not a KPI. Best current estimates of tutoring effects are far lower (0.29–0.79 SD depending on method and meta-analysis).
- **LLM-as-judge reliability is a genuine risk** — documented poor correlation with human pedagogy labels on fine-grained dimensions; requires human calibration.
- **Domain transfer:** much of the ITS evidence (AutoTutor, Cognitive Tutors) is from math/physics; the dialogue-move and feedback principles transfer well to ACT-English grammar, but some psychometric benchmark numbers (functioning-distractor rates from Tarrant et al.) come from medical/nursing samples and are context-specific.
- **Effect-size figures** (d≈0.76 step-based tutoring; g=0.55 self-explanation; 0.29–0.37 SD tutoring meta-analyses) come from meta-analyses with heterogeneous studies; use as orientation, not precise predictions.
- **Interleaving/spacing/desirable difficulties can backfire** if applied before minimal acquisition — they are gated goods.