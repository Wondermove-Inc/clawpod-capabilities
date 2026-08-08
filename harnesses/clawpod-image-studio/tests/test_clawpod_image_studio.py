import importlib.util,json,os,subprocess,sys
from pathlib import Path
import pytest
P=Path(__file__).parents[1]/"clawpod_image_studio.py"
spec=importlib.util.spec_from_file_location("studio",P); s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)

def invoke(tmp,cmd,payload=None,env=None):
 e={k:v for k,v in os.environ.items() if not k.startswith("CLAWPOD_IMAGE_STUDIO_")}; e.update(env or {})
 q=subprocess.run([sys.executable,str(P),cmd,"--root",str(tmp),"--input-json",json.dumps(payload or {})],text=True,capture_output=True,env=e)
 assert q.stdout and not q.stderr; return q,json.loads(q.stdout)
def policies(): return {"safetyPolicy":"safe","rightsPolicy":"owned","publicationPolicy":"review-required"}
def req(**kw):
 x={"prompt":"a geometric fox","output":"fox.png","count":1,"maxUsd":1,"expiresAt":"2099-01-01T00:00:00Z",**policies()}; x.update(kw); return x
def bind(tmp,p="openai",**extra):
 x={"provider":p,"pointer":"msp_unit_test_pointer",**extra}
 if p=="vertex": x={"provider":"vertex","project":"p1","location":"us-central1","iam":"roles/aiplatform.user"}
 return invoke(tmp,"connection.bind",x)
def prep(tmp,**kw): return invoke(tmp,"request.prepare",req(**kw))[1]["data"]

def test_routing_and_vertex_governance(tmp_path):
 for features,fmt,expected in [([],"png","openai"),(["vector"],"svg","recraft"),(["synthid"],"png","vertex"),(["photoreal"],"png","bfl")]:
  x=req(features=features,format=fmt); x.pop("maxUsd"); x.pop("expiresAt")
  if expected=="vertex": x.update(project="p",location="us",iam="role")
  _,o=invoke(tmp_path,"request.validate",x)
  assert o["data"]["request"]["provider"]==expected and "error" not in o

def test_schema_unknown_and_separate_policies(tmp_path):
 _,o=invoke(tmp_path,"request.validate",{**req(),"unexpected":1}); assert o["error"]["code"]=="SCHEMA_VIOLATION"
 for policy in ("safetyPolicy","rightsPolicy","publicationPolicy"):
  x=req(); x.pop(policy); _,o=invoke(tmp_path,"request.validate",x); assert o["error"]["code"]=="POLICY_REQUIRED"

def test_estimate_prepare_digest_mutation_and_binding(tmp_path):
 bind(tmp_path); a=prep(tmp_path); b=prep(tmp_path,prompt="changed"); assert a["preparedDigest"]!=b["preparedDigest"]
 x=req(preparedDigest=a["preparedDigest"],bindingDigest=a["bindingDigest"]); x["prompt"]="changed"
 _,o=invoke(tmp_path,"image.generate",x,env={"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-success"}); assert o["error"]["code"]=="DIGEST_MISMATCH"

def test_missing_wrong_binding_and_no_network_default(tmp_path):
 bind(tmp_path); a=prep(tmp_path)
 x=req(preparedDigest=a["preparedDigest"]); _,o=invoke(tmp_path,"image.generate",x); assert o["error"]["code"]=="DIGEST_MISMATCH"
 x["bindingDigest"]=a["bindingDigest"]; _,o=invoke(tmp_path,"image.generate",x); assert o["error"]["code"]=="NETWORK_DISABLED"

