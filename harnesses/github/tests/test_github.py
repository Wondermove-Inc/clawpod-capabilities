import json,os,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];CLI=ROOT/'github.py'
FAKE='''#!/usr/bin/env python3
import json,os,sys,time
args=sys.argv[1:];mode=os.getenv("FAKE_GH_MODE","")
open(os.environ["ARGV_LOG"],"a").write(json.dumps(args)+"\\n")
if mode=="timeout":time.sleep(2)
if mode=="fail":print("backend failed",file=sys.stderr);sys.exit(3)
if mode=="rate":
 p=os.environ["FAKE_COUNT"];n=int(open(p).read()) if os.path.exists(p) else 0;open(p,"w").write(str(n+1))
 if n==0:print("rate limit",file=sys.stderr);sys.exit(75)
if mode=="secret":print(json.dumps({"token":"gh"+"p_"+"ABCDEFGHIJKLMNOPQRSTUVWXYZ"}));sys.exit(0)
if args[:2]==["api","--hostname"] and "user" in args:print(json.dumps({"login":os.getenv("FAKE_ACCOUNT","octocat"),"token":"must-not-pass-through"}))
else:print(json.dumps({"argv":args}))
'''
@pytest.fixture
def env(tmp_path):
 gh=tmp_path/'gh';gh.write_text(FAKE);gh.chmod(0o755);return {**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ.get('PATH',''),'ARGV_LOG':str(tmp_path/'argv')}
def run(args,env):return subprocess.run([sys.executable,str(CLI)]+args,text=True,capture_output=True,env=env,cwd='/tmp')
def data(r):return json.loads(r.stdout)
@pytest.mark.parametrize('cmd,args',[('repo.view',['--repo','o/r']),('issue.list',['--repo','o/r']),('issue.get',['--repo','o/r','--number','1']),('pr.list',['--repo','o/r']),('pr.view',['--repo','o/r','--number','2']),('pr.checks',['--repo','o/r','--number','2']),('run.list',['--repo','o/r']),('run.view',['--repo','o/r','--run-id','3']),('release.list',['--repo','o/r']),('release.view',['--repo','o/r','--tag','v1']),('api.get',['--endpoint','repos/o/r'])])
def test_read_commands(env,cmd,args):assert data(run([cmd]+args,env))['ok']
def test_auth_status_is_bounded_allowlisted_and_exact(env):
 r=run(['auth.status','--host','github.com','--expected-account','octocat'],env);d=data(r)
 assert r.returncode==0 and d['data']=={'host':'github.com','login':'octocat','authenticated':True}
 argv=json.loads(Path(env['ARGV_LOG']).read_text().splitlines()[-1]);assert argv==['api','--hostname','github.com','--method','GET','user','--jq','{login:.login}']
 assert 'auth status' not in ' '.join(argv) and 'hosts' not in argv and 'token' not in r.stdout.lower()
 assert run(['auth.status','--expected-account','Octocat'],env).returncode==2
@pytest.mark.parametrize('cmd',['auth.login.start','auth.login.status','auth.login.cancel'])
def test_fake_login_commands_removed(env,cmd):assert run([cmd],env).returncode==2
def test_manifest_safety_and_no_login():
 m=json.loads((ROOT/'harness.json').read_text());assert m['title']=='GitHub';assert not any(x.startswith('auth.login') for x in m['commands'])
 assert m['commands']['auth.status']['safetyClasses']==['secretUse','readOnly']
 assert 'destructive' in m['commands']['release.upload']['safetyClasses'];assert m['commands']['issue.create']['safetyClasses']==['externalSideEffect','humanAccountAction']
def test_mutation_preview_confirmation_and_ambiguity(env):
 base=['issue.create','--repo','o/r','--title','x'];pre=data(run(base,env));assert pre['error']['ambiguousCommit'] is False
 p=data(run(base+['--dry-run'],env));assert p['data']['preview']['idempotency'].startswith('best-effort')
 bad=data(run(base+['--confirm','issue.create'],{**env,'FAKE_GH_MODE':'fail'}));assert bad['error']['retryable'] is False and bad['error']['ambiguousCommit'] is True
def test_release_preview_discloses_clobber(env,tmp_path):
 f=tmp_path/'x';f.write_text('x');d=data(run(['release.upload','--repo','o/r','--tag','v1','--file',str(f),'--dry-run'],env));assert d['data']['preview']['clobbersExistingAsset'] is True
def test_mutation_not_retried(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};r=run(['issue.create','--repo','o/r','--title','x','--confirm','issue.create','--retries','3'],e);assert r.returncode==2 and (tmp_path/'n').read_text()=='1'
def test_read_retry_timeout_redaction(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};assert run(['repo.view','--repo','o/r'],e).returncode==0
 assert run(['repo.view','--repo','o/r','--timeout-ms','100'],{**env,'FAKE_GH_MODE':'timeout'}).returncode==2
 r=run(['repo.view','--repo','o/r'],{**env,'FAKE_GH_MODE':'secret'});assert 'ghp_' not in r.stdout+r.stderr
@pytest.mark.parametrize('args',[['repo.view'],['repo.view','--repo','bad'],['api.get','--endpoint','graphql'],['repo.view','--repo','o/r','--limit','101'],['auth.status','--host','https://github.com'],['issue.get','--repo','o/r','--number','0'],['issue.list','--repo','o/r','--state','bad'],['issue.list','--repo','o/r','--state','merged']])
def test_validation(env,args):assert run(args,env).returncode==2
