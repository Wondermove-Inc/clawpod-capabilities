#!/usr/bin/env python3
"""Render a built deck to slides/slide-N.png (1920x1080), a PDF and 2x2 contact sheets.

usage: render.py OUTDIR [--name 학평분석-다크키노트.html] [--nojs] [--only N,M]

Why this exists: headless chromium on the ClawPod pod has NO network (any CDN request hangs until
timeout), so the delivered HTML (which keeps CDN <link>s for real browsers) is copied to
_render-deck.html with locally cached @font-face rules. Fonts live in ~/.cache/highschool-learning-assessment-analysis/fonts
(override with HS_DECK_FONT_CACHE); the first run downloads them with curl -4 (IPv4 works, IPv6
may not). Nothing is bundled in the skill.

Safety rules baked in: one chromium at a time (sequential), `timeout 60` per shot, a fresh temporary
--user-data-dir per shot (removed afterwards), --virtual-time-budget=5000 so the entrance reveal
has finished. It never kills other chromium processes.

Before shooting, a DOM layout check (script-free copy + one measuring script, chromium --dump-dom) writes
_layout.json: headline wraps to 2+ lines, headline/body collisions, elements off the 1920x1080 slide,
clipped text. qa.py fails when _layout.json is not ok. Use --layout-only for a fast iteration loop.

Outputs in OUTDIR: _render-deck.html, slides/slide-N.png, <name>.pdf, _sheet-K.png (2x2), and with
--nojs _nojs.png (top of the deck rendered with all <script> removed = no-JS viewer).
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time
from urllib.parse import urljoin

CACHE = pathlib.Path(os.environ.get('HS_DECK_FONT_CACHE', pathlib.Path.home() / '.cache/highschool-learning-assessment-analysis/fonts'))
PRETENDARD_CSS = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css'
INTER_CSS = 'https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;600;800&display=swap'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CHROMIUM = shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')


def curl(url, dest=None, ua=None):
    cmd = ['curl', '-4', '-fsSL', '--max-time', '60', '--retry', '2']
    if ua:
        cmd += ['-A', ua]
    if dest:
        cmd += ['-o', str(dest)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=150)
    if r.returncode != 0:
        raise SystemExit(f'font download failed ({r.returncode}): {url}\n{r.stderr.decode()[:300]}')
    return r.stdout.decode() if not dest else None


def ensure_fonts():
    """Return @font-face CSS pointing at cached files (absolute file:// URLs). Download on first use."""
    CACHE.mkdir(parents=True, exist_ok=True)
    css_path = CACHE / 'fonts-local.css'
    if css_path.exists():
        css = css_path.read_text()
        files = re.findall(r'url\(file://([^)]+)\)', css)
        if files and all(pathlib.Path(f).exists() and pathlib.Path(f).stat().st_size > 1000 for f in files):
            return css
    faces = []
    # Inter (Google Fonts): keep only the latin subset faces; numbers and Latin are all the deck uses Inter for.
    g = curl(INTER_CSS, ua=UA)
    for block in re.findall(r'@font-face\s*{[^}]+}', g):
        if 'U+0000-00FF' not in block:
            continue
        url = re.search(r'url\((https://[^)]+)\)', block).group(1)
        fn = 'inter-' + url.rstrip('/').split('/')[-1]
        dest = CACHE / fn
        if not dest.exists() or dest.stat().st_size < 1000:
            curl(url, dest)
        faces.append(re.sub(r'src:[^;]+;', f"src: url(file://{dest}) format('woff2');", block))
    # Pretendard (jsDelivr static): woff2 only.
    p = curl(PRETENDARD_CSS)
    for block in re.findall(r'@font-face\s*{[^}]+}', p):
        m = re.search(r"url\(([^)]+\.woff2)\)", block)
        if not m:
            continue
        rel = m.group(1).strip('\'"')
        url = urljoin(PRETENDARD_CSS, rel)
        fn = 'pretendard-' + url.split('/')[-1]
        dest = CACHE / fn
        if not dest.exists() or dest.stat().st_size < 1000:
            curl(url, dest)
        faces.append(re.sub(r'src:[^;]+;', f"src: url(file://{dest}) format('woff2');", block))
    if not faces:
        raise SystemExit('no @font-face rules parsed from the font CSS')
    css = '\n'.join(faces)
    css_path.write_text(css)
    return css


def make_render_html(out, name):
    src = (out / name).read_text()
    faces = ensure_fonts()
    src = re.sub(r'<link[^>]+rel="stylesheet"[^>]*>', '', src)
    src = re.sub(r'<link rel="preconnect"[^>]*>', '', src)
    extra = '.deck-controls,.progress,.edit-toggle,.edit-hotzone{display:none!important}.reveal,.fill{transition:none!important}'
    src = src.replace('<style>', '<style>\n/* local font cache for headless render */\n' + faces + '\n' + extra + '\n', 1)
    rp = out / '_render-deck.html'
    rp.write_text(src)
    return rp, len(re.findall(r'<section class="slide', src))


MEASURE_JS = r"""<script>
addEventListener('load',()=>setTimeout(()=>{
 const res=[];
 document.querySelectorAll('.slide').forEach((sl,i)=>{
  const r0=sl.getBoundingClientRect();const f={slide:i+1,problems:[]};
  const h=sl.querySelector('h2,h1');
  if(h&&h.tagName==='H2'){const lh=parseFloat(getComputedStyle(h).lineHeight)||75;const hh=h.getBoundingClientRect().height;
    f.h2_lines=Math.round(hh/lh);if(hh>lh*1.5)f.problems.push('headline wraps to '+Math.round(hh/lh)+' lines: '+h.textContent.trim().slice(0,60));}
  sl.querySelectorAll('*').forEach(el=>{
   if(el.closest('.halo'))return;const r=el.getBoundingClientRect();if(!r.width||!r.height)return;
   const x0=r.left-r0.left,y0=r.top-r0.top,x1=x0+r.width,y1=y0+r.height;
   if(x0<-2||y0<-2||x1>1922||y1>1082)f.problems.push('off-slide '+el.tagName.toLowerCase()+'.'+el.className+' ['+[x0,y0,x1,y1].map(Math.round)+'] '+(el.textContent||'').trim().slice(0,30));
   const cs=getComputedStyle(el);
   if(el.children.length===0&&el.textContent.trim()&&cs.overflow!=='visible'&&(el.scrollWidth>el.clientWidth+2||el.scrollHeight>el.clientHeight+2))
     f.problems.push('clipped text '+el.tagName.toLowerCase()+': '+el.textContent.trim().slice(0,30));
  });
  // body content must not start above the headline's bottom (headline collision)
  if(h&&h.tagName==='H2'){const hb=h.getBoundingClientRect().bottom-r0.top;
   sl.querySelectorAll('.dg,.tbl,.cmp,.sw,.tiles,.wk,.det,.two,.pw,.est,.bands,.cols,.chart,.pri,.legend,.basis').forEach(b=>{
    const bt=b.getBoundingClientRect().top-r0.top;if(bt<hb+12)f.problems.push('headline collides with body ('+b.className+' top '+Math.round(bt)+' < headline bottom '+Math.round(hb)+'+12)');});}
  res.push(f);});
 const pre=document.createElement('pre');pre.id='layout-json';pre.textContent=JSON.stringify(res);document.body.appendChild(pre);
},300));
</script>"""


def layout_check(out, rp):
    """Measure every slide in a script-free copy (no-JS stacked layout at 1920 wide) with one injected
    measuring script; write _layout.json. Returns the list of problems."""
    html = re.sub(r'<script>.*?</script>', '', rp.read_text(), flags=re.S)
    html = html.replace('</body>', MEASURE_JS + '</body>')
    mp = out / '_render-measure.html'
    mp.write_text(html)
    ud = tempfile.mkdtemp(prefix='chr-hsdeck-')
    try:
        r = subprocess.run(['timeout', '60', CHROMIUM, '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={ud}',
                            '--window-size=1920,1080', '--virtual-time-budget=5000', '--dump-dom', f'file://{mp}'],
                           capture_output=True, text=True)
    finally:
        shutil.rmtree(ud, ignore_errors=True)
    m = re.search(r'<pre id="layout-json">(.*?)</pre>', r.stdout, flags=re.S)
    if not m:
        res = {'ok': False, 'error': f'measure failed rc={r.returncode}'}
    else:
        import html as H
        slides = json.loads(H.unescape(m.group(1)))
        probs = [f'slide {x["slide"]}: {p}' for x in slides for p in x['problems']]
        res = {'ok': not probs, 'problems': probs, 'slides': slides}
    (out / '_layout.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def shoot(url, png, w=1920, h=1080, extra=()):
    ud = tempfile.mkdtemp(prefix='chr-hsdeck-')
    try:
        cmd = ['timeout', '60', CHROMIUM, '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={ud}',
               '--hide-scrollbars', f'--window-size={w},{h}', '--virtual-time-budget=5000', *extra,
               f'--screenshot={png}', url]
        r = subprocess.run(cmd, capture_output=True)
        return r.returncode
    finally:
        shutil.rmtree(ud, ignore_errors=True)


def sheets(out, pngs):
    from PIL import Image
    made = []
    for k in range(0, len(pngs), 4):
        grp = pngs[k:k + 4]
        sheet = Image.new('RGB', (1920, 1080), (40, 40, 40))
        for j, p in enumerate(grp):
            im = Image.open(p).convert('RGB').resize((956, 538))
            sheet.paste(im, ((j % 2) * 964, (j // 2) * 542))
        sp = out / f'_sheet-{k // 4 + 1}.png'
        sheet.save(sp)
        made.append(str(sp))
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outdir')
    ap.add_argument('--name', default='학평분석-다크키노트.html')
    ap.add_argument('--nojs', action='store_true', help='also render _nojs.png with JavaScript disabled')
    ap.add_argument('--layout-only', action='store_true', help='only run the DOM layout check (fast; no screenshots)')
    ap.add_argument('--only', help='comma-separated slide numbers to (re)shoot; PDF/sheets still use all PNGs')
    a = ap.parse_args()
    if not CHROMIUM:
        raise SystemExit('chromium not found')
    out = pathlib.Path(a.outdir).resolve()
    rp, n = make_render_html(out, a.name)
    lay = layout_check(out, rp)
    print('layout:', 'ok' if lay.get('ok') else json.dumps(lay.get('problems') or lay.get('error'), ensure_ascii=False), flush=True)
    if a.layout_only:
        sys.exit(0 if lay.get('ok') else 1)
    sd = out / 'slides'; sd.mkdir(exist_ok=True)
    for old in sd.glob('slide-*.png'):
        m = re.match(r'slide-(\d+)\.png', old.name)
        if m and int(m.group(1)) > n:
            old.unlink()
    todo = [int(x) for x in a.only.split(',')] if a.only else list(range(1, n + 1))
    fails = []
    for i in todo:
        png = sd / f'slide-{i}.png'
        if png.exists():
            png.unlink()
        rc = shoot(f'file://{rp}#{i}', png)
        if rc != 0 or not png.exists():  # one retry
            time.sleep(1)
            rc = shoot(f'file://{rp}#{i}', png)
        ok = png.exists() and png.stat().st_size > 20000
        print(f'slide {i}: rc={rc} bytes={png.stat().st_size if png.exists() else 0}', flush=True)
        if not ok:
            fails.append(i)
    if a.nojs:
        # chromium --screenshot writes nothing when scriptEnabled=false, so emulate a no-JS viewer by
        # stripping every <script> block (same DOM/CSS state: <html> never gets class "js").
        nj = out / '_render-nojs.html'
        nj.write_text(re.sub(r'<script>.*?</script>', '', rp.read_text(), flags=re.S))
        rc = shoot(f'file://{nj}', out / '_nojs.png', 1920, 2240)
        print(f'nojs: rc={rc}', flush=True)
    pngs = [sd / f'slide-{i}.png' for i in range(1, n + 1)]
    missing = [str(p) for p in pngs if not p.exists()]
    if fails or missing:
        print(json.dumps({'ok': False, 'failed': fails, 'missing': missing}), flush=True)
        sys.exit(1)
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in pngs]
    pdf = out / (pathlib.Path(a.name).stem + '.pdf')
    ims[0].save(pdf, save_all=True, append_images=ims[1:], resolution=144.0)
    sh = sheets(out, pngs)
    print(json.dumps({'ok': True, 'layout_ok': bool(lay.get('ok')), 'slides': n, 'pdf': str(pdf), 'sheets': sh, 'render_html': str(rp)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
