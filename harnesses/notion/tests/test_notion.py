import base64, hashlib, hmac, json, os, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import importlib.util
P=Path(__file__).parents[1]/"notion.py"
spec=importlib.util.spec_from_file_location("notion",P);n=importlib.util.module_from_spec(spec);sys.modules["notion"]=n;spec.loader.exec_module(n)

def run(*args,env=None):
 e={**os.environ,**(env or {})};p=subprocess.run([sys.executable,str(P),*args],text=True,capture_output=True,env=e);return p.returncode,json.loads(p.stdout),p.stderr

def test_resolve_and_invalid():
 rc,o,_=run("resolve.url","--url","https://notion.so/Page-123456781234123412341234567890ab?pvs=4");assert rc==0 and o["data"]["id"]=="12345678-1234-1234-1234-1234567890ab"
 rc,o,_=run("resolve.id","--id","bad");assert rc==2 and o["error"]["category"]=="validation"
def test_onboarding_disconnected():
 rc,o,_=run("auth.onboarding.plan");assert rc==0 and not o["data"]["connected"] and "internal" in o["data"]["modes"]
def test_redaction():
 x=n.redact({"Authorization":"Bearer fake_secret_value","url":"https://x.amazonaws.com/a?X-Amz-Signature=fake"});assert x["Authorization"]=="[REDACTED]" and "fake" not in json.dumps(x)
def test_markdown_choice():
 _,o,_=run("markdown.validate","--markdown","hello");assert o["data"]["recommendation"]=="markdown"
 _,o,_=run("markdown.validate","--markdown","<unknown block_id=x>");assert o["data"]["recommendation"]=="blocks"
def test_webhook_signature():
 raw=b'{"id":"e1"}';secret="fake-webhook-test-key";sig=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest();_,o,_=run("webhook.signature.verify","--raw-body-b64",base64.b64encode(raw).decode(),"--signature",sig,env={"NOTION_WEBHOOK_SECRET":secret});assert o["data"]["valid"]
 _,o,_=run("webhook.signature.verify","--raw-body-b64",base64.b64encode(raw+b"x").decode(),"--signature",sig,env={"NOTION_WEBHOOK_SECRET":secret});assert not o["data"]["valid"]
def test_preview_and_stale_hash():
 rid="123456781234123412341234567890ab";_,o,_=run("page.properties.update","--id",rid,"--body",'{"properties":{}}',"--preview");h=o["data"]["preview"]["intent_hash"]
 rc,o,_=run("page.properties.update","--id",rid,"--body",'{"properties":{"x":1}}',"--confirm",h,env={"NOTION_TOKEN":"fake-token"});assert rc==2 and "exact intent_hash" in o["error"]["message"]

class H(BaseHTTPRequestHandler):
 counts={}
 def log_message(self,*a):pass
 def out(self,status,obj,headers=None):
  b=json.dumps(obj).encode();self.send_response(status);[self.send_header(k,v) for k,v in (headers or {}).items()];self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  H.counts[self.path]=H.counts.get(self.path,0)+1
  if self.path.startswith("/v1/pages/"):self.out(200,{"object":"page","id":self.path.split("/")[-1],"last_edited_time":"t"},{"x-request-id":"nr"})
  elif self.path.startswith("/v1/users"):self.out(403,{"code":"restricted_resource","message":"missing capability"})
  else:self.out(404,{"code":"object_not_found","message":"not shared"})
 def do_POST(self):
  self.rfile.read(int(self.headers.get("Content-Length","0")))
  H.counts[self.path]=H.counts.get(self.path,0)+1
  if self.path.startswith("/v1/search"):
   if H.counts[self.path]==1:self.out(429,{"code":"rate_limited","message":"slow"},{"Retry-After":"0"})
   else:self.out(200,{"results":[{"id":"1"}],"has_more":False,"next_cursor":None})
  elif self.path=="/v1/pages":self.out(200,{"id":"12345678-1234-1234-1234-1234567890ab"})
 def do_PATCH(self):
  self.rfile.read(int(self.headers.get("Content-Length","0")))
  self.out(500,{"code":"internal_server_error","message":"uncertain"})

