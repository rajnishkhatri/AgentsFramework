/**
 * Live task / todo checklist (eval-UI F9).
 *
 * Renders the `state_todo`-backed checklist projected by
 * `todo_list_projection`: one row per TodoItem with a status icon,
 * completed rows struck/dimmed, and a compact progress count. For the
 * wave-2 adversarial gold-set cells a visibly not-done row (pending /
 * cancelled) is primary `goal_met` evidence -- cancelled is NEVER
 * rendered as done.
 *
 * Deterministic hooks: `data-todo-count`, `data-todo-done`,
 * `data-testid="todo-{id}"`. Long lists collapse behind a native
 * <details> expander (progressive disclosure) with the first items
 * always visible.
 *
 * Per F-R2/F-R8: consumes wire types only; no SDK imports.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { TodoListView } from "@/lib/translators/todo_list_projection";
import type { TodoItem } from "@/lib/wire/ui_runtime_events";

const STATUS_ICON: Record<TodoItem["status"], string> = {
  pending: "○",
  in_progress: "◐",
  completed: "✓",
  cancelled: "⊘",
};

const VISIBLE_CAP = 7;

function TodoRow(props: { todo: TodoItem }): React.JSX.Element {
  const { todo } = props;
  return (
    <li
      data-testid={`todo-${todo.id}`}
      data-status={todo.status}
      className={cn(
        "flex gap-2 items-baseline text-sm",
        todo.status === "completed" && "line-through text-muted",
        todo.status === "cancelled" && "text-muted",
        todo.status === "in_progress" && "font-medium",
      )}
    >
      <span aria-hidden="true">{STATUS_ICON[todo.status]}</span>
      <span>{todo.content}</span>
    </li>
  );
}

export function TaskList(props: { view: TodoListView }): React.JSX.Element {
  const { view } = props;
  const overflow = view.todos.length > VISIBLE_CAP;
  const head = overflow ? view.todos.slice(0, VISIBLE_CAP) : view.todos;
  const tail = overflow ? view.todos.slice(VISIBLE_CAP) : [];
  return (
    <section
      data-testid="task-list"
      data-todo-count={view.total}
      data-todo-done={view.done}
      aria-label="Task list"
      className="border border-border rounded-md px-3 py-2 my-1 bg-surface grid gap-1"
    >
      <header className="flex justify-between text-xs text-muted">
        <span>Tasks</span>
        <span data-testid="todo-progress">
          {view.done}/{view.total} done
        </span>
      </header>
      <ul className="list-none m-0 p-0 grid gap-1">
        {head.map((todo) => (
          <TodoRow key={todo.id} todo={todo} />
        ))}
      </ul>
      {overflow ? (
        <details>
          <summary className="cursor-pointer text-xs text-muted">
            show all {view.total}
          </summary>
          <ul className="list-none m-0 p-0 grid gap-1">
            {tail.map((todo) => (
              <TodoRow key={todo.id} todo={todo} />
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
