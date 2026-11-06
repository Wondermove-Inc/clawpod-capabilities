#!/usr/bin/env python3
"""QA gate for a built 학평 분석 deck. Exits 1 on any failure, 0 when everything passes.

usage: qa.py DATA.json OUTDIR [--name 학평분석-다크키노트.html] [--no-pdf]

Checks (JSON report on stdout):
  numbers      every 성적표 number in data.json (raw/full, std, pct, grade, rank/total, 영역 got/full,
               전국 avg, combined 백분위, wrong items) appears in the HTML text
  rounding     every "NN%" next to a known fraction (got/full) or national rate uses half-up rounding;
               any banker's/floor/truncate mismatch (e.g. 29/40 shown as 72%) fails, and the
               derived rates of every 영역 must appear with the half-up value
  slides_pdf   number of <section class="slide"> == PDF page count == slides/slide-N.png count
  privacy      none of privacy.forbidden_strings appears (HTML, title, render copy)
  emoji        no emoji / pictographs
  nojs         the no-JS fallback CSS (html:not(.js)) and the inline js-flag script are present,
               and .reveal is hidden only under .js
  labels       inferred content carries 추정: admission slide banner, item-type blocks, every
               {추정} marker in data.json rendered as a pill; 제안 pills present for routine/targets
  vague        none of the banned vague words (고도화 효율화 최적화 혁신 체계적 극대화 다양한 적극 강화 개선 향상)
  leftovers    data.qa.must_not_contain strings absent (use it for other students' numbers)
  layout       render.py's _layout.json has no problems (single-line headlines, nothing off-slide/clipped)
"""
import argparse, html as htmlmod, json, pathlib, re, subprocess, sys
from decimal import Decimal, ROUND_HALF_UP

VAGUE = ['고도화', '효율화', '최적화', '혁신', '체계적', '극대화', '다양한', '적극', '강화', '개선', '향상']
EMOJI = re.compile('[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF\uFE0F]')