def server():
 s=HTTPServer(("127.0.0.1",0),H);threading.Thread(target=s.serve_forever,daemon=True).start();return s

def test_retry_permission_not_found_and_pagination():
 s=server();base=f"http://127.0.0.1:{s.server_port}/v1";env={"NOTION_TOKEN":"fake-token","NOTION_API_BASE":base};H.counts={}
 rc,o,_=run("search.query","--all-pages","--max-pages","2",env=env);assert rc==0 and o["retry"]["attempts"]==2
 rc,o,_=run("user.list",env=env);assert rc==2 and o["error"]["category"]=="permission"
 rc,o,_=run("block.retrieve","--id","123456781234123412341234567890ab",env=env);assert rc==2 and o["error"]["category"]=="not_found";s.shutdown()

def test_non_paginated_endpoints_omit_pagination_parameters():
 rid="123456781234123412341234567890ab"
 for command,args in (("user.me",[]),("user.retrieve",["--id",rid]),("page.retrieve",["--id",rid]),("database.retrieve",["--id",rid]),("data_source.retrieve",["--id",rid])):
  a=n.parser().parse_args([command,*args,"--page-size","17","--start-cursor","cursor"])
  req=n.canonical(n.SPECS[command],a,{})
  assert req["query"]=={},command
  assert req["body"]=={},command

def test_post_pagination_is_encoded_in_body_and_advances_cursor(monkeypatch):
 rid="123456781234123412341234567890ab"
 for command,args in (("search.query",[]),("data_source.query",["--id",rid])):
  calls=[]
  class T:
   def __init__(self,a):self.attempts=1
   def request(self,method,path,query,body,mutation=False):
    calls.append((method,path,query,body.copy()))
    if len(calls)==1:return {"results":[{"id":"1"}],"has_more":True,"next_cursor":"next"},{}
    return {"results":[{"id":"2"}],"has_more":False,"next_cursor":None},{}
  monkeypatch.setattr(n,"Transport",T)
  a=n.parser().parse_args([command,*args,"--body",'{"filter":{"value":"x"}}',"--page-size","25","--all-pages","--max-pages","2"])
  req=n.canonical(n.SPECS[command],a,n.parse_body(a));out=n.execute(a,n.SPECS[command],req)
  assert calls[0][2]=={} and calls[0][3]["page_size"]==25 and "start_cursor" not in calls[0][3]
  assert calls[1][2]=={} and calls[1][3]["start_cursor"]=="next" and calls[1][3]["filter"]=={"value":"x"}
  assert [x["id"] for x in out["data"]["results"]]==["1","2"]

def test_get_list_pagination_stays_in_query_and_respects_bounds(monkeypatch):
 calls=[]
 class T:
  def __init__(self,a):self.attempts=1
  def request(self,method,path,query,body,mutation=False):
   calls.append((query.copy(),body.copy()))
   if len(calls)==1:return {"results":[{"id":"1"}],"has_more":True,"next_cursor":"next"},{}
   return {"results":[{"id":"2"}],"has_more":False,"next_cursor":None},{}
 monkeypatch.setattr(n,"Transport",T)
 a=n.parser().parse_args(["user.list","--page-size","100","--all-pages","--max-items","2","--max-pages","2"])
 req=n.canonical(n.SPECS[a.command],a,{});out=n.execute(a,n.SPECS[a.command],req)
 assert calls==[({"page_size":2},{}),({"page_size":2,"start_cursor":"next"},{})]
 assert len(out["data"]["results"])==2
