#!/usr/bin/env python3
"""ClawPod OCR: bounded local OCR and opt-in image-bearing Ollama review."""
from __future__ import annotations
import argparse, base64, hashlib, html, json, os, re, secrets, shutil, signal, stat, struct, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path

VERSION="0.2.0"; SCHEMA=1; MAX_FILE=64*1024*1024; MAX_PAGES=200; MAX_PIXELS=40_000_000; MAX_HTTP=2*1024*1024; MAX_IMAGE_TRANSFER=8*1024*1024
CHILDREN={}

def out(cmd,data=None,effects=None,err=None):
 r={"ok":err is None,"schemaVersion":SCHEMA,"command":cmd,"requestId":str(uuid.uuid4()),"data":data or {},"effects":effects or [],"provenance":{"harness":"clawpod-ocr","version":VERSION}}
 if err:r["error"]={"code":err[0],"message":err[1],"retryable":bool(err[2]) if len(err)>2 else False}
 print(json.dumps(r,ensure_ascii=False,sort_keys=True),flush=True);return 0 if err is None else 2

def root(args):
 p=Path(args.state_root or os.environ.get("CLAWPOD_OCR_STATE",".clawpod-ocr")).resolve();p.mkdir(parents=True,exist_ok=True)
 if p.is_symlink():raise ValueError("state root symlink forbidden")
 return p

def safe(base,rel,must=False):
 if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:raise ValueError("path must be bounded and relative")
 b=base.resolve();p=base/rel
 if p.is_symlink():raise ValueError("symlink is forbidden")
 q=p.resolve(strict=must)
 if q!=b and b not in q.parents:raise ValueError("path escapes root")
 for parent in p.parents:
  if parent==b:break
  if parent.is_symlink():raise ValueError("symlink parent is forbidden")
 return q

def atomic(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+".tmp");t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8");os.replace(t,p)
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1024*1024),b""):h.update(x)
 return h.hexdigest()
def deps():return {x:shutil.which(x) for x in ("pdftotext","pdfinfo","pdftoppm","tesseract","ocrmypdf")}
def bounded_timeout(v):
 v=float(v);return max(.1,min(v,60.0))
def cgroup():
 mem=cpu=None
 try:
  x=Path("/sys/fs/cgroup/memory.max").read_text().strip();mem=None if x=="max" else int(x)
 except Exception:pass
 try:
  q,p=Path("/sys/fs/cgroup/cpu.max").read_text().split();cpu=None if q=="max" else round(int(q)/int(p),2)
 except Exception:pass
 return {"memoryBytes":mem,"cpuQuota":cpu,"workerLimit":1,"ompThreadLimit":1}

def image_dimensions(p):
 with p.open("rb") as f:
  h=f.read(32)
  if h.startswith(b"\x89PNG\r\n\x1a\n") and len(h)>=24:return struct.unpack(">II",h[16:24])
  if h[:2]==b"BM" and len(h)>=26:return abs(struct.unpack("<i",h[18:22])[0]),abs(struct.unpack("<i",h[22:26])[0])
  if h[:2] in (b"P6",b"P5",b"P3",b"P2"):
   f.seek(0);tokens=[]
   while len(tokens)<4:
    line=f.readline(4096)
    if not line:break
    line=line.split(b"#",1)[0];tokens.extend(line.split())
   if len(tokens)>=3:return int(tokens[1]),int(tokens[2])
  if h[:2]==b"\xff\xd8":
   f.seek(2)
   while True:
    b=f.read(1)
    if not b:break
    if b!=b"\xff":continue
    marker=f.read(1)
    while marker==b"\xff":marker=f.read(1)
    if marker in (b"\xd8",b"\xd9"):continue
    n=struct.unpack(">H",f.read(2))[0]
    if marker and marker[0] in set(range(0xC0,0xC4))|set(range(0xC5,0xC8))|set(range(0xC9,0xCC))|set(range(0xCD,0xD0)):
     x=f.read(5);return struct.unpack(">H",x[3:5])[0],struct.unpack(">H",x[1:3])[0]
    f.seek(n-2,1)
 raise ValueError("unable to verify decoded image dimensions")
def check_pixels(p):
 w,h=image_dimensions(p)
 if w<=0 or h<=0 or w>MAX_PIXELS or h>MAX_PIXELS or w*h>MAX_PIXELS:raise ValueError("decoded pixel limit exceeded")
 return {"width":w,"height":h,"pixels":w*h}

