"""Deterministic, offline semantic authoring pipeline for Memory Graph v0.10."""
from __future__ import annotations
import hashlib, html, json, os, re, tempfile, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_INPUT="memory-graph-extractor-input/v1"
SCHEMA_PROPOSAL="memory-graph-extractor-proposals/v1"
SCHEMA_APPROVAL="memory-graph-approval-manifest/v1"
SCHEMA_SNAPSHOT="memory-graph-semantic-snapshot/v1"
TYPES={"Person","Project","Decision","Event"}; PREDICATES={"participates_in","decided","caused","supersedes"}
ENDPOINTS={"participates_in":({"Person"},{"Project","Event"}),"decided":({"Person"},{"Decision"}),"caused":({"Decision","Event"},{"Event"}),"supersedes":({"Decision","Event","Project"},{"Decision","Event","Project"})}
HASH=re.compile(r"^[0-9a-f]{64}$"); SAFE_ID=re.compile(r"^[a-z][a-z0-9_-]{0,31}:[A-Za-z0-9._:-]{1,128}$")
REVIEWER_ID=re.compile(r"^human:[A-Za-z0-9._:-]{1,128}$")
SECRET=re.compile(r"(?i)(?:sk|api[_-]?key|token|password|secret)[_:= -]+[A-Za-z0-9_./+\-=]{12,}")
# Closed causal phrases.  Bare Korean nouns such as "원인" and English words
# such as "result" are not evidence that the claim asserts a directed cause.
CAUSAL=re.compile(r"(?i)(?:\b(?:directly\s+)?caused\b|\bbecause\s+of\b|\bled\s+to\b|\bresulted\s+in\b|\bdue\s+to\b|(?:직접\s*)?원인이\s*(?:되어|돼|되었|됐다)|때문에|초래(?:했|하였|하여|함))")

def causal_review_bound(proposal, decision):
 """Require the reviewer to bind causal approval to the exact claim digest."""
 if proposal.get("payload",{}).get("predicate")!="caused": return True
 expected="causal-evidence:"+str(proposal.get("source",{}).get("claim_content_hash",""))
 return decision is not None and decision.get("lifecycle")=="approved" and expected in decision.get("reason","").split()

def canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def sha(v): return hashlib.sha256(v if isinstance(v,bytes) else canon(v)).hexdigest()
def fail(api,code,msg,**details): raise api["error"](code,msg,details)
def closed(v, keys): return isinstance(v,dict) and set(v)==set(keys)
def canonical_path(value):
 if not isinstance(value,str) or value!=unicodedata.normalize("NFC",value) or "\\" in value: return None
 p=Path(value)
 if p.is_absolute() or re.match(r"^[A-Za-z]:",value) or p.parts!=("memory",p.name) or p.suffix!=".md" or any(x in {".",".."} for x in p.parts): return None
 return p.as_posix()

def fresh(api,root,agent,workspace):
 p=api["plan"](api["inspect"](root,"reject"),False,api["namespace"](agent,root,workspace)); return p,{c["claim_id"]:c for c in p["claims"]}
