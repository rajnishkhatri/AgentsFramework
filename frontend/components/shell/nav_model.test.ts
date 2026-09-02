/**
 * Phase 1.1 — navigation model (FR-B1/B3/B5, L1 deterministic, TAP-1).
 *
 * Per F-R1 the shell components own NO domain logic: which screens exist, their
 * routes, per-surface visibility (desktop/iPad sidebar vs iPhone 3-tab), the
 * ordered flow-step pills, and which controls are wired vs "coming soon" all
 * live here in a pure, React-free model exercised in node — the analogue of the
 * `openQuizItem`/`runQuizSubmit` split in use_quiz.ts.
 *
 * Failure path first (Anti-Pattern 6): FR-B5 — a nav control with no wired
 * destination must NOT ship as a live link. We assert the invariant "every
 * enabled control has an href" BEFORE the per-surface shape tests, because a
 * dead control is the failure a learner hits (a tap that goes nowhere), and a
 * "coming soon" screen must be surfaced as disabled, never as a live route.
 */

import { describe, expect, it } from "vitest";
import {
  SCREENS,
  COACH_BASE,
  navItemsForSurface,
  flowStepPills,
  focusScreenIds,
  activeScreenId,
  screen,
  type Surface,
} from "./nav_model";

const SURFACES: readonly Surface[] = ["desktop", "ipad", "iphone"];

describe("route tree is anchored under COACH_BASE (no collision with the chat landing)", () => {
  it('never routes any screen to "/" — that path is the chat landing (app/page.tsx)', () => {
    // Regression guard: a screen at "/" would collide with app/page.tsx once its
    // (coach) page.tsx lands (route groups add nothing to the URL) — a Next.js
    // build-time parallel-page error. Every screen route lives under /learn.
    for (const s of SCREENS) {
      expect(s.route, `screen "${s.id}" must not be routed to "/"`).not.toBe("/");
      expect(
        s.route === COACH_BASE || s.route.startsWith(`${COACH_BASE}/`),
        `screen "${s.id}" route ${s.route} must be anchored under ${COACH_BASE}`,
      ).toBe(true);
    }
    expect(COACH_BASE).not.toBe("/");
  });

  it("highlights Dashboard at the base and Quiz at a deeper path (longest-prefix)", () => {
    expect(activeScreenId(COACH_BASE)).toBe("dashboard");
    expect(activeScreenId(`${COACH_BASE}/quiz`)).toBe("quiz");
    expect(activeScreenId(`${COACH_BASE}/quiz/anything`)).toBe("quiz");
    // The site root belongs to the chat app, not any coach screen.
    expect(activeScreenId("/")).toBeNull();
  });
});

describe("FR-B5 no dead controls — every enabled nav control routes", () => {
  it.each(SURFACES)(
    "%s: every ENABLED nav item has a non-empty href; every disabled item is comingSoon",
    (surface) => {
      const items = navItemsForSurface(surface);
      expect(items.length, `${surface} must expose at least one nav item`).toBeGreaterThan(0);
      for (const item of items) {
        if (item.disabled) {
          // A screen without a wired destination ships as an explicit
          // "coming soon" (disabled) control, never as a live link (FR-B5).
          expect(
            item.comingSoon,
            `${surface} item "${item.label}" is disabled but not marked comingSoon`,
          ).toBe(true);
        } else {
          expect(
            item.href.length,
            `${surface} item "${item.label}" is enabled but has no destination (dead control, FR-B5)`,
          ).toBeGreaterThan(0);
          expect(item.href.startsWith("/"), `${item.href} must be an app-absolute route`).toBe(true);
        }
      }
    },
  );

  it("every flow-step pill target is a real, wired screen route (FR-B3/B4)", () => {
    const wiredRoutes = new Set(
      SCREENS.filter((s) => !s.comingSoon).map((s) => s.route),
    );
    const pills = flowStepPills();
    expect(pills.length, "there must be flow-step pills").toBeGreaterThan(0);
    for (const pill of pills) {
      expect(
        wiredRoutes.has(pill.href),
        `pill "${pill.label}" → ${pill.href} is not a wired screen route (FR-B4 dead jump)`,
      ).toBe(true);
    }
  });
});

