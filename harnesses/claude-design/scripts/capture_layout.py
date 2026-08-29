#!/usr/bin/env python3
"""Offline layout capture for the Claude Design quality gate.

Takes an exported `.dc.html` deck, injects the same geometry-capture script the
Skill uses in the live browser, renders it once in headless Chromium, and writes
the layout JSON that `projects.qa.layout --layout-json` consumes. No network, no
login, no provider calls: the deck file is the only input.

    capture_layout.py --deck deck.dc.html --out layout.json [--chromium /usr/bin/chromium]
        [--docker-image clawpod/agent:latest] [--width 1920 --height 1080] [--slide-selector CSS]

Chromium is resolved from --chromium, then PATH, then (if --docker-image is set) a
throwaway container with the deck directory mounted read-only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_SLIDE_SELECTORS = [
    "[data-slide]", "section.slide", ".slide", "[class*='slide']", "[data-page]", ".page", "main > section", "body > div > div",
]

CAPTURE_JS = r"""
(() => {
  const candidates = %SELECTORS%;
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
"""


def build_injected_deck(deck: Path, selectors: list[str]) -> str:
    source = deck.read_text(encoding="utf-8", errors="replace")
    script = CAPTURE_JS.replace("%SELECTORS%", json.dumps(selectors))
    tag = "<script>window.addEventListener('load', () => setTimeout(() => {" + script + "}, 800));</script>"
    if "</body>" in source:
        return source.replace("</body>", tag + "</body>", 1)
    return source + tag


def resolve_chromium(explicit: str | None) -> list[str] | None:
    for candidate in ([explicit] if explicit else []) + ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"]:
        found = shutil.which(candidate) if candidate else None
        if found:
            return [found]
    return None


def run_chromium(argv_prefix: list[str], url: str, width: int, height: int, timeout: int) -> str:
    argv = argv_prefix + ["--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars", "--run-all-compositor-stages-before-draw", f"--virtual-time-budget={min(timeout, 20) * 1000}", f"--window-size={width},{height}", "--dump-dom", url]
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, errors="replace")
    if completed.returncode != 0 and not completed.stdout:
        raise RuntimeError(f"chromium exited {completed.returncode}: {completed.stderr.strip()[:500]}")
    return completed.stdout


def extract_layout(dom: str) -> dict:
    match = re.search(r'<script type="application/json" id="__layout_capture__">(.*?)</script>', dom, re.S)
    if not match:
        raise RuntimeError("capture script did not run; the deck may block scripts or take longer than the virtual time budget")
    return json.loads(html.unescape(match.group(1)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deck", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--chromium")
    parser.add_argument("--docker-image")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--slide-selector", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)
    deck = Path(args.deck).resolve()
    if not deck.is_file():
        print(json.dumps({"ok": False, "error": {"code": "NOT_FOUND", "message": f"deck not found: {deck}"}}))
        return 2
    selectors = args.slide_selector + DEFAULT_SLIDE_SELECTORS
    with tempfile.TemporaryDirectory(prefix="dc-capture-") as tmp:
        work = Path(tmp)
        injected = work / "deck.injected.html"
        injected.write_text(build_injected_deck(deck, selectors), encoding="utf-8")
        os.chmod(work, 0o755); os.chmod(injected, 0o644)
        chromium = resolve_chromium(args.chromium)
        try:
            if chromium:
                dom = run_chromium(chromium, injected.as_uri(), args.width, args.height, args.timeout)
                runner = chromium[0]
            elif args.docker_image:
                if not shutil.which("docker"):
                    raise RuntimeError("no chromium on PATH and docker is unavailable")
                prefix = ["docker", "run", "--rm", "-v", f"{work}:/capture:ro", "--entrypoint", "/usr/bin/chromium", args.docker_image]
                dom = run_chromium(prefix, "file:///capture/deck.injected.html", args.width, args.height, args.timeout)
                runner = f"docker:{args.docker_image}"
            else:
                raise RuntimeError("no chromium found; pass --chromium or --docker-image")
            layout = extract_layout(dom)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            print(json.dumps({"ok": False, "error": {"code": "CAPTURE_FAILED", "message": str(error)[:800]}}))
            return 6
    layout["source"] = {"deck": str(deck), "bytes": deck.stat().st_size, "runner": runner, "requestedViewport": [args.width, args.height]}
    Path(args.out).write_text(json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {"ok": True, "out": args.out, "slides": len(layout["slides"]), "slideSelector": layout.get("slideSelector"), "viewport": layout["viewport"], "elements": sum(len(s["elements"]) for s in layout["slides"])}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
