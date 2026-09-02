/**
 * ExamNavigator — flagged / answered / unanswered / current cells (FR-23).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { NavigatorCell } from "./exam_section_reducer";

export interface ExamNavigatorProps {
  readonly cells: readonly NavigatorCell[];
  readonly onJump: (questionId: string) => void;
}

function cellState(cell: NavigatorCell): string {
  if (cell.current) return "current";
  if (cell.flagged) return "flagged";
  if (cell.answered) return "answered";
  return "unanswered";
}

export function ExamNavigator(props: ExamNavigatorProps): React.JSX.Element {
  return (
    <nav data-testid="exam-navigator" aria-label="Question navigator">
      <ol className="flex flex-wrap gap-1.5">
        {props.cells.map((cell, index) => {
          const state = cellState(cell);
          return (
            <li key={cell.questionId}>
              <button
                type="button"
                data-testid={`exam-nav-${cell.questionId}`}
                data-state={state}
                aria-current={cell.current ? "step" : undefined}
                onClick={() => props.onJump(cell.questionId)}
                className={cn(
                  "grid size-9 place-items-center rounded-md border text-xs font-semibold",
                  "data-[state=current]:border-accent data-[state=current]:bg-accent data-[state=current]:text-on-accent",
                  "data-[state=flagged]:border-warning data-[state=flagged]:text-warning",
                  "data-[state=answered]:border-border data-[state=answered]:bg-selected",
                  "data-[state=unanswered]:border-dashed data-[state=unanswered]:border-border data-[state=unanswered]:text-muted",
                )}
              >
                {index + 1}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
