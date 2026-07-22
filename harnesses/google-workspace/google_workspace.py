#!/usr/bin/env python3
"""Google Workspace CLI Harness. Emits exactly one JSON object on stdout."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from google_workspace_core.catalog import catalog
from google_workspace_core.core import run,fail

def parser():
 p=argparse.ArgumentParser(prog="google_workspace.py",description="Typed Google Workspace API harness")
 p.add_argument("command",nargs="?");p.add_argument("--json",action="store_true");p.add_argument("--input-json");p.add_argument("--account");p.add_argument("--fields",action="append");p.add_argument("--page-size",type=int);p.add_argument("--page-token");p.add_argument("--all-pages",action="store_true");p.add_argument("--max-items",type=int);p.add_argument("--max-pages",type=int);p.add_argument("--timeout-ms",type=int);p.add_argument("--dry-run",action="store_true");p.add_argument("--preview",action="store_true");p.add_argument("--confirm");p.add_argument("--request-id");p.add_argument("--if-match");p.add_argument("--idempotency-key");p.add_argument("--params");p.add_argument("--body");p.add_argument("--input-path");p.add_argument("--output-path");p.add_argument("--transfer-root");p.add_argument("--overwrite",action="store_true");p.add_argument("--resume",action="store_true");p.add_argument("--expected-sha256");p.add_argument("--batch");p.add_argument("--list-commands",action="store_true");return p
def load_json(value):
 if value is None:return None
 return json.loads(value)
def load_fields(value):
 if value is None:return None
 if len(value)==1 and value[0].lstrip().startswith('['):
  decoded=json.loads(value[0])
  if not isinstance(decoded,list) or not all(isinstance(x,str) for x in decoded):raise ValueError("fields must be a JSON array of strings")
  return decoded
 return value
def main(argv=None):
 try:
  ns=parser().parse_args(argv)
  if ns.list_commands:
   print(json.dumps({"ok":True,"schemaVersion":1,"command":"help","requestId":"help","account":None,"data":{"commands":sorted(catalog())},"effects":[],"provenance":{"provider":"google","api":"catalog","apiVersion":"1"},"warnings":[]},separators=(",",":")));return 0
  if not ns.command: parser().error("command is required")
  payload={}
  if ns.input_json:
   text=sys.stdin.read() if ns.input_json=="-" else Path(ns.input_json).read_text(encoding="utf-8");payload=json.loads(text)
   if not isinstance(payload,dict):raise ValueError("input JSON must be an object")
  mapping={"account":ns.account,"fields":load_fields(ns.fields),"pageSize":ns.page_size,"pageToken":ns.page_token,"maxItems":ns.max_items,"maxPages":ns.max_pages,"timeoutMs":ns.timeout_ms,"confirm":ns.confirm,"requestId":ns.request_id,"ifMatch":ns.if_match,"idempotencyKey":ns.idempotency_key,"params":load_json(ns.params),"body":load_json(ns.body),"inputPath":ns.input_path,"outputPath":ns.output_path,"transferRoot":ns.transfer_root,"expectedSha256":ns.expected_sha256,"batch":load_json(ns.batch)}
  for k,v in mapping.items():
   if v is not None:payload[k]=v
  for k,v in (("allPages",ns.all_pages),("dryRun",ns.dry_run),("preview",ns.preview),("overwrite",ns.overwrite),("resume",ns.resume)):
   if v:payload[k]=True
  out,code=run(ns.command,payload)
 except SystemExit: raise
 except Exception as e:
  command=getattr(locals().get("ns",None),"command",None) or "unknown";out,code=fail(command,locals().get("payload",{}),"INVALID_ARGUMENT",str(e))
 print(json.dumps(out,ensure_ascii=False,separators=(",",":")));return code
if __name__=="__main__":raise SystemExit(main())
