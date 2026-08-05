import importlib.util, json, os, stat, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]; CLI=HERE/"enterprise_newsletter.py"
SPEC=importlib.util.spec_from_file_location("enterprise_newsletter",CLI); MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

def fact(text="Verified fact", evidence=True): return {"text":text,"evidenceRequired":evidence,"sourceIds":["s1"] if evidence else []}
def card(i): return {"title":f"Card {i}","facts":[fact()],"whyItMatters":f"Reason {i}","cta":{"label":"Read source","url":"https://example.com/item"},"imageAlt":f"Abstract illustration for card {i}"}
def document(profile="newsletter"):
    counts={"brief":2,"newsletter":3,"capability-catalog":4}; cards=[card(i) for i in range(counts[profile])]
    sections=[{"title":"Primary section","cards":cards}] if profile!="newsletter" else [{"title":"First section","cards":cards[:2]},{"title":"Second section","cards":cards[2:]}]
    return {"schemaVersion":1,"profile":profile,"brand":{"name":"Example Enterprise","primaryColor":"#1A73E8","tagline":"Useful context & <care>"},"edition":{"label":"Weekly Brief","date":"2026-08-05"},"headline":"Decisions with evidence <script>alert(1)</script>","preheader":"A concise evidence-backed edition","executiveLead":"This edition separates facts from analysis.","atAGlance":[{"title":"Signal one","summary":"A bounded summary","signal":"Review"},{"title":"Signal two","summary":"Another bounded summary"}],"keyNumbers":[{"value":str(i),"label":f"Metric {i}","sourceIds":["s1"]} for i in range(1,5)],"sections":sections,"synthesis":["Evidence changes the decision."],"methodology":"Sources were reviewed within the declared boundary.","footer":{"tagline":"Customer insight, clearly delivered","text":"Prepared for internal review","unsubscribeUrl":"https://example.com/unsubscribe"},"sources":[{"id":"s1","title":"Primary source","url":"https://example.com/source","publisher":"Example","publishedAt":"2026-08-04"}]}

def private(tmp_path):
    p=tmp_path; p.mkdir(mode=0o700,parents=True); os.chmod(p,0o700); return p
def write(root,name,value): (root/name).write_text(json.dumps(value),encoding="utf-8"); os.chmod(root/name,0o600)
def run(*args):
    cp=subprocess.run([sys.executable,str(CLI),*map(str,args)],text=True,capture_output=True); return cp.returncode,json.loads(cp.stdout)

def test_status_and_all_profiles(tmp_path):
    code,out=run("status"); assert code==0 and out["data"]["ready"] and isinstance(out["schemaVersion"],int)
    for profile in ("brief","newsletter","capability-catalog"):
        root=private(tmp_path/profile); write(root,"in.json",document(profile)); code,out=run("validate","--input-root",root,"--input","in.json"); assert code==0 and out["data"]["profile"]==profile

def test_render_escape_parity_determinism_and_inspect(tmp_path):
    src=private(tmp_path/"src"); write(src,"in.json",document()); out1=private(tmp_path/"out1"); out2=private(tmp_path/"out2")
    for out in (out1,out2):
        code,r=run("render","--input-root",src,"--input","in.json","--output-root",out,"--html","n.html","--text","n.txt"); assert code==0 and r["data"]["parity"]["cards"]
    assert (out1/"n.html").read_bytes()==(out2/"n.html").read_bytes(); assert (out1/"n.txt").read_bytes()==(out2/"n.txt").read_bytes()
    html=(out1/"n.html").read_text(); plain=(out1/"n.txt").read_text(); assert "&lt;script&gt;" in html and "<script>alert" not in html and "Useful context &amp; &lt;care&gt;" in html and "Useful context & <care>" in plain
    assert "--brand-primary:#1A73E8" in html and "Customer insight, clearly delivered" in html and "Customer insight, clearly delivered" in plain
    assert stat.S_IMODE((out1/"n.html").stat().st_mode)==0o600 and stat.S_IMODE((out1/"n.txt").stat().st_mode)==0o600
    code,r=run("inspect","--input-root",out1,"--input","n.html"); assert code==0 and r["data"]["hasTemplateMarker"] and not r["data"]["containsScript"]

def test_malformed_evidence_links_profile_template_and_clobber(tmp_path):
    src=private(tmp_path/"src")
    (src/"bad.json").write_text("{"); os.chmod(src/"bad.json",0o600); assert run("validate","--input-root",src,"--input","bad.json")[1]["error"]["code"]=="malformed_json"
    cases=[]
    d=document(); d["sections"][0]["cards"][0]["facts"][0]["sourceIds"]=[]; cases.append((d,"evidence_missing"))
    d=document(); d["sources"][0]["url"]="javascript:alert(1)"; cases.append((d,"unsafe_link"))
    d=document(); d["profile"]="unknown"; cases.append((d,"unsupported_profile"))
    d=document(); d["brand"]["primaryColor"]="#12345"; cases.append((d,"invalid_newsletter"))
    d=document(); del d["footer"]["tagline"]; cases.append((d,"invalid_newsletter"))
    d=document(); del d["sections"][0]["cards"][0]["cta"]["label"]; cases.append((d,"invalid_newsletter"))
    for i,(d,code) in enumerate(cases): write(src,f"x{i}.json",d); assert run("validate","--input-root",src,"--input",f"x{i}.json")[1]["error"]["code"]==code
    write(src,"in.json",document()); out=private(tmp_path/"out"); assert run("render","--input-root",src,"--input","in.json","--output-root",out,"--template","other")[1]["error"]["code"]=="unsupported_template"
    (out/"n.html").write_text("existing"); os.chmod(out/"n.html",0o600); assert run("render","--input-root",src,"--input","in.json","--output-root",out,"--html","n.html")[1]["error"]["code"]=="clobber_rejected"

