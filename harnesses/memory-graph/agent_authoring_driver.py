#!/usr/bin/env python3
"""Bounded external-agent-style authoring from sealed natural-language pages."""
import re

MAX_PROPOSALS=1000
CLAUSE=r"(?:[^.!?;\n]|\.(?!\s|$)){2,180}?"
POLICY_CLAUSE=r"(?:[^.!?;\n]|\.(?!\s|$)){4,256}?"
END=r"(?=\.(?=\s|$)|[!?;]|$)"
BOUNDARY=r"(?:^|(?<=[!?;]\s)|(?<=\.\s)|(?<=\n))\s*(?:[-*]\s*)?"
PROPER=r"[A-Z][A-Za-z0-9_'’-]*(?:\s+[A-Z][A-Za-z0-9_'’-]*){0,3}"
PERSON=rf"(?:{PROPER}|[가-힣]{{2,4}}(?:\s+[가-힣]{{2,4}})?)"
COMPLETED_ACTION=r"decided|chose|stopped|cancelled|canceled|abandoned|approved|prohibited|required|adopted|updated|결정(?:했|했다|하였다)|선택(?:했|했다|하였다)|중단(?:했|했다|하였다)|취소(?:했|했다|하였다)|포기(?:했|했다|하였다)|승인(?:했|했다|하였다)|금지(?:했|했다|하였다)|요구(?:했|했다|하였다)|채택(?:했|했다|하였다)|수정(?:했|했다|하였다)|업데이트(?:했|했다|하였다)"
PATTERNS=(
 ("decided","Person","Decision",re.compile(rf"(?P<subject>\b{PERSON})(?:은|는)?\s+(?i:explicitly\s+)?(?P<predicate>(?i:{COMPLETED_ACTION}))\s+(?i:to\s+|that\s+)?(?P<object>{CLAUSE})(?=\s+(?i:because|due\s+to)\b|\.(?=\s|$)|[!?;]|$)")),
 ("decided","Person","Decision",re.compile(rf"(?P<subject>\b{PROPER})\s+(?P<predicate>prohibits|requires)\s+(?P<object>{POLICY_CLAUSE})(?=\s+(?:because|due\s+to)\b|\.(?=\s|$)|[!?;]|$)")),
 # Korean factual policy actions use subject-object-predicate word order.
 ("decided","Person","Decision",re.compile(rf"(?P<subject>[가-힣]{{2,4}})(?:은|는)\s+(?P<object>{POLICY_CLAUSE})\s+(?P<predicate>요구한다)(?=[.!?;]|$)")),
 ("motivated_by","Decision","Cause",re.compile(rf"{BOUNDARY}(?P<subject>{CLAUSE})\s+(?P<predicate>because|due\s+to|왜냐하면)\s+(?P<object>{CLAUSE}){END}",re.I)),
 ("caused","Cause","Effect",re.compile(rf"(?P<subject>{CLAUSE})\s+(?P<predicate>(?:directly\s+)?caused|led\s+to|resulted\s+in)\s+(?P<object>{CLAUSE}){END}",re.I)),
 ("affected","Event","Event",re.compile(rf"(?P<subject>{CLAUSE})\s+(?P<predicate>affected|impacted)\s+(?P<object>{CLAUSE}){END}",re.I)),
 ("affected","Event","Event",re.compile(rf"(?P<subject>{CLAUSE})\s+(?P<predicate>blocked)\s+(?P<object>{CLAUSE}){END}",re.I)),
 ("participates_in","Person","Project",re.compile(rf"(?P<subject>\b{PROPER})\s+(?P<predicate>(?i:works?\s+on|participates?\s+in|leads?|maintains?))\s+(?P<object>{CLAUSE}\b(?i:project|capability|product|initiative|program)){END}")),
 ("supersedes",None,None,re.compile(rf"(?P<subject>{CLAUSE}\b(?:project|decision|event|effect))\s+(?P<predicate>supersedes?|replaces?|makes?\s+obsolete)\s+(?P<object>{CLAUSE}\b(?:project|decision|event|effect)){END}",re.I)),
 # Korean cause-first constructions preserve textual subject→predicate→object order.
 ("caused","Cause","Effect",re.compile(r"(?P<subject>[^.!?;\n]{2,100}?)(?P<predicate>때문에|(?:로|으로)\s*인해|원인이\s*(?:되어|돼|되었|됐다))(?P<object>[^.!?;\n]{2,100})(?=[.!?;]|$)")),
 ("affected","Event","Event",re.compile(r"(?P<subject>[^.!?;\n]{2,100}?)(?P<predicate>영향을\s*주어|영향을\s*줘서)(?P<object>[^.!?;\n]{2,100})(?=[.!?;]|$)")),
)
NEGATED=re.compile(r"(?i)(?:\b(?:not|never|no(?!-)|cannot|can't|didn't|doesn't|without)\b|않(?:았|는|다)|아니(?:다|었))")
NONFACTUAL=re.compile(r"(?i)(?:\b(?:if|unless|would|could|might|may|perhaps|possibly|apparently|reportedly|will|shall|going\s+to|planned|proposed|intended|tomorrow|next\s+(?:week|month|year)|in\s+the\s+future|future)\b|만약|(?:으)?(?<!왜냐하)면(?:\s|,|$)|라면|수\s*(?:있|없)|수도|예정|계획|제안|의도|할\s*것|다음\s*(?:주|달|해)|향후|미래)")
STATUS_LANGUAGE=re.compile(r"(?i)(?:\b(?:status|state|lifecycle|claim|record|blocked|until\s+fixed|with\s+proof)\b|상태|수명주기|클레임|레코드|차단|수정될\s*때까지|증명과\s*함께)")
REPORTING_ONLY=re.compile(r"(?i)(?:\b(?:says?|said|reports?|reported|claims?|claimed|quoted?|according\s+to)\b|말했|보도|주장|인용|따르면)")
PROPOSITION=re.compile(r"(?i)(?:\b(?:is|are|was|were|be|has|have|had|failed|blocked|changed|removed|missing|cannot|did|does|requir(?:e|es|ed|ing)|impos(?:e|es|ed|ing)|can\s+block|runs?|writes?|reads?|uses?)\b|되|했|함|없|있|실패|차단|변경|삭제|필요|의존성\s*게이팅|막을\s*수)")
DECISION_PROPOSITION=re.compile(rf"(?i)(?:\b(?:{COMPLETED_ACTION}|recommend(?:ed|s|ing|ation)?|select(?:ed|s|ing)?|must|should|use[ds]?)\b|결정|선택|권장|권고|채택|사용|중단|취소|포기|승인|금지|요구|수정|업데이트|해야\s*한다|추가하는\s*것)")
PROJECT_MENTION=re.compile(rf"\b{PROPER}\s+(?:Project|Capability|Product|Initiative|Program)\b|[A-Za-z0-9][A-Za-z0-9._-]{{1,63}}\s*(?:프로젝트|기능|제품)")
def decision_signal(text):
 for label,pattern in (("recommendation",r"(?i)recommend|권장|권고"),("decision",r"(?i)decid|결정"),("selection",r"(?i)chos|select|선택"),("policy_action",r"(?i)stopped|cancelled|canceled|abandoned|approved|prohibited|required|must|should|use[ds]?|adopted|updated|중단|취소|포기|승인|금지|요구|채택|수정|업데이트|사용|해야|추가하는")):
  if re.search(pattern,text): return label
 return None

