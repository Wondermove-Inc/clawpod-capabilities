#!/usr/bin/env python3
"""Deterministic guardrail CLI for Claude Design's currently human-operated surfaces."""
from __future__ import annotations
import argparse, hashlib, json, mimetypes, os, re, shutil, subprocess, sys, uuid
from pathlib import Path

VERSION="0.2.0"
DESIGN_URL="https://claude.ai/design"
MCP_NAME="claude-design"
MCP_URL="https://api.anthropic.com/v1/design/mcp"
DESTINATIONS=["Adobe","Base44","Canva","Gamma","Lovable","Miro","Replit","Vercel","Wix","Claude Code"]
FORMATS={"html":"text/html","pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation","pdf":"application/pdf"}
PREVIEW_APPLY={
 "projects.share","projects.comment","projects.handoff","design-systems.publish","design-systems.set-default",
 "destinations.handoff","code.sync","admin.enable","admin.role-update"
}
READS={
 "projects.list","projects.get","projects.search","projects.present","design-systems.list","design-systems.get",
 "templates.list","templates.get","admin.status","admin.permissions","admin.usage","destinations.list"
}
HANDOFFS={
 "projects.create","projects.update","projects.iterate","projects.edit","projects.delete",
 "design-systems.create","design-systems.update","design-systems.remix","design-systems.delete",
 "templates.create","templates.update","templates.delete"
}
SECRET_KEYS=re.compile(r"token|password|secret|authorization|cookie",re.I)
ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")

def envelope(command,ok=True,data=None,warnings=None,error=None,retry_safe=True,evidence=None):
 out={"ok":ok,"command":command,"request_id":str(uuid.uuid4()),"data":data or {},"warnings":warnings or [],"evidence":evidence or [],"retry_safe":retry_safe}
 if error: out["error"]=error
 print(json.dumps(out,separators=(",",":"),ensure_ascii=False)); return 0 if ok else 2

def fail(command,code,message,retry=True,data=None):
 return envelope(command,False,data=data,error={"code":code,"message":message},retry_safe=retry)

def canonical(command, values):
 clean={k:v for k,v in values.items() if v not in (None,False,[],"") and k not in {"effect_digest","approve","command"} and not SECRET_KEYS.search(k)}
 return json.dumps({"command":command,"values":clean},sort_keys=True,separators=(",",":"),ensure_ascii=False)

def effect_digest(command,values): return hashlib.sha256(canonical(command,values).encode()).hexdigest()

def run_claude(args,timeout=5):
 exe=shutil.which("claude")
 if not exe:return {"available":False,"exit_code":None,"stdout":"","stderr":"claude executable not found"}
 env={k:v for k,v in os.environ.items() if k!="CLAUDE_CODE_OAUTH_TOKEN"}
 # setup-token is a contract, never silently remapped to another auth variable.
 try:
  p=subprocess.run([exe,*args],capture_output=True,text=True,timeout=timeout,env=env)
  text=lambda s: re.sub(r"(?i)(token|secret|password|authorization|cookie)\s*[:=]\s*\S+",r"\1=[REDACTED]",s)[:12000]
  return {"available":True,"exit_code":p.returncode,"stdout":text(p.stdout.strip()),"stderr":text(p.stderr.strip())}
 except subprocess.TimeoutExpired:return {"available":True,"exit_code":None,"stdout":"","stderr":"bounded command timed out","timed_out":True}
 except OSError as e:return {"available":True,"exit_code":None,"stdout":"","stderr":str(e)[:500]}

def require_id(command,value,label):
 if not value or not ID_RE.fullmatch(value):return fail(command,"INVALID_INPUT",f"--{label.replace('_','-')} must be a non-empty safe identifier.")