def inspect_doc(base,rel):
 p=safe(base,rel,True);st=p.stat()
 if not p.is_file():raise ValueError("input is not a regular file")
 if st.st_size>MAX_FILE:raise ValueError("input exceeds max file bytes")
 with p.open("rb") as f:head=f.read(16)
 ext=p.suffix.lower()
 if ext==".pdf" and not head.startswith(b"%PDF-"):raise ValueError("corrupt PDF header")
 if ext not in {".pdf",".png",".jpg",".jpeg",".ppm",".pgm",".txt"}:raise ValueError("unsupported input type")
 pages=1;dimensions=None
 if ext==".pdf":
  pi=deps()["pdfinfo"]
  if not pi:raise ValueError("pdfinfo required to establish PDF page limit")
  z=subprocess.run([pi,str(p)],capture_output=True,text=True,timeout=10)
  if z.returncode:raise ValueError("pdfinfo failed")
  m=re.search(r"^Pages:\s*(\d+)\s*$",z.stdout,re.M)
  if not m:raise ValueError("unable to establish PDF page count")
  pages=int(m.group(1))
 else:
  if ext!=".txt":dimensions=check_pixels(p)
 if pages<1 or pages>MAX_PAGES:raise ValueError("page limit exceeded")
 return p,{"relativePath":rel,"bytes":st.st_size,"sha256":sha(p),"type":ext[1:],"pages":pages,"dimensions":dimensions,"limits":{"maxFileBytes":MAX_FILE,"maxPages":MAX_PAGES,"maxPixels":MAX_PIXELS}}

def tesseract_probe(timeout):
 d=deps();result={"executables":d,"requiredMajor":5,"languagesRequired":["kor","eng","osd"],"verified":False}
 if not d["tesseract"]:return result
 v=subprocess.run([d["tesseract"],"--version"],capture_output=True,text=True,timeout=timeout)
 m=re.search(r"tesseract\s+(\d+)(?:\.\S+)?",v.stdout+v.stderr,re.I);major=int(m.group(1)) if m else None
 l=subprocess.run([d["tesseract"],"--list-langs"],capture_output=True,text=True,timeout=timeout)
 langs={x.strip() for x in l.stdout.splitlines() if x.strip() and not x.lower().startswith("list of")};missing=sorted({"kor","eng","osd"}-langs)
 result.update({"version":m.group(0) if m else None,"major":major,"languages":sorted(langs),"missingLanguages":missing,"verified":v.returncode==0 and l.returncode==0 and major==5 and not missing and bool(d["pdfinfo"] and d["pdftoppm"] and d["pdftotext"])})
 return result

def require_local_engine(state,timeout):
 p=state/"local-onboarding.json"
 if not p.exists() or load(p).get("state")!="verified":raise ValueError("local OCR engine is not persistently verified; run engine.verify")
 current=tesseract_probe(timeout)
 if not current["verified"]:raise ValueError("current local OCR engine no longer matches verified Tesseract 5 kor/eng/osd requirements")
 return current

def proc_start(pid):
 try:
  fields=Path(f"/proc/{pid}/stat").read_text().split()
  return None if fields[2]=="Z" else fields[21]
 except Exception:return None
def alive(m):return bool(m.get("workerPid") and proc_start(m["workerPid"])==m.get("workerStartIdentity"))
def reconcile(jd,m):
 for pid,child in list(CHILDREN.items()):
  if child.poll() is not None:child.wait();CHILDREN.pop(pid,None)
 if m.get("status")=="running" and not alive(m):
  # A worker atomically records completion before exit. Only a stale running state is interrupted.
  m=load(jd/"job.json")
  if m.get("status")=="running":
   m["status"]="interrupted";m["workerPid"]=None;m["workerStartIdentity"]=None;atomic(jd/"job.json",m)
 return m

def auth_headers(cfg):
 if not cfg.get("secretPointer"):return {}
 target=cfg.get("injection",{})
 auth_value=None
 if target.get("type")=="env":auth_value=os.environ.get(target.get("name", ""))
 elif target.get("type")=="file-env":
  fp=os.environ.get(target.get("name", ""))
  if fp:
   st=os.stat(fp)
   if stat.S_IMODE(st.st_mode)&0o077:raise ValueError("secret file must be mode 0600")
   auth_value=Path(fp).read_text(encoding="utf-8").strip()
 if not auth_value:raise ValueError("configured secret requires separate protected injection")
 if len(auth_value)>8192 or "\n" in auth_value or "\r" in auth_value:raise ValueError("invalid injected token")
 return {"Authorization":"Bearer "+auth_value}
def http_json(cfg,path,timeout,body=None):
 data=None if body is None else json.dumps(body,separators=(",",":")).encode()
 headers={"Accept":"application/json",**auth_headers(cfg)}
 if data is not None:headers["Content-Type"]="application/json"
 req=urllib.request.Request(cfg["endpoint"]+path,data,headers)
 with urllib.request.urlopen(req,timeout=bounded_timeout(timeout)) as r:
  raw=r.read(MAX_HTTP+1)
  if len(raw)>MAX_HTTP:raise ValueError("remote response exceeds limit")
 try:return json.loads(raw)
 except Exception:raise ValueError("malformed remote JSON")

