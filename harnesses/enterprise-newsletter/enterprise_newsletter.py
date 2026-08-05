#!/usr/bin/env python3
"""Credential-free deterministic enterprise newsletter renderer and release binder."""
from __future__ import annotations

import argparse, datetime, hashlib, html, json, os, re, stat, sys, tempfile
from pathlib import Path
from typing import Any

VERSION = "0.1.1"
TEMPLATE = "enterprise-dark-v1"
MAX_INPUT = 256_000
PROFILES = {"brief": (1, 4, 2, 8), "newsletter": (2, 6, 3, 12), "capability-catalog": (1, 6, 4, 24)}
HEX = re.compile(r"^[0-9a-f]{64}$")
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
LEAF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EMAIL = re.compile(r"^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$")
SECRET = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?\S+|bearer\s+\S+|(?:api[_-]?key|token|secret)\s*[:=]\s*\S+)")

class Error(Exception):
    def __init__(self, code: str, message: str): super().__init__(message); self.code = code

def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()

def digest(value: Any) -> str: return hashlib.sha256(canonical(value)).hexdigest()

def clean_message(value: str) -> str: return SECRET.sub("[REDACTED]", value)[:500]

def result(command: str, ok: bool, data: Any = None, error: Error | None = None) -> dict:
    out = {"schemaVersion": 1, "ok": ok, "command": command, "effects": [], "version": VERSION}
    if data is not None: out["data"] = data
    if error: out["error"] = {"code": error.code, "message": clean_message(str(error))}
    return out

def root(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute(): raise Error("unsafe_path", "root must be absolute")
    if not p.exists() or not p.is_dir() or p.is_symlink(): raise Error("unsafe_path", "root must be an existing non-symlink directory")
    resolved = p.resolve(strict=True)
    if resolved != p: raise Error("unsafe_path", "root must not contain symlink indirection")
    s = p.stat()
    if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) & 0o077: raise Error("unsafe_path", "root must be owner-only")
    return p

def leaf(raw: str) -> str:
    if not LEAF.fullmatch(raw) or raw in {".", ".."}: raise Error("unsafe_path", "file name must be a bounded relative leaf")
    return raw

def input_path(root_raw: str, name: str) -> Path:
    p = root(root_raw) / leaf(name)
    if p.is_symlink() or not p.is_file(): raise Error("unsafe_path", "input must be a regular non-symlink file")
    if p.stat().st_size > MAX_INPUT: raise Error("input_too_large", "input exceeds 256000 bytes")
    return p

def output_path(root_raw: str, name: str) -> Path:
    p = root(root_raw) / leaf(name)
    if p.exists() or p.is_symlink(): raise Error("clobber_rejected", "output already exists")
    return p

