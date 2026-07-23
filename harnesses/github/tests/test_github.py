import json, os, subprocess, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]; CLI=ROOT/'github.py'
FAKE='''#!/usr/bin/env python3
import json,os,sys,time
args=sys.argv[1:]
mode=os.getenv("FAKE_GH_MODE","")
if mode=="timeout": time.sleep(2)
if mode=="fail": print("backend failed",file=sys.stderr);sys.exit(3)
if mode=="rate":
 p=os.environ["FAKE_COUNT"]; n=int(open(p).read()) if os.path.exists(p) else 0;open(p,"w").write(str(n+1))
 if n==0:print("rate limit",file=sys.stderr);sys.exit(75)
if mode=="secret": print(json.dumps({"token":"gh"+"p_"+"ABCDEFGHIJKLMNOPQRSTUVWXYZ"}));sys.exit(0)
if args[:2]==["auth","status"]: print(json.dumps({"account":os.getenv("FAKE_ACCOUNT","octocat"),"host":"github.com"}))
elif args[:2]==["auth","login"]: time.sleep(.05)
else: print(json.dumps({"argv":args}))
'''
@pytest.fixture
def env(tmp_path):
 gh=tmp_path/'gh';gh.write_text(FAKE);gh.chmod(0o755);return {**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ.get('PATH','')}
def run(args,env):return subprocess.run([sys.executable,str(CLI)]+args,text=True,capture_output=True,env=env,cwd='/tmp')
def data(r):return json.loads(r.stdout)
@pytest.mark.parametrize('cmd,args',[('repo.view',['--repo','o/r']),('issue.list',['--repo','o/r']),('issue.get',['--repo','o/r','--number','1']),('pr.list',['--repo','o/r']),('pr.view',['--repo','o/r','--number','2']),('pr.checks',['--repo','o/r','--number','2']),('run.list',['--repo','o/r']),('run.view',['--repo','o/r','--run-id','3']),('release.list',['--repo','o/r']),('release.view',['--repo','o/r','--tag','v1']),('api.get',['--endpoint','repos/o/r'])])
def test_read_commands(env,cmd,args):
 r=run([cmd]+args,env);assert r.returncode==0 and data(r)['ok'];assert data(r)['provenance']['backend']=='gh'
def test_manifest_numeric_and_safety():
 m=json.loads((ROOT/'harness.json').read_text());assert m['title']=='GitHub'
 assert all(c['inputSchema']['properties']['limit']['type']=='number' for c in m['commands'].values())
 assert 'destructive' in m['commands']['pr.merge']['safetyClasses'];assert m['commands']['issue.create']['safetyClasses']==['externalSideEffect','humanAccountAction']
def test_contract_integer():
 c=json.loads((ROOT/'command_contracts.json').read_text());assert c['commands']['repo.view']['inputSchema']['properties']['limit']['type']=='integer'
def test_mutation_requires_preview_and_confirmation(env):
 base=['issue.create','--repo','o/r','--title','x'];r=run(base,env);assert r.returncode==2 and not data(r)['ok']
 p=run(base+['--dry-run'],env);assert p.returncode==0 and data(p)['data']['preview']['operation']=='issue.create'
 ok=run(base+['--confirm','issue.create'],env);assert ok.returncode==0 and data(ok)['effects'][0]['type']=='externalSideEffect'
def test_mutation_not_retried(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};r=run(['issue.create','--repo','o/r','--title','x','--confirm','issue.create','--retries','3'],e);assert r.returncode==2;assert (tmp_path/'n').read_text()=='1'
def test_idempotency_receipt_and_replay(env,tmp_path):
 args=['issue.create','--repo','o/r','--title','x','--confirm','issue.create','--idempotency-key','case-12345','--jobs-dir',str(tmp_path)]
 first=run(args,env);second=run(args,env);assert data(first)['data']['receipt'];assert data(second)['data']['idempotentReplay'];assert data(second)['effects']==[]
 bad=run(['issue.create','--repo','o/r','--title','different','--confirm','issue.create','--idempotency-key','case-12345','--jobs-dir',str(tmp_path)],env);assert bad.returncode==2
def test_read_rate_limit_retry(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};r=run(['repo.view','--repo','o/r','--retries','1'],e);assert r.returncode==0;assert (tmp_path/'n').read_text()=='2'
def test_timeout(env):
 r=run(['repo.view','--repo','o/r','--timeout-ms','100'],{**env,'FAKE_GH_MODE':'timeout'});assert r.returncode==2 and 'timed out' in data(r)['error']['message']
def test_backend_failure(env):
 r=run(['repo.view','--repo','o/r'],{**env,'FAKE_GH_MODE':'fail'});assert r.returncode==2 and 'backend failed' in r.stderr
def test_missing_backend():
 r=run(['repo.view','--repo','o/r'],{**os.environ,'PATH':'/nonexistent'});assert r.returncode==2
def test_validation(env):
 for args in [['repo.view'],['repo.view','--repo','bad'],['api.get','--endpoint','graphql'],['repo.view','--repo','o/r','--limit','101']]:assert run(args,env).returncode==2
def test_redaction(env):
 r=run(['repo.view','--repo','o/r'],{**env,'FAKE_GH_MODE':'secret'});assert 'ghp_' not in r.stdout+r.stderr and '[REDACTED]' in r.stdout
def test_expected_account(env):
 assert run(['auth.status','--expected-account','octocat'],env).returncode==0
 assert run(['auth.status','--expected-account','wrong'],env).returncode==2
def test_auth_async(env,tmp_path):
 root=tmp_path/'jobs';p=run(['auth.login.start','--jobs-dir',str(root),'--dry-run'],env);assert data(p)['data']['preview']['humanAccountAction']
 s=run(['auth.login.start','--jobs-dir',str(root),'--confirm','auth.login.start'],env);jid=data(s)['data']['jobId'];assert jid
 st=run(['auth.login.status','--jobs-dir',str(root),'--job-id',jid],env);assert st.returncode==0 and data(st)['data']['state'] in {'waiting-for-user','finished'}
def test_installed_style_executable(env):
 r=subprocess.run([str(CLI),'repo.view','--repo','o/r'],text=True,capture_output=True,env=env,cwd='/tmp');assert r.returncode==0 and data(r)['ok']
