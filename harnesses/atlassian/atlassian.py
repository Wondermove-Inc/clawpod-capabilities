#!/usr/bin/env python3
"""Dependency-free Atlassian Cloud REST harness with durable mutation guards."""
from __future__ import annotations
import argparse,base64,hashlib,json,os,re,secrets,tempfile,time,uuid
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urljoin,urlparse,parse_qs
from urllib.request import Request,urlopen
ROOT=Path(__file__).parent; CONTRACTS=json.loads((ROOT/'command_contracts.json').read_text())['commands']; SENSITIVE=re.compile(r'(?i)(authorization|api[_-]?token|access[_-]?token|password|secret|cookie)')
class Failure(Exception):
 def __init__(self,code,message,retryable=False,ambiguous=False,systemic=False): super().__init__(message); self.code,self.message,self.retryable,self.ambiguous,self.systemic=code,message,retryable,ambiguous,systemic
def redact(v):
 if isinstance(v,dict): return {k:('[REDACTED]' if SENSITIVE.search(k) else redact(x)) for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 if isinstance(v,str): return re.sub(r'(?i)(basic|bearer)\s+\S+',r'\1 [REDACTED]',v)[:512]
 return v
def secure_file(p,label):
 if p.is_symlink() or (p.exists() and p.stat().st_mode&0o077): raise Failure(label+'_permissions',f'{label} file must be regular mode 0600 or stricter')
def safe_path(path,root,max_bytes=25*1024*1024):
 if not root: raise Failure('transfer_root_required','--transfer-root is required')
 raw=Path(path).expanduser(); rr=Path(root).expanduser()
 for q in [rr,*rr.parents,raw,*raw.parents]:
  if q.exists() and q.is_symlink(): raise Failure('unsafe_path','symlink components are forbidden')
 p=raw.resolve(); r=rr.resolve()
 if p!=r and r not in p.parents: raise Failure('unsafe_path','transfer path escapes transfer root')
 if not p.is_file() or p.stat().st_size>max_bytes: raise Failure('attachment_invalid','attachment missing or exceeds size bound')
 return p
def load_sites(path=None):
 p=Path(path or os.getenv('ATLASSIAN_SITES_FILE','~/.config/atlassian/sites.json')).expanduser(); secure_file(p,'site_config')
 if not p.exists(): raise Failure('site_config_missing','site alias file is missing')
 try: data=json.loads(p.read_text())
 except Exception: raise Failure('site_config_invalid','site alias file is invalid JSON')
 sites=data.get('sites',data)
 if any(isinstance(s,dict) and s.get('auth') for s in sites.values()): secure_file(p,'site_config')
 return sites
def get_site(alias,path=None):
 s=load_sites(path).get(alias)
 if not isinstance(s,dict): raise Failure('site_unknown','unknown site alias')
 url=str(s.get('baseUrl','')).rstrip('/'); u=urlparse(url)
 if u.scheme!='https' or not u.netloc or u.username or u.query or u.fragment: raise Failure('site_invalid','baseUrl must be an HTTPS origin')
 return dict(s,baseUrl=url)
def secret(ref):
 if not isinstance(ref,str) or ':' not in ref: raise Failure('auth_invalid','credential must use env:NAME or file:/path reference')
 kind,val=ref.split(':',1)
 if kind=='env': out=os.getenv(val)
 elif kind=='file':
  p=Path(val).expanduser(); secure_file(p,'auth'); out=p.read_text().strip() if p.exists() else None
 else: raise Failure('auth_invalid','unsupported credential provider')
 if not out: raise Failure('auth_missing','credential reference could not be resolved',systemic=True)
 return out
def authorization(s):
 a=s.get('auth',{}); typ=a.get('type')
 if typ=='oauth': return 'Bearer '+secret(a.get('tokenRef'))
 if typ=='basic' and a.get('email'): return 'Basic '+base64.b64encode((a['email']+':'+secret(a.get('tokenRef'))).encode()).decode()
 raise Failure('auth_invalid','auth.type must be basic or oauth',systemic=True)
def bounds(ns):
 if not 100<=ns.timeout_ms<=120000: raise Failure('timeout_invalid','timeout must be 100..120000 ms')
 if not 0<=ns.retries<=5: raise Failure('retry_invalid','retries must be 0..5')
 if not 1<=ns.max_pages<=100 or not 1<=ns.max_items<=10000: raise Failure('pagination_invalid','pagination bounds exceeded')
def state_dir():
 p=Path(os.getenv('ATLASSIAN_STATE_DIR','~/.local/state/clawpod-atlassian')).expanduser(); p.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(p,0o700); return p
def installation_key():
 p=state_dir()/'key';
 if not p.exists():
  fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,secrets.token_bytes(32)); os.close(fd)
 secure_file(p,'state'); return p.read_bytes()
