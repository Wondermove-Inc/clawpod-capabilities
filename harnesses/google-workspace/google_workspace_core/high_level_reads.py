"""Narrow normalization for high-level read-only convenience commands."""
from __future__ import annotations

def _headers(item):
    values={}
    payload=item.get("payload")
    if not isinstance(payload,dict):payload={}
    for header in payload.get("headers",[]):
        if isinstance(header,dict) and isinstance(header.get("name"),str):values[header["name"].lower()]=header.get("value")
    return values

def _masked_owner(value):
    if not isinstance(value,str) or "@" not in value:return None
    local,domain=value.rsplit("@",1);return (local[:1] or "*")+"***@"+domain

def _gmail_item(item,include_body=False):
    if not isinstance(item,dict):return {}
    # Thread list fixtures may already include bounded messages. Use only the
    # newest supplied message and never initiate an unbounded follow-up read.
    source=item
    messages=item.get("messages")
    if isinstance(messages,list) and messages:source=messages[-1]
    headers=_headers(source)
    out={
      "id":item.get("id") or source.get("id"),"threadId":source.get("threadId") or item.get("id"),
      "labelIds":source.get("labelIds",[]),"sender":headers.get("from"),"recipients":headers.get("to"),
      "date":headers.get("date") or source.get("internalDate"),"subject":headers.get("subject"),
      "snippet":source.get("snippet"),
    }
    if include_body:
        payload=source.get("payload");body=payload.get("body") if isinstance(payload,dict) else None
        if isinstance(body,dict):out["body"]={k:body.get(k) for k in ("size","data") if k in body}
    return out

def normalize(command,data,params=None):
    params=params or {}
    if command=="gmail.read":
        key="threads" if "threads" in data else "messages";items=data.get(key,[])
        return [_gmail_item(item,bool(params.get("includeBody"))) for item in items],data.get("nextPageToken")
    if command=="calendar.read":
        items=[]
        for item in data.get("items",[]):
            items.append({"id":item.get("id"),"summary":item.get("summary"),"start":item.get("start"),"end":item.get("end"),"timeZone":(item.get("start") or {}).get("timeZone"),"organizerCount":1 if item.get("organizer") else 0,"attendeeCount":len(item.get("attendees",[])),"status":item.get("status"),"recurring":bool(item.get("recurringEventId") or item.get("recurrence"))})
        return items,data.get("nextPageToken")
    if command=="drive.read":
        source=data.get("files")
        if source is None:source=[data]
        items=[]
        for item in source:
            owners=item.get("owners",[]);hints=[]
            for owner in owners:
                if isinstance(owner,dict):
                    hint=_masked_owner(owner.get("emailAddress"))
                    if hint:hints.append(hint)
            items.append({"id":item.get("id"),"name":item.get("name"),"mimeType":item.get("mimeType"),"modifiedTime":item.get("modifiedTime"),"ownerCount":len(owners),"ownerHints":hints,"parents":item.get("parents",[]),"webViewLink":item.get("webViewLink"),"size":item.get("size")})
        return items,data.get("nextPageToken")
    if command=="docs.read":
        text=[]
        for element in (data.get("body") or {}).get("content",[]):
            paragraph=element.get("paragraph") if isinstance(element,dict) else None
            if not isinstance(paragraph,dict):continue
            run="".join(e.get("textRun",{}).get("content","") for e in paragraph.get("elements",[]) if isinstance(e,dict))
            if run:text.append(run.rstrip("\n"))
        return [{"documentId":data.get("documentId"),"title":data.get("title"),"revisionId":data.get("revisionId"),"paragraphCount":len(text),"text":"\n".join(text)}],None
    if command=="sheets.read":
        values=data.get("values",[])
        return [{"range":data.get("range"),"majorDimension":data.get("majorDimension"),"rowCount":len(values),"columnCount":max((len(r) for r in values),default=0),"values":values}],None
    if command=="slides.read":
        slides=[]
        for index,slide in enumerate(data.get("slides",[]),1):
            lines=[]
            for element in slide.get("pageElements",[]):
                shape=element.get("shape") if isinstance(element,dict) else None
                if not isinstance(shape,dict):continue
                run="".join(t.get("textRun",{}).get("content","") for t in (shape.get("text") or {}).get("textElements",[]) if isinstance(t,dict)).strip()
                if run:lines.append(run)
            slides.append({"index":index,"objectId":slide.get("objectId"),"text":lines})
        return [{"presentationId":data.get("presentationId"),"title":data.get("title"),"revisionId":data.get("revisionId"),"slideCount":len(slides),"slides":slides}],None
    return None,None