def test_write_verify_and_mutation_error_classification(monkeypatch):
 class T:
  def __init__(self,a):self.attempts=1
  def request(self,method,path,query,body,mutation=False):
   if method=="POST":return {"id":"12345678-1234-1234-1234-1234567890ab"},{"x-request-id":"n1"}
   return {"id":"12345678-1234-1234-1234-1234567890ab","last_edited_time":"t"},{}
 monkeypatch.setattr(n,"Transport",T)
 a=n.parser().parse_args(["page.create","--body",'{"parent":{"page_id":"x"},"properties":{}}'])
 req=n.canonical(n.SPECS[a.command],a,n.parse_body(a));o=n.execute(a,n.SPECS[a.command],req)
 assert o["effects"]["performed"] and o["verification"]["performed"]
 assert n.category(500,"internal_server_error")=="backend" and n.category(429,"rate_limited")=="rate_limit"

def test_command_specific_manifest_schemas():
 manifest=json.loads((P.parent/"harness.json").read_text())
 assert manifest["commands"]["page.retrieve"]["inputSchema"]["required"]==["id"]
 assert "body" not in manifest["commands"]["page.retrieve"]["inputSchema"]["properties"]
 assert manifest["commands"]["auth.onboarding.verify"]["inputSchema"]["properties"]["roots"]["type"]=="string"
 contracts=json.loads((P.parent/"command_contracts.json").read_text())
 assert contracts["commands"]["page.create"]["structuredInputSchemas"]["allowedRoots"]["items"]["required"]==["type","id"]

def test_gateway_arg_map_contract_and_structured_transport():
 manifest=json.loads((P.parent/"harness.json").read_text())
 allowed={"string","number","integer","boolean","enum","path"}
 structured=0
 for name,command in manifest["commands"].items():
  properties=command["inputSchema"].get("properties",{})
  for entry in command["argMap"]:
   assert entry["valueType"] in allowed,(name,entry)
   if entry["type"]=="booleanFlag":assert entry["valueType"]=="boolean" and entry.get("flag")
   if entry["valueType"]=="path":assert entry.get("pathRole") in {"input","output","inout"}
   else:assert "pathRole" not in entry
   if entry["arg"] in json.loads((P.parent/"command_contracts.json").read_text())["commands"][name].get("jsonStringTransport",[]):
    structured+=1;assert entry["valueType"]=="string" and properties[entry["arg"]]["type"]=="string"
 assert structured==39
 contracts=json.loads((P.parent/"command_contracts.json").read_text())
 assert contracts["commands"]["page.create"]["jsonStringTransport"]==["allowedRoots","body"]

def test_gateway_arg_map_contract_and_structured_transport():
 manifest=json.loads((P.parent/"harness.json").read_text())
 contracts=json.loads((P.parent/"command_contracts.json").read_text())
 allowed={"string","number","integer","boolean","enum","path"}
 structured=0
 for name,command in manifest["commands"].items():
  properties=command["inputSchema"].get("properties",{})
  transported=set(contracts["commands"][name].get("jsonStringTransport",[]))
  for entry in command["argMap"]:
   assert entry["valueType"] in allowed,(name,entry)
   if entry["type"]=="booleanFlag":assert entry["valueType"]=="boolean" and entry.get("flag")
   if entry["valueType"]=="path":assert entry.get("pathRole") in {"input","output","inout"}
   else:assert "pathRole" not in entry
   if entry["arg"] in transported:
    structured+=1;assert properties[entry["arg"]]=={"type":"string"} and entry["valueType"]=="string"
 assert structured==39
 assert contracts["commands"]["page.create"]["jsonStringTransport"]==["allowedRoots","body"]

def test_allowlist_rejects_write_outside_root():
 root="123456781234123412341234567890ab";other="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
 rc,o,_=run("page.properties.update","--id",other,"--body",'{"properties":{}}',"--allowed-roots",json.dumps([{"type":"page","id":root}]),"--preview")
 assert rc==2 and "outside configured allowedRoots" in o["error"]["message"]