def hu(x):
    return int(Decimal(str(x)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def visible_text(h):
    h = re.sub(r'<style>.*?</style>', ' ', h, flags=re.S)
    h = re.sub(r'<script>.*?</script>', ' ', h, flags=re.S)
    h = re.sub(r'data-v="([^"]*)"', r'> \1 <', h)  # national-average labels live in data-v attributes
    t = re.sub(r'<[^>]+>', '', h)
    return htmlmod.unescape(t)


def fmtn(x):
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    if isinstance(x, float):
        return f'{x:.2f}'
    return str(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data'); ap.add_argument('outdir')
    ap.add_argument('--name', default='학평분석-다크키노트.html')
    ap.add_argument('--no-pdf', action='store_true')
    a = ap.parse_args()
    data = json.loads(pathlib.Path(a.data).read_text())
    out = pathlib.Path(a.outdir)
    raw = (out / a.name).read_text()
    text = visible_text(raw)
    flat = re.sub(r'\s+', '', text)
    res = {}

    def chk(name, fails):
        res[name] = {'ok': not fails, 'fails': fails[:40]}

    # ---- numbers ----
    miss = []
    T = data['exam'].get('school_total')

    def need(tok, why):
        if tok not in flat:
            miss.append(f'{tok} ({why})')
    for s in data['subjects']:
        n = s['name']
        need(f'{s["raw"]}', f'{n} raw')
        for k in ('std', 'pct', 'grade'):
            if s.get(k) is not None:
                need(fmtn(s[k]), f'{n} {k}')
        if s.get('rank') is not None:
            need(f'{s["rank"]}/{T}', f'{n} rank')
        for ar in s.get('areas') or []:
            need(f'{ar["got"]}/{ar["full"]}', f'{n} {ar["name"]}')
            if ar.get('avg') is not None:
                need(f'전국{hu(ar["avg"] / ar["full"] * 100)}%', f'{n} {ar["name"]} 전국률')
            need(f'{hu(ar["got"] / ar["full"] * 100)}%', f'{n} {ar["name"]} 득점률')
        for w in s.get('wrong') or []:
            if f'<i>{w}</i>' not in raw and w not in flat:
                miss.append(f'{n} wrong {w}')
    hc = data.get('headline_combo')
    if hc:
        need(hc['pct'], 'headline combo')
    chk('numbers', miss)

    # ---- rounding: any "a/b ... NN%" with a wrong rounding ----
    bad = []
    fr = {}
    for s in data['subjects']:
        for ar in s.get('areas') or []:
            fr[(ar['got'], ar['full'])] = ar['got'] / ar['full'] * 100
    # pattern 1: fraction followed (within the same element run) by a percent
    # work on the raw HTML: the percent must start right after a tag ('>NN%'), so '−16' + '43%' never fuse
    for m in re.finditer(r'(\d+)/(\d+)(?:(?!</td>|</div>|%).){0,60}?>\s*(\d{1,3})%', raw):
        g, f, p = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if f and g <= f and (g, f) in fr:
            exp = hu(g / f * 100)
            if p != exp:
                bad.append(f'{g}/{f} shown as {p}% (half-up {exp}%)')
    # pattern 2: for every area rate whose .5 boundary matters, the wrong rounding must not appear next to the fraction
    for (g, f), v in fr.items():
        lo, hi = int(v), int(v) + 1
        exp = hu(v)
        wrong = lo if exp == hi else None
        if wrong is not None and abs(v - lo - 0.5) < 1e-9:
            for m in re.finditer(rf'{g}/{f}(?:(?!</td>|</div>|%).){{0,60}}?>\s*(\d+)%', raw):
                if int(m.group(1)) == wrong:
                    bad.append(f'{g}/{f} rounded to {wrong}% (banker\'s/floor); half-up is {exp}%')
    # pattern 3: global sweep of '%' values that equal floor(x.5) for a known x.5 fraction anywhere in the deck
    for (g, f), v in fr.items():
        if abs(v - int(v) - 0.5) < 1e-9:
            w = int(v)
            if re.search(rf'(?<![\d.]){w}%', text) and not any(
                    abs(vv - w) < 0.5 and hu(vv) == w for vv in fr.values()) and not _explained(w, data):
                bad.append(f'{w}% appears; {g}/{f}={v:.1f} must round half-up to {hu(v)}%')
    chk('rounding', sorted(set(bad)))

    # ---- slides vs pdf ----
    n = len(re.findall(r'<section class="slide', raw))
    f = []
    pngs = len(list((out / 'slides').glob('slide-*.png'))) if (out / 'slides').exists() else None
    if not a.no_pdf:
        pdf = out / (pathlib.Path(a.name).stem + '.pdf')
        if not pdf.exists():
            f.append(f'missing {pdf}')
        else:
            info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
            pages = int(re.search(r'Pages:\s+(\d+)', info).group(1))
            if pages != n:
                f.append(f'pdf pages {pages} != slides {n}')
        if pngs is not None and pngs != n:
            f.append(f'slide PNGs {pngs} != slides {n}')
    totals = set(re.findall(r'<div class="pg">\d+ / (\d+)</div>', raw))
    if totals and totals != {f'{n:02d}'}:
        f.append(f'page-number totals {totals} != {n:02d}')
    chk('slides_pdf', f)
    res['slides_pdf']['slides'] = n

    # ---- privacy ----
    f = []
    others = [raw]
    rd = out / '_render-deck.html'
    if rd.exists():
        others.append(rd.read_text())
    for s in data.get('privacy', {}).get('forbidden_strings', []):
        if s and any(s in o for o in others):
            f.append(f'forbidden string present: {s}')
    chk('privacy', f)

    # ---- emoji ----
    f = sorted(set(EMOJI.findall(text)))
    chk('emoji', [f'emoji {repr(x)}' for x in f])

    # ---- no-JS fallback ----
    f = []
    for need_s in ['html:not(.js) .slide{position:relative;visibility:visible;opacity:1',
                   "document.documentElement.classList.add('js')", '.js .reveal{opacity:0']:
        if need_s not in raw:
            f.append(f'missing: {need_s}')
    if re.search(r'(?<!\.js )\.reveal\{opacity:0', raw.replace('.js .reveal{opacity:0', '')):
        f.append('.reveal hidden without .js guard')
    if 'word-break:keep-all' not in raw:
        f.append('word-break:keep-all missing')
    chk('nojs', f)

    # ---- labels ----
    f = []
    sl = data.get('slides', {})
    if sl.get('admission') and '<div class="est reveal d2"><div class="mk"></div><b>추정</b>' not in raw:
        f.append('admission slide without 추정 banner')
    for g, d in (sl.get('details') or {}).items():
        if d.get('item_types') and '유형<span class="est-i">추정</span>' not in raw:
            f.append(f'{g} item types without 추정')
    dj = json.dumps(data, ensure_ascii=False)
    have = raw.count('<span class="est-i">추정</span>')
    if have < dj.count('{추정}'):
        f.append(f'{{추정}} markers {dj.count("{추정}")} > rendered 추정 pills {have}')
    if sl.get('priorities', {}).get('routine') and '<span class="prop-i">제안</span>' not in raw:
        f.append('routine without 제안 label')
    if sl.get('next', {}).get('targets') and '<span class="prop-i">제안 목표</span>' not in raw:
        f.append('targets without 제안 목표 label')
    # inference keywords must sit near a 추정 pill
    for kw in ['일반적인 학평 배치', '수능형 문항 배치', '학교 학생 수준']:
        for m in re.finditer(re.escape(kw), raw):
            window = raw[m.start(): m.start() + 600]
            if '추정' not in window:
                f.append(f'"{kw}" without nearby 추정')
    chk('labels', f)

    # ---- layout (written by render.py: headline wraps, collisions, off-slide, clipped text) ----
    if not a.no_pdf:
        lp = out / '_layout.json'
        if not lp.exists():
            chk('layout', ['_layout.json missing: run render.py first'])
        else:
            lj = json.loads(lp.read_text())
            chk('layout', lj.get('problems') or ([lj['error']] if lj.get('error') else []))

    # ---- vague words ----
    chk('vague', [w for w in VAGUE if w in text])

    # ---- leftovers ----
    chk('leftovers', [s for s in data.get('qa', {}).get('must_not_contain', []) if s in text])

    ok = all(v['ok'] for v in res.values())
    print(json.dumps({'ok': ok, 'checks': res}, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


def _explained(w, data):
    """A bare 'w%' is allowed when it is a legitimate value elsewhere (e.g. a 상위 %, a target)."""
    allow = set(str(x) for x in data.get('qa', {}).get('allowed_percents', []))
    return str(w) in allow


if __name__ == '__main__':
    main()
