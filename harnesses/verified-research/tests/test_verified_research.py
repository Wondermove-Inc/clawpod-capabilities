import importlib.util, json, os, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pytest

P=Path(__file__).parents[1]/'verified_research.py'
spec=importlib.util.spec_from_file_location('vr',P); vr=importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)

class H(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/redirect': self.send_response(302); self.send_header('Location','/html'); self.end_headers(); return
  if self.path=='/private-redirect': self.send_response(302); self.send_header('Location','http://169.254.169.254/'); self.end_headers(); return
  if self.path=='/compressed': self.send_response(200); self.send_header('Content-Encoding','gzip'); self.end_headers(); return
  if self.path=='/declared-large': self.send_response(200); self.send_header('Content-Length','999999'); self.end_headers(); return
  if self.path=='/metadata': body=b'''<html><head><title>Doc</title><meta name="author" content="A"><meta property="article:published_time" content="2024-01-02T00:00:00Z"><meta property="og:site_name" content="Site"><script type="application/ld+json">{"dateModified":"2024-01-03T00:00:00Z"}</script></head><body><p>One</p><p>Two</p></body></html>'''; typ='text/html'
  elif self.path=='/rss': body=b'''<?xml version="1.0"?><rss><channel><title>Example Publisher</title><link>https://example.com/</link><lastBuildDate>Tue, 02 Jan 2024 04:05:06 GMT</lastBuildDate><item><title>Story</title><link>https://example.com/story</link><author>Alice</author><pubDate>Tue, 02 Jan 2024 03:04:05 +0000</pubDate></item></channel></rss>'''; typ='application/rss+xml'
  elif self.path=='/atom': body=b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Publisher</title><link href="https://example.com/feed"/><updated>2024-01-03T00:00:00Z</updated><author><name>Feed Author</name></author><entry><title>Entry</title><link href="https://example.com/entry"/><published>2024-01-02T00:00:00Z</published><author><name>Entry Author</name></author></entry></feed>'''; typ='application/atom+xml'
  elif self.path=='/unsafe-canonical': body=b'<link rel="canonical" href="http://169.254.169.254/private"><p>X</p>'; typ='text/html'
  elif self.path=='/large': body=b'x'*200; typ='text/plain'
  elif self.path=='/json': body=b'{"b":2,"a":1}'; typ='application/json'
  elif self.path=='/feed': body=b'<?xml version="1.0"?><rss><channel><title>Feed</title><item><title>One</title></item></channel></rss>'; typ='application/rss+xml'
  elif self.path=='/pdf': body=b'%PDF-1.4\nnot a complete pdf'; typ='application/pdf'
  else: body=b'<html><head><title>T</title><link rel="canonical" href="/canonical"></head><body>A  B\nC<script>ignore</script></body></html>'; typ='text/html'
  self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(body)))
  if self.path=='/metadata': self.send_header('Last-Modified','Tue, 02 Jan 2024 03:04:05 GMT')
  self.end_headers(); self.wfile.write(body)
 def log_message(self,*a): pass

@pytest.fixture
def server(monkeypatch,tmp_path):
 fixture=tmp_path/'fixture.json'; fixture.write_text('{}'); fixture.chmod(0o600)
 s=HTTPServer(('127.0.0.1',0),H); t=threading.Thread(target=s.serve_forever,daemon=True); t.start(); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE','1'); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(fixture)); yield f'http://127.0.0.1:{s.server_port}'; s.shutdown()

def test_html_redirect_canonical_deterministic(server):
 a,_=vr.fetch(server+'/redirect'); b,_=vr.fetch(server+'/html')
 assert a['text']=='A B\nC' and a['canonicalUrl'].endswith('/canonical') and a['rawSha256']==b['rawSha256']

def test_json_feed_pdf_states(server):
 j,_=vr.fetch(server+'/json'); f,_=vr.fetch(server+'/feed'); p,_=vr.fetch(server+'/pdf')
 assert j['text'].find('"a"') < j['text'].find('"b"')
 assert 'Feed' in f['text']
 assert p['extraction'] in ('dependency_missing','unsupported')

def test_size_limit(server):
 with pytest.raises(vr.VError,match='byte limit'): vr.fetch(server+'/large',max_bytes=20)

@pytest.mark.parametrize('url',['file:///etc/passwd','http://user:pass@example.com','http://localhost','http://127.0.0.1','http://0.0.0.0','http://169.254.169.254','http://[::1]','http://example.com:22'])
def test_ssrf_rejections(monkeypatch,url):
 monkeypatch.delenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE',raising=False)
 with pytest.raises(vr.VError): vr.syntax_url(url)

def test_test_seam_requires_flag(monkeypatch,tmp_path):
 monkeypatch.delenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE',raising=False)
 with pytest.raises(vr.VError): vr.syntax_url('http://127.0.0.1:8888')
 with pytest.raises(vr.VError): vr.syntax_url('http://127.0.0.1:8888',True,True)
 fixture=tmp_path/'fixture.json'; fixture.write_text('{}'); fixture.chmod(0o600); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE','1'); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(fixture))
 assert vr.syntax_url('http://127.0.0.1:8888',True,True).startswith('http://127.0.0.1:8888')

def test_paths_and_symlink(tmp_path):
 root=tmp_path/'r'; root.mkdir(); (root/'x').write_text('x')
 with pytest.raises(vr.VError): vr.safe_path(root,'../x')
 link=root/'link'; link.symlink_to(root/'x')
 with pytest.raises(vr.VError): vr.safe_path(root,'link',True)

def test_import_hash_and_atomic_mode(tmp_path):
 (tmp_path/'c.txt').write_text(' A   B\r\nC ')
 a=type('A',(),dict(command='source.import',input_root=str(tmp_path),capture='c.txt',source_url=None,media_type='text/plain',output_root=str(tmp_path),output='out.json',max_bytes=100))
 r=vr.cmd(a)['source']; assert r['text']=='A B\nC'; assert (tmp_path/'out.json').stat().st_mode & 0o777 == 0o600

def test_batch_partial_and_dedupe(tmp_path,server):
 (tmp_path/'m.json').write_text(json.dumps({'urls':[server+'/html',server+'/html','file:///bad']}))
 a=type('A',(),dict(command='source.batch',input_root=str(tmp_path),manifest='m.json',output_root=None,output=None,timeout=3,max_bytes=10000))
 with pytest.raises(vr.Partial) as e: vr.cmd(a)
 r=e.value.data; assert r['partial'] and r['sources'][1]['duplicateOf']==r['sources'][0]['id']; assert len(r['failures'])==1

def build_bundle(tmp_path,status='supported',quote='Alpha'):
 text='Alpha\nBeta'; raw=text.encode(); s={'id':'s1','text':text,'textSha256':vr.digest(raw),'rawSha256':vr.digest(raw),'rawBytes':len(raw),'mediaType':'text/plain','finalUrl':'https://example.com/a','canonicalUrl':None,'metadataCandidates':[]}
 (tmp_path/'s.json').write_text(json.dumps({'sources':[s]})); (tmp_path/'c.json').write_text(json.dumps({'claims':[{'id':'c1','text':'Claim','status':status,'evidence':[{'sourceId':'s1','startLine':1,'endLine':1,'quote':quote}]}]}))
 a=type('A',(),dict(command='bundle.build',input_root=str(tmp_path),sources='s.json',claims='c.json',output_root=str(tmp_path),output='bundle.json'))
 return vr.cmd(a)['bundle']

def test_bundle_build_validate_inspect(tmp_path):
 b=build_bundle(tmp_path); assert (tmp_path/'bundle.json.md').exists()
 a=type('A',(),dict(command='bundle.validate',input_root=str(tmp_path),bundle='bundle.json')); assert vr.cmd(a)['valid']
 a.command='bundle.inspect'; assert vr.cmd(a)['sourceCount']==1 and vr.cmd(a)['claimCount']==1

def test_quote_unresolved_missing_and_tamper(tmp_path):
 b=build_bundle(tmp_path); b['claims'][0]['status']='conflicted'; b['claims'][0]['evidence'][0]['quote']='wrong'; b['claims'][0]['evidence'].append({'sourceId':'missing','startLine':1,'endLine':1,'quote':'x'}); b['sources'][0]['text']='tampered'; (tmp_path/'bad.json').write_text(json.dumps(b))
 a=type('A',(),dict(command='bundle.validate',input_root=str(tmp_path),bundle='bad.json')); codes={x['code'] for x in vr.cmd(a)['issues']}
 assert {'MANIFEST_TAMPERED','TEXT_HASH_MISMATCH','QUOTE_MISMATCH','MISSING_SOURCE','UNRESOLVED_CLAIM'} <= codes

def test_malformed_and_manifest_bound(tmp_path):
 (tmp_path/'bad.json').write_text('{');
 with pytest.raises(vr.VError): vr.load(tmp_path,'bad.json')
 (tmp_path/'many.json').write_text(json.dumps({'urls':['https://example.com']*51})); a=type('A',(),dict(command='source.batch',input_root=str(tmp_path),manifest='many.json',output_root=None,output=None,timeout=1,max_bytes=10))
 with pytest.raises(vr.VError): vr.cmd(a)

def test_no_secret_in_http_failure(server):
 with pytest.raises(vr.VError) as e: vr.syntax_url('http://token:secret@example.com')
 assert 'token' not in e.value.message and 'secret' not in e.value.message

def test_command_schema_path_roles_and_simple_types():
 h=json.loads((P.parent/'harness.json').read_text()); contracts=json.loads((P.parent/'command_contracts.json').read_text())['commands']; child_names={'snapshot','manifest','output','capture','sources','claims','bundle'}
 for name,c in h['commands'].items():
  for a in c['argMap']:
   if a['arg'] in ('inputRoot','outputRoot'):
    assert a['valueType']=='path' and a['pathRole'] in ('input','output')
   elif a['arg'] in child_names:
    assert a['valueType']=='string' and 'pathRole' not in a
   else:
    assert a['valueType']!='path' and 'pathRole' not in a
  assert contracts[name]['rootPathArgs']==sorted(a['arg'] for a in c['argMap'] if a['arg'] in ('inputRoot','outputRoot'))
  assert contracts[name]['relativeChildArgs']==sorted(a['arg'] for a in c['argMap'] if a['arg'] in child_names)
  assert all(v.get('type') in ('string','integer','boolean','number') for v in c['inputSchema']['properties'].values())

def test_snapshot_exact_bytes_and_tamper(tmp_path,server):
 a=type('A',(),dict(command='source.fetch',url=server+'/html',timeout=2,max_bytes=10000,snapshot='record.json',output_root=str(tmp_path),overwrite=False))
 s=vr.cmd(a)['source']; raw=(tmp_path/s['snapshotPath']).read_bytes(); assert vr.digest(raw)==s['rawSha256'] and len(raw)==s['rawBytes']
 (tmp_path/'sources.json').write_text(json.dumps({'sources':[s]})); (tmp_path/'claims.json').write_text(json.dumps({'claims':[]}))
 b=type('A',(),dict(command='bundle.build',input_root=str(tmp_path),sources='sources.json',claims='claims.json',output_root=str(tmp_path),output='b.json',overwrite=False)); vr.cmd(b)
 (tmp_path/s['snapshotPath']).write_bytes(b'tampered'); v=type('A',(),dict(command='bundle.validate',input_root=str(tmp_path),bundle='b.json',as_of=None)); assert 'RAW_HASH_MISMATCH' in {x['code'] for x in vr.cmd(v)['issues']}

def test_metadata_candidates_and_block_lines(server):
 s,_=vr.fetch(server+'/metadata'); fields={x['field'] for x in s['metadataCandidates'] if x['valid']}
 assert {'title','author','published','modified','publisher'} <= fields and s['text']=='One\nTwo' and s['lineCount']==2
 s,_=vr.fetch(server+'/unsafe-canonical'); assert s['canonicalUrl'] is None and any(not x['valid'] and x['field']=='canonicalUrl' for x in s['metadataCandidates'])

def test_claim_integrity_rules(tmp_path):
 text='A'; base={'schemaVersion':1,'sources':[{'id':'s','text':text,'textSha256':vr.digest(text.encode()),'finalUrl':'https://example.com','metadataCandidates':[]}],'claims':[{'id':'c','text':'X','status':'supported','confidence':2,'evidence':[]},{'id':'c','text':'','status':'bogus','evidence':[]}]}; base['manifestSha256']=vr.digest(vr.stable({k:v for k,v in base.items() if k!='manifestSha256'}).encode())
 issues,_=vr.validate_bundle(base); codes={x['code'] for x in issues}; assert {'VALID_EVIDENCE_REQUIRED','INVALID_CONFIDENCE','INVALID_OR_DUPLICATE_CLAIM_ID','INVALID_CLAIM_TEXT','INVALID_STATUS'} <= codes

def test_dates_future_and_malformed():
 s={'id':'s','text':'A','textSha256':vr.digest(b'A'),'finalUrl':'https://example.com','metadataCandidates':[vr.candidate('published','not-date','x'),vr.candidate('modified','2099-01-01T00:00:00Z','x')]}; b={'schemaVersion':1,'sources':[s],'claims':[]}; b['manifestSha256']=vr.digest(vr.stable(b).encode()); issues,_=vr.validate_bundle(b,as_of=vr.dt.datetime(2025,1,1,tzinfo=vr.dt.timezone.utc)); assert [x['code'] for x in issues].count('INVALID_DATE')==2

def test_symlink_root_parent_and_overwrite(tmp_path):
 real=tmp_path/'real'; real.mkdir(); link=tmp_path/'root'; link.symlink_to(real,target_is_directory=True)
 with pytest.raises(vr.VError): vr.root_path(link)
 parent=real/'p'; target=real/'target'; target.mkdir(); parent.symlink_to(target,target_is_directory=True)
 with pytest.raises(vr.VError): vr.safe_path(real,'p/x',output=True)
 out=real/'x'; vr.atomic(out,b'a');
 with pytest.raises(vr.VError,match='output exists'): vr.atomic(out,b'b')

def test_oversized_json_rejected_before_read(tmp_path):
 p=tmp_path/'huge.json'; p.write_bytes(b' '* (vr.MAX_INPUT+1))
 with pytest.raises(vr.VError,match='byte limit'): vr.load(tmp_path,'huge.json')

def test_pdf_timeout_and_overflow():
 class TimeoutP:
  def __init__(self,*a,**k): self.dead=False
  def poll(self): return 0 if self.dead else None
  def kill(self): self.dead=True
  def wait(self): return 0
 with pytest.raises(vr.VError,match='timed out'): vr.pdf_text(b'x',binary='/bin/echo',popen_factory=TimeoutP,timeout=.01)
 class BigP:
  def __init__(self,args,**k): Path(args[-1]).write_bytes(b'x'*101)
  def poll(self): return 0
  def kill(self): pass
  def wait(self): return 0
 with pytest.raises(vr.VError,match='exceeds'): vr.pdf_text(b'x',binary='/bin/echo',popen_factory=BigP,max_output=100)

def test_fetch_rejects_private_redirect_compression_and_length(server):
 for path,code in [('/private-redirect','UNSAFE_URL'),('/compressed','UNSUPPORTED_ENCODING'),('/declared-large','SIZE_LIMIT')]:
  with pytest.raises(vr.VError) as e: vr.fetch(server+path,max_bytes=100)
  assert e.value.code==code

def test_import_offline_url_plain_and_html_without_url(tmp_path):
 (tmp_path/'plain').write_text('A <b>B</b>'); a=type('A',(),dict(command='source.import',input_root=str(tmp_path),capture='plain',source_url='https://does-not-resolve.invalid/x',media_type='text/plain',output_root=None,output=None,max_bytes=100)); assert vr.cmd(a)['source']['text']=='A <b>B</b>'
 (tmp_path/'html').write_text('<link rel="canonical" href="/x"><p>A</p>'); a.capture='html'; a.source_url=None; a.media_type='text/html'; assert vr.cmd(a)['source']['canonicalUrl'] is None

def test_partial_cli_and_internal_error_redaction(tmp_path):
 (tmp_path/'m.json').write_text(json.dumps({'urls':['file:///bad']})); env=dict(os.environ); env['VERIFIED_RESEARCH_INTERNAL_TEST_MODE']='0'
 r=subprocess.run([sys.executable,str(P),'source.batch','--input-root',str(tmp_path),'--manifest','m.json'],text=True,capture_output=True,env=env); o=json.loads(r.stdout); assert r.returncode==3 and o['error']['code']=='PARTIAL_FAILURE' and o['data']['failures']
 (tmp_path/'list.json').write_text('[]'); r=subprocess.run([sys.executable,str(P),'bundle.inspect','--input-root',str(tmp_path),'--bundle','list.json'],text=True,capture_output=True); o=json.loads(r.stdout); assert r.returncode==5 and o['error']['code']=='INTERNAL_ERROR' and 'traceback' not in r.stdout.lower()

def test_deterministic_output_excluding_request_id(tmp_path):
 (tmp_path/'b.json').write_text(json.dumps({'schemaVersion':1,'sources':[],'claims':[],'manifestSha256':vr.digest(vr.stable({'schemaVersion':1,'sources':[],'claims':[]}).encode())})); a=type('A',(),dict(command='bundle.inspect',input_root=str(tmp_path),bundle='b.json')); x=vr.output(a.command,vr.cmd(a)); y=vr.output(a.command,vr.cmd(a)); x.pop('requestId'); y.pop('requestId'); assert x==y

def test_rfc_http_date_rss_and_namespaced_atom(server):
 html,_=vr.fetch(server+'/metadata'); modified=[x for x in html['metadataCandidates'] if x['field']=='modified' and x['method']=='http-header'][0]
 assert modified['rawValue']=='Tue, 02 Jan 2024 03:04:05 GMT' and modified['normalizedTimestamp']=='2024-01-02T03:04:05Z'
 rss,_=vr.fetch(server+'/rss'); atom,_=vr.fetch(server+'/atom')
 rc={(x['field'],x['rawValue']) for x in rss['metadataCandidates']}; ac={(x['field'],x['rawValue']) for x in atom['metadataCandidates']}
 assert ('link','https://example.com/story') in rc and ('author','Alice') in rc and ('published','Tue, 02 Jan 2024 03:04:05 +0000') in rc and ('publisher','Example Publisher') in rc
 assert ('link','https://example.com/entry') in ac and ('author','Entry Author') in ac and ('published','2024-01-02T00:00:00Z') in ac and ('publisher','Atom Publisher') in ac
 assert all(x['method'].startswith('feed-element:/') for x in rss['metadataCandidates'] if x['field'] in ('link','author','published','publisher'))
 assert vr.parse_date('Wed, 31 Feb 2024 10:00:00 GMT')[0] is False

def test_batch_snapshots_are_verifiable_and_tamper_detected(tmp_path,server):
 (tmp_path/'m.json').write_text(json.dumps({'urls':[server+'/html',server+'/json']}))
 a=type('A',(),dict(command='source.batch',input_root=str(tmp_path),manifest='m.json',output_root=str(tmp_path),output='batch.json',timeout=3,max_bytes=10000,overwrite=False))
 d=vr.cmd(a); assert len(d['writtenSnapshots'])==2 and all((tmp_path/x).is_file() for x in d['writtenSnapshots'])
 b={'schemaVersion':1,'sources':d['sources'],'claims':[]}; b['manifestSha256']=vr.digest(vr.stable(b).encode()); (tmp_path/'bundle.json').write_text(json.dumps(b))
 v=type('A',(),dict(command='bundle.validate',input_root=str(tmp_path),bundle='bundle.json',as_of=None)); assert vr.cmd(v)['valid']
 (tmp_path/d['writtenSnapshots'][0]).write_bytes(b'changed'); assert 'RAW_HASH_MISMATCH' in {x['code'] for x in vr.cmd(v)['issues']}

def test_snapshot_text_derivation_detects_recomputed_record(tmp_path):
 raw=b'Alpha\n'; (tmp_path/'raw.bytes').write_bytes(raw); text='Different'
 s={'id':'s','text':text,'textSha256':vr.digest(text.encode()),'rawSha256':vr.digest(raw),'rawBytes':len(raw),'mediaType':'text/plain','snapshotPath':'raw.bytes','finalUrl':'https://example.com','canonicalUrl':None,'metadataCandidates':[]}
 b={'schemaVersion':1,'sources':[s],'claims':[]}; b['manifestSha256']=vr.digest(vr.stable(b).encode()); issues,_=vr.validate_bundle(b,tmp_path)
 assert 'SNAPSHOT_TEXT_MISMATCH' in {x['code'] for x in issues}

def test_fixture_gate_requires_private_regular_owned_file(monkeypatch,tmp_path):
 monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE','1'); f=tmp_path/'f'; f.write_text('{}'); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(f))
 f.chmod(0o644)
 with pytest.raises(vr.VError): vr.syntax_url('http://127.0.0.1:8888',True,True)
 f.chmod(0o600); link=tmp_path/'link'; link.symlink_to(f); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(link))
 with pytest.raises(vr.VError): vr.syntax_url('http://127.0.0.1:8888',True,True)
 monkeypatch.setattr(vr.os,'getuid',lambda: f.stat().st_uid+1); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(f))
 with pytest.raises(vr.VError): vr.syntax_url('http://127.0.0.1:8888',True,True)

def test_output_root_must_exist_and_be_private(tmp_path):
 missing=tmp_path/'missing'
 with pytest.raises(vr.VError,match='already exist'): vr.root_path(missing,True)
 public=tmp_path/'public'; public.mkdir(); public.chmod(0o777)
 with pytest.raises(vr.VError,match='writable'): vr.root_path(public,True)

def test_source_candidate_evidence_and_contradiction_limits():
 raw=b'A'; bad_candidates=[{'field':'x','rawValue':'v','method':'m','confidence':'medium','valid':True}]*101
 s={'id':'s','text':'A','textSha256':vr.digest(raw),'rawSha256':vr.digest(raw),'rawBytes':1,'mediaType':'text/plain','finalUrl':'https://example.com','metadataCandidates':bad_candidates}
 claims=[{'id':'a','text':'A','status':'supported','evidence':[{'sourceId':'missing','startLine':1,'endLine':1,'quote':'A'}],'contradictions':[{'claimId':'missing','reason':'x'}]}]
 b={'schemaVersion':1,'sources':[s],'claims':claims}; b['manifestSha256']=vr.digest(vr.stable(b).encode()); issues,_=vr.validate_bundle(b); codes={x['code'] for x in issues}
 assert {'INVALID_METADATA_CANDIDATES','MISSING_SOURCE','VALID_EVIDENCE_REQUIRED','INVALID_CONTRADICTION'} <= codes
 s['metadataCandidates']=[{'field':1,'rawValue':'x'*4001,'method':False,'confidence':'bogus','valid':'yes'}]; b['manifestSha256']=vr.digest(vr.stable({k:v for k,v in b.items() if k!='manifestSha256'}).encode()); issues,_=vr.validate_bundle(b); assert 'INVALID_METADATA_CANDIDATE' in {x['code'] for x in issues}

def test_markdown_contains_evidence_inventory_and_escapes(monkeypatch):
 raw=b'Quote'; src={'id':'s','title':'# Fake heading','text':'Quote','textSha256':vr.digest(raw),'rawSha256':vr.digest(raw),'rawBytes':5,'mediaType':'text/plain','finalUrl':'https://example.com/a','canonicalUrl':None,'snapshotPath':'s.bytes','metadataCandidates':[vr.candidate('publisher','Pub','x'),vr.candidate('published','2024-01-02','x')]}
 claims=[{'id':'c','text':'Claim','status':'supported','confidence':.9,'evidence':[{'sourceId':'s','startLine':1,'endLine':1,'quote':'Quote'}],'contradictions':[]}]; b={'schemaVersion':1,'sources':[src],'claims':claims}; data=vr.render_markdown(b,[]).decode()
 assert '## Claim: c' in data and '- Status: supported' in data and '- Confidence: 0.9' in data and '- Publisher: Pub' in data and '- Date: 2024-01-02' in data and '- Lines: 1-1' in data and 'Raw SHA-256' in data and 'Snapshot: s.bytes' in data and '\\# Fake heading' in data
 monkeypatch.setattr(vr,'MAX_OUTPUT',100)
 with pytest.raises(vr.VError,match='Markdown'): vr.render_markdown(b,[])

def test_pdf_snapshot_reextraction_unavailable_is_warning(monkeypatch,tmp_path):
 raw=b'%PDF-1.4\n'; (tmp_path/'p.bytes').write_bytes(raw); monkeypatch.setattr(vr.shutil,'which',lambda _:None)
 s={'id':'p','text':'','textSha256':vr.digest(b''),'rawSha256':vr.digest(raw),'rawBytes':len(raw),'mediaType':'application/pdf','snapshotPath':'p.bytes','finalUrl':'https://example.com/p.pdf','metadataCandidates':[]}
 b={'schemaVersion':1,'sources':[s],'claims':[]}; b['manifestSha256']=vr.digest(vr.stable(b).encode()); issues,warnings=vr.validate_bundle(b,tmp_path)
 assert not issues and 'TEXT_REEXTRACTION_UNAVAILABLE' in {x['code'] for x in warnings}

def run_cli(args,env=None):
 return subprocess.run([sys.executable,str(P),*args],text=True,capture_output=True,env=env)

def test_cli_absolute_roots_nested_relative_children_and_fetch_without_snapshot(tmp_path,server):
 nested=tmp_path/'nested'; nested.mkdir(); (nested/'capture.txt').write_text('Alpha\nBeta'); (nested/'manifest.json').write_text(json.dumps({'urls':[server+'/html']}))
 env=dict(os.environ)
 fetched=run_cli(['source.fetch','--url',server+'/html'],env); assert fetched.returncode==0 and json.loads(fetched.stdout)['data']['source']['text']=='A B\nC'
 batch=run_cli(['source.batch','--input-root',str(tmp_path.resolve()),'--manifest','nested/manifest.json','--output-root',str(tmp_path.resolve()),'--output','nested/results/batch.json'],env); assert batch.returncode==0
 batch_data=json.loads((nested/'results/batch.json').read_text()); assert batch_data['sources'][0]['snapshotPath'].startswith('nested/results/batch.json.snapshots/')
 imported=run_cli(['source.import','--input-root',str(tmp_path.resolve()),'--capture','nested/capture.txt','--output-root',str(tmp_path.resolve()),'--output','nested/records/source.json'],env); assert imported.returncode==0
 source=json.loads((nested/'records/source.json').read_text()); (nested/'sources.json').write_text(json.dumps({'sources':[source]})); (nested/'claims.json').write_text(json.dumps({'claims':[{'id':'c','text':'Alpha exists','status':'supported','evidence':[{'sourceId':source['id'],'startLine':1,'endLine':1,'quote':'Alpha'}]}]}))
 built=run_cli(['bundle.build','--input-root',str(tmp_path.resolve()),'--sources','nested/sources.json','--claims','nested/claims.json','--output-root',str(tmp_path.resolve()),'--output','nested/bundles/evidence.json'],env); assert built.returncode==0
 validated=run_cli(['bundle.validate','--input-root',str(tmp_path.resolve()),'--bundle','nested/bundles/evidence.json'],env); assert validated.returncode==0 and json.loads(validated.stdout)['data']['valid']
 inspected=run_cli(['bundle.inspect','--input-root',str(tmp_path.resolve()),'--bundle','nested/bundles/evidence.json'],env); assert inspected.returncode==0 and json.loads(inspected.stdout)['data']['claimCount']==1

def test_cli_incomplete_output_root_name_pairs_fail(tmp_path):
 nested=tmp_path/'nested'; nested.mkdir(); (nested/'capture').write_text('x'); (nested/'manifest.json').write_text(json.dumps({'urls':['https://example.com']}))
 cases=[
  ['source.fetch','--url','https://example.com','--output-root',str(tmp_path)],
  ['source.fetch','--url','https://example.com','--snapshot','nested/x.json'],
  ['source.batch','--input-root',str(tmp_path),'--manifest','nested/manifest.json','--output-root',str(tmp_path)],
  ['source.import','--input-root',str(tmp_path),'--capture','nested/capture','--output','nested/x.json'],
  ['source.import','--input-root',str(tmp_path),'--capture','nested/capture','--output-root',str(tmp_path)],
 ]
 for args in cases:
  r=run_cli(args); assert r.returncode==2, (args,r.stdout,r.stderr)
  assert json.loads(r.stdout)['error']['code']=='MALFORMED_INPUT'
