import io,json,stat,urllib.error
from pathlib import Path
import pytest
from google_workspace_core.core import SCOPES
from google_workspace_core.oauth_desktop import LoginError,_canonical_scopes,_devtools_endpoint,_open_devtools,_smoke


def test_managed_endpoint_is_literal_loopback_only():
 assert _devtools_endpoint("http://127.0.0.1:9222")=="http://127.0.0.1:9222"
 assert _devtools_endpoint("http://[::1]:9222")=="http://[::1]:9222"
 for value in ("https://127.0.0.1:9222","http://localhost:9222","http://10.0.0.1:9222","http://127.0.0.1","http://user@127.0.0.1:1","http://127.0.0.1:1/path"):
  with pytest.raises(LoginError,match="loopback"): _devtools_endpoint(value)


def test_devtools_new_tab_success_failure_and_encoded_target(monkeypatch):
 seen={}
 class Response:
  def __enter__(self):return io.StringIO('{"id":"tab-1"}')
  def __exit__(self,*args):pass
 def ok(req,timeout):seen.update(url=req.full_url,method=req.method,timeout=timeout);return Response()
 monkeypatch.setattr("urllib.request.urlopen",ok)
 assert _open_devtools("http://127.0.0.1:9222","https://accounts.google.com/x?a=1&b=2",99)
 assert seen["method"]=="PUT" and seen["timeout"]==5 and "accounts.google.com" in seen["url"] and "%26b%3D2" in seen["url"]
 monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:(_ for _ in ()).throw(OSError("detail")))
 assert not _open_devtools("http://127.0.0.1:9222","https://accounts.google.com/",5)


def test_gmail_settings_profile_is_available_for_filter_consent():
 assert SCOPES["gmail-settings"]==["https://www.googleapis.com/auth/gmail.settings.basic"]


def test_requested_scope_canonicalization_and_subsumption():
 assert _canonical_scopes(["email","https://www.googleapis.com/auth/userinfo.email"])==["https://www.googleapis.com/auth/userinfo.email"]
 assert _canonical_scopes(["https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/gmail.modify"])==["https://www.googleapis.com/auth/gmail.modify"]
 assert _canonical_scopes(["https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"])==["https://www.googleapis.com/auth/drive"]


def test_smoke_results_are_sanitized_counts_only():
 secrets=[]
 def request(url,token,timeout):
  secrets.append((url,token,timeout));return {"messages":[{"id":"SECRET_REMOTE_ID","snippet":"SECRET_BODY"}]}
 out=_smoke("ACCESS_SECRET",["gmail"],99,request)
 assert out=={"gmail":{"ok":True,"count":1}}
 assert "SECRET" not in json.dumps(out) and secrets[0][2]==15


def test_smoke_failure_and_invalid_shape_are_sanitized():
 def failed(*args):raise LoginError("post-login smoke test failed")
 assert _smoke("token",["drive"],5,failed)=={"drive":{"ok":False,"error":"REQUEST_FAILED"}}
 assert _smoke("token",["calendar"],5,lambda *a:{"items":"secret"})=={"calendar":{"ok":False,"error":"INVALID_RESPONSE"}}
 with pytest.raises(LoginError,match="unknown smoke"):_smoke("token",["contacts"],5,lambda *a:{})
