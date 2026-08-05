import json,os,shutil,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];CLI=ROOT/'github.py'
FAKE='''#!/usr/bin/env python3
import copy,json,os,sys,time
args=sys.argv[1:];mode=os.getenv("FAKE_GH_MODE","")
open(os.environ["ARGV_LOG"],"a").write(json.dumps(args)+"\\n")
if mode=="timeout":time.sleep(2)
if mode=="fail":print("backend failed",file=sys.stderr);sys.exit(3)
if mode=="require-home" and not os.getenv("HOME"):print("HOME missing",file=sys.stderr);sys.exit(3)
if mode=="rate":
 p=os.environ["FAKE_COUNT"];n=int(open(p).read()) if os.path.exists(p) else 0;open(p,"w").write(str(n+1))
 if n==0:print("rate limit",file=sys.stderr);sys.exit(75)
if mode=="secret":print(json.dumps({"token":"gh"+"p_"+"ABCDEFGHIJKLMNOPQRSTUVWXYZ"}));sys.exit(0)
if args[:2]==["api","--hostname"] and "user" in args:
 print(json.dumps({"login":os.getenv("FAKE_ACCOUNT","octocat"),"token":"must-not-pass-through"}));sys.exit(0)
if args[:2]==["repo","create"]:
 if mode=="repo-create-rate":print("rate limit",file=sys.stderr);sys.exit(75)
 print(json.dumps({"created":True}));sys.exit(0)
if args[:2]==["repo","view"] and "--json" in args:
 target=args[2];branch=os.getenv("FAKE_SOURCE_BRANCH","main");visibility=os.getenv("FAKE_VISIBILITY","PRIVATE")
 if mode=="repo-target-mismatch":target="other/repo"
 if mode=="repo-branch-mismatch":branch="other"
 print(json.dumps({"nameWithOwner":target,"visibility":visibility,"defaultBranchRef":{"name":branch},"url":"https://github.com/"+target}));sys.exit(0)
if "/git/matching-refs/heads/" in " ".join(args):
 sha=os.getenv("FAKE_REMOTE_BEFORE","");branch=args[-1].split("/heads/",1)[1]
 print(json.dumps([] if not sha else [{"ref":"refs/heads/"+branch,"object":{"sha":sha}}]));sys.exit(0)
if "/git/ref/heads/" in " ".join(args):
 sha=os.getenv("FAKE_SOURCE_HEAD","")
 if mode in {"repo-sha-mismatch","push-sha-mismatch"}:sha="0"*40
 print(json.dumps({"sha":sha,"object":{"sha":sha}}));sys.exit(0)
endpoint=next((x for x in args if x.startswith("repos/") and "/releases/" in x),"")
method=args[args.index("--method")+1] if "--method" in args else ""
state_path=os.getenv("FAKE_RELEASE_STATE")
if state_path and endpoint and method=="GET":
 release=json.load(open(state_path))
 if mode=="wrong-tag":release["tag_name"]="other"
 print(json.dumps(release));sys.exit(0)
if state_path and endpoint and method=="PATCH":
 count_path=os.environ["FAKE_PATCH_COUNT"];count=int(open(count_path).read()) if os.path.exists(count_path) else 0;open(count_path,"w").write(str(count+1))
 if mode=="release-patch-rate":print("rate limit",file=sys.stderr);sys.exit(75)
 payload=json.load(sys.stdin);open(os.environ["STDIN_LOG"],"a").write(json.dumps(payload)+"\\n")
 release=json.load(open(state_path));response=copy.deepcopy(release);response["body"]=payload.get("body");response["updated_at"]="2026-08-01T00:00:00Z"
 stored=copy.deepcopy(response)
 if mode=="body-mismatch":stored["body"]="unexpected body"
 if mode=="metadata-mismatch":stored["name"]="Changed elsewhere"
 if mode=="asset-mismatch":stored["assets"][0]["download_count"]+=1
 open(state_path,"w").write(json.dumps(stored));print(json.dumps(response));sys.exit(0)
print(json.dumps({"argv":args}))
'''
FAKE_GIT='''#!/usr/bin/env python3
import json,os,subprocess,sys
args=sys.argv[1:]
if "push" in args:
 open(os.environ["GIT_ARGV_LOG"],"a").write(json.dumps(args)+"\\n")
 if os.getenv("FAKE_GIT_PUSH_FAIL"):
  print("push rejected",file=sys.stderr);sys.exit(1)
 sys.exit(0)
os.execv("/usr/bin/git",["git"]+args)
'''
@pytest.fixture
def env(tmp_path):
 gh=tmp_path/'gh';gh.write_text(FAKE);gh.chmod(0o755)
 git=tmp_path/'git';git.write_text(FAKE_GIT);git.chmod(0o755)
 state=tmp_path/'release.json';shutil.copyfile(ROOT/'tests/fixtures/release.json',state)
 return {**os.environ,'PATH':str(tmp_path)+os.pathsep+os.environ.get('PATH',''),'ARGV_LOG':str(tmp_path/'argv'),'GIT_ARGV_LOG':str(tmp_path/'git-argv'),'STDIN_LOG':str(tmp_path/'stdin'),'FAKE_RELEASE_STATE':str(state),'FAKE_PATCH_COUNT':str(tmp_path/'patch-count')}
