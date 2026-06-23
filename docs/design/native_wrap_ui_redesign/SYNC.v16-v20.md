# Frontend sync — frozen foundations (v16–v20)

The cloud design-system bundle (`styles.css`) has moved ahead of `frontend/`. This folder
brings the repo back in line. Token files are drop-in; component/CSS edits are listed as a
checklist (they can't be inferred from tokens alone).

## 1. Tokens — copy into `frontend/design/tokens/`, then rebuild

Replace these four files, then run `pnpm tokens:build` (regenerates the git-ignored
`app/generated-theme.css`):

| File | Change |
|---|---|
| `color.tokens.json` | accent `#c2704e → #d87758`; **+ `warning` `#a9741f`** |
| `color.dark.tokens.json` | accent `#d98b6a → #e5967c`; accent-light `rgba(219,141,105,.22) → rgba(229,150,124,.22)`; **+ `warning` `#e3b357`** |
| `type.tokens.json` | every size **+2px** — xs 12→14, sm 14→16, base 16→18, lg 18→20, xl 22→24, 2xl 26→28 (line-heights unchanged) |
| `radius.tokens.json` | sm `.375→.625` (10px), md `.5→1` (16px), lg `.75→1.375` (22px) |

## 2. `app/globals.css` — apply `globals-surface-patch.css`

- Replace `.surface-etched`, `.surface-embossed`, `.separator-etched`, `.separator-etched-v`
  with the Option-E versions (1.5px border + soft drop shadow; solid dividers).
- Delete the `[data-theme="dark"] .badge-warning { color: #e3b357 }` override (now a token).
- (Optional type parity) bump the two hardcoded `0.6875rem` font-sizes → `0.8125rem`.
- `.bubble-user` and `.btn-shine` are **unchanged**.

## 3. Components (Tailwind / .tsx) — manual edits

- **Button** (`components/ui/button.tsx`): radius → **`rounded-full`** on every size (pill);
  icon-button variant → `rounded-full` (circle). The coral bezel/shine (`.btn-shine`) stays.
- **Cards** (`card.tsx`, ToolCard, TaskUnderstanding): drop the embossed/etched insets →
  **1.5px border + soft drop shadow** on a flat `bg-surface`
  (`border-[1.5px] border-[color-mix(in_oklab,var(--color-fg)_18%,transparent)] shadow-[0_4px_12px_-4px_color-mix(in_oklab,#000_20%,transparent)]`),
  or just apply the `.surface-etched` / `.surface-embossed` class.
- **Radius usage remap**: chips/badges → `rounded-sm` (10px); inputs/tabs/menus/toasts/
  dropdowns → `rounded-md` (16px); cards/dialogs/sheets/bubbles → `rounded-lg` (22px).
- **Badge `warning`** (`badge.tsx` / globals): use `var(--color-warning)` for text + the
  15% bg mix + 32% border, instead of hardcoded `#c08a2e` / `#a9741f`.

## 4. Root font-size — no change

Production is already 16px (no `html { font-size }`). The cloud preview's 17.5px was
preview-only; the +2px type bump is baked into the token sizes above, so production lands
on the intended px (base 18, 2xl 28).

## Reference

Per-decision snapshots live in this project under `frozen/styles.v16-*.css … v20-*.css`;
the live flattened bundle is `styles.css`. Design contract: `.design-sync/conventions.md`.
