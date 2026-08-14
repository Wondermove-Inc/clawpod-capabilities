from __future__ import annotations
import json, os, stat, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

class AuthError(Exception):
    def __init__(self,message,code="AUTH_REQUIRED",details=None):
        super().__init__(message);self.code=code;self.details=details or {}
class CredentialProvider:
    """Injected credential-file provider. Files must be private and are never copied."""
    def __init__(self,path=None,allow_environment_path=True):
        self.explicit_path=path
        self.path=path or (os.environ.get("GOOGLE_WORKSPACE_CREDENTIAL_FILE") if allow_environment_path else None)
        self.resolved_alias=None
        self.bundle_alias=None
    def read_document(self):
        if not self.path: raise AuthError("credential provider is required")
        p=Path(self.path)
        try:
            from .bindings import _check_parent_chain
            _check_parent_chain(p)
        except Exception as exc:
            raise AuthError(str(exc),getattr(exc,"code","AUTH_REQUIRED"),getattr(exc,"details",{})) from None
        flags=os.O_RDONLY|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0)
        try:
            fd=os.open(p,flags);info=os.fstat(fd);current=p.lstat()
        except OSError: raise AuthError("credential file is unavailable") from None
        try:
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise AuthError("credential file must be a regular non-symlink file")
            if hasattr(os,"geteuid") and info.st_uid!=os.geteuid():raise AuthError("credential file is not owned by the current user")
            if os.name!="nt" and (stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1): raise AuthError("credential file must be private and have one link")
            if (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino):raise AuthError("credential file changed while opening")
            if info.st_size>64*1024*1024:raise AuthError("credential file exceeds the size limit")
            raw=b"";remaining=64*1024*1024+1
            while remaining:
                chunk=os.read(fd,min(65536,remaining))
                if not chunk:break
                raw+=chunk;remaining-=len(chunk)
            after=os.fstat(fd)
            if len(raw)>64*1024*1024 or (info.st_dev,info.st_ino,info.st_size)!=(after.st_dev,after.st_ino,after.st_size):raise AuthError("credential file changed while reading")
            return json.loads(raw.decode("utf-8"))
        except AuthError:raise
        except (OSError,UnicodeError,ValueError):raise AuthError("credential file is malformed or unreadable") from None
        finally:os.close(fd)
    def load(self,alias):
        if not self.path:
            try:
                from .bindings import resolve_binding
                selected,self.path,self.bundle_alias,_,_=resolve_binding(alias);self.resolved_alias=selected
            except Exception as exc:
                raise AuthError(str(exc),getattr(exc,"code","AUTH_REQUIRED"),getattr(exc,"details",{})) from None
        doc=self.read_document(); accounts=doc.get("accounts",doc)
        if not isinstance(accounts,dict) or not accounts:raise AuthError("credential bundle has no accounts")
        if self.bundle_alias is not None:alias=self.bundle_alias
        if alias is None:
            if len(accounts)!=1:raise AuthError("account alias is required for a multi-account credential bundle","ACCOUNT_REQUIRED")
            alias=next(iter(accounts));self.resolved_alias=alias
        item=accounts.get(alias)
        if not isinstance(item,dict): raise AuthError("account alias not found","ACCOUNT_NOT_FOUND")
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
