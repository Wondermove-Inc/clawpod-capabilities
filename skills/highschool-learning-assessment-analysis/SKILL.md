---
name: highschool-learning-assessment-analysis
description: "Use when asked to analyze a Korean high-school mock exam score report (national academic assessment, mock exam, or CSAT) and produce the standard 14-slide 'Midnight Keynote' dark HTML deck plus PDF. It extracts scores into a JSON file, auto-derives the analysis (points lost, weakest areas, national-vs-school position, priorities, targets), renders, QA-checks, and delivers. For other deck styles use frontend-slides."
---

# 고등 학습 평가 분석 (highschool-learning-assessment-analysis)

This skill turns one 성적표 (image or PDF) into the approved "Midnight Keynote" dark deck: a single-file HTML with nav, edit mode and a no-JS fallback, plus 1920×1080 slide PNGs and a PDF. Slide copy is Korean. Quality bar: the approved v2 고1 10월 reference deck (2026-11-06). `examples/sample-g1-oct.json` reproduces it byte for byte.

Package:
- `scripts/build_deck.py DATA OUT`: data.json → `OUT/학평분석-다크키노트.html`. Data-driven: slides drop or adapt when data is missing, giving about 10–16 slides.
- `scripts/render.py OUT [--nojs] [--layout-only]`: local-font render copy → DOM layout check (`_layout.json`) → `slides/slide-N.png` → PDF → 2×2 `_sheet-K.png` → `_nojs.png`.
- `scripts/qa.py DATA OUT`: numbers, half-up rounding, slide = PDF page count, privacy, emoji, no-JS CSS, 추정/제안 labels, vague words, leftovers, layout. Exits 1 on any failure.
- `scripts/make_deck.sh DATA OUT`: all three stages in order.
- `scripts/nojs_cdp.sh` + `nojs_shot.mjs`: optional no-JS cross-check with JavaScript truly disabled via CDP.
- `assets/`: the design system (CSS, nav/edit JS, viewport base). Do not edit it per student.
- `references/data-schema.md` (fields and length limits) and `references/analysis-rules.md` (derivations, labelling, copy rules). **Read both before writing data.json.**

## Workflow

1. **Get the 성적표.** Download the image/PDF into `/workspace/documents/<job>/`. Crop and zoom with the image tool (write crops under /workspace, never /tmp) until **every** number is legible: 원점수, 표준점수, 백분위, 등급, 교내 석차/응시자, 조합 백분위, 영역별 득점/배점/전국평균, 보충학습 문항.
2. **Write `data.json`.** Copy the closer example (`examples/sample-g1-oct.json` = 고1 with 교내 석차; `examples/sample-g2-jun.json` = 고2, 선택과목, no 석차) and replace everything. Decimal 성적표 values go in as strings (`"79.80"`). Put the student name and school in `privacy.forbidden_strings`. If another student's deck was made recently, list its distinctive numbers in `qa.must_not_contain`.
3. **Read the numbers back** against the image a second time, field by field, in a separate response. If anything is unreadable, ask the user. Never guess.
4. **Write the copy** in `slides.*` following `references/analysis-rules.md`:
   - The headline states the takeaway, on one line (about 34 chars or less).
   - Use concrete actions. No vague words, no emoji.
   - Label everything not on the 성적표 `{추정}`. Label routines `제안` and targets `제안 목표` (both automatic).
   - Include `admission` (정시 지원 범위) only when the user asks for it or the reference flow calls for it. It always carries the 추정 banner.
5. **Build, render, QA** (sequential; one chromium at a time):
   ```bash
   S=/workspace/skills/highschool-learning-assessment-analysis/scripts
   bash $S/make_deck.sh data.json OUT        # = build_deck.py → render.py --nojs → qa.py (writes OUT/qa.json)
   ```
   To iterate on copy quickly: `python3 $S/build_deck.py data.json OUT && python3 $S/render.py OUT --layout-only`. This takes a few seconds and needs no screenshots. Fix every problem it reports, usually by shortening the headline or text named in `_layout.json`.
