"""Deterministic stand-ins for the external tools the harness calls.

Each fake reads and updates a small JSON state file next to itself so tests can
assert that mutations happened exactly once and that preconditions are
re-checked. Nothing here touches the real system.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SECRET_LINE = "2026-08-27T10:00:00+0000 host app[12]: connecting with token=abc123SECRET to broker"
CRASH_POD = {
    "metadata": {"name": "api-7c9f-crash", "namespace": "prod", "ownerReferences": [{"kind": "ReplicaSet", "name": "api-7c9f"}]},
    "spec": {"nodeName": "node-a"},
    "status": {"phase": "Running", "startTime": "2026-08-27T09:00:00Z", "containerStatuses": [
        {"name": "api", "ready": False, "restartCount": 42, "state": {"waiting": {"reason": "CrashLoopBackOff"}}, "lastState": {"terminated": {"reason": "OOMKilled"}}}]},
}
PENDING_POD = {
    "metadata": {"name": "worker-pending", "namespace": "prod", "ownerReferences": [{"kind": "ReplicaSet", "name": "worker-1"}]},
    "spec": {},
    "status": {"phase": "Pending", "conditions": [{"type": "PodScheduled", "status": "False", "reason": "Unschedulable"}], "containerStatuses": []},
}
HEALTHY_POD = {
    "metadata": {"name": "web-ok", "namespace": "prod", "ownerReferences": [{"kind": "ReplicaSet", "name": "web-1"}]},
    "spec": {"nodeName": "node-a"},
    "status": {"phase": "Running", "containerStatuses": [{"name": "web", "ready": True, "restartCount": 0, "state": {"running": {}}, "lastState": {}}]},
}
UNMANAGED_POD = {"metadata": {"name": "debug-shell", "namespace": "prod", "uid": "u-1"}, "spec": {"nodeName": "node-a"}, "status": {"phase": "Running"}}


def state_path(tool_dir: Path) -> Path:
    return tool_dir / "state.json"


def load_state(tool_dir: Path) -> dict:
    path = state_path(tool_dir)
    return json.loads(path.read_text()) if path.exists() else {"calls": [], "unitActive": "failed", "deploymentGeneration": 7}


def save_state(tool_dir: Path, state: dict) -> None:
    state_path(tool_dir).write_text(json.dumps(state))


def out(text: str, code: int = 0) -> int:
    sys.stdout.write(text)
    return code


def kubectl(args: list[str], state: dict) -> int:
    joined = " ".join(args)
    if "sleep" in args:
        time.sleep(5)
        return 0
    if args[:2] == ["config", "current-context"] or "config" in args:
        return out("kind-test\n")
    if "version" in args:
        return out(json.dumps({"clientVersion": {"gitVersion": "v1.31.0"}, "serverVersion": {"gitVersion": "v1.31.0"}}))
    if "can-i" in args:
        return out("yes\n")
    if "top" in args:
        return out("", 1)
    if "get" in args and "pods" in args and "-o" in args:
        ns_filter = args[args.index("-n") + 1] if "-n" in args else None
        items = [CRASH_POD, PENDING_POD, HEALTHY_POD]
        if ns_filter == "empty":
            items = []
        return out(json.dumps({"items": items}))
    if "get" in args and "pod" in args:
        name = args[args.index("pod") + 1]
        return out(json.dumps(UNMANAGED_POD if name == "debug-shell" else {**CRASH_POD, "metadata": {**CRASH_POD["metadata"], "uid": "u-crash"}}))
    if "get" in args and "events" in args:
        return out(json.dumps({"items": [
            {"metadata": {"namespace": "prod"}, "type": "Warning", "reason": "BackOff", "count": 12, "lastTimestamp": "2026-08-27T10:05:00Z", "involvedObject": {"kind": "Pod", "name": "api-7c9f-crash"}, "message": "Back-off restarting failed container password=hunter2"},
            {"metadata": {"namespace": "prod"}, "type": "Warning", "reason": "FailedScheduling", "count": 3, "lastTimestamp": "2026-08-27T10:07:00Z", "involvedObject": {"kind": "Pod", "name": "worker-pending"}, "message": "0/2 nodes are available: insufficient memory"},
        ]}))
    if "get" in args and "nodes" in args:
        return out(json.dumps({"items": [
            {"metadata": {"name": "node-a", "labels": {"node-role.kubernetes.io/control-plane": ""}}, "spec": {}, "status": {"conditions": [{"type": "Ready", "status": "True"}], "nodeInfo": {"kubeletVersion": "v1.31.0", "osImage": "Ubuntu"}, "allocatable": {"cpu": "4", "memory": "8Gi", "pods": "110"}}},
            {"metadata": {"name": "node-b", "labels": {}}, "spec": {"unschedulable": True, "taints": [{"key": "node.kubernetes.io/unreachable", "effect": "NoSchedule"}]}, "status": {"conditions": [{"type": "Ready", "status": "Unknown"}, {"type": "MemoryPressure", "status": "True"}], "nodeInfo": {}, "allocatable": {}}},
        ]}))
    if "get" in args and "deployment" in args:
        generation = state["deploymentGeneration"]
        return out(json.dumps({"metadata": {"name": "api", "namespace": "prod", "uid": "d-1", "generation": generation}, "spec": {"replicas": 3, "template": {"spec": {"containers": [{"image": "registry/api:1.2.3"}]}}}, "status": {"observedGeneration": generation, "readyReplicas": 2, "updatedReplicas": 3, "availableReplicas": 2, "unavailableReplicas": 1, "conditions": [{"type": "Progressing", "status": "False", "reason": "ProgressDeadlineExceeded", "message": "deadline exceeded"}]}}))
    if "describe" in args:
        return out(f"Name: {args[args.index('describe') + 2]}\nStatus: Running\nToken: token=shouldberedacted\n")
    if "logs" in args:
        return out("2026-08-27T10:00:00Z boot ok\n2026-08-27T10:00:01Z ERROR db timeout\n2026-08-27T10:00:02Z retrying\n")
    if "rollout" in args and "status" in args:
        return out("deployment \"api\" successfully rolled out\n")
    if "rollout" in args and "history" in args:
        return out("REVISION  CHANGE-CAUSE\n1         <none>\n2         <none>\n")
    if "rollout" in args and "restart" in args:
        state["calls"].append(joined)
        return out("deployment.apps/api restarted\n")
    if "delete" in args:
        state["calls"].append(joined)
        return out("pod \"api-7c9f-crash\" deleted\n")
    return out(f"unhandled kubectl args: {joined}\n", 1)


def systemctl(args: list[str], state: dict) -> int:
    if "list-units" in args:
        return out("broken.service loaded failed failed Broken Service\n")
    if "show" in args:
        unit = args[args.index("show") + 1]
        if unit == "missing":
            return out("Id=missing.service\nLoadState=not-found\nActiveState=inactive\nSubState=dead\n")
        return out(f"Id={unit}\nDescription=Fake\nLoadState=loaded\nActiveState={state['unitActive']}\nSubState={'running' if state['unitActive'] == 'active' else 'failed'}\nResult=exit-code\nNRestarts=5\nMainPID=0\nFragmentPath=/etc/systemd/system/{unit}\n")
    if "restart" in args:
        state["calls"].append(" ".join(args))
        state["unitActive"] = "active"
        return 0
    return 1


def journalctl(args: list[str], state: dict) -> int:
    if "-t" in args and "sshd" in args:
        lines = [f"2026-08-27T10:00:{i:02d}+0000 host sshd[1]: Failed password for root from 203.0.113.9 port 4{i} ssh2" for i in range(25)]
        lines += ["2026-08-27T10:01:00+0000 host sshd[1]: Accepted publickey for ops from 198.51.100.4 port 5 ssh2", "2026-08-27T10:02:00+0000 host sudo[3]: ops : TTY=pts/0 ; COMMAND=/bin/ls"]
        return out("\n".join(lines) + "\n")
    tail = int(args[args.index("-n") + 1])
    lines = [SECRET_LINE, "2026-08-27T10:00:01+0000 host kernel: Out of memory: Killed process 999 (java)", "2026-08-27T10:00:02+0000 host app[12]: ready"]
    return out("\n".join(lines[:tail]) + "\n")


def ss(args: list[str], state: dict) -> int:
    return out('tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=700,fd=3))\ntcp LISTEN 0 128 127.0.0.1:5432 0.0.0.0:* users:(("postgres",pid=800,fd=5))\nudp UNCONN 0 0 [::]:123 [::]:*\n')


def df(args: list[str], state: dict) -> int:
    if "-i" in args:
        return out("Filesystem Inodes IUsed IFree IUse% Mounted on\n/dev/root 1000 990 10 99% /\n/dev/sdb1 1000 10 990 1% /data\n")
    return out("Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/root 100000 96000 4000 96% /\n/dev/sdb1 100000 10000 90000 10% /data\n")


def ps(args: list[str], state: dict) -> int:
    return out("PID PPID USER STAT %CPU %MEM RSS ELAPSED COMMAND\n1 0 root Ss 0.1 0.2 1024 100 systemd\n42 1 app Z 95.0 1.0 2048 50 zombie-worker\n43 1 app R 50.0 40.0 819200 60 java\n")


def ip(args: list[str], state: dict) -> int:
    if "route" in args:
        return out("[]")
    return out(json.dumps([{"ifname": "lo", "operstate": "UNKNOWN", "mtu": 65536, "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}]}, {"ifname": "eth0", "operstate": "DOWN", "mtu": 1500, "addr_info": []}]))


def last(args: list[str], state: dict) -> int:
    return out("ops pts/0 198.51.100.4 Wed Aug 27 10:01:00 2026 - Wed Aug 27 11:00:00 2026 (00:59)\nroot tty1 0.0.0.0 Wed Aug 27 09:00:00 2026 still logged in\n\nwtmp begins Mon Aug 25 00:00:00 2026\n")


def find(args: list[str], state: dict) -> int:
    return out("2026-08-27T10:00:00.1234 512 /etc/ssh/sshd_config\n2026-08-27T09:00:00.0000 20 /etc/hosts\n")


def apt(args: list[str], state: dict) -> int:
    return out("Listing... Done\nopenssl/noble-security 3.0.13 amd64 [upgradable from: 3.0.12]\ncurl/noble-updates 8.5.0 amd64 [upgradable from: 8.4.0]\n")


def slowtool(args: list[str], state: dict) -> int:
    time.sleep(5)
    return 0


TOOLS = {"kubectl": kubectl, "systemctl": systemctl, "journalctl": journalctl, "ss": ss, "df": df, "ps": ps, "ip": ip, "last": last, "find": find, "apt": apt, "slowtool": slowtool}


def run(tool: str, args: list[str], tool_dir: Path) -> int:
    state = load_state(tool_dir)
    try:
        return TOOLS[tool](args, state)
    finally:
        save_state(tool_dir, state)