def source_hash(root,path): return hashlib.sha256((root/path).read_bytes()).hexdigest()
def atomic_write(output, data):
 """Durably replace a regular output without exposing a partial document."""
 output.parent.mkdir(parents=False,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix="."+output.name+".",suffix=".tmp",dir=output.parent)
 try:
  with os.fdopen(fd,"wb") as stream:
   stream.write(data); stream.flush(); os.fsync(stream.fileno())
  os.chmod(tmp,0o600); os.replace(tmp,output)
  directory=os.open(output.parent,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
  try: os.fsync(directory)
  finally: os.close(directory)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass
def proposal_id(namespace, raw, extractor):
 material={k:raw[k] for k in ("kind","claim_id","source","payload","basis")}
 return "proposal:"+sha({"namespace":namespace,"proposal":material,"extractor":extractor})[:40]

def normalized_time(value):
 if value is None: return None
 if not closed(value,{"start","end","timezone","time_unknown"}) or not isinstance(value["time_unknown"],bool): return False
 if value["time_unknown"] is True:
  return value if value["start"] is None and value["end"] is None and value["timezone"] is None else False
 if not isinstance(value["timezone"],str) or value["timezone"] in {"UTC","Etc/UTC"}: return False
 try: zone=ZoneInfo(value["timezone"])
 except (ZoneInfoNotFoundError,ValueError): return False
 parsed=[]
 for raw in (value["start"],value["end"]):
  if raw is None: parsed.append(None); continue
  if not isinstance(raw,str): return False
  try: dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
  except ValueError: return False
  if dt.tzinfo is None or dt.utcoffset()!=zone.utcoffset(dt): return False
  parsed.append(dt.astimezone(timezone.utc))
 if parsed[0] is None and parsed[1] is None or parsed[0] and parsed[1] and parsed[0]>parsed[1]: return False
 iso=lambda dt: dt.isoformat().replace("+00:00","Z") if dt else None
 return {"start":iso(parsed[0]),"end":iso(parsed[1]),"timezone":value["timezone"],"time_unknown":False}

def extractor_input(root,agent,workspace,api,limit=20,cursor=None):
 if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=20: fail(api,"invalid_claim_limit","claim limit must be an integer from 1..20")
 plan,claims=fresh(api,root,agent,workspace); ordered=sorted(claims.values(),key=lambda c:(c["path"],c["line"],c["claim_id"]))
 start=0
 if cursor:
  matches=[i for i,c in enumerate(ordered) if sha({"snapshot":plan["snapshot_hash"],"claim_id":c["claim_id"]})==cursor]
  if len(matches)!=1: fail(api,"invalid_extractor_cursor","cursor is stale or does not belong to this snapshot")
  start=matches[0]+1
 selected=ordered[start:start+limit]
 endpoints=[]
 for e in sorted(plan.get("semantic_entities",[]),key=lambda x:(x.get("type",""),x.get("entity_id",""))):
  if e.get("type") in TYPES and SAFE_ID.fullmatch(e.get("entity_id","")): endpoints.append({"type":e["type"],"entity_id":e["entity_id"]})
 endpoints=endpoints[:100]
 rows=[]
 for c in selected:
  value=c.get("value","")
  if SECRET.search(value): value="[REDACTED]"
  rows.append({"claim_id":c["claim_id"],"path":c["path"],"line_start":c["line"],"line_end":c["line"],"source_content_hash":source_hash(root,c["path"]),"claim_content_hash":c["content_hash"],"claim_text":value})
 next_cursor=sha({"snapshot":plan["snapshot_hash"],"claim_id":selected[-1]["claim_id"]}) if selected and start+len(selected)<len(ordered) else None
 out={"schema_version":SCHEMA_INPUT,"namespace":plan["ownership"]["namespace"],"source_snapshot_hash":plan["snapshot_hash"],"source_digest":plan["source_digest"],"claims":rows,"page":{"cursor":cursor,"next_cursor":next_cursor,"offset":start,"count":len(selected),"total":len(ordered),"remaining":max(0,len(ordered)-start-len(selected))},"known_endpoints":endpoints,"constraints":{"may_invent_entities":False,"network_allowed":False,"max_claims":20}}
 out["bundle_hash"]=sha(out); return out

def assemble_extractor_pages(pages,api):
 """Seal a complete, single-snapshot extraction manifest from cursor pages."""
 if not isinstance(pages,list) or not pages: fail(api,"incomplete_extractor_batch","at least one extractor page is required")
 claims=[]; hashes=[]; expected_cursor=None; identity=None
 for index,page in enumerate(pages):
  if not isinstance(page,dict) or page.get("bundle_hash")!=sha({k:v for k,v in page.items() if k!="bundle_hash"}): fail(api,"invalid_extractor_page","extractor page is malformed or tampered",page_index=index)
  current=(page.get("namespace"),page.get("source_snapshot_hash"),page.get("source_digest"))
  if identity is None: identity=current
  if current!=identity: fail(api,"mixed_extractor_snapshot","all pages must bind one namespace and source snapshot",page_index=index)
  meta=page.get("page",{})
  if meta.get("cursor")!=expected_cursor or meta.get("offset")!=len(claims) or meta.get("count")!=len(page.get("claims",[])): fail(api,"extractor_page_discontinuity","cursor chain or page offset is discontinuous",page_index=index)
  claims.extend(page["claims"]); hashes.append(page["bundle_hash"]); expected_cursor=meta.get("next_cursor")
 if expected_cursor is not None or pages[-1]["page"].get("remaining")!=0 or pages[-1]["page"].get("total")!=len(claims): fail(api,"incomplete_extractor_batch","final page must prove complete cursor exhaustion")
 ids=[x.get("claim_id") for x in claims]
 if len(ids)!=len(set(ids)): fail(api,"duplicate_extractor_claim","claim IDs must occur exactly once across the batch")
 out={"schema_version":"memory-graph-extractor-batch/v1","namespace":identity[0],"source_snapshot_hash":identity[1],"source_digest":identity[2],"page_hashes":hashes,"claim_ids":ids,"claim_count":len(ids),"complete":True}
 out["batch_hash"]=sha(out); return out

def validate_proposals(root,bundle,agent,workspace,api):
 required={"schema_version","namespace","source_snapshot_hash","source_digest","extractor","proposals"}
 if not closed(bundle,required) or bundle["schema_version"]!=SCHEMA_PROPOSAL: fail(api,"malformed_model_output","extractor proposal bundle has unknown/missing fields")
 plan,claims=fresh(api,root,agent,workspace)
 if bundle["namespace"]!=plan["ownership"]["namespace"]: fail(api,"namespace_mismatch","wrong namespace")
 if bundle["source_snapshot_hash"]!=plan["snapshot_hash"] or bundle["source_digest"]!=plan["source_digest"]: fail(api,"stale_hashes","source snapshot is stale")
 ex=bundle["extractor"]
 if not closed(ex,{"extractor_id","extractor_version","config_hash"}) or not HASH.fullmatch(str(ex["config_hash"])): fail(api,"invalid_extractor","invalid extractor metadata")
 entities=[]; assertions=[]; quarantine=[]
 if not isinstance(bundle["proposals"],list): fail(api,"malformed_model_output","proposals must be an array")
 seen_ids=set()
 for raw in bundle["proposals"]:
  if not isinstance(raw,dict) or set(raw)!={"proposal_id","kind","claim_id","source","payload","basis"}: continue
  expected=proposal_id(bundle["namespace"],raw,ex)
  if raw["proposal_id"]!=expected: fail(api,"unstable_proposal_id","proposal_id must equal the deterministic content-derived ID",expected_proposal_id=expected)
  if expected in seen_ids: fail(api,"duplicate_proposal_id","duplicate proposal IDs are ambiguous")
  seen_ids.add(expected)
 known_endpoints={(e.get("type"),e.get("entity_id")) for e in plan.get("semantic_entities",[]) if e.get("type") in TYPES and SAFE_ID.fullmatch(str(e.get("entity_id","")))}
 # An entity ID is an identity key, not merely a (type, ID) tuple. If the
 # extractor proposes incompatible identities for the same key, quarantine
 # every alternative rather than letting proposal ordering pick a winner.
 entity_identities={}
 for entity_type,entity_id in known_endpoints: entity_identities.setdefault(entity_id,set()).add(entity_type)
 for raw in bundle["proposals"]:
  if isinstance(raw,dict) and raw.get("kind")=="entity" and isinstance(raw.get("payload"),dict):
   p=raw["payload"]
   if closed(p,{"entity_id","type","temporal"}) and p["type"] in TYPES and SAFE_ID.fullmatch(str(p["entity_id"])): entity_identities.setdefault(p["entity_id"],set()).add(p["type"])
 conflicted_entity_ids={entity_id for entity_id,types in entity_identities.items() if len(types)>1}
 for entity_id,types in entity_identities.items():
  if len(types)==1: known_endpoints.add((next(iter(types)),entity_id))
 for raw in bundle["proposals"]:
  if not isinstance(raw,dict) or set(raw)!={"proposal_id","kind","claim_id","source","payload","basis"}: quarantine.append({"proposal_id":str(raw.get("proposal_id","?")) if isinstance(raw,dict) else "?","reason_code":"invalid_shape"}); continue
  cid=raw["claim_id"]; c=claims.get(cid); s=raw["source"]
  if not c or not closed(s,{"path","line_start","line_end","source_content_hash","claim_content_hash"}) or canonical_path(s.get("path"))!=c["path"] or s!={"path":c["path"],"line_start":c["line"],"line_end":c["line"],"source_content_hash":source_hash(root,c["path"]),"claim_content_hash":c["content_hash"]}: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"stale_provenance"}); continue
  if SECRET.search(json.dumps(raw,ensure_ascii=False)): quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"secret_like_input","redacted":True}); continue
  p=raw["payload"]
  temporal=normalized_time(p.get("temporal") if isinstance(p,dict) else None)
  if raw["kind"]=="entity" and isinstance(p,dict) and p.get("entity_id") in conflicted_entity_ids: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"entity_identity_conflict"}); continue
  if raw["kind"]=="entity" and closed(p,{"entity_id","type","temporal"}) and p["type"] in TYPES and SAFE_ID.fullmatch(p["entity_id"]) and temporal is not False: entities.append({**raw,"payload":{**p,"temporal":temporal},"lifecycle":"candidate","review":None,"extractor":ex})
  elif raw["kind"]=="assertion" and closed(p,{"subject","predicate","object","valid_time"}) and p["predicate"] in PREDICATES and closed(p["subject"],{"entity_id","type"}) and closed(p["object"],{"entity_id","type"}):
   subj,obj=p["subject"],p["object"]; domains=ENDPOINTS[p["predicate"]]
   if not SAFE_ID.fullmatch(str(subj["entity_id"])) or not SAFE_ID.fullmatch(str(obj["entity_id"])) or subj["type"] not in domains[0] or obj["type"] not in domains[1]: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"invalid_endpoints"}); continue
   if (subj["type"],subj["entity_id"]) not in known_endpoints or (obj["type"],obj["entity_id"]) not in known_endpoints: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"dangling_endpoints"}); continue
   if p["predicate"]=="caused" and not CAUSAL.search(c.get("value","")): quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"chronology_only_cause"}); continue
   valid_time=normalized_time(p["valid_time"])
   if valid_time is False: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"invalid_temporal_interval"}); continue
   assertions.append({**raw,"payload":{**p,"valid_time":valid_time},"lifecycle":"candidate","review":None,"extractor":ex})
  else: quarantine.append({"proposal_id":raw["proposal_id"],"reason_code":"invalid_payload"})
 for arr in (entities,assertions): arr.sort(key=lambda x:x["proposal_id"])
 result={"schema_version":"memory-graph-validated-proposals/v1","namespace":bundle["namespace"],"source_snapshot_hash":plan["snapshot_hash"],"source_digest":plan["source_digest"],"entity_proposals":entities,"assertion_proposals":assertions,"quarantine":sorted(quarantine,key=lambda x:(x["proposal_id"],x["reason_code"])),"aliases_inert":True,"identity_merge_performed":False}
 latest_mtime=max((root/c["path"]).stat().st_mtime for c in claims.values())
 if latest_mtime > datetime.now(timezone.utc).timestamp()+300: fail(api,"source_clock_skew","canonical source mtime is more than 5 minutes in the future")
 result["source_latest_mtime"]=datetime.fromtimestamp(latest_mtime,timezone.utc).isoformat().replace("+00:00","Z")
 result["validated_hash"]=sha(result); return result

