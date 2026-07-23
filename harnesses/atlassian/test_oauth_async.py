import json, os, stat, subprocess, sys, tempfile, time, unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
import oauth3lo
HERE = Path(__file__).resolve().parent

SCOPES=["offline_access","read:me","read:jira-work","read:space:confluence"]
LIVE_SCOPES=["offline_access","read:me","read:jira-work","read:jira-user","write:jira-work","read:confluence-content.all","read:confluence-space.summary","search:confluence","write:confluence-content","write:confluence-file","read:space:confluence"]

class OAuthAsyncTests(unittest.TestCase):
 def root(self):
  t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); p=Path(t.name); os.chmod(p,0o700); return p
 def client(self,r,scopes=SCOPES):
  p=r/'client.json'; p.write_text(json.dumps({"oauth2":{"client_id":"fixture-client","client_secret":"fixture-secret","redirect_uri":getattr(self,'redirect_uri','http://127.0.0.1:43119/oauth/atlassian/callback'),"scopes":scopes}})); os.chmod(p,0o600); return p
 def test_confluence_granular_scope_required(self):
  r=self.root(); p=self.client(r,["offline_access","read:me","read:page:confluence"])
  with self.assertRaisesRegex(oauth3lo.OAuthFailure,"read:space:confluence"): oauth3lo._client(p)
 def test_duplicate_resources_coalesce_and_union(self):
  rows=[{"id":"one","url":"https://acme.atlassian.net","scopes":["a"]},{"id":"one","url":"https://acme.atlassian.net/","scopes":["b"]}]
  got=oauth3lo._select_resource(rows,"https://acme.atlassian.net")
  self.assertEqual(got["scopes"],["a","b"])
 def test_multiple_distinct_resources_fail_closed(self):
  rows=[{"id":"one","url":"https://acme.atlassian.net"},{"id":"two","url":"https://acme.atlassian.net/"}]
  with self.assertRaisesRegex(oauth3lo.OAuthFailure,"ambiguous"): oauth3lo._select_resource(rows,"https://acme.atlassian.net")
 def test_explicit_id_and_url_filter_multiple_resources(self):
  rows=[{"id":"one","url":"https://acme.atlassian.net","scopes":["a"]},{"id":"one","url":"https://acme.atlassian.net/","scopes":["b"]},{"id":"two","url":"https://other.atlassian.net","scopes":["c"]}]
  self.assertEqual(oauth3lo._select_resource(rows,"https://unused.atlassian.net","one")["scopes"],["a","b"])
  self.assertEqual(oauth3lo._select_resource(rows,"https://acme.atlassian.net")["id"],"one")
 def test_wrong_single_resource_fails_when_explicit_id(self):
  with self.assertRaises(oauth3lo.OAuthFailure): oauth3lo._select_resource([{"id":"one","url":"https://x.atlassian.net"}],"https://x.atlassian.net","two")
  with self.assertRaises(oauth3lo.OAuthFailure): oauth3lo._select_resource([{"id":"one","url":"https://wrong.atlassian.net"}],"https://approved.atlassian.net")
 def test_receiver_rejects_callback_state(self):
  class FakeServer:
   timeout=0
   def __init__(self,addr,handler): self.handler=handler
   def handle_request(self): time.sleep(.001)
   def server_close(self): pass
  result,done=oauth3lo._receiver(43119,"wanted",.01,FakeServer); done.wait(.1)
  self.assertNotIn("code",result)
 def test_job_status_is_allowlisted_and_mode_0600(self):
  r=self.root(); jid="a"*32; p=r/'.oauth-jobs'/f'{jid}.json'; p.parent.mkdir(mode=0o700)
  oauth3lo._atomic_json(p,{"schemaVersion":1,"jobId":jid,"status":"pending-consent","updatedAt":1,"access_token":"never"},overwrite=False)
  got=oauth3lo.job_status(transfer_root=r,job_id=jid)
  self.assertNotIn("access_token",got); self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
 def test_stale_job_fails_boundedly(self):
  r=self.root(); jid='e'*32; p=r/'.oauth-jobs'/f'{jid}.json'; p.parent.mkdir(mode=0o700)
  oauth3lo._atomic_json(p,{"schemaVersion":1,"jobId":jid,"status":"pending-login","updatedAt":1,"deadline":1},overwrite=False)
  got=oauth3lo.job_status(transfer_root=r,job_id=jid); self.assertEqual(got['status'],'failed'); self.assertEqual(got['errorCode'],'oauth_job_stale')
 def test_start_returns_nonsecret_job_and_detaches(self):
  r=self.root(); self.client(r)
  with mock.patch('oauth3lo.subprocess.Popen') as pop:
   got=oauth3lo.start(transfer_root=str(r),client_path='client.json',output_path='token.json',sites_output_path='sites.json',site_alias='acme',resource_url='https://acme.atlassian.net',managed_browser_devtools_url='http://127.0.0.1:9222',timeout=30,overwrite=False,smoke_tests=('jira','confluence'))
  self.assertRegex(got['jobId'],r'^[a-f0-9]{32}$'); argv=pop.call_args.args[0]
  self.assertNotIn('fixture-secret',' '.join(argv)); self.assertTrue(pop.call_args.kwargs['start_new_session'])
  status=json.loads((r/got['statusPath']).read_text()); self.assertEqual(status['status'],'pending-login'); self.assertNotIn('fixture-secret',json.dumps(status))
  with self.assertRaisesRegex(oauth3lo.OAuthFailure,'already owns'):
   oauth3lo.start(transfer_root=str(r),client_path='client.json',output_path='token.json',sites_output_path='sites.json',site_alias='acme',resource_url='https://acme.atlassian.net',managed_browser_devtools_url='http://127.0.0.1:9222',timeout=30,overwrite=False,smoke_tests=('jira','confluence'))
 def test_worker_transitions_cleanup_and_redaction(self):
  r=self.root(); jid='b'*32; d=r/'.oauth-jobs'; d.mkdir(mode=0o700); job=d/f'{jid}.json'; cfg=d/f'{jid}.config.json'
  oauth3lo._atomic_json(job,{"status":"pending-login","deadline":int(time.time())+60},overwrite=False); oauth3lo._atomic_json(cfg,{"transfer_root":str(r)},overwrite=False)
  def fake_login(**kw): kw['status_cb']('pending-consent'); return {'siteAlias':'acme','smokeTests':{'jira':{'ok':True},'confluence':{'ok':True}}}
  with mock.patch('oauth3lo.login',fake_login): oauth3lo.worker(str(r),jid)
  got=json.loads(job.read_text()); self.assertEqual(got['status'],'completed'); self.assertFalse(cfg.exists()); self.assertNotIn('token',json.dumps(got).lower())
 def test_worker_failure_is_safe_and_cleans_diagnostics(self):
  r=self.root(); jid='c'*32; d=r/'.oauth-jobs'; d.mkdir(mode=0o700); job=d/f'{jid}.json'; cfg=d/f'{jid}.config.json'; diag=r/'.oauth-resource-candidates.json'
  oauth3lo._atomic_json(job,{"status":"pending-login"},overwrite=False); oauth3lo._atomic_json(cfg,{"transfer_root":str(r)},overwrite=False); oauth3lo._atomic_json(diag,{"x":1},overwrite=False)
  with mock.patch('oauth3lo.login',side_effect=oauth3lo.OAuthFailure('oauth_site_mismatch','approved site mismatch')): oauth3lo.worker(str(r),jid)
  got=json.loads(job.read_text()); self.assertEqual(got['status'],'failed'); self.assertFalse(cfg.exists()); self.assertFalse(diag.exists())
 def test_deadline_blocks_smoke_and_storage(self):
  r=self.root(); self.client(r); calls=[]
  class Response:
   def __init__(self,value): self.value=value
   def __enter__(self): return self
   def __exit__(self,*_): pass
   def read(self): return json.dumps(self.value).encode()
  def opener(req,timeout=30):
   calls.append(req.full_url)
   if req.full_url==oauth3lo.TOKEN_URL:return Response({"access_token":"a","refresh_token":"r","scope":" ".join(SCOPES)})
   if req.full_url==oauth3lo.RESOURCES_URL:return Response([{"id":"one","url":"https://acme.atlassian.net","scopes":SCOPES}])
   if req.full_url==oauth3lo.ME_URL:return Response({"account_id":"account"})
   return Response({})
  done=threading.Event(); done.set()
  with mock.patch('oauth3lo._receiver',return_value=({'code':'code'},done)):
   with self.assertRaisesRegex(oauth3lo.OAuthFailure,'bounded lifetime'):
    oauth3lo.login(transfer_root=str(r),client_path='client.json',output_path='token.json',sites_output_path='sites.json',site_alias='acme',resource_url='https://acme.atlassian.net',managed_browser_devtools_url='http://127.0.0.1:9222',timeout=10,opener=opener,consent_driver=lambda **_:None,deadline_check=lambda:(_ for _ in ()).throw(oauth3lo.OAuthFailure('oauth_job_stale','OAuth job exceeded its bounded lifetime')))
  self.assertFalse((r/'token.json').exists()); self.assertFalse((r/'sites.json').exists()); self.assertFalse(any('/smoke/' in x or '/project/search' in x for x in calls))
 def test_failed_stale_job_cannot_be_overwritten_completed(self):
  r=self.root(); jid='f'*32; d=r/'.oauth-jobs'; d.mkdir(mode=0o700); job=d/f'{jid}.json'; cfg=d/f'{jid}.config.json'
  oauth3lo._atomic_json(job,{"schemaVersion":1,"jobId":jid,"status":"pending-consent","deadline":int(time.time())+60},overwrite=False); oauth3lo._atomic_json(cfg,{"transfer_root":str(r)},overwrite=False)
  def fake_login(**kw):
   oauth3lo._job_write(job,'failed',errorCode='oauth_job_stale',message='OAuth job exceeded its bounded lifetime'); kw['status_cb']('pending-consent'); return {"siteAlias":"acme"}
  with mock.patch('oauth3lo.login',fake_login): oauth3lo.worker(str(r),jid)
  self.assertEqual(json.loads(job.read_text())['status'],'failed')
 def test_status_end_to_end_subprocess(self):
  r=self.root(); jid='d'*32; d=r/'.oauth-jobs'; d.mkdir(mode=0o700)
  oauth3lo._atomic_json(d/f'{jid}.json',{"schemaVersion":1,"jobId":jid,"status":"pending-login","updatedAt":1,"deadline":int(time.time())+60},overwrite=False)
  cp=subprocess.run([sys.executable,str(HERE/'atlassian.py'),'auth.oauth.job.status','--transfer-root',str(r),'--job-id',jid],text=True,capture_output=True,check=True)
  doc=json.loads(cp.stdout); self.assertTrue(doc['ok']); self.assertEqual(doc['data']['status'],'pending-login'); self.assertEqual(cp.stderr,'')
 def node(self,scopes,text,**site_state):
  auth='https://auth.atlassian.com/authorize?state=s&redirect_uri='+__import__('urllib.parse').parse.quote('http://127.0.0.1:9/oauth/atlassian/callback',safe='')
  post=site_state.pop('postSelection',None); snapshot={"text":text,"acceptButtons":["Accept"],**site_state}; snapshot.setdefault('siteOrigins',['acme.atlassian.net'])
  snapshots=[snapshot]+([post] if post else [])
  payload={"endpoint":"http://127.0.0.1:1","authorize_url":auth,"resource_url":"https://acme.atlassian.net","scopes":scopes,"redirect_uri":"http://127.0.0.1:9/oauth/atlassian/callback","state":"s","timeout":5,"skipCallback":True,"testSnapshots":snapshots}
  env=dict(os.environ,OAUTH_CDP_TEST_MODE='1'); return json.loads(subprocess.run(['node',str(HERE/'oauth_cdp.js')],input=json.dumps(payload),text=True,capture_output=True,env=env,check=True).stdout)
 def test_node_abbreviated_classic_and_granular_scope_tokens(self):
  for scope,text in [('read:confluence-space.summary','acme.atlassian.net confluence-space.summary'),('read:space:confluence','acme.atlassian.net view spaces')]:
   got=self.node([scope],text); self.assertTrue(got['ok']); self.assertTrue(got['accepted'])
 def test_node_missing_scope_wrong_site_and_unmapped_fail_closed(self):
  self.assertEqual(self.node(['read:space:confluence'],'acme.atlassian.net profile')['code'],'oauth_scope_missing')
  self.assertEqual(self.node(['read:space:confluence'],'other.atlassian.net spaces',siteOrigins=['other.atlassian.net'])['code'],'oauth_site_mismatch')
  self.assertEqual(self.node(['unknown:scope'],'acme.atlassian.net unknown')['code'],'oauth_scope_unmapped')
  self.assertEqual(self.node(['read:me'],'acme.atlassian.net something')['code'],'oauth_scope_missing')
 def test_live_scope_fixture_and_all_site_states_through_node(self):
  captured='acme.atlassian.net me jira-user jira-work confluence-content.all confluence-space.summary confluence confluence-content confluence-file spaces'
  self.assertTrue(self.node(LIVE_SCOPES,captured,siteOrigins=['acme.atlassian.net'])['ok'])
  post={"text":captured,"siteOrigins":['acme.atlassian.net']}
  self.assertTrue(self.node(LIVE_SCOPES,captured,siteOrigins=[],nativeOptions=['acme.atlassian.net'],postSelection=post)['ok'])
  self.assertTrue(self.node(LIVE_SCOPES,captured,siteOrigins=[],comboboxOptions=['acme.atlassian.net'],postSelection=post)['ok'])
  self.assertEqual(self.node(LIVE_SCOPES,captured,siteOrigins=['other.atlassian.net'])['code'],'oauth_site_mismatch')
  self.assertEqual(self.node(LIVE_SCOPES,captured,siteOrigins=['other.atlassian.net'],nativeOptions=['acme.atlassian.net'],comboboxOptions=['acme.atlassian.net'])['code'],'oauth_site_ambiguous')
  self.assertEqual(self.node(LIVE_SCOPES,captured,siteOrigins=[],nativeOptions=['acme.atlassian.net'])['code'],'oauth_site_unsettled')
  self.assertEqual(self.node(LIVE_SCOPES,captured,siteOrigins=[],nativeOptions=['acme.atlassian.net'],postSelection={"text":captured,"siteOrigins":[]})['code'],'oauth_site_unsettled')
 def test_start_worker_completion_end_to_end_with_loopback_fakes(self):
  r=self.root(); seen=[]
  class Provider(BaseHTTPRequestHandler):
   def log_message(self,*_): pass
   def reply(self,value):
    b=json.dumps(value).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
   def do_POST(self): seen.append(self.path); self.rfile.read(int(self.headers.get('Content-Length','0'))); self.reply({"access_token":"fixture-access","refresh_token":"fixture-refresh","scope":" ".join(SCOPES),"expires_in":3600})
   def do_GET(self):
    seen.append(self.path)
    if self.path=='/accessible-resources': self.reply([{"id":"cloud-one","url":"https://acme.atlassian.net","scopes":["read:jira-work"]},{"id":"cloud-one","url":"https://acme.atlassian.net/","scopes":["read:space:confluence"]},{"id":"cloud-two","url":"https://other.atlassian.net","scopes":[]}])
    elif self.path=='/me': self.reply({"account_id":"fixture-account"})
    else: self.reply({"values":[]})
  provider=ThreadingHTTPServer(('127.0.0.1',0),Provider); threading.Thread(target=provider.serve_forever,daemon=True).start(); self.addCleanup(provider.server_close); self.addCleanup(provider.shutdown)
  callback=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler); port=callback.server_address[1]; callback.server_close(); self.redirect_uri=f'http://127.0.0.1:{port}/oauth/atlassian/callback'; self.client(r)
  cfg=r/'fake.json'; cfg.write_text(json.dumps({"providerBase":f'http://127.0.0.1:{provider.server_address[1]}',"snapshots":[{"login":True},{"text":"acme.atlassian.net me jira-work view spaces","siteOrigins":["acme.atlassian.net"],"acceptButtons":["Accept"]}]})); os.chmod(cfg,0o600)
  env=dict(os.environ,ATLASSIAN_INTERNAL_TEST_MODE='1',ATLASSIAN_OAUTH_TEST_CONFIG='fake.json'); cmd=[sys.executable,str(HERE/'atlassian.py'),'auth.oauth.start','--transfer-root',str(r),'--client-path','client.json','--output-path','token.json','--sites-output-path','sites.json','--site-alias','acme','--resource-url','https://acme.atlassian.net','--managed-browser-devtools-url','http://127.0.0.1:9222','--worker-timeout','20']
  started=subprocess.run(cmd,text=True,capture_output=True,env=env,check=True); doc=json.loads(started.stdout); self.assertEqual(doc['data']['status'],'pending-login'); self.assertNotIn('fixture-secret',started.stdout+started.stderr)
  jid=doc['data']['jobId']; final=None
  for _ in range(100):
   status=subprocess.run([sys.executable,str(HERE/'atlassian.py'),'auth.oauth.job.status','--transfer-root',str(r),'--job-id',jid],text=True,capture_output=True,check=True); final=json.loads(status.stdout)['data']
   if final['status'] in ('completed','failed'): break
   time.sleep(.05)
  self.assertEqual(final['status'],'completed',final); self.assertEqual(stat.S_IMODE((r/'token.json').stat().st_mode),0o600); self.assertFalse((r/f'.oauth-jobs/{jid}.config.json').exists())
  corpus=started.stdout+started.stderr+json.dumps(final)+(r/f'.oauth-jobs/{jid}.json').read_text(); self.assertNotIn('fixture-secret',corpus); self.assertNotIn('fixture-access',corpus); self.assertNotIn('state=',corpus)
  self.assertIn('/smoke/jira',seen); self.assertIn('/smoke/confluence',seen)

if __name__=='__main__': unittest.main()
