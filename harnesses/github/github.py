#!/usr/bin/env python3
"""Guarded JSON wrapper around the real GitHub CLI (`gh`)."""
from __future__ import annotations
import argparse, hashlib, json, os, pwd, re, resource, shutil, subprocess, sys, tempfile, time, uuid
from pathlib import Path
from urllib.parse import quote

MAX_OUTPUT=262144; MAX_TITLE=256; MAX_BODY=65536; MAX_UPLOAD=100*1024*1024; MAX_DESCRIPTION=350; MAX_HOMEPAGE=2048
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
 "repo.create":[],
 "repo.push":[],
 "issue.create":["issue","create","--repo","{repo}","--title","{title}","--body","{body}"],"issue.comment":["issue","comment","{number}","--repo","{repo}","--body","{body}"],"issue.close":["issue","close","{number}","--repo","{repo}"],"issue.reopen":["issue","reopen","{number}","--repo","{repo}"],
 "pr.create":["pr","create","--repo","{repo}","--title","{title}","--body","{body}","--head","{head}","--base","{base}"],"pr.comment":["pr","comment","{number}","--repo","{repo}","--body","{body}"],"pr.review":["pr","review","{number}","--repo","{repo}","--{review}","--body","{body}"],"pr.merge":["pr","merge","{number}","--repo","{repo}","--{merge_method}"],
 "run.rerun":["run","rerun","{run_id}","--repo","{repo}"],"run.cancel":["run","cancel","{run_id}","--repo","{repo}"],"release.create":["release","create","{tag}","--repo","{repo}","--title","{title}","--notes","{body}"],"release.upload":["release","upload","{tag}","{file}","--repo","{repo}","--clobber"],
 "release.body.update":[],
}
DESTRUCTIVE={"issue.close","pr.merge","run.cancel","release.upload"}
REQUIRED={"repo.create":["repo","source","visibility","description"],"repo.push":["host","expected_account","repo","source","source_branch","remote_branch"],"repo.view":["repo"],"issue.list":["repo"],"issue.get":["repo","number"],"issue.create":["repo","title"],"issue.comment":["repo","number","body"],"issue.close":["repo","number"],"issue.reopen":["repo","number"],"pr.list":["repo"],"pr.view":["repo","number"],"pr.checks":["repo","number"],"pr.create":["repo","title","head","base"],"pr.comment":["repo","number","body"],"pr.review":["repo","number","review"],"pr.merge":["repo","number"],"run.list":["repo"],"run.view":["repo","run_id"],"run.logs":["repo","run_id"],"run.rerun":["repo","run_id"],"run.cancel":["repo","run_id"],"release.list":["repo"],"release.view":["repo","tag"],"release.create":["repo","tag","title"],"release.upload":["repo","tag","file"],"release.body.update":["repo","tag","body"],"api.get":["endpoint"]}
REDACTION_PATTERN=re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|bearer\s+\S+|(?:token|secret|password|authorization)[=:]\s*\S+|AKIA[0-9A-Z]{16})")
HOST=re.compile(r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*")
ENDPOINT=re.compile(r"(?:repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.~!$&'()*+,;=:@%/-]+)?|user|rate_limit)(?:\?[A-Za-z0-9_.~!$&'()*+,;=:@%/?=-]+)?")
def redact(v): return REDACTION_PATTERN.sub("[REDACTED]",v)
def envelope(command,ok,data=None,error=None,effects=None):
 d={"ok":ok,"schemaVersion":1,"command":command,"requestId":str(uuid.uuid4()),"effects":effects or [],"provenance":{"backend":"gh","host":"redacted"}}
 if data is not None:d["data"]=data
 if error is not None:d["error"]=error
 return d
def parser():
 p=argparse.ArgumentParser();p.add_argument("command")
 for n in ("host","expected-account","repo","source","source-branch","remote-branch","expected-remote-sha","visibility","description","homepage","state","number","run-id","title","body","head","base","review","merge-method","tag","file","endpoint","confirm"):p.add_argument("--"+n)
 p.add_argument("--limit",type=int,default=20);p.add_argument("--timeout-ms",type=int,default=20000);p.add_argument("--retries",type=int,default=1);p.add_argument("--dry-run",action="store_true");p.set_defaults(host=None,state="open",body=None,review="comment",merge_method="squash");return p
def validate(a):
 if a.command not in READ and a.command not in MUTATE and a.command!="auth.status":raise ValueError("unknown command")
 if a.command!="repo.push" and a.host is None:a.host="github.com"
 for key in REQUIRED.get(a.command,[]):
  value=getattr(a,key)
  if value is None or (value=="" and not (a.command=="release.body.update" and key=="body")):raise ValueError(f"missing --{key.replace('_','-')}")
 if not HOST.fullmatch(a.host):raise ValueError("host must be an exact DNS hostname")
 if a.expected_account and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})",a.expected_account):raise ValueError("invalid expected account")
 if a.repo and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})/[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})",a.repo):raise ValueError("repo must be exact owner/name")
 if a.command in {"repo.create","repo.push"}:
  source=Path(a.source)
  if not source.is_absolute() or source.is_symlink() or not source.is_dir():raise ValueError("source must be an absolute non-symlink directory")
 if a.command=="repo.create":
  if a.visibility not in {"private","public","internal"}:raise ValueError("visibility must be exactly private, public, or internal")
  if len(a.description)>MAX_DESCRIPTION or any(ord(c)<32 or ord(c)==127 for c in a.description):raise ValueError("description contains control characters or exceeds 350 characters")
  if a.homepage is not None:
   if len(a.homepage)>MAX_HOMEPAGE or not re.fullmatch(r"https://[^\s/?#]+(?:[/?#][^\s]*)?",a.homepage):raise ValueError("homepage must be an HTTPS URL of at most 2048 characters")
 if a.command=="repo.push":
  for value,name in ((a.source_branch,"source-branch"),(a.remote_branch,"remote-branch")):
   if len(value)>255 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError(f"--{name} is not a bounded Git branch name")
  if a.expected_remote_sha is not None and not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",a.expected_remote_sha):raise ValueError("--expected-remote-sha must be a full commit SHA")
 allowed_states={"issue.list":{"open","closed","all"},"pr.list":{"open","closed","merged","all"}}
 if a.command in allowed_states and a.state not in allowed_states[a.command]:raise ValueError(f"invalid state for {a.command}")
 for value,name in ((a.number,"number"),(a.run_id,"run-id")):
  if value is not None and (not value.isdigit() or int(value)<1):raise ValueError(f"--{name} must be a positive integer")
 if a.endpoint and (len(a.endpoint)>512 or not ENDPOINT.fullmatch(a.endpoint) or ".." in a.endpoint):raise ValueError("API GET endpoint is outside the bounded allowlist")
 if not 1<=a.limit<=100 or not 100<=a.timeout_ms<=120000 or not 0<=a.retries<=3:raise ValueError("numeric option outside bounded range")
 if a.review not in {"approve","request-changes","comment"} or a.merge_method not in {"merge","squash","rebase"}:raise ValueError("invalid review or merge method")
 if a.title is not None and len(a.title)>MAX_TITLE:raise ValueError("title exceeds 256 characters")
 if a.body is not None and len(a.body)>MAX_BODY:raise ValueError("body exceeds 65536 characters")
 if a.tag is not None and (len(a.tag)>255 or any(ord(c)<32 or ord(c)==127 for c in a.tag)):raise ValueError("tag contains control characters or exceeds 255 characters")
 if a.command=="release.upload":
  f=Path(a.file)
  if not f.is_file() or f.is_symlink():raise ValueError("upload must be a regular non-symlink file")
  if f.stat().st_size>MAX_UPLOAD:raise ValueError("upload exceeds 100 MiB")
 if a.body is None:a.body=""
