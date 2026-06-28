# The Comprehension-Debt Runbook: Rules and Forced-Engagement Gates for a Solo Agentic Coding Practice

**Runbook 3 of 3 — for one senior engineer plus their coding agent.**

## TL;DR
- **Comprehension debt — the gap between code that exists and code any human genuinely understands — is best controlled at write-time with two coordinated mechanisms: (1) a drop-in AGENTS.md/CLAUDE.md directive block that constrains the agent's behavior, and (2) a library of forced-engagement approval gates worded so you cannot rubber-stamp them.** The empirical anchor is Anthropic's randomized controlled trial (Shen & Tamkin, "How AI assistance impacts the formation of coding skills," published Jan 29, 2026): the AI-assisted group averaged 50% on a comprehension quiz versus 67% for the hand-coding group — "the equivalent of nearly two letter grades (Cohen's d=0.738, p=0.01)" — with the largest gap on debugging questions.
- **The single most important design move is to make every gate require you to PRODUCE something — a prediction, an explanation in your own words, the load-bearing line — BEFORE the agent reveals its account.** This is grounded in the generation effect (Slamecka & Graf, 1978), the self-explanation effect (Chi et al., 1989), the illusion of explanatory depth (Rozenblit & Keil, 2002), and cognitive forcing functions, which in a controlled N=199 study (Buçinca, Malaya & Gajos, 2021) significantly reduced overreliance on incorrect AI advice compared with simple explainable-AI designs.
- **Gates must fire only on comprehension-risky changes (new abstractions, dependencies, security boundaries, complex algorithms, large or wide diffs, unfamiliar APIs, architecture). Over-gating trivial changes trains automaticity and reintroduces rubber-stamping** — so the runbook includes decision thresholds and an anti-habituation rotation of question wording.

## Key Findings

**1. Comprehension debt is real, measurable, and invisible to your dashboards.** Addy Osmani (Director, Google Cloud AI) defines it as "the growing gap between how much code exists in your system and how much of it any human being genuinely understands." Unlike technical debt, it "breeds false confidence. The codebase looks clean. The tests are green. The reckoning arrives quietly, usually at the worst possible moment." Velocity, DORA metrics, PR counts, and coverage all stay green while it accrues. Margaret-Anne Storey (University of Victoria), in "From Technical Debt to Cognitive and Intent Debt: Rethinking Software Health in the Age of AI" (ACM Queue; arXiv 2603.22106, v1 Mar 23 2026), proposes a Triple Debt Model: "two under appreciated forms of debt accumulate: cognitive debt, the erosion of shared understanding across a team, and intent debt, the absence of externalized rationale that developers and AI agents need to work safely with code." She recounts a student team that by week seven "could no longer make even simple changes without breaking something unexpected" — the theory of the program had evaporated.

**2. The mechanism is generation-verification asymmetry plus passive delegation.** AI generates code far faster than a human can critically audit it; Osmani notes the inversion: "a junior engineer can now generate code faster than a senior engineer can critically audit it… What used to be a quality gate is now a throughput problem." The Anthropic RCT found that *how* you use AI determines retention: passive delegation ("just make it work") impairs skill development far more than active, question-driven use. The high-scoring participants "used AI assistance not just to produce code but to build comprehension while doing so—whether by asking follow-up questions, requesting explanations, or posing conceptual questions." Delegation-pattern clusters averaged under 40%; conceptual-inquiry and hybrid clusters scored 65%+. Anthropic explicitly notes their setup "is different from agentic coding products like Claude Code; we expect that the impacts of such programs on skill development are likely to be more pronounced than the results here."

**3. Forced-engagement gates work because they exploit well-established cognitive mechanisms.** The generation effect (Slamecka & Graf, 1978: across five experiments "performance in the generate condition was superior to that in the read condition" for recognition, recall, and confidence) shows produced answers beat read ones. The self-explanation effect (Chi et al., 1989) shows good learners "generate many explanations… and relate these actions to principles," while poor learners "do not generate sufficient self-explanations [and] monitor their learning inaccurately." The illusion of explanatory depth (Rozenblit & Keil, 2002, *Cognitive Science* 26(5):521–562) shows "people feel they understand complex phenomena with far greater precision, coherence, and depth than they really do" — confidence collapses the instant they must produce a step-by-step explanation. That collapse is exactly the false confidence comprehension debt rides on. Cognitive forcing strategies from clinical medicine (Croskerry, 2003, *Annals of Emergency Medicine*: metacognitive techniques to "force practitioners out of pattern recognition into a more analytic mode") and accountability manipulations from automation-bias research (Skitka, Mosier & Burdick, 2000: "making participants accountable for either their overall performance or their decision accuracy led to lower rates of 'automation bias'") are the direct precedents for "make the human justify before approving."

