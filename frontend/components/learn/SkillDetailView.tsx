/**
 * SkillDetailView — presentational `/learn/skill` surface (E1a).
 *
 * Renders a SkillDetailVM. Local ephemeral state only: self-explain note +
 * completionTry pick (FR-12/14 — never persisted, never Scheduler.review /
 * AttemptRepo.record). Role-tinted blocks with text labels (AL-25).
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import type { BlockVM, SkillDetailVM } from "@/lib/translators/skill_detail_vm";
import { screen } from "@/components/shell/nav_model";
import { AccuracyBars } from "./AccuracyBars";
import { setCoachPin } from "@/components/coach/coach_thread_store";

export interface SkillDetailViewProps {
  readonly vm: SkillDetailVM;
  /** Optional spies for FR-12/14 tests — must never be called by the view. */
  readonly onAttemptRecord?: () => void;
  readonly onSchedulerReview?: () => void;
}

function BlockShell(props: {
  readonly block: BlockVM;
  readonly children: React.ReactNode;
  readonly className?: string;
}): React.JSX.Element {
  const { block, children, className } = props;
  const { tint, role, tag } = block;
  return (
    <section
      data-testid={`block-${tag}`}
      data-role={role}
      data-zone={block.zone}
      style={{
        borderColor: tint.border,
        background: tint.background,
        borderStyle: tint.borderStyle,
        color: "var(--color-fg)",
        // Bind skill accent for accent-* roles
        ["--accent" as string]: "var(--accent, var(--color-accent))",
      }}
      className={cn(
        "flex flex-col gap-2.5 rounded-[14px] border p-4",
        className,
      )}
    >
      {children}
    </section>
  );
}

function RoleLabel(props: {
  readonly ink: string;
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <h2
      className="text-[0.7rem] font-semibold uppercase tracking-[0.06em]"
      style={{ color: props.ink }}
    >
      {props.children}
    </h2>
  );
}

function GroundBlock(props: {
  readonly block: Extract<BlockVM, { tag: "ground" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <div className="flex items-center gap-2.5">
        <RoleLabel ink={block.tint.ink}>What you already know</RoleLabel>
        {block.opener ? (
          <span
            data-testid="opener-marker"
            className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.66rem] uppercase tracking-wide"
            style={{
              color: "var(--accent, var(--color-accent))",
              borderColor:
                "color-mix(in oklab, var(--accent, var(--color-accent)) 40%, var(--color-border))",
            }}
          >
            ▸ start here
          </span>
        ) : null}
      </div>
      <p className="text-[1.08rem] leading-relaxed">{block.body}</p>
    </BlockShell>
  );
}

function PitfallBlock(props: {
  readonly block: Extract<BlockVM, { tag: "pitfall" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>
        {block.framing === "parting" ? "One thing to watch" : "Where it trips you up"}
      </RoleLabel>
      <p className="text-[1.08rem] leading-relaxed">{block.body}</p>
    </BlockShell>
  );
}

function QuestionBlock(props: {
  readonly block: Extract<BlockVM, { tag: "question" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>The question</RoleLabel>
      <p className="text-[1.28rem] font-medium leading-snug">{block.body}</p>
    </BlockShell>
  );
}

function SelfExplainBlock(props: {
  readonly block: Extract<BlockVM, { tag: "selfExplainPrompt" }>;
  readonly note: string;
  readonly onNote: (v: string) => void;
}): React.JSX.Element {
  const { block, note, onNote } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>In your own words</RoleLabel>
      <p className="text-base leading-relaxed">{block.prompt}</p>
      <textarea
        data-testid="self-explain-input"
        aria-label="Your best guess"
        placeholder="Your best guess…"
        defaultValue={note}
        onChange={(e) => onNote(e.target.value)}
        className="min-h-14 w-full rounded-md border border-border bg-bg p-2 text-sm"
      />
      <p className="text-xs italic text-muted">
        Your note — kept here for you, never saved or scored.
      </p>
    </BlockShell>
  );
}

function RuleBlock(props: {
  readonly block: Extract<BlockVM, { tag: "rule" }>;
  readonly noteEcho: string | null;
}): React.JSX.Element {
  const { block, noteEcho } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>The rule</RoleLabel>
      <p className="text-[1.08rem] leading-relaxed">{block.body}</p>
      {block.examples[0] ? (
        <p className="font-serif text-[1.28rem] leading-relaxed">{block.examples[0]}</p>
      ) : null}
      {noteEcho != null ? (
        <div
          data-testid="note-echo"
          className="flex gap-2 rounded-[11px] border p-2.5 text-sm"
          style={{
            borderColor:
              "color-mix(in oklab, var(--accent, var(--color-accent)) 25%, var(--color-border))",
            background:
              "color-mix(in oklab, var(--accent, var(--color-accent)) 6%, var(--color-bg))",
          }}
        >
          <p>
            <span className="text-muted">You guessed:</span> &ldquo;{noteEcho}
            &rdquo;{" "}
            <span className="text-muted">— did the rule match your thinking?</span>
          </p>
        </div>
      ) : null}
    </BlockShell>
  );
}

