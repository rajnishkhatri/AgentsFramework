---
type: research
title: ACT / PreACT English — Official Weights & Bucket Coverage Research
description: Enhanced ACT (2025+) / PreACT (2026+) English blueprint — per-bucket weights and standard coverage that drive item-bank quotas and share-of-test percentages.
tags: [research, eng-coach, act-english, taxonomy]
---

# ACT / PreACT English — Official Weights & Bucket Coverage Research

**Date:** 2026-07-08  
**Purpose:** Validate the project's 6 skill-bucket taxonomy and weightings (`27 / 21 / 19 / 19 / 8 / 6`) against official ACT and PreACT specifications.  
**Companion docs:** `PreACT-English-Coach-Spec.md` §3, `eng-coach-v2.md` §3.1, `bank_review-analysis.md`

---

## Executive summary

1. **ACT does not publish the project's 6-bucket weights.** The official exam reports **3 reporting categories**, not 6. The weights in our spec (`Rhetoric 27%`, etc.) are a **pedagogical flattening**, not an ACT score-reporting taxonomy.

2. **Those weights are outdated for the Enhanced ACT (2025–2026).** The biggest official shift is that **Conventions of Standard English dropped from ~52% → ~40%**, while **Production of Writing rose from ~30% → ~40%**. Our spec still treats grammar/punctuation as ~60% combined.

3. **The 6 buckets do cover the full ACT English skill space** — but with **mapping overlaps** and **one misplacement**: modifier placement is officially under *Sentence Structure and Formation*, not *Organization*.

4. **Recommended action:** Adopt a **two-tier taxonomy** — 3 official reporting categories for score alignment + 6 drill buckets for coaching UI — with weights derived from the target exam form (Enhanced ACT vs PreACT Secure vs legacy).

---

## 1. Official ACT reporting structure

ACT English is a passage-based editing test. Students act as writers revising short essays. Four scores are reported:

- 1 overall English score
- 3 **reporting category** subscores