describe("FR-B3 flow-step pills — numbered, ordered, jump-nav to the five", () => {
  it("emits the five numbered core-loop steps in order", () => {
    const pills = flowStepPills();
    expect(pills.map((p) => p.label)).toEqual([
      "Dashboard",
      "Quiz",
      "Feedback",
      "Coach",
      "Summary",
    ]);
    // Numbered 1..5, contiguous, in order (FR-B3 "1 Dashboard · 2 Quiz · …").
    expect(pills.map((p) => p.step)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe("FR-B1 surface-appropriate global navigation", () => {
  it("E1a FR-20: skill screen is live (not comingSoon) and a sidebar peer on desktop/iPad", () => {
    const skill = screen("skill");
    expect(skill.comingSoon).toBe(false);
    expect(skill.route).toBe("/learn/skill");
    // D-C1: Skill is a persistent sidebar item on the roomy surfaces; iPhone's
    // 4-tab bar omits it (reached via the dashboard bucket→skill link, D-D) —
    // so membership is asserted for desktop/iPad only. Skill stays LIVE (never a
    // dead/coming-soon control) on every surface it appears.
    for (const surface of ["desktop", "ipad"] as const) {
      const items = navItemsForSurface(surface);
      const skillItem = items.find((i) => i.screenId === "skill");
      expect(skillItem, `${surface} must list skill`).toBeDefined();
      expect(skillItem!.disabled).toBe(false);
      expect(skillItem!.href).toBe("/learn/skill");
    }
    // iPhone does NOT surface Skill as a tab (D-C1 parity restore).
    const iphoneSkill = navItemsForSurface("iphone").find(
      (i) => i.screenId === "skill",
    );
    expect(iphoneSkill).toBeUndefined();
  });

  // G8-OK: Epic F flips progress.comingSoon → false with the live page (FR-5).
  it("Epic F FR-5: progress screen is live (not comingSoon) and in membership", () => {
    const progress = screen("progress");
    expect(progress.comingSoon).toBe(false);
    expect(progress.route).toBe("/learn/progress");
    const wiredRoutes = SCREENS.filter((s) => !s.comingSoon).map((s) => s.route);
    expect(wiredRoutes).toContain("/learn/progress");
    for (const surface of SURFACES) {
      const items = navItemsForSurface(surface);
      const progressItem = items.find((i) => i.screenId === "progress");
      expect(progressItem, `${surface} must list progress`).toBeDefined();
      expect(progressItem!.disabled).toBe(false);
      expect(progressItem!.href).toBe("/learn/progress");
    }
  });
  it("iPhone bottom bar matches the prototype: Home / Practice / Coach / Progress", () => {
    // D-C1 (parity-review): the prototype's iPhone tab bar keeps Coach as a
    // persistent tab and does NOT surface Skill — Skill detail is reached on
    // iPhone via the dashboard bucket→skill link (D-D), not a bottom tab. This
    // reverts the earlier Skill-for-Coach swap that cited a fabricated "§8.1".
    const iphoneLabels = navItemsForSurface("iphone").map((i) => i.label);
    expect(iphoneLabels).toEqual(["Home", "Practice", "Coach", "Progress"]);
    expect(iphoneLabels).not.toContain("Skill");

    for (const surface of ["desktop", "ipad"] as const) {
      const labels = navItemsForSurface(surface).map((i) => i.label);
      expect(labels, `${surface} sidebar must include Coach as a peer`).toContain("Coach");
      // Sidebar model: Home / Practice / Coach / Skill / Progress (E1a FR-20).
      expect(labels).toEqual(["Home", "Practice", "Coach", "Skill", "Progress", "Exam"]);
    }
  });

  it("S-D4: exam screen is live and reachable from desktop/iPad nav", () => {
    const exam = screen("exam");
    expect(exam.comingSoon).toBe(false);
    expect(exam.route).toBe("/learn/exam");
    expect(exam.isFocusScreen).toBe(true);
    expect(activeScreenId("/learn/exam")).toBe("exam");
    expect(activeScreenId("/learn/exam/run-1/english")).toBe("exam");
    for (const surface of ["desktop", "ipad"] as const) {
      const item = navItemsForSurface(surface).find((i) => i.screenId === "exam");
      expect(item, `${surface} must list exam`).toBeDefined();
      expect(item!.disabled).toBe(false);
      expect(item!.href).toBe("/learn/exam");
    }
  });

  it("iPhone focus screens (Quiz/Feedback/Coach/Summary) drive the tab-hide rule (FR-B2)", () => {
    // The set the shell hides the bottom tab bar for. Dashboard/Progress are NOT
    // focus screens (tabs stay visible there).
    const focus = new Set(focusScreenIds());
    expect(focus.has("quiz")).toBe(true);
    expect(focus.has("feedback")).toBe(true);
    expect(focus.has("coach")).toBe(true);
    expect(focus.has("summary")).toBe(true);
    expect(focus.has("dashboard")).toBe(false);
    expect(focus.has("progress")).toBe(false);
  });
});
