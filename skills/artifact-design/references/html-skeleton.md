# HTML artifact skeleton

Author a **complete, self-contained document**. The panel may render it in a frame or inject it; a full document is safe either way. Inline every stylesheet and script. No external scripts, no remote images, no CDN. A Google Fonts `<link>` is optional progressive enhancement only — the fallback stack must already be a deliberate choice.

## Three-state theming

The viewer may be in light, dark, or "system" with nothing stamped on the root. Structure tokens for all three:

```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Q3 Pricing Review</title>
<style>
  /* 1. Complete light palette on bare :root — every color the page uses. */
  :root {
    --ground: #F7F6F2;
    --surface: #FFFFFF;
    --ink: #1D1F24;
    --ink-muted: #5C6070;
    --line: #DCD9D0;
    --accent: #1F5F8B;
    --accent-ink: #FFFFFF;
    --good: #2E7D5B;
    --warn: #B7791F;
    --crit: #B23A3A;
    --font-display: "Iowan Old Style", "Palatino Linotype", "Noto Serif KR", Georgia, serif;
    --font-body: "Avenir Next", "Segoe UI", "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
    --font-mono: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
    --measure: 65ch;
    --radius: 6px;
  }
  /* 2. Dark tokens for "system" viewers, unless the host stamped light explicitly. */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground: #15171C;
      --surface: #1E2128;
      --ink: #ECEAE3;
      --ink-muted: #A3A7B3;
      --line: #2F333D;
      --accent: #7FB2DC;
      --accent-ink: #0F1B26;
      --good: #6FBF95;
      --warn: #E0B15A;
      --crit: #E27878;
    }
  }
  /* 3. Explicit dark stamp wins in the other direction. */
  :root[data-theme="dark"] {
    --ground: #15171C;
    --surface: #1E2128;
    --ink: #ECEAE3;
    --ink-muted: #A3A7B3;
    --line: #2F333D;
    --accent: #7FB2DC;
    --accent-ink: #0F1B26;
    --good: #6FBF95;
    --warn: #E0B15A;
    --crit: #E27878;
  }

  /* Components use tokens only. Never a literal color that works in one theme. */
  * { box-sizing: border-box; }
  html { color-scheme: light dark; }
  body {
    margin: 0;
    background: var(--ground);   /* explicit — a transparent body borrows the host ground */
    color: var(--ink);
    font: 16px/1.6 var(--font-body);
    -webkit-font-smoothing: antialiased;
  }
  main { max-width: 72rem; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; display: grid; gap: 2rem; }
  h1, h2, h3 { font-family: var(--font-display); line-height: 1.15; text-wrap: balance; margin: 0; }
  h1 { font-size: clamp(1.9rem, 3.5vw, 2.6rem); font-weight: 600; }
  h2 { font-size: 1.35rem; font-weight: 600; }
  p { max-width: var(--measure); margin: 0; }
  .eyebrow { font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-muted); }
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.25rem; }
  .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); }
  .scroll { overflow-x: auto; }               /* wide tables, code, diagrams live inside this */
  table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; color: var(--ink-muted); }
  td.num, th.num { text-align: right; }
  code, pre { font-family: var(--font-mono); font-size: .9em; }
  pre { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem; }
  .pill { display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
  .pill.good { background: color-mix(in srgb, var(--good) 15%, transparent); color: var(--good); }
  .pill.warn { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }
  .pill.crit { background: color-mix(in srgb, var(--crit) 15%, transparent); color: var(--crit); }
  a { color: var(--accent); }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">Pricing · Q3 2026</div>
    <h1>Q3 Pricing Review</h1>
    <p>Three tiers, two proposed changes, one decision needed by 12 September.</p>
  </header>
  <!-- real content follows -->
</main>
</body>
</html>
```

The palette and faces above are a **worked example**, not a house style. Replace them from your design plan every time; leaving them in place is exactly the templated look to avoid.

## Rules the skeleton encodes

- Every color the page uses is defined on bare `:root`. The dark blocks only **redefine** tokens; they never introduce a new one.
- `body { background: var(--ground) }` is mandatory.
- `html { color-scheme: light dark }` keeps form controls and scrollbars in step with the theme.
- Wide content sits inside `.scroll` (or any `overflow-x: auto` container). The body never scrolls sideways.
- Focus is visible; reduced motion is respected.
- Preview text: the server strips tags and keeps the first 240 characters of `content` for the card. Put the eyebrow and lede at the top of `<body>` so the preview reads as a sentence, not as a CSS fragment.

## Size discipline

`content` is capped at 200,000 characters and data URIs count. Prefer inline SVG or Canvas over embedded raster images; if an image is essential, keep it small and compressed. Diagrams: hand-author only short SVG; anything generative goes to Canvas.

## Interactivity

Inline `<script>` is fine. `localStorage` may or may not be available in the panel — wrap every read and write in `try/catch` and render correctly with no stored value. Nothing in the page may depend on network access.

## Charts and diagrams

Give them the same care as type: an area fill, a faint grid, tabular numbers on axes, an emphasized endpoint or the one bar that matters. Semantic colors (`--good`, `--warn`, `--crit`) carry state; the accent carries emphasis; do not use the accent for both.
