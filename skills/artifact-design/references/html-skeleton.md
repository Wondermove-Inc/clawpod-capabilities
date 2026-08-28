# HTML artifact skeleton

The panel renders `html` artifacts as `<iframe sandbox="" srcDoc={content}>` (verified in `generic-artifact-panel.tsx`). That single line dictates the skeleton:

- **No JavaScript runs.** Do not ship `<script>`; nothing depends on it.
- **No same-origin.** No `localStorage`, cookies, or fetch.
- **The portal's CSP is inherited.** Fonts: system stacks, `data:` URIs, or `https://cdn.jsdelivr.net` only (Google Fonts is blocked). Images: `https:` and `data:`. Nothing else external.
- **Only the OS theme reaches the frame.** Use `prefers-color-scheme`; the portal's own dark-mode class never propagates.
- **The frame is 70 vh tall and 320–670 px wide.** Single column; content scrolls inside the frame.
- **The card preview is `content` with tags stripped, first 240 chars.** Put `<style>` at the **end of `<body>`**, keep `<head>` to `meta` + `title`, and open `<body>` with the eyebrow, title, and lede so the preview reads as a sentence.

## Skeleton

```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Q3 Pricing Review</title>
</head>
<body>
<main>
  <header class="lede">
    <p class="eyebrow">Pricing · Q3 2026</p>
    <h1>Q3 Pricing Review</h1>
    <p>Three tiers, two proposed changes, one decision needed by 12 September.</p>
  </header>

  <section class="card">
    <h2>What changes</h2>
    <p>…real content…</p>
  </section>

  <section>
    <h2>Tier comparison</h2>
    <div class="scroll">
      <table>
        <thead><tr><th>Tier</th><th class="num">Today</th><th class="num">Proposed</th><th>State</th></tr></thead>
        <tbody>
          <tr><td>Pro</td><td class="num">49,000</td><td class="num">54,000</td><td><span class="pill warn">review</span></td></tr>
        </tbody>
      </table>
    </div>
  </section>
</main>

<!-- Styles last on purpose: the card preview is the first 240 characters of
     tag-stripped content, so prose must come before CSS. -->
<style>
  /* 1. Complete palette on :root — every color the page uses. */
  :root {
    --ground: #F7F6F2;
    --surface: #FFFFFF;
    --ink: #1D1F24;
    --ink-muted: #5C6070;
    --line: #DCD9D0;
    --accent: #1F5F8B;
    --good: #2E7D5B;
    --warn: #B7791F;
    --crit: #B23A3A;
    --font-display: "Iowan Old Style", "Palatino Linotype", "Noto Serif KR", Georgia, serif;
    --font-body: "Avenir Next", "Segoe UI", "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
    --font-mono: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
    --radius: 6px;
  }
  /* 2. Dark redefines tokens only; it never introduces a new color. */
  @media (prefers-color-scheme: dark) {
    :root {
      --ground: #15171C;
      --surface: #1E2128;
      --ink: #ECEAE3;
      --ink-muted: #A3A7B3;
      --line: #2F333D;
      --accent: #7FB2DC;
      --good: #6FBF95;
      --warn: #E0B15A;
      --crit: #E27878;
    }
  }

  * { box-sizing: border-box; }
  html { color-scheme: light dark; }
  body {
    margin: 0;
    background: var(--ground);   /* explicit — never transparent */
    color: var(--ink);
    font: 15px/1.6 var(--font-body);
    -webkit-font-smoothing: antialiased;
  }
  main { padding: 1.25rem 1.25rem 2.5rem; display: grid; gap: 1.5rem; }
  h1, h2 { font-family: var(--font-display); line-height: 1.15; text-wrap: balance; margin: 0; }
  h1 { font-size: clamp(1.5rem, 5vw, 1.9rem); font-weight: 600; }
  h2 { font-size: 1.15rem; font-weight: 600; margin-bottom: .5rem; }
  p { margin: 0; max-width: 65ch; }
  .lede { display: grid; gap: .35rem; }
  .eyebrow { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-muted); }
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem; }
  .scroll { overflow-x: auto; }               /* wide tables and SVG live inside this */
  table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: .9rem; }
  th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; white-space: nowrap; }
  th { font-size: .74rem; letter-spacing: .04em; text-transform: uppercase; color: var(--ink-muted); }
  .num { text-align: right; }
  code, pre { font-family: var(--font-mono); font-size: .88em; }
  pre { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: .85rem; overflow-x: auto; }
  .pill { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; font-weight: 600; }
  .pill.good { background: color-mix(in srgb, var(--good) 15%, transparent); color: var(--good); }
  .pill.warn { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }
  .pill.crit { background: color-mix(in srgb, var(--crit) 15%, transparent); color: var(--crit); }
  a { color: var(--accent); }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
</body>
</html>
```

The palette and faces above are a **worked example**, not a house style. Replace them from your design plan every time; leaving them in place is exactly the templated look to avoid.

## Web fonts that actually load

Google Fonts is blocked by the inherited CSP. If a specific face matters, load it from jsDelivr with a real fallback stack — for example a Fontsource package:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/fraunces@5/index.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css">
```

Place `<link>` tags in `<head>` (they carry no text, so they do not affect the preview). Treat them as enhancement: the system stack must already look intentional.

## Charts and diagrams without scripts

Author charts as inline SVG with tokens for color (`fill="var(--accent)"` works inside inline SVG). Give them the same care as type: a faint grid, tabular numbers on axes, an area fill, an emphasized endpoint. Semantic colors (`--good`, `--warn`, `--crit`) carry state; the accent carries emphasis; do not use the accent for both. Wrap any SVG wider than ~440 px in `.scroll` or give it `width: 100%; height: auto` with a `viewBox`.

If the diagram is a flowchart, sequence, state, ER, or Gantt, consider a `markdown` artifact with a ```` ```mermaid ```` block instead — it renders natively and follows the portal theme.

## CSS-only affordances

`<details>/<summary>` for collapsible sections, `:target` for in-page tabs, `:hover` for row highlights, CSS counters for real sequences. Nothing else is interactive.

## Size discipline

`content` is capped at 200,000 characters and data URIs count. Prefer inline SVG over embedded raster images; if an image is essential, reference an `https:` URL or keep the data URI small.
