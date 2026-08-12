from __future__ import annotations
import json, os, stat, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

class AuthError(Exception): pass
class CredentialProvider:
    """Injected credential-file provider. Files must be private and are never copied."""
    def __init__(self,path=None): self.path=path or os.environ.get("GOOGLE_WORKSPACE_CREDENTIAL_FILE")
    def read_document(self):
        if not self.path: raise AuthError("credential provider is required")
        p=Path(self.path)
        try:
            info=p.lstat()
        except OSError: raise AuthError("credential file is unavailable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise AuthError("credential file must be a regular non-symlink file")
        if os.name!="nt" and stat.S_IMODE(info.st_mode)&0o077: raise AuthError("credential file must be mode 0600")
        try:return json.loads(p.read_text(encoding="utf-8"))
        except (OSError,ValueError):raise AuthError("credential file is malformed or unreadable") from None
    def load(self,alias):
        doc=self.read_document(); accounts=doc.get("accounts",doc); item=accounts.get(alias)
        if not item: raise AuthError("account alias not found")
        return dict(item)
    def token(self,alias,transport=None):
        item=self.load(alias); token=item.get("access_token")
        if token and item.get("expires_at",time.time()+60)>time.time()+30: return token,item
        if not all(item.get(k) for k in ("refresh_token","client_id","client_secret")): raise AuthError("access token expired and protected refresh material is unavailable")
        data=urllib.parse.urlencode({"grant_type":"refresh_token","refresh_token":item["refresh_token"],"client_id":item["client_id"],"client_secret":item["client_secret"]}).encode()
        req=urllib.request.Request(item.get("token_uri","https://oauth2.googleapis.com/token"),data=data,method="POST")
        try:
            with urllib.request.urlopen(req,timeout=15) as r: refreshed=json.load(r)
        except urllib.error.HTTPError as exc:
            # Provider response bodies may contain sensitive diagnostic material.
            # Classify invalid_grant from the sanitized OAuth error code only.
            if exc.code == 400:
                raise AuthError("credential refresh was rejected (invalid_grant possible): reauthorize this agent; causes include External Testing seven-day expiry, revocation, account security changes, inactivity, token limits, or an invalid/expired refresh token") from None
            raise AuthError("credential refresh was rejected by the provider; reauthorize this agent") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
            raise AuthError("credential refresh failed; retry if transient or reauthorize this agent") from None
        if not isinstance(refreshed,dict) or not refreshed.get("access_token"):
            raise AuthError("credential refresh returned no usable access token; reauthorize this agent")
        return refreshed["access_token"],item
