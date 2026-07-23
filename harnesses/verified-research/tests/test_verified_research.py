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
  elif self.path=='/unsafe-canonical': body=b'<link rel="canonical" href="http://169.254.169.254/private"><p>X</p>'; typ='text/html'
  elif self.path=='/large': body=b'x'*200; typ='text/plain'
  elif self.path=='/json': body=b'{"b":2,"a":1}'; typ='application/json'
  elif self.path=='/feed': body=b'<?xml version="1.0"?><rss><channel><title>Feed</title><item><title>One</title></item></channel></rss>'; typ='application/rss+xml'
  elif self.path=='/pdf': body=b'%PDF-1.4\nnot a complete pdf'; typ='application/pdf'
  else: body=b'<html><head><title>T</title><link rel="canonical" href="/canonical"></head><body>A  B\nC<script>ignore</script></body></html>'; typ='text/html'
  self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
 def log_message(self,*a): pass

@pytest.fixture
def server(monkeypatch,tmp_path):
 fixture=tmp_path/'fixture.json'; fixture.write_text('{}')
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
 fixture=tmp_path/'fixture.json'; fixture.write_text('{}'); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE','1'); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_FIXTURE',str(fixture))
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
 text='Alpha\nBeta'; s={'id':'s1','text':text,'textSha256':vr.digest(text.encode()),'finalUrl':'https://example.com/a','canonicalUrl':None}
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
 h=json.loads((P.parent/'harness.json').read_text())
 for c in h['commands'].values():
  for a in c['argMap']:
   if a['valueType']=='path': assert a['pathRole'] in ('input','output')
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
 issues,_=vr.validate_bundle(base); codes={x['code'] for x in issues}; assert {'EVIDENCE_REQUIRED','INVALID_CONFIDENCE','INVALID_OR_DUPLICATE_CLAIM_ID','INVALID_CLAIM_TEXT','INVALID_STATUS'} <= codes

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

def test_pdf_timeout_and_overflow(monkeypatch):
 monkeypatch.setattr(vr.shutil,'which',lambda x:'/bin/echo')
 class TimeoutP:
  def __init__(self,*a,**k): pass
  def communicate(self,*a,**k):
   if 'timeout' in k: raise subprocess.TimeoutExpired('x',1)
   return b'',b''
  def kill(self): pass
 monkeypatch.setattr(vr.subprocess,'Popen',TimeoutP)
 with pytest.raises(vr.VError,match='timed out'): vr.pdf_text(b'x')
 class BigP:
  def __init__(self,*a,**k): pass
  def communicate(self,*a,**k): return b'x'*(vr.MAX_TEXT+1),b''
  def kill(self): pass
 monkeypatch.setattr(vr.subprocess,'Popen',BigP)
 with pytest.raises(vr.VError,match='exceeds'): vr.pdf_text(b'x')

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
