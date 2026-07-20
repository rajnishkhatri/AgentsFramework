/**
 * FeedbackView — the post-answer teaching screen (FR-E1..E5 / T22–T23).
 *
 * Presentational only (F-R1): it renders a `FeedbackVM` (composed by
 * `feedback_vm` from a graded Verdict) as props. No engine port, no grading, no
 * SDK — wire/VM types only.
 *
 * FR-A8 (color is never the sole signal): each reviewed choice pairs its
 * per-state color (via `data-state` + tokens) with an ICON and a TEXT LABEL
 * ("CORRECT ANSWER" / "YOUR CHOICE"), so the state is legible without color.
 * State-driven styling rides `data-state` (§13 convention), not className
 * ternaries, so it survives style merges and is DevTools-inspectable.
 */

import * as React from "react";
import { Check, X, Circle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  FeedCardKind,
  FeedbackVM,
  ReviewedChoiceState,
} from "@/lib/translators/feedback_vm";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";

const STATE_ICON: Record<ReviewedChoiceState, LucideIcon> = {
  correct: Check,
  "chosen-wrong": X,
  other: Circle,
};

/** The text label paired with color for every state (FR-A8). */
const STATE_LABEL: Record<ReviewedChoiceState, string> = {
  correct: "CORRECT ANSWER",
  "chosen-wrong": "YOUR CHOICE",
  other: "",
};

const FEED_CARD_TONE: Record<FeedCardKind, string> = {
  up: "border-[color-mix(in_oklab,var(--color-accent)_35%,transparent)] bg-accent-light/50",
  back: "border-[color-mix(in_oklab,var(--color-warning,var(--color-accent))_35%,transparent)] bg-[color-mix(in_oklab,var(--color-warning,var(--color-accent))_10%,transparent)]",
  forward:
    "border-[color-mix(in_oklab,var(--color-success)_35%,transparent)] bg-[color-mix(in_oklab,var(--color-success)_10%,transparent)]",
};

function ReviewedChoiceRow(props: {
  letter: string;
  label: string;
  state: ReviewedChoiceState;
  rationale: string;
}): React.JSX.Element {
  const { letter, label, state, rationale } = props;
  const Icon = STATE_ICON[state];
  const stateLabel = STATE_LABEL[state];
  return (
    <li
      data-testid={`choice-${letter}`}
      data-state={state}
      className={cn(
        "flex flex-col gap-1.5 rounded-[13px] border px-4 py-3",
        "data-[state=correct]:border-[color-mix(in_oklab,var(--color-success)_45%,transparent)]",
        "data-[state=correct]:bg-[color-mix(in_oklab,var(--color-success)_10%,transparent)]",
        "data-[state=chosen-wrong]:border-[color-mix(in_oklab,var(--color-danger)_45%,transparent)]",
        "data-[state=chosen-wrong]:bg-[color-mix(in_oklab,var(--color-danger)_9%,transparent)]",
        "data-[state=other]:border-border data-[state=other]:bg-surface",
      )}
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          data-state={state}
          className={cn(
            "grid size-7 place-items-center rounded-full font-semibold",
            "data-[state=correct]:bg-success data-[state=correct]:text-on-success",
            "data-[state=chosen-wrong]:bg-danger data-[state=chosen-wrong]:text-on-danger",
            "data-[state=other]:bg-selected data-[state=other]:text-muted",
          )}
        >
          {letter}
        </span>
        <span className="flex-1 font-medium">{label}</span>
        {stateLabel ? (
          <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide">
            <Icon aria-hidden="true" className="size-3.5" />
            {stateLabel}
          </span>
        ) : null}
      </div>
      {rationale.length > 0 ? (
        <div
          data-testid={`choice-rationale-${letter}`}
          className="pl-10 text-sm leading-relaxed text-muted"
        >
          <StreamingMarkdown text={rationale} tone="plain" />
        </div>
      ) : null}
    </li>
  );
}