def atomic(path: Path, content: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".enterprise-newsletter-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f: f.write(content); f.flush(); os.fsync(f.fileno())
        if path.exists() or path.is_symlink(): raise Error("clobber_rejected", "output already exists")
        os.link(tmp, path); os.unlink(tmp)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def text(v: Any, field: str, lo: int = 1, hi: int = 2000) -> str:
    if not isinstance(v, str) or not lo <= len(v) <= hi or "\x00" in v: raise Error("invalid_newsletter", f"{field} must be text of length {lo}-{hi}")
    return v

def https(v: Any, field: str) -> str:
    value = text(v, field, 8, 2048)
    if not re.fullmatch(r"https://[^\s<>'\"]+", value, re.I): raise Error("unsafe_link", f"{field} must be an https URL")
    return value

def arr(v: Any, field: str, lo: int, hi: int) -> list:
    if not isinstance(v, list) or not lo <= len(v) <= hi: raise Error("invalid_newsletter", f"{field} must contain {lo}-{hi} items")
    return v

def validate(doc: Any) -> dict:
    required = {"schemaVersion","profile","brand","edition","headline","preheader","executiveLead","atAGlance","keyNumbers","sections","synthesis","methodology","footer","sources"}
    if not isinstance(doc, dict) or set(doc) != required: raise Error("invalid_newsletter", "newsletter fields do not match the contract")
    if doc["schemaVersion"] != 1 or isinstance(doc["schemaVersion"], bool): raise Error("invalid_newsletter", "schemaVersion must be number 1")
    profile = doc["profile"]
    if profile not in PROFILES: raise Error("unsupported_profile", "profile is unsupported")
    if not isinstance(doc["brand"], dict) or not {"name","primaryColor"} <= set(doc["brand"]) <= {"name","primaryColor","tagline"}: raise Error("invalid_newsletter", "brand fields are invalid")
    text(doc["brand"]["name"], "brand.name", 1, 80)
    if not isinstance(doc["brand"]["primaryColor"], str) or not COLOR.fullmatch(doc["brand"]["primaryColor"]): raise Error("invalid_newsletter", "brand.primaryColor must be strict #RRGGBB")
    if "tagline" in doc["brand"]: text(doc["brand"]["tagline"], "brand.tagline", 1, 160)
    if not isinstance(doc["edition"], dict) or set(doc["edition"]) != {"label","date"}: raise Error("invalid_newsletter", "edition fields are invalid")
    text(doc["edition"]["label"], "edition.label", 1, 80)
    try: datetime.date.fromisoformat(doc["edition"]["date"])
    except (TypeError, ValueError): raise Error("invalid_newsletter", "edition.date must be ISO date")
    for f, hi in (("headline",180),("preheader",220),("executiveLead",2000),("methodology",2000)): text(doc[f], f, 1, hi)
    glance = arr(doc["atAGlance"], "atAGlance", 2, 6)
    for i, x in enumerate(glance):
        if not isinstance(x, dict) or not {"title","summary"} <= set(x) <= {"title","summary","signal"}: raise Error("invalid_newsletter", f"atAGlance[{i}] fields are invalid")
        text(x["title"], "glance.title", 1, 100); text(x["summary"], "glance.summary", 1, 300)
        if "signal" in x: text(x["signal"], "glance.signal", 1, 160)
    number_refs=[]
    for x in arr(doc["keyNumbers"], "keyNumbers", 4, 4):
        if not isinstance(x, dict) or set(x) != {"value","label","sourceIds"}: raise Error("invalid_newsletter", "keyNumbers fields are invalid")
        text(x["value"], "keyNumbers.value", 1, 30); text(x["label"], "keyNumbers.label", 1, 100)
        number_refs.append(arr(x["sourceIds"], "keyNumbers.sourceIds", 1, 8))
    sources = arr(doc["sources"], "sources", 1, 40); ids = set()
    for s in sources:
        if not isinstance(s, dict) or set(s) != {"id","title","url","publisher","publishedAt"}: raise Error("invalid_newsletter", "source fields are invalid")
        sid = text(s["id"], "source.id", 1, 40)
        if sid in ids or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", sid): raise Error("invalid_newsletter", "source ids must be unique safe tokens")
        ids.add(sid); text(s["title"], "source.title", 1, 200); text(s["publisher"], "source.publisher", 1, 120); https(s["url"], "source.url")
        try: datetime.date.fromisoformat(s["publishedAt"])
        except (TypeError, ValueError): raise Error("invalid_newsletter", "source.publishedAt must be ISO date")
    if any(any(not isinstance(x,str) or x not in ids for x in refs) for refs in number_refs): raise Error("evidence_missing", "key number has missing or unknown source metadata")
    sec_lo, sec_hi, card_lo, card_hi = PROFILES[profile]; sections = arr(doc["sections"], "sections", sec_lo, sec_hi); cards = 0
    for si, s in enumerate(sections):
        if not isinstance(s, dict) or set(s) != {"title","cards"}: raise Error("invalid_newsletter", f"sections[{si}] fields are invalid")
        text(s["title"], "section.title", 1, 120)
        for c in arr(s["cards"], "section.cards", 1, 12):
            cards += 1
            if not isinstance(c, dict) or set(c) != {"title","facts","whyItMatters","cta","imageAlt"}: raise Error("invalid_newsletter", "card fields are invalid")
            text(c["title"], "card.title", 1, 180); text(c["whyItMatters"], "card.whyItMatters", 1, 1000); text(c["imageAlt"], "card.imageAlt", 1, 240)
            if not isinstance(c["cta"], dict) or set(c["cta"]) != {"label","url"}: raise Error("invalid_newsletter", "cta fields are invalid")
            text(c["cta"]["label"], "cta.label", 1, 80); https(c["cta"]["url"], "cta.url")
            for fact in arr(c["facts"], "card.facts", 1, 8):
                if not isinstance(fact, dict) or set(fact) != {"text","evidenceRequired","sourceIds"} or not isinstance(fact["evidenceRequired"], bool): raise Error("invalid_newsletter", "fact fields are invalid")
                text(fact["text"], "fact.text", 1, 600); refs = arr(fact["sourceIds"], "fact.sourceIds", 0, 8)
                if any(not isinstance(x, str) or x not in ids for x in refs): raise Error("invalid_newsletter", "fact references an unknown source")
                if fact["evidenceRequired"] and not refs: raise Error("evidence_missing", "evidence-required fact has no source metadata")
    if not card_lo <= cards <= card_hi: raise Error("profile_mismatch", f"{profile} requires {card_lo}-{card_hi} cards")
    for x in arr(doc["synthesis"], "synthesis", 1, 6): text(x, "synthesis", 1, 500)
    if not isinstance(doc["footer"], dict) or not {"text","tagline"} <= set(doc["footer"]) <= {"text","tagline","unsubscribeUrl"}: raise Error("invalid_newsletter", "footer fields are invalid")
    text(doc["footer"]["text"], "footer.text", 1, 500)
    text(doc["footer"]["tagline"], "footer.tagline", 1, 160)
    if "unsubscribeUrl" in doc["footer"]: https(doc["footer"]["unsubscribeUrl"], "footer.unsubscribeUrl")
    return doc

def load_newsletter(root_raw: str, name: str) -> dict:
    try: value = json.loads(input_path(root_raw, name).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc: raise Error("malformed_json", f"invalid JSON: {exc}")
    return validate(value)

def esc(v: str) -> str: return html.escape(v, quote=True)
def render_html(d: dict) -> str:
    glance = "".join(f'<tr><td class="n">{i}</td><td><b>{esc(x["title"])}</b><br>{esc(x["summary"])}</td><td>{esc(x.get("signal",""))}</td></tr>' for i,x in enumerate(d["atAGlance"],1))
    tiles = "".join(f'<td><b>{esc(x["value"])}</b><span>{esc(x["label"])}</span></td>' for x in d["keyNumbers"])
    tiles = f"<tr>{tiles[:tiles.find('</td>',tiles.find('</td>')+5)+5]}</tr><tr>{tiles[tiles.find('</td>',tiles.find('</td>')+5)+5:]}</tr>"
    sections=[]
    source_map={x["id"]:x for x in d["sources"]}
    for si,s in enumerate(d["sections"],1):
        cards=[]
        for c in s["cards"]:
            facts=[]
            for f in c["facts"]:
                cites=" ".join(f'<a href="{esc(source_map[x]["url"])}">[{esc(x)}]</a>' for x in f["sourceIds"])
                facts.append(f'<li>{esc(f["text"])} {cites}</li>')
            cards.append(f'<table role="presentation" width="100%" class="card"><tr><td><h3>{esc(c["title"])}</h3><div class="label">FACTS</div><ul>{"".join(facts)}</ul><div class="label">WHY IT MATTERS</div><p class="analysis">{esc(c["whyItMatters"])}</p><p class="alt">Image description: {esc(c["imageAlt"])}</p><p class="link"><a href="{esc(c["cta"]["url"])}">{esc(c["cta"]["label"])}</a></p></td></tr></table>')
        sections.append(f'<table role="presentation" width="100%" class="section"><tr><td><small>SECTION {si:02d}</small><h2>{esc(s["title"])}</h2></td></tr></table>{"".join(cards)}')
    synth="".join(f"<p>{esc(x)}</p>" for x in d["synthesis"])
    unsub=f' · <a href="{esc(d["footer"]["unsubscribeUrl"])}">Unsubscribe</a>' if "unsubscribeUrl" in d["footer"] else ""
    color=d["brand"]["primaryColor"]
    brand_tag=f'<div class="brand-tagline">{esc(d["brand"]["tagline"])}</div>' if "tagline" in d["brand"] else ""
    sources_html="".join(f'<li><a href="{esc(x["url"])}">{esc(x["title"])}</a></li>' for x in d["sources"])
    css=f':root{{--brand-primary:{color}}}body{{margin:0;background:#06101f;color:#dbe7f7;font-family:Arial,sans-serif}}table{{border-collapse:collapse}}.wrap{{width:100%;background:#06101f}}.shell{{width:100%;max-width:720px;margin:auto}}.pad{{padding:28px 18px 48px}}.brand{{letter-spacing:.18em;color:var(--brand-primary);font-weight:800;font-size:13px}}.brand-tagline{{color:#cbd9ea;font-size:13px;margin-top:6px}}h1{{font-size:31px;line-height:1.25;margin:15px 0;color:#fff}}.date{{color:#8ca8c9;font-size:13px}}.rule{{height:2px;background:var(--brand-primary)}}.lead,.panel,.card,.synthesis,.method{{margin-top:18px;background:#0c1b30;border:1px solid #17385f}}.lead td,.panel>tbody>tr>td,.card td,.synthesis td,.method td{{padding:22px}}.eyebrow,.label{{font-size:11px;letter-spacing:.15em;color:var(--brand-primary);font-weight:800}}.copy,.analysis{{font-size:15px;line-height:1.72;color:#cbd9ea}}.analysis{{background:#102a49;border-left:3px solid var(--brand-primary);padding:12px}}.glance td{{padding:11px 7px;border-top:1px solid #1a385a;font-size:12px}}.glance .n{{color:var(--brand-primary);width:22px}}.tiles{{margin-top:10px}}.tiles td{{width:50%;border:5px solid #06101f;background:#102644;padding:17px}}.tiles b,.tiles span{{display:block}}.tiles b{{font-size:25px;color:#fff}}.tiles span{{font-size:11px;color:#9bb4cf}}.section{{margin-top:32px;border-bottom:2px solid var(--brand-primary)}}.section td{{padding:9px 2px}}h2{{color:#fff}}h3{{color:#fff}}.link a{{display:inline-block;background:var(--brand-primary);color:#fff;text-decoration:none;padding:10px 14px}}.alt{{font-size:12px;color:#8fa8c4}}.footer{{text-align:center;color:#7892ad;font-size:11px;padding:22px}}@media(max-width:520px){{h1{{font-size:26px}}.pad{{padding:18px 10px 36px}}.lead td,.panel>tbody>tr>td,.card td,.synthesis td,.method td{{padding:17px}}}}'
    return f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="enterprise-newsletter-template" content="{TEMPLATE}"><title>{esc(d["headline"])}</title><style>{css}</style></head><body><div style="display:none;max-height:0;overflow:hidden">{esc(d["preheader"])}</div><table role="presentation" width="100%" class="wrap"><tr><td><table role="presentation" class="shell" align="center"><tr><td class="pad"><div class="brand">{esc(d["brand"]["name"])}</div>{brand_tag}<div class="date">{esc(d["edition"]["date"])} · {esc(d["edition"]["label"])}</div><h1>{esc(d["headline"])}</h1><div class="rule"></div><table role="presentation" width="100%" class="lead"><tr><td><div class="eyebrow">EXECUTIVE LEAD</div><p class="copy">{esc(d["executiveLead"])}</p></td></tr></table><table role="presentation" width="100%" class="panel"><tr><td><div class="eyebrow">AT A GLANCE</div><table role="presentation" width="100%" class="glance">{glance}</table></td></tr></table><div class="eyebrow">KEY NUMBERS</div><table role="presentation" width="100%" class="tiles">{tiles}</table>{"".join(sections)}<table role="presentation" width="100%" class="synthesis"><tr><td><div class="eyebrow">SYNTHESIS</div>{synth}</td></tr></table><table role="presentation" width="100%" class="method"><tr><td><div class="eyebrow">METHODOLOGY</div><p class="copy">{esc(d["methodology"])}</p></td></tr></table><div class="eyebrow">SOURCES</div><ul>{sources_html}</ul><div class="footer">{esc(d["footer"]["tagline"])}<br>{esc(d["footer"]["text"])}{unsub}</div></td></tr></table></td></tr></table></body></html>\n'

def render_text(d: dict) -> str:
    lines=[d["brand"]["name"]]+([d["brand"]["tagline"]] if "tagline" in d["brand"] else [])+[f'{d["edition"]["date"]} · {d["edition"]["label"]}',d["headline"],"",d["executiveLead"],"","AT A GLANCE"]
    for i,x in enumerate(d["atAGlance"],1): lines.append(f'{i}. {x["title"]}: {x["summary"]}' + (f' — {x["signal"]}' if x.get("signal") else ""))
    lines += ["","KEY NUMBERS"] + [f'{x["value"]} — {x["label"]}' for x in d["keyNumbers"]]
    sm={x["id"]:x for x in d["sources"]}
    for s in d["sections"]:
        lines += ["",s["title"].upper()]
        for c in s["cards"]:
            lines += ["",c["title"],"Facts:"]+[f'- {f["text"]}' + (" " + " ".join(f'[{x}] {sm[x]["url"]}' for x in f["sourceIds"]) if f["sourceIds"] else "") for f in c["facts"]]+[f'Why it matters: {c["whyItMatters"]}',f'{c["cta"]["label"]}: {c["cta"]["url"]}',f'Image description: {c["imageAlt"]}']
    lines += ["","SYNTHESIS"]+[f'- {x}' for x in d["synthesis"]]+["","METHODOLOGY",d["methodology"],"","SOURCES"]+[f'{x["title"]}: {x["url"]}' for x in d["sources"]]+["",d["footer"]["tagline"],d["footer"]["text"]]
    if "unsubscribeUrl" in d["footer"]: lines.append("Unsubscribe: "+d["footer"]["unsubscribeUrl"])
    return "\n".join(lines)+"\n"

def recipients(raw: str) -> tuple[str,int]:
    try: values=json.loads(raw)
    except json.JSONDecodeError: raise Error("invalid_recipients", "recipients must be a JSON array")
    if not isinstance(values,list) or not 1 <= len(values) <= 5000: raise Error("invalid_recipients", "recipients must contain 1-5000 addresses")
    normalized=[]
    for v in values:
        if not isinstance(v,str) or not EMAIL.fullmatch(v.strip()): raise Error("invalid_recipients", "recipient address is invalid")
        normalized.append(v.strip().lower())
    unique=sorted(set(normalized)); return digest(unique),len(unique)

def parity(d: dict, rendered_html: str, rendered_text: str) -> dict:
    """Check required semantic content in both representations; never infer success."""
    def both(value: str) -> bool:
        return esc(value) in rendered_html and value in rendered_text
    checks={
        "headline":both(d["headline"]),
        "cards":all(both(c["title"]) for s in d["sections"] for c in s["cards"]),
        "ctaLinks":all(both(c["cta"]["url"]) for s in d["sections"] for c in s["cards"]),
        "sourceLinks":all(both(s["url"]) for s in d["sources"]),
        "footer":both(d["footer"]["tagline"]) and both(d["footer"]["text"]),
    }
    checks["passed"]=all(checks.values())
    return checks

def schema() -> dict:
    def string(hi: int, lo: int=1, pattern: str|None=None) -> dict:
        out={"type":"string","minLength":lo,"maxLength":hi}
        if pattern: out["pattern"]=pattern
        return out
    def obj(required: list[str], properties: dict) -> dict:
        return {"type":"object","required":required,"properties":properties,"additionalProperties":False}
    sid=string(40,1,r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    ids={"type":"array","minItems":0,"maxItems":8,"items":sid}
    fact=obj(["text","evidenceRequired","sourceIds"],{"text":string(600),"evidenceRequired":{"type":"boolean"},"sourceIds":ids})
    card=obj(["title","facts","whyItMatters","cta","imageAlt"],{"title":string(180),"facts":{"type":"array","minItems":1,"maxItems":8,"items":fact},"whyItMatters":string(1000),"cta":obj(["label","url"],{"label":string(80),"url":string(2048,8,r"^https://[^\\s<>'\"]+$")}),"imageAlt":string(240)})
    props={
      "schemaVersion":{"type":"number","const":1},"profile":{"type":"string","enum":sorted(PROFILES)},
      "brand":obj(["name","primaryColor"],{"name":string(80),"primaryColor":{"type":"string","pattern":r"^#[0-9A-Fa-f]{6}$"},"tagline":string(160)}),
      "edition":obj(["label","date"],{"label":string(80),"date":{"type":"string","format":"date"}}),
      "headline":string(180),"preheader":string(220),"executiveLead":string(2000),
      "atAGlance":{"type":"array","minItems":2,"maxItems":6,"items":obj(["title","summary"],{"title":string(100),"summary":string(300),"signal":string(160)})},
      "keyNumbers":{"type":"array","minItems":4,"maxItems":4,"items":obj(["value","label","sourceIds"],{"value":string(30),"label":string(100),"sourceIds":{"type":"array","minItems":1,"maxItems":8,"items":sid}})},
      "sections":{"type":"array","minItems":1,"maxItems":6,"items":obj(["title","cards"],{"title":string(120),"cards":{"type":"array","minItems":1,"maxItems":12,"items":card}})},
      "synthesis":{"type":"array","minItems":1,"maxItems":6,"items":string(500)},"methodology":string(2000),
      "footer":obj(["text","tagline"],{"text":string(500),"tagline":string(160),"unsubscribeUrl":string(2048,8,r"^https://[^\\s<>'\"]+$")}),
      "sources":{"type":"array","minItems":1,"maxItems":40,"items":obj(["id","title","url","publisher","publishedAt"],{"id":sid,"title":string(200),"url":string(2048,8,r"^https://[^\\s<>'\"]+$"),"publisher":string(120),"publishedAt":{"type":"string","format":"date"}})}
    }
    return {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"urn:clawpod:enterprise-newsletter:1","title":"Enterprise Newsletter","type":"object","required":list(props),"properties":props,"additionalProperties":False,"x-template":TEMPLATE,"x-profileSectionBounds":{"brief":[1,4],"newsletter":[2,6],"capability-catalog":[1,6]},"x-profileCardBounds":{"brief":[2,8],"newsletter":[3,12],"capability-catalog":[4,24]}}

def execute(a) -> dict:
    c=a.command
    if c=="status": return result(c,True,{"ready":True,"credentialRequired":False,"gatewayCalls":False,"emailSending":False,"profiles":sorted(PROFILES),"templates":[TEMPLATE]})
    if c=="schema":
        value=schema()
        if a.output_root: atomic(output_path(a.output_root,a.output), canonical(value))
        return result(c,True,{"schema":value,"written":bool(a.output_root)})
    if c=="inspect":
        p=input_path(a.input_root,a.input); raw=p.read_bytes(); decoded=raw.decode("utf-8")
        return result(c,True,{"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"kind":"html" if decoded.lstrip().lower().startswith("<!doctype html") else "text","hasTemplateMarker":TEMPLATE in decoded,"containsScript":bool(re.search(r"<script\b",decoded,re.I))})
    d=load_newsletter(a.input_root,a.input); cd=digest(d)
    if c=="validate": return result(c,True,{"valid":True,"profile":d["profile"],"contentDigest":cd,"sections":len(d["sections"]),"cards":sum(len(x["cards"]) for x in d["sections"])})
    if c=="render":
        if a.template != TEMPLATE: raise Error("unsupported_template", "template is unsupported")
        hp=output_path(a.output_root,a.html); tp=output_path(a.output_root,a.text)
        if hp==tp: raise Error("unsafe_path", "HTML and text outputs must differ")
        rendered_html=render_html(d); rendered_text=render_text(d); parity_result=parity(d,rendered_html,rendered_text)
        if not parity_result["passed"]: raise Error("parity_failed", "HTML and plain-text required content parity failed")
        hb=rendered_html.encode(); tb=rendered_text.encode(); atomic(hp,hb)
        try: atomic(tp,tb)
        except Exception:
            try: hp.unlink()
            except OSError: pass
            raise
        return result(c,True,{"contentDigest":cd,"template":TEMPLATE,"html":{"file":hp.name,"sha256":hashlib.sha256(hb).hexdigest(),"bytes":len(hb)},"text":{"file":tp.name,"sha256":hashlib.sha256(tb).hexdigest(),"bytes":len(tb)},"parity":parity_result})
    rd,count=recipients(a.recipients)
    if c=="release.prepare":
        if not HEX.fullmatch(a.approved_content_digest or "") or a.approved_content_digest != cd: raise Error("approval_invalid", "approved content digest does not match current content")
        manifest={"schemaVersion":1,"kind":"enterprise-newsletter.release.v1","contentDigest":cd,"recipientSetDigest":rd,"recipientCount":count,"template":TEMPLATE,"profile":d["profile"]}
        manifest["releaseDigest"]=digest(manifest); p=output_path(a.output_root,a.manifest); atomic(p,canonical(manifest))
        return result(c,True,{"manifest":p.name,**manifest})
    if c=="release.verify":
        try: m=json.loads(input_path(a.manifest_root,a.manifest).read_text())
        except json.JSONDecodeError: raise Error("manifest_invalid", "manifest is malformed")
        if not isinstance(m,dict) or set(m)!={"schemaVersion","kind","contentDigest","recipientSetDigest","recipientCount","template","profile","releaseDigest"} or m.get("schemaVersion") != 1 or isinstance(m.get("schemaVersion"),bool) or not all(isinstance(m.get(x),str) for x in ("kind","contentDigest","recipientSetDigest","template","profile","releaseDigest")) or not isinstance(m.get("recipientCount"),int) or isinstance(m.get("recipientCount"),bool): raise Error("manifest_invalid", "manifest does not match the release schema")
        expected={"schemaVersion":1,"kind":"enterprise-newsletter.release.v1","contentDigest":cd,"recipientSetDigest":rd,"recipientCount":count,"template":TEMPLATE,"profile":d["profile"]}
        expected["releaseDigest"]=digest(expected)
        if m != expected: raise Error("release_changed", "content, recipients, or manifest changed after approval")
        return result(c,True,{"verified":True,"contentDigest":cd,"recipientSetDigest":rd,"recipientCount":count,"releaseDigest":expected["releaseDigest"],"readyForApprovedHandoff":True,"deliveryConfirmed":False})
    raise Error("invalid_command", "unsupported command")

class JsonParser(argparse.ArgumentParser):
    def error(self,message): raise Error("invalid_input",message)

def parser():
    p=JsonParser(); sub=p.add_subparsers(dest="command",required=True,parser_class=JsonParser)
    sub.add_parser("status")
    s=sub.add_parser("schema"); s.add_argument("--output-root"); s.add_argument("--output",default="newsletter.schema.json")
    for name in ("validate","render","release.prepare","release.verify"):
        x=sub.add_parser(name); x.add_argument("--input-root",required=True); x.add_argument("--input",required=True)
        if name=="render": x.add_argument("--output-root",required=True); x.add_argument("--html",default="newsletter.html"); x.add_argument("--text",default="newsletter.txt"); x.add_argument("--template",default=TEMPLATE)
        elif name=="release.prepare": x.add_argument("--recipients",required=True); x.add_argument("--approved-content-digest",required=True); x.add_argument("--output-root",required=True); x.add_argument("--manifest",default="release.json")
        elif name=="release.verify": x.add_argument("--recipients",required=True); x.add_argument("--manifest-root",required=True); x.add_argument("--manifest",default="release.json")
    x=sub.add_parser("inspect"); x.add_argument("--input-root",required=True); x.add_argument("--input",required=True)
    return p

def main() -> int:
    command="unknown"
    try:
        a=parser().parse_args(); command=a.command; out=execute(a)
    except Error as exc: out=result(command,False,error=exc)
    except Exception as exc: out=result(command,False,error=Error("internal_error",str(exc)))
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(",",":"))); return 0 if out["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
