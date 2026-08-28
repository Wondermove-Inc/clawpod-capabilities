#!/usr/bin/env python3
"""ops-troubleshooting Harness.

Bounded, read-only infrastructure and security diagnostics for Linux hosts and
Kubernetes clusters, plus plan-bound remediation for a tiny allowlist of
disruptive-but-recoverable actions. Every response is one JSON envelope that
records the exact commands executed, so findings are evidence, not opinion.

Design rules:
- No shell. Every external tool runs with a fixed argv, a hard timeout, and a
  bounded, redacted stdout/stderr capture.
- Read commands never mutate anything and never read secret material
  (no Kubernetes Secrets, no credential files, no shadow contents).
- Mutations exist only as `remediate.plan` -> `remediate.apply`; apply requires
  the plan id and the plan's confirmation challenge, re-checks preconditions,
  runs exactly one allowlisted action, and verifies the outcome.
"""
from __future__ import annotations

import argparse
import datetime as dt
import grp
import hashlib
import json
import os
import platform
import pwd
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA_VERSION = 1
EXIT = {
    "ok": 0,
    "invalid": 2,
    "unavailable": 3,
    "confirmation_required": 4,
    "precondition": 5,
    "failed": 6,
    "timeout": 7,
}
LIMITS = {
    "timeoutMsDefault": 15_000,
    "timeoutMsMax": 60_000,
    "stdoutBytes": 262_144,
    "jsonBytes": 8_388_608,
    "stderrBytes": 8_192,
    "tailMax": 1_000,
    "journalTailMax": 500,
    "topMax": 50,
    "eventsMax": 200,
    "podsMax": 500,
    "findMax": 200,
    "loginsMax": 200,
    "sinceSecondsMax": 30 * 24 * 3600,
    "patternLength": 200,
    "planTtlSeconds": 900,
}
SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|password|passwd|secret|api[_-]?key|authorization)[=:]\s*\S+|"
    r"tskey-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----)",
    re.DOTALL,
)
SINCE_PATTERN = re.compile(r"^-?(\d{1,6})([smhd])$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,252}$")
K8S_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
UNIT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@:\\-]{0,254}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.:-]{0,252}[A-Za-z0-9])?$")
K8S_READ_KINDS = {
    "pod", "pods", "deployment", "deployments", "statefulset", "statefulsets", "daemonset", "daemonsets",
    "replicaset", "replicasets", "service", "services", "ingress", "ingresses", "node", "nodes", "job", "jobs",
    "cronjob", "cronjobs", "persistentvolumeclaim", "pvc", "persistentvolume", "pv", "namespace", "namespaces",
    "endpoints", "horizontalpodautoscaler", "hpa", "event", "events",
}
K8S_ROLLOUT_KINDS = {"deployment", "statefulset", "daemonset"}
CHANGE_ROOTS = ("/etc", "/opt", "/usr/local", "/srv", "/home", "/root", "/var/lib", "/var/spool/cron")
REMEDIATION_ACTIONS = {"service.restart", "k8s.rollout.restart", "k8s.pod.delete"}
PRIORITIES = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, "warning": 4, "notice": 5, "info": 6, "debug": 7}


