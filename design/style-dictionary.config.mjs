import path from 'path';
import { fileURLToPath } from 'url';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { glob } from 'fs/promises';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const TOKENS_DIR = path.join(ROOT, 'tokens');
const OUT_FILE = path.join(ROOT, '..', 'frontend', 'app', 'generated-theme.css');

// --- load all token files ---
async function loadTokenFiles(pattern) {
  const files = [];
  for await (const f of glob(path.join(TOKENS_DIR, '*.tokens.json'))) {
    files.push(f);
  }
  return files;
}

function readTokens(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

// Flatten nested DTCG token tree into { path: string[], value: string }[]
function flattenTokens(obj, pathParts = []) {
  const result = [];
  for (const [key, val] of Object.entries(obj)) {
    if (key.startsWith('$')) continue;
    if (val && typeof val === 'object' && '$value' in val) {
      result.push({ path: [...pathParts, key], value: String(val.$value) });
    } else if (val && typeof val === 'object') {
      result.push(...flattenTokens(val, [...pathParts, key]));
    }
  }
  return result;
}

// Map token path to CSS custom property name
function toCSSVar(pathParts) {
  const [ns, ...rest] = pathParts;
  // color.* -> --color-*
  // font.* -> --font-*
  // text.xs.size -> --text-xs, text.xs.lineHeight -> --text-xs--line-height
  // radius.* -> --radius-*
  if (ns === 'color') {
    return `--color-${rest.join('-')}`;
  }
  if (ns === 'font') {
    return `--font-${rest.join('-')}`;
  }
  if (ns === 'text') {
    const [size, prop] = rest;
    if (prop === 'size') return `--text-${size}`;
    if (prop === 'lineHeight') return `--text-${size}--line-height`;
    return `--text-${rest.join('-')}`;
  }
  if (ns === 'radius') {
    return `--radius-${rest.join('-')}`;
  }
  // Tailwind v4 spacing base: a single `spacing` token → `--spacing`
  // (Tailwind multiplies it for every p-*/m-*/gap-* utility). Nested
  // spacing.* (a named ladder) would emit `--spacing-<name>`.
  if (ns === 'spacing') {
    return rest.length ? `--spacing-${rest.join('-')}` : '--spacing';
  }
  return `--${pathParts.join('-')}`;
}

async function build() {
  const tokenFiles = await loadTokenFiles();

  // Separate light and dark files
  const lightFiles = tokenFiles.filter(f => !f.includes('.dark.'));
  const darkFiles  = tokenFiles.filter(f =>  f.includes('.dark.'));

  const lightTokens = lightFiles.flatMap(f => flattenTokens(readTokens(f)));
  const darkTokens  = darkFiles.flatMap(f => flattenTokens(readTokens(f)));

  const themeVars = lightTokens
    .map(({ path: p, value }) => `  ${toCSSVar(p)}: ${value};`)
    .join('\n');

  const darkVars = darkTokens
    .map(({ path: p, value }) => `  ${toCSSVar(p)}: ${value};`)
    .join('\n');

  const css = [
    '/* !! GENERATED — do not edit. Run: pnpm tokens:build !! */',
    '',
    '@theme {',
    themeVars,
    '}',
    '',
    '[data-theme="dark"] {',
    darkVars,
    '}',
    '',
    '/* !! END GENERATED !! */',
    '',
  ].join('\n');

  mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  writeFileSync(OUT_FILE, css, 'utf8');
  console.log(`tokens:build → ${OUT_FILE}`);
}

build().catch(err => { console.error(err); process.exit(1); });