def run(args,env):return subprocess.run([sys.executable,str(CLI)]+args,text=True,capture_output=True,env=env,cwd='/tmp')
def data(r):return json.loads(r.stdout)
def argv_log(env):return [json.loads(x) for x in Path(env['ARGV_LOG']).read_text().splitlines()]
def git_argv_log(env):return [json.loads(x) for x in Path(env['GIT_ARGV_LOG']).read_text().splitlines()]
def make_repo(tmp_path,branch='main'):
 source=tmp_path/'source';source.mkdir()
 subprocess.run(['git','init','-b',branch,str(source)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(source),'config','user.email','test@example.invalid'],check=True)
 subprocess.run(['git','-C',str(source),'config','user.name','Test'],check=True)
 (source/'README.md').write_text('hello\n')
 subprocess.run(['git','-C',str(source),'add','README.md'],check=True)
 subprocess.run(['git','-C',str(source),'commit','-m','initial'],check=True,capture_output=True)
 head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
 return source,branch,head
@pytest.mark.parametrize('cmd,args',[('repo.view',['--repo','o/r']),('issue.list',['--repo','o/r']),('issue.get',['--repo','o/r','--number','1']),('pr.list',['--repo','o/r']),('pr.view',['--repo','o/r','--number','2']),('pr.checks',['--repo','o/r','--number','2']),('run.list',['--repo','o/r']),('run.view',['--repo','o/r','--run-id','3']),('release.list',['--repo','o/r']),('release.view',['--repo','o/r','--tag','v1']),('api.get',['--endpoint','repos/o/r'])])
def test_read_commands(env,cmd,args):assert data(run([cmd]+args,env))['ok']
def test_auth_status_is_bounded_allowlisted_and_exact(env):
 r=run(['auth.status','--host','github.com','--expected-account','octocat'],env);d=data(r)
 assert r.returncode==0 and d['data']=={'host':'github.com','login':'octocat','authenticated':True}
 argv=argv_log(env)[-1];assert argv==['api','--hostname','github.com','--method','GET','user','--jq','{login:.login}']
 assert 'auth status' not in ' '.join(argv) and 'hosts' not in argv and 'token' not in r.stdout.lower()
 assert run(['auth.status','--expected-account','Octocat'],env).returncode==2
def test_gateway_style_environment_recovers_system_home(env):
 e={**env,'FAKE_GH_MODE':'require-home'};e.pop('HOME',None)
 r=run(['auth.status','--host','github.com'],e)
 assert r.returncode==0 and data(r)['data']['authenticated'] is True
@pytest.mark.parametrize('cmd',['auth.login.start','auth.login.status','auth.login.cancel'])
def test_fake_login_commands_removed(env,cmd):assert run([cmd],env).returncode==2
def test_manifest_safety_and_no_login():
 m=json.loads((ROOT/'harness.json').read_text());assert m['title']=='GitHub';assert not any(x.startswith('auth.login') for x in m['commands'])
 assert m['commands']['auth.status']['safetyClasses']==['secretUse','readOnly']
 assert 'destructive' in m['commands']['release.upload']['safetyClasses'];assert m['commands']['issue.create']['safetyClasses']==['externalSideEffect','humanAccountAction']
 assert m['commands']['release.body.update']['safetyClasses']==['externalSideEffect','humanAccountAction']
def test_mutation_preview_confirmation_and_ambiguity(env):
 base=['issue.create','--repo','o/r','--title','x'];pre=data(run(base,env));assert pre['error']['ambiguousCommit'] is False
 p=data(run(base+['--dry-run'],env));assert p['data']['preview']['idempotency'].startswith('best-effort')
 bad=data(run(base+['--confirm','issue.create'],{**env,'FAKE_GH_MODE':'fail'}));assert bad['error']['retryable'] is False and bad['error']['ambiguousCommit'] is True
