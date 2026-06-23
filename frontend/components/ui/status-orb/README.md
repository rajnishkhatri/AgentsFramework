# Pulsing Status Orb (v14)

A small "alive" indicator with a radar-pulse halo — for run/streaming/live states.

## Files
- `status-orb.css` — the only thing you need. Drop it in and link it.
- `status-orb.html` — live usage examples (light + cocoa dark).

## Usage
```html
<link rel="stylesheet" href="status-orb.css">

<span class="status-orb"></span> Running
<span class="status-orb is-success"></span> Live
<span class="status-orb is-danger"></span> Error

<!-- inside a badge, smaller -->
<span class="badge"><span class="status-orb" style="width:8px;height:8px"></span> Streaming</span>
```

## Notes
- Colors use AgentsFramework tokens (`--color-accent`, `--color-success`, `--color-danger`) with literal fallbacks, so it works standalone.
- Honors `prefers-reduced-motion` — the dot shows, the pulse stops.
- Size with `width`/`height` on `.status-orb`.
