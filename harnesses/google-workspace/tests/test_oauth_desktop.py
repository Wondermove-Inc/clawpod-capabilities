import hashlib,json,os,stat,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
import pytest
from google_workspace_core.oauth_desktop import desktop_login,LoginError,_client,_private_file,_missing_scopes,_canonical_scopes,_devtools_endpoint,_open_devtools

SCOPES={"openid","email","https://www.googleapis.com/auth/gmail.readonly"}
def setup_files(tmp_path):
 c=tmp_path/"client.json";c.write_text(json.dumps({"installed":{"client_id":"id x","client_secret":"SECRET","auth_uri":"https://accounts.google.com/o/oauth2/v2/auth","token_uri":"https://oauth2.googleapis.com/token"}}));c.chmod(0o600);return c

def invoke(tmp_path, callback="ok", **kw):
 setup_files(tmp_path); box={};urls=[]
 browser_result=kw.pop("browser_result",True);devtools_result=kw.pop("devtools_result",None);duplicate=kw.pop("duplicate",False);token_error=kw.pop("token_error",False);token_update=kw.pop("token_update",{});identity=kw.pop("identity",{"email":"User@Example.invalid","sub":"subject"})
 def browser(url,**_):
  urls.append(url)
  def hit():
   time.sleep(.05);q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query);redirect=q["redirect_uri"][0];state=q["state"][0]
   if callback=="mismatch":state="wrong"
   args={"state":state}
   if callback=="denied":args["error"]="access_denied"
   else:args["code"]="AUTH_CODE_SECRET"
   callback_url=redirect+"?"+urllib.parse.urlencode(args)
   try: urllib.request.urlopen(callback_url,timeout=2).read()
   except Exception: pass
   if duplicate:
    try: urllib.request.urlopen(callback_url,timeout=2).read()
    except urllib.error.HTTPError as e: box["duplicate_status"]=e.code
    except Exception: pass
  threading.Thread(target=hit,daemon=True).start();return browser_result
 def devtools(endpoint,url,timeout):
  box["devtools"]={"endpoint":endpoint,"timeout":timeout}
  if devtools_result: browser(url)
  return bool(devtools_result)
 def post(url, fields, timeout):
  box["fields"]=dict(fields)
  if token_error:raise LoginError("token endpoint rejected the request")
  d={"access_token":"ACCESS_SECRET","refresh_token":"REFRESH_SECRET","scope":" ".join(SCOPES),"expires_in":3600};d.update(token_update);return d
 def ident(token,timeout):return identity
 if devtools_result is not None:kw.setdefault("open_devtools",devtools)
 result=desktop_login(transfer_root=str(tmp_path),client_path="client.json",output_path="creds.json",alias=kw.pop("alias","work"),profiles=["gmail-read"],timeout=kw.pop("timeout",5),overwrite=kw.pop("overwrite",False),open_browser=browser,post_json=post,get_identity=ident,**kw)
 return result,box,urls

def test_success_pkce_url_encoding_and_private_output(tmp_path):
 result,box,urls=invoke(tmp_path);p=tmp_path/"creds.json";doc=json.loads(p.read_text());q=urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)
 assert result["alias"]=="work" and stat.S_IMODE(p.stat().st_mode)==0o600
 assert q["code_challenge_method"]==["S256"] and q["client_id"]==["id x"]
 expected=__import__('base64').urlsafe_b64encode(hashlib.sha256(box["fields"]["code_verifier"].encode()).digest()).rstrip(b"=").decode();assert q["code_challenge"]==[expected]
 assert doc["accounts"]["work"]["refresh_token"]=="REFRESH_SECRET"

def test_denied_and_state_mismatch(tmp_path):
 with pytest.raises(LoginError,match="denied"):invoke(tmp_path,callback="denied")
 with pytest.raises(LoginError,match="state mismatch"):invoke(tmp_path,callback="mismatch")

def test_missing_refresh_and_token_error(tmp_path):
 with pytest.raises(LoginError,match="reusable"):invoke(tmp_path,token_update={"refresh_token":""})
 with pytest.raises(LoginError,match="token endpoint"):invoke(tmp_path,token_error=True)

def test_malformed_wrong_type_and_permissions(tmp_path):
 p=tmp_path/"client.json";p.write_text("{");p.chmod(0o600)
 with pytest.raises(LoginError,match="malformed"):_client(p)
 p.write_text(json.dumps({"web":{}}));p.chmod(0o600)
 with pytest.raises(LoginError,match="Desktop"):_client(p)
 p.chmod(0o644)
 with pytest.raises(LoginError,match="0600"):_private_file(str(tmp_path),"client.json")