def worker_launch(jd,args):
 nonce=secrets.token_hex(16);m=load(jd/"job.json");m.update({"status":"launching","workerNonce":nonce});atomic(jd/"job.json",m)
 argv=[sys.executable,str(Path(__file__).resolve()),"_worker","--state-root",str(jd.parents[1]),"--job-id",m["jobId"],"--owner",m["owner"],"--worker-nonce",nonce,"--timeout",str(bounded_timeout(args.timeout)),"--preprocess",args.preprocess]
 p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True);CHILDREN[p.pid]=p
 ident=None
 for _ in range(50):
  ident=proc_start(p.pid)
  if ident:break
  time.sleep(.002)
 if not ident:raise ValueError("worker failed to launch")
 m=load(jd/"job.json");m.update({"status":"running","workerPid":p.pid,"workerStartIdentity":ident,"workerNonce":nonce});atomic(jd/"job.json",m)
 return m

def run(args):
 cmd=args.command
 try:
  state=root(args);inp=Path(args.input_root or ".").resolve();work=state/"jobs";work.mkdir(parents=True,exist_ok=True);timeout=bounded_timeout(args.timeout)
  if cmd=="system.version":return out(cmd,{"name":"clawpod-ocr","title":"ClawPod OCR","version":VERSION})
  if cmd=="engine.requirements":return out(cmd,{"required":{"tesseractMajor":5,"languages":["kor","eng","osd"],"tools":["tesseract","pdfinfo","pdftotext","pdftoppm"]},"limits":{"maxPixels":MAX_PIXELS,"maxPages":MAX_PAGES}})
  if cmd=="engine.verify":
   p=tesseract_probe(timeout);atomic(state/"local-onboarding.json",{"state":"verified" if p["verified"] else "verification-failed","checkedAt":int(time.time()),"probe":p});return out(cmd,{"state":"verified" if p["verified"] else "verification-failed",**p},[{"type":"onboarding-state-write"}])
  if cmd=="system.preflight":
   p=tesseract_probe(timeout);saved=load(state/"local-onboarding.json") if (state/"local-onboarding.json").exists() else {"state":"not-verified"};return out(cmd,{"currentProbe":p,"persistedState":saved["state"],"ready":p["verified"] and saved["state"]=="verified","resource":cgroup()})
  if cmd=="onboarding.status":
   local=load(state/"local-onboarding.json") if (state/"local-onboarding.json").exists() else {"state":"not-verified"};cfg=load(state/"ollama.json") if (state/"ollama.json").exists() else {"state":"deferred"};return out(cmd,{"local":local,"ollama":{"state":cfg["state"],"model":cfg.get("model")},"nextCommands":["engine.requirements","engine.verify","system.preflight","ollama.requirements"]})
  if cmd=="ollama.requirements":return out(cmd,{"optional":True,"transport":"HTTP loopback only; HTTPS otherwise","auth":"secret pointer metadata plus injected CLAWPOD_OLLAMA_TOKEN or CLAWPOD_OLLAMA_TOKEN_FILE (0600)","review":"bounded low-confidence page image via Ollama images field"})
  if cmd=="ollama.configure":
   u=urllib.parse.urlparse(args.endpoint or "");host=(u.hostname or "").lower();loop=host in {"127.0.0.1","localhost","::1"}
   if not u.hostname or u.username or u.password or u.query or u.fragment or u.scheme not in ({"http","https"}):raise ValueError("invalid endpoint")
   if u.scheme=="http" and not loop:raise ValueError("HTTP allowed only for loopback")
   if args.secret and not args.secret.startswith("secret:"):raise ValueError("plaintext secret rejected")
   injection={"type":args.auth_mode,"name":args.auth_env} if args.secret else None
   if args.secret and (args.auth_mode not in {"env","file-env"} or not re.fullmatch(r"[A-Z_][A-Z0-9_]*",args.auth_env or "")):raise ValueError("declare protected injection target")
   cfg={"endpoint":args.endpoint.rstrip("/"),"model":args.model,"secretPointer":args.secret,"injection":injection,"state":"configured_unverified"};atomic(state/"ollama.json",cfg);return out(cmd,{**cfg,"secretPointer":"configured" if args.secret else None},[{"type":"config-write","path":"ollama.json"}])
  if cmd=="ollama.revoke":(state/"ollama.json").unlink(missing_ok=True);return out(cmd,{"state":"deferred"},[{"type":"config-delete"}])
  if cmd=="ollama.verify":
   cfg=load(state/"ollama.json");cfg["state"]="verification_in_progress";atomic(state/"ollama.json",cfg)
   try:version=http_json(cfg,"/api/version",timeout);tags=http_json(cfg,"/api/tags",timeout)
   except Exception:
    cfg["state"]="configured_unverified";atomic(state/"ollama.json",cfg);raise
   names=[x.get("name") for x in tags.get("models",[]) if isinstance(x,dict)]
   if cfg["model"] not in names:cfg["state"]="model_unavailable";atomic(state/"ollama.json",cfg);raise ValueError("configured model unavailable")
   show=http_json(cfg,"/api/show",timeout,{"model":cfg["model"]});caps=show.get("capabilities")
   if isinstance(caps,list):vision="vision" in caps;cfg["state"]="verified" if vision else "model_vision_incompatible"
   else:
    smoke=http_json(cfg,"/api/generate",timeout,{"model":cfg["model"],"prompt":"Reply OK if you can see this image.","images":[base64.b64encode(tiny_png()).decode()],"stream":False});vision=isinstance(smoke.get("response"),str) and bool(smoke["response"].strip());cfg["state"]="verified" if vision else "model_capability_unverified"
   atomic(state/"ollama.json",cfg)
   if cfg["state"]!="verified":raise ValueError(cfg["state"])
   return out(cmd,{"state":"verified","version":version,"model":cfg["model"],"vision":True})
  if cmd=="document.inspect":_,d=inspect_doc(inp,args.input);return out(cmd,d)
  if cmd=="ocr.prepare":
   _,d=inspect_doc(inp,args.input);key=hashlib.sha256((d["sha256"]+VERSION+args.language+args.preprocess).encode()).hexdigest();return out(cmd,{"planId":key,"document":d,"workers":1,"cacheKey":key})
  if cmd=="ocr.quick":
   require_local_engine(state,timeout);p,d=inspect_doc(inp,args.input)
   if d["type"] not in {"png","jpeg","ppm","pgm"} or d["pages"]!=1:raise ValueError("ocr.quick accepts one local image only; use the standard workflow for PDFs or multi-page inputs")
   jid=args.job_id or uuid.uuid4().hex;jd=work/jid
   if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}",jid):raise ValueError("invalid job id")
   if jd.exists():raise ValueError("job already exists")
   jd.mkdir();src=jd/("input"+p.suffix.lower());shutil.copyfile(p,src);key=hashlib.sha256((d["sha256"]+VERSION+args.language+args.preprocess).encode()).hexdigest();cache=state/"cache";cache.mkdir(exist_ok=True);cp=cache/(key+".json")
   meta={"jobId":jid,"owner":args.owner,"status":"running","source":d,"language":args.language,"preprocess":args.preprocess,"completedPages":0,"createdAt":int(time.time()),"cancelRequested":False,"pages":[]};atomic(jd/"job.json",meta)
   if cp.exists():result=load(cp);result.update({"jobId":jid,"source":d,"cacheHit":True})
   else:
    page=ocr_image(src,1,meta,args);result={"schemaVersion":1,"jobId":jid,"source":d,"rawOcrPreserved":True,"cacheKey":key,"cacheHit":False,"pages":[page]};atomic(cp,result)
   atomic(jd/"result.json",result);meta.update({"status":"completed","completedPages":1,"pages":result["pages"],"checkpoint":"result.json"});atomic(jd/"job.json",meta);page=result["pages"][0];valid=sha(src)==d["sha256"]
   return out(cmd,{"jobId":jid,"text":page["text"],"confidence":page["confidence"],"cacheHit":result["cacheHit"],"valid":valid,"rawPreserved":True,"sourceDigest":d["sha256"],"dimensions":d["dimensions"],"engine":page["provenance"]["engine"],"language":args.language},[{"type":"quick-result-write","jobId":jid}])
  if cmd=="ocr.start":
   require_local_engine(state,timeout);p,d=inspect_doc(inp,args.input);jid=args.job_id or uuid.uuid4().hex;jd=work/jid
   if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}",jid):raise ValueError("invalid job id")
   if jd.exists():raise ValueError("job already exists")
   jd.mkdir();shutil.copyfile(p,jd/("input"+p.suffix.lower()));meta={"jobId":jid,"owner":args.owner,"status":"created","source":d,"language":args.language,"preprocess":args.preprocess,"completedPages":0,"createdAt":int(time.time()),"cancelRequested":False,"pages":[]};atomic(jd/"job.json",meta)
   if args.detached:
    m=worker_launch(jd,args);return out(cmd,{"jobId":jid,"status":m["status"],"workerPid":m["workerPid"],"checkpoint":"job.json"},[{"type":"worker-launch","jobId":jid}])
   return process(jd,args,cmd)
  if cmd=="_worker":
   jd=work/args.job_id;m=load(jd/"job.json")
   if m.get("owner")!=args.owner or m.get("workerNonce")!=args.worker_nonce:return 3
   require_local_engine(state,timeout)
   # Parent publishes PID/start identity before work, preventing completion from being overwritten by launch state.
   for _ in range(100):
    m=load(jd/"job.json")
    if m.get("status")=="running" and m.get("workerPid")==os.getpid() and m.get("workerStartIdentity")==proc_start(os.getpid()):break
    time.sleep(.005)
   else:return 4
   return process(jd,args,cmd,worker=True)
  if cmd in {"job.status","job.logs"}:
   m=owned(work,args);m=reconcile(work/args.job_id,m);return out(cmd,m if cmd=="job.status" else {"jobId":m["jobId"],"events":load(work/args.job_id/"logs.json") if (work/args.job_id/"logs.json").exists() else []})
  if cmd=="job.resume":
   require_local_engine(state,timeout);m=owned(work,args);m=reconcile(work/args.job_id,m)
   if m["status"]=="running":raise ValueError("job already running")
   m["cancelRequested"]=False;atomic(work/args.job_id/"job.json",m)
   if args.detached:
    m=worker_launch(work/args.job_id,args);return out(cmd,{"jobId":m["jobId"],"status":"running","completedPages":m["completedPages"]})
   return process(work/args.job_id,args,cmd)
  if cmd=="job.cancel":
   jd=work/args.job_id;m=owned(work,args);m=reconcile(jd,m);m["cancelRequested"]=True
   if m.get("status")=="running":
    if not alive(m):raise ValueError("worker identity changed; refusing signal")
    os.killpg(m["workerPid"],signal.SIGTERM)
    for _ in range(50):
     if not alive(m):break
     time.sleep(.02)
    if alive(m):raise ValueError("worker did not stop within bound")
    child=CHILDREN.pop(m["workerPid"],None)
    if child is not None:child.wait(timeout=1)
   m["status"]="cancelled";m["workerPid"]=None;m["workerStartIdentity"]=None;atomic(jd/"job.json",m);cleanup(jd);return out(cmd,m,[{"type":"job-cancel","jobId":args.job_id}])
  if cmd.startswith("result."):
   m=owned(work,args);rp=work/args.job_id/"result.json"
   if not rp.exists():raise ValueError("result unavailable")
   r=load(rp)
   if cmd=="result.validate":return out(cmd,{"valid":r.get("schemaVersion")==1 and sha(next((work/args.job_id).glob("input.*")))==m["source"]["sha256"],"rawPreserved":True})
   if cmd=="result.export":
    base=Path(args.output_root or ".").resolve();dest=safe(base,args.output);dest.parent.mkdir(parents=True,exist_ok=True);safe(base,args.output)
    if dest.exists() and dest.is_symlink():raise ValueError("output symlink forbidden")
    fmt=args.format
    if fmt=="searchable-pdf":
     if not shutil.which("ocrmypdf"):raise ValueError("ocrmypdf unavailable")
     src=next((work/args.job_id).glob("input.*"))
     if src.suffix.lower()!=".pdf":raise ValueError("searchable PDF requires PDF input")
     subprocess.run(["ocrmypdf","--skip-text","--jobs","1",str(src),str(dest)],check=True,timeout=timeout,env={**os.environ,"OMP_THREAD_LIMIT":"1"})
    else:
     text="\n\n".join(x["text"] for x in r["pages"])
     if fmt=="json":content=json.dumps(r,ensure_ascii=False,indent=2)
     elif fmt=="tsv":content="page\tconfidence\ttext\n"+"\n".join(f'{x["page"]}\t{x["confidence"]}\t{x["text"].replace(chr(9)," ").replace(chr(10)," ")}' for x in r["pages"])
     elif fmt=="hocr":content='<html><body>'+''.join(f'<div class="ocr_page" id="page_{x["page"]}" title="x_wconf {round(x["confidence"]*100)}">{html.escape(x["text"])}</div>' for x in r["pages"])+'</body></html>'
     elif fmt=="markdown":content="\n\n".join(f'## Page {x["page"]}\n\n{x["text"]}' for x in r["pages"])
     else:content=text
     dest.write_text(content,encoding="utf-8")
    return out(cmd,{"path":args.output,"format":fmt},[{"type":"export","path":args.output}])
   return out(cmd,r)
  if cmd=="review.export-low-confidence":
   owned(work,args);r=load(work/args.job_id/"result.json");items=[{"page":p["page"],"confidence":p["confidence"],"text":p["text"],"image":"page image retained locally"} for p in r["pages"] if p["confidence"]<args.threshold];dest=safe(Path(args.output_root or ".").resolve(),args.output);atomic(dest,{"schemaVersion":1,"jobId":args.job_id,"threshold":args.threshold,"items":items,"documentTransferred":False,"reviewUnit":"page"});return out(cmd,{"count":len(items),"path":args.output})
  if cmd=="review.prepare":
   owned(work,args);cfg=load(state/"ollama.json")
   if cfg.get("state")!="verified":raise ValueError("Ollama vision model not verified")
   intent=review_intent(work/args.job_id,cfg,args);atomic(work/args.job_id/"review-intent.json",intent);return out(cmd,intent,[{"type":"review-intent-write","jobId":args.job_id}])
  if cmd=="review.start":
   owned(work,args)
   if not args.approved or not args.approval_digest:raise ValueError("exact review approval digest required")
   cfg=load(state/"ollama.json")
   if cfg.get("state")!="verified":raise ValueError("Ollama vision model not verified")
   current=review_intent(work/args.job_id,cfg,args)
   if not secrets.compare_digest(args.approval_digest,current["intentDigest"]):raise ValueError("review approval digest mismatch; prepare and approve the unchanged intent")
   raw=load(work/args.job_id/"result.json");corrections=[]
   for p in raw["pages"]:
    if p["confidence"]>=args.threshold:continue
    img=ensure_page_image(work/args.job_id,p["page"],args);b=img.read_bytes()
    if len(b)>MAX_IMAGE_TRANSFER:raise ValueError("page image transfer exceeds limit")
    resp=http_json(cfg,"/api/generate",timeout,{"model":cfg["model"],"prompt":"Review this page image. Return corrected OCR text only. Raw OCR: "+p["text"][:20000],"images":[base64.b64encode(b).decode()],"stream":False});corrected=resp.get("response")
    if not isinstance(corrected,str):raise ValueError("malformed Ollama response")
    cid=f'p{p["page"]}-{hashlib.sha256((p["text"]+corrected).encode()).hexdigest()[:12]}';corrections.append({"id":cid,"page":p["page"],"rawHash":hashlib.sha256(p["text"].encode()).hexdigest(),"corrected":corrected,"applied":False,"provenance":{"model":cfg["model"],"endpoint":cfg["endpoint"],"mode":"diff-only-page-image","createdAt":int(time.time())}})
   atomic(work/args.job_id/"corrections.json",{"schemaVersion":1,"items":corrections});return out(cmd,{"count":len(corrections),"localResultPreserved":True,"reviewUnit":"page"})
  if cmd=="correction.inspect":owned(work,args);return out(cmd,load(work/args.job_id/"corrections.json"))
  if cmd=="correction.apply":
   owned(work,args)
   ids=set(args.correction_id or []);pages=set(args.page or [])
   if not ids and not pages:raise ValueError("explicit correction IDs or pages required")
   r=load(work/args.job_id/"result.json");c=load(work/args.job_id/"corrections.json");applied=[]
   for x in c["items"]:
    if x["id"] not in ids and x["page"] not in pages:continue
    target=next((p for p in r["pages"] if p["page"]==x["page"]),None)
    if not target or hashlib.sha256(target["text"].encode()).hexdigest()!=x["rawHash"]:raise ValueError("raw OCR provenance mismatch")
    target["correctedText"]=x["corrected"];target["correctionProvenance"]={"correctionId":x["id"],**x["provenance"]};x["applied"]=True;applied.append(x["id"])
   if not applied:raise ValueError("no requested corrections matched")
   atomic(work/args.job_id/"result.corrected.json",r);atomic(work/args.job_id/"corrections.json",c);return out(cmd,{"applied":applied,"rawResult":"result.json","correctedResult":"result.corrected.json"})
  if cmd=="cache.inspect":
   files=list((state/"cache").glob("*.json")) if (state/"cache").exists() else [];return out(cmd,{"entries":len(files),"bytes":sum(x.stat().st_size for x in files)})
  if cmd=="cache.prune":
   files=list((state/"cache").glob("*.json")) if (state/"cache").exists() else []
   for x in files:x.unlink()
   return out(cmd,{"pruned":len(files)},[{"type":"cache-prune"}])
  return out(cmd,err=("UNKNOWN_COMMAND",cmd,False))
 except (ValueError,FileNotFoundError,PermissionError,json.JSONDecodeError,subprocess.SubprocessError,urllib.error.URLError,TimeoutError,OSError) as e:return out(cmd,{"localResultPreserved":cmd=="review.start"},err=("INVALID_OR_UNAVAILABLE",str(e),isinstance(e,(urllib.error.URLError,TimeoutError))))

