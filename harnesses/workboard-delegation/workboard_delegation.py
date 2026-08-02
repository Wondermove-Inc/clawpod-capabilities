#!/usr/bin/env python3
"""Pure deterministic planner and validator for Workboard delegation."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from typing import Any
VERSION="0.3.2"; SCHEMA=1
MAX_SNAPSHOT_BYTES=65536; MAX_PLAN_BYTES=65536; MAX_TEXT=12000; MAX_LABELS=32
GATEWAY_STDOUT_PREVIEW_BYTES=2000; MAX_STDOUT_BYTES=1900
SENSITIVE=re.compile(r"(?i)(token|secret|password|authorization|api[-_]?key)")
SAFE_ERROR_MESSAGES={
 "output_too_large":f"Output exceeds the {MAX_STDOUT_BYTES}-byte stdout budget; shorten delegation text and re-plan",
 "internal_error":"Unexpected harness failure",
}

class HarnessError(Exception):
 def __init__(self,code:str,message:str,details:Any=None): self.code,self.message,self.details=code,message,details; super().__init__(message)
def stable(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return hashlib.sha256(stable(v).encode()).hexdigest()
def redact(v):
 if isinstance(v,dict): return {k:("[REDACTED]" if SENSITIVE.search(str(k)) else redact(x)) for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 if isinstance(v,str):
  v=re.sub(r"(?i)(bearer\s+)\S+",r"\1[REDACTED]",v); v=re.sub(r"(?i)((?:token|secret|password|api[-_]?key)\s*[=:]\s*)\S+",r"\1[REDACTED]",v)
 return v
def required(v,name,limit=MAX_TEXT):
 if not isinstance(v,str) or not v.strip() or len(v.encode())>limit: raise HarnessError("invalid_input",f"{name} is required and must be at most {limit} bytes")
 return v.strip()
def parse_json_arg(raw,name,limit):
 if not isinstance(raw,str): raise HarnessError("invalid_input",f"{name} must be a JSON string")
 if len(raw.encode())>limit: raise HarnessError("input_too_large",f"{name} exceeds {limit} bytes")
 try:v=json.loads(raw)
 except (ValueError,TypeError) as e: raise HarnessError("malformed_json",f"{name} is not valid JSON") from e
 if not isinstance(v,dict): raise HarnessError("invalid_snapshot",f"{name} must decode to an object")
 return v
def labels(raw):
 if not raw:data=[]
 else:
  try:data=json.loads(raw)
  except ValueError as e: raise HarnessError("malformed_json","labels must be a JSON array") from e
 if not isinstance(data,list) or len(data)>MAX_LABELS or any(not isinstance(x,str) or not x or len(x)>64 for x in data): raise HarnessError("invalid_input","labels must contain at most 32 non-empty strings of at most 64 characters")
 return sorted(set(data+["delegated-execution","workboard-delegation"]))
def metadata(c): return c.get("metadata") if isinstance(c.get("metadata"),dict) else {}
def automation(c): return metadata(c).get("automation") if isinstance(metadata(c).get("automation"),dict) else {}
def claim(c): return metadata(c).get("claim") if isinstance(metadata(c).get("claim"),dict) else {}
def comments(c):
 x=c.get("comments")
 if isinstance(x,list):return x
 x=metadata(c).get("comments"); return x if isinstance(x,list) else []
def card_id(c): return str(c.get("id") or c.get("cardId") or "")
def parent_ids(c):
 p=c.get("parents") if c.get("parents") is not None else c.get("parentIds")
 return p if isinstance(p,list) else []

def make_plan(a):
 intent={"schemaVersion":1,"operation":"workboard-delegation","leaderId":required(a.leader_id,"leaderId",128),"expectedLeaderOwnerId":a.expected_leader_owner_id or None,"title":required(a.title,"title",300),"practitionerAgentId":required(a.agent_id,"agentId",128),"scope":required(a.scope,"scope"),"nonGoals":a.non_goals.strip() if a.non_goals else None,"doneWhen":required(a.done_when,"doneWhen"),"evidenceRequired":required(a.evidence_required,"evidenceRequired"),"reportBackTarget":required(a.report_back_target,"reportBackTarget",300),"tenant":a.tenant or "default","boardId":a.board_id or "default","labels":labels(a.labels),"dependencyMode":"related-card-not-parent-child"}
 key="workboard-delegation:"+sha(intent)[:32]
 notes=["[workboard-delegation]",f"leader_sot_card_id: {intent['leaderId']}",f"delegated_by_owner_id: {intent['expectedLeaderOwnerId'] or 'unclaimed'}",f"practitioner_agent_id: {intent['practitionerAgentId']}",f"idempotency_key: {key}",f"scope: {intent['scope']}"]
 if intent["nonGoals"]:notes.append(f"non_goals: {intent['nonGoals']}")
 notes += [f"done_when: {intent['doneWhen']}",f"evidence_required: {intent['evidenceRequired']}",f"report_back_target: {intent['reportBackTarget']}","dependency_mode: related-card-not-parent-child"]
 marker=f"[workboard-delegation:{key.split(':',1)[1]}]"; create={"title":intent["title"],"notes":"\n".join(notes),"agentId":intent["practitionerAgentId"],"tenant":intent["tenant"],"boardId":intent["boardId"],"labels":intent["labels"],"createdByCardId":intent["leaderId"],"idempotencyKey":key}
 core={"leaderId":intent["leaderId"],"expectedLeaderOwnerId":intent["expectedLeaderOwnerId"],"createFields":create,"commentMarker":marker,"commentTemplate":marker+" execution card: {executionCardId}"}
 result={**core,"planHash":sha(core)}
 return result
def validate_plan(raw,expected_hash):
 p=parse_json_arg(raw,"planJson",MAX_PLAN_BYTES); supplied=p.get("planHash"); core={k:v for k,v in p.items() if k!="planHash"}; actual=sha(core)
 if supplied!=actual: raise HarnessError("plan_integrity_mismatch","planJson planHash does not match its contents")
 if expected_hash!=actual: raise HarnessError("plan_hash_mismatch","planHash does not match approved plan")
 required_keys={"leaderId","expectedLeaderOwnerId","createFields","commentMarker","commentTemplate","planHash"}
 if not required_keys.issubset(p): raise HarnessError("invalid_plan","planJson lacks required fields")
 return p
def validate_leader_snapshot(p,c,expected_owner):
 if card_id(c)!=p["leaderId"]: raise HarnessError("leader_id_mismatch","Leader snapshot id does not match plan")
 if parent_ids(c): raise HarnessError("dependency_mode_rejected","Leader must not use dependency mode")
 planned=p.get("expectedLeaderOwnerId")
 if (expected_owner or None)!=planned: raise HarnessError("expected_owner_mismatch","Expected owner argument does not match approved plan")
 owner=claim(c).get("ownerId")
 if owner and not expected_owner: raise HarnessError("expected_owner_required","Claimed leader requires expected owner")
 if owner and owner!=expected_owner: raise HarnessError("foreign_claim","Leader claim owner does not match expected owner")
 if not owner and expected_owner: raise HarnessError("owner_mismatch","Leader is unclaimed but expected owner was supplied")
 return {"leaderId":card_id(c),"claimOwnerId":owner or None,"valid":True}
def auto_matches(c,p):
 a=automation(c); f=p["createFields"]
 return a.get("createdByCardId")==f["createdByCardId"] and a.get("idempotencyKey")==f["idempotencyKey"] and a.get("tenant")==f["tenant"] and a.get("boardId")==f["boardId"]
def execution_matches(c,p):
 f=p["createFields"]
 return bool(card_id(c)) and auto_matches(c,p) and not parent_ids(c) and c.get("notes")==f["notes"] and c.get("title")==f["title"] and c.get("agentId")==f["agentId"]
def matching_comments(leader,p,execution_id):
 marker=p["commentMarker"]
 return [x for x in comments(leader) if marker in str(x.get("body",x)) and execution_id in str(x.get("body",x))]
def validate_result(p,leader,execution,expected_owner):
 validate_leader_snapshot(p,leader,expected_owner)
 if not execution_matches(execution,p): raise HarnessError("execution_mismatch","Execution snapshot does not match exact plan fields and automation metadata")
 eid=card_id(execution); found=matching_comments(leader,p,eid)
 if len(found)!=1: raise HarnessError("comment_missing" if not found else "duplicate_comment","Leader must contain exactly one matching cross-reference comment")
 return {"valid":True,"leaderId":card_id(leader),"executionCardId":eid,"commentCount":1,"verifiedFields":["automation","notes","title","agentId","noParents","comment"]}
def reconcile_actions(p,leader,execution,expected_owner):
 validate_leader_snapshot(p,leader,expected_owner); actions=[]
 if execution is None:
  actions.append({"action":"create","fields":p["createFields"],"reason":"execution snapshot absent","idempotencyKey":p["createFields"]["idempotencyKey"]}); return actions
 if not execution_matches(execution,p): raise HarnessError("execution_mismatch","Existing execution snapshot conflicts with exact plan; refuse reconciliation")
 eid=card_id(execution); found=matching_comments(leader,p,eid)
 if not found: actions.append({"action":"comment","cardId":p["leaderId"],"body":p["commentTemplate"].replace("{executionCardId}",eid),"reason":"cross-reference missing"})
 elif len(found)>1: raise HarnessError("duplicate_comment","Multiple matching cross-reference comments require human review")
 return actions

def add_plan_fields(q):
 q.add_argument("--leader-id",required=True); q.add_argument("--expected-leader-owner-id");q.add_argument("--title",required=True);q.add_argument("--agent-id",required=True);q.add_argument("--scope",required=True);q.add_argument("--non-goals");q.add_argument("--done-when",required=True);q.add_argument("--evidence-required",required=True);q.add_argument("--report-back-target",required=True);q.add_argument("--tenant");q.add_argument("--board-id");q.add_argument("--labels")
def add_validation_fields(q,execution_required=False):
 q.add_argument("--plan-json",required=True);q.add_argument("--plan-hash",required=True);q.add_argument("--leader-snapshot",required=True);q.add_argument("--expected-leader-owner-id")
 q.add_argument("--execution-snapshot",required=execution_required)
def parser():
 p=argparse.ArgumentParser(prog="workboard-delegation");sub=p.add_subparsers(dest="command",required=True);sub.add_parser("status");q=sub.add_parser("plan");add_plan_fields(q);q=sub.add_parser("validate-leader");add_validation_fields(q);q=sub.add_parser("validate-result");add_validation_fields(q,True);q=sub.add_parser("reconcile-plan");add_validation_fields(q);return p
def envelope(ok,command,data=None,error=None): return {"ok":ok,"schemaVersion":SCHEMA,"command":command,"data":data,"error":error,"performed":False,"effects":[]}
def output_line(value): return stable(value)+"\n"
def bounded_success(command,data):
 value=envelope(True,command,data=data)
 if len(output_line(value).encode("utf-8"))>MAX_STDOUT_BYTES:
  raise HarnessError("output_too_large",f"Output exceeds the {MAX_STDOUT_BYTES}-byte stdout budget; shorten delegation text and re-plan")
 return output_line(value)
def error_value(command,code,message):
 # Error output is deliberately fixed-shape and never includes caller input or exception text.
 return envelope(False,command,error={"code":code,"message":message,"details":None,"performed":False,"retrySafe":False,"verification":"failed"})
def write_error(command,code,message):
 # Only registered messages cross stdout, so exceptions cannot reflect caller input.
 safe_message=SAFE_ERROR_MESSAGES.get(code,"Harness request failed")
 line=output_line(error_value(command,code,safe_message))
 if len(line.encode("utf-8"))>MAX_STDOUT_BYTES: line=output_line(error_value("unknown","internal_error","Harness failure"))
 sys.stdout.write(line)
def main(argv=None):
 command="unknown"
 try:
  a=parser().parse_args(argv);command=a.command
  if command=="status":data={"name":"workboard-delegation","title":"Workboard Delegation","version":VERSION,"pure":True,"gatewayCalls":False,"mutates":False,"maxSnapshotBytes":MAX_SNAPSHOT_BYTES,"maxStdoutBytes":MAX_STDOUT_BYTES,"gatewayStdoutPreviewBytes":GATEWAY_STDOUT_PREVIEW_BYTES}
  elif command=="plan":data={"preview":make_plan(a)}
  else:
   p=validate_plan(a.plan_json,a.plan_hash);leader=parse_json_arg(a.leader_snapshot,"leaderSnapshot",MAX_SNAPSHOT_BYTES)
   if command=="validate-leader":data=validate_leader_snapshot(p,leader,a.expected_leader_owner_id)
   else:
    execution=parse_json_arg(a.execution_snapshot,"executionSnapshot",MAX_SNAPSHOT_BYTES) if a.execution_snapshot else None
    data=validate_result(p,leader,execution,a.expected_leader_owner_id) if command=="validate-result" else {"planHash":p["planHash"],"actions":reconcile_actions(p,leader,execution,a.expected_leader_owner_id),"mutates":False}
  sys.stdout.write(bounded_success(command,data));return 0
 except HarnessError as e:
  write_error(command,e.code,e.message);return 2
 except SystemExit:raise
 except Exception:
  write_error(command,"internal_error","Unexpected harness failure");return 3
if __name__=="__main__":raise SystemExit(main())