def format_argv(t,a):return [x.format(**vars(a)) for x in t]
def _limit_filesize():resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_OUTPUT+1,MAX_OUTPUT+1))
def _gh_env():
 env={**os.environ,"GH_PROMPT_DISABLED":"1"}
 if not env.get("HOME"):
  try:home=pwd.getpwuid(os.geteuid()).pw_dir
  except KeyError as e:raise RuntimeError("cannot resolve the system account home for GitHub CLI authentication") from e
  if not home or not os.path.isabs(home):raise RuntimeError("system account home is invalid")
  env["HOME"]=home
 return env
def run_gh(argv,a,retryable=True,input_data=None):
 exe=shutil.which("gh")
 if not exe:raise RuntimeError("GitHub CLI `gh` is not installed")
 for i in range(1+(a.retries if retryable else 0)):
  with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
   try:
    r=subprocess.run([exe]+argv,input=input_data,stdout=out,stderr=err,timeout=a.timeout_ms/1000,env=_gh_env(),preexec_fn=_limit_filesize)
    if not retryable:a.mutation_backend_started=True
   except subprocess.TimeoutExpired:
    if not retryable:a.mutation_backend_started=True
    raise RuntimeError("gh command timed out")
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
def _release_endpoint(repo,release_id):return f"repos/{repo}/releases/{release_id}"
def _release_snapshot(release,expected_tag,expected_id=None):
 if not isinstance(release,dict):raise RuntimeError("release response was not an object")
 release_id=release.get("id")
 if isinstance(release_id,bool) or not isinstance(release_id,int) or release_id<1:raise RuntimeError("release response did not contain a positive numeric id")
 if expected_id is not None and release_id!=expected_id:raise RuntimeError("release readback id did not match the inspected release")
 if release.get("tag_name")!=expected_tag:raise RuntimeError("release response tag did not exactly match --tag")
 if not isinstance(release.get("body"),str):raise RuntimeError("release response body was not a string")
 if not isinstance(release.get("assets"),list):raise RuntimeError("release response assets was not an array")
 metadata={k:v for k,v in release.items() if k not in {"body","updated_at","assets"}}
 return release_id,{"metadata":metadata,"assets":release["assets"]}