def test_markdown_bodies_are_validated_before_preview():
 root="123456781234123412341234567890ab";roots=json.dumps([{"type":"page","id":root}])
 rc,o,_=run("markdown.page.update","--id",root,"--body",'{"markdown":"invalid"}',"--allowed-roots",roots,"--preview")
 assert rc==2 and o["effects"]["performed"] is False and "body.type" in o["error"]["message"]
 rc,o,_=run("markdown.page.update","--id",root,"--body",'{"type":"replace_content","replace_content":{"new_str":"# Valid"}}',"--allowed-roots",roots,"--preview")
 assert rc==0 and o["data"]["preview"]["safety_class"]=="destructive"
 parent={"type":"page_id","page_id":root}
 rc,o,_=run("markdown.page.create","--body",json.dumps({"parent":parent,"markdown":42}),"--allowed-roots",roots,"--preview")
 assert rc==2 and "string markdown" in o["error"]["message"]
 rc,o,_=run("markdown.page.create","--body",json.dumps({"parent":parent,"markdown":"# Valid"}),"--allowed-roots",roots,"--preview")
 assert rc==0 and o["data"]["preview"]["safety_class"]=="externalSideEffect"

def test_archive_restore_use_in_trash_and_verify_exact_state(monkeypatch):
 rid="12345678-1234-1234-1234-1234567890ab"
 for command,expected in (("page.archive",True),("page.restore",False)):
  calls=[]
  class T:
   def __init__(self,a):self.attempts=1
   def request(self,method,path,query,body,mutation=False):
    calls.append((method,body.copy()))
    if method=="PATCH":return {"id":rid},{"x-request-id":"n1"}
    return {"id":rid,"in_trash":expected,"last_edited_time":"t"},{}
  monkeypatch.setattr(n,"Transport",T)
  a=n.parser().parse_args([command,"--id",rid])
  body={"in_trash":expected};req=n.canonical(n.SPECS[command],a,body);o=n.execute(a,n.SPECS[command],req)
  assert calls[0][1]=={"in_trash":expected} and "archived" not in calls[0][1]
  assert o["verification"]|{"field":"in_trash","expected":expected,"actual":expected}==o["verification"]


def test_archive_verification_rejects_mismatched_in_trash(monkeypatch):
 rid="12345678-1234-1234-1234-1234567890ab"
 class T:
  def __init__(self,a):self.attempts=1
  def request(self,method,path,query,body,mutation=False):
   return ({"id":rid},{}) if method=="PATCH" else ({"id":rid,"in_trash":False},{})
 monkeypatch.setattr(n,"Transport",T)
 a=n.parser().parse_args(["page.archive","--id",rid]);req=n.canonical(n.SPECS[a.command],a,{"in_trash":True})
 import pytest
 with pytest.raises(RuntimeError,match="in_trash verification"):n.execute(a,n.SPECS[a.command],req)


def test_file_upload_lifecycle_has_narrow_unattached_allowlist_exception():
 root="123456781234123412341234567890ab";roots=json.dumps([{"type":"page","id":root}])
 rc,o,_=run("file_upload.create","--body",'{"mode":"single_part"}',"--allowed-roots",roots,"--preview")
 assert rc==0 and "unattached file-upload" in o["data"]["preview"]["root_policy"]["exception"]
 upload="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
 rc,o,_=run("file_upload.complete","--id",upload,"--allowed-roots",roots,"--preview")
 assert rc==0 and "unattached file-upload" in o["data"]["preview"]["root_policy"]["exception"]
 rc,o,_=run("page.create","--body",'{"properties":{}}',"--allowed-roots",roots,"--preview")
 assert rc==2 and "cannot be proven" in o["error"]["message"]
 rc,o,_=run("page.properties.update","--id",upload,"--body",'{"properties":{}}',"--allowed-roots",roots,"--preview")
 assert rc==2 and "outside configured allowedRoots" in o["error"]["message"]

