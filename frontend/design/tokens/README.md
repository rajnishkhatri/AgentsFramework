# design/tokens

DTCG (Design Tokens Community Group) token source for AgentsFramework UI.

## Why this exists
The runtime CSS (`styles.css` / `app/globals.css`) is the source of truth **today**. This folder holds the DTCG equivalents for when a token build (e.g. Style Dictionary) becomes the upstream source.

## `color.dark.tokens.json`
The dark theme uses **richer per-mode mix percentages** than light (surface `92/8` vs `96/4`, sunken `85/15`, `accent-light` 22%, bumped borders/overlays). The P0 architecture intentionally redeclares only *primitives* for dark and lets derived tokens recompute against the dark base — which would otherwise flatten dark to the *light* percentages and reduce surface/border separation.

This file re-introduces those derived values **explicitly** so the dark look (Cocoa `#241c15` base + embossed/etched separation) survives the build. Each derived token carries:
- `$value` — the oklab `color-mix` recipe resolved to concrete sRGB
- `$extensions["com.agentsframework.mix"]` — the original recipe, for regeneration if a primitive changes

If you change a dark primitive (`bg`, `fg`, `accent`), re-resolve the derived `$value`s from their recipes rather than hand-editing.