function WorkedExampleBlock(props: {
  readonly block: Extract<BlockVM, { tag: "workedExample" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>Worked example</RoleLabel>
      <p className="font-serif text-[1.05rem] font-semibold leading-snug">
        {block.example.sentence}
      </p>
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {block.example.steps.map((step, i) => (
          <li key={i} className="flex gap-2.5 text-[0.98rem] leading-snug">
            <span
              aria-hidden
              className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[0.78rem] font-bold text-white"
              style={{ background: "var(--accent, var(--color-accent))" }}
            >
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <div className="self-start rounded-full border border-[color-mix(in_oklab,var(--color-success)_32%,transparent)] bg-[color-mix(in_oklab,var(--color-success)_15%,var(--color-bg))] px-3 py-1.5 text-[0.92rem] font-semibold text-success">
        ✓ {block.example.answer}
      </div>
    </BlockShell>
  );
}

function CompletionTryBlock(props: {
  readonly block: Extract<BlockVM, { tag: "completionTry" }>;
  readonly picked: number | null;
  readonly onPick: (i: number) => void;
  readonly onReset: () => void;
}): React.JSX.Element {
  const { block, picked, onPick, onReset } = props;
  const choices = block.tryItem.choices;
  const pickedChoice = picked != null ? choices[picked] : null;
  const correct = pickedChoice?.correct === true;
  const missed = pickedChoice != null && !pickedChoice.correct;

  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>Now you try</RoleLabel>
      <p className="font-serif text-[1.05rem] font-semibold leading-snug">
        {block.tryItem.sentence}
      </p>
      <div className="flex flex-wrap gap-2.5">
        {choices.map((c, i) => {
          const isPicked = picked === i;
          const showMark = isPicked || (missed && c.correct);
          const mark = c.correct ? "✓" : "✗";
          return (
            <button
              key={i}
              type="button"
              data-testid={`try-choice-${i}`}
              data-correct={c.correct ? "true" : "false"}
              disabled={picked != null}
              onClick={() => onPick(i)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm",
                isPicked && c.correct && "border-success font-semibold text-success",
                isPicked && !c.correct && "border-warning font-semibold text-warning",
                !isPicked && missed && c.correct && "border-success font-semibold",
              )}
            >
              {showMark ? <span aria-hidden>{mark}</span> : null}
              {c.text}
            </button>
          );
        })}
      </div>
      {pickedChoice != null ? (
        <div
          role="status"
          data-testid="try-feedback"
          className="rounded-[11px] border p-3 text-sm"
        >
          {correct
            ? "Nice — you got it."
            : block.tryItem.why}
        </div>
      ) : null}
      {correct ? (
        <Link
          href={`${screen("quiz").route}?focus=${block.skillId}`}
          data-testid="practice-skill-cta"
          className="btn btn-default btn-md self-start rounded-[var(--radius-sm)]"
        >
          Practice this skill →
        </Link>
      ) : null}
      {missed ? (
        <button
          type="button"
          data-testid="try-again"
          onClick={onReset}
          className="self-start rounded-full border border-border px-3.5 py-1.5 text-sm"
        >
          ↺ Try again
        </button>
      ) : null}
      <p className="text-xs italic text-muted">
        Practice — not recorded. Your review schedule doesn&apos;t move here.
      </p>
    </BlockShell>
  );
}

function MisconceptionCalloutBlock(props: {
  readonly block: Extract<BlockVM, { tag: "misconceptionCallout" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>{block.eyebrow}</RoleLabel>
      <p data-testid="callout-body" className="text-[1.08rem] leading-relaxed">
        {block.body}
      </p>
    </BlockShell>
  );
}

function AnnotatedExampleBlock(props: {
  readonly block: Extract<BlockVM, { tag: "annotatedExample" }>;
}): React.JSX.Element {
  const { block } = props;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>See it in action</RoleLabel>
      {block.examples.map((ex, i) => (
        <div key={i} className="flex flex-col gap-2">
          <p className="font-serif text-base leading-relaxed">
            {ex.pre}
            <span
              className="rounded-sm px-0.5"
              style={{
                background: ex.essential
                  ? "color-mix(in oklab, var(--color-muted) 18%, transparent)"
                  : "color-mix(in oklab, var(--accent, var(--color-accent)) 16%, transparent)",
              }}
            >
              {ex.essential ? "" : ","}
              {ex.clause}
              {ex.essential ? "" : ","}
            </span>
            {ex.post}
          </p>
          <div className="flex flex-wrap gap-3.5 text-sm text-muted">
            {ex.callouts.map((c, j) => (
              <span key={j}>{c}</span>
            ))}
          </div>
        </div>
      ))}
    </BlockShell>
  );
}

function DueChecklistBlock(props: {
  readonly block: Extract<BlockVM, { tag: "dueChecklist" }>;
}): React.JSX.Element {
  const { block } = props;
  const quiz = screen("quiz").route;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>Also due for review</RoleLabel>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {block.items.map((item) => (
          <li
            key={item.skillId}
            className="flex items-center justify-between gap-2 text-sm"
          >
            <span>{item.name}</span>
            <Link
              href={`${quiz}?focus=${item.skillId}`}
              className="text-sm font-semibold underline-offset-2 hover:underline"
            >
              Drill →
            </Link>
          </li>
        ))}
      </ul>
    </BlockShell>
  );
}

function AccuracyStatBlock(props: {
  readonly block: Extract<BlockVM, { tag: "accuracyStat" }>;
}): React.JSX.Element {
  const { block } = props;
  const footnote =
    block.masteryPct == null
      ? "Not your mastery estimate — accuracy is a different number"
      : `Not your mastery estimate (${block.masteryPct}%) — accuracy is a different number`;
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>Accuracy</RoleLabel>
      <p
        data-testid="accuracy-value"
        className="text-2xl font-semibold tabular-nums leading-none"
      >
        {block.valuePct}%
      </p>
      <p className="text-sm text-muted">Recent sessions on this skill</p>
      <AccuracyBars bars={block.bars} />
      <p data-testid="accuracy-mastery-footnote" className="text-xs text-muted">
        {footnote}
      </p>
    </BlockShell>
  );
}