def test_file_upload_send_preview_and_authenticated_multipart(tmp_path,monkeypatch):
 root=tmp_path/"root";root.mkdir();(root/"a.txt").write_bytes(b"hello")
 uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
 a=n.parser().parse_args(["file_upload.send","--id",uid,"--transfer-root",str(root),"--source-path","a.txt","--preview"])
 n.validate(a);source=n.upload_source(a);intent=n.upload_intent(a,source)
 assert intent["endpoint"]==f"/file_uploads/{uid}/send" and "data" not in intent
 seen={}
 class R:
  status=200
  def __enter__(self):return self
  def __exit__(self,*x):pass
  def read(self,n):return json.dumps({"id":uid,"status":"uploaded"}).encode()
 def fake(req,timeout):seen.update(headers=dict(req.header_items()),body=req.data,url=req.full_url);return R()
 class T:
  def __init__(self,a):self.attempts=1
  def request(self,*x,**y):return {"id":uid,"status":"uploaded"},{}
 monkeypatch.setattr(n.urllib.request,"urlopen",fake);monkeypatch.setattr(n,"Transport",T);monkeypatch.setenv("NOTION_TOKEN","fixture-token")
 out=n.send_upload(a,source,intent)
 assert out["ok"] and out["verification"]["status"]=="uploaded" and out["data"]["source_size"]==5
 assert seen["url"].endswith(f"/v1/file_uploads/{uid}/send")
 assert b'name="file"; filename="a.txt"' in seen["body"] and b"hello" in seen["body"]
 assert seen["headers"]["Authorization"]=="Bearer fixture-token" and seen["headers"]["Notion-version"]==n.API_VERSION
 assert "fixture-token" not in json.dumps(out)


def test_file_upload_send_rejects_paths_size_and_bad_id(tmp_path):
 import pytest
 root=tmp_path/"root";root.mkdir();outside=tmp_path/"outside";outside.write_bytes(b"x")
 (root/"big").write_bytes(b"xx");(root/"link").symlink_to(outside)
 uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
 def args(path="big",limit="1",ident=uid,transfer=None):
  return n.parser().parse_args(["file_upload.send","--id",ident,"--transfer-root",str(transfer or root),"--source-path",path,"--max-upload-bytes",limit])
 with pytest.raises(ValueError,match="exceeds upload limit"):n.upload_source(args())
 with pytest.raises(ValueError,match="traversal-free"):n.upload_source(args("../outside",limit="20"))
 with pytest.raises(ValueError,match="symlinks"):n.upload_source(args("link",limit="20"))
 source=n.upload_source(args("big",limit="20"))
 with pytest.raises(ValueError,match="Notion UUID"):n.upload_intent(args("big","20","bad"),source)


def test_file_upload_send_failure_is_ambiguous(tmp_path,monkeypatch):
 import pytest
 root=tmp_path/"root";root.mkdir();(root/"a").write_bytes(b"x");uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
 a=n.parser().parse_args(["file_upload.send","--id",uid,"--transfer-root",str(root),"--source-path","a"])
 source=n.upload_source(a);intent=n.upload_intent(a,source);monkeypatch.setenv("NOTION_TOKEN","fixture")
 def fail(*x,**y):raise n.urllib.error.URLError("timeout")
 monkeypatch.setattr(n.urllib.request,"urlopen",fail)
 with pytest.raises(n.TransferError) as exc:n.send_upload(a,source,intent)
 assert exc.value.unknown


def test_file_upload_send_manifest_contract():
 manifest=json.loads((P.parent/"harness.json").read_text());cmd=manifest["commands"]["file_upload.send"]
 assert cmd["safetyClasses"]==["externalSideEffect","secretUse","authReuse"]
 assert cmd["inputSchema"]["required"]==["id","transferRoot","sourcePath"]
 contract=json.loads((P.parent/"command_contracts.json").read_text())["commands"]["file_upload.send"]
 assert contract["path"]=="/file_uploads/{id}/send" and contract["verify"]=="file_upload"

