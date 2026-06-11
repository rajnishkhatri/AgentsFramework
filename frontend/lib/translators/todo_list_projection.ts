/**
 * Pure projection: state_render events -> typed todo checklist view
 * (eval-UI F9, plan §8 F9 + §8.6-A).
 *
 * The backend `state_todo` tool replaces the `todos` state channel
 * wholesale; the runtime emits it as a wire StateDelta with JSON-Patch
 * `replace` ops, which the AG-UI translator surfaces as
 * `state_render{key:"delta", value:[ops]}` (snapshots arrive as
 * `key:"snapshot"`). This translator narrows that unknown payload into
 * `TodoItem`s, dropping anything malformed (failure-first: a bad delta
 * must never crash the chat).
 *
 * `cancelled` deliberately does NOT count toward `done` -- a dropped
 * subtask staying visibly not-done is exactly the `goal_met` evidence
 * the wave-2 adversarial cells need.
 *
 * Imports: only `wire/`. No SDK, no React.
 */

import {
  TodoItemSchema,
  type TodoItem,
  type UIRuntimeEvent,
} from "../wire/ui_runtime_events";

export interface TodoListView {
  readonly todos: ReadonlyArray<TodoItem>;
  readonly done: number;
  readonly total: number;
}

function parseItems(value: unknown): ReadonlyArray<TodoItem> | null {
  if (!Array.isArray(value)) return null;
  const items: TodoItem[] = [];
  for (const raw of value) {
    const parsed = TodoItemSchema.safeParse(raw);
    if (parsed.success) items.push(parsed.data);
  }
  return items;
}

function toView(todos: ReadonlyArray<TodoItem>): TodoListView {
  return {
    todos,
    done: todos.filter((t) => t.status === "completed").length,
    total: todos.length,
  };
}

function todosFromDelta(value: unknown): ReadonlyArray<TodoItem> | null {
  if (!Array.isArray(value)) return null;
  // Last /todos op wins -- state_todo replaces the channel wholesale.
  let found: ReadonlyArray<TodoItem> | null = null;
  for (const op of value) {
    if (
      typeof op === "object" &&
      op !== null &&
      (op as { path?: unknown }).path === "/todos"
    ) {
      const items = parseItems((op as { value?: unknown }).value);
      if (items !== null) found = items;
    }
  }
  return found;
}

function todosFromSnapshot(value: unknown): ReadonlyArray<TodoItem> | null {
  if (typeof value !== "object" || value === null) return null;
  return parseItems((value as { todos?: unknown }).todos);
}

/**
 * Fold one UIRuntimeEvent into the todo view. Non-state events and
 * payloads without a usable `/todos` projection return `prev` unchanged.
 */
export function projectTodoList(
  prev: TodoListView | null,
  evt: UIRuntimeEvent,
): TodoListView | null {
  if (evt.type !== "state_render") return prev;
  const todos =
    evt.key === "delta"
      ? todosFromDelta(evt.value)
      : evt.key === "snapshot"
        ? todosFromSnapshot(evt.value)
        : null;
  if (todos === null) return prev;
  return toView(todos);
}
