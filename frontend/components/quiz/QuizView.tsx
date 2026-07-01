/**
 * QuizView — the quiz item column (FR-D2/D3/D4/D5/A6).
 *
 * Presentational only (F-R1): renders a `QuizItemVM` + the caller-owned
 * selection/hint state as props. All state lives in the screen hook (use_quiz);
 * this component raises `onSelect`/`onSubmit`/`onToggleHint` and styles off
 * `data-*` attributes (§13), never its own logic.
 *
 * FR-D4 submit gate: `canSubmit(selectedLetter)` (the pure quiz_item_vm helper)
 * drives the button's `disabled` — the component does not re-derive the rule.
 * FR-D5 non-reveal: the hint text is passed in (a Socratic prompt); the VM
 * carries no answer letter (quiz_item_vm omits it), so the pre-answer DOM cannot
 * leak the answer.
 *
 * `context_html` (FR-A6 underlined span) is REVIEWED, engine-authored content
 * (the `reviewed` gate guarantees it) — not agent/user output — so rendering it
 * via dangerouslySetInnerHTML is the sanctioned delivery of the underlined span,
 * distinct from FE-AP-12 (which bans agent-emitted HTML in the app origin).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { canSubmit, type QuizItemVM } from "@/lib/translators/quiz_item_vm";

export interface QuizViewProps {
  readonly vm: QuizItemVM;
  readonly selectedLetter: string | null;
  readonly onSelect: (letter: string) => void;
  readonly onSubmit: () => void;
  readonly hintOpen: boolean;
  readonly hint: string;
  readonly onToggleHint: () => void;
}

export function QuizView(props: QuizViewProps): React.JSX.Element {
  const { vm, selectedLetter, onSelect, onSubmit, hintOpen, hint, onToggleHint } =
    props;
  const submittable = canSubmit(selectedLetter);

  return (
    <section aria-label="Quiz question" className="mx-auto flex max-w-[760px] flex-col gap-5">
      {/* FR-A6: reviewed engine-authored context carrying the underlined span. */}
      <p
        data-testid="quiz-context"
        className="text-[1.25rem] leading-[1.8]"
        // Reviewed engine content, not agent output — see file header.
        dangerouslySetInnerHTML={{ __html: vm.contextHtml }}
      />

      <p className="text-base font-medium">{vm.stem}</p>

      <ul className="flex flex-col gap-2">
        {vm.choices.map((c) => {
          const selected = c.letter === selectedLetter;
          return (
            <li key={c.letter}>
              <button
                type="button"
                data-testid={`choice-${c.letter}`}
                data-selected={selected ? "true" : "false"}
                onClick={() => onSelect(c.letter)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[16px] border px-4 py-3 text-left",
                  "data-[selected=false]:border-border data-[selected=false]:bg-surface",
                  "data-[selected=true]:border-accent",
                  "data-[selected=true]:bg-accent-light",
                )}
              >
                <span
                  data-selected={selected ? "true" : "false"}
                  className={cn(
                    "grid size-7 place-items-center rounded-full font-semibold",
                    "data-[selected=false]:bg-selected data-[selected=false]:text-muted",
                    "data-[selected=true]:bg-accent data-[selected=true]:text-white",
                  )}
                >
                  {c.letter}
                </span>
                <span className="flex-1">{c.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex items-center gap-3">
        <button
          type="button"
          data-testid="quiz-hint-toggle"
          onClick={onToggleHint}
          className="rounded-full border border-dashed border-accent px-4 py-2 text-sm text-accent"
        >
          {hintOpen ? "Hide hint" : "Get a hint"}
        </button>
        {/* FR-D6: Reveal answer is a low-emphasis ghost control, separate from the hint. */}
        <button
          type="button"
          data-testid="quiz-reveal"
          className="rounded-full px-4 py-2 text-sm text-muted"
        >
          Reveal answer
        </button>
      </div>

      {hintOpen ? (
        <div
          data-testid="quiz-hint"
          role="note"
          className="rounded-[16px] border border-dashed border-accent bg-accent-light px-4 py-3 text-sm"
        >
          {hint}
        </div>
      ) : null}

      <button
        type="button"
        data-testid="quiz-submit"
        disabled={!submittable}
        onClick={onSubmit}
        data-enabled={submittable ? "true" : "false"}
        className={cn(
          "rounded-full bg-accent px-6 py-3 font-semibold text-white",
          "data-[enabled=false]:opacity-60 data-[enabled=false]:pointer-events-none",
        )}
      >
        Submit answer
      </button>
    </section>
  );
}
