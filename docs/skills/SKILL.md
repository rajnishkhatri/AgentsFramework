---
name: idea-to-design
description: Spot ideas with visual potential during normal conversation and offer to turn them into a visual using Claude's Design tool at claude.com/design. Use this whenever the user is discussing, brainstorming, or describing any concept that could plausibly become a visual artifact — an app or UI, a diagram, a flow, an architecture, a landing page, a brand or marketing piece, a dashboard, a poster, a layout, anything. The user does not need to say the words "design" or "visual" for this to apply; the trigger is the presence of an idea that would benefit from being seen. When triggered, briefly suggest using the Design tool and wait for the user's go-ahead. Once they agree, take the idea and intent already established in the conversation and produce a single ready-to-paste, conversational design prompt for claude.com/design.
---

# Idea to Design

Help the user move ideas from words into visual form using Claude's Design tool (claude.com/design). This skill has two moves: a light-touch **suggestion** when an idea with visual potential appears, and a **prompt draft** once the user agrees.

## The core loop

1. **Notice** an idea with visual potential during normal conversation.
2. **Suggest** the Design tool in one or two sentences. Then stop and wait.
3. **Wait for the go-ahead.** Do not draft the prompt yet.
4. **Draft** a ready-to-paste, conversational design prompt once the user agrees.

This is a suggest-then-wait skill. The user chose deliberately not to have the prompt drafted in the same breath as the suggestion. Respect that — the suggestion comes first, on its own, and the prompt only follows an explicit yes.

## When to notice

Visual potential is broad. An idea qualifies if a person could reasonably imagine *seeing* it rather than only reading about it. Examples of the territory:

- App screens, UI mockups, product interfaces
- Diagrams, flows, system architecture, decision trees
- Landing pages, marketing pages, brand and identity pieces
- Dashboards, data layouts, reports as visual artifacts
- Posters, slides, layouts, infographics

The user does not need to say "design," "visual," "mockup," or "draw." The cue is the *shape of the idea*, not the vocabulary. If someone describes "an app that helps people track meditation streaks" or "a way to show how our agents pass trust signals between each other," that is visual potential — suggest the tool.

Do not force it. If the conversation is plainly non-visual (debugging a regex, discussing a career decision, writing prose), stay quiet. A misplaced suggestion is more annoying than a missed one. Suggest when it would genuinely help the idea, not on every turn.

## How to suggest

Keep it short, natural, and non-pushy. Name the tool, name what you'd visualize, and offer. One or two sentences. For example:

> That layout is clear enough that it'd be worth seeing — want me to turn it into a prompt for Claude's Design tool (claude.com/design)?

Then stop. Let the user decide. Don't pre-write the prompt, don't list options, don't explain the tool at length.

If the user has already brushed off a design suggestion earlier in the conversation, don't keep re-offering for the same idea. Read the room.

## How to draft the prompt (after the go-ahead)

Once the user says yes, write **one** design prompt they can paste directly into claude.com/design. Keep it loose and conversational — a clear paragraph or two of natural language, not a rigid spec with labeled sections. The Design tool works well with prose that conveys intent.

Pull everything you can from the conversation already in progress. The whole point is that the idea and the intent are *already here* — don't re-interview the user for things they've effectively told you. Fold in:

- **What it is** — the artifact and its purpose, in plain terms.
- **Who/what it's for** — audience or context, if it surfaced.
- **The feel** — tone, mood, or style cues the user gave (or a sensible default if they gave none).
- **Key content** — the specific elements, screens, sections, or nodes the idea implies.
- **Anything constraining** — brand, platform, must-haves, things to avoid.

Where the conversation didn't specify something that matters, make a light, reasonable assumption and state it briefly rather than stalling — but don't invent heavy detail the user never implied. If something genuinely pivotal is missing (e.g., you have no idea whether it's a mobile or desktop app and it changes everything), ask one quick question instead of guessing.

### Output format

Present the prompt clearly set off so it's obvious what to copy. A short framing line, then the prompt itself, then a brief offer to adjust. For example:

> Here's a prompt you can paste into claude.com/design:
>
> "[the conversational design prompt]"
>
> Want me to push it more in any direction — different mood, more screens, tighter focus?

Keep the prompt itself in the user's spirit: if they're casual, keep it casual; if the idea is technical, keep the precision. Don't pad it with buzzwords or design jargon the user didn't use.

## Examples

**Example 1 — UI idea surfaces mid-chat**

User has been describing an app that nudges people to take walking breaks.

Suggestion: "The break-nudge screen you're describing is pretty visual — want me to draft a prompt for Claude's Design tool (claude.com/design) so you can see it?"

(After yes) Prompt: "Design a mobile app screen for a gentle walking-break reminder app. The main screen shows the user's current sitting streak and a soft, friendly nudge to step away — think calm and encouraging rather than nagging, with plenty of whitespace and a single clear call-to-action button to start a break. Include a small daily progress indicator. Warm, muted palette, rounded shapes, nothing clinical."

**Example 2 — system idea surfaces**

User is explaining how trust signals move between agents in their framework.

Suggestion: "This trust-handoff is the kind of thing that's much clearer as a diagram — want me to turn it into a prompt for claude.com/design?"

(After yes) Prompt: "Create a system diagram showing how trust signals pass between autonomous agents. Show three or four agent nodes connected by directional arrows representing signed trust handoffs, with a central audit log that every handoff writes to. Label the handoffs with what's being verified. Clean, technical, readable — the kind of diagram that belongs in an architecture doc, not a marketing deck."

**Example 3 — no suggestion warranted**

User is working through a tax question. No visual potential. Say nothing about the Design tool; just help with the question.
