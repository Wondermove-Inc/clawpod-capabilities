"""One-shot Google installed-app OAuth using a private loopback receiver.

This module deliberately returns only sanitized metadata. Secret material is written
straight to the requested private credential bundle and is never logged or returned.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, re, secrets, stat, sys, threading, time, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from .security import safe_path

class LoginError(Exception): pass
_EMAIL=re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}$")
_CALLBACK="/oauth2/callback"

def _private_file(root, relative, *, existing=True):
    if not root or not relative or Path(relative).is_absolute(): raise LoginError("transferRoot and a relative path are required")
    try: p=safe_path(root,relative,output=not existing)
    except Exception as e: raise LoginError(str(e)) from None
    if existing and (not p.is_file() or p.is_symlink()): raise LoginError("input must be a regular non-symlink file")
    if p.exists() and os.name!="nt" and stat.S_IMODE(p.stat().st_mode)!=0o600: raise LoginError("file must be mode 0600")
    return p

def _client(path):
    try: doc=json.loads(path.read_text(encoding="utf-8"))
    except Exception: raise LoginError("OAuth client file is malformed") from None
    if set(doc)!={"installed"} or not isinstance(doc["installed"],dict): raise LoginError("OAuth client must be Desktop/installed type")
    c=doc["installed"]
    if not all(isinstance(c.get(k),str) and c[k] for k in ("client_id","client_secret","auth_uri","token_uri")): raise LoginError("OAuth client file is malformed")
    if not c["auth_uri"].startswith("https://accounts.google.com/") or not c["token_uri"].startswith("https://oauth2.googleapis.com/"): raise LoginError("OAuth endpoints are not approved Google endpoints")
    return c

def _post_json(url, fields, timeout):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(fields).encode("ascii"),headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
    except Exception: raise LoginError("token endpoint rejected the request") from None

def _get_identity(token, timeout):
    req=urllib.request.Request("https://openidconnect.googleapis.com/v1/userinfo",headers={"Authorization":"Bearer "+token})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
    except Exception: raise LoginError("identity endpoint rejected the request") from None

def _atomic_bundle(path, doc, overwrite):
    data=(json.dumps(doc,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    tmp=path.parent/("."+path.name+"."+secrets.token_hex(8)+".part")
    fd=None
    try:
        fd=os.open(tmp,flags,0o600)
        with os.fdopen(fd,"wb") as f: fd=None;f.write(data);f.flush();os.fsync(f.fileno())
        if overwrite:
            os.replace(tmp,path)
        else:
            try: os.link(tmp,path);tmp.unlink()
            except FileExistsError: raise LoginError("output exists; pass overwrite explicitly") from None
        os.chmod(path,0o600)
    finally:
        if fd is not None: os.close(fd)
        try: tmp.unlink()
        except FileNotFoundError: pass

def _receiver(state, timeout, server_factory=HTTPServer):
    result={};done=threading.Event(); expected_host={"127.0.0.1"}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def _reply(self,status,text):
            body=text.encode();self.send_response(status);self.send_header("Content-Type","text/plain; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            parsed=urllib.parse.urlsplit(self.path)
            host=self.headers.get("Host","").split(":",1)[0].strip("[]").lower()
            if parsed.path!=_CALLBACK or parsed.fragment or host not in expected_host: self._reply(404,"Not found");return
            q=urllib.parse.parse_qs(parsed.query,keep_blank_values=True,strict_parsing=False)
            if done.is_set(): self._reply(409,"Callback already received");return
            supplied=q.get("state",[""])[0]
            if not hmac.compare_digest(supplied,state): result["error"]="state mismatch";done.set();self._reply(400,"Invalid OAuth response");return
            if q.get("error"): result["error"]="authorization was denied";done.set();self._reply(400,"Authorization denied");return
            code=q.get("code",[""])[0]
            if not code: result["error"]="authorization response omitted code";done.set();self._reply(400,"Invalid OAuth response");return
            result["code"]=code;done.set();self._reply(200,"Authorization complete. You may close this tab.")
        def do_POST(self): self._reply(405,"Method not allowed")
    try: server=server_factory(("127.0.0.1",0),Handler)
    except Exception: raise LoginError("could not bind private loopback receiver") from None
    server.timeout=.2
    def wait():
        deadline=time.monotonic()+timeout
        while not done.is_set() and time.monotonic()<deadline: server.handle_request()
        # Briefly accept one repeated browser navigation and reject it explicitly.
        if done.is_set():
            server.timeout=.15;server.handle_request()
        server.server_close();done.set()
    thread=threading.Thread(target=wait,daemon=True);thread.start()
    return server.server_address[1],result,done

def _print_url(message): print(message,file=sys.stderr)

def _missing_scopes(requested, granted):
    """Compare provider grants after Google's documented scope canonicalization."""
    equivalents={
        "email":{"email","https://www.googleapis.com/auth/userinfo.email"},
        "profile":{"profile","https://www.googleapis.com/auth/userinfo.profile"},
    }
    broader={
        "https://www.googleapis.com/auth/gmail.compose":{"https://www.googleapis.com/auth/gmail.modify","https://mail.google.com/"},
        "https://www.googleapis.com/auth/gmail.readonly":{"https://www.googleapis.com/auth/gmail.modify","https://mail.google.com/"},
        "https://www.googleapis.com/auth/calendar.events":{"https://www.googleapis.com/auth/calendar"},
        "https://www.googleapis.com/auth/calendar.readonly":{"https://www.googleapis.com/auth/calendar"},
        "https://www.googleapis.com/auth/drive.file":{"https://www.googleapis.com/auth/drive"},
        "https://www.googleapis.com/auth/drive.readonly":{"https://www.googleapis.com/auth/drive"},
    }
    return {scope for scope in requested if not (equivalents.get(scope,{scope})|broader.get(scope,set())) & granted}

