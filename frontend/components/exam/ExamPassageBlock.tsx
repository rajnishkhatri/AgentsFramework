/**
 * ExamPassageBlock — Reading/Science passage for the current item (C-3 / FR-P2-12).
 * Lookup by question.passage label. Figure <img> when the passage carries one.
 * @container layout (repo convention) so the block flexes inside the runner.
 */

"use client";

import * as React from "react";
import type { ExamPassage } from "@/lib/wire/exam_entities";
import { assetRefToUrl } from "./exam_item_vm";

export interface ExamPassageBlockProps {
  readonly passages: readonly ExamPassage[];
  readonly passageLabel: string | null;
}

export function ExamPassageBlock(
  props: ExamPassageBlockProps,
): React.JSX.Element | null {
  const passage = props.passages.find((p) => p.label === props.passageLabel);
  if (passage == null) return null;

  return (
    <article
      data-testid="exam-passage"
      aria-label={passage.title ?? "Passage"}
      className="@container rounded-[13px] border border-border p-4"
    >
      <div className="flex flex-col gap-3 @md:gap-4">
        {passage.title ? (
          <h2 className="text-base font-semibold text-fg">{passage.title}</h2>
        ) : null}
        {passage.intro ? (
          <p className="text-sm text-muted">{passage.intro}</p>
        ) : null}
        {passage.text ? (
          <p className="whitespace-pre-wrap text-[1.1rem] leading-7">
            {passage.text}
          </p>
        ) : null}
        <PassageFigure image={passage.image} title={passage.title} />
      </div>
    </article>
  );
}

function PassageFigure(props: {
  readonly image: ExamPassage["image"];
  readonly title: string | null;
}): React.JSX.Element | null {
  const [failedUrl, setFailedUrl] = React.useState<string | null>(null);
  if (props.image == null) return null;
  const src = assetRefToUrl(props.image);
  if (failedUrl === src) {
    return (
      <p
        data-testid="exam-passage-unavailable"
        role="status"
        className="rounded-md border border-border px-3 py-2 text-sm text-muted"
      >
        content unavailable
      </p>
    );
  }
  return (
    <img
      src={src}
      alt={props.title ? `${props.title} (official image)` : "Passage figure (official image)"}
      data-testid="exam-passage-figure"
      onError={() => setFailedUrl(src)}
    />
  );
}