def test_repo_push_preview_new_branch_is_exact_and_has_no_push(env,tmp_path):
 source,branch,head=make_repo(tmp_path)
 args=['repo.push','--host','github.com','--expected-account','octocat','--repo','o/r','--source',str(source),'--source-branch',branch,'--remote-branch','feature/x','--dry-run']
 r=run(args,env);p=data(r)['data']['preview']
 assert r.returncode==0 and p['target']=={'host':'github.com','repo':'o/r','expectedAccount':'octocat'}
 assert p['source']=={'branch':branch,'head':head,'clean':True}
 assert p['remote']=={'branch':'feature/x','currentSha':None,'expectedRemoteSha':None}
 assert p['refspec']=='HEAD:refs/heads/feature/x' and p['force'] is False and str(source) not in r.stdout
 assert not Path(env['GIT_ARGV_LOG']).exists()

def test_repo_push_existing_branch_requires_matching_expected_sha(env,tmp_path):
 source,branch,head=make_repo(tmp_path);base=['repo.push','--host','github.com','--expected-account','octocat','--repo','o/r','--source',str(source),'--source-branch',branch,'--remote-branch','main','--dry-run']
 e={**env,'FAKE_REMOTE_BEFORE':'1'*40}
 assert 'expected-remote-sha is required' in data(run(base,e))['error']['message']
 assert 'does not exactly match' in data(run(base+['--expected-remote-sha','2'*40],e))['error']['message']
 assert run(base+['--expected-remote-sha','1'*40],e).returncode==0

def test_repo_push_success_uses_exact_non_force_refspec_and_readback(env,tmp_path):
 source,branch,head=make_repo(tmp_path);e={**env,'FAKE_SOURCE_HEAD':head}
 args=['repo.push','--host','github.com','--expected-account','octocat','--repo','o/r','--source',str(source),'--source-branch',branch,'--remote-branch','feature/x','--confirm','repo.push']
 r=run(args,e);d=data(r);push=git_argv_log(e)[0]
 assert r.returncode==0 and d['data']['verified'] and d['data']['remoteCommitSha']==head
 assert push==['-C',str(source),'push','https://x-access-token@github.com/o/r.git','HEAD:refs/heads/feature/x']
 assert '--force' not in push and '+' not in push[-1]
 calls=argv_log(e);assert calls[-2][-1]=='repos/o/r/git/ref/heads/feature%2Fx' and calls[-1][:3]==['repo','view','o/r']
 assert d['effects']==[{'type':'externalSideEffect','operation':'repo.push','target':'o/r'}]

def test_repo_push_validation_failure_and_no_retry_after_start(env,tmp_path):
 source,branch,head=make_repo(tmp_path);base=['repo.push','--host','github.com','--expected-account','octocat','--repo','o/r','--source',str(source),'--source-branch',branch,'--remote-branch','feature/x']
 assert run(base+['--source-branch','other','--dry-run'],env).returncode==2
 r=run(base+['--confirm','repo.push','--retries','3'],{**env,'FAKE_GIT_PUSH_FAIL':'1'});d=data(r)
 assert r.returncode==2 and d['error']['ambiguousCommit'] is True and d['error']['retryable'] is False and len(git_argv_log(env))==1

def test_repo_push_readback_mismatch_is_ambiguous(env,tmp_path):
 source,branch,head=make_repo(tmp_path);e={**env,'FAKE_SOURCE_HEAD':head,'FAKE_GH_MODE':'push-sha-mismatch'}
 r=run(['repo.push','--host','github.com','--expected-account','octocat','--repo','o/r','--source',str(source),'--source-branch',branch,'--remote-branch','x','--confirm','repo.push'],e)
 assert r.returncode==2 and 'remote commit mismatch' in data(r)['error']['message'] and data(r)['error']['ambiguousCommit'] is True

def test_repo_create_preview_is_bounded_and_omits_source_path(env,tmp_path):
 source,branch,head=make_repo(tmp_path)
 r=run(['repo.create','--repo','Wondermove-Inc/clawpod-tech-blog','--source',str(source),'--visibility','private','--description','Tech blog','--homepage','https://example.com/blog','--dry-run'],env);d=data(r);p=d['data']['preview']
 assert r.returncode==0 and p['target']=='Wondermove-Inc/clawpod-tech-blog' and p['visibility']=='private'
 assert p['source']=={'branch':branch,'head':head,'clean':True} and str(source) not in r.stdout
 assert not Path(env['ARGV_LOG']).exists()

