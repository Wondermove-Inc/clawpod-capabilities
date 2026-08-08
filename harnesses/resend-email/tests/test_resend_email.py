import importlib.util, json, os, subprocess, sys
from pathlib import Path
from types import SimpleNamespace

import pytest

P=Path(__file__).parents[1]/"resend_email.py"
spec=importlib.util.spec_from_file_location("resend_email",P); r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

def argv(command,**kw):
    base=dict(command=command,base_url="https://api.resend.com",timeout=1.0,retries=0,from_address="Agent <mail@sender.test>",to='["a@example.com"]',subject="Hello",text="Body",html=None,reply_to=None,cc=None,bcc=None,attachment=[],dry_run=False,idempotency_key="operation-1",batch_size=2,concurrency=2,rate_per_second=100.0,state=None)
    base.update(kw); return SimpleNamespace(**base)

class SuccessClient:
    calls=[]
    def __init__(self,*a): pass
    def request(self,method,path,body=None,idem=None):
        self.calls.append((method,path,body,idem))
        if path=="/domains": return ({"data":[{"id":"d1","name":"sender.test","status":"verified"}]},1,None)
        return ({"id":"email_123"},1,None)

def test_fresh_agent_onboarding_has_only_irreducible_inputs():
    proc=subprocess.run([sys.executable,str(P),"onboarding"],text=True,capture_output=True,env={})
    data=json.loads(proc.stdout)["data"]; rendered=json.dumps(data).lower()
    handoff=data["secret_handoff"]
    assert data["state"]=="installed_but_unconnected"
    assert handoff["source"]=="Room, message, or an existing owner-authorized credential" and handoff["storage"]=="memory_secret" and handoff["owner_only"]
    assert handoff["gateway_parameter"]=="secretRefs" and handoff["per_run_binding"]
    assert handoff["prepare_run_binding_must_match"]
    assert handoff["environment"]=="RESEND_API_KEY" and handoff["environment_injection_only"] and not handoff["argument_allowed"]
    assert not handoff["plaintext_persistence_allowed"] and not handoff["plaintext_output_allowed"] and not handoff["protected_ui_required"]
    assert data["send_defaults"]=={"single":True,"bulk":True,"attachments":True,"recipient_domains":"any syntactically valid domain","user_configured_send_limits":False}
    for removed in ("allowed_recipient_domains","max_recipients_per_operation","max_recipients_per_day","allow_single","allow_bulk","allow_attachments","standing_policy"):
        assert removed not in rendered
    assert "resend_api_key" in rendered and "sender.readiness" in rendered and "re_fixture_secret" not in proc.stdout

def test_fresh_agent_skill_room_capture_contract_and_no_fake_ui_or_revocation_rule():
    skill=(P.parents[2]/"skills"/"resend-email"/"SKILL.md").read_text()
    lowered=skill.lower()
    assert "room or a message" in lowered and "route it immediately" in lowered and "`memory_secret`" in skill
    assert "ordinary files, normal memory, reports, prompts, or logs" in lowered
    assert "safe pointer metadata" in lowered and "owner-authorized memory-secret pointer" in lowered
    assert '"secretrefs":{"resend_api_key":"msp_..."}' in lowered
    assert "room delivery alone does not mean the key is compromised" in lowered
    assert "does not require revocation" in lowered and "independent compromise signal" in lowered
    assert "treat it as exposed and require revocation" not in lowered
    assert "protected secret-entry surface" not in lowered
    assert "never as an argument" in lowered and "original message as sensitive" in lowered

def test_removed_onboarding_and_policy_flags_are_rejected():
    for args in (["onboarding.configure"],["onboarding","--allowed-recipient-domains","example.com"],["status","--policy","policy.json"],["onboarding","--max-recipients-per-day","1"],["onboarding","--allow-bulk"]):
        proc=subprocess.run([sys.executable,str(P),*args],text=True,capture_output=True)
        out=json.loads(proc.stdout); assert proc.returncode==2 and out["error"]["code"]=="invalid_input" and not proc.stderr

def test_preview_all_valid_domains_and_body_redaction():
    for address in ("person@example.com","person@sub.example.co.uk","person@new-valid.test"):
        out=r.command(argv("preview",to=json.dumps([address])))
        assert out["data"]["preview"]["authorized"] and address in json.dumps(out) and "Body" not in json.dumps(out)
    with pytest.raises(r.HarnessError,match="invalid email"): r.command(argv("preview",to='["bad"]'))

def test_single_bulk_and_attachments_work_without_policy(tmp_path,monkeypatch):
    attachment=tmp_path/"note.txt"; attachment.write_text("attachment secret")
    SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    single=r.command(argv("send",to='["one@anywhere.example"]',attachment=[str(attachment)]))
    bulk=r.command(argv("bulk.send",to='["a@one.example","A@one.example","b@another.test"]',attachment=[str(attachment)]))
    assert single["ok"] and single["data"]["sender_verified"] and bulk["ok"] and bulk["data"]["submitted"]==2
    posts=[call for call in SuccessClient.calls if call[1]=="/emails"]
    assert len(posts)==3 and all(len(call[2]["to"])==1 for call in posts)
    rendered=json.dumps([single,bulk]); assert "attachment secret" not in rendered and "fixture_secret" not in rendered