def file_evidence(path_s):
 p=Path(path_s).expanduser()
 if not p.is_file():raise ValueError("output path is not a regular file")
 raw=p.read_bytes(); mime=mimetypes.guess_type(p.name)[0] or "application/octet-stream"
 return {"path":str(p.resolve()),"mime":mime,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

def handoff(command,values,action,source):
 return fail(command,"HUMAN_VERIFICATION",action+" Then reconcile "+source+" before retrying or claiming success.",False,{"url":DESIGN_URL,"values":values,"reconciliation_source":source})

def parser():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("command")
 for name in ["project-id","design-system-id","template-id","repository-path","direction","effect-digest","prompt","template","model","access","role","principal","format","output-path","exact-name","destination","name","query","owner","sort","view","target","text","patch","sources","member","organization","scope","mcp-name","mcp-command","mcp-url"]:p.add_argument("--"+name)
 p.add_argument("--starred",action="store_true");p.add_argument("--start-from-code",action="store_true");p.add_argument("--approve",action="store_true")
 p.add_argument("--attachment",action="append",default=[]);p.add_argument("--option",action="append",default=[])
 return p

def main(argv=None):
 a=parser().parse_args(argv); c=a.command; v=vars(a)
 if c=="system.version":return envelope(c,data={"name":"claude-design","title":"Claude Design","version":VERSION,"provider_execution":"human_or_live_mcp_schema_required"})
 if c=="onboarding.plan":return envelope(c,data={"state":"installed_not_connected","approval_scope":"One connection approval covers bounded authentication and official MCP onboarding only; project mutations and external effects remain separately approved.","agent_steps":["inspect Claude Code and existing authentication","idempotently register official user-scope MCP","verify MCP get/list connectivity","discover live tool schema","run bounded read-only account/project smoke test","recover safe transient failures and report CONNECTED, DEGRADED, or BLOCKED"],"human_only":["sign-in when no reusable authentication exists","MFA","provider consent","credential-use authorization"],"never_delegate_to_user":["CLI commands","MCP endpoint entry","configuration editing","schema inspection","routine retries"],"official_mcp":{"name":MCP_NAME,"url":MCP_URL,"scope":"user","transport":"http"},"revocation":["claude mcp logout claude-design","claude mcp remove claude-design -s user","Claude account settings"],"no_secret_persistence":True})
 if c=="onboarding.preflight":
  r=run_claude(["--version"]);return envelope(c,data={"claude":r,"setup_token_present":bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN")),"design_url":DESIGN_URL,"ready_for_login":r["available"]},warnings=["Presence of a setup token does not authorize its use."])
 if c=="onboarding.status":
  get=run_claude(["mcp","get",MCP_NAME]); listed=run_claude(["mcp","list"]); connected=get.get("exit_code")==0 and "Connected" in (get.get("stdout","")+get.get("stderr","")); return envelope(c,data={"installed":True,"connection_state":"CONNECTED" if connected else "NOT_CONNECTED","official_mcp":{"name":MCP_NAME,"url":MCP_URL},"mcp_get":get,"mcp_list":listed,"schema_discovered":False},warnings=[] if connected else ["After approval, the agent must register and verify the official MCP automatically; do not delegate CLI work to the user."])
 if c=="auth.contract":return envelope(c,data={"setup_token_command":"claude setup-token","setup_token_env":"CLAUDE_CODE_OAUTH_TOKEN","setup_token_use_requires_approval":True,"setup_token_persisted":False,"login_handoff":"Agent starts and resumes the bounded login flow; user performs only sign-in, MFA, and provider consent when required.","existing_auth_reuse":True,"agent_owns_mcp_registration":True,"official_mcp":{"name":MCP_NAME,"url":MCP_URL,"scope":"user","transport":"http"}})
 if c=="auth.status":return envelope(c,data={"claude_cli":bool(shutil.which("claude")),"setup_token_present":bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN")),"identity":"not_safely_inferred"})
 if c=="auth.setup-token.plan":return envelope(c,data={"command":["claude","setup-token"],"interactive":True,"credential_use":True,"next":"Protect the resulting token; do not paste it into argv or files. Then run /design-login in Claude Code."})
 if c=="code.login.handoff":return handoff(c,{},"The agent starts the bounded Claude/MCP login flow. Complete only the provider sign-in, MFA, or consent screen if it appears; return control immediately afterward.","Claude Code MCP get/list, live schema, and read-only Claude Design source of truth")
 if c=="mcp.inspect":return envelope(c,data={"get":run_claude(["mcp","get",MCP_NAME]),"list":run_claude(["mcp","list"]),"official_design_mcp_documented":True,"official_name":MCP_NAME,"official_url":MCP_URL,"tool_schema_discovered":False},warnings=["Connectivity and live schema still require source-of-truth verification."])
 if c=="mcp.validate":return fail(c,"BACKEND_UNAVAILABLE","Run MCP get/list, discover the live schema, and execute a bounded read-only smoke test before claiming CONNECTED.",True,{"agent_next":["idempotently register the official MCP if absent","reuse existing auth or start bounded login","discover schema","run read-only smoke test"],"human_only":["sign-in","MFA","consent"]})
 if c in {"mcp.install-plan","mcp.remove-plan"}:
  verb="add" if c.endswith("install-plan") else "remove"
  if verb=="add" and not (a.mcp_command or a.mcp_url):return fail(c,"INVALID_INPUT","An observed official --mcp-command or --mcp-url is required; this harness will not invent one.")
  if verb=="remove":
   result=require_id(c,a.mcp_name,"mcp_name")
   if result is not None:return result
  argv=["claude","mcp",verb]+(([a.mcp_name] if a.mcp_name else []))
  return envelope(c,data={"argv":argv,"execute":False,"requires_approval":True,"reconcile":"claude mcp list/get"})
 if c=="projects.export.verify":
  if not a.output_path:return fail(c,"INVALID_INPUT","--output-path is required.")
  try: info=file_evidence(a.output_path)
  except (OSError,ValueError) as e:return fail(c,"NOT_FOUND",str(e))
  if a.format:
   if a.format not in FORMATS:return fail(c,"INVALID_INPUT","--format must be html, pptx, or pdf.")
   expected=FORMATS[a.format]; info["expected_mime"]=expected; info["mime_matches"]=info["mime"]==expected
  return envelope(c,data=info,evidence=[{"kind":"artifact","ref":info["sha256"]}])
 if c=="projects.export":
  result=require_id(c,a.project_id,"project_id")
  if result is not None:return result
  if a.format not in FORMATS:return fail(c,"INVALID_INPUT","--format must be html, pptx, or pdf.")
  if not a.output_path:return fail(c,"INVALID_INPUT","--output-path is required.")
  return handoff(c,{"project_id":a.project_id,"format":a.format,"output_path":a.output_path},"Open the exact project, choose Share > Export and the requested format, and save to the approved path.","local regular file MIME, bytes, and SHA-256 via projects.export.verify")
 if c in READS:
  if c.endswith(".get") and not (a.project_id or a.design_system_id or a.template_id):return fail(c,"INVALID_INPUT","The resource identifier is required.")
  if c=="destinations.list":return envelope(c,data={"destinations":DESTINATIONS,"connection_state":"requires live account readback"})
  return handoff(c,{k:x for k,x in v.items() if x not in (None,False,[],"") and k not in {"command","approve"}},"Open the Claude Design web UI and perform this read-only inspection.","the corresponding Projects, Design systems, Templates, or organization source of truth")
 for stem in PREVIEW_APPLY:
  if c==stem+".preview":
   values={k:x for k,x in v.items() if x not in (None,False,[],"")}; d=effect_digest(c,values)
   return envelope(c,data={"effect_digest":d,"values":{k:x for k,x in values.items() if not SECRET_KEYS.search(k)},"apply_command":stem+".apply","execute":False})
  if c==stem+".apply":
   expected=effect_digest(stem+".preview",v)
   if not a.approve or not a.effect_digest or a.effect_digest!=expected:return fail(c,"APPROVAL_REQUIRED","Run the matching preview, pass its exact --effect-digest, and set --approve.")
   return handoff(c,{k:x for k,x in v.items() if x not in (None,False,[],"") and k not in {"command","approve","effect_digest"}},"Perform only the exactly previewed effect in Claude Design or Claude Code.","ACL, comment, destination, git diff, design-system state, or organization settings")
 if c in HANDOFFS:
  rid=a.project_id or a.design_system_id or a.template_id
  if c not in {"projects.create","design-systems.create","templates.create"}:
   result=require_id(c,rid,"resource_id")
   if result is not None:return result
  destructive=c.endswith("delete")
  if destructive and (not a.approve or not a.exact_name):return fail(c,"APPROVAL_REQUIRED","Deletion requires --exact-name and --approve.")
  return handoff(c,{k:x for k,x in v.items() if x not in (None,False,[],"") and k not in {"command","approve"}},"Open the exact resource in Claude Design and perform this operation once"+(" after matching the displayed name exactly" if destructive else "")+".","resource detail/list readback, preserving ID and revision")
 return fail(c,"UNSUPPORTED","No official stable API or discovered Claude Design MCP schema supports deterministic provider execution for this command.")

if __name__=="__main__":sys.exit(main())
