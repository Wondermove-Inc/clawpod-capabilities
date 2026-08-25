#!/usr/bin/env python3
"""Deterministic guardrail CLI for Claude Design's currently human-operated surfaces."""
from __future__ import annotations
import argparse, hashlib, json, mimetypes, os, re, shutil, subprocess, sys, uuid, zipfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

VERSION="0.3.9"
DESIGN_URL="https://claude.ai/design"
LONG_CONTENTEDITABLE_CHARS=600
MCP_NAME="claude-design"
MCP_URL="https://api.anthropic.com/v1/design/mcp"
MCP_DEFECT="Claude Code 2.1.229 sends an OAuth redirect_uri that the provider rejects; transport Connected does not prove tool authorization."
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
LITERAL_UNICODE_ESCAPE_RE=re.compile(r"\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}")
MOJIBAKE_MARKERS=("\ufffd","Ã","Â","â€","ðŸ","ï¿½")

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

def editable_kind(tag_name,contenteditable,role):
 tag=(tag_name or "").lower()
 if tag in {"input","textarea"}:return "standard"
 if contenteditable or (role or "").lower()=="textbox":return "contenteditable"
 return "unsupported"

def contenteditable_injection(prompt):
 # OpenClaw evaluate passes the ref-resolved element as `el`. Embed the text as a
 # JSON string literal so quotes, newlines, and Unicode cannot alter the function.
 literal=json.dumps(prompt,ensure_ascii=True)
 return "(el) => { const text = "+literal+"; el.focus(); el.replaceChildren(document.createTextNode(text)); el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:text})); el.dispatchEvent(new Event('change',{bubbles:true})); return {text:el.innerText ?? el.textContent ?? '',length:(el.innerText ?? el.textContent ?? '').length}; }"

def browser_input_plan(prompt,ref,tag_name=None,contenteditable=False,role=None,evaluate_enabled=True):
 kind=editable_kind(tag_name,contenteditable,role)
 common={"editable_kind":kind,"expected_length":len(prompt),"expected_sha256":hashlib.sha256(prompt.encode()).hexdigest(),"verify":"read text/value with evaluate and require exact text, length, and SHA-256 match","stale_ref_recovery":["take a fresh snapshot of the same target","redetect the editable by role/name and editable semantics","retry the selected input action once with the new ref","verify exactly; never retry or submit on ambiguity"]}
 if kind=="standard":
  return {**common,"strategy":"fill","action":{"kind":"fill","fields":[{"ref":ref,"type":"text","value":prompt}]}}
 if kind=="contenteditable" and len(prompt)>LONG_CONTENTEDITABLE_CHARS:
  if not evaluate_enabled:return {**common,"strategy":"blocked","reason":"Long contenteditable input requires enabled browser evaluate or a separately supported paste action; type is not a safe long-input fallback."}
  return {**common,"strategy":"evaluate","action":{"kind":"evaluate","ref":ref,"fn":contenteditable_injection(prompt)}}
 if kind=="contenteditable":return {**common,"strategy":"type","action":{"kind":"type","ref":ref,"text":prompt},"constraint":f"type is allowed only at or below {LONG_CONTENTEDITABLE_CHARS} characters"}
 return {**common,"strategy":"blocked","reason":"Element is not a standard editable or contenteditable textbox; refresh the snapshot and redetect."}

def diagnose_browser_input(error_message,gateway_healthy=None):
 message=error_message or ""
 lower=message.lower()
 stale=bool(re.search(r"stale|element .*not found|not visible|unknown ref|snapshot",lower))
 timeout="timed out" in lower or "timeout" in lower
 if stale:return {"classification":"STALE_REF","next_action":"fresh snapshot, redetect editable, retry once, then exact verification","gateway_restart":False}
 if timeout:return {"classification":"BROWSER_ACTION_TIMEOUT","next_action":"inspect current field content and browser status; choose evaluate for long contenteditable input","gateway_restart":False,"gateway_status":gateway_healthy}
 if gateway_healthy is False:return {"classification":"BROWSER_CONTROL_UNAVAILABLE","next_action":"diagnose browser/Gateway health independently before any restart decision","gateway_restart":False}
 return {"classification":"BROWSER_INPUT_FAILED","next_action":"inspect current browser state and exact field content before retrying","gateway_restart":False}

