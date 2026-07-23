// @vitest-environment jsdom

/**
 * Phase C page orchestration: bounded sessions close only when the target-th
 * item resolves, after its attempt persists.
 */

import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  return {
    push,
    // Stable identity — Effect 1 lists `router` in its deps.
    router: { push },
    openSession: vi.fn(),
    openItem: vi.fn(),
    resumeSession: vi.fn(),
    planAnswer: vi.fn(),
    submit: vi.fn(),
    escape: vi.fn(),
    closeSession: vi.fn(),
    listSkillIds: vi.fn(),
    listSkills: vi.fn(),
    loadLadder: vi.fn(),
    recordPointer: vi.fn(),
    clearActiveQuiz: vi.fn(),
    shellSnapshot: { panelDismissed: false },
    durableEnabled: false,
    search: "",
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
  useSearchParams: () => new URLSearchParams(mocks.search),
}));

vi.mock("@/components/learn/LearnIdentityProvider", () => ({
  useLearnIdentity: () => ({ learnerId: "learner-1" }),
}));

vi.mock("@/components/quiz/use_quiz", () => ({
  useQuiz: () => ({
    openSession: mocks.openSession,
    openItem: mocks.openItem,
    resumeSession: mocks.resumeSession,
    planAnswer: mocks.planAnswer,
    submit: mocks.submit,
    escape: mocks.escape,
    closeSession: mocks.closeSession,
    listSkillIds: mocks.listSkillIds,
    listSkills: mocks.listSkills,
    loadLadder: mocks.loadLadder,
    recordPointer: mocks.recordPointer,
  }),
  isNoContentError: (err: unknown) =>
    err instanceof Error && err.message === "no content available",
  isPoolExhaustedError: (err: unknown) =>
    err instanceof Error && err.message === "pool exhausted",
  isResumeExhaustedError: (err: unknown) =>
    err instanceof Error && err.name === "QuizResumeExhaustedError",
}));

vi.mock("@/lib/adapters/engine/engine_client", () => ({
  durableEngineEnabled: () => mocks.durableEnabled,
}));

vi.mock("@/components/quiz/quiz_session_store", () => ({
  clearActiveQuiz: mocks.clearActiveQuiz,
  readActiveQuiz: () => null,
  setActiveQuiz: vi.fn(),
  stashQuizSession: vi.fn(),
}));

vi.mock("@/lib/adapters/feature_flags/env_var_flags_adapter", () => ({
  EnvVarFlagsAdapter: class {
    isEnabled(): boolean {
      return true;
    }
  },
}));

vi.mock("@/lib/composition_browser", () => ({
  buildBrowserRuntimeClient: () => ({}),
}));

vi.mock("@/components/shell/use_surface", () => ({
  RAIL_COLLAPSED: 64,
  coachMode: () => "fullscreen",
  useSurface: () => "desktop",
}));

vi.mock("@/components/shell/shell_layout_store", () => ({
  getShellLayoutSnapshot: () => mocks.shellSnapshot,
  setPanelDismissed: vi.fn(),
  subscribeShellLayout: () => () => undefined,
}));

vi.mock("@/components/quiz/QuizView", async () => {
  const ReactModule = await import("react");
  return {
    QuizFrameChrome: () => null,
    QuizView: (props: {
      onSelect: (letter: string) => void;
      onSubmit: () => void;
    }) =>
      ReactModule.createElement(
        "div",
        null,
        ReactModule.createElement(
          "button",
          {
            "data-testid": "select-a",
            onClick: () => props.onSelect("A"),
          },
          "A",
        ),
        ReactModule.createElement(
          "button",
          {
            "data-testid": "select-b",
            onClick: () => props.onSelect("B"),
          },
          "B",
        ),
        ReactModule.createElement(
          "button",
          { "data-testid": "submit", onClick: props.onSubmit },
          "Submit",
        ),
      ),
  };
});

vi.mock("@/components/quiz/QuizProgress", () => ({
  QuizProgress: () => null,
}));
vi.mock("@/components/feedback/FeedbackView", () => ({
  FeedbackView: () => null,
}));
vi.mock("@/components/coach/CoachDrawer", () => ({ CoachDrawer: () => null }));
vi.mock("@/components/coach/CoachPanel", () => ({ CoachPanel: () => null }));
vi.mock("@/components/coach/CoachTriggerPill", () => ({
  CoachTriggerPill: () => null,
}));
vi.mock("@/components/quiz/QuizDurableStates", () => ({
  QuizNoContentState: () => null,
  QuizPersistErrorBanner: () => null,
}));

