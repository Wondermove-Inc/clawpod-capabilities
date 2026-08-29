# Quality gates

Three gates, run in this order, before any handoff. Content and structure are judged from the brief and the canvas; the visual gate is deterministic through `projects.qa.layout`. A failed gate feeds a revision into `projects.iterate` on the same project (at most three rounds), never a different rendering.

## 1. Content gate (what the deck says)

- Every slide carries **one** message, and its title states that message as a sentence (a takeaway), not a topic label.
- Every number, name, date, and claim traces to the pinned source; stale markers are absent.
- The storyline reads in order without the speaker: situation → insight → evidence → implication/ask.
- No slide exists only because the template had a slot for it. Delete or merge.

Record a one-line verdict per slide (pass / fix: what).

## 2. Structure gate (how the deck is organized)

- One layout family across body slides: same title position and size, same margins, same content grid. Cover and section dividers may differ.
- Hierarchy is visible at a glance: title > section label > body > caption, with a type scale of at most 4 sizes and at most 2 families.
- **Text budget**: ≤ 6 bullets per slide, ≤ 12 words per bullet, ≤ 90 words per slide; tables ≤ 6 columns; otherwise split.
- **Diagram grammar**: one shape per concept type (e.g. rounded rectangle = system, pill = actor, diamond = decision), one arrow style, edges labeled when the relationship is not obvious, flow in one direction (left→right or top→bottom), nodes snapped to a grid with equal gaps, ≤ 7 nodes per view (group or split beyond that), and a legend when more than two shape kinds appear.
- **Charts**: axis labels and units, the one data point that matters emphasized, at most one semantic color plus the accent, no 3D, no legend when direct labels fit.
- Korean text: no single-character orphans on a line, no mid-word breaks in headings, mixed Latin terms set in the same weight.

## 3. Visual gate (deterministic)

### Capture

Two equivalent ways to obtain the per-slide geometry JSON. Both produce the same shape and were validated on a real 14-slide Claude Design export (`section.slide` roots inside the `__bundler` template; hidden stacked slides are measured by forcing visibility during capture).

**A. Offline from the `.dc.html` export (preferred when the file exists — no login, no live browser):**

```
python3 harnesses/claude-design/scripts/capture_layout.py --deck <deck>.dc.html --out <workspace>/design-qa/<project>-layout.json \
    [--chromium /usr/bin/chromium | --docker-image clawpod/agent:latest] [--width 1920 --height 1080]
```

It injects the capture script below, renders once in headless Chromium, and writes the JSON (plus `slideSelector`, per-slide `label` from `data-label`, and `slideRect`).

**B. Live from the canvas through Browser `evaluate`** (one call on the exact `.dc.html` file route; the script picks the first selector that matches slide-sized elements — extend the list from a fresh snapshot if none match) and read back the JSON from the injected `<script id="__layout_capture__">` node:

```js
(() => {
  const candidates = ['section.slide', '[data-slide]', '.slide', '[data-page]', '.page'];
  let slides = [];
  for (const sel of candidates) {
    try { const found = [...document.querySelectorAll(sel)].filter(el => { const r = el.getBoundingClientRect(); return r.width >= 600 && r.height >= 300; }); if (found.length) { slides = found; window.__slideSelector = sel; break; } } catch (e) {}
  }
  if (!slides.length) { slides = [document.body]; window.__slideSelector = 'body'; }
  const vw = slides[0].getBoundingClientRect().width || innerWidth;
  const vh = slides[0].getBoundingClientRect().height || innerHeight;
  let n = 0;
  const hasOwnText = el => [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
  const kindOf = el => el.matches('img,svg,canvas,video,picture') ? 'image' : hasOwnText(el) ? 'text' : 'shape';
  const shapeOf = (el, cs) => { const r = parseFloat(cs.borderRadius) || 0; const w = el.getBoundingClientRect().width;
    if (cs.clipPath && cs.clipPath !== 'none') return 'polygon'; if (r >= w / 2 && w > 0) return 'circle'; if (r > 40) return 'pill'; if (r > 0) return 'rounded'; return 'rect'; };
  const visibleBox = (el, cs) => cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || (cs.borderStyle !== 'none' && parseFloat(cs.borderWidth) > 0) || cs.boxShadow !== 'none';
  const out = { viewport: { width: Math.round(vw), height: Math.round(vh) }, slideSelector: window.__slideSelector, slides: slides.map((slide, i) => {
    // Viewers stack slides and hide all but the current one (visibility:hidden / opacity:0). Geometry is still laid out,
    // so force this slide visible only for the duration of the measurement and restore afterwards.
    const saved = { visibility: slide.style.visibility, opacity: slide.style.opacity, display: slide.style.display };
    slide.style.visibility = 'visible'; slide.style.opacity = '1'; if (getComputedStyle(slide).display === 'none') slide.style.display = 'block';
    const base = slide.getBoundingClientRect(); const ids = new Map();
    const ownHidden = el => { const cs = getComputedStyle(el); return cs.display === 'none' || (el.style && (el.style.visibility === 'hidden' || el.style.display === 'none')); };
    const els = [...slide.querySelectorAll('*')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2 && !ownHidden(el) && !el.matches('script,style,br'); });
    els.forEach(el => ids.set(el, 'e' + (++n)));
    const elements = [];
    for (const el of els) {
      const cs = getComputedStyle(el); const kind = kindOf(el);
      if (kind === 'shape' && !visibleBox(el, cs)) continue;           // skip invisible layout wrappers
      const r = el.getBoundingClientRect();
      let parent = el.parentElement; while (parent && parent !== slide && !ids.has(parent)) parent = parent.parentElement;   // nearest captured DOM ancestor
      let box = el.parentElement; while (box && box !== slide && !(ids.has(box) && kindOf(box) === 'shape' && visibleBox(box, getComputedStyle(box)))) box = box.parentElement;   // nearest visible container
      const cls = (el.getAttribute('class') || '').trim().split(/\s+/)[0] || undefined;
      elements.push({ id: ids.get(el), kind, tag: el.tagName.toLowerCase(), cls, display: cs.display, position: cs.position,
        inDiagram: !!(el.closest('figure, svg, canvas, table') && el.closest('figure, svg, canvas, table') !== el),
        overflow: cs.overflowY !== 'visible' || cs.overflowX !== 'visible' || cs.textOverflow === 'ellipsis' ? 'clip' : 'visible',
        shape: kind === 'shape' ? shapeOf(el, cs) : undefined,
        text: kind === 'text' ? (el.innerText || el.textContent).trim().slice(0, 200) : undefined,
        fontPx: kind === 'text' ? parseFloat(cs.fontSize) : undefined, fontFamily: kind === 'text' ? cs.fontFamily.split(',')[0].replace(/["']/g, '').trim() : undefined,
        color: kind === 'text' ? cs.color : undefined, background: cs.backgroundColor,
        bbox: [Math.round(r.left - base.left), Math.round(r.top - base.top), Math.round(r.width), Math.round(r.height)],
        parent: parent && parent !== slide ? ids.get(parent) : undefined, box: box && box !== slide ? ids.get(box) : undefined,
        clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight });
    }
    slide.style.visibility = saved.visibility; slide.style.opacity = saved.opacity; slide.style.display = saved.display;
    return { index: i + 1, label: slide.getAttribute('data-label') || slide.getAttribute('aria-label') || undefined, classes: (slide.className || '').toString().slice(0, 80), slideRect: [Math.round(base.left), Math.round(base.top), Math.round(base.width), Math.round(base.height)], elements };
  }) };
  const holder = document.createElement('script'); holder.type = 'application/json'; holder.id = '__layout_capture__';
  holder.textContent = JSON.stringify(out); document.documentElement.appendChild(holder);
})();
```

