from __future__ import annotations
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
RFC3339=re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$");FIELD=re.compile(r"^[A-Za-z0-9_(),/*.-]+$")
class ValidationError(ValueError):
 def __init__(self,code,message):self.code=code;super().__init__(message)
def validate(payload,schema=None,command=None):
 if schema:
  allowed=set(schema.get('properties',{}));unknown=set(payload)-allowed
  if unknown:raise ValidationError('INVALID_ARGUMENT','unknown input field(s): '+', '.join(sorted(unknown)))
  missing=[] if payload.get('batch') is not None else [k for k in schema.get('required',[]) if k not in payload or payload[k] in (None,'')]
  if missing:raise ValidationError('INVALID_ARGUMENT','missing required field(s): '+', '.join(missing))
  ps=schema.get('properties',{}).get('params',{});params=payload.get('params',{})
  unknownp=set(params)-set(ps.get('properties',{})) if ps.get('additionalProperties') is False else set()
  if unknownp:raise ValidationError('INVALID_ARGUMENT','unsupported provider query/identifier(s): '+', '.join(sorted(unknownp)))
  missingp=[] if payload.get('batch') is not None else [k for k in ps.get('required',[]) if not params.get(k)]
  if missingp:raise ValidationError('INVALID_ARGUMENT','missing required identifier(s): '+', '.join(missingp))
 if payload.get('pageSize',1)>500:raise ValidationError('INVALID_ARGUMENT','pageSize exceeds 500')
 if payload.get('maxPages',1)>100 or payload.get('maxItems',1)>10000:raise ValidationError('INVALID_ARGUMENT','pagination bound exceeds contract maximum')
 for x in payload.get('fields') or []:
  if len(x)>512 or not FIELD.fullmatch(x):raise ValidationError('INVALID_ARGUMENT','invalid fields expression')
 params=payload.get('params') or {};body=payload.get('body') or {}
 for key in ('timeMin','timeMax'):
  if params.get(key) and not RFC3339.fullmatch(str(params[key])):raise ValidationError('INVALID_ARGUMENT',f'{key} must be RFC 3339 with offset')
 for obj in (body,body.get('start',{}) if isinstance(body.get('start'),dict) else {},body.get('end',{}) if isinstance(body.get('end'),dict) else {}):
  if obj.get('timeZone'):
   try:ZoneInfo(obj['timeZone'])
   except ZoneInfoNotFoundError:raise ValidationError('INVALID_TIME_ZONE',f"unknown IANA time zone: {obj['timeZone']}")
 for rec in body.get('recurrence',[]):
  if not re.fullmatch(r'(?:RRULE|RDATE|EXDATE):[^\r\n]{1,2048}',rec):raise ValidationError('INVALID_RECURRENCE','invalid recurrence line')
 if len(body.get('recurrence',[]))>100:raise ValidationError('INVALID_RECURRENCE','too many recurrence lines')
 if command:
  action=command.rsplit('.',1)[-1]
  if action in ('batchModify','batchDelete') and not isinstance(body.get('ids'),list):raise ValidationError('INVALID_ARGUMENT','body.ids array is required')
  if command=='calendar.events.quickAdd' and not params.get('text'):raise ValidationError('INVALID_ARGUMENT','params.text is required')
  if command=='drive.files.export' and not params.get('mimeType'):raise ValidationError('INVALID_ARGUMENT','params.mimeType is required')
