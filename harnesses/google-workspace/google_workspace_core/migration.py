"""Bounded, non-recursive legacy credential discovery and migration plans."""
from __future__ import annotations

from pathlib import Path

from .bindings import (
    BindingError, _accounts, _check_artifact, _identity, import_binding,
    mark_migration_completed, normalize_alias,
)


def preview_candidates(paths):
    if not isinstance(paths,list) or not 1<=len(paths)<=32 or not all(isinstance(item,str) for item in paths):
        raise BindingError("INVALID_ARGUMENT","migration candidates must be a bounded non-empty array")
    found=[]
    for index,raw in enumerate(paths):
        path=Path(raw)
        if not path.is_absolute():raise BindingError("BINDING_PATH_UNSAFE","migration candidate paths must be absolute")
        try:
            _check_artifact(path);accounts=_accounts(path)
        except BindingError as exc:
            found.append({"candidateId":str(index),"healthy":False,"checkId":exc.code,"aliases":[]});continue
        identities=[]
        for source_alias,value in sorted(accounts.items()):
            try:
                _,hint=_identity(value);identities.append({"alias":source_alias,"emailHint":hint})
            except BindingError:
                identities.append({"alias":source_alias,"emailHint":None})
        found.append({"candidateId":str(index),"healthy":True,"checkId":"candidateValid","aliases":identities})
    return found


def plan_migration(paths,mappings=None):
    candidates=preview_candidates(paths)
    mappings=mappings or []
    seen=set();planned=[]
    for mapping in mappings:
        if not isinstance(mapping,dict):raise BindingError("MIGRATION_CONFLICT","migration mapping must be an object")
        candidate_id=str(mapping.get("candidateId"));alias=normalize_alias(mapping.get("alias"))
        key=(candidate_id,alias)
        if key in seen:raise BindingError("MIGRATION_CONFLICT","migration mapping is duplicated")
        seen.add(key)
        if not candidate_id.isdigit() or int(candidate_id)>=len(candidates):raise BindingError("MIGRATION_CONFLICT","migration mapping references an unknown candidate")
        if not candidates[int(candidate_id)]["healthy"]:raise BindingError("MIGRATION_CONFLICT","migration mapping references an unhealthy candidate")
        planned.append({"candidateId":candidate_id,"alias":alias,"mode":mapping.get("mode","copy"),"overwrite":bool(mapping.get("overwrite",False))})
    return {"operation":"migrate","candidates":candidates,"mappings":planned}


def apply_migration(paths,mappings,root=None):
    plan=plan_migration(paths,mappings)
    if not mappings:raise BindingError("MIGRATION_CONFLICT","migration apply requires an explicit candidate mapping")
    results=[]
    for mapping in mappings:
        index=int(str(mapping["candidateId"]));alias=normalize_alias(mapping["alias"])
        result=import_binding(alias,paths[index],mapping.get("mode","copy"),mapping.get("sourceAlias"),mapping.get("overwrite",False),root)
        results.append({"candidateId":str(index),"alias":alias,"revision":result["revision"]})
    final=mark_migration_completed(root)
    return results,final["revision"],plan
