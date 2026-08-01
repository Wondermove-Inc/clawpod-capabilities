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