def review_queue(validated):
 q=[{"proposal_id":x["proposal_id"],"kind":x["kind"],"claim_id":x["claim_id"],"basis":x["basis"],"lifecycle":x["lifecycle"]} for x in validated["entity_proposals"]+validated["assertion_proposals"]]
 return {"schema_version":"memory-graph-semantic-review-queue/v1","namespace":validated["namespace"],"items":sorted(q,key=lambda x:x["proposal_id"]),"quarantine":validated["quarantine"],"automatic_approval":False}

def migrate_v09(bundle,api):
 """Read-only bridge: preserve supported v0.9 semantics as inert evidence only."""
 required={"conforms","shape_version","semantic_contract_version","namespace","source_snapshot_hash","source_digest","migration","entity_proposals","approved_endpoint_catalog","accepted_assertions","quarantine","identity_candidates","report_hash"}
 if not closed(bundle,required) or bundle.get("semantic_contract_version")!="0.9" or bundle.get("shape_version")!="memory-graph-ontology-shapes/v2": fail(api,"unsupported_semantic_version","only a sealed v0.9 validated semantic report can migrate")
 if bundle.get("report_hash")!=sha({k:v for k,v in bundle.items() if k!="report_hash"}): fail(api,"invalid_v09_bundle","v0.9 report is malformed or tampered")
 candidates=[]
 for kind,key in (("entity","entity_proposals"),("assertion","accepted_assertions")):
  for item in bundle[key]: candidates.append({"legacy_kind":kind,"legacy_id":item.get("entity_proposal_id") if kind=="entity" else item.get("assertion_id"),"legacy_status":item.get("status"),"record":item,"lifecycle":"candidate","review":None})
 out={"schema_version":"memory-graph-v09-migration/v1","from_semantic_contract":"0.9","to_semantic_contract":"1.0.0","namespace":bundle["namespace"],"source_snapshot_hash":bundle["source_snapshot_hash"],"source_digest":bundle["source_digest"],"candidates":sorted(candidates,key=lambda x:(x["legacy_kind"],str(x["legacy_id"]))),"quarantine":bundle["quarantine"],"input_rewritten":False,"approval_authority_migrated":False,"requires_fresh_v10_validation_and_human_review":True}
 out["migration_hash"]=sha(out); return out

