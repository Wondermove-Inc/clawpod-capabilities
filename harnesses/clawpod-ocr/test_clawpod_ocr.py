import importlib.util, io, json, os, pathlib, tempfile, threading, unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler,HTTPServer
P=pathlib.Path(__file__).with_name('clawpod_ocr.py');S=importlib.util.spec_from_file_location('ocr',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class A: pass
def args(cmd,**kw):
 a=A(); defaults=dict(command=cmd,state_root=None,input_root=None,input=None,output_root=None,output='result.json',format='json',language='kor+eng',preprocess='default',job_id=None,owner='u',detached=False,endpoint=None,model='llava',secret=None,timeout=2,threshold=.75,approved=False)
 defaults.update(kw)
 for k,v in defaults.items():setattr(a,k,v)
 return a
def call(a):
 b=io.StringIO()
 with redirect_stdout(b):code=M.run(a)
 return code,json.loads(b.getvalue())
class H(BaseHTTPRequestHandler):
 malformed=False
 def log_message(self,*x):pass
 def do_GET(self):
  x={'version':'1'} if self.path=='/api/version' else {'models':[{'name':'llava'}]};self.send_response(200);self.end_headers();self.wfile.write(json.dumps(x).encode())
 def do_POST(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'{}' if self.malformed else b'{"response":"corrected"}')
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.r=pathlib.Path(self.t.name);self.i=self.r/'in';self.s=self.r/'state';self.i.mkdir();self.bin=self.r/'bin';self.bin.mkdir();self.old=os.environ['PATH'];os.environ['PATH']=str(self.bin)+os.pathsep+self.old
 def tearDown(self):os.environ['PATH']=self.old;self.t.cleanup()
 def fake(self,name,body):
  p=self.bin/name;p.write_text('#!/bin/sh\n'+body);p.chmod(0o755)
 def test_onboarding_and_resources(self):
  _,x=call(args('onboarding.status',state_root=str(self.s)));self.assertEqual(x['data']['ollamaState'],'deferred');_,x=call(args('system.preflight',state_root=str(self.s)));self.assertEqual(x['data']['resource']['workerLimit'],1)
 def test_text_fast_cache_lifecycle(self):
  (self.i/'a.txt').write_text('hello');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='j'));self.assertTrue(x['ok']);_,v=call(args('result.validate',state_root=str(self.s),job_id='j'));self.assertTrue(v['data']['valid']);_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='j2'));self.assertTrue(x['data']['cacheHit']);_,x=call(args('job.cancel',state_root=str(self.s),job_id='j2'));self.assertEqual(x['data']['status'],'cancelled')
 def test_pdf_text_layer_fast_path_and_exports(self):
  self.fake('pdftotext','printf "PDF text layer"');(self.i/'a.pdf').write_bytes(b'%PDF-1.4 synthetic');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.pdf',job_id='p'));self.assertTrue(x['ok']);r=json.loads((self.s/'jobs/p/result.json').read_text());self.assertEqual(r['pages'][0]['provenance']['engine'],'text-layer')
  for fmt in ('txt','markdown','json','tsv','hocr'):
   _,x=call(args('result.export',state_root=str(self.s),job_id='p',output_root=str(self.r),output=f'x.{fmt}',format=fmt));self.assertTrue(x['ok'])
 def test_fake_tesseract_languages_and_low_confidence(self):
  self.fake('tesseract','printf "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n5\\t1\\t1\\t1\\t1\\t1\\t0\\t0\\t1\\t1\\t60\\t테스트\\n"')
  for n,lang in enumerate(('kor','eng','kor+eng')):
   (self.i/f'{n}.png').write_bytes(b'x');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input=f'{n}.png',job_id=f'j{n}',language=lang));self.assertTrue(x['ok'])
  _,x=call(args('review.export-low-confidence',state_root=str(self.s),job_id='j0',output_root=str(self.r),output='low.json',threshold=.75));self.assertEqual(x['data']['count'],1)
 def test_detached_resume_owner(self):
  (self.i/'a.txt').write_text('x');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='d',detached=True));self.assertEqual(x['data']['status'],'running');_,x=call(args('job.status',state_root=str(self.s),job_id='d',owner='bad'));self.assertFalse(x['ok']);_,x=call(args('job.resume',state_root=str(self.s),job_id='d'));self.assertEqual(x['data']['status'],'completed')
 def test_path_symlink_corrupt_oversize(self):
  (self.i/'bad.pdf').write_bytes(b'bad');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='bad.pdf'));self.assertFalse(x['ok']);_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='../x'));self.assertFalse(x['ok']);(self.r/'x').write_text('x');(self.i/'l.txt').symlink_to(self.r/'x');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='l.txt'));self.assertFalse(x['ok']);old=M.MAX_FILE;M.MAX_FILE=1;(self.i/'b.txt').write_text('xx');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='b.txt'));self.assertFalse(x['ok']);M.MAX_FILE=old
 def test_ollama_guards_verify_correction(self):
  _,x=call(args('ollama.configure',state_root=str(self.s),endpoint='http://example.com',secret='plain'));self.assertFalse(x['ok']);srv=HTTPServer(('127.0.0.1',0),H);threading.Thread(target=srv.serve_forever,daemon=True).start();ep=f'http://127.0.0.1:{srv.server_port}';_,x=call(args('ollama.configure',state_root=str(self.s),endpoint=ep,secret='secret:pointer'));self.assertNotIn('plain',json.dumps(x));_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok']);(self.i/'a.txt').write_text('raw');call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='r'));r=json.loads((self.s/'jobs/r/result.json').read_text());r['pages'][0]['confidence']=.2;M.atomic(self.s/'jobs/r/result.json',r);_,x=call(args('review.start',state_root=str(self.s),job_id='r',approved=True));self.assertTrue(x['ok']);_,x=call(args('correction.apply',state_root=str(self.s),job_id='r'));self.assertEqual(x['data']['rawResult'],'result.json');H.malformed=True;_,x=call(args('review.start',state_root=str(self.s),job_id='r',approved=True));self.assertFalse(x['ok']);self.assertTrue(x['data']['localResultPreserved']);srv.shutdown()
if __name__=='__main__':unittest.main()
