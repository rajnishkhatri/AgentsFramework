/**
 * Engine port conformance suite (ADR-0006; sibling of test_port_conformance).
 *
 * The eight Subject-Coach engine ports (7 ADR-0006 + `LearnerReadRepo`,
 * ADR-0011) live under `lib/ports/engine/` rather
 * than flat in `lib/ports/` so the engine bounded context is separate from the
 * eight V3 chat ports and the flat-dir chat gate stays untouched. This suite is
 * the P7 pairing for the engine ports and enforces the same structural rules:
 *
 *   P1  One interface per file
 *   P2  Vendor-neutral name (no SDK acronyms — no "Drizzle", "Fsrs", "Sqlite")
 *   P3  Behavioral contract documented in JSDoc
 *   P5  Async by default (Promise<...>) unless a sync exception is declared
 *   P6  No imports from adapters/, translators/, transport/, composition.ts
 *
 * `errors.ts` and `index.ts` are ports-local helper modules, not interface
 * files, and are excluded from the interface checks.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import { Project, type SourceFile, SyntaxKind } from "ts-morph";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const ENGINE_PORTS_DIR = path.join(FRONTEND_ROOT, "lib", "ports", "engine");

// Non-interface helper modules under ports/engine/ — skipped by interface checks.
const NON_PORT_FILES = new Set(["errors.ts", "index.ts"]);

// The nine engine ports (7 ADR-0006 + LearnerReadRepo, ADR-0011 + HintRepo,
// ADR-0014). Adding a port without a row here is a P7 violation (port ->
// conformance pairing).
const REQUIRED_PORTS: ReadonlyArray<{
  file: string;
  interfaceName: string;
  syncJustification?: string;
}> = [
  { file: "skill_taxonomy.ts", interfaceName: "SkillTaxonomy" },
  { file: "question_repo.ts", interfaceName: "QuestionRepo" },
  { file: "attempt_repo.ts", interfaceName: "AttemptRepo" },
  { file: "session_repo.ts", interfaceName: "SessionRepo" },
  { file: "scheduler.ts", interfaceName: "Scheduler" },
  {
    file: "grader.ts",
    interfaceName: "Grader",
    syncJustification:
      "Grader is pure/deterministic and called inline at feedback time and on the generation self-consistency gate; sync return is the documented P5 exception (FR-C2).",
  },
  { file: "content_repo.ts", interfaceName: "ContentRepo" },
  // ADR-0011: read-only skill_state port that unblocks Dashboard mastery
  // (FR-C3) + Summary delta (FR-G1) without the UI touching the EngineDb seam.
  { file: "learner_read_repo.ts", interfaceName: "LearnerReadRepo" },
  // ADR-0014: read-only hint-ladder seam (reviewed=true rungs only, FR-12/20).
  { file: "hint_repo.ts", interfaceName: "HintRepo" },
  // ADR-0015: read-only test-blueprint seam (10th port).
  { file: "test_blueprint_repo.ts", interfaceName: "TestBlueprintRepo" },
  // ADR-0015: read-only test-item seam (11th, reviewed=true only, FR-27.1).
  { file: "test_item_repo.ts", interfaceName: "TestItemRepo" },
];

// Vendor acronyms a port name must never contain (P2).
const VENDOR_TOKENS = [/drizzle/i, /sqlite/i, /\bpg\b/i, /neon/i, /fsrs/i, /tsfsrs/i];

const FORBIDDEN_RING_PREFIXES = [
  "../../adapters/",
  "../../translators/",
  "../../transport/",
  "../../composition",
  "@/lib/adapters/",
  "@/lib/translators/",
  "@/lib/transport/",
  "@/lib/composition",
];

function project(): Project {
  return new Project({
    tsConfigFilePath: path.join(FRONTEND_ROOT, "tsconfig.json"),
    skipAddingFilesFromTsConfig: false,
  });
}

function findInterface(sf: SourceFile, name: string) {
  return sf.getInterface(name);
}

describe("Engine port conformance suite [ADR-0006 / P7]", () => {
  it("ports/engine/ contains exactly the eleven engine ports (+ helper modules)", () => {
    expect(fs.existsSync(ENGINE_PORTS_DIR), `${ENGINE_PORTS_DIR} must exist`).toBe(true);
    const interfaceFiles = fs
      .readdirSync(ENGINE_PORTS_DIR)
      .filter(
        (f) =>
          f.endsWith(".ts") &&
          !f.endsWith(".test.ts") &&
          !NON_PORT_FILES.has(f),
      );
    const required = new Set(REQUIRED_PORTS.map((p) => p.file));
    expect(new Set(interfaceFiles), "mismatch in ports/engine/").toEqual(required);
  });

  it.each(REQUIRED_PORTS)(
    "$file exports a single interface named $interfaceName [P1]",
    ({ file, interfaceName }) => {
      const proj = project();
      const fp = path.join(ENGINE_PORTS_DIR, file);
      const sf = proj.getSourceFile(fp);
      expect(sf, `expected ts-morph to load ${fp}`).toBeTruthy();
      const exportedInterfaces = sf!.getInterfaces().filter((i) => i.isExported());
      expect(exportedInterfaces, "exactly one exported interface").toHaveLength(1);
      expect(exportedInterfaces[0]!.getName()).toBe(interfaceName);
    },
  );

  it.each(REQUIRED_PORTS)(
    "$interfaceName has a vendor-neutral name [P2]",
    ({ interfaceName }) => {
      for (const tok of VENDOR_TOKENS) {
        expect(
          tok.test(interfaceName),
          `${interfaceName} must not contain a vendor token (${tok})`,
        ).toBe(false);
      }
    },
  );

  it.each(REQUIRED_PORTS)(
    "$interfaceName documents its behavioral contract in JSDoc [P3]",
    ({ file, interfaceName }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(ENGINE_PORTS_DIR, file))!;
      const iface = findInterface(sf, interfaceName)!;
      const doc = iface.getJsDocs().map((d) => d.getInnerText()).join("\n");
      expect(doc.length, `${interfaceName} requires JSDoc`).toBeGreaterThan(40);
    },
  );

  it.each(REQUIRED_PORTS)(
    "$interfaceName uses Promise<...> by default unless explicitly justified [P5]",
    ({ file, interfaceName, syncJustification }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(ENGINE_PORTS_DIR, file))!;
      const iface = findInterface(sf, interfaceName)!;

      let syncMethod = false;
      for (const member of iface.getMembers()) {
        if (member.getKind() === SyntaxKind.MethodSignature) {
          const ms = member.asKindOrThrow(SyntaxKind.MethodSignature);
          const ret = ms.getReturnType().getText();
          if (!ret.includes("Promise<") && !ret.includes("AsyncIterable<")) {
            syncMethod = true;
            break;
          }
        }
      }

      if (syncMethod) {
        expect(
          syncJustification,
          `${interfaceName} has a sync method but P5 exception not declared in REQUIRED_PORTS`,
        ).toBeTruthy();
        const doc = iface.getJsDocs().map((d) => d.getInnerText()).join(" ");
        expect(
          /sync|synchronous|render time|render-time|pure|P5/i.test(doc),
          `${interfaceName} JSDoc must mention the sync exception`,
        ).toBe(true);
      }
    },
  );

  it.each(REQUIRED_PORTS)(
    "$file does not import from adapters/, translators/, transport/, or composition [P6]",
    ({ file }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(ENGINE_PORTS_DIR, file))!;
      const offenders: string[] = [];
      for (const decl of sf.getImportDeclarations()) {
        const spec = decl.getModuleSpecifierValue();
        if (FORBIDDEN_RING_PREFIXES.some((p) => spec.startsWith(p))) {
          offenders.push(spec);
        }
      }
      expect(offenders, `${file} imports forbidden ring`).toEqual([]);
    },
  );

  it.each(REQUIRED_PORTS)(
    "$file imports only zod, wire/, trust-view/ + ports-local helpers [P6]",
    ({ file }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(ENGINE_PORTS_DIR, file))!;
      const allowedExternal = new Set(["zod"]);
      const offenders: string[] = [];
      for (const decl of sf.getImportDeclarations()) {
        const spec = decl.getModuleSpecifierValue();
        if (spec.startsWith("node:")) continue;
        if (allowedExternal.has(spec)) continue;
        if (
          spec.startsWith("../../wire/") ||
          spec.startsWith("../../trust-view/") ||
          spec.startsWith("@/lib/wire/") ||
          spec.startsWith("@/lib/trust-view/")
        ) {
          continue;
        }
        // relative imports inside ports/engine/ are fine (shared error types).
        if (spec.startsWith("./")) continue;
        offenders.push(spec);
      }
      expect(offenders, `${file} imports outside allowed surface`).toEqual([]);
    },
  );

  // ADR-0011: LearnerReadRepo is a READ port — the Scheduler stays the sole
  // skill_state writer (FR-A2). Enforce read-only by construction: no method
  // name uses a write verb, and no method returns void/Promise<void> (a mutation
  // shape). This is the port-level half of the compiler-enforced ReadableEngineDb
  // projection the adapter depends on.
  it("LearnerReadRepo exposes only read methods (no write verbs) [ADR-0011 P/FR-A2]", () => {
    const proj = project();
    const sf = proj.getSourceFile(
      path.join(ENGINE_PORTS_DIR, "learner_read_repo.ts"),
    )!;
    const iface = findInterface(sf, "LearnerReadRepo")!;
    const WRITE_VERB =
      /^(upsert|insert|update|delete|patch|write|save|set|record|remove|review|seed|put|create|mutate|clear|append|merge|reset|mark|flag)/i;
    for (const member of iface.getMembers()) {
      if (member.getKind() !== SyntaxKind.MethodSignature) continue;
      const ms = member.asKindOrThrow(SyntaxKind.MethodSignature);
      const name = ms.getName();
      expect(
        WRITE_VERB.test(name),
        `LearnerReadRepo.${name} looks like a write; the read port must not mutate skill_state`,
      ).toBe(false);
      const ret = ms.getReturnType().getText();
      expect(
        /Promise<void>|(^|\W)void(\W|$)/.test(ret),
        `LearnerReadRepo.${name} returns a mutation shape (${ret}); read methods must return data`,
      ).toBe(false);
    }
  });
});