export function FeedbackView(props: {
  vm: FeedbackVM;
  /** Optional Ask-the-coach action (desktop Feedback bridge, FR-E5 / FR-5). */
  onAskCoach?: () => void;
}): React.JSX.Element {
  const { vm, onAskCoach } = props;
  const [gauge, setGauge] = React.useState<"clicked" | "fuzzy" | null>(null);

  return (
    <section aria-label="Answer feedback" className="flex flex-col gap-5">
      <div
        data-testid="feedback-banner"
        data-banner={vm.banner}
        role="status"
        className={cn(
          "flex items-center gap-2 rounded-md px-4 py-3 text-lg font-semibold",
          "data-[banner=celebrate]:bg-[color-mix(in_oklab,var(--color-success)_12%,transparent)]",
          "data-[banner=celebrate]:text-success",
          "data-[banner=soft]:bg-accent-light data-[banner=soft]:text-accent",
          "data-[banner=walked_through]:bg-[color-mix(in_oklab,var(--color-warning,var(--color-accent))_14%,transparent)]",
          "data-[banner=walked_through]:text-accent",
        )}
      >
        {vm.banner === "celebrate" ? (
          <Check aria-hidden="true" className="size-5" />
        ) : vm.banner === "walked_through" ? (
          <span aria-hidden="true" className="text-lg font-bold">
            →
          </span>
        ) : (
          <Circle aria-hidden="true" className="size-5" />
        )}
        {vm.bannerText}
      </div>

      {vm.resultLabel != null ? (
        <p
          data-testid="feedback-result-label"
          className="text-sm font-medium text-muted"
        >
          {vm.resultLabel}
        </p>
      ) : null}

      {/* FR-A7 / C5: reviewed context_html with <u> restyled to success; plain otherwise. */}
      {vm.recapHasUnderline ? (
        <p
          data-testid="feedback-recap"
          data-has-underline="true"
          className={cn(
            "text-[1.15rem] leading-[1.7]",
            "[&_u]:text-success [&_u]:underline [&_u]:decoration-success [&_u]:underline-offset-2",
          )}
          dangerouslySetInnerHTML={{ __html: vm.recapHtml }}
        />
      ) : (
        <p
          data-testid="feedback-recap"
          data-has-underline="false"
          className="text-[1.15rem] leading-[1.7]"
        >
          {vm.recapHtml}
        </p>
      )}

      <div
        data-testid="feedback-feed-cards"
        className="grid gap-3 md:grid-cols-3"
      >
        {vm.feedCards.map((card) => (
          <article
            key={card.kind}
            data-testid={`feedback-feed-${card.kind}`}
            className={cn(
              "rounded-[13px] border px-3.5 py-3 text-sm leading-relaxed",
              FEED_CARD_TONE[card.kind],
            )}
          >
            <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
              {card.eyebrow}
            </p>
            <StreamingMarkdown text={card.body} tone="plain" />
          </article>
        ))}
      </div>

      <ul className="flex flex-col gap-2">
        {vm.reviewedChoices.map((c) => (
          <ReviewedChoiceRow
            key={c.letter}
            letter={c.letter}
            label={c.label}
            state={c.state}
            rationale={c.rationale}
          />
        ))}
      </ul>

      <div className="flex flex-col gap-3 text-base">
        <div data-testid="feedback-why-correct">
          <span className="font-semibold">
            Why {vm.correctLetter} is correct:{" "}
          </span>
          <StreamingMarkdown text={vm.correctRationale} tone="plain" />
        </div>
        {!vm.correct && vm.chosenLetter ? (
          <div data-testid="feedback-why-tempted">
            <span className="font-semibold">
              Why {vm.chosenLetter} tempted you:{" "}
            </span>
            <StreamingMarkdown text={vm.chosenRationale} tone="plain" />
          </div>
        ) : null}
        <div
          data-testid="feedback-rule"
          className="rounded-[13px] bg-surface px-4 py-3 text-muted"
        >
          <span className="font-semibold text-fg">
            One rule decided this item:{" "}
          </span>
          {vm.procedureSteps != null ? (
            <ol
              data-testid="feedback-procedure"
              className="mt-2 list-decimal space-y-1 pl-5 text-fg"
            >
              {vm.procedureSteps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          ) : (
            <StreamingMarkdown text={vm.ruleMd} tone="plain" />
          )}
        </div>
      </div>

      {onAskCoach ? (
        <button
          type="button"
          data-testid="feedback-ask-coach"
          onClick={onAskCoach}
          className="w-fit rounded-full border border-accent px-5 py-2.5 text-sm font-medium text-accent hover:bg-accent-light"
        >
          Ask the coach
        </button>
      ) : null}

      {/*
        FBK-2 + V18: optional self-explanation + non-gating gauge chips.
        Value is NOT persisted; advancing stays possible without interacting.
      */}
      <div className="flex flex-col gap-2 rounded-[13px] border border-border bg-accent-light/30 px-4 py-3">
        <label
          htmlFor="feedback-self-explanation"
          className="text-sm font-medium text-fg"
        >
          Saying it back makes it stick
        </label>
        <p className="text-xs text-muted">
          Say the rule back in your own words — what test decided it?
        </p>
        <textarea
          id="feedback-self-explanation"
          data-testid="feedback-self-explanation"
          placeholder="Why does the correct answer work here?"
          rows={2}
          className="rounded-[13px] border border-border bg-surface px-4 py-3 text-sm"
        />
        <div
          data-testid="feedback-gauge"
          className="flex flex-wrap items-center gap-2 pt-1"
        >
          <span className="text-xs text-muted">
            Gauge understanding before moving on:
          </span>
          <button
            type="button"
            data-testid="feedback-gauge-clicked"
            data-selected={gauge === "clicked" ? "true" : "false"}
            onClick={() => setGauge("clicked")}
            className={cn(
              "min-h-9 rounded-full border px-3 py-1.5 text-sm font-semibold",
              gauge === "clicked"
                ? "border-success bg-[color-mix(in_oklab,var(--color-success)_14%,transparent)] text-success"
                : "border-border text-fg",
            )}
          >
            This clicked ✓
          </button>
          <button
            type="button"
            data-testid="feedback-gauge-fuzzy"
            data-selected={gauge === "fuzzy" ? "true" : "false"}
            onClick={() => setGauge("fuzzy")}
            className={cn(
              "min-h-9 rounded-full border px-3 py-1.5 text-sm font-semibold",
              gauge === "fuzzy"
                ? "border-accent bg-accent-light text-accent"
                : "border-border text-fg",
            )}
          >
            Still fuzzy
          </button>
        </div>
      </div>
    </section>
  );
}
