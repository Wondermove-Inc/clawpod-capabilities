from __future__ import annotations
import hashlib, json, os, re, tempfile, time
from pathlib import Path

SECRET_KEYS=re.compile(r"token|secret|authorization|code|verifier|raw|content|body|description|credentialPath",re.I)
def redact(value):
    if isinstance(value,dict): return {k:("[REDACTED]" if SECRET_KEYS.search(k) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    return value

def canonical(value)->str: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(command,account,payload)->str:
    safe={k:v for k,v in payload.items() if k not in ("account","confirm","preview","dryRun")}
    return hashlib.sha256(canonical({"command":command,"account":account,"input":safe}).encode()).hexdigest()

def safe_path(root:str,path:str, *, output=False)->Path:
    base=Path(root).expanduser().resolve(strict=True)
    target=Path(path).expanduser()
    if not target.is_absolute(): target=base/target
    lexical=Path(os.path.abspath(target))
    if base != lexical and base not in lexical.parents: raise ValueError("path escapes transfer root")
    cur=base
    for part in lexical.relative_to(base).parts:
        cur=cur/part
        if cur.exists() and cur.is_symlink(): raise ValueError("symlink paths are forbidden")
    parent=lexical.parent.resolve(strict=True)
    resolved=parent/lexical.name
    if base != resolved and base not in resolved.parents: raise ValueError("path escapes transfer root")
    return resolved

def atomic_write(path:Path,data:bytes,overwrite=False):
    if path.exists() and not overwrite: raise FileExistsError(str(path))
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",suffix=".part",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def append_audit(path,record):
    p=Path(path); p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    line=canonical(redact(record))+"\n"
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    with os.fdopen(fd,"a",encoding="utf-8") as f:f.write(line)
