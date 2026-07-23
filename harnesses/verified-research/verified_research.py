#!/usr/bin/env python3
"""Bounded deterministic evidence capture. Fetched content is untrusted data."""
from __future__ import annotations
import argparse, codecs, datetime as dt, email.utils, hashlib, html, ipaddress, json, os, re, shutil, socket, stat, subprocess, tempfile, time, urllib.error, urllib.parse, urllib.request, uuid
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES=5_000_000; MAX_INPUT=8_000_000; MAX_TEXT=1_000_000; MAX_OUTPUT=12_000_000; MAX_ITEMS=50; MAX_CLAIMS=500; MAX_EVIDENCE=50; MAX_REDIRECTS=5; MAX_DEPTH=12; MAX_STRING=1_000_000; SAFE_PORTS={80,443}; STATUSES={'supported','verified','unsupported','unresolved','conflicted'}
class VError(Exception):
 def __init__(self,code,message,retryable=False): self.code,self.message,self.retryable=code,message,retryable
class Partial(VError):
 def __init__(self,data): super().__init__('PARTIAL_FAILURE','one or more batch items failed'); self.data=data

def stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(b): return hashlib.sha256(b).hexdigest()
def normalize(s):
 s=html.unescape(s).replace('\r\n','\n').replace('\r','\n').replace('\x00','')
 return '\n'.join(x for x in (re.sub(r'[ \t\f\v]+',' ',z).strip() for z in s.split('\n')) if x)[:MAX_TEXT]
def validate_shape(v,depth=0):
 if depth>MAX_DEPTH: raise VError('INPUT_LIMIT','JSON nesting too deep')
 if isinstance(v,str) and len(v)>MAX_STRING: raise VError('INPUT_LIMIT','string too long')
 if isinstance(v,list):
  if len(v)>max(MAX_CLAIMS,MAX_ITEMS): raise VError('INPUT_LIMIT','list too long')
  for x in v: validate_shape(x,depth+1)
 elif isinstance(v,dict):
  if len(v)>1000: raise VError('INPUT_LIMIT','object too large')
  for k,x in v.items(): validate_shape(k,depth+1); validate_shape(x,depth+1)
def root_path(root,output=False):
 if not root: raise VError('INVALID_PATH','explicit existing root required')
 p=Path(root)
 if p.is_symlink(): raise VError('INVALID_PATH','symlink root forbidden')
 try: rp=p.resolve(strict=True)
 except FileNotFoundError: raise VError('INVALID_PATH','root must already exist')
 if not rp.is_dir(): raise VError('INVALID_PATH','root must be directory')
 mode=stat.S_IMODE(rp.stat().st_mode)
 if output and mode & 0o022: raise VError('INVALID_PATH','output root must not be group/world writable')
 return rp
def safe_path(root,rel,must_exist=False,output=False):
 p=root_path(root,output)
 if not isinstance(rel,str) or not rel or len(rel)>500 or '\x00' in rel: raise VError('INVALID_PATH','bounded nonempty relative child name required')
 q=Path(rel)
 if q.is_absolute() or '..' in q.parts: raise VError('INVALID_PATH','relative non-traversing path required')
 cur=p
 for part in q.parts:
  cur=cur/part
  if cur.exists() and cur.is_symlink(): raise VError('INVALID_PATH','symlink component forbidden')
 out=p/q
 if must_exist and not out.is_file(): raise VError('INVALID_PATH','input file missing')
 return out