class Fail(Exception):
    def __init__(self, code: str, message: str, kind: str = "invalid", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.details = details or {}


# ---------------------------------------------------------------------------
# helpers


def now() -> dt.datetime:
    override = os.environ.get("OPS_TROUBLESHOOTING_NOW")
    if override:
        return dt.datetime.fromisoformat(override.replace("Z", "+00:00"))
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact(text: str) -> tuple[str, bool]:
    redacted, count = SECRET_PATTERN.subn("[REDACTED]", text)
    return redacted, count > 0


def parse_since(value: str) -> int:
    match = SINCE_PATTERN.match(value.strip())
    if not match:
        raise Fail("INVALID_SINCE", "since must look like -30m, -2h, -1d, or -90s")
    amount, unit = int(match.group(1)), match.group(2)
    seconds = amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    if seconds <= 0 or seconds > LIMITS["sinceSecondsMax"]:
        raise Fail("INVALID_SINCE", "since must be between 1 second and 30 days")
    return seconds


def bounded_int(value: int | None, default: int, maximum: int, label: str) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise Fail("INVALID_LIMIT", f"{label} must be a positive integer")
    return min(value, maximum)


def check_name(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise Fail("INVALID_NAME", f"{label} contains unsupported characters")
    return value


def check_pattern(value: str | None) -> re.Pattern[str] | None:
    if value is None:
        return None
    if len(value) > LIMITS["patternLength"]:
        raise Fail("INVALID_PATTERN", "pattern is too long")
    try:
        return re.compile(value)
    except re.error as error:
        raise Fail("INVALID_PATTERN", f"pattern is not a valid regular expression: {error}")


def read_text(path: str, limit: int = LIMITS["stdoutBytes"]) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return None


def percent(used: float, total: float) -> float | None:
    if not total:
        return None
    return round(used * 100.0 / total, 1)


class Context:
    """Carries tool resolution, timeouts, and the evidence trail for one command."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.started = time.monotonic()
        self.timeout_ms = bounded_int(getattr(args, "timeout_ms", None), LIMITS["timeoutMsDefault"], LIMITS["timeoutMsMax"], "timeoutMs")
        self.tool_root = self._tool_root(getattr(args, "tool_root", None))
        self.commands: list[dict[str, Any]] = []
        self.redacted = False
        self.notes: list[str] = []

    @staticmethod
    def _tool_root(value: str | None) -> Path | None:
        if value is None:
            return None
        path = Path(value)
        if not path.is_absolute() or not path.is_dir():
            raise Fail("INVALID_TOOL_ROOT", "toolRoot must be an absolute existing directory")
        return path

    def tool(self, name: str) -> str:
        if self.tool_root is not None:
            candidate = self.tool_root / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
            raise Fail("TOOL_UNAVAILABLE", f"{name} is not available in toolRoot", "unavailable", {"tool": name})
        found = shutil.which(name)
        if not found:
            raise Fail("TOOL_UNAVAILABLE", f"{name} is not installed or not on PATH", "unavailable", {"tool": name})
        return found

    def has_tool(self, name: str) -> bool:
        try:
            self.tool(name)
            return True
        except Fail:
            return False

    def run(self, argv: list[str], *, ok_codes: tuple[int, ...] = (0,), stdin: str | None = None, stdout_limit: int = LIMITS["stdoutBytes"], redact_stdout: bool = True) -> dict[str, Any]:
        """Run one tool. Structured (JSON) callers pass redact_stdout=False and must only emit summarized fields,
        because text redaction would corrupt escaped JSON; every text caller keeps redaction on."""
        started = time.monotonic()
        env = {"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"), "LANG": "C", "LC_ALL": "C", "HOME": os.environ.get("HOME", "/"), "KUBECONFIG": os.environ.get("KUBECONFIG", "")}
        if not env["KUBECONFIG"]:
            env.pop("KUBECONFIG")
        try:
            completed = subprocess.run(
                argv, input=stdin, capture_output=True, text=True, timeout=self.timeout_ms / 1000.0,
                env=env, check=False, errors="replace",
            )
        except subprocess.TimeoutExpired:
            self.commands.append({"argv": argv, "exitCode": None, "durationMs": int((time.monotonic() - started) * 1000), "truncated": False, "timedOut": True})
            raise Fail("TIMEOUT", f"{argv[0]} exceeded {self.timeout_ms} ms", "timeout", {"argv": argv})
        except OSError as error:
            raise Fail("TOOL_FAILED", f"{argv[0]} could not be executed: {error.__class__.__name__}", "unavailable", {"argv": argv})
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        truncated = len(stdout) > stdout_limit or len(stderr) > LIMITS["stderrBytes"]
        stdout = stdout[:stdout_limit]
        stderr = stderr[: LIMITS["stderrBytes"]]
        if redact_stdout:
            stdout, r1 = redact(stdout)
        else:
            r1 = False
        stderr, r2 = redact(stderr)
        self.redacted = self.redacted or r1 or r2
        record = {"argv": argv, "exitCode": completed.returncode, "durationMs": int((time.monotonic() - started) * 1000), "truncated": truncated, "timedOut": False}
        self.commands.append(record)
        if completed.returncode not in ok_codes:
            raise Fail("TOOL_FAILED", f"{os.path.basename(argv[0])} exited with {completed.returncode}", "failed", {"argv": argv, "stderr": stderr.strip()[:1000]})
        return {"stdout": stdout, "stderr": stderr, "exitCode": completed.returncode, "truncated": truncated}

    def evidence(self) -> dict[str, Any]:
        return {
            "collectedAt": iso(now()),
            "host": socket.gethostname(),
            "harnessVersion": VERSION,
            "commands": self.commands,
            "redacted": self.redacted,
            "notes": self.notes,
            "durationMs": int((time.monotonic() - self.started) * 1000),
        }


def require_linux() -> None:
    if platform.system() != "Linux":
        raise Fail("UNSUPPORTED_PLATFORM", "host diagnostics require Linux", "unavailable")


# ---------------------------------------------------------------------------
# host.*


def meminfo() -> dict[str, int]:
    text = read_text("/proc/meminfo") or ""
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key.strip()] = int(parts[0]) * 1024
    return values


def os_release() -> dict[str, str]:
    text = read_text("/etc/os-release") or ""
    result = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"')
    return result


def top_processes(ctx: Context, sort: str, top: int) -> list[dict[str, Any]]:
    key = "-pcpu" if sort == "cpu" else "-pmem"
    out = ctx.run([ctx.tool("ps"), "-eo", "pid,ppid,user,stat,pcpu,pmem,rss,etimes,comm", f"--sort={key}"])
    rows = []
    for line in out["stdout"].splitlines()[1:]:
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        try:
            rows.append({
                "pid": int(parts[0]), "ppid": int(parts[1]), "user": parts[2], "state": parts[3],
                "cpuPercent": float(parts[4]), "memPercent": float(parts[5]), "rssBytes": int(parts[6]) * 1024,
                "elapsedSeconds": int(parts[7]), "command": parts[8],
            })
        except ValueError:
            continue
        if len(rows) >= top:
            break
    return rows


def cmd_host_overview(ctx: Context) -> dict[str, Any]:
    require_linux()
    uptime = (read_text("/proc/uptime") or "0 0").split()
    load = (read_text("/proc/loadavg") or "0 0 0").split()
    mem = meminfo()
    cpus = os.cpu_count() or 1
    release = os_release()
    findings: list[dict[str, str]] = []
    load1 = float(load[0]) if load else 0.0
    if load1 > cpus:
        findings.append({"severity": "warning", "code": "LOAD_ABOVE_CPUS", "message": f"1-minute load {load1} exceeds {cpus} CPUs"})
    total, avail = mem.get("MemTotal", 0), mem.get("MemAvailable", 0)
    if total and avail / total < 0.10:
        findings.append({"severity": "critical", "code": "MEMORY_LOW", "message": f"only {percent(avail, total)}% of memory available"})
    swap_total, swap_free = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
    if swap_total and (swap_total - swap_free) / swap_total > 0.5:
        findings.append({"severity": "warning", "code": "SWAP_PRESSURE", "message": f"{percent(swap_total - swap_free, swap_total)}% of swap in use"})
    disk = shutil.disk_usage("/")
    if disk.total and disk.used / disk.total > 0.90:
        findings.append({"severity": "critical", "code": "ROOT_DISK_FULL", "message": f"root filesystem {percent(disk.used, disk.total)}% used"})
    processes: list[dict[str, Any]] = []
    if ctx.has_tool("ps"):
        processes = top_processes(ctx, "cpu", 5)
    else:
        ctx.notes.append("ps unavailable: top processes omitted")
    return {
        "system": {
            "hostname": socket.gethostname(), "kernel": platform.release(), "os": release.get("PRETTY_NAME"),
            "architecture": platform.machine(), "cpus": cpus,
            "uptimeSeconds": int(float(uptime[0])) if uptime else None, "bootedAt": iso(now() - dt.timedelta(seconds=float(uptime[0]))) if uptime else None,
        },
        "load": {"1m": float(load[0]), "5m": float(load[1]), "15m": float(load[2])} if len(load) >= 3 else None,
        "memory": {"totalBytes": total, "availableBytes": avail, "usedPercent": percent(total - avail, total), "swapTotalBytes": swap_total, "swapUsedBytes": swap_total - swap_free},
        "rootDisk": {"totalBytes": disk.total, "usedBytes": disk.used, "usedPercent": percent(disk.used, disk.total)},
        "topCpuProcesses": processes,
        "findings": findings,
    }


def parse_df(text: str, inode: bool) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            total, used, avail = int(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            continue
        mount = parts[5]
        row = {"filesystem": parts[0], "mount": mount}
        if inode:
            row.update({"inodesTotal": total, "inodesUsed": used, "inodesUsedPercent": percent(used, total)})
        else:
            row.update({"totalBytes": total * 1024, "usedBytes": used * 1024, "availableBytes": avail * 1024, "usedPercent": percent(used, total)})
        rows.append(row)
    return rows


def cmd_host_disk(ctx: Context) -> dict[str, Any]:
    warn = bounded_int(ctx.args.warn_percent, 85, 100, "warnPercent")
    df = ctx.tool("df")
    space = parse_df(ctx.run([df, "-P", "-k", "-l"])["stdout"], inode=False)
    inodes = parse_df(ctx.run([df, "-P", "-i", "-l"])["stdout"], inode=True)
    inode_by_mount = {row["mount"]: row for row in inodes}
    findings = []
    for row in space:
        row.update({k: v for k, v in inode_by_mount.get(row["mount"], {}).items() if k.startswith("inodes")})
        if row.get("usedPercent") is not None and row["usedPercent"] >= warn:
            findings.append({"severity": "critical" if row["usedPercent"] >= 95 else "warning", "code": "DISK_USAGE_HIGH", "mount": row["mount"], "message": f"{row['mount']} is {row['usedPercent']}% full"})
        if row.get("inodesUsedPercent") is not None and row["inodesUsedPercent"] >= warn:
            findings.append({"severity": "critical" if row["inodesUsedPercent"] >= 95 else "warning", "code": "INODE_USAGE_HIGH", "mount": row["mount"], "message": f"{row['mount']} has {row['inodesUsedPercent']}% of inodes used"})
    return {"filesystems": space, "warnPercent": warn, "findings": findings}


def cmd_host_processes(ctx: Context) -> dict[str, Any]:
    sort = ctx.args.sort or "cpu"
    if sort not in {"cpu", "mem"}:
        raise Fail("INVALID_SORT", "sort must be cpu or mem")
    top = bounded_int(ctx.args.top, 15, LIMITS["topMax"], "top")
    rows = top_processes(ctx, sort, top)
    zombies = [row for row in rows if row["state"].startswith("Z")]
    findings = [{"severity": "warning", "code": "ZOMBIE_PROCESSES", "message": f"{len(zombies)} zombie processes in the top {top}"}] if zombies else []
    return {"sort": sort, "top": top, "processes": rows, "findings": findings}


def cmd_host_services(ctx: Context) -> dict[str, Any]:
    systemctl = ctx.tool("systemctl")
    unit = ctx.args.unit
    if unit:
        check_name(unit, UNIT_PATTERN, "unit")
        props = ["Id", "Description", "LoadState", "ActiveState", "SubState", "Result", "NRestarts", "MainPID", "ExecMainStartTimestamp", "ActiveEnterTimestamp", "InactiveEnterTimestamp", "UnitFileState", "FragmentPath", "MemoryCurrent", "TasksCurrent"]
        out = ctx.run([systemctl, "show", unit, "--no-pager", "-p", ",".join(props)])
        detail: dict[str, Any] = {}
        for line in out["stdout"].splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                detail[key] = value
        if not detail.get("Id") or detail.get("LoadState") == "not-found":
            raise Fail("UNIT_NOT_FOUND", f"systemd unit {unit} was not found", "precondition")
        findings = []
        if detail.get("ActiveState") not in {"active", "activating"}:
            findings.append({"severity": "critical", "code": "UNIT_NOT_ACTIVE", "message": f"{unit} is {detail.get('ActiveState')}/{detail.get('SubState')} (result {detail.get('Result')})"})
        try:
            if int(detail.get("NRestarts", "0")) > 3:
                findings.append({"severity": "warning", "code": "UNIT_RESTART_LOOP", "message": f"{unit} restarted {detail['NRestarts']} times"})
        except ValueError:
            pass
        return {"unit": detail, "findings": findings}
    out = ctx.run([systemctl, "list-units", "--type=service", "--state=failed", "--no-pager", "--plain", "--no-legend"], ok_codes=(0, 1))
    failed = []
    for line in out["stdout"].splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            failed.append({"unit": parts[0], "load": parts[1], "active": parts[2], "sub": parts[3], "description": parts[4] if len(parts) > 4 else ""})
    findings = [{"severity": "critical", "code": "FAILED_UNITS", "message": f"{len(failed)} failed service units"}] if failed else []
    return {"failedUnits": failed, "findings": findings}


def journal_lines(ctx: Context, since_seconds: int, tail: int, unit: str | None = None, priority: str | None = None, identifiers: tuple[str, ...] = (), grep: str | None = None) -> list[str]:
    argv = [ctx.tool("journalctl"), "--no-pager", "-o", "short-iso", "-q", "--since", f"-{since_seconds}s", "-n", str(tail)]
    if unit:
        argv += ["-u", unit]
    if priority is not None:
        argv += ["-p", priority]
    for identifier in identifiers:
        argv += ["-t", identifier]
    if grep:
        argv += ["-g", grep]
    out = ctx.run(argv, ok_codes=(0, 1))
    return out["stdout"].splitlines()


def cmd_host_journal(ctx: Context) -> dict[str, Any]:
    since = parse_since(ctx.args.since or "-1h")
    tail = bounded_int(ctx.args.tail, 200, LIMITS["journalTailMax"], "tail")
    unit = check_name(ctx.args.unit, UNIT_PATTERN, "unit") if ctx.args.unit else None
    priority = ctx.args.priority
    if priority is not None and priority not in PRIORITIES and priority not in {str(n) for n in range(8)}:
        raise Fail("INVALID_PRIORITY", "priority must be emerg..debug or 0..7")
    pattern = check_pattern(ctx.args.pattern)
    lines = journal_lines(ctx, since, tail, unit=unit, priority=priority)
    if pattern:
        lines = [line for line in lines if pattern.search(line)]
    counts: dict[str, int] = {}
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) >= 3:
            ident = parts[2].split("[")[0].rstrip(":")
            counts[ident] = counts.get(ident, 0) + 1
    top = sorted(counts.items(), key=lambda item: -item[1])[:10]
    return {"sinceSeconds": since, "tail": tail, "unit": unit, "priority": priority, "lineCount": len(lines), "lines": lines, "topIdentifiers": [{"identifier": k, "count": v} for k, v in top]}


# ---------------------------------------------------------------------------
# net.*


def cmd_net_ports(ctx: Context) -> dict[str, Any]:
    out = ctx.run([ctx.tool("ss"), "-H", "-tulpn"])
    sockets = []
    for line in out["stdout"].splitlines():
        parts = line.split(None, 6)
        if len(parts) < 5:
            continue
        local = parts[4]
        address, _, port = local.rpartition(":")
        process = None
        if len(parts) > 6 and "users:" in parts[6]:
            match = re.search(r'\("([^"]+)",pid=(\d+)', parts[6])
            if match:
                process = {"name": match.group(1), "pid": int(match.group(2))}
        sockets.append({"protocol": parts[0], "state": parts[1], "localAddress": address, "port": int(port) if port.isdigit() else port, "process": process})
    exposed = [s for s in sockets if s["localAddress"] in {"0.0.0.0", "*", "[::]", "::"}]
    return {"listening": sockets, "exposedToAllInterfaces": [{"protocol": s["protocol"], "port": s["port"], "process": s["process"]} for s in exposed], "findings": []}


def cmd_net_dns(ctx: Context) -> dict[str, Any]:
    name = check_name(ctx.args.name, HOST_PATTERN, "name")
    resolv = read_text("/etc/resolv.conf") or ""
    nameservers = [line.split()[1] for line in resolv.splitlines() if line.startswith("nameserver") and len(line.split()) > 1]
    started = time.monotonic()
    try:
        infos = socket.getaddrinfo(name, None)
        addresses = sorted({info[4][0] for info in infos})
        error = None
    except socket.gaierror as exc:
        addresses, error = [], str(exc)
    duration = int((time.monotonic() - started) * 1000)
    findings = [] if addresses else [{"severity": "critical", "code": "DNS_RESOLUTION_FAILED", "message": f"{name} did not resolve: {error}"}]
    if duration > 2000 and addresses:
        findings.append({"severity": "warning", "code": "DNS_SLOW", "message": f"resolution took {duration} ms"})
    return {"name": name, "addresses": addresses, "durationMs": duration, "nameservers": nameservers, "error": error, "findings": findings}


def cmd_net_reach(ctx: Context) -> dict[str, Any]:
    host = check_name(ctx.args.host, HOST_PATTERN, "host")
    port = ctx.args.port
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise Fail("INVALID_PORT", "port must be 1-65535")
    timeout = min(ctx.timeout_ms, 10_000) / 1000.0
    started = time.monotonic()
    result: dict[str, Any] = {"host": host, "port": port, "tcpConnected": False, "connectMs": None, "tls": None, "findings": []}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            result["tcpConnected"] = True
            result["connectMs"] = int((time.monotonic() - started) * 1000)
            if ctx.args.tls:
                result["tls"] = tls_inspect(sock, host, port, timeout)
    except OSError as exc:
        result["error"] = str(exc)
        result["findings"].append({"severity": "critical", "code": "TCP_UNREACHABLE", "message": f"{host}:{port} not reachable: {exc}"})
        return result
    tls = result["tls"]
    if tls:
        if tls.get("verifyError"):
            result["findings"].append({"severity": "critical", "code": "TLS_VERIFY_FAILED", "message": tls["verifyError"]})
        days = tls.get("daysRemaining")
        if days is not None and days < 14:
            result["findings"].append({"severity": "critical" if days < 3 else "warning", "code": "TLS_EXPIRING", "message": f"certificate expires in {days} days"})
    return result


def decode_der_certificate(der: bytes) -> dict[str, Any] | None:
    """Decode a DER certificate into the getpeercert() dictionary shape using only the standard library."""
    import tempfile
    decoder = getattr(getattr(ssl, "_ssl", None), "_test_decode_cert", None)
    if decoder is None:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=True) as handle:
        handle.write(ssl.DER_cert_to_PEM_cert(der))
        handle.flush()
        try:
            return decoder(handle.name)
        except Exception:  # noqa: BLE001 - private helper; fall back to fingerprint only
            return None


def tls_inspect(sock: socket.socket, host: str, port: int, timeout: float) -> dict[str, Any]:
    info: dict[str, Any] = {"verifyError": None}
    context = ssl.create_default_context()
    cert = None
    try:
        with context.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
            info["protocol"] = tls.version()
            info["verified"] = True
    except ssl.SSLError as exc:
        info["verified"] = False
        info["verifyError"] = str(exc)
    if cert is None:
        try:
            with socket.create_connection((host, port), timeout=timeout) as raw:
                unverified = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                unverified.check_hostname = False
                unverified.verify_mode = ssl.CERT_NONE
                with unverified.wrap_socket(raw, server_hostname=host) as tls:
                    der = tls.getpeercert(binary_form=True)
                    info["protocol"] = tls.version()
                    info["peerCertificateSha256"] = hashlib.sha256(der).hexdigest() if der else None
                    cert = decode_der_certificate(der) if der else None
        except (OSError, ssl.SSLError) as exc:
            info["error"] = str(exc)
            return info
    if cert:
        subject = {k: v for rdn in cert.get("subject", ()) for k, v in rdn}
        issuer = {k: v for rdn in cert.get("issuer", ()) for k, v in rdn}
        not_after = cert.get("notAfter")
        expires = dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc) if not_after else None
        info.update({
            "subject": subject.get("commonName"), "issuer": issuer.get("organizationName") or issuer.get("commonName"),
            "notBefore": cert.get("notBefore"), "notAfter": not_after,
            "daysRemaining": (expires - now()).days if expires else None,
            "subjectAltNames": [value for kind, value in cert.get("subjectAltName", ()) if kind == "DNS"][:20],
        })
    return info


def cmd_net_route(ctx: Context) -> dict[str, Any]:
    ip = ctx.tool("ip")
    routes = json.loads(ctx.run([ip, "-j", "route", "show"])["stdout"] or "[]")
    addrs = json.loads(ctx.run([ip, "-j", "addr", "show"])["stdout"] or "[]")
    interfaces = []
    for entry in addrs:
        interfaces.append({
            "name": entry.get("ifname"), "state": entry.get("operstate"), "mtu": entry.get("mtu"),
            "addresses": [f"{a.get('local')}/{a.get('prefixlen')}" for a in entry.get("addr_info", []) if a.get("family") == "inet"],
        })
    default = [r for r in routes if r.get("dst") == "default"]
    findings = [] if default else [{"severity": "critical", "code": "NO_DEFAULT_ROUTE", "message": "no default route is configured"}]
    down = [i["name"] for i in interfaces if i["state"] == "DOWN" and i["name"] != "lo"]
    if down:
        findings.append({"severity": "warning", "code": "INTERFACES_DOWN", "message": f"interfaces down: {', '.join(down)}"})
    return {"defaultRoutes": default, "routeCount": len(routes), "interfaces": interfaces, "findings": findings}


# ---------------------------------------------------------------------------
# security.*


def cmd_security_logins(ctx: Context) -> dict[str, Any]:
    count = bounded_int(ctx.args.top, 50, LIMITS["loginsMax"], "top")
    out = ctx.run([ctx.tool("last"), "-F", "-w", "-i", "-n", str(count)], ok_codes=(0, 1))
    sessions = []
    for line in out["stdout"].splitlines():
        if not line.strip() or line.startswith("wtmp begins") or line.startswith("btmp begins"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        source = parts[2] if parts[2] not in {"0.0.0.0", "-", "::"} else None
        sessions.append({"user": parts[0], "tty": parts[1], "from": source, "raw": line.strip()})
    by_user: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for session in sessions:
        by_user[session["user"]] = by_user.get(session["user"], 0) + 1
        if session["from"]:
            by_source[session["from"]] = by_source.get(session["from"], 0) + 1
    return {"sessions": sessions, "byUser": by_user, "bySource": dict(sorted(by_source.items(), key=lambda item: -item[1])[:20]), "findings": []}


def cmd_security_auth_events(ctx: Context) -> dict[str, Any]:
    since = parse_since(ctx.args.since or "-24h")
    tail = bounded_int(ctx.args.tail, 500, LIMITS["journalTailMax"], "tail")
    lines = journal_lines(ctx, since, tail, identifiers=("sshd", "sudo", "su", "login"))
    failed = re.compile(r"Failed password for (?:invalid user )?(\S+) from (\S+)")
    invalid = re.compile(r"Invalid user (\S+) from (\S+)")
    accepted = re.compile(r"Accepted (\S+) for (\S+) from (\S+)")
    sudo = re.compile(r"sudo(?:\[\d+\])?:\s+(\S+) :")
    stats = {"failedPassword": 0, "invalidUser": 0, "accepted": 0, "sudo": 0}
    sources: dict[str, int] = {}
    accepted_users: dict[str, int] = {}
    for line in lines:
        if match := failed.search(line):
            stats["failedPassword"] += 1
            sources[match.group(2)] = sources.get(match.group(2), 0) + 1
        elif match := invalid.search(line):
            stats["invalidUser"] += 1
            sources[match.group(2)] = sources.get(match.group(2), 0) + 1
        elif match := accepted.search(line):
            stats["accepted"] += 1
            accepted_users[match.group(2)] = accepted_users.get(match.group(2), 0) + 1
        elif sudo.search(line):
            stats["sudo"] += 1
    findings = []
    top_sources = sorted(sources.items(), key=lambda item: -item[1])[:10]
    for source, hits in top_sources:
        if hits >= 20:
            findings.append({"severity": "critical", "code": "BRUTE_FORCE_SOURCE", "message": f"{hits} failed logins from {source}"})
    if stats["failedPassword"] + stats["invalidUser"] >= 50:
        findings.append({"severity": "warning", "code": "AUTH_FAILURE_VOLUME", "message": f"{stats['failedPassword'] + stats['invalidUser']} failed authentication attempts"})
    return {"sinceSeconds": since, "lineCount": len(lines), "stats": stats, "topFailedSources": [{"source": s, "count": c} for s, c in top_sources], "acceptedByUser": accepted_users, "sample": lines[-50:], "findings": findings}


def cmd_security_users(ctx: Context) -> dict[str, Any]:
    login_shells = {"/bin/bash", "/bin/sh", "/bin/zsh", "/usr/bin/bash", "/usr/bin/zsh", "/usr/bin/fish", "/bin/fish", "/usr/bin/sh"}
    accounts = []
    root_accounts = []
    for entry in pwd.getpwall():
        interactive = entry.pw_shell in login_shells
        if entry.pw_uid == 0:
            root_accounts.append(entry.pw_name)
        if interactive or entry.pw_uid == 0:
            keys = None
            auth_keys = Path(entry.pw_dir) / ".ssh" / "authorized_keys"
            try:
                keys = sum(1 for line in auth_keys.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.startswith("#"))
            except OSError:
                keys = None
            accounts.append({"user": entry.pw_name, "uid": entry.pw_uid, "shell": entry.pw_shell, "home": entry.pw_dir, "authorizedKeys": keys})
    admin_groups = {}
    for name in ("sudo", "wheel", "admin", "docker"):
        try:
            admin_groups[name] = sorted(grp.getgrnam(name).gr_mem)
        except KeyError:
            continue
    files = {}
    for path in ("/etc/passwd", "/etc/shadow", "/etc/group", "/etc/sudoers", "/etc/ssh/sshd_config"):
        try:
            info = os.stat(path)
            files[path] = {"modifiedAt": iso(dt.datetime.fromtimestamp(info.st_mtime, dt.timezone.utc)), "mode": oct(stat.S_IMODE(info.st_mode))}
        except OSError:
            continue
    findings = []
    if len(root_accounts) > 1:
        findings.append({"severity": "critical", "code": "MULTIPLE_UID0", "message": f"uid 0 accounts: {', '.join(root_accounts)}"})
    shadow = files.get("/etc/shadow")
    if shadow and shadow["mode"] not in {"0o640", "0o600", "0o0"}:
        findings.append({"severity": "critical", "code": "SHADOW_PERMISSIONS", "message": f"/etc/shadow mode is {shadow['mode']}"})
    return {"interactiveAccounts": accounts, "uid0Accounts": root_accounts, "adminGroups": admin_groups, "sensitiveFiles": files, "findings": findings}


def cmd_security_updates(ctx: Context) -> dict[str, Any]:
    if ctx.has_tool("apt"):
        out = ctx.run([ctx.tool("apt"), "list", "--upgradable"], ok_codes=(0,))
        packages = []
        for line in out["stdout"].splitlines():
            if "/" not in line or line.startswith("Listing"):
                continue
            name, rest = line.split("/", 1)
            packages.append({"name": name, "detail": rest.strip(), "security": "-security" in rest or "security" in rest.split()[0]})
        manager = "apt"
    elif ctx.has_tool("dnf"):
        out = ctx.run([ctx.tool("dnf"), "-q", "check-update"], ok_codes=(0, 100))
        packages = []
        for line in out["stdout"].splitlines():
            parts = line.split()
            if len(parts) >= 3 and "." in parts[0]:
                packages.append({"name": parts[0], "detail": f"{parts[1]} {parts[2]}", "security": False})
        manager = "dnf"
    else:
        raise Fail("UNSUPPORTED_PACKAGE_MANAGER", "neither apt nor dnf is available", "unavailable")
    security = [p for p in packages if p["security"]]
    findings = []
    if security:
        findings.append({"severity": "warning", "code": "SECURITY_UPDATES_PENDING", "message": f"{len(security)} security updates pending"})
    reboot = Path("/var/run/reboot-required").exists()
    if reboot:
        findings.append({"severity": "warning", "code": "REBOOT_REQUIRED", "message": "the system reports a pending reboot"})
    return {"packageManager": manager, "upgradable": packages[:LIMITS["findMax"]], "upgradableCount": len(packages), "securityCount": len(security), "rebootRequired": reboot, "findings": findings}


# ---------------------------------------------------------------------------
# change.*


def cmd_change_recent(ctx: Context) -> dict[str, Any]:
    since = parse_since(ctx.args.since or "-24h")
    root = ctx.args.root or "/etc"
    path = Path(root)
    if not path.is_absolute():
        raise Fail("INVALID_ROOT", "root must be an absolute path")
    resolved = path.resolve()
    if not any(str(resolved) == allowed or str(resolved).startswith(allowed + "/") for allowed in CHANGE_ROOTS):
        raise Fail("ROOT_NOT_ALLOWED", f"root must be within {', '.join(CHANGE_ROOTS)}")
    if not resolved.is_dir():
        raise Fail("INVALID_ROOT", "root is not a directory", "precondition")
    limit = bounded_int(ctx.args.top, 100, LIMITS["findMax"], "top")
    minutes = max(1, since // 60)
    out = ctx.run([ctx.tool("find"), str(resolved), "-xdev", "-type", "f", "-mmin", f"-{minutes}", "-printf", "%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n"], ok_codes=(0, 1))
    files = []
    for line in out["stdout"].splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3:
            files.append({"modifiedAt": parts[0].split(".")[0] + "Z" if "." in parts[0] else parts[0], "sizeBytes": int(parts[1]) if parts[1].isdigit() else None, "path": parts[2]})
    files.sort(key=lambda item: item["modifiedAt"], reverse=True)
    packages: list[dict[str, Any]] = []
    history = read_text("/var/log/apt/history.log", 65_536)
    if history:
        block: dict[str, str] = {}
        for line in history.splitlines():
            if line.startswith("Start-Date:"):
                block = {"startedAt": line.split(":", 1)[1].strip()}
            elif line.startswith("Commandline:") and block:
                block["commandline"] = redact(line.split(":", 1)[1].strip())[0]
            elif line.startswith("End-Date:") and block:
                packages.append(block)
                block = {}
        packages = packages[-20:]
    elif ctx.has_tool("rpm"):
        out = ctx.run([ctx.tool("rpm"), "-qa", "--last"], ok_codes=(0,))
        packages = [{"package": line.split()[0], "installedAt": " ".join(line.split()[1:])} for line in out["stdout"].splitlines()[:20] if line.strip()]
    return {"root": str(resolved), "sinceSeconds": since, "fileCount": len(files), "files": files[:limit], "recentPackageOperations": packages, "findings": []}


# ---------------------------------------------------------------------------
# k8s.*


def kube_base(ctx: Context) -> list[str]:
    argv = [ctx.tool("kubectl")]
    kubeconfig = getattr(ctx.args, "kubeconfig", None)
    if kubeconfig:
        path = Path(kubeconfig)
        if not path.is_absolute() or not path.is_file():
            raise Fail("INVALID_KUBECONFIG", "kubeconfig must be an absolute path to an existing file")
        argv += ["--kubeconfig", str(path)]
    context = getattr(ctx.args, "context", None)
    if context:
        argv += ["--context", check_name(context, NAME_PATTERN, "context")]
    argv += ["--request-timeout", f"{max(1, ctx.timeout_ms // 1000)}s"]
    return argv


def kube_namespace(ctx: Context, *, allow_all: bool = True) -> list[str]:
    if getattr(ctx.args, "all_namespaces", False):
        if not allow_all:
            raise Fail("INVALID_NAMESPACE", "this command requires a single namespace")
        return ["-A"]
    namespace = getattr(ctx.args, "namespace", None)
    if namespace:
        return ["-n", check_name(namespace, K8S_NAME_PATTERN, "namespace")]
    return []


def kube_json(ctx: Context, argv: list[str]) -> Any:
    out = ctx.run(argv, stdout_limit=LIMITS["jsonBytes"], redact_stdout=False)
    try:
        return json.loads(out["stdout"])
    except json.JSONDecodeError:
        raise Fail("TOOL_FAILED", "kubectl did not return JSON" + (" (output truncated)" if out["truncated"] else ""), "failed")


def summarize_pod(item: dict[str, Any]) -> dict[str, Any]:
    meta, status, spec = item.get("metadata", {}), item.get("status", {}), item.get("spec", {})
    containers = []
    restarts = 0
    issues: list[str] = []
    for cs in status.get("containerStatuses", []) + status.get("initContainerStatuses", []):
        restarts += cs.get("restartCount", 0)
        state = cs.get("state", {})
        last = cs.get("lastState", {})
        waiting = state.get("waiting", {}).get("reason")
        terminated = state.get("terminated", {}).get("reason")
        last_terminated = last.get("terminated", {}).get("reason")
        if waiting:
            issues.append(waiting)
        if terminated and terminated != "Completed":
            issues.append(terminated)
        if last_terminated == "OOMKilled":
            issues.append("OOMKilled(previous)")
        containers.append({"name": cs.get("name"), "ready": cs.get("ready"), "restarts": cs.get("restartCount", 0), "waiting": waiting, "terminated": terminated, "lastTerminated": last_terminated})
    phase = status.get("phase")
    if phase in {"Pending", "Failed", "Unknown"}:
        issues.append(phase)
    for condition in status.get("conditions", []):
        if condition.get("type") == "PodScheduled" and condition.get("status") == "False":
            issues.append(f"Unschedulable:{condition.get('reason')}")
    ready = all(c["ready"] for c in containers) if containers else phase == "Succeeded"
    return {
        "namespace": meta.get("namespace"), "name": meta.get("name"), "phase": phase, "ready": ready, "restarts": restarts,
        "node": spec.get("nodeName"), "startedAt": status.get("startTime"), "owner": (meta.get("ownerReferences") or [{}])[0].get("kind"),
        "issues": sorted(set(issues)), "containers": containers,
    }


def cmd_k8s_pods(ctx: Context) -> dict[str, Any]:
    limit = bounded_int(ctx.args.top, 200, LIMITS["podsMax"], "top")
    argv = kube_base(ctx) + ["get", "pods", "-o", "json"] + kube_namespace(ctx)
    selector = ctx.args.selector
    if selector:
        if len(selector) > LIMITS["patternLength"] or not re.match(r"^[A-Za-z0-9_.,=!()/ -]+$", selector):
            raise Fail("INVALID_SELECTOR", "selector contains unsupported characters")
        argv += ["-l", selector]
    data = kube_json(ctx, argv)
    pods = [summarize_pod(item) for item in data.get("items", [])]
    unhealthy = [pod for pod in pods if pod["issues"] or not pod["ready"] and pod["phase"] != "Succeeded"]
    unhealthy.sort(key=lambda pod: (-pod["restarts"], pod["namespace"] or "", pod["name"] or ""))
    findings = []
    reasons: dict[str, int] = {}
    for pod in unhealthy:
        for issue in pod["issues"]:
            reasons[issue] = reasons.get(issue, 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
        severity = "critical" if reason in {"CrashLoopBackOff", "OOMKilled", "ImagePullBackOff", "ErrImagePull", "Failed"} or reason.startswith("Unschedulable") else "warning"
        findings.append({"severity": severity, "code": f"POD_{reason.upper().replace('(', '_').replace(')', '').replace(':', '_')}", "message": f"{count} pods report {reason}"})
    return {"podCount": len(pods), "unhealthyCount": len(unhealthy), "unhealthy": unhealthy[:limit], "healthySample": [p["name"] for p in pods if p not in unhealthy][:20], "findings": findings}


def cmd_k8s_describe(ctx: Context) -> dict[str, Any]:
    kind = (ctx.args.kind or "").lower()
    if kind not in K8S_READ_KINDS:
        raise Fail("KIND_NOT_ALLOWED", f"kind must be one of the read-only kinds; secrets and configmaps are never described")
    name = check_name(ctx.args.name, K8S_NAME_PATTERN, "name")
    argv = kube_base(ctx) + ["describe", kind, name] + kube_namespace(ctx, allow_all=False)
    out = ctx.run(argv)
    return {"kind": kind, "name": name, "description": out["stdout"], "truncated": out["truncated"]}


def cmd_k8s_logs(ctx: Context) -> dict[str, Any]:
    name = check_name(ctx.args.name, K8S_NAME_PATTERN, "pod")
    tail = bounded_int(ctx.args.tail, 200, LIMITS["tailMax"], "tail")
    since = parse_since(ctx.args.since or "-1h")
    argv = kube_base(ctx) + ["logs", name, "--tail", str(tail), "--since", f"{since}s", "--timestamps"] + kube_namespace(ctx, allow_all=False)
    if ctx.args.container:
        argv += ["-c", check_name(ctx.args.container, K8S_NAME_PATTERN, "container")]
    if ctx.args.previous:
        argv += ["--previous"]
    pattern = check_pattern(ctx.args.pattern)
    out = ctx.run(argv)
    lines = out["stdout"].splitlines()
    if pattern:
        lines = [line for line in lines if pattern.search(line)]
    errors = sum(1 for line in lines if re.search(r"(?i)\b(error|exception|fatal|panic|traceback)\b", line))
    return {"pod": name, "container": ctx.args.container, "previous": bool(ctx.args.previous), "tail": tail, "sinceSeconds": since, "lineCount": len(lines), "errorLikeLines": errors, "lines": lines, "truncated": out["truncated"]}


def cmd_k8s_events(ctx: Context) -> dict[str, Any]:
    limit = bounded_int(ctx.args.top, 100, LIMITS["eventsMax"], "top")
    argv = kube_base(ctx) + ["get", "events", "-o", "json"] + kube_namespace(ctx)
    if not ctx.args.all_types:
        argv += ["--field-selector", "type=Warning"]
    data = kube_json(ctx, argv)
    events = []
    for item in data.get("items", []):
        obj = item.get("involvedObject", {})
        events.append({
            "namespace": item.get("metadata", {}).get("namespace"), "type": item.get("type"), "reason": item.get("reason"),
            "object": f"{obj.get('kind')}/{obj.get('name')}", "count": item.get("count", 1),
            "lastSeen": item.get("lastTimestamp") or item.get("eventTime") or item.get("metadata", {}).get("creationTimestamp"),
            "message": redact(item.get("message", ""))[0][:500],
        })
    events.sort(key=lambda event: event["lastSeen"] or "", reverse=True)
    reasons: dict[str, int] = {}
    for event in events:
        reasons[event["reason"]] = reasons.get(event["reason"], 0) + event["count"]
    findings = [{"severity": "warning", "code": "WARNING_EVENTS", "message": f"{len(events)} warning events; top reasons: " + ", ".join(f"{k}×{v}" for k, v in sorted(reasons.items(), key=lambda i: -i[1])[:5])}] if events and not ctx.args.all_types else []
    return {"eventCount": len(events), "events": events[:limit], "reasonCounts": reasons, "findings": findings}


def cmd_k8s_nodes(ctx: Context) -> dict[str, Any]:
    data = kube_json(ctx, kube_base(ctx) + ["get", "nodes", "-o", "json"])
    nodes = []
    findings = []
    for item in data.get("items", []):
        meta, status, spec = item.get("metadata", {}), item.get("status", {}), item.get("spec", {})
        conditions = {c.get("type"): c.get("status") for c in status.get("conditions", [])}
        ready = conditions.get("Ready") == "True"
        pressure = [t for t in ("MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable") if conditions.get(t) == "True"]
        node = {
            "name": meta.get("name"), "ready": ready, "pressure": pressure, "unschedulable": bool(spec.get("unschedulable")),
            "taints": [f"{t.get('key')}={t.get('value', '')}:{t.get('effect')}" for t in spec.get("taints", [])],
            "kubeletVersion": status.get("nodeInfo", {}).get("kubeletVersion"), "os": status.get("nodeInfo", {}).get("osImage"),
            "allocatable": {k: status.get("allocatable", {}).get(k) for k in ("cpu", "memory", "pods")},
            "roles": sorted(label.split("/", 1)[1] for label in meta.get("labels", {}) if label.startswith("node-role.kubernetes.io/")),
        }
        nodes.append(node)
        if not ready:
            findings.append({"severity": "critical", "code": "NODE_NOT_READY", "message": f"node {node['name']} is not Ready"})
        for condition in pressure:
            findings.append({"severity": "warning", "code": f"NODE_{condition.upper()}", "message": f"node {node['name']} reports {condition}"})
    usage = None
    if ctx.args.usage:
        try:
            out = ctx.run(kube_base(ctx) + ["top", "nodes", "--no-headers"])
            usage = []
            for line in out["stdout"].splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    usage.append({"name": parts[0], "cpu": parts[1], "cpuPercent": parts[2], "memory": parts[3], "memoryPercent": parts[4]})
        except Fail as error:
            ctx.notes.append(f"kubectl top nodes unavailable: {error.message}")
    return {"nodeCount": len(nodes), "nodes": nodes, "usage": usage, "findings": findings}


def cmd_k8s_rollout(ctx: Context) -> dict[str, Any]:
    kind = (ctx.args.kind or "deployment").lower()
    if kind not in K8S_ROLLOUT_KINDS:
        raise Fail("KIND_NOT_ALLOWED", "kind must be deployment, statefulset, or daemonset")
    name = check_name(ctx.args.name, K8S_NAME_PATTERN, "name")
    namespace = kube_namespace(ctx, allow_all=False)
    obj = kube_json(ctx, kube_base(ctx) + ["get", kind, name, "-o", "json"] + namespace)
    status_out = ctx.run(kube_base(ctx) + ["rollout", "status", f"{kind}/{name}", "--timeout", "5s"] + namespace, ok_codes=(0, 1))
    history = ctx.run(kube_base(ctx) + ["rollout", "history", f"{kind}/{name}"] + namespace, ok_codes=(0, 1))
    status, spec, meta = obj.get("status", {}), obj.get("spec", {}), obj.get("metadata", {})
    summary = {
        "kind": kind, "name": name, "namespace": meta.get("namespace"), "generation": meta.get("generation"), "observedGeneration": status.get("observedGeneration"),
        "desired": spec.get("replicas"), "ready": status.get("readyReplicas", status.get("numberReady")), "updated": status.get("updatedReplicas", status.get("updatedNumberScheduled")),
        "available": status.get("availableReplicas", status.get("numberAvailable")), "unavailable": status.get("unavailableReplicas", status.get("numberUnavailable")),
        "images": [c.get("image") for c in spec.get("template", {}).get("spec", {}).get("containers", [])],
        "conditions": [{"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason"), "message": redact(c.get("message", ""))[0][:300]} for c in status.get("conditions", [])],
        "rolloutStatus": status_out["stdout"].strip()[:500], "rolloutComplete": status_out["exitCode"] == 0, "history": history["stdout"].strip().splitlines()[-10:],
    }
    findings = []
    if not summary["rolloutComplete"]:
        findings.append({"severity": "critical", "code": "ROLLOUT_INCOMPLETE", "message": summary["rolloutStatus"] or "rollout has not completed"})
    for condition in summary["conditions"]:
        if condition["type"] == "Progressing" and condition["status"] == "False":
            findings.append({"severity": "critical", "code": "ROLLOUT_STALLED", "message": condition["message"] or condition["reason"] or "progress deadline exceeded"})
    return {**summary, "findings": findings}


def cmd_k8s_context(ctx: Context) -> dict[str, Any]:
    base = kube_base(ctx)
    current = ctx.run(base + ["config", "current-context"], ok_codes=(0, 1))["stdout"].strip()
    version = ctx.run(base + ["version", "-o", "json"], ok_codes=(0, 1))
    try:
        version_json = json.loads(version["stdout"] or "{}")
    except json.JSONDecodeError:
        version_json = {}
    checks = {}
    for verb, resource in (("list", "pods"), ("list", "nodes"), ("get", "events")):
        out = ctx.run(base + ["auth", "can-i", verb, resource, "-A"], ok_codes=(0, 1))
        checks[f"{verb} {resource}"] = out["stdout"].strip() == "yes"
    findings = []
    if not current:
        findings.append({"severity": "critical", "code": "NO_KUBE_CONTEXT", "message": "no current kubectl context is configured"})
    if not version_json.get("serverVersion"):
        findings.append({"severity": "critical", "code": "API_UNREACHABLE", "message": "the Kubernetes API server did not answer a version request"})
    return {"currentContext": current or None, "clientVersion": version_json.get("clientVersion", {}).get("gitVersion"), "serverVersion": version_json.get("serverVersion", {}).get("gitVersion"), "permissions": checks, "findings": findings}


# ---------------------------------------------------------------------------
# triage.*


def collect(ctx: Context, label: str, func) -> dict[str, Any]:
    try:
        return {"ok": True, "data": func(ctx)}
    except Fail as error:
        ctx.notes.append(f"{label}: {error.code}: {error.message}")
        return {"ok": False, "error": {"code": error.code, "message": error.message}}


def cmd_triage_host(ctx: Context) -> dict[str, Any]:
    ctx.args.warn_percent = ctx.args.warn_percent or 85
    ctx.args.unit = None
    ctx.args.priority = "err"
    ctx.args.pattern = None
    ctx.args.since = ctx.args.since or "-1h"
    ctx.args.tail = min(ctx.args.tail or 100, LIMITS["journalTailMax"])
    sections = {
        "overview": collect(ctx, "overview", cmd_host_overview),
        "disk": collect(ctx, "disk", cmd_host_disk),
        "services": collect(ctx, "services", cmd_host_services),
        "journalErrors": collect(ctx, "journal", cmd_host_journal),
        "ports": collect(ctx, "ports", cmd_net_ports),
    }
    findings = [f for section in sections.values() if section.get("ok") for f in section["data"].get("findings", [])]
    return {"sections": sections, "findings": findings, "summary": summarize_findings(findings)}


def cmd_triage_k8s(ctx: Context) -> dict[str, Any]:
    ctx.args.usage = False
    ctx.args.selector = None
    ctx.args.top = ctx.args.top or 50
    ctx.args.all_types = False
    sections = {
        "context": collect(ctx, "context", cmd_k8s_context),
        "nodes": collect(ctx, "nodes", cmd_k8s_nodes),
        "pods": collect(ctx, "pods", cmd_k8s_pods),
        "warningEvents": collect(ctx, "events", cmd_k8s_events),
    }
    findings = [f for section in sections.values() if section.get("ok") for f in section["data"].get("findings", [])]
    return {"sections": sections, "findings": findings, "summary": summarize_findings(findings)}


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"critical": 0, "warning": 0}
    for finding in findings:
        counts[finding.get("severity", "warning")] = counts.get(finding.get("severity", "warning"), 0) + 1
    return {"critical": counts["critical"], "warning": counts["warning"], "healthy": not findings}


# ---------------------------------------------------------------------------
# remediate.*


def secure_state_root(value: str, create: bool) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise Fail("INVALID_STATE_ROOT", "stateRoot must be an absolute path")
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        (path / "plans").mkdir(mode=0o700, exist_ok=True)
    try:
        info = os.lstat(path)
    except OSError:
        raise Fail("STATE_UNAVAILABLE", "stateRoot is unavailable", "precondition")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise Fail("UNSAFE_STATE", "stateRoot must be an owner-only (0700) directory", "precondition")
    return path


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_target(action: str, ctx: Context) -> dict[str, Any]:
    target = ctx.args.target or ""
    if action == "service.restart":
        return {"unit": check_name(target, UNIT_PATTERN, "target")}
    namespace = ctx.args.namespace
    if not namespace:
        raise Fail("INVALID_NAMESPACE", "kubernetes remediation requires namespace")
    check_name(namespace, K8S_NAME_PATTERN, "namespace")
    if action == "k8s.rollout.restart":
        if "/" not in target:
            raise Fail("INVALID_TARGET", "target must be kind/name, e.g. deployment/api")
        kind, name = target.split("/", 1)
        if kind.lower() not in K8S_ROLLOUT_KINDS:
            raise Fail("KIND_NOT_ALLOWED", "kind must be deployment, statefulset, or daemonset")
        return {"namespace": namespace, "kind": kind.lower(), "name": check_name(name, K8S_NAME_PATTERN, "name")}
    if action == "k8s.pod.delete":
        return {"namespace": namespace, "pod": check_name(target, K8S_NAME_PATTERN, "target")}
    raise Fail("ACTION_NOT_ALLOWED", f"action must be one of {sorted(REMEDIATION_ACTIONS)}")


def snapshot_preconditions(ctx: Context, action: str, target: dict[str, Any]) -> dict[str, Any]:
    if action == "service.restart":
        out = ctx.run([ctx.tool("systemctl"), "show", target["unit"], "--no-pager", "-p", "Id,LoadState,ActiveState,SubState,MainPID,NRestarts,FragmentPath"])
        props = dict(line.split("=", 1) for line in out["stdout"].splitlines() if "=" in line)
        if not props.get("Id") or props.get("LoadState") == "not-found":
            raise Fail("UNIT_NOT_FOUND", f"unit {target['unit']} does not exist", "precondition")
        return {"unit": props.get("Id"), "loadState": props.get("LoadState"), "activeState": props.get("ActiveState"), "subState": props.get("SubState"), "fragmentPath": props.get("FragmentPath")}
    namespace = ["-n", target["namespace"]]
    if action == "k8s.rollout.restart":
        obj = kube_json(ctx, kube_base(ctx) + ["get", target["kind"], target["name"], "-o", "json"] + namespace)
        spec, status, meta = obj.get("spec", {}), obj.get("status", {}), obj.get("metadata", {})
        return {"uid": meta.get("uid"), "generation": meta.get("generation"), "replicas": spec.get("replicas"), "images": [c.get("image") for c in spec.get("template", {}).get("spec", {}).get("containers", [])], "readyReplicas": status.get("readyReplicas", status.get("numberReady"))}
    obj = kube_json(ctx, kube_base(ctx) + ["get", "pod", target["pod"], "-o", "json"] + namespace)
    meta, status = obj.get("metadata", {}), obj.get("status", {})
    owner = (meta.get("ownerReferences") or [{}])[0]
    if not owner.get("kind"):
        raise Fail("POD_UNMANAGED", "refusing to delete a pod without a controller owner; it would not be recreated", "precondition")
    return {"uid": meta.get("uid"), "ownerKind": owner.get("kind"), "ownerName": owner.get("name"), "phase": status.get("phase"), "node": obj.get("spec", {}).get("nodeName")}


def cmd_remediate_plan(ctx: Context) -> dict[str, Any]:
    action = ctx.args.action
    if action not in REMEDIATION_ACTIONS:
        raise Fail("ACTION_NOT_ALLOWED", f"action must be one of {sorted(REMEDIATION_ACTIONS)}")
    root = secure_state_root(ctx.args.state_root, create=True)
    target = parse_target(action, ctx)
    preconditions = snapshot_preconditions(ctx, action, target)
    created = now()
    plan = {
        "schemaVersion": SCHEMA_VERSION, "id": uuid.uuid4().hex, "action": action, "target": target,
        "preconditions": preconditions, "preconditionsHash": digest(preconditions), "reason": (ctx.args.reason or "")[:500],
        "createdAt": iso(created), "expiresAt": iso(created + dt.timedelta(seconds=LIMITS["planTtlSeconds"])),
        "commands": planned_commands(action, target), "rollback": rollback_note(action), "harnessVersion": VERSION,
    }
    plan["confirmationChallenge"] = digest({k: plan[k] for k in ("id", "action", "target", "preconditionsHash", "expiresAt")})
    path = root / "plans" / f"{plan['id']}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(plan, stream, sort_keys=True)
    return {"plan": plan, "nextAction": {"kind": "confirm", "message": "Review the plan; obtain approval; then run remediate.apply with this planId and confirmationChallenge before it expires.", "planId": plan["id"], "confirmationChallenge": plan["confirmationChallenge"], "expiresAt": plan["expiresAt"]}}


def planned_commands(action: str, target: dict[str, Any]) -> list[str]:
    if action == "service.restart":
        return [f"systemctl restart {target['unit']}", f"systemctl show {target['unit']} -p ActiveState,SubState,NRestarts"]
    if action == "k8s.rollout.restart":
        return [f"kubectl -n {target['namespace']} rollout restart {target['kind']}/{target['name']}", f"kubectl -n {target['namespace']} rollout status {target['kind']}/{target['name']} --timeout=<timeout>"]
    return [f"kubectl -n {target['namespace']} delete pod {target['pod']} --wait=false", f"kubectl -n {target['namespace']} get pods -l <owner selector>"]


def rollback_note(action: str) -> str:
    return {
        "service.restart": "A restart has no rollback; if the unit fails to come back, inspect journalctl -u <unit> and restore the previous configuration or package.",
        "k8s.rollout.restart": "Use kubectl rollout undo <kind>/<name> to return to the previous ReplicaSet/revision if the restarted pods do not become ready.",
        "k8s.pod.delete": "The controller recreates the pod automatically; if the replacement fails, inspect kubectl describe and the controller's rollout status.",
    }[action]


def load_plan(root: Path, plan_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{32}", plan_id or ""):
        raise Fail("INVALID_PLAN_ID", "planId must be a 32-character hex id")
    path = root / "plans" / f"{plan_id}.json"
    try:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise Fail("UNSAFE_STATE", "plan file must be a regular 0600 file", "precondition")
        plan = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise Fail("PLAN_REQUIRED", "a fresh remediation plan is required", "confirmation_required")
    except json.JSONDecodeError:
        raise Fail("PLAN_REQUIRED", "the plan file is unreadable; create a fresh plan", "confirmation_required")
    return plan


def cmd_remediate_apply(ctx: Context) -> dict[str, Any]:
    root = secure_state_root(ctx.args.state_root, create=False)
    plan = load_plan(root, ctx.args.plan_id)
    if plan.get("harnessVersion") != VERSION or plan.get("schemaVersion") != SCHEMA_VERSION:
        raise Fail("PLAN_INCOMPATIBLE", "the plan was produced by a different harness version; create a fresh plan", "confirmation_required")
    expected = digest({k: plan.get(k) for k in ("id", "action", "target", "preconditionsHash", "expiresAt")})
    if ctx.args.confirm != expected or plan.get("confirmationChallenge") != expected:
        raise Fail("CONFIRMATION_MISMATCH", "confirm does not bind this exact plan", "confirmation_required")
    if now() > dt.datetime.fromisoformat(plan["expiresAt"].replace("Z", "+00:00")):
        raise Fail("PLAN_EXPIRED", "the plan expired; re-plan and re-approve", "confirmation_required")
    if plan.get("consumedAt"):
        raise Fail("PLAN_CONSUMED", "this plan was already applied; create a fresh plan", "confirmation_required")
    action, target = plan["action"], plan["target"]
    current = snapshot_preconditions(ctx, action, target)
    if digest(current) != plan["preconditionsHash"]:
        raise Fail("PLAN_STALE", "the target changed since the plan was approved; re-plan", "precondition", {"planned": plan["preconditions"], "current": current})
    plan["consumedAt"] = iso(now())
    path = root / "plans" / f"{plan['id']}.json"
    path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    effects: list[str] = []
    if action == "service.restart":
        systemctl = ctx.tool("systemctl")
        ctx.run([systemctl, "restart", target["unit"]])
        effects.append(f"restarted systemd unit {target['unit']}")
        out = ctx.run([systemctl, "show", target["unit"], "--no-pager", "-p", "ActiveState,SubState,NRestarts,MainPID"])
        props = dict(line.split("=", 1) for line in out["stdout"].splitlines() if "=" in line)
        verified = props.get("ActiveState") in {"active", "activating"}
        outcome = {"activeState": props.get("ActiveState"), "subState": props.get("SubState"), "mainPid": props.get("MainPID")}
    elif action == "k8s.rollout.restart":
        base = kube_base(ctx) + ["-n", target["namespace"]]
        ctx.run(base + ["rollout", "restart", f"{target['kind']}/{target['name']}"])
        effects.append(f"restarted rollout of {target['kind']}/{target['name']} in {target['namespace']}")
        status = ctx.run(base + ["rollout", "status", f"{target['kind']}/{target['name']}", "--timeout", f"{max(5, ctx.timeout_ms // 1000 - 5)}s"], ok_codes=(0, 1))
        verified = status["exitCode"] == 0
        outcome = {"rolloutStatus": status["stdout"].strip()[:500]}
    else:
        base = kube_base(ctx) + ["-n", target["namespace"]]
        ctx.run(base + ["delete", "pod", target["pod"], "--wait=false"])
        effects.append(f"deleted pod {target['pod']} in {target['namespace']} (controller {current['ownerKind']}/{current['ownerName']} recreates it)")
        verified = True
        outcome = {"owner": f"{current['ownerKind']}/{current['ownerName']}"}
    result = {"planId": plan["id"], "action": action, "target": target, "verified": verified, "outcome": outcome, "rollback": plan.get("rollback")}
    if not verified:
        raise Fail("VERIFY_FAILED", "the action ran but verification did not confirm recovery", "failed", {**result, "effects": effects})
    return {**result, "effects": effects}


def cmd_version(ctx: Context) -> dict[str, Any]:
    return {"version": VERSION, "schemaVersion": SCHEMA_VERSION, "platform": platform.system(), "limits": LIMITS, "remediationActions": sorted(REMEDIATION_ACTIONS)}


# ---------------------------------------------------------------------------
# CLI

COMMANDS = {
    "version": cmd_version,
    "host.overview": cmd_host_overview,
    "host.disk": cmd_host_disk,
    "host.processes": cmd_host_processes,
    "host.services": cmd_host_services,
    "host.journal": cmd_host_journal,
    "net.ports": cmd_net_ports,
    "net.dns": cmd_net_dns,
    "net.reach": cmd_net_reach,
    "net.route": cmd_net_route,
    "security.logins": cmd_security_logins,
    "security.auth-events": cmd_security_auth_events,
    "security.users": cmd_security_users,
    "security.updates": cmd_security_updates,
    "change.recent": cmd_change_recent,
    "k8s.context": cmd_k8s_context,
    "k8s.nodes": cmd_k8s_nodes,
    "k8s.pods": cmd_k8s_pods,
    "k8s.describe": cmd_k8s_describe,
    "k8s.logs": cmd_k8s_logs,
    "k8s.events": cmd_k8s_events,
    "k8s.rollout": cmd_k8s_rollout,
    "triage.host": cmd_triage_host,
    "triage.k8s": cmd_triage_k8s,
    "remediate.plan": cmd_remediate_plan,
    "remediate.apply": cmd_remediate_apply,
}

# Option definitions shared by the CLI parser and the manifest generator.
# name -> (flag, valueType, help)
OPTIONS = {
    "timeoutMs": ("--timeout-ms", "integer", "Per-tool timeout in milliseconds (max 60000)."),
    "toolRoot": ("--tool-root", "path:input", "Directory that must contain every external tool (for pinned or test toolchains)."),
    "since": ("--since", "string", "Relative window such as -30m, -2h, -1d."),
    "tail": ("--tail", "integer", "Maximum lines to return."),
    "top": ("--top", "integer", "Maximum items to return."),
    "unit": ("--unit", "string", "systemd unit name."),
    "priority": ("--priority", "string", "journal priority (emerg..debug or 0..7)."),
    "pattern": ("--pattern", "string", "Regular expression filter applied to returned lines."),
    "sort": ("--sort", "enum:cpu,mem", "Process sort key."),
    "warnPercent": ("--warn-percent", "integer", "Usage percentage that raises a finding."),
    "name": ("--name", "string", "Object or host name."),
    "host": ("--host", "string", "Host name or IP literal."),
    "port": ("--port", "integer", "TCP port."),
    "tls": ("--tls", "boolean", "Perform a TLS handshake and inspect the certificate."),
    "root": ("--root", "path:input", "Directory to scan (must be within the allowlisted roots)."),
    "kubeconfig": ("--kubeconfig", "path:input", "kubeconfig file to pass to kubectl."),
    "context": ("--context", "string", "kubectl context name."),
    "namespace": ("--namespace", "string", "Kubernetes namespace."),
    "allNamespaces": ("--all-namespaces", "boolean", "Query every namespace."),
    "selector": ("--selector", "string", "Label selector."),
    "kind": ("--kind", "string", "Kubernetes resource kind."),
    "container": ("--container", "string", "Container name inside the pod."),
    "previous": ("--previous", "boolean", "Read logs from the previous container instance."),
    "allTypes": ("--all-types", "boolean", "Include Normal events as well as Warning events."),
    "usage": ("--usage", "boolean", "Include kubectl top nodes usage when metrics are available."),
    "stateRoot": ("--state-root", "path:inout", "Owner-only directory that stores remediation plans."),
    "action": ("--action", "enum:service.restart,k8s.rollout.restart,k8s.pod.delete", "Allowlisted remediation action."),
    "target": ("--target", "string", "Unit name, kind/name, or pod name for the action."),
    "reason": ("--reason", "string", "Why this remediation is proposed (recorded in the plan)."),
    "planId": ("--plan-id", "string", "Plan id returned by remediate.plan."),
    "confirm": ("--confirm", "string", "Exact confirmationChallenge from the approved plan."),
}
COMMON = ("timeoutMs", "toolRoot")
COMMAND_OPTIONS: dict[str, tuple[tuple[str, bool], ...]] = {
    "version": (),
    "host.overview": (),
    "host.disk": (("warnPercent", True),),
    "host.processes": (("sort", True), ("top", True)),
    "host.services": (("unit", True),),
    "host.journal": (("since", True), ("tail", True), ("unit", True), ("priority", True), ("pattern", True)),
    "net.ports": (),
    "net.dns": (("name", False),),
    "net.reach": (("host", False), ("port", False), ("tls", True)),
    "net.route": (),
    "security.logins": (("top", True),),
    "security.auth-events": (("since", True), ("tail", True)),
    "security.users": (),
    "security.updates": (),
    "change.recent": (("since", True), ("root", True), ("top", True)),
    "k8s.context": (("kubeconfig", True), ("context", True)),
    "k8s.nodes": (("kubeconfig", True), ("context", True), ("usage", True)),
    "k8s.pods": (("kubeconfig", True), ("context", True), ("namespace", True), ("allNamespaces", True), ("selector", True), ("top", True)),
    "k8s.describe": (("kubeconfig", True), ("context", True), ("namespace", True), ("kind", False), ("name", False)),
    "k8s.logs": (("kubeconfig", True), ("context", True), ("namespace", True), ("name", False), ("container", True), ("tail", True), ("since", True), ("previous", True), ("pattern", True)),
    "k8s.events": (("kubeconfig", True), ("context", True), ("namespace", True), ("allNamespaces", True), ("allTypes", True), ("top", True)),
    "k8s.rollout": (("kubeconfig", True), ("context", True), ("namespace", True), ("kind", True), ("name", False)),
    "triage.host": (("since", True), ("tail", True), ("warnPercent", True)),
    "triage.k8s": (("kubeconfig", True), ("context", True), ("namespace", True), ("allNamespaces", True), ("top", True)),
    "remediate.plan": (("stateRoot", False), ("action", False), ("target", False), ("namespace", True), ("reason", True), ("kubeconfig", True), ("context", True)),
    "remediate.apply": (("stateRoot", False), ("planId", False), ("confirm", False), ("kubeconfig", True), ("context", True)),
}
SAFETY = {
    "remediate.plan": ["readOnly", "writeSafe"],
    "remediate.apply": ["writeSafe", "externalSideEffect"],
}
DEFAULTS: dict[str, Any] = {name: None for name in OPTIONS}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ops-troubleshooting", description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, options in COMMAND_OPTIONS.items():
        sub = subparsers.add_parser(command)
        for name in COMMON + tuple(option for option, _ in options):
            flag, value_type, help_text = OPTIONS[name]
            dest = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), name)
            if value_type == "boolean":
                sub.add_argument(flag, dest=dest, action="store_true", help=help_text)
            elif value_type == "integer":
                sub.add_argument(flag, dest=dest, type=int, help=help_text)
            elif value_type.startswith("enum:"):
                sub.add_argument(flag, dest=dest, choices=value_type.split(":", 1)[1].split(","), help=help_text)
            else:
                sub.add_argument(flag, dest=dest, help=help_text)
    return parser


def fill_defaults(args: argparse.Namespace) -> argparse.Namespace:
    for name in OPTIONS:
        dest = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), name)
        if not hasattr(args, dest):
            setattr(args, dest, False if OPTIONS[name][1] == "boolean" else None)
    return args


def require_options(args: argparse.Namespace) -> None:
    for name, optional in COMMAND_OPTIONS[args.command]:
        dest = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), name)
        if not optional and getattr(args, dest) in (None, ""):
            raise Fail("MISSING_OPTION", f"{OPTIONS[name][0]} is required for {args.command}")


def normalize_argv(argv: list[str]) -> list[str]:
    """Join option values that begin with '-' (such as --since -30m) so argparse does not read them as flags."""
    flags = {definition[0] for definition in OPTIONS.values()}
    result: list[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in flags and index + 1 < len(argv) and argv[index + 1].startswith("-") and argv[index + 1] not in flags:
            result.append(f"{item}={argv[index + 1]}")
            index += 2
            continue
        result.append(item)
        index += 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = fill_defaults(parser.parse_args(normalize_argv(list(sys.argv[1:] if argv is None else argv))))
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        print(json.dumps({"ok": False, "schemaVersion": SCHEMA_VERSION, "command": None, "error": {"code": "INVALID_ARGUMENTS", "message": "arguments could not be parsed"}, "effects": []}, separators=(",", ":")))
        return EXIT["invalid"]
    ctx: Context | None = None
    try:
        require_options(args)
        ctx = Context(args)
        data = COMMANDS[args.command](ctx)
        effects = data.pop("effects", [])
        data["evidence"] = ctx.evidence()
        response = {"ok": True, "schemaVersion": SCHEMA_VERSION, "command": args.command, "data": data, "effects": effects}
        code = EXIT["ok"]
    except Fail as error:
        details = dict(error.details)
        effects = details.pop("effects", [])
        response = {"ok": False, "schemaVersion": SCHEMA_VERSION, "command": args.command, "error": {"code": error.code, "message": error.message, "kind": error.kind, "details": details}, "effects": effects}
        if ctx is not None:
            response["data"] = {"evidence": ctx.evidence()}
        code = EXIT.get(error.kind, EXIT["failed"])
    print(json.dumps(response, separators=(",", ":"), ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