Each element records: `kind` (text/shape/image), `tag`, `cls` (first class), `display`, `position`, `inDiagram` (inside figure/svg/canvas/table), `overflow` (`clip` when the element clips or uses ellipsis, else `visible`), `shape`, `text`, `fontPx`, `fontFamily`, `color`, `background`, `bbox` relative to the slide, `parent` (nearest captured DOM ancestor), `box` (nearest visible container), and scroll/client sizes.

### Evaluate

```
projects.qa.layout --layout-json <file> --expected-pages N [--min-font-px 14] [--tolerance-px 4] [--max-words 90] [--overlap-ratio 0.15] [--max-font-sizes 8] [--strict]
```

| Code | Severity | Means |
|---|---|---|
| `TEXT_OVERFLOW` | critical | text wider/taller than a box that **clips** it (scroll > client with overflow hidden/clip/ellipsis); visible overflow is judged by `TEXT_OUTSIDE_SHAPE` instead |
| `TEXT_OUTSIDE_SHAPE` | critical | a text box escapes its container shape |
| `OVERLAP` | critical | two independent block-level text boxes intersect > 15 % (DOM ancestors and inline children are never counted) |
| `OFF_CANVAS` | critical | element extends beyond the slide |
| `PAGE_COUNT_MISMATCH` | critical | captured slides ≠ expected |
| `MISALIGNED_EDGE` | warning | two **peer** siblings (same kind, tag, first class, similar font size; outside diagrams) are *almost* aligned — edge off by 1–4× tolerance and centers not aligned — the classic "오와 열이 안 맞음" |
| `UNEVEN_SPACING` | warning | a row/column of ≥ 3 peer siblings has unequal, non-negative gaps |
| `FONT_TOO_SMALL` | warning | below the floor (14 px at 1920×1080) |
| `TEXT_DENSITY` | warning | > 90 words on a slide |
| `INCONSISTENT_SHAPES` | warning | > 3 shape kinds on one slide — diagram has no grammar |
| `TITLE_DRIFT` | warning | body-slide `h1`/`h2` title position varies across slides by more than 2× tolerance |
| `FONT_SIZE_SPRAWL` | warning | > 8 distinct font sizes in the deck (`--max-font-sizes`) |
| `EMPTY_SLIDE` | warning | nothing captured on a slide |

`pass` is false on any critical finding (and on warnings with `--strict`). The response carries `revision_prompt`, a single instruction that names every defect per slide; paste it into `projects.iterate` unchanged, then re-capture and re-run.

### Eyeball after the gate

One screenshot per slide: contrast on both light and dark backgrounds, Korean line breaks, chart labels present, diagram reads in one direction, numbers match the source. Geometry cannot see these.

## Revise loop

```
brief → generate → capture → qa.layout ──pass──▶ screenshots → link.verify → handoff
                     ▲                │
                     └── iterate(revision_prompt + content/structure fixes) ◀── fail (≤ 3 rounds)
```

After three failed rounds: hand over the link with the open findings listed, and propose a re-brief (usually the layout family or diagram grammar was under-specified).

## Calibration record (2026-08-29)

Pilot on a real 14-slide Claude Design export (교육용 실험 안내 덱): before calibration the gate reported 4 critical / 105 warnings, almost all false positives — role-mixed siblings treated as one column, visible (non-clipping) overflow, inline children counted as overlaps, diagram labels judged as a grid, and vertically centered checkbox/label pairs flagged for top misalignment. After adding peer grouping, clipping awareness, DOM-ancestry overlap rules, diagram exclusion, and center-alignment acceptance, the same deck reports 0 critical / 3 warnings, each confirmed real (a 103-word slide, titles 42 px higher on two slides, 15 font sizes). A synthetic deck with planted defects still fails on every planted code.
