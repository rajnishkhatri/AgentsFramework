import { describe, it, expect } from "vitest";
import { isNearBottom, THRESHOLD_PX } from "./use_stick_to_bottom";

describe("isNearBottom", () => {
  it("is true when scrolled exactly to the bottom", () => {
    // scrollHeight - scrollTop - clientHeight === 0
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 600, clientHeight: 400 })).toBe(true);
  });

  it("is true within the threshold slack", () => {
    // 1000 - 540 - 400 = 60 <= 80
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 540, clientHeight: 400 })).toBe(true);
  });

  it("is false past the threshold", () => {
    // 1000 - 400 - 400 = 200 > 80
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 400, clientHeight: 400 })).toBe(false);
  });

  it("is true at the exact threshold boundary", () => {
    expect(
      isNearBottom({ scrollHeight: 1000, scrollTop: 600 - THRESHOLD_PX, clientHeight: 400 }),
    ).toBe(true);
  });

  it("honors a custom threshold", () => {
    const el = { scrollHeight: 1000, scrollTop: 560, clientHeight: 400 }; // gap = 40
    expect(isNearBottom(el, 20)).toBe(false);
    expect(isNearBottom(el, 50)).toBe(true);
  });

  it("treats a short non-scrolling container as at-bottom", () => {
    // content fits: scrollHeight === clientHeight, scrollTop 0 → gap 0
    expect(isNearBottom({ scrollHeight: 300, scrollTop: 0, clientHeight: 300 })).toBe(true);
  });
});
