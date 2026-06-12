/**
 * TaskList SSR tests (eval-UI F9). Failure-path first: cancelled stays
 * visibly not-done.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TaskList } from "./TaskList";
import type { TodoListView } from "@/lib/translators/todo_list_projection";
import type { TodoItem } from "@/lib/wire/ui_runtime_events";

function view(...statuses: TodoItem["status"][]): TodoListView {
  const todos = statuses.map((status, i) => ({
    id: `t${i + 1}`,
    content: `task ${i + 1}`,
    status,
  }));
  return {
    todos,
    done: todos.filter((t) => t.status === "completed").length,
    total: todos.length,
  };
}

function render(v: TodoListView): Document {
  const html = renderToStaticMarkup(React.createElement(TaskList, { view: v }));
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("TaskList — failure paths first", () => {
  it("cancelled item renders with its own status, never as done", () => {
    const d = render(view("completed", "cancelled"));
    const cancelled = d.querySelector('[data-testid="todo-t2"]');
    expect(cancelled?.getAttribute("data-status")).toBe("cancelled");
    const root = d.querySelector('[data-testid="task-list"]');
    expect(root?.getAttribute("data-todo-done")).toBe("1");
    expect(root?.getAttribute("data-todo-count")).toBe("2");
  });

  it("pending item is not struck through", () => {
    const d = render(view("pending"));
    const row = d.querySelector('[data-testid="todo-t1"]');
    expect(row?.className ?? "").not.toContain("line-through");
  });
});

describe("TaskList — rendering", () => {
  it("shows the progress count", () => {
    const d = render(view("completed", "completed", "pending"));
    expect(d.querySelector('[data-testid="todo-progress"]')?.textContent).toBe(
      "2/3 done",
    );
  });

  it("completed rows are struck/dimmed", () => {
    const d = render(view("completed"));
    const row = d.querySelector('[data-testid="todo-t1"]');
    expect(row?.className).toContain("line-through");
  });

  it("collapses items past the visible cap behind an expander", () => {
    const d = render(
      view(
        ...Array.from({ length: 10 }, () => "pending" as TodoItem["status"]),
      ),
    );
    expect(d.querySelectorAll('[data-testid^="todo-t"]').length).toBe(10);
    expect(d.querySelector("details summary")?.textContent).toContain(
      "show all 10",
    );
  });
});