**4. Cognitive forcing functions measurably cut AI overreliance — at a usability cost.** Buçinca, Malaya & Gajos ("To Trust or to Think," *Proc. ACM Hum.-Comput. Interact.* 5, CSCW1, Article 188, April 2021; N=199 on MTurk) tested designs that hide the AI's answer, require the human to decide first then update, or impose a wait. They found "cognitive forcing significantly reduced overreliance compared to the simple explainable AI approaches. However, there was a trade-off: people assigned the least favorable subjective ratings to the designs that reduced the overreliance the most." Crucially, "people over-relied less on the AI when exposed to the conditions that they found more difficult, preferred less, and trusted less," and the benefit "benefited the more advantaged group—people with high NFC [Need for Cognition]—the most." The friction is the feature; expect to dislike it.

**5. Over-gating is itself a failure mode.** Automation complacency (Parasuraman & Manzey, 2010, *Human Factors*) is driven by constant, high-reliability automation under multitask load and "is found in both naive and expert participants and cannot be overcome with simple practice." If every change fires a gate, you habituate and auto-approve — the rubber-stamping the gates exist to prevent. Gate frequency must be calibrated to risk, and gate wording must vary.

## Details

### Part A — Why each rule exists (mechanism map)

| Mechanism | Source | Implication for the runbook |
|---|---|---|
| Generation-verification asymmetry | Osmani; Karpathy | Agent output volume outpaces audit; cap diff size, force walkthroughs |
| Passive delegation degrades skill | Shen & Tamkin (Anthropic RCT, 2026) | Require active, question-driven engagement at gates |
| Illusion of explanatory depth | Rozenblit & Keil (2002) | Make the human explain mechanism before seeing the agent's account |
| Generation effect (generated > read) | Slamecka & Graf (1978) | Human predicts/states first; reading the agent's explanation is weaker |
| Self-explanation effect | Chi et al. (1989) | Explain-back / Feynman prompts produce real understanding |
| Retrieval/testing effect & desirable difficulties | Roediger & Karpicke (2006); Bjork | Effortful recall at the gate beats re-reading the diff |
| Automation bias & complacency | Parasuraman & Manzey (2010) | Vary gate reliability/wording; avoid constant low-value gates |
| Accountability reduces automation bias | Skitka, Mosier & Burdick (2000) | Require the human to justify the approval, not just click yes |
| Cognitive forcing functions reduce overreliance | Croskerry (2003); Buçinca et al. (2021) | Disrupt heuristic acceptance, force System-2 engagement |
| Productive friction / microboundaries | Cox et al. (2016); Chen & Schmidt | Small deliberate speed bumps shift System-1 → System-2 |
| Checklist design (DO-CONFIRM, 5–9 items, pause points) | Gawande, *The Checklist Manifesto* | Gate format: short, pause-pointed, resists automaticity |

### Part B — TRACK 1: Drop-in AGENTS.md / CLAUDE.md directive block

> Paste the block below into `AGENTS.md` (symlink `CLAUDE.md` to it). Keep the whole file under ~150 lines and front-load these rules; research on instruction-following indicates long files get truncated and diluted (frontier thinking models reliably follow on the order of 150–200 instructions, fewer for smaller models). Use deterministic tools (linters, formatters, tests) for style so these rules stay focused on comprehension, not cosmetics. Phrase prohibitions as "Prefer X over Y" where possible — positive guidance is followed more reliably than "Do not."

