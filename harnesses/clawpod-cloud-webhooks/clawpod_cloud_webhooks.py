#!/usr/bin/env python3
"""OpenClaw Harness adapter. Reads one JSON request from stdin and invokes the CLI."""
import json, subprocess, sys
MAP={
 "system.version":["system","version"], "auth.contract":["auth","contract"], "auth.status":["auth","status"],
 "permissions.list":["permissions","list"], "presets.list":["presets","list"], "source.list":["source","list"],
 "source.get":["source","get"], "playbook.list":["playbook","list"], "rule.list":["rule","list"],
 "event.inspect-redacted":["event-inspect-redacted"], "event.verify":["event-verify"], "audit.config":["audit-config"],
 "mutation.preview":["mutation-preview"], "source.update":["source-update"], "source.test-local":["source-test-local"],
 "secret.rotate-warning":["secret-action-warning","--action","rotate"],
 "secret.regenerate-warning":["secret-action-warning","--action","regenerate"]
}
def main():
    try:
        req=json.load(sys.stdin); command=req.get('command'); args=dict(req.get('args') or {}); base=req.get('baseUrl') or args.get('baseUrl')
        if command not in MAP: raise ValueError('unknown command')
        argv=['cli-anything-clawpod-cloud-webhooks','--json']
        if base: argv += ['--base-url',base]
        argv += MAP[command]
        positional={'source.get':['resourceId'],'event.inspect-redacted':['eventId'],'event.verify':['eventId'],'source.update':['sourceId']}.get(command,[])
        for k in positional:
            if k not in args: raise ValueError(f'{k} is required')
            argv.append(str(args.pop(k)))
        for k,v in sorted(args.items()):
            if k == 'baseUrl': continue
            flag='--'+''.join(('-'+c.lower() if c.isupper() else c) for c in k).replace('_','-')
            if isinstance(v,bool):
                if v: argv.append(flag)
            else: argv += [flag,json.dumps(v,separators=(',',':')) if isinstance(v,(dict,list)) else str(v)]
        p=subprocess.run(argv,text=True,capture_output=True,timeout=30)
        sys.stdout.write(p.stdout or json.dumps({'ok':False,'error':{'code':'cli_error','message':p.stderr.strip()}})); return p.returncode
    except Exception as e:
        print(json.dumps({'ok':False,'error':{'code':'adapter_error','message':str(e)}})); return 2
if __name__=='__main__': raise SystemExit(main())