def _snapshot_digest(snapshot):
 raw=json.dumps(snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
 return hashlib.sha256(raw).hexdigest()
def _get_release_by_tag(a):
 endpoint=f"repos/{a.repo}/releases/tags/{quote(a.tag,safe='')}"
 release=run_gh(["api","--hostname",a.host,"--method","GET",endpoint],a,True)
 release_id,snapshot=_release_snapshot(release,a.tag)
 return release,release_id,snapshot
def release_body_update(a,mutate):
 before,release_id,snapshot=_get_release_by_tag(a)
 endpoint=_release_endpoint(a.repo,release_id);digest=_snapshot_digest(snapshot)
 preview={"backend":"gh","operation":a.command,"target":a.repo,"tag":a.tag,"releaseId":release_id,"endpoint":endpoint,"request":{"method":"PATCH","jsonKeys":["body"]},"changes":{"body":{"before":before["body"],"after":a.body}},"protectedSnapshot":{"fields":sorted(snapshot["metadata"]),"digest":digest,"assetCount":len(snapshot["assets"])},"idempotency":"mutation is never retried; post-mutation state is independently read back and verified"}
 if not mutate:return {"preview":preview}
 payload=json.dumps({"body":a.body},separators=(",",":"),ensure_ascii=False).encode("utf-8")
 run_gh(["api","--hostname",a.host,"--method","PATCH",endpoint,"--input","-"],a,retryable=False,input_data=payload)
 after=run_gh(["api","--hostname",a.host,"--method","GET",endpoint],a,True)
 _,after_snapshot=_release_snapshot(after,a.tag,release_id)
 mismatches=[]
 if after["body"]!=a.body:mismatches.append("body")
 if after_snapshot["metadata"]!=snapshot["metadata"]:mismatches.append("protected metadata")
 if after_snapshot["assets"]!=snapshot["assets"]:mismatches.append("assets")
 if mismatches:raise RuntimeError("release body-only verification failed: "+", ".join(mismatches)+" mismatch")
 return {"releaseId":release_id,"tag":a.tag,"endpoint":endpoint,"bodyMatched":True,"protectedMetadataMatched":True,"assetsMatched":True,"protectedSnapshotDigest":digest,"readback":"independent GET by numeric release id"}
def _run_local_git(source,args,a):
 exe=shutil.which("git")
 if not exe:raise RuntimeError("git is not installed")
 try:r=subprocess.run([exe,"-C",str(source)]+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=a.timeout_ms/1000,env={**os.environ,"GIT_TERMINAL_PROMPT":"0"},preexec_fn=_limit_filesize)
 except subprocess.TimeoutExpired as e:raise RuntimeError("git inspection timed out") from e
 if len(r.stdout)>MAX_OUTPUT or len(r.stderr)>MAX_OUTPUT:raise RuntimeError("git output exceeded 262144-byte limit")
 out=redact(r.stdout.decode("utf-8","replace")).strip();err=redact(r.stderr.decode("utf-8","replace")).strip()
 if r.returncode:raise RuntimeError(err or f"git exited {r.returncode}")
 return out

def _validate_branch_name(source,branch,a,flag):
 try:_run_local_git(source,["check-ref-format","--branch",branch],a)
 except RuntimeError as e:raise ValueError(f"--{flag} is not a valid Git branch name") from e

def _inspect_source(a):
 source=Path(a.source)
 if _run_local_git(source,["rev-parse","--is-inside-work-tree"],a)!="true":raise ValueError("source is not a git work tree")
 if _run_local_git(source,["rev-parse","--is-bare-repository"],a)!="false":raise ValueError("source must be non-bare")
 branch=_run_local_git(source,["symbolic-ref","--quiet","--short","HEAD"],a)
 if not branch or len(branch)>255 or any(ord(c)<32 or ord(c)==127 for c in branch):raise ValueError("source HEAD must be attached to a bounded branch")
 head=_run_local_git(source,["rev-parse","--verify","HEAD"],a)
 if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",head):raise ValueError("source must have a full HEAD commit")
 if _run_local_git(source,["status","--porcelain=v1","--untracked-files=all"],a):raise ValueError("source git work tree must be clean")
 return source,branch,head.lower()

def _remote_branch(a):
 endpoint=f"repos/{a.repo}/git/matching-refs/heads/{quote(a.remote_branch,safe='')}"
 refs=run_gh(["api","--hostname",a.host,"--method","GET",endpoint],a,True)
 if not isinstance(refs,list):raise RuntimeError("remote matching-refs response was not an array")
 exact=[item for item in refs if isinstance(item,dict) and item.get("ref")==f"refs/heads/{a.remote_branch}"]
 if len(exact)>1:raise RuntimeError("remote branch lookup returned duplicate exact refs")
 if not exact:return None
 obj=exact[0].get("object")
 sha=obj.get("sha") if isinstance(obj,dict) else None
 if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",sha):raise RuntimeError("remote branch response did not contain a full commit SHA")
 return sha.lower()

def _git_push(source,a):
 exe=shutil.which("git");gh=shutil.which("gh")
 if not exe:raise RuntimeError("git is not installed")
 if not gh:raise RuntimeError("gh is not installed")
 with tempfile.TemporaryDirectory(prefix="github-push-") as td:
  askpass=Path(td)/"askpass";askpass.write_text(f'#!/bin/sh\nif [ -n "$GH_TOKEN" ]; then printf %s "$GH_TOKEN"; else exec {gh} auth token --hostname "$GH_HOST"; fi\n');askpass.chmod(0o700)
  env={**_gh_env(),"GIT_TERMINAL_PROMPT":"0","GIT_ASKPASS":str(askpass),"GIT_ASKPASS_REQUIRE":"force","GH_HOST":a.host}
  argv=[exe,"-C",str(source),"push",f"https://x-access-token@{a.host}/{a.repo}.git",f"HEAD:refs/heads/{a.remote_branch}"]
  try:
   a.mutation_backend_started=True
   r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=a.timeout_ms/1000,env=env,preexec_fn=_limit_filesize)
  except subprocess.TimeoutExpired as e:raise RuntimeError("git push timed out") from e
 if len(r.stdout)>MAX_OUTPUT or len(r.stderr)>MAX_OUTPUT:raise RuntimeError("git push output exceeded 262144-byte limit")
 if r.returncode:
  error=redact(r.stderr.decode("utf-8","replace")).strip()
  raise RuntimeError(error or f"git push exited {r.returncode}")

