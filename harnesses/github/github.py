#!/usr/bin/env python3
"""Guarded JSON wrapper around the real GitHub CLI (`gh`)."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path

READ = {
 "auth.status": ["auth","status","--hostname","{host}","--active","--json","hosts"],
 "repo.view": ["repo","view","{repo}","--json","nameWithOwner,description,url,visibility,defaultBranchRef"],
 "issue.list": ["issue","list","--repo","{repo}","--state","{state}","--limit","{limit}","--json","number,title,state,url,author,labels,updatedAt"],
 "issue.get": ["issue","view","{number}","--repo","{repo}","--json","number,title,body,state,url,author,labels,comments,updatedAt"],
 "pr.list": ["pr","list","--repo","{repo}","--state","{state}","--limit","{limit}","--json","number,title,state,url,author,isDraft,updatedAt"],
 "pr.view": ["pr","view","{number}","--repo","{repo}","--json","number,title,body,state,url,author,isDraft,mergeable,reviewDecision,statusCheckRollup"],
 "pr.checks": ["pr","checks","{number}","--repo","{repo}","--json","name,state,link,bucket,event,workflow"],
 "run.list": ["run","list","--repo","{repo}","--limit","{limit}","--json","databaseId,name,status,conclusion,url,workflowName,createdAt,updatedAt"],
 "run.view": ["run","view","{run_id}","--repo","{repo}","--json","databaseId,name,status,conclusion,url,jobs,workflowName"],
 "run.logs": ["run","view","{run_id}","--repo","{repo}","--log-failed"],
 "release.list": ["release","list","--repo","{repo}","--limit","{limit}","--json","tagName,name,isDraft,isPrerelease,publishedAt,url"],
 "release.view": ["release","view","{tag}","--repo","{repo}","--json","tagName,name,body,isDraft,isPrerelease,publishedAt,url,assets"],
 "api.get": ["api","--method","GET","{endpoint}"],
}
MUTATE = {
 "issue.create": ["issue","create","--repo","{repo}","--title","{title}","--body","{body}"],
 "issue.comment": ["issue","comment","{number}","--repo","{repo}","--body","{body}"],
 "issue.close": ["issue","close","{number}","--repo","{repo}"],
 "issue.reopen": ["issue","reopen","{number}","--repo","{repo}"],
 "pr.create": ["pr","create","--repo","{repo}","--title","{title}","--body","{body}","--head","{head}","--base","{base}"],
 "pr.comment": ["pr","comment","{number}","--repo","{repo}","--body","{body}"],
 "pr.review": ["pr","review","{number}","--repo","{repo}","--{review}","--body","{body}"],
 "pr.merge": ["pr","merge","{number}","--repo","{repo}","--{merge_method}"],
 "run.rerun": ["run","rerun","{run_id}","--repo","{repo}"],
 "run.cancel": ["run","cancel","{run_id}","--repo","{repo}"],
 "release.create": ["release","create","{tag}","--repo","{repo}","--title","{title}","--notes","{body}"],
 "release.upload": ["release","upload","{tag}","{file}","--repo","{repo}","--clobber"],
}
DESTRUCTIVE={"issue.close","pr.merge","run.cancel","release.upload"}
REQUIRED={
 "repo.view":["repo"],"issue.list":["repo"],"issue.get":["repo","number"],"issue.create":["repo","title"],"issue.comment":["repo","number","body"],"issue.close":["repo","number"],"issue.reopen":["repo","number"],
 "pr.list":["repo"],"pr.view":["repo","number"],"pr.checks":["repo","number"],"pr.create":["repo","title","head","base"],"pr.comment":["repo","number","body"],"pr.review":["repo","number","review"],"pr.merge":["repo","number"],
 "run.list":["repo"],"run.view":["repo","run_id"],"run.logs":["repo","run_id"],"run.rerun":["repo","run_id"],"run.cancel":["repo","run_id"],
 "release.list":["repo"],"release.view":["repo","tag"],"release.create":["repo","tag","title"],"release.upload":["repo","tag","file"],"api.get":["endpoint"]}
SECRET=re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|bearer\s+\S+|(?:token|secret|password|authorization)[=:]\s*\S+|AKIA[0-9A-Z]{16})")

def redact(v): return SECRET.sub("[REDACTED]", v)
def envelope(command, ok, data=None, error=None, effects=None):
 d={"ok":ok,"schemaVersion":1,"command":command,"requestId":str(uuid.uuid4()),"effects":effects or [],"provenance":{"backend":"gh","host":"redacted"}}
 if data is not None:d["data"]=data
 if error is not None:d["error"]=error
 return d

def parser():
 p=argparse.ArgumentParser(); p.add_argument("command");
 for n in ("host","expected-account","repo","state","number","run-id","title","body","head","base","review","merge-method","tag","file","endpoint","idempotency-key","job-id","jobs-dir"):
  p.add_argument("--"+n)
 p.add_argument("--limit",type=int,default=20);p.add_argument("--timeout-ms",type=int,default=20000);p.add_argument("--retries",type=int,default=1);p.add_argument("--dry-run",action="store_true");p.add_argument("--confirm")
 p.set_defaults(host="github.com",state="open",body="",review="comment",merge_method="squash",jobs_dir=os.path.expanduser("~/.openclaw/github-auth-jobs"));return p

def validate(a):
 if a.command not in READ and a.command not in MUTATE and a.command not in {"auth.login.start","auth.login.status","auth.login.cancel"}: raise ValueError("unknown command")
 for key in REQUIRED.get(a.command,[]):
  if not getattr(a,key):raise ValueError(f"missing --{key.replace('_','-')}")
 if a.repo and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",a.repo):raise ValueError("repo must be owner/name")
 if a.endpoint and (a.endpoint.startswith(("http:","https:","graphql")) or ".." in a.endpoint or not a.endpoint.startswith(("repos/","user","rate_limit"))):raise ValueError("API GET endpoint is outside the bounded allowlist")
 if a.limit<1 or a.limit>100 or a.timeout_ms<100 or a.timeout_ms>120000 or a.retries<0 or a.retries>3:raise ValueError("numeric option outside bounded range")
 if a.review not in {"approve","request-changes","comment"} or a.merge_method not in {"merge","squash","rebase"}:raise ValueError("invalid review or merge method")
 if a.command=="release.upload" and not Path(a.file).is_file():raise ValueError("upload file does not exist")
 if a.idempotency_key and not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}",a.idempotency_key):raise ValueError("idempotency key must be 8-128 safe characters")

def format_argv(template,a):
 vals=vars(a); return [x.format(**vals) for x in template]
def run_gh(argv,a,retryable=True):
 exe=shutil.which("gh");
 if not exe: raise RuntimeError("GitHub CLI `gh` is not installed")
 attempts=1+(a.retries if retryable else 0)
 for i in range(attempts):
  try:r=subprocess.run([exe]+argv,capture_output=True,text=True,timeout=a.timeout_ms/1000,env={**os.environ,"GH_PROMPT_DISABLED":"1"})
  except subprocess.TimeoutExpired: raise RuntimeError("gh command timed out")
  out=redact(r.stdout);err=redact(r.stderr)
  if r.returncode==0:
   try:return json.loads(out) if out.strip() else {"message":err.strip() or "completed"}
   except json.JSONDecodeError:return {"text":out.rstrip()}
  transient=("rate limit" in err.lower() or r.returncode in {75})
  if not transient or i+1==attempts: raise RuntimeError(err.strip() or f"gh exited {r.returncode}")
  time.sleep(min(.1*(2**i),.4))

def auth_start(a):
 root=Path(a.jobs_dir);root.mkdir(parents=True,exist_ok=True,mode=0o700); jid=str(uuid.uuid4())
 exe=shutil.which("gh")
 if not exe:raise RuntimeError("GitHub CLI `gh` is not installed")
 # Never capture provider output: it may contain one-time codes. `gh --web` owns the browser handoff.
 p=subprocess.Popen([exe,"auth","login","--hostname",a.host,"--web","--git-protocol","https"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env={**os.environ,"GH_PROMPT_DISABLED":"0"})
 state=root/(jid+".json");state.write_text(json.dumps({"pid":p.pid,"host":a.host,"created":time.time()}));state.chmod(0o600)
 return {"jobId":jid,"state":"waiting-for-user","humanSteps":["Complete GitHub sign-in, password, MFA, verification, and provider consent in the browser flow."],"next":"auth.login.status"}

def idempotency(a, record=False):
 if not a.idempotency_key:return None
 root=Path(a.jobs_dir)/"idempotency";root.mkdir(parents=True,exist_ok=True,mode=0o700)
 signature=hashlib.sha256(json.dumps({k:v for k,v in vars(a).items() if k not in {"confirm","dry_run","timeout_ms","retries"}},sort_keys=True).encode()).hexdigest()
 path=root/(hashlib.sha256(a.idempotency_key.encode()).hexdigest()+".json")
 if path.exists():
  prior=json.loads(path.read_text())
  if prior.get("signature")!=signature:raise ValueError("idempotency key was already used for different input")
  return {"idempotentReplay":True,"receipt":prior["receipt"]}
 if record:
  receipt=str(uuid.uuid4());path.write_text(json.dumps({"signature":signature,"receipt":receipt}));path.chmod(0o600);return {"receipt":receipt}
 return None
def auth_job(a,cancel=False):
 if not a.job_id or not re.fullmatch(r"[0-9a-f-]{36}",a.job_id):raise ValueError("valid --job-id required")
 path=Path(a.jobs_dir)/(a.job_id+".json"); info=json.loads(path.read_text());pid=int(info["pid"])
 alive=True
 try:os.kill(pid,15 if cancel else 0)
 except ProcessLookupError:alive=False
 return {"jobId":a.job_id,"state":"cancelled" if cancel else ("waiting-for-user" if alive else "finished"),"next":"auth.status" if not alive else "auth.login.status"}

def main():
 a=parser().parse_args(); effects=[]
 try:
  validate(a)
  if a.command in MUTATE:
   argv=format_argv(MUTATE[a.command],a);preview={"backend":"gh","operation":a.command,"target":a.repo,"destructive":a.command in DESTRUCTIVE}
   if a.dry_run: print(json.dumps(envelope(a.command,True,{"preview":preview},effects=[]),separators=(",",":")));return
   if a.confirm!=a.command:raise ValueError(f"mutation requires --confirm {a.command}; preview first with --dry-run")
   prior=idempotency(a)
   if prior:data=prior
   else:
    data=run_gh(argv,a,retryable=False);receipt=idempotency(a,record=True)
    if receipt and isinstance(data,dict):data={**data,**receipt}
   effects=[] if prior else [{"type":"externalSideEffect","operation":a.command,"target":a.repo}]
  elif a.command=="auth.login.start":
   if a.dry_run:data={"preview":{"operation":a.command,"host":a.host,"humanAccountAction":True}}
   elif a.confirm!=a.command:raise ValueError("authorization requires --confirm auth.login.start")
   else:data=auth_start(a);effects=[{"type":"humanAccountAction","operation":a.command}]
  elif a.command=="auth.login.status":data=auth_job(a)
  elif a.command=="auth.login.cancel":data=auth_job(a,True);effects=[{"type":"writeSafe","operation":a.command}]
  else:
   data=run_gh(format_argv(READ[a.command],a),a,True)
   if a.command=="auth.status" and a.expected_account:
    text=json.dumps(data)
    if a.expected_account not in text:raise RuntimeError("authenticated account does not match --expected-account")
  print(json.dumps(envelope(a.command,True,data,effects=effects),separators=(",",":")))
 except (ValueError,RuntimeError,FileNotFoundError,json.JSONDecodeError) as e:
  print(json.dumps(envelope(getattr(a,"command","unknown"),False,error={"code":"command_failed","message":redact(str(e))}),separators=(",",":")));print(redact(str(e)),file=sys.stderr);raise SystemExit(2)
if __name__=="__main__":main()