def owned(work,args):
 if not args.job_id or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}",args.job_id):raise ValueError("invalid job id")
 p=work/args.job_id/"job.json"
 if not p.exists():raise ValueError("job not found")
 m=load(p)
 if m["owner"]!=args.owner:raise ValueError("job owner mismatch")
 return m
def cleanup(jd):shutil.rmtree(jd/"tmp",ignore_errors=True)
def cancelled(jd):return load(jd/"job.json").get("cancelRequested",False)
def page_image(jd,page):
 for ext in ("png","ppm","pgm","jpg","jpeg"):
  p=jd/"page-images"/f"page-{page}.{ext}"
  if p.exists():return p
 raise ValueError("bounded page image unavailable for vision review")

def ensure_page_image(jd,page,args):
 try:
  p=page_image(jd,page);check_pixels(p);return p
 except ValueError:pass
 src=next(jd.glob("input.*"));ext=src.suffix.lower();destdir=jd/"page-images";destdir.mkdir(exist_ok=True)
 if ext in {".png",".jpg",".jpeg",".ppm",".pgm"} and page==1:
  check_pixels(src);dest=destdir/("page-1"+ext);shutil.copyfile(src,dest);return dest
 if ext==".pdf":
  tmp=jd/"tmp";tmp.mkdir(exist_ok=True);prefix=tmp/f"review-{page}"
  subprocess.run(["pdftoppm","-r","200","-f",str(page),"-l",str(page),"-singlefile",str(src),str(prefix)],check=True,timeout=bounded_timeout(args.timeout),env={**os.environ,"OMP_THREAD_LIMIT":"1"})
  raster=prefix.with_suffix(".ppm");check_pixels(raster);dest=destdir/f"page-{page}.ppm";shutil.copyfile(raster,dest);raster.unlink(missing_ok=True);cleanup(jd);return dest
 raise ValueError("bounded page image unavailable for vision review")