def repo_push(a,mutate):
 source,branch,head=_inspect_source(a)
 _validate_branch_name(source,a.source_branch,a,"source-branch");_validate_branch_name(source,a.remote_branch,a,"remote-branch")
 if branch!=a.source_branch:raise ValueError("attached source branch does not exactly match --source-branch")
 branch_head=_run_local_git(source,["rev-parse","--verify",f"refs/heads/{a.source_branch}"],a).lower()
 if branch_head!=head:raise ValueError("--source-branch does not resolve to the exact local HEAD")
 auth_status(a)
 remote_before=_remote_branch(a)
 expected=a.expected_remote_sha.lower() if a.expected_remote_sha else None
 if remote_before is not None and expected is None:raise ValueError("remote branch already exists; --expected-remote-sha is required")
 if expected is not None and remote_before!=expected:raise ValueError("remote branch SHA does not exactly match --expected-remote-sha")
 preview={"backend":"git+gh","operation":a.command,"target":{"host":a.host,"repo":a.repo,"expectedAccount":a.expected_account},"source":{"branch":branch,"head":head,"clean":True},"remote":{"branch":a.remote_branch,"currentSha":remote_before,"expectedRemoteSha":expected},"refspec":f"HEAD:refs/heads/{a.remote_branch}","force":False,"idempotency":"push is never retried once started; independent branch ref and repository metadata readback is required"}
 if not mutate:return {"preview":preview}
 _git_push(source,a)
 ref=run_gh(["api","--hostname",a.host,"--method","GET",f"repos/{a.repo}/git/ref/heads/{quote(a.remote_branch,safe='')}"],a,True)
 repo=run_gh(["repo","view",a.repo,"--json","nameWithOwner,visibility,url"],a,True)
 remote_sha=(ref.get("object") or {}).get("sha") if isinstance(ref,dict) and isinstance(ref.get("object"),dict) else ref.get("sha") if isinstance(ref,dict) else None
 visibility=repo.get("visibility","").lower() if isinstance(repo,dict) and isinstance(repo.get("visibility"),str) else None
 mismatches=[]
 if not isinstance(remote_sha,str) or remote_sha.lower()!=head:mismatches.append("remote commit")
 if not isinstance(repo,dict) or repo.get("nameWithOwner")!=a.repo:mismatches.append("target")
 if visibility not in {"private","public","internal"}:mismatches.append("visibility")
 if not isinstance(repo.get("url") if isinstance(repo,dict) else None,str) or not repo["url"].startswith("https://"):mismatches.append("URL")
 if mismatches:raise RuntimeError("repository push verification failed: "+", ".join(mismatches)+" mismatch")
 return {"nameWithOwner":a.repo,"visibility":visibility,"url":repo["url"],"sourceBranch":branch,"remoteBranch":a.remote_branch,"sourceHead":head,"remoteCommitSha":remote_sha.lower(),"verified":True,"readback":"independent repository metadata and branch ref queries"}