def test_success_artifact_digest_mime_and_svg_qa(tmp_path):
 bind(tmp_path,"recraft"); a=prep(tmp_path,provider="recraft",format="svg",output="logo.svg")
 x=req(provider="recraft",format="svg",output="logo.svg",preparedDigest=a["preparedDigest"],bindingDigest=a["bindingDigest"])
 _,o=invoke(tmp_path,"image.generate",x,{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-success"}); art=o["data"]["artifact"]
 assert art["mimeType"]=="image/svg+xml" and art["qa"]["svgParsed"] and art["sha256"].startswith("sha256:")
 _,i=invoke(tmp_path,"artifact.inspect",{"path":"logo.svg"}); assert i["data"]["sha256"]==art["sha256"]

def test_path_escape(tmp_path):
 bind(tmp_path)
 _,o=invoke(tmp_path,"request.prepare",req(output="../../escape.png")); assert o["error"]["code"]=="PATH_VIOLATION" or o["ok"]
 if o["ok"]:
  a=o["data"]; _,r=invoke(tmp_path,"image.generate",req(output="../../escape.png",preparedDigest=a["preparedDigest"],bindingDigest=a["bindingDigest"]),{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-success"}); assert r["error"]["code"]=="PATH_VIOLATION"

def test_ambiguous_billing_no_retry_and_outage(tmp_path):
 bind(tmp_path); a=prep(tmp_path); x=req(preparedDigest=a["preparedDigest"],bindingDigest=a["bindingDigest"])
 _,o=invoke(tmp_path,"image.generate",x,{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-ambiguous"}); assert o["error"]["code"]=="BILLING_AMBIGUOUS" and not o["error"]["retryable"] and not o["error"]["details"]["automaticRetry"]
 _,o=invoke(tmp_path,"image.generate",x,{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-outage"}); assert o["error"]["code"]=="PROVIDER_OUTAGE" and o["error"]["retryable"]

def test_redaction_and_plaintext_rejection(tmp_path):
 _,o=invoke(tmp_path,"connection.bind",{"provider":"openai","pointer":"sk-secretvalue123456"}); assert o["error"]["code"] in {"POINTER_REQUIRED","PLAINTEXT_SECRET_FORBIDDEN"} and "secretvalue" not in json.dumps(o)
 assert "secretvalue" not in json.dumps(s.redact({"token":"secretvalue","x":"Bearer abcdefghijk"}))

def test_pricing_stale(tmp_path):
 _,o=invoke(tmp_path,"pricing.snapshot",{"asOf":"2020-01-01"}); assert o["data"]["stale"] and o["data"]["ageDays"]>30

def test_onboarding_transitions_and_vertex_no_key(tmp_path):
 _,o=invoke(tmp_path,"connection.status",{"provider":"openai"}); assert o["data"]["items"][0]["state"]=="deferred"
 _,o=bind(tmp_path); assert o["data"]["state"]=="configured_unverified"
 _,o=invoke(tmp_path,"connection.verify",{"provider":"openai","nonBillable":True}); assert o["data"]["state"]=="configured_unverified"
 _,o=invoke(tmp_path,"connection.verify",{"provider":"openai","nonBillable":True},{"CLAWPOD_IMAGE_STUDIO_VERIFY":"mock-success"}); assert o["data"]["state"]=="connected"
 _,o=invoke(tmp_path,"connection.revoke",{"provider":"openai","confirm":"revoke-binding"}); assert o["data"]["state"]=="revoked"
 _,o=invoke(tmp_path,"connection.bind",{"provider":"vertex","pointer":"msp_something"}); assert o["error"]["code"]=="SCHEMA_VIOLATION"

def test_onboarding_interview_contract(tmp_path):
 _,o=invoke(tmp_path,"onboarding.interview",{}); d=o["data"]; assert not d["complete"] and "ADC/OAuth/service account" in d["vertexAuth"] and set(d["states"])=={"connected","configured_unverified","deferred","revoked"}

def test_compare_caps_budget_digests_and_partial(tmp_path):
 bind(tmp_path,"openai"); bind(tmp_path,"bfl")
 base=req(operation="compare",legs=[{"provider":"openai"},{"provider":"bfl"}],maxUsd=1,output="choice.png")
 _,o=invoke(tmp_path,"request.prepare",base); d=o["data"]; assert len(d["legDigests"])==2 and d["aggregateDigest"].startswith("sha256:")
 bindings=[leg["bindingDigest"] for leg in d["legs"]]
 _,run=invoke(tmp_path,"image.compare",{"aggregateDigest":d["aggregateDigest"],"legDigests":d["legDigests"],"bindingDigests":bindings},{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-success"}); assert run["data"]["state"]=="succeeded"
 _,bad=invoke(tmp_path,"request.prepare",{**base,"legs":[{"provider":"openai"}]*5}); assert bad["error"]["code"]=="COMPARE_CAP"
 _,budget=invoke(tmp_path,"request.prepare",{**base,"maxUsd":0.01}); assert budget["error"]["code"]=="COST_CEILING_REQUIRED"
 # mutate one connection after preparation: one leg succeeds and one fails closed
 invoke(tmp_path,"connection.revoke",{"provider":"bfl","confirm":"revoke-binding"})
 _,partial=invoke(tmp_path,"image.compare",{"aggregateDigest":d["aggregateDigest"],"legDigests":d["legDigests"],"bindingDigests":bindings},{"CLAWPOD_IMAGE_STUDIO_TRANSPORT":"mock-success"}); assert partial["data"]["state"]=="partial" and partial["data"]["failed"]==1

def test_manifest_contract_and_no_pointer_ids():
 m=json.loads((P.parent/"harness.json").read_text()); c=json.loads((P.parent/"command_contracts.json").read_text()); rendered=(P.parent/"harness.json").read_text()+(P.parent/"command_contracts.json").read_text()
 assert m["name"]=="clawpod-image-studio" and m["title"]=="ClawPod Image Studio" and set(m["commands"])==set(s.COMMANDS)
 assert c["secretBinding"]["prepareRunMustMatch"] and not c["secretBinding"]["manifestStoresPointer"] and "msp_" not in rendered
 for name in ("image.generate","image.edit","image.compare"): assert "externalSideEffect" in m["commands"][name]["safetyClasses"]