def review_intent(jd,cfg,args):
 raw=load(jd/"result.json");items=[]
 for p in raw["pages"]:
  if p["confidence"]>=args.threshold:continue
  image=ensure_page_image(jd,p["page"],args);size=image.stat().st_size
  if size>MAX_IMAGE_TRANSFER:raise ValueError("page image transfer exceeds limit")
  items.append({"page":p["page"],"imageSha256":sha(image),"imageBytes":size})
 payload={"schemaVersion":1,"jobId":raw["jobId"],"sourceDigest":raw["source"]["sha256"],"threshold":args.threshold,"pages":items,"model":cfg["model"],"endpointIdentity":cfg["endpoint"],"reviewUnit":"page","mode":"diff-only","automaticTransfer":False}
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return {**payload,"intentDigest":digest,"requiresSeparateApproval":True}
def tiny_png():return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")

def process(jd,args,cmd,worker=False):
 old=None
 if worker:
  def stop(_s,_f):
   m=load(jd/"job.json");m["cancelRequested"]=True;atomic(jd/"job.json",m)
  old=signal.signal(signal.SIGTERM,stop)
 try:
  m=load(jd/"job.json")
  if m.get("cancelRequested"):return out(cmd,m) if not worker else 0
  m["status"]="running";atomic(jd/"job.json",m);src=next(jd.glob("input.*"));cache=jd.parents[1]/"cache";cache.mkdir(exist_ok=True);key=hashlib.sha256((m["source"]["sha256"]+VERSION+m["language"]+m["preprocess"]).encode()).hexdigest();cp=cache/(key+".json")
  if cp.exists() and m["completedPages"]==0:
   result=load(cp);result["jobId"]=m["jobId"];result["source"]=m["source"];result["cacheHit"]=True;atomic(jd/"result.json",result);m["status"]="completed";m["completedPages"]=len(result["pages"]);m["pages"]=result["pages"];m["checkpoint"]="result.json";atomic(jd/"job.json",m);return out(cmd,{"jobId":m["jobId"],"status":"completed","cacheHit":True}) if not worker else 0
  pages=list(m.get("pages",[]));ext=src.suffix.lower();start=len(pages)+1
  if ext==".txt" and start==1:
   text=src.read_text(encoding="utf-8");pages.append(page_result(1,text,1.0,"text-layer",m));checkpoint(jd,m,pages)
  elif ext==".pdf":
   for page in range(start,m["source"]["pages"]+1):
    if cancelled(jd):break
    text=""
    if shutil.which("pdftotext"):
     z=subprocess.run(["pdftotext","-f",str(page),"-l",str(page),str(src),"-"],capture_output=True,text=True,timeout=bounded_timeout(args.timeout),env={**os.environ,"OMP_THREAD_LIMIT":"1"})
     if z.returncode==0:text=z.stdout.strip()
    if text:pages.append(page_result(page,text,1.0,"text-layer",m));checkpoint(jd,m,pages);continue
    tmp=jd/"tmp";tmp.mkdir(exist_ok=True);prefix=tmp/f"page-{page}";subprocess.run(["pdftoppm","-r","200","-f",str(page),"-l",str(page),"-singlefile",str(src),str(prefix)],check=True,timeout=bounded_timeout(args.timeout),env={**os.environ,"OMP_THREAD_LIMIT":"1"});img=prefix.with_suffix(".ppm");check_pixels(img);keep=jd/"page-images"/f"page-{page}.ppm";keep.parent.mkdir(exist_ok=True);shutil.copyfile(img,keep);pages.append(ocr_image(img,page,m,args));checkpoint(jd,m,pages);img.unlink(missing_ok=True);cleanup(jd)
  else:
   if start==1:
    check_pixels(src);keep=jd/"page-images"/("page-1"+src.suffix.lower());keep.parent.mkdir(exist_ok=True);shutil.copyfile(src,keep);pages.append(ocr_image(src,1,m,args));checkpoint(jd,m,pages)
  m=load(jd/"job.json")
  if m.get("cancelRequested"):
   m["status"]="cancelled";m["workerPid"]=None;m["workerStartIdentity"]=None;atomic(jd/"job.json",m);cleanup(jd);return out(cmd,m) if not worker else 0
  result={"schemaVersion":1,"jobId":m["jobId"],"source":m["source"],"rawOcrPreserved":True,"cacheKey":key,"cacheHit":False,"pages":pages};atomic(cp,result);atomic(jd/"result.json",result);m["status"]="completed";m["completedPages"]=len(pages);m["checkpoint"]="result.json";m["workerPid"]=None;m["workerStartIdentity"]=None;atomic(jd/"job.json",m);atomic(jd/"logs.json",[{"event":"completed","pages":len(pages)}]);return out(cmd,{"jobId":m["jobId"],"status":"completed","result":"result.json","cacheHit":False},[{"type":"result-write","jobId":m["jobId"]}]) if not worker else 0
 finally:
  if worker and old is not None:signal.signal(signal.SIGTERM,old)