Source: [ACT — Description of English Test](https://www.act.org/content/act/en/products-and-services/the-act/test-preparation/description-of-english-test.html)

### 1.1 The three reporting categories

| Reporting category | What it measures | Sub-elements |
|---|---|---|
| **Production of Writing** | Purpose, focus, development, organization | Topic Development; Organization, Unity, and Cohesion |
| **Knowledge of Language** | Effective word use | Precision, concision, style, tone |
| **Conventions of Standard English** | Grammar, usage, mechanics | Sentence Structure and Formation; Punctuation; Usage |

ACT explicitly describes **six elements** nested inside the three reporting categories (confirmed in PreACT technical bulletins). **ACT does not publish percentage weights at the element level** — only at the 3-category level.

---

## 2. Official percentage weights by exam form

### 2.1 Enhanced ACT (current blueprint, 50 questions / 35 min)

Effective for national/enhanced administrations from **September 2025** onward.  
40 operational (scored) items + 10 embedded field-test items.

| Reporting category | Items | % of section |
|---|---:|---:|
| Production of Writing | 15–17 | **38–43%** |
| Knowledge of Language | 7–9 | **18–23%** |
| Conventions of Standard English | 15–17 | **38–43%** |

Sources:
- [ACT Reporting Category Tables Comparison (PDF)](https://www.act.org/content/dam/act/unsecured/documents/ACT-Reporting-Category-Tables-Comparison.pdf)
- [Enhanced ACT FAQs](https://www.act.org/content/act/en/products-and-services/the-act-educator/the-act-test/enhancements-k12/faqs.html)
- [Preparing for the ACT 2025–2026 (PDF)](https://www.act.org/content/dam/act/unsecured/documents/Preparing-for-the-ACT-e.pdf)

### 2.2 Legacy ACT (75 questions / 45 min) — for reference

| Reporting category | Items | % of section |
|---|---:|---:|
| Production of Writing | 22–24 | **29–32%** |
| Knowledge of Language | 11–13 | **15–17%** |
| Conventions of Standard English | 39–41 | **52–55%** |

The legacy test was **grammar-heavy** (> half the section). The Enhanced ACT deliberately rebalanced toward rhetoric and passage-level editing.

### 2.3 PreACT Secure (current, 36 scored items)

Relevant because this product targets **PreACT** preparation.

| Reporting category | Items | % of test |
|---|---:|---:|
| Production of Writing | 10–12 | **28–33%** |
| Knowledge of Language | 5–7 | **14–19%** |
| Conventions of Standard English | 18–20 | **50–56%** |

Source: [Wisconsin PreACT Secure Technical Report 2022–23](https://dpi.wi.gov/media/26424/download?inline=) (ACT-published technical specs)

PreACT Secure is **closer to legacy ACT** than Enhanced ACT — conventions still dominate (~53% midpoint).

### 2.4 Enhanced PreACT (launching Spring 2026)

Aligned to Enhanced ACT blueprint.

**PreACT / PreACT Secure (36 operational items):**

| Reporting category | Items | % of test |
|---|---:|---:|
| Production of Writing | 12–14 | **33–39%** |
| Knowledge of Language | 5–7 | **14–19%** |
| Conventions of Standard English | 15–17 | **42–47%** |

**PreACT 9 Secure (33 operational items):**

| Reporting category | Items | % of test |
|---|---:|---:|
| Production of Writing | 11–13 | **33–39% |
| Knowledge of Language | 4–6 | **12–18%** |
| Conventions of Standard English | 14–16 | **42–48%** |

Source: [PreACT FAQs — Enhanced Blueprint](https://www.act.org/content/act/en/products-and-services/preact/faqs.html)

### 2.5 PreACT 8/9 (40 items, 8 unscored)

| Reporting category | Items | % of test |
|---|---:|---:|
| Production of Writing | 9–11 | **28–34%** |
| Knowledge of Language | 4–6 | **13–19%** |
| Conventions of Standard English | 16–18 | **50–56%** |

Source: [PreACT 8/9 Technical Bulletin 2025 (PDF)](https://www.act.org/content/dam/act/unsecured/documents/PreACT-8-9-Technical-Bulletin-2025.pdf)

---

## 3. Visual: how weights shifted

```
Legacy ACT English (75Q)          Enhanced ACT English (50Q)
┌─────────────────────────┐       ┌─────────────────────────┐
│ Conventions    52-55%   │       │ Production     38-43%   │
│ ████████████████████████│       │ ████████████████████    │
│ Production     29-32%   │       │ Conventions    38-43%   │
│ ████████████            │       │ ████████████████████    │
│ Knowledge      15-17%   │       │ Knowledge      18-23%   │
│ ██████                  │       │ ████████                │
└─────────────────────────┘       └─────────────────────────┘
   Grammar-dominated                 Rhetoric ≈ Grammar
```

**Key takeaway for this app:** If the student is preparing for the **Enhanced ACT / Enhanced PreACT (2026+)**, overweighting punctuation and usage (as our current bank and spec do) mirrors the **legacy** exam, not the **current** one.

---

## 4. Project's 6 buckets vs official structure

### 4.1 Current project taxonomy

From `PreACT-English-Coach-Spec.md` §3 and `eng-coach-v2.md` §3.1:

| Project bucket | Project weight | Spec says it tests |
|---|---:|---|
| Rhetoric | 27% | add/delete sentences, transitions, tone, essay purpose |
| Usage | 21% | verb tense/form, pronoun agreement, parallelism, adj vs adv |
| Punctuation | 19% | commas, colons, semicolons |
| Organization | 19% | modifier placement, transitions, idiom, word choice |
| Sentence Structure | 8% | fragments, comma splices, boundaries |
| Conciseness | 6% | redundancy |

### 4.2 Official mapping

| Project bucket | Maps to official… | Notes |
|---|---|---|
| **Rhetoric** | Production of Writing → **Topic Development** | Add/delete, relevance, purpose, goal-oriented word choice. **Does not include transitions** (those are Organization). |
| **Organization** | Production of Writing → **Organization, Unity, and Cohesion** | Transitions, logical order, intro/conclusion, sentence placement. |
| **Conciseness** | **Knowledge of Language** (partial) | Redundancy, precision, concision. KoL also covers style/tone, which our **Rhetoric** bucket partially absorbs. |
| **Usage** | Conventions → **Usage** | Grammar, agreement, tense, pronouns, idioms, parallelism. |
| **Punctuation** | Conventions → **Punctuation** | Commas, apostrophes, colons, semicolons, dashes. |
| **Sentence Structure** | Conventions → **Sentence Structure and Formation** | Fragments, run-ons, comma splices, clauses, **modifier placement**. |

### 4.3 Mapping diagram

```
OFFICIAL (3 categories, 6 elements)     PROJECT (6 drill buckets)
─────────────────────────────────────     ───────────────────────────
Production of Writing (38-43%)          
  ├─ Topic Development          ──────►  Rhetoric
  └─ Organization/Unity/Cohesion ─────►  Organization

Knowledge of Language (18-23%)            
  └─ Precision, concision, style, tone   
       ├─ concision/redundancy   ──────►  Conciseness
       └─ style/tone/register    ──────►  Rhetoric (partial overlap)

Conventions of Standard English (38-43%)
  ├─ Sentence Structure/Formation ─────►  Sentence Structure
  ├─ Punctuation                  ─────►  Punctuation
  └─ Usage                        ─────►  Usage
```

### 4.4 Misalignments in the project taxonomy

| Issue | Detail |
|---|---|
| **Weights are not official** | `27/21/19/19/8/6` cannot be traced to any ACT document. Rhetoric at 27% ≈ the entire legacy *Production of Writing* category, not just Topic Development. |
| **Rhetoric + Organization = 46%** | Exceeds even Enhanced PoW (38–43%). Double-counts passage-level skills. |
| **Conciseness at 6%** | Understates *Knowledge of Language* (18–23% on Enhanced ACT). Style/tone items bleed into Rhetoric but aren't counted there. |
| **Conventions at 48%** (Usage+Punct+Struct) | Close to Enhanced CSE (38–43%) but **Sentence Structure at 8%** is likely too low; third-party analysis of practice tests puts clauses/fragments at ~5 items (~12%) per Enhanced form. |
| **Modifier placement** | Spec places under Organization; ACT places under **Sentence Structure and Formation**. |
| **Transitions** | Spec lists under both Rhetoric and Organization; ACT places under **Organization, Unity, and Cohesion** only. |

---

## 5. Do the 6 buckets cover the full ACT English exam?

### 5.1 Verdict: **Yes, with caveats**

Every skill ACT lists for English is reachable through the 6 buckets, but coverage is **uneven** and some ACT question types are **missing from the item bank** (see `bank_review-analysis.md`).

### 5.2 Coverage matrix

| ACT skill / question type | Official home | Project bucket | In `bank_review.json`? |
|---|---|---|---|
| Add/delete sentences | Topic Development | Rhetoric | ❌ Missing |
| Relevance / purpose of a sentence | Topic Development | Rhetoric | ⚠️ Partial (2 goal-word items) |
| Essay intro/conclusion | Organization | Organization | ❌ Missing |
| Transition words/phrases | Organization | Organization | ✅ std 1 (8 items) |
| Sentence order / logical sequence | Organization | Organization | ⚠️ Partial |
| Introductory/concluding sentences | Organization | Organization | ❌ Missing |
| Precision in word choice | Knowledge of Language | Rhetoric / Conciseness | ⚠️ Partial |
| Concision / redundancy | Knowledge of Language | Conciseness | ✅ std 5, 8, 9 |
| Style and tone consistency | Knowledge of Language | Rhetoric | ⚠️ Partial (std 4, 2 items) |
| Fragments and run-ons | Sentence Structure | Sentence Structure | ✅ std 10, 15 |
| Comma splices | Sentence Structure | Sentence Structure | ✅ std 15, 29 |
| Modifier placement | Sentence Structure | Organization *(misplaced)* | ❌ Missing |
| Clause relationships | Sentence Structure | Sentence Structure | ⚠️ Partial |
| Comma rules (series, FANBOYS, etc.) | Punctuation | Punctuation | ✅ std 14 (9 items) |
| Apostrophes / possessives | Punctuation | Punctuation | ✅ std 24 |
| Semicolons / colons | Punctuation | Punctuation | ⚠️ Semicolons yes; **colons missing** |
| That/which clauses | Punctuation | Punctuation | ✅ std 31 |
| Subject-verb agreement | Usage | Usage (Grammar) | ✅ std 17 |
| Verb tense / form | Usage | Usage (Grammar) | ✅ std 11, 12, 27 |
| Pronoun agreement / clarity | Usage | Usage (Grammar) | ✅ std 18, 28 |
| Parallelism | Usage | Usage (Grammar) | ✅ std 26 |
| Adjective vs adverb | Usage | Usage (Grammar) | ✅ std 13, 16 |
| Who/whom, idioms | Usage | Usage (Grammar) | ✅ std 22, 23 |
| Comparisons (that of/those of) | Usage / Sentence Structure | Sentence Structure | ✅ std 32 |

### 5.3 Critical content gaps (exam requirements not in bank)

| Gap | ACT weight impact | Priority |
|---|---|---|
| Add/delete sentences | High — core Topic Development skill | 🔴 Critical |
| Essay purpose / intro / conclusion | High — Organization + Topic Development | 🔴 Critical |
| Modifier placement | Medium — Sentence Structure element | 🟡 High |
| Colons | Low-medium — Punctuation element | 🟡 High |
| Style/tone (Knowledge of Language) | Medium — 18–23% of Enhanced ACT | 🟡 High |
| Logical sentence ordering | Medium — Organization element | 🟡 High |

---

## 6. Corrected weight recommendations

ACT does not publish 6-element percentages. The tables below **estimate** drill-bucket weights by splitting each official category proportionally. Use the tier that matches the student's target exam.

### 6.1 Enhanced ACT / Enhanced PreACT 2026+ (recommended default)

Split PoW 50/50 into Rhetoric + Organization. Split CSE into thirds. KoL → Conciseness (absorbing style/tone into Rhetoric for coaching purposes).

| Drill bucket | Official source | Recommended weight | Midpoint items (ACT 40Q) |
|---|---|---:|---:|
| Rhetoric | ½ × Production of Writing | **19–22%** | ~8 |
| Organization | ½ × Production of Writing | **19–22%** | ~8 |
| Conciseness | Knowledge of Language (concision slice) | **9–12%** | ~4 |
| Sentence Structure | ⅓ × Conventions | **13–14%** | ~5 |
| Punctuation | ⅓ × Conventions | **13–14%** | ~5 |
| Usage | ⅓ × Conventions | **13–14%** | ~5 |

**PoW + Org combined: 38–43%** (not 46% as in current spec)

### 6.2 PreACT Secure (current, pre-2026)

| Drill bucket | Recommended weight | Midpoint items (36Q) |
|---|---:|---:|
| Rhetoric | 14–17% | ~5 |
| Organization | 14–17% | ~5 |
| Conciseness | 7–10% | ~3 |
| Sentence Structure | 17–19% | ~6 |
| Punctuation | 17–19% | ~6 |
| Usage | 17–19% | ~6 |

Conventions still ~53% combined — grammar drills remain high-value for current PreACT Secure.

### 6.3 Comparison: current spec vs corrected (Enhanced ACT)

| Bucket | Current spec | Enhanced ACT estimate | Delta |
|---|---:|---:|---:|
| Rhetoric | 27% | 19–22% | −5 to −8pp |
| Organization | 19% | 19–22% | 0 to +3pp |
| Conciseness | 6% | 9–12% | +3 to +6pp |
| Sentence Structure | 8% | 13–14% | +5 to +6pp |
| Punctuation | 19% | 13–14% | −5 to −6pp |
| Usage | 21% | 13–14% | −7 to −8pp |

The current spec **overweights Rhetoric, Usage, and Punctuation** and **underweights Conciseness and Sentence Structure** relative to Enhanced ACT.

---

## 7. Implications for the app

### 7.1 Taxonomy design

Keep the **6 drill buckets** for coaching UI (good granularity for mastery cards, color coding, and session focus). Add a **3-category layer** for score prediction and reporting alignment:

```ts
type ReportingCategory = 'productionOfWriting' | 'knowledgeOfLanguage' | 'conventionsOfStandardEnglish';

const bucketToReporting: Record<SkillKey, ReportingCategory> = {
  rhetoric:       'productionOfWriting',
  organization:   'productionOfWriting',
  conciseness:    'knowledgeOfLanguage',
  usage:          'conventionsOfStandardEnglish',
  punctuation:    'conventionsOfStandardEnglish',
  structure:      'conventionsOfStandardEnglish',
};
```

### 7.2 Sampler weights

Replace hardcoded `bmeta[].share` values with a **target-exam profile**:

| Profile | When to use | PoW / KoL / CSE |
|---|---|---|
| `enhanced-act` | ACT Sept 2025+, Enhanced PreACT 2026+ | 40 / 20 / 40 |
| `preact-secure` | Current PreACT Secure (pre-Spring 2026) | 30 / 17 / 53 |
| `preact-8-9` | PreACT 8/9 | 31 / 16 / 53 |

The outer-loop sequencer should sample by **reporting-category weights first**, then distribute within categories across drill buckets.

### 7.3 Spec corrections needed

| Current spec claim | Correction |
|---|---|
| "Rhetoric ~27%, biggest lever" | PoW (Rhetoric + Organization) is ~40% on Enhanced ACT; Rhetoric alone is ~20%. Biggest lever is now **PoW + KoL combined (~60%)**, not grammar. |
| "Punctuation ~19%" | Punctuation is ~13% on Enhanced ACT (~5 items). Still high-impact for weak students, but not 1/5 of the test. |
| "Organization tests modifier placement" | Move modifier placement to Sentence Structure per ACT. Organization = transitions, order, intro/conclusion. |
| "Transitions" listed under Rhetoric | Remove from Rhetoric; keep under Organization only. |

### 7.4 Bank expansion priorities (revised with official weights)

Given Enhanced ACT is the forward-looking target:

| Priority | Content | Est. items needed | Rationale |
|---|---:|---|
| 🔴 P1 | Add/delete sentences, essay purpose | +15–20 | Topic Development — half of the now-largest category |
| 🔴 P1 | Intro/conclusion, sentence ordering | +8–10 | Organization — other half of PoW |
| 🟡 P2 | Style/tone (Knowledge of Language) | +6–8 | 18–23% of test; currently almost absent |
| 🟡 P2 | Modifier placement | +4–6 | Officially Sentence Structure; misbucketed in spec |
| 🟢 P3 | Colons, comparisons | +3–5 | Minor punctuation/usage gaps |
| ⚪ Hold | Grammar, punctuation deep drills | keep | Still valuable for Conventions (~40%) and weak-area remediation |

---

## 8. Sources

| Source | URL |
|---|---|
| ACT — Description of English Test | https://www.act.org/content/act/en/products-and-services/the-act/test-preparation/description-of-english-test.html |
| ACT — Exam Sections & Structure | https://www.act.org/content/act/en/products-and-services/the-act/test-preparation/act-exam-sections-and-structure.html |
| ACT — Enhanced ACT FAQs | https://www.act.org/content/act/en/products-and-services/the-act-educator/the-act-test/enhancements-k12/faqs.html |
| ACT — Legacy vs Enhanced Comparison (PDF) | https://www.act.org/content/dam/act/unsecured/documents/ACT-Reporting-Category-Tables-Comparison.pdf |
| ACT — Preparing for the ACT 2025–2026 (PDF) | https://www.act.org/content/dam/act/unsecured/documents/Preparing-for-the-ACT-e.pdf |
| ACT — PreACT FAQs (Enhanced Blueprint) | https://www.act.org/content/act/en/products-and-services/preact/faqs.html |
| ACT — PreACT Enhancements | https://www.act.org/content/act/en/products-and-services/preact/enhancements.html |
| ACT — PreACT 8/9 Technical Bulletin 2025 (PDF) | https://www.act.org/content/dam/act/unsecured/documents/PreACT-8-9-Technical-Bulletin-2025.pdf |
| Wisconsin — PreACT Secure Technical Report 2022–23 | https://dpi.wi.gov/media/26424/download?inline= |
| Third-party Enhanced ACT practice test analysis | https://www.piqosity.com/2026/03/05/whats-tested-on-the-english-section-of-the-act/ |

---

## 9. Bottom line

| Question | Answer |
|---|---|
| Are the project's 6 buckets the official ACT taxonomy? | **No.** ACT uses 3 reporting categories with 6 nested elements. |
| Are the project's weights (27/21/19/19/8/6) correct? | **No.** They appear to be an internal/prep-industry estimate aligned to the **legacy** grammar-heavy ACT, not the **Enhanced ACT (2025+)** or current PreACT specs. |
| Do the 6 buckets cover all ACT English skills? | **Yes**, but with overlap, one misplacement (modifier placement), and significant **content gaps** in the item bank (especially add/delete, essay purpose, style/tone). |
| What should we use for weights? | **Enhanced ACT profile** (40/20/40 at category level) for forward-looking prep; split into 6 drill buckets as estimated in §6.1. Keep a `preact-secure` profile for students on the current PreACT form. |
