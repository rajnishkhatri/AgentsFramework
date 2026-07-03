/**
 * Seeded test-form assembler (Phase 6 — ADR-0013 §8.2 / ADR-0015, FR-26/27).
 *
 * A PURE, offline, client-side engine function: `(blueprint, bank_rows)` → a
 * deterministic form. No I/O, no clock, no SDK — the sibling of the pure
 * `grader/` (the engine plane's other pure-function home). Determinism holds by
 * construction:
 *   - the reviewed bank is filtered (FR-27.1 assembler-layer gate — independent
 *     of the repo-level gate) then sorted by content-hash `id`, so the draw
 *     never depends on query order (FR-26.2);
 *   - a seeded PRNG (mulberry32 over the blueprint `seed`) drives a
 *     Fisher–Yates shuffle per skill stratum, so a fixed seed over a frozen
 *     bank yields a byte-identical form, and a different seed yields a
 *     different one (FR-26.3);
 *   - a stratum short of its required count fails closed with the named skill
 *     (FR-26.1) — never a short, padded, or silently re-stratified form.
 *
 * Scope (ADR-0015): the assembler produces a form object; it does NOT serve it
 * into `/learn/test` (that fires ADR-0013's delivery tripwire). The difficulty
 * distribution is carried on the blueprint but not yet a draw axis — the bank
 * is single-difficulty today; a difficulty split lands with a multi-difficulty
 * bank (build-on-the-second-consumer).
 */

import type { TestBlueprint, TestItem } from "../../../wire/engine_entities";

/** A short stratum: the reviewed bank cannot satisfy a skill's required count. */
export class ShortStratumError extends Error {
  constructor(
    readonly skillId: string,
    readonly need: number,
    readonly have: number,
  ) {
    super(
      `test-form assembly failed: skill '${skillId}' needs ${need} reviewed ` +
        `item(s), bank has ${have}`,
    );
    this.name = "ShortStratumError";
  }
}

export interface AssembledForm {
  readonly blueprint_id: string;
  readonly seed: number;
  readonly items: readonly TestItem[];
}

/** mulberry32 — a tiny, fast, deterministic 32-bit PRNG. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** In-place Fisher–Yates over `rng`; returns the same array for chaining. */
function shuffle<T>(rows: T[], rng: () => number): T[] {
  for (let i = rows.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [rows[i], rows[j]] = [rows[j]!, rows[i]!];
  }
  return rows;
}

/**
 * Split the blueprint `count` across skills by `skill_mix` weights. Largest-
 * remainder rounding keeps the parts summing to exactly `count` (never a form
 * off-by-one from independent per-skill rounding). Deterministic tie-break by
 * skill id so the split itself never depends on object key order.
 */
function stratumCounts(
  count: number,
  skillMix: Record<string, number>,
): Map<string, number> {
  const skills = Object.keys(skillMix).sort();
  const raw = skills.map((s) => ({ skill: s, exact: count * (skillMix[s] ?? 0) }));
  const floors = raw.map((r) => ({ skill: r.skill, n: Math.floor(r.exact), frac: r.exact - Math.floor(r.exact) }));
  let assigned = floors.reduce((a, f) => a + f.n, 0);
  // Hand out the remaining units to the largest fractional remainders.
  const byFrac = [...floors].sort((a, b) => b.frac - a.frac || a.skill.localeCompare(b.skill));
  let idx = 0;
  while (assigned < count && byFrac.length > 0) {
    byFrac[idx % byFrac.length]!.n += 1;
    assigned += 1;
    idx += 1;
  }
  return new Map(floors.map((f) => [f.skill, f.n]));
}

export function assembleTestForm(
  blueprint: TestBlueprint,
  bankRows: readonly TestItem[],
): AssembledForm {
  // FR-27.1 assembler-layer filter (independent of the repo gate) + sort by id
  // so the draw is order-insensitive (FR-26.2).
  const reviewed = bankRows
    .filter((i) => i.reviewed === true && i.subject === blueprint.subject)
    .slice()
    .sort((a, b) => a.id.localeCompare(b.id));

  const bySkill = new Map<string, TestItem[]>();
  for (const it of reviewed) {
    (bySkill.get(it.skill_id) ?? bySkill.set(it.skill_id, []).get(it.skill_id)!).push(it);
  }

  const needs = stratumCounts(blueprint.count, blueprint.skill_mix);
  const rng = mulberry32(blueprint.seed);
  const picked: TestItem[] = [];

  // Deterministic stratum order (sorted skill ids) so the PRNG stream is
  // consumed in a fixed order regardless of skill_mix key order.
  for (const skill of [...needs.keys()].sort()) {
    const need = needs.get(skill) ?? 0;
    if (need === 0) continue;
    const pool = bySkill.get(skill) ?? [];
    if (pool.length < need) {
      throw new ShortStratumError(skill, need, pool.length);
    }
    // Shuffle a copy (pool is already id-sorted) and take the first `need`.
    const drawn = shuffle(pool.slice(), rng).slice(0, need);
    picked.push(...drawn);
  }

  // Stable final order: by skill then id, so the form itself is byte-stable and
  // independent of stratum iteration timing.
  picked.sort((a, b) => a.skill_id.localeCompare(b.skill_id) || a.id.localeCompare(b.id));

  return { blueprint_id: blueprint.id, seed: blueprint.seed, items: picked };
}
