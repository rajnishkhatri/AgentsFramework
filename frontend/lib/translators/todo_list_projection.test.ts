/**
 * todo_list_projection tests (eval-UI F9, plan §8 F9 / §8.6-A).
 *
 * Failure paths first (TAP-4): malformed deltas are ignored (never
 * crash), unknown statuses rejected, cancelled is NOT done -- before the
 * happy path. Driven with the real shapes `state_todo` emits
 * (services/tools/todo_tools.py: state_delta={"todos":[...]}) as carried
 * by wire StateDelta JSON-Patch replace ops.
 */

import { describe, expect, it } from "vitest";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";
import { projectTodoList, type TodoListView } from "./todo_list_projection";

const TRACE = "trace-todo-1";

function deltaRender(value: unknown): UIRuntimeEvent {
  return {
    type: "state_render",
    trace_id: TRACE,
    key: "delta",
    value,
  };
}

function todos(...statuses: string[]): unknown[] {
  return statuses.map((status, i) => ({
    id: `t${i + 1}`,
    content: `task ${i + 1}`,
    status,
  }));
}

function replaceOp(value: unknown): unknown[] {
  return [{ op: "replace", path: "/todos", value }];
}

describe("projectTodoList — failure paths first", () => {
  it("ignores a non-array delta payload (no crash, view unchanged)", () => {
    expect(projectTodoList(null, deltaRender("garbage"))).toBeNull();
    expect(projectTodoList(null, deltaRender({ op: "replace" }))).toBeNull();
  });

  it("ignores ops that do not target /todos", () => {
    const evt = deltaRender([{ op: "replace", path: "/plan_ref", value: "p" }]);
    expect(projectTodoList(null, evt)).toBeNull();
  });

  it("ignores a /todos op whose value is not an array", () => {
    const evt = deltaRender(replaceOp({ not: "a list" }));
    expect(projectTodoList(null, evt)).toBeNull();
  });

  it("drops malformed items but keeps valid ones", () => {
    const evt = deltaRender(
      replaceOp([
        { id: "t1", content: "good", status: "pending" },
        { id: "t2", status: "pending" }, // missing content
        { id: "t3", content: "bad status", status: "exploded" },
      ]),
    );
    const view = projectTodoList(null, evt);
    expect(view?.todos.map((t) => t.id)).toEqual(["t1"]);
  });

  it("cancelled items are NOT counted as done (subtask-dropped evidence)", () => {
    const evt = deltaRender(replaceOp(todos("completed", "cancelled", "pending")));
    const view = projectTodoList(null, evt);
    expect(view?.done).toBe(1);
    expect(view?.total).toBe(3);
  });

  it("non-state events leave the view untouched", () => {
    const prev: TodoListView = { todos: [], done: 0, total: 0 };
    const out = projectTodoList(prev, {
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "x",
    });
    expect(out).toBe(prev);
  });
});

describe("projectTodoList — happy path", () => {
  it("projects a /todos replace op into a typed checklist view", () => {
    const evt = deltaRender(replaceOp(todos("pending", "in_progress")));
    const view = projectTodoList(null, evt);
    expect(view?.todos).toEqual([
      { id: "t1", content: "task 1", status: "pending" },
      { id: "t2", content: "task 2", status: "in_progress" },
    ]);
    expect(view?.done).toBe(0);
    expect(view?.total).toBe(2);
  });

  it("a later delta replaces the list wholesale (state_todo semantics)", () => {
    const v1 = projectTodoList(null, deltaRender(replaceOp(todos("pending", "pending"))));
    const v2 = projectTodoList(
      v1,
      deltaRender(replaceOp(todos("completed", "completed"))),
    );
    expect(v2?.done).toBe(2);
  });

  it("projects a snapshot render carrying todos", () => {
    const view = projectTodoList(null, {
      type: "state_render",
      trace_id: TRACE,
      key: "snapshot",
      value: { todos: todos("completed"), plan_ref: "" },
    });
    expect(view?.total).toBe(1);
    expect(view?.done).toBe(1);
  });
});
