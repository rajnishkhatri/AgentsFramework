/**
 * Quiz durable-engine UI states (FR-A8 error banner + FR-G3 empty content).
 * Presentational only — page owns when to show them (F-R1).
 */

import * as React from "react";

/** FR-A8: hold optimistic verdict; block advance; retry with same idempotency key. */
export function QuizPersistErrorBanner(props: {
  readonly message: string;
  readonly onRetry: () => void;
  readonly retrying?: boolean;
}): React.JSX.Element {
  return (
    <div
      role="alert"
      data-testid="quiz-persist-error"
      className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger"
    >
      <p>{props.message}</p>
      <button
        type="button"
        data-testid="quiz-persist-retry"
        onClick={props.onRetry}
        disabled={props.retrying === true}
        className="mt-2 rounded-full border border-danger/50 px-4 py-1.5 font-medium hover:bg-danger/10 disabled:opacity-50"
      >
        {props.retrying === true ? "Saving…" : "Retry save"}
      </button>
    </div>
  );
}

/** FR-G3: empty content tables — honest empty state, not a broken quiz. */
export function QuizNoContentState(): React.JSX.Element {
  return (
    <div
      role="status"
      data-testid="quiz-no-content"
      className="mx-auto flex max-w-[480px] flex-col gap-2 py-16 text-center"
    >
      <p className="text-lg font-semibold text-fg">No content available</p>
      <p className="text-sm text-muted">
        Practice items are not ready yet. Please try again later.
      </p>
    </div>
  );
}
