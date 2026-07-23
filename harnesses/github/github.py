#!/usr/bin/env python3
"""Guarded JSON wrapper around the real GitHub CLI (`gh`)."""
from __future__ import annotations
import argparse, hashlib, json, os, re, resource, shutil, subprocess, sys, tempfile, time, uuid
from pathlib import Path

MAX_OUTPUT=262144; MAX_TITLE=256; MAX_BODY=65536; MAX_UPLOAD=100*1024*1024
READ={
 "repo.view":["repo","view","{repo}","--json","nameWithOwner,description,url,visibility,defaultBranchRef"],
 "issue.list":["issue","list","--repo","{repo}","--state","{state}","--limit","{limit}","--json","number,title,state,url,author,labels,updatedAt"],
 "issue.get":["issue","view","{number}","--repo","{repo}","--json","number,title,body,state,url,author,labels,comments,updatedAt"],
 "pr.list":["pr","list","--repo","{repo}","--state","{state}","--limit","{limit}","--json","number,title,state,url,author,isDraft,updatedAt"],
 "pr.view":["pr","view","{number}","--repo","{repo}","--json","number,title,body,state,url,author,isDraft,mergeable,reviewDecision,statusCheckRollup"],
 "pr.checks":["pr","checks","{number}","--repo","{repo}","--json","name,state,link,bucket,event,workflow"],
 "run.list":["run","list","--repo","{repo}","--limit","{limit}","--json","databaseId,name,status,conclusion,url,workflowName,createdAt,updatedAt"],
 "run.view":["run","view","{run_id}","--repo","{repo}","--json","databaseId,name,status,conclusion,url,jobs,workflowName"],
 "run.logs":["run","view","{run_id}","--repo","{repo}","--log-failed"],
 "release.list":["release","list","--repo","{repo}","--limit","{limit}","--json","tagName,name,isDraft,isPrerelease,publishedAt,url"],
 "release.view":["release","view","{tag}","--repo","{repo}","--json","tagName,name,body,isDraft,isPrerelease,publishedAt,url,assets"],
 "api.get":["api","--method","GET","{endpoint}"],
}
MUTATE={
 "issue.create":["issue","create","--repo","{repo}","--title","{title}","--body","{body}"],"issue.comment":["issue","comment","{number}","--repo","{repo}","--body","{body}"],"issue.close":["issue","close","{number}","--repo","{repo}"],"issue.reopen":["issue","reopen","{number}","--repo","{repo}"],
 "pr.create":["pr","create","--repo","{repo}","--title","{title}","--body","{body}","--head","{head}","--base","{base}"],"pr.comment":["pr","comment","{number}","--repo","{repo}","--body","{body}"],"pr.review":["pr","review","{number}","--repo","{repo}","--{review}","--body","{body}"],"pr.merge":["pr","merge","{number}","--repo","{repo}","--{merge_method}"],
 "run.rerun":["run","rerun","{run_id}","--repo","{repo}"],"run.cancel":["run","cancel","{run_id}","--repo","{repo}"],"release.create":["release","create","{tag}","--repo","{repo}","--title","{title}","--notes","{body}"],"release.upload":["release","upload","{tag}","{file}","--repo","{repo}","--clobber"],
}
DESTRUCTIVE={"issue.close","pr.merge","run.cancel","release.upload"}
REQUIRED={"repo.view":["repo"],"issue.list":["repo"],"issue.get":["repo","number"],"issue.create":["repo","title"],"issue.comment":["repo","number","body"],"issue.close":["repo","number"],"issue.reopen":["repo","number"],"pr.list":["repo"],"pr.view":["repo","number"],"pr.checks":["repo","number"],"pr.create":["repo","title","head","base"],"pr.comment":["repo","number","body"],"pr.review":["repo","number","review"],"pr.merge":["repo","number"],"run.list":["repo"],"run.view":["repo","run_id"],"run.logs":["repo","run_id"],"run.rerun":["repo","run_id"],"run.cancel":["repo","run_id"],"release.list":["repo"],"release.view":["repo","tag"],"release.create":["repo","tag","title"],"release.upload":["repo","tag","file"],"api.get":["endpoint"]}
SECRET=re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|bearer\s+\S+|(?:token|secret|password|authorization)[=:]\s*\S+|AKIA[0-9A-Z]{16})")
HOST=re.compile(r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*")
ENDPOINT=re.compile(r"(?:repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.~!$&'()*+,;=:@%/-]+)?|user|rate_limit)(?:\?[A-Za-z0-9_.~!$&'()*+,;=:@%/?=-]+)?")
def redact(v): return SECRET.sub("[REDACTED]",v)
def envelope(command,ok,data=None,error=None,effects=None):
 d={"ok":ok,"schemaVersion":1,"command":command,"requestId":str(uuid.uuid4()),"effects":effects or [],"provenance":{"backend":"gh","host":"redacted"}}
 if data is not None:d["data"]=data
 if error is not None:d["error"]=error
 return d
def parser():
 p=argparse.ArgumentParser();p.add_argument("command")
 for n in ("host","expected-account","repo","state","number","run-id","title","body","head","base","review","merge-method","tag","file","endpoint","confirm"):p.add_argument("--"+n)
 p.add_argument("--limit",type=int,default=20);p.add_argument("--timeout-ms",type=int,default=20000);p.add_argument("--retries",type=int,default=1);p.add_argument("--dry-run",action="store_true");p.set_defaults(host="github.com",state="open",body="",review="comment",merge_method="squash");return p
def validate(a):
 if a.command not in READ and a.command not in MUTATE and a.command!="auth.status":raise ValueError("unknown command")
 for key in REQUIRED.get(a.command,[]):
  if getattr(a,key) in (None,""):raise ValueError(f"missing --{key.replace('_','-')}")
 if not HOST.fullmatch(a.host):raise ValueError("host must be an exact DNS hostname")
 if a.expected_account and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})",a.expected_account):raise ValueError("invalid expected account")
 if a.repo and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}",a.repo):raise ValueError("repo must be owner/name")
 if a.state not in {"open","closed","merged","all"}:raise ValueError("invalid state")
 for value,name in ((a.number,"number"),(a.run_id,"run-id")):
  if value is not None and (not value.isdigit() or int(value)<1):raise ValueError(f"--{name} must be a positive integer")
 if a.endpoint and (len(a.endpoint)>512 or not ENDPOINT.fullmatch(a.endpoint) or ".." in a.endpoint):raise ValueError("API GET endpoint is outside the bounded allowlist")
 if not 1<=a.limit<=100 or not 100<=a.timeout_ms<=120000 or not 0<=a.retries<=3:raise ValueError("numeric option outside bounded range")
 if a.review not in {"approve","request-changes","comment"} or a.merge_method not in {"merge","squash","rebase"}:raise ValueError("invalid review or merge method")
 if a.title is not None and len(a.title)>MAX_TITLE:raise ValueError("title exceeds 256 characters")
 if a.body is not None and len(a.body)>MAX_BODY:raise ValueError("body exceeds 65536 characters")
 if a.command=="release.upload":
  f=Path(a.file)
  if not f.is_file() or f.is_symlink():raise ValueError("upload must be a regular non-symlink file")
  if f.stat().st_size>MAX_UPLOAD:raise ValueError("upload exceeds 100 MiB")
