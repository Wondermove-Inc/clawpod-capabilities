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

From the fresh canvas of the exact `.dc.html` file, run one Browser `evaluate` per slide root (adapt `SLIDE_SELECTOR` and `TEXT_SELECTOR` from a fresh snapshot; the slide root is the element whose box equals the slide viewport) and save the combined result as JSON:

```js
(() => {
  const SLIDE_SELECTOR = '[data-slide], section.slide';   // adapt from snapshot
  const slides = [...document.querySelectorAll(SLIDE_SELECTOR)];
  const vw = slides[0]?.getBoundingClientRect().width || innerWidth;
  const vh = slides[0]?.getBoundingClientRect().height || innerHeight;
  let n = 0;
  const kindOf = el => el.matches('img,svg,canvas,video') ? 'image'
    : (el.childNodes.length && [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())) ? 'text' : 'shape';
  return JSON.stringify({ viewport: { width: Math.round(vw), height: Math.round(vh) }, slides: slides.map((slide, i) => {
    const base = slide.getBoundingClientRect(); const ids = new Map();
    const els = [...slide.querySelectorAll('*')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2; });
    els.forEach(el => ids.set(el, 'e' + (++n)));
    return { index: i + 1, elements: els.map(el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); const kind = kindOf(el);
      const parent = [...ids.keys()].reverse().find(p => p !== el && p.contains(el));
      return { id: ids.get(el), kind, shape: kind === 'shape' ? (parseFloat(cs.borderRadius) > 40 ? 'pill' : parseFloat(cs.borderRadius) > 0 ? 'rounded' : cs.clipPath && cs.clipPath !== 'none' ? 'polygon' : 'rect') : undefined,
        text: kind === 'text' ? el.innerText.trim().slice(0, 200) : undefined, fontPx: kind === 'text' ? parseFloat(cs.fontSize) : undefined,
        bbox: [Math.round(r.left - base.left), Math.round(r.top - base.top), Math.round(r.width), Math.round(r.height)],
        parent: parent ? ids.get(parent) : undefined, clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight };
    }) };
  }) });
})()
```

Write the returned string to `<workspace>/design-qa/<project>-layout.json`.

### Evaluate

```
projects.qa.layout --layout-json <file> --expected-pages N [--min-font-px 14] [--tolerance-px 4] [--max-words 90] [--overlap-ratio 0.15] [--strict]
```

| Code | Severity | Means |
|---|---|---|
| `TEXT_OVERFLOW` | critical | text wider/taller than its box (scroll > client) |
| `TEXT_OUTSIDE_SHAPE` | critical | a text box escapes its container shape |
| `OVERLAP` | critical | two independent text boxes intersect > 15 % |
| `OFF_CANVAS` | critical | element extends beyond the slide |
| `PAGE_COUNT_MISMATCH` | critical | captured slides ≠ expected |
| `MISALIGNED_EDGE` | warning | two siblings are *almost* aligned (off by 1–4× tolerance) — the classic "오와 열이 안 맞음" |
| `UNEVEN_SPACING` | warning | a row/column of ≥ 3 siblings has unequal gaps |
| `FONT_TOO_SMALL` | warning | below the floor (14 px at 1920×1080) |
| `TEXT_DENSITY` | warning | > 90 words on a slide |
| `INCONSISTENT_SHAPES` | warning | > 3 shape kinds on one slide — diagram has no grammar |
| `TITLE_DRIFT` | warning | body-slide title position varies across slides |
| `FONT_SIZE_SPRAWL` | warning | > 5 distinct font sizes in the deck |
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