def atomic(path,data,overwrite=False):
 if len(data)>MAX_OUTPUT: raise VError('OUTPUT_LIMIT','output exceeds limit')
 if path.exists() and not overwrite: raise VError('OUTPUT_EXISTS','output exists; pass --overwrite')
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 if path.parent.is_symlink(): raise VError('INVALID_PATH','symlink parent forbidden')
 fd,tmp=tempfile.mkstemp(prefix='.tmp-',dir=path.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
  if path.exists() and not overwrite: raise VError('OUTPUT_EXISTS','output exists')
  os.replace(tmp,path)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass
def read_bounded(path,limit=MAX_INPUT):
 size=path.stat().st_size
 if size>limit: raise VError('INPUT_LIMIT','input exceeds byte limit')
 with path.open('rb') as f:
  b=f.read(limit+1)
 if len(b)>limit: raise VError('INPUT_LIMIT','input exceeds byte limit')
 return b
def load(root,rel):
 try: v=json.loads(read_bounded(safe_path(root,rel,True),MAX_INPUT))
 except UnicodeDecodeError: raise VError('MALFORMED_INPUT','input is not UTF-8')
 except json.JSONDecodeError: raise VError('MALFORMED_INPUT','invalid JSON input')
 validate_shape(v); return v

def syntax_url(url,resolve=True,allow_test=False):
 try: u=urllib.parse.urlsplit(url)
 except ValueError: raise VError('UNSAFE_URL','malformed URL')
 if u.scheme not in ('http','https') or not u.hostname or u.username or u.password: raise VError('UNSAFE_URL','credential-free HTTP(S) URL required')
 try: host=u.hostname.encode('idna').decode('ascii').lower()
 except UnicodeError: raise VError('UNSAFE_URL','invalid IDN')
 if any(ord(c)>127 for c in u.hostname): raise VError('UNSAFE_URL','use canonical ASCII IDNA host')
 try: port=u.port
 except ValueError: raise VError('UNSAFE_URL','invalid port')
 fixture=os.getenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE') if allow_test and os.getenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE')=='1' else None
 fixture_ok=False
 if fixture:
  fp=Path(fixture)
  try:
   st=fp.lstat(); fixture_ok=stat.S_ISREG(st.st_mode) and not fp.is_symlink() and st.st_uid==os.getuid() and stat.S_IMODE(st.st_mode)==0o600
  except OSError: fixture_ok=False
  fixture_ok=fixture_ok and host in ('127.0.0.1','localhost')
 if port and port not in SAFE_PORTS and not fixture_ok: raise VError('UNSAFE_URL','unsafe port')
 try:
  lit=ipaddress.ip_address(host.strip('[]'))
  if not lit.is_global and not (fixture_ok and lit.is_loopback): raise VError('UNSAFE_URL','non-public IP literal')
 except ValueError: pass
 if host=='localhost' or host.endswith('.localhost'):
  if not fixture_ok: raise VError('UNSAFE_URL','localhost forbidden')
 if resolve:
  try: infos=socket.getaddrinfo(host,port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)
  except socket.gaierror as e: raise VError('DNS_ERROR',str(e),True)
  for info in infos:
   ip=ipaddress.ip_address(info[4][0].split('%')[0])
   if not ip.is_global and not (fixture_ok and ip.is_loopback): raise VError('UNSAFE_URL','DNS resolved non-public address')
 net=host+((':'+str(port)) if port else '')
 return urllib.parse.urlunsplit((u.scheme,net,u.path or '/',u.query,''))

class HTMLExtract(HTMLParser):
 BLOCK={'p','div','article','section','main','header','footer','aside','li','tr','td','th','h1','h2','h3','h4','h5','h6','br','blockquote','pre'}
 def __init__(self): super().__init__(convert_charrefs=True); self.lines=[]; self.buf=[]; self.skip=0; self.in_title=False; self.title=[]; self.meta=[]; self.canon=[]; self.times=[]; self.jsonld=[]; self.in_jsonld=False; self.jbuf=[]
 def flush(self):
  s=normalize(' '.join(self.buf)); self.buf=[]
  if s: self.lines.extend(s.splitlines())
 def handle_starttag(self,t,a):
  d={k.lower():(v or '') for k,v in a}; tl=t.lower()
  if tl in ('script','style','noscript'):
   if tl=='script' and 'ld+json' in d.get('type','').lower(): self.in_jsonld=True; self.jbuf=[]
   else: self.skip+=1
  if tl=='title': self.in_title=True
  if tl in self.BLOCK: self.flush()
  if tl=='link' and 'canonical' in d.get('rel','').lower() and d.get('href'): self.canon.append(d['href'])
  if tl=='meta': self.meta.append(d)
  if tl=='time' and d.get('datetime'): self.times.append(d['datetime'])
 def handle_endtag(self,t):
  tl=t.lower()
  if tl=='script' and self.in_jsonld:
   self.in_jsonld=False; self.jsonld.append(''.join(self.jbuf)[:100000]); self.jbuf=[]
  elif tl in ('script','style','noscript') and self.skip: self.skip-=1
  if tl=='title': self.in_title=False
  if tl in self.BLOCK: self.flush()
 def handle_data(self,d):
  if self.in_jsonld: self.jbuf.append(d); return
  if self.skip: return
  if self.in_title: self.title.append(d); return
  self.buf.append(d)
 def finish(self): self.flush(); return normalize('\n'.join(self.lines))

def candidate(field,value,method,confidence='medium',valid=True,diagnostic=None):
 d={'field':field,'rawValue':str(value)[:4000],'method':method,'confidence':confidence,'valid':valid}
 if diagnostic: d['diagnostic']=diagnostic
 return d
def parse_date(raw,as_of=None):
 s=str(raw).strip()
 if not s or len(s)>200: return False,'malformed date'
 x=None
 try:
  if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[Tt ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:[Zz]|[+-]\d{2}:?\d{2})?)?',s): x=dt.datetime.fromisoformat(s.replace('Z','+00:00').replace('z','+00:00'))
  else: x=email.utils.parsedate_to_datetime(s)
 except (TypeError,ValueError,OverflowError): return False,'malformed date'
 if not isinstance(x,dt.datetime): return False,'malformed date'
 if x.tzinfo is None: x=x.replace(tzinfo=dt.timezone.utc)
 try: x=x.astimezone(dt.timezone.utc)
 except (ValueError,OverflowError): return False,'malformed date'
 if as_of:
  limit=as_of if as_of.tzinfo else as_of.replace(tzinfo=dt.timezone.utc)
  if x>limit.astimezone(dt.timezone.utc)+dt.timedelta(days=2): return False,'future date: '+x.isoformat().replace('+00:00','Z')
 return True,x.isoformat().replace('+00:00','Z')
