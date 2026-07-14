/**
 * D0 — (coach) group-root server layout auth guard (FR-1, FR-2, FR-3).
 *
 * The layout is an RSC that awaits withAuth({ ensureSignedIn: true }) then
 * renders children (the existing 'use client' learn/layout.tsx shell).
 * Unit-tested with a mocked WorkOS SDK — no network.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const withAuth = vi.fn(async () => ({ user: { id: "user_test" } }));

vi.mock("@workos-inc/authkit-nextjs", () => ({
  withAuth: (...args: unknown[]) => withAuth(...args),
}));

describe("CoachGroupLayout — D0 withAuth guard (FR-1/2/3)", () => {
  beforeEach(() => {
    withAuth.mockClear();
    withAuth.mockResolvedValue({ user: { id: "user_test" } });
    // Unit path must exercise the real guard, not the learn-e2e bypass.
    delete process.env.E2E_BYPASS_AUTH;
    vi.resetModules();
  });

  it("awaits withAuth({ ensureSignedIn: true }) before rendering children (FR-1/FR-3)", async () => {
    const { default: CoachGroupLayout } = await import("./layout");
    await CoachGroupLayout({
      children: React.createElement("div", { "data-testid": "shell" }, "ok"),
    });
    expect(withAuth).toHaveBeenCalledTimes(1);
    expect(withAuth).toHaveBeenCalledWith({ ensureSignedIn: true });
  });

  it("renders children for an authenticated user (FR-2)", async () => {
    const { default: CoachGroupLayout } = await import("./layout");
    const element = await CoachGroupLayout({
      children: React.createElement(
        "div",
        { "data-testid": "coach-shell" },
        "shell",
      ),
    });
    const html = renderToStaticMarkup(element as React.ReactElement);
    expect(html).toContain('data-testid="coach-shell"');
    expect(html).toContain("shell");
  });

  it("is the single group-root guard — learn pages do not import withAuth (FR-3)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const learnDir = path.join(__dirname, "learn");
    const pageFiles = [
      "page.tsx",
      "coach/page.tsx",
      "quiz/page.tsx",
      "skill/page.tsx",
      "progress/page.tsx",
      "summary/page.tsx",
      "test/page.tsx",
    ];
    for (const rel of pageFiles) {
      const src = fs.readFileSync(path.join(learnDir, rel), "utf8");
      expect(src, `${rel} must not call withAuth`).not.toMatch(/withAuth/);
    }
    const groupLayout = fs.readFileSync(path.join(__dirname, "layout.tsx"), "utf8");
    expect(groupLayout).toMatch(/withAuth\(\{\s*ensureSignedIn:\s*true\s*\}\)/);
  });
});