```markdown
# AGENTS.md — Comprehension-Preservation Protocol (solo operator + agent)

## Prime directive
- I (the human) must understand every change before it is committed. Your job is
  not just to make tests pass — it is to keep me in genuine understanding of this
  system. Optimize for my comprehension, not for merge speed.
- Never generate code I have not been walked through. If I have not seen an
  explanation of a change, treat it as not-yet-approved.

## Change size & scope (keep diffs auditable)
- Default to the smallest working change. Prefer small, reversible diffs.
- Hard stop: if a change will exceed ~150 changed lines OR touch >5 files OR
  span >2 modules, STOP and present a plan for my approval before writing code.
- Do not touch unrelated code. No opportunistic "while I was here" refactors,
  renames, or cleanups unless I explicitly asked. Surface them as suggestions.
- One concern per change. If you discover a second concern mid-task, finish the
  first, then surface the second separately.

## Explain-as-you-go (plain language, before I read code)
- Before presenting any non-trivial diff, give me a PLAIN-LANGUAGE summary:
  what changed, why, and what behavior is now different. Max ~8 bullet points.
- Explicitly FLAG THE LOAD-BEARING PARTS: name the specific lines/functions
  that, if changed, would break correctness — and say what would break.
- State the SINGLE ASSUMPTION most likely to be wrong in this change, and why
  you might be wrong about it.

## Surface hidden complexity (no silent growth)
- STOP AND SURFACE before doing any of the following, and wait for my approval:
  - introducing a NEW ABSTRACTION (base class, interface, layer, framework,
    indirection, generic/meta-programming, new design pattern);
  - adding a NEW DEPENDENCY or upgrading a major version;
  - touching a SECURITY BOUNDARY (auth, authz, crypto, input validation,
    secrets, serialization, file/network/permission handling, SQL);
  - changing PUBLIC INTERFACES, data schemas, or migrations;
  - introducing CONCURRENCY, caching, retries, or non-determinism;
  - using an API/library I have not used before in this repo.
- For each of the above, present the alternatives you considered and why you
  chose this one. Do not present only the chosen path.

## Tests are necessary, not sufficient
- When a change updates many existing tests to match new behavior, STOP and tell
  me: which assertions changed, whether the behavior change was intended, and
  what behavior is NOT covered by any test. Never silently rewrite tests to green.
- Never delete or weaken a test to make a build pass. Surface it instead.

## Uncertainty & honesty
- Distinguish "I verified this" from "I believe this." Flag uncertainty before
  acting, not after. If requirements are ambiguous, ask one clarifying question
  rather than guessing confidently.
- If you are unsure, propose a short plan or open a draft; do not push a large
  speculative change.

## Explanation artifacts (intent-debt control)
- For any change that adds a non-obvious decision, append 2–4 lines to
  DECISIONS.md: the decision, the rejected alternative, and the reason.
- When asked, produce a LINEAR WALKTHROUGH: a file-by-file, top-to-bottom
  explanation document of the change or module, written for me to learn from.

## Gate protocol (you enforce the pause)
- Before committing a change classified GATED (see thresholds I maintain), you
  MUST pause and present the relevant forced-engagement gate questions, and WAIT.
- Do not answer the gate questions for me. Ask them, then stop. After I respond
  in my own words, THEN reveal your explanation and tell me where I was wrong.
- Never proceed past a gate on my silence, a bare "ok", or "lgtm". Require a
  substantive answer to the comprehension question first.
```

### Part C — TRACK 2: Forced-engagement human approval gates

**Design law of these gates (the novel core):** every gate makes you *produce* before the agent *reveals*. A plain "Approve? Y/N" is trivially rubber-stamped; a prompt that requires you to predict, explain, or name something specific cannot be answered without engaging. The agent asks, you answer in your own words, *then* the agent shows its account and corrects you. This sequence is deliberate: it exploits the generation effect (Slamecka & Graf), defeats the illusion of explanatory depth (your confidence collapses the moment you try to explain — Rozenblit & Keil), and acts as a cognitive forcing function that disrupts heuristic acceptance (Croskerry; Buçinca et al.). It also imposes accountability — you must construct a justification — which Skitka, Mosier & Burdick showed lowers automation bias.