def charset_decode(raw,ctype,header):
 m=re.search(r'charset\s*=\s*["\']?([^;"\'\s]+)',header or '',re.I); names=[m.group(1) if m else None,'utf-8','windows-1252']
 for n in names:
  if not n: continue
  try: codecs.lookup(n); return raw.decode(n,'strict'),n
  except (LookupError,UnicodeDecodeError): continue
 return raw.decode('utf-8','replace'),'utf-8-replacement'
def pdf_text(raw,binary=None,popen_factory=subprocess.Popen,max_output=MAX_TEXT,timeout=10):
 binary=binary or shutil.which('pdftotext')
 if not binary: return '', 'dependency_missing'
 resolved=str(Path(binary).resolve()); env={'PATH':str(Path(resolved).parent),'LANG':'C','LC_ALL':'C'}
 infd,inname=tempfile.mkstemp(prefix='verified-research-pdf-in-'); outfd,outname=tempfile.mkstemp(prefix='verified-research-pdf-out-'); os.close(outfd)
 try:
  with os.fdopen(infd,'wb') as f: f.write(raw)
  try: p=popen_factory([resolved,'-layout',inname,outname],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
  except OSError: return '', 'dependency_missing'
  start=time.monotonic()
  try:
   while p.poll() is None:
    if time.monotonic()-start>timeout: p.kill(); p.wait(); raise VError('TIMEOUT','PDF extraction timed out',True)
    if os.path.getsize(outname)>max_output: p.kill(); p.wait(); raise VError('OUTPUT_LIMIT','PDF text exceeds limit')
    time.sleep(.01)
   if os.path.getsize(outname)>max_output: raise VError('OUTPUT_LIMIT','PDF text exceeds limit')
  finally:
   if p.poll() is None: p.kill(); p.wait()
  data=read_bounded(Path(outname),max_output); text=normalize(data.decode('utf-8','replace')); return text,('ok' if text else 'unsupported')
 finally:
  for name in (inname,outname):
   try: os.unlink(name)
   except FileNotFoundError: pass

def local_name(e): return e.tag.rsplit('}',1)[-1].lower()
def element_text(e): return normalize(' '.join(x for x in e.itertext()))
def feed_extract(root,candidates):
 entries=[]; feed_title=None
 def add(field,value,path,confidence='medium'):
  if value: candidates.append(candidate(field,value,'feed-element:'+path,confidence))
 channel=next((e for e in root.iter() if local_name(e) in ('channel','feed')),root)
 for child in list(channel):
  tag=local_name(child); val=element_text(child); path='/'+local_name(channel)+'/'+tag
  if tag=='title' and val: feed_title=feed_title or val; add('publisher',val,path,'medium'); add('title',val,path,'medium')
  elif tag in ('author','managingeditor','webmaster'):
   name=next((element_text(x) for x in child.iter() if local_name(x)=='name' and element_text(x)),val); add('author',name,path)
  elif tag in ('published','pubdate'): add('published',val,path)
  elif tag in ('updated','lastbuilddate'): add('modified',val,path)
  elif tag=='link': add('link',child.attrib.get('href') or val,path)
 for idx,e in enumerate(x for x in root.iter() if local_name(x) in ('item','entry')):
  item={}; base=f'/{local_name(e)}[{idx}]'
  for child in list(e):
   tag=local_name(child); val=element_text(child); path=base+'/'+tag
   if tag=='link': val=child.attrib.get('href') or val
   if tag=='author': val=next((element_text(x) for x in child.iter() if local_name(x)=='name' and element_text(x)),val)
   if tag in ('title','author','published','pubdate','updated','link') and val:
    field={'pubdate':'published','updated':'modified'}.get(tag,tag); add(field,val,path)
   if val and len(item)<30: item[tag]=val[:4000]
  entries.append(item)
 return normalize(json.dumps({'feedTitle':feed_title,'entries':entries},ensure_ascii=False,sort_keys=True,indent=2))
def source_record(requested,final,ctype,raw,headers=None):
 headers=headers or {}; candidates=[candidate('contentType',headers.get('Content-Type',ctype),'http-header','high'),candidate('finalUrl',final,'http-redirect','high')]
 if headers.get('Last-Modified'): candidates.append(candidate('modified',headers['Last-Modified'],'http-header'))
 title=None; canonical=None; extraction='ok'; kind='text'; text=''
 if ctype=='application/pdf' or raw.startswith(b'%PDF'):
  kind='pdf'; text,extraction=pdf_text(raw)
 elif 'json' in ctype:
  kind='json'
  try: obj=json.loads(raw); validate_shape(obj); text=normalize(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2))
  except (json.JSONDecodeError,UnicodeDecodeError): raise VError('MALFORMED_CONTENT','invalid JSON')
 elif any(x in ctype for x in ('xml','rss','atom')) or raw.lstrip().startswith(b'<?xml'):
  kind='feed'
  try: root=ElementTree.fromstring(raw); text=feed_extract(root,candidates)
  except ElementTree.ParseError: raise VError('MALFORMED_CONTENT','invalid XML')
 elif ctype.startswith('text/plain'):
  kind='text'; decoded,_=charset_decode(raw,ctype,headers.get('Content-Type','')); text=normalize(decoded)
 else:
  kind='html'; decoded,charset=charset_decode(raw,ctype,headers.get('Content-Type','')); p=HTMLExtract(); p.feed(decoded); text=p.finish(); title=normalize(' '.join(p.title)) or None
  if title: candidates.append(candidate('title',title,'html-title','high'))
  mapping={'author':'author','article:published_time':'published','article:modified_time':'modified','og:site_name':'publisher','publisher':'publisher','date':'published'}
  for m in p.meta:
   key=(m.get('property') or m.get('name') or m.get('itemprop')).lower(); val=m.get('content')
   if key in mapping and val: candidates.append(candidate(mapping[key],val,'html-meta'))
  for x in p.times: candidates.append(candidate('published',x,'html-time','low'))
  for blob in p.jsonld:
   try:
    objs=json.loads(blob); objs=objs if isinstance(objs,list) else [objs]
    for o in objs:
     if not isinstance(o,dict): continue
     for k,f in [('headline','title'),('author','author'),('datePublished','published'),('dateModified','modified'),('publisher','publisher')]:
      if k in o: candidates.append(candidate(f,o[k] if isinstance(o[k],str) else stable(o[k]),'json-ld'))
   except (json.JSONDecodeError,VError): candidates.append(candidate('jsonLd',blob[:200],'json-ld',valid=False,diagnostic='malformed JSON-LD'))
  for href in p.canon:
   joined=urllib.parse.urljoin(final or requested or '',href)
   try: val=syntax_url(joined,resolve=False,allow_test=True); candidates.append(candidate('canonicalUrl',val,'html-link','high')); canonical=canonical or val
   except VError: candidates.append(candidate('canonicalUrl','[rejected]','html-link','low',False,'unsafe canonical URL'))
 for c in candidates:
  if c.get('field') in ('published','modified'):
   ok,diag=parse_date(c.get('rawValue',''))
   if ok: c['normalizedTimestamp']=diag
   else: c['valid']=False; c['diagnostic']=diag
 sid='src-'+digest(raw)[:16]
 return {'schemaVersion':1,'id':sid,'requestedUrl':requested,'finalUrl':final,'canonicalUrl':canonical,'mediaType':ctype,'contentTypeHeader':str(headers.get('Content-Type',ctype))[:200],'kind':kind,'title':title,'metadataCandidates':candidates[:100],'rawSha256':digest(raw),'textSha256':digest(text.encode()),'text':text,'lineCount':len(text.splitlines()) if text else 0,'extraction':extraction,'rawBytes':len(raw)},raw
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k): return None
def fetch(url,timeout=10,max_bytes=MAX_BYTES):
 current=syntax_url(url,True,True); opener=urllib.request.build_opener(NoRedirect)
 for _ in range(MAX_REDIRECTS+1):
  req=urllib.request.Request(current,headers={'User-Agent':'ClawPod-Verified-Research/0.1','Accept-Encoding':'identity','Accept':'text/html,application/json,application/xml,application/rss+xml,application/atom+xml,application/pdf,text/plain;q=0.9,*/*;q=0.1'})
  try: resp=opener.open(req,timeout=max(1,min(timeout,30)))
  except urllib.error.HTTPError as e:
   if e.code in (301,302,303,307,308):
    loc=e.headers.get('Location')
    if not loc: raise VError('HTTP_ERROR','redirect missing Location')
    current=syntax_url(urllib.parse.urljoin(current,loc),True,True); continue
   raise VError('HTTP_ERROR',f'HTTP {e.code}',e.code in (408,429) or e.code>=500)
  except (urllib.error.URLError,TimeoutError) as e: raise VError('FETCH_ERROR','network request failed',True)
  enc=resp.headers.get('Content-Encoding','identity').lower()
  if enc not in ('','identity'): raise VError('UNSUPPORTED_ENCODING','compressed responses rejected')
  try: declared=int(resp.headers.get('Content-Length','0'))
  except ValueError: declared=0
  if declared>max_bytes: raise VError('SIZE_LIMIT','Content-Length exceeds byte limit')
  raw=resp.read(max_bytes+1)
  if len(raw)>max_bytes: raise VError('SIZE_LIMIT','response exceeds byte limit')
  final=syntax_url(resp.geturl(),False,True); ctype=resp.headers.get_content_type().lower()
  return source_record(current,final,ctype,raw,dict(resp.headers))
 raise VError('REDIRECT_LIMIT','too many redirects')