def approve(validated,manifest,api,expected_reviewer_id):
 if not closed(manifest,{"schema_version","namespace","validated_hash","reviewer_id","reviewed_at","decisions"}) or manifest["schema_version"]!=SCHEMA_APPROVAL: fail(api,"invalid_approval_manifest","closed approval manifest required")
 if validated.get("validated_hash")!=sha({k:v for k,v in validated.items() if k!="validated_hash"}): fail(api,"invalid_validated_bundle","validated bundle is malformed or tampered")
 if manifest["namespace"]!=validated["namespace"] or manifest["validated_hash"]!=validated["validated_hash"]: fail(api,"invalid_approval_manifest","manifest must bind the exact validated bundle")
 if manifest["reviewer_id"]!=expected_reviewer_id or not isinstance(expected_reviewer_id,str) or expected_reviewer_id!=unicodedata.normalize("NFC",expected_reviewer_id) or not REVIEWER_ID.fullmatch(expected_reviewer_id): fail(api,"invalid_approval_authority","authenticated reviewer must be an exact canonical ASCII human ID matching the manifest")
 try: dt=datetime.fromisoformat(manifest["reviewed_at"].replace("Z","+00:00")); assert dt.tzinfo
 except Exception: fail(api,"invalid_approval_manifest","reviewed_at must be timezone-aware ISO-8601")
 source_dt=datetime.fromisoformat(validated["source_latest_mtime"].replace("Z","+00:00"))
 if dt < source_dt or dt > datetime.now(timezone.utc): fail(api,"stale_approval_manifest","review must be after the latest source change and not in the future")
 proposals=validated["entity_proposals"]+validated["assertion_proposals"]; known={x["proposal_id"] for x in proposals}
 if len(known)!=len(proposals): fail(api,"invalid_approval_manifest","proposal IDs must be unique")
 decisions={}
 for d in manifest["decisions"]:
  if not closed(d,{"proposal_id","lifecycle","reason"}) or d["lifecycle"] not in {"approved","rejected","revoked"} or not isinstance(d["reason"],str) or not d["reason"].strip(): fail(api,"invalid_approval_manifest","every decision must be closed and reasoned")
  if d["proposal_id"] not in known or d["proposal_id"] in decisions: fail(api,"invalid_approval_manifest","decision IDs must be known and unique")
  decisions[d["proposal_id"]]=d
 out=[]
 for x in validated["entity_proposals"]+validated["assertion_proposals"]:
  d=decisions.get(x["proposal_id"]); y=dict(x)
  if d: y.update(lifecycle=d["lifecycle"],review={"reviewer_id":manifest["reviewer_id"],"reviewed_at":manifest["reviewed_at"],"review_reason":d["reason"],"approval_effect":"withdrawn" if d["lifecycle"]=="revoked" else "granted" if d["lifecycle"]=="approved" else "denied"})
  if y["payload"].get("predicate")=="caused" and y.get("lifecycle")=="approved" and not causal_review_bound(y,d): y.update(lifecycle="candidate",review=None)
  out.append(y)
 expires=(dt.astimezone(timezone.utc)+timedelta(hours=24)).isoformat().replace("+00:00","Z")
 result={"schema_version":"memory-graph-reviewed-proposals/v1","namespace":validated["namespace"],"source_snapshot_hash":validated["source_snapshot_hash"],"source_digest":validated["source_digest"],"proposals":sorted(out,key=lambda x:x["proposal_id"]),"quarantine":validated["quarantine"],"manifest_hash":sha(manifest),"approval_expires_at":expires}
 result["reviewed_hash"]=sha(result); return result