def test_paths_symlinks_and_private_roots(tmp_path):
    src=private(tmp_path/"src"); write(src,"in.json",document()); out=private(tmp_path/"out")
    assert run("validate","--input-root",src,"--input","../in.json")[1]["error"]["code"]=="unsafe_path"
    (src/"link.json").symlink_to(src/"in.json"); assert run("validate","--input-root",src,"--input","link.json")[1]["error"]["code"]=="unsafe_path"
    public=tmp_path/"public"; public.mkdir(mode=0o755); assert run("validate","--input-root",public,"--input","x")[1]["error"]["code"]=="unsafe_path"

def test_release_binding_privacy_and_invalidation(tmp_path):
    src=private(tmp_path/"src"); manifests=private(tmp_path/"manifests"); d=document(); write(src,"in.json",d)
    _,v=run("validate","--input-root",src,"--input","in.json"); cd=v["data"]["contentDigest"]; raw='["Alice@Example.com","bob@example.com","alice@example.com"]'
    code,p=run("release.prepare","--input-root",src,"--input","in.json","--recipients",raw,"--approved-content-digest",cd,"--output-root",manifests); assert code==0 and p["data"]["recipientCount"]==2
    persisted=(manifests/"release.json").read_text(); assert "alice@" not in persisted.lower() and "bob@" not in persisted.lower()
    assert run("release.verify","--input-root",src,"--input","in.json","--recipients",raw,"--manifest-root",manifests)[0]==0
    assert run("release.verify","--input-root",src,"--input","in.json","--recipients",'["other@example.com"]',"--manifest-root",manifests)[1]["error"]["code"]=="release_changed"
    d["headline"]="Changed"; write(src,"changed.json",d); assert run("release.verify","--input-root",src,"--input","changed.json","--recipients",raw,"--manifest-root",manifests)[1]["error"]["code"]=="release_changed"
    bad=private(tmp_path/"bad-manifest"); (bad/"release.json").write_text("{"); os.chmod(bad/"release.json",0o600)
    assert run("release.verify","--input-root",src,"--input","in.json","--recipients",raw,"--manifest-root",bad)[1]["error"]["code"]=="manifest_invalid"
    invalid=private(tmp_path/"invalid-manifest"); write(invalid,"release.json",{"schemaVersion":"1"})
    assert run("release.verify","--input-root",src,"--input","in.json","--recipients",raw,"--manifest-root",invalid)[1]["error"]["code"]=="manifest_invalid"

def test_secret_redaction_and_no_network_surface(tmp_path):
    src=private(tmp_path/"src"); write(src,"in.json",document()); code,out=run("release.prepare","--input-root",src,"--input","in.json","--recipients",'["bad"]',"--approved-content-digest","api_key=SUPERSECRET","--output-root",private(tmp_path/"out")); assert code and "SUPERSECRET" not in json.dumps(out)
    assert MODULE.clean_message("authorization: Bearer SUPERSECRET") == "[REDACTED]"
    manifest=json.loads((HERE/"harness.json").read_text()); assert all("externalSideEffect" not in c["safetyClasses"] for c in manifest["commands"].values()); assert manifest["authModel"]["type"]=="none"
    assert manifest["definitions"]["output"]["properties"]["schemaVersion"]["type"]=="number"

def test_complete_schema_parity_helper_unicode_and_limits(tmp_path):
    schema=MODULE.schema(); assert schema["additionalProperties"] is False and schema["properties"]["brand"]["additionalProperties"] is False
    assert schema["properties"]["sections"]["items"]["properties"]["cards"]["items"]["properties"]["cta"]["required"]==["label","url"]
    assert schema["properties"]["schemaVersion"]["type"]=="number"
    d=document(); h=MODULE.render_html(d); t=MODULE.render_text(d); assert MODULE.parity(d,h,t)["passed"]
    assert not MODULE.parity(d,h.replace("Card 0","missing",1),t)["cards"]
    assert not MODULE.parity(d,h,t.replace("https://example.com/item","missing"))["ctaLinks"]
    d["headline"]="Résumé 世界"; src=private(tmp_path/"unicode"); write(src,"in.json",d); assert run("validate","--input-root",src,"--input","in.json")[0]==0
    huge=private(tmp_path/"huge"); (huge/"in.json").write_bytes(b" "*(MODULE.MAX_INPUT+1)); os.chmod(huge/"in.json",0o600)
    assert run("validate","--input-root",huge,"--input","in.json")[1]["error"]["code"]=="input_too_large"

def test_output_name_recipients_and_schema_output(tmp_path):
    src=private(tmp_path/"src"); write(src,"in.json",document()); out=private(tmp_path/"out")
    assert run("render","--input-root",src,"--input","in.json","--output-root",out,"--html","same","--text","same")[1]["error"]["code"]=="unsafe_path"
    too_many=json.dumps([f"u{i}@example.com" for i in range(5001)])
    _,v=run("validate","--input-root",src,"--input","in.json")
    assert run("release.prepare","--input-root",src,"--input","in.json","--recipients",too_many,"--approved-content-digest",v["data"]["contentDigest"],"--output-root",out)[1]["error"]["code"]=="invalid_recipients"
    schema_root=private(tmp_path/"schema"); code,res=run("schema","--output-root",schema_root); assert code==0
    written=json.loads((schema_root/"newsletter.schema.json").read_text()); assert written["properties"]["schemaVersion"]["type"]=="number" and stat.S_IMODE((schema_root/"newsletter.schema.json").stat().st_mode)==0o600