def checkpoint(jd,m,pages):
 m=load(jd/"job.json");m["pages"]=pages;m["completedPages"]=len(pages);m["checkpoint"]=f'page-{len(pages)}';atomic(jd/"job.json",m);atomic(jd/"checkpoint.json",{"pages":pages})
def page_result(page,text,confidence,engine,m):return {"page":page,"text":text,"confidence":confidence,"regions":[{"id":f"p{page}","confidence":confidence}],"provenance":{"engine":engine,"language":m["language"],"sourceHash":m["source"]["sha256"]}}
def ocr_image(img,page,m,args):
 if not shutil.which("tesseract"):raise ValueError("tesseract unavailable")
 z=subprocess.run(["tesseract",str(img),"stdout","-l",m["language"],"tsv"],capture_output=True,text=True,timeout=bounded_timeout(args.timeout),env={**os.environ,"OMP_THREAD_LIMIT":"1"})
 if z.returncode:raise ValueError("tesseract failed")
 rows=[x.split("\t") for x in z.stdout.splitlines()[1:] if x.strip()];words=[x for x in rows if len(x)>11 and x[11].strip()];conf=[max(0,float(x[10]))/100 for x in words if x[10] not in {"-1",""}];txt=" ".join(x[11] for x in words);c=round(sum(conf)/len(conf),4) if conf else 0.0;return page_result(page,txt,c,"tesseract-5",m)

