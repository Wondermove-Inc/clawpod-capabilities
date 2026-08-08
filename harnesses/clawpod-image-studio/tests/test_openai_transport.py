import base64, datetime as dt, importlib.util, io, json, os, struct, urllib.error
from pathlib import Path
import pytest

P=Path(__file__).parents[1]/"clawpod_image_studio.py"
spec=importlib.util.spec_from_file_location("studio",P); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
PNG=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"+struct.pack(">II",2,3)+b"\x08\x06\x00\x00\x00"
class Resp:
 def __init__(self,data): self.data=data
 def read(self,n=-1): return self.data[:n]
 def __enter__(self): return self
 def __exit__(self,*a): pass

def payload(**kw):
 d={"operation":"generate","provider":"openai","model":"gpt-image-1","prompt":"safe test","count":1,"format":"png","options":{}}
 d.update(kw); return d

def test_base64_success_and_key_only_header(monkeypatch):
 monkeypatch.setenv("OPENAI_API_KEY","top-secret-value")
 seen=[]
 def op(req,timeout):
  seen.append((req,timeout)); return Resp(json.dumps({"id":"req_1","data":[{"b64_json":base64.b64encode(PNG).decode()}]}).encode())
 out=m.openai_generate(payload(options={"quality":"low"}),op)
 assert out["items"]==[PNG] and seen[0][1]==m.HTTP_TIMEOUT
 assert b"top-secret-value" not in seen[0][0].data
 assert seen[0][0].get_header("Authorization")=="Bearer top-secret-value"
 body=json.loads(seen[0][0].data)
 assert body["model"]=="gpt-image-1" and body["prompt"]=="safe test" and body["n"]==1


def test_key_injection_auto_enables_openai_live_and_options_cannot_override(monkeypatch):
 monkeypatch.setenv("OPENAI_API_KEY","x")
 monkeypatch.delenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT",raising=False)
 seen=[]
 def op(req,timeout):
  seen.append(json.loads(req.data)); return Resp(json.dumps({"data":[{"b64_json":base64.b64encode(PNG).decode()}]}).encode())
 assert m.transport("openai",payload(options={"quality":"low"}),op)["items"]==[PNG]
 assert seen[0]["quality"]=="low"
 with pytest.raises(m.E) as e: m.openai_generate(payload(options={"model":"attacker-override"}),op)
 assert e.value.code=="SCHEMA_VIOLATION"

def test_url_result_is_https_and_downloaded(monkeypatch):
 monkeypatch.setenv("OPENAI_API_KEY","x")
 calls=[]
 def op(req,timeout):
  calls.append(req.full_url)
  return Resp(json.dumps({"data":[{"url":"https://cdn.example/image.png"}]}).encode()) if len(calls)==1 else Resp(PNG)
 assert m.openai_generate(payload(),op)["items"]==[PNG]
 assert len(calls)==2

def test_malformed_and_unsafe_result(monkeypatch):
 monkeypatch.setenv("OPENAI_API_KEY","x")
 with pytest.raises(m.E) as e: m.openai_generate(payload(),lambda *_:Resp(b'{bad'))
 assert e.value.code=="PROVIDER_RESPONSE_INVALID" and not e.value.retryable
 with pytest.raises(m.E) as e: m.openai_generate(payload(),lambda *_:Resp(b'{"data":[{"url":"http://bad/x"}]}'))
 assert e.value.code=="PROVIDER_RESPONSE_INVALID"

@pytest.mark.parametrize("status,code",[(401,"PROVIDER_AUTH_FAILED"),(403,"PROVIDER_AUTH_FAILED"),(429,"PROVIDER_RATE_LIMITED")])
def test_http_classification_no_retry(monkeypatch,status,code):
 monkeypatch.setenv("OPENAI_API_KEY","secret")
 err=urllib.error.HTTPError("https://api.openai.com",status,"contains secret",{},io.BytesIO(b'{"error":"secret"}'))
 with pytest.raises(m.E) as e: m.openai_generate(payload(),lambda *_:(_ for _ in ()).throw(err))
 assert e.value.code==code and e.value.retryable is False
 if status==429: assert e.value.details["automaticRetry"] is False

@pytest.mark.parametrize("failure",[TimeoutError(),urllib.error.URLError("down"),urllib.error.HTTPError("https://api.openai.com",500,"boom",{},None)])
def test_timeout_and_5xx_are_ambiguous_and_never_retried(monkeypatch,failure):
 monkeypatch.setenv("OPENAI_API_KEY","x"); calls=0
 def op(*_):
  nonlocal calls; calls+=1; raise failure
 with pytest.raises(m.E) as e: m.openai_generate(payload(),op)
 assert calls==1 and e.value.code=="BILLING_AMBIGUOUS" and not e.value.retryable and e.value.details["automaticRetry"] is False

def test_nonbillable_verify(monkeypatch):
 monkeypatch.setenv("OPENAI_API_KEY","x")
 out=m.openai_verify(lambda *_:Resp(b'{"id":"gpt-image-1"}'))
 assert out["verified"] and not out["billingAttempted"]

def test_path_validation_redaction_and_artifact_qa(tmp_path):
 with pytest.raises(m.E): m.safe_output(tmp_path,"../escape.png")
 outside=tmp_path/"out"; outside.mkdir(); (tmp_path/"link").symlink_to(outside,target_is_directory=True)
 with pytest.raises(m.E): m.safe_output(tmp_path,"link/x.png")
 assert "top-secret-value" not in json.dumps(m.redact({"message":"Bearer top-secret-value","authorization":"top-secret-value"}))
 p=tmp_path/"x.png"; p.write_bytes(PNG); art=m.inspect_artifact(p)
 assert art["mimeType"]=="image/png" and art["dimensions"]=={"width":2,"height":3} and art["sha256"].startswith("sha256:")

def test_missing_key_is_preacceptance():
 os.environ.pop("OPENAI_API_KEY",None)
 with pytest.raises(m.E) as e: m.openai_generate(payload(),lambda *_:None)
 assert e.value.code=="CREDENTIAL_UNAVAILABLE"

def test_prepared_digest_binding_cost_expiry_and_output_are_enforced(tmp_path,monkeypatch):
 root=m.root(str(tmp_path)); rec={"state":"configured_unverified","pointer":"msp_example123"}
 m.atomic(m.conn_path(root),{"openai":rec})
 expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=10)).isoformat().replace("+00:00","Z")
 req={**payload(),"output":"ok.png","maxUsd":0.04,"expiresAt":expiry,"safetyPolicy":"approved","rightsPolicy":"approved","publicationPolicy":"not-approved"}
 prepared=m.prepare(req,root); run={k:v for k,v in prepared.items() if k!="estimate"}
 monkeypatch.setenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT","mock-success")
 out=m.run_image(run,root,"generate")
 assert out["state"]=="succeeded" and out["artifacts"][0]["dimensions"]=={"width":1,"height":1}
 assert Path(out["artifacts"][0]["path"]).is_relative_to(root/"artifacts")
 changed={**run,"maxUsd":0.05}
 with pytest.raises(m.E) as e: m.run_image(changed,root,"generate")
 assert e.value.code=="DIGEST_MISMATCH"
 changed={**run,"bindingDigest":"sha256:"+"0"*64}
 with pytest.raises(m.E) as e: m.run_image(changed,root,"generate")
 assert e.value.code=="DIGEST_MISMATCH"