def test_append_records_created_block_ids_and_reply_is_created_with_response_evidence(monkeypatch):
 parent="12345678-1234-1234-1234-1234567890ab";b1="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";b2="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
 class AppendT:
  def __init__(self,a):self.attempts=1
  def request(self,method,path,query,body,mutation=False):return {"results":[{"id":b1},{"id":b2}]},{"x-request-id":"n1"}
 monkeypatch.setattr(n,"Transport",AppendT)
 a=n.parser().parse_args(["block.children.append","--id",parent,"--body",'{"children":[{}]}']);req=n.canonical(n.SPECS[a.command],a,n.parse_body(a));o=n.execute(a,n.SPECS[a.command],req)
 assert o["effects"]["created"]==[b1,b2] and not o["effects"]["updated"]
 class ReplyT:
  def __init__(self,a):self.attempts=1
  def request(self,method,path,query,body,mutation=False):return {"object":"comment","id":b1,"discussion_id":parent},{"x-request-id":"n2"}
 monkeypatch.setattr(n,"Transport",ReplyT)
 a=n.parser().parse_args(["comment.reply","--body",json.dumps({"discussion_id":parent,"rich_text":[]})]);req=n.canonical(n.SPECS[a.command],a,n.parse_body(a));o=n.execute(a,n.SPECS[a.command],req)
 assert o["effects"]["created"]==[b1] and not o["effects"]["updated"]
 assert not o["verification"]["supported"] and o["verification"]["response_evidence"]=={"comment_id":b1,"discussion_id":parent,"object":"comment"}


def test_operation_plan_and_required_input():
 rc,o,_=run("operation.plan","--operation","page.create","--target-kind","page")
 assert rc==0 and o["data"]["recipe"][0].startswith("resolve") and o["data"]["verification"]=="page"
 rc,o,_=run("operation.plan");assert rc==2 and "--operation is required" in o["error"]["message"]

def test_payload_element_text_and_url_limits():
 rc,o,_=run("page.create","--body",json.dumps({"children":[{}]*101}),"--preview");assert rc==2 and "exceeds 100 items" in o["error"]["message"]
 rc,o,_=run("page.create","--body",json.dumps({"url":"x"*2001}),"--preview");assert rc==2 and "exceeds 2000" in o["error"]["message"]

def test_onboarding_verify_success_and_guidance(monkeypatch):
 rid="12345678-1234-1234-1234-1234567890ab"
 class T:
  def __init__(self,a):pass
  def request(self,method,path,query,body,mutation=False):
   if path=="/users/me":return {"id":"bot","name":"Fixture bot","type":"bot","bot":{"workspace_name":"Fixture","workspace_id":"ws"}},{}
   return {"id":rid,"object":"page"},{}
 monkeypatch.setattr(n,"Transport",T)
 a=n.parser().parse_args(["auth.onboarding.verify","--roots",json.dumps([{"type":"page","id":rid}])])
 o=n.onboarding_verify(a);assert o["ok"] and o["data"]["identity"]["workspace_name"]=="Fixture" and o["data"]["ready"]
 assert "token" not in json.dumps(o).lower()

def test_onboarding_verify_404_diagnostic(monkeypatch):
 rid="12345678-1234-1234-1234-1234567890ab"
 class T:
  def __init__(self,a):pass
  def request(self,method,path,query,body,mutation=False):
   if path=="/users/me":return {"id":"bot","type":"bot","bot":{}},{}
   raise n.ApiError(404,"object_not_found","not shared",None)
 monkeypatch.setattr(n,"Transport",T)
 a=n.parser().parse_args(["auth.onboarding.verify","--roots",json.dumps([{"type":"page","id":rid}])])
 o=n.onboarding_verify(a);assert not o["ok"] and "not shared" in o["data"]["roots"][0]["diagnostic"]

def test_no_secret_leakage_in_onboarding_error():
 secret="fixture-sensitive-credential-value"
 rc,o,err=run("auth.onboarding.verify","--roots",json.dumps([{"type":"page","id":"123456781234123412341234567890ab"}]),env={"NOTION_TOKEN":secret,"NOTION_API_BASE":"http://127.0.0.1:1/v1"})
 assert rc==2 and secret not in json.dumps(o)+err


