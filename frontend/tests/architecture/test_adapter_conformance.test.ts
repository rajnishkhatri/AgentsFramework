/**
 * Adapter conformance suite (FD6.PORT adapter side / A3 / A4).
 *
 * Companion to `test_port_conformance.test.ts`. Where the port-side test
 * verifies that every `lib/ports/*.ts` file satisfies P1-P7, this suite
 * walks each `{port, adapter}` pair and asserts the adapter side of the
 * contract:
 *
 *   AC1  The adapter class declares an `implements <PortInterface>` clause.
 *   AC2  Every method on the port interface is implemented by the class
 *        (signature presence; the TypeScript compiler validates types).
 *   AC3  No method's return-type token text references an SDK package
 *        (A4 / F-R8 — SDK types never escape past the adapter boundary).
 *
 * The synthetic-FAIL test at the bottom plants an adapter whose method
 * returns an SDK type and confirms the rule (AC3) trips. Per the
 * `failure-paths-first` discipline (FD6.ADAPTER), the synthetic fixture
 * lives BEFORE the live-suite expectations in the file even though it
 * runs last by Vitest convention (vitest preserves describe order when
 * tests are independent).
 */

import { describe, expect, it } from "vitest";
import * as path from "node:path";
import * as fs from "node:fs";
import {
  Project,
  type ClassDeclaration,
  type InterfaceDeclaration,
  type SourceFile,
  SyntaxKind,
} from "ts-morph";

const TEST_DIR =
  (import.meta as { dirname?: string }).dirname ?? __dirname;
const FRONTEND_ROOT = path.resolve(TEST_DIR, "..", "..");
const TSCONFIG = path.join(FRONTEND_ROOT, "tsconfig.json");

interface PortAdapterPair {
  readonly port_file: string;
  readonly port_interface: string;
  readonly adapter_file: string;
  readonly adapter_class: string;
}

// SDK packages the reviewer treats as A1-confined. Mirrors the
// THIRD_PARTY_SDK_PACKAGES list in `test_frontend_layering.test.ts`.
const SDK_PACKAGES: ReadonlyArray<string> = [
  "@copilotkit/react-core",
  "@copilotkit/react-ui",
  "@copilotkit/runtime",
  "@workos-inc/authkit-nextjs",
  "@workos-inc/node",
  "@langchain/langgraph-sdk",
  "mem0ai",
  "langfuse",
  "drizzle-orm",
  "@neondatabase/serverless",
];

// All currently-built {port, adapter} pairs. Each new adapter that
// implements an existing port adds a row here. A port with no live
// adapter (e.g. MemoryClient, TelemetrySink today) is intentionally
// absent; the port-side test (P7) covers their existence.
const PAIRS: ReadonlyArray<PortAdapterPair> = [
  {
    port_file: "lib/ports/agent_runtime_client.ts",
    port_interface: "AgentRuntimeClient",
    adapter_file:
      "lib/adapters/runtime/self_hosted_langgraph_dev_client.ts",
    adapter_class: "SelfHostedLangGraphDevClient",
  },
  {
    port_file: "lib/ports/auth_provider.ts",
    port_interface: "AuthProvider",
    adapter_file: "lib/adapters/auth/workos_authkit_adapter.ts",
    adapter_class: "WorkOSAuthKitAdapter",
  },
  {
    port_file: "lib/ports/thread_store.ts",
    port_interface: "ThreadStore",
    adapter_file: "lib/adapters/thread_store/neon_free_thread_store.ts",
    adapter_class: "NeonFreeThreadStore",
  },
  {
    port_file: "lib/ports/feature_flag_provider.ts",
    port_interface: "FeatureFlagProvider",
    adapter_file:
      "lib/adapters/feature_flags/env_var_flags_adapter.ts",
    adapter_class: "EnvVarFlagsAdapter",
  },
  {
    port_file: "lib/ports/tool_renderer_registry.ts",
    port_interface: "ToolRendererRegistry",
    adapter_file:
      "lib/adapters/tool_renderer/copilotkit_registry_adapter.ts",
    adapter_class: "CopilotKitRegistryAdapter",
  },
  {
    port_file: "lib/ports/ui_runtime.ts",
    port_interface: "UIRuntime",
    adapter_file: "lib/adapters/ui_runtime/copilotkit_ui_runtime.ts",
    adapter_class: "CopilotKitUIRuntime",
  },
];