6. **View every slide** in a later response than the one that created it. Open each `_sheet-K.png` (4 slides per sheet), and open full-size `slides/slide-N.png` wherever a sheet is too small to judge. Check that there are no blank bodies, no overflow or overlap, and that Korean renders. Open `_nojs.png` once: content must be visible. qa.py exit 0 is necessary but not sufficient.
7. **Deliver.** Send a room message first with 3–5 key findings and which items are 추정. Then, in a **separate** call, attach `학평분석-다크키노트.html` and `.pdf`. A message with both text and files drops the text.

## Delegating this skill (main → worker card)
The card notes must include:
- the 성적표 path;
- the `data.json` path (or an instruction to write it there);
- whether to include the admission slide;
- the output dir;
- the done criteria: `make_deck.sh` exits 0 (qa.py ok, layout ok), every `_sheet-K.png` viewed, numbers read back against the image.

Main re-runs `qa.py` when it reviews the card.

## Rules that keep quality consistent
- Never hardcode a student in the scripts. Everything lives in data.json. If a new layout need appears, add a generic data-driven option to `build_deck.py` and keep `sample-g1-oct.json` byte-identical to the reference. Check this with `cmp` against the reference HTML when it is available, or by re-running qa on both examples.
- Rounding is half-up (29/40 = **73%**). qa.py fails on a 72%.
- Never invent grade cuts, national averages, item topics or 입결. General-knowledge notes (5등급제 from the 2025 고1 cohort, 2028 수능 통합사회·통합과학, 영어 절대평가 cuts) are written as "참고(일반 기준)".
- No name or school anywhere: slides, title, file names.

## Pod constraints and recovery
- **Fonts.** Headless chromium on the pod has no network: CDN fonts hang until timeout. render.py builds `_render-deck.html` with `@font-face` rules pointing at `~/.cache/highschool-learning-assessment-analysis/fonts` (about 6.7 MB of Pretendard woff2 + Inter latin). These are downloaded with `curl -4` on first use; IPv6 may not work. Fonts are not bundled. The delivered HTML keeps the CDN links for real browsers.
  - If a download fails, check `curl -4 -I https://cdn.jsdelivr.net` and retry.
  - To force a fresh cache, delete `~/.cache/highschool-learning-assessment-analysis/fonts/fonts-local.css`.
  - `HS_DECK_FONT_CACHE` overrides the cache location.
- **Chromium.** render.py uses `timeout 60` per shot, a fresh temporary `--user-data-dir`, `--virtual-time-budget=5000` (the reveal animation finishes) and one retry. Never `pkill chromium`: the desktop and browser tools share it. Run one render at a time; the pod memory limit is 4 GB.
- **No-JS shot.** chromium `--screenshot` writes nothing when `scriptEnabled=false`. render.py instead renders a copy with every `<script>` removed. That is the same state a no-JS viewer sees.
  - Optional cross-check with JS truly disabled: `bash $S/nojs_cdp.sh OUT/_render-deck.html OUT/_nojs-cdp.png` (CDP `Emulation.setScriptExecutionDisabled`). It prints `state "|visible|1|..."`, where the empty html class means no `js` flag; then view the PNG.
- **Blank slide body in a PNG.** The reveal had not finished. Re-shoot only that slide with `render.py OUT --only N`; the PDF and sheets are rebuilt.
- **Layout check fails.**
  - Headline wraps: shorten the headline.
  - Collision or off-slide: shorten that element's text using the limits in data-schema.md.
  - If a long list is the cause, cut items: `wrong[]` with more than 3 items is shown as "보충학습 N문항" in the 보완할 점 table automatically.
- **qa numbers failure.** A value in data.json does not appear on any slide. Either it belongs in the copy (put it there) or the data has a typo. Recheck it against the image.
- **Image tool** rejects `/tmp` paths. Keep all outputs under `/workspace`.

## Validation record (2026-11-06)
- `sample-g1-oct.json` → HTML byte-identical to the approved deck; slide PNGs pixel-identical (max channel diff 3/255 on 2 slides from the halo animation phase); 14 slides, 14 PDF pages; qa exit 0.
- `sample-g2-jun.json` (고2 6월, 미적분, 물리학Ⅰ/화학Ⅰ, no 석차, 영어 3등급) → 12 slides; qa exit 0; no sample-1 strings.
- Negative test: changing the 29/40 rate to 72% makes qa exit 1 (rounding + numbers checks).
- `nojs_cdp.sh` on the sample-g1 render: state `"|visible|1|15456"`; cover content visible with JS disabled.