def format_argv(t,a):return [x.format(**vars(a)) for x in t]
def _limit_filesize():resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_OUTPUT+1,MAX_OUTPUT+1))
def run_gh(argv,a,retryable=True):
 exe=shutil.which("gh")
 if not exe:raise RuntimeError("GitHub CLI `gh` is not installed")
 for i in range(1+(a.retries if retryable else 0)):
  with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
   try:r=subprocess.run([exe]+argv,stdout=out,stderr=err,timeout=a.timeout_ms/1000,env={**os.environ,"GH_PROMPT_DISABLED":"1"},preexec_fn=_limit_filesize)
   except subprocess.TimeoutExpired:raise RuntimeError("gh command timed out")
   out.seek(0);rawout=out.read(MAX_OUTPUT+1);err.seek(0);rawerr=err.read(MAX_OUTPUT+1)
  if len(rawout)>MAX_OUTPUT or len(rawerr)>MAX_OUTPUT:raise RuntimeError("gh output exceeded 262144-byte limit")
  text=redact(rawout.decode("utf-8","replace"));error=redact(rawerr.decode("utf-8","replace"))
  if r.returncode==0:
   try:return json.loads(text) if text.strip() else {"message":error.strip() or "completed"}
   except json.JSONDecodeError:return {"text":text.rstrip()}
  transient="rate limit" in error.lower() or r.returncode==75
  if not transient or i==a.retries or not retryable:raise RuntimeError(error.strip() or f"gh exited {r.returncode}")
  time.sleep(min(.1*(2**i),.4))
def auth_status(a):
 data=run_gh(["api","--hostname",a.host,"--method","GET","user","--jq","{login:.login}"],a,True)
 login=data.get("login") if isinstance(data,dict) else None
 if not isinstance(login,str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})",login):raise RuntimeError("authenticated account response was invalid")
 if a.expected_account is not None and login!=a.expected_account:raise RuntimeError("authenticated account does not match --expected-account")
 return {"host":a.host,"login":login,"authenticated":True}
def main():
 a=parser().parse_args();effects=[]
 try:
  validate(a)
  if a.command in MUTATE:
   preview={"backend":"gh","operation":a.command,"target":a.repo,"destructive":a.command in DESTRUCTIVE,"clobbersExistingAsset":a.command=="release.upload","idempotency":"best-effort local receipt only; backend commit may be ambiguous"}
   if a.dry_run:data={"preview":preview}
   elif a.confirm!=a.command:raise ValueError(f"mutation requires --confirm {a.command}; preview first with --dry-run")
   else:
    data=run_gh(format_argv(MUTATE[a.command],a),a,retryable=False);effects=[{"type":"externalSideEffect","operation":a.command,"target":a.repo}]
  elif a.command=="auth.status":data=auth_status(a)
  else:data=run_gh(format_argv(READ[a.command],a),a,True)
  print(json.dumps(envelope(a.command,True,data,effects=effects),separators=(",",":")))
 except (ValueError,RuntimeError,OSError,json.JSONDecodeError) as e:
  mutation=getattr(a,"command","") in MUTATE
  error={"code":"command_failed","message":redact(str(e)),"retryable":False if mutation else "rate limit" in str(e).lower(),"ambiguousCommit":mutation and getattr(a,"confirm",None)==getattr(a,"command",None)}
  print(json.dumps(envelope(getattr(a,"command","unknown"),False,error=error),separators=(",",":")));print(redact(str(e))[:4096],file=sys.stderr);raise SystemExit(2)
if __name__=="__main__":main()