def build_snapshot(reviewed,api):
 if not isinstance(reviewed,dict) or set(reviewed)!={"schema_version","namespace","source_snapshot_hash","source_digest","proposals","quarantine","manifest_hash","approval_expires_at","reviewed_hash"} or reviewed.get("schema_version")!="memory-graph-reviewed-proposals/v1" or reviewed.get("reviewed_hash")!=sha({k:v for k,v in reviewed.items() if k!="reviewed_hash"}): fail(api,"invalid_reviewed_bundle","reviewed proposal bundle is malformed or tampered")
 try: expires=datetime.fromisoformat(reviewed["approval_expires_at"].replace("Z","+00:00")); assert expires.tzinfo
 except Exception: fail(api,"invalid_reviewed_bundle","approval expiry must be timezone-aware ISO-8601")
 if expires <= datetime.now(timezone.utc): fail(api,"approval_expired","source-backed approval expired; revalidate sources and obtain a fresh review")
 approved=[x for x in reviewed["proposals"] if x["lifecycle"]=="approved"]
 relation_keys={}
 supersedes={}
 for x in approved:
  if x.get("kind")!="assertion": continue
  p=x.get("payload",{}); key=(p.get("subject",{}).get("entity_id"),p.get("predicate"),p.get("object",{}).get("entity_id"))
  if key[0]==key[2]: fail(api,"semantic_self_loop","approved semantic relations must connect distinct entity IDs",proposal_id=x.get("proposal_id"),predicate=key[1])
  if key in relation_keys: fail(api,"duplicate_semantic_assertion","multiple approved assertions express the same semantic edge",first=relation_keys[key],duplicate=x.get("proposal_id"))
  relation_keys[key]=x.get("proposal_id")
  if p.get("predicate")=="supersedes": supersedes.setdefault(key[0],set()).add(key[2])
 def cyclic(node,path):
  if node in path: return True
  return any(cyclic(n,path|{node}) for n in supersedes.get(node,set()))
 if any(cyclic(n,set()) for n in supersedes): fail(api,"supersession_cycle","approved supersedes assertions must form an acyclic graph")
 entities=[]; assertions=[]
 for x in approved:
  item={"semantic_id":x["proposal_id"],"namespace":reviewed["namespace"],"claim_id":x["claim_id"],"source":x["source"],"review":x["review"],"label":"approved/private"}
  if x["kind"]=="entity": entities.append({**item,**x["payload"]})
  else: assertions.append({**item,**x["payload"]})
 out={"schema_version":SCHEMA_SNAPSHOT,"namespace":reviewed["namespace"],"source_snapshot_hash":reviewed["source_snapshot_hash"],"source_digest":reviewed["source_digest"],"entities":sorted(entities,key=lambda x:x["semantic_id"]),"assertions":sorted(assertions,key=lambda x:x["semantic_id"]),"candidates":[x for x in reviewed["proposals"] if x["lifecycle"]=="candidate"],"revoked":[x for x in reviewed["proposals"] if x["lifecycle"]=="revoked"],"quarantine":reviewed["quarantine"],"inference_overlays":[]}
 out["snapshot_hash"]=sha(out); return out

