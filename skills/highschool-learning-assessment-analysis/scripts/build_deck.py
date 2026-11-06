#!/usr/bin/env python3
"""Build the 'Midnight Keynote' 학평 분석 HTML deck from a data.json file.

usage: build_deck.py DATA.json OUTDIR [--name 학평분석-다크키노트.html]

Data-driven refactor of the approved v2 deck generator (14 slides for the reference student).
Nothing about a specific student is hardcoded here: every number and every sentence comes from
DATA.json (see references/data-schema.md). Derived values (lost points, rates, %p gaps, weakest
areas, 교내 상위 %) are computed here with half-up rounding.

Slides are emitted only when their data exists, so the deck shrinks or grows (about 9-16 slides):
  cover, diagnosis, score table, [national vs school], [subject strengths], [area strengths],
  weak spots, [one detail slide per subject with 영역별 data], [other-subject slides],
  priorities, [admission range], next steps.
"""
import argparse, json, pathlib, re, sys
from decimal import Decimal, ROUND_HALF_UP

SKILL = pathlib.Path(__file__).resolve().parent.parent
ASSETS = SKILL / 'assets'

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;600;800&display=swap" rel="stylesheet">\n'
         '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">')

GLOW, GLOW2, SOFT, AMBER = '#5ac8fa', '#9fdcff', '#c9ccd4', '#e0b36a'
TONE = {'glow': GLOW, 'glow2': GLOW2, 'warn': AMBER, 'soft': SOFT}
VAGUE = ['고도화', '효율화', '최적화', '혁신', '체계적', '극대화', '다양한', '적극', '강화', '개선', '향상']