def desktop_login(*, transfer_root, client_path, output_path, alias, profiles, timeout=180, overwrite=False,
                  open_browser=webbrowser.open, print_url=_print_url, post_json=_post_json, get_identity=_get_identity,
                  server_factory=HTTPServer):
    if not isinstance(alias,str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}",alias): raise LoginError("invalid account alias")
    if not isinstance(timeout,(int,float)) or not 5<=timeout<=600: raise LoginError("timeout must be between 5 and 600 seconds")
    cp=_private_file(transfer_root,client_path);op=_private_file(transfer_root,output_path,existing=False);c=_client(cp)
    # Profiles are the public names used by core.SCOPES; keep the dependency local to avoid a cycle.
    from .core import SCOPES
    try: requested=sorted(set(sum((SCOPES[p] for p in profiles),[])))
    except Exception: raise LoginError("unknown scope profile") from None
    requested=sorted(set(requested+SCOPES["identity"]))
    verifier=secrets.token_urlsafe(64);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode();state=secrets.token_urlsafe(32)
    port,result,done=_receiver(state,timeout,server_factory);redirect=f"http://127.0.0.1:{port}{_CALLBACK}"
    query={"client_id":c["client_id"],"redirect_uri":redirect,"response_type":"code","scope":" ".join(requested),"access_type":"offline","prompt":"consent","state":state,"code_challenge":challenge,"code_challenge_method":"S256"}
    url=c["auth_uri"]+"?"+urllib.parse.urlencode(query,quote_via=urllib.parse.quote)
    try: opened=bool(open_browser(url,new=1,autoraise=True))
    except Exception: opened=False
    if not opened: print_url("Open this Google authorization URL in your browser:\n"+url)
    if not done.wait(timeout+.5): raise LoginError("authorization timed out")
    if result.get("error"): raise LoginError(result["error"])
    code=result.pop("code",None)
    if not code: raise LoginError("authorization timed out")
    token=post_json(c["token_uri"],{"code":code,"client_id":c["client_id"],"client_secret":c["client_secret"],"redirect_uri":redirect,"grant_type":"authorization_code","code_verifier":verifier},min(timeout,30))
    if not isinstance(token,dict) or not all(isinstance(token.get(k),str) and token[k] for k in ("access_token","refresh_token")): raise LoginError("token response did not include reusable credentials")
    granted=set((token.get("scope") or "").split())
    if _missing_scopes(requested,granted): raise LoginError("token response omitted requested scopes")
    ident=get_identity(token["access_token"],min(timeout,30));email=ident.get("email") if isinstance(ident,dict) else None;sub=ident.get("sub") if isinstance(ident,dict) else None
    if not isinstance(email,str) or not _EMAIL.fullmatch(email) or not isinstance(sub,str) or not 1<=len(sub)<=255: raise LoginError("identity response was invalid")
    existing={"accounts":{}}
    if op.exists():
        if os.name!="nt" and stat.S_IMODE(op.stat().st_mode)!=0o600: raise LoginError("existing output must be mode 0600")
        try: existing=json.loads(op.read_text()); accounts=existing.get("accounts",existing)
        except Exception: raise LoginError("existing credential bundle is malformed") from None
        if alias in accounts: raise LoginError("account alias already exists")
        if "accounts" not in existing: existing={"accounts":accounts}
    accounts=existing.setdefault("accounts",{})
    accounts[alias]={"access_token":token["access_token"],"refresh_token":token["refresh_token"],"client_id":c["client_id"],"client_secret":c["client_secret"],"token_uri":c["token_uri"],"expires_at":time.time()+int(token.get("expires_in",3600)),"email":email.lower(),"subject_hash":hashlib.sha256(sub.encode()).hexdigest(),"scopes":sorted(granted)}
    _atomic_bundle(op,existing,overwrite)
    return {"alias":alias,"email":email.lower(),"subject_hash":accounts[alias]["subject_hash"],"scopes":sorted(granted),"credentialPath":str(Path(output_path))}