def reconcile(snapshot,current,api):
 if snapshot.get("schema_version")!=SCHEMA_SNAPSHOT or snapshot.get("snapshot_hash")!=sha({k:v for k,v in snapshot.items() if k!="snapshot_hash"}): fail(api,"invalid_semantic_snapshot","invalid snapshot hash")
 ns=snapshot["namespace"]
 if not isinstance(current,dict) or set(current)!={"schema_version","entities","relations"}: fail(api,"invalid_memory_mcp_schema","current backend graph shape invalid")
 def owned(x): return x.get("namespace")==ns and x.get("semantic_owner")==ns
 target_e=[{**x,"semantic_owner":ns} for x in snapshot["entities"]]
 target_r=[{"semantic_id":x["semantic_id"],"namespace":ns,"semantic_owner":ns,"from":x["subject"],"relationType":x["predicate"],"to":x["object"],"claim_id":x["claim_id"],"source":x["source"],"review":x["review"]} for x in snapshot["assertions"]]
 ce={x["semantic_id"]:x for x in current["entities"] if owned(x)}; cr={x["semantic_id"]:x for x in current["relations"] if owned(x)}; te={x["semantic_id"]:x for x in target_e}; tr={x["semantic_id"]:x for x in target_r}
 deleted_entity_ids={ce[i].get("entity_id") for i in ce.keys()-te.keys()}
 for relation in current["relations"]:
  if owned(relation): continue
  endpoints=[]
  for endpoint in (relation.get("from"),relation.get("to")):
   endpoints.append(endpoint.get("entity_id") if isinstance(endpoint,dict) else endpoint)
  if deleted_entity_ids.intersection(endpoints): fail(api,"foreign_relation_dependency","cannot delete an owned entity still referenced by a preserved foreign relation",foreign_relation=relation.get("semantic_id"))
 ops=[]
 # Preserve referential integrity: remove relations before entities, then create
 # entities before relations. Updates occur in their corresponding upsert phase.
 for i in sorted(cr.keys()-tr.keys()): ops.append({"op":"delete","kind":"relation","semantic_id":i})
 for i in sorted(ce.keys()-te.keys()): ops.append({"op":"delete","kind":"entity","semantic_id":i})
 for kind,a,b in (("entity",ce,te),("relation",cr,tr)):
  for i in sorted(b):
   if a.get(i)!=b[i]: ops.append({"op":"create" if i not in a else "update","kind":kind,"semantic_id":i,"value":b[i]})
 for index,op in enumerate(ops): op.update(operation_index=index,operation_hash=sha({"namespace":ns,"snapshot_hash":snapshot["snapshot_hash"],"operation_index":index,"operation":op}))
 current_hash=sha(current); transaction_id=sha({"snapshot":snapshot["snapshot_hash"],"current_graph_hash":current_hash,"operations":ops})[:24]
 return {"schema_version":"memory-graph-semantic-reconcile/v1","namespace":ns,"current_graph_hash":current_hash,"target_snapshot_hash":snapshot["snapshot_hash"],"operations":ops,"foreign_entities_preserved":sum(not owned(x) for x in current["entities"]),"foreign_relations_preserved":sum(not owned(x) for x in current["relations"]),"canonical_markdown_mutated":False,"inference_applied":False,"idempotent":not ops,"journal":{"transaction_id":transaction_id,"state":"pending" if ops else "verified","dispatch_index":0,"next_operation_hash":ops[0]["operation_hash"] if ops else None,"retry_safe":True,"resume_requires_fresh_current_view":True,"resume_contract":"discard_prior_index_and_regenerate_from_fresh_view"}}

def verify_reconcile(snapshot,plan,current,api):
 required={"schema_version","namespace","current_graph_hash","target_snapshot_hash","operations","foreign_entities_preserved","foreign_relations_preserved","canonical_markdown_mutated","inference_applied","idempotent","journal"}
 if not closed(plan,required) or plan.get("schema_version")!="memory-graph-semantic-reconcile/v1": fail(api,"invalid_reconcile_plan","closed reconcile plan required")
 if plan["namespace"]!=snapshot.get("namespace") or plan["target_snapshot_hash"]!=snapshot.get("snapshot_hash"): fail(api,"reconcile_plan_mismatch","plan does not target this snapshot")
 journal=plan.get("journal")
 if not closed(journal,{"transaction_id","state","dispatch_index","next_operation_hash","retry_safe","resume_requires_fresh_current_view","resume_contract"}) or journal["dispatch_index"]!=0 or journal["resume_contract"]!="discard_prior_index_and_regenerate_from_fresh_view" or journal["resume_requires_fresh_current_view"] is not True: fail(api,"invalid_reconcile_plan","resume state must use fresh-view regeneration and never trust a persisted dispatch index")
 for index,op in enumerate(plan["operations"]):
  if op.get("operation_index")!=index: fail(api,"invalid_reconcile_plan","operation indexes must be contiguous")
  base={k:v for k,v in op.items() if k not in {"operation_index","operation_hash"}}
  expected=sha({"namespace":plan["namespace"],"snapshot_hash":plan["target_snapshot_hash"],"operation_index":index,"operation":base})
  if op.get("operation_hash")!=expected: fail(api,"invalid_reconcile_plan","operation seal mismatch",operation_index=index)
 expected_tx=sha({"snapshot":plan["target_snapshot_hash"],"current_graph_hash":plan["current_graph_hash"],"operations":plan["operations"]})[:24]
 if journal["transaction_id"]!=expected_tx or journal["next_operation_hash"]!=(plan["operations"][0]["operation_hash"] if plan["operations"] else None): fail(api,"invalid_reconcile_plan","journal seal or next operation does not match the plan")
 post=reconcile(snapshot,current,api)
 if not post["idempotent"]: fail(api,"semantic_reconcile_incomplete","fresh backend view does not match target",remaining_operations=len(post["operations"]),resume_plan=post)
 return {"schema_version":"memory-graph-semantic-reconcile-verification/v1","namespace":plan["namespace"],"transaction_id":plan["journal"].get("transaction_id"),"target_snapshot_hash":plan["target_snapshot_hash"],"post_current_graph_hash":post["current_graph_hash"],"verified":True,"remaining_operations":0,"canonical_markdown_mutated":False,"foreign_entities_preserved":post["foreign_entities_preserved"],"foreign_relations_preserved":post["foreign_relations_preserved"]}