function CoachEntryBlock(props: {
  readonly block: Extract<BlockVM, { tag: "coachEntry" }>;
}): React.JSX.Element {
  const { block } = props;
  const router = useRouter();
  return (
    <BlockShell block={block}>
      <RoleLabel ink={block.tint.ink}>Stuck? Ask the coach</RoleLabel>
      <p className="text-sm leading-relaxed">
        Work it out with a hint-first Socratic nudge — never the answer up front.
        Pinned to {block.skillName}.
      </p>
      <button
        type="button"
        data-testid="coach-entry-seam"
        className="self-start rounded-md border border-border px-3 py-1.5 text-sm font-semibold"
        onClick={() => {
          setCoachPin(
            {
              kind: "lesson",
              skillId: block.skillId,
              label: block.skillName,
            },
            "pre_submit",
          );
          router.push(screen("coach").route);
        }}
      >
        ✦ Open coach
      </button>
    </BlockShell>
  );
}

function renderBlock(
  block: BlockVM,
  state: {
    note: string;
    onNote: (v: string) => void;
    noteEcho: string | null;
    picked: number | null;
    onPick: (i: number) => void;
    onReset: () => void;
  },
): React.JSX.Element {
  switch (block.tag) {
    case "ground":
      return <GroundBlock block={block} />;
    case "pitfall":
      return <PitfallBlock block={block} />;
    case "question":
      return <QuestionBlock block={block} />;
    case "selfExplainPrompt":
      return (
        <SelfExplainBlock block={block} note={state.note} onNote={state.onNote} />
      );
    case "rule":
      return <RuleBlock block={block} noteEcho={state.noteEcho} />;
    case "workedExample":
      return <WorkedExampleBlock block={block} />;
    case "completionTry":
      return (
        <CompletionTryBlock
          block={block}
          picked={state.picked}
          onPick={state.onPick}
          onReset={state.onReset}
        />
      );
    case "misconceptionCallout":
      return <MisconceptionCalloutBlock block={block} />;
    case "annotatedExample":
      return <AnnotatedExampleBlock block={block} />;
    case "dueChecklist":
      return <DueChecklistBlock block={block} />;
    case "accuracyStat":
      return <AccuracyStatBlock block={block} />;
    case "coachEntry":
      return <CoachEntryBlock block={block} />;
    default: {
      const _e: never = block;
      return _e;
    }
  }
}