def validate_bundle(b,root=None,as_of=None):
 issues=[]; warnings=[]
 if not isinstance(b,dict): raise VError('MALFORMED_INPUT','bundle must be object')
 core={k:v for k,v in b.items() if k!='manifestSha256'}
 if b.get('manifestSha256')!=digest(stable(core).encode()): issues.append({'code':'MANIFEST_TAMPERED'})
 sources=b.get('sources'); claims=b.get('claims')
 if not isinstance(sources,list) or len(sources)>MAX_ITEMS or not isinstance(claims,list) or len(claims)>MAX_CLAIMS: raise VError('INPUT_LIMIT','invalid or oversized source/claim lists')
 ids=set(); byid={}
 for s in sources:
  sid=s.get('id') if isinstance(s,dict) else None
  if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',sid) or sid in ids: issues.append({'code':'INVALID_OR_DUPLICATE_SOURCE_ID','sourceId':sid}); continue
  ids.add(sid); byid[sid]=s
  text=s.get('text'); tsha=s.get('textSha256'); rsha=s.get('rawSha256'); rb=s.get('rawBytes'); media=s.get('mediaType'); snap=s.get('snapshotPath')
  if not isinstance(text,str) or len(text)>MAX_TEXT: issues.append({'code':'INVALID_SOURCE_TEXT','sourceId':sid}); text=''
  if not isinstance(tsha,str) or not re.fullmatch(r'[a-f0-9]{64}',tsha): issues.append({'code':'INVALID_TEXT_HASH','sourceId':sid})
  elif digest(text.encode())!=tsha: issues.append({'code':'TEXT_HASH_MISMATCH','sourceId':sid})
  if not isinstance(rsha,str) or not re.fullmatch(r'[a-f0-9]{64}',rsha): issues.append({'code':'INVALID_RAW_HASH','sourceId':sid})
  if not isinstance(rb,int) or isinstance(rb,bool) or rb<0 or rb>MAX_BYTES: issues.append({'code':'INVALID_RAW_BYTES','sourceId':sid})
  if not isinstance(media,str) or not media or len(media)>200: issues.append({'code':'INVALID_MEDIA_TYPE','sourceId':sid})
  cth=s.get('contentTypeHeader',media)
  if not isinstance(cth,str) or not cth or len(cth)>200: issues.append({'code':'INVALID_CONTENT_TYPE_HEADER','sourceId':sid})
  if snap is not None and (not isinstance(snap,str) or len(snap)>500): issues.append({'code':'INVALID_SNAPSHOT_PATH','sourceId':sid}); snap=None
  for f in ('finalUrl','canonicalUrl'):
   if s.get(f):
    if not isinstance(s[f],str) or len(s[f])>4000: issues.append({'code':'INVALID_LINK','sourceId':sid,'field':f}); continue
    try: syntax_url(s[f],False,True)
    except VError: issues.append({'code':'INVALID_LINK','sourceId':sid,'field':f})
  mdc=s.get('metadataCandidates',[])
  if not isinstance(mdc,list) or len(mdc)>100: issues.append({'code':'INVALID_METADATA_CANDIDATES','sourceId':sid}); mdc=[]
  for x in mdc:
   if not isinstance(x,dict) or not isinstance(x.get('field'),str) or not 1<=len(x['field'])<=64 or not isinstance(x.get('method'),str) or not 1<=len(x['method'])<=200 or x.get('confidence') not in ('high','medium','low') or not isinstance(x.get('valid'),bool) or not isinstance(x.get('rawValue'),str) or len(x['rawValue'])>4000:
    issues.append({'code':'INVALID_METADATA_CANDIDATE','sourceId':sid}); continue
   if x['field'] in ('published','modified'):
    ok,diag=parse_date(x['rawValue'],as_of)
    if not ok: issues.append({'code':'INVALID_DATE','sourceId':sid,'diagnostic':diag})
  fields={x.get('field') for x in mdc if isinstance(x,dict) and x.get('valid') is True}
  if 'published' not in fields and 'modified' not in fields: warnings.append({'code':'MISSING_DATE','sourceId':sid})
  if 'publisher' not in fields: warnings.append({'code':'MISSING_PUBLISHER','sourceId':sid})
  if s.get('fetchState') in ('broken','unfetched'): issues.append({'code':'BROKEN_SOURCE','sourceId':sid})
  if snap and root:
   try: raw=read_bounded(safe_path(root,snap,True),MAX_BYTES)
   except VError: issues.append({'code':'MISSING_SNAPSHOT','sourceId':sid})
   else:
    raw_ok=isinstance(rb,int) and len(raw)==rb and isinstance(rsha,str) and digest(raw)==rsha
    if not raw_ok: issues.append({'code':'RAW_HASH_MISMATCH','sourceId':sid})
    if raw_ok and isinstance(media,str):
     try: derived,_=source_record(None,None,media,raw,{'Content-Type':s.get('contentTypeHeader',media)})
     except VError as e: warnings.append({'code':'TEXT_REEXTRACTION_UNAVAILABLE','sourceId':sid,'diagnostic':e.code})
     else:
      if derived.get('extraction') in ('dependency_missing','unsupported'): warnings.append({'code':'TEXT_REEXTRACTION_UNAVAILABLE','sourceId':sid,'diagnostic':derived.get('extraction')})
      elif derived.get('textSha256')!=tsha: issues.append({'code':'SNAPSHOT_TEXT_MISMATCH','sourceId':sid})
  elif snap: warnings.append({'code':'SNAPSHOT_NOT_CHECKED','sourceId':sid})
 claimids={c.get('id') for c in claims if isinstance(c,dict) and isinstance(c.get('id'),str)}
 seen_claims=set()
 for c in claims:
  cid=c.get('id') if isinstance(c,dict) else None; text=c.get('text') if isinstance(c,dict) else None; statusv=c.get('status') if isinstance(c,dict) else None; evs=c.get('evidence',[]) if isinstance(c,dict) else []
  if not isinstance(cid,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',cid) or cid in seen_claims: issues.append({'code':'INVALID_OR_DUPLICATE_CLAIM_ID','claimId':cid})
  else: seen_claims.add(cid)
  if not isinstance(text,str) or not text.strip() or len(text)>10000: issues.append({'code':'INVALID_CLAIM_TEXT','claimId':cid})
  if statusv not in STATUSES: issues.append({'code':'INVALID_STATUS','claimId':cid})
  if statusv in ('unresolved','conflicted'): issues.append({'code':'UNRESOLVED_CLAIM','claimId':cid})
  if not isinstance(evs,list) or len(evs)>MAX_EVIDENCE: issues.append({'code':'INVALID_EVIDENCE_COUNT','claimId':cid}); continue
  conf=c.get('confidence')
  if conf is not None and (not isinstance(conf,(int,float)) or isinstance(conf,bool) or not 0<=conf<=1): issues.append({'code':'INVALID_CONFIDENCE','claimId':cid})
  contradictions=c.get('contradictions',[])
  if not isinstance(contradictions,list) or len(contradictions)>50: issues.append({'code':'INVALID_CONTRADICTIONS','claimId':cid}); contradictions=[]
  for x in contradictions:
   if not isinstance(x,dict) or not isinstance(x.get('claimId'),str) or x.get('claimId') not in claimids or x.get('claimId')==cid or not isinstance(x.get('reason'),str) or not x['reason'].strip() or len(x['reason'])>4000: issues.append({'code':'INVALID_CONTRADICTION','claimId':cid})
  seen=set(); valid_evidence=0
  for ev in evs:
   if not isinstance(ev,dict) or not isinstance(ev.get('sourceId'),str) or not isinstance(ev.get('quote'),str) or len(ev.get('quote',''))>100000: issues.append({'code':'INVALID_EVIDENCE','claimId':cid}); continue
   key=(ev.get('sourceId'),ev.get('startLine'),ev.get('endLine'))
   if key in seen: issues.append({'code':'DUPLICATE_EVIDENCE','claimId':cid}); continue
   seen.add(key); source=byid.get(ev['sourceId'])
   if not source: issues.append({'code':'MISSING_SOURCE','claimId':cid}); continue
   a,z=ev.get('startLine'),ev.get('endLine'); lines=source.get('text','').splitlines()
   if not isinstance(a,int) or isinstance(a,bool) or not isinstance(z,int) or isinstance(z,bool) or a<1 or z<a or z>len(lines): issues.append({'code':'INVALID_LINE_RANGE','claimId':cid}); continue
   if ev['quote']!='\n'.join(lines[a-1:z]): issues.append({'code':'QUOTE_MISMATCH','claimId':cid}); continue
   valid_evidence+=1
  if statusv in ('supported','verified') and valid_evidence<1: issues.append({'code':'VALID_EVIDENCE_REQUIRED','claimId':cid})
 return issues,warnings

def md_escape(value):
 s=str(value or '').replace('\\','\\\\').replace('`','\\`').replace('[','\\[').replace(']','\\]').replace('<','&lt;').replace('>','&gt;')
 return '\n'.join(('\\'+line if line.startswith('#') else line) for line in s.splitlines())
def metadata_value(source,field):
 for x in source.get('metadataCandidates',[]):
  if isinstance(x,dict) and x.get('field')==field and x.get('valid') is True: return x.get('rawValue','')
 return ''
def render_markdown(bundle,warnings):
 byid={s['id']:s for s in bundle['sources'] if isinstance(s,dict) and isinstance(s.get('id'),str)}; out=['# Evidence Bundle','']
 for c in bundle['claims']:
  out += [f"## Claim: {md_escape(c.get('id'))}",f"- Text: {md_escape(c.get('text'))}",f"- Status: {md_escape(c.get('status'))}",f"- Confidence: {md_escape(c.get('confidence','not provided'))}"]
  evs=c.get('evidence',[])
  if not evs: out.append('- Evidence: none')
  for i,e in enumerate(evs,1):
   src=byid.get(e.get('sourceId'),{}); url=src.get('canonicalUrl') or src.get('finalUrl') or ''; label=md_escape(src.get('title') or src.get('id') or 'source')
   out += [f"### Evidence {i}",f"- Source: {label}",f"- Publisher: {md_escape(metadata_value(src,'publisher') or 'unknown')}",f"- Date: {md_escape(metadata_value(src,'published') or metadata_value(src,'modified') or 'unknown')}",f"- URL: {md_escape(url)}",f"- Lines: {e.get('startLine')}-{e.get('endLine')}",'```text',md_escape(e.get('quote','')),'```']
  cons=c.get('contradictions',[])
  if cons:
   out.append('### Contradictions')
   for x in cons: out.append(f"- {md_escape(x.get('claimId'))}: {md_escape(x.get('reason'))}")
  if c.get('status') in ('unresolved','conflicted'): out.append('- Warning: claim is unresolved or conflicted.')
  out.append('')
 out += ['## Source Inventory','']
 for s in bundle['sources']:
  out += [f"### Source: {md_escape(s.get('id'))}",f"- Title: {md_escape(s.get('title') or 'unknown')}",f"- URL: {md_escape(s.get('canonicalUrl') or s.get('finalUrl') or '')}",f"- Raw SHA-256: `{md_escape(s.get('rawSha256'))}`",f"- Text SHA-256: `{md_escape(s.get('textSha256'))}`",f"- Snapshot: {md_escape(s.get('snapshotPath') or 'not stored')}"]
 for w in warnings: out.append(f"- Validation warning: {md_escape(w.get('code'))} {md_escape(w.get('sourceId',''))}")
 data=('\n'.join(out)+'\n').encode()
 if len(data)>MAX_OUTPUT: raise VError('OUTPUT_LIMIT','Markdown evidence bundle exceeds output limit')
 return data

def output(command,data=None,error=None):
 r={'ok':error is None,'schemaVersion':1,'command':command,'requestId':str(uuid.uuid4()),'data':data,'effects':[],'provenance':{'tool':'verified-research','version':'0.1.1'}}
 if error: r['error']={'code':error.code,'message':error.message,'retryable':error.retryable}
 return r
def write_json(root,rel,v,overwrite=False): atomic(safe_path(root,rel,output=True),(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode(),overwrite)
def cmd(a):
 c=a.command; overwrite=getattr(a,"overwrite",False)
 def require_pair(left,right,label):
  if bool(left)!=bool(right): raise VError('MALFORMED_INPUT',label+' requires both root and relative child name')
 if c=='source.fetch':
  require_pair(getattr(a,'output_root',None),getattr(a,'snapshot',None),'snapshot output')
  r,raw=fetch(a.url,a.timeout,a.max_bytes)
  if a.snapshot:
   snap=a.snapshot+'.bytes'; bp=safe_path(a.output_root,snap,output=True); jp=safe_path(a.output_root,a.snapshot,output=True)
   if not overwrite and (bp.exists() or jp.exists()): raise VError('OUTPUT_EXISTS','snapshot output exists; pass --overwrite')
   atomic(bp,raw,overwrite); r['snapshotPath']=snap; write_json(a.output_root,a.snapshot,r,overwrite)
  return {'source':r}
 if c=='source.batch':
  require_pair(getattr(a,'output_root',None),getattr(a,'output',None),'batch output')
  m=load(a.input_root,a.manifest); urls=m.get('urls') if isinstance(m,dict) else None
  if not isinstance(urls,list) or not urls or len(urls)>MAX_ITEMS or any(not isinstance(x,str) or len(x)>4000 for x in urls): raise VError('MALFORMED_INPUT','urls must be a nonempty bounded string array')
  records=[]; raws=[]; failures=[]; seen={}
  for i,u in enumerate(urls):
   try:
    r,raw=fetch(u,a.timeout,a.max_bytes); key=r.get('canonicalUrl') or r['finalUrl']
    if key in seen or r['rawSha256'] in seen: r['duplicateOf']=seen.get(key) or seen.get(r['rawSha256'])
    else: seen[key]=seen[r['rawSha256']]=r['id']
    records.append(r); raws.append((i,raw))
   except VError as e: failures.append({'index':i,'url':re.sub(r'//[^/@]+@','//[redacted]@',u)[:4000],'error':{'code':e.code,'message':e.message,'retryable':e.retryable}})
  written=[]
  if a.output:
   op=safe_path(a.output_root,a.output,output=True); planned=[]
   for record,(idx,raw) in zip(records,raws):
    rel=f"{a.output}.snapshots/{idx:03d}-{record['rawSha256'][:16]}.bytes"; planned.append((record,raw,rel,safe_path(a.output_root,rel,output=True)))
   if not overwrite and (op.exists() or any(path.exists() for _,_,_,path in planned)): raise VError('OUTPUT_EXISTS','batch output exists; pass --overwrite')
   try:
    for record,raw,rel,path in planned: atomic(path,raw,overwrite); record['snapshotPath']=rel; written.append(rel)
    d={'sources':records,'failures':failures,'partial':bool(failures),'writtenSnapshots':written}; write_json(a.output_root,a.output,d,overwrite)
   except VError as e:
    d={'sources':records,'failures':failures+[{'error':{'code':e.code,'message':e.message,'retryable':e.retryable}}],'partial':True,'writtenSnapshots':written}; raise Partial(d)
  else: d={'sources':records,'failures':failures,'partial':bool(failures),'writtenSnapshots':[]}
  if failures: raise Partial(d)
  return d
 if c=='source.import':
  require_pair(getattr(a,'output_root',None),getattr(a,'output',None),'import output')
  p=safe_path(a.input_root,a.capture,True); raw=read_bounded(p,a.max_bytes); url=syntax_url(a.source_url,False) if a.source_url else None; r,_=source_record(url,url,a.media_type,raw,{})
  if a.output:
   snap=a.output+'.bytes'; bp=safe_path(a.output_root,snap,output=True); jp=safe_path(a.output_root,a.output,output=True)
   if not overwrite and (bp.exists() or jp.exists()): raise VError('OUTPUT_EXISTS','import output exists; pass --overwrite')
   atomic(bp,raw,overwrite); r['snapshotPath']=snap; write_json(a.output_root,a.output,r,overwrite)
  return {'source':r}
 if c=='bundle.build':
  if not getattr(a,'output_root',None) or not getattr(a,'output',None): raise VError('MALFORMED_INPUT','bundle output requires both root and relative child name')
  src=load(a.input_root,a.sources); cl=load(a.input_root,a.claims); sources=src.get('sources',src if isinstance(src,list) else []); claims=cl.get('claims',cl if isinstance(cl,list) else [])
  core={'schemaVersion':1,'sources':sources,'claims':claims}; probe=dict(core); probe['manifestSha256']=digest(stable(core).encode()); issues,warnings=validate_bundle(probe,a.input_root,None)
  unresolved=[x for x in issues if x.get('code')=='UNRESOLVED_CLAIM']; fatal=[x for x in issues if x.get('code')!='UNRESOLVED_CLAIM']; warnings += unresolved
  if fatal: raise VError('VALIDATION_FAILED',stable(fatal)[:4000])
  jp=safe_path(a.output_root,a.output,output=True); mp=safe_path(a.output_root,a.output+'.md',output=True)
  if not overwrite and (jp.exists() or mp.exists()): raise VError('OUTPUT_EXISTS','bundle output exists; pass --overwrite')
  markdown=render_markdown(probe,warnings)
  write_json(a.output_root,a.output,probe,overwrite); atomic(mp,markdown,overwrite)
  return {'bundle':probe,'warnings':warnings,'jsonPath':a.output,'markdownPath':a.output+'.md'}
 if c in ('bundle.validate','bundle.inspect'):
  b=load(a.input_root,a.bundle)
  if c=='bundle.inspect': return {'sourceCount':len(b.get('sources',[])),'claimCount':len(b.get('claims',[])),'claimStatuses':{x.get('id'):x.get('status') for x in b.get('claims',[]) if isinstance(x,dict)}}
  asof=None
  as_of_arg=getattr(a,'as_of',None)
  if as_of_arg:
   try: asof=dt.datetime.fromisoformat(as_of_arg.replace('Z','+00:00')); asof=asof if asof.tzinfo else asof.replace(tzinfo=dt.timezone.utc)
   except ValueError: raise VError('MALFORMED_INPUT','invalid --as-of date')
  issues,warnings=validate_bundle(b,a.input_root,asof); return {'valid':not issues,'issues':issues,'warnings':warnings,'sourceCount':len(b.get('sources',[])),'claimCount':len(b.get('claims',[]))}
 raise VError('UNKNOWN_COMMAND','unknown command')
def parser():
 p=argparse.ArgumentParser(); p.add_argument('command',choices=['source.fetch','source.batch','source.import','bundle.build','bundle.validate','bundle.inspect']); p.add_argument('--url'); p.add_argument('--input-root'); p.add_argument('--output-root'); p.add_argument('--manifest'); p.add_argument('--snapshot'); p.add_argument('--output'); p.add_argument('--capture'); p.add_argument('--source-url'); p.add_argument('--media-type',default='text/plain'); p.add_argument('--sources'); p.add_argument('--claims'); p.add_argument('--bundle'); p.add_argument('--as-of'); p.add_argument('--timeout',type=int,default=10); p.add_argument('--max-bytes',type=int,default=MAX_BYTES); p.add_argument('--overwrite',action='store_true'); return p
def exit_code(e):
 if isinstance(e,Partial): return 3
 if e.code in ('FETCH_ERROR','DNS_ERROR','TIMEOUT') and e.retryable: return 4
 if e.code in ('INTERNAL_ERROR',): return 5
 return 2
if __name__=='__main__':
 a=parser().parse_args()
 try: print(json.dumps(output(a.command,cmd(a)),ensure_ascii=False,sort_keys=True)); raise SystemExit(0)
 except Partial as e: print(json.dumps(output(a.command,e.data,e),ensure_ascii=False,sort_keys=True)); raise SystemExit(3)
 except VError as e: print(json.dumps(output(a.command,error=e),ensure_ascii=False,sort_keys=True)); raise SystemExit(exit_code(e))
 except Exception:
  e=VError('INTERNAL_ERROR','unexpected internal error; details suppressed')
  print(json.dumps(output(getattr(a,'command','unknown'),error=e),ensure_ascii=False,sort_keys=True)); raise SystemExit(5)