def test_sender_domain_must_be_verified_before_submission(monkeypatch):
    class Unverified(SuccessClient):
        def request(self,method,path,body=None,idem=None):
            if path=="/domains": return ({"data":[{"name":"sender.test","status":"pending"}]},1,None)
            raise AssertionError("send called")
    monkeypatch.setattr(r,"Client",Unverified)
    with pytest.raises(r.HarnessError) as caught: r.command(argv("send"))
    assert caught.value.code=="sender_not_ready"

def private_state(tmp_path):
    root=tmp_path/"private"; root.mkdir(mode=0o700)
    return root/"onboarding.json"

def test_onboarding_test_success_state_privacy_and_precise_acceptance(tmp_path,monkeypatch):
    path=private_state(tmp_path); SuccessClient.calls=[]
    monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    recipient="Owner.Test+onboarding@example.com"
    out=r.command(argv("onboarding.test",to=recipient,state=str(path)))
    posts=[x for x in SuccessClient.calls if x[0]=="POST"]
    assert out["ok"] and out["effects"]["status"]=="email_submitted" and len(posts)==1
    assert posts[0][2]["subject"].startswith("[Resend onboarding test]") and posts[0][3].startswith("resend-onboarding-v1-")
    assert out["data"]["provider_accepted"] and not out["data"]["delivery_confirmed"]
    assert "accepted" in out["data"]["meaning"].lower() and "not confirmed" in out["data"]["meaning"].lower()
    stored=json.loads(path.read_text()); raw=path.read_text()
    assert set(stored)==r.ONBOARDING_STATE_FIELDS and path.stat().st_mode & 0o777==0o600
    assert stored["test_recipient_sha256"]==r.hashlib.sha256(recipient.lower().encode()).hexdigest()
    for forbidden in (recipient.lower(),"fixture_secret","Bearer","Provider submission check","Inbox delivery"):
        assert forbidden not in raw

def test_onboarding_test_is_stably_idempotent(tmp_path,monkeypatch):
    path=private_state(tmp_path); SuccessClient.calls=[]
    monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    first=r.command(argv("onboarding.test",to="test@example.com",state=str(path)))
    first_key=next(x[3] for x in SuccessClient.calls if x[0]=="POST")
    second=r.command(argv("onboarding.test",to="TEST@example.com",state=str(path)))
    assert second["data"]["idempotent"] and second["data"]["message_id"]==first["data"]["message_id"]
    assert len([x for x in SuccessClient.calls if x[0]=="POST"])==1
    assert first_key=="resend-onboarding-v1-"+r.digest({"sender":"mail@sender.test","test_recipient_sha256":r.hashlib.sha256(b"test@example.com").hexdigest()})

def test_onboarding_test_unverified_fails_closed_before_send_or_state(tmp_path,monkeypatch):
    path=private_state(tmp_path)
    class Unverified(SuccessClient):
        calls=[]
        def request(self,method,path,body=None,idem=None):
            self.calls.append((method,path,body,idem))
            return ({"data":[{"name":"sender.test","status":"pending"}]},1,None)
    monkeypatch.setattr(r,"Client",Unverified); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    with pytest.raises(r.HarnessError) as caught: r.command(argv("onboarding.test",to="test@example.com",state=str(path)))
    assert caught.value.code=="sender_not_ready" and [x[0] for x in Unverified.calls]==["GET"] and not path.exists()

def test_onboarding_test_provider_rejection_does_not_complete(tmp_path,monkeypatch):
    path=private_state(tmp_path)
    class Rejected(SuccessClient):
        def request(self,method,url,body=None,idem=None):
            if url=="/domains": return super().request(method,url,body,idem)
            raise r.HarnessError("backend_failure","Resend API request failed",status=422)
    monkeypatch.setattr(r,"Client",Rejected); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    with pytest.raises(r.HarnessError) as caught: r.command(argv("onboarding.test",to="test@example.com",state=str(path)))
    assert caught.value.code=="backend_failure" and not path.exists()

def test_onboarding_state_path_must_be_private_and_absolute(tmp_path,monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret"); monkeypatch.chdir(tmp_path); monkeypatch.setattr(r,"Client",SuccessClient)
    public=tmp_path/"public"; public.mkdir(mode=0o755)
    for unsafe in ("relative.json",str(public/"state.json")):
        with pytest.raises(r.HarnessError) as caught: r.command(argv("status",state=unsafe))
        assert caught.value.code=="unsafe_state_path"
    SuccessClient.calls=[]
    with pytest.raises(r.HarnessError) as caught: r.command(argv("onboarding.test",to="test@example.com",state=str(public/"state.json")))
    assert caught.value.code=="unsafe_state_path" and not any(x[0]=="POST" for x in SuccessClient.calls)

def test_status_transitions_use_credential_and_verified_private_state(tmp_path,monkeypatch):
    path=private_state(tmp_path); monkeypatch.delenv("RESEND_API_KEY",raising=False)
    assert r.command(argv("status",state=str(path)))["data"]["state"]=="installed_but_unconnected"
    monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    incomplete=r.command(argv("status",state=str(path)))["data"]
    assert incomplete["state"]=="connected_not_verified" and incomplete["onboarding"]=="onboarding_incomplete"
    SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient)
    r.command(argv("onboarding.test",to="test@example.com",state=str(path)))
    complete=r.command(argv("status",state=str(path)))["data"]
    assert complete["state"]==complete["onboarding"]=="onboarding_complete" and complete["provider_test_accepted"] and not complete["delivery_confirmed"]