**Universal gate preamble (DO-CONFIRM style, keep to one screen — Gawande's 5–9 item, single-pause-point rule):**

```
=== COMPREHENSION GATE ===
Answer in your own words BEFORE I show my explanation. Do not scroll to the diff.
1. In one or two sentences, what does this change do and why?
2. Which line/function here is load-bearing — what breaks if it changes?
3. What is the ONE assumption here most likely to be wrong?
[You answer. Then I reveal my account and tell you where you were off.]
```

#### Gate library by change type (exact wording)

**G1 — New abstraction**
```
Before I show the new abstraction:
- What problem does this abstraction solve that the previous code could not?
- Name one concrete future change this makes EASIER and one it makes HARDER.
- If you had to delete this abstraction in 6 months, what would you have to know?
Type your answers. Then I'll show the code and the alternative I rejected.
```
*Mechanism: forces articulation of the cost/benefit the IOED hides; generation before reveal.*

**G2 — New dependency**
```
Before adding this dependency:
- What exactly are we getting from it that we can't easily write ourselves?
- Predict its transitive dependency count and last-release date (guess a number).
- What is our exit plan if it is abandoned or has a CVE next year?
Answer first. Then I'll show the real numbers and where your guess was off.
```
*Mechanism: prediction-before-reveal (generation effect); makes the supply-chain cost salient instead of invisible.*

**G3 — Security boundary**
```
STOP — security-relevant change. Answer before I reveal anything:
- In your own words, what is the trust boundary here and who/what is untrusted?
- Write the one input that, if an attacker controlled it, would do the most damage.
- Predict: does this change widen, narrow, or keep the attack surface? Why?
Then I'll walk the data flow line by line and show what you missed.
```
*Mechanism: accountability + self-explanation on the highest-stakes class; prediction commits you before the reveal.*

**G4 — Complex algorithm**
```
Before I explain the algorithm:
- Predict the output for this specific input: [agent supplies a concrete case].
- What is the time/space complexity, and what input makes it blow up?
- Which single step is the "trick" that makes it correct?
Write your prediction. Then we run it and compare to what you said.
```
*Mechanism: predict-the-output (commitment + retrieval practice); running it after is feedback that strengthens the memory trace.*

**G5 — Large or wide diff**
```
This diff is large/wide. Before reviewing:
- Without looking, list the files you EXPECT changed and why each had to change.
- Which one file is the heart of this change? Which are just mechanical follow-on?
- Name one file you'd be surprised to see changed here.
Then compare your list to the actual file list — investigate any surprise.
```
*Mechanism: retrieval before recognition; a surprised expectation is a high-signal pointer to scope creep.*

**G6 — Unfamiliar API**
```
You haven't used this API in this repo before. Before I show usage:
- What does this API call DO, in one sentence, and what can it fail on?
- What does it return on the empty/error case, and do we handle that?
- Guess one footgun in this API. Then I'll tell you the real ones.
```
*Mechanism: converts a passive copy-paste into active inquiry — the exact behavior Anthropic's high-scoring group used.*

**G7 — Architectural change**
```
Architectural change. Before I present the design:
- State the current architecture in 3 boxes-and-arrows in your own words.
- What invariant does this change preserve, and what invariant does it break?
- If this is wrong, where will the pain show up first, and in how many months?
Answer, then I'll show the design and the two alternatives I discarded.
```
*Mechanism: explain-back of the current state forces you to confront the IOED before evaluating the new state.*

**G8 — Test-mass rewrite (the "all green" trap)**
```
This change rewrote N existing tests. Before I explain:
- Which behavior changed such that these tests HAD to change?
- Pick one rewritten assertion: was the old behavior wrong, or just different?
- What behavior here is now covered by NO test at all?
Then I'll show the assertion diffs and the coverage gap.
```
*Mechanism: directly counters Osmani's named failure mode — when an AI "updates hundreds of test cases to match the new behavior… Tests cannot answer [whether they were necessary]. Only comprehension can."*

### Part D — Decision rules and thresholds (when a gate fires)

Gates fire on **comprehension risk**, not size alone. Maintain this classifier in a `GATES.md` or in your head.

**PROCEED autonomously (no gate)** when ALL hold:
- ≤ ~30 changed lines, ≤ 2 files, single module;
- no new abstraction, dependency, or public-interface change;
- touches only code you have walked through before;
- not on a security/persistence/concurrency boundary;
- a deterministic check (tests/types/lint) fully covers the behavior.

**GATE (pause + forced-engagement question)** when ANY hold:
- new abstraction, dependency, or major-version bump → G1/G2;
- security boundary, auth, crypto, input handling, migration → G3;
- non-trivial algorithm, concurrency, caching, retries, non-determinism → G4;
- diff > ~150 lines OR > 5 files OR > 2 modules → G5;
- first use of an API/library in this repo → G6;
- architecture, module boundaries, or data schema → G7;
- a change that rewrites > ~5 existing tests → G8;
- *your own felt signal*: "I'm not sure I could explain this." That feeling is itself a gate trigger — it is the IOED collapsing in real time.

**Escalation rule:** two or more GATE conditions on one change → require a full linear walkthrough, not just the gate questions.

### Part E — Standing personal practices (as rules)

1. **Only ship code you understand (Hashimoto's rule).** Ghostty's contributor guidance: "Never commit code you cannot explain." If you can't explain it, invoke the next rule.
2. **Learn-or-discard (Hashimoto).** If the agent produced something you don't understand: either study it until you do, or discard it and reimplement it yourself. No third option ("ship it anyway").
3. **Inline learning, never delegate the understanding (Karpathy).** Take the learning opportunity at the moment of review — Karpathy's emphasis is "being slow, defensive, careful, paranoid, and on always taking the inline learning opportunity, not delegating." Treat AI-generated code "like code from a mentor — review it to learn, not just to ship."
4. **Linear walkthroughs (Willison).** For any vibe-coded or forgotten module, have the agent produce a top-to-bottom, file-by-file walkthrough document and read it. Willison used exactly this to learn SwiftUI from a slideshow app he had "prompted the whole thing into existence… without paying any attention to the code."
5. **Build to learn (Hashimoto / Thorsten Ball).** When confidence is low on an unfamiliar area, do the task manually once (or build a toy version) so the understanding is earned, then let the agent take it over. Hashimoto literally "did the work twice" — manually, then fighting an agent to reproduce it — to build expertise.
6. **The cleanup step is mandatory (Hashimoto).** Always do a human cleanup pass on agent output: "to cleanup effectively you have to have a pretty good understanding of the code, so this forces me to not blindly accept AI-written code."
7. **Quality bar scales with lifespan (Hashimoto).** Throwaway/short-lived code (his family wedding website: "Did it render right in three browsers? Ship it. It's only online for 2 months"): skip the gates. Long-lived/core code (Ghostty): review every line, every gate fires.
8. **Conceptual-inquiry mode by default (Anthropic RCT).** Ask the agent conceptual/why questions, not just "make it work" — the behavior that correlated with 65%+ comprehension versus under 40% for delegators.
9. **Maintain DECISIONS.md (intent debt — Storey).** Capture the rejected alternative and the reason, so the *why* doesn't evaporate.
10. **Keep the agent on a leash (Karpathy).** Small, concrete, verifiable steps; you remain the bottleneck on purpose. "I'm still the bottleneck."

### Part F — Avoiding gate fatigue and habituation

The meta-risk: too many gates train you to auto-approve, recreating automation complacency. Countermeasures:

1. **Calibrate frequency to risk (Part D).** If gates fire on trivial changes, raise the thresholds. A gate that fires on everything is a gate that fires on nothing.
2. **Rotate the wording (anti-automaticity).** Never let the gate become a fixed script you pattern-match. Cycle among: predict-the-output, explain-back, name-the-load-bearing-line, name-the-wrong-assumption, list-expected-files, find-the-footgun. Parasuraman & Manzey found complacency "is sharply reduced when automation reliability varies over time instead of remaining constant, but is not reduced by experience and practice" — variability, not repetition, is what keeps you engaged.
3. **Keep gates short (Gawande: 5–9 items, one pause point).** A bloated gate gets skimmed. Three sharp questions beat ten dull ones; Boorman's aviation rule of thumb is that after ~60 seconds people start skipping steps.
4. **Answer-before-reveal is non-negotiable.** The moment you let the agent show its explanation first, the gate degrades into a reading task you'll skim. The friction (you typing first) is the point — it is the microboundary (Cox et al.) that shifts you from System 1 to System 2. Buçinca et al. confirm you will *prefer* the easier, non-forcing designs precisely because they let you over-rely.
5. **Make the gate generative, not recognitional.** "Do you agree? Y/N" is recognition (rubber-stampable). "Write the input that breaks this" is generation (not fakeable). This is the generation-effect principle applied to interface design.
6. **Use a fresh-context second-opinion review as a supplement, never a substitute.** Having the agent re-review its own diff in a clean context catches some issues, but its green review never replaces your gate answer.
7. **Honor the "I can't explain this" signal.** When it fires, that is not friction to push past — it is the debt forming in real time. Stop and walk through it.

### Part G — Anti-patterns and the rules that counter them

| Anti-pattern | What it looks like | Countering rule(s) |
|---|---|---|
| "Just make the tests pass" | Agent rewrites tests to green; behavior drift unreviewed | G8; "tests necessary not sufficient" directive |
| Spec-and-trust | Review the spec, never the code | Osmani: a spec detailed enough to fully describe a program "is more or less the program"; still gate the diff |
| Accept-all / "I don't read the diffs anymore" | Karpathy's original vibe-coding mode applied to durable code | Rules 1, 7; leash directive |
| Silent complexity growth | New abstraction/dependency slipped in unannounced | "Stop and surface" directives; G1/G2 |
| Rubber-stamp approval | "lgtm" on unread diffs | Forced-engagement gates; never proceed on bare "ok" |
| Gate habituation | Auto-answering a fixed gate script | Part F rotation + risk-calibrated frequency |
| Fluency illusion | Clean, well-formatted code feels understood | IOED: explain-back before reveal |
| Bus-factor-zero module | Only the agent "knows" a subsystem | Linear walkthroughs; learn-or-discard |
| Scope creep | One-line fix touches 3 unrelated files | "Do not touch unrelated code"; G5 |

## Recommendations

**Stage 1 — Adopt this week.** Paste the Part B directive block into `AGENTS.md`, symlink `CLAUDE.md`. Create `DECISIONS.md`. Adopt the universal gate preamble (Part C) and the three gates you'll hit most: G2 (dependency), G3 (security), G8 (test rewrite). Adopt personal rules 1, 2, 6 (only-ship-what-you-understand, learn-or-discard, mandatory cleanup). Benchmark that flips you forward: if you can run a full day without ever hitting "I can't explain this," the protocol is working.

**Stage 2 — Within a month.** Add the full gate library (G1–G8) and the Part D classifier. Start writing linear walkthroughs for any module you can't currently explain. Begin rotating gate wording (Part F) so no single phrasing becomes automatic.

**Stage 3 — Ongoing calibration.** Watch two signals and adjust:
- *Gate-fatigue signal:* if you catch yourself answering gates reflexively, or resenting them on trivial changes → raise thresholds (gate less, on riskier changes only) and rotate wording. Remember Buçinca et al.: you will dislike the gates that help most, so dislike alone is not a reason to drop them — reflexive answering is.
- *Debt signal:* if you hit a change you "can't explain," or a bug surfaces in code you approved but don't understand → lower thresholds in that area, add a walkthrough, and treat it as learn-or-discard.

**Thresholds that change the regime:** Loosen toward more autonomy when code is short-lived/throwaway (Hashimoto's wedding-site standard). Tighten toward every-line review and every-gate-fires when code is long-lived, load-bearing, security-relevant, or headed for a regulated/high-stakes domain — Osmani warns the regulatory reckoning is closer than it looks: "the AI wrote it and we didn't fully review it" will not survive a post-incident report when lives or significant assets are at stake.

## Caveats
- **The empirical base is young and partly indirect.** The Anthropic RCT (n=52, mostly junior, immediate quiz) explicitly does not resolve long-term effects, and its authors note agentic tools likely have *stronger* effects than their non-agentic setup. The MIT Media Lab "Your Brain on ChatGPT" study (Kosmyna et al., 2025; n=54, 18 in the crossover session; arXiv 2506.08872) — which coined "cognitive debt" and found LLM users showed the weakest EEG connectivity and that 83% "were unable to quote from the essays they had just written" — is an essay-writing study, not coding, and is a preprint. Treat it as suggestive analogy, not proof for code.
- **Cognitive forcing functions reduce but do not eliminate overreliance, and carry a real usability trade-off.** In Buçinca et al. (2021), the designs that most reduced overreliance were the ones people liked and trusted *least*, and the benefits skewed toward high-need-for-cognition individuals. Expect the gates to feel annoying; that feeling is partly the mechanism working and partly a genuine adoption risk — which is why Part F's calibration matters.
- **Some sources are practitioner blog posts, podcasts, and secondary write-ups**, not peer-reviewed (Osmani, Willison, Hashimoto interviews, AGENTS.md/CLAUDE.md guides, Karpathy talk coverage). They are field-tested practitioner opinion, weighted accordingly. Storey's Triple Debt paper is a recent preprint also appearing in ACM Queue.
- **This runbook is preventive only.** By design it contains no measurement/scoring/audit machinery — the gates prevent debt in real time rather than measuring it after the fact. If you later want detection, that is a separate instrument and out of scope here.
- **A few quantified secondary figures should be treated cautiously** — e.g., the "under 40% vs 65%+" split comes from Osmani's and Anthropic's summary of the interaction-pattern clusters (small per-cluster n), and the Chi et al. self-explanation counts come from secondary summaries. The headline 50% vs 67% (Cohen's d=0.738, p=0.01) is from the Anthropic primary source, and the Slamecka & Graf, Rozenblit & Keil, Buçinca et al., and Skitka et al. quotes are verified against their primary sources.
