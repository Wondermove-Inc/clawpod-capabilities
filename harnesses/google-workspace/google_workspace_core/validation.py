from __future__ import annotations
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
RFC3339=re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$");FIELD=re.compile(r"^[A-Za-z0-9_(),/*.-]+$");EMAIL=re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
class ValidationError(ValueError):
 def __init__(self,code,message):self.code=code;super().__init__(message)
def _check(v,s,path):
 types=s.get('type');types=[types] if isinstance(types,str) else types
 if types:
  ok=any((t=='object' and isinstance(v,dict)) or (t=='array' and isinstance(v,list)) or (t=='string' and isinstance(v,str)) or (t=='integer' and isinstance(v,int) and not isinstance(v,bool)) or (t=='boolean' and isinstance(v,bool)) or (t=='null' and v is None) for t in types)
  if not ok:raise ValidationError('INVALID_ARGUMENT',f'{path} has invalid type; expected {types}')
 if isinstance(v,str):
  if len(v)<s.get('minLength',0) or len(v)>s.get('maxLength',10**9):raise ValidationError('INVALID_ARGUMENT',f'{path} has invalid length')
  if s.get('pattern') and not re.fullmatch(s['pattern'],v):raise ValidationError('INVALID_ARGUMENT',f'{path} has invalid format')
  if s.get('format')=='email' and not EMAIL.fullmatch(v):raise ValidationError('INVALID_ARGUMENT',f'{path} must be an email address')
  if s.get('format')=='date-time' and not RFC3339.fullmatch(v):raise ValidationError('INVALID_ARGUMENT',f'{path} must be RFC 3339 with offset')
  if s.get('format')=='uri' and not urlparse(v).scheme:raise ValidationError('INVALID_ARGUMENT',f'{path} must be an absolute URI')
 if 'enum' in s and v not in s['enum']:raise ValidationError('INVALID_ARGUMENT',f'{path} must be one of {s["enum"]}')
 if isinstance(v,int) and (v<s.get('minimum',v) or v>s.get('maximum',v)):raise ValidationError('INVALID_ARGUMENT',f'{path} is outside allowed range')
 if isinstance(v,list):
  if len(v)<s.get('minItems',0) or len(v)>s.get('maxItems',10**9):raise ValidationError('INVALID_ARGUMENT',f'{path} has invalid item count')
  for i,x in enumerate(v):_check(x,s.get('items',{}),f'{path}[{i}]')
 if isinstance(v,dict):
  props=s.get('properties',{});missing=[k for k in s.get('required',[]) if k not in v or v[k] in ('',None)]
  if missing:raise ValidationError('INVALID_ARGUMENT',f'{path} missing required field(s): '+', '.join(missing))
  if len(v)<s.get('minProperties',0):raise ValidationError('INVALID_ARGUMENT',f'{path} must not be empty')
  additional=s.get('additionalProperties',True);unknown=set(v)-set(props)
  if additional is False and unknown:
   label='unsupported provider query/identifier(s)' if path=='input.params' else f'{path} unknown field(s)'
   raise ValidationError('INVALID_ARGUMENT',label+': '+', '.join(sorted(unknown)))
  for k,x in v.items():
   sub=props.get(k,additional if isinstance(additional,dict) else {})
   _check(x,sub,f'{path}.{k}')
def validate(payload,schema=None,command=None,semantic=True):
 if schema:_check(payload,schema,'input')
 if payload.get('pageSize',1)>500:raise ValidationError('INVALID_ARGUMENT','pageSize exceeds 500')
 for x in payload.get('fields') or []:
  if len(x)>512 or not FIELD.fullmatch(x):raise ValidationError('INVALID_ARGUMENT','invalid fields expression')
 params=payload.get('params') or {};body=payload.get('body') or {}
 for obj in (body,body.get('start',{}) if isinstance(body.get('start'),dict) else {},body.get('end',{}) if isinstance(body.get('end'),dict) else {}):
  if obj.get('timeZone'):
   try:ZoneInfo(obj['timeZone'])
   except ZoneInfoNotFoundError:raise ValidationError('INVALID_TIME_ZONE',f"unknown IANA time zone: {obj['timeZone']}")
 for rec in body.get('recurrence',[]):
  if not re.fullmatch(r'(?:RRULE|RDATE|EXDATE):[^\r\n]{1,2048}',rec):raise ValidationError('INVALID_RECURRENCE','invalid recurrence line')
 if not command or not semantic:return
 if command.startswith('calendar.events.') and body:
  for edge in ('start','end'):
   x=body.get(edge)
   if x and bool(x.get('date'))==bool(x.get('dateTime')):raise ValidationError('INVALID_ARGUMENT',f'body.{edge} requires exactly one of date or dateTime')
  if body.get('start') and body.get('end') and bool(body['start'].get('date'))!=bool(body['end'].get('date')):raise ValidationError('INVALID_ARGUMENT','event start/end must both be all-day or timed')
 if command=='drive.files.move':
  add=[x for x in str(params.get('addParents','')).split(',') if x];remove=[x for x in str(params.get('removeParents','')).split(',') if x]
  if len(add)!=1 or not remove or set(add)&set(remove):raise ValidationError('INVALID_ARGUMENT','Drive move requires exactly one addParents ID and distinct removeParents ID(s)')
 if command.startswith('drive.files.') or command.startswith('drive.folders.'):
  if isinstance(body.get('parents'),list) and len(body['parents'])>1:raise ValidationError('INVALID_ARGUMENT','Drive v3 files support at most one parent')
  if params.get('corpora')=='drive' and not params.get('driveId'):raise ValidationError('INVALID_ARGUMENT','corpora=drive requires driveId')
  if params.get('driveId') and params.get('includeItemsFromAllDrives') is not True and command.endswith(('.list','.search')):raise ValidationError('INVALID_ARGUMENT','driveId queries require includeItemsFromAllDrives=true')
 if command=='drive.permissions.create':
  t=body.get('type');email=body.get('emailAddress');domain=body.get('domain')
  if t in ('user','group') and not email:raise ValidationError('INVALID_ARGUMENT',f'permission type {t} requires emailAddress')
  if t=='domain' and not domain:raise ValidationError('INVALID_ARGUMENT','domain permission requires domain')
  if t=='anyone' and (email or domain):raise ValidationError('INVALID_ARGUMENT','anyone permission cannot name emailAddress or domain')
  if body.get('role')=='owner' and params.get('transferOwnership') is not True:raise ValidationError('INVALID_ARGUMENT','owner permission requires transferOwnership=true')
  if params.get('sendNotificationEmail') is None:raise ValidationError('INVALID_ARGUMENT','sendNotificationEmail must be explicit')
 if command.startswith('calendar.events.') and command.rsplit('.',1)[-1] in ('insert','patch','update','move','delete','quickAdd') and params.get('sendUpdates') is None:raise ValidationError('INVALID_ARGUMENT','sendUpdates must be explicit')
 if command.startswith('calendar.acl.') and command.rsplit('.',1)[-1] in ('insert','patch','update','delete') and params.get('sendNotifications') is None:raise ValidationError('INVALID_ARGUMENT','sendNotifications must be explicit')
