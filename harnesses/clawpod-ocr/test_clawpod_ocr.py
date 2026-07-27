import importlib.util, io, json, os, pathlib, socket, tempfile, threading, time, unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
P=pathlib.Path(__file__).with_name('clawpod_ocr.py');S=importlib.util.spec_from_file_location('ocr',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class A:pass
def args(cmd,**kw):
 a=A();defaults=dict(command=cmd,state_root=None,input_root=None,input=None,output_root=None,output='result.json',format='json',language='kor+eng',preprocess='default',job_id=None,owner='u',detached=False,endpoint=None,model='llava',secret=None,auth_mode='env',auth_env='CLAWPOD_OLLAMA_TOKEN',timeout=2,threshold=.75,approved=False,correction_id=None,page=None,worker_nonce=None);defaults.update(kw)
 for k,v in defaults.items():setattr(a,k,v)
 return a
def call(a):
 b=io.StringIO()
 with redirect_stdout(b):code=M.run(a)
 return code,json.loads(b.getvalue())
def ppm(w=1,h=1):return f'P6\n{w} {h}\n255\n'.encode()+b'\0\0\0'*(w*h)
class H(BaseHTTPRequestHandler):
 malformed=False;caps=['vision'];seen=[];auth=None;delay=0
 def log_message(self,*x):pass
 def reply(self,x):
  raw=(b'{' if self.malformed else json.dumps(x).encode());self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers()
  try:self.wfile.write(raw)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_GET(self):
  if self.delay:time.sleep(self.delay)
  self.auth=self.headers.get('Authorization');self.reply({'version':'1'} if self.path=='/api/version' else {'models':[{'name':'llava'}]})
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));body=json.loads(self.rfile.read(n));H.seen.append((self.path,body,self.headers.get('Authorization')))
  self.reply({'capabilities':H.caps} if self.path=='/api/show' else {'response':'corrected'})
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.r=pathlib.Path(self.t.name);self.i=self.r/'in';self.s=self.r/'state';self.i.mkdir();self.bin=self.r/'bin';self.bin.mkdir();self.old=os.environ['PATH'];os.environ['PATH']=str(self.bin)+os.pathsep+self.old;H.malformed=False;H.caps=['vision'];H.seen=[];H.delay=0
 def tearDown(self):os.environ['PATH']=self.old;os.environ.pop('CLAWPOD_OLLAMA_TOKEN',None);os.environ.pop('TOKEN_FILE',None);self.t.cleanup()
 def fake(self,name,body):p=self.bin/name;p.write_text('#!/bin/sh\n'+body);p.chmod(0o755)
 def engines(self):
  self.fake('pdfinfo','printf "Pages: 3\\n"');self.fake('pdftotext','exit 0');self.fake('pdftoppm','page="$3"; out="$8"; printf "P6\\n1 1\\n255\\n\\0\\0\\0" > "$out.ppm"');self.fake('tesseract','if [ "$1" = "--version" ]; then echo "tesseract 5.3.0"; elif [ "$1" = "--list-langs" ]; then printf "List of available languages (3):\\nkor\\neng\\nosd\\n"; else printf "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n5\\t1\\t1\\t1\\t1\\t1\\t0\\t0\\t1\\t1\\t60\\tpage-$1\\n"; fi')
 def server(self):
  s=ThreadingHTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=s.serve_forever,daemon=True);t.start();self.addCleanup(lambda:(s.shutdown(),s.server_close(),t.join(2)));return f'http://127.0.0.1:{s.server_port}'
 def test_engine_semantics_and_persisted_onboarding(self):
  self.engines();_,r=call(args('engine.requirements',state_root=str(self.s)));self.assertNotIn('verified',r['data']);_,v=call(args('engine.verify',state_root=str(self.s)));self.assertEqual(v['data']['state'],'verified');self.assertEqual(v['data']['major'],5);_,p=call(args('system.preflight',state_root=str(self.s)));self.assertTrue(p['data']['ready']);_,o=call(args('onboarding.status',state_root=str(self.s)));self.assertEqual(o['data']['local']['state'],'verified')
 def test_verify_rejects_missing_language(self):
  self.fake('tesseract','if [ "$1" = "--version" ]; then echo "tesseract 5.0"; else echo eng; fi');_,x=call(args('engine.verify',state_root=str(self.s)));self.assertEqual(x['data']['state'],'verification-failed');self.assertIn('kor',x['data']['missingLanguages'])
 def test_pixel_ceiling_and_fail_closed_header(self):
  (self.i/'huge.ppm').write_bytes(b'P6\n50000 50000\n255\n');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='huge.ppm'));self.assertFalse(x['ok']);(self.i/'bad.png').write_bytes(b'x');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='bad.png'));self.assertFalse(x['ok'])
 def test_multipage_checkpoint_and_resume(self):
  self.engines();(self.i/'a.pdf').write_bytes(b'%PDF-1.4 synthetic');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.pdf',job_id='p'));self.assertTrue(x['ok']);m=json.loads((self.s/'jobs/p/job.json').read_text());self.assertEqual(m['completedPages'],3);self.assertEqual(len(json.loads((self.s/'jobs/p/result.json').read_text())['pages']),3);self.assertFalse((self.s/'jobs/p/tmp').exists())
  r=json.loads((self.s/'jobs/p/result.json').read_text());m['status']='interrupted';m['pages']=r['pages'][:2];m['completedPages']=2;(self.s/'jobs/p/result.json').unlink();M.atomic(self.s/'jobs/p/job.json',m);_,x=call(args('job.resume',state_root=str(self.s),job_id='p'));self.assertEqual(x['data']['status'],'completed');self.assertEqual(len(json.loads((self.s/'jobs/p/result.json').read_text())['pages']),3)
 def test_real_detached_worker_and_status(self):
  (self.i/'a.txt').write_text('hello');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='d',detached=True));self.assertTrue(x['data']['workerPid']>0)
  for _ in range(100):
   _,st=call(args('job.status',state_root=str(self.s),job_id='d'))
   if st['data']['status']=='completed':break
   time.sleep(.02)
  self.assertEqual(st['data']['status'],'completed');self.assertTrue((self.s/'jobs/d/result.json').exists());_,bad=call(args('job.cancel',state_root=str(self.s),job_id='d',owner='bad'));self.assertFalse(bad['ok'])
 def test_cancel_refuses_foreign_identity(self):
  (self.i/'a.txt').write_text('x');call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='c'));m=json.loads((self.s/'jobs/c/job.json').read_text());m.update(status='running',workerPid=os.getpid(),workerStartIdentity='wrong');M.atomic(self.s/'jobs/c/job.json',m);_,x=call(args('job.cancel',state_root=str(self.s),job_id='c'));self.assertEqual(x['data']['status'],'cancelled');self.assertTrue(M.proc_start(os.getpid()))
 def test_cancel_actual_owned_worker(self):
  self.fake('tesseract','sleep 10');(self.i/'slow.ppm').write_bytes(ppm());_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='slow.ppm',job_id='slow',detached=True,timeout=30));pid=x['data']['workerPid'];_,x=call(args('job.cancel',state_root=str(self.s),job_id='slow',timeout=2));self.assertEqual(x['data']['status'],'cancelled');self.assertIsNone(M.proc_start(pid))
 def test_export_escape_markdown_and_symlink(self):
  (self.i/'a.txt').write_text('<script>&');call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='e'));call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='x.html',format='hocr'));self.assertIn('&lt;script&gt;&amp;', (self.r/'x.html').read_text());call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='x.md',format='markdown'));self.assertTrue((self.r/'x.md').read_text().startswith('## Page 1'));(self.r/'link').symlink_to(self.r/'real');_,x=call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='link/x',format='txt'));self.assertFalse(x['ok'])
 def setup_review(self,secret=None,auth_mode='env',auth_env='CLAWPOD_OLLAMA_TOKEN'):
  ep=self.server();_,x=call(args('ollama.configure',state_root=str(self.s),endpoint=ep,secret=secret,auth_mode=auth_mode,auth_env=auth_env));self.assertTrue(x['ok']);return ep
 def test_vision_image_request_and_explicit_apply(self):
  self.setup_review();_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok']);self.engines();(self.i/'a.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.ppm',job_id='r'));raw_before=(self.s/'jobs/r/result.json').read_bytes();_,x=call(args('review.start',state_root=str(self.s),job_id='r',approved=True));self.assertTrue(x['ok']);post=[b for path,b,a in H.seen if path=='/api/generate'][-1];self.assertTrue(post['images'][0]);self.assertEqual((self.s/'jobs/r/result.json').read_bytes(),raw_before);corr=json.loads((self.s/'jobs/r/corrections.json').read_text())['items'][0];_,no=call(args('correction.apply',state_root=str(self.s),job_id='r'));self.assertFalse(no['ok']);_,yes=call(args('correction.apply',state_root=str(self.s),job_id='r',correction_id=[corr['id']]));self.assertEqual(yes['data']['applied'],[corr['id']]);self.assertEqual((self.s/'jobs/r/result.json').read_bytes(),raw_before)
 def test_auth_injection_and_permissions(self):
  self.setup_review('secret:pointer');_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);os.environ['CLAWPOD_OLLAMA_TOKEN']='tok';_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok']);self.assertTrue(all(a=='Bearer tok' for _,_,a in H.seen));self.assertNotIn('tok',(self.s/'ollama.json').read_text())
  self.s.mkdir(exist_ok=True);(self.s/'ollama.json').unlink();self.setup_review('secret:pointer','file-env','TOKEN_FILE');f=self.r/'token';f.write_text('tok');f.chmod(0o644);os.environ['TOKEN_FILE']=str(f);_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);f.chmod(0o600);_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok'])
 def test_model_vision_incompatible_and_malformed(self):
  self.setup_review();H.caps=['completion'];_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'model_vision_incompatible');H.caps=['vision'];H.malformed=True;_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'configured_unverified')
 def test_ollama_timeout_is_bounded_and_unverified(self):
  self.setup_review();H.delay=.3;_,x=call(args('ollama.verify',state_root=str(self.s),timeout=.1));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'configured_unverified')
if __name__=='__main__':unittest.main()