def test_overwrite_refusal_alias_collision_and_repeat(tmp_path):
 invoke(tmp_path)
 with pytest.raises(LoginError,match="alias already exists"):invoke(tmp_path,overwrite=True)
 # A different alias safely merges only when overwrite is explicit.
 r,_,_=invoke(tmp_path,alias="personal",overwrite=True);assert set(json.loads((tmp_path/"creds.json").read_text())["accounts"])=={"work","personal"}

def test_existing_output_permissions(tmp_path):
 setup_files(tmp_path);p=tmp_path/"creds.json";p.write_text('{"accounts":{}}');p.chmod(0o644)
 with pytest.raises(LoginError,match="0600"):
  invoke(tmp_path,alias="new",overwrite=True)

def test_scope_and_identity_validation(tmp_path):
 with pytest.raises(LoginError,match="omitted requested"):invoke(tmp_path,token_update={"scope":"openid email"})
 assert not _missing_scopes(
  {"email","https://www.googleapis.com/auth/gmail.compose"},
  {"https://www.googleapis.com/auth/userinfo.email","https://www.googleapis.com/auth/gmail.modify"},
 )
 with pytest.raises(LoginError,match="identity response"):
  invoke(tmp_path,identity={"email":"bad","sub":"x"})

def test_browser_failure_does_not_print_oauth_url(tmp_path, capsys):
 with pytest.raises(LoginError,match="could not open"):
  invoke(tmp_path,browser_result=False)
 captured=capsys.readouterr();assert "accounts.google.com" not in captured.out+captured.err

def test_duplicate_callback_is_rejected(tmp_path):
 _,box,_=invoke(tmp_path,duplicate=True);time.sleep(.2);assert box.get("duplicate_status")==409

def test_managed_browser_success_and_safe_system_fallback(tmp_path):
 result,box,_=invoke(tmp_path,managed_browser_devtools_url="http://127.0.0.1:9222",devtools_result=True,browser_result=False)
 assert result["alias"]=="work" and box["devtools"]["endpoint"]=="http://127.0.0.1:9222"
 other=tmp_path/"fallback";other.mkdir()
 result,box,urls=invoke(other,managed_browser_devtools_url="http://127.0.0.1:9222",devtools_result=False,browser_result=True)
 assert result["alias"]=="work" and len(urls)==1

def test_timeout_bounds_are_rejected_before_browser(tmp_path):
 setup_files(tmp_path)
 for timeout in (4,601):
  with pytest.raises(LoginError,match="between 5 and 600"):
   desktop_login(transfer_root=str(tmp_path),client_path="client.json",output_path="x",alias="a",profiles=[],timeout=timeout)

def test_smoke_success_is_sanitized_and_failure_keeps_credentials(tmp_path):
 def smoke(url,token,timeout):
  key="messages" if "gmail" in url else "items" if "calendar" in url else "files"
  return {key:[{"id":"REMOTE_SECRET"}]}
 result,_,_=invoke(tmp_path,smoke_tests=["gmail","calendar","drive"],smoke_request=smoke)
 assert result["smokeTests"]=={x:{"ok":True,"count":1} for x in ("gmail","calendar","drive")}
 other=tmp_path/"failed";other.mkdir()
 result,_,_=invoke(other,smoke_tests=["gmail"],smoke_request=lambda *a:(_ for _ in ()).throw(LoginError("provider detail")))
 assert result["smokeTests"]=={"gmail":{"ok":False,"error":"REQUEST_FAILED"}}
 assert (other/"creds.json").is_file() and stat.S_IMODE((other/"creds.json").stat().st_mode)==0o600

def test_bind_failure(tmp_path):
 setup_files(tmp_path)
 def bad(*a,**k):raise OSError("secret detail")
 with pytest.raises(LoginError,match="bind private"):
  desktop_login(transfer_root=str(tmp_path),client_path="client.json",output_path="x",alias="a",profiles=[],timeout=5,server_factory=bad)

def test_timeout(tmp_path):
 setup_files(tmp_path)
 with pytest.raises(LoginError,match="timed out"):
  desktop_login(transfer_root=str(tmp_path),client_path="client.json",output_path="x",alias="a",profiles=[],timeout=5,open_browser=lambda *a,**k:True)

def test_path_traversal_and_symlink(tmp_path):
 setup_files(tmp_path)
 with pytest.raises(LoginError,match="escapes"):_private_file(str(tmp_path),"../client.json")
 link=tmp_path/"link";link.symlink_to(tmp_path/"client.json")
 with pytest.raises(LoginError,match="symlink"):_private_file(str(tmp_path),"link")