def author_with_diagnostics(pages,semantic,extractor):
 if not isinstance(pages,list) or not pages: raise ValueError("pages required")
 namespace=pages[0]["namespace"]; proposals=[]; seen=set(); diagnostics={"claims_scanned":0,"eligible_claims_scanned":0,"pattern_matches":{},"rejected_by_reason":{},"proposal_limit_reached":False}
 def rejected(reason,predicate):
  diagnostics["rejected_by_reason"].setdefault(reason,{})[predicate]=diagnostics["rejected_by_reason"].get(reason,{}).get(predicate,0)+1
 def add(row,kind,payload,spans,basis):
  mentions=[{"role":role,"start":start,"end":end,"text":row["claim_text"][start:end]} for role,start,end in spans]
  evidence={"mentions":mentions,"evidence_hash":semantic.sha({"claim_content_hash":row["claim_content_hash"],"mentions":mentions})}
  source={k:row[k] for k in ("path","line_start","line_end","source_content_hash","claim_content_hash")}
  raw={"proposal_id":"","kind":kind,"claim_id":row["claim_id"],"source":source,"payload":payload,"basis":basis,"evidence":evidence}; raw["proposal_id"]=semantic.proposal_id(namespace,raw,extractor)
  if raw["proposal_id"] not in seen:
   if len(proposals)>=MAX_PROPOSALS: diagnostics["proposal_limit_reached"]=True; return
   seen.add(raw["proposal_id"]); proposals.append(raw)
 def entity(row,entity_type,start,end,basis):
  entity_id=semantic.grounded_entity_id(entity_type,row["claim_text"][start:end]); add(row,"entity",{"entity_id":entity_id,"type":entity_type,"temporal":None},[("entity",start,end)],basis); return entity_id
 def relation(row,match,predicate,stype,otype):
  spans=[match.span("subject"),match.span("predicate"),match.span("object")]
  cue=match.group("predicate").casefold()
  sov=predicate=="decided" and cue=="요구한다"
  if predicate=="decided" and cue not in {"decided","chose"}:
   actor=match.group("subject").strip()
   if actor.isascii() and len(actor.split())<2: rejected("incomplete_person_actor",predicate); return
   # A following comma-delimited governing clause is not part of the action's
   # Decision object ("stopped X, Forge restored Y").
   tail=match.group("object"); boundary=re.search(r",\s+(?=[A-Z][A-Za-z0-9_'’-]*(?:\s+[A-Za-z][A-Za-z0-9_'’-]*)+\s)",tail)
   if boundary: spans[2]=(spans[2][0],spans[2][0]+boundary.start())
  if not ((spans[0][1]<=spans[2][0] and spans[2][1]<=spans[1][0]) if sov else (spans[0][1]<=spans[1][0] and spans[1][1]<=spans[2][0])): return
  boundaries=[m for m in re.finditer(r"[!?;\n]|\.(?=\s|$)",row["claim_text"]) if m.end()<=spans[0][0]]; sentence_start=boundaries[-1].end() if boundaries else 0
  sentence=row["claim_text"][sentence_start:spans[2][1]]; window=row["claim_text"][max(spans[1][0]-24,spans[0][0]):spans[1][1]]
  if NEGATED.search(window): rejected("negated",predicate); return
  if cue in {"prohibits","requires","요구한다"} and (REPORTING_ONLY.search(sentence[:spans[0][0]-sentence_start]) or re.search(r"[\"“”‘’]",sentence) or re.search(r"'[^']{4,}'",sentence)): rejected("reporting_or_quoted_policy",predicate); return
  modalities=list(NONFACTUAL.finditer(sentence))
  # A completed, actor-bound decision remains factual when modality occurs only
  # inside its adopted policy/content (for example "updated ... may" or
  # "decided ... planned ... must"). Modality before the action, or in its
  # causal justification, still weakens the governing assertion.
  completed=re.search(rf"\b{PERSON}(?:은|는)?\s+(?i:explicitly\s+)?(?i:{COMPLETED_ACTION})\b",sentence)
  if cue in {"prohibits","requires","요구한다"}: completed=True
  if modalities:
   predicate_at=spans[1][0]-sentence_start
   object_at=spans[2][0]-sentence_start
   embedded_policy=completed and predicate in {"decided","motivated_by"} and all(completed.end()<=m.start()<predicate_at if predicate=="motivated_by" else object_at<=m.start() for m in modalities)
   if not embedded_policy: rejected("nonfactual_modality",predicate); return
  if predicate=="affected" and STATUS_LANGUAGE.search(sentence): rejected("status_language",predicate); return
  if predicate=="motivated_by" and not DECISION_PROPOSITION.search(match.group("subject")): rejected("fragmentary_decision_subject",predicate); return
  if predicate=="motivated_by" and not PROPOSITION.search(match.group("object")): rejected("incomplete_causal_proposition",predicate); return
  if predicate=="supersedes":
   if STATUS_LANGUAGE.search(sentence): rejected("status_language",predicate); return
   def endpoint_type(value):
    found=re.search(r"(?i)\b(project|decision|event|effect)\s*$",value.strip())
    return {"project":"Project","decision":"Decision","event":"Event","effect":"Effect"}.get(found.group(1).casefold()) if found else None
   stype=endpoint_type(match.group("subject")); otype=endpoint_type(match.group("object"))
   if not stype or not otype: rejected("untyped_supersession_endpoint",predicate); return
  cue=" ".join(match.group("predicate").casefold().split()); basis=f"explicit {predicate} construction ({cue})"
  sid=entity(row,stype,*spans[0],basis); oid=entity(row,otype,*spans[2],basis)
  add(row,"assertion",{"subject":{"entity_id":sid,"type":stype},"predicate":predicate,"object":{"entity_id":oid,"type":otype},"valid_time":None},[("subject",*spans[0]),("predicate",*spans[1]),("object",*spans[2])],basis)
 for page in pages:
  for row in page["claims"]:
   diagnostics["claims_scanned"]+=1
   if not row.get("proposal_eligible"): continue
   diagnostics["eligible_claims_scanned"]+=1
   for predicate,stype,otype,pattern in PATTERNS:
    for match in pattern.finditer(row["claim_text"]): diagnostics["pattern_matches"][predicate]=diagnostics["pattern_matches"].get(predicate,0)+1; relation(row,match,predicate,stype,otype)
   for match in PROJECT_MENTION.finditer(row["claim_text"]):
    context=row["claim_text"][max(0,match.start()-32):match.end()]
    name=re.sub(r"(?i)\s+(?:project|capability|product|initiative|program)$|\s*(?:프로젝트|기능|제품)$","",match.group()).strip()
    if name.casefold() in {x.casefold() for x in semantic.TYPES}|{"documentation","ontology","type","status","lifecycle"} or re.search(r"(?i)\b(?:documentation|ontology|types?|lists?)\b",context) or STATUS_LANGUAGE.search(match.group()): rejected("ontology_or_status_listing","entity:Project"); continue
    entity(row,"Project",*match.span(),"explicit named project/capability/product mention")
 # Suppress only a closed, high-confidence paraphrase family. The richer claim
 # remains exact-span grounded; its same-claim rationale preserves the second
 # evidence locator without manufacturing a cross-claim merged entity.
 stopped=[]
 for proposal in proposals:
  if proposal["kind"]!="assertion" or proposal["payload"]["predicate"]!="decided" or proposal["evidence"]["mentions"][1]["text"].casefold()!="stopped": continue
  obj=proposal["evidence"]["mentions"][2]["text"].casefold()
  version=re.search(r"\bv\d+(?:\.\d+)+\b",obj)
  if version and "plugin" in obj and re.search(r"\b(?:migration|direction)\b",obj):
   prefix=re.sub(r"^(?:the\s+)?|\s+$","",obj[:version.start()]); words=re.findall(r"[a-z][a-z0-9_-]*",prefix)
   product=" ".join(words[-2:]) if words else None
   stopped.append(((proposal["payload"]["subject"]["entity_id"],version.group()),product,proposal))
 rationale_claims={x["claim_id"] for x in proposals if x["kind"]=="assertion" and x["payload"]["predicate"]=="motivated_by"}
 suppressed=[]
 for key in sorted({x[0] for x in stopped}):
  entries=[x for x in stopped if x[0]==key]; products=sorted({x[1] for x in entries if x[1]})
  rationale_products={x[1] for x in entries if x[1] and x[2]["claim_id"] in rationale_claims}
  generic_target=next(iter(rationale_products)) if len(rationale_products)==1 else products[0] if len(products)==1 else None
  for product in products:
   group=[x[2] for x in entries if x[1]==product or x[1] is None and product==generic_target]
   if len(group)<2: continue
   keep=max(group,key=lambda x:(x["claim_id"] in rationale_claims,len(x["evidence"]["mentions"][2]["text"]),x["proposal_id"]))
   suppressed.extend(x for x in group if x is not keep)
 if suppressed:
  remove_ids=set()
  for assertion in suppressed:
   remove_ids.add(assertion["proposal_id"]); endpoint_ids={assertion["payload"]["subject"]["entity_id"],assertion["payload"]["object"]["entity_id"]}
   remove_ids.update(x["proposal_id"] for x in proposals if x["kind"]=="entity" and x["claim_id"]==assertion["claim_id"] and x["payload"]["entity_id"] in endpoint_ids and x["basis"]==assertion["basis"])
   rejected("semantic_duplicate_decision","decided")
  proposals[:]=[x for x in proposals if x["proposal_id"] not in remove_ids]
 proposals.sort(key=lambda x:x["proposal_id"])
 diagnostics["proposal_counts_by_kind"]={kind:sum(x["kind"]==kind for x in proposals) for kind in ("entity","assertion")}
 diagnostics["assertions_by_predicate"]={p:sum(x["kind"]=="assertion" and x["payload"]["predicate"]==p for x in proposals) for p in sorted({x["payload"]["predicate"] for x in proposals if x["kind"]=="assertion"}|{x[0] for x in PATTERNS})}
 diagnostics["entities_by_type"]={t:sum(x["kind"]=="entity" and x["payload"]["type"]==t for x in proposals) for t in sorted({x["payload"]["type"] for x in proposals if x["kind"]=="entity"})}
 diagnostics["zero_predicates"]=[p for p,n in diagnostics["assertions_by_predicate"].items() if n==0]
 diagnostics["accepted_assertion_summaries"]=[{"assertion_id":x["proposal_id"],"predicate":x["payload"]["predicate"],"subject_type":x["payload"]["subject"]["type"],"object_type":x["payload"]["object"]["type"],"cue":x["evidence"]["mentions"][1]["text"].casefold(),"subject_chars":len(x["evidence"]["mentions"][0]["text"]),"object_chars":len(x["evidence"]["mentions"][2]["text"]),"subject_proposition_kind":decision_signal(x["evidence"]["mentions"][0]["text"]) if x["payload"]["predicate"] in {"decided","motivated_by"} else None,"object_proposition_verified":bool(PROPOSITION.search(x["evidence"]["mentions"][2]["text"])) if x["payload"]["predicate"]=="motivated_by" else None,"evidence_hash":x["evidence"]["evidence_hash"]} for x in proposals if x["kind"]=="assertion"]
 return proposals,diagnostics

def author(pages,semantic,extractor): return author_with_diagnostics(pages,semantic,extractor)[0]
