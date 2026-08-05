#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).parents[1]
COMMANDS={
 "onboarding":(["state"],['readOnly']),"status":(["state"],['readOnly']),
 "verify":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),
 "domains.list":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),"readiness":(["baseUrl","timeout","retries"],['readOnly','secretUse','authReuse']),
 "sender.readiness":(["baseUrl","timeout","retries","from"],['readOnly','secretUse','authReuse']),
 "onboarding.test":(["baseUrl","timeout","retries","from","to","state"],['externalSideEffect','humanAccountAction','secretUse','authReuse']),
 "preview":(["from","to","subject","text","html","replyTo","cc","bcc","attachment"],['readOnly']),
 "send":(["baseUrl","timeout","retries","from","to","subject","text","html","replyTo","cc","bcc","attachment","dryRun","idempotencyKey"],['externalSideEffect','humanAccountAction','secretUse','authReuse']),
 "bulk.send":(["baseUrl","timeout","retries","from","to","subject","text","html","replyTo","attachment","dryRun","idempotencyKey","batchSize","concurrency","ratePerSecond"],['externalSideEffect','humanAccountAction','secretUse','authReuse'])}
FLAGS={"baseUrl":"--base-url","timeout":"--timeout","retries":"--retries","from":"--from","to":"--to","subject":"--subject","text":"--text","html":"--html","replyTo":"--reply-to","cc":"--cc","bcc":"--bcc","attachment":"--attachment","dryRun":"--dry-run","idempotencyKey":"--idempotency-key","batchSize":"--batch-size","concurrency":"--concurrency","ratePerSecond":"--rate-per-second","state":"--state"}
NUM={"timeout","retries","batchSize","concurrency","ratePerSecond"}; BOOL={"dryRun"}; PATH={"attachment","state"}
required={"sender.readiness":{"from"},"onboarding.test":{"from","to","state"},"preview":{"from","to","subject"},"send":{"from","to","subject"},"bulk.send":{"from","to","subject"}}
out={"type":"object","required":["schema_version","ok","command","request_id","effects","retry","warnings"],"properties":{"schema_version":{"type":"string"},"ok":{"type":"boolean"},"command":{"type":"string"},"request_id":{"type":"string"},"effects":{"type":"object"},"retry":{"type":"object"},"warnings":{"type":"array"},"data":{},"error":{"type":"object"}},"additionalProperties":False}
commands={}
for name,(args,safety) in COMMANDS.items():
 props={}; amap=[]
 for arg in args:
  typ="boolean" if arg in BOOL else "number" if arg in NUM else "string"
  props[arg]={"type":typ}
  item={"arg":arg,"type":"booleanFlag" if arg in BOOL else "option","flag":FLAGS[arg],"valueType":typ,"optional":arg not in required.get(name,set())}
  if arg in PATH: item["valueType"]="path"; item["pathRole"]="output" if arg=="state" and name=="onboarding.test" else "input"
  amap.append(item)
 commands[name]={"description":name.replace("."," ")+" via guarded Resend HTTPS API.","baseArgv":[name],"safetyClasses":safety,"inputSchema":{"type":"object","required":sorted(required.get(name,set())),"properties":props,"additionalProperties":False},"outputSchema":out,"argMap":amap}
manifest={"schemaVersion":1,"kind":"openclaw.harness.v1","name":"resend-email","title":"Resend Email","description":"Guarded Resend HTTPS transactional email with protected onboarding, verified-sender enforcement, previews, and retry-safe per-recipient bulk delivery.","version":"0.1.1","entrypoint":"./resend_email.py","packageRoot":".","execution":{"cwd":".","timeoutMs":120000,"requiresJson":True},"whenToUse":["Onboard, verify, preview, or send transactional email with Resend"],"capabilities":["resend-https-api","protected-secret-handoff","verified-sender-domain","per-recipient-bulk","stable-json-redaction"],"authModel":{"type":"bearer-token-protected-injection","storesSecrets":False,"requiresHumanAccount":True},"commands":commands}
(ROOT/"harness.json").write_text(json.dumps(manifest,indent=2)+"\n")
