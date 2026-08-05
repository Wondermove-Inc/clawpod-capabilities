#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).parents[1]
COMMANDS={
 "onboarding":([],['readOnly']),"status":(["policy"],['readOnly']),
 "onboarding.configure":(["policy","allowedRecipientDomains","allowedSenderDomains","maxRecipients","allowAttachments","allowSingle","allowBulk","maxRecipientsPerDay"],['writeSafe','humanAccountAction']),
 "verify":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),
 "domains.list":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),"readiness":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),
 "sender.readiness":(["baseUrl","timeout","retries","from"],['readOnly','secretUse','authReuse']),
 "preview":(["policy","from","to","subject","text","html","replyTo","cc","bcc","attachment"],['readOnly']),
 "send":(["policy","baseUrl","timeout","retries","from","to","subject","text","html","replyTo","cc","bcc","attachment","dryRun","idempotencyKey"],['externalSideEffect','humanAccountAction','secretUse','authReuse']),
 "bulk.send":(["policy","baseUrl","timeout","retries","from","to","subject","text","html","replyTo","attachment","dryRun","idempotencyKey","batchSize","concurrency","ratePerSecond"],['externalSideEffect','humanAccountAction','secretUse','authReuse'])}
FLAGS={"policy":"--policy","baseUrl":"--base-url","timeout":"--timeout","retries":"--retries","allowedRecipientDomains":"--allowed-recipient-domains","allowedSenderDomains":"--allowed-sender-domains","maxRecipients":"--max-recipients","allowAttachments":"--allow-attachments","allowSingle":"--allow-single","allowBulk":"--allow-bulk","maxRecipientsPerDay":"--max-recipients-per-day","from":"--from","to":"--to","subject":"--subject","text":"--text","html":"--html","replyTo":"--reply-to","cc":"--cc","bcc":"--bcc","attachment":"--attachment","dryRun":"--dry-run","idempotencyKey":"--idempotency-key","batchSize":"--batch-size","concurrency":"--concurrency","ratePerSecond":"--rate-per-second"}
NUM={"timeout","retries","maxRecipients","maxRecipientsPerDay","batchSize","concurrency","ratePerSecond"}; BOOL={"allowAttachments","allowSingle","allowBulk","dryRun"}; PATH={"policy","attachment"}
required={"onboarding.configure":{"policy","allowedRecipientDomains","allowedSenderDomains","allowSingle","allowBulk","maxRecipientsPerDay"},"sender.readiness":{"from"},"preview":{"policy","from","to","subject"},"send":{"policy","from","to","subject"},"bulk.send":{"policy","from","to","subject"}}
out={"type":"object","required":["schema_version","ok","command","request_id","effects","retry","warnings"],"properties":{"schema_version":{"type":"string"},"ok":{"type":"boolean"},"command":{"type":"string"},"request_id":{"type":"string"},"effects":{"type":"object"},"retry":{"type":"object"},"warnings":{"type":"array"},"data":{},"error":{"type":"object"}},"additionalProperties":False}
commands={}
for name,(args,safety) in COMMANDS.items():
 props={}; amap=[]
 for arg in args:
  typ="boolean" if arg in BOOL else "number" if arg in NUM else "string"
  props[arg]={"type":typ}
  item={"arg":arg,"type":"booleanFlag" if arg in BOOL else "option","flag":FLAGS[arg],"valueType":typ,"optional":arg not in required.get(name,set())}
  if arg in PATH: item["valueType"]="path"; item["pathRole"]="output" if name=="onboarding.configure" and arg=="policy" else "input"
  amap.append(item)
 commands[name]={"description":name.replace("."," ")+" via guarded Resend HTTPS API.","baseArgv":[name],"safetyClasses":safety,"inputSchema":{"type":"object","required":sorted(required.get(name,set())),"properties":props,"additionalProperties":False},"outputSchema":out,"argMap":amap}
manifest={"schemaVersion":1,"kind":"openclaw.harness.v1","name":"resend-email","title":"Resend Email","description":"Guarded Resend HTTPS transactional email with protected onboarding, standing authorization policy, previews, readiness, and retry-safe per-recipient bulk delivery.","version":"0.1.0","entrypoint":"./resend_email.py","packageRoot":".","execution":{"cwd":".","timeoutMs":120000,"requiresJson":True},"whenToUse":["Onboard, verify, preview, or send transactional email with Resend"],"capabilities":["resend-https-api","protected-secret-handoff","standing-send-policy","per-recipient-bulk","stable-json-redaction"],"authModel":{"type":"bearer-token-protected-injection","storesSecrets":False,"requiresHumanAccount":True},"commands":commands}
(ROOT/"harness.json").write_text(json.dumps(manifest,indent=2)+"\n")