def repo_create(a,mutate):
 source,branch,head=_inspect_source(a)
 preview={"backend":"gh","operation":a.command,"target":a.repo,"visibility":a.visibility,"source":{"branch":branch,"head":head,"clean":True},"descriptionLength":len(a.description),"homepage":a.homepage,"idempotency":"mutation is never retried; repository creation or push may be ambiguous once started; independent provider readback is required"}
 if not mutate:return {"preview":preview}
 argv=["repo","create",a.repo,"--"+a.visibility,"--description",a.description,"--source",str(source),"--remote","origin","--push"]
 if a.homepage is not None:argv.extend(["--homepage",a.homepage])
 run_gh(argv,a,retryable=False)
 repo=run_gh(["repo","view",a.repo,"--json","nameWithOwner,visibility,defaultBranchRef,url"],a,True)
 ref=run_gh(["api","--hostname",a.host,"--method","GET",f"repos/{a.repo}/git/ref/heads/{quote(branch,safe='')}","--jq","{sha:.object.sha}"],a,True)
 default=(repo.get("defaultBranchRef") or {}).get("name") if isinstance(repo,dict) else None
 remote_sha=ref.get("sha") if isinstance(ref,dict) else None
 visibility=repo.get("visibility","").lower() if isinstance(repo,dict) and isinstance(repo.get("visibility"),str) else None
 mismatches=[]
 if not isinstance(repo,dict) or repo.get("nameWithOwner")!=a.repo:mismatches.append("target")
 if visibility!=a.visibility:mismatches.append("visibility")
 if default!=branch:mismatches.append("default branch")
 if not isinstance(repo.get("url") if isinstance(repo,dict) else None,str) or not repo["url"].startswith("https://"):mismatches.append("URL")
 if not isinstance(remote_sha,str) or remote_sha.lower()!=head:mismatches.append("remote commit")
 if mismatches:raise RuntimeError("repository creation verification failed: "+", ".join(mismatches)+" mismatch")
 return {"nameWithOwner":a.repo,"visibility":a.visibility,"defaultBranch":branch,"url":repo["url"],"sourceHead":head,"remoteCommitSha":remote_sha.lower(),"verified":True,"readback":"independent repository metadata and branch ref queries"}

