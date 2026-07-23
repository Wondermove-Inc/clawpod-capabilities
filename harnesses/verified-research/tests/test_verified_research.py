import importlib.util, json, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pytest

P=Path(__file__).parents[1]/'verified_research.py'
spec=importlib.util.spec_from_file_location('vr',P); vr=importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)

class H(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/redirect': self.send_response(302); self.send_header('Location','/html'); self.end_headers(); return
  if self.path=='/large': body=b'x'*200; typ='text/plain'
  elif self.path=='/json': body=b'{"b":2,"a":1}'; typ='application/json'
  elif self.path=='/feed': body=b'<?xml version="1.0"?><rss><channel><title>Feed</title><item><title>One</title></item></channel></rss>'; typ='application/rss+xml'
  elif self.path=='/pdf': body=b'%PDF-1.4\nnot a complete pdf'; typ='application/pdf'
  else: body=b'<html><head><title>T</title><link rel="canonical" href="/canonical"></head><body>A  B\nC<script>ignore</script></body></html>'; typ='text/html'
  self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
 def log_message(self,*a): pass

@pytest.fixture
def server(monkeypatch):
 s=HTTPServer(('127.0.0.1',0),H); t=threading.Thread(target=s.serve_forever,daemon=True); t.start(); monkeypatch.setenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE','1'); yield f'http://127.0.0.1:{s.server_port}'; s.shutdown()

def test_html_redirect_canonical_deterministic(server):
 a=vr.fetch(server+'/redirect'); b=vr.fetch(server+'/html')
 assert a['text']=='T\nA B\nC' and a['canonicalUrl'].endswith('/canonical') and a['rawSha256']==b['rawSha256']

def test_json_feed_pdf_states(server):
 assert vr.fetch(server+'/json')['text'].find('"a"') < vr.fetch(server+'/json')['text'].find('"b"')
 assert 'Feed' in vr.fetch(server+'/feed')['text']
 assert vr.fetch(server+'/pdf')['extraction'] in ('dependency_missing','unsupported')

def test_size_limit(server):
 with pytest.raises(vr.VError,match='byte limit'): vr.fetch(server+'/large',max_bytes=20)

@pytest.mark.parametrize('url',['file:///etc/passwd','http://user:pass@example.com','http://localhost','http://127.0.0.1','http://0.0.0.0','http://169.254.169.254','http://[::1]','http://example.com:22'])
def test_ssrf_rejections(monkeypatch,url):
 monkeypatch.delenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE',raising=False)
 with pytest.raises(vr.VError): vr.clean_url(url)

def test_test_seam_requires_flag(monkeypatch):
 monkeypatch.delenv('VERIFIED_RESEARCH_INTERNAL_TEST_MODE',raising=False)
 with pytest.raises(vr.VError): vr.clean_url('http://127.0.0.1:8888')
 assert vr.clean_url('http://127.0.0.1:8888',True).startswith('http://127.0.0.1:8888')

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
 r=vr.cmd(a); assert r['partial'] and r['sources'][1]['duplicateOf']==r['sources'][0]['id']; assert len(r['failures'])==1

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
 b=build_bundle(tmp_path,'conflicted','wrong'); b['claims'][0]['evidence'].append({'sourceId':'missing','startLine':1,'endLine':1,'quote':'x'}); b['sources'][0]['text']='tampered'; (tmp_path/'bad.json').write_text(json.dumps(b))
 a=type('A',(),dict(command='bundle.validate',input_root=str(tmp_path),bundle='bad.json')); codes={x['code'] for x in vr.cmd(a)['issues']}
 assert {'MANIFEST_TAMPERED','TEXT_HASH_MISMATCH','QUOTE_MISMATCH','MISSING_SOURCE','UNRESOLVED_CLAIM'} <= codes

def test_malformed_and_manifest_bound(tmp_path):
 (tmp_path/'bad.json').write_text('{');
 with pytest.raises(vr.VError): vr.load(tmp_path,'bad.json')
 (tmp_path/'many.json').write_text(json.dumps({'urls':['https://example.com']*51})); a=type('A',(),dict(command='source.batch',input_root=str(tmp_path),manifest='many.json',output_root=None,output=None,timeout=1,max_bytes=10))
 with pytest.raises(vr.VError): vr.cmd(a)

def test_no_secret_in_http_failure(server):
 with pytest.raises(vr.VError) as e: vr.clean_url('http://token:secret@example.com')
 assert 'token' not in e.value.message and 'secret' not in e.value.message

def test_command_schema_path_roles_and_simple_types():
 h=json.loads((P.parent/'harness.json').read_text())
 for c in h['commands'].values():
  for a in c['argMap']:
   if a['valueType']=='path': assert a['pathRole'] in ('input','output')
  assert all(v.get('type') in ('string','integer','boolean','number') for v in c['inputSchema']['properties'].values())