def export_html(snapshot,output,api,include_candidates=False):
 if snapshot.get("schema_version")!=SCHEMA_SNAPSHOT or snapshot.get("snapshot_hash")!=sha({k:v for k,v in snapshot.items() if k!="snapshot_hash"}): fail(api,"invalid_semantic_snapshot","invalid snapshot hash")
 candidate_entities=sum(x.get("kind")=="entity" for x in snapshot.get("candidates",[])); candidate_assertions=sum(x.get("kind")=="assertion" for x in snapshot.get("candidates",[]))
 if len(snapshot.get("entities",[]))+candidate_entities>500 or len(snapshot.get("assertions",[]))+candidate_assertions>1000: fail(api,"semantic_visualization_too_large","visualization is bounded to 500 nodes and 1000 edges")
 def endpoint_id(value): return value.get("entity_id","") if isinstance(value,dict) else str(value)
 def bounded(value,limit=80):
  text=str(value or "").replace("\n"," ").replace("\r"," ")
  return text[:limit]+("…" if len(text)>limit else "")
 def safe_detail(item,kind):
  # Omit claim text, basis, source provenance, review reasons, and observations.
  keys=("semantic_id","entity_id","type","predicate","status","trust")
  return {"kind":kind,**{k:bounded(item[k]) for k in keys if k in item}}
 nodes=[]
 for e in snapshot.get("entities",[]):
  trust="canonical explicit" if e.get("label")=="approved/explicit" or e.get("entity_source")=="canonical_explicit" else "approved private proposal"
  nodes.append({"id":e.get("entity_id") or e["semantic_id"],"semantic_id":e["semantic_id"],"type":e.get("type","Unknown"),"cluster":bounded(e.get("claim_id","unknown"),64),"label":bounded(e.get("name") or e.get("entity_id") or e["semantic_id"]),"trust":trust,"status":"approved","detail":safe_detail({**e,"status":"approved","trust":trust},"entity")})
 edges=[]
 for a in snapshot.get("assertions",[]):
  edges.append({"id":a["semantic_id"],"source":endpoint_id(a.get("subject")),"target":endpoint_id(a.get("object")),"relation":bounded(a.get("predicate","")),"cluster":bounded(a.get("claim_id","unknown"),64),"status":"approved","trust":"approved assertion","detail":safe_detail({**a,"status":"approved","trust":"approved assertion"},"assertion")})
 for c in snapshot.get("candidates",[]) if include_candidates else []:
  p=c.get("payload",{}); kind=c.get("kind")
  if kind=="entity": nodes.append({"id":p.get("entity_id") or c["proposal_id"],"semantic_id":c["proposal_id"],"type":p.get("type","Unknown"),"cluster":bounded(c.get("claim_id","unknown"),64),"label":bounded(p.get("entity_id") or c["proposal_id"]),"trust":"candidate/inert","status":"candidate","detail":safe_detail({**p,"semantic_id":c["proposal_id"],"status":"candidate","trust":"candidate/inert"},"entity")})
  elif kind=="assertion": edges.append({"id":c["proposal_id"],"source":endpoint_id(p.get("subject")),"target":endpoint_id(p.get("object")),"relation":bounded(p.get("predicate","")),"cluster":bounded(c.get("claim_id","unknown"),64),"status":"candidate","trust":"candidate/inert","detail":safe_detail({**p,"semantic_id":c["proposal_id"],"status":"candidate","trust":"candidate/inert"},"assertion")})
 graph={"schema_version":"memory-graph-html-dataset/v1","nodes":sorted(nodes,key=lambda x:x["id"]),"edges":sorted(edges,key=lambda x:x["id"]),"inferred_edges":[]}
 def embedded(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
 doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><meta name="referrer" content="no-referrer"><title>Memory Graph Semantic</title><style>html,body{height:100%;margin:0;background:#0d1118;color:#eef;font:14px system-ui}body{display:grid;grid-template-rows:auto 1fr}header{padding:10px;background:#181d28;z-index:2}input,select,button{margin:3px;padding:7px;background:#222b3a;color:#eef;border:1px solid #526078;border-radius:5px}.legend{margin-left:8px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 3px 0 9px}.explicit{background:#50d890}.private{background:#4aa8ff}.candidate{background:#e2a84a}main{min-height:0;display:grid;grid-template-columns:1fr 320px}#stage{width:100%;height:100%;touch-action:none;background:radial-gradient(circle,#20283a 1px,transparent 1px);background-size:24px 24px}#details{overflow:auto;padding:12px;background:#141a24;border-left:1px solid #394158;white-space:pre-wrap}.edge{stroke:#8a9ab5;stroke-width:2}.edge.candidate{stroke:#e2a84a;stroke-dasharray:7 5}.edge-label{fill:#cbd5e8;font-size:11px}.node{cursor:pointer;stroke:#eef;stroke-width:1.5}.node.explicit{fill:#50d890}.node.private{fill:#4aa8ff}.node.candidate{fill:#e2a84a;stroke-dasharray:4 3}.node-label{fill:#fff;font-size:12px;pointer-events:none}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}</style><header><b>Semantic Memory Graph</b><input id="q" placeholder="Search"><select id="type"><option value="">All types</option><option>Person</option><option>Project</option><option>Decision</option><option>Event</option></select><select id="cluster"><option value="">All clusters</option></select><button id="reset">Reset pan/zoom</button><span class="legend"><i class="dot explicit"></i>canonical explicit<i class="dot private"></i>approved private proposal<i class="dot candidate"></i>candidate/inert</span></header><main><p id="graph-help" hidden>Use Tab to focus nodes, then Enter or Space to show bounded non-sensitive details.</p><svg id="stage" role="img" aria-label="Interactive semantic graph" aria-describedby="graph-help"><g id="viewport"></g></svg><aside id="details" role="status" aria-live="polite">Click a node or edge for details.</aside></main><script id="snapshot-data" type="application/json">'''+embedded(snapshot)+'''</script><script id="graph-data" type="application/json">'''+embedded(graph)+'''</script><script>const G=JSON.parse(document.getElementById('graph-data').textContent),svg=document.getElementById('stage'),vp=document.getElementById('viewport'),q=document.getElementById('q'),ty=document.getElementById('type'),cl=document.getElementById('cluster'),details=document.getElementById('details'),NS=svg.namespaceURI;[...new Set([...G.nodes,...G.edges].map(x=>x.cluster))].sort().forEach(x=>cl.add(new Option(x,x)));let scale=1,tx=0,tt=0,drag=null;function el(n,a){const e=document.createElementNS(NS,n);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);return e}function visible(x){const s=JSON.stringify(x).toLowerCase();return(!q.value||s.includes(q.value.toLowerCase()))&&(!ty.value||x.type===ty.value)&&(!cl.value||x.cluster===cl.value)}function draw(){vp.textContent='';const ns=G.nodes.filter(visible),ids=new Set(ns.map(x=>x.id)),w=Math.max(svg.clientWidth,600),h=Math.max(svg.clientHeight,500),pos={};ns.forEach((n,i)=>{const a=2*Math.PI*i/Math.max(ns.length,1)-Math.PI/2;pos[n.id]={x:w/2+Math.cos(a)*Math.min(w,h)*.33,y:h/2+Math.sin(a)*Math.min(w,h)*.33}});G.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)&&visible(e)).forEach(e=>{const a=pos[e.source],b=pos[e.target],line=el('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'edge '+e.status});line.onclick=()=>details.textContent=JSON.stringify(e.detail,null,2);vp.append(line);const t=el('text',{x:(a.x+b.x)/2,y:(a.y+b.y)/2,class:'edge-label'});t.textContent=e.relation;vp.append(t)});ns.forEach(n=>{const p=pos[n.id],klass=n.trust==='canonical explicit'?'explicit':n.status==='candidate'?'candidate':'private',c=el('circle',{cx:p.x,cy:p.y,r:18,class:'node '+klass,tabindex:0,role:'button','aria-label':`${n.status} ${n.type} ${n.label}`});c.onclick=()=>details.textContent=JSON.stringify(n.detail,null,2);c.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();c.onclick()}};vp.append(c);const t=el('text',{x:p.x+23,y:p.y+4,class:'node-label'});t.textContent=n.label;vp.append(t)});transform()}function transform(){vp.setAttribute('transform',`translate(${tx} ${tt}) scale(${scale})`)}svg.onwheel=e=>{e.preventDefault();scale=Math.max(.25,Math.min(4,scale*(e.deltaY<0?1.1:.9)));transform()};svg.onpointerdown=e=>drag={x:e.clientX-tx,y:e.clientY-tt};svg.onpointermove=e=>{if(drag){tx=e.clientX-drag.x;tt=e.clientY-drag.y;transform()}};svg.onpointerup=svg.onpointerleave=()=>drag=null;document.getElementById('reset').onclick=()=>{scale=1;tx=tt=0;transform()};q.oninput=ty.onchange=cl.onchange=draw;addEventListener('resize',draw);draw()</script></html>'''
 atomic_write(output,doc.encode("utf-8")); return {"schema_version":"memory-graph-semantic-html/v1","path":str(output),"sha256":hashlib.sha256(doc.encode()).hexdigest(),"offline":True,"network_requests":0,"node_count":len(graph["nodes"]),"edge_count":len(graph["edges"]),"candidate_lane_included":include_candidates,"quarantine_count":len(snapshot.get("quarantine",[])),"quarantine_projected":False,"filters":["search","type","cluster"],"interactions":["pan","zoom","node_details","edge_details"],"labels":["canonical explicit","approved private proposal"]+(["candidate/inert"] if include_candidates else [])}