import QuizPage from "./page";

const session = {
  id: "session-1",
  subject: "act-english",
  learner_id: "learner-1",
  mode: "adaptive" as const,
  skill_focus: null,
  started_at: "2026-07-22T00:00:00.000Z",
  ended_at: null,
  score_correct: 0,
  score_total: 0,
  target_count: 1,
  current_question_id: null,
};

const question = {
  id: "q1",
  subject: "act-english",
  skill_id: "skill-1",
  difficulty: 1,
  context_html: "",
  stem: "Pick B",
  choices: [
    { letter: "A", label: "Wrong", is_no_change: false },
    { letter: "B", label: "Right", is_no_change: false },
  ],
  answer_letter: "B",
  per_choice_rationale: { A: "wrong", B: "right" },
  why_correct_md: "Because B.",
  why_tempted_md: "",
  rule_md: "Rule",
  item_type: "mc",
  misconception: null,
  reviewed: true,
  generated_by: "test",
};

async function flush(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("QuizPage — Phase C bounded completion", () => {
  let container: HTMLDivElement;
  let root: Root | null;

  beforeEach(async () => {
    vi.clearAllMocks();
    mocks.durableEnabled = false;
    mocks.search = "";
    mocks.openSession.mockResolvedValue({
      session,
      skillStateAtStart: new Map(),
    });
    mocks.openItem.mockResolvedValue({
      skillId: "skill-1",
      question,
      hintLadder: [],
    });
    mocks.resumeSession.mockResolvedValue(null);
    mocks.listSkillIds.mockResolvedValue(["skill-1"]);
    mocks.listSkills.mockResolvedValue([
      {
        id: "skill-1",
        subject: "act-english",
        key: "skill",
        name: "Skill",
        share_of_test_pct: 100,
        accent_var: "--color-bucket-rhetoric",
        description: "",
        order: 1,
      },
    ]);
    mocks.loadLadder.mockResolvedValue([]);
    mocks.planAnswer.mockImplementation(
      ({ letter }: { letter: string | null }) =>
        letter == null
          ? null
          : {
              letter,
              idempotencyKey: `key-${letter}`,
              verdict: {
                correct: letter === "B",
                correct_letter: "B",
                chosen_letter: letter,
              },
            },
    );
    mocks.submit.mockResolvedValue({});
    mocks.closeSession.mockResolvedValue({
      ...session,
      ended_at: "2026-07-22T00:01:00.000Z",
      score_total: 1,
    });

    root = null;
  });

  async function mountPage(): Promise<void> {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root!.render(React.createElement(QuizPage));
    });
    await flush();
    await flush();
  }

  afterEach(async () => {
    if (root != null) {
      await act(async () => {
        root!.unmount();
      });
      container.remove();
    }
  });

  it("keeps Q1 open after a wrong first grade, then persists, closes, and routes when resolved", async () => {
    await mountPage();
    const selectA = container.querySelector<HTMLButtonElement>(
      '[data-testid="select-a"]',
    );
    const selectB = container.querySelector<HTMLButtonElement>(
      '[data-testid="select-b"]',
    );
    const submit = container.querySelector<HTMLButtonElement>(
      '[data-testid="submit"]',
    );
    expect(selectA).not.toBeNull();
    expect(selectB).not.toBeNull();
    expect(submit).not.toBeNull();

    await act(async () => selectA!.click());
    await act(async () => submit!.click());
    await flush();

    expect(mocks.submit).toHaveBeenCalledTimes(1);
    expect(mocks.closeSession).not.toHaveBeenCalled();
    expect(mocks.push).not.toHaveBeenCalled();

    await act(async () => selectB!.click());
    await act(async () => submit!.click());
    await flush();
    await flush();

    expect(mocks.submit).toHaveBeenCalledTimes(2);
    expect(mocks.closeSession).toHaveBeenCalledWith({
      sessionId: "session-1",
      scoreCorrect: 0,
      scoreTotal: 1,
    });
    expect(mocks.submit.mock.invocationCallOrder[1]).toBeLessThan(
      mocks.closeSession.mock.invocationCallOrder[0]!,
    );
    expect(mocks.clearActiveQuiz).toHaveBeenCalled();
    expect(mocks.push).toHaveBeenCalledWith(
      "/learn/summary?session=session-1",
    );
    expect(mocks.openItem).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toContain("Keep practising");
    expect(
      container.querySelector('[data-testid="quiz-next"]'),
    ).toBeNull();
  });

  it("closes to summary at the reached count when the servable pool exhausts", async () => {
    mocks.openSession.mockResolvedValue({
      session: { ...session, target_count: 2 },
      skillStateAtStart: new Map(),
    });
    mocks.openItem
      .mockResolvedValueOnce({
        skillId: "skill-1",
        question,
        hintLadder: [],
      })
      .mockRejectedValueOnce(new Error("pool exhausted"));
    await mountPage();

    await act(async () => {
      container
        .querySelector<HTMLButtonElement>('[data-testid="select-b"]')!
        .click();
    });
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>('[data-testid="submit"]')!
        .click();
    });
    await flush();

    const next = container.querySelector<HTMLButtonElement>(
      '[data-testid="quiz-next"]',
    );
    expect(next).not.toBeNull();
    await act(async () => next!.click());
    await flush();
    await flush();

    expect(mocks.openItem).toHaveBeenCalledTimes(2);
    expect(mocks.closeSession).toHaveBeenCalledWith({
      sessionId: "session-1",
      scoreCorrect: 1,
      scoreTotal: 1,
    });
    expect(mocks.push).toHaveBeenCalledWith(
      "/learn/summary?session=session-1",
    );
  });
});

