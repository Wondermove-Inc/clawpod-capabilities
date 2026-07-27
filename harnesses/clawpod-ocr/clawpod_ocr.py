#!/usr/bin/env python3
"""ClawPod OCR: bounded local OCR and opt-in Ollama correction."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request, uuid
from pathlib import Path

VERSION="0.1.0"; SCHEMA=1; MAX_FILE=64*1024*1024; MAX_PAGES=200; MAX_PIXELS=40_000_000
READ={"system.version","system.preflight","engine.requirements","engine.verify","onboarding.status","ollama.requirements","ollama.verify","document.inspect","job.status","job.logs","result.inspect","result.validate","correction.inspect","cache.inspect"}

def out(cmd,data=None,effects=None,err=None):
 r={"ok":err is None,"schemaVersion":SCHEMA,"command":cmd,"requestId":str(uuid.uuid4()),"data":data or {},"effects":effects or [],"provenance":{"harness":"clawpod-ocr","version":VERSION}}
 if err:r["error"]={"code":err[0],"message":err[1],"retryable":bool(err[2]) if len(err)>2 else False}
 print(json.dumps(r,ensure_ascii=False,sort_keys=True)); return 0 if err is None else 2

def root(args):
 p=Path(args.state_root or os.environ.get("CLAWPOD_OCR_STATE",".clawpod-ocr")).resolve(); p.mkdir(parents=True,exist_ok=True); return p

def safe(base,rel,must=False):
 if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts: raise ValueError("path must be bounded and relative")
 b=base.resolve(); p=base/rel
 if p.is_symlink(): raise ValueError("symlink input is forbidden")
 q=p.resolve(strict=must)
 if q!=b and b not in q.parents: raise ValueError("path escapes root")
 return q

def atomic(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp"); t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8"); os.replace(t,p)
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1024*1024),b""):h.update(x)
 return h.hexdigest()
def deps(): return {x:shutil.which(x) for x in ("pdftotext","pdfinfo","pdftoppm","tesseract","ocrmypdf")}
def cgroup():
 mem=None; cpu=None
 try: mem=int(Path("/sys/fs/cgroup/memory.max").read_text().strip())
 except: pass
 try:
  q,p=Path("/sys/fs/cgroup/cpu.max").read_text().split(); cpu=None if q=="max" else round(int(q)/int(p),2)
 except: pass
 return {"memoryBytes":mem,"cpuQuota":cpu,"workerLimit":1,"ompThreadLimit":1}
def inspect_doc(base,rel):
 p=safe(base,rel,True); st=p.stat()
 if not p.is_file():raise ValueError("input is not a regular file")
 if st.st_size>MAX_FILE:raise ValueError("input exceeds max file bytes")
 head=p.read_bytes()[:16]; ext=p.suffix.lower()
 if ext==".pdf" and not head.startswith(b"%PDF-"):raise ValueError("corrupt PDF header")
 if ext not in {".pdf",".png",".jpg",".jpeg",".tif",".tiff",".webp",".txt"}:raise ValueError("unsupported input type")
 pages=1
 if ext==".pdf" and deps()["pdfinfo"]:
  z=subprocess.run([deps()["pdfinfo"],str(p)],capture_output=True,text=True,timeout=10)
  for line in z.stdout.splitlines():
   if line.startswith("Pages:"): pages=int(line.split(":",1)[1]);break
 if pages>MAX_PAGES:raise ValueError("page limit exceeded")
 return p,{"relativePath":rel,"bytes":st.st_size,"sha256":sha(p),"type":ext[1:],"pages":pages,"limits":{"maxFileBytes":MAX_FILE,"maxPages":MAX_PAGES,"maxPixels":MAX_PIXELS}}
def run(args):
 cmd=args.command; state=root(args); inp=Path(args.input_root or ".").resolve(); work=state/"jobs"; work.mkdir(parents=True,exist_ok=True)
 try:
  if cmd=="system.version": return out(cmd,{"name":"clawpod-ocr","title":"ClawPod OCR","version":VERSION})
  if cmd in {"system.preflight","engine.requirements","engine.verify"}:
   d=deps(); return out(cmd,{"dependencies":d,"resource":cgroup(),"languagesRequired":["kor","eng","osd"],"ready":bool(d["pdftotext"] and d["pdftoppm"] and d["tesseract"])})
  if cmd=="onboarding.status":
   d=deps(); cfg=state/"ollama.json"; return out(cmd,{"installed":True,"localReady":bool(d["pdftotext"] and d["pdftoppm"] and d["tesseract"]),"ollamaState":"configured-unverified" if cfg.exists() else "deferred","nextCommands":["system.preflight","engine.verify","ollama.requirements"],"handoff":"Install Poppler and Tesseract kor/eng/osd, then verify. Ollama is optional and requires separate configure, verify, and review approval."})
  if cmd=="ollama.requirements": return out(cmd,{"optional":True,"adapters":["/api/version","/api/tags"],"transport":"loopback HTTP or private-host HTTPS","secretStorage":"pointer metadata only"})
  if cmd=="ollama.configure":
   u=urllib.parse.urlparse(args.endpoint or ""); host=u.hostname
   if u.scheme not in {"http","https"} or (u.scheme=="http" and host not in {"127.0.0.1","localhost","::1"}):raise ValueError("plaintext transport allowed only for loopback")
   if args.secret and not args.secret.startswith("secret:"):raise ValueError("plaintext secret rejected; provide protected secret pointer")
   cfg={"endpoint":args.endpoint.rstrip("/"),"model":args.model,"secretPointer":args.secret,"state":"configured-unverified"}; atomic(state/"ollama.json",cfg); return out(cmd,cfg,[{"type":"config-write","path":"ollama.json"}])
  if cmd=="ollama.revoke":
   (state/"ollama.json").unlink(missing_ok=True); return out(cmd,{"state":"deferred"},[{"type":"config-delete","path":"ollama.json"}])
  if cmd=="ollama.verify":
   cfg=load(state/"ollama.json"); data={}
   for ep in ("/api/version","/api/tags"):
    with urllib.request.urlopen(cfg["endpoint"]+ep,timeout=min(args.timeout,5)) as r:data[ep]=json.loads(r.read(1024*1024))
   names=[x.get("name") for x in data["/api/tags"].get("models",[])]
   if cfg["model"] not in names:raise ValueError("configured model is unavailable")
   cfg["state"]="verified"; atomic(state/"ollama.json",cfg); return out(cmd,{"state":"verified","version":data["/api/version"],"model":cfg["model"]})
  if cmd=="document.inspect":
   _,d=inspect_doc(inp,args.input); return out(cmd,d)
  if cmd=="ocr.prepare":
   _,d=inspect_doc(inp,args.input); key=hashlib.sha256((d["sha256"]+VERSION+args.language+args.preprocess).encode()).hexdigest(); return out(cmd,{"planId":key,"document":d,"engine":"text-fast-path-then-tesseract","language":args.language,"workers":1,"environment":{"OMP_THREAD_LIMIT":"1"},"cacheKey":key})
  if cmd=="ocr.start":
   p,d=inspect_doc(inp,args.input); jid=args.job_id or uuid.uuid4().hex; jd=work/jid
   if jd.exists():raise ValueError("job already exists")
   jd.mkdir(); shutil.copyfile(p,jd/("input"+p.suffix.lower())); meta={"jobId":jid,"owner":args.owner,"status":"running","source":d,"language":args.language,"completedPages":0,"createdAt":int(time.time()),"cancelRequested":False}; atomic(jd/"job.json",meta)
   if args.detached:return out(cmd,{"jobId":jid,"status":"running","checkpoint":"job.json"},[{"type":"job-create","jobId":jid}])
   return process(jd,args,cmd)
  if cmd in {"job.status","job.logs"}:
   m=owned(work,args); return out(cmd,m if cmd=="job.status" else {"jobId":m["jobId"],"events":load(work/args.job_id/"logs.json") if (work/args.job_id/"logs.json").exists() else []})
  if cmd=="job.resume":
   owned(work,args); return process(work/args.job_id,args,cmd)
  if cmd=="job.cancel":
   m=owned(work,args); m["cancelRequested"]=True;m["status"]="cancelled";atomic(work/args.job_id/"job.json",m);cleanup(work/args.job_id);return out(cmd,m,[{"type":"job-cancel","jobId":args.job_id}])
  if cmd.startswith("result."):
   m=owned(work,args); rp=work/args.job_id/"result.json"
   if not rp.exists():raise ValueError("result unavailable")
   r=load(rp)
   if cmd=="result.validate": return out(cmd,{"valid":r.get("schemaVersion")==1 and sha(work/args.job_id/("input"+Path(m["source"]["relativePath"]).suffix.lower()))==m["source"]["sha256"],"rawPreserved":True})
   if cmd=="result.export":
    dest=safe(Path(args.output_root or ".").resolve(),args.output); dest.parent.mkdir(parents=True,exist_ok=True); fmt=args.format
    if fmt=="searchable-pdf":
     if not shutil.which("ocrmypdf"):raise ValueError("ocrmypdf unavailable")
     src=work/args.job_id/("input"+Path(m["source"]["relativePath"]).suffix.lower())
     if src.suffix.lower()!=".pdf":raise ValueError("searchable PDF export requires PDF input")
     subprocess.run(["ocrmypdf","--skip-text","--jobs","1",str(src),str(dest)],check=True,timeout=args.timeout,env={**os.environ,"OMP_THREAD_LIMIT":"1"})
    else:
     text="\n\n".join(x["text"] for x in r["pages"])
     if fmt=="json":content=json.dumps(r,ensure_ascii=False,indent=2)
     elif fmt=="tsv":content="page\tconfidence\ttext\n"+"\n".join(f'{x["page"]}\t{x["confidence"]}\t{x["text"].replace(chr(9)," ")}' for x in r["pages"])
     elif fmt=="hocr":content='<html><body>'+''.join(f'<div class="ocr_page" id="page_{x["page"]}" title="x_wconf {round(x["confidence"]*100)}">{x["text"]}</div>' for x in r["pages"])+'</body></html>'
     else:content=text
     dest.write_text(content,encoding="utf-8")
    return out(cmd,{"path":args.output,"format":fmt},[{"type":"export","path":args.output}])
   return out(cmd,r)
  if cmd=="review.export-low-confidence":
   m=owned(work,args);r=load(work/args.job_id/"result.json"); items=[{"page":p["page"],"confidence":p["confidence"],"text":p["text"],"crop":None} for p in r["pages"] if p["confidence"]<args.threshold]; dest=safe(Path(args.output_root or ".").resolve(),args.output);atomic(dest,{"schemaVersion":1,"jobId":args.job_id,"threshold":args.threshold,"items":items,"documentTransferred":False});return out(cmd,{"count":len(items),"path":args.output})
  if cmd=="review.prepare":
   owned(work,args);return out(cmd,{"jobId":args.job_id,"intent":"ollama-vision-review","requiresSeparateApproval":True,"automaticTransfer":False,"mode":"diff-only"})
  if cmd=="review.start":
   m=owned(work,args)
   if not args.approved:raise ValueError("separate review approval required")
   cfg=load(state/"ollama.json");
   if cfg.get("state")!="verified":raise ValueError("Ollama not verified")
   raw=load(work/args.job_id/"result.json"); corrections=[]
   for p in raw["pages"]:
    if p["confidence"]>=args.threshold:continue
    body=json.dumps({"model":cfg["model"],"prompt":"Return corrected text only. Original: "+p["text"],"stream":False}).encode()
    try:
     req=urllib.request.Request(cfg["endpoint"]+"/api/generate",body,{"Content-Type":"application/json"}); resp=json.loads(urllib.request.urlopen(req,timeout=args.timeout).read(1024*1024)); corrected=resp.get("response")
     if not isinstance(corrected,str):raise ValueError("malformed Ollama response")
     corrections.append({"page":p["page"],"raw":p["text"],"corrected":corrected,"applied":False,"provenance":{"model":cfg["model"],"endpoint":cfg["endpoint"],"mode":"diff-only"}})
    except Exception as e:return out(cmd,{"jobId":args.job_id,"localResultPreserved":True},err=("REMOTE_FAILURE",str(e),True))
   atomic(work/args.job_id/"corrections.json",{"schemaVersion":1,"items":corrections});return out(cmd,{"count":len(corrections),"localResultPreserved":True})
  if cmd=="correction.inspect": return out(cmd,load(work/args.job_id/"corrections.json"))
  if cmd=="correction.apply":
   owned(work,args);r=load(work/args.job_id/"result.json");c=load(work/args.job_id/"corrections.json")
   for x in c["items"]:
    r["pages"][x["page"]-1]["correctedText"]=x["corrected"];x["applied"]=True
   atomic(work/args.job_id/"result.corrected.json",r);atomic(work/args.job_id/"corrections.json",c);return out(cmd,{"applied":len(c["items"]),"rawResult":"result.json","correctedResult":"result.corrected.json"})
  if cmd=="cache.inspect":
   files=list((state/"cache").glob("*.json")) if (state/"cache").exists() else [];return out(cmd,{"entries":len(files),"bytes":sum(x.stat().st_size for x in files)})
  if cmd=="cache.prune":
   files=list((state/"cache").glob("*.json")) if (state/"cache").exists() else []
   for x in files:x.unlink()
   return out(cmd,{"pruned":len(files)},[{"type":"cache-prune"}])
  return out(cmd,err=("UNKNOWN_COMMAND",cmd,False))
 except (ValueError,FileNotFoundError,json.JSONDecodeError,subprocess.SubprocessError,urllib.error.URLError) as e:return out(cmd,err=("INVALID_OR_UNAVAILABLE",str(e),False))

def owned(work,args):
 p=work/args.job_id/"job.json"
 if not p.exists():raise ValueError("job not found")
 m=load(p)
 if m["owner"]!=args.owner:raise ValueError("job owner mismatch")
 return m
def cleanup(jd):
 shutil.rmtree(jd/"tmp",ignore_errors=True)
def process(jd,args,cmd):
 m=load(jd/"job.json")
 if m.get("cancelRequested"):return out(cmd,m)
 src=next(jd.glob("input.*")); cache=jd.parents[1]/"cache";cache.mkdir(exist_ok=True); key=hashlib.sha256((m["source"]["sha256"]+VERSION+m["language"]+args.preprocess).encode()).hexdigest(); cp=cache/(key+".json")
 if cp.exists():result=load(cp);result["cacheHit"]=True
 else:
  pages=[]; ext=src.suffix.lower(); text=""; engine="tesseract"
  if ext==".txt":text=src.read_text(encoding="utf-8");engine="text-layer"
  elif ext==".pdf" and shutil.which("pdftotext"):
   z=subprocess.run(["pdftotext",str(src),"-"],capture_output=True,text=True,timeout=args.timeout,env={**os.environ,"OMP_THREAD_LIMIT":"1"});text=z.stdout.strip();engine="text-layer" if text else "tesseract"
  if text:pages=[{"page":1,"text":text,"confidence":1.0,"regions":[{"id":"p1","confidence":1.0}],"provenance":{"engine":engine,"sourceHash":m["source"]["sha256"]}}]
  else:
   tmp=jd/"tmp";tmp.mkdir(exist_ok=True); images=[]
   if ext==".pdf":
    if not shutil.which("pdftoppm"):raise ValueError("pdftoppm unavailable")
    subprocess.run(["pdftoppm","-f","1","-singlefile","-png",str(src),str(tmp/"page")],check=True,timeout=args.timeout,env={**os.environ,"OMP_THREAD_LIMIT":"1"});images=[tmp/"page.png"]
   else:images=[src]
   if not shutil.which("tesseract"):raise ValueError("tesseract unavailable")
   for i,img in enumerate(images,1):
    z=subprocess.run(["tesseract",str(img),"stdout","-l",m["language"],"tsv"],capture_output=True,text=True,timeout=args.timeout,env={**os.environ,"OMP_THREAD_LIMIT":"1"}); rows=[x.split("\t") for x in z.stdout.splitlines()[1:] if x.strip()]; words=[x for x in rows if len(x)>11 and x[11].strip()]; conf=[max(0,float(x[10]))/100 for x in words if x[10] not in {"-1",""}];txt=" ".join(x[11] for x in words);c=sum(conf)/len(conf) if conf else 0.0;pages.append({"page":i,"text":txt,"confidence":round(c,4),"regions":[{"id":f"p{i}","confidence":round(c,4)}],"provenance":{"engine":"tesseract-5","language":m["language"],"sourceHash":m["source"]["sha256"]}})
   cleanup(jd)
  result={"schemaVersion":1,"jobId":m["jobId"],"source":m["source"],"rawOcrPreserved":True,"cacheKey":key,"cacheHit":False,"pages":pages};atomic(cp,result)
 atomic(jd/"result.json",result);m["status"]="completed";m["completedPages"]=len(result["pages"]);m["checkpoint"]="result.json";atomic(jd/"job.json",m);atomic(jd/"logs.json",[{"event":"completed","pages":m["completedPages"]}]);return out(cmd,{"jobId":m["jobId"],"status":"completed","result":"result.json","cacheHit":result.get("cacheHit",False)},[{"type":"result-write","jobId":m["jobId"]}])

def parser():
 p=argparse.ArgumentParser();p.add_argument("command");p.add_argument("--state-root");p.add_argument("--input-root");p.add_argument("--input");p.add_argument("--output-root");p.add_argument("--output",default="result.json");p.add_argument("--format",default="json",choices=["json","txt","markdown","tsv","hocr","searchable-pdf"]);p.add_argument("--language",default="kor+eng");p.add_argument("--preprocess",default="default");p.add_argument("--job-id");p.add_argument("--owner",default="default");p.add_argument("--detached",action="store_true");p.add_argument("--endpoint");p.add_argument("--model",default="llava");p.add_argument("--secret");p.add_argument("--timeout",type=float,default=15);p.add_argument("--threshold",type=float,default=.75);p.add_argument("--approved",action="store_true");return p
if __name__=="__main__":sys.exit(run(parser().parse_args()))