def test_provider_hard_caps_remain(tmp_path):
    too_many=json.dumps([f"p{i}@example.com" for i in range(r.MAX_RECIPIENTS+1)])
    with pytest.raises(r.HarnessError,match=f"at most {r.MAX_RECIPIENTS}"): r.command(argv("bulk.send",to=too_many,dry_run=True))
    paths=[]
    for i in range(r.MAX_ATTACHMENTS+1):
        path=tmp_path/f"{i}.txt"; path.write_text("x"); paths.append(str(path))
    with pytest.raises(r.HarnessError,match=f"at most {r.MAX_ATTACHMENTS}"): r.command(argv("preview",attachment=paths))
    large=tmp_path/"large.bin"; large.write_bytes(b"x"*(r.MAX_ATTACHMENT_BYTES+1))
    with pytest.raises(r.HarnessError,match="attachment exceeds"): r.command(argv("preview",attachment=[str(large)]))

def test_parser_invalid_input_is_stable_json():
    proc=subprocess.run([sys.executable,str(P),"send","--timeout","nope"],text=True,capture_output=True)
    out=json.loads(proc.stdout); assert proc.returncode==2 and not out["ok"] and out["error"]["code"]=="invalid_input" and not proc.stderr

def test_bulk_dedupe_partial_retry_after_and_idempotency(monkeypatch):
    class Partial(SuccessClient):
        calls=[]
        def request(self,method,path,body=None,idem=None):
            if path=="/domains": return ({"data":[{"name":"sender.test","status":"verified"}]},1,None)
            self.calls.append((body["to"][0],idem))
            if body["to"][0]=="b@example.com": raise r.HarnessError("rate_limited","later",retryable=True,status=429,retry_after=2)
            return ({"id":"ok"},1,None)
    monkeypatch.setattr(r,"Client",Partial); Partial.calls=[]
    out=r.command(argv("bulk.send",to='["a@example.com","A@example.com","b@example.com"]'))
    data=out["data"]; assert not out["ok"] and data["partial_failure"] and data["submitted"]==1 and data["failed"]==1 and data["retry_safe"]
    assert len(Partial.calls)==2 and Partial.calls[0][1]!=Partial.calls[1][1]
    failed=next(x for x in data["results"] if not x["ok"]); assert failed["retry_after_seconds"]==2 and failed["idempotency_key"]

def test_recursive_secret_and_body_redaction(monkeypatch):
    raw={"authorization":"Bearer re_secretvalue","nested":["re_moresecret",{"token":"abc"}]}
    rendered=json.dumps(r.redact(raw)); assert all(x not in rendered for x in ("secretvalue","moresecret","abc"))
    SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    out=r.command(argv("send",text="uniquely-sensitive-body"))
    assert "uniquely-sensitive-body" not in json.dumps(out) and "fixture_secret" not in json.dumps(out)

def test_manifest_defaults_and_external_effect_metadata():
    manifest=json.loads((P.parent/"harness.json").read_text())
    skill_metadata=json.loads((P.parents[2]/"skills"/"resend-email"/"capability.json").read_text())
    harness_metadata=json.loads((P.parent/"capability.json").read_text())
    assert manifest["version"]=="0.1.4" and "onboarding.configure" not in manifest["commands"]
    assert "secretEnv" not in manifest
    assert skill_metadata["safety"]==harness_metadata["safety"]=={"risk":"externally-visible","approvalRequired":True}
    assert skill_metadata["linkedHarness"]=={"id":"resend-email","version":"0.1.4"}
    for command in manifest["commands"].values():
        args=set(command["inputSchema"]["properties"])
        assert not args & {"policy","allowedRecipientDomains","allowedSenderDomains","maxRecipients","allowAttachments","allowSingle","allowBulk","maxRecipientsPerDay"}
    assert "externalSideEffect" in manifest["commands"]["send"]["safetyClasses"]
    assert "externalSideEffect" in manifest["commands"]["bulk.send"]["safetyClasses"]
    test=manifest["commands"]["onboarding.test"]
    assert set(test["safetyClasses"])=={"externalSideEffect","humanAccountAction","secretUse","authReuse"}
    assert set(manifest["commands"]["verify"]["safetyClasses"])=={"readOnly","secretUse","authReuse"}
    for name in ("send","bulk.send"):
        assert "humanAccountAction" in manifest["commands"][name]["safetyClasses"]
    assert set(test["inputSchema"]["required"])=={"from","to","state"}
