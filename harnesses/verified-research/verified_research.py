#!/usr/bin/env python3
"""Deterministic evidence capture. Content is untrusted data, never instructions."""
from __future__ import annotations
import argparse, hashlib, html, ipaddress, json, os, re, socket, subprocess, tempfile, urllib.error, urllib.parse, urllib.request, uuid
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES=5_000_000; MAX_TEXT=1_000_000; MAX_ITEMS=50; MAX_REDIRECTS=5; SAFE_PORTS={80,443}; VERSION=1
class VError(Exception):
 def __init__(self, code, message, retryable=False): self.code,self.message,self.retryable=code,message,retryable
class TextParser(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]; self.skip=0; self.canonical=None; self.title=None; self._title=False
 def handle_starttag(self,t,a):
  d=dict(a); self.skip += t in ('script','style','noscript'); self._title=t=='title'
  if t=='link' and 'canonical' in d.get('rel','').lower(): self.canonical=d.get('href')
 def handle_endtag(self,t):
  if t in ('script','style','noscript') and self.skip: self.skip-=1
  if t=='title': self._title=False
 def handle_data(self,d):
  if not self.skip:
   self.parts.append(d)
   if self._title: self.title=(self.title or '')+d

def stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(b): return hashlib.sha256(b).hexdigest()
def normalize(s):
 s=html.unescape(s).replace('\r\n','\n').replace('\r','\n').replace('\x00','')
 lines=[]
 for x in s.split('\n'):
  x=re.sub(r'[ \t\f\v]+',' ',x).strip()
  if x: lines.append(x)
 return '\n'.join(lines)[:MAX_TEXT]
def safe_path(root, rel, must_exist=False):
 if not root or not rel: raise VError('INVALID_PATH','explicit root and relative path required')
 p=Path(root).resolve(); q=Path(rel)
 if q.is_absolute() or '..' in q.parts: raise VError('INVALID_PATH','absolute paths and traversal are forbidden')
 cur=p
 for part in q.parts:
  cur=cur/part
  if cur.is_symlink(): raise VError('INVALID_PATH','symlinks are forbidden')
 out=(p/q).resolve(strict=False)
 if p!=out and p not in out.parents: raise VError('INVALID_PATH','path escapes root')
 if must_exist and not out.is_file(): raise VError('INVALID_PATH','input file missing')
 return out
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.tmp-',dir=path.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass
def clean_url(url, allow_test=False):
 try: u=urllib.parse.urlsplit(url)
 except ValueError: raise VError('UNSAFE_URL','malformed URL')
 if u.scheme not in ('http','https') or not u.hostname or u.username or u.password: raise VError('UNSAFE_URL','only credential-free HTTP(S) URLs are allowed')
 try: host=u.hostname.encode('idna').decode('ascii').lower()
 except UnicodeError: raise VError('UNSAFE_URL','invalid IDN')
 if host!=u.hostname.lower() and any(ord(c)>127 for c in u.hostname): raise VError('UNSAFE_URL','Unicode hostnames must be supplied as canonical ASCII IDNA')
 if host=='localhost' or host.endswith('.localhost') or (u.port and u.port not in SAFE_PORTS):
  if not (allow_test and host in ('127.0.0.1','localhost')): raise VError('UNSAFE_URL','localhost or unsafe port')
 try: infos=socket.getaddrinfo(host,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)
 except socket.gaierror as e: raise VError('DNS_ERROR',str(e),True)
 for info in infos:
  ip=ipaddress.ip_address(info[4][0].split('%')[0])
  unsafe=not ip.is_global
  if unsafe and not (allow_test and ip.is_loopback): raise VError('UNSAFE_URL','host resolves to non-public address')
 return urllib.parse.urlunsplit((u.scheme,host+((':'+str(u.port)) if u.port else ''),u.path or '/',u.query,''))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k): return None
def fetch(url, timeout=10, max_bytes=MAX_BYTES):
 test=os.getenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE')=='1'; current=clean_url(url,test); opener=urllib.request.build_opener(NoRedirect)
 for _ in range(MAX_REDIRECTS+1):
  req=urllib.request.Request(current,headers={'User-Agent':'ClawPod-Verified-Research/0.1','Accept-Encoding':'identity','Accept':'text/html,application/json,application/xml,application/rss+xml,application/atom+xml,application/pdf;q=0.9,*/*;q=0.1'})
  try: resp=opener.open(req,timeout=max(1,min(timeout,30)))
  except urllib.error.HTTPError as e:
   if e.code in (301,302,303,307,308):
    loc=e.headers.get('Location');
    if not loc: raise VError('HTTP_ERROR','redirect missing Location')
    current=clean_url(urllib.parse.urljoin(current,loc),test); continue
   raise VError('HTTP_ERROR',f'HTTP {e.code}',e.code in (408,429) or e.code>=500)
  except (urllib.error.URLError,TimeoutError) as e: raise VError('FETCH_ERROR',str(e.reason if hasattr(e,'reason') else e),True)
  ctype=resp.headers.get_content_type(); raw=resp.read(max_bytes+1)
  if len(raw)>max_bytes: raise VError('SIZE_LIMIT','response exceeds byte limit')
  return record(current,resp.geturl(),ctype,raw)
 raise VError('REDIRECT_LIMIT','too many redirects')