def test_repo_create_success_uses_exact_guarded_argv_and_verified_readback(env,tmp_path):
 source,branch,head=make_repo(tmp_path);e={**env,'FAKE_SOURCE_BRANCH':branch,'FAKE_SOURCE_HEAD':head}
 args=['repo.create','--repo','Wondermove-Inc/clawpod-tech-blog','--source',str(source),'--visibility','private','--description','Tech blog','--homepage','https://example.com','--confirm','repo.create']
 r=run(args,e);d=data(r);calls=argv_log(e)
 assert r.returncode==0 and d['data']['verified'] and d['data']['remoteCommitSha']==head
 assert calls[0]==['repo','create','Wondermove-Inc/clawpod-tech-blog','--private','--description','Tech blog','--source',str(source),'--remote','origin','--push','--homepage','https://example.com']
 assert calls[1][:3]==['repo','view','Wondermove-Inc/clawpod-tech-blog'] and calls[2][-2:]==['--jq','{sha:.object.sha}']
 assert all('token' not in ' '.join(call).lower() for call in calls)

def test_repo_create_validation_paths_and_git_state(env,tmp_path):
 source,_,_=make_repo(tmp_path)
 base=['repo.create','--repo','o/r','--visibility','private','--description','x','--dry-run']
 assert run(base+['--source','relative'],env).returncode==2
 link=tmp_path/'link';link.symlink_to(source,target_is_directory=True);assert run(base+['--source',str(link)],env).returncode==2
 (source/'dirty').write_text('x');assert run(base+['--source',str(source)],env).returncode==2;(source/'dirty').unlink()
 subprocess.run(['git','-C',str(source),'checkout','--detach'],check=True,capture_output=True);assert run(base+['--source',str(source)],env).returncode==2

def test_repo_create_rejects_invalid_visibility_homepage_and_description(env,tmp_path):
 source,_,_=make_repo(tmp_path);base=['repo.create','--repo','o/r','--source',str(source),'--description','x','--dry-run']
 assert run(base+['--visibility','Private'],env).returncode==2
 assert run(base+['--visibility','private','--homepage','http://example.com'],env).returncode==2
 assert run(['repo.create','--repo','o/r','--source',str(source),'--visibility','private','--description','x'*351,'--dry-run'],env).returncode==2

def test_repo_create_backend_failure_is_ambiguous_and_never_retried(env,tmp_path):
 source,branch,head=make_repo(tmp_path);e={**env,'FAKE_GH_MODE':'repo-create-rate','FAKE_SOURCE_BRANCH':branch,'FAKE_SOURCE_HEAD':head}
 r=run(['repo.create','--repo','o/r','--source',str(source),'--visibility','private','--description','x','--confirm','repo.create','--retries','3'],e);d=data(r)
 assert r.returncode==2 and d['error']['ambiguousCommit'] is True and d['error']['retryable'] is False and len(argv_log(e))==1

@pytest.mark.parametrize('mode,fragment',[('repo-target-mismatch','target mismatch'),('repo-branch-mismatch','default branch mismatch'),('repo-sha-mismatch','remote commit mismatch')])
def test_repo_create_readback_mismatch_fails_closed(env,tmp_path,mode,fragment):
 source,branch,head=make_repo(tmp_path);e={**env,'FAKE_GH_MODE':mode,'FAKE_SOURCE_BRANCH':branch,'FAKE_SOURCE_HEAD':head}
 r=run(['repo.create','--repo','o/r','--source',str(source),'--visibility','private','--description','x','--confirm','repo.create'],e);d=data(r)
 assert r.returncode==2 and fragment in d['error']['message'] and d['error']['ambiguousCommit'] is True and len(argv_log(e))==3

def test_release_preview_discloses_clobber(env,tmp_path):
 f=tmp_path/'x';f.write_text('x');d=data(run(['release.upload','--repo','o/r','--tag','v1','--file',str(f),'--dry-run'],env));assert d['data']['preview']['clobbersExistingAsset'] is True
def test_release_body_update_dry_run_inspects_exact_tag_without_patch(env):
 r=run(['release.body.update','--repo','o/r','--tag','v1','--body','new notes\n','--dry-run'],env);d=data(r);p=d['data']['preview']
 assert r.returncode==0 and p['releaseId']==41 and p['endpoint']=='repos/o/r/releases/41'
 assert p['request']=={'method':'PATCH','jsonKeys':['body']}
 assert p['changes']['body']=={'before':'old notes\n','after':'new notes\n'}
 assert 'name' in p['protectedSnapshot']['fields'] and p['protectedSnapshot']['assetCount']==1
 assert argv_log(env)==[['api','--hostname','github.com','--method','GET','repos/o/r/releases/tags/v1']]
 assert not Path(env['FAKE_PATCH_COUNT']).exists()