function newProject(): Project {
  return new Project({
    tsConfigFilePath: TSCONFIG,
    skipAddingFilesFromTsConfig: false,
  });
}

function loadInterface(
  project: Project,
  relPath: string,
  name: string,
): InterfaceDeclaration | undefined {
  const sf = project.getSourceFile(path.join(FRONTEND_ROOT, relPath));
  if (!sf) return undefined;
  return sf.getInterface(name);
}

function loadClass(
  project: Project,
  relPath: string,
  name: string,
): ClassDeclaration | undefined {
  const sf = project.getSourceFile(path.join(FRONTEND_ROOT, relPath));
  if (!sf) return undefined;
  return sf.getClass(name);
}

function interfaceMethodNames(iface: InterfaceDeclaration): string[] {
  const out: string[] = [];
  for (const member of iface.getMembers()) {
    if (member.getKind() === SyntaxKind.MethodSignature) {
      const ms = member.asKindOrThrow(SyntaxKind.MethodSignature);
      out.push(ms.getName());
    } else if (member.getKind() === SyntaxKind.PropertySignature) {
      // A function-typed property still satisfies "method" semantics for
      // adapter conformance — capture its name.
      const ps = member.asKindOrThrow(SyntaxKind.PropertySignature);
      out.push(ps.getName());
    }
  }
  return out;
}

function classMethodNames(cls: ClassDeclaration): Set<string> {
  const out = new Set<string>();
  for (const m of cls.getMethods()) out.add(m.getName());
  for (const p of cls.getProperties()) out.add(p.getName());
  return out;
}

function returnTypeReferencesSdk(
  cls: ClassDeclaration,
  sf: SourceFile,
): { method: string; sdk: string }[] {
  const findings: { method: string; sdk: string }[] = [];
  // Build a quick "does this file import an SDK directly?" map. Only
  // SDK names that actually appear in import declarations are candidates
  // for leaks via return types — anything else won't surface in the
  // method's printed type.
  const importedSdkNames = new Set<string>();
  for (const decl of sf.getImportDeclarations()) {
    const spec = decl.getModuleSpecifierValue();
    if (!SDK_PACKAGES.includes(spec)) continue;
    for (const named of decl.getNamedImports()) {
      importedSdkNames.add(named.getName());
    }
    const def = decl.getDefaultImport();
    if (def) importedSdkNames.add(def.getText());
    const ns = decl.getNamespaceImport();
    if (ns) importedSdkNames.add(ns.getText());
  }

  if (importedSdkNames.size === 0) return findings;

  for (const m of cls.getMethods()) {
    const ret = m.getReturnTypeNode();
    if (!ret) continue;
    const text = ret.getText();
    for (const sdkName of importedSdkNames) {
      // Match the SDK-imported identifier as a whole word in the return
      // type token text. This catches `Promise<SdkSession>`,
      // `AsyncIterable<SdkEvent>`, etc.
      const re = new RegExp(`\\b${sdkName}\\b`);
      if (re.test(text)) {
        findings.push({ method: m.getName(), sdk: sdkName });
      }
    }
  }
  return findings;
}

