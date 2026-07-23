from __future__ import annotations
import base64, hashlib, json, mimetypes
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from .security import safe_path

def _set_deterministic_boundaries(msg:EmailMessage, seed:bytes)->None:
    """Assign stable, distinct multipart boundaries without exposing message data."""
    for index,part in enumerate(p for p in msg.walk() if p.is_multipart()):
        counter=0
        while True:
            material=seed+b"\0"+str(index).encode()+b"\0"+str(counter).encode()
            boundary="=_clawpod_"+hashlib.sha256(material).hexdigest()
            # Avoid the already encoded leaf content even though a SHA-256 collision
            # with user data is vanishingly unlikely.
            if all(boundary not in str(leaf.get_payload()) for leaf in part.walk() if not leaf.is_multipart()):
                part.set_boundary(boundary);break
            counter+=1

def compose_message(compose:dict, transfer_root:str|None=None)->tuple[str,list]:
    msg=EmailMessage(policy=SMTP)
    for field in ("from","subject"):
        val=compose.get(field)
        if val is not None:
            if "\r" in val or "\n" in val: raise ValueError("header injection")
            msg[field.title()]=val
    for field in ("to","cc","bcc","replyTo"):
        vals=compose.get(field,[])
        if any("\r" in x or "\n" in x for x in vals): raise ValueError("header injection")
        if vals: msg["Reply-To" if field=="replyTo" else field.title()]=", ".join(vals)
    headers=compose.get("headers",{})
    for k,v in headers.items():
        if not k or any(c in k for c in "\r\n:") or any(c in str(v) for c in "\r\n"): raise ValueError("invalid header")
        msg[k]=str(v)
    text=compose.get("text",""); html=compose.get("html")
    msg.set_content(text)
    if html is not None: msg.add_alternative(html,subtype="html")
    attachments=[]
    attachment_digests=[]
    for att in compose.get("attachments",[]):
        if not transfer_root: raise ValueError("transferRoot is required for attachments")
        p=safe_path(transfer_root,att["path"]); data=p.read_bytes(); mime=att.get("mimeType") or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if "/" not in mime or any(c in mime for c in "\r\n"): raise ValueError("invalid attachment MIME type")
        main,sub=mime.split("/",1); filename=att.get("filename",p.name)
        if any(c in filename for c in "\r\n"): raise ValueError("invalid attachment filename")
        msg.add_attachment(data,maintype=main,subtype=sub,filename=filename)
        content_digest=hashlib.sha256(data).hexdigest();attachment_digests.append(content_digest)
        attachments.append({"filename":filename,"size":len(data),"sha256":content_digest,"mimeType":mime})
    seed=hashlib.sha256(json.dumps({"compose":compose,"attachmentSha256":attachment_digests},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).digest()
    _set_deterministic_boundaries(msg,seed)
    raw=base64.urlsafe_b64encode(msg.as_bytes()).rstrip(b"=").decode("ascii")
    return raw,attachments