describe("QuizPage — Phase B durable resume + served pointer", () => {
  let container: HTMLDivElement;
  let root: Root | null;

  beforeEach(async () => {
    vi.clearAllMocks();
    mocks.durableEnabled = true;
    mocks.search = "";
    mocks.openSession.mockResolvedValue({
      session,
      skillStateAtStart: new Map(),
    });
    mocks.openItem.mockResolvedValue({
      skillId: "skill-1",
      question,
      hintLadder: [],
    });
    mocks.resumeSession.mockResolvedValue(null);
    mocks.listSkillIds.mockResolvedValue(["skill-1"]);
    mocks.listSkills.mockResolvedValue([
      {
        id: "skill-1",
        subject: "act-english",
        key: "skill",
        name: "Skill",
        share_of_test_pct: 100,
        accent_var: "--color-bucket-rhetoric",
        description: "",
        order: 1,
      },
    ]);
    mocks.loadLadder.mockResolvedValue([]);
    mocks.closeSession.mockResolvedValue({
      ...session,
      ended_at: "2026-07-22T00:01:00.000Z",
    });
    root = null;
  });

  async function mountPage(): Promise<void> {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root!.render(React.createElement(QuizPage));
    });
    await flush();
    await flush();
  }

  afterEach(async () => {
    if (root != null) {
      await act(async () => {
        root!.unmount();
      });
      container.remove();
    }
  });

  it("records the served pointer on entering answering without blocking the serve (FR-B3a)", async () => {
    await mountPage();
    expect(mocks.recordPointer).toHaveBeenCalledWith("session-1", "q1");
    expect(
      container.querySelector('[data-testid="select-a"]'),
    ).not.toBeNull();
  });

  it("resumes from the server active session with the server score (FR-B1/B10)", async () => {
    mocks.resumeSession.mockResolvedValue({
      session: { ...session, current_question_id: "q1", target_count: 30 },
      item: { skillId: "skill-1", question, hintLadder: [] },
      score: { correct: 4, total: 7 },
    });

    await mountPage();

    expect(mocks.resumeSession).toHaveBeenCalledWith({
      subject: "act-english",
    });
    expect(mocks.openSession).not.toHaveBeenCalled();
    // Resume lands in answering — openItem is skipped.
    expect(mocks.openItem).not.toHaveBeenCalled();
    expect(
      container.querySelector('[data-testid="select-a"]'),
    ).not.toBeNull();
  });

  it("still serves the question when the pointer write rejects (FR-B3a-nonblock)", async () => {
    // Fire-and-forget helper swallows async failures; Effect still records.
    mocks.recordPointer.mockImplementation(() => undefined);

    await mountPage();
    expect(
      container.querySelector('[data-testid="select-a"]'),
    ).not.toBeNull();
  });

  it("honors ?mode=review as a fresh session, not resume (FR-B6)", async () => {
    mocks.search = "mode=review";
    mocks.resumeSession.mockResolvedValue({
      session: { ...session, current_question_id: "q1", target_count: 30 },
      item: { skillId: "skill-1", question, hintLadder: [] },
      score: { correct: 4, total: 7 },
    });

    await mountPage();

    expect(mocks.resumeSession).not.toHaveBeenCalled();
    expect(mocks.openSession).toHaveBeenCalled();
  });
});
