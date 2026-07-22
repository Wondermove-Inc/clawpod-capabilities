from __future__ import annotations
import base64, hashlib, mimetypes
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

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
    for att in compose.get("attachments",[]):
        p=Path(att["path"]); data=p.read_bytes(); mime=att.get("mimeType") or mimetypes.guess_type(p.name)[0] or "application/octet-stream"; main,sub=mime.split("/",1)
        msg.add_attachment(data,maintype=main,subtype=sub,filename=att.get("filename",p.name))
        attachments.append({"filename":att.get("filename",p.name),"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"mimeType":mime})
    raw=base64.urlsafe_b64encode(msg.as_bytes()).rstrip(b"=").decode("ascii")
    return raw,attachments
