import importlib.util, io, json, os, pathlib, socket, tempfile, threading, time, unittest, zipfile
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
P=pathlib.Path(__file__).with_name('clawpod_ocr.py');S=importlib.util.spec_from_file_location('ocr',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class A:pass
def args(cmd,**kw):
 a=A();defaults=dict(command=cmd,state_root=None,input_root=None,input=None,output_root=None,output='result.json',format='json',language='kor+eng',preprocess='default',job_id=None,job_ids=None,owner='u',detached=False,endpoint=None,model='llava',secret=None,auth_mode='env',auth_env='CLAWPOD_OLLAMA_TOKEN',timeout=2,threshold=.75,security_label='INTERNAL',document_id=None,approved=False,approval_digest=None,correction_id=None,page=None,worker_nonce=None);defaults.update(kw)
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
  self.t=tempfile.TemporaryDirectory();self.r=pathlib.Path(self.t.name);self.i=self.r/'in';self.s=self.r/'state';self.i.mkdir();self.bin=self.r/'bin';self.bin.mkdir();self.old=os.environ['PATH'];os.environ['PATH']=str(self.bin)+os.pathsep+self.old;H.malformed=False;H.caps=['vision'];H.seen=[];H.delay=0;self.engines();call(args('engine.verify',state_root=str(self.s)))
 def tearDown(self):os.environ['PATH']=self.old;os.environ.pop('CLAWPOD_OLLAMA_TOKEN',None);os.environ.pop('TOKEN_FILE',None);self.t.cleanup()
 def fake(self,name,body):p=self.bin/name;p.write_text('#!/bin/sh\n'+body);p.chmod(0o755)
 def engines(self):
  self.fake('pdfinfo','printf "Pages: 3\\n"');self.fake('pdftotext','exit 0');self.fake('pdftoppm','[ "$1" = "-r" ] && [ "$2" = "200" ] || exit 9; for out; do :; done; printf "P6\\n1 1\\n255\\n\\0\\0\\0" > "$out.ppm"');self.fake('tesseract','if [ "$1" = "--version" ]; then echo "tesseract 5.3.0"; elif [ "$1" = "--list-langs" ]; then printf "List of available languages (3):\\nkor\\neng\\nosd\\n"; else printf "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n5\\t1\\t1\\t1\\t1\\t1\\t0\\t0\\t1\\t1\\t60\\tpage-$1\\n"; fi')
 def server(self):
  s=ThreadingHTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=s.serve_forever,daemon=True);t.start();self.addCleanup(lambda:(s.shutdown(),s.server_close(),t.join(2)));return f'http://127.0.0.1:{s.server_port}'
 def test_gateway_boolean_option_shape(self):
  parsed=M.parser().parse_args(['ocr.start','--detached','true','--approved','false']);self.assertTrue(parsed.detached);self.assertFalse(parsed.approved)
 def test_engine_semantics_and_persisted_onboarding(self):
  self.engines();_,r=call(args('engine.requirements',state_root=str(self.s)));self.assertNotIn('verified',r['data']);_,v=call(args('engine.verify',state_root=str(self.s)));self.assertEqual(v['data']['state'],'verified');self.assertEqual(v['data']['major'],5);_,p=call(args('system.preflight',state_root=str(self.s)));self.assertTrue(p['data']['ready']);_,o=call(args('onboarding.status',state_root=str(self.s)));self.assertEqual(o['data']['local']['state'],'verified')
 def test_verify_rejects_missing_language(self):
  self.fake('tesseract','if [ "$1" = "--version" ]; then echo "tesseract 5.0"; else echo eng; fi');_,x=call(args('engine.verify',state_root=str(self.s)));self.assertEqual(x['data']['state'],'verification-failed');self.assertIn('kor',x['data']['missingLanguages'])
 def test_ocr_requires_persisted_current_engine_verification(self):
  (self.s/'local-onboarding.json').unlink();(self.i/'a.txt').write_text('x');_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='unverified'));self.assertFalse(x['ok']);self.assertIn('engine.verify',x['error']['message'])
 def test_pixel_ceiling_and_fail_closed_header(self):
  (self.i/'huge.ppm').write_bytes(b'P6\n50000 50000\n255\n');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='huge.ppm'));self.assertFalse(x['ok']);(self.i/'bad.png').write_bytes(b'x');_,x=call(args('document.inspect',state_root=str(self.s),input_root=str(self.i),input='bad.png'));self.assertFalse(x['ok'])
 def test_quick_single_image_returns_validated_text_and_cache(self):
  (self.i/'quick.ppm').write_bytes(ppm());_,first=call(args('ocr.quick',state_root=str(self.s),input_root=str(self.i),input='quick.ppm',job_id='quick-1'));self.assertTrue(first['ok']);self.assertTrue(first['data']['valid']);self.assertTrue(first['data']['rawPreserved']);self.assertFalse(first['data']['cacheHit']);self.assertIn('page-',first['data']['text']);_,second=call(args('ocr.quick',state_root=str(self.s),input_root=str(self.i),input='quick.ppm',job_id='quick-2'));self.assertTrue(second['data']['cacheHit']);self.assertEqual(second['data']['sourceDigest'],first['data']['sourceDigest']);(self.i/'quick.pdf').write_bytes(b'%PDF-1.4 synthetic');_,bad=call(args('ocr.quick',state_root=str(self.s),input_root=str(self.i),input='quick.pdf',job_id='quick-pdf'));self.assertFalse(bad['ok'])
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
  self.fake('tesseract','if [ "$1" = "--version" ]; then echo "tesseract 5.3.0"; elif [ "$1" = "--list-langs" ]; then printf "kor\\neng\\nosd\\n"; else sleep 10; fi');(self.i/'slow.ppm').write_bytes(ppm());_,x=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='slow.ppm',job_id='slow',detached=True,timeout=30));pid=x['data']['workerPid'];_,x=call(args('job.cancel',state_root=str(self.s),job_id='slow',timeout=2));self.assertEqual(x['data']['status'],'cancelled');self.assertIsNone(M.proc_start(pid))
 def test_export_escape_markdown_and_symlink(self):
  (self.i/'a.txt').write_text('<script>&');call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.txt',job_id='e'));call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='x.html',format='hocr'));self.assertIn('&lt;script&gt;&amp;', (self.r/'x.html').read_text());call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='x.md',format='markdown'));self.assertTrue((self.r/'x.md').read_text().startswith('## Page 1'));(self.r/'link').symlink_to(self.r/'real');_,x=call(args('result.export',state_root=str(self.s),job_id='e',output_root=str(self.r),output='link/x',format='txt'));self.assertFalse(x['ok'])
 def test_single_and_multi_file_enterprise_docx(self):
  for n in ('one','two'):
   (self.i/f'{n}.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input=f'{n}.ppm',job_id=n))
  raw=(self.s/'jobs/one/result.json').read_bytes();r=json.loads(raw);r['pages'][0]['correctedText']='normalized text';M.atomic(self.s/'jobs/one/result.corrected.json',r)
  _,one=call(args('report.create',state_root=str(self.s),job_ids='one',output_root=str(self.r),output='one.docx',document_id='DOC-ONE',security_label='CONFIDENTIAL'));self.assertTrue(one['ok']);self.assertEqual((self.s/'jobs/one/result.json').read_bytes(),raw)
  with zipfile.ZipFile(self.r/'one.docx') as z:
   names=set(z.namelist());xml=z.read('word/document.xml').decode();self.assertIn('[Content_Types].xml',names);self.assertTrue(any(x.startswith('word/media/') for x in names));self.assertIn('DOC-ONE',xml);self.assertIn('읽기용 정리본',xml);self.assertIn('Appendix A. RAW OCR (감사용 원문)',xml);self.assertLess(xml.index('읽기용 정리본'),xml.index('Source comparison and evidence'));self.assertLess(xml.index('Source comparison and evidence'),xml.index('Appendix A. RAW OCR'));self.assertIn('Corrected/normalized text',xml);self.assertIn('normalized text',xml);self.assertEqual(xml.count('>normalized text<'),1);self.assertIn('Immutable: yes',xml)
  _,multi=call(args('report.create',state_root=str(self.s),job_ids='one,two',output_root=str(self.r),output='multi.docx'));self.assertTrue(multi['ok']);self.assertEqual(multi['data']['files'],2)
  with zipfile.ZipFile(self.r/'multi.docx') as z:
   xml=z.read('word/document.xml').decode();self.assertIn('Executive information',xml);self.assertIn('Review-needed highlights',xml);self.assertIn('File index',xml);self.assertIn('one.ppm',xml);self.assertIn('two.ppm',xml);self.assertEqual(xml.count('Appendix A. RAW OCR (감사용 원문)'),1);self.assertGreater(xml.index('Appendix A. RAW OCR'),xml.index('File 2: two.ppm'));self.assertEqual(len([x for x in z.namelist() if x.startswith('word/media/')]),2)
 def test_presentation_normalization_is_conservative_and_table_fallback_is_safe(self):
  raw='상호: 테스트 상점\r\n금액  12,300원\n애매한 한 칸\n\n\n토큰   순서 유지'
  rows=M.presentation_lines(raw);self.assertEqual(rows[0],('kv','상호:','테스트 상점'));self.assertEqual(rows[1],('kv','금액','12,300원'));self.assertEqual(rows[2],('line','애매한 한 칸',None));self.assertEqual(rows.count(('blank',None,None)),1)
  rendered=' '.join(x for row in rows for x in row[1:] if x);self.assertEqual(rendered.split(),raw.replace('\r','').split())
 def test_one_line_receipt_is_segmented_without_token_mutation(self):
  raw='Ao 택시 이용 상세 26.06.17 운행 정보 출발 OOS 양 재 역 점 도착 나 옥 길 센 트 럴 힐 아파트 운행 시간 20:42 - 21:23 호출 옵션 일반 택시 정보 상호 동 창 산 업 (주) 차량 번호 경기 37 바 1035 | 쏘나타 기 사 명 송 강 수 제휴 브랜드 캡 시 요금 정보 운행 요 금 ( 미 터 기 요금) 24,500 원 통행료 1,900 원 결제 금액 26,400 원 결제 수단 카 카 오 페이 현 대 카드 9490 결제 일시 26.06.17 21:23 @ 실제 요 금 과 다를 수 있습니다. 고객 지원 기 사 님께 전화'
  rows=M.presentation_lines(raw)
  self.assertEqual([r[1].replace(' ','') for r in rows if r[0]=='section'],['운행정보','택시정보','요금정보','고객지원'])
  labels=[r[1].replace(' ','') for r in rows if r[0]=='kv']
  for expected in ('출발','도착','운행시간','호출옵션','상호','차량번호','기사명','제휴브랜드','운행요금','통행료','결제금액','결제수단','결제일시'):self.assertIn(expected,labels)
  rendered=' '.join(x for row in rows for x in row[1:] if x)
  self.assertEqual(rendered.split(),raw.split())
  self.assertEqual(set(rendered.split())-set(raw.split()),set())
 def test_generic_long_line_uses_sentence_and_bounded_chunks(self):
  raw=('첫 문장입니다. '+'긴문장토큰 '*80+'끝입니다!').strip();rows=M.presentation_lines(raw)
  self.assertGreater(len(rows),2);self.assertTrue(all(len(r[1])<=180 for r in rows if r[0]=='line'))
  self.assertEqual(' '.join(r[1] for r in rows if r[1]).split(),raw.split())
 def test_receipt_raw_is_exactly_present_in_consolidated_appendix(self):
  raw='운행 정보 출발 A 도착 B 결제 금액 1,000 원 고객 지원 문의\n둘째 줄 그대로'
  record={'filename':'receipt.txt','qa':'PASS','confidence':.92,'language':'kor','engine':'test','sha':'a'*64,'dimensions':'n/a','pages':1,'cache':'miss','validation':'valid','raw_state':'preserved','review':False,'image':None,'raw':raw,'corrected':None}
  target=self.r/'receipt.docx';M.create_docx(target,[record],'DOC','2026-01-01T00:00:00Z','INTERNAL')
  with zipfile.ZipFile(target) as z:xml=z.read('word/document.xml').decode()
  appendix=xml[xml.index('Appendix A. RAW OCR'):]
  self.assertIn(M.xml_text(raw),appendix);self.assertEqual(xml.count('Appendix A. RAW OCR'),1)
  reading=xml[xml.index('읽기용 정리본'):xml.index('Source comparison and evidence')]
  self.assertIn('Heading3',reading);self.assertGreaterEqual(reading.count('<w:tr>'),3)
 def test_report_rejects_bad_jobs_paths_and_clobber(self):
  (self.i/'a.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.ppm',job_id='a'))
  for ids in ('','a,a','a,../x','missing'):
   _,x=call(args('report.create',state_root=str(self.s),job_ids=ids,output_root=str(self.r),output=f'x-{len(ids)}.docx'));self.assertFalse(x['ok'])
  _,x=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='../x.docx'));self.assertFalse(x['ok']);(self.r/'link').symlink_to(self.r/'real');_,x=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='link/x.docx'));self.assertFalse(x['ok']);(self.r/'exists.docx').write_bytes(b'x');_,x=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='exists.docx'));self.assertFalse(x['ok'])
 def test_report_rejects_incomplete_and_missing_result(self):
  (self.i/'a.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.ppm',job_id='a'));m=json.loads((self.s/'jobs/a/job.json').read_text());m['status']='running';M.atomic(self.s/'jobs/a/job.json',m);_,x=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='a.docx'));self.assertFalse(x['ok']);m['status']='completed';M.atomic(self.s/'jobs/a/job.json',m);(self.s/'jobs/a/result.json').unlink();_,x=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='b.docx'));self.assertFalse(x['ok'])
 def test_report_owner_and_backend_unavailable(self):
  (self.i/'a.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.ppm',job_id='a'));_,foreign=call(args('report.create',state_root=str(self.s),job_ids='a',owner='other',output_root=str(self.r),output='foreign.docx'));self.assertFalse(foreign['ok'])
  with patch.object(M,'create_docx',side_effect=OSError('OOXML backend unavailable')):
   _,failed=call(args('report.create',state_root=str(self.s),job_ids='a',output_root=str(self.r),output='failed.docx'));self.assertFalse(failed['ok']);self.assertIn('backend unavailable',failed['error']['message']);self.assertFalse((self.r/'failed.docx').exists())
 def setup_review(self,secret=None,auth_mode='env',auth_env='CLAWPOD_OLLAMA_TOKEN'):
  ep=self.server();_,x=call(args('ollama.configure',state_root=str(self.s),endpoint=ep,secret=secret,auth_mode=auth_mode,auth_env=auth_env));self.assertTrue(x['ok']);return ep
 def test_vision_image_request_and_explicit_apply(self):
  self.setup_review();_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok']);(self.i/'a.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='a.ppm',job_id='r'));raw_before=(self.s/'jobs/r/result.json').read_bytes();_,intent=call(args('review.prepare',state_root=str(self.s),job_id='r'));digest=intent['data']['intentDigest'];self.assertEqual(intent['data']['pages'][0]['imageBytes'],14);_,bad=call(args('review.start',state_root=str(self.s),job_id='r',approved=True,approval_digest='0'*64));self.assertFalse(bad['ok']);_,x=call(args('review.start',state_root=str(self.s),job_id='r',approved=True,approval_digest=digest));self.assertTrue(x['ok']);post=[b for path,b,a in H.seen if path=='/api/generate'][-1];self.assertTrue(post['images'][0]);self.assertEqual((self.s/'jobs/r/result.json').read_bytes(),raw_before);corr=json.loads((self.s/'jobs/r/corrections.json').read_text())['items'][0];_,no=call(args('correction.apply',state_root=str(self.s),job_id='r'));self.assertFalse(no['ok']);_,yes=call(args('correction.apply',state_root=str(self.s),job_id='r',correction_id=[corr['id']]));self.assertEqual(yes['data']['applied'],[corr['id']]);self.assertEqual((self.s/'jobs/r/result.json').read_bytes(),raw_before)
 def test_cache_hit_rebinds_job_and_materializes_review_image(self):
  self.setup_review();call(args('ollama.verify',state_root=str(self.s)));(self.i/'cache.ppm').write_bytes(ppm());call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='cache.ppm',job_id='first'));_,hit=call(args('ocr.start',state_root=str(self.s),input_root=str(self.i),input='cache.ppm',job_id='second'));self.assertTrue(hit['data']['cacheHit']);result=json.loads((self.s/'jobs/second/result.json').read_text());self.assertEqual(result['jobId'],'second');self.assertFalse((self.s/'jobs/second/page-images').exists());_,intent=call(args('review.prepare',state_root=str(self.s),job_id='second'));self.assertEqual(intent['data']['jobId'],'second');self.assertTrue((self.s/'jobs/second/page-images/page-1.ppm').exists());_,review=call(args('review.start',state_root=str(self.s),job_id='second',approved=True,approval_digest=intent['data']['intentDigest']));self.assertTrue(review['ok'])
 def test_auth_injection_and_permissions(self):
  self.setup_review('secret:pointer');_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);os.environ['CLAWPOD_OLLAMA_TOKEN']='tok';_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok']);self.assertTrue(all(a=='Bearer tok' for _,_,a in H.seen));self.assertNotIn('tok',(self.s/'ollama.json').read_text())
  self.s.mkdir(exist_ok=True);(self.s/'ollama.json').unlink();self.setup_review('secret:pointer','file-env','TOKEN_FILE');f=self.r/'token';f.write_text('tok');f.chmod(0o644);os.environ['TOKEN_FILE']=str(f);_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);f.chmod(0o600);_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertTrue(x['ok'])
 def test_model_vision_incompatible_and_malformed(self):
  self.setup_review();H.caps=['completion'];_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'model_vision_incompatible');H.caps=['vision'];H.malformed=True;_,x=call(args('ollama.verify',state_root=str(self.s)));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'configured_unverified')
 def test_ollama_timeout_is_bounded_and_unverified(self):
  self.setup_review();H.delay=.3;_,x=call(args('ollama.verify',state_root=str(self.s),timeout=.1));self.assertFalse(x['ok']);self.assertEqual(json.loads((self.s/'ollama.json').read_text())['state'],'configured_unverified')
if __name__=='__main__':unittest.main()
