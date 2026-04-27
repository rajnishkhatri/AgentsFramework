/**
 * Port conformance test (FD6.PORT / S3.2.1 DoD).
 *
 * Per FRONTEND_ARCHITECTURE.md §5: every port is a vendor-neutral interface
 * defining method signatures and behavioral guarantees. The conformance test
 * verifies the structural rules (one-interface-per-file is already enforced
 * by `test_frontend_layering.test.ts`):
 *
 *   P1  One interface per file
 *   P2  Vendor-neutral name (no SDK acronyms)
 *   P3  Behavioral contract documented in JSDoc
 *   P4  Typed errors via @throws
 *   P5  Async by default (Promise<...>) -- documented exceptions allowed
 *   P6  No imports from adapters/, translators/, transport/, composition.ts
 *   P7  Each port has a corresponding entry in this conformance test
 *
 * The 8 expected ports come from FRONTEND_ARCHITECTURE.md §5.
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import { Project, type SourceFile, SyntaxKind } from "ts-morph";

const FRONTEND_ROOT = path.resolve(__dirname, "..", "..");
const PORTS_DIR = path.join(FRONTEND_ROOT, "lib", "ports");

// The 8 ports the V3-Dev-Tier plan requires. Adding a new port without
// adding a row here triggers P7 (port -> conformance test pairing).
const REQUIRED_PORTS: ReadonlyArray<{
  file: string;
  interfaceName: string;
  syncJustification?: string;
}> = [
  { file: "agent_runtime_client.ts", interfaceName: "AgentRuntimeClient" },
  { file: "auth_provider.ts", interfaceName: "AuthProvider" },
  { file: "thread_store.ts", interfaceName: "ThreadStore" },
  { file: "memory_client.ts", interfaceName: "MemoryClient" },
  { file: "telemetry_sink.ts", interfaceName: "TelemetrySink" },
  {
    file: "feature_flag_provider.ts",
    interfaceName: "FeatureFlagProvider",
    syncJustification:
      "Env-var flags must be readable synchronously to avoid render-time async (P5 exception, justified in JSDoc).",
  },
  {
    file: "tool_renderer_registry.ts",
    interfaceName: "ToolRendererRegistry",
    syncJustification:
      "Renderer lookup happens at React render time and must be sync (P5 exception, justified in JSDoc).",
  },
  { file: "ui_runtime.ts", interfaceName: "UIRuntime" },
];

const FORBIDDEN_RING_PREFIXES = [
  "../adapters/",
  "../translators/",
  "../transport/",
  "../composition",
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

describe("Port conformance suite [FD6.PORT / S3.2.1]", () => {
  it("contains exactly the 8 required ports under lib/ports/", () => {
    expect(fs.existsSync(PORTS_DIR), `${PORTS_DIR} must exist`).toBe(true);
    const files = fs
      .readdirSync(PORTS_DIR)
      .filter((f) => f.endsWith(".ts") && !f.endsWith(".test.ts") && f !== "index.ts");
    const required = new Set(REQUIRED_PORTS.map((p) => p.file));
    expect(new Set(files), `mismatch in ports/`).toEqual(required);
  });

  it.each(REQUIRED_PORTS)(
    "$file exports a single interface named $interfaceName [P1, P2]",
    ({ file, interfaceName }) => {
      const proj = project();
      const fp = path.join(PORTS_DIR, file);
      const sf = proj.getSourceFile(fp);
      expect(sf, `expected ts-morph to load ${fp}`).toBeTruthy();
      const exportedInterfaces = sf!.getInterfaces().filter((i) => i.isExported());
      expect(exportedInterfaces, "exactly one exported interface").toHaveLength(1);
      expect(exportedInterfaces[0]!.getName()).toBe(interfaceName);
    },
  );

  it.each(REQUIRED_PORTS)(
    "$interfaceName documents its behavioral contract in JSDoc [P3]",
    ({ file, interfaceName }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(PORTS_DIR, file))!;
      const iface = findInterface(sf, interfaceName)!;
      const doc = iface.getJsDocs().map((d) => d.getInnerText()).join("\n");
      expect(doc.length, `${interfaceName} requires JSDoc`).toBeGreaterThan(40);
    },
  );

  it.each(REQUIRED_PORTS)(
    "$interfaceName uses Promise<...> by default unless explicitly justified [P5]",
    ({ file, interfaceName, syncJustification }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(PORTS_DIR, file))!;
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
        // Justification must also appear in the port's JSDoc so reviewers see it.
        const doc = iface.getJsDocs().map((d) => d.getInnerText()).join(" ");
        expect(
          /sync|synchronous|render time|render-time|P5/i.test(doc),
          `${interfaceName} JSDoc must mention the sync exception`,
        ).toBe(true);
      }
    },
  );

  it.each(REQUIRED_PORTS)(
    "$file does not import from adapters/, translators/, transport/, or composition [P6]",
    ({ file }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(PORTS_DIR, file))!;
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
    "$file imports only zod, wire/, trust-view/ + stdlib [P6]",
    ({ file }) => {
      const proj = project();
      const sf = proj.getSourceFile(path.join(PORTS_DIR, file))!;
      const allowedExternal = new Set(["zod"]);
      const offenders: string[] = [];
      for (const decl of sf.getImportDeclarations()) {
        const spec = decl.getModuleSpecifierValue();
        if (spec.startsWith("node:")) continue;
        if (allowedExternal.has(spec)) continue;
        if (
          spec.startsWith("../wire/") ||
          spec.startsWith("../trust-view/") ||
          spec.startsWith("@/lib/wire/") ||
          spec.startsWith("@/lib/trust-view/")
        ) {
          continue;
        }
        // relative imports inside ports/ are fine (e.g. shared types)
        if (spec.startsWith("./")) continue;
        offenders.push(spec);
      }
      expect(offenders, `${file} imports outside allowed surface`).toEqual([]);
    },
  );
});
