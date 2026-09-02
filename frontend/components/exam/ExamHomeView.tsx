/**
 * ExamHomeView — presentational form × section status (S-D2 / FR-10–12).
 */

"use client";

import * as React from "react";
import type { ExamSectionCode } from "@/lib/wire/exam_entities";
import type { ExamHomeVM } from "./use_exam_home";

export interface ExamHomeViewProps {
  readonly vm: ExamHomeVM;
  readonly onStart: (formId: string, sectionCode: ExamSectionCode) => void;
}

function statusLabel(status: string, remainingMs: number | null): string {
  if (status === "in_progress" && remainingMs != null) {
    const minutes = Math.ceil(remainingMs / 60_000);
    return `In progress · ${minutes} min left`;
  }
  if (status === "submitted") return "Submitted";
  if (status === "expired") return "Expired";
  return "Not started";
}

function actionLabel(status: string): string {
  if (status === "in_progress") return "Resume";
  if (status === "submitted" || status === "expired") return "Review";
  return "Start";
}

export function ExamHomeView(props: ExamHomeViewProps): React.JSX.Element {
  return (
    <div data-testid="exam-home" className="mx-auto flex w-full max-w-[760px] flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-fg">Official exam</h1>
        <p className="mt-1 text-sm text-muted">
          Start any section independently. Official order is recommended.
        </p>
      </header>
      {props.vm.forms.map((form) => (
        <section
          key={form.formId}
          data-testid={`exam-form-${form.formId}`}
          className="rounded-[13px] bg-surface-sunken p-4"
        >
          <h2 className="text-lg font-semibold text-fg">{form.title}</h2>
          <ol className="mt-3 flex flex-col gap-2">
            {form.sections.map((section) => (
              <li
                key={section.code}
                data-testid={`exam-section-${section.code}`}
                data-status={section.status}
                className="flex items-center justify-between gap-3 rounded-[16px] border border-border bg-surface px-4 py-3"
              >
                <div>
                  <p className="font-medium text-fg">
                    {section.officialOrder}. {section.title}
                    {section.recommended ? (
                      <span className="ml-2 text-xs font-semibold uppercase tracking-wide text-muted">
                        recommended
                      </span>
                    ) : null}
                  </p>
                  <p
                    data-testid={`exam-section-status-${section.code}`}
                    className="text-sm text-muted"
                  >
                    {statusLabel(section.status, section.remainingMs)} ·{" "}
                    {section.minutes} min
                  </p>
                </div>
                <button
                  type="button"
                  data-testid={`exam-section-start-${section.code}`}
                  disabled={section.startBlocked}
                  onClick={() => props.onStart(form.formId, section.code)}
                  className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent disabled:pointer-events-none disabled:opacity-50"
                >
                  {actionLabel(section.status)}
                </button>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