# ---------------- helpers ----------------
def pct(x):
    """Half-up integer percent (29/40 = 72.5 -> 73). Never use round()."""
    return int(Decimal(str(x)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def d1(x):
    return str(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def fmt(x):
    """Print a number the way it appears on the 성적표 (strings are kept verbatim, e.g. '79.80')."""
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def lab(s):
    """Expand {추정}/{제안}/{제안 목표} markers into the pill labels."""
    if s is None:
        return ''
    s = s.replace('{추정}', '<span class="est-i">추정</span>')
    s = re.sub(r'\{(제안[^}]*)\}', r'<span class="prop-i">\1</span>', s)
    return s


def dot(items):
    return '·'.join(items)


class Deck:
    def __init__(self, data):
        self.d = data
        self.subs = data['subjects']
        self.by = {s['name']: s for s in self.subs}
        self.total = data['exam'].get('school_total')
        self.slides = []
        for s in self.subs:
            s['lost'] = s['full'] - s['raw']
            for a in s.get('areas') or []:
                a['rate'] = a['got'] / a['full'] * 100
                a['avg_rate'] = a['avg'] / a['full'] * 100 if a.get('avg') is not None else None
                a['lost'] = a['full'] - a['got']
            if s.get('areas'):
                # weakest = lowest 득점률; tie -> more points lost; tie -> first listed
                s['weakest'] = min(s['areas'], key=lambda a: (a['rate'], -a['lost']))['name']

    # ---- shared chrome ----
    def head(self, label):
        n = len(self.slides) + 1
        return f'<div class="meta reveal">{label}</div><div class="pg">{n:02d} / @@TOTAL@@</div>'

    def add(self, html):
        self.slides.append(html)

    # ---- pieces ----
    def bars(self, g, delay=2, reveal=True):
        s = self.by[g]
        rs = []
        for a in s['areas']:
            p = a['rate']; ap = a['avg_rate']
            low = a['name'] == s['weakest'] and a['lost'] > 0
            lt = f' · −{a["lost"]}' if a['lost'] else ''
            avg = (f'<div class="avg" style="left:calc({ap:.1f}% - 1px)" data-v="전국 {pct(ap)}%"></div>' if ap is not None else '')
            rs.append(f'''<div class="row{' low' if low else ''}"><div class="t"><b>{a['name']}</b><span>{a['got']}/{a['full']}{lt}<em>{pct(p)}%</em></span></div>
<div class="track"><div class="fill" style="width:{p:.1f}%;transition-delay:.3s"></div>{avg}</div></div>''')
        has_avg = any(a['avg_rate'] is not None for a in s['areas'])
        small = '<small>흰 선 = 전국 평균</small>' if has_avg else ''
        cls = f'grp reveal d{delay}' if reveal else 'grp'
        return f'<div class="{cls}"><h3>{g} 영역별 득점률{small}</h3>{"".join(rs)}</div>'

    @staticmethod
    def chips(items, label='보충학습 문항'):
        return f'<div class="chips"><span class="lb">{label}</span>' + ''.join(f'<i>{x}</i>' for x in items) + '</div>'

    # ---- slides ----
    def cover(self):
        dk = self.d['deck']; hc = self.d.get('headline_combo')
        big = ''
        if hc:
            big = (f'<div class="big reveal d3"><div class="n glow">{hc["pct"]}</div>'
                   f'<div class="l">{hc["label"]} 백분위 · <b>상위 {hc["top"]}%</b></div></div>')
        stats = ''.join(f'<div><b>{a}</b>{b}</div>' for a, b in dk.get('cover_stats', []))
        self.add(f"""<section class="slide cover" aria-label="표지">
<div class="halo" style="left:1010px;top:200px;width:760px;height:760px"></div>
<div class="meta reveal">{dk['meta']}</div>
<h1 class="reveal d1">{dk['cover_title']}</h1>
<p class="sub reveal d2">{dk['cover_sub']}</p>
{big}
<div class="rule" style="bottom:150px"></div>
<div class="stats reveal d5">{stats}</div>
</section>""")

    def diagnosis(self):
        sd = self.d['slides']['diagnosis']
        lines = []
        for i, l in enumerate(sd['lines']):
            c = TONE.get(l.get('tone', 'glow'), GLOW)
            vcls = 'am' if l.get('tone') == 'warn' else 'glow'
            lines.append(f'<div class="dl reveal d{i+2}" style="--c:{c}"><div class="k">{l["key"]}</div><div><b>{lab(l["title"])}</b><span>{lab(l["desc"])}</span></div>'
                         f'<div class="v {vcls}">{l["value"]}<small>{l["value_small"]}</small></div></div>')
        lost_html = ''.join(f'<div><i>{s["name"]}</i><em class="{"z" if s["lost"] == 0 else ""}">{"0" if s["lost"] == 0 else "−" + str(s["lost"])}</em></div>'
                            for s in self.subs)
        cols = len(self.subs)
        style = '' if cols == 6 else f' style="grid-template-columns:230px repeat({cols},1fr)"'
        self.add(f"""<section class="slide" aria-label="종합 진단">
<div class="halo" style="left:1300px;top:240px;width:620px;height:620px;opacity:.7"></div>
{self.head('종합 진단')}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="dg">
 {(chr(10) + ' ').join(lines)}
</div>
<div class="lost reveal d5"{style}><div class="t">잃은 점수<small>만점 − 원점수</small></div>{lost_html}</div>
</section>""")

    def table(self):
        sd = self.d['slides'].get('table', {})
        has_rank = any(s.get('rank') is not None for s in self.subs)
        has_note = any(s.get('table_note') for s in self.subs)
        T = self.total
        th = '<th>과목</th><th>원점수</th><th>표준점수</th><th>백분위</th><th>등급</th>'
        if has_rank:
            th += '<th>교내 석차</th>'
        if has_note:
            th += '<th style="text-align:left">비고</th>'
        rows = []
        for s in self.subs:
            st = s.get('status', '')
            best = st == 'best'

            def v(x, small=''):
                if x is None:
                    return '<td class="na">–</td>'
                inner = f'{x}{f"<small>{small}</small>" if small else ""}'
                return f'<td class="v"><span class="glow">{inner}</span></td>' if best else f'<td class="v">{inner}</td>'
            name = f'<td class="hl">{s["name"]}</td>' if best else f'<td>{s["name"]}</td>'
            cells = [name, v(s['raw'], f'/{s["full"]}'), v(s.get('std')), v(s.get('pct')), v(s.get('grade'))]
            if has_rank:
                cells.append(v(s.get('rank'), f'/{T}' if s.get('rank') is not None else ''))
            if has_note:
                note = ''
                if s.get('table_note'):
                    tag = s.get('tag') or ('강점' if best else '주의')
                    note = f'<span class="tag {"g" if best else "w"}">{tag}</span> {s["table_note"]}'
                cells.append(f'<td class="nt">{note}</td>')
            cls = {'best': ' class="best"', 'warn': ' class="warn"'}.get(st, '')
            rows.append(f'<tr{cls}>{"".join(cells)}</tr>')
        absn = [s['name'] for s in self.subs if s.get('absolute')]
        foot = sd.get('foot')
        if foot is None and absn:
            miss = '표준점수·백분위·교내 석차' if has_rank else '표준점수·백분위'
            foot = f'{dot(absn)}{"은" if self._batchim(absn[-1]) else "는"} 절대평가(등급만 산출)라 {miss}가 없습니다.'
        if foot is None and not has_rank:
            foot = '이번 성적표에는 교내 석차가 없습니다.'
        foot_html = f'\n<div class="foot reveal d4">{lab(foot)}</div>' if foot else ''
        headline = sd.get('headline') or self.auto_table_headline()
        self.add(f"""<section class="slide" aria-label="과목별 성적">
{self.head('과목별 성적')}
<h2 class="reveal d1">{lab(headline)}</h2>
<table class="tbl reveal d2">
<thead><tr>{th}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>{foot_html}
</section>""")

    def auto_table_headline(self):
        best = [s['name'] for s in self.subs if s.get('status') == 'best']
        warn = [s['name'] for s in self.subs if s.get('status') == 'warn']
        a = f'{dot(best)}이 가장 높고' if best else '과목별 성적을 정리했습니다'
        return f'{a}, {"와 ".join(warn)}는 주의가 필요합니다' if warn else a

    def national_vs_school(self):
        sd = self.d['slides'].get('national_vs_school')
        cmp_ = [s for s in self.subs if s.get('rank') is not None and s.get('pct') is not None]
        if not sd or not cmp_ or not self.total:
            return
        T = self.total
        cc = []
        for i, s in enumerate(cmp_[:4]):
            pc = float(s['pct'])
            nat = d1(100 - pc); sch = d1(s['rank'] / T * 100)
            cc.append(f'<div class="cc reveal d{i+2}"><h3>{s["name"]}</h3>'
                      f'<div class="p">전국 · 백분위 {pc:.2f}<b>상위 {nat}<small>%</small></b><span>100 − 백분위</span></div>'
                      f'<div class="p s">교내 · 석차 {s["rank"]}/{T}<b>상위 {sch}<small>%</small></b><span>석차 ÷ {T}</span></div></div>')
        style = '' if len(cc) == 4 else f' style="grid-template-columns:repeat({len(cc)},1fr)"'
        ins = ''
        if sd.get('insight_title'):
            ins = (f'\n<div class="ins reveal d6"><b>{lab(sd["insight_title"])}</b>\n'
                   f'<span>{lab(sd.get("insight_body", ""))}</span></div>')
        self.add(f"""<section class="slide" aria-label="전국 대비 교내 위치">
{self.head('전국 vs 교내 위치')}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="cmp"{style}>{''.join(cc)}</div>{ins}
</section>""")

    def subject_strengths(self):
        sd = self.d['slides'].get('subject_strengths')
        if not sd or not sd.get('cards'):
            return
        cards = []
        for i, c in enumerate(sd['cards'][:3]):
            small = f'<small>{c["n_small"]}</small>' if c.get('n_small') else ''
            cards.append(f'<div class="sc reveal d{i+2}"><i>{i+1:02d}</i><div class="n glow">{c["n"]}{small}</div><b>{lab(c["title"])}</b>'
                         f'<span>{lab(c["desc"])}</span><div class="x"><em>{c["x_em"]}</em>{c["x_label"]}</div></div>')
        style = '' if len(cards) == 3 else f' style="grid-template-columns:repeat({len(cards)},1fr)"'
        self.add(f"""<section class="slide" aria-label="잘한 점 과목 단위">
<div class="halo" style="left:100px;top:300px;width:620px;height:620px"></div>
{self.head(sd.get('label', '잘한 점 ① 과목 단위'))}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="sw"{style}>
 {(chr(10) + ' ').join(cards)}
</div>
</section>""")

    def area_strengths(self):
        sd = self.d['slides'].get('area_strengths')
        if not sd or not sd.get('items'):
            return
        tiles = []
        for i, it in enumerate(sd['items'][:4]):
            a = next(x for x in self.by[it['subject']]['areas'] if x['name'] == it['area'])
            n, full, avg = a['got'], a['full'], a.get('avg')
            if avg is not None:
                ap = avg / full * 100; gap = pct(a['rate'] - ap)
                gp = f'<div class="gp"><em>+{gap}%p</em>전국 대비 격차</div>' if gap >= 0 else f'<div class="gp"><em>{gap}%p</em>전국 대비 격차</div>'
                x = f'<div class="x"><em>{avg:.2f}</em>전국 평균 ({pct(ap)}%)</div>'
            else:
                gp = ''; x = f'<div class="x"><em>{pct(a["rate"])}%</em>내 득점률</div>'
            tiles.append(f'<div class="tile reveal d{i+2}"><i>{i+1:02d}</i><div class="n glow">{n}<small>/{full}</small></div><b>{lab(it["title"])}</b>'
                         f'{gp}<span>{lab(it["desc"])}</span>{x}</div>')
        style = 'top:300px' if len(tiles) == 4 else f'top:300px;grid-template-columns:repeat({len(tiles)},1fr)'
        foot = f'\n<div class="foot reveal d6">{lab(sd["foot"])}</div>' if sd.get('foot') else ''
        self.add(f"""<section class="slide s6" aria-label="잘한 점 영역 단위">
{self.head(sd.get('label', '잘한 점 ② 영역 단위'))}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="tiles" style="{style}">
 {(chr(10) + ' ').join(tiles)}
</div>{foot}
</section>""")

    def weak_rows(self):
        out = []
        for s in self.subs:
            if s.get('areas'):
                a = next(x for x in s['areas'] if x['name'] == s['weakest'])
                if a['lost'] == 0:
                    continue
                out.append(dict(s=s, area=a['name'], g=f'{a["got"]}/{a["full"]}', p=pct(a['rate']), l=a['lost'], rate=a['rate']))
            elif s['lost'] > 0:
                w = s.get('wrong') or []
                area = (f'{len(w)}문항 ({dot(w)}번)' if len(w) <= 3 else f'보충학습 {len(w)}문항') if w else '영역별 점수 없음'
                out.append(dict(s=s, area=area, g=f'{s["raw"]}/{s["full"]}', p=None, l=s['lost'], rate=999))
        out.sort(key=lambda r: (-r['l'], r['rate'], -(r['s'].get('grade') or 0)))
        return out

    def weak(self):
        sd = self.d['slides'].get('weak', {})
        rows_d = self.weak_rows()
        if not rows_d:
            return
        mx = max(r['l'] for r in rows_d)
        unit = min(18, 300 / mx)
        rows = []
        for i, r in enumerate(rows_d[:6]):
            pp = f'<small>{r["p"]}%</small>' if r['p'] is not None else ''
            note = r['s'].get('weak_note', '')
            w = r['l'] * unit
            w = int(w) if float(w).is_integer() else round(w, 1)
            rows.append(f'<tr class="{"top" if i == 0 else ""}"><td class="s">{r["s"]["name"]}</td><td class="a">{r["area"]}</td><td class="g">{r["g"]}{pp}</td>'
                        f'<td class="l"><div class="lb"><em>−{r["l"]}</em><i style="width:{w}px"></i></div></td><td>{lab(note)}</td></tr>')
        top = rows_d[0]
        headline = sd.get('headline') or (f'가장 큰 감점은 {top["s"]["name"]} {top["area"]} −{top["l"]}점입니다' if top['p'] is not None
                                          else f'가장 큰 감점은 {top["s"]["name"]} −{top["l"]}점입니다')
        noarea = [r['s']['name'] for r in rows_d if r['p'] is None]
        foot = '가장 약한 영역 = 과목 안에서 득점률이 가장 낮은 영역.'
        if noarea:
            foot += f' {dot(noarea)}{"은" if self._batchim(noarea[-1]) else "는"} 영역별 점수가 없어 보충학습 문항으로 표시합니다.'
        foot = sd.get('foot', foot)
        dense = '\n<style>.wk.dense td{height:94px}</style>' if len(rows) > 5 else ''
        self.add(f"""<section class="slide" aria-label="보완할 점 한눈에">{dense}
{self.head('보완할 점 한눈에')}
<h2 class="reveal d1">{lab(headline)}</h2>
<table class="wk{' dense' if dense else ''} reveal d2"><thead><tr><th>과목</th><th>가장 약한 영역</th><th>득점 · 득점률</th><th>잃은 점수</th><th>참고</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<div class="foot reveal d4">{lab(foot)}</div>
</section>""")

    @staticmethod
    def _batchim(word):
        ch = word[-1]
        if '가' <= ch <= '힣':
            return (ord(ch) - 0xAC00) % 28 != 0
        return False

    def detail(self, g):
        s = self.by[g]
        sd = self.d['slides'].get('details', {}).get(g, {})
        areas = s['areas']
        losing = sorted([a for a in areas if a['lost'] > 0], key=lambda a: -a['lost'])
        zero = [a for a in areas if a['lost'] == 0]
        ls = ''.join(f'<div>{a.get("short", a["name"])}<em>−{a["lost"]}</em></div>' for a in losing)
        if zero:
            ls += f'<div>{dot([a.get("short", a["name"]) for a in zero])}<em class="z">0</em></div>'
        lost_total = sum(a['lost'] for a in areas)
        blocks = [f'<div class="blk"><h4>잃은 점수 {lost_total}점</h4><div class="ls">{ls}</div></div>']
        w = s.get('wrong') or []
        if sd.get('item_types'):
            typ = ''.join(f'<div><b>{n}</b><span>{t}</span></div>' for n, t in sd['item_types'])
            note = f'\n   <p class="d">{lab(sd["item_types_note"])}</p>' if sd.get('item_types_note') else ''
            blocks.append(f'<div class="blk"><h4>성적표 보충학습 문항 · 유형<span class="est-i">추정</span></h4><div class="typ">{typ}</div>{note}</div>')
        elif w:
            note = f'\n   <p class="d">{lab(sd["chips_note"])}</p>' if sd.get('chips_note') else ''
            blocks.append(f'<div class="blk"><h4>성적표 보충학습 문항</h4>{self.chips(w, "")}{note}</div>')
        if sd.get('diagnosis'):
            blocks.append(f'<div class="blk"><h4>진단</h4><p>{lab(sd["diagnosis"])}</p></div>')
        if sd.get('actions'):
            blocks.append('<div class="blk"><h4>실천</h4><ul>' + ''.join(f'<li>{lab(x)}</li>' for x in sd['actions']) + '</ul></div>')
        cut = s.get('cut')
        if cut:
            diff = s['raw'] - cut['score']
            dl = '여유' if diff >= 0 else '부족'
            dv = f'+{diff}' if diff >= 0 else f'−{-diff}'
            left = (f'<div class="reveal d2">{self.bars(g, reveal=False)}\n'
                    f'  <div class="cut" style="margin-top:44px"><div class="me">내 점수<em>{s["raw"]}</em></div><div>{cut["grade"]}등급 기준<em>{cut["score"]}</em></div><div>{dl}<em>{dv}</em></div></div></div>')
            left = '\n ' + left
        else:
            left = self.bars(g)
        headline = sd.get('headline') or f'{g}는 {s["weakest"]}에서 가장 많이 잃었습니다'
        side = '\n  '.join(blocks)
        self.add(f"""<section class="slide" aria-label="{g} 상세">
{self.head(f'{g} 상세 · {s["raw"]}/{s["full"]}')}
<h2 class="reveal d1">{lab(headline)}</h2>
<div class="det">{left}
 <div class="side reveal d3">
  {side}
 </div></div>
</section>""")

    def kv(self, s):
        warn = s.get('status') == 'warn'
        if s.get('absolute') or s.get('pct') is None:
            cells = [('원점수', f'{s["raw"]}<small>/{s["full"]}</small>', ''), ('등급', fmt(s['grade']), ''),
                     ('평가 방식', '절대평가' if s.get('absolute') else '–', 'style="font:600 34px/1.6 var(--body);color:var(--soft)"')]
        else:
            third = (('교내 석차', f'{s["rank"]}<small>/{self.total}</small>', '') if s.get('rank') is not None
                     else ('등급', fmt(s['grade']), ''))
            cells = [('원점수', f'{s["raw"]}<small>/{s["full"]}</small>', ''), ('백분위', s['pct'], 'class="w"' if warn else ''), third]
        return '<div class="kv">' + ''.join(f'<div>{k}<em{(" " + a) if a else ""}>{v}</em></div>' for k, v, a in cells) + '</div>'

    def others(self):
        for grp in self.d['slides'].get('others', []):
            cols = []
            for i, name in enumerate(grp['subjects']):
                s = self.by[name]
                c = AMBER if s.get('status') == 'warn' else GLOW
                ch = f'\n  {self.chips(s["wrong"])}' if s.get('wrong') else ''
                com = lab(grp.get('comments', {}).get(name, ''))
                p = f'\n  <p>{com}</p>' if com else ''
                cols.append(f'<div class="reveal d{i+2}" style="--c:{c}"><h3>{name}<small>{fmt(s["grade"])}등급</small></h3>\n  {self.kv(s)}{ch}{p}</div>')
            style = '' if len(cols) == 2 else ' style="grid-template-columns:1fr"'
            self.add(f"""<section class="slide" aria-label="{grp.get('aria', grp['label'])}">
{self.head(grp['label'])}
<h2 class="reveal d1">{lab(grp['headline'])}</h2>
<div class="two"{style}>
 {(chr(10) + ' ').join(cols)}
</div>
</section>""")

    def priorities(self):
        sd = self.d['slides']['priorities']
        pcs = []
        for i, it in enumerate(sd['items'][:4]):
            cls = 'glow' if i < 2 else 'd'
            pcs.append(f'<div class="pc"><div class="no {cls}">{i+1}</div><div><b>{lab(it["title"])}</b><span>{lab(it["desc"])}</span></div></div>')
        rts = [f'<div class="rt"><div class="f">{r["freq"]}</div><div><b>{lab(r["title"])}</b><span>{lab(r["desc"])}</span></div></div>'
               for r in sd.get('routine', [])[:4]]
        right = ''
        if rts:
            right = (f'\n <div class="reveal d3"><h3>{sd.get("routine_title", "주간 루틴")}<span class="prop-i">제안</span></h3>\n  '
                     + '\n  '.join(rts) + '\n </div>')
        style = '' if rts else ' style="grid-template-columns:1fr"'
        self.add(f"""<section class="slide" aria-label="보완 우선순위와 학습 제안">
{self.head('보완 우선순위 & 학습 제안')}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="pw"{style}>
 <div class="reveal d2"><h3>우선순위</h3>
  {(chr(10) + '  ').join(pcs)}
 </div>{right}
</div>
</section>""")

    def admission(self):
        sd = self.d['slides'].get('admission')
        if not sd:
            return
        colors = [GLOW, GLOW2, SOFT, AMBER]
        bands = []
        for i, b in enumerate(sd['bands'][:4]):
            li = ''.join(f'<li>{x}</li>' for x in b['items'])
            cls = 'hard' if i == 3 else ''
            bands.append(f' <div class="reveal d{i+3}"><div class="band {cls}" style="--c:{colors[i]}"><div class="k">{b["k"]}</div><div class="d">{b["desc"]}</div><ul>{li}</ul></div></div>')
        hc = self.d.get('headline_combo')
        basis = sd.get('basis') or (f'기준: {hc["label"]} 백분위<b>{hc["pct"]}</b>' if hc else '')
        basis_html = f'\n<div class="basis reveal d2">{basis}</div>' if basis else ''
        foot = f'\n<div class="foot reveal d6">{lab(sd["foot"])}</div>' if sd.get('foot') else ''
        self.add(f"""<section class="slide" aria-label="정시 지원 범위">
{self.head('정시 지원 범위 · ' + sd.get('track', '자연계열'))}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="est reveal d2"><div class="mk"></div><b>추정</b><span>{sd.get('banner', '실제 입결 자료 미확인 · 이 점수가 수능에서 그대로 나온다는 가정')}</span></div>{basis_html}
<div class="bands">
{chr(10).join(bands)}
</div>{foot}
</section>""")

    def next_steps(self):
        sd = self.d['slides']['next']
        its = []
        cs = sd['cautions'][:4]
        for i, c in enumerate(cs):
            st = ' style="border-bottom:0"' if i == len(cs) - 1 else ''
            its.append(f'<div class="it c"{st}><i>{i+1:02d}</i><div><b>{lab(c["title"])}</b><span>{lab(c["desc"])}</span></div></div>')
        tgs = [f'<div class="tg"><div><b>{lab(t["title"])}</b><span>{lab(t["desc"])}</span></div><div class="ft">{t["from"]} → <em>{t["to"]}</em><small>{t.get("unit", "")}</small></div></div>'
               for t in sd.get('targets', [])[:4]]
        right = ''
        if tgs:
            right = (f'\n <div class="reveal d3" style="--c:#5ac8fa"><h3>{sd.get("targets_title", "다음 시험 목표")}<span class="prop-i">제안 목표</span></h3>\n  '
                     + '\n  '.join(tgs) + '\n </div>')
        self.add(f"""<section class="slide" aria-label="다음 단계와 목표">
<div class="halo" style="left:1250px;top:560px;width:600px;height:600px;opacity:.5"></div>
{self.head('다음 단계 & 목표')}
<h2 class="reveal d1">{lab(sd['headline'])}</h2>
<div class="cols" style="gap:100px">
 <div class="reveal d2" style="--c:#e0b36a"><h3>주의</h3>
  {(chr(10) + '  ').join(its)}
 </div>{right}
</div>
</section>""")

    def build(self):
        self.cover()
        self.diagnosis()
        self.table()
        self.national_vs_school()
        self.subject_strengths()
        self.area_strengths()
        self.weak()
        for s in self.subs:
            if s.get('areas'):
                self.detail(s['name'])
        self.others()
        self.priorities()
        self.admission()
        self.next_steps()
        total = len(self.slides)
        return [s.replace('@@TOTAL@@', f'{total:02d}') for s in self.slides]


def render_html(data):
    deck = Deck(data)
    slides = deck.build()
    # normalise edge whitespace so copies of the assets with/without a trailing newline build identically
    base = (ASSETS / 'viewport-base.css').read_text().strip('\n') + '\n'
    css = '\n' + (ASSETS / 'midnight-keynote.css').read_text().strip('\n') + '\n'
    js = (ASSETS / 'deck.js').read_text().strip('\n')
    title = data['deck']['title']
    nl = '\n'
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script>document.documentElement.classList.add('js')</script>
{FONTS}
<style>
/* --- viewport-base.css (mandatory fixed 1920x1080 stage) --- */
{base}
{css}
</style></head>
<body>
<div class="edit-hotzone"></div><button class="edit-toggle" id="editToggle" title="편집 모드 (E)">편집</button>
<div class="deck-viewport"><main class="deck-stage" id="deckStage">
{nl.join(slides)}
</main></div>
<nav class="deck-controls" aria-label="슬라이드 이동"></nav><div class="progress"></div>
{js}
</body></html>""", len(slides)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('data')
    ap.add_argument('outdir')
    ap.add_argument('--name', default='학평분석-다크키노트.html')
    a = ap.parse_args()
    data = json.loads(pathlib.Path(a.data).read_text())
    html, n = render_html(data)
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    (out / a.name).write_text(html)
    hits = [w for w in VAGUE if w in html]
    if hits:
        print('WARNING vague words present:', hits, file=sys.stderr)
    print(json.dumps({'html': str(out / a.name), 'slides': n, 'bytes': len(html.encode())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