def test_release_body_update_uses_only_numeric_endpoint_body_key_and_independent_readback(env):
 r=run(['release.body.update','--repo','o/r','--tag','v1','--body','new notes\n','--confirm','release.body.update'],env);d=data(r)
 assert r.returncode==0 and d['data']['bodyMatched'] and d['data']['protectedMetadataMatched'] and d['data']['assetsMatched']
 calls=argv_log(env);assert calls==[
  ['api','--hostname','github.com','--method','GET','repos/o/r/releases/tags/v1'],
  ['api','--hostname','github.com','--method','PATCH','repos/o/r/releases/41','--input','-'],
  ['api','--hostname','github.com','--method','GET','repos/o/r/releases/41']]
 payload=json.loads(Path(env['STDIN_LOG']).read_text());assert payload=={'body':'new notes\n'} and list(payload)==['body']
 assert Path(env['FAKE_PATCH_COUNT']).read_text()=='1'
@pytest.mark.parametrize('mode,fragment',[('body-mismatch','body mismatch'),('metadata-mismatch','protected metadata mismatch'),('asset-mismatch','assets mismatch')])
def test_release_body_update_fails_closed_on_readback_mismatch(env,mode,fragment):
 r=run(['release.body.update','--repo','o/r','--tag','v1','--body','new','--confirm','release.body.update'],{**env,'FAKE_GH_MODE':mode});d=data(r)
 assert r.returncode==2 and fragment in d['error']['message'] and d['error']['ambiguousCommit'] is True
 assert Path(env['FAKE_PATCH_COUNT']).read_text()=='1' and argv_log(env)[-1][-1]=='repos/o/r/releases/41'
def test_release_body_update_rejects_wrong_tag_before_mutation(env):
 r=run(['release.body.update','--repo','o/r','--tag','v1','--body','new','--dry-run'],{**env,'FAKE_GH_MODE':'wrong-tag'})
 assert r.returncode==2 and 'exactly match' in data(r)['error']['message'] and not Path(env['FAKE_PATCH_COUNT']).exists()
def test_release_body_update_percent_encodes_tag_path_and_still_checks_exact_value(env):
 state=Path(env['FAKE_RELEASE_STATE']);release=json.loads(state.read_text());release['tag_name']='release/v1';state.write_text(json.dumps(release))
 r=run(['release.body.update','--repo','o/r','--tag','release/v1','--body','new','--dry-run'],env)
 assert r.returncode==0 and argv_log(env)[0][-1]=='repos/o/r/releases/tags/release%2Fv1'
def test_release_body_mutation_is_never_retried(env):
 r=run(['release.body.update','--repo','o/r','--tag','v1','--body','new','--confirm','release.body.update','--retries','3'],{**env,'FAKE_GH_MODE':'release-patch-rate'});d=data(r)
 assert r.returncode==2 and d['error']['retryable'] is False and d['error']['ambiguousCommit'] is True
 assert Path(env['FAKE_PATCH_COUNT']).read_text()=='1'
def test_release_body_update_requires_explicit_body_but_allows_empty(env):
 assert run(['release.body.update','--repo','o/r','--tag','v1','--dry-run'],env).returncode==2
 assert run(['release.body.update','--repo','o/r','--tag','v1','--body','','--dry-run'],env).returncode==0
def test_mutation_not_retried(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};r=run(['issue.create','--repo','o/r','--title','x','--confirm','issue.create','--retries','3'],e);assert r.returncode==2 and (tmp_path/'n').read_text()=='1'
def test_read_retry_timeout_redaction(env,tmp_path):
 e={**env,'FAKE_GH_MODE':'rate','FAKE_COUNT':str(tmp_path/'n')};assert run(['repo.view','--repo','o/r'],e).returncode==0
 assert run(['repo.view','--repo','o/r','--timeout-ms','100'],{**env,'FAKE_GH_MODE':'timeout'}).returncode==2
 r=run(['repo.view','--repo','o/r'],{**env,'FAKE_GH_MODE':'secret'});assert 'ghp_' not in r.stdout+r.stderr
@pytest.mark.parametrize('args',[['repo.view'],['repo.view','--repo','bad'],['api.get','--endpoint','graphql'],['repo.view','--repo','o/r','--limit','101'],['auth.status','--host','https://github.com'],['issue.get','--repo','o/r','--number','0'],['issue.list','--repo','o/r','--state','bad'],['issue.list','--repo','o/r','--state','merged'],['release.body.update','--repo','o/r','--tag','bad\ntag','--body','x','--dry-run']])
def test_validation(env,args):assert run(args,env).returncode==2