def test_onboarding_verify_403_and_wrong_workspace(monkeypatch):
 rid="12345678-1234-1234-1234-1234567890ab"
 class Denied:
  def __init__(self,a):pass
  def request(self,method,path,query,body,mutation=False):
   if path=="/users/me":return {"id":"bot","type":"bot","bot":{"workspace_name":"Other","workspace_id":"other"}},{}
   raise n.ApiError(403,"restricted_resource","denied",None)
 monkeypatch.setattr(n,"Transport",Denied)
 a=n.parser().parse_args(["auth.onboarding.verify","--workspace","Expected","--roots",json.dumps([{"type":"page","id":rid}])])
 o=n.onboarding_verify(a);assert not o["ok"] and o["error"]["code"]=="wrong_workspace" and o["data"]["roots"][0]["http_status"]==403 and not o["data"]["allowedRoots"]


def test_every_gateway_input_schema_uses_runtime_supported_keywords_only():
 manifest=json.loads((P.parent/"harness.json").read_text())
 supported={"type","required","properties","additionalProperties"}
 seen=set()
 def audit(schema,path):
  assert isinstance(schema,dict),path
  assert set(schema)<=supported,(path,set(schema)-supported)
  seen.update(schema)
  if "type" in schema:assert schema["type"] in {"object","array","string","number","integer","boolean","null"},path
  if "required" in schema:assert isinstance(schema["required"],list) and all(isinstance(x,str) for x in schema["required"]),path
  if "properties" in schema:
   assert isinstance(schema["properties"],dict),path
   for key,child in schema["properties"].items():audit(child,f"{path}.properties.{key}")
  if "additionalProperties" in schema:assert isinstance(schema["additionalProperties"],bool),path
 for name,command in manifest["commands"].items():audit(command["inputSchema"],name)
 assert seen==supported


def test_every_gateway_arg_map_uses_runtime_supported_contract():
 manifest=json.loads((P.parent/"harness.json").read_text())
 value_types={"string","enum","integer","number","boolean","path"}
 entry_types={"positional","option","booleanFlag","repeatableOption"}
 covered_values=set();covered_entries=set()
 for name,command in manifest["commands"].items():
  props=command["inputSchema"].get("properties",{})
  for entry in command["argMap"]:
   assert entry["arg"] in props,(name,entry["arg"])
   assert entry["valueType"] in value_types,(name,entry)
   assert entry["type"] in entry_types,(name,entry)
   covered_values.add(entry["valueType"]);covered_entries.add(entry["type"])
   if entry["type"] in {"option","booleanFlag","repeatableOption"}:assert entry.get("flag"),(name,entry)
   if entry["valueType"]=="path":assert entry.get("pathRole") in {"input","output","inout"},(name,entry)
   else:assert "pathRole" not in entry,(name,entry)
 assert covered_values=={"string","boolean"}
 assert covered_entries=={"option","booleanFlag"}


def test_gateway_simplification_retains_harness_side_revalidation():
 manifest=json.loads((P.parent/"harness.json").read_text())
 assert manifest["commands"]["onboard.plan"]["inputSchema"]["properties"]["authMode"]=={"type":"string"}
 assert manifest["commands"]["onboard.status"]["inputSchema"]["properties"]["outputRoot"]=={"type":"string"}
 invalid=subprocess.run([sys.executable,str(P),"onboard.plan","--auth-mode","invalid"],text=True,capture_output=True)
 assert invalid.returncode!=0 and "invalid choice" in invalid.stderr
 rc,o,_=run("onboard.status","--output-root","")
 assert rc==2 and "--output-root is required" in o["error"]["message"]


def test_per_run_secretrefs_manifest_contract():
 import json
 from pathlib import Path
 root=Path(__file__).resolve()
 while not (root/'harnesses').exists(): root=root.parent
 manifest=json.loads((root/'harnesses/notion/harness.json').read_text())
 binding=json.loads((root/'harnesses/notion/command_contracts.json').read_text())['directCredentialSecretBinding']
 assert manifest['version']=='0.1.9' and 'credentialEnvironment' not in manifest
 assert binding['names']==['NOTION_TOKEN'] and binding['parameter']=='secretRefs'
 assert binding['prepareRunMustMatch'] and not binding['manifestStoresPointer']
 assert json.loads((root/'skills/notion/capability.json').read_text())['linkedHarness']['version']=='0.1.9'