describe("Adapter conformance suite [FD6.PORT adapter side / A3 / A4]", () => {
  it.each(PAIRS)(
    "$adapter_class declares `implements $port_interface` (AC1)",
    ({ port_file, port_interface, adapter_file, adapter_class }) => {
      const project = newProject();
      const iface = loadInterface(project, port_file, port_interface);
      const cls = loadClass(project, adapter_file, adapter_class);
      expect(iface, `port interface ${port_interface} not found`).toBeTruthy();
      expect(cls, `adapter class ${adapter_class} not found`).toBeTruthy();
      const implementsClause = cls!.getImplements().map((i) => i.getText());
      const matches = implementsClause.some((t) => t.includes(port_interface));
      expect(
        matches,
        `${adapter_class} must declare \`implements ${port_interface}\` (got: [${implementsClause.join(", ")}])`,
      ).toBe(true);
    },
  );

  it.each(PAIRS)(
    "$adapter_class implements every $port_interface method (AC2)",
    ({ port_file, port_interface, adapter_file, adapter_class }) => {
      const project = newProject();
      const iface = loadInterface(project, port_file, port_interface);
      const cls = loadClass(project, adapter_file, adapter_class);
      expect(iface).toBeTruthy();
      expect(cls).toBeTruthy();
      const expected = interfaceMethodNames(iface!);
      const actual = classMethodNames(cls!);
      const missing = expected.filter((m) => !actual.has(m));
      expect(
        missing,
        `${adapter_class} is missing required methods: [${missing.join(", ")}]`,
      ).toEqual([]);
    },
  );

  it.each(PAIRS)(
    "$adapter_class return types do not reference SDK packages (AC3 / A4)",
    ({ adapter_file, adapter_class }) => {
      const project = newProject();
      const sf = project.getSourceFile(path.join(FRONTEND_ROOT, adapter_file));
      expect(sf, `adapter file ${adapter_file} not loaded`).toBeTruthy();
      const cls = sf!.getClass(adapter_class);
      expect(cls).toBeTruthy();
      const leaks = returnTypeReferencesSdk(cls!, sf!);
      expect(
        leaks,
        leaks
          .map((l) => `${adapter_class}.${l.method} returns SDK type ${l.sdk}`)
          .join("\n"),
      ).toEqual([]);
    },
  );

  it("PAIRS catalogue stays in sync with adapter folders on disk", () => {
    // Belt-and-braces: any new sibling `.ts` (non-test, non-errors)
    // under `lib/adapters/<family>/` should either be intentionally
    // omitted (no port pair yet) or appear in PAIRS.
    const adaptersRoot = path.join(FRONTEND_ROOT, "lib", "adapters");
    const dirs = fs.readdirSync(adaptersRoot, { withFileTypes: true });
    const knownAdapterFiles = new Set(PAIRS.map((p) => p.adapter_file));
    const orphans: string[] = [];
    for (const d of dirs) {
      if (!d.isDirectory()) continue;
      const family = d.name;
      const familyDir = path.join(adaptersRoot, family);
      for (const f of fs.readdirSync(familyDir)) {
        if (!f.endsWith(".ts")) continue;
        if (f.endsWith(".test.ts") || f === "errors.ts" || f.startsWith("_")) continue;
        const rel = path.join("lib", "adapters", family, f);
        if (!knownAdapterFiles.has(rel)) orphans.push(rel);
      }
    }
    // Every known orphan must be intentional. We surface the list so a
    // reviewer can decide whether to add a row to PAIRS.
    expect(
      orphans,
      `Unmapped adapter files (add to PAIRS or document the omission): ${orphans.join(", ")}`,
    ).toEqual([
      // Known intentional omissions:
      "lib/adapters/auth/workos_server_sdk.ts", // server-only seam (D-V3-S3.7.1-RouteHandler)
    ]);
  });
});

describe("Pattern-7 self-validation (synthetic FAIL fixture)", () => {
  it("flags an adapter whose method returns an SDK type (AC3 negative)", () => {
    const project = new Project({
      useInMemoryFileSystem: false,
      compilerOptions: {},
    });
    const fakeAdapterPath = path.join(
      FRONTEND_ROOT,
      "lib",
      "adapters",
      "runtime",
      "__synthetic_sdk_leak__.ts",
    );
    project.createSourceFile(
      fakeAdapterPath,
      `import type { Client } from "@langchain/langgraph-sdk";\n` +
        `export class LeakyAdapter {\n` +
        `  async getClient(): Promise<Client> { return null as unknown as Client; }\n` +
        `}\n`,
      { overwrite: true },
    );
    const sf = project.getSourceFile(fakeAdapterPath)!;
    const cls = sf.getClass("LeakyAdapter")!;
    const leaks = returnTypeReferencesSdk(cls, sf);
    expect(
      leaks.find((l) => l.method === "getClient" && l.sdk === "Client"),
      "expected the synthetic adapter to trip AC3 (SDK type leak)",
    ).toBeTruthy();
  });
});