export function SkillDetailView(props: SkillDetailViewProps): React.JSX.Element {
  const { vm } = props;
  const [note, setNote] = React.useState("");
  const [picked, setPicked] = React.useState<number | null>(null);

  const noteEcho =
    vm.context === "newSkill" && note.trim().length > 0 ? note.trim() : null;

  // Spies must never fire — the view is inert to the scheduler (FR-12/14).
  void props.onAttemptRecord;
  void props.onSchedulerReview;

  if (vm.empty) {
    return (
      <div
        data-testid="skill-detail-empty"
        className="flex flex-col gap-4 p-6"
        style={{ ["--accent" as string]: `var(${vm.accentVar})` }}
      >
        <header>
          <h1 className="text-[28px] font-semibold tracking-tight">{vm.skillName}</h1>
          <p className="text-sm text-muted">Lesson coming — nothing to show yet.</p>
        </header>
      </div>
    );
  }

  const state = {
    note,
    onNote: setNote,
    noteEcho,
    picked,
    onPick: (i: number) => setPicked(i),
    onReset: () => setPicked(null),
  };

  return (
    <div
      data-testid="skill-detail"
      data-context={vm.context}
      className="flex flex-col gap-4 p-6"
      style={{ ["--accent" as string]: `var(${vm.accentVar})` }}
    >
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-[0.7rem] font-semibold uppercase tracking-[0.06em] text-muted">
            {vm.context === "newSkill"
              ? "New skill · first lesson"
              : vm.context === "returning"
                ? "Returning · clear the debt"
                : "Quick refresher"}
          </span>
          <h1 className="text-[28px] font-semibold tracking-tight">{vm.skillName}</h1>
        </div>
      </header>

      <div className="flex items-start gap-5">
        <div className="flex min-w-0 flex-1 flex-col gap-3.5">
          {vm.main.map((b) => (
            <React.Fragment key={`${b.tag}-${b.order}`}>
              {renderBlock(b, state)}
            </React.Fragment>
          ))}
        </div>
        {vm.rail.length > 0 ? (
          <aside
            data-testid="skill-rail"
            className="flex w-[260px] shrink-0 flex-col gap-3.5"
          >
            {vm.rail.map((b) => (
              <React.Fragment key={`${b.tag}-${b.order}`}>
                {renderBlock(b, state)}
              </React.Fragment>
            ))}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