def main():
 a=parser().parse_args();a.mutation_backend_started=False;effects=[]
 try:
  validate(a)
  if a.command=="repo.create":
   if a.dry_run:data=repo_create(a,False)
   elif a.confirm!=a.command:raise ValueError(f"mutation requires --confirm {a.command}; preview first with --dry-run")
   else:
    data=repo_create(a,True);effects=[{"type":"externalSideEffect","operation":a.command,"target":a.repo}]
  elif a.command=="repo.push":
   if a.dry_run:data=repo_push(a,False)
   elif a.confirm!=a.command:raise ValueError(f"mutation requires --confirm {a.command}; preview first with --dry-run")
   else:
    data=repo_push(a,True);effects=[{"type":"externalSideEffect","operation":a.command,"target":a.repo}]
  elif a.command=="release.body.update":
   if a.dry_run:data=release_body_update(a,False)
   elif a.confirm!=a.command:raise ValueError(f"mutation requires --confirm {a.command}; preview first with --dry-run")
   else:
    data=release_body_update(a,True);effects=[{"type":"externalSideEffect","operation":a.command,"target":a.repo}]
  elif a.command in MUTATE:
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
  error={"code":"command_failed","message":redact(str(e)),"retryable":False if mutation else "rate limit" in str(e).lower(),"ambiguousCommit":bool(mutation and getattr(a,"mutation_backend_started",False))}
  print(json.dumps(envelope(getattr(a,"command","unknown"),False,error=error),separators=(",",":")));print(redact(str(e))[:4096],file=sys.stderr);raise SystemExit(2)
if __name__=="__main__":main()