def parse_bool(value):
 if isinstance(value,bool):return value
 text=str(value).strip().lower()
 if text in {"1","true","yes","on"}:return True
 if text in {"0","false","no","off"}:return False
 raise argparse.ArgumentTypeError("expected a boolean value")
def parser():
 p=argparse.ArgumentParser();p.add_argument("command");p.add_argument("--state-root");p.add_argument("--input-root");p.add_argument("--input");p.add_argument("--output-root");p.add_argument("--output",default="result.json");p.add_argument("--format",default="json",choices=["json","txt","markdown","tsv","hocr","searchable-pdf"]);p.add_argument("--language",default="kor+eng");p.add_argument("--preprocess",default="default");p.add_argument("--job-id");p.add_argument("--owner",default="default");p.add_argument("--detached",nargs="?",const=True,default=False,type=parse_bool);p.add_argument("--endpoint");p.add_argument("--model",default="llava");p.add_argument("--secret");p.add_argument("--auth-mode",default="env",choices=["env","file-env"]);p.add_argument("--auth-env",default="CLAWPOD_OLLAMA_TOKEN");p.add_argument("--timeout",type=float,default=15);p.add_argument("--threshold",type=float,default=.75);p.add_argument("--approved",nargs="?",const=True,default=False,type=parse_bool);p.add_argument("--approval-digest");p.add_argument("--correction-id",action="append");p.add_argument("--page",action="append",type=int);p.add_argument("--worker-nonce",help=argparse.SUPPRESS);return p
if __name__=="__main__":sys.exit(run(parser().parse_args()))
