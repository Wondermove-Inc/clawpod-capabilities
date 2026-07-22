from __future__ import annotations
import json, os, stat, time, urllib.parse, urllib.request
from pathlib import Path

class AuthError(Exception): pass
class CredentialProvider:
    """Injected credential-file provider. Files must be private and are never copied."""
    def __init__(self,path=None): self.path=path or os.environ.get("GOOGLE_WORKSPACE_CREDENTIAL_FILE")
    def load(self,alias):
        if not self.path: raise AuthError("credential provider is required")
        p=Path(self.path)
        if os.name!="nt" and stat.S_IMODE(p.stat().st_mode)&0o077: raise AuthError("credential file must be mode 0600")
        doc=json.loads(p.read_text(encoding="utf-8")); accounts=doc.get("accounts",doc); item=accounts.get(alias)
        if not item: raise AuthError("account alias not found")
        return dict(item)
    def token(self,alias,transport=None):
        item=self.load(alias); token=item.get("access_token")
        if token and item.get("expires_at",time.time()+60)>time.time()+30: return token,item
        if not all(item.get(k) for k in ("refresh_token","client_id","client_secret")): raise AuthError("access token expired and protected refresh material is unavailable")
        data=urllib.parse.urlencode({"grant_type":"refresh_token","refresh_token":item["refresh_token"],"client_id":item["client_id"],"client_secret":item["client_secret"]}).encode()
        req=urllib.request.Request(item.get("token_uri","https://oauth2.googleapis.com/token"),data=data,method="POST")
        with urllib.request.urlopen(req,timeout=15) as r: refreshed=json.load(r)
        return refreshed["access_token"],item
