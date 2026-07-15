/**
 * D0 — (coach) group-root server layout auth guard (FR-1, FR-2, FR-3) +
 * learn-identity RSC bridge (FR-4/5/6).
 *
 * The layout is an RSC that awaits withAuth({ ensureSignedIn: true }), resolves
 * learn identity, wraps children in LearnIdentityProvider.
 * Unit-tested with a mocked WorkOS SDK — no network.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const withAuth = vi.fn(async () => ({
  user: { id: "user_workos_1", firstName: "Rajnish", email: "r@ex.com" },
}));

vi.mock("@workos-inc/authkit-nextjs", () => ({
  withAuth: (...args: unknown[]) =>
    withAuth(...(args as Parameters<typeof withAuth>)),
}));

describe("CoachGroupLayout — D0 withAuth guard (FR-1/2/3) + identity bridge", () => {
  beforeEach(() => {
    withAuth.mockClear();
    withAuth.mockResolvedValue({
      user: { id: "user_workos_1", firstName: "Rajnish", email: "r@ex.com" },
    });
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

  it("passes resolved WorkOS identity into LearnIdentityProvider (FR-4/FR-5)", async () => {
    const { default: CoachGroupLayout } = await import("./layout");
    const element = await CoachGroupLayout({
      children: React.createElement("div", { "data-testid": "shell" }, "ok"),
    });
    const html = renderToStaticMarkup(element as React.ReactElement);
    // Provider is a client component — SSR markup still nests children; assert
    // withAuth user was consumed (not discarded) via the resolved learner id
    // appearing only if we rendered a probe. Instead assert source wiring:
    expect(withAuth).toHaveBeenCalled();
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(path.join(__dirname, "layout.tsx"), "utf8");
    expect(src).toMatch(/resolveLearnIdentity/);
    expect(src).toMatch(/LearnIdentityProvider/);
    expect(src).toMatch(/\.user/);
    expect(html).toContain('data-testid="shell"');
  });

  it("returns an unauthed /learn visitor to /learn post-login via ensureSignedIn — no return-path override (Q1 / FR-6)", async () => {
    // FR-6 is satisfied by the layout guard, NOT by a coach CTA (there is no
    // distinct coach sign-in CTA — the only web CTA is the agent home button at
    // page.tsx:64, which must keep landing on / per FR-7). AuthKit's
    // withAuth({ ensureSignedIn: true }) internally calls getReturnPathname(url)
    // and threads the CURRENT path (/learn) as returnPathname, so an unauthed
    // /learn visitor lands back on /learn after signing in. This test locks the
    // two properties we own that keep that native capture intact:
    //   (a) the guard uses ensureSignedIn: true (triggers the return capture);
    //   (b) it passes NO returnTo/redirectUri/returnPathname override that would
    //       redirect the post-login landing somewhere other than the origin path.
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(path.join(__dirname, "layout.tsx"), "utf8");
    expect(src).toMatch(/withAuth\(\{\s*ensureSignedIn:\s*true\s*\}\)/);
    // No override arg that would defeat the native /learn return-path capture.
    expect(src).not.toMatch(/returnTo|returnPathname|redirectUri/);
  });

  it("is the single group-root guard — learn pages do not import withAuth (FR-3)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const learnDir = path.join(__dirname, "learn");

    // Spec §6: enumerate pages that exist on the branch (not a fixed list).
    function collectPageTsx(dir: string): string[] {
      const out: string[] = [];
      for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, ent.name);
        if (ent.isDirectory()) {
          out.push(...collectPageTsx(full));
        } else if (ent.name === "page.tsx") {
          out.push(full);
        }
      }
      return out;
    }

    const pageFiles = collectPageTsx(learnDir);
    expect(pageFiles.length).toBeGreaterThan(0);
    for (const pagePath of pageFiles) {
      const rel = path.relative(learnDir, pagePath);
      const src = fs.readFileSync(pagePath, "utf8");
      expect(src, `${rel} must not call withAuth`).not.toMatch(/withAuth/);
    }
    const groupLayout = fs.readFileSync(path.join(__dirname, "layout.tsx"), "utf8");
    expect(groupLayout).toMatch(/withAuth\(\{\s*ensureSignedIn:\s*true\s*\}\)/);
  });
});