def record(requested,final,ctype,raw):
 title=canonical=None; kind='binary'; extraction='ok'; text=''
 charset='utf-8'
 if ctype=='application/pdf' or raw.startswith(b'%PDF'):
  kind='pdf'; extraction='dependency_missing'
  try:
   p=subprocess.run(['pdftotext','-layout','-','-'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,check=True)
   text=normalize(p.stdout.decode('utf-8','replace')); extraction='ok' if text else 'unsupported'
  except (FileNotFoundError,subprocess.SubprocessError): pass
 elif 'json' in ctype:
  kind='json'
  try: text=normalize(json.dumps(json.loads(raw.decode(charset)),ensure_ascii=False,sort_keys=True,indent=2))
  except Exception: raise VError('MALFORMED_CONTENT','invalid JSON')
 elif any(x in ctype for x in ('xml','rss','atom')) or raw.lstrip().startswith(b'<?xml'):
  kind='feed'
  try:
   root=ElementTree.fromstring(raw); text=normalize('\n'.join(x.strip() for x in root.itertext() if x.strip()))
  except ElementTree.ParseError: raise VError('MALFORMED_CONTENT','invalid XML')
 else:
  kind='html'
  p=TextParser(); p.feed(raw.decode(charset,'replace')); text=normalize('\n'.join(p.parts)); title=normalize(p.title or '') or None
  canonical=urllib.parse.urljoin(final,p.canonical) if p.canonical else None
  if canonical:
   try: canonical=clean_url(canonical,os.getenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE')=='1')
   except VError: canonical=None
 sid='src-'+digest(raw)[:16]
 return {'schemaVersion':1,'id':sid,'requestedUrl':requested,'finalUrl':final,'canonicalUrl':canonical,'mediaType':ctype,'kind':kind,'title':title,'metadataCandidates':[],'rawSha256':digest(raw),'textSha256':digest(text.encode()),'text':text,'lineCount':len(text.splitlines()) if text else 0,'extraction':extraction,'rawBytes':len(raw)}
def load(root,rel):
 try: return json.loads(safe_path(root,rel,True).read_text())
 except json.JSONDecodeError: raise VError('MALFORMED_INPUT','invalid JSON input')
def output(command,data=None,error=None):
 base={'ok':error is None,'schemaVersion':1,'command':command,'requestId':str(uuid.uuid4()),'data':data,'effects':[],'provenance':{'tool':'verified-research','version':'0.1.0'}}
 if error: base['error']={'code':error.code,'message':error.message,'retryable':error.retryable}
 return base
def write_json(root,rel,value): atomic(safe_path(root,rel), (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
def cmd(args):
 c=args.command
 if c=='source.fetch':
  r=fetch(args.url,args.timeout,args.max_bytes)
  if args.snapshot:
   write_json(args.output_root,args.snapshot,r)
  return {'source':r}
 if c=='source.batch':
  m=load(args.input_root,args.manifest); urls=m.get('urls') if isinstance(m,dict) else None
  if not isinstance(urls,list) or len(urls)>MAX_ITEMS or not all(isinstance(x,str) for x in urls): raise VError('MALFORMED_INPUT','urls must be a bounded string array')
  records=[]; failures=[]; seen={}
  for i,u in enumerate(urls):
   try:
    r=fetch(u,args.timeout,args.max_bytes); key=r.get('canonicalUrl') or r['finalUrl']
    if key in seen or r['rawSha256'] in seen: r['duplicateOf']=seen.get(key) or seen.get(r['rawSha256'])
    else: seen[key]=seen[r['rawSha256']]=r['id']
    records.append(r)
   except VError as e: failures.append({'index':i,'url':re.sub(r'//[^/@]+@','//[redacted]@',u),'error':{'code':e.code,'message':e.message,'retryable':e.retryable}})
  d={'sources':records,'failures':failures,'partial':bool(failures)}
  if args.output: write_json(args.output_root,args.output,d)
  return d
 if c=='source.import':
  p=safe_path(args.input_root,args.capture,True); raw=p.read_bytes()
  if len(raw)>args.max_bytes: raise VError('SIZE_LIMIT','capture exceeds byte limit')
  url=clean_url(args.source_url) if args.source_url else None; r=record(url,url,args.media_type,raw)
  if args.output: write_json(args.output_root,args.output,r)
  return {'source':r}
 if c=='bundle.build':
  src=load(args.input_root,args.sources); cl=load(args.input_root,args.claims)
  sources=src.get('sources',src if isinstance(src,list) else []); claims=cl.get('claims',cl if isinstance(cl,list) else [])
  if not isinstance(sources,list) or not isinstance(claims,list): raise VError('MALFORMED_INPUT','sources and claims must be arrays')
  core={'schemaVersion':1,'sources':sources,'claims':claims}; core['manifestSha256']=digest(stable(core).encode())
  write_json(args.output_root,args.output,core)
  md=['# Evidence Bundle','']+[f"## {x.get('id','claim')}: {x.get('text','')}" for x in claims]
  atomic(safe_path(args.output_root,args.output+'.md'), ('\n\n'.join(md)+'\n').encode())
  return {'bundle':core,'jsonPath':args.output,'markdownPath':args.output+'.md'}
 if c in ('bundle.validate','bundle.inspect'):
  b=load(args.input_root,args.bundle)
  if c=='bundle.inspect': return {'sourceCount':len(b.get('sources',[])),'claimCount':len(b.get('claims',[])),'claimStatuses':{x.get('id'):x.get('status','unresolved') for x in b.get('claims',[])}}
  issues=[]; core={k:v for k,v in b.items() if k!='manifestSha256'}
  if b.get('manifestSha256')!=digest(stable(core).encode()): issues.append({'code':'MANIFEST_TAMPERED'})
  byid={s.get('id'):s for s in b.get('sources',[])}; hashes={}
  for s in b.get('sources',[]):
   if digest(s.get('text','').encode())!=s.get('textSha256'): issues.append({'code':'TEXT_HASH_MISMATCH','sourceId':s.get('id')})
   key=s.get('canonicalUrl') or s.get('finalUrl');
   if key in hashes: issues.append({'code':'DUPLICATE_SOURCE','sourceId':s.get('id'),'duplicateOf':hashes[key]})
   hashes[key]=s.get('id')
  for claim in b.get('claims',[]):
   if claim.get('status') in (None,'unresolved','conflicted'): issues.append({'code':'UNRESOLVED_CLAIM','claimId':claim.get('id')})
   for ev in claim.get('evidence',[]):
    s=byid.get(ev.get('sourceId'))
    if not s: issues.append({'code':'MISSING_SOURCE','claimId':claim.get('id')}); continue
    a,z=ev.get('startLine'),ev.get('endLine'); lines=s.get('text','').splitlines()
    if not isinstance(a,int) or not isinstance(z,int) or a<1 or z<a or z>len(lines): issues.append({'code':'INVALID_LINE_RANGE','claimId':claim.get('id')}); continue
    exact='\n'.join(lines[a-1:z])
    if ev.get('quote')!=exact: issues.append({'code':'QUOTE_MISMATCH','claimId':claim.get('id')})
  return {'valid':not issues,'issues':issues,'sourceCount':len(byid),'claimCount':len(b.get('claims',[]))}
 raise VError('UNKNOWN_COMMAND','unknown command')
def parser():
 p=argparse.ArgumentParser(); p.add_argument('command',choices=['source.fetch','source.batch','source.import','bundle.build','bundle.validate','bundle.inspect']); p.add_argument('--url'); p.add_argument('--input-root'); p.add_argument('--output-root'); p.add_argument('--manifest'); p.add_argument('--snapshot'); p.add_argument('--output'); p.add_argument('--capture'); p.add_argument('--source-url'); p.add_argument('--media-type',default='text/plain'); p.add_argument('--sources'); p.add_argument('--claims'); p.add_argument('--bundle'); p.add_argument('--timeout',type=int,default=10); p.add_argument('--max-bytes',type=int,default=MAX_BYTES); return p
if __name__=='__main__':
 a=parser().parse_args()
 try: result=output(a.command,cmd(a)); print(json.dumps(result,ensure_ascii=False,sort_keys=True)); raise SystemExit(0)
 except VError as e: print(json.dumps(output(a.command,error=e),ensure_ascii=False,sort_keys=True)); raise SystemExit(2)