def fingerprint(command,site,path,params,body): return hashlib.sha256(json.dumps([command,site,path,params,body],sort_keys=True,separators=(',',':')).encode()).hexdigest()
def preview(command,site,path,params,body):
 ident=uuid.uuid4().hex; issued=int(time.time()); fp=fingerprint(command,site,path,params,body); mac=hashlib.sha256(installation_key()+f'{ident}:{issued}:{fp}'.encode()).hexdigest(); token=f'{ident}.{issued}.{mac}'; rec={'fingerprint':fp,'expires':issued+300,'used':False}; (state_dir()/('preview-'+ident+'.json')).write_text(json.dumps(rec)); os.chmod(state_dir()/('preview-'+ident+'.json'),0o600); return token
def consume(token,command,site,path,params,body):
 try: ident,issued,mac=token.split('.'); p=state_dir()/('preview-'+ident+'.json'); rec=json.loads(p.read_text()); expected=hashlib.sha256(installation_key()+f'{ident}:{issued}:{rec["fingerprint"]}'.encode()).hexdigest()
 except Exception: raise Failure('confirm_invalid','invalid confirmation state')
 if not secrets.compare_digest(mac,expected) or rec['used'] or time.time()>rec['expires'] or rec['fingerprint']!=fingerprint(command,site,path,params,body): raise Failure('confirm_stale','confirmation expired, used, or request mismatch')
 rec['used']=True; tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(rec)); os.chmod(tmp,0o600); os.replace(tmp,p)
def idem(ns,fp,result=None):
 if not ns.idempotency_key:return None
 key=hashlib.sha256((ns.site+':'+ns.command+':'+ns.idempotency_key).encode()).hexdigest(); p=state_dir()/('idem-'+key+'.json')
 if result is None and p.exists():
  rec=json.loads(p.read_text());
  if rec['fingerprint']!=fp: raise Failure('idempotency_conflict','idempotency key reused with different input')
  return rec['result']
 if result is not None:
  p.write_text(json.dumps({'fingerprint':fp,'result':result})); os.chmod(p,0o600)
def multipart(path):
 boundary='----clawpod'+secrets.token_hex(12); data=path.read_bytes(); head=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode(); return head+data+f'\r\n--{boundary}--\r\n'.encode(),f'multipart/form-data; boundary={boundary}'
def request(method,url,headers,body,timeout,retries=3,opener=urlopen,sleep=time.sleep,raw=False):
 payload=body if raw else (None if body is None else json.dumps(body).encode())
 for attempt in range(retries+1):
  try:
   with opener(Request(url,data=payload,headers=headers,method=method),timeout=timeout) as r:
    b=r.read(); return json.loads(b) if b else {}
  except HTTPError as e:
   code={400:'invalid_request',401:'auth_rejected',403:'forbidden',404:'not_found',409:'conflict',429:'rate_limited'}.get(e.code,'provider_error'); safe=f'Atlassian HTTP {e.code}'
   if e.code in (429,502,503,504) and attempt<retries: sleep(min(float(e.headers.get('Retry-After','0.25')),2)); continue
   raise Failure(code,safe,e.code in (429,502,503,504),False,e.code in (401,403))
  except TimeoutError: raise Failure('timeout','request timed out',True,method not in ('GET','HEAD'))
  except URLError: raise Failure('network_error','network request failed',True,method not in ('GET','HEAD'))
 raise Failure('retry_exhausted','retry budget exhausted',True)
def paginate(c,url,headers,ns,opener):
 items=[]; pages=0; next_url=url
 while next_url and pages<ns.max_pages and len(items)<ns.max_items:
  data=request('GET',next_url,headers,None,ns.timeout_ms/1000,ns.retries,opener); pages+=1
  vals=data.get('values',data.get('results',data.get('issues',[]))); items.extend(vals[:ns.max_items-len(items)])
  nxt=data.get('_links',{}).get('next') or data.get('next')
  if nxt: next_url=urljoin(next_url,nxt)
  elif 'startAt' in data and data.get('startAt',0)+data.get('maxResults',len(vals))<data.get('total',0):
   q=parse_qs(urlparse(next_url).query); q['startAt']=[str(data['startAt']+data.get('maxResults',len(vals)))]; next_url=next_url.split('?')[0]+'?'+urlencode(q,doseq=True)
  else: next_url=None
 return {'items':items,'pages':pages,'truncated':bool(next_url)}
