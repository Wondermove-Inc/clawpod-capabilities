import importlib.util, json, os, stat, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

P=Path(__file__).parents[1]/"resend_email.py"
spec=importlib.util.spec_from_file_location("resend_email",P); r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

def private_policy(tmp_path, **overrides):
    root=tmp_path/"private"; root.mkdir(mode=0o700,parents=True)
    policy={"schema_version":1,"allowed_recipient_domains":["example.com"],"allowed_sender_domains":["sender.test"],"max_recipients_per_operation":100,"allow_attachments":False,"allow_single":True,"allow_bulk":True,"max_recipients_per_day":100,"usage_state_path":str(root/"usage.json"),"created_by":"test"}; policy.update(overrides)
    path=root/"policy.json"; path.write_text(json.dumps(policy)); path.chmod(0o600); return path

def argv(command,policy,**kw):
    base=dict(command=command,policy=str(policy),base_url="https://api.resend.com",timeout=1.0,retries=0,allowed_recipient_domains=None,allowed_sender_domains=None,max_recipients=100,allow_attachments=False,allow_single=False,allow_bulk=False,max_recipients_per_day=None,from_address="Agent <mail@sender.test>",to='["a@example.com"]',subject="Hello",text="Body",html=None,reply_to=None,cc=None,bcc=None,attachment=[],dry_run=False,idempotency_key="operation-1",batch_size=2,concurrency=2,rate_per_second=100.0)
    base.update(kw); return SimpleNamespace(**base)

class SuccessClient:
    calls=[]
    def __init__(self,*a): pass
    def request(self,method,path,body=None,idem=None):
        self.calls.append((method,path,body,idem)); return ({"id":"email_123"},1,None)

def test_onboarding_discoverability_and_no_secret(tmp_path):
    proc=subprocess.run([sys.executable,str(P),"onboarding"],text=True,capture_output=True,env={})
    data=json.loads(proc.stdout)["data"]
    assert data["state"]=="installed_but_unconnected" and data["secret_handoff"]["protected_storage_only"]
    assert "RESEND_API_KEY" in data["secret_handoff"]["environment"] and "re_" not in proc.stdout

def test_configure_private_policy_and_status(tmp_path):
    root=tmp_path/"private"; root.mkdir(mode=0o700); path=root/"policy.json"
    a=argv("onboarding.configure",path,allowed_recipient_domains="example.com",allowed_sender_domains="sender.test",allow_single=True,max_recipients_per_day=25)
    out=r.command(a); assert out["ok"] and stat.S_IMODE(path.stat().st_mode)==0o600 and "api" not in path.read_text().lower()
    saved=json.loads(path.read_text()); assert saved["allow_single"] and not saved["allow_bulk"] and saved["max_recipients_per_day"]==25

def test_preview_success_and_invalid_input(tmp_path):
    policy=private_policy(tmp_path)
    out=r.command(argv("preview",policy)); assert out["data"]["preview"]["authorized"] and "Body" not in json.dumps(out)
    try: r.command(argv("preview",policy,to='["bad"]'))
    except r.HarnessError as exc: assert exc.code=="invalid_input"
    else: assert False

def test_parser_invalid_input_is_stable_json():
    proc=subprocess.run([sys.executable,str(P),"send","--timeout","nope"],text=True,capture_output=True)
    out=json.loads(proc.stdout); assert proc.returncode==2 and not out["ok"] and out["error"]["code"]=="invalid_input" and not proc.stderr

def test_policy_violation_fails_closed(tmp_path):
    policy=private_policy(tmp_path)
    try: r.command(argv("send",policy,to='["x@outside.test"]'))
    except r.HarnessError as exc: assert exc.code=="policy_violation"
    else: assert False

def test_single_and_bulk_permissions_fail_before_backend(tmp_path,monkeypatch):
    class Never:
        def __init__(self,*a): pass
        def request(self,*a,**k): raise AssertionError("backend called")
    monkeypatch.setattr(r,"Client",Never)
    single=private_policy(tmp_path/"single",allow_single=False)
    with __import__("pytest").raises(r.HarnessError,match="single send is disabled"): r.command(argv("send",single))
    bulk=private_policy(tmp_path/"bulk",allow_bulk=False)
    with __import__("pytest").raises(r.HarnessError,match="bulk send is disabled"): r.command(argv("bulk.send",bulk))

def test_send_success_and_stable_idempotency(tmp_path,monkeypatch):
    policy=private_policy(tmp_path); SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    out=r.command(argv("send",policy)); assert out["data"]["id"]=="email_123" and SuccessClient.calls[0][3]=="operation-1"
    assert "fixture_secret" not in json.dumps(out)

def test_daily_limit_dry_run_and_rollover(tmp_path,monkeypatch):
    policy=private_policy(tmp_path,max_recipients_per_day=1); SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient)
    r.command(argv("send",policy,dry_run=True)); assert not Path(json.loads(policy.read_text())["usage_state_path"]).exists()
    r.command(argv("send",policy))
    with __import__("pytest").raises(r.HarnessError) as caught: r.command(argv("send",policy))
    assert caught.value.code=="daily_quota_exhausted" and len(SuccessClient.calls)==1
    usage=Path(json.loads(policy.read_text())["usage_state_path"]); state=json.loads(usage.read_text()); state["date"]="2000-01-01"; usage.write_text(json.dumps(state)); usage.chmod(0o600)
    r.command(argv("send",policy)); assert len(SuccessClient.calls)==2

