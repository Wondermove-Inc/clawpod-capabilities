from __future__ import annotations
import re
from datetime import datetime
from email.utils import parseaddr
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RFC3339=re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$")
FIELD=re.compile(r"^[A-Za-z0-9_(),/*.-]+$")
HEADER=re.compile(r"^[!-9;-~]+$")
def validate(payload):
    if payload.get("pageSize",1)>500: raise ValueError("pageSize exceeds 500")
    if payload.get("fields"):
        for x in payload["fields"]:
            if len(x)>512 or not FIELD.fullmatch(x): raise ValueError("invalid fields expression")
    for key in ("timeMin","timeMax"):
        val=payload.get("params",{}).get(key)
        if val and not RFC3339.fullmatch(val): raise ValidationError("INVALID_ARGUMENT",f"{key} must be RFC 3339 with offset")
    body=payload.get("body",{})
    for k in ("timeZone",):
        if k in body:
            try: ZoneInfo(body[k])
            except ZoneInfoNotFoundError: raise ValidationError("INVALID_TIME_ZONE",f"unknown IANA time zone: {body[k]}")
    for rec in body.get("recurrence",[]):
        if not re.fullmatch(r"(?:RRULE|RDATE|EXDATE):[^\r\n]{1,2048}",rec): raise ValidationError("INVALID_RECURRENCE","invalid recurrence line")
    if len(body.get("recurrence",[]))>100: raise ValidationError("INVALID_RECURRENCE","too many recurrence lines")

class ValidationError(ValueError):
    def __init__(self,code,message): self.code=code; super().__init__(message)
