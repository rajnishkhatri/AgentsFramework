/**
 * FR-3 + FR-6 + FR-8 — cross-learner isolation, no live-page Garvit LEARNER_ID,
 * honest empty dashboard slate.
 */

import { describe, expect, it } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import { loadDashboard } from "@/components/dashboard/use_dashboard";
import {
  DEFAULT_SUBJECT,
  type Skill,
  type SkillState,
} from "@/lib/wire/engine_entities";

function state(
  learnerId: string,
  skillId: string,
  mastery: number,
): SkillState {
  return {
    subject: DEFAULT_SUBJECT,
    skill_id: skillId,
    learner_id: learnerId,
    mastery,
    last_seen: null,
    fsrs_stability: 1,
    fsrs_difficulty: 5,
    due_at: "2026-07-01T12:00:00.000Z",
    fsrs_card: null,
  };
}

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punc",
    subject: DEFAULT_SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 15,
    accent_var: "--color-bucket-punctuation",
    description: "…",
    order: 1,
    ...over,
  };
}

describe("FR-3 cross-learner skill_state isolation", () => {
  it("reads for learner B never return learner A's mastery", async () => {
    const db = new InMemoryEngineDb();
    db.seedSkillStates([
      state("user_a", "s-punc", 0.28),
      state("user_b", "s-punc", 0.9),
    ]);
    const a = await db.listSkillState(DEFAULT_SUBJECT, "user_a");
    const b = await db.listSkillState(DEFAULT_SUBJECT, "user_b");
    expect(a).toHaveLength(1);
    expect(a[0]!.mastery).toBe(0.28);
    expect(b).toHaveLength(1);
    expect(b[0]!.mastery).toBe(0.9);
    expect(b.every((s) => s.learner_id === "user_b")).toBe(true);
    expect(a.every((s) => s.learner_id !== "user_b")).toBe(true);
  });
});

describe("FR-6 no live-page Garvit LEARNER_ID constants", () => {
  it("rg: zero LEARNER_ID / LEARNER_DISPLAY_NAME = Garvit under (coach)/learn", () => {
    const learnRoot = path.join(__dirname, "../../app/(coach)/learn");
    function walk(dir: string): string[] {
      const out: string[] = [];
      for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, ent.name);
        if (ent.isDirectory()) out.push(...walk(full));
        else if (ent.name.endsWith(".tsx") || ent.name.endsWith(".ts")) {
          out.push(full);
        }
      }
      return out;
    }
    const files = walk(learnRoot);
    expect(files.length).toBeGreaterThan(0);
    const re = /LEARNER_ID\s*=\s*"Garvit"|LEARNER_DISPLAY_NAME\s*=\s*"Garvit"/;
    for (const f of files) {
      const src = fs.readFileSync(f, "utf8");
      expect(src, path.relative(learnRoot, f)).not.toMatch(re);
    }
  });
});

describe("FR-8 honest empty slate", () => {
  it("empty skill states → no fabricated 28% punctuation focus", async () => {
    const db = new InMemoryEngineDb();
    db.seedSkills([
      skill({ id: "s-punc", name: "Punctuation" }),
      skill({
        id: "s-gram",
        key: "grammar",
        name: "Usage",
        order: 2,
        accent_var: "--color-bucket-usage",
      }),
    ]);
    const ports = buildBrowserEngineAdapters({ engineDb: db });
    const vm = await loadDashboard(ports, {
      subject: DEFAULT_SUBJECT,
      learnerId: "user_workos_1",
      displayName: "Rajnish",
      nowISO: "2026-07-01T12:00:00.000Z",
    });
    expect(vm.todayFocus.present).toBe(false);
    expect(vm.greeting.headline).not.toContain("Garvit");
    const punc = vm.buckets.find((b) => b.skillId === "s-punc");
    expect(punc?.masteryKnown).toBe(false);
  });
});