def run_claude(args,timeout=5):
 exe=shutil.which("claude")
 if not exe:return {"available":False,"exit_code":None,"stdout":"","stderr":"claude executable not found"}
 env={k:v for k,v in os.environ.items() if k!="CLAUDE_CODE_OAUTH_TOKEN"}
 # setup-token is a contract, never silently remapped to another auth variable.
 try:
  p=subprocess.run([exe,*args],capture_output=True,text=True,timeout=timeout,env=env)
  text=lambda s: re.sub(r"(?i)(token|secret|password|authorization|cookie)\s*[:=]\s*\S+","[REDACTED]",s)[:12000]
  return {"available":True,"exit_code":p.returncode,"stdout":text(p.stdout.strip()),"stderr":text(p.stderr.strip())}
 except subprocess.TimeoutExpired:return {"available":True,"exit_code":None,"stdout":"","stderr":"bounded command timed out","timed_out":True}
 except OSError as e:return {"available":True,"exit_code":None,"stdout":"","stderr":str(e)[:500]}

def require_id(command,value,label):
 if not value or not ID_RE.fullmatch(value):return fail(command,"INVALID_INPUT",f"--{label.replace('_','-')} must be a non-empty safe identifier.")

def file_evidence(path_s):
 p=Path(path_s).expanduser()
 if not p.is_file():raise ValueError("output path is not a regular file")
 raw=p.read_bytes(); mime=mimetypes.guess_type(p.name)[0] or "application/octet-stream"
 info={"path":str(p.resolve()),"mime":mime,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
 if mime=="application/pdf":
  try:
   from pypdf import PdfReader
   info["page_count"]=len(PdfReader(str(p)).pages)
  except (ImportError,OSError,ValueError):
   info["page_count"]=len(re.findall(rb"/Type\s*/Page(?!s)\b",raw))
 if mime==FORMATS["pptx"]:
  try:
   with zipfile.ZipFile(p) as archive:
    info["page_count"]=len([name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml",name)])
  except (OSError,zipfile.BadZipFile):
   info["page_count"]=0
 return info

def positive_integer(value):
 return int(value) if value and value.isdigit() and int(value)>0 else None

def strict_bool(value):
 if value == "true": return True
 if value == "false": return False
 return None

def page_set(value,expected):
 tokens=[x.strip() for x in (value or "").split(",") if x.strip()]
 if not tokens or any(not x.isdigit() for x in tokens):return None
 pages={int(x) for x in tokens}
 return pages if pages==set(range(1,expected+1)) else None

def safe_text(value):
 if value is None: return None
 return re.sub(r"(?i)(token|secret|password|authorization|cookie)\s*[:=]\s*\S+","[REDACTED]",value)[:2000]

def route_identity(project_id,project_url,file_url,ui_filename,thumbnail_id):
 return {"project_id":project_id,"project_url":project_url,"file_url":file_url,"ui_filename":ui_filename,"thumbnail_id":thumbnail_id}

def reenter_plan(project_id,project_url,file_url,ui_filename,thumbnail_id,expected_pages,attempt):
 return {"execute":False,"providerExecution":False,"readOnly":True,"identity":route_identity(project_id,project_url,file_url,ui_filename,thumbnail_id),"expectedPages":expected_pages,"attempt":attempt,"maxAttempts":2,"steps":["read a fresh project list","locate the exact project ID and URL","select the exact generated-result thumbnail once","wait once for a bounded interval","observe active URL, exact UI filename, served canvas, and slide count"],"attemptRequirement":"Attempt 2 requires another fresh project-list read." if attempt==2 else "Attempt 1 starts from a fresh project-list read.","prohibited":["waiting on a stale URL","repeated refresh","prompt resubmission","duplicate prompt or project creation","Gateway restart"],"handoff":"Execute these Browser DOM steps externally, then pass observed evidence to projects.reenter.verify; this Harness does not click Browser or provider UI."}

def verify_route(a):
 healthy=strict_bool(a.browser_healthy); canvas=strict_bool(a.canvas_served); fresh=strict_bool(a.fresh_list_read)
 observed=positive_integer(a.observed_slides)
 evidence={"expected":route_identity(a.project_id,a.project_url,a.file_url,a.ui_filename,a.thumbnail_id),"observed":{"project_id":a.observed_project_id,"thumbnail_id":a.observed_thumbnail_id,"active_url":a.active_url,"ui_filename":a.observed_ui_filename,"slides":observed,"canvas_served":canvas,"browser_healthy":healthy,"fresh_list_read":fresh},"attempt":positive_integer(a.attempt)}
 if healthy is False:return "browser_failure",False,"Browser or CDP is unhealthy; this is never provider_failure.","Diagnose Browser/CDP without restarting the Gateway.",evidence
 required=[healthy,canvas,fresh,observed,a.observed_project_id,a.observed_thumbnail_id,a.active_url,a.observed_ui_filename]
 if any(x is None or x=="" for x in required):return "ambiguous",False,"Required route evidence is missing or invalid.","Collect fresh non-conflicting Browser evidence.",evidence
 exact=(a.observed_project_id==a.project_id and a.observed_thumbnail_id==a.thumbnail_id and a.active_url==a.file_url and a.observed_ui_filename==a.ui_filename)
 if healthy and exact and canvas and observed==positive_integer(a.expected_pages):return "recovered",False,"Exact route and slide count verified.","Continue from the last verification checkpoint into post-recovery QA and independent exports.",evidence
 if healthy and (not exact or not canvas):return "stale_route",True,"Healthy Browser is on the wrong or unserved file route.","Run the next bounded exact-thumbnail re-entry plan if available.",evidence
 return "ambiguous",False,"Route evidence conflicts with the expected slide count.","Reobserve the exact active file and canvas.",evidence

def diagnose_route(a):
 state,retry,reason,next_action,evidence=verify_route(a)
 if state=="browser_failure":return state,retry,reason,next_action,evidence
 exp_init=strict_bool(a.export_initiated); artifact=strict_bool(a.artifact_valid)
 if state=="recovered" and exp_init is True and artifact is False:return "export_failure",True,"Recovered route but the independently initiated export artifact is absent or invalid.","Diagnose the bounded native export from the same verified project state.",evidence
 if state=="recovered":return state,False,reason,next_action,evidence
 a1fresh=strict_bool(a.attempt1_fresh_list);a2fresh=strict_bool(a.attempt2_fresh_list)
 a1healthy=strict_bool(a.attempt1_browser_healthy);a2healthy=strict_bool(a.attempt2_browser_healthy)
 same=(a.attempt1_thumbnail_id and a.attempt1_thumbnail_id==a.thumbnail_id==a.attempt2_thumbnail_id)
 def provider404(x): return bool(x and re.search(r"(?i)(OmeletteService/GetFile|thumbnail|claudeusercontent).*404|404.*(OmeletteService/GetFile|thumbnail|claudeusercontent)",x))
 e1=provider404(a.attempt1_error);e2=provider404(a.attempt2_error)
 evidence["attempts"]=[{"attempt":1,"fresh_list_read":a1fresh,"browser_healthy":a1healthy,"thumbnail_id":a.attempt1_thumbnail_id,"error":safe_text(a.attempt1_error)},{"attempt":2,"fresh_list_read":a2fresh,"browser_healthy":a2healthy,"thumbnail_id":a.attempt2_thumbnail_id,"error":safe_text(a.attempt2_error)}]
 if False in (a1healthy,a2healthy):return "browser_failure",False,"Browser or CDP failed during bounded re-entry; this is never provider_failure.","Diagnose Browser/CDP health separately.",evidence
 if all(x is True for x in (a1fresh,a2fresh,a1healthy,a2healthy)) and same and e1 and e2:return "provider_failure",False,"Two bounded exact generated-result thumbnail re-entry attempts independently failed with provider file-serving 404 evidence.","Stop retries and preserve the original project and artifacts.",evidence
 return state if state=="stale_route" else "ambiguous",state=="stale_route","Provider failure is not proven until both bounded same-thumbnail attempts satisfy every gate.","Collect missing evidence or perform the remaining bounded exact-thumbnail attempt.",evidence

def decoded_design_filename(file_url):
 try:
  values=parse_qs(urlparse(file_url).query,keep_blank_values=True,strict_parsing=False).get("file",[])
 except ValueError:
  return None
 if len(values)!=1:return None
 # parse_qs performs one URL decode. Decode repeatedly boundedly because observed
 # Design URLs may encode the filename value itself before encoding the query.
 value=values[0]
 for _ in range(2):
  decoded=unquote(value)
  if decoded==value:break
  value=decoded
 return value

def filename_problem(filename):
 if not filename:return "filename is empty"
 if LITERAL_UNICODE_ESCAPE_RE.search(filename):return "filename contains a literal Unicode escape placeholder"
 if any(marker in filename for marker in MOJIBAKE_MARKERS):return "filename contains mojibake or replacement characters"
 if "/" in filename or "\\" in filename:return "filename must be the exact basename shown in the UI"
 if not filename.endswith(".dc.html"):return "filename must end exactly with .dc.html"

def export_identity(file_url,ui_filename):
 decoded=decoded_design_filename(file_url)
 data={"file_url":file_url,"decoded_file_parameter":decoded,"ui_filename":ui_filename,"exact_filename_match":decoded==ui_filename if decoded is not None else False}
 problem=filename_problem(decoded) if decoded is not None else "URL must contain exactly one non-empty file parameter"
 if not problem:problem=filename_problem(ui_filename)
 if not problem and decoded!=ui_filename:problem="URL-decoded file parameter does not exactly equal the active UI filename"
 return data,problem

def export_plan(file_url,ui_filename,expected_pages,observed_slides,preview_pages=None):
 identity,problem=export_identity(file_url,ui_filename)
 data={**identity,"expected_pages":expected_pages,"observed_slide_count":observed_slides,"observed_slide_count_matches":observed_slides==expected_pages,"read_only":True,"provider_execution":False}
 if problem:return data,"ACTIVE_FILE_MISMATCH",problem
 if observed_slides!=expected_pages:return data,"SLIDE_COUNT_MISMATCH",f"Observed {observed_slides} slides; expected {expected_pages}. Do not Share or export."
 if preview_pages is not None:
  data["print_preview_pages"]=preview_pages;data["print_preview_page_count_matches"]=preview_pages==expected_pages
  if preview_pages==1 and expected_pages>1:return data,"IFRAME_PRINT_REJECTED","A one-page iframe/browser print is not a full-deck export. Return to Claude Design and use Share > PDF."
  if preview_pages!=expected_pages:return data,"PRINT_PAGE_COUNT_MISMATCH",f"Print preview shows {preview_pages} pages; expected {expected_pages}. Do not save."
 data["workflow"]=["open the exact selected .dc.html active file","confirm observed slide count equals expected pages","Share","PDF","Print or Save as PDF","verify the local file exists","verify PDF page count equals expected pages"]
 data["environment_workflow"]={"chrome":"In print preview, traverse the preview shadow DOM to activate Save when ordinary browser refs cannot reach it.","gtk":"In the native Save File dialog, enter the exact output path/name and activate Save; then verify the file on disk."}
 return data,None,None

def handoff(command,values,action,source):
 return fail(command,"HUMAN_VERIFICATION",action+" Then reconcile "+source+" before retrying or claiming success.",False,{"url":DESIGN_URL,"values":values,"reconciliation_source":source})

def parser():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("command")
 for name in ["project-id","design-system-id","template-id","repository-path","direction","effect-digest","prompt","template","model","access","role","principal","format","output-path","exact-name","destination","name","query","owner","sort","view","target","text","patch","sources","member","organization","scope","mcp-name","mcp-command","mcp-url","provenance","ref","tag-name","observed-text","error-message","gateway-status","file-url","ui-filename","provider-error","project-url","thumbnail-id","attempt","observed-project-id","observed-thumbnail-id","active-url","observed-ui-filename","canvas-served","browser-healthy","fresh-list-read","attempt1-fresh-list","attempt2-fresh-list","attempt1-browser-healthy","attempt2-browser-healthy","attempt1-thumbnail-id","attempt2-thumbnail-id","attempt1-error","attempt2-error","export-initiated","artifact-valid","review-pass-1","review-pass-2","render-pages","reflow-pages"]:p.add_argument("--"+name)
 p.add_argument("--expected-pages");p.add_argument("--observed-slides");p.add_argument("--preview-pages");p.add_argument("--qa-pages")
 p.add_argument("--starred",action="store_true");p.add_argument("--start-from-code",action="store_true");p.add_argument("--approve",action="store_true");p.add_argument("--contenteditable",action="store_true");p.add_argument("--evaluate-disabled",action="store_true")
 p.add_argument("--attachment",action="append",default=[]);p.add_argument("--option",action="append",default=[])
 return p

def main(argv=None):
 a=parser().parse_args(argv); c=a.command; v=vars(a)
 if c=="system.version":return envelope(c,data={"name":"claude-design","title":"Claude Design","version":VERSION,"provider_execution":"logged_in_browser","mcp_mode":"optional_acceleration"})
 if c=="onboarding.plan":return envelope(c,data={"state":"browser_ready_when_authenticated","default_execution":"logged-in browser at "+DESIGN_URL,"approval_scope":"Browser authentication approval covers only bounded sign-in readiness; mutations and external effects remain separately approved.","agent_steps":["open Claude Design in the desktop/browser capability","reuse the logged-in browser session","verify the Design UI is readable","use browser workflows for projects, design systems, templates, administration, and exports"],"human_only":["sign-in when browser authentication is absent","MFA","provider consent"],"never_delegate_to_user":["CLI commands","MCP endpoint registration","configuration editing","schema inspection","routine retries"],"mcp":{"required":False,"use_only_after_real_tool_smoke":True,"readiness_independent":True},"revocation":["Claude account settings","browser session sign-out"],"no_secret_persistence":True})
 if c=="onboarding.preflight":return envelope(c,data={"design_url":DESIGN_URL,"default_execution":"browser","browser_check":"Open with desktop/browser and verify authenticated Design UI; the pure Harness does not inspect cookies or browser state.","ready_for_browser_check":True,"mcp_required":False})
 if c=="onboarding.status":return envelope(c,data={"installed":True,"capability_readiness":"READY_PENDING_BROWSER_AUTH_CHECK","default_execution":"browser","design_url":DESIGN_URL,"browser_authenticated":"not_safely_inferred","mcp_required":False},warnings=["Verify the logged-in Claude Design UI with the desktop/browser capability before provider work."])
 if c=="auth.contract":return envelope(c,data={"default_auth":"existing claude.ai browser session","login_handoff":"Agent opens Claude Design; user performs only sign-in, MFA, or provider consent when the browser is not authenticated.","credential_files":False,"mcp_oauth_required":False,"mcp_registration_required":False,"browser_readiness_check":"authenticated Design UI is readable"})
 if c=="auth.status":return envelope(c,data={"browser_authentication":"not_safely_inferred","verification":"desktop/browser source-of-truth check required","claude_cli_optional":bool(shutil.which("claude")),"mcp_required":False})
 if c=="browser.input.plan":
  if a.prompt is None or not a.ref:return fail(c,"INVALID_INPUT","--prompt and --ref are required.")
  plan=browser_input_plan(a.prompt,a.ref,a.tag_name,a.contenteditable,a.role,not a.evaluate_disabled)
  if plan["strategy"]=="blocked":return fail(c,"UNSUPPORTED",plan["reason"],False,plan)
  return envelope(c,data=plan)
 if c=="browser.input.verify":
  if a.prompt is None or a.observed_text is None:return fail(c,"INVALID_INPUT","--prompt and --observed-text are required for exact verification.")
  expected_hash=hashlib.sha256(a.prompt.encode()).hexdigest(); observed_hash=hashlib.sha256(a.observed_text.encode()).hexdigest()
  data={"exact_match":a.prompt==a.observed_text,"expected_length":len(a.prompt),"observed_length":len(a.observed_text),"expected_sha256":expected_hash,"observed_sha256":observed_hash}
  if not data["exact_match"]:return fail(c,"VERIFICATION_FAILED","Inserted browser content does not exactly match the requested content and must not be submitted.",False,data)
  return envelope(c,data=data,evidence=[{"kind":"browser-input-verification","ref":observed_hash,"metadata":{"length":len(a.observed_text),"exact_match":True}}])
 if c=="browser.input.diagnose":
  if not a.error_message:return fail(c,"INVALID_INPUT","--error-message is required.")
  if a.gateway_status not in {None,"healthy","unhealthy","unknown"}:return fail(c,"INVALID_INPUT","--gateway-status must be healthy, unhealthy, or unknown.")
  status={"healthy":True,"unhealthy":False}.get(a.gateway_status)
  return envelope(c,data=diagnose_browser_input(a.error_message,status),warnings=["A browser type timeout alone is not evidence that the Gateway must be restarted."])
 if c=="auth.setup-token.plan":return envelope(c,data={"deprecated_for_default_path":True,"execute":False,"reason":"Browser-first readiness does not require a Claude Code setup token or MCP OAuth."},warnings=["Use only for a separately approved Claude Code workflow, never for default Claude Design onboarding."])
 if c=="code.login.handoff":return handoff(c,{},"Open Claude Design in the browser. If authentication is absent, complete only provider sign-in, MFA, or consent, then return control.","authenticated Claude Design UI")
 if c=="mcp.inspect":
  get=run_claude(["mcp","get",MCP_NAME]); listed=run_claude(["mcp","list"])
  return envelope(c,data={"optional":True,"required_for_readiness":False,"get":get,"list":listed,"official_name":MCP_NAME,"official_url":MCP_URL,"tool_smoke_succeeded":False,"authorized":False,"known_defect":MCP_DEFECT},warnings=["A Connected transport is not proof of authorization. Do not use MCP until a real read-only tool call succeeds."])
 if c=="mcp.validate":return fail(c,"BACKEND_UNAVAILABLE","Optional MCP acceleration is disabled until a real read-only Claude Design tool smoke succeeds. Browser capability readiness is unaffected.",True,{"required_for_readiness":False,"known_defect":MCP_DEFECT,"success_criterion":"real tool result, not transport Connected"})
 if c in {"mcp.install-plan","mcp.remove-plan"}:
  verb="add" if c.endswith("install-plan") else "remove"
  if verb=="add" and not (a.mcp_command or a.mcp_url):return fail(c,"INVALID_INPUT","Optional MCP setup requires a separately observed provider-supported transport; default onboarding never installs it.")
  if verb=="remove":
   result=require_id(c,a.mcp_name,"mcp_name")
   if result is not None:return result
  argv=["claude","mcp",verb]+(([a.mcp_name] if a.mcp_name else []))
  return envelope(c,data={"argv":argv,"execute":False,"optional":True,"requires_separate_approval":True,"readiness_impact":"none","reconcile":"real tool smoke for install; list/get for removal"})
 if c=="projects.reenter.plan":
  expected=positive_integer(a.expected_pages);attempt=positive_integer(a.attempt)
  if not all([a.project_id,a.project_url,a.file_url,a.ui_filename,a.thumbnail_id]) or expected is None or attempt not in {1,2}:return fail(c,"INVALID_INPUT","Exact project/file/thumbnail identity, positive --expected-pages, and --attempt 1 or 2 are required.",False)
  return envelope(c,data=reenter_plan(a.project_id,a.project_url,a.file_url,a.ui_filename,a.thumbnail_id,expected,attempt))
 if c in {"projects.reenter.verify","projects.file_route.diagnose"}:
  expected=positive_integer(a.expected_pages);attempt=positive_integer(a.attempt)
  if not all([a.project_id,a.project_url,a.file_url,a.ui_filename,a.thumbnail_id]) or expected is None or attempt not in {1,2}:return fail(c,"INVALID_INPUT","Exact expected identity, positive --expected-pages, and --attempt 1 or 2 are required.",False)
  result=diagnose_route(a) if c.endswith("diagnose") else verify_route(a)
  state,retry,reason,next_action,evidence=result
  return envelope(c,data={"state":state,"retryAllowed":retry,"stopReason":reason,"nextAction":next_action,"evidence":evidence,"execute":False,"providerExecution":False},retry_safe=retry,evidence=[{"kind":"file-route-diagnosis","ref":hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest(),"metadata":{"state":state,"attempt":attempt}}])
 if c in {"projects.export.plan","projects.export.diagnose"}:
  expected=positive_integer(a.expected_pages);observed=positive_integer(a.observed_slides);preview=positive_integer(a.preview_pages) if a.preview_pages is not None else None
  if not a.file_url or not a.ui_filename or expected is None or observed is None:return fail(c,"INVALID_INPUT","--file-url, --ui-filename, --expected-pages, and --observed-slides are required; page counts must be positive integers.")
  if a.preview_pages is not None and preview is None:return fail(c,"INVALID_INPUT","--preview-pages must be a positive integer when supplied.")
  data,code,message=export_plan(a.file_url,a.ui_filename,expected,observed,preview)
  if code:return fail(c,code,message,False,{**data,"provider_error":a.provider_error} if a.provider_error else data)
  if c=="projects.export.diagnose":
   data["classification"]="PROVIDER_BLOCKER" if a.provider_error else "READY"
   data["next_action"]="Resolve the provider blocker only after active-file identity and slide/page counts pass." if a.provider_error else "Continue with the prescribed native export workflow."
   if a.provider_error:data["provider_error"]=a.provider_error
  return envelope(c,data=data)
 if c=="projects.export.verify":
  if not a.output_path:return fail(c,"INVALID_INPUT","--output-path is required.")
  try: info=file_evidence(a.output_path)
  except (OSError,ValueError) as e:return fail(c,"NOT_FOUND",str(e))
  if a.format:
   if a.format not in FORMATS:return fail(c,"INVALID_INPUT","--format must be html, pptx, or pdf.")
   expected=FORMATS[a.format]; info["expected_mime"]=expected; info["mime_matches"]=info["mime"]==expected
  if not a.project_id or not a.provenance:return fail(c,"INVALID_INPUT","Artifact metadata requires --project-id and --provenance (native-claude-design or fallback-rendering).")
  if a.provenance not in {"native-claude-design","fallback-rendering"}:return fail(c,"INVALID_INPUT","--provenance must be native-claude-design or fallback-rendering.")
  if a.format in {"pdf","pptx"}:
   expected_pages=positive_integer(a.expected_pages)
   if expected_pages is None:return fail(c,"INVALID_INPUT","PPTX/PDF verification requires --expected-pages as a positive integer before success.")
   info["expected_pages"]=expected_pages; info["page_count_matches"]=info.get("page_count")==expected_pages
   if not info["page_count_matches"]:return fail(c,"VERIFICATION_FAILED",f"Artifact has {info.get('page_count',0)} pages/slides; expected {expected_pages}.",False,info)
   checks={"review_pass_1":a.review_pass_1,"review_pass_2":a.review_pass_2,"render_pages":a.render_pages,"reflow_pages":a.reflow_pages}
   if any(value is not None for value in checks.values()):
    incomplete=[name for name,value in checks.items() if page_set(value,expected_pages) is None]
    if incomplete:return fail(c,"VERIFICATION_FAILED","Two full slide reviews, independent render pages, and page-by-page reflow comparison must each cover the complete deck.",False,{**info,"incomplete_post_recovery_checks":incomplete})
    info["post_recovery_qa_complete"]=True;info.update({name:list(range(1,expected_pages+1)) for name in checks})
  if a.format=="pdf":
   tokens=[x.strip() for x in (a.qa_pages or "").split(",") if x.strip()]
   if not tokens or any(not x.isdigit() for x in tokens):return fail(c,"INVALID_INPUT","--qa-pages must be a comma-separated list of positive page numbers.")
   reviewed={int(x) for x in tokens}
   invalid=sorted(x for x in reviewed if x < 1 or x > expected_pages)
   if invalid:return fail(c,"INVALID_INPUT","--qa-pages contains pages outside the expected range.",False,{**info,"invalid_qa_pages":invalid})
   missing=sorted(set(range(1,expected_pages+1))-reviewed)
   if missing:return fail(c,"VERIFICATION_FAILED","Page-by-page visual QA is incomplete.",False,{**info,"qa_pages":sorted(reviewed),"missing_qa_pages":missing})
   info["qa_pages"]=sorted(reviewed);info["visual_qa_complete"]=True
  info["project_id"]=a.project_id;info["provenance"]=a.provenance
  return envelope(c,data=info,evidence=[{"kind":"artifact","ref":info["sha256"],"metadata":{"project_id":a.project_id,"provenance":a.provenance,"page_count":info.get("page_count"),"visual_qa_complete":info.get("visual_qa_complete",False)}}])
 if c=="projects.export":
  result=require_id(c,a.project_id,"project_id")
  if result is not None:return result
  if a.format not in FORMATS:return fail(c,"INVALID_INPUT","--format must be html, pptx, or pdf.")
  if not a.output_path:return fail(c,"INVALID_INPUT","--output-path is required.")
  return handoff(c,{"project_id":a.project_id,"format":a.format,"output_path":a.output_path},"First run projects.export.plan for the exact selected .dc.html file. For PDF use Share > PDF > Print or Save as PDF; verify print preview shows the expected full-deck page count before saving. A one-page iframe/browser print is not a full-deck export. For any fallback, label provenance as fallback-rendering rather than native Claude Design export.","actual local regular file MIME, bytes, SHA-256, and PDF page count via projects.export.verify")
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