def test_concurrent_reservations_cannot_overrun_quota(tmp_path,monkeypatch):
    policy=private_policy(tmp_path,max_recipients_per_day=1); entered=threading.Event(); release=threading.Event(); calls=[]
    class Blocking:
        def __init__(self,*a): pass
        def request(self,*a,**k): calls.append(1); entered.set(); release.wait(2); return ({"id":"ok"},1,None)
    monkeypatch.setattr(r,"Client",Blocking)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(r.command,argv("send",policy)); assert entered.wait(1)
        second=pool.submit(r.command,argv("send",policy,idempotency_key="operation-2"))
        with __import__("pytest").raises(r.HarnessError) as caught: second.result(timeout=1)
        assert caught.value.code=="daily_quota_exhausted" and len(calls)==1
        release.set(); assert first.result(timeout=1)["ok"]

def test_backend_failure_and_429_shape(tmp_path,monkeypatch):
    policy=private_policy(tmp_path)
    class Failing:
        def __init__(self,*a): pass
        def request(self,*a,**k): raise r.HarnessError("rate_limited","slow down",retryable=True,status=429,retry_after=3)
    monkeypatch.setattr(r,"Client",Failing)
    try: r.command(argv("send",policy))
    except r.HarnessError as exc: assert exc.status==429 and exc.retry_after==3 and exc.retryable
    class Backend(Failing):
        def request(self,*a,**k): raise r.HarnessError("backend_failure","unavailable",retryable=True,status=503)
    monkeypatch.setattr(r,"Client",Backend)
    try: r.command(argv("send",policy))
    except r.HarnessError as exc: assert exc.code=="backend_failure" and exc.retryable
    class Timeout(Failing):
        def request(self,*a,**k): raise r.HarnessError("transport_failure","timed out",retryable=True)
    monkeypatch.setattr(r,"Client",Timeout)
    try: r.command(argv("send",policy))
    except r.HarnessError as exc: assert exc.code=="transport_failure" and exc.retryable

def test_bulk_dedupe_partial_retry_safety_and_per_recipient_idempotency(tmp_path,monkeypatch):
    policy=private_policy(tmp_path)
    class Partial:
        calls=[]
        def __init__(self,*a): pass
        def request(self,method,path,body=None,idem=None):
            self.calls.append((body["to"][0],idem))
            if body["to"][0]=="b@example.com": raise r.HarnessError("rate_limited","later",retryable=True,status=429,retry_after=2)
            return ({"id":"ok"},1,None)
    monkeypatch.setattr(r,"Client",Partial)
    a=argv("bulk.send",policy,to='["a@example.com","A@example.com","b@example.com"]')
    out=r.command(a); data=out["data"]
    assert not out["ok"] and data["partial_failure"] and data["submitted"]==1 and data["failed"]==1 and data["retry_safe"]
    assert len(Partial.calls)==2 and Partial.calls[0][1]!=Partial.calls[1][1]
    failed=next(x for x in data["results"] if not x["ok"]); assert failed["retry_after_seconds"]==2 and failed["idempotency_key"]
    usage=json.loads(Path(json.loads(policy.read_text())["usage_state_path"]).read_text()); assert usage["used"]==1 and not usage["reservations"]

def test_unsafe_usage_state_path_fails_before_backend(tmp_path,monkeypatch):
    policy=private_policy(tmp_path); root=policy.parent; target=root/"target"; target.write_text("{}"); target.chmod(0o600)
    usage=root/"usage.json"; usage.symlink_to(target)
    class Never:
        def __init__(self,*a): pass
        def request(self,*a,**k): raise AssertionError("backend called")
    monkeypatch.setattr(r,"Client",Never)
    with __import__("pytest").raises(r.HarnessError) as caught: r.command(argv("send",policy))
    assert caught.value.code=="unsafe_storage"

def test_usage_state_and_errors_leak_no_secret_or_body(tmp_path,monkeypatch):
    policy=private_policy(tmp_path); SuccessClient.calls=[]; monkeypatch.setattr(r,"Client",SuccessClient); monkeypatch.setenv("RESEND_API_KEY","re_fixture_secret")
    out=r.command(argv("send",policy,text="uniquely-sensitive-body")); usage=Path(json.loads(policy.read_text())["usage_state_path"])
    rendered=json.dumps(out)+usage.read_text()+usage.with_name(usage.name+".lock").read_text()
    assert "uniquely-sensitive-body" not in rendered and "fixture_secret" not in rendered and "a@example.com" not in usage.read_text()

def test_recursive_redaction():
    raw={"authorization":"Bearer re_secretvalue","nested":["re_moresecret",{"token":"abc"}]}
    rendered=json.dumps(r.redact(raw)); assert "secretvalue" not in rendered and "moresecret" not in rendered and "abc" not in rendered

def test_manifest_uses_gateway_classes_and_number_not_integer():
    manifest=json.loads((P.parent/"harness.json").read_text())
    allowed={"readOnly","writeSafe","modifiesSource","destructive","secretUse","externalSideEffect","authReuse","humanAccountAction"}
    for command in manifest["commands"].values():
        assert set(command["safetyClasses"])<=allowed
        for prop in command["inputSchema"]["properties"].values(): assert prop.get("type")!="integer"
    assert "externalSideEffect" in manifest["commands"]["send"]["safetyClasses"]
    configure=manifest["commands"]["onboarding.configure"]["inputSchema"]
    assert {"allowSingle","allowBulk","maxRecipientsPerDay"}<=set(configure["required"])
    assert configure["properties"]["allowSingle"]["type"]=="boolean" and configure["properties"]["maxRecipientsPerDay"]["type"]=="number"
