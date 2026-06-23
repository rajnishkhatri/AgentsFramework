import { defineConfig } from "tsup";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * Library build for the shadcn primitive layer (PS1 / plan §2.5).
 *
 * Emits `dist/` (ESM + .d.ts) for the design-sync bundle. React and all
 * runtime deps are externalized — design-sync / consumers provide them; we
 * ship only our primitive code. The `@/lib/utils` alias is resolved to the
 * real file since esbuild does not read tsconfig paths.
 */
export default defineConfig({
  entry: { index: "components/ui/index.ts" },
  format: ["esm"],
  // .d.ts is emitted separately by `tsc -p tsconfig.lib.json` (the repo
  // tsconfig's `incremental: true` is incompatible with tsup's dts worker).
  dts: false,
  sourcemap: true,
  clean: true,
  treeshake: true,
  // Single ESM file for the bundle. Note: esbuild strips module-level
  // "use client" directives when bundling, so dist/index.js has none. That
  // is fine for the design-sync surface (it ships per-component previews,
  // not an RSC-consumed package); the source primitives keep their own
  // directives for the Next app. If this dist is ever consumed directly by
  // Next, add esbuild-plugin-preserve-directives and disable bundling.
  external: [
    "react",
    "react-dom",
    "react/jsx-runtime",
    /^@radix-ui\//,
    "class-variance-authority",
    "clsx",
    "tailwind-merge",
    "lucide-react",
    "sonner",
  ],
  esbuildOptions(options) {
    options.alias = {
      ...options.alias,
      "@/lib/utils": path.resolve(here, "lib/utils.ts"),
    };
  },
});
