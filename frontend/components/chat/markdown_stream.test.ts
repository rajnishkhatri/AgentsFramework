/**
 * stabilizeStreamingMarkdown tests (eval-UI F4).
 *
 * Failure path first: a fence left dangling mid-stream must not flash
 * raw backticks / swallow subsequent text -- it is closed for the
 * in-flight render and the next delta re-parses the full text.
 */

import { describe, expect, it } from "vitest";
import { stabilizeStreamingMarkdown } from "./markdown_stream";

describe("stabilizeStreamingMarkdown — failure paths first", () => {
  it("closes a dangling fenced code block", () => {
    const input = "Here:\n```python\nprint('hi')\n";
    expect(stabilizeStreamingMarkdown(input)).toBe(
      "Here:\n```python\nprint('hi')\n```",
    );
  });

  it("closes a dangling fence that ends mid-line", () => {
    const input = "```js\nconst x = 1";
    expect(stabilizeStreamingMarkdown(input)).toBe("```js\nconst x = 1\n```");
  });

  it("empty input stays empty", () => {
    expect(stabilizeStreamingMarkdown("")).toBe("");
  });
});

describe("stabilizeStreamingMarkdown — stability", () => {
  it("balanced fences are left untouched", () => {
    const input = "```sh\nls\n```\nafter";
    expect(stabilizeStreamingMarkdown(input)).toBe(input);
  });

  it("inline backticks are not fences", () => {
    const input = "use `map` here";
    expect(stabilizeStreamingMarkdown(input)).toBe(input);
  });

  it("two complete blocks stay untouched", () => {
    const input = "```a\nx\n```\nmid\n```b\ny\n```";
    expect(stabilizeStreamingMarkdown(input)).toBe(input);
  });

  it("plain prose passes through unchanged", () => {
    const input = "# Title\n\n- one\n- two";
    expect(stabilizeStreamingMarkdown(input)).toBe(input);
  });
});