def execute(ns,opener=urlopen):
 bounds(ns); c=CONTRACTS.get(ns.command)
 if not c: raise Failure('command_unknown','unknown command')
 if ns.command=='auth.sites.list': return {'sites':sorted(load_sites(ns.sites_file))}
 if not ns.site: raise Failure('site_required','--site is required')
 s=get_site(ns.site,ns.sites_file); params=json.loads(ns.params or '{}'); body=json.loads(ns.body) if ns.body else None; path=c['path']
 for k,v in vars(ns).items():
  if v is not None:path=path.replace('{'+k+'}',str(v))
 if '{' in path:raise Failure('input_missing','required path parameter missing')
 upload=None
 if ns.input_path: upload=safe_path(ns.input_path,ns.transfer_root,ns.max_upload_bytes)
 fp=fingerprint(ns.command,ns.site,path,params,body if not upload else {'sha256':hashlib.sha256(upload.read_bytes()).hexdigest()})
 prior=idem(ns,fp)
 if prior is not None:return dict(prior,idempotentReplay=True)
 if c['mutation']:
  if ns.dry_run:return {'dryRun':True,'confirm':preview(ns.command,ns.site,path,params,body if not upload else {'sha256':hashlib.sha256(upload.read_bytes()).hexdigest()}),'expiresInSeconds':300,'request':{'method':c['method'],'path':path,'body':redact(body),'uploadBytes':upload.stat().st_size if upload else None}}
  if not ns.confirm:raise Failure('confirm_required','successful dry-run confirmation required')
  consume(ns.confirm,ns.command,ns.site,path,params,body if not upload else {'sha256':hashlib.sha256(upload.read_bytes()).hexdigest()})
 url=s['baseUrl']+path+('?' + urlencode(params,doseq=True) if params else ''); headers={'Accept':'application/json','Authorization':authorization(s),'User-Agent':'clawpod-atlassian/0.1.0'}
 raw=False
 if upload: body,headers['Content-Type']=multipart(upload); headers['X-Atlassian-Token']='no-check'; raw=True
 elif body is not None:headers['Content-Type']='application/json'
 if c['method']=='GET' and ns.all_pages: result=paginate(c,url,headers,ns,opener)
 else:result=redact(request(c['method'],url,headers,body,ns.timeout_ms/1000,ns.retries,opener,raw=raw))
 if c['mutation']:idem(ns,fp,result)
 return result
def item_error(e): return {'ok':False,'error':{'code':e.code,'message':redact(e.message),'retryable':e.retryable,'ambiguousCommit':e.ambiguous}}
def run_batch(ns):
 items=json.loads(Path(ns.batch).read_text() if Path(ns.batch).exists() else ns.batch); out=[]
 for item in items:
  child=parser().parse_args([item.pop('command'),*sum(([f'--{k.replace("_","-")}',str(v)] if not isinstance(v,bool) else ([f'--{k.replace("_","-")}'] if v else []) for k,v in item.items()),[])])
  try:out.append({'ok':True,'data':execute(child)})
  except Failure as e:
   out.append(item_error(e))
   if e.systemic:break
 return {'items':out,'stopped':len(out)<len(items)}
def parser():
 p=argparse.ArgumentParser(); p.add_argument('command',nargs='?'); p.add_argument('--site'); p.add_argument('--sites-file'); p.add_argument('--params'); p.add_argument('--body'); p.add_argument('--batch'); p.add_argument('--dry-run',action='store_true'); p.add_argument('--confirm'); p.add_argument('--idempotency-key'); p.add_argument('--input-path'); p.add_argument('--transfer-root'); p.add_argument('--max-upload-bytes',type=int,default=25*1024*1024); p.add_argument('--timeout-ms',type=int,default=30000); p.add_argument('--retries',type=int,default=3); p.add_argument('--all-pages',action='store_true'); p.add_argument('--max-pages',type=int,default=10); p.add_argument('--max-items',type=int,default=1000)
 for d in ('issueIdOrKey','commentId','projectIdOrKey','pageId','spaceId'):p.add_argument('--'+re.sub(r'([A-Z])',lambda m:'-'+m.group(1).lower(),d),dest=d)
 return p
def main(argv=None):
 ns=parser().parse_args(argv); out={'ok':True,'schemaVersion':1,'command':ns.command or 'batch','requestId':str(uuid.uuid4()),'effects':[],'provenance':{'provider':'atlassian-cloud','live':False}}
 try:out['data']=run_batch(ns) if ns.batch else execute(ns); out['provenance']['live']=not out['data'].get('dryRun',False)
 except Failure as e:out.update(item_error(e))
 except Exception:out.update(ok=False,error={'code':'internal_error','message':'internal failure','retryable':False,'ambiguousCommit':False})
 print(json.dumps(out,separators=(',',':'))); return 0 if out['ok'] else 2
if __name__=='__main__':raise SystemExit(main())
